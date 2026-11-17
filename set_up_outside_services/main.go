// set-up-outside-services does the account and secret work of the
// Monkeymaxxing Stack's setup on a systems desk: the buckets and keys at
// Backblaze, the tokens and R2 keys at Cloudflare, the vault's other
// secrets, the person's own tokens on the desk, and the recovery bundle. The
// person runs it in their own desk terminal. It asks for each master
// credential at a hidden prompt, keeps it in memory only, and saves each new
// key straight into the systems repository's vault with `mmx secrets set`.
// docs/design.md, "Account and secret setup from the systems desk", records
// the design.
package main

import (
	"errors"
	"fmt"
	"io"
	"os"
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
Cloudflare, the vault's other secrets, your own tokens on this desk, and the
recovery bundle. Run it in your own desk terminal. The first setup runs go-live
through ssh desk01-setup. The other commands run in your systems repository,
after loading your token file:

  . ~/.config/monkeymaxxing-stack/example_systems.env && set-up-outside-services backblaze

Commands:
  go-live                       The first setup, one screen at a time: Cloudflare, your
                                domain's registrar, Backblaze, the registry's token, your apps'
                                keys from outside services, every other vault secret without
                                a question, then the lock: your
                                recovery passphrase and your phone code. It saves the
                                recovery bundle, recovery_bundle.age, commits and pushes it
                                with the vault, signed, and copies it into the locked backup
                                bucket. It writes which steps are done, never a secret, to
                                /var/lib/monkeymaxxing-stack/setup_results.json. A rerun
                                continues where a run stopped.
  backblaze [--replace-key VAULT_KEY]... [--delete-the-old-keys-at-once]
                                Create every B2 bucket with its lock and lifecycle rule,
                                check each lock, and save each server's key in the vault.
                                --replace-key makes a new key for a saved one, to rotate it,
                                such as --replace-key pgbackrest_b2_write_key_id. The old
                                key keeps working until the servers' run passed and you press
                                Enter; --delete-the-old-keys-at-once deletes it without waiting,
                                after a break-in.
  cloudflare [--replace-key NAME]... [--replace-every-key] [--delete-the-old-keys-at-once]
                                From one link token you make with the link it prints, make
                                your desk's Cloudflare token (in the API proxy and your
                                token file), the tunnels, the R2 buckets and keys, the
                                MMHotline-down alarm's token, the status page and your own
                                key for posting to it, and the One-time PIN login method; save
                                the servers' keys in the vault. With staging01, also make
                                staging's Access service token, saved in your token file.
                                The status page waits until your domain is Active. The link
                                token is deleted when the command ends.
                                --replace-key makes a new key for a saved one and saves it,
                                such as --replace-key shop_R2_ACCESS_KEY_ID; --replace-every-key
                                replaces all. A key the servers use keeps its old key working
                                until the servers' run passed and you press Enter, as for
                                backblaze; --delete-the-old-keys-at-once deletes it at once.
  cloudflare --delete-tokens-of-person NAME
                                Delete, by name, the Cloudflare tokens this command made for a
                                person who leaves the team. NAME is their desk account name.
  personal-token server-provider --server-listing-path PATH [--token-header NAME]
                                Save your server provider token in your token file and in
                                the desk's API proxy. PATH is the provider guide's
                                server listing, such as servers for Hetzner Cloud. NAME is
                                the guide's header for a provider without Authorization:
                                Bearer, such as X-Auth-Token for Scaleway. For a provider
                                whose requests are signed, such as OVHcloud or AWS, it asks
                                for each value the provider's page gives, or at Google Cloud
                                for the service account's key file, and fills the desk's API
                                API proxy instead.
  personal-token staging-access Save staging's Access service token, from your password manager,
                                in your token file, on a desk where cloudflare did not make it.
  secrets [--replace KEY]       Save every vault secret the servers read that the vault lacks:
                                the ones only a website gives, at hidden prompts, with the page
                                where you make each, the servers' console password, shown once
                                for your password manager, and random ones nobody needs to see.
                                --replace KEY enters one again.
                                go-live, backblaze, cloudflare and secrets each commit and push
                                the vault, signed, and refuse a repository with other changes
                                not pushed.
  version                       Print this program's version.
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
	default:
		var e *environment
		e, err = newEnvironment(out)
		if err == nil {
			err = e.dispatch(arguments)
		}
	}
	if err != nil {
		fmt.Fprintf(errorOut, "Stopped: %v.\n", trimPeriod(err.Error()))
		if errors.Is(err, errUsage) {
			return 4
		}
		return 1
	}
	return 0
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
	case "go-live":
		// The recovery passphrase shows only in a terminal the person watches.
		if !stdinIsTerminal() {
			return errNoTerminal
		}
		if err := e.useTheSystemsRepository(); err != nil {
			return err
		}
		return e.withNoMoreArguments(arguments, runGoLive)
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
	person           string
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
	// go-live's outside addresses: IANA's RDAP bootstrap file, GitHub's API,
	// and the registry the apps' images come from.
	rdapBootstrapURL     string
	githubAPIURL         string
	containerRegistryURL string
	stripeAPIURL         string
	// readRootFile reads a file of the desk that only root reads, through
	// sudo; setUpThePhoneCode runs the desk's phone-code setup as root.
	readRootFile      func(path string) ([]byte, error)
	setUpThePhoneCode func(emergencyCodesPath string) error
	// resultsFile is go-live's results file; writeResultsFile writes it.
	resultsFile      string
	writeResultsFile func(content []byte) error
	// replaceKeys names the keys a rotation replaces: B2 key pairs by their
	// key ID's vault name, Cloudflare's by --replace-key's names.
	replaceKeys map[string]bool
	// deleteOldKeysAtOnce deletes a replaced key's old key without waiting
	// for the servers' run, after a break-in.
	deleteOldKeysAtOnce bool
	// git runs git in the systems repository, through the person's own
	// agent socket, which signs the vault's commits.
	git func(arguments ...string) (string, error)

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

