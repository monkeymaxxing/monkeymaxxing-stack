package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
)

// vault is the systems repository's MMX vault. This command lists its keys
// and adds values, and never writes the vault's file itself: MMX owns the
// vault's format. Only make-a-new-recovery-bundle reads a value back, to
// copy it into the new bundle or to upload with it, never to the screen.
type vault interface {
	keys() (map[string]bool, error)
	set(key, value string, replace bool) error
	// value reads one saved value, through MMX.
	value(key string) (string, error)
	// addRandom makes a random value of length characters inside MMX.
	addRandom(key string, length int, replace bool) error
	// missing lists the keys the playbooks read that the vault lacks.
	missing() ([]string, error)
}

// mmxVault runs the pinned `mmx secrets` commands in the systems
// repository. Each value goes to MMX on standard input, never in arguments,
// so no value shows in the desk's process list.
type mmxVault struct {
	directory string
	// file and passwordFile name another vault file than the project's,
	// such as the recovery bundle, and the file that holds its passphrase.
	// Empty for the project's vault, whose passphrase MMX finds itself.
	file         string
	passwordFile string
	// asRoot runs MMX as root through sudo, for a vault in the coding
	// agent's checkout on the desk, which the person's account cannot read.
	// MMX then reads the project vault's passphrase from the desk's root
	// file itself, and the vault file MMX wrote goes back to coding-agent.
	// Reason for root and not coding-agent: a process of coding-agent's
	// could be read by the coding agent, which must never see the vault
	// passphrase.
	asRoot bool
}

// The coding agent's checkout of the systems repository on the desk, which
// the desk's bootstrap makes (roles/systems_desk/files/start-the-systems-repository),
// and the vault passphrase the bootstrap makes there, root:servers-mmx 0640.
const (
	codingAgentAccount      = "coding-agent"
	codingAgentCheckout     = "/home/coding-agent/systems_repository"
	deskVaultPassphraseFile = "/etc/systems-desk/vault-passphrase"
)

// arguments adds --vault and --vault-password-file for another vault file.
func (v mmxVault) arguments(arguments ...string) []string {
	if v.file != "" {
		arguments = append(arguments, "--vault", v.file, "--vault-password-file", v.passwordFile)
	}
	return arguments
}

// command is mmx with arguments, run in the vault's directory.
func (v mmxVault) command(arguments ...string) *exec.Cmd {
	if !v.asRoot {
		command := exec.Command("mmx", arguments...)
		command.Dir = v.directory
		return command
	}
	written := v.file
	if written == "" {
		written = filepath.Join(v.directory, vaultFile)
	}
	// The person's account cannot enter the coding agent's home, so the
	// shell changes into the directory as root.
	script := `cd -- "$1" || exit 1; written=$2; shift 2; mmx "$@"; status=$?
if [ -e "$written" ]; then chown --no-dereference coding-agent:coding-agent -- "$written" || exit 1; fi
exit "$status"`
	return exec.Command("sudo", append([]string{"-n", "env", "MMX_VAULT_PASSWORD_FILE=" + deskVaultPassphraseFile,
		"sh", "-c", script, "sh", v.directory, written}, arguments...)...)
}

func (v mmxVault) keys() (map[string]bool, error) {
	command := v.command(v.arguments("secrets", "list-keys", "--json")...)
	var output, errorOutput bytes.Buffer
	command.Stdout, command.Stderr = &output, &errorOutput
	if err := command.Run(); err != nil {
		return nil, fmt.Errorf("mmx secrets list-keys failed: %s", firstLine(errorOutput.String(), err))
	}
	var listing struct {
		Keys []string `json:"keys"`
	}
	if err := json.Unmarshal(output.Bytes(), &listing); err != nil {
		return nil, fmt.Errorf("mmx secrets list-keys printed something this command cannot read: %v", err)
	}
	keys := map[string]bool{}
	for _, key := range listing.Keys {
		keys[key] = true
	}
	return keys, nil
}

