package main

import (
	"bytes"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/monkeymaxxing/monkeymaxxing-stack/set_up_outside_services/internal/standins"
)

const testAccountID = "a1b2c3d4e5f60718293a4b5c6d7e8f90"

// settingsYAML is a team's settings, as the template has them, with the
// team's own names. {{STAGING}} and the uploads lines vary per test.
const settingsYAML = `project_name: acme_systems
vars:
  cloudflare_account_id: "a1b2c3d4e5f60718293a4b5c6d7e8f90"
  status_page_host_name: status.example.org
  systems_desk_provider_api_url: PROVIDER_URL
  systems_desk_provider_api_authentication: token_in_a_header
  triage_agent_coding_agent: claude_code
  apps:
    shop:
      secrets_from_vault: [SECRET_KEY_BASE, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY]
      production_uploads_r2_bucket: UPLOADS_R2_BUCKET
      staging_uploads_r2_bucket: acme-shop-staging-uploads
      production_uploads_r2_key_variables:
        access_key_id: R2_ACCESS_KEY_ID
        secret_access_key: R2_SECRET_ACCESS_KEY
  backups:
    keep_database_backups_for_days: 30
    lock_backups_against_deletion_for_days: 20
    keep_prior_file_versions_in_buckets_for_days: 25
    b2_s3_endpoint: s3.eu-central-003.backblazeb2.com
    production_bucket: acme-systems-backups
    uploads_bucket: acme-systems-uploads-backups
    uploads_backup_runs_on: [util_server]
    mmhotline_backup_replica_url: "s3://acme-mmhotline-backup/mmhotline?endpoint=https://s3.eu-central-003.backblazeb2.com&region=eu-central-003"
`

type fakeVault struct {
	values map[string]string
	// referenced are the keys the playbooks read, for missing().
	referenced []string
	// file, when set, is the vault's file in a Git checkout.
	file string
	// failOn makes setting that key fail, as MMX refuses a key.
	failOn map[string]bool
	sets   []string
	// fileWhenListed is the vault file's text when keys() last ran.
	fileWhenListed string
}

func (v *fakeVault) keys() (map[string]bool, error) {
	if v.file != "" {
		text, _ := os.ReadFile(v.file)
		v.fileWhenListed = string(text)
	}
	keys := map[string]bool{}
	for key := range v.values {
		keys[key] = true
	}
	return keys, nil
}

func (v *fakeVault) set(key, value string, replace bool) error {
	if v.failOn[key] {
		return fmt.Errorf("mmx secrets set %s failed: the vault is not writable", key)
	}
	if _, ok := v.values[key]; ok && !replace {
		return fmt.Errorf("mmx secrets set %s failed: the key exists", key)
	}
	v.values[key] = value
	v.sets = append(v.sets, key)
	if v.file != "" {
		// The vault file changes on each save, as MMX's does, so a test sees
		// what a commit holds. It holds names only.
		text, _ := os.ReadFile(v.file)
		if err := os.WriteFile(v.file, append(text, []byte(key+"\n")...), 0o644); err != nil {
			return err
		}
	}
	return nil
}

func (v *fakeVault) addRandom(key string, length int, replace bool) error {
	return v.set(key, strings.Repeat("r", length)+"-"+key, replace)
}

func (v *fakeVault) missing() ([]string, error) {
	var missing []string
	for _, key := range v.referenced {
		if _, ok := v.values[key]; !ok {
			missing = append(missing, key)
		}
	}
	return missing, nil
}

type harness struct {
	t          *testing.T
	e          *environment
	out        *bytes.Buffer
	vault      *fakeVault
	b2         *standins.B2
	cloudflare *standins.Cloudflare
	answers    []string
	provider   *httptest.Server
	proxy      map[string]string
	// git runs git in a directory; origin is the repository's bare origin.
	git    func(directory string, arguments ...string) string
	origin string
	// linkTokens counts the link tokens the person made, for unique values.
	linkTokens int
}

const (
	masterKeyID   = "0031234567890ab0000000001"
	masterKey     = "K003masterkeyvaluemasterkeyvalue"
	providerToken = "provider-token-value-000001"
)

