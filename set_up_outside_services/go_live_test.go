package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

const (
	registryToken         = "ghp_registrytokenvalue0000000000000001"
	expiringRegistryToken = "ghp_registrytokenvalue0000000000000002"
	// endsTooSoonRegistryToken ends in 10 days, expiringRegistryToken in 90.
	endsTooSoonRegistryToken = "ghp_registrytokenvalue0000000000000003"
	vaultPassphrase          = "vault-passphrase-value"
	emergencyCodes           = "11111111\n22222222\n33333333"
	stripeKey                = "sk_live_stripekeyvalue000000000001"
)

// github stands in for GitHub's API and ghcr.io: each token's scopes, end
// date, and whether the image is built.
type github struct {
	scopes     map[string]string
	ends       map[string]string
	imageBuilt bool
}

func (g *github) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	switch {
	case r.URL.Path == "/user":
		token := strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
		scopes, known := g.scopes[token]
		if !known {
			w.WriteHeader(http.StatusUnauthorized)
			fmt.Fprint(w, `{"message": "Bad credentials"}`)
			return
		}
		w.Header().Set("X-OAuth-Scopes", scopes)
		if ends := g.ends[token]; ends != "" {
			w.Header().Set("GitHub-Authentication-Token-Expiration", ends)
		}
		fmt.Fprint(w, `{"login": "alex-acme"}`)
	case r.URL.Path == "/token":
		login, token, _ := r.BasicAuth()
		if login != "alex-acme" || g.scopes[token] == "" || r.URL.Query().Get("scope") != "repository:acme/shop:pull" {
			w.WriteHeader(http.StatusUnauthorized)
			fmt.Fprint(w, `{"errors": [{"code": "UNAUTHORIZED", "message": "authentication required"}]}`)
			return
		}
		fmt.Fprintf(w, `{"token": "pull-%s"}`, token)
	case r.URL.Path == "/v2/acme/shop/tags/list" && strings.HasPrefix(r.Header.Get("Authorization"), "Bearer pull-"):
		if !g.imageBuilt {
			w.WriteHeader(http.StatusNotFound)
			fmt.Fprint(w, `{"errors": [{"code": "NAME_UNKNOWN", "message": "repository name not known to registry"}]}`)
			return
		}
		fmt.Fprint(w, `{"name": "acme/shop", "tags": ["main"]}`)
	default:
		w.WriteHeader(http.StatusForbidden)
		fmt.Fprint(w, `{"errors": [{"code": "DENIED", "message": "denied"}]}`)
	}
}

// stripe stands in for Stripe's balance call, which any working key reads.
func stripe(keys ...string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/v1/balance" && contains(keys, strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")) {
			fmt.Fprint(w, `{"object": "balance"}`)
			return
		}
		w.WriteHeader(http.StatusUnauthorized)
		fmt.Fprint(w, `{"error": {"message": "Invalid API Key provided: sk_live_****wxyz"}}`)
	}
}

// rdap stands in for IANA's bootstrap file and the registry of .org.
func rdap(dnssec bool) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/dns.json":
			fmt.Fprintf(w, `{"services": [[["com", "net"], ["https://rdap.example.net/com/"]], [["org"], ["http://%s/org/"]]]}`, r.Host)
		case "/org/domain/example.org":
			fmt.Fprintf(w, `{"secureDNS": {"delegationSigned": %t}, "entities": [{"roles": ["registrar"],
				"vcardArray": ["vcard", [["version", {}, "text", "4.0"], ["fn", {}, "text", "Namecheap, Inc."]]]}]}`, dnssec)
		default:
			w.WriteHeader(http.StatusNotFound)
		}
	}
}

// goLiveHarness runs go-live as the person does, with stand-ins for every
// service, the desk's root files, and the phone-code setup. transcript is
// what the person's terminal shows, prompts and typing included.
type goLiveHarness struct {
	*harness
	github     *github
	transcript *strings.Builder
	// hidden and visible answer the hidden and visible prompts in turn. A
	// function answers with what the screen showed, such as the passphrase.
	hidden, visible []func() string
	results         []setupResults
	// passphrase is the recovery passphrase the screen showed.
	passphrase string
	phoneCode  func(path string) error
}

