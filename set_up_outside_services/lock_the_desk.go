package main

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// lock-the-desk is the setup's last command, in the person's own window,
// because only the person may see what it shows: the servers' shared root
// console password, the recovery passphrase, and the phone code. Then it
// completes the recovery bundle, refusing with the missing items' names,
// commits and pushes it, copies it into the locked backup bucket with the
// write key the backblaze command kept, and deletes that key's file. The
// person runs it with ssh desk01-lock. A rerun skips the steps that are
// done. docs/design.md, "Account and secret setup from the systems desk",
// records the design.

// The lock stage of playbooks/systems_desk.yml writes deskLockedFile and
// deletes deskRootLoginBeforeTheLockFile, which admits root from a laptop
// with the laptop key alone.
const (
	deskLockedFile                 = "/etc/systems-desk/locked"
	deskRootLoginBeforeTheLockFile = "/etc/ssh/sshd_config.d/00-systems-desk-root-login-before-the-lock.conf"
)

// deskIsLockedAt says the lock stage ran: its record exists and root's
// login from a laptop is closed.
func deskIsLockedAt(lockedFile, rootLoginBeforeTheLockFile string) bool {
	_, record := os.Stat(lockedFile)
	_, rootLogin := os.Stat(rootLoginBeforeTheLockFile)
	return record == nil && errors.Is(rootLogin, os.ErrNotExist)
}

// lockDoneMessage is lock-the-desk's last screen. It says the desk is locked
// only when it is. Reason: at the first setup the coding agent runs the
// lock stage afterwards, and until then the laptop key alone is root on
// the desk.
func lockDoneMessage(e *environment) string {
	if e.deskIsLocked() {
		return "\nDone.  Your systems desk is locked.\n\nGo back to your coding agent."
	}
	return "\nDone.  Your phone code is ready.  Your coding agent locks your systems desk next, then builds your servers.\n\nGo back to your coding agent."
}

// setUpThePhoneCodeWithSudo runs the desk's own phone-code setup in the
// person's terminal: it shows the QR code, asks for one code, and writes the
// emergency codes to emergencyCodesPath.
func setUpThePhoneCodeWithSudo(emergencyCodesPath string) error {
	command := exec.Command("sudo", "-n", "/usr/local/bin/set-up-the-phone-code", "--emergency-codes-to", emergencyCodesPath)
	command.Stdin, command.Stdout, command.Stderr = os.Stdin, os.Stdout, os.Stderr
	if err := command.Run(); err != nil {
		return fmt.Errorf("set-up-the-phone-code stopped (%v), so the systems desk is not locked yet", err)
	}
	return nil
}

// passwordManager names the team's password manager on the screens.
func passwordManager(settings systemSettings) string {
	if name := settings.Vars.PasswordManager; name != "" {
		return name
	}
	return "your password manager"
}

// companyName is the project's name as a person says it: Example for
// example_systems.
func companyName(settings systemSettings) string {
	return capitalize(strings.ReplaceAll(strings.TrimSuffix(settings.ProjectName, "_systems"), "_", " "))
}

// lockStep is one step of lock-the-desk, by its name in the results file.
type lockStep struct {
	name string
	run  func() error
}