func newHarness(t *testing.T, staging, uploads bool) *harness {
	t.Helper()
	h := &harness{t: t, out: &bytes.Buffer{}, vault: &fakeVault{values: map[string]string{}, failOn: map[string]bool{}}, proxy: map[string]string{}}
	h.b2 = standins.NewB2(masterKeyID, masterKey)
	b2Server := httptest.NewServer(h.b2)
	t.Cleanup(b2Server.Close)
	h.b2.BaseURL = b2Server.URL
	h.cloudflare = standins.NewCloudflare(testAccountID)
	cloudflareServer := httptest.NewServer(h.cloudflare)
	t.Cleanup(cloudflareServer.Close)
	h.provider = httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if (r.Header.Get("Authorization") != "Bearer "+providerToken && r.Header.Get("X-Auth-Token") != providerToken) || r.URL.Path != "/v1/servers" {
			w.WriteHeader(http.StatusUnauthorized)
			return
		}
		fmt.Fprint(w, `{"servers": []}`)
	}))
	t.Cleanup(h.provider.Close)
	savedClient := httpClient
	httpClient = h.provider.Client()
	t.Cleanup(func() { httpClient = savedClient })

	directory := t.TempDir()
	text := strings.ReplaceAll(settingsYAML, "PROVIDER_URL", h.provider.URL+"/v1/")
	if uploads {
		text = strings.ReplaceAll(text, "UPLOADS_R2_BUCKET", "acme-shop-uploads")
	} else {
		text = strings.ReplaceAll(text, "UPLOADS_R2_BUCKET", `""`)
	}
	writeFile(t, filepath.Join(directory, projectSettingsFile), text)
	inventory := "groups:\n  staging_server:\n    nodes: []\n"
	if staging {
		inventory = "groups:\n  staging_server:\n    nodes: [staging01]\n"
	}
	writeFile(t, filepath.Join(directory, inventoryFile), inventory)
	t.Setenv("MMX_VAULT_PASSWORD_FILE", "/nonexistent/used-by-mmx-only")
	h.e = &environment{
		directory: directory, home: t.TempDir(), person: "alex", out: h.out, vault: h.vault,
		prompt: func(label string) (string, error) {
			if len(h.answers) == 0 {
				return "", errors.New("unexpected prompt " + label)
			}
			answer := h.answers[0]
			h.answers = h.answers[1:]
			return answer, nil
		},
		// No answer, as when the person presses Ctrl-C or stdin ends; a test
		// that presses Enter replaces it.
		confirm:        func(label string) (string, error) { return "", errors.New("no answer was entered") },
		b2AuthorizeURL: b2Server.URL + "/b2api/v4/b2_authorize_account", cloudflareAPIURL: cloudflareServer.URL + "/client/v4",
		providerGuideAPIAddresses: []string{h.provider.URL + "/v1/"},
		now:                       time.Now,
		runMMHotlineStatusPageSetUp: func(accountID, hostName, token string) (statusPageSetUp, error) {
			// MMHotline gets the person's desk token, which must be live.
			desk := h.cloudflare.LiveTokensNamed("acme_systems: " + h.e.person + "'s systems desk sets up Cloudflare")
			if len(desk) != 1 || desk[0].Value != token || accountID != testAccountID {
				return statusPageSetUp{}, errors.New("MMHotline got the wrong token or account")
			}
			h.cloudflare.Lock()
			h.cloudflare.R2Buckets["mmhotline-status-status-example-org-0a1b2c3d"] = true
			h.cloudflare.Unlock()
			return statusPageSetUp{BucketName: "mmhotline-status-status-example-org-0a1b2c3d",
				R2BucketURL: "https://" + accountID + ".r2.cloudflarestorage.com/mmhotline-status-status-example-org-0a1b2c3d"}, nil
		},
		writeProxyFile: func(request proxyFileRequest) error {
			if request.API == "cloudflare" && request.CloudflareAccountID != testAccountID {
				return errors.New("the root step needs the account ID to check the token")
			}
			h.proxy[request.API] = request.TokenHeader + request.Token
			return nil
		},
	}
	// Every run that saves keys commits and pushes the vault itself, so
	// each test's directory is a signed checkout with an origin.
	h.signedSecretsRepository()
	return h
}

