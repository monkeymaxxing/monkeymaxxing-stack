package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const newEmergencyCodes = "61234567\n62345678\n63456789\n64567890\n65678901"

// After a finished lock whose recovery passphrase is lost, the new bundle
// opens with the new passphrase alone and holds every item the lock
// requires, with the desk's current values, a new console password and new
// emergency codes. It is pushed in place of the old bundle and copied into
// the locked backup bucket, and no secret shows on the screen.
func TestANewRecoveryBundleOpensWithTheNewPassphraseAndHoldsEveryItem(t *testing.T) {
	h := newLockHarness(t)
	h.accounts()
	if err := runLockTheDesk(h.e); err != nil {
		t.Fatalf("lock-the-desk: %v\n%s", err, h.out)
	}
	oldPassphrase, oldHash := h.passphrase, h.vault.values[consolePasswordVaultKey]
	h.e.makeNewEmergencyCodes = func(path string) error { return os.WriteFile(path, []byte(newEmergencyCodes+"\n"), 0o600) }
	h.out.Reset()

	if err := runMakeANewRecoveryBundle(h.e); err != nil {
		t.Fatalf("make-a-new-recovery-bundle: %v\n%s", err, h.out)
	}
	output := h.out.String()
	if h.passphrase == oldPassphrase || strings.Count(output, strings.ReplaceAll(h.passphrase, " ", "  ")) != 1 {
		t.Fatal("the new passphrase is the old one, or shows more than once")
	}
	if !strings.Contains(output, "Save it in place of the old one in 1Password") {
		t.Errorf("the passphrase screen does not say to replace the old one:\n%s", output)
	}

	// The new passphrase opens the bundle in the repository, and each item
	// holds the desk's value.
	passwordFile := filepath.Join(t.TempDir(), "passphrase")
	writeFile(t, passwordFile, h.passphrase+"\n")
	if err := os.Chmod(passwordFile, 0o600); err != nil {
		t.Fatal(err)
	}
	bundle := mmxVault{directory: t.TempDir(), file: filepath.Join(h.e.directory, recoveryBundleFile), passwordFile: passwordFile}
	keys, err := bundle.keys()
	if err != nil {
		t.Fatalf("the new passphrase does not open the new bundle: %v", err)
	}
	if len(keys) != 10 {
		t.Errorf("the new bundle holds %d items, want the lock's 10: %v", len(keys), keys)
	}
	consolePassword := ""
	want := map[string]string{
		bundleVaultPassphrase:        vaultPassphrase,
		bundleProductionKey:          "-----BEGIN OPENSSH PRIVATE KEY-----\nproduction\n-----END OPENSSH PRIVATE KEY-----",
		bundleWireGuardKey:           "wireguardprivatekeyvalue=",
		bundleProviderCredential:     providerToken,
		bundleCloudflareDeskToken:    tokenFileValue(h.e.tokenFilePath(mustSettings(t, h.e)), deskTokenVariable),
		bundlePhoneCodeEmergencyCode: newEmergencyCodes,
		bundleConsolePassword:        "",
	}
	for key := range copiedIntoTheBundle {
		want[key] = h.vault.values[key]
	}
	for key, value := range want {
		got, err := bundle.value(key)
		switch {
		case err != nil:
			t.Errorf("the new bundle lacks %s: %v", key, err)
		case key == bundleConsolePassword:
			consolePassword = got
		case got != value || value == "":
			t.Errorf("the new bundle's %s is not the desk's value", key)
		}
	}
	if len(consolePassword) != 23 || h.vault.values[consolePasswordVaultKey] == oldHash {
		t.Errorf("the console password %q is not a new 4-group password, or its hash did not change", consolePassword)
	}

	// Pushed with the vault, and a second locked copy at Backblaze.
	if files := strings.TrimSpace(h.git(h.e.directory, "--git-dir", h.origin, "diff-tree", "--no-commit-id", "--name-only", "-r", "main")); files != recoveryBundleFile+"\n"+vaultFile {
		t.Errorf("the push changes %q, want the bundle and the vault", files)
	}
	copies := 0
	for _, file := range h.b2.Files {
		if strings.HasPrefix(file.Name, "recovery_bundle/") && file.Mode == "compliance" {
			copies++
		}
	}
	if copies != 2 {
		t.Errorf("want the lock's copy and the new one at Backblaze, got %d", copies)
	}
	if _, err := os.Stat(h.e.newBundleDirectory(mustSettings(t, h.e))); !os.IsNotExist(err) {
		t.Error("the new bundle's folder, with its passphrase, stays on the desk")
	}
	h.requireNoSecretInOutput(providerToken, masterKey, vaultPassphrase, "61234567")
}

// Before the lock is done, the lock makes the bundle, so this command
// refuses and names it.
func TestANewRecoveryBundleWaitsForTheLock(t *testing.T) {
	h := newLockHarness(t)
	h.accounts()
	err := runMakeANewRecoveryBundle(h.e)
	if err == nil || !strings.Contains(err.Error(), "lock-the-desk") {
		t.Fatalf("want a refusal naming lock-the-desk, got %v", err)
	}
	if strings.Contains(h.out.String(), "step 1 of 2") {
		t.Fatal("the refusal came after a screen")
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
