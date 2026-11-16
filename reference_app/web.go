package main

import (
	"context"
	_ "embed"
	"fmt"
	"html/template"
	"io/fs"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// runWebServer serves the pages on the port in PORT until the stop signal,
// then answers the requests in flight and exits.
func runWebServer() error {
	port, err := requiredSetting("PORT")
	if err != nil {
		return err
	}
	database, err := openDatabase()
	if err != nil {
		return err
	}
	defer database.Close()
	databaseForReads, err := openReadDatabase()
	if err != nil {
		return err
	}
	defer databaseForReads.Close()
	hostName, err := os.Hostname()
	if err != nil {
		return err
	}

	server := &http.Server{
		// Every IP address of the server: Caddy on each app server reaches
		// this web container at this server's private IP address.
		Addr:              ":" + port,
		Handler:           newWebHandler(database, databaseForReads, hostName, os.DirFS(assetDirectory)),
		ReadHeaderTimeout: 10 * time.Second,
	}
	stop, stopListening := signal.NotifyContext(context.Background(), syscall.SIGTERM, os.Interrupt)
	defer stopListening()
	serverFailed := make(chan error, 1)
	go func() { serverFailed <- server.ListenAndServe() }()
	log.Printf("web: release %s on %s, listening on port %s", release, hostName, port)

	select {
	case err := <-serverFailed:
		return err
	case <-stop.Done():
	}
	log.Print("web: stopping once the requests in flight are answered")
	// The container's stop timeout is 30 seconds. A request still running
	// after 25 seconds is cut off, so the program exits before Podman kills it.
	shutdownContext, cancel := context.WithTimeout(context.Background(), 25*time.Second)
	defer cancel()
	if err := server.Shutdown(shutdownContext); err != nil {
		return err
	}
	log.Print("web: stopped")
	return nil
}

// webPages holds what the pages read: the database, the pool for reads that
// may be a moment behind it, the host name of this server, and the asset
// files.
type webPages struct {
	database         *pgxpool.Pool
	databaseForReads *pgxpool.Pool
	hostName         string
	assetFiles       fs.FS
}

// newWebHandler sends each request to its page. Every answer says whether
// Cloudflare may keep a copy: Cache-Control: no-store, unless the page sets
// its own. The stack's Cache Rule makes Cloudflare follow the app's
// Cache-Control, and it may cache an answer that has none.
func newWebHandler(database, databaseForReads *pgxpool.Pool, hostName string, assetFiles fs.FS) http.Handler {
	pages := &webPages{database: database, databaseForReads: databaseForReads, hostName: hostName, assetFiles: assetFiles}
	routes := http.NewServeMux()
	routes.HandleFunc("GET /{$}", pages.showHomePage)
	routes.HandleFunc("POST /jobs", pages.addJob)
	routes.HandleFunc("GET /cached", pages.showCachedPage)
	routes.HandleFunc("GET /up", pages.checkHealth)
	routes.HandleFunc("GET /assets/{name}", pages.serveAsset)
	// Refuses a form that another site's page sends (cross-site request forgery).
	protectedRoutes := http.NewCrossOriginProtection().Handler(routes)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		protectedRoutes.ServeHTTP(w, r)
	})
}

type homePage struct {
	Release           string
	StylesheetPath    string
	AppServerHostName string
	RequestArrivedOn  string // the IP address the request arrived on, with its server name
	DatabaseServer    string
	DatabaseProblem   string
	PageViewCount     int64
	CountedOn         string // the database server that counted the page views, and whether it is a replica
	Jobs              []jobRow
	PageViews         []pageViewRow
}

type jobRow struct {
	ID       int64
	Added    string
	Finished string
}

type pageViewRow struct {
	ViewedAt          string
	AppServerHostName string
	DatabaseServer    string
}