func newGoLiveHarness(t *testing.T, dnssec bool) *goLiveHarness {
	t.Helper()
	if _, err := exec.LookPath("mmx"); err != nil {
		t.Skip("go-live's tests keep the recovery bundle in a real MMX vault, so they need mmx on PATH")
	}
	h := &goLiveHarness{harness: newHarness(t, false, false), github: &github{scopes: map[string]string{
		registryToken: "read:packages", expiringRegistryToken: "read:packages", endsTooSoonRegistryToken: "read:packages"},
		ends: map[string]string{expiringRegistryToken: tokenEnd(90), endsTooSoonRegistryToken: tokenEndsInTenDays}}}
	h.transcript = &strings.Builder{}
	h.e.out = h.transcript
	h.cloudflare.ZoneStatus = ""
	githubServer := httptest.NewServer(h.github)
	t.Cleanup(githubServer.Close)
	rdapServer := httptest.NewServer(rdap(dnssec))
	t.Cleanup(rdapServer.Close)
	h.e.githubAPIURL, h.e.containerRegistryURL, h.e.rdapBootstrapURL = githubServer.URL, githubServer.URL, rdapServer.URL+"/dns.json"
	stripeServer := httptest.NewServer(stripe(stripeKey))
	t.Cleanup(stripeServer.Close)
	h.e.stripeAPIURL = stripeServer.URL
	rootFiles := map[string]string{
		"/etc/systems-desk/provider-api-token.conf":    `proxy_set_header Authorization "Bearer ` + providerToken + `";` + "\n",
		deskVaultPassphraseFile:                        vaultPassphrase + "\n",
		filepath.Join(h.e.home, ".ssh/production_key"): "-----BEGIN OPENSSH PRIVATE KEY-----\nproduction\n-----END OPENSSH PRIVATE KEY-----\n",
		deskWireGuardPrivateKeyFile:                    "wireguardprivatekeyvalue=\n",
	}
	h.e.readRootFile = func(path string) ([]byte, error) {
		if content, ok := rootFiles[path]; ok {
			return []byte(content), nil
		}
		return os.ReadFile(path)
	}
	// The desk's set-up-the-phone-code, which shows the QR code and asks for
	// one code, then writes the emergency codes.
	h.phoneCode = func(path string) error {
		fmt.Fprint(h.transcript, "\n  [QR code]\n\n  3. Type the 6 digits your phone shows.\n\n  Code: 123456\n")
		return os.WriteFile(path, []byte(emergencyCodes+"\n"), 0o600)
	}
	h.e.setUpThePhoneCode = func(path string) error { return h.phoneCode(path) }
	h.e.resultsFile = filepath.Join(t.TempDir(), "setup_results.json")
	h.e.writeResultsFile = func(content []byte) error {
		var results setupResults
		if err := json.Unmarshal(content, &results); err != nil {
			t.Fatalf("the results file is not JSON: %v", err)
		}
		h.results = append(h.results, results)
		return os.WriteFile(h.e.resultsFile, content, 0o644)
	}
	h.e.clearScreen = func() { fmt.Fprint(h.transcript, "\n[the screen is cleared]\n") }
	answer := func(queue *[]func() string, label, kind string) (string, error) {
		if len(*queue) == 0 {
			return "", errors.New("unexpected " + kind + " prompt " + label)
		}
		value := (*queue)[0]()
		*queue = (*queue)[1:]
		shown := value
		if kind == "hidden" {
			shown = "(typed, not shown)"
		}
		fmt.Fprintf(h.transcript, "%s%s\n", label, shown)
		return value, nil
	}
	h.e.prompt = func(label string) (string, error) { return answer(&h.hidden, label, "hidden") }
	h.e.confirm = func(label string) (string, error) { return answer(&h.visible, label, "visible") }
	return h
}

var tokenEndsInTenDays = tokenEnd(10)

// tokenEnd is a token's end date in GitHub's format, days from now.
func tokenEnd(days int) string {
	return time.Now().UTC().AddDate(0, 0, days).Format("2006-01-02 15:04:05 UTC")
}

