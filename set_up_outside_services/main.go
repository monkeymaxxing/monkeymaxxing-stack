// set-up-outside-services does the account and secret work of the
// Monkeymaxxing Stack's setup on a systems desk: the buckets and keys at
// Backblaze, the tokens and R2 keys at Cloudflare, the vault's other
// secrets, the person's own tokens on the desk, and the recovery bundle. The
// person runs it on the desk from the laptop, with a short SSH entry such as
// ssh desk01-secrets. It asks for each master credential at a hidden
// prompt, keeps it in memory only, and saves each new key straight into the
// vault of the desk's checkout of the systems repository with `mmx secrets
// set`. docs/design.md, "Account and secret setup from the systems desk",
// records the design.
package main

import (
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"os/signal"
	"os/user"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"syscall"
	"time"
)

// version is set at release build time: -ldflags "-X main.version=..."
var version = "development"

const usage = `set-up-outside-services sets up your system's accounts at Backblaze and
Cloudflare, the vault's other secrets, your own tokens on this systems desk, and the
recovery bundle. During the setup your coding agent runs the account commands for
you, with each key passed straight from your clipboard; you run the lock yourself
with ssh desk01-lock. You run the other commands from your laptop with
ssh -t desk01, plus a code from your phone once the desk is locked, such as:

  ssh -t desk01 set-up-outside-services backblaze

Every command works in the systems desk's checkout of the systems repository,
/home/coding-agent/systems_repository, from any folder. backblaze, cloudflare,
secrets and the coding agent's commands write which steps are done, never a
secret, to /var/lib/monkeymaxxing-stack/setup_results.json.

Commands:
  backblaze [--replace-key VAULT_KEY]... [--delete-the-old-keys-at-once]
                                Create every B2 bucket with its lock and lifecycle rule,
                                check each lock, and save each server's key in the vault,
                                from the account's master key. --replace-key makes a new
                                key for a saved one, to rotate it, such as --replace-key
                                pgbackrest_b2_write_key_id. The old key keeps working until
                                the servers' run passed and you press Enter;
                                --delete-the-old-keys-at-once deletes it without waiting,
                                after a break-in.
  cloudflare [--account-id ID] [--replace-key NAME]... [--replace-every-key] [--delete-the-old-keys-at-once]
                                From one link token you make with the link it prints: find
                                the account (--account-id names it when the token reaches
                                several), add your domain and copy its DNS records, give the
                                account its workers.dev address, then make your systems
                                desk's Cloudflare token (in the API proxy and your token
                                file), the tunnels, the R2 buckets and keys, the
                                MMHotline-down alarm's token, the status page and your own
                                key for posting to it, and the One-time PIN login method;
                                save the servers' keys in the vault. With staging01, also
                                make staging's Access service token, saved in your token
                                file. The status page waits until your domain is Active, and
                                the R2 buckets until R2 is on. The link token is deleted when
                                the command ends.
                                --replace-key makes a new key for a saved one and saves it,
                                such as --replace-key shop_R2_ACCESS_KEY_ID; --replace-every-key
                                replaces all. A key the servers use keeps its old key working
                                until the servers' run passed and you press Enter, as for
                                backblaze; --delete-the-old-keys-at-once deletes it at once.
  cloudflare --delete-tokens-of-person NAME
                                Delete, by name, the Cloudflare tokens this command made for a
                                person who leaves the team. NAME is their systems desk account name.
  secrets [--replace KEY]       Save every vault secret the servers read that the vault lacks:
                                the ones only a website gives, at hidden prompts, with the page
                                where you make each, and random ones nobody needs to see.
                                --replace KEY enters one again; --replace
                                shared_root_console_password_hash makes a new console
                                password, shown once for your password manager.
  lock-the-desk                 The setup's last step, in your own window (ssh desk01-lock):
                                the servers' shared root console password, shown once; your
                                recovery passphrase, shown once; your phone code. Then it
                                checks that the recovery bundle, recovery_bundle.age, holds
                                every item, commits and pushes it with the vault, and copies
                                it into the locked backup bucket. A rerun continues where a
                                run stopped.
  personal-token server-provider --server-listing-path PATH [--token-header NAME]
                                Replace your server provider token in the systems desk's API proxy,
                                such as after a rotation. PATH is the provider guide's server
                                listing, such as servers for Hetzner Cloud. NAME is the
                                guide's header for a provider without Authorization: Bearer,
                                such as X-Auth-Token for Scaleway. For a provider whose
                                requests are signed, such as OVHcloud or AWS, it asks for each
                                value the provider's page gives, or at Google Cloud for the
                                service account's key file.
  personal-token staging-access Save staging's Access service token, from your password manager,
                                in your token file, on a systems desk where cloudflare did not make it.
  from-the-coding-agent backblaze | cloudflare [--account-id ID] | save-a-key KEY | random-secrets
                                Your coding agent's way to run an account command, as root
                                through the desk's sudo rule, with each key on standard input,
                                one value per line, so the key never shows in its chat:
                                backblaze takes the master key's keyID and applicationKey;
                                cloudflare the link token; save-a-key KEY the value of
                                container_registry_read_only_token or of an app's key from an
                                outside service, checked at its service; random-secrets makes
                                every random vault secret and takes nothing. It prints no key.
  version                       Print this program's version.

backblaze, cloudflare, secrets, lock-the-desk and the coding agent's commands each
commit and push the vault to the main copy on util01, and refuse a repository with
other changes not pushed. Before util01 exists, the systems desk's checkout is the
main copy: they commit there.
`

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}

