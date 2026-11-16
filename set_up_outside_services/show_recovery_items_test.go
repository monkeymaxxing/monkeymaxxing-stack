package main

import (
	"errors"
	"path/filepath"
	"strings"
	"testing"
)

// recoveryRun runs show-recovery-items with stand-ins for the terminal. It
// returns what happened, in order: "show", "clear", and each question.
func recoveryRun(t *testing.T, failShow bool, failAnswerAt string) ([]string, string, error) {
	t.Helper()
	h := newHarness(t, false, false)
	for _, name := range []string{".google_authenticator", ".ssh/production_key", ".config/monkeymaxxing-stack/acme_systems_mmx_vault_passphrase"} {
		writeFile(t, filepath.Join(h.e.home, name), "MARKER\n")
	}
	var events []string
	h.e.showFile = func(path string, asRoot bool) error {
		events = append(events, "show")
		if failShow {
			return errors.New("sudo cat failed")
		}
		return nil
	}
	h.e.clearScreen = func() { events = append(events, "clear") }
	h.e.confirm = func(label string) (string, error) {
		events = append(events, label)
		if failAnswerAt != "" && strings.Contains(label, failAnswerAt) {
			return "", errors.New("end of input")
		}
		return "", nil
	}
	err := runRecoveryItems(h.e)
	return events, h.out.String(), err
}

// Every shown value is cleared before the next question that is not about
// the value itself, and before the command ends, on every way out.
func requireEachShownValueCleared(t *testing.T, events []string) {
	t.Helper()
	shown := false
	for _, event := range events {
		switch {
		case event == "show":
			shown = true
		case event == "clear":
			shown = false
		case shown && !strings.Contains(event, "Saved it"):
			t.Fatalf("a value stayed on the screen until %q: %v", event, events)
		}
	}
	if shown {
		t.Fatalf("the command ended with a value on the screen: %v", events)
	}
}

func TestRecoveryItemsClearEachValueAndPointToTheLaptopsScrollback(t *testing.T) {
	events, output, err := recoveryRun(t, false, "")
	if err != nil {
		t.Fatal(err)
	}
	if strings.Count(strings.Join(events, "|"), "show") < 3 {
		t.Fatalf("want the three home-directory items shown, got %v", events)
	}
	requireEachShownValueCleared(t, events)
	if !strings.Contains(output, "terminal window, or Rex for Mac, may keep what this screen showed") {
		t.Fatal("the person must be told to check the laptop's scrollback")
	}
}

func TestRecoveryItemsClearAValueWhenTheyStopEarly(t *testing.T) {
	for _, failShow := range []bool{true, false} {
		events, _, err := recoveryRun(t, failShow, map[bool]string{false: "Saved it"}[failShow])
		if err == nil {
			t.Fatal("want the error")
		}
		requireEachShownValueCleared(t, events)
	}
}

func TestRecoveryItemsNeedTheTerminal(t *testing.T) {
	if stdinIsTerminal() {
		t.Skip("standard input is a terminal here")
	}
	e := &environment{}
	if err := e.dispatch([]string{"show-recovery-items"}); !errors.Is(err, errNoTerminal) {
		t.Fatalf("want errNoTerminal, got %v", err)
	}
}

// The console password's reminder says "not made yet" until the secrets
// step saved the password's hash, and asks once the hash is in the vault.
func TestTheConsolePasswordReminderWaitsForItsHash(t *testing.T) {
	for _, saved := range []bool{false, true} {
		h := newHarness(t, false, false)
		if saved {
			h.vault.values["shared_root_console_password_hash"] = "$6$salt$hash"
		}
		h.e.showFile = func(string, bool) error { return nil }
		h.e.clearScreen = func() {}
		h.e.confirm = func(string) (string, error) { return "", nil }
		if err := runRecoveryItems(h.e); err != nil {
			t.Fatal(err)
		}
		output := h.out.String()
		item := output[strings.Index(output, consolePasswordItem):]
		item = item[:strings.Index(item, "Item ")]
		if strings.Contains(item, "Not made yet") == saved {
			t.Fatalf("with the hash saved %v, the console password item said:\n%s", saved, item)
		}
	}
}