// commitAll commits a test's own edit to the repository and pushes it, as
// the coding agent does before the person runs a command.
func (h *harness) commitAll(message string) {
	h.t.Helper()
	h.git(h.e.directory, "add", "-A")
	h.git(h.e.directory, "commit", "--quiet", "-m", message)
	h.git(h.e.directory, "push", "--quiet")
}

func writeFile(t *testing.T, path, text string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(text), 0o644); err != nil {
		t.Fatal(err)
	}
}

func (h *harness) runBackblaze() error {
	h.answers = []string{masterKeyID, masterKey}
	return runBackblaze(h.e, nil)
}

// addLinkToken makes the token the person makes with the command's link,
// which holds only Account API Tokens Write, and returns its value.
func (h *harness) addLinkToken() string {
	h.linkTokens++
	value := fmt.Sprintf("link-token-value-%08d", h.linkTokens)
	h.cloudflare.AddToken("acme_systems: "+h.e.person+" makes tokens with set-up-outside-services, deleted after the run", value, false, standins.PermissionAccountAPITokensWrite)
	return value
}

// runCloudflare runs the command as the person does: with a new link token
// at the prompt, since each run deletes its link token.
func (h *harness) runCloudflare(arguments ...string) error {
	h.answers = []string{h.addLinkToken()}
	return runCloudflare(h.e, arguments)
}

func (h *harness) count(calls []string, name string) int {
	n := 0
	for _, call := range calls {
		if call == name {
			n++
		}
	}
	return n
}

// requireNoSecretInOutput fails when any vault value, or a master credential,
// shows in what the person's terminal printed.
func (h *harness) requireNoSecretInOutput(extra ...string) {
	h.t.Helper()
	output := h.out.String()
	for key, value := range h.vault.values {
		if lowered := strings.ToLower(key); strings.Contains(output, value) && !strings.HasSuffix(lowered, "_key_id") {
			h.t.Fatalf("the output shows the value of %s", key)
		}
	}
	for _, secret := range extra {
		if strings.Contains(output, secret) {
			h.t.Fatalf("the output shows a master credential")
		}
	}
}

func bucketNamed(b *standins.B2, name string) *standins.B2Bucket {
	b.Lock()
	defer b.Unlock()
	for _, bucket := range b.Buckets {
		if bucket.Name == name {
			return bucket
		}
	}
	return nil
}

