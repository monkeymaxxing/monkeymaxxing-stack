package main

import (
	"bufio"
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"syscall"
	"testing"
	"time"
)

// remakeHarness is a desk whose lock is done, whose recovery passphrase is
// lost: lock-the-desk ran, the lock stage locked the desk, and the phone
// code is set up. phoneCodes records each set of emergency codes the phone
// code was given.
type remakeHarness struct {
	*lockHarness
	oldPassphrase, oldHash, oldBundle string
	phoneCodes                        []string
}

func newRemakeHarness(t *testing.T) *remakeHarness {
	t.Helper()
	h := &remakeHarness{lockHarness: newLockHarness(t)}
	h.accounts()
	if err := runLockTheDesk(h.e); err != nil {
		t.Fatalf("lock-the-desk: %v\n%s", err, h.out)
	}
	h.e.deskIsLocked = func() bool { return true }
	h.rootFiles[deskPhoneCodeFile] = "JBSWY3DPEHPK3PXP\n\" TOTP_AUTH\n" + emergencyCodes + "\n"
	h.e.replaceEmergencyCodes = func(codes string) error {
		h.phoneCodes = append(h.phoneCodes, codes)
		return nil
	}
	h.oldPassphrase, h.oldHash = h.passphrase, h.vault.values[consolePasswordVaultKey]
	h.oldBundle = h.repositoryBundle()
	h.out.Reset()
	return h
}

func (h *remakeHarness) repositoryBundle() string {
	h.t.Helper()
	content, err := os.ReadFile(filepath.Join(h.e.directory, recoveryBundleFile))
	if err != nil {
		h.t.Fatal(err)
	}
	return string(content)
}

// bundleValue reads one item of the repository's bundle with the passphrase
// the screen showed last.
func (h *remakeHarness) bundleValue(key string) string {
	h.t.Helper()
	passwordFile := filepath.Join(h.t.TempDir(), "passphrase")
	writeFile(h.t, passwordFile, h.passphrase+"\n")
	if err := os.Chmod(passwordFile, 0o600); err != nil {
		h.t.Fatal(err)
	}
	value, err := mmxVault{directory: h.t.TempDir(), file: filepath.Join(h.e.directory, recoveryBundleFile), passwordFile: passwordFile}.value(key)
	if err != nil {
		h.t.Fatalf("the new passphrase does not open the new bundle's %s: %v", key, err)
	}
	return value
}

func (h *remakeHarness) lockedCopies() int {
	copies := 0
	for _, file := range h.b2.Files {
		if strings.HasPrefix(file.Name, "recovery_bundle/") && file.Mode == "compliance" {
			copies++
		}
	}
	return copies
}

// requireNothingChanged says a stopped run left the vault, the phone code,
// the repository's bundle and the checkout as they were, and no folder with
// a passphrase on the desk.
func (h *remakeHarness) requireNothingChanged() {
	h.t.Helper()
	if h.vault.values[consolePasswordVaultKey] != h.oldHash {
		h.t.Error("the vault's console password hash changed")
	}
	if len(h.phoneCodes) > 0 {
		h.t.Error("the phone code got new emergency codes")
	}
	if h.repositoryBundle() != h.oldBundle {
		h.t.Error("the repository's recovery bundle changed")
	}
	if status := h.git(h.e.directory, "status", "--porcelain"); status != "" {
		h.t.Errorf("the checkout has changes: %s", status)
	}
	if _, err := os.Stat(h.e.newBundleDirectory(mustSettings(h.t, h.e))); !os.IsNotExist(err) {
		h.t.Error("the new bundle's folder, with its passphrase, stays on the desk")
	}
}

// consolePasswordMatchesHash says whether hash is the SHA-512 crypt hash of
// password, as /etc/shadow checks it.
func consolePasswordMatchesHash(t *testing.T, password, hash string) bool {
	t.Helper()
	parts := strings.Split(hash, "$")
	if len(parts) != 4 || parts[1] != "6" {
		return false
	}
	command := exec.Command("openssl", "passwd", "-6", "-salt", parts[2], "-stdin")
	command.Stdin = strings.NewReader(password + "\n")
	output, err := command.Output()
	if err != nil {
		t.Fatal(err)
	}
	return strings.TrimSpace(string(output)) == hash
}

