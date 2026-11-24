package main

import (
	"crypto/rand"
	"encoding/json"
	"errors"
	"fmt"
	"math/big"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
)

// make-a-new-recovery-bundle makes a new recovery bundle, with a new
// recovery passphrase, on a locked desk: the route when the recovery
// passphrase is lost while the desk still works. The old bundle cannot be
// opened without the old passphrase, so this command builds a new one from
// where each item lives on the desk. Two items the desk cannot read back
// come another way: the person types the servers' current console password
// from the password manager, checked against its hash in the vault, and the
// command makes new emergency codes, which the desk's phone code keeps but
// never shows. The phone's own secret stays, so the person scans nothing.
// The console password and the vault stay as they are, so the servers need
// no run.
//
// It changes nothing live until the bundle is safe: it checks every input,
// runs both screens and builds the bundle in a private folder, and copies
// it into the locked backup bucket. Only then does it give the phone code
// the new emergency codes, replace recovery_bundle.age, and commit and
// push. A stop before the person typed the passphrase back leaves the desk
// as it was, and a rerun starts again; a stop after it leaves the folder,
// and a rerun finishes that bundle with that passphrase.
//
// Only the person runs it, in their own terminal on the desk, because the
// person types the console password and the screen shows the new recovery
// passphrase. It reads the vault as root through MMX, as every account
// command writes it: each value goes from the vault, or a root-only file,
// straight into the new bundle or the password's check, and never to the
// screen. docs/design.md, "Account and secret
// setup from the systems desk", records the design.

const makeANewRecoveryBundleCommand = "make-a-new-recovery-bundle"

// deskPhoneCodeFile is the desk's phone code: the phone's secret, its
// options, and the emergency codes, root:root 0400.
const deskPhoneCodeFile = "/etc/systems-desk/phone-code"

// replaceEmergencyCodesWithSudo gives the desk's phone code the new
// emergency codes, one per line, on standard input; the phone's secret and
// options stay.
func replaceEmergencyCodesWithSudo(codes string) error {
	command := exec.Command("sudo", "-n", "/usr/local/bin/set-up-the-phone-code", "--replace-emergency-codes")
	command.Stdin = strings.NewReader(codes + "\n")
	command.Stdout, command.Stderr = os.Stdout, os.Stderr
	if err := command.Run(); err != nil {
		return fmt.Errorf("set-up-the-phone-code --replace-emergency-codes stopped (%v)", err)
	}
	return nil
}

// emergencyCodeCount is how many one-time emergency codes the phone code
// has, as set-up-the-phone-code makes them at the lock.
const emergencyCodeCount = 5

// newEmergencyCodes makes emergency codes as google-authenticator makes
// them, 8 digits that do not start with 0, one per line.
func newEmergencyCodes() (string, error) {
	codes := make([]string, emergencyCodeCount)
	for i := range codes {
		n, err := rand.Int(rand.Reader, big.NewInt(90000000))
		if err != nil {
			return "", err
		}
		codes[i] = fmt.Sprint(10000000 + n.Int64())
	}
	return strings.Join(codes, "\n"), nil
}

// newBundleDirectory holds the new bundle and its passphrase while this
// command builds and publishes it, readable only by the person. Its files
// say how far a run got:
//   - recovery_bundle.age and recovery_passphrase, while the run builds;
//   - copyRecordFile, once the person typed the passphrase back, written
//     before the upload;
//   - uploadedMark, once the backup bucket holds the copy;
//   - installedCodesFile, once the phone code has the bundle's emergency
//     codes.
//
// Until copyRecordFile, any stop removes the folder, so a passphrase the
// person never saved goes. From copyRecordFile on, the folder stays until
// the push succeeds, so a rerun publishes the bundle whose passphrase the
// person saved.
func (e *environment) newBundleDirectory(settings systemSettings) string {
	return filepath.Join(e.home, ".config", "monkeymaxxing-stack", settings.ProjectName+"_new_recovery_bundle_until_it_is_pushed")
}