func run(arguments []string, out, errorOut io.Writer) int {
	if len(arguments) == 0 || arguments[0] == "--help" || arguments[0] == "-h" || arguments[0] == "help" {
		fmt.Fprint(out, usage)
		return 0
	}
	if arguments[0] == "version" {
		fmt.Fprintf(out, "set-up-outside-services %s\n", version)
		return 0
	}
	var err error
	switch arguments[0] {
	case writeProxyFileCommand:
		err = runWriteAPITokenProxyFile(arguments[1:], os.Stdin, out)
	case apiProxyCommand:
		err = runProviderAPIProxy(arguments[1:])
	case fromTheCodingAgentCommand:
		return codingAgentExitCode(runFromTheCodingAgent(arguments[1:], os.Stdin, out), errorOut)
	default:
		var e *environment
		e, err = newEnvironment(out)
		if err == nil {
			err = e.dispatch(arguments)
		}
	}
	if err != nil {
		if errors.Is(err, errUsage) {
			fmt.Fprintf(errorOut, "Stopped: %v.\n", trimPeriod(err.Error()))
			return 4
		}
		// The plain sentence comes first, the technical line after it.
		fmt.Fprintf(errorOut, "%s\n\nTechnical line for your coding agent:\n", failureInPlainWords(arguments[0]))
		fmt.Fprintf(errorOut, "Stopped: %v.\n", trimPeriod(err.Error()))
		return 1
	}
	return 0
}

// codingAgentExitCode prints a stop of from-the-coding-agent for the coding
// agent alone: the reason, which never holds a secret, on standard error.
func codingAgentExitCode(err error, errorOut io.Writer) int {
	if err == nil {
		return 0
	}
	fmt.Fprintf(errorOut, "Stopped: %v.\n", trimPeriod(err.Error()))
	if errors.Is(err, errUsage) {
		return 4
	}
	return 1
}

// failureInPlainWords says, before any technical line: what failed, whether
// anything is harmed, and what happens next. The reason it claims no
// undo or rollback: the commands undo nothing they finished, and none of
// them touches the person's site or servers when it stops.
func failureInPlainWords(command string) string {
	what := "The command " + command + " stopped before it finished."
	if command == "lock-the-desk" {
		what = "Locking your systems desk stopped before it finished."
	}
	return what + "  Nothing that it already finished is undone, and your site and servers are not affected.  " +
		"Tell your coding agent: it reads the technical line below and tells you what to do next."
}