func runLockTheDesk(e *environment) error {
	e.named("lock-the-desk")
	if e.readResults().Finished {
		e.show("Your systems desk's lock is done already.\n\nGo back to your coding agent.")
		return nil
	}
	err := e.asStep("", func(map[string]string) (string, error) {
		settings, err := readSystemSettings(e.readRepositoryFile)
		if err != nil {
			return "", err
		}
		providerCredential, err := e.readProviderCredential(settings)
		if err != nil {
			return "", err
		}
		saved, err := e.beginVaultChange()
		if err != nil {
			return "", err
		}
		bundle, passphrase, err := e.openTheBundle(settings)
		if err != nil {
			return "", err
		}
		if bundle == nil {
			return "", fmt.Errorf("%s exists, but its passphrase file %s is gone. Delete %s from the systems repository and run the account commands again: they make a new bundle", recoveryBundleFile, e.recoveryPassphraseFile(settings), recoveryBundleFile)
		}
		// Before the first screen, so the person never does the lock's steps
		// for a run that then stops on a missing account.
		if _, missing := e.bundleItemsFromTheAccounts(settings, bundle); len(missing) > 0 {
			return "", refuseMissingItems(missing)
		}
		if _, err := e.readRootFile(e.backupWriteKeyFile); err != nil {
			return "", fmt.Errorf("the backup write key that set-up-outside-services backblaze keeps for the recovery bundle's upload is missing (%v). Run set-up-outside-services backblaze --replace-key %s, which makes a new one and keeps it, then run lock-the-desk again", err, backupWriteKeyIDVaultName)
		}
		steps := []lockStep{
			{"shared_root_console_password", func() error { return e.consolePasswordScreen(settings, saved, bundle) }},
			{"recovery_passphrase", func() error { return e.recoveryPassphraseScreen(settings, passphrase) }},
			{"phone_code", func() error { return e.phoneCodeScreen(bundle) }},
			{"recovery_bundle", func() error {
				if err := e.completeTheBundle(settings, bundle, providerCredential); err != nil {
					return err
				}
				// Pushed before the upload, so a rerun after a failed upload
				// still has the kept key and uploads the same bundle.
				if err := e.finishVaultChange(saved, e.commandLine); err != nil {
					return err
				}
				if err := e.uploadTheBundle(settings); err != nil {
					return err
				}
				if err := os.Remove(e.recoveryPassphraseFile(settings)); err != nil && !errors.Is(err, os.ErrNotExist) {
					return err
				}
				return nil
			}},
		}
		for _, step := range steps {
			if e.readResults().state(step.name) == stepDone {
				continue
			}
			if err := e.updateResults(func(r *setupResults) { r.setState(step.name, stepInProgress) }); err != nil {
				return "", err
			}
			if err := step.run(); err != nil {
				return "", err
			}
			if err := e.updateResults(func(r *setupResults) { r.setState(step.name, stepDone) }); err != nil {
				return "", err
			}
		}
		return "", e.updateResults(func(r *setupResults) { r.Finished = true })
	})
	if err != nil {
		return fmt.Errorf("%v.\n\nGo back to your coding agent. It sees where this stopped", trimPeriod(err.Error()))
	}
	e.show(lockDoneMessage(e))
	return nil
}

// consolePasswordScreen makes the servers' shared root console password,
// shows it once, and saves its hash in the vault and the password itself in
// the recovery bundle.
func (e *environment) consolePasswordScreen(settings systemSettings, saved, bundle *savedKeys) error {
	e.show(`
Your keys locked away: step 1 of 3, your servers' console password

What this is for:
  Your server provider's web console lets root log in with it, the way in when everything else fails.
`)
	for _, item := range secretsPlan(settings) {
		if item.Kind == consolePasswordSecret {
			return e.saveConsolePassword(saved, item, bundle)
		}
	}
	return errors.New("the secrets plan has no console password")
}

func (e *environment) recoveryPassphraseScreen(settings systemSettings, passphrase string) error {
	words := strings.Fields(passphrase)
	e.setValueOnScreen(true)
	e.show(fmt.Sprintf(`
Your keys locked away: step 2 of 3, your recovery passphrase

What this is for:
  If you lose your systems desk, this one passphrase brings everything back.

  SAVE IT NOW.  IT IS SHOWN ONLY ONCE.

    %s

Do this now:
  1. Save it in %s as  "%s recovery passphrase".
  2. Type it here to prove you saved it.

`, strings.Join(words, "  "), passwordManager(settings), companyName(settings)))
	for {
		typed, err := e.prompt("  Recovery passphrase: ")
		if errors.Is(err, errEmptyValue) {
			continue
		}
		if err != nil {
			e.clearValueFromScreen()
			return err
		}
		if strings.Join(strings.Fields(strings.ToLower(typed)), " ") == passphrase {
			break
		}
		e.say("")
		e.say("That is not the passphrase above.  Check the copy in %s, then type it again.", passwordManager(settings))
		e.say("The lock is still running.  It waits for you at the line below.")
		e.say("")
	}
	e.clearValueFromScreen()
	return nil
}

func (e *environment) phoneCodeScreen(bundle *savedKeys) error {
	e.show(`
Your keys locked away: step 3 of 3, your phone code

What this is for:
  From now on, your systems desk needs your laptop AND a code from your phone.

Do this now:
  1. Open the authenticator app on your phone.
  2. Scan this code.
`)
	// A private folder of the person's own, so the root step's file is never
	// readable by another account.
	folder, err := os.MkdirTemp(e.home, ".phone-code-emergency-codes-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(folder)
	path := filepath.Join(folder, "emergency_codes")
	if err := e.setUpThePhoneCode(path); err != nil {
		return err
	}
	codes, err := e.readRootFile(path)
	if err != nil || strings.TrimSpace(string(codes)) == "" {
		return fmt.Errorf("set-up-the-phone-code wrote no emergency codes to %s", path)
	}
	return bundle.save(bundlePhoneCodeEmergencyCode, strings.TrimSpace(string(codes)))
}