func typed(values ...string) []func() string {
	var answers []func() string
	for _, value := range values {
		answers = append(answers, func() string { return value })
	}
	return answers
}

// theShownPassphrase types the passphrase the screen showed, as the person
// does from the password manager.
func (h *goLiveHarness) theShownPassphrase() string {
	text := h.transcript.String()
	after := text[strings.LastIndex(text, "IT IS SHOWN ONLY ONCE.")+len("IT IS SHOWN ONLY ONCE."):]
	h.passphrase = strings.Join(strings.Fields(strings.SplitN(strings.TrimLeft(after, "\n"), "\n", 2)[0]), " ")
	return h.passphrase
}

func (h *goLiveHarness) last() setupResults {
	return h.results[len(h.results)-1]
}

func (h *goLiveHarness) bundleKeys() map[string]bool {
	h.t.Helper()
	passwordFile := filepath.Join(h.t.TempDir(), "passphrase")
	writeFile(h.t, passwordFile, h.passphrase+"\n")
	if err := os.Chmod(passwordFile, 0o600); err != nil {
		h.t.Fatal(err)
	}
	keys, err := mmxVault{directory: h.t.TempDir(), file: filepath.Join(h.e.directory, recoveryBundleFile), passwordFile: passwordFile}.keys()
	if err != nil {
		h.t.Fatalf("the recovery passphrase does not open the bundle: %v", err)
	}
	return keys
}