var errUsage = errors.New("see set-up-outside-services --help")

func (e *environment) dispatch(arguments []string) error {
	switch arguments[0] {
	case "backblaze":
		return runBackblaze(e, arguments[1:])
	case "cloudflare":
		return runCloudflare(e, arguments[1:])
	case "personal-token":
		return runPersonalToken(e, arguments[1:])
	case "secrets":
		if !stdinIsTerminal() {
			return errNoTerminal
		}
		return runSecrets(e, arguments[1:])
	case "lock-the-desk":
		// The console password and the recovery passphrase show only in a
		// terminal the person watches.
		if !stdinIsTerminal() {
			return errNoTerminal
		}
		return e.withNoMoreArguments(arguments, runLockTheDesk)
	}
	return fmt.Errorf("unknown command %q: %w", arguments[0], errUsage)
}

func (e *environment) withNoMoreArguments(arguments []string, command func(*environment) error) error {
	if len(arguments) > 1 {
		return fmt.Errorf("%s takes no arguments: %w", arguments[0], errUsage)
	}
	return command(e)
}

// environment holds what the commands use from outside: the repository,
// the vault, the terminal, and the providers' addresses. Tests replace them.
type environment struct {
	directory string
	home      string
	// person is the person's account name on the desk, which names the
	// person's own Cloudflare tokens.
	person string
	// owner is the person's account when the command runs as root for the
	// coding agent, so each file it writes in the person's home stays the
	// person's; nil when the person runs it.
	owner *fileOwner
	// forTheCodingAgent says the coding agent runs the command: the keys
	// come on standard input and nothing asks a question.
	forTheCodingAgent bool
	// commandLine names the run, such as set-up-outside-services backblaze,
	// in commit messages and the results file.
	commandLine      string
	out              io.Writer
	vault            vault
	prompt           func(label string) (string, error)
	confirm          func(label string) (string, error)
	b2AuthorizeURL   string
	cloudflareAPIURL string
	// providerGuideAPIAddresses, the only addresses that get the person's
	// server provider token.
	providerGuideAPIAddresses []string
	// signingAPIAddresses, the same for each way of signing requests.
	signingAPIAddresses map[string]*regexp.Regexp
	now                 func() time.Time
	// runMMHotlineStatusPageSetUp runs `mmhotline status-page set-up`.
	runMMHotlineStatusPageSetUp func(accountID, hostName, token string) (statusPageSetUp, error)
	// writeProxyFile installs a token in the desk's API proxy, as root.
	writeProxyFile func(request proxyFileRequest) error
	clearScreen    func()
	// The outside addresses of the first-time and key checks: IANA's RDAP
	// bootstrap file, GitHub's API, the registry the apps' images come from,
	// and Stripe's API.
	rdapBootstrapURL     string
	githubAPIURL         string
	containerRegistryURL string
	stripeAPIURL         string
	// readRootFile reads a file of the desk that only root reads, through
	// sudo; setUpThePhoneCode runs the desk's phone-code setup as root.
	readRootFile      func(path string) ([]byte, error)
	setUpThePhoneCode func(emergencyCodesPath string) error
	// deskIsLocked says the desk playbook's lock stage ran on this desk.
	deskIsLocked func() bool
	// resultsFile is the results file the coding agent reads, and
	// backupWriteKeyFile keeps the backup write key for the bundle's upload.
	resultsFile        string
	backupWriteKeyFile string
	// writeFileAsRoot and removeFileAsRoot change a file only root may
	// change, through sudo.
	writeFileAsRoot  func(path string, mode os.FileMode, content []byte) error
	removeFileAsRoot func(path string) error
	// bundleStore replaces the recovery bundle's MMX vault in a test.
	bundleStore vault
	// replaceKeys names the keys a rotation replaces: B2 key pairs by their
	// key ID's vault name, Cloudflare's by --replace-key's names.
	replaceKeys map[string]bool
	// deleteOldKeysAtOnce deletes a replaced key's old key without waiting
	// for the servers' run, after a break-in.
	deleteOldKeysAtOnce bool
	// git runs git in the systems repository, through the production key's
	// agent socket, which reaches the main copy.
	git func(arguments ...string) (string, error)
	// inTheCodingAgentsCheckout says the systems repository is the coding
	// agent's checkout on the desk, which the person's account reaches
	// only through sudo.
	inTheCodingAgentsCheckout bool

	interruptMutex    sync.Mutex
	inCriticalSection bool
	interrupted       bool
	// valueOnScreen is true while a secret shows on the screen, such as the
	// recovery passphrase, so Ctrl-C clears the screen before it stops.
	valueOnScreen bool
}