func TestBackblazeCreatesLockedBucketsAndLimitedKeysAndSavesThem(t *testing.T) {
	h := newHarness(t, true, true)
	if err := h.runBackblaze(); err != nil {
		t.Fatalf("backblaze: %v\n%s", err, h.out)
	}
	// staging01 keeps no backups: staging holds only seed data.
	if bucketNamed(h.b2, "acme-systems-staging-backups") != nil || len(h.b2.LiveKeysNamed("acme-systems-staging-pgbackrest-write")) != 0 {
		t.Fatal("with staging01, no staging backup bucket and no staging backup key")
	}
	for _, name := range []string{"acme-systems-backups", "acme-systems-uploads-backups"} {
		bucket := bucketNamed(h.b2, name)
		if bucket == nil || !bucket.FileLockEnabled || bucket.Type != "allPrivate" || *bucket.DefaultRetention.Mode != "compliance" ||
			bucket.DefaultRetention.Period.Duration != 20 || bucket.DefaultRetention.Period.Unit != "days" {
			t.Fatalf("%s is not private with the 20-day compliance lock of the settings: %+v", name, bucket)
		}
		if len(bucket.LifecycleRules) != 1 || *bucket.LifecycleRules[0].DaysFromHidingToDeleting != 25 || bucket.LifecycleRules[0].DaysFromUploadingToHiding != nil {
			t.Fatalf("%s lacks the 25-day hidden-version rule of the settings", name)
		}
	}
	mmhotline := bucketNamed(h.b2, "acme-mmhotline-backup")
	if mmhotline == nil || mmhotline.FileLockEnabled {
		t.Fatalf("MMHotline's bucket must exist without Object Lock: %+v", mmhotline)
	}
	if len(mmhotline.LifecycleRules) != 1 || *mmhotline.LifecycleRules[0].DaysFromHidingToDeleting != 25 {
		t.Fatalf("MMHotline's bucket must keep prior versions for the settings' 25 days: %+v", mmhotline.LifecycleRules)
	}
	expected := map[string][]string{
		"acme-systems-pgbackrest-write":        {"listBuckets", "listFiles", "readFiles", "writeFiles", "deleteFiles"},
		"acme-systems-restore-drill-read-only": {"listBuckets", "listFiles", "readFiles"},
		"acme-systems-util01-uploads-copy":     {"listBuckets", "listFiles", "readFiles", "writeFiles"},
		"acme-systems-mmhotline-backup":        {"listBuckets", "listFiles", "readFiles", "writeFiles", "deleteFiles"},
	}
	vaultNames := map[string][2]string{
		"acme-systems-pgbackrest-write":        {"pgbackrest_b2_write_key_id", "pgbackrest_b2_write_application_key"},
		"acme-systems-restore-drill-read-only": {"pgbackrest_b2_read_only_key_id", "pgbackrest_b2_read_only_application_key"},
		"acme-systems-util01-uploads-copy":     {"uploads_backup_b2_write_key_id", "uploads_backup_b2_write_application_key"},
		"acme-systems-mmhotline-backup":        {"mmhotline_backup_access_key_id", "mmhotline_backup_secret_access_key"},
	}
	for name, capabilities := range expected {
		keys := h.b2.LiveKeysNamed(name)
		if len(keys) != 1 || !sameSet(keys[0].Capabilities, capabilities) || len(keys[0].BucketIDs) != 1 {
			t.Fatalf("%s: want one key with %v on one bucket, got %+v", name, capabilities, keys)
		}
		names := vaultNames[name]
		if h.vault.values[names[0]] != keys[0].ID || h.vault.values[names[1]] != keys[0].Secret {
			t.Fatalf("%s is not in the vault as %v", name, names)
		}
	}
	// The uploads key reaches only the uploads bucket.
	if h.b2.LiveKeysNamed("acme-systems-util01-uploads-copy")[0].BucketIDs[0] != bucketNamed(h.b2, "acme-systems-uploads-backups").ID {
		t.Fatal("the uploads key must reach the uploads bucket only")
	}
	// One lock check, a refused deletion, and a hidden test file per locked bucket.
	calls := h.b2.Snapshot()["calls"].([]string)
	if h.count(calls, "b2_upload_file") != 2 || h.count(calls, "b2_delete_file_version") != 2 || h.count(calls, "b2_hide_file") != 2 {
		t.Fatalf("want two lock checks, production's database bucket and the uploads bucket, got calls %v", calls)
	}
	// Every lock check happens before its bucket's first key.
	firstKey, lastCheck := -1, -1
	for i, call := range calls {
		if call == "b2_create_key" && firstKey < 0 {
			firstKey = i
		}
		if call == "b2_delete_file_version" && lastCheck < 0 {
			lastCheck = i
		}
	}
	if lastCheck > firstKey {
		t.Fatal("a key was made before its bucket's lock check")
	}
	h.requireNoSecretInOutput(masterKey)
	if !strings.Contains(h.out.String(), b2BucketsPage) {
		t.Fatal("the output must link to the buckets page")
	}
}

func TestBackblazeRerunCreatesNothingTwice(t *testing.T) {
	h := newHarness(t, true, true)
	if err := h.runBackblaze(); err != nil {
		t.Fatal(err)
	}
	before := len(h.b2.Snapshot()["keys"].([]*standins.B2Key))
	sets := len(h.vault.sets)
	if err := h.runBackblaze(); err != nil {
		t.Fatalf("rerun: %v\n%s", err, h.out)
	}
	calls := h.b2.Snapshot()["calls"].([]string)
	if after := len(h.b2.Snapshot()["keys"].([]*standins.B2Key)); after != before || len(h.vault.sets) != sets {
		t.Fatalf("a rerun made keys or vault changes: %d keys before, %d after", before, after)
	}
	if h.count(calls, "b2_create_bucket") != 3 || h.count(calls, "b2_upload_file") != 2 {
		t.Fatalf("a rerun created buckets or test files again: %v", calls)
	}
}

func TestBackblazeMakesOnlyWhatTheSystemUses(t *testing.T) {
	h := newHarness(t, false, false)
	if err := h.runBackblaze(); err != nil {
		t.Fatal(err)
	}
	if bucketNamed(h.b2, "acme-systems-uploads-backups") != nil {
		t.Fatal("without uploads, no uploads bucket")
	}
	for _, key := range []string{"uploads_backup_b2_write_key_id"} {
		if _, ok := h.vault.values[key]; ok {
			t.Fatalf("%s must not be made", key)
		}
	}
}