// The whole of sitting 1 on the desk, with one refused value on each screen
// that checks one.
func TestGoLiveWalksEveryScreenAndLocksTheDesk(t *testing.T) {
	h := newGoLiveHarness(t, true)
	// An app that keeps uploads, in an account without R2 yet, and has a
	// Stripe key.
	path := filepath.Join(h.e.directory, projectSettingsFile)
	text, _ := os.ReadFile(path)
	text = []byte(strings.Replace(string(text), `production_uploads_r2_bucket: ""`, "production_uploads_r2_bucket: acme-shop-uploads", 1))
	writeFile(t, path, strings.Replace(string(text), "      secrets_from_vault:\n", "      secrets_from_vault:\n"+stripeSecret, 1))
	h.commitAll("An app with uploads and a Stripe key")
	h.cloudflare.R2Off = true
	turnOnR2 := func() string { h.cloudflare.Lock(); h.cloudflare.R2Off = false; h.cloudflare.Unlock(); return "" }
	h.hidden = append(typed("not-the-token-it-made", h.addLinkToken(), "wrong-application-key", masterKey, endsTooSoonRegistryToken, expiringRegistryToken, registryToken,
		"sk_live_notthekey", stripeKey, "maple orbit candle river stone pilot"), h.theShownPassphrase)
	h.visible = append([]func() string{turnOnR2}, typed("", masterKeyID, masterKeyID, "no")...)
	err := runGoLive(h.e)
	t.Logf("The person's terminal:\n%s", h.transcript)
	if err != nil {
		t.Fatalf("go-live: %v", err)
	}
	output := h.transcript.String()

	// Each screen in the design's order, with its four parts.
	order := []string{"Account 2 of 4: Cloudflare (your web address and protection)", "4. Turn on R2", "It costs nothing up to 10 GB of files a month.",
		"5. Open this link.", "Cloudflare accepted the token.", "R2 is not on yet",
		"Account 3 of 4: your domain's registrar (Namecheap, Inc.)", "TURN OFF DNSSEC FIRST.", "Account 4 of 4: Backblaze (your backups)",
		"THE REGION CANNOT BE CHANGED LATER.", "Backblaze accepted the key.", "One more key: so your servers can download your app.",
		`SET EXPIRATION TO "NO EXPIRATION".`, "GitHub accepted the token.", "Key for shop: STRIPE_API_KEY",
		"Stripe takes your customers' card payments with it.", "1. Open  https://dashboard.stripe.com/apikeys", "Stripe accepted the key.", "Step 1 of 2: your recovery passphrase", "SAVE IT NOW.",
		"[the screen is cleared]", "Step 2 of 2: your phone code", "Done.  Your desk is locked."}
	at := 0
	for _, line := range order {
		next := strings.Index(output[at:], line)
		if next < 0 {
			t.Fatalf("the screens lack %q after position %d", line, at)
		}
		at += next
	}
	// The labels the providers' pages show.
	for _, label := range []string{"Two-Factor Authentication", "Scroll to the bottom, below the list of permissions.", "Press  Review token,  then  Create token.",
		"When Backblaze asks for a region, choose  EU Central.", "Get Started Free", "Confirm access"} {
		if !strings.Contains(output, label) {
			t.Errorf("the screens lack the provider's label %q", label)
		}
	}
	// Each loud line is in capitals on its own line, with a blank line above and below.
	for _, loud := range []string{"TURN OFF DNSSEC FIRST.  YOUR SITE WILL NOT WORK WITH IT ON.", "THE REGION CANNOT BE CHANGED LATER.",
		`SET EXPIRATION TO "NO EXPIRATION".  OTHERWISE YOUR DEPLOYS STOP IN 30 DAYS.`, "SAVE IT NOW.  IT IS SHOWN ONLY ONCE."} {
		if !strings.Contains(output, "\n\n"+loud+"\n\n") && !strings.Contains(output, "\n\n  "+loud+"\n\n") {
			t.Errorf("the loud line %q is not on its own line between blank lines", loud)
		}
	}
	// Each refused value was asked again, with the service's reason.
	for _, reason := range []string{"Cloudflare did not accept the token.  It said: Invalid request headers.",
		"Backblaze did not accept the key.  It said: The applicationKeyId and/or the applicationKey are wrong.", "This token stops working on " + tokenEndsInTenDays + ", less than 30 days from now",
		"Stripe did not accept the key.  It said: Invalid API Key provided: sk_live_****wxyz.", "That is not the passphrase above."} {
		if !strings.Contains(output, reason) {
			t.Errorf("the output lacks the refusal %q", reason)
		}
	}
	// After each refusal, a line says the setup still waits at the prompt,
	// which shows nothing while the person types.
	for _, refusal := range []string{"Cloudflare did not accept", "Backblaze did not accept", "less than 30 days from now", "Stripe did not accept", "That is not the passphrase above."} {
		at := strings.Index(output, refusal)
		next := strings.Index(output[at:], "(hidden): ")
		if next < 0 {
			next = strings.Index(output[at:], "Recovery passphrase: ")
		}
		if !strings.Contains(output[at:at+next], "The setup is still running.  It waits for you at the line below.") {
			t.Errorf("after %q, no line says the setup still waits:\n%s", refusal, output[at:at+next])
		}
	}
	if strings.Contains(output, "Made ") || strings.Contains(output, "Bucket ") || strings.Contains(output, "Tunnel") {
		t.Error("the screens show the work's step-by-step lines")
	}

	// Cloudflare: the domain added and its records copied, the workers.dev
	// address made, the servers' tokens saved, and no token that can make
	// tokens or zones left.
	if h.cloudflare.ZoneStatus != "pending" || h.cloudflare.DNSScans != 1 || h.cloudflare.WorkersSubdomain != "acme-systems" {
		t.Fatalf("zone %q, %d scans, workers.dev %q", h.cloudflare.ZoneStatus, h.cloudflare.DNSScans, h.cloudflare.WorkersSubdomain)
	}
	for _, name := range []string{"acme_systems: alex makes tokens with set-up-outside-services, deleted after the run",
		"acme_systems: set-up-outside-services adds the domain, deleted after the run"} {
		if len(h.cloudflare.LiveTokensNamed(name)) != 0 {
			t.Errorf("the token %q is left", name)
		}
	}
	// The vault: every key go-live makes, and util01's provider credential
	// is the desk's.
	for _, key := range []string{"apps_cloudflare_tunnel_token", "mmhotline_down_alarm_cloudflare_api_token", "pgbackrest_b2_write_key_id",
		"pgbackrest_b2_read_only_application_key", "container_registry_read_only_token", "pg_auto_failover_replication_password",
		"pgbackrest_repository_cipher_passphrase", "mmhotline_signing_secret_of_the_fleet_hub", "shop_database_password", "shared_root_console_password_hash"} {
		if h.vault.values[key] == "" {
			t.Errorf("the vault lacks %s", key)
		}
	}
	if h.vault.values["util01_provider_api_token"] != providerToken || h.vault.values["container_registry_read_only_token"] != registryToken ||
		h.vault.values["shop_STRIPE_API_KEY"] != stripeKey {
		t.Error("util01's provider credential, the registry token or the Stripe key is not the one entered")
	}
	// The app's secret the setup generates, and its R2 key, made in the same run.
	if len(h.vault.values["shop_SECRET_KEY_BASE"]) < 64 || h.vault.values["shop_R2_ACCESS_KEY_ID"] == "" || !h.cloudflare.R2Buckets["acme-shop-uploads"] {
		t.Error("the app's generated secret, its R2 key, or its uploads bucket is missing")
	}
	// The vault and the bundle are pushed, each in its own commit.
	log := h.git(h.e.directory, "--git-dir", h.origin, "log", "--format=%s", "-2", "main")
	if !strings.Contains(log, "Add the recovery bundle with set-up-outside-services go-live") || !strings.Contains(log, "vault keys with set-up-outside-services go-live") {
		t.Fatalf("origin's main lacks the two commits:\n%s", log)
	}
	if files := strings.TrimSpace(h.git(h.e.directory, "--git-dir", h.origin, "diff-tree", "--no-commit-id", "--name-only", "-r", "main")); files != recoveryBundleFile {
		t.Fatalf("the bundle's commit changes %q", files)
	}
	// The recovery passphrase opens the bundle, which holds every item.
	keys := h.bundleKeys()
	for _, key := range []string{bundleVaultPassphrase, bundleProductionKey, bundleWireGuardKey, bundleProviderCredential, bundleCloudflareDeskToken,
		bundleConsolePassword, bundlePhoneCodeEmergencyCode, "pgbackrest_repository_cipher_passphrase", "pgbackrest_b2_read_only_key_id", "pgbackrest_b2_read_only_application_key"} {
		if !keys[key] {
			t.Errorf("the bundle lacks %s", key)
		}
	}
	// A copy is in the locked backup bucket.
	copies := 0
	for _, file := range h.b2.Files {
		if strings.HasPrefix(file.Name, "recovery_bundle/") && file.BucketID == bucketNamed(h.b2, "acme-systems-backups").ID && file.Mode == "compliance" {
			copies++
		}
	}
	if copies != 1 {
		t.Fatalf("want one locked copy of the bundle at Backblaze, got %d", copies)
	}
	if _, err := os.Stat(filepath.Join(h.e.home, ".config/monkeymaxxing-stack/acme_systems_recovery_passphrase_until_the_bundle_is_saved")); !errors.Is(err, os.ErrNotExist) {
		t.Error("the recovery passphrase's file stays after the bundle is saved")
	}

	// The results file: every step done, the values the coding agent needs,
	// and never a secret.
	results := h.last()
	if !results.Finished || results.StoppedWith != "" {
		t.Fatalf("the results are not finished: %+v", results)
	}
	for _, step := range results.Steps {
		if step.State != stepDone {
			t.Errorf("step %s is %s", step.Name, step.State)
		}
	}
	for name, want := range map[string]string{"cloudflare_account_id": testAccountID, "cloudflare_nameservers": "ada.ns.cloudflare.com bob.ns.cloudflare.com",
		"container_registry_read_only_username": "alex-acme", "container_image_found": "no, not built yet", "registrar": "Namecheap, Inc."} {
		if results.ForTheCodingAgent[name] != want {
			t.Errorf("for_the_coding_agent.%s = %q, want %q", name, results.ForTheCodingAgent[name], want)
		}
	}
	file, _ := os.ReadFile(h.e.resultsFile)
	for key, value := range h.vault.values {
		if strings.Contains(string(file), value) && !strings.HasSuffix(key, "_key_id") {
			t.Errorf("the results file holds the value of %s", key)
		}
	}
	for _, secret := range []string{providerToken, masterKey, registryToken, h.passphrase, vaultPassphrase} {
		if strings.Contains(string(file), secret) {
			t.Error("the results file holds a secret")
		}
	}
	h.requireNoSecretInOutput(providerToken, masterKey, registryToken, vaultPassphrase, "11111111", stripeKey)
	// The passphrase showed once: the screen was cleared after it.
	if strings.Count(output, h.passphrase) != 1 && strings.Count(output, strings.ReplaceAll(h.passphrase, " ", "  ")) != 1 {
		t.Error("the recovery passphrase shows more than once")
	}

	// A rerun after the end asks nothing.
	h.transcript.Reset()
	if err := runGoLive(h.e); err != nil || !strings.Contains(h.transcript.String(), "Everything here is done already.") {
		t.Fatalf("a rerun of a finished setup: %v\n%s", err, h.transcript)
	}
}

