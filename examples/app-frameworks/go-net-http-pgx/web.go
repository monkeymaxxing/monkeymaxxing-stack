package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"golang.org/x/crypto/bcrypt"
	"io"
	"mime"
	"net/http"
	"net/mail"
	"strconv"
	"strings"
	"time"
)

//go:generate go tool templ generate

const sessionCookie = "__Host-portal_session"

type pageData struct {
	Records   []record
	Documents []document
	Reports   []report
}

type app struct {
	database *pgxpool.Pool
	storage  *objectStorage
	origin   string
}
type record struct {
	ID          int64  `json:"id"`
	Title       string `json:"title"`
	Description string `json:"description"`
}
type document struct {
	ID       int64  `json:"id"`
	FileName string `json:"file_name"`
	SHA256   string `json:"sha256"`
}
type report struct {
	ID     int64   `json:"id"`
	Output *string `json:"output"`
}

func (a *app) routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", a.health)
	mux.HandleFunc("GET /{$}", a.home)
	mux.HandleFunc("POST /register", a.register)
	mux.HandleFunc("POST /login", a.login)
	mux.HandleFunc("POST /logout", a.logout)
	mux.HandleFunc("GET /records", a.records)
	mux.HandleFunc("POST /records", a.createRecord)
	mux.HandleFunc("POST /records/{id}/update", a.updateRecord)
	mux.HandleFunc("POST /records/{id}/delete", a.deleteRecord)
	mux.HandleFunc("GET /documents", a.documents)
	mux.HandleFunc("POST /documents", a.upload)
	mux.HandleFunc("GET /documents/{id}", a.download)
	mux.HandleFunc("GET /reports", a.reports)
	mux.HandleFunc("POST /reports", a.queueReport)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("Content-Security-Policy", "default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
		if r.Method != "GET" && r.Method != "HEAD" && r.Header.Get("Origin") != a.origin {
			http.Error(w, "request origin refused", 403)
			return
		}
		r.Body = http.MaxBytesReader(w, r.Body, maxUploadBytes+64*1024)
		ctx, cancel := context.WithTimeout(r.Context(), 12*time.Second)
		defer cancel()
		mux.ServeHTTP(w, r.WithContext(ctx))
	})
}
func fail(w http.ResponseWriter) { http.Error(w, "service unavailable", 503) }
func respond(w http.ResponseWriter, r *http.Request, value any, status int) {
	if strings.Contains(r.Header.Get("Accept"), "application/json") {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		json.NewEncoder(w).Encode(value)
	} else {
		http.Redirect(w, r, "/", 303)
	}
}
func (a *app) health(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()
	r = r.WithContext(ctx)
	var ready bool
	err := a.database.QueryRow(r.Context(), "select exists(select 1 from schema_migrations where version=$1)", latestMigration).Scan(&ready)
	if err != nil || !ready {
		fail(w)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ok", "release": release})
}
func (a *app) home(w http.ResponseWriter, r *http.Request) {
	cookie, err := r.Cookie(sessionCookie)
	if err != nil || cookie.Value == "" {
		landingPage().Render(r.Context(), w)
		return
	}
	owner, ok := a.owner(w, r)
	if !ok {
		return
	}
	rows, err := a.database.Query(r.Context(), "select id,title,description from records where account_id=$1 order by id", owner)
	if err != nil {
		fail(w)
		return
	}
	defer rows.Close()
	records := []record{}
	for rows.Next() {
		var item record
		if rows.Scan(&item.ID, &item.Title, &item.Description) != nil {
			fail(w)
			return
		}
		records = append(records, item)
	}
	if rows.Err() != nil {
		fail(w)
		return
	}
	rows.Close()
	data := pageData{Records: records}
	documentRows, err := a.database.Query(r.Context(), "select id,file_name,sha256 from documents where account_id=$1 order by id", owner)
	if err != nil {
		fail(w)
		return
	}
	for documentRows.Next() {
		var item document
		if documentRows.Scan(&item.ID, &item.FileName, &item.SHA256) != nil {
			documentRows.Close()
			fail(w)
			return
		}
		data.Documents = append(data.Documents, item)
	}
	err = documentRows.Err()
	documentRows.Close()
	if err != nil {
		fail(w)
		return
	}
	reportRows, err := a.database.Query(r.Context(), "select id,output from report_jobs where account_id=$1 order by id", owner)
	if err != nil {
		fail(w)
		return
	}
	for reportRows.Next() {
		var item report
		if reportRows.Scan(&item.ID, &item.Output) != nil {
			reportRows.Close()
			fail(w)
			return
		}
		data.Reports = append(data.Reports, item)
	}
	err = reportRows.Err()
	reportRows.Close()
	if err != nil {
		fail(w)
		return
	}
	portalPage(data).Render(r.Context(), w)
}
func credentialsForm(r *http.Request) (string, string, error) {
	if err := r.ParseForm(); err != nil {
		return "", "", err
	}
	email := strings.ToLower(strings.TrimSpace(r.FormValue("email")))
	password := r.FormValue("password")
	parsed, err := mail.ParseAddress(email)
	if err != nil || parsed.Address != email || len(email) > 254 || len(password) < 12 || len(password) > 72 {
		return "", "", errors.New("invalid email or password")
	}
	return email, password, nil
}
func (a *app) register(w http.ResponseWriter, r *http.Request) {
	email, password, err := credentialsForm(r)
	if err != nil {
		http.Error(w, "use an email and a password of 12 to 72 bytes", 400)
		return
	}
	hash, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		fail(w)
		return
	}
	var owner int64
	err = a.database.QueryRow(r.Context(), "insert into accounts(email,password_hash) values($1,$2) on conflict(email) do nothing returning id", email, string(hash)).Scan(&owner)
	if errors.Is(err, pgx.ErrNoRows) {
		http.Error(w, "account unavailable", 409)
		return
	}
	if err != nil {
		fail(w)
		return
	}
	a.newSession(w, r, owner)
}
func (a *app) login(w http.ResponseWriter, r *http.Request) {
	email, password, err := credentialsForm(r)
	if err != nil {
		http.Error(w, "invalid login", 401)
		return
	}
	var owner int64
	var hash string
	err = a.database.QueryRow(r.Context(), "select id,password_hash from accounts where email=$1", email).Scan(&owner, &hash)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		fail(w)
		return
	}
	if err != nil || bcrypt.CompareHashAndPassword([]byte(hash), []byte(password)) != nil {
		http.Error(w, "invalid login", 401)
		return
	}
	a.newSession(w, r, owner)
}
func newToken() string {
	data := make([]byte, 32)
	if _, err := rand.Read(data); err != nil {
		panic("random source unavailable")
	}
	return hex.EncodeToString(data)
}
func (a *app) newSession(w http.ResponseWriter, r *http.Request, owner int64) {
	token := newToken()
	tx, err := a.database.Begin(r.Context())
	if err != nil {
		fail(w)
		return
	}
	defer tx.Rollback(r.Context())
	if old, err := r.Cookie(sessionCookie); err == nil {
		if _, err = tx.Exec(r.Context(), "delete from sessions where token_hash=$1", digest([]byte(old.Value))); err != nil {
			fail(w)
			return
		}
	}
	if _, err = tx.Exec(r.Context(), "insert into sessions values($1,$2,now()+interval '7 days')", digest([]byte(token)), owner); err != nil {
		fail(w)
		return
	}
	if err = tx.Commit(r.Context()); err != nil {
		fail(w)
		return
	}
	http.SetCookie(w, &http.Cookie{Name: sessionCookie, Value: token, Path: "/", Secure: true, HttpOnly: true, SameSite: http.SameSiteLaxMode, MaxAge: 7 * 24 * 3600})
	respond(w, r, map[string]int64{"account_id": owner}, 200)
}
func (a *app) owner(w http.ResponseWriter, r *http.Request) (int64, bool) {
	cookie, err := r.Cookie(sessionCookie)
	if err != nil {
		http.Error(w, "login required", 401)
		return 0, false
	}
	var owner int64
	err = a.database.QueryRow(r.Context(), "select account_id from sessions where token_hash=$1 and expires_at>now()", digest([]byte(cookie.Value))).Scan(&owner)
	if errors.Is(err, pgx.ErrNoRows) {
		http.Error(w, "login required", 401)
		return 0, false
	}
	if err != nil {
		fail(w)
		return 0, false
	}
	return owner, true
}
func (a *app) logout(w http.ResponseWriter, r *http.Request) {
	cookie, err := r.Cookie(sessionCookie)
	if err == nil {
		if _, err = a.database.Exec(r.Context(), "delete from sessions where token_hash=$1", digest([]byte(cookie.Value))); err != nil {
			fail(w)
			return
		}
	}
	http.SetCookie(w, &http.Cookie{Name: sessionCookie, Value: "", Path: "/", Secure: true, HttpOnly: true, SameSite: http.SameSiteLaxMode, MaxAge: -1})
	respond(w, r, map[string]bool{"logged_out": true}, 200)
}
func (a *app) records(w http.ResponseWriter, r *http.Request) {
	owner, ok := a.owner(w, r)
	if !ok {
		return
	}
	rows, err := a.database.Query(r.Context(), "select id,title,description from records where account_id=$1 order by id", owner)
	if err != nil {
		fail(w)
		return
	}
	defer rows.Close()
	items := []record{}
	for rows.Next() {
		var item record
		if rows.Scan(&item.ID, &item.Title, &item.Description) != nil {
			fail(w)
			return
		}
		items = append(items, item)
	}
	if rows.Err() != nil {
		fail(w)
		return
	}
	respond(w, r, items, 200)
}
func recordForm(r *http.Request) (string, string, bool) {
	if r.ParseForm() != nil {
		return "", "", false
	}
	title := strings.TrimSpace(r.FormValue("title"))
	description := r.FormValue("description")
	return title, description, len(title) > 0 && len([]rune(title)) <= 200 && len(description) <= 10000
}
func (a *app) createRecord(w http.ResponseWriter, r *http.Request) {
	owner, ok := a.owner(w, r)
	if !ok {
		return
	}
	title, description, valid := recordForm(r)
	if !valid {
		http.Error(w, "invalid title or description", 400)
		return
	}
	var id int64
	if a.database.QueryRow(r.Context(), "insert into records(account_id,title,description) values($1,$2,$3) returning id", owner, title, description).Scan(&id) != nil {
		fail(w)
		return
	}
	respond(w, r, map[string]int64{"id": id}, 201)
}
func (a *app) updateRecord(w http.ResponseWriter, r *http.Request) { a.changeRecord(w, r, false) }
func (a *app) deleteRecord(w http.ResponseWriter, r *http.Request) { a.changeRecord(w, r, true) }
func (a *app) changeRecord(w http.ResponseWriter, r *http.Request, remove bool) {
	owner, ok := a.owner(w, r)
	if !ok {
		return
	}
	id, err := strconv.ParseInt(r.PathValue("id"), 10, 64)
	if err != nil {
		http.NotFound(w, r)
		return
	}
	sql := "delete from records where id=$1 and account_id=$2"
	args := []any{id, owner}
	if !remove {
		title, description, valid := recordForm(r)
		if !valid {
			http.Error(w, "invalid title or description", 400)
			return
		}
		sql = "update records set title=$3,description=$4 where id=$1 and account_id=$2"
		args = append(args, title, description)
	}
	result, err := a.database.Exec(r.Context(), sql, args...)
	if err != nil {
		fail(w)
		return
	}
	if result.RowsAffected() == 0 {
		http.NotFound(w, r)
		return
	}
	respond(w, r, map[string]int64{"id": id}, 200)
}
func (a *app) documents(w http.ResponseWriter, r *http.Request) {
	owner, ok := a.owner(w, r)
	if !ok {
		return
	}
	rows, err := a.database.Query(r.Context(), "select id,file_name,sha256 from documents where account_id=$1 order by id", owner)
	if err != nil {
		fail(w)
		return
	}
	defer rows.Close()
	items := []document{}
	for rows.Next() {
		var item document
		if rows.Scan(&item.ID, &item.FileName, &item.SHA256) != nil {
			fail(w)
			return
		}
		items = append(items, item)
	}
	if rows.Err() != nil {
		fail(w)
		return
	}
	respond(w, r, items, 200)
}
func (a *app) upload(w http.ResponseWriter, r *http.Request) {
	owner, ok := a.owner(w, r)
	if !ok {
		return
	}
	reader, err := r.MultipartReader()
	if err != nil {
		http.Error(w, "multipart file required", 400)
		return
	}
	part, err := reader.NextPart()
	if err != nil || part.FormName() != "file" || part.FileName() == "" {
		http.Error(w, "file required", 400)
		return
	}
	defer part.Close()
	data, err := io.ReadAll(io.LimitReader(part, maxUploadBytes+1))
	if err != nil || len(data) > maxUploadBytes {
		http.Error(w, "file exceeds 5 MiB or cannot be read", 413)
		return
	}
	key := "documents/" + newToken()
	if a.storage.put(r.Context(), key, data) != nil {
		fail(w)
		return
	}
	var id int64
	if a.database.QueryRow(r.Context(), "insert into documents(account_id,object_key,file_name,sha256,byte_count) values($1,$2,$3,$4,$5) returning id", owner, key, part.FileName(), digest(data), len(data)).Scan(&id) != nil {
		// Never delete after uncertain commit: the row may have committed.
		fail(w)
		return
	}
	respond(w, r, map[string]int64{"id": id}, 201)
}
func (a *app) download(w http.ResponseWriter, r *http.Request) {
	owner, ok := a.owner(w, r)
	if !ok {
		return
	}
	id, err := strconv.ParseInt(r.PathValue("id"), 10, 64)
	if err != nil {
		http.NotFound(w, r)
		return
	}
	var key, name, hash string
	err = a.database.QueryRow(r.Context(), "select object_key,file_name,sha256 from documents where id=$1 and account_id=$2", id, owner).Scan(&key, &name, &hash)
	if errors.Is(err, pgx.ErrNoRows) {
		http.NotFound(w, r)
		return
	}
	if err != nil {
		fail(w)
		return
	}
	data, err := a.storage.get(r.Context(), key)
	if err != nil || digest(data) != hash {
		fail(w)
		return
	}
	w.Header().Set("Content-Type", "application/octet-stream")
	w.Header().Set("Content-Disposition", mime.FormatMediaType("attachment", map[string]string{"filename": name}))
	w.Write(data)
}
func (a *app) reports(w http.ResponseWriter, r *http.Request) {
	owner, ok := a.owner(w, r)
	if !ok {
		return
	}
	rows, err := a.database.Query(r.Context(), "select id,output from report_jobs where account_id=$1 order by id", owner)
	if err != nil {
		fail(w)
		return
	}
	defer rows.Close()
	items := []report{}
	for rows.Next() {
		var item report
		if rows.Scan(&item.ID, &item.Output) != nil {
			fail(w)
			return
		}
		items = append(items, item)
	}
	if rows.Err() != nil {
		fail(w)
		return
	}
	respond(w, r, items, 200)
}
func (a *app) queueReport(w http.ResponseWriter, r *http.Request) {
	owner, ok := a.owner(w, r)
	if !ok {
		return
	}
	var id int64
	if a.database.QueryRow(r.Context(), "insert into report_jobs(account_id) values($1) returning id", owner).Scan(&id) != nil {
		fail(w)
		return
	}
	respond(w, r, map[string]int64{"id": id}, 201)
}