// The accounts that must never run this command: the coding agent, so it
// never sees a key, and the button and root accounts, which are not a person.
var accountsThatMayNotRun = []string{"coding-agent", "servers-mmx", "root"}

// newEnvironment is the person's own run, in their own desk account.
func newEnvironment(out io.Writer) (*environment, error) {
	current, err := user.Current()
	if err != nil {
		return nil, err
	}
	for _, name := range accountsThatMayNotRun {
		if current.Username == name {
			return nil, fmt.Errorf("this command runs only in the person's own account, never as %s. The person runs it in their own systems desk terminal, where its prompts keep every key away from the coding agent. The coding agent runs set-up-outside-services from-the-coding-agent", name)
		}
	}
	e := defaultEnvironment(out)
	e.home, e.person = current.HomeDir, current.Username
	e.useTheCodingAgentsCheckout()
	e.handleInterrupts()
	return e, nil
}

// defaultEnvironment is the desk's real environment, without the person.
func defaultEnvironment(out io.Writer) *environment {
	return &environment{
		out:                         out,
		prompt:                      readHiddenLine,
		confirm:                     readVisibleLine,
		b2AuthorizeURL:              b2AuthorizeURL,
		cloudflareAPIURL:            cloudflareAPIURL,
		providerGuideAPIAddresses:   providerGuideAPIAddresses,
		signingAPIAddresses:         signingAPIAddresses,
		now:                         time.Now,
		runMMHotlineStatusPageSetUp: runMMHotlineStatusPageSetUp,
		writeProxyFile:              writeProxyFileWithSudo,
		clearScreen:                 clearTerminal,
		rdapBootstrapURL:            "https://data.iana.org/rdap/dns.json",
		githubAPIURL:                "https://api.github.com",
		containerRegistryURL:        "https://ghcr.io",
		stripeAPIURL:                "https://api.stripe.com",
		readRootFile:                readRootFileWithSudo,
		setUpThePhoneCode:           setUpThePhoneCodeWithSudo,
		deskIsLocked:                func() bool { return deskIsLockedAt(deskLockedFile, deskRootLoginBeforeTheLockFile) },
		resultsFile:                 setupResultsFile,
		backupWriteKeyFile:          backupWriteKeyFile,
		writeFileAsRoot:             writeFileAsRootWithSudo,
		removeFileAsRoot:            removeFileAsRootWithSudo,
	}
}

// named names the running command, such as set-up-outside-services
// backblaze, for its commit messages and the results file.
func (e *environment) named(command string) {
	e.commandLine = "set-up-outside-services " + command
	if e.forTheCodingAgent {
		e.commandLine = "set-up-outside-services " + fromTheCodingAgentCommand + " " + command
	}
}

func (e *environment) say(format string, values ...any) {
	fmt.Fprintf(e.out, format+"\n", values...)
}