// showHomePage records this view, then shows which app server and which
// database server answered, the newest jobs, and the newest page views.
func (pages *webPages) showHomePage(w http.ResponseWriter, r *http.Request) {
	// Every view is recorded and shows the newest rows, so Cloudflare must
	// never answer it from a copy.
	w.Header().Set("Cache-Control", "private, no-store")
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	defer cancel()

	page := homePage{
		Release:           release,
		StylesheetPath:    "/assets/" + stylesheetFileName,
		AppServerHostName: pages.hostName,
	}
	localAddress := r.Context().Value(http.LocalAddrContextKey).(net.Addr)
	localIPAddress, _, _ := net.SplitHostPort(localAddress.String())
	page.RequestArrivedOn = describeIPAddress(ctx, localIPAddress)

	status := http.StatusOK
	if err := pages.readDatabase(ctx, &page); err != nil {
		log.Printf("web: home page: %v", err)
		page.DatabaseProblem = err.Error()
		status = http.StatusServiceUnavailable
	}
	render(w, status, "home", page)
}

// readDatabase records the page view and reads the rows the home page shows.
func (pages *webPages) readDatabase(ctx context.Context, page *homePage) error {
	var databaseIPAddress string
	err := pages.database.QueryRow(ctx, `
		insert into page_views (app_server_host_name, database_server_ip_address)
		values ($1, inet_server_addr())
		returning coalesce(host(database_server_ip_address), '')`,
		pages.hostName).Scan(&databaseIPAddress)
	if err != nil {
		return fmt.Errorf("recording the page view: %w", err)
	}
	page.DatabaseServer = describeIPAddress(ctx, databaseIPAddress)

	// A count may be a moment behind, so it is read through
	// DATABASE_READ_URL, from a replica when one answers. A replica that
	// restarts, as in the weekly update window, breaks the connection the
	// read was on, so the read is asked once more on the primary's pool:
	// the page view is already written, and the page shouldn't fail.
	var countedOnIPAddress string
	var countedOnReplica bool
	countPageViews := `
		select count(*), coalesce(host(inet_server_addr()), ''), pg_is_in_recovery()
		from page_views`
	err = pages.databaseForReads.QueryRow(ctx, countPageViews).Scan(&page.PageViewCount, &countedOnIPAddress, &countedOnReplica)
	if err != nil {
		err = pages.database.QueryRow(ctx, countPageViews).Scan(&page.PageViewCount, &countedOnIPAddress, &countedOnReplica)
	}
	if err != nil {
		return fmt.Errorf("counting the page views: %w", err)
	}
	page.CountedOn = describeIPAddress(ctx, countedOnIPAddress) + ", the primary"
	if countedOnReplica {
		page.CountedOn = describeIPAddress(ctx, countedOnIPAddress) + ", a replica"
	}

	jobs, err := pages.database.Query(ctx, `
		select id, added_at, added_on_server, finished_at, coalesce(finished_on_server, '')
		from jobs
		order by id desc
		limit 10`)
	if err != nil {
		return fmt.Errorf("reading the jobs: %w", err)
	}
	page.Jobs, err = pgx.CollectRows(jobs, func(row pgx.CollectableRow) (jobRow, error) {
		var job jobRow
		var addedAt time.Time
		var finishedAt *time.Time // empty until the job has finished
		var addedOnServer, finishedOnServer string
		err := row.Scan(&job.ID, &addedAt, &addedOnServer, &finishedAt, &finishedOnServer)
		job.Added = formatTime(addedAt) + " on " + addedOnServer
		job.Finished = "not yet"
		if finishedAt != nil {
			job.Finished = formatTime(*finishedAt) + " on " + finishedOnServer
		}
		return job, err
	})
	if err != nil {
		return fmt.Errorf("reading the jobs: %w", err)
	}

	pageViews, err := pages.database.Query(ctx, `
		select viewed_at, app_server_host_name, coalesce(host(database_server_ip_address), '')
		from page_views
		order by id desc
		limit 10`)
	if err != nil {
		return fmt.Errorf("reading the page views: %w", err)
	}
	page.PageViews, err = pgx.CollectRows(pageViews, func(row pgx.CollectableRow) (pageViewRow, error) {
		var view pageViewRow
		var viewedAt time.Time
		var databaseIPAddress string
		err := row.Scan(&viewedAt, &view.AppServerHostName, &databaseIPAddress)
		view.ViewedAt = formatTime(viewedAt)
		view.DatabaseServer = describeIPAddress(ctx, databaseIPAddress)
		return view, err
	})
	if err != nil {
		return fmt.Errorf("reading the page views: %w", err)
	}
	return nil
}