// After a finished lock whose recovery passphrase is lost, the new bundle
// opens with the new passphrase alone and holds every item the lock
// requires, with the desk's current values, a new console password and new
// emergency codes. It is pushed in place of the old bundle and copied into
// the locked backup bucket, and no secret shows on the screen.
func TestANewRecoveryBundleOpensWithTheNewPassphraseAndHoldsEveryItem(t *testing.T) {
	h := newRemakeHarness(t)
	if err := runMakeANewRecoveryBundle(h.e); err != nil {
		t.Fatalf("make-a-new-recovery-bundle: %v\n%s", err, h.out)
	}
	output := h.out.String()
	if h.passphrase == h.oldPassphrase || strings.Count(output, strings.ReplaceAll(h.passphrase, " ", "  ")) != 1 {
		t.Fatal("the new passphrase is the old one, or shows more than once")
	}
	if !strings.Contains(output, "Save it in place of the old one in 1Password") {
		t.Errorf("the passphrase screen does not say to replace the old one:\n%s", output)
	}

	// The new passphrase opens the bundle in the repository, and each item
	// holds the desk's value.
	keys := h.bundleKeys()
	if len(keys) != 10 {
		t.Errorf("the new bundle holds %d items, want the lock's 10: %v", len(keys), keys)
	}
	want := map[string]string{
		bundleVaultPassphrase:     vaultPassphrase,
		bundleProductionKey:       "-----BEGIN OPENSSH PRIVATE KEY-----\nproduction\n-----END OPENSSH PRIVATE KEY-----",
		bundleWireGuardKey:        "wireguardprivatekeyvalue=",
		bundleProviderCredential:  providerToken,
		bundleCloudflareDeskToken: tokenFileValue(h.e.tokenFilePath(mustSettings(t, h.e)), deskTokenVariable),
	}
	for key := range copiedIntoTheBundle {
		want[key] = h.vault.values[key]
	}
	for key, value := range want {
		if got := h.bundleValue(key); got != value || value == "" {
			t.Errorf("the new bundle's %s is not the desk's value", key)
		}
	}
	// The phone code got the new emergency codes the bundle holds, five
	// codes of 8 digits, none of the old ones.
	codes := h.bundleValue(bundlePhoneCodeEmergencyCode)
	if len(h.phoneCodes) != 1 || h.phoneCodes[0] != codes || !regexp.MustCompile(`^([1-9][0-9]{7}\n){4}[1-9][0-9]{7}$`).MatchString(codes) {
		t.Errorf("the phone code got %q, the bundle holds %q", h.phoneCodes, codes)
	}
	for _, old := range strings.Fields(emergencyCodes) {
		if strings.Contains(codes, old) {
			t.Errorf("the new emergency codes keep the old %s", old)
		}
	}
	consolePassword := h.bundleValue(bundleConsolePassword)
	if len(consolePassword) != 23 || h.vault.values[consolePasswordVaultKey] == h.oldHash ||
		!consolePasswordMatchesHash(t, consolePassword, h.vault.values[consolePasswordVaultKey]) {
		t.Errorf("the console password %q is not a new 4-group password, or the vault's hash is not its hash", consolePassword)
	}

	// Pushed with the vault, and a second locked copy at Backblaze.
	if files := strings.TrimSpace(h.git(h.e.directory, "--git-dir", h.origin, "diff-tree", "--no-commit-id", "--name-only", "-r", "main")); files != recoveryBundleFile+"\n"+vaultFile {
		t.Errorf("the push changes %q, want the bundle and the vault", files)
	}
	if copies := h.lockedCopies(); copies != 2 {
		t.Errorf("want the lock's copy and the new one at Backblaze, got %d", copies)
	}
	if _, err := os.Stat(h.e.newBundleDirectory(mustSettings(t, h.e))); !os.IsNotExist(err) {
		t.Error("the new bundle's folder, with its passphrase, stays on the desk")
	}
	h.requireNoSecretInOutput(providerToken, masterKey, vaultPassphrase, strings.Fields(codes)[0])
}

// The gate is the desk's lock itself, not lock-the-desk's record: a desk
// whose lock-the-desk finished but whose lock stage has not run is refused,
// with lock-the-desk named, before any screen.
func TestANewRecoveryBundleWaitsForTheLock(t *testing.T) {
	h := newRemakeHarness(t)
	h.e.deskIsLocked = func() bool { return false }
	err := runMakeANewRecoveryBundle(h.e)
	if err == nil || !strings.Contains(err.Error(), "lock-the-desk") {
		t.Fatalf("want a refusal naming lock-the-desk, got %v", err)
	}
	if strings.Contains(h.out.String(), "step 1 of 2") {
		t.Fatal("the refusal came after a screen")
	}
	h.requireNothingChanged()
}

// A rebuilt desk, or a teammate's, is locked by the lock stage alone and
// never ran lock-the-desk: it makes a new bundle too.
func TestANewRecoveryBundleOnARebuiltDesk(t *testing.T) {
	h := newRemakeHarness(t)
	if err := h.e.updateResults(func(r *setupResults) { *r = setupResults{} }); err != nil {
		t.Fatal(err)
	}
	if err := runMakeANewRecoveryBundle(h.e); err != nil {
		t.Fatalf("make-a-new-recovery-bundle on a rebuilt desk: %v\n%s", err, h.out)
	}
	if h.repositoryBundle() == h.oldBundle || h.lockedCopies() != 2 {
		t.Error("no new bundle was saved and copied")
	}
}

