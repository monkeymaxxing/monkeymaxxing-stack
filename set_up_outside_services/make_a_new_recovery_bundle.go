package main

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// make-a-new-recovery-bundle makes a new recovery bundle, with a new
// recovery passphrase, on a desk whose lock is done: the route when the
// recovery passphrase is lost while the desk still works. The old bundle
// cannot be opened without the old passphrase, so this command builds a new
// one from where each item lives on the desk. It makes new values for the
// two items the desk cannot read back: a new console password, whose hash
// alone is in the vault, and new emergency codes, which the desk's phone
// code keeps but never shows. The phone's own secret stays, so the person
// scans nothing. Then it copies the new bundle into the locked backup
// bucket, and commits and pushes it in place of the old one.
//
// Only the person runs it, in their own terminal on the desk, because the
// screens show the new console password and recovery passphrase. It reads
// the vault as root through MMX, as every account command writes it: each
// value goes from the vault, or a root-only file, straight into the new
// bundle, and never to the screen. docs/design.md, "Account and secret
// setup from the systems desk", records the design.

const makeANewRecoveryBundleCommand = "make-a-new-recovery-bundle"

// makeNewEmergencyCodesWithSudo makes new emergency codes for the desk's
// phone code, keeping its secret, and writes them to emergencyCodesPath.
func makeNewEmergencyCodesWithSudo(emergencyCodesPath string) error {
	command := exec.Command("sudo", "-n", "/usr/local/bin/set-up-the-phone-code", "--new-emergency-codes-to", emergencyCodesPath)
	command.Stdin, command.Stdout, command.Stderr = os.Stdin, os.Stdout, os.Stderr
	if err := command.Run(); err != nil {
		return fmt.Errorf("set-up-the-phone-code --new-emergency-codes-to stopped (%v)", err)
	}
	return nil
}

// newBundleDirectory holds the new bundle and its passphrase while this
// command builds it, readable only by the person. A rerun starts it again,
// so a bundle that was not finished never reaches the systems repository.
func (e *environment) newBundleDirectory(settings systemSettings) string {
	return filepath.Join(e.home, ".config", "monkeymaxxing-stack", settings.ProjectName+"_new_recovery_bundle_until_it_is_pushed")
}

func runMakeANewRecoveryBundle(e *environment) error {
	e.named(makeANewRecoveryBundleCommand)
	if !e.readResults().Finished {
		return errors.New("this systems desk's lock is not done yet, and the lock makes the recovery bundle. Run set-up-outside-services lock-the-desk (ssh desk01-lock) instead")
	}
	err := e.asStep("new_recovery_bundle", func(map[string]string) (string, error) {
		settings, err := readSystemSettings(e.readRepositoryFile)
		if err != nil {
			return "", err
		}
		return stepDone, e.makeANewRecoveryBundle(settings)
	})
	if err != nil {
		return fmt.Errorf("%v.\n\nGo back to your coding agent. It sees where this stopped", trimPeriod(err.Error()))
	}
	e.show("\nDone.  Your new recovery passphrase opens your new recovery bundle.\n\nGo back to your coding agent.")
	return nil
}

