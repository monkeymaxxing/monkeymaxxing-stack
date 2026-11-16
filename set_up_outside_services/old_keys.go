package main

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
)

// A replaced key's old key keeps working until the servers run with the new
// one, so a routine replacement never leaves an app without its uploads.
// The command records each old key in the person's old-keys file, waits in
// the person's terminal while the coding agent runs every_server, and
// deletes the old keys when the person presses Enter. After a break-in,
// --delete-the-old-keys-at-once deletes them without waiting.
//
// The file holds key IDs and names only, never a secret: one line per old
// key, PROVIDER<TAB>ID<TAB>NAME. It lets a run that stopped while waiting
// be finished by the next run, which deletes exactly the recorded keys and
// never guesses which key of a name the vault holds.

const deleteTheOldKeysAtOnceFlag = "--delete-the-old-keys-at-once"

type oldKey struct {
	Provider string // "backblaze" or "cloudflare"
	ID       string
	Name     string
}

func (e *environment) oldKeysFilePath(settings systemSettings) string {
	return filepath.Join(e.home, ".config", "monkeymaxxing-stack", settings.ProjectName+"_old_keys_to_delete")
}

func readOldKeys(path string) []oldKey {
	text, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	var keys []oldKey
	for _, line := range strings.Split(string(text), "\n") {
		fields := strings.SplitN(line, "\t", 3)
		if len(fields) == 3 {
			keys = append(keys, oldKey{Provider: fields[0], ID: fields[1], Name: fields[2]})
		}
	}
	return keys
}

func writeOldKeys(path string, keys []oldKey) error {
	if len(keys) == 0 {
		if err := os.Remove(path); err != nil && !errors.Is(err, os.ErrNotExist) {
			return err
		}
		return nil
	}
	var lines []string
	for _, key := range keys {
		lines = append(lines, key.Provider+"\t"+key.ID+"\t"+key.Name)
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return err
	}
	return os.WriteFile(path, []byte(strings.Join(lines, "\n")+"\n"), 0o600)
}

// recordOldKeys adds old keys to the file, before anything deletes them.
func recordOldKeys(path string, keys ...oldKey) error {
	all := readOldKeys(path)
	for _, key := range keys {
		known := false
		for _, have := range all {
			known = known || have == key
		}
		if !known {
			all = append(all, key)
		}
	}
	return writeOldKeys(path, all)
}

// deleteOldKeys deletes the provider's recorded old keys. With wait, it
// first tells the person the run that brings the new keys to the servers
// and waits for Enter; no answer, Ctrl-C included, leaves the old keys
// working and recorded for the next run.
func (e *environment) deleteOldKeys(path, provider string, wait bool, deleteKey func(id string) error, keysPage string) error {
	var mine, others []oldKey
	for _, key := range readOldKeys(path) {
		if key.Provider == provider {
			mine = append(mine, key)
		} else {
			others = append(others, key)
		}
	}
	if len(mine) == 0 {
		return nil
	}
	e.say("")
	e.say("The old keys of the keys this command replaced:")
	for _, key := range mine {
		e.say("  %s (ID %s)", key.Name, key.ID)
	}
	if wait {
		e.say("They keep working until you press Enter here, so the servers keep working until they have the new keys.")
		e.say("Tell your coding agent to run now, from its checkout:")
		e.say("  ./server_management_scripts/run_mmx_on_util01 run every_server")
		e.say("During a lock-out, it runs instead: sudo -n -u servers-mmx run-mmx-on-the-servers run every_server --connection ssh_only")
		e.say("Once the run passed and each new key's check in rotate_a_secret.md passed, press Enter to delete the old keys.")
		e.say("Ctrl-C leaves the old keys working; the next run of this command asks again before it deletes them.")
		if _, err := e.confirm("Press Enter to delete the old keys: "); err != nil {
			e.say("")
			e.say("The old keys keep working. The next run of this command asks again before it deletes them.")
			return nil
		}
	}
	var left []oldKey
	for _, key := range mine {
		if err := deleteKey(key.ID); err != nil && !refusedWith(err, 404) {
			e.say("  Deleting %s (ID %s) failed (%v). The next run tries again, or delete it by hand: %s", key.Name, key.ID, err, keysPage)
			left = append(left, key)
			continue
		}
		e.say("  Deleted the old key %s (ID %s).", key.Name, key.ID)
	}
	return writeOldKeys(path, append(others, left...))
}