// A run stopped at the phone code continues there: no earlier screen comes
// back except Backblaze's, whose key the bundle's copy needs, and the bundle
// keeps what the first run put in it.
func TestGoLiveContinuesWhereARunStopped(t *testing.T) {
	h := newGoLiveHarness(t, false)
	h.cloudflare.ZoneStatus = "active"
	h.hidden = append(typed(h.addLinkToken(), masterKey, registryToken), h.theShownPassphrase)
	h.visible = typed(masterKeyID)
	h.phoneCode = func(string) error {
		return errors.New("set-up-the-phone-code stopped (exit status 1), so the desk is not locked yet")
	}
	err := runGoLive(h.e)
	if err == nil || !strings.Contains(err.Error(), "Go back to your coding agent") {
		t.Fatalf("want the stop at the phone code, got %v", err)
	}
	stopped := h.last()
	if stopped.StoppedWith == "" || stopped.Finished {
		t.Fatalf("the results do not say where the run stopped: %+v", stopped)
	}
	for _, step := range stopped.Steps {
		want := map[string]string{"registrar": stepNotNeeded, "app_keys_from_outside_services": stepNotNeeded, "phone_code": stepInProgress, "recovery_bundle": stepNotStarted}[step.Name]
		if want == "" {
			want = stepDone
		}
		if step.State != want {
			t.Errorf("after the stop, step %s is %s, want %s", step.Name, step.State, want)
		}
	}

	h.transcript.Reset()
	writes := len(h.results)
	h.phoneCode = func(path string) error { return os.WriteFile(path, []byte(emergencyCodes), 0o600) }
	h.hidden, h.visible = typed(masterKey), typed(masterKeyID)
	if err := runGoLive(h.e); err != nil {
		t.Fatalf("rerun: %v\n%s", err, h.transcript)
	}
	// The coding agent waits for finished or stopped_with, so a rerun's
	// first write drops the earlier run's reason.
	if rerun := h.results[writes]; rerun.StoppedWith != "" {
		t.Errorf("the rerun's first results still say it stopped: %q", rerun.StoppedWith)
	}
	output := h.transcript.String()
	for _, screen := range []string{"Account 2 of 4", "Account 3 of 4", "Account 4 of 4", "Get Started Free", "One more key", "Step 1 of 2"} {
		if strings.Contains(output, screen) {
			t.Errorf("the rerun showed %q again", screen)
		}
	}
	// The master key is never kept, so the bundle's copy at Backblaze asks
	// for it again, on a short screen that says why.
	for _, line := range []string{"Paste your Backblaze master key again.",
		"The setup needs it once more, to put a copy of your recovery bundle into your locked backup bucket.  It does not keep the key.",
		"press  Generate New Master Application Key.", "Backblaze accepted the key."} {
		if !strings.Contains(output, line) {
			t.Errorf("the rerun's Backblaze screen lacks %q", line)
		}
	}
	if !strings.Contains(output, "Step 2 of 2: your phone code") {
		t.Fatalf("the rerun did not ask for the phone code:\n%s", output)
	}
	keys := h.bundleKeys()
	if !keys[bundleConsolePassword] || !keys[bundlePhoneCodeEmergencyCode] || !keys["pgbackrest_repository_cipher_passphrase"] {
		t.Fatalf("the bundle lost what the first run put in it: %v", keys)
	}
	if !h.last().Finished {
		t.Fatal("the rerun did not finish")
	}
}