// A missing input stops the run before its first screen, and changes
// nothing.
func TestANewRecoveryBundleChecksEveryInputBeforeAScreen(t *testing.T) {
	for _, stop := range []struct {
		name, want string
		cause      func(h *remakeHarness)
	}{
		{"no phone code", deskPhoneCodeFile, func(h *remakeHarness) { h.rootFiles[deskPhoneCodeFile] = "" }},
		{"no WireGuard key", deskWireGuardPrivateKeyFile, func(h *remakeHarness) { delete(h.rootFiles, deskWireGuardPrivateKeyFile) }},
		{"Backblaze refuses the write key", "Backblaze", func(h *remakeHarness) { h.b2.Failures["b2_authorize_account"] = "malformed" }},
	} {
		t.Run(stop.name, func(t *testing.T) {
			h := newRemakeHarness(t)
			stop.cause(h)
			err := runMakeANewRecoveryBundle(h.e)
			if err == nil || !strings.Contains(err.Error(), stop.want) {
				t.Fatalf("want a refusal naming %s, got %v", stop.want, err)
			}
			if strings.Contains(h.out.String(), "step 1 of 2") {
				t.Fatalf("the refusal came after a screen:\n%s", h.out)
			}
			h.requireNothingChanged()
		})
	}
}

// A run that stops after both screens but before the upload, here because
// Backblaze refuses the upload, changes nothing live: the vault keeps the
// old hash, the phone code its old emergency codes, and the repository its
// old bundle. The folder with the new passphrase is gone.
func TestAStopBeforeTheUploadChangesNothing(t *testing.T) {
	h := newRemakeHarness(t)
	h.b2.Failures["b2_upload_file"] = "malformed"
	err := runMakeANewRecoveryBundle(h.e)
	if err == nil || !strings.Contains(h.out.String(), "step 2 of 2") {
		t.Fatalf("want a stop at the upload after both screens, got %v\n%s", err, h.out)
	}
	h.requireNothingChanged()
	if h.lockedCopies() != 1 {
		t.Error("a copy was uploaded")
	}
}

// A run that stops after the upload keeps what it needs, and the rerun
// finishes that bundle: no new screen, no second upload, and the vault's
// hash and the phone's codes are the uploaded bundle's.
func TestAStopAfterTheUploadFinishesOnTheRerun(t *testing.T) {
	h := newRemakeHarness(t)
	h.vault.failOn[consolePasswordVaultKey] = true
	err := runMakeANewRecoveryBundle(h.e)
	if err == nil || !strings.Contains(err.Error(), "run "+makeANewRecoveryBundleCommand+" again: it finishes this bundle") {
		t.Fatalf("want a stop after the upload that says the rerun finishes it, got %v", err)
	}
	if h.lockedCopies() != 2 || h.repositoryBundle() != h.oldBundle || len(h.phoneCodes) != 0 {
		t.Fatal("the stop is not right after the upload")
	}
	passphrase := h.passphrase

	delete(h.vault.failOn, consolePasswordVaultKey)
	h.out.Reset()
	if err := runMakeANewRecoveryBundle(h.e); err != nil {
		t.Fatalf("the rerun: %v\n%s", err, h.out)
	}
	if strings.Contains(h.out.String(), "step 1 of 2") || strings.Contains(h.out.String(), "step 2 of 2") || h.passphrase != passphrase {
		t.Fatalf("the rerun showed a screen again:\n%s", h.out)
	}
	if h.lockedCopies() != 2 {
		t.Error("the rerun uploaded another copy")
	}
	if !consolePasswordMatchesHash(t, h.bundleValue(bundleConsolePassword), h.vault.values[consolePasswordVaultKey]) {
		t.Error("the vault's hash is not the uploaded bundle's console password")
	}
	if len(h.phoneCodes) != 1 || h.phoneCodes[0] != h.bundleValue(bundlePhoneCodeEmergencyCode) {
		t.Error("the phone code did not get the uploaded bundle's emergency codes")
	}
	if files := strings.TrimSpace(h.git(h.e.directory, "--git-dir", h.origin, "diff-tree", "--no-commit-id", "--name-only", "-r", "main")); files != recoveryBundleFile+"\n"+vaultFile {
		t.Errorf("the push changes %q, want the bundle and the vault", files)
	}
	if _, err := os.Stat(h.e.newBundleDirectory(mustSettings(t, h.e))); !os.IsNotExist(err) {
		t.Error("the new bundle's folder, with its passphrase, stays on the desk")
	}
}