func (v mmxVault) set(key, value string, replace bool) error {
	arguments := []string{"secrets", "set", key}
	if replace {
		arguments = append(arguments, "--replace")
	}
	command := v.command(v.arguments(arguments...)...)
	command.Stdin = strings.NewReader(value)
	var errorOutput bytes.Buffer
	command.Stdout, command.Stderr = &errorOutput, &errorOutput
	// MMX never prints the value, also not in an error message, so its
	// message is safe to show.
	if err := command.Run(); err != nil {
		return fmt.Errorf("mmx secrets set %s failed: %s", key, firstLine(errorOutput.String(), err))
	}
	return nil
}

// value reads one value with mmx secrets pipe-to, which writes it to cat's
// standard input; cat's output comes back here, never to the screen. MMX
// ends the value with a newline, which is not part of it.
func (v mmxVault) value(key string) (string, error) {
	command := v.command(append(v.arguments("secrets", "pipe-to", key), "--", "cat")...)
	var output, errorOutput bytes.Buffer
	command.Stdout, command.Stderr = &output, &errorOutput
	if err := command.Run(); err != nil {
		return "", fmt.Errorf("mmx secrets pipe-to %s failed: %s", key, firstLine(errorOutput.String(), err))
	}
	return strings.TrimSuffix(output.String(), "\n"), nil
}

func firstLine(text string, fallback error) string {
	text = strings.TrimSpace(text)
	if text == "" {
		return fallback.Error()
	}
	return strings.SplitN(text, "\n", 2)[0]
}

// savedKeys is the vault as one run sees it: the key names MMX listed when
// the run opened the vault, plus each key the run saved since. It chooses
// --replace itself, so a caller only says what to save.
type savedKeys struct {
	store vault
	names map[string]bool
	// made lists the keys this run saved, in order, for the vault commit.
	made []string
	// leftover says the run committed a vault change an earlier run left,
	// which its push then carries.
	leftover bool
	// copyInto receives each saved key that copied names, as the recovery
	// bundle receives the secrets that exist nowhere else on the desk.
	copyInto *savedKeys
	copied   map[string]bool
}

// beginVaultChange opens the vault for a run that saves keys in it. It fails
// early, before any account changes, when MMX could not save a key or when
// the run could not commit and push the vault itself (see
// prepareVaultCommit). It lists the keys after the pull, so the run sees the
// team's vault.
func (e *environment) beginVaultChange() (*savedKeys, error) {
	leftover, err := e.prepareVaultCommit()
	if err != nil {
		return nil, err
	}
	names, err := e.vault.keys()
	if err != nil {
		return nil, err
	}
	return &savedKeys{store: e.vault, names: names, leftover: leftover}, nil
}

// hasAll says whether the vault holds every one of names.
func (v *savedKeys) hasAll(names ...string) bool {
	for _, name := range names {
		if !v.names[name] {
			return false
		}
	}
	return true
}

// hasAny says whether the vault holds at least one of names.
func (v *savedKeys) hasAny(names ...string) bool {
	for _, name := range names {
		if v.names[name] {
			return true
		}
	}
	return false
}

// save saves one value, replacing the key's old value when the vault has one.
// A value the recovery bundle keeps goes into the bundle first. Reason: a
// command makes only what the vault lacks, so a value in the vault but not
// in the bundle would stay missing from the bundle on every rerun.
func (v *savedKeys) save(name, value string) error {
	if v.copyInto != nil && v.copied[name] {
		if err := v.copyInto.save(name, value); err != nil {
			return err
		}
	}
	if err := v.store.set(name, value, v.names[name]); err != nil {
		return err
	}
	v.saved(name)
	return nil
}

// addRandom makes a random value inside MMX, replacing an old one.
func (v *savedKeys) addRandom(name string, length int) error {
	if err := v.store.addRandom(name, length, v.names[name]); err != nil {
		return err
	}
	v.saved(name)
	return nil
}