// When Cloudflare does not list the token's account, the person copies its
// ID from the dashboard, and a malformed ID is asked again.
func TestTheAccountIDScreenWhenCloudflareDoesNotListTheAccount(t *testing.T) {
	h := newGoLiveHarness(t, false)
	h.cloudflare.RefuseAccountsList = true
	settings, err := readSystemSettings(h.e.readRepositoryFile)
	if err != nil {
		t.Fatal(err)
	}
	g := &goLive{e: h.e, settings: settings, tokenStep: 4}
	h.visible = typed("dash.cloudflare.com/abc", testAccountID)
	link, _, err := g.checkTheLinkToken(h.addLinkToken())
	t.Logf("The person's terminal:\n%s", h.transcript)
	if err != nil || link.accountID != testAccountID {
		t.Fatalf("want the token accepted in the typed account, got %v", err)
	}
	for _, line := range []string{"Under  Account Details,  press the copy button beside  Account ID.", "right after  dash.cloudflare.com/", "An account ID is 32 letters and digits."} {
		if !strings.Contains(h.transcript.String(), line) {
			t.Errorf("the screen lacks %q", line)
		}
	}
}

func TestTheRegistryTokenIsCheckedAsTheServersUseIt(t *testing.T) {
	h := newGoLiveHarness(t, false)
	h.github.scopes["ghp_broad"] = "read:packages, repo"
	h.github.scopes["ghp_narrow"] = "read:user"
	g := &goLive{e: h.e}
	for token, want := range map[string]string{
		"ghp_unknown":            "Bad credentials",
		endsTooSoonRegistryToken: "less than 30 days from now",
		"ghp_broad":              "can also use repo",
		"ghp_narrow":             "cannot download packages",
	} {
		_, advice, err := g.checkTheRegistryToken(token, "acme/shop")
		if err == nil || advice == "" || !strings.Contains(err.Error(), want) {
			t.Errorf("%s: want a refusal with advice containing %q, got %v (advice %q)", token, want, err, advice)
		}
	}
	if _, advice, err := g.checkTheRegistryToken(registryToken, "acme/other"); err == nil || advice == "" || !strings.Contains(err.Error(), "cannot read your app's image") {
		t.Errorf("an image the token cannot read: got %v", err)
	}
	h.github.imageBuilt = true
	check, _, err := g.checkTheRegistryToken(registryToken, "acme/shop")
	if err != nil || !check.imageFound || check.login != "alex-acme" {
		t.Errorf("a good token: %+v, %v", check, err)
	}
}