// addJob adds a job to the queue, for a job worker to run.
func (pages *webPages) addJob(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	defer cancel()
	if _, err := pages.database.Exec(ctx,
		"insert into jobs (added_on_server) values ($1)", pages.hostName); err != nil {
		log.Printf("web: adding a job: %v", err)
		http.Error(w, "The job wasn't added: the database didn't answer.", http.StatusServiceUnavailable)
		return
	}
	// Back to the home page, which lists the new job. Reloading it adds no
	// second job.
	http.Redirect(w, r, "/", http.StatusSeeOther)
}

type cachedPage struct {
	Release           string
	StylesheetPath    string
	AppServerHostName string
	RenderedAt        string
}

// showCachedPage shows when and on which app server it was rendered.
// Cloudflare may keep a copy for 60 seconds and answer from it, so while
// the copy lasts, every reload shows the same time and server.
func (pages *webPages) showCachedPage(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Cache-Control", "public, max-age=60")
	render(w, http.StatusOK, "cached", cachedPage{
		Release:           release,
		StylesheetPath:    "/assets/" + stylesheetFileName,
		AppServerHostName: pages.hostName,
		RenderedAt:        formatTime(time.Now()),
	})
}

// checkHealth is the health URL, /up. It answers 200 only when this web
// container can serve requests: the database answers, and the newest
// migration this release knows is applied. Otherwise it answers 503.
// Caddy asks every 5 seconds, waits 3 seconds for the answer, and sends
// requests only to web containers whose answer is 200; a deploy switches
// to a new release only once its health URL answers 200.
func (pages *webPages) checkHealth(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()
	var applied bool
	err := pages.database.QueryRow(ctx,
		"select exists (select 1 from schema_migrations where version = $1)", newestMigrationVersion,
	).Scan(&applied)
	switch {
	case err != nil:
		// The details stay in the log: anyone on the internet can ask /up.
		log.Printf("web: health check: %v", err)
		http.Error(w, "not ready: the database check failed", http.StatusServiceUnavailable)
	case !applied:
		http.Error(w, "not ready: migration "+newestMigrationVersion+" isn't applied", http.StatusServiceUnavailable)
	default:
		fmt.Fprintln(w, "up")
	}
}

// serveAsset serves one file of the asset directory. Its name carries a
// fingerprint of its content, so the file under that name never changes,
// and a browser or Cloudflare may keep it for a year.
func (pages *webPages) serveAsset(w http.ResponseWriter, r *http.Request) {
	name := r.PathValue("name")
	if _, err := fs.Stat(pages.assetFiles, name); err != nil {
		// Still no-store: a file missing for a moment, such as while a
		// deploy switches releases, must not stay missing in Cloudflare.
		http.NotFound(w, r)
		return
	}
	w.Header().Set("Cache-Control", "public, max-age=31536000, immutable")
	http.ServeFileFS(w, r, pages.assetFiles, name)
}

// describeIPAddress returns an IP address with the server name that a
// reverse lookup finds for it, such as "10.20.2.1 (db01)". On the stack's
// servers, the name comes from /etc/hosts, which lists every server's
// private IP address.
func describeIPAddress(ctx context.Context, ipAddress string) string {
	if ipAddress == "" {
		return "none: the connection is through a Unix socket"
	}
	names, err := net.DefaultResolver.LookupAddr(ctx, ipAddress)
	if err != nil || len(names) == 0 {
		return ipAddress
	}
	return fmt.Sprintf("%s (%s)", ipAddress, strings.TrimSuffix(names[0], "."))
}

func formatTime(moment time.Time) string {
	return moment.UTC().Format("2006-01-02 15:04:05 UTC")
}

//go:embed pages.html
var pagesHTML string

var pageTemplates = template.Must(template.New("pages").Parse(pagesHTML))

func render(w http.ResponseWriter, status int, pageName string, data any) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(status)
	if err := pageTemplates.ExecuteTemplate(w, pageName, data); err != nil {
		log.Printf("web: rendering the %s page: %v", pageName, err)
	}
}