func TestBackblazeRefusesAKeyThatCannotDeleteBeforeChangingAnything(t *testing.T) {
	h := newHarness(t, false, false)
	h.b2.Keys = append(h.b2.Keys, &standins.B2Key{ID: "limited-id", Secret: "limited-secret", Name: "limited", Capabilities: []string{"listBuckets", "writeBuckets", "writeKeys", "listFiles", "writeFiles"}})
	h.answers = []string{"limited-id", "limited-secret"}
	err := runBackblaze(h.e, nil)
	if err == nil || !strings.Contains(err.Error(), "deleteFiles") || !strings.Contains(err.Error(), "master application key") {
		t.Fatalf("want a refusal naming deleteFiles, got %v", err)
	}
	if len(h.b2.Buckets) != 0 {
		t.Fatal("nothing may change before the key is accepted")
	}
}

func TestBackblazeStopsWhenTheLockDoesNotHold(t *testing.T) {
	h := newHarness(t, false, false)
	h.b2.IgnoreLocks = true
	err := h.runBackblaze()
	if err == nil || !strings.Contains(err.Error(), "deleted the locked test file") {
		t.Fatalf("want a failed lock check, got %v", err)
	}
	if len(h.b2.LiveKeysNamed("acme-systems-pgbackrest-write")) != 0 || len(h.vault.values) != 0 {
		t.Fatal("no key may be made for a bucket whose lock failed")
	}
}

func TestBackblazeRevokesOnlyTheNewKeyWhenTheVaultFails(t *testing.T) {
	h := newHarness(t, false, false)
	h.vault.failOn["pgbackrest_b2_write_application_key"] = true
	err := h.runBackblaze()
	if err == nil || !strings.Contains(err.Error(), "revoked the new Backblaze key acme-systems-pgbackrest-write") {
		t.Fatalf("want the issued-but-unsaved outcome, got %v", err)
	}
	if len(h.b2.LiveKeysNamed("acme-systems-pgbackrest-write")) != 0 {
		t.Fatal("the new key must be revoked")
	}
	if !strings.Contains(err.Error(), "got pgbackrest_b2_write_key_id") {
		t.Fatalf("the message must say what the vault got: %v", err)
	}
	// The fix: the vault works again. The rerun completes the half-saved pair.
	delete(h.vault.failOn, "pgbackrest_b2_write_application_key")
	if err := h.runBackblaze(); err != nil {
		t.Fatalf("rerun: %v", err)
	}
	keys := h.b2.LiveKeysNamed("acme-systems-pgbackrest-write")
	if len(keys) != 1 || h.vault.values["pgbackrest_b2_write_key_id"] != keys[0].ID || h.vault.values["pgbackrest_b2_write_application_key"] != keys[0].Secret {
		t.Fatal("the rerun must save one new, complete pair")
	}
}

func TestBackblazeNeverRevokesASavedWorkingKey(t *testing.T) {
	h := newHarness(t, false, false)
	if err := h.runBackblaze(); err != nil {
		t.Fatal(err)
	}
	working := h.b2.LiveKeysNamed("acme-systems-pgbackrest-write")[0].ID
	h.vault.failOn["pgbackrest_b2_write_key_id"] = true
	if err := h.runBackblaze(); err != nil {
		t.Fatalf("a rerun with every key saved writes nothing, so it cannot fail: %v", err)
	}
	if keys := h.b2.LiveKeysNamed("acme-systems-pgbackrest-write"); len(keys) != 1 || keys[0].ID != working {
		t.Fatal("the working key must stay")
	}
}

func TestBackblazeRerunAfterALostAnswerLeavesOneKey(t *testing.T) {
	h := newHarness(t, false, false)
	h.b2.Failures["b2_create_key"] = "drop"
	err := h.runBackblaze()
	if err == nil || !strings.Contains(err.Error(), "may have made the key") {
		t.Fatalf("want the lost-answer message, got %v", err)
	}
	if len(h.b2.LiveKeysNamed("acme-systems-pgbackrest-write")) != 1 {
		t.Fatal("the stand-in made the key before dropping the answer")
	}
	if err := h.runBackblaze(); err != nil {
		t.Fatalf("rerun: %v", err)
	}
	keys := h.b2.LiveKeysNamed("acme-systems-pgbackrest-write")
	if len(keys) != 1 || h.vault.values["pgbackrest_b2_write_key_id"] != keys[0].ID {
		t.Fatalf("want exactly the saved key left, got %d keys", len(keys))
	}
}