func (v *savedKeys) saved(name string) {
	v.names[name] = true
	v.made = append(v.made, name)
}

// vaultFile is the vault's file in the systems repository.
const vaultFile = "secrets_vault.age"

// filesThisCommandCommits are the only files this command commits: the
// vault and the recovery bundle. A change of either that an earlier run left
// is committed by the next run; any other change stops the run.
var filesThisCommandCommits = []string{vaultFile, recoveryBundleFile}

// sudoProgram is sudo; a test replaces it with a stand-in.
var sudoProgram = "sudo"

// gitAsTheCodingAgent runs git as coding-agent in its checkout on the desk,
// as the coding agent's own logins run it (roles/systems_desk/files/sshd.conf):
// the production key's relay socket reaches the main copy, and the coding
// agent's Git settings name the Git host's verified keys. So every file
// stays coding-agent's own, and no value passes through. Hooks are off: no
// file of the checkout runs here.
func gitAsTheCodingAgent(directory string) func(arguments ...string) (string, error) {
	return func(arguments ...string) (string, error) {
		command := exec.Command(sudoProgram, append([]string{"-n", "-u", codingAgentAccount, "env", "-C", directory,
			"HOME=/home/coding-agent", "SSH_AUTH_SOCK=/run/desk-ssh-agent/socket",
			"GIT_CONFIG_SYSTEM=/etc/systems-desk/coding-agent-gitconfig", "git", "-c", "core.hooksPath=/dev/null"}, arguments...)...)
		var output, errorOutput bytes.Buffer
		// No terminal: standard input stays /dev/null, output and errors go
		// to buffers, and a session of its own has no controlling terminal.
		// Reason: coding-agent's own Git settings run its programs, and one
		// that held the person's terminal could read the secrets typed there.
		command.Stdout, command.Stderr = &output, &errorOutput
		command.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
		if err := command.Run(); err != nil {
			return output.String(), fmt.Errorf("git %s failed: %s", strings.Join(arguments, " "), firstLine(errorOutput.String(), err))
		}
		return output.String(), nil
	}
}

// prepareVaultCommit makes sure the run's push holds only the vault and
// lands on top of the team's main: it refuses a repository with other
// uncommitted changes or with commits of the person's own not pushed yet,
// commits a vault change an earlier run left, and pulls. leftover says
// whether it committed such a change, which the run then pushes.
//
// After it, this checkout's vault is the team's vault, plus at most that
// left-over change on top. So a key this vault lacks, the team's lacks too,
// and issueAndSave may delete a same-name one at a provider as left over.
func (e *environment) prepareVaultCommit() (leftover bool, err error) {
	status, err := e.git("status", "--porcelain")
	if err != nil {
		return false, err
	}
	var others, ours []string
	for _, line := range strings.Split(strings.TrimRight(status, "\n"), "\n") {
		if line == "" {
			continue
		}
		if path := strings.TrimSpace(line[2:]); contains(filesThisCommandCommits, path) {
			ours = append(ours, path)
		} else {
			others = append(others, path)
		}
	}
	vaultChanged := len(ours) > 0
	if len(others) > 0 {
		return false, fmt.Errorf("this repository has changes that are not committed: %s. This command commits only the vault, so commit or undo those first, then run it again", strings.Join(others, ", "))
	}
	origin := e.hasOrigin()
	if origin {
		if _, err := e.git("fetch", "--quiet", "origin", "main"); err != nil {
			return false, err
		}
		ahead, err := e.git("rev-list", "--count", "origin/main..HEAD")
		if err != nil {
			return false, err
		}
		if strings.TrimSpace(ahead) != "0" {
			return false, fmt.Errorf("this repository has %s commits that are not pushed yet. This command pushes only the vault, so push those first (git push origin main), then run it again", strings.TrimSpace(ahead))
		}
	}
	if vaultChanged {
		if _, err := e.commitFiles("Save the vault changes left uncommitted", ours...); err != nil {
			return false, err
		}
		e.say("Committed the vault changes an earlier run or edit left uncommitted.")
	}
	if !origin {
		return vaultChanged, nil
	}
	if _, err := e.git("pull", "--rebase", "--quiet", "origin", "main"); err != nil {
		_, _ = e.git("rebase", "--abort")
		return false, fmt.Errorf("%v. Nothing changed in the vault. Pull the team's main by hand (git pull --rebase origin main), then run this command again", err)
	}
	return vaultChanged, nil
}