func newEnvironment(out io.Writer) (*environment, error) {
	current, err := user.Current()
	if err != nil {
		return nil, err
	}
	for _, name := range accountsThatMayNotRun {
		if current.Username == name {
			return nil, fmt.Errorf("this command runs only in the person's own account, never as %s. The person runs it in their own desk terminal, where its prompts keep every key away from the coding agent", name)
		}
	}
	directory, err := os.Getwd()
	if err != nil {
		return nil, err
	}
	e := &environment{
		directory:                   directory,
		home:                        current.HomeDir,
		person:                      current.Username,
		out:                         out,
		vault:                       mmxVault{directory: directory},
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
		git:                         gitInRepository(directory),
		rdapBootstrapURL:            "https://data.iana.org/rdap/dns.json",
		githubAPIURL:                "https://api.github.com",
		containerRegistryURL:        "https://ghcr.io",
		stripeAPIURL:                "https://api.stripe.com",
		readRootFile:                readRootFileWithSudo,
		setUpThePhoneCode:           setUpThePhoneCodeWithSudo,
		resultsFile:                 setupResultsFile,
		writeResultsFile:            writeResultsFileWithSudo,
	}
	e.handleInterrupts()
	return e, nil
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

// quietly runs work without its step-by-step lines, which go-live's screens
// leave out: the person reads only what to do, and errors still stop the run.
func (e *environment) quietly(work func() error) error {
	out := e.out
	e.out = io.Discard
	defer func() { e.out = out }()
	return work()
}

// useTheSystemsRepository finds the person's systems repository when the
// command runs outside it, as ssh desk01-setup runs go-live in the home
// directory: the one directory in the home that holds mmx_project_settings.yml,
// where the desk's bootstrap copied the repository.
func (e *environment) useTheSystemsRepository() error {
	if _, err := os.Stat(filepath.Join(e.directory, projectSettingsFile)); err == nil {
		return nil
	}
	found, _ := filepath.Glob(filepath.Join(e.home, "*", projectSettingsFile))
	if len(found) != 1 {
		return fmt.Errorf("this command runs in your systems repository, and your home holds %d directories with %s. Run it from your systems repository", len(found), projectSettingsFile)
	}
	e.directory = filepath.Dir(found[0])
	e.vault = mmxVault{directory: e.directory}
	e.git = gitInRepository(e.directory)
	return nil
}

const sayTellTheCodingAgent = "Tell your coding agent this command finished. It checks the result with mmx secrets usage, which lists names only."

// handleInterrupts lets Ctrl-C stop the command at once, except between a
// provider issuing a key and the vault saving it. There the command first
// finishes saving, or revokes the new key, so nothing is left half done.
func (e *environment) handleInterrupts() {
	// The terminal, also while go-live's quiet work swaps e.out.
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
