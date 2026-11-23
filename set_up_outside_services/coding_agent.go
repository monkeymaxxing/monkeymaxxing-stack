package main

import (
	"bufio"
	"errors"
	"fmt"
	"io"
	"os"
	"os/user"
	"regexp"
	"strconv"
	"strings"
)

// from-the-coding-agent runs an account command for the coding agent, which
// passes the person's key on standard input, straight from the clipboard,
// so the key never shows in the agent's chat. The agent runs it on the desk
// through one sudo rule:
//
//	coding-agent ALL=(root) NOPASSWD: /usr/local/bin/set-up-outside-services from-the-coding-agent *
//
// so it runs as root, the way the desk's other agent rules run their one
// command. Root keeps the key out of every process the coding agent could
// read. The command takes no path or setting from its caller, prints no
// key, and reads none back: the agent can put a key in, never get one out.
// It checks its arguments strictly before it reads standard input, and it
// works for the person the desk role names in a root-only file, never for
// root. It reads the coding agent's checkout as the coding agent, so a
// symbolic link there reaches nothing the coding agent cannot read itself.

const fromTheCodingAgentCommand = "from-the-coding-agent"

// codingAgentCommand is one checked command line of from-the-coding-agent.
type codingAgentCommand struct {
	name string
	// accountID is cloudflare's --account-id; key is save-a-key's KEY.
	accountID string
	key       string
}

var vaultKeyPattern = regexp.MustCompile(`^[A-Za-z0-9_]{1,128}$`)

// readCodingAgentArguments checks the command line exactly, before
// anything else runs: one of the four commands with only its own arguments.
func readCodingAgentArguments(arguments []string) (codingAgentCommand, error) {
	const commands = "backblaze, cloudflare [--account-id ID], save-a-key KEY, or random-secrets"
	if len(arguments) == 0 {
		return codingAgentCommand{}, fmt.Errorf("%s needs one of %s: %w", fromTheCodingAgentCommand, commands, errUsage)
	}
	command := codingAgentCommand{name: arguments[0]}
	rest := arguments[1:]
	switch {
	case (command.name == "backblaze" || command.name == "random-secrets" || command.name == "cloudflare") && len(rest) == 0:
	case command.name == "cloudflare" && len(rest) == 2 && rest[0] == "--account-id" && cloudflareAccountIDPattern.MatchString(rest[1]):
		command.accountID = rest[1]
	case command.name == "save-a-key" && len(rest) == 1 && vaultKeyPattern.MatchString(rest[0]):
		command.key = rest[0]
	default:
		return codingAgentCommand{}, fmt.Errorf("%s takes only %s: %w", fromTheCodingAgentCommand, commands, errUsage)
	}
	return command, nil
}

// runFromTheCodingAgent is the whole of from-the-coding-agent.
func runFromTheCodingAgent(arguments []string, input io.Reader, out io.Writer) error {
	command, err := readCodingAgentArguments(arguments)
	if err != nil {
		return err
	}
	if os.Geteuid() != 0 {
		return fmt.Errorf("%s runs as root, through the systems desk's sudo rule: sudo -n /usr/local/bin/set-up-outside-services %s %s", fromTheCodingAgentCommand, fromTheCodingAgentCommand, strings.Join(arguments, " "))
	}
	e := defaultEnvironment(out)
	e.useTheCodingAgentsCheckout()
	if err := e.becomeTheDesksPerson(); err != nil {
		return err
	}
	e.readFromTheCodingAgent(input)
	e.handleInterrupts()
	return e.runForTheCodingAgent(command)
}

// readFromTheCodingAgent makes the prompts read the coding agent's
// standard input, one value per line, and refuses every question: the
// coding agent has no terminal, and a question would wait for ever.
func (e *environment) readFromTheCodingAgent(input io.Reader) {
	e.forTheCodingAgent = true
	// A value is one line; 1 MiB holds every key many times over.
	lines := bufio.NewReader(io.LimitReader(input, 1<<20))
	number := 0
	e.prompt = func(label string) (string, error) {
		number++
		what := strings.TrimSpace(strings.TrimSuffix(strings.TrimSpace(label), "(hidden):"))
		line, err := lines.ReadString('\n')
		if err != nil && !errors.Is(err, io.EOF) {
			return "", err
		}
		// A Windows clipboard ends its text with a carriage return.
		value := strings.TrimSpace(strings.TrimRight(line, "\r\n"))
		if value == "" {
			return "", fmt.Errorf("line %d of standard input, %s, is empty or missing. Give one value per line", number, what)
		}
		return value, nil
	}
	e.confirm = func(label string) (string, error) {
		return "", errors.New("this step needs the person's answer in their own terminal, so the coding agent cannot run it")
	}
}

// runForTheCodingAgent runs one checked command. Each takes the same path as
// the person's own command of the same name; only the input differs.
func (e *environment) runForTheCodingAgent(command codingAgentCommand) error {
	switch command.name {
	case "backblaze":
		return runBackblaze(e, nil)
	case "cloudflare":
		var arguments []string
		if command.accountID != "" {
			arguments = []string{"--account-id", command.accountID}
		}
		return runCloudflare(e, arguments)
	case "save-a-key":
		return runSaveAKey(e, command.key)
	case "random-secrets":
		return runRandomSecrets(e)
	}
	return fmt.Errorf("unknown command %q: %w", command.name, errUsage)
}

