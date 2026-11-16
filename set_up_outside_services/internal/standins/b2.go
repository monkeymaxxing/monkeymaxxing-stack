// Package standins imitates the parts of Backblaze B2's native API and
// Cloudflare's API that set-up-outside-services uses, for its unit tests and
// for the desk test on a disposable server. Each handler enforces the
// request shape and the permission its cited documentation describes, and
// refuses what the real API would refuse. A pass against a stand-in is never
// evidence that the real API behaves the same: the live check at the real
// providers is a separate step (docs/design.md, "Account and secret setup
// from the systems desk").
package standins

import (
	"crypto/rand"
	"crypto/sha1"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"
)

// AllB2Capabilities is what a master key has.
var AllB2Capabilities = []string{"listKeys", "writeKeys", "deleteKeys", "listAllBucketNames", "listBuckets", "readBuckets", "writeBuckets", "deleteBuckets",
	"readBucketRetentions", "writeBucketRetentions", "readBucketEncryption", "writeBucketEncryption", "listFiles", "readFiles", "shareFiles", "writeFiles",
	"deleteFiles", "readFileLegalHolds", "writeFileLegalHolds", "readFileRetentions", "writeFileRetentions", "bypassGovernance", "readBucketReplications", "writeBucketReplications"}

type B2Key struct {
	ID             string   `json:"applicationKeyId"`
	Secret         string   `json:"applicationKey"`
	Name           string   `json:"keyName"`
	Capabilities   []string `json:"capabilities"`
	BucketIDs      []string `json:"bucketIds"`
	DeletedByCalls bool     `json:"deleted"`
}

type B2Retention struct {
	Mode   *string `json:"mode"`
	Period *struct {
		Duration int    `json:"duration"`
		Unit     string `json:"unit"`
	} `json:"period"`
}

type B2LifecycleRule struct {
	FileNamePrefix            string `json:"fileNamePrefix"`
	DaysFromHidingToDeleting  *int   `json:"daysFromHidingToDeleting"`
	DaysFromUploadingToHiding *int   `json:"daysFromUploadingToHiding"`
}

type B2Bucket struct {
	ID               string            `json:"bucketId"`
	Name             string            `json:"bucketName"`
	Type             string            `json:"bucketType"`
	FileLockEnabled  bool              `json:"fileLockEnabled"`
	DefaultRetention B2Retention       `json:"defaultRetention"`
	LifecycleRules   []B2LifecycleRule `json:"lifecycleRules"`
}

type B2File struct {
	ID          string `json:"fileId"`
	Name        string `json:"fileName"`
	BucketID    string `json:"bucketId"`
	Mode        string `json:"retentionMode"`
	RetainUntil int64  `json:"retainUntilTimestamp"`
	Hidden      bool   `json:"hidden"`
	Deleted     bool   `json:"deleted"`
}

// B2 is a stand-in Backblaze account.
type B2 struct {
	mu        sync.Mutex
	BaseURL   string // where the stand-in answers, set by the caller
	AccountID string
	S3APIURL  string
	Keys      []*B2Key
	Buckets   []*B2Bucket
	Files     []*B2File
	// TakenBucketNames are names another Backblaze account has.
	TakenBucketNames map[string]bool
	// Failures make the next call of a name fail: "drop" closes the
	// connection after doing the work, "malformed" answers bad JSON.
	Failures map[string]string
	// IgnoreLocks makes the account delete locked files, as a broken lock
	// would, so a test can show that the lock check catches it.
	IgnoreLocks bool
	Calls       []string
	tokens      map[string]*B2Key // authorization token -> key
	uploads     map[string]string // upload token -> bucket ID
	Now         func() time.Time
	nextNumber  int
}

func NewB2(masterKeyID, masterKey string) *B2 {
	b := &B2{AccountID: "b2account0001", S3APIURL: "https://s3.eu-central-003.backblazeb2.com", TakenBucketNames: map[string]bool{},
		Failures: map[string]string{}, tokens: map[string]*B2Key{}, uploads: map[string]string{}, Now: time.Now}
	b.Keys = append(b.Keys, &B2Key{ID: masterKeyID, Secret: masterKey, Name: "master", Capabilities: AllB2Capabilities})
	return b
}

