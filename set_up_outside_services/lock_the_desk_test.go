package main

import (
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

// lockHarness runs the setup as the coding agent and the person do: the
// account commands from the coding agent, then lock-the-desk in the
// person's window, with the recovery bundle in a real MMX vault.
type lockHarness struct {
	*harness
	phoneCode func(path string) error
	// passphrase is the recovery passphrase the screen showed.
	passphrase string
}

func newLockHarness(t *testing.T) *lockHarness {
	t.Helper()
	if _, err := exec.LookPath("mmx"); err != nil {
		t.Skip("lock-the-desk's tests keep the recovery bundle in a real MMX vault, so they need mmx on PATH")
	}
	h := &lockHarness{harness: newHarness(t, false, false)}
	h.e.bundleStore = nil
	for path, content := range map[string]string{
		"/etc/systems-desk/provider-api-token.conf": `proxy_set_header Authorization "Bearer ` + providerToken + `";` + "\n",
		deskVaultPassphraseFile:                     vaultPassphrase + "\n",
		deskWireGuardPrivateKeyFile:                 "wireguardprivatekeyvalue=\n",
	} {
		h.rootFiles[path] = content
	}
	writeFile(t, filepath.Join(h.e.home, ".ssh/production_key"), "-----BEGIN OPENSSH PRIVATE KEY-----\nproduction\n-----END OPENSSH PRIVATE KEY-----\n")
	h.phoneCode = func(path string) error { return os.WriteFile(path, []byte(emergencyCodes+"\n"), 0o600) }
	h.e.setUpThePhoneCode = func(path string) error { return h.phoneCode(path) }
	h.e.deskIsLocked = func() bool { return false }
	h.e.clearScreen = func() { h.out.WriteString("\n[the screen is cleared]\n") }
	// The person saves what the screen shows and types it back.
	consolePassword := regexp.MustCompile(`----\n  ([a-z-]+)\n  ----`)
	h.e.confirm = func(string) (string, error) { return "", nil }
	h.e.prompt = func(label string) (string, error) {
		text := h.out.String()
		switch {
		case strings.Contains(label, "Type the password"):
			matches := consolePassword.FindAllStringSubmatch(text, -1)
			return matches[len(matches)-1][1], nil
		case strings.Contains(label, "Recovery passphrase"):
			after := text[strings.LastIndex(text, "IT IS SHOWN ONLY ONCE.")+len("IT IS SHOWN ONLY ONCE."):]
			// The line as the screen shows it, without its indent: a copy
			// pasted as displayed must open the bundle.
			h.passphrase = strings.TrimSpace(strings.SplitN(strings.TrimLeft(after, "\n"), "\n", 2)[0])
			return h.passphrase, nil
		}
		return "", errors.New("unexpected prompt " + label)
	}
	return h
}

// accounts runs the coding agent's account commands.
func (h *lockHarness) accounts() {
	h.t.Helper()
	for _, run := range []struct {
		input     string
		arguments []string
	}{
		{h.addLinkToken() + "\n", []string{"cloudflare"}},
		{masterKeyID + "\n" + masterKey + "\n", []string{"backblaze"}},
		{registryToken + "\n", []string{"save-a-key", registryTokenVaultKey}},
		{"", []string{"random-secrets"}},
	} {
		if code, out, errorOut := h.fromTheCodingAgent(run.input, run.arguments...); code != 0 {
			h.t.Fatalf("%v: exit %d\n%s%s", run.arguments, code, out, errorOut)
		}
	}
}

func (h *lockHarness) bundleKeys() map[string]bool {
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

func (h *lockHarness) passphraseFile() string {
	return filepath.Join(h.e.home, ".config/monkeymaxxing-stack/acme_systems_recovery_passphrase_until_the_bundle_is_saved")
}

// The accounts from the coding agent, then the lock: the bundle holds every
// item, is pushed with the vault, and is copied into the locked backup
// bucket with the write key the backblaze command kept, which is then gone.
func TestTheAccountsFromTheCodingAgentThenTheLock(t *testing.T) {
	h := newLockHarness(t)
	h.accounts()
	if err := runLockTheDesk(h.e); err != nil {
		t.Fatalf("lock-the-desk: %v\n%s", err, h.out)
	}
	output := h.out.String()
	at := 0
	for _, line := range []string{"step 1 of 3, your servers' console password", "[the screen is cleared]",
		"step 2 of 3, your recovery passphrase", "SAVE IT NOW.  IT IS SHOWN ONLY ONCE.", "[the screen is cleared]", "step 3 of 3, your phone code",
		"Copied the recovery bundle into the locked backup bucket acme-systems-backups", "Done.  Your phone code is ready."} {
		next := strings.Index(output[at:], line)
		if next < 0 {
			t.Fatalf("the screens lack %q after position %d:\n%s", line, at, output)
		}
		at += next
	}
	keys := h.bundleKeys()
	for _, key := range []string{bundleVaultPassphrase, bundleProductionKey, bundleWireGuardKey, bundleProviderCredential, bundleCloudflareDeskToken,
		bundleConsolePassword, bundlePhoneCodeEmergencyCode, bundleSystemsDeskName, "pgbackrest_repository_cipher_passphrase", "pgbackrest_b2_read_only_key_id", "pgbackrest_b2_read_only_application_key"} {
		if !keys[key] {
			t.Errorf("the bundle lacks %s", key)
		}
	}
	if !strings.HasPrefix(h.vault.values[consolePasswordVaultKey], "$6$") {
		t.Error("the vault lacks the console password's hash")
	}
	copies := 0
	for _, file := range h.b2.Files {
		if strings.HasPrefix(file.Name, "recovery_bundle/") && file.BucketID == bucketNamed(h.b2, "acme-systems-backups").ID && file.Mode == "compliance" {
			copies++
		}
	}
	if copies != 1 {
		t.Fatalf("want one locked copy of the bundle at Backblaze, got %d", copies)
	}
	for _, path := range []string{h.e.backupWriteKeyFile, h.passphraseFile()} {
		if _, err := os.Stat(path); !errors.Is(err, os.ErrNotExist) {
			t.Errorf("%s stays after the bundle is saved", path)
		}
	}
	if files := strings.TrimSpace(h.git(h.e.directory, "--git-dir", h.origin, "diff-tree", "--no-commit-id", "--name-only", "-r", "main")); files != recoveryBundleFile+"\n"+vaultFile {
		t.Errorf("the lock's commit changes %q, want the bundle and the vault", files)
	}
	results := h.results()
	if !results.Finished || results.StoppedWith != "" {
		t.Fatalf("the results are not finished: %+v", results)
	}
	for _, step := range results.Steps {
		if step.State != stepDone {
			t.Errorf("step %s is %s", step.Name, step.State)
		}
	}
	file := mustRead(t, h.e.resultsFile)
	for _, secret := range []string{providerToken, masterKey, registryToken, h.passphrase, vaultPassphrase, "11111111"} {
		if strings.Contains(file, secret) {
			t.Error("the results file holds a secret")
		}
	}
	h.requireNoSecretInOutput(providerToken, masterKey, registryToken, vaultPassphrase, "11111111")
	if strings.Count(output, h.passphrase) != 1 {
		t.Error("the recovery passphrase shows more than once")
	}

	// A rerun after the end asks nothing, and a later key rotation leaves
	// the saved bundle alone.
	h.out.Reset()
	if err := runLockTheDesk(h.e); err != nil || !strings.Contains(h.out.String(), "done already") {
		t.Fatalf("a rerun of a finished lock: %v\n%s", err, h.out)
	}
	answers := []string{masterKeyID, masterKey}
	h.e.prompt = func(string) (string, error) {
		answer := answers[0]
		answers = answers[1:]
		return answer, nil
	}
	if err := runBackblaze(h.e, []string{"--replace-key", "pgbackrest_b2_read_only_key_id", deleteTheOldKeysAtOnceFlag}); err != nil {
		t.Fatalf("a rotation after the lock: %v\n%s", err, h.out)
	}
	if _, err := os.Stat(h.passphraseFile()); !errors.Is(err, os.ErrNotExist) {
		t.Error("a rotation after the lock opened a new bundle")
	}
}

// lock-the-desk refuses before its first screen while an account command
// has not run, and names each missing item with the command that makes it.
func TestLockTheDeskRefusesBeforeItsFirstScreenWhileAnAccountIsMissing(t *testing.T) {
	h := newLockHarness(t)
	if code, out, errorOut := h.fromTheCodingAgent(h.addLinkToken()+"\n", "cloudflare"); code != 0 {
		t.Fatalf("cloudflare: exit %d\n%s%s", code, out, errorOut)
	}
	err := runLockTheDesk(h.e)
	if err == nil || !strings.Contains(err.Error(), "pgbackrest_b2_read_only_key_id (set-up-outside-services backblaze)") ||
		!strings.Contains(err.Error(), "pgbackrest_repository_cipher_passphrase (set-up-outside-services from-the-coding-agent random-secrets)") {
		t.Fatalf("want the refusal naming the missing items, got %v", err)
	}
	if strings.Contains(h.out.String(), "step 1 of 3") || !strings.Contains(h.results().StoppedWith, "lacks") {
		t.Fatal("the refusal came after a screen, or is not in the results file")
	}
}

// A lock stopped at the phone code continues there, and the bundle keeps
// what the first run put in it.
func TestLockTheDeskContinuesWhereARunStopped(t *testing.T) {
	h := newLockHarness(t)
	h.accounts()
	h.phoneCode = func(string) error {
		return errors.New("set-up-the-phone-code stopped (exit status 1), so the systems desk is not locked yet")
	}
	if err := runLockTheDesk(h.e); err == nil || !strings.Contains(err.Error(), "Go back to your coding agent") {
		t.Fatalf("want the stop at the phone code, got %v", err)
	}
	for step, want := range map[string]string{"shared_root_console_password": stepDone, "recovery_passphrase": stepDone, "phone_code": stepInProgress} {
		if got := h.results().state(step); got != want {
			t.Errorf("after the stop, step %s is %q, want %q", step, got, want)
		}
	}
	h.out.Reset()
	h.phoneCode = func(path string) error { return os.WriteFile(path, []byte(emergencyCodes), 0o600) }
	if err := runLockTheDesk(h.e); err != nil {
		t.Fatalf("rerun: %v\n%s", err, h.out)
	}
	for _, screen := range []string{"step 1 of 3", "step 2 of 3"} {
		if strings.Contains(h.out.String(), screen) {
			t.Errorf("the rerun showed %q again", screen)
		}
	}
	keys := h.bundleKeys()
	if !keys[bundleConsolePassword] || !keys[bundlePhoneCodeEmergencyCode] || !keys["pgbackrest_repository_cipher_passphrase"] {
		t.Fatalf("the bundle lost what the first run put in it: %v", keys)
	}
	if !h.results().Finished {
		t.Fatal("the rerun did not finish")
	}
}

// lock-the-desk says the desk is locked only when the lock stage ran: the
// lock's record exists and root's login from the laptop is closed.
func TestTheDeskIsLockedOnlyWithTheRecordAndWithoutTheRootLoginFile(t *testing.T) {
	directory := t.TempDir()
	locked, beforeTheLock := filepath.Join(directory, "locked"), filepath.Join(directory, "root-login-before-the-lock.conf")
	for _, c := range []struct {
		record, rootLogin, want bool
	}{{false, true, false}, {true, true, false}, {false, false, false}, {true, false, true}} {
		os.Remove(locked)
		os.Remove(beforeTheLock)
		if c.record {
			writeFile(t, locked, "This systems desk is locked.\n")
		}
		if c.rootLogin {
			writeFile(t, beforeTheLock, "Match User root\n")
		}
		if got := deskIsLockedAt(locked, beforeTheLock); got != c.want {
			t.Errorf("record %v, root login file %v: locked %v, want %v", c.record, c.rootLogin, got, c.want)
		}
	}
	e := &environment{deskIsLocked: func() bool { return true }}
	if message := lockDoneMessage(e); !strings.HasPrefix(message, "\nDone.  Your systems desk is locked.") {
		t.Errorf("a locked systems desk: %q", message)
	}
	e.deskIsLocked = func() bool { return false }
	if message := lockDoneMessage(e); strings.Contains(message, "is locked") {
		t.Errorf("a systems desk that is not locked yet: %q", message)
	}
}

// bundleCopies counts the recovery bundle's copies at Backblaze.
func (h *lockHarness) bundleCopies() int {
	copies := 0
	for _, file := range h.b2.Files {
		if strings.HasPrefix(file.Name, "recovery_bundle/") {
			copies++
		}
	}
	return copies
}

// A lock stopped after the bundle's upload, while it removes the kept write
// key, has recorded the upload: the rerun only removes what is left, never
// uploads again and never asks to delete the bundle.
func TestLockTheDeskRecordsTheUploadBeforeItRemovesTheKeptFiles(t *testing.T) {
	h := newLockHarness(t)
	h.accounts()
	removeFileAsRoot := h.e.removeFileAsRoot
	h.e.removeFileAsRoot = func(string) error { return errors.New("sudo: interrupted") }
	if err := runLockTheDesk(h.e); err == nil {
		t.Fatal("want the stop at the removal")
	}
	if state := h.results().state("recovery_bundle"); state != stepDone || h.bundleCopies() != 1 {
		t.Fatalf("after the stop, recovery_bundle is %q with %d copies, want done with 1", state, h.bundleCopies())
	}
	h.e.removeFileAsRoot = removeFileAsRoot
	h.out.Reset()
	if err := runLockTheDesk(h.e); err != nil {
		t.Fatalf("rerun: %v\n%s", err, h.out)
	}
	if !h.results().Finished || h.bundleCopies() != 1 {
		t.Fatalf("the rerun did not finish, or uploaded again: %d copies", h.bundleCopies())
	}
	for _, path := range []string{h.e.backupWriteKeyFile, h.passphraseFile()} {
		if _, err := os.Stat(path); !errors.Is(err, os.ErrNotExist) {
			t.Errorf("%s stays after the rerun", path)
		}
	}
}

// The phone code's root step enrolls once and refuses a second time. A lock
// that stops after the enrollment, before the bundle holds the emergency
// codes, takes them from the kept file on the rerun, without enrolling again.
func TestLockTheDeskKeepsTheEmergencyCodesUntilTheBundleHoldsThem(t *testing.T) {
	h := newLockHarness(t)
	h.accounts()
	h.phoneCode = func(path string) error {
		if err := os.WriteFile(path, []byte(emergencyCodes+"\n"), 0o600); err != nil {
			return err
		}
		return errors.New("the connection dropped after the phone code was set up")
	}
	if err := runLockTheDesk(h.e); err == nil {
		t.Fatal("want the stop at the phone code")
	}
	h.phoneCode = func(string) error {
		return errors.New("This systems desk's phone code is already set up. Nothing changed.")
	}
	h.out.Reset()
	if err := runLockTheDesk(h.e); err != nil {
		t.Fatalf("rerun: %v\n%s", err, h.out)
	}
	if !h.bundleKeys()[bundlePhoneCodeEmergencyCode] || !h.results().Finished {
		t.Fatal("the bundle lacks the emergency codes, or the lock did not finish")
	}
	if _, err := os.Stat(h.e.phoneCodeEmergencyCodesFile(systemSettings{projectSettings: projectSettings{ProjectName: "acme_systems"}})); !errors.Is(err, os.ErrNotExist) {
		t.Error("the emergency codes file stays after the bundle holds the codes")
	}
}

// A bundle item the vault holds already is made again by its rotation, not
// by the command that made it, which skips a key the vault holds.
func TestAMissingBundleItemTheVaultHoldsNamesItsRotation(t *testing.T) {
	vault := &savedKeys{names: map[string]bool{"pgbackrest_repository_cipher_passphrase": true, "pgbackrest_b2_read_only_key_id": true}}
	err := refuseMissingItems([]string{"pgbackrest_b2_read_only_key_id", "pgbackrest_repository_cipher_passphrase", bundleCloudflareDeskToken}, vault, makeANewRecoveryBundleCommand)
	for _, want := range []string{"then run " + makeANewRecoveryBundleCommand + " again", "pgbackrest_repository_cipher_passphrase (set-up-outside-services secrets --replace pgbackrest_repository_cipher_passphrase)",
		"pgbackrest_b2_read_only_key_id (set-up-outside-services backblaze --replace-key pgbackrest_b2_read_only_key_id)",
		bundleCloudflareDeskToken + " (set-up-outside-services cloudflare)"} {
		if err == nil || !strings.Contains(err.Error(), want) {
			t.Errorf("want %q in %v", want, err)
		}
	}
}

// The screen shows the passphrase exactly as the bundle needs it, one space
// between words, and takes back only that exact text, apart from spaces at
// its ends. A copy that differs only in capital letters or spaces is
// refused with a message that says so, because MMX would refuse it later.
func TestTheRecoveryPassphraseScreenWantsTheExactPassphrase(t *testing.T) {
	h := newHarness(t, false, false)
	h.e.clearScreen = func() {}
	passphrase := "apple banana cherry delta echo fox"
	typed := []string{"apple  banana  cherry  delta  echo  fox", "Apple banana cherry delta echo fox", "  " + passphrase + " "}
	h.e.prompt = func(string) (string, error) {
		answer := typed[0]
		typed = typed[1:]
		return answer, nil
	}
	if err := h.e.recoveryPassphraseScreen(mustSettings(t, h.e), passphrase, "Title", "Save it in", "The lock"); err != nil {
		t.Fatal(err)
	}
	output := h.out.String()
	if !strings.Contains(output, "\n    "+passphrase+"\n") {
		t.Errorf("the screen does not show the passphrase with one space between words:\n%s", output)
	}
	if len(typed) != 0 || strings.Count(output, "differs from the passphrase above only in capital letters or spaces") != 2 {
		t.Errorf("want the two near copies refused as such and the exact one taken:\n%s", output)
	}
}
