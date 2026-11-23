package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

// The person's token file, ~/.config/monkeymaxxing-stack/PROJECT.env: shell
// lines such as  export CLOUDFLARE_API_TOKEN='...'   # a comment
// Only the person's own account reads it.

func (e *environment) tokenFilePath(settings systemSettings) string {
	return filepath.Join(e.home, ".config", "monkeymaxxing-stack", settings.ProjectName+".env")
}

// safeTokenValue is the set of characters this command writes into the
// token file's single quotes and the proxy's token files' double quotes
// without escaping.
// The providers' tokens and keys use only these characters.
var safeTokenValue = regexp.MustCompile(`^[A-Za-z0-9._~+/=:-]+$`)

func checkTokenValue(what, value string) error {
	if !safeTokenValue.MatchString(value) {
		return fmt.Errorf("the %s has a character this command does not write into files, such as a space or a quote. Check that you pasted the whole value and nothing else", what)
	}
	return nil
}

// updateTokenFile sets each variable's value in the token file, keeping
// every other line, and each changed line's comment. A variable the file
// lacks gets a new line at the end. The file is replaced in one step, with
// mode 0600.
func updateTokenFile(path string, values map[string]string) error {
	text, err := os.ReadFile(path)
	if err != nil && !errors.Is(err, os.ErrNotExist) {
		return err
	}
	lines := strings.Split(strings.TrimRight(string(text), "\n"), "\n")
	if len(text) == 0 {
		lines = nil
	}
	names := make([]string, 0, len(values))
	for name := range values {
		if err := checkTokenValue(name, values[name]); err != nil {
			return err
		}
		names = append(names, name)
	}
	sort.Strings(names)
	for _, name := range names {
		line := regexp.MustCompile(`^export ` + regexp.QuoteMeta(name) + `=('[^']*'|"[^"]*"|[^\s#]*)(.*)$`)
		replaced := false
		for i, existing := range lines {
			if match := line.FindStringSubmatch(existing); match != nil && !replaced {
				lines[i] = "export " + name + "='" + values[name] + "'" + match[2]
				replaced = true
			}
		}
		if !replaced {
			lines = append(lines, "export "+name+"='"+values[name]+"'")
		}
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return err
	}
	temporary, err := os.CreateTemp(filepath.Dir(path), ".token-file-*")
	if err != nil {
		return err
	}
	defer os.Remove(temporary.Name())
	if err := temporary.Chmod(0o600); err != nil {
		temporary.Close()
		return err
	}
	if _, err := temporary.WriteString(strings.Join(lines, "\n") + "\n"); err != nil {
		temporary.Close()
		return err
	}
	if err := temporary.Close(); err != nil {
		return err
	}
	return os.Rename(temporary.Name(), path)
}

// tokenFileValue reads one variable's value, for keeping the old value
// until a new one is checked. Empty when the file or the line is missing.
func tokenFileValue(path, name string) string {
	text, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	line := regexp.MustCompile(`(?m)^export ` + regexp.QuoteMeta(name) + `='([^']*)'`)
	if match := line.FindStringSubmatch(string(text)); match != nil {
		return match[1]
	}
	return ""
}

// updateTokenFile updates the person's token file, which stays the person's
// own when the command runs as root for the coding agent.
func (e *environment) updateTokenFile(path string, values map[string]string) error {
	if err := updateTokenFile(path, values); err != nil {
		return err
	}
	return e.giveToThePerson(path)
}

// fileOwner is the person's account, which owns each file the command
// writes in the person's home while it runs as root.
type fileOwner struct {
	uid, gid int
}

// giveToThePerson gives a file in the person's home, and each folder above
// it up to the home, to the person, when the command runs as root. Lchown
// changes a link itself, never what it points at.
func (e *environment) giveToThePerson(path string) error {
	if e.owner == nil {
		return nil
	}
	for current := path; strings.HasPrefix(current, e.home+string(filepath.Separator)); current = filepath.Dir(current) {
		if err := os.Lchown(current, e.owner.uid, e.owner.gid); err != nil {
			return err
		}
	}
	return nil
}