func random(n int) string {
	bytes := make([]byte, n)
	_, _ = rand.Read(bytes)
	return hex.EncodeToString(bytes)
}

type b2Refusal struct {
	status        int
	code, message string
}

func writeB2(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}

func (b *B2) refuse(w http.ResponseWriter, r b2Refusal) {
	writeB2(w, r.status, map[string]any{"status": r.status, "code": r.code, "message": r.message})
}

func decodeStrict(r *http.Request, into any) error {
	decoder := json.NewDecoder(io.LimitReader(r.Body, 1<<20))
	decoder.DisallowUnknownFields()
	return decoder.Decode(into)
}

// ServeHTTP answers B2's native API v4 at /b2api/v4/NAME and uploads at
// /upload/BUCKET_ID.
func (b *B2) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	b.mu.Lock()
	defer b.mu.Unlock()
	name := strings.TrimPrefix(r.URL.Path, "/b2api/v4/")
	if strings.HasPrefix(r.URL.Path, "/upload/") {
		name = "b2_upload_file"
	}
	b.Calls = append(b.Calls, name)
	failure := b.Failures[name]
	delete(b.Failures, name)
	if failure == "malformed" {
		w.Header().Set("Content-Type", "application/json")
		_, _ = io.WriteString(w, `{"this is not`)
		return
	}
	var result any
	var refusal *b2Refusal
	switch name {
	case "b2_authorize_account":
		result, refusal = b.authorize(r)
	case "b2_upload_file":
		result, refusal = b.upload(r)
	default:
		key := b.tokens[r.Header.Get("Authorization")]
		if key == nil {
			refusal = &b2Refusal{401, "bad_auth_token", "Invalid authorization token"}
		} else if r.Method != http.MethodPost {
			refusal = &b2Refusal{405, "method_not_allowed", "use POST"}
		} else {
			result, refusal = b.call(name, key, r)
		}
	}
	if refusal != nil {
		b.refuse(w, *refusal)
		return
	}
	if failure == "drop" {
		// The work is done, but the answer never arrives.
		if hijacker, ok := w.(http.Hijacker); ok {
			if connection, _, err := hijacker.Hijack(); err == nil {
				connection.Close()
				return
			}
		}
	}
	writeB2(w, http.StatusOK, result)
}

func (b *B2) has(key *B2Key, capability string) bool {
	for _, c := range key.Capabilities {
		if c == capability {
			return true
		}
	}
	return false
}

// https://www.backblaze.com/apidocs/b2-authorize-account
func (b *B2) authorize(r *http.Request) (any, *b2Refusal) {
	id, secret, ok := r.BasicAuth()
	if r.Method != http.MethodGet || !ok {
		return nil, &b2Refusal{400, "bad_request", "use GET with basic authentication"}
	}
	for _, key := range b.Keys {
		if key.ID == id && key.Secret == secret && !key.DeletedByCalls {
			token := "auth_" + random(16)
			b.tokens[token] = key
			return map[string]any{"accountId": b.AccountID, "authorizationToken": token, "apiInfo": map[string]any{"storageApi": map[string]any{
				"apiUrl": b.BaseURL, "downloadUrl": b.BaseURL, "s3ApiUrl": b.S3APIURL, "absoluteMinimumPartSize": 5000000, "recommendedPartSize": 100000000,
				"allowed": map[string]any{"capabilities": key.Capabilities, "buckets": nil, "namePrefix": nil}}}}, nil
		}
	}
	return nil, &b2Refusal{401, "unauthorized", "The applicationKeyId and/or the applicationKey are wrong."}
}

func (b *B2) bucketByID(id string) *B2Bucket {
	for _, bucket := range b.Buckets {
		if bucket.ID == id {
			return bucket
		}
	}
	return nil
}