func TestBackblazeExplainsWrongKeysTakenNamesAndUnreadableAnswers(t *testing.T) {
	h := newHarness(t, false, false)
	h.answers = []string{masterKeyID, "wrong"}
	if err := runBackblaze(h.e, nil); err == nil || !strings.Contains(err.Error(), "HTTP 401, unauthorized") {
		t.Fatalf("want Backblaze's refusal, got %v", err)
	}
	h.b2.TakenBucketNames["acme-systems-backups"] = true
	if err := h.runBackblaze(); err == nil || !strings.Contains(err.Error(), "taken in another Backblaze account") {
		t.Fatalf("want the taken-name message, got %v", err)
	}
	delete(h.b2.TakenBucketNames, "acme-systems-backups")
	h.b2.Failures["b2_authorize_account"] = "malformed"
	if err := h.runBackblaze(); err == nil || !strings.Contains(err.Error(), "cannot read") {
		t.Fatalf("want the unreadable-answer message, got %v", err)
	}
	h.requireNoSecretInOutput(masterKey)
}

func TestBackblazeRefusesTheTemplatesExampleBuckets(t *testing.T) {
	h := newHarness(t, false, false)
	path := filepath.Join(h.e.directory, projectSettingsFile)
	text, _ := os.ReadFile(path)
	writeFile(t, path, strings.ReplaceAll(string(text), "acme-systems-backups", "example-systems-backups"))
	if err := h.runBackblaze(); err == nil || !strings.Contains(err.Error(), "still the template's example") {
		t.Fatalf("want the example refusal, got %v", err)
	}
}

func TestTokenFileKeepsOtherLinesAndComments(t *testing.T) {
	path := filepath.Join(t.TempDir(), "acme_systems.env")
	writeFile(t, path, "# This desk's token file\nexport MMX_VAULT_PASSWORD_FILE=\"$HOME/x\"\nexport CLOUDFLARE_API_TOKEN=''      # this person's Cloudflare API token\n")
	if err := updateTokenFile(path, map[string]string{"CLOUDFLARE_API_TOKEN": "abc_123-XYZ", "CLOUDFLARE_ACCOUNT_ID": testAccountID}); err != nil {
		t.Fatal(err)
	}
	text, _ := os.ReadFile(path)
	want := "# This desk's token file\nexport MMX_VAULT_PASSWORD_FILE=\"$HOME/x\"\nexport CLOUDFLARE_API_TOKEN='abc_123-XYZ'      # this person's Cloudflare API token\nexport CLOUDFLARE_ACCOUNT_ID='" + testAccountID + "'\n"
	if string(text) != want {
		t.Fatalf("got\n%s\nwant\n%s", text, want)
	}
	if info, _ := os.Stat(path); info.Mode().Perm() != 0o600 {
		t.Fatalf("mode %v, want 0600", info.Mode().Perm())
	}
	if err := updateTokenFile(path, map[string]string{"CLOUDFLARE_API_TOKEN": "has'quote"}); err == nil {
		t.Fatal("a quote must be refused")
	}
}

func TestPersonalTokenChecksTheNewTokenBeforeChangingAnything(t *testing.T) {
	h := newHarness(t, false, false)
	h.answers = []string{"not-a-working-token"}
	if err := runPersonalToken(h.e, []string{"server-provider", "--server-listing-path", "servers"}); err == nil || !strings.Contains(err.Error(), "nothing changed") {
		t.Fatalf("want a failed check, got %v", err)
	}
	tokenFile := filepath.Join(h.e.home, ".config", "monkeymaxxing-stack", "acme_systems.env")
	if _, err := os.Stat(tokenFile); err == nil || len(h.proxy) != 0 {
		t.Fatal("a failed check changes neither file")
	}
	h.answers = []string{providerToken}
	if err := runPersonalToken(h.e, []string{"server-provider", "--server-listing-path", "servers"}); err != nil {
		t.Fatal(err)
	}
	if h.proxy["server-provider"] != providerToken || tokenFileValue(tokenFile, "SERVER_PROVIDER_API_TOKEN") != providerToken {
		t.Fatal("one entry must reach both the proxy and the token file")
	}
	h.requireNoSecretInOutput(providerToken)
}