// show prints a screen's text as it is, ending its last line.
func (e *environment) show(text string) {
	if !strings.HasSuffix(text, "\n") {
		text += "\n"
	}
	fmt.Fprint(e.out, text)
}

// useTheCodingAgentsCheckout makes every command work in the desk's one
// working copy of the systems repository, the coding agent's checkout,
// where the desk's bootstrap made the vault, whatever folder the command
// starts in: MMX runs as root with the
// desk's vault passphrase file, and git runs as coding-agent with the
// production key's relay socket, so a push reaches the main copy and every file
// stays coding-agent's own. The person keeps no checkout on the desk.
func (e *environment) useTheCodingAgentsCheckout() {
	e.directory = codingAgentCheckout
	e.vault = mmxVault{directory: codingAgentCheckout, asRoot: true}
	e.git = gitAsTheCodingAgent(codingAgentCheckout)
	e.inTheCodingAgentsCheckout = true
}

// readRepositoryFile reads a file of the systems repository, through sudo
// in the coding agent's checkout.
func (e *environment) readRepositoryFile(name string) ([]byte, error) {
	path := filepath.Join(e.directory, name)
	if e.inTheCodingAgentsCheckout {
		return e.readRootFile(path)
	}
	return os.ReadFile(path)
}

// repositoryHas says whether the systems repository holds a file.
func (e *environment) repositoryHas(name string) bool {
	if e.inTheCodingAgentsCheckout {
		return exec.Command("sudo", "-n", "test", "-e", filepath.Join(e.directory, name)).Run() == nil
	}
	_, err := os.Stat(filepath.Join(e.directory, name))
	return err == nil
}

const sayTheCodingAgentCarriesOn = "This command finished. Your coding agent carries on by itself: it checks the result with mmx secrets usage, which lists names only."

// handleInterrupts lets Ctrl-C stop the command at once, except between a
// provider issuing a key and the vault saving it. There the command first
// finishes saving, or revokes the new key, so nothing is left half done.
func (e *environment) handleInterrupts() {
	screen := e.out
	signals := make(chan os.Signal, 1)
	signal.Notify(signals, os.Interrupt, syscall.SIGTERM, syscall.SIGHUP)
	go func() {
		for range signals {
			e.interruptMutex.Lock()
			if e.inCriticalSection {
				e.interrupted = true
				e.interruptMutex.Unlock()
				fmt.Fprintln(screen, "\nStopping once the key being saved is saved or revoked.")
				continue
			}
			clear := e.valueOnScreen
			e.interruptMutex.Unlock()
			restoreTerminal()
			if clear {
				e.clearScreen()
			}
			fmt.Fprintln(screen, "\nStopped. A rerun continues where this run stopped.")
			os.Exit(130)
		}
	}()
}

func (e *environment) enterCriticalSection() {
	e.interruptMutex.Lock()
	e.inCriticalSection = true
	e.interruptMutex.Unlock()
}

func (e *environment) leaveCriticalSection() {
	e.interruptMutex.Lock()
	e.inCriticalSection = false
	stop := e.interrupted
	e.interruptMutex.Unlock()
	if stop {
		fmt.Fprintln(e.out, "Stopped after the last key was saved. A rerun continues where this run stopped.")
		os.Exit(130)
	}
}

func (e *environment) stopIfInterrupted() error {
	e.interruptMutex.Lock()
	defer e.interruptMutex.Unlock()
	if e.interrupted {
		return errors.New("interrupted. A rerun continues where this run stopped")
	}
	return nil
}

func (e *environment) setValueOnScreen(on bool) {
	e.interruptMutex.Lock()
	e.valueOnScreen = on
	e.interruptMutex.Unlock()
}

// clearValueFromScreen clears the screen and its scrollback once a shown
// secret is no longer needed there.
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

func trimPeriod(text string) string {
	for len(text) > 0 && text[len(text)-1] == '.' {
		text = text[:len(text)-1]
	}
	return text
}
