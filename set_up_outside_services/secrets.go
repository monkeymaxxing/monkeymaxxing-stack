package main

import (
	"bytes"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"math/big"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

// The secrets step walks every vault key that a person must type, because
// only an outside company's website gives its value, and makes every
// missing key that nobody needs to see. Then it commits and pushes the
// vault itself, signed through the person's own agent socket. The person
// runs it in their own desk terminal: the values pass only through the
// hidden prompts and MMX's standard input, never through the coding agent.

// secretKind says where a vault key's value comes from.
type secretKind int

const (
	// typedSecret: the person makes it on a website and pastes it.
	typedSecret secretKind = iota
	// appSecret: one of an app's secrets_from_vault. It is random, such as
	// SECRET_KEY_BASE, or comes from an outside service, such as a Stripe
	// key; only the person knows which, so the step asks.
	appSecret
	// randomSecret: nobody needs to see it. hexLength > 0 makes it as that
	// many hexadecimal characters, for a reader that needs hex.
	randomSecret
	// consolePasswordSecret: the servers' shared root console password. The
	// step makes it, shows it once for the password manager, and saves only
	// its hash.
	consolePasswordSecret
)

type secretPlan struct {
	Key       string
	Kind      secretKind
	What      string // shown to the person, such as "the Pushover application's token"
	Why       string
	Where     string // where the person makes it: a page link and the clicks
	Length    int    // randomSecret: mmx secrets add-random --length
	HexLength int
}

const triageCredentialKey = "mmhotline_triage_agent_credential"

// triageSubscriptionTokenWhere is where the person makes the subscription
// token. The token is billed to that person's Claude plan, lasts one year,
// and stops working when that person's account is removed.
const triageSubscriptionTokenWhere = "your own terminal, on a computer where Claude Code is signed in to your Claude account: run claude setup-token and copy the token it prints. It is billed to your Claude plan, lasts one year, and stops working when your account is removed. MMHotline warns you before it expires."

const triageOpenAIAPIKeyWhere = "https://platform.openai.com/api-keys, Create new secret key."

const triageCodexAccessTokenWhere = "your ChatGPT Business or Enterprise workspace, on its Access tokens page: create a Codex access token and pick its end date, up to 90 days away. Choose the longest end date the workspace allows."

// triageChatGPTSignInLimit is MMHotline's limit on the auth.json text
// (triage_agent.credential for chatgpt_sign_in): 64 KiB. MMHotline refuses
// a longer value, so this step refuses it first.
const triageChatGPTSignInLimit = 64 * 1024

// triageChoice is what the person chose for the triage credential, which
// the closing message turns into settings for the coding agent.
type triageChoice struct {
	credentialType string
	expiresOn      string
}

// askTriageCodingAgent finds out which coding agent runs the triage agent:
// from triage_agent_coding_agent in mmx_project_settings.yml when it says,
// otherwise by asking.
func (e *environment) askTriageCodingAgent(settings systemSettings) (string, error) {
	if known := settings.Vars.TriageAgentCodingAgent; known == "claude_code" || known == "codex" {
		return known, nil
	}
	for {
		answer, err := e.confirm("  triage_agent_coding_agent in mmx_project_settings.yml does not say which coding agent the triage agent uses. Type claude_code or codex, or press Enter for claude_code: ")
		if err != nil {
			return "", err
		}
		switch strings.ToLower(strings.TrimSpace(answer)) {
		case "", "claude_code", "claude", "claude code":
			return "claude_code", nil
		case "codex":
			return "codex", nil
		}
		e.say("  Type claude_code or codex.")
	}
}

// triageWhere is where the person makes each kind of credential.
func triageWhere(codingAgent, credentialType, apiKeyWhere string) string {
	switch {
	case credentialType == "subscription_token":
		return triageSubscriptionTokenWhere
	case credentialType == "access_token":
		return triageCodexAccessTokenWhere
	case codingAgent == "codex":
		return triageOpenAIAPIKeyWhere
	}
	return apiKeyWhere
}

// askAccessTokenEndDate asks for the access token's end date, which is not
// a secret, and checks its form: YYYY-MM-DD, after today.
func (e *environment) askAccessTokenEndDate() (string, error) {
	for {
		answer, err := e.confirm("  The access token's end date, as ChatGPT showed it when you made the token, written YYYY-MM-DD, such as 2027-02-06: ")
		if err != nil {
			return "", err
		}
		answer = strings.TrimSpace(answer)
		date, parseErr := time.Parse("2006-01-02", answer)
		switch {
		case parseErr != nil:
			e.say("  Write the date as YYYY-MM-DD, such as 2027-02-06.")
		case !date.After(e.now()):
			e.say("  That date has passed. Make a new access token with a later end date, then type its end date.")
		default:
			return answer, nil
		}
	}
}

// readChatGPTSignIn asks for the path of the auth.json file and returns its
// content unchanged. It never prints the content.
func (e *environment) readChatGPTSignIn() (string, error) {
	e.say("  Make the sign-in on your own computer, in a new empty folder used only for MMHotline, with a ChatGPT account that has no connected apps, because the agent can reach that account's connected apps:")
	e.say("      export CODEX_HOME=\"$(mktemp -d)\"")
	e.say("      codex login")
	e.say("      echo \"$CODEX_HOME/auth.json\"")
	e.say("  Never use this copy anywhere else, and never run codex logout on it: that would end MMHotline's sign-in too. Your own Codex sign-in is separate and keeps working.")
	for {
		answer, err := e.confirm("  Type the path of that auth.json file (its content is not shown), or press Enter to leave it for later: ")
		if err != nil {
			return "", err
		}
		path := strings.TrimSpace(answer)
		if path == "" {
			return "", nil
		}
		if path == "~" || strings.HasPrefix(path, "~/") {
			path = filepath.Join(e.home, strings.TrimPrefix(path, "~"))
		}
		content, readErr := os.ReadFile(path)
		switch {
		case readErr != nil:
			e.say("  I could not read %s. Check the path.", path)
		case len(content) > triageChatGPTSignInLimit:
			e.say("  That file is longer than 64 KiB, which MMHotline refuses. Check that it is the auth.json file that codex login made.")
		case !json.Valid(content):
			e.say("  That file is not valid JSON. Check that it is the auth.json file that codex login made.")
		default:
			e.say("  Read the file. Now delete that folder (rm -rf \"$CODEX_HOME\" && unset CODEX_HOME), and do not run codex logout.")
			return string(content), nil
		}
	}
}

// askTriageCredentialType asks which kind of credential the person has for
// the coding agent, and returns the credential_type value for
// mmhotline_settings.yml. An API key is the default: it belongs to the
// company account, so it keeps working when a person leaves, and it has no
// renewal.
func (e *environment) askTriageCredentialType(codingAgent string) (string, error) {
	if codingAgent == "codex" {
		e.say("  Codex accepts three kinds of credential:")
		e.say("  - An OpenAI API key. Recommended. It belongs to your company's account at OpenAI, keeps working when a person leaves, never expires, and has its own usage limits, so the triage agent still runs at 3 a.m. after a busy day.")
		e.say("  - A Codex access token, from a ChatGPT Business or Enterprise workspace. You pick its end date, up to 90 days away. MMHotline reminds the administrators 30 and 7 days before that date. It shares the workspace's usage limits.")
		e.say("  - A ChatGPT sign-in, for any other ChatGPT plan: the auth.json file that signing in to Codex once makes. It shares the plan's usage limits, and it stops working if anything else uses the same sign-in.")
		for {
			answer, err := e.confirm("  Which one do you have? Type key, token, or sign-in, or press Enter for key: ")
			if err != nil {
				return "", err
			}
			switch strings.ToLower(strings.TrimSpace(answer)) {
			case "", "key", "api key", "api_key":
				return "api_key", nil
			case "token", "access token", "access_token":
				return "access_token", nil
			case "sign-in", "sign in", "signin", "chatgpt_sign_in", "chatgpt sign-in":
				return "chatgpt_sign_in", nil
			}
			e.say("  Type key, token, or sign-in.")
		}
	}
	e.say("  Claude Code accepts two kinds of credential:")
	e.say("  - An Anthropic API key. It belongs to your company's account at Anthropic, keeps working when a person leaves, and has no renewal. Recommended for a small team.")
	e.say("  - A person's Claude subscription token. It is billed to that person's plan, lasts one year, and stops working when that person leaves.")
	for {
		answer, err := e.confirm("  Which one do you have? Type key for an API key, or subscription for a subscription token, or press Enter for key: ")
		if err != nil {
			return "", err
		}
		switch strings.ToLower(strings.TrimSpace(answer)) {
		case "", "key", "api key", "api_key":
			return "api_key", nil
		case "subscription", "subscription token", "subscription_token":
			return "subscription_token", nil
		}
		e.say("  Type key or subscription.")
	}
}

// madeElsewhere names the command or chapter that makes each vault key this
// step leaves alone, so the summary can say where a missing one comes from.
func madeElsewhere(key string) string {
	switch {
	case strings.HasSuffix(key, "_cloudflare_tunnel_token"), strings.HasPrefix(key, "uploads_r2_"),
		strings.HasPrefix(key, "mmhotline_status_page_r2_"), key == "mmhotline_down_alarm_cloudflare_api_token",
		strings.Contains(key, "_R2_"):
		return "set-up-outside-services cloudflare"
	case strings.Contains(key, "_b2_"), strings.HasPrefix(key, "mmhotline_backup_"):
		return "set-up-outside-services backblaze"
	case key == "mmx_vault_passphrase":
		return "set-up-the-systems-repository, in chapter 2"
	case strings.HasPrefix(key, "database_moving_in_"):
		return "Move a database into the Stack, only while a database moves in"
	}
	return ""
}

// providerTokenPages are where each provider guide's provider makes an API
// token, by the guide's API address.
var providerTokenPages = map[string]string{
	"https://api.hetzner.cloud/v1/":    "https://console.hetzner.cloud/projects, then your project, Security, API tokens, Generate API token (Read & Write)",
	"https://api.digitalocean.com/v2/": "https://cloud.digitalocean.com/account/api/tokens, Generate New Token",
	"https://api.vultr.com/v2/":        "https://my.vultr.com/settings/#settingsapi, then Personal Access Tokens or a sub-account's API key",
	"https://api.scaleway.com/":        "https://console.scaleway.com/iam/api-keys, Generate an API key for the application util01-restore",
}

// secretsPlan lists the keys this step makes, from the settings: the typed
// keys first, then the apps' keys, then the random keys.
func secretsPlan(s systemSettings) []secretPlan {
	providerPage := providerTokenPages[s.Vars.SystemsDeskProviderAPIURL]
	util01What := "util01's own server provider token"
	util01Where := ". Give it the permissions your provider guide names for util01's restore token, and name it util01 restore drill."
	if method, signs := requestSigningMethods[s.Vars.SystemsDeskProviderAPIAuthentication]; signs {
		// The link fills in util01's access rules; the guide gives the name.
		providerPage = method.util01TokenPage
		util01What = "util01's own server provider credential"
		util01Where = ". Name it as your provider guide says for util01's credential."
	}
	if providerPage == "" {
		providerPage = "your server provider's API token page, as your provider guide gives it"
	}
	plan := []secretPlan{
		{Key: "util01_provider_api_token", Kind: typedSecret, What: util01What,
			Why:   "util01 creates and deletes the weekly restore drill's server with it. It belongs to the account, not to you, so the drill keeps working when someone leaves.",
			Where: providerPage + util01Where},
		{Key: "pushover_application_token", Kind: typedSecret, What: "the Pushover application's API token",
			Why:   "MMHotline and MMWatchdog send every alert to your phones with it.",
			Where: "https://pushover.net/apps, then your application: copy its API Token/Key."},
		{Key: "mmwatchdog_pushover_user_or_group_key", Kind: typedSecret, What: "the Pushover delivery group's key",
			Why:   "The hub-outage alerters alert everyone in the group if util01 goes silent.",
			Where: "https://pushover.net/groups, then your group: copy its group key."},
		{Key: "mmhotline_triage_agent_credential", Kind: typedSecret, What: "the triage agent's key",
			Why:   "The triage agent investigates each alert with it, at any hour. Its work is billed to this key's account.",
			Where: "https://console.anthropic.com/settings/keys, Create Key."},
		{Key: "container_registry_read_only_token", Kind: typedSecret, What: "the registry's read-only token",
			Why:   "Your servers download your app's images with it. It can only read, so a broken-into server cannot replace an image.",
			Where: "https://github.com/settings/tokens/new?scopes=read:packages&description=" + s.ProjectName + "+servers+read+images, a classic token with read:packages only. Your coding agent sets container_registry_read_only_username, which is not a secret, to the account that owns it."},
	}
	plan = append(plan, secretPlan{Key: "shared_root_console_password_hash", Kind: consolePasswordSecret, What: "the servers' shared root console password",
		Why: "Every server lets root log in with it at your server provider's web console, the way in when SSH and the private network fail. SSH never accepts it. The vault keeps only its hash."})
	var apps []string
	for name := range s.Vars.Apps {
		apps = append(apps, name)
	}
	sort.Strings(apps)
	environments := []string{""}
	if s.hasStagingServer {
		environments = append(environments, "staging_")
	}
	for _, environment := range environments {
		for _, name := range apps {
			app := s.Vars.Apps[name]
			for _, variable := range app.SecretsFromVault {
				if variable == app.ProductionUploadsR2KeyVariables.AccessKeyID || variable == app.ProductionUploadsR2KeyVariables.SecretAccessKey {
					continue
				}
				what := name + "'s " + variable
				if environment != "" {
					what = name + "'s " + variable + " on staging01"
				}
				plan = append(plan, secretPlan{Key: environment + name + "_" + variable, Kind: appSecret, What: what, Length: 64})
			}
		}
	}
	random := []secretPlan{
		{Key: "pg_auto_failover_autoctl_node_password", What: "the failover monitor's login"},
		{Key: "pg_auto_failover_replication_password", What: "the database replicas' login"},
		{Key: "pgbackrest_repository_cipher_passphrase", What: "production's backup passphrase",
			Why: "pgBackRest encrypts every backup with it. go-live keeps a copy in the recovery bundle."},
		{Key: "mmhotline_signing_secret_of_the_fleet_hub", What: "the fleet hub's signing secret",
			Why: "The fleet hub signs MMWatchdog's alerts with it, so MMHotline takes alerts only from your servers.", HexLength: 64},
	}
	for _, environment := range environments {
		for _, name := range apps {
			random = append(random, secretPlan{Key: environment + name + "_database_password", What: name + "'s database password"})
		}
	}
	for _, item := range random {
		item.Kind = randomSecret
		if item.Length == 0 {
			item.Length = 32
		}
		plan = append(plan, item)
	}
	return plan
}

func runSecrets(e *environment, arguments []string) error {
	flags := flag.NewFlagSet("secrets", flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	replace := flags.String("replace", "", "")
	if err := flags.Parse(arguments); err != nil || flags.NArg() > 0 {
		return fmt.Errorf("secrets takes only --replace KEY: %w", errUsage)
	}
	settings, err := readSystemSettings(e.directory)
	if err != nil {
		return err
	}
	plan := secretsPlan(settings)
	if *replace != "" {
		found := false
		for _, item := range plan {
			found = found || item.Key == *replace
		}
		if !found {
			if where := madeElsewhere(*replace); where != "" {
				return fmt.Errorf("%s is made by %s, not by this step", *replace, where)
			}
			return fmt.Errorf("%s is not a key this step makes. It makes: %s", *replace, planKeys(plan))
		}
	}
	saved, err := e.beginVaultChange()
	if err != nil {
		return err
	}
	missingList, err := e.vault.missing()
	if err != nil {
		return err
	}
	missing := map[string]bool{}
	for _, key := range missingList {
		missing[key] = true
	}
	e.say("Vault secrets: this step saves each secret your servers read that the vault still lacks.")
	e.say("You paste the ones that only a website gives, at hidden prompts. It makes the servers' console password and shows it")
	e.say("once, for your password manager. It makes the rest itself, with random values that nobody needs to see.")
	e.say("Then it commits and pushes the vault for you. Your coding agent never sees a value.")
	var made, later, kept []string
	var triageChoices []triageChoice
	for _, item := range plan {
		if err := e.stopIfInterrupted(); err != nil {
			return err
		}
		wanted := missing[item.Key] || item.Key == *replace
		if !wanted {
			if saved.names[item.Key] {
				kept = append(kept, item.Key)
			}
			continue
		}
		var value string
		switch item.Kind {
		case typedSecret:
			e.say("")
			e.say("%s, saved as %s.", capitalize(item.What), item.Key)
			e.say("  Why: %s", item.Why)
			var choice triageChoice
			isTriage := item.Key == triageCredentialKey
			if isTriage {
				codingAgent, askErr := e.askTriageCodingAgent(settings)
				if askErr != nil {
					return askErr
				}
				if choice.credentialType, askErr = e.askTriageCredentialType(codingAgent); askErr != nil {
					return askErr
				}
				item.Where = triageWhere(codingAgent, choice.credentialType, item.Where)
			}
			if isTriage && choice.credentialType == "chatgpt_sign_in" {
				content, readErr := e.readChatGPTSignIn()
				if readErr != nil {
					return readErr
				}
				if content == "" {
					e.say("  Left for later. Run this step again when you have it.")
					later = append(later, item.Key)
					continue
				}
				if err := saved.save(item.Key, content); err != nil {
					return err
				}
				e.say("  Saved it as %s.", item.Key)
				made = append(made, item.Key)
				triageChoices = append(triageChoices, choice)
				continue
			}
			e.say("  Make it at %s", item.Where)
			if method, signs := requestSigningMethods[settings.Vars.SystemsDeskProviderAPIAuthentication]; signs && item.Key == "util01_provider_api_token" {
				if method.pastesAKeyFile {
					e.say("  Paste the key file's whole text, or press Enter to leave it for later.")
				} else {
					e.say("  Paste each value at its own prompt, or press Enter at the first to leave it for later.")
				}
				value, err = e.promptSignedProviderToken(method, "  ")
				break
			}
			value, err = e.prompt("  Paste it here (hidden), or press Enter to leave it for later: ")
			if err == nil && isTriage && strings.TrimSpace(value) != "" {
				if choice.credentialType == "access_token" {
					if choice.expiresOn, err = e.askAccessTokenEndDate(); err != nil {
						return err
					}
				}
				triageChoices = append(triageChoices, choice)
			}
		case appSecret:
			e.say("")
			e.say("%s, saved as %s.", capitalize(item.What), item.Key)
			answer, askErr := e.confirm("  Type random if nobody needs to see it, such as a secret key base, or press Enter to paste the value an outside service gave, such as an API key: ")
			if askErr != nil {
				return askErr
			}
			if strings.EqualFold(strings.TrimSpace(answer), "random") {
				if err := saved.addRandom(item.Key, item.Length); err != nil {
					return err
				}
				e.say("  Made a random value and saved it as %s.", item.Key)
				made = append(made, item.Key)
				continue
			}
			value, err = e.prompt("  Paste it from the service's own page, such as its API keys page (hidden), or press Enter to leave it for later: ")
		case randomSecret:
			if err := saveRandom(saved, item.Key, item.Length, item.HexLength); err != nil {
				return err
			}
			e.say("")
			e.say("Made %s, a random value nobody needs to see, and saved it as %s.", item.What, item.Key)
			if item.Why != "" {
				e.say("  Why: %s", item.Why)
			}
			made = append(made, item.Key)
			continue
		case consolePasswordSecret:
			if err := e.saveConsolePassword(saved, item); err != nil {
				return err
			}
			made = append(made, item.Key)
			continue
		}
		if err != nil {
			return err
		}
		value = strings.TrimSpace(value)
		if value == "" {
			e.say("  Left for later. Run this step again when you have it.")
			later = append(later, item.Key)
			continue
		}
		if strings.ContainsAny(value, "\r\n") {
			return fmt.Errorf("the value for %s has more than one line. Paste the one value only, then run this step again", item.Key)
		}
		if err := saved.save(item.Key, value); err != nil {
			return err
		}
		e.say("  Saved it as %s.", item.Key)
		made = append(made, item.Key)
	}
	var elsewhere, unknown []string
	inPlan := map[string]bool{}
	for _, item := range plan {
		inPlan[item.Key] = true
	}
	for _, key := range missingList {
		if inPlan[key] {
			continue
		}
		if where := madeElsewhere(key); where != "" {
			elsewhere = append(elsewhere, key+" (by "+where+")")
		} else {
			unknown = append(unknown, key)
		}
	}
	if err := e.finishVaultChange(saved, "set-up-outside-services secrets"); err != nil {
		return err
	}
	e.say("Saved now: %s.", listOrNone(made))
	e.say("Left for later: %s.", listOrNone(later))
	e.say("Made by another command: %s.", listOrNone(elsewhere))
	if len(unknown) > 0 {
		e.say("Read by your playbooks, but not a key this step knows: %s. Ask your coding agent where each comes from.", strings.Join(unknown, ", "))
	}
	for _, choice := range triageChoices {
		if choice.expiresOn != "" {
			e.say("Tell your coding agent to set credential_type: %s and credential_expires_on: \"%s\" under triage_agent in mmhotline_settings.yml. Neither setting is a secret, so your coding agent writes them.", choice.credentialType, choice.expiresOn)
			continue
		}
		e.say("Tell your coding agent to set credential_type: %s under triage_agent in mmhotline_settings.yml. That setting is not a secret, so your coding agent writes it.", choice.credentialType)
	}
	e.say(sayTellTheCodingAgent)
	return nil
}

func planKeys(plan []secretPlan) string {
	var keys []string
	for _, item := range plan {
		keys = append(keys, item.Key)
	}
	return strings.Join(keys, ", ")
}

// saveRandom makes a random value that nobody sees: MMX's add-random, or,
// for a reader that needs hexadecimal characters, a value made here and
// handed to MMX on standard input.
func saveRandom(saved *savedKeys, key string, length, hexLength int) error {
	if hexLength == 0 {
		return saved.addRandom(key, length)
	}
	random := make([]byte, hexLength/2)
	if _, err := rand.Read(random); err != nil {
		return err
	}
	return saved.save(key, hex.EncodeToString(random))
}

// consolePasswordItem is the password manager item that keeps the servers'
// shared root console password, when the secrets step makes it. go-live
// keeps it in the recovery bundle instead.
const consolePasswordItem = "Shared root console password"

// consolePasswordLetters are lowercase letters that sit in the same place on
// the common keyboard layouts (QWERTY, QWERTZ, AZERTY): a provider's web
// console often cannot paste and may assume another layout than the
// person's. 30 of them carry about 129 bits.
const consolePasswordLetters = "bcdefghijklnoprstuvx"

// newConsolePassword makes six groups of five such letters, joined by
// hyphens, such as "kbdte-ronvx-...", so a person can read it off a screen
// and type it at a console.
func newConsolePassword() (string, error) {
	var groups []string
	for range 6 {
		group := make([]byte, 5)
		for i := range group {
			n, err := rand.Int(rand.Reader, big.NewInt(int64(len(consolePasswordLetters))))
			if err != nil {
				return "", err
			}
			group[i] = consolePasswordLetters[n.Int64()]
		}
		groups = append(groups, string(group))
	}
	return strings.Join(groups, "-"), nil
}

// saveConsolePassword makes the servers' shared root console password,
// shows it once for the team's password manager, has the person type it
// back from there, and saves only its hash. Every way out clears the
// screen.
func (e *environment) saveConsolePassword(saved *savedKeys, item secretPlan) error {
	password, err := newConsolePassword()
	if err != nil {
		return err
	}
	e.say("")
	e.say("%s, saved as its hash in %s.", capitalize(item.What), item.Key)
	e.say("  Why: %s", item.Why)
	for {
		e.say("  Save it in your team's password manager as a new item named %q. It shows here once:", consolePasswordItem)
		e.setValueOnScreen(true)
		e.say("  ----")
		e.say("  %s", password)
		e.say("  ----")
		_, err := e.confirm("  Press Enter once it is saved. The screen is cleared then: ")
		e.clearValueFromScreen()
		if err != nil {
			return err
		}
		typed, err := e.prompt(fmt.Sprintf("  Type the password from the item %q (hidden), to check the saved copy: ", consolePasswordItem))
		if err != nil {
			return err
		}
		if strings.TrimSpace(typed) == password {
			break
		}
		e.say("  That is not the password shown. It shows again; check the item in the password manager.")
	}
	hash, err := consolePasswordHash(password)
	if err != nil {
		return err
	}
	if err := saved.save(item.Key, hash); err != nil {
		return err
	}
	e.say("  The password manager's copy matches. Saved only its hash as %s; the servers get it at their next MMX run.", item.Key)
	return nil
}

// consolePasswordHash makes the SHA-512 crypt hash that MMX's user module
// writes to /etc/shadow (password_hash), with a random salt. Debian's
// openssl makes it: Go's standard library has no crypt, and the desk has
// openssl already. The password goes on standard input, never in arguments.
func consolePasswordHash(password string) (string, error) {
	command := exec.Command("openssl", "passwd", "-6", "-stdin")
	command.Stdin = strings.NewReader(password + "\n")
	var output, errorOutput bytes.Buffer
	command.Stdout, command.Stderr = &output, &errorOutput
	if err := command.Run(); err != nil {
		return "", fmt.Errorf("openssl passwd -6 failed: %s", firstLine(errorOutput.String(), err))
	}
	hash := strings.TrimSpace(output.String())
	if !strings.HasPrefix(hash, "$6$") || strings.ContainsAny(hash, " \n") {
		return "", errors.New("openssl passwd -6 printed something that is not a SHA-512 crypt hash")
	}
	return hash, nil
}

// missing lists the keys the playbooks read that the vault lacks, as
// `mmx secrets usage --json` reports them. MMX exits 1 when a key is
// missing, which is the case this reads, so its JSON decides.
func (v mmxVault) missing() ([]string, error) {
	command := exec.Command("mmx", "secrets", "usage", "--json")
	command.Dir = v.directory
	var output, errorOutput bytes.Buffer
	command.Stdout, command.Stderr = &output, &errorOutput
	runErr := command.Run()
	var usage struct {
		Missing []string `json:"referenced_but_not_defined"`
	}
	if err := json.Unmarshal(output.Bytes(), &usage); err != nil {
		if runErr != nil {
			return nil, fmt.Errorf("mmx secrets usage failed: %s", firstLine(errorOutput.String(), runErr))
		}
		return nil, fmt.Errorf("mmx secrets usage printed something this command cannot read: %v", err)
	}
	return usage.Missing, nil
}

func (v mmxVault) addRandom(key string, length int, replace bool) error {
	arguments := []string{"secrets", "add-random", key, "--length", fmt.Sprint(length)}
	if replace {
		arguments = append(arguments, "--replace")
	}
	command := exec.Command("mmx", v.arguments(arguments...)...)
	command.Dir = v.directory
	var errorOutput bytes.Buffer
	command.Stdout, command.Stderr = &errorOutput, &errorOutput
	if err := command.Run(); err != nil {
		return fmt.Errorf("mmx secrets add-random %s failed: %s", key, firstLine(errorOutput.String(), err))
	}
	return nil
}