// deskPersonFile names the desk's person, written by the desk role as root.
// Reason: the command runs as root for the coding agent, so it takes the
// person's account from a file only root writes, never from the coding
// agent's own checkout, where a changed name could aim root's writes at
// another account's files.
const deskPersonFile = "/etc/systems-desk/person-unix-username"

// becomeTheDesksPerson works for the desk's person, never for root, which
// runs the command: the person's tokens carry the person's name, and each
// file in the person's home stays the person's own.
func (e *environment) becomeTheDesksPerson() error {
	content, err := e.readRootFile(deskPersonFile)
	if err != nil {
		return fmt.Errorf("this systems desk has no %s, which names its person. Run the systems desk's playbook again: %v", deskPersonFile, err)
	}
	person := strings.TrimSpace(string(content))
	if !unixUserNamePattern.MatchString(person) || contains(accountsThatMayNotRun, person) {
		return fmt.Errorf("%s names %q, which is not a person's account", deskPersonFile, person)
	}
	account, err := user.Lookup(person)
	if err != nil {
		return fmt.Errorf("this systems desk has no account %s, the person %s names: %v", person, deskPersonFile, err)
	}
	uid, uidErr := strconv.Atoi(account.Uid)
	gid, gidErr := strconv.Atoi(account.Gid)
	if uidErr != nil || gidErr != nil {
		return fmt.Errorf("the account %s has no numeric user and group ID", person)
	}
	e.person, e.home, e.owner = person, account.HomeDir, &fileOwner{uid: uid, gid: gid}
	return nil
}

// runPersonsSaveAKey is the person's save-a-key KEY, in their own window,
// for a key the coding agent cannot send from the clipboard: one key, at a
// hidden prompt, and no other question.
func runPersonsSaveAKey(e *environment, arguments []string) error {
	if len(arguments) != 1 || !vaultKeyPattern.MatchString(arguments[0]) {
		return fmt.Errorf("save-a-key takes one KEY, such as %s: %w", registryTokenVaultKey, errUsage)
	}
	return runSaveAKey(e, arguments[0])
}

// runSaveAKey saves one vault key that only a person can give, after its
// service's check: the registry's read-only token or an app's key from an
// outside service.
func runSaveAKey(e *environment, key string) error {
	e.named("save-a-key " + key)
	return e.asStep(key, func(notes map[string]string) (string, error) {
		settings, err := readSystemSettings(e.readRepositoryFile)
		if err != nil {
			return "", err
		}
		if err := settings.checkAppSecrets(); err != nil {
			return "", err
		}
		item, ok := keyOnlyAPersonGives(settings, key)
		if !ok {
			return "", fmt.Errorf("save-a-key saves only a key the playbooks read that only a person can give: %s. The other keys come from the other commands", strings.Join(keysOnlyAPersonGives(settings), ", "))
		}
		saved, err := e.beginAccountChange(settings)
		if err != nil {
			return "", err
		}
		value, err := e.prompt("Paste " + item.What + " (hidden): ")
		if err != nil {
			return "", err
		}
		if err := e.checkAKeyBeforeSaving(settings, item, value, notes); err != nil {
			return "", err
		}
		if err := saved.save(item.Key, value); err != nil {
			return "", err
		}
		e.say("Saved %s in the vault as %s.", item.What, item.Key)
		if err := e.finishVaultChange(saved, e.commandLine); err != nil {
			return "", err
		}
		return stepDone, nil
	})
}

// runRandomSecrets makes every random vault secret the vault lacks, without
// a question, and saves the desk's own server provider credential as
// util01's: providers such as Hetzner make tokens only on their website, and
// util01's restore drill needs one. The servers' console password is not one
// of them: lock-the-desk makes it, in the person's own window, because only
// the person may see it.
func runRandomSecrets(e *environment) error {
	e.named("random-secrets")
	return e.asStep("random_secrets", func(notes map[string]string) (string, error) {
		settings, err := readSystemSettings(e.readRepositoryFile)
		if err != nil {
			return "", err
		}
		if err := settings.checkAppSecrets(); err != nil {
			return "", err
		}
		providerCredential, err := e.readProviderCredential(settings)
		if err != nil {
			return "", err
		}
		saved, err := e.beginAccountChange(settings)
		if err != nil {
			return "", err
		}
		var made []string
		if !saved.hasAll("util01_provider_api_token") {
			if err := saved.save("util01_provider_api_token", providerCredential); err != nil {
				return "", err
			}
			e.say("Copied your server provider key into the vault as util01_provider_api_token, for util01's own work.")
		}
		for _, item := range secretsPlan(settings) {
			if item.Kind != randomSecret || saved.hasAll(item.Key) {
				continue
			}
			if err := saveRandomSecret(saved, item); err != nil {
				return "", err
			}
			made = append(made, item.Key)
		}
		e.say("Made and saved in the vault: %s.", listOrNone(made))
		if err := e.finishVaultChange(saved, e.commandLine); err != nil {
			return "", err
		}
		return stepDone, nil
	})
}