// A token that ends 30 or more days from now is accepted after the person
// types yes, and its end date goes to the coding agent.
func TestGoLiveAcceptsARegistryTokenThatExpires(t *testing.T) {
	h := newGoLiveHarness(t, false)
	h.cloudflare.ZoneStatus = "active"
	h.hidden = append(typed(h.addLinkToken(), masterKey, expiringRegistryToken, expiringRegistryToken), h.theShownPassphrase)
	h.visible = typed(masterKeyID, "no", "yes")
	if err := runGoLive(h.e); err != nil {
		t.Fatalf("go-live: %v\n%s", err, h.transcript)
	}
	t.Logf("The person's terminal:\n%s", h.transcript)
	output := h.transcript.String()
	ends := strings.TrimSuffix(tokenEnd(90), " UTC")
	ends = strings.Split(ends, " ")[0]
	for _, line := range []string{"This token stops working on " + ends, "your servers cannot download your app.",
		"Deploys and new servers stop until you replace the token.", "Type  yes  to use this token.", `SET EXPIRATION TO "NO EXPIRATION".`} {
		if !strings.Contains(output, line) {
			t.Errorf("the screen lacks %q", line)
		}
	}
	afterNo := output[strings.Index(output, "Use this token (yes): no"):]
	if !strings.Contains(afterNo[:strings.Index(afterNo, "GitHub token (hidden): ")], "The setup is still running.  It waits for you at the line below.") {
		t.Errorf("after no, no line says the setup still waits for a token:\n%s", afterNo)
	}
	if strings.Count(output, "GitHub accepted the token.") != 1 {
		t.Error("the token must be accepted once, after yes, not after no")
	}
	if h.vault.values["container_registry_read_only_token"] != expiringRegistryToken {
		t.Error("the accepted token is not in the vault")
	}
	got := h.last().ForTheCodingAgent["container_registry_read_only_token_expires_at"]
	want := time.Now().UTC().AddDate(0, 0, 90).Format("2006-01-02")
	if !strings.HasPrefix(got, want) || !strings.HasSuffix(got, "Z") {
		t.Errorf("container_registry_read_only_token_expires_at = %q, want %s...Z", got, want)
	}
}

