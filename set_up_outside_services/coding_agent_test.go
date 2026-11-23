package main

import (
	"bytes"
	"errors"
	"os"
	"os/user"
	"path/filepath"
	"strings"
	"testing"
)

// fromTheCodingAgent runs one from-the-coding-agent command line with input
// on standard input, as the coding agent does through its sudo rule, and
// returns the exit code, standard output and standard error. The harness's
// person-mode prompts come back afterwards.
func (h *harness) fromTheCodingAgent(input string, arguments ...string) (int, string, string) {
	h.t.Helper()
	var out, errorOut bytes.Buffer
	command, err := readCodingAgentArguments(arguments)
	if err == nil {
		savedOut, savedPrompt, savedConfirm := h.e.out, h.e.prompt, h.e.confirm
		h.e.out = &out
		h.e.readFromTheCodingAgent(strings.NewReader(input))
		err = h.e.runForTheCodingAgent(command)
		h.e.out, h.e.prompt, h.e.confirm, h.e.forTheCodingAgent = savedOut, savedPrompt, savedConfirm, false
	}
	return codingAgentExitCode(err, &errorOut), out.String(), errorOut.String()
}

// failingReader fails a test that reads it: the command must refuse its
// arguments before it reads standard input.
type failingReader struct{ t *testing.T }

func (r failingReader) Read([]byte) (int, error) {
	r.t.Fatal("the command read standard input before it checked its arguments")
	return 0, errors.New("read")
}

func TestTheCodingAgentsArgumentsAreCheckedBeforeStandardInput(t *testing.T) {
	for _, arguments := range [][]string{nil, {"go-live"}, {"secrets"}, {"backblaze", "--replace-key", "pgbackrest_b2_write_key_id"},
		{"cloudflare", "--replace-every-key"}, {"cloudflare", "--account-id", "not-an-id"}, {"cloudflare", "--account-id"},
		{"save-a-key"}, {"save-a-key", "a key"}, {"save-a-key", "a", "b"}, {"random-secrets", "extra"}, {"lock-the-desk"}} {
		err := runFromTheCodingAgent(arguments, failingReader{t}, &bytes.Buffer{})
		if !errors.Is(err, errUsage) {
			t.Errorf("%v: want a refusal of the arguments, got %v", arguments, err)
		}
		if code := codingAgentExitCode(err, &bytes.Buffer{}); code != 4 {
			t.Errorf("%v: exit code %d, want 4", arguments, code)
		}
	}
	for _, arguments := range [][]string{{"backblaze"}, {"cloudflare"}, {"cloudflare", "--account-id", testAccountID}, {"save-a-key", "shop_STRIPE_API_KEY"}, {"random-secrets"}} {
		if _, err := readCodingAgentArguments(arguments); err != nil {
			t.Errorf("%v: %v", arguments, err)
		}
	}
	// save-a-key refuses a key no person gives before it reads standard input.
	h := newHarness(t, false, false)
	h.e.readFromTheCodingAgent(failingReader{t})
	if err := h.e.runForTheCodingAgent(codingAgentCommand{name: "save-a-key", key: "pgbackrest_b2_write_key_id"}); err == nil ||
		!strings.Contains(err.Error(), "save-a-key saves only") || !strings.Contains(err.Error(), registryTokenVaultKey) {
		t.Fatalf("want save-a-key to refuse a key another command makes, got %v", err)
	}
	if len(h.vault.sets) != 0 {
		t.Fatal("a refused key changed the vault")
	}
}

// The command runs as root and works for the person the desk role names in a
// root-only file, never for a name in the coding agent's own checkout.
func TestTheDesksPersonComesFromTheRootOnlyFile(t *testing.T) {
	h := newHarness(t, false, false)
	current, err := user.Current()
	if err != nil {
		t.Fatal(err)
	}
	h.e.person, h.e.home = "", ""
	h.rootFiles[deskPersonFile] = current.Username + "\n"
	if err := h.e.becomeTheDesksPerson(); err != nil || h.e.person != current.Username || h.e.home != current.HomeDir {
		t.Fatalf("want the file's person %s, got %q at %q: %v", current.Username, h.e.person, h.e.home, err)
	}
	for _, named := range []string{"root\n", "coding-agent\n", "../etc\n", ""} {
		h.rootFiles[deskPersonFile] = named
		if err := h.e.becomeTheDesksPerson(); err == nil {
			t.Errorf("%q: want a refusal", named)
		}
	}
	delete(h.rootFiles, deskPersonFile)
	if err := h.e.becomeTheDesksPerson(); err == nil || !strings.Contains(err.Error(), deskPersonFile) {
		t.Errorf("want a refusal without the file, got %v", err)
	}
	if os.Geteuid() != 0 {
		if err := runFromTheCodingAgent([]string{"backblaze"}, failingReader{t}, &bytes.Buffer{}); err == nil || !strings.Contains(err.Error(), "runs as root") {
			t.Fatalf("want a refusal outside root, got %v", err)
		}
	}
}