const (
	// copyRecordFile names the bundle's copy in the backup bucket and
	// holds the bundle's SHA-256, written before the upload, so a rerun
	// finds a copy whose answer never arrived.
	copyRecordFile = "backup_bucket_copy.json"
	// uploadedMark says the backup bucket holds the copy.
	uploadedMark = "uploaded_to_the_backup_bucket"
	// installedCodesFile holds the SHA-256 of the emergency codes the phone
	// code got, so a rerun never gives them again: a code the person used
	// meanwhile stays used.
	installedCodesFile = "phone_code_has_these_emergency_codes"
)

// bundleCopy is copyRecordFile's content: the copy's file name in the
// backup bucket and the bundle's SHA-256.
type bundleCopy struct {
	FileName string `json:"backup_bucket_file_name"`
	SHA256   string `json:"bundle_sha256"`
}

// oneRunAtATime locks a file in the person's private folder while the
// command runs, so a second terminal is refused. Reason: two runs share the
// new bundle's folder, and one could upload the other's bundle under its
// own passphrase. The lock ends with the process, also on Ctrl-C.
func (e *environment) oneRunAtATime() (release func(), err error) {
	directory := filepath.Join(e.home, ".config", "monkeymaxxing-stack")
	if err := os.MkdirAll(directory, 0o700); err != nil {
		return nil, err
	}
	file, err := os.OpenFile(filepath.Join(directory, "make_a_new_recovery_bundle.lock"), os.O_RDWR|os.O_CREATE, 0o600)
	if err != nil {
		return nil, err
	}
	if err := syscall.Flock(int(file.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); err != nil {
		file.Close()
		if errors.Is(err, syscall.EWOULDBLOCK) {
			return nil, fmt.Errorf("%s runs already, in another terminal on this systems desk. Finish or stop that run first; two runs at once could save one run's bundle under the other run's passphrase", makeANewRecoveryBundleCommand)
		}
		return nil, err
	}
	return func() { file.Close() }, nil
}

func runMakeANewRecoveryBundle(e *environment) error {
	e.named(makeANewRecoveryBundleCommand)
	// The lock itself, not lock-the-desk's record: a rebuilt desk or a
	// teammate's desk is locked by the lock stage alone.
	if !e.deskIsLocked() {
		return errors.New("this systems desk is not locked yet, and a systems desk's first recovery bundle comes from its lock. At the setup, run set-up-outside-services lock-the-desk (ssh desk01-lock), then your coding agent locks the systems desk; on a rebuilt systems desk, your coding agent runs the lock stage first")
	}
	release, err := e.oneRunAtATime()
	if err != nil {
		return err
	}
	defer release()
	err = e.asStep("new_recovery_bundle", func(notes map[string]string) (string, error) {
		if err := e.makeANewRecoveryBundle(); err != nil {
			return "", err
		}
		notes[recoveryBundleDeskNote] = e.deskName
		return stepDone, nil
	})
	if err != nil {
		return fmt.Errorf("%v.\n\nGo back to your coding agent. It sees where this stopped", trimPeriod(err.Error()))
	}
	e.show("\nDone.  Your new recovery passphrase opens your new recovery bundle.\n\nGo back to your coding agent.")
	return nil
}

func (e *environment) makeANewRecoveryBundle() error {
	// A bundle whose passphrase the person saved is finished before the
	// pull: its commit may wait for its push, which the pull's check
	// would refuse.
	settings, err := readSystemSettings(e.readRepositoryFile)
	if err != nil {
		return err
	}
	directory := e.newBundleDirectory(settings)
	if _, err := os.Stat(filepath.Join(directory, copyRecordFile)); err == nil {
		e.say("An earlier run made a new recovery bundle and stopped before publishing it. Finishing that bundle: the recovery passphrase that run showed opens it.")
		return e.publishTheNewBundle(settings, directory, nil)
	}

	// The pull first, so the settings and the inventory are the team's: a
	// staging01 a teammate added is in the bundle and in its check.
	saved, err := e.beginVaultChange()
	if err != nil {
		return err
	}
	if settings, err = readSystemSettings(e.readRepositoryFile); err != nil {
		return err
	}
	directory = e.newBundleDirectory(settings)

	// Every input, before any screen or change: the desk's files, the
	// vault's keys, the phone code, and the upload's key.
	providerCredential, err := e.readProviderCredential(settings)
	if err != nil {
		return err
	}
	var missing []string
	for key := range copiedIntoTheBundle {
		if !saved.names[key] {
			missing = append(missing, key)
		}
	}
	if len(missing) > 0 {
		return refuseMissingItems(missing, saved, makeANewRecoveryBundleCommand)
	}
	if phoneCode, err := e.readRootFile(deskPhoneCodeFile); err != nil || strings.TrimSpace(strings.SplitN(string(phoneCode), "\n", 2)[0]) == "" {
		return fmt.Errorf("this systems desk has no phone code in %s, so it cannot get new emergency codes. Ask your coding agent", deskPhoneCodeFile)
	}
	bucket, err := e.backupBucketWithTheVaultsWriteKey(settings)
	if err != nil {
		return err
	}
	consolePasswordHash, err := saved.store.value(consolePasswordVaultKey)
	if err != nil {
		return err
	}

	if err := os.RemoveAll(directory); err != nil {
		return err
	}
	if err := os.MkdirAll(directory, 0o700); err != nil {
		return err
	}
	// Until the person saved the passphrase, any stop removes the folder
	// with it, Ctrl-C and a lost connection too.
	e.removeOnStop(directory)
	kept := false
	defer func() {
		if !kept {
			e.removeOnStop("")
			os.RemoveAll(directory)
		}
	}()
	passphrase, err := newRecoveryPassphrase()
	if err != nil {
		return err
	}
	bundle := newBundleIn(directory)
	if err := os.WriteFile(bundle.passwordFile, []byte(passphrase+"\n"), 0o600); err != nil {
		return err
	}
	// MMX runs as the person here: the new bundle is the person's file
	// until it is uploaded.
	building := &savedKeys{store: bundle, names: map[string]bool{}}
	for _, key := range sortedNames(copiedIntoTheBundle) {
		value, err := saved.store.value(key)
		if err != nil {
			return err
		}
		if err := building.save(key, value); err != nil {
			return err
		}
	}
	if err := e.addTheDesksItems(settings, building, providerCredential, makeANewRecoveryBundleCommand); err != nil {
		return err
	}

	// After every check of the desk's items, so a refusal comes before this
	// first screen; a wrong password removes the folder like any stop.
	consolePassword, err := e.typeTheCurrentConsolePassword(settings, consolePasswordHash)
	if err != nil {
		return err
	}
	if err := building.save(bundleConsolePassword, consolePassword); err != nil {
		return err
	}
	codes, err := newEmergencyCodes()
	if err != nil {
		return err
	}
	if err := building.save(bundlePhoneCodeEmergencyCode, codes); err != nil {
		return err
	}
	if err := checkThePersonsItems(building, makeANewRecoveryBundleCommand); err != nil {
		return err
	}
	if err := e.recoveryPassphraseScreen(settings, passphrase, "Your new recovery bundle: step 2 of 2, your new recovery passphrase",
		"Save it in place of the old one in", "Making your new recovery bundle"); err != nil {
		return err
	}

	// The person saved the passphrase, so from the record on the folder
	// stays until the push, and a rerun publishes this bundle.
	content, err := os.ReadFile(bundle.file)
	if err != nil {
		return err
	}
	record, err := json.Marshal(bundleCopy{FileName: e.newBundleCopyName(), SHA256: sha256Hex(content)})
	if err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(directory, copyRecordFile), record, 0o600); err != nil {
		return err
	}
	// A stop from here on keeps the folder. A stop that began before this
	// line holds the stop's lock until its exit, so it removes the folder
	// and nothing is sent.
	e.removeOnStop("")
	kept = true
	return e.publishTheNewBundle(settings, directory, bucket)
}