// Two runs at once would share one folder, so the second is refused before
// it changes anything.
func TestANewRecoveryBundleOneRunAtATime(t *testing.T) {
	h := newRemakeHarness(t)
	release, err := h.e.oneRunAtATime()
	if err != nil {
		t.Fatal(err)
	}
	defer release()
	err = runMakeANewRecoveryBundle(h.e)
	if err == nil || !strings.Contains(err.Error(), "another terminal") {
		t.Fatalf("want a refusal of the second run, got %v", err)
	}
	if strings.Contains(h.out.String(), "step 1 of 2") {
		t.Fatal("the refusal came after a screen")
	}
}

// The settings and the inventory are read after the pull: a staging01 a
// teammate pushed is in the bundle's check, so this desk, without staging's
// Access token, is refused.
func TestANewRecoveryBundleReadsTheSettingsAfterThePull(t *testing.T) {
	h := newRemakeHarness(t)
	teammate := t.TempDir()
	h.git(teammate, "clone", "--quiet", h.origin, ".")
	writeFile(t, filepath.Join(teammate, inventoryFile), "groups:\n  staging_server:\n    nodes: [staging01]\n")
	h.git(teammate, "commit", "--quiet", "-am", "Add staging01")
	h.git(teammate, "push", "--quiet", "origin", "HEAD:main")

	err := runMakeANewRecoveryBundle(h.e)
	if err == nil || !strings.Contains(err.Error(), bundleStagingAccessClientID) {
		t.Fatalf("want a refusal naming %s, got %v", bundleStagingAccessClientID, err)
	}
	if strings.Contains(h.out.String(), "step 1 of 2") {
		t.Fatal("the refusal came after a screen")
	}
}

// Ctrl-C at a screen removes the folder that holds the new passphrase. The
// stop exits the process, so a child test process runs the command, and
// this test presses Ctrl-C.
func TestCtrlCRemovesTheNewPassphrase(t *testing.T) {
	if os.Getenv("REMAKE_WAITS_AT_A_SCREEN") == "" {
		t.Skip("runs only as TestCtrlCRemovesTheNewPassphraseFromAScreen's child")
	}
	h := newRemakeHarness(t)
	h.e.handleInterrupts()
	h.e.confirm = func(string) (string, error) {
		os.Stdout.WriteString("waiting " + h.e.newBundleDirectory(mustSettings(t, h.e)) + "\n")
		select {}
	}
	_ = runMakeANewRecoveryBundle(h.e)
	t.Fatal("the command did not wait at the screen")
}

func TestCtrlCRemovesTheNewPassphraseFromAScreen(t *testing.T) {
	if _, err := exec.LookPath("mmx"); err != nil {
		t.Skip("needs mmx on PATH")
	}
	child := exec.Command(os.Args[0], "-test.run=^TestCtrlCRemovesTheNewPassphrase$", "-test.count=1")
	// The child's own temporary folders stay after its stop; this test's
	// cleanup removes them.
	child.Env = append(os.Environ(), "REMAKE_WAITS_AT_A_SCREEN=1", "TMPDIR="+t.TempDir())
	output, err := child.StdoutPipe()
	if err != nil {
		t.Fatal(err)
	}
	if err := child.Start(); err != nil {
		t.Fatal(err)
	}
	folder := ""
	lines := bufio.NewScanner(output)
	for lines.Scan() {
		if after, found := strings.CutPrefix(lines.Text(), "waiting "); found {
			folder = after
			break
		}
	}
	if folder == "" {
		_ = child.Process.Kill()
		t.Fatal("the child never reached the screen")
	}
	if _, err := os.Stat(filepath.Join(folder, "recovery_passphrase")); err != nil {
		_ = child.Process.Kill()
		t.Fatalf("the folder holds no passphrase at the screen: %v", err)
	}
	if err := child.Process.Signal(syscall.SIGINT); err != nil {
		t.Fatal(err)
	}
	done := make(chan error, 1)
	go func() { done <- child.Wait() }()
	select {
	case err = <-done:
	case <-time.After(30 * time.Second):
		_ = child.Process.Kill()
		t.Fatal("Ctrl-C did not stop the command")
	}
	var exit *exec.ExitError
	if !errors.As(err, &exit) || exit.ExitCode() != 130 {
		t.Errorf("want exit 130 after Ctrl-C, got %v", err)
	}
	if _, err := os.Stat(folder); !os.IsNotExist(err) {
		t.Error("the folder with the new passphrase stays after Ctrl-C")
	}
}

func mustSettings(t *testing.T, e *environment) systemSettings {
	t.Helper()
	settings, err := readSystemSettings(e.readRepositoryFile)
	if err != nil {
		t.Fatal(err)
	}
	return settings
}