func (e *environment) makeANewRecoveryBundle(settings systemSettings) error {
	providerCredential, err := e.readProviderCredential(settings)
	if err != nil {
		return err
	}
	saved, err := e.beginVaultChange()
	if err != nil {
		return err
	}
	// Before any screen: every value the bundle copies is where it should
	// be, and the upload's key works.
	var missing []string
	for key := range copiedIntoTheBundle {
		if !saved.names[key] {
			missing = append(missing, key)
		}
	}
	if len(missing) > 0 {
		return refuseMissingItems(missing, saved)
	}
	upload, err := e.backupBucketWithTheVaultsWriteKey(settings, saved)
	if err != nil {
		return err
	}

	directory := e.newBundleDirectory(settings)
	if err := os.RemoveAll(directory); err != nil {
		return err
	}
	if err := os.MkdirAll(directory, 0o700); err != nil {
		return err
	}
	defer os.RemoveAll(directory)
	passphrase, err := newRecoveryPassphrase()
	if err != nil {
		return err
	}
	passphraseFile := filepath.Join(directory, "recovery_passphrase")
	if err := os.WriteFile(passphraseFile, []byte(passphrase+"\n"), 0o600); err != nil {
		return err
	}
	// MMX runs as the person here: the new bundle is the person's file
	// until it is complete.
	bundleFile := filepath.Join(directory, recoveryBundleFile)
	bundle := &savedKeys{store: mmxVault{directory: directory, file: bundleFile, passwordFile: passphraseFile}, names: map[string]bool{}}
	for _, key := range sortedNames(copiedIntoTheBundle) {
		value, err := saved.store.value(key)
		if err != nil {
			return err
		}
		if err := bundle.save(key, value); err != nil {
			return err
		}
	}
	if _, missing := e.bundleItemsFromTheAccounts(settings, bundle); len(missing) > 0 {
		return refuseMissingItems(missing, saved)
	}

	if err := e.consolePasswordScreen(settings, saved, bundle, "Your new recovery bundle: step 1 of 2, a new console password for your servers"); err != nil {
		return err
	}
	if err := e.newEmergencyCodes(settings, bundle); err != nil {
		return err
	}
	if err := e.completeTheBundle(settings, bundle, providerCredential); err != nil {
		return err
	}
	if err := e.recoveryPassphraseScreen(settings, passphrase, "Your new recovery bundle: step 2 of 2, your new recovery passphrase",
		"Save it in place of the old one in"); err != nil {
		return err
	}

	content, err := os.ReadFile(bundleFile)
	if err != nil {
		return err
	}
	// The locked copy first, so a pushed bundle always has its copy at
	// Backblaze; a stop before the push leaves the old bundle in place.
	if err := upload(content); err != nil {
		return err
	}
	e.say("The older copies there stay until their lock ends; only the old passphrase opens them.")
	if err := e.writeRepositoryFile(recoveryBundleFile, content); err != nil {
		return err
	}
	if err := e.finishVaultChange(saved, e.commandLine); err != nil {
		return fmt.Errorf("%v. The new bundle is in the systems desk's checkout and in the backup bucket, and your new passphrase opens it: do not run %s again, which would make another passphrase. Your coding agent commits and pushes recovery_bundle.age and secrets_vault.age", err, makeANewRecoveryBundleCommand)
	}
	return nil
}

// newEmergencyCodes makes new emergency codes for the desk's phone code and
// saves them in the bundle. The phone keeps its secret, so it keeps working
// with no new scan; the old emergency codes stop working.
func (e *environment) newEmergencyCodes(settings systemSettings, bundle *savedKeys) error {
	path := filepath.Join(e.newBundleDirectory(settings), "phone_code_emergency_codes")
	if err := e.makeNewEmergencyCodes(path); err != nil {
		return err
	}
	codes, err := os.ReadFile(path)
	if err != nil || strings.TrimSpace(string(codes)) == "" {
		return fmt.Errorf("set-up-the-phone-code wrote no emergency codes to %s", path)
	}
	if err := bundle.save(bundlePhoneCodeEmergencyCode, strings.TrimSpace(string(codes))); err != nil {
		return err
	}
	e.say("Saved the new emergency codes only in the new recovery bundle. The old emergency codes no longer work.")
	return os.Remove(path)
}

// backupBucketWithTheVaultsWriteKey signs in to Backblaze with the database
// servers' write key on the production backup bucket, the key lock-the-desk
// uploaded the first copy with, and returns the upload of a new copy.
// Reason for this key, not the master key: the vault holds it, so the
// person gives no key, and it can only add files, which the bucket's lock
// keeps.
func (e *environment) backupBucketWithTheVaultsWriteKey(settings systemSettings, saved *savedKeys) (func(content []byte) error, error) {
	keyID, err := saved.store.value(backupWriteKeyIDVaultName)
	if err != nil {
		return nil, err
	}
	applicationKey, err := saved.store.value(backupWriteApplicationKeyVaultName)
	if err != nil {
		return nil, err
	}
	upload, err := e.backupBucketUpload(settings, keyID, applicationKey)
	if err != nil {
		return nil, fmt.Errorf("signing in to Backblaze with the vault's backup write key %s failed (%v). When the key no longer works, run set-up-outside-services backblaze --replace-key %s, then run this command again", backupWriteKeyIDVaultName, err, backupWriteKeyIDVaultName)
	}
	return upload, nil
}