func (b *B2) bucketView(key *B2Key, bucket *B2Bucket) map[string]any {
	lock := map[string]any{"isClientAuthorizedToRead": b.has(key, "readBucketRetentions"), "value": nil}
	if b.has(key, "readBucketRetentions") {
		lock["value"] = map[string]any{"isFileLockEnabled": bucket.FileLockEnabled, "defaultRetention": bucket.DefaultRetention}
	}
	rules := bucket.LifecycleRules
	if rules == nil {
		rules = []B2LifecycleRule{}
	}
	return map[string]any{"accountId": b.AccountID, "bucketId": bucket.ID, "bucketName": bucket.Name, "bucketType": bucket.Type,
		"fileLockConfiguration": lock, "lifecycleRules": rules, "options": []string{"s3"}, "revision": 1}
}

var bucketNamePattern = regexp.MustCompile(`^[A-Za-z0-9-]{6,63}$`)
var keyNamePattern = regexp.MustCompile(`^[A-Za-z0-9-]{1,100}$`)

func validRetention(retention B2Retention) bool {
	if retention.Mode == nil || (*retention.Mode != "compliance" && *retention.Mode != "governance") || retention.Period == nil {
		return false
	}
	return retention.Period.Duration > 0 && (retention.Period.Unit == "days" || retention.Period.Unit == "years")
}

func validLifecycle(rules []B2LifecycleRule) bool {
	for _, rule := range rules {
		if rule.DaysFromHidingToDeleting != nil && *rule.DaysFromHidingToDeleting < 1 {
			return false
		}
	}
	return true
}