func TestBackblazeRotationKeepsTheOldKeyUntilThePersonDeletesIt(t *testing.T) {
	h := newHarness(t, false, false)
	if err := h.runBackblaze(); err != nil {
		t.Fatal(err)
	}
	old := h.b2.LiveKeysNamed("acme-systems-pgbackrest-write")[0]
	h.answers = []string{masterKeyID, masterKey}
	if err := runBackblaze(h.e, []string{"--replace-key", "pgbackrest_b2_write_key_id"}); err != nil {
		t.Fatalf("rotation: %v", err)
	}
	keys := h.b2.LiveKeysNamed("acme-systems-pgbackrest-write")
	if len(keys) != 2 || keys[0].ID != old.ID {
		t.Fatalf("the old key must keep working beside the new one, got %d keys", len(keys))
	}
	if h.vault.values["pgbackrest_b2_write_key_id"] != keys[1].ID || h.vault.values["pgbackrest_b2_write_application_key"] != keys[1].Secret {
		t.Fatal("the vault must hold the new key")
	}
	if !strings.Contains(h.out.String(), "./server_management_scripts/run_mmx_on_util01 run every_server") ||
		!strings.Contains(h.out.String(), "The old keys keep working") {
		t.Fatal("the output must give the run's command and say the old key keeps working without an answer")
	}
	h.answers = []string{masterKeyID, masterKey}
	if err := runBackblaze(h.e, []string{"--replace-key", "no_such_key_id"}); err == nil {
		t.Fatal("an unknown key name must be refused")
	}
	// The next run, after the servers' run, asks again; Enter deletes
	// exactly the old key.
	h.e.confirm = func(string) (string, error) { return "", nil }
	if err := h.runBackblaze(); err != nil {
		t.Fatalf("rerun: %v\n%s", err, h.out)
	}
	keys = h.b2.LiveKeysNamed("acme-systems-pgbackrest-write")
	if len(keys) != 1 || keys[0].ID == old.ID || h.vault.values["pgbackrest_b2_write_key_id"] != keys[0].ID {
		t.Fatalf("Enter must delete the old key and keep the new one, got %d keys", len(keys))
	}
}

func TestBackblazeDeleteTheOldKeysAtOnce(t *testing.T) {
	h := newHarness(t, false, false)
	if err := h.runBackblaze(); err != nil {
		t.Fatal(err)
	}
	asked := false
	h.e.confirm = func(string) (string, error) { asked = true; return "", nil }
	h.answers = []string{masterKeyID, masterKey}
	if err := runBackblaze(h.e, []string{"--replace-key", "pgbackrest_b2_write_key_id", "--delete-the-old-keys-at-once"}); err != nil {
		t.Fatalf("rotation: %v", err)
	}
	keys := h.b2.LiveKeysNamed("acme-systems-pgbackrest-write")
	if asked || len(keys) != 1 || h.vault.values["pgbackrest_b2_write_key_id"] != keys[0].ID {
		t.Fatalf("the old key must be deleted without a question, got %d keys", len(keys))
	}
}

func TestProviderTokenInTheGuidesOwnHeader(t *testing.T) {
	h := newHarness(t, false, false)
	h.answers = []string{providerToken}
	if err := runPersonalToken(h.e, []string{"server-provider", "--server-listing-path", "servers", "--token-header", "X-Auth-Token"}); err != nil {
		t.Fatal(err)
	}
	if h.proxy["server-provider"] != "X-Auth-Token"+providerToken {
		t.Fatal("the proxy must get the token with the guide's header")
	}
	h.answers = []string{providerToken}
	if err := runPersonalToken(h.e, []string{"server-provider", "--server-listing-path", "servers", "--token-header", "Bad Header"}); err == nil {
		t.Fatal("a header name with a space must be refused")
	}
}

