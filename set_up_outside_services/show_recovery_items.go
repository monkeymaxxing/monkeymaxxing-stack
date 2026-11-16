package main

import (
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// A recovery item is a value the team's password manager must hold,
// because the system cannot be recovered without it. The person copies
// each one from this terminal, where only the person sees it. The coding
// agent never sees a value: it hears only which items the person saved.
type recoveryItem struct {
	Label string // the password manager entry's name
	Why   string
	// Files to show, in order. AsRoot reads a file that only root reads.
	Files  []string
	AsRoot bool
	// VaultKey names a value inside the vault, which MMX never prints: the
	// person copies it from `mmx secrets edit` and closes without saving.
	VaultKey string
	// Reminder is an item with no value here, such as an account's login.
	Reminder string
	// MadeWhenTheVaultHas is the vault key whose presence says a reminder's
	// item exists, such as the console password's hash.
	MadeWhenTheVaultHas string
	// TokenFile and TokenFileVariables show a few lines of the person's
	// token file, such as staging's Access service token, and no others.
	TokenFile          string
	TokenFileVariables []string
}

func recoveryItemsPlan(settings systemSettings, home, desk string) []recoveryItem {
	items := []recoveryItem{
		{Label: desk + " phone-code secret", Why: "With it you can set up the phone code again on a new phone. It is the first line of this file.",
			Files: []string{filepath.Join(home, ".google_authenticator")}},
		{Label: settings.ProjectName + " vault passphrase", Why: "It opens the vault, which holds every secret the servers use. A new desk needs it.",
			Files: []string{filepath.Join(home, ".config", "monkeymaxxing-stack", settings.ProjectName+"_mmx_vault_passphrase")}},
		{Label: desk + " production SSH key", Why: "It logs in to every server. A rebuilt desk restores it.",
			Files: []string{filepath.Join(home, ".ssh", "production_key")}},
		{Label: desk + " WireGuard private key", Why: "It is this desk's identity on the private network. A rebuilt desk restores it, so no server needs a change.",
			Files: []string{"/etc/wireguard/wg0.private_key"}, AsRoot: true},
		{Label: settings.ProjectName + " production backup passphrase", Why: "pgBackRest encrypts every backup with it. Without it the backups cannot be read.",
			VaultKey: "pgbackrest_repository_cipher_passphrase"},
	}
	if settings.hasStagingServer {
		items = append(items,
			recoveryItem{Label: settings.ProjectName + " staging Access service token", Why: "CI and local app tests open the staging pages with it, and another person's desk needs it. Cloudflare showed its secret only once. Save both lines.",
				TokenFile:          filepath.Join(home, ".config", "monkeymaxxing-stack", settings.ProjectName+".env"),
				TokenFileVariables: []string{stagingAccessClientIDVariable, stagingAccessClientSecretVariable}})
	}
	items = append(items,
		recoveryItem{Label: consolePasswordItem, Why: "It logs in at the provider's console when SSH and WireGuard fail.",
			Reminder:            "set-up-outside-services secrets showed it once, in chapter 4, and checked the copy you saved. Check that the entry is there.",
			MadeWhenTheVaultHas: "shared_root_console_password_hash"},
		recoveryItem{Label: "Account logins and recovery codes", Why: "Losing one of these accounts can lock the team out.",
			Reminder: "Check that the password manager has the login and recovery codes of Cloudflare, the server provider, Backblaze, and the Git host."},
	)
	return items
}

func runRecoveryItems(e *environment) error {
	settings, err := readSystemSettings(e.directory)
	if err != nil {
		return err
	}
	desk, err := os.Hostname()
	if err != nil {
		return err
	}
	keys, vaultErr := e.vault.keys()
	items := recoveryItemsPlan(settings, e.home, desk)
	e.say("Your password manager must hold %d recovery items. This command shows each one here, in your terminal only,", len(items))
	e.say("one at a time, with the name to give its entry. Copy it into a new entry, save the entry, then come back here:")
	e.say("the screen is cleared before the next item. Never paste a value into the chat with your coding agent.")
	e.say("Clearing this screen cannot clear a copy your laptop keeps, so at the end you check your laptop's terminal or Rex.")
	var saved, skipped, notYet []string
	for i, item := range items {
		e.say("")
		e.say("Item %d of %d: %q", i+1, len(items), item.Label)
		e.say("  Why: %s", item.Why)
		if item.Reminder != "" {
			if item.MadeWhenTheVaultHas != "" && !(vaultErr == nil && keys[item.MadeWhenTheVaultHas]) {
				e.say("  Not made yet. Run this command again once it exists.")
				notYet = append(notYet, item.Label)
				continue
			}
			e.say("  %s", item.Reminder)
			answer, err := e.confirm("  Press Enter when it is saved, or type later: ")
			if err != nil {
				return err
			}
			if strings.EqualFold(answer, "later") {
				skipped = append(skipped, item.Label)
			} else {
				saved = append(saved, item.Label)
			}
			continue
		}
		ready := true
		if item.VaultKey != "" {
			ready = vaultErr == nil && keys[item.VaultKey]
		}
		for _, path := range item.Files {
			if _, err := os.Stat(path); err != nil && !(item.AsRoot && errors.Is(err, os.ErrPermission)) {
				ready = false
			}
		}
		for _, variable := range item.TokenFileVariables {
			ready = ready && tokenFileValue(item.TokenFile, variable) != ""
		}
		if !ready || len(item.Files) == 0 && item.VaultKey == "" && len(item.TokenFileVariables) == 0 {
			e.say("  Not made yet. Run this command again once it exists.")
			notYet = append(notYet, item.Label)
			continue
		}
		answer, err := e.confirm("  Press Enter to show it, or type skip if your password manager has it already: ")
		if err != nil {
			return err
		}
		if strings.EqualFold(answer, "skip") {
			skipped = append(skipped, item.Label)
			continue
		}
		// From here a value may be on the screen. Every way out clears it:
		// the answer, an error, and Ctrl-C (handleInterrupts).
		e.setValueOnScreen(true)
		if item.VaultKey != "" {
			e.say("  MMX opens the vault in your editor now. Copy the value of %s, then close the editor without saving.", item.VaultKey)
			if err := runVaultEditor(e.directory); err != nil {
				e.clearValueFromScreen()
				return err
			}
		} else if len(item.TokenFileVariables) > 0 {
			e.say("  ----")
			for _, variable := range item.TokenFileVariables {
				e.say("  %s: %s", variable, tokenFileValue(item.TokenFile, variable))
			}
			e.say("  ----")
		} else {
			for _, path := range item.Files {
				e.say("  ---- %s ----", path)
				if err := e.showFile(path, item.AsRoot); err != nil {
					e.clearValueFromScreen()
					return err
				}
			}
			e.say("  ----")
		}
		answer, err = e.confirm("  Saved it in the password manager? Press Enter to clear the screen, or type later: ")
		e.clearValueFromScreen()
		if err != nil {
			return err
		}
		if strings.EqualFold(answer, "later") {
			skipped = append(skipped, item.Label)
		} else {
			saved = append(saved, item.Label)
		}
	}
	e.say("Recovery items saved now: %s.", listOrNone(saved))
	e.say("Skipped or left for later: %s.", listOrNone(skipped))
	e.say("Not made yet: %s.", listOrNone(notYet))
	e.say("Tell your coding agent these three lines. They hold names only, no values.")
	e.say("")
	e.say("Last, check your laptop. Its terminal window, or Rex for Mac, may keep what this screen showed in its scrollback.")
	e.say("Scroll up in the window you used. If a recovery value is still there, clear that window's scrollback, or close the window.")
	return nil
}

func (e *environment) setValueOnScreen(on bool) {
	e.interruptMutex.Lock()
	e.valueOnScreen = on
	e.interruptMutex.Unlock()
}

// clearValueFromScreen clears the screen and its scrollback once a shown
// recovery value is no longer needed there.
func (e *environment) clearValueFromScreen() {
	e.clearScreen()
	e.setValueOnScreen(false)
}

func listOrNone(items []string) string {
	if len(items) == 0 {
		return "none"
	}
	return strings.Join(items, "; ")
}

// showFileInTerminal writes a file straight to the terminal. A file only
// root reads goes through sudo cat, so the value never passes through this
// program's memory either.
func showFileInTerminal(path string, asRoot bool) error {
	if asRoot {
		command := exec.Command("sudo", "-n", "cat", "--", path)
		command.Stdout, command.Stderr = os.Stdout, os.Stderr
		return command.Run()
	}
	file, err := os.Open(path)
	if err != nil {
		return err
	}
	defer file.Close()
	_, err = io.Copy(os.Stdout, file)
	return err
}

func runVaultEditor(directory string) error {
	command := exec.Command("mmx", "secrets", "edit")
	command.Dir = directory
	command.Stdin, command.Stdout, command.Stderr = os.Stdin, os.Stdout, os.Stderr
	if err := command.Run(); err != nil {
		return fmt.Errorf("mmx secrets edit failed: %v", err)
	}
	return nil
}