// typeTheCurrentConsolePassword asks the person for the servers' current
// shared root console password, from the team's password manager, and
// returns it once it matches the vault's hash. Two wrong ones stop the run.
// Reason for two: a typing slip gets a second try, and a person who does
// not have the current password learns at once how to replace it.
func (e *environment) typeTheCurrentConsolePassword(settings systemSettings, hash string) (string, error) {
	e.show(fmt.Sprintf(`
Your new recovery bundle: step 1 of 2, your servers' console password

What this is for:
  The new recovery bundle keeps your servers' console password as it is now. It does not change.

Do this now:
  Type the password from the item  %s  in %s.
`, consolePasswordItem, passwordManager(settings)))
	for tries := 1; ; {
		typed, err := e.prompt("  Console password (hidden): ")
		if errors.Is(err, errEmptyValue) {
			continue
		}
		if err != nil {
			return "", err
		}
		matches, err := consolePasswordMatchesHash(typed, hash)
		if err != nil {
			return "", err
		}
		if matches {
			e.say("  It matches your servers' console password.")
			return typed, nil
		}
		if tries == 2 {
			return "", fmt.Errorf("the password typed twice is not your servers' current console password, so nothing changed. When nobody has the current one, replace it first, as operating_procedures/rotate_a_secret.md, section \"The shared root console password\", says, then run %s again", makeANewRecoveryBundleCommand)
		}
		tries++
		e.say("  That is not your servers' current console password. Check the item %q in %s, then type it again.", consolePasswordItem, passwordManager(settings))
	}
}