// project_name becomes part of file names that root writes in the person's
// home, so a name that could leave ~/.config/monkeymaxxing-stack is refused.
func TestAProjectNameThatCouldLeaveItsFolderIsRefused(t *testing.T) {
	h := newHarness(t, false, false)
	path := filepath.Join(h.e.directory, projectSettingsFile)
	original := mustRead(t, path)
	for _, name := range []string{"../../../../etc/foo", "a/b", "..", "-a", "_a", "a b"} {
		writeFile(t, path, strings.Replace(original, "project_name: acme_systems", "project_name: \""+name+"\"", 1))
		if _, err := readSystemSettings(h.e.readRepositoryFile); err == nil || !strings.Contains(err.Error(), "project_name") {
			t.Errorf("%q: want a refusal, got %v", name, err)
		}
	}
	writeFile(t, path, original)
	if _, err := readSystemSettings(h.e.readRepositoryFile); err != nil {
		t.Fatalf("the template's project_name: %v", err)
	}
}

// Every command the coding agent runs, done and stopped, with each key on
// standard input: no key, and no value the command saved, shows on standard
// output, standard error, or in the results file. The stand-ins for GitHub
// and Stripe repeat the refused key in their message, as a provider may.
func TestNoCodingAgentCommandShowsAKey(t *testing.T) {
	const dummy = "dummysecretvalue0000000000000042"
	type run struct {
		name     string
		input    string
		args     []string
		prepare  func(h *harness)
		wantCode int
		// secrets that must not show, besides every vault and bundle value.
		secrets []string
		// want is a line the output or the reason must hold.
		want string
	}
	h := newHarness(t, false, true)
	writeFile(t, filepath.Join(h.e.directory, projectSettingsFile), strings.Replace(mustRead(t, filepath.Join(h.e.directory, projectSettingsFile)),
		"      secrets_from_vault:\n", "      secrets_from_vault:\n"+stripeSecret, 1))
	h.commitAll("A Stripe key")
	h.rootFiles["/etc/systems-desk/provider-api-token.conf"] = `proxy_set_header Authorization "Bearer ` + providerToken + `";` + "\n"
	var linkToken string
	runs := []run{
		{name: "backblaze with a wrong key", input: masterKeyID + "\n" + dummy + "\n", args: []string{"backblaze"}, wantCode: 1,
			secrets: []string{dummy}, want: "Backblaze refused b2_authorize_account with HTTP 401, code unauthorized"},
		{name: "backblaze in another region", input: masterKeyID + "\n" + masterKey + "\n", args: []string{"backblaze"}, wantCode: 1,
			prepare: func(h *harness) { h.b2.S3APIURL = "https://s3.us-west-004.backblazeb2.com" },
			secrets: []string{masterKey}, want: "saved nothing: the Backblaze account is in the region us-west-004"},
		{name: "backblaze", input: masterKeyID + "\r\n" + masterKey + "\r\n", args: []string{"backblaze"},
			prepare: func(h *harness) { h.b2.S3APIURL = "https://s3.eu-central-003.backblazeb2.com" },
			secrets: []string{masterKey}, want: "Committed the vault"},
		{name: "cloudflare with an unknown link token", input: "link-token-" + dummy + "\n", args: []string{"cloudflare"}, wantCode: 1, secrets: []string{dummy}},
		{name: "cloudflare", args: []string{"cloudflare"}, prepare: func(h *harness) { linkToken = h.addLinkToken() }, want: "Deleted the link token"},
		{name: "save-a-key with a refused token", input: "ghp_" + dummy + "\n", args: []string{"save-a-key", registryTokenVaultKey}, wantCode: 1,
			secrets: []string{dummy}, want: "GitHub refused GET /user with HTTP 401"},
		{name: "save-a-key with a token that ends too soon", input: endsTooSoonRegistryToken + "\n", args: []string{"save-a-key", registryTokenVaultKey}, wantCode: 1,
			secrets: []string{endsTooSoonRegistryToken}, want: "less than 30 days from now"},
		{name: "save-a-key", input: registryToken + "\n", args: []string{"save-a-key", registryTokenVaultKey}, secrets: []string{registryToken}, want: "GitHub accepted the token"},
		{name: "save-a-key with a refused Stripe key", input: "sk_live_" + dummy + "\n", args: []string{"save-a-key", "shop_STRIPE_API_KEY"}, wantCode: 1,
			secrets: []string{dummy}, want: "Stripe refused GET /v1/balance with HTTP 401, code api_key_invalid"},
		{name: "save-a-key with no input", input: "", args: []string{"save-a-key", "shop_STRIPE_API_KEY"}, wantCode: 1, want: "line 1 of standard input"},
		{name: "save-a-key with a Stripe key", input: stripeKey + "\n", args: []string{"save-a-key", "shop_STRIPE_API_KEY"}, secrets: []string{stripeKey}, want: "Stripe accepted the key."},
		{name: "random-secrets without the provider credential", args: []string{"random-secrets"}, wantCode: 1,
			prepare: func(h *harness) { delete(h.rootFiles, "/etc/systems-desk/provider-api-token.conf") }, want: "no server provider key"},
		{name: "random-secrets", args: []string{"random-secrets"}, secrets: []string{providerToken},
			prepare: func(h *harness) {
				h.rootFiles["/etc/systems-desk/provider-api-token.conf"] = `proxy_set_header Authorization "Bearer ` + providerToken + `";` + "\n"
			}, want: "Made and saved in the vault:"},
	}
	for _, r := range runs {
		if r.prepare != nil {
			r.prepare(h)
		}
		input := r.input
		if r.name == "cloudflare" {
			input = linkToken + "\n"
			r.secrets = []string{linkToken}
		}
		code, out, errorOut := h.fromTheCodingAgent(input, r.args...)
		t.Logf("%s: exit %d\n%s%s", r.name, code, out, errorOut)
		if code != r.wantCode {
			t.Errorf("%s: exit code %d, want %d", r.name, code, r.wantCode)
		}
		if r.want != "" && !strings.Contains(out+errorOut, r.want) {
			t.Errorf("%s: the output lacks %q", r.name, r.want)
		}
		if r.wantCode != 0 && !strings.HasPrefix(errorOut, "Stopped: ") {
			t.Errorf("%s: standard error does not give the reason: %q", r.name, errorOut)
		}
		results, _ := os.ReadFile(h.e.resultsFile)
		secrets := append([]string{}, r.secrets...)
		for key, value := range h.vault.values {
			if !strings.HasSuffix(key, "_key_id") && !strings.HasSuffix(key, "_ACCESS_KEY_ID") {
				secrets = append(secrets, value)
			}
		}
		for key, value := range h.bundle.values {
			if !strings.HasSuffix(key, "_key_id") {
				secrets = append(secrets, value)
			}
		}
		for _, secret := range secrets {
			for where, text := range map[string]string{"standard output": out, "standard error": errorOut, "the results file": string(results)} {
				if strings.Contains(text, secret) {
					t.Errorf("%s: %s shows a secret", r.name, where)
				}
			}
		}
	}
	// What the coding agent reads afterwards.
	results := h.results()
	for step, want := range map[string]string{"backblaze": stepDone, "cloudflare": stepDone, registryTokenVaultKey: stepDone, "shop_STRIPE_API_KEY": stepDone, "random_secrets": stepDone} {
		if got := results.state(step); got != want {
			t.Errorf("step %s is %q, want %q", step, got, want)
		}
	}
	for name, want := range map[string]string{"b2_account_region": "us-west-004", "b2_account_s3_endpoint": "s3.us-west-004.backblazeb2.com",
		"cloudflare_account_id": testAccountID, "container_registry_read_only_username": "alex-acme", "container_image_found": "no, not built yet"} {
		if results.ForTheCodingAgent[name] != want {
			t.Errorf("for_the_coding_agent.%s = %q, want %q", name, results.ForTheCodingAgent[name], want)
		}
	}
	if h.vault.values["util01_provider_api_token"] != providerToken || h.vault.values[registryTokenVaultKey] != registryToken || h.vault.values["shop_STRIPE_API_KEY"] != stripeKey {
		t.Error("the vault lacks a value the coding agent passed")
	}
	// The bundle got each item as it was made, and the backblaze command kept
	// the write key for the bundle's upload, root-only.
	for _, key := range []string{"pgbackrest_repository_cipher_passphrase", "pgbackrest_b2_read_only_key_id", "pgbackrest_b2_read_only_application_key"} {
		if h.bundle.values[key] == "" || h.bundle.values[key] != h.vault.values[key] {
			t.Errorf("the recovery bundle lacks %s", key)
		}
	}
	kept, err := os.Stat(h.e.backupWriteKeyFile)
	if err != nil || kept.Mode().Perm() != 0o600 || mustRead(t, h.e.backupWriteKeyFile) != h.vault.values["pgbackrest_b2_write_key_id"]+"\n"+h.vault.values["pgbackrest_b2_write_application_key"]+"\n" {
		t.Errorf("the backup write key was not kept for the bundle's upload: %v", err)
	}
}

// The region refusal saves nothing: no bucket, no key, no vault value.
func TestABackblazeAccountInAnotherRegionChangesNothing(t *testing.T) {
	h := newHarness(t, false, false)
	h.b2.S3APIURL = "https://s3.us-west-004.backblazeb2.com"
	if code, _, _ := h.fromTheCodingAgent(masterKeyID+"\n"+masterKey+"\n", "backblaze"); code != 1 {
		t.Fatalf("exit code %d, want 1", code)
	}
	if len(h.b2.Buckets) != 0 || len(h.b2.LiveKeysNamed("acme-systems-pgbackrest-write")) != 0 || len(h.vault.sets) != 0 {
		t.Fatal("a refused region made a bucket, a key or a vault value")
	}
	if !strings.Contains(h.results().StoppedWith, "b2_s3_endpoint and b2_region") {
		t.Errorf("stopped_with does not say what to set: %q", h.results().StoppedWith)
	}
}

func mustRead(t *testing.T, path string) string {
	t.Helper()
	text, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	return string(text)
}