func (b *B2) call(name string, key *B2Key, r *http.Request) (any, *b2Refusal) {
	need := map[string]string{"b2_list_buckets": "listBuckets", "b2_create_bucket": "writeBuckets", "b2_update_bucket": "writeBuckets",
		"b2_get_upload_url": "writeFiles", "b2_get_file_info": "readFiles", "b2_delete_file_version": "deleteFiles", "b2_hide_file": "writeFiles",
		"b2_create_key": "writeKeys", "b2_list_keys": "listKeys", "b2_delete_key": "deleteKeys"}[name]
	if need == "" {
		return nil, &b2Refusal{404, "not_found", "unknown call " + name}
	}
	if name != "b2_get_file_info" && !b.has(key, need) {
		return nil, &b2Refusal{401, "unauthorized", "not entitled: " + need}
	}
	bad := &b2Refusal{400, "bad_request", "the request body does not match " + name}
	switch name {
	// https://www.backblaze.com/apidocs/b2-list-buckets
	case "b2_list_buckets":
		var body struct {
			AccountID  string `json:"accountId"`
			BucketName string `json:"bucketName"`
			BucketID   string `json:"bucketId"`
		}
		if decodeStrict(r, &body) != nil || body.AccountID != b.AccountID {
			return nil, bad
		}
		buckets := []any{}
		for _, bucket := range b.Buckets {
			if (body.BucketName == "" || bucket.Name == body.BucketName) && (body.BucketID == "" || bucket.ID == body.BucketID) {
				buckets = append(buckets, b.bucketView(key, bucket))
			}
		}
		return map[string]any{"buckets": buckets}, nil
	// https://www.backblaze.com/apidocs/b2-create-bucket: no defaultRetention in the request
	case "b2_create_bucket":
		var body struct {
			AccountID       string            `json:"accountId"`
			BucketName      string            `json:"bucketName"`
			BucketType      string            `json:"bucketType"`
			FileLockEnabled bool              `json:"fileLockEnabled"`
			LifecycleRules  []B2LifecycleRule `json:"lifecycleRules"`
		}
		if decodeStrict(r, &body) != nil || body.AccountID != b.AccountID || !bucketNamePattern.MatchString(body.BucketName) ||
			strings.HasPrefix(body.BucketName, "b2-") || (body.BucketType != "allPrivate" && body.BucketType != "allPublic") || !validLifecycle(body.LifecycleRules) {
			return nil, bad
		}
		if body.FileLockEnabled && !b.has(key, "writeBucketRetentions") {
			return nil, &b2Refusal{401, "unauthorized", "not entitled: writeBucketRetentions"}
		}
		if b.TakenBucketNames[body.BucketName] {
			return nil, &b2Refusal{400, "duplicate_bucket_name", "Bucket name is already in use."}
		}
		for _, bucket := range b.Buckets {
			if bucket.Name == body.BucketName {
				return nil, &b2Refusal{400, "duplicate_bucket_name", "Bucket name is already in use."}
			}
		}
		b.nextNumber++
		bucket := &B2Bucket{ID: fmt.Sprintf("bucket%04d", b.nextNumber), Name: body.BucketName, Type: body.BucketType,
			FileLockEnabled: body.FileLockEnabled, LifecycleRules: body.LifecycleRules}
		b.Buckets = append(b.Buckets, bucket)
		return b.bucketView(key, bucket), nil
	// https://www.backblaze.com/apidocs/b2-update-bucket
	case "b2_update_bucket":
		var body struct {
			AccountID        string             `json:"accountId"`
			BucketID         string             `json:"bucketId"`
			FileLockEnabled  *bool              `json:"fileLockEnabled"`
			DefaultRetention *B2Retention       `json:"defaultRetention"`
			LifecycleRules   *[]B2LifecycleRule `json:"lifecycleRules"`
		}
		if decodeStrict(r, &body) != nil || body.AccountID != b.AccountID {
			return nil, bad
		}
		bucket := b.bucketByID(body.BucketID)
		if bucket == nil {
			return nil, &b2Refusal{400, "bad_bucket_id", "no such bucket"}
		}
		if (body.FileLockEnabled != nil || body.DefaultRetention != nil) && !b.has(key, "writeBucketRetentions") {
			return nil, &b2Refusal{401, "unauthorized", "not entitled: writeBucketRetentions"}
		}
		if body.FileLockEnabled != nil {
			if !*body.FileLockEnabled && bucket.FileLockEnabled {
				return nil, &b2Refusal{400, "bad_request", "Object Lock cannot be turned off"}
			}
			bucket.FileLockEnabled = bucket.FileLockEnabled || *body.FileLockEnabled
		}
		if body.DefaultRetention != nil {
			if !bucket.FileLockEnabled || !validRetention(*body.DefaultRetention) {
				return nil, &b2Refusal{400, "bad_request", "default retention needs Object Lock and a valid mode and period"}
			}
			bucket.DefaultRetention = *body.DefaultRetention
		}
		if body.LifecycleRules != nil {
			if !validLifecycle(*body.LifecycleRules) {
				return nil, bad
			}
			bucket.LifecycleRules = *body.LifecycleRules
		}
		return b.bucketView(key, bucket), nil
	// https://www.backblaze.com/apidocs/b2-get-upload-url
	case "b2_get_upload_url":
		var body struct {
			BucketID string `json:"bucketId"`
		}
		if decodeStrict(r, &body) != nil || b.bucketByID(body.BucketID) == nil {
			return nil, bad
		}
		token := "upload_" + random(12)
		b.uploads[token] = body.BucketID
		return map[string]any{"bucketId": body.BucketID, "uploadUrl": b.BaseURL + "/upload/" + body.BucketID, "authorizationToken": token}, nil
	// https://www.backblaze.com/apidocs/b2-get-file-info
	case "b2_get_file_info":
		var body struct {
			FileID string `json:"fileId"`
		}
		if decodeStrict(r, &body) != nil {
			return nil, bad
		}
		for _, file := range b.Files {
			if file.ID == body.FileID && !file.Deleted {
				retention := map[string]any{"isClientAuthorizedToRead": b.has(key, "readFileRetentions"), "value": nil}
				if b.has(key, "readFileRetentions") {
					value := map[string]any{"mode": nil, "retainUntilTimestamp": nil}
					if file.Mode != "" {
						value = map[string]any{"mode": file.Mode, "retainUntilTimestamp": file.RetainUntil}
					}
					retention["value"] = value
				}
				return map[string]any{"fileId": file.ID, "fileName": file.Name, "fileRetention": retention}, nil
			}
		}
		return nil, &b2Refusal{404, "not_found", "file not found"}
	// https://www.backblaze.com/apidocs/b2-delete-file-version
	case "b2_delete_file_version":
		var body struct {
			FileName string `json:"fileName"`
			FileID   string `json:"fileId"`
		}
		if decodeStrict(r, &body) != nil {
			return nil, bad
		}
		for _, file := range b.Files {
			if file.ID == body.FileID && file.Name == body.FileName && !file.Deleted {
				if file.Mode == "compliance" && file.RetainUntil > b.Now().UnixMilli() && !b.IgnoreLocks {
					return nil, &b2Refusal{401, "access_denied", "The file is locked by Object Lock."}
				}
				file.Deleted = true
				return map[string]any{"fileId": file.ID, "fileName": file.Name}, nil
			}
		}
		return nil, &b2Refusal{400, "file_not_present", "file not present"}
	// https://www.backblaze.com/apidocs/b2-hide-file
	case "b2_hide_file":
		var body struct {
			BucketID string `json:"bucketId"`
			FileName string `json:"fileName"`
		}
		if decodeStrict(r, &body) != nil {
			return nil, bad
		}
		for _, file := range b.Files {
			if file.BucketID == body.BucketID && file.Name == body.FileName && !file.Deleted {
				file.Hidden = true
				return map[string]any{"fileId": "hide_" + file.ID, "fileName": file.Name, "action": "hide"}, nil
			}
		}
		return nil, &b2Refusal{400, "no_such_file", "no such file"}
	// https://www.backblaze.com/apidocs/b2-create-key: bucketIds in v4
	case "b2_create_key":
		var body struct {
			AccountID    string   `json:"accountId"`
			KeyName      string   `json:"keyName"`
			Capabilities []string `json:"capabilities"`
			BucketIDs    []string `json:"bucketIds"`
		}
		if decodeStrict(r, &body) != nil || body.AccountID != b.AccountID || !keyNamePattern.MatchString(body.KeyName) || len(body.Capabilities) == 0 {
			return nil, bad
		}
		for _, capability := range body.Capabilities {
			known := false
			for _, c := range AllB2Capabilities {
				known = known || c == capability
			}
			if !known {
				return nil, &b2Refusal{400, "bad_request", "unknown capability " + capability}
			}
		}
		for _, id := range body.BucketIDs {
			if b.bucketByID(id) == nil {
				return nil, &b2Refusal{400, "bad_bucket_id", "no such bucket " + id}
			}
		}
		b.nextNumber++
		newKey := &B2Key{ID: fmt.Sprintf("003%019d", b.nextNumber), Secret: "K003" + random(14), Name: body.KeyName,
			Capabilities: append([]string(nil), body.Capabilities...), BucketIDs: append([]string(nil), body.BucketIDs...)}
		b.Keys = append(b.Keys, newKey)
		return map[string]any{"accountId": b.AccountID, "applicationKeyId": newKey.ID, "applicationKey": newKey.Secret, "keyName": newKey.Name,
			"capabilities": newKey.Capabilities, "bucketIds": newKey.BucketIDs, "expirationTimestamp": nil, "namePrefix": nil, "options": []string{"s3"}}, nil
	// https://www.backblaze.com/apidocs/b2-list-keys
	case "b2_list_keys":
		var body struct {
			AccountID             string `json:"accountId"`
			MaxKeyCount           int    `json:"maxKeyCount"`
			StartApplicationKeyID string `json:"startApplicationKeyId"`
		}
		if decodeStrict(r, &body) != nil || body.AccountID != b.AccountID || body.MaxKeyCount > 10000 {
			return nil, bad
		}
		keys := []any{}
		for _, k := range b.Keys {
			if !k.DeletedByCalls && k.Name != "master" && k.ID >= body.StartApplicationKeyID {
				keys = append(keys, map[string]any{"keyName": k.Name, "applicationKeyId": k.ID, "capabilities": k.Capabilities, "bucketIds": k.BucketIDs, "accountId": b.AccountID})
			}
		}
		return map[string]any{"keys": keys, "nextApplicationKeyId": nil}, nil
	// https://www.backblaze.com/apidocs/b2-delete-key
	case "b2_delete_key":
		var body struct {
			ApplicationKeyID string `json:"applicationKeyId"`
		}
		if decodeStrict(r, &body) != nil {
			return nil, bad
		}
		for _, k := range b.Keys {
			if k.ID == body.ApplicationKeyID && !k.DeletedByCalls && k.Name != "master" {
				k.DeletedByCalls = true
				return map[string]any{"applicationKeyId": k.ID, "keyName": k.Name}, nil
			}
		}
		return nil, &b2Refusal{400, "bad_request", "no such key"}
	}
	return nil, bad
}