// hasOrigin says whether the checkout has an origin, the team's main copy
// of the systems repository on util01. Before util01 exists the desk's
// checkout has none: it is the main copy itself, so a command commits there
// and fetches and pushes nothing.
func (e *environment) hasOrigin() bool {
	_, err := e.git("remote", "get-url", "origin")
	return err == nil
}

// pushMain pushes the checkout's commits to the main copy, when the main
// copy is elsewhere, and says where main now is, for the command's message.
func (e *environment) pushMain() (string, error) {
	if !e.hasOrigin() {
		return "in the systems desk's checkout, the team's main copy until util01 exists", nil
	}
	_, err := e.git("push", "--quiet", "origin", "HEAD:main")
	return "to the main copy on util01", err
}

// commitFiles commits files and returns the commit's short hash.
func (e *environment) commitFiles(message string, files ...string) (string, error) {
	if _, err := e.git(append([]string{"add", "--"}, files...)...); err != nil {
		return "", err
	}
	if _, err := e.git(append([]string{"commit", "--quiet", "-m", message, "--"}, files...)...); err != nil {
		return "", err
	}
	commit, err := e.git("rev-parse", "--short", "HEAD")
	return strings.TrimSpace(commit), err
}

// finishVaultChange commits the keys this run saved, and the recovery
// bundle when it changed, pushes main to origin's main, and says so.
// command names the run, such as "set-up-outside-services backblaze", for
// the commit message.
func (e *environment) finishVaultChange(v *savedKeys, command string) error {
	e.say("")
	var files []string
	message := fmt.Sprintf("Add %d vault keys with %s\n\nKeys: %s", len(v.made), command, strings.Join(v.made, ", "))
	if len(v.made) > 0 {
		files = append(files, vaultFile)
	}
	status, err := e.git("status", "--porcelain", "--", recoveryBundleFile)
	if err != nil {
		return err
	}
	if strings.TrimSpace(status) != "" {
		files = append(files, recoveryBundleFile)
		if len(v.made) == 0 {
			message = "Update the recovery bundle with " + command
		}
	}
	if len(files) == 0 && !v.leftover {
		e.say("The vault needed nothing from this run, so nothing was committed.")
		return nil
	}
	commit, err := e.git("rev-parse", "--short", "HEAD")
	commit = strings.TrimSpace(commit)
	if err == nil && len(files) > 0 {
		commit, err = e.commitFiles(message, files...)
	}
	where := ""
	if err == nil {
		var pushErr error
		if where, pushErr = e.pushMain(); pushErr != nil {
			err = fmt.Errorf("%v. The commit %s is saved here", pushErr, commit)
		}
	}
	if err != nil {
		return fmt.Errorf("%v. The vault holds the new keys; fix the cause and run %s again, which commits and pushes them", err, command)
	}
	e.say("Committed the vault as commit %s, published %s, so the servers' next run gets the new keys.", commit, where)
	return nil
}

