package main

import (
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

// The keys the template's playbooks read, as mmx secrets usage lists them,
// for a system with staging01 and one app.
var templateKeys = []string{
	"apps_cloudflare_tunnel_token", "shared_root_console_password_hash", "container_registry_read_only_token",
	"database_moving_in_relay_admin_password", "mmhotline_signing_secret_of_the_fleet_hub",
	"mmhotline_triage_agent_credential", "mmwatchdog_pushover_user_or_group_key", "mmx_vault_passphrase",
	"pg_auto_failover_autoctl_node_password", "pg_auto_failover_replication_password",
	"pgbackrest_b2_write_key_id", "pgbackrest_repository_cipher_passphrase", "pushover_application_token",
	"shop_R2_ACCESS_KEY_ID", "shop_SECRET_KEY_BASE", "shop_STRIPE_API_KEY", "shop_database_password",
	"staging_shop_SECRET_KEY_BASE", "staging_shop_STRIPE_API_KEY",
	"staging_shop_database_password", "util01_provider_api_token", "a_key_of_the_teams_own",
}

// stripeSecret is an app secret from an outside service, as the coding agent
// writes it into secrets_from_vault.
const stripeSecret = `        STRIPE_API_KEY:
          where_the_value_comes_from: an_outside_service
          what_it_is_for: Stripe takes your customers' card payments with it.
          steps_to_get_it:
            - Open  https://dashboard.stripe.com/apikeys
            - Press  Reveal live key,  then copy it.
          checked_with: stripe
`

// secretsRepository makes the harness's directory a Git checkout of a
// bare origin, the way the desk's repository is one, and returns git and origin.
func (h *harness) secretsRepository() (func(directory string, arguments ...string) string, string) {
	h.t.Helper()
	if h.git != nil {
		return h.git, h.origin
	}
	origin := filepath.Join(h.t.TempDir(), "origin.git")
	run := func(directory string, arguments ...string) string {
		h.t.Helper()
		command := exec.Command("git", append([]string{"-c", "init.defaultBranch=main", "-c", "user.name=Alex", "-c", "user.email=alex@example.org"}, arguments...)...)
		command.Dir = directory
		output, err := command.CombinedOutput()
		if err != nil {
			h.t.Fatalf("git %v: %v\n%s", arguments, err, output)
		}
		return string(output)
	}
	directory := h.e.directory
	run(h.t.TempDir(), "init", "--bare", "--quiet", origin)
	run(directory, "init", "--quiet", "-b", "main")
	for _, setting := range [][2]string{{"user.name", "Alex"}, {"user.email", "alex@example.org"}} {
		run(directory, "config", setting[0], setting[1])
	}
	h.vault.file = filepath.Join(directory, vaultFile)
	writeFile(h.t, h.vault.file, "vault\n")
	run(directory, "add", "-A")
	run(directory, "commit", "--quiet", "-m", "Systems repository")
	run(directory, "remote", "add", "origin", origin)
	run(directory, "push", "--quiet", "-u", "origin", "main")
	h.e.git = gitInRepository(directory)
	h.git, h.origin = run, origin
	return run, origin
}

// prompts records each question and answers from two queues: hidden
// prompts and visible questions.
func (h *harness) answerSecrets(hidden, visible []string) *[]string {
	asked := &[]string{}
	h.answers = hidden
	h.e.confirm = func(label string) (string, error) {
		*asked = append(*asked, label)
		if len(visible) == 0 {
			h.t.Fatalf("unexpected question %q", label)
		}
		answer := visible[0]
		visible = visible[1:]
		return answer, nil
	}
	prompt := h.e.prompt
	h.e.prompt = func(label string) (string, error) {
		*asked = append(*asked, label)
		return prompt(label)
	}
	return asked
}

func TestSecretsSkipsSavedKeysMakesRandomOnesAndPushesASignedCommit(t *testing.T) {
	h := newHarness(t, true, true)
	h.vault.referenced = templateKeys
	h.vault.values["pushover_application_token"] = "saved-before"
	settingsPath := filepath.Join(h.e.directory, projectSettingsFile)
	text, _ := os.ReadFile(settingsPath)
	writeFile(t, settingsPath, strings.Replace(string(text), "      secrets_from_vault:\n", "      secrets_from_vault:\n"+stripeSecret, 1))
	h.commitAll("Add the Stripe key")
	h.vault.values["shared_root_console_password_hash"] = "$6$saved-before"
	run, origin := h.secretsRepository()
	asked := h.answerSecrets(
		// util01's token, the group key, the triage key, the registry token,
		// then the two Stripe keys.
		[]string{"util01-token-value", "group-key-value", "triage-key-value", "registry-token-value", "sk_live_value", "sk_test_value"},
		// The triage credential's kind; the app's secrets ask nothing.
		[]string{""})
	if err := runSecrets(h.e, nil); err != nil {
		t.Fatalf("secrets: %v\n%s", err, h.out)
	}
	if !strings.Contains(h.out.String(), "credential_type: api_key under triage_agent in mmhotline_settings.yml") {
		t.Errorf("the output does not tell the coding agent the default credential_type:\n%s", h.out)
	}
	if h.vault.values["pushover_application_token"] != "saved-before" || strings.Contains(strings.Join(*asked, "\n"), "Pushover application") ||
		h.vault.values["shared_root_console_password_hash"] != "$6$saved-before" || strings.Contains(strings.Join(*asked, "\n"), "console password") {
		t.Fatalf("a key the vault had was asked for or changed:\n%s", strings.Join(*asked, "\n"))
	}
	for key, want := range map[string]string{"util01_provider_api_token": "util01-token-value", "mmwatchdog_pushover_user_or_group_key": "group-key-value",
		"mmhotline_triage_agent_credential": "triage-key-value", "container_registry_read_only_token": "registry-token-value",
		"shop_STRIPE_API_KEY": "sk_live_value", "staging_shop_STRIPE_API_KEY": "sk_test_value"} {
		if h.vault.values[key] != want {
			t.Errorf("%s = %q, want the pasted value", key, h.vault.values[key])
		}
	}
	for _, key := range []string{"shop_SECRET_KEY_BASE", "staging_shop_SECRET_KEY_BASE", "pg_auto_failover_autoctl_node_password",
		"pg_auto_failover_replication_password", "pgbackrest_repository_cipher_passphrase",
		"shop_database_password", "staging_shop_database_password"} {
		if h.vault.values[key] == "" {
			t.Errorf("the random key %s was not made", key)
		}
	}
	// staging01 keeps no backups, so it needs no backup passphrase.
	if _, ok := h.vault.values["staging_pgbackrest_repository_cipher_passphrase"]; ok {
		t.Error("staging_pgbackrest_repository_cipher_passphrase must not be made")
	}
	if !regexp.MustCompile(`^[0-9a-f]{64}$`).MatchString(h.vault.values["mmhotline_signing_secret_of_the_fleet_hub"]) {
		t.Errorf("the fleet hub's signing secret is not 64 hexadecimal characters")
	}
	for _, key := range []string{"mmx_vault_passphrase", "database_moving_in_relay_admin_password", "a_key_of_the_teams_own", "shop_R2_ACCESS_KEY_ID"} {
		if _, ok := h.vault.values[key]; ok {
			t.Errorf("%s belongs to another command but was made here", key)
		}
	}
	h.requireNoSecretInOutput()
	for _, page := range []string{"https://pushover.net/groups", "https://console.anthropic.com/settings/keys", "https://github.com/settings/tokens/new?scopes=read:packages"} {
		if !strings.Contains(h.out.String(), page) {
			t.Errorf("the output lacks the page %s", page)
		}
	}
	if !strings.Contains(h.out.String(), "a_key_of_the_teams_own") || !strings.Contains(h.out.String(), "shop_R2_ACCESS_KEY_ID (by set-up-outside-services cloudflare)") {
		t.Errorf("the summary does not name the keys left to others:\n%s", h.out)
	}
	if files := strings.TrimSpace(run(h.e.directory, "--git-dir", origin, "diff-tree", "--no-commit-id", "--name-only", "-r", "main")); files != vaultFile {
		t.Fatalf("the pushed commit changes %q, not only the vault", files)
	}

	// A rerun finds nothing missing, asks nothing, and commits nothing.
	h.out.Reset()
	h.answerSecrets(nil, nil)
	before := run(h.e.directory, "rev-parse", "HEAD")
	if err := runSecrets(h.e, nil); err != nil {
		t.Fatalf("rerun: %v\n%s", err, h.out)
	}
	if run(h.e.directory, "rev-parse", "HEAD") != before || !strings.Contains(h.out.String(), "nothing was committed") {
		t.Fatalf("a rerun with nothing missing committed:\n%s", h.out)
	}
}

func TestSecretsRefusesARepositoryWithOtherChangesBeforeAsking(t *testing.T) {
	h := newHarness(t, false, false)
	h.vault.referenced = templateKeys
	h.secretsRepository()
	writeFile(t, filepath.Join(h.e.directory, "inventories/servers.yml"), "groups: {}\n# an edit not committed\n")
	asked := h.answerSecrets(nil, nil)
	err := runSecrets(h.e, nil)
	if err == nil || !strings.Contains(err.Error(), "inventories/servers.yml") {
		t.Fatalf("want a refusal naming the changed file, got %v", err)
	}
	if len(*asked) > 0 || len(h.vault.sets) > 0 {
		t.Fatalf("it asked or saved before refusing: %v %v", *asked, h.vault.sets)
	}
}

func TestSecretsPullsTheTeamsMainBeforeItCommits(t *testing.T) {
	h := newHarness(t, false, false)
	h.vault.referenced = []string{"pg_auto_failover_replication_password"}
	run, origin := h.secretsRepository()
	other := filepath.Join(t.TempDir(), "other")
	run(t.TempDir(), "clone", "--quiet", origin, other)
	writeFile(t, filepath.Join(other, "README.md"), "a teammate's change\n")
	run(other, "add", "README.md")
	run(other, "commit", "--quiet", "-m", "A teammate's change")
	run(other, "push", "--quiet")
	h.answerSecrets(nil, nil)
	if err := runSecrets(h.e, nil); err != nil {
		t.Fatalf("secrets: %v\n%s", err, h.out)
	}
	if log := run(h.e.directory, "--git-dir", origin, "log", "--format=%s", "main"); !strings.Contains(log, "A teammate's change") || !strings.HasPrefix(log, "Add 1 vault keys with set-up-outside-services secrets") {
		t.Fatalf("origin's main lost the teammate's commit or lacks the vault commit:\n%s", log)
	}
}

func TestSecretsPushesAVaultChangeAnEarlierRunLeftAndRefusesUnpushedCommits(t *testing.T) {
	h := newHarness(t, false, false)
	h.vault.referenced = nil
	run, origin := h.secretsRepository()
	writeFile(t, h.vault.file, "vault\nchanged by an interrupted run\n")
	h.answerSecrets(nil, nil)
	if err := runSecrets(h.e, nil); err != nil {
		t.Fatalf("secrets: %v\n%s", err, h.out)
	}
	if run(h.e.directory, "--git-dir", origin, "rev-parse", "main") != run(h.e.directory, "rev-parse", "HEAD") {
		t.Fatalf("the left-over vault change was not pushed:\n%s", h.out)
	}
	writeFile(t, filepath.Join(h.e.directory, "README.md"), "an unpushed change\n")
	run(h.e.directory, "add", "README.md")
	run(h.e.directory, "commit", "--quiet", "-m", "Not pushed")
	if err := runSecrets(h.e, nil); err == nil || !strings.Contains(err.Error(), "1 commits that are not pushed") {
		t.Fatalf("want a refusal of the unpushed commit, got %v", err)
	}
}

func TestSecretsReplaceEntersOneSavedKeyAgain(t *testing.T) {
	h := newHarness(t, false, false)
	h.vault.referenced = templateKeys
	for _, key := range templateKeys {
		h.vault.values[key] = "old-" + key
	}
	h.secretsRepository()
	asked := h.answerSecrets([]string{"new-pushover-token"}, nil)
	if err := runSecrets(h.e, []string{"--replace", "pushover_application_token"}); err != nil {
		t.Fatalf("secrets --replace: %v\n%s", err, h.out)
	}
	if h.vault.values["pushover_application_token"] != "new-pushover-token" || len(*asked) != 1 {
		t.Fatalf("--replace asked %d questions and saved %q", len(*asked), h.vault.values["pushover_application_token"])
	}
	if err := runSecrets(h.e, []string{"--replace", "apps_cloudflare_tunnel_token"}); err == nil || !strings.Contains(err.Error(), "set-up-outside-services cloudflare") {
		t.Fatalf("--replace of another command's key: %v", err)
	}
}

func TestSecretsLeavesATypedKeyForLaterOnEnter(t *testing.T) {
	h := newHarness(t, false, false)
	h.vault.referenced = []string{"pushover_application_token"}
	run, _ := h.secretsRepository()
	before := run(h.e.directory, "rev-parse", "HEAD")
	h.answerSecrets([]string{""}, nil)
	if err := runSecrets(h.e, nil); err != nil {
		t.Fatalf("secrets: %v", err)
	}
	if _, ok := h.vault.values["pushover_application_token"]; ok || run(h.e.directory, "rev-parse", "HEAD") != before {
		t.Fatalf("an empty answer saved or committed something")
	}
	if !strings.Contains(h.out.String(), "Left for later: pushover_application_token.") {
		t.Fatalf("the summary does not list the key left for later:\n%s", h.out)
	}
}

func TestCloudflareLeavesTheStatusPageWhileTheDomainIsPending(t *testing.T) {
	h := newHarness(t, false, true)
	h.cloudflare.ZoneStatus = "pending"
	ranStatusPage := false
	setUp := h.e.runMMHotlineStatusPageSetUp
	h.e.runMMHotlineStatusPageSetUp = func(accountID, hostName, token string) (statusPageSetUp, error) {
		ranStatusPage = true
		return setUp(accountID, hostName, token)
	}
	if err := h.runCloudflare(); err != nil {
		t.Fatalf("cloudflare: %v\n%s", err, h.out)
	}
	if ranStatusPage || h.vault.values["mmhotline_status_page_r2_access_key_id"] != "" {
		t.Fatalf("the status page was set up while the domain is pending")
	}
	if !strings.Contains(h.out.String(), "the status page waits until your domain example.org is Active") &&
		!strings.Contains(h.out.String(), "The status page waits until your domain example.org is Active") {
		t.Fatalf("the output does not say the status page waits:\n%s", h.out)
	}
	if h.vault.values["mmhotline_down_alarm_cloudflare_api_token"] == "" || h.vault.values["apps_cloudflare_tunnel_token"] == "" {
		t.Fatalf("the rest of the run did not finish")
	}
	// Once the domain is Active, a rerun adds the status page.
	h.cloudflare.ZoneStatus = "active"
	h.out.Reset()
	if err := h.runCloudflare(); err != nil {
		t.Fatalf("rerun: %v\n%s", err, h.out)
	}
	if !ranStatusPage || h.vault.values["mmhotline_status_page_r2_access_key_id"] == "" {
		t.Fatalf("the rerun after Active did not set up the status page")
	}
}

func TestCloudflareMakesStagingsServiceTokenOnceIntoTheTokenFile(t *testing.T) {
	h := newHarness(t, true, true)
	if err := h.runCloudflare(); err != nil {
		t.Fatalf("cloudflare: %v\n%s", err, h.out)
	}
	if len(h.cloudflare.ServiceTokens) != 1 || h.cloudflare.ServiceTokens[0].Name != "acme_systems: staging tests" {
		t.Fatalf("want one service token named for staging tests, got %+v", h.cloudflare.ServiceTokens)
	}
	made := h.cloudflare.ServiceTokens[0]
	path := filepath.Join(h.e.home, ".config", "monkeymaxxing-stack", "acme_systems.env")
	if tokenFileValue(path, stagingAccessClientIDVariable) != made.ClientID || tokenFileValue(path, stagingAccessClientSecretVariable) != made.ClientSecret {
		t.Fatalf("the token file does not hold the service token's values")
	}
	if strings.Contains(h.out.String(), made.ClientSecret) {
		t.Fatalf("the output shows the Client Secret")
	}
	if info, err := os.Stat(path); err != nil || info.Mode().Perm() != 0o600 {
		t.Fatalf("the token file is not mode 0600: %v", err)
	}
	if err := h.runCloudflare(); err != nil || len(h.cloudflare.ServiceTokens) != 1 {
		t.Fatalf("a rerun made another service token: %v", err)
	}
	// Another desk, whose token file lacks the values, makes none either.
	h.e.home = t.TempDir()
	h.out.Reset()
	if err := h.runCloudflare(); err != nil || len(h.cloudflare.ServiceTokens) != 1 || !strings.Contains(h.out.String(), "personal-token staging-access") {
		t.Fatalf("another desk's run made a second token or did not say how to enter the saved one: %v\n%s", err, h.out)
	}
}

// consolePasswordRun runs the secrets step for the console password only.
// The person types a wrong password first, then the password shown. It
// returns the steps in order and the password shown last.
func (h *harness) consolePasswordRun(arguments ...string) ([]string, string, error) {
	var events []string
	shown := regexp.MustCompile(`----\n  ([a-z-]+)\n  ----`)
	password := func() string {
		matches := shown.FindAllStringSubmatch(h.out.String(), -1)
		if len(matches) == 0 {
			return ""
		}
		return matches[len(matches)-1][1]
	}
	h.e.clearScreen = func() { events = append(events, "clear") }
	h.e.confirm = func(label string) (string, error) {
		events = append(events, "saved it?")
		return "", nil
	}
	typed := 0
	h.e.prompt = func(label string) (string, error) {
		events = append(events, "type it back")
		typed++
		if typed == 1 {
			return "not-the-password", nil
		}
		return password(), nil
	}
	err := runSecrets(h.e, arguments)
	return events, password(), err
}

func TestSecretsMakesTheConsolePasswordAndSavesOnlyItsHash(t *testing.T) {
	h := newHarness(t, false, false)
	h.vault.referenced = []string{"shared_root_console_password_hash"}
	events, password, err := h.consolePasswordRun()
	if err != nil {
		t.Fatalf("secrets: %v\n%s", err, h.out)
	}
	if !regexp.MustCompile(`^([bcdefghijklnoprstuvx]{5}-){5}[bcdefghijklnoprstuvx]{5}$`).MatchString(password) {
		t.Fatalf("the console password %q is not six groups of five letters", password)
	}
	// Each time it shows, the screen is cleared before the person types it
	// back from the password manager; a mismatch shows it again.
	want := "saved it?,clear,type it back,saved it?,clear,type it back"
	if strings.Join(events, ",") != want {
		t.Fatalf("steps %v, want %s", events, want)
	}
	if !strings.Contains(h.out.String(), "That is not the password shown") || !strings.Contains(h.out.String(), `"Shared root console password"`) {
		t.Fatalf("the output does not name the item or the mismatch:\n%s", h.out)
	}
	if strings.Join(h.vault.sets, ",") != "shared_root_console_password_hash" {
		t.Fatalf("want only the hash saved, got %v", h.vault.sets)
	}
	hash := h.vault.values["shared_root_console_password_hash"]
	if !strings.HasPrefix(hash, "$6$") || strings.Contains(hash, password) {
		t.Fatalf("the vault holds %q, not a SHA-512 crypt hash", hash)
	}
	// The hash verifies against the password: the same salt makes the same hash.
	salt := strings.Split(hash, "$")[2]
	check := exec.Command("openssl", "passwd", "-6", "-salt", salt, "-stdin")
	check.Stdin = strings.NewReader(password + "\n")
	output, err := check.Output()
	if err != nil || strings.TrimSpace(string(output)) != hash {
		t.Fatalf("the hash does not verify against the password: %v", err)
	}
	h.requireNoSecretInOutput()
	if pushed := h.git(h.e.directory, "--git-dir", h.origin, "cat-file", "commit", "main"); !strings.Contains(pushed, "vault keys with set-up-outside-services") {
		t.Fatalf("the hash was not pushed in a vault commit:\n%s", pushed)
	}

	// A rerun keeps the saved hash and asks nothing; --replace makes a new one.
	h.out.Reset()
	events, _, err = h.consolePasswordRun()
	if err != nil || len(events) > 0 || h.vault.values["shared_root_console_password_hash"] != hash {
		t.Fatalf("a rerun asked %v or changed the hash: %v", events, err)
	}
	h.out.Reset()
	if _, _, err := h.consolePasswordRun("--replace", "shared_root_console_password_hash"); err != nil {
		t.Fatalf("--replace: %v", err)
	}
	if replaced := h.vault.values["shared_root_console_password_hash"]; replaced == hash || !strings.HasPrefix(replaced, "$6$") {
		t.Fatalf("--replace did not make a new hash")
	}
}

func TestSecretsAsksWhichTriageCredentialTypeAndGivesEachTypesSource(t *testing.T) {
	for _, test := range []struct{ answer, credentialType, source, otherSource string }{
		{"key", "api_key", "https://console.anthropic.com/settings/keys", "claude setup-token"},
		{"subscription", "subscription_token", "claude setup-token", "console.anthropic.com"},
	} {
		h := newHarness(t, false, false)
		h.vault.referenced = []string{"mmhotline_triage_agent_credential"}
		h.secretsRepository()
		h.answerSecrets([]string{"credential-value"}, []string{test.answer})
		if err := runSecrets(h.e, nil); err != nil {
			t.Fatalf("%s: %v\n%s", test.answer, err, h.out)
		}
		if h.vault.values["mmhotline_triage_agent_credential"] != "credential-value" {
			t.Errorf("%s: the credential was not saved", test.answer)
		}
		out := h.out.String()
		if !strings.Contains(out, "Make it at "+test.source) && !strings.Contains(out, "Make it at your own terminal") ||
			!strings.Contains(out, test.source) || !strings.Contains(out, "credential_type: "+test.credentialType+" under triage_agent") {
			t.Errorf("%s: the output lacks %q or credential_type %s:\n%s", test.answer, test.source, test.credentialType, out)
		}
		if strings.Contains(out, "Make it at "+test.otherSource) {
			t.Errorf("%s: the output shows the other type's source:\n%s", test.answer, out)
		}
		h.requireNoSecretInOutput()
	}
}

// Before util01 exists the desk's checkout has no origin: it is the team's
// main copy, so the vault is committed there, signed, and nothing is pushed.
func TestSecretsCommitsInTheCheckoutWhileItIsTheMainCopy(t *testing.T) {
	h := newHarness(t, false, false)
	h.vault.referenced = []string{"pg_auto_failover_replication_password"}
	run, _ := h.secretsRepository()
	run(h.e.directory, "remote", "remove", "origin")
	h.answerSecrets(nil, nil)
	if err := runSecrets(h.e, nil); err != nil {
		t.Fatalf("secrets: %v\n%s", err, h.out)
	}
	if commit := run(h.e.directory, "cat-file", "commit", "HEAD"); !strings.Contains(commit, "Add 1 vault keys with set-up-outside-services secrets") {
		t.Fatalf("the checkout's main is not the vault commit:\n%s", commit)
	}
	if !strings.Contains(h.out.String(), "the team's main copy until util01 exists") {
		t.Fatalf("the output does not say where main is:\n%s", h.out)
	}
}