// https://www.backblaze.com/apidocs/b2-upload-file: the SHA-1 is required,
// and a file in a bucket with default retention gets that retention.
func (b *B2) upload(r *http.Request) (any, *b2Refusal) {
	bucketID := strings.TrimPrefix(r.URL.Path, "/upload/")
	if b.uploads[r.Header.Get("Authorization")] != bucketID {
		return nil, &b2Refusal{401, "bad_auth_token", "Invalid upload authorization token"}
	}
	content, _ := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	checksum := sha1.Sum(content)
	name, err := url.PathUnescape(r.Header.Get("X-Bz-File-Name"))
	if err != nil || name == "" || r.Header.Get("Content-Type") == "" {
		return nil, &b2Refusal{400, "bad_request", "missing file name or content type"}
	}
	if r.Header.Get("X-Bz-Content-Sha1") != hex.EncodeToString(checksum[:]) {
		return nil, &b2Refusal{400, "bad_request", "Checksum did not match data received"}
	}
	bucket := b.bucketByID(bucketID)
	b.nextNumber++
	file := &B2File{ID: fmt.Sprintf("4_z%s_f%06d", bucketID, b.nextNumber), Name: name, BucketID: bucketID}
	if bucket.FileLockEnabled && bucket.DefaultRetention.Mode != nil && bucket.DefaultRetention.Period != nil {
		file.Mode = *bucket.DefaultRetention.Mode
		days := bucket.DefaultRetention.Period.Duration
		if bucket.DefaultRetention.Period.Unit == "years" {
			days *= 365
		}
		file.RetainUntil = b.Now().Add(time.Duration(days) * 24 * time.Hour).UnixMilli()
	}
	b.Files = append(b.Files, file)
	return map[string]any{"fileId": file.ID, "fileName": file.Name, "bucketId": bucketID, "contentSha1": hex.EncodeToString(checksum[:]), "action": "upload"}, nil
}

// LiveKeysNamed lists the keys of that name that were not deleted.
func (b *B2) LiveKeysNamed(name string) []*B2Key {
	b.mu.Lock()
	defer b.mu.Unlock()
	var keys []*B2Key
	for _, key := range b.Keys {
		if key.Name == name && !key.DeletedByCalls {
			keys = append(keys, key)
		}
	}
	sort.Slice(keys, func(i, j int) bool { return keys[i].ID < keys[j].ID })
	return keys
}

// Snapshot is the account's state, for checks in tests.
func (b *B2) Snapshot() map[string]any {
	b.mu.Lock()
	defer b.mu.Unlock()
	return map[string]any{"buckets": b.Buckets, "keys": b.Keys, "files": b.Files, "calls": b.Calls}
}

func (b *B2) Lock()   { b.mu.Lock() }
func (b *B2) Unlock() { b.mu.Unlock() }