func TestGoLiveRefusesTheButtonAndAgentAccountsAndNeedsATerminal(t *testing.T) {
	if !strings.Contains(strings.Join(accountsThatMayNotRun, " "), "coding-agent servers-mmx root") {
		t.Fatal("go-live must refuse the coding agent, the button account and root")
	}
	if stdinIsTerminal() {
		t.Skip("standard input is a terminal here")
	}
	if err := (&environment{}).dispatch([]string{"go-live"}); !errors.Is(err, errNoTerminal) {
		t.Fatalf("want errNoTerminal, got %v", err)
	}
}

func TestTheRegionNameOnBackblazesSignUpPage(t *testing.T) {
	for endpoint, want := range map[string]string{"s3.eu-central-003.backblazeb2.com": "EU Central", "s3.us-west-004.backblazeb2.com": "US West", "": ""} {
		if got := backblazeRegionName(endpoint); got != want {
			t.Errorf("%q: got %q, want %q", endpoint, got, want)
		}
	}
}

// A Backblaze account in another region than the plan: the screen names the
// account's region, says it cannot change, and waits for the person's choice
// between carrying on and a new account in the planned region.
func TestGoLiveAsksWhenTheBackblazeAccountIsInAnotherRegion(t *testing.T) {
	for _, choice := range []string{"1", "2"} {
		t.Run("choice "+choice, func(t *testing.T) {
			h := newGoLiveHarness(t, false)
			h.cloudflare.ZoneStatus = "active"
			h.b2.S3APIURL = "https://s3.us-west-001.backblazeb2.com"
			// The person's choice; a new account is in the planned region.
			choose := func() string {
				if choice == "2" {
					h.b2.S3APIURL = "https://s3.eu-central-003.backblazeb2.com"
				}
				return choice
			}
			hidden := []string{h.addLinkToken(), masterKey}
			visible := []func() string{func() string { return masterKeyID }, func() string { return "3" }, choose}
			if choice == "2" {
				hidden = append(hidden, masterKey)
				visible = append(visible, func() string { return masterKeyID })
			}
			h.hidden = append(typed(append(hidden, registryToken)...), h.theShownPassphrase)
			h.visible = visible
			if err := runGoLive(h.e); err != nil {
				t.Fatalf("go-live: %v\n%s", err, h.transcript)
			}
			t.Logf("The person's terminal:\n%s", h.transcript)
			output := h.transcript.String()
			for _, line := range []string{"Your Backblaze account is in  US West.  The plan was  EU Central,  near your servers.",
				"An account's region cannot be changed.",
				"  1. Carry on with  US West.  Your backups work the same, farther from your servers.",
				"  2. Make a new Backblaze account in  EU Central.  It needs another email address.",
				"  Type 1 or 2: 3", "  Type 1 or 2: " + choice} {
				if !strings.Contains(output, line) {
					t.Errorf("the screen lacks %q", line)
				}
			}
			endpoint := h.last().ForTheCodingAgent["b2_s3_endpoint"]
			if choice == "1" && endpoint != "s3.us-west-001.backblazeb2.com" {
				t.Errorf("carrying on: b2_s3_endpoint = %q, want the account's", endpoint)
			}
			if choice == "2" {
				if endpoint != "" {
					t.Errorf("a new account in the planned region: b2_s3_endpoint = %q, want none", endpoint)
				}
				if !strings.Contains(output, "When Backblaze asks for a region, choose  EU Central.") || strings.Count(output, "Backblaze accepted the key.") != 2 {
					t.Error("a new account: the screen must say which region to choose, and accept the new account's key")
				}
			}
		})
	}
}