// newBundleIn is the new bundle's MMX vault in its folder, with its
// passphrase file beside it.
func newBundleIn(directory string) mmxVault {
	return mmxVault{directory: directory, file: filepath.Join(directory, recoveryBundleFile), passwordFile: filepath.Join(directory, "recovery_passphrase")}
}

// publishTheNewBundle publishes the bundle in directory, whose passphrase
// the person saved: it copies the bundle into the locked backup bucket
// unless the bucket holds that copy already, gives the phone code the
// bundle's emergency codes unless it has them already, then replaces
// recovery_bundle.age in the checkout and commits and pushes it. Each part
// may run twice, so a rerun after any stop here finishes the same bundle.
// bucket is nil on a rerun; it signs in when the copy is still to make.
func (e *environment) publishTheNewBundle(settings systemSettings, directory string, bucket *backupBucket) error {
	bundle := newBundleIn(directory)
	content, err := os.ReadFile(bundle.file)
	if err != nil {
		return err
	}
	if err := e.copyTheNewBundle(settings, directory, content, bucket); err != nil {
		return fmt.Errorf("%v. Your new recovery passphrase opens the new bundle, which waits on this systems desk. Fix the cause, then run %s again: it copies this bundle into the backup bucket and makes no new passphrase", trimPeriod(err.Error()), makeANewRecoveryBundleCommand)
	}
	e.say("The older copies there stay until their lock ends; only the old passphrase opens them.")
	commit, where, err := func() (string, string, error) {
		codes, err := bundle.value(bundlePhoneCodeEmergencyCode)
		if err != nil {
			return "", "", err
		}
		if err := e.giveThePhoneCodeTheNewCodes(directory, codes); err != nil {
			return "", "", err
		}
		if err := e.writeRepositoryFile(recoveryBundleFile, content); err != nil {
			return "", "", err
		}
		return e.publishTheRecoveryBundle("Replace the recovery bundle with " + e.commandLine + "\n\n" + e.bundleCoversLine())
	}()
	if err != nil {
		return fmt.Errorf("%v. The new bundle is in the backup bucket, and your new passphrase opens it. Fix the cause, then run %s again: it finishes publishing this bundle and makes no new passphrase", trimPeriod(err.Error()), makeANewRecoveryBundleCommand)
	}
	e.say("Committed the new recovery bundle as commit %s and published it %s. The vault did not change.", commit, where)
	// Published, so the folder and its passphrase go.
	return os.RemoveAll(directory)
}