// A pushed settings change can name any host. The typed token must reach
// only a provider guide's address, and nothing must reach the other host.
func TestProviderTokenGoesOnlyToAProviderGuidesAddress(t *testing.T) {
	h := newHarness(t, false, false)
	received := 0
	other := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		received++
		fmt.Fprint(w, `{"servers": []}`)
	}))
	t.Cleanup(other.Close)
	path := filepath.Join(h.e.directory, projectSettingsFile)
	text, _ := os.ReadFile(path)
	writeFile(t, path, strings.Replace(string(text), h.provider.URL+"/v1/", other.URL+"/v1/", 1))
	h.answers = []string{providerToken}
	err := runPersonalToken(h.e, []string{"server-provider", "--server-listing-path", "servers"})
	if err == nil || !strings.Contains(err.Error(), "not a provider guide's API address") || !strings.Contains(err.Error(), "Nothing was sent") {
		t.Fatalf("want a refusal, got %v", err)
	}
	if received != 0 || len(h.answers) != 1 || len(h.proxy) != 0 {
		t.Fatal("the command must refuse before the prompt, send nothing, and change nothing")
	}
	writeFile(t, path, string(text))
	if err := runPersonalToken(h.e, []string{"server-provider", "--server-listing-path", "servers"}); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(h.out.String(), "checks it at "+h.provider.URL+"/v1/servers") {
		t.Fatal("the destination must be named before the prompt")
	}
	for _, address := range providerGuideAPIAddresses {
		if !strings.HasPrefix(address, "https://") || !strings.HasSuffix(address, "/") {
			t.Fatalf("%s is not an https address with its trailing slash", address)
		}
	}
}

func TestStagingUploadsNeedTheirOwnBucketBeforeAnythingChanges(t *testing.T) {
	for _, value := range []string{`""`, "acme-shop-uploads"} {
		h := newHarness(t, true, true)
		path := filepath.Join(h.e.directory, projectSettingsFile)
		text, _ := os.ReadFile(path)
		writeFile(t, path, strings.Replace(string(text), "staging_uploads_r2_bucket: acme-shop-staging-uploads", "staging_uploads_r2_bucket: "+value, 1))
		err := h.runCloudflare()
		if err == nil || !strings.Contains(err.Error(), "staging_uploads_r2_bucket") {
			t.Fatalf("%s: want a refusal naming staging_uploads_r2_bucket, got %v", value, err)
		}
		if len(h.cloudflare.Tunnels) != 0 || len(h.vault.sets) != 0 {
			t.Fatalf("%s: nothing may change before the settings are right", value)
		}
	}
}

func TestBackblazeRefusesBackupLengthsBelowTheirMinimumsBeforeChangingAnything(t *testing.T) {
	keep := "    keep_database_backups_for_days: 30\n"
	lock := "    lock_backups_against_deletion_for_days: 20\n"
	prior := "    keep_prior_file_versions_in_buckets_for_days: 25\n"
	cases := []struct{ name, from, to, want string }{
		{"keep below 14", keep, "    keep_database_backups_for_days: 13\n", "the weekly restore drill needs the previous full backup"},
		{"lock below 8", lock, "    lock_backups_against_deletion_for_days: 7\n", "warns at 8 days"},
		{"lock above keep", lock, "    lock_backups_against_deletion_for_days: 31\n", "more than keep_database_backups_for_days"},
		{"prior versions of 0", prior, "    keep_prior_file_versions_in_buckets_for_days: 0\n", "keep_prior_file_versions_in_buckets_for_days"},
		{"keep missing", keep, "", "keep_database_backups_for_days in mmx_project_settings.yml is missing"},
	}
	for _, c := range cases {
		h := newHarness(t, false, false)
		path := filepath.Join(h.e.directory, projectSettingsFile)
		text, _ := os.ReadFile(path)
		if !strings.Contains(string(text), c.from) {
			t.Fatalf("%s: the fixture lacks %q", c.name, c.from)
		}
		writeFile(t, path, strings.Replace(string(text), c.from, c.to, 1))
		err := h.runBackblaze()
		if err == nil || !strings.Contains(err.Error(), c.want) {
			t.Fatalf("%s: want a refusal containing %q, got %v", c.name, c.want, err)
		}
		if len(h.b2.Buckets) != 0 || len(h.vault.sets) != 0 {
			t.Fatalf("%s: nothing may change before the settings are right", c.name)
		}
	}
}