// issuedCredential is a key or token that a provider issues and the vault
// keeps. Each provider gives its own calls; issueAndSave keeps the order
// and the rules, the same for every provider.
type issuedCredential struct {
	provider   string   // "Backblaze" or "Cloudflare"
	item       string   // "key" or "token"
	name       string   // its name at the provider, as messages show it
	vaultNames []string // where its values go, in order
	// deletePage is where the person deletes one by hand.
	deletePage string
	// replaceSaved makes a new one although the vault holds one: a rotation,
	// which keeps the old one working, so it deletes no same-name one.
	replaceSaved bool
	// idsNamed lists the provider's ones with this name.
	idsNamed func() ([]string, error)
	delete   func(id string) error
	// create issues a new one. problem is set when the provider made it
	// other than asked, so it must not be saved.
	create func() (id string, values []string, problem string, err error)
}

// credentialOutcome says what issueAndSave did, for the caller's message.
type credentialOutcome int

const (
	alreadySaved credentialOutcome = iota
	issuedAndSaved
)

// issueAndSave makes sure the vault holds the credential:
//
//   - A complete set in the vault is left alone, so a rerun of a finished
//     setup creates nothing and a working credential is never revoked.
//   - A same-name one at the provider while the vault holds none of the set
//     is left over from a run whose answer was lost, so it is deleted first:
//     a rerun never leaves two behind. That holds because beginVaultChange
//     pulled the team's vault first, so a key this vault lacks, the team's
//     lacks too. When the vault holds part of the set, the saved part may
//     name one of them, so none is deleted.
//   - Ctrl-C between issuing and saving waits until it is saved or revoked.
//   - A lost answer says the provider may have made it anyway; the rerun
//     deletes such a one.
//   - When the provider made it other than asked, or a save fails, the new
//     one is revoked, and only that one. The message says whether the
//     revocation worked, and where to delete it by hand when it did not.
func (e *environment) issueAndSave(v *savedKeys, c issuedCredential) (credentialOutcome, string, error) {
	if v.hasAll(c.vaultNames...) && !c.replaceSaved {
		return alreadySaved, "", nil
	}
	if !c.replaceSaved {
		ids, err := c.idsNamed()
		if err != nil {
			return 0, "", err
		}
		if len(ids) > 0 && v.hasAny(c.vaultNames...) {
			e.say("  Kept %d %s %ss named %s: the vault still holds part of its set, which may name one of them. Delete any unused one by hand: %s", len(ids), c.provider, c.item, c.name, c.deletePage)
			ids = nil
		}
		for _, id := range ids {
			if err := c.delete(id); err != nil {
				return 0, "", err
			}
			e.say("  Deleted the %s %s (ID %s), left over from an earlier run that did not save it.", c.item, c.name, id)
		}
	}
	e.enterCriticalSection()
	defer e.leaveCriticalSection()
	id, values, problem, err := c.create()
	if err != nil {
		var lost *networkError
		if errors.As(err, &lost) {
			return 0, "", fmt.Errorf("%v. %s may have made the %s %s anyway. Run this command again: it deletes such a %s before making a new one", err, c.provider, c.item, c.name, c.item)
		}
		return 0, "", err
	}
	if problem != "" {
		return 0, "", fmt.Errorf("%s made the %s %s %s. It is not saved, %s. Run this command again", c.provider, c.item, c.name, problem, c.revoked(id))
	}
	for i, name := range c.vaultNames {
		if err := v.save(name, values[i]); err != nil {
			saved := strings.Join(c.vaultNames[:i], " and ")
			if saved == "" {
				saved = "nothing"
			}
			return 0, "", fmt.Errorf("%v. The vault got %s of the new %s %s %s, %s. Fix the cause, then run this command again", err, saved, c.provider, c.item, c.name, c.revoked(id))
		}
	}
	return issuedAndSaved, id, nil
}

// revoked revokes a new credential that is not saved and says what is left.
func (c issuedCredential) revoked(id string) string {
	if err := c.delete(id); err != nil {
		return fmt.Sprintf("and revoking the new %s %s %s (ID %s) failed too (%v): delete it by hand at %s", c.provider, c.item, c.name, id, err, c.deletePage)
	}
	return fmt.Sprintf("so this command revoked the new %s %s %s. Nothing else changed", c.provider, c.item, c.name)
}