// copyTheNewBundle makes sure the backup bucket holds the copy that
// copyRecordFile names, with the bundle's SHA-256: it looks first, so a
// copy whose answer never arrived is not made twice. The stop protection
// holds from before the upload until uploadedMark is written.
func (e *environment) copyTheNewBundle(settings systemSettings, directory string, content []byte, bucket *backupBucket) error {
	if _, err := os.Stat(filepath.Join(directory, uploadedMark)); err == nil {
		return nil
	}
	e.enterCriticalSection()
	defer e.leaveCriticalSection()
	text, err := os.ReadFile(filepath.Join(directory, copyRecordFile))
	if err != nil {
		return err
	}
	var record bundleCopy
	if err := json.Unmarshal(text, &record); err != nil || record.FileName == "" {
		return fmt.Errorf("%s does not name the bundle's copy", filepath.Join(directory, copyRecordFile))
	}
	if sha256Hex(content) != record.SHA256 {
		return fmt.Errorf("the new bundle in %s is not the one its record names", directory)
	}
	if bucket == nil {
		if bucket, err = e.backupBucketWithTheVaultsWriteKey(settings); err != nil {
			return err
		}
	}
	held, err := bucket.holds(record.FileName, record.SHA256)
	if err != nil {
		return err
	}
	if held {
		e.say("The locked backup bucket %s holds this bundle already, as %s.", bucket.bucket.BucketName, record.FileName)
	} else if err := bucket.upload(record.FileName, content); err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(directory, uploadedMark), nil, 0o600)
}

// giveThePhoneCodeTheNewCodes gives the phone code the bundle's emergency
// codes, unless installedCodesFile says it has them already. Reason: a rerun
// that gave all five again would revive a code the person used meanwhile.
func (e *environment) giveThePhoneCodeTheNewCodes(directory, codes string) error {
	installed := filepath.Join(directory, installedCodesFile)
	if text, err := os.ReadFile(installed); err == nil && strings.TrimSpace(string(text)) == sha256Hex([]byte(codes)) {
		return nil
	}
	e.enterCriticalSection()
	defer e.leaveCriticalSection()
	if err := e.replaceEmergencyCodes(codes); err != nil {
		return err
	}
	if err := os.WriteFile(installed, []byte(sha256Hex([]byte(codes))+"\n"), 0o600); err != nil {
		return err
	}
	e.say("Saved the new emergency codes only in the new recovery bundle. The old emergency codes no longer work.")
	return nil
}

// backupBucketWithTheVaultsWriteKey signs in to Backblaze with the database
// servers' write key on the production backup bucket, the key lock-the-desk
// uploaded the first copy with.
// Reason for this key, not the master key: the vault holds it, so the
// person gives no key, and it can only add files, which the bucket's lock
// keeps.
func (e *environment) backupBucketWithTheVaultsWriteKey(settings systemSettings) (*backupBucket, error) {
	keyID, err := e.vault.value(backupWriteKeyIDVaultName)
	if err != nil {
		return nil, err
	}
	applicationKey, err := e.vault.value(backupWriteApplicationKeyVaultName)
	if err != nil {
		return nil, err
	}
	bucket, err := e.signInToTheBackupBucket(settings, keyID, applicationKey)
	if err != nil {
		return nil, fmt.Errorf("signing in to Backblaze with the vault's backup write key %s failed (%v). When the key no longer works, run set-up-outside-services backblaze --replace-key %s, then run this command again", backupWriteKeyIDVaultName, err, backupWriteKeyIDVaultName)
	}
	return bucket, nil
}
