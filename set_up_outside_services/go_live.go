package main

import (
	"bytes"
	"crypto/rand"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math/big"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

// go-live is sitting 1's whole part on the desk. The person runs it with
// ssh desk01-setup, whose SSH entry runs it as the person. It walks the
// outside accounts one screen at a time (Cloudflare, the domain's registrar,
// Backblaze, the registry's token, the apps' keys from outside services),
// makes every other vault secret without a question, and ends with the lock: the recovery passphrase and the phone
// code. Each value is checked with its service at once; a refused value is
// asked again with the service's reason. The results file tells the coding
// agent which steps are done, so the person relays nothing. A rerun skips
// the steps that are done. docs/design.md, "Account and secret setup from
// the systems desk", records the design.

const goLiveCommand = "set-up-outside-services go-live"

// setupResultsFile is the results file the coding agent reads. It holds step
// names, their states, and values that are not secrets, never a secret.
const setupResultsFile = "/var/lib/monkeymaxxing-stack/setup_results.json"

// The states of a step in the results file.
const (
	stepNotStarted = "not_started"
	stepInProgress = "in_progress"
	stepDone       = "done"
	// stepNotNeeded: the step has nothing to do on this system, such as the
	// registrar's screen for a domain that points at Cloudflare already.
	stepNotNeeded = "not_needed"
)

type stepResult struct {
	Name  string `json:"name"`
	State string `json:"state"`
}

// setupResults is the results file's content.
type setupResults struct {
	Command   string       `json:"command"`
	Version   string       `json:"version"`
	UpdatedAt string       `json:"updated_at"`
	Steps     []stepResult `json:"steps"`
	Finished  bool         `json:"finished"`
	// StoppedWith is the reason the last run stopped. Error messages hold no
	// secret: a provider's refusal keeps only its code and message.
	StoppedWith string `json:"stopped_with,omitempty"`
	// ForTheCodingAgent holds values that are not secrets: settings the
	// coding agent writes, such as cloudflare_account_id, and facts it
	// checks, such as the domain's nameservers.
	ForTheCodingAgent map[string]string `json:"for_the_coding_agent"`
}

type goLiveStep struct {
	name string
	run  func() (string, error)
}

// goLive is one run of go-live.
type goLive struct {
	e        *environment
	settings systemSettings
	domain   string
	oldKeys  string
	saved    *savedKeys
	// bundle is the recovery bundle, an MMX vault of its own.
	bundle             *savedKeys
	passphrase         string
	providerCredential string
	results            setupResults
	// zone is the domain at Cloudflare, once this run read it.
	zone *cloudflareZone
	// tokenStep is the number of the Cloudflare screen's step that makes the
	// token, which a refusal names.
	tokenStep int
	// b2 is the Backblaze sign-in of this run, which the bundle's copy
	// needs at the end. The master key is never saved anywhere.
	b2 *b2Client
}

func (g *goLive) steps() []goLiveStep {
	return []goLiveStep{
		{"cloudflare", g.cloudflare},
		{"registrar", g.registrar},
		{"backblaze", g.backblaze},
		{"container_registry_token", g.containerRegistryToken},
		{"app_keys_from_outside_services", g.appKeysFromOutsideServices},
		{"random_vault_secrets", g.randomVaultSecrets},
		{"recovery_passphrase", g.recoveryPassphrase},
		{"phone_code", g.phoneCode},
		{"recovery_bundle", g.recoveryBundle},
	}
}

func runGoLive(e *environment) error {
	g := &goLive{e: e}
	if err := g.prepare(); err != nil {
		return err
	}
	if g.results.Finished {
		e.show("Everything here is done already.\n\nGo back to your coding agent.")
		return nil
	}
	for _, step := range g.steps() {
		if state := g.state(step.name); state == stepDone || state == stepNotNeeded {
			continue
		}
		if err := g.setState(step.name, stepInProgress); err != nil {
			return err
		}
		state, err := step.run()
		if err == nil {
			err = g.setState(step.name, state)
		}
		if err != nil {
			g.results.StoppedWith = trimPeriod(err.Error())
			_ = g.writeResults()
			return fmt.Errorf("%v.\n\nGo back to your coding agent. It sees where this stopped", trimPeriod(err.Error()))
		}
	}
	g.results.Finished = true
	g.results.StoppedWith = ""
	if err := g.writeResults(); err != nil {
		return err
	}
	e.show("\nDone.  Your desk is locked.\n\nGo back to your coding agent.")
	return nil
}

// prepare checks everything the screens need before the first one, so the
// person never does a screen's steps for a run that then stops on a setting.
func (g *goLive) prepare() error {
	e := g.e
	settings, err := readSystemSettings(e.readRepositoryFile)
	if err != nil {
		return err
	}
	g.settings = settings
	if g.domain, err = settings.domain(); err != nil {
		return err
	}
	if _, err := backblazePlan(settings); err != nil {
		return err
	}
	if err := settings.checkAppSecrets(); err != nil {
		return err
	}
	// The plan's checks do not depend on the account, which Cloudflare names
	// only once the person pasted the token.
	if _, err := cloudflareAccountTokenPlan(settings, exampleCloudflareAccountID); err != nil {
		return err
	}
	g.oldKeys = e.oldKeysFilePath(settings)
	g.results = g.readResults()
	if g.results.Finished {
		return nil
	}
	// A new run has not stopped yet; the coding agent waits for finished or
	// stopped_with, so an earlier run's reason must not end its wait.
	g.results.StoppedWith = ""
	if g.providerCredential, err = g.readProviderCredential(); err != nil {
		return err
	}
	err = e.quietly(func() error {
		g.saved, err = e.beginVaultChange()
		return err
	})
	if err != nil {
		return err
	}
	return g.openTheBundle()
}

// readProviderCredential reads the server provider's credential from the
// desk's API proxy, where the desk's bootstrap put it. util01 uses the same
// credential, and the recovery bundle keeps it.
func (g *goLive) readProviderCredential() (string, error) {
	authentication := g.settings.Vars.SystemsDeskProviderAPIAuthentication
	path := proxyAPIs["server-provider"].file
	if _, signs := requestSigningMethods[authentication]; signs {
		path = signingCredentialFile
	}
	content, err := g.e.readRootFile(path)
	if err != nil {
		return "", fmt.Errorf("this desk has no server provider key in its API proxy yet (%v). The desk's bootstrap puts it there; ask your coding agent", err)
	}
	if path == signingCredentialFile {
		var credential signingCredential
		if json.Unmarshal(content, &credential) != nil || credential.Token == "" {
			return "", fmt.Errorf("%s is not the API proxy's credential file", path)
		}
		return credential.Token, nil
	}
	// The proxy's one line: proxy_set_header HEADER "TOKEN";
	_, quoted, found := strings.Cut(strings.TrimSpace(string(content)), `"`)
	token, _, closed := strings.Cut(quoted, `"`)
	token = strings.TrimPrefix(token, "Bearer ")
	if !found || !closed || checkTokenValue("token", token) != nil {
		return "", fmt.Errorf("%s does not hold the API proxy's token line", path)
	}
	return token, nil
}

func (g *goLive) state(name string) string {
	for _, step := range g.results.Steps {
		if step.Name == name {
			return step.State
		}
	}
	return stepNotStarted
}

func (g *goLive) setState(name, state string) error {
	found := false
	for i := range g.results.Steps {
		if g.results.Steps[i].Name == name {
			g.results.Steps[i].State, found = state, true
		}
	}
	if !found {
		g.results.Steps = append(g.results.Steps, stepResult{Name: name, State: state})
	}
	return g.writeResults()
}

func (g *goLive) note(name, value string) {
	g.results.ForTheCodingAgent[name] = value
}

// readResults reads an earlier run's results, so a rerun skips what is done.
// A missing or unreadable file starts every step anew.
func (g *goLive) readResults() setupResults {
	var results setupResults
	if text, err := os.ReadFile(g.e.resultsFile); err == nil {
		_ = json.Unmarshal(text, &results)
	}
	if results.ForTheCodingAgent == nil {
		results.ForTheCodingAgent = map[string]string{}
	}
	// Every step is listed, in the screens' order, so the coding agent sees
	// the whole walk from the first write.
	var steps []stepResult
	for _, step := range g.steps() {
		steps = append(steps, stepResult{Name: step.name, State: stepNotStarted})
	}
	for i := range steps {
		for _, earlier := range results.Steps {
			if earlier.Name == steps[i].Name {
				steps[i].State = earlier.State
			}
		}
	}
	results.Steps = steps
	return results
}

func (g *goLive) writeResults() error {
	g.results.Command, g.results.Version = goLiveCommand, version
	g.results.UpdatedAt = g.e.now().UTC().Format(time.RFC3339)
	content, err := json.MarshalIndent(g.results, "", "  ")
	if err != nil {
		return err
	}
	if err := g.e.writeResultsFile(append(content, '\n')); err != nil {
		return fmt.Errorf("writing the results file %s failed: %v", g.e.resultsFile, err)
	}
	return nil
}

// writeResultsFileWithSudo writes the results file as root, readable by
// everyone (0644), so the coding agent reads it and cannot change it.
func writeResultsFileWithSudo(content []byte) error {
	script := `set -e; umask 022; mkdir -p "${1%/*}"; cat > "$1.new"; chmod 0644 "$1.new"; mv "$1.new" "$1"`
	command := exec.Command("sudo", "-n", "sh", "-c", script, "sh", setupResultsFile)
	command.Stdin = bytes.NewReader(content)
	if output, err := command.CombinedOutput(); err != nil {
		return errors.New(firstLine(string(output), err))
	}
	return nil
}

// readRootFileWithSudo reads a file only root reads, such as the API proxy's
// token file. The content never shows on the screen.
func readRootFileWithSudo(path string) ([]byte, error) {
	command := exec.Command("sudo", "-n", "cat", "--", path)
	var output, errorOutput bytes.Buffer
	command.Stdout, command.Stderr = &output, &errorOutput
	if err := command.Run(); err != nil {
		return nil, errors.New(firstLine(errorOutput.String(), err))
	}
	return output.Bytes(), nil
}

// setUpThePhoneCodeWithSudo runs the desk's own phone-code setup in the
// person's terminal: it shows the QR code, asks for one code, and writes the
// emergency codes to emergencyCodesPath.
func setUpThePhoneCodeWithSudo(emergencyCodesPath string) error {
	command := exec.Command("sudo", "-n", "/usr/local/bin/set-up-the-phone-code", "--emergency-codes-to", emergencyCodesPath)
	command.Stdin, command.Stdout, command.Stderr = os.Stdin, os.Stdout, os.Stderr
	if err := command.Run(); err != nil {
		return fmt.Errorf("set-up-the-phone-code stopped (%v), so the desk is not locked yet", err)
	}
	return nil
}

// The words the person reads on each screen.

func (g *goLive) passwordManager() string {
	if name := g.settings.Vars.PasswordManager; name != "" {
		return name
	}
	return "your password manager"
}

// companyName is the project's name as a person says it: Example for
// example_systems.
func (g *goLive) companyName() string {
	return capitalize(strings.ReplaceAll(strings.TrimSuffix(g.settings.ProjectName, "_systems"), "_", " "))
}

// askHidden asks at a hidden prompt until the person types something.
func (g *goLive) askHidden(label string) (string, error) {
	for {
		value, err := g.e.prompt(label)
		if !errors.Is(err, errEmptyValue) {
			return strings.TrimSpace(value), err
		}
	}
}

// askVisible asks at a visible prompt until the person types something.
func (g *goLive) askVisible(label string) (string, error) {
	for {
		value, err := g.e.confirm(label)
		if err != nil || strings.TrimSpace(value) != "" {
			return strings.TrimSpace(value), err
		}
	}
}

// refused tells the person why a service refused a value, in plain words,
// and what to do before the prompt asks again.
func (g *goLive) refused(service, item string, err error, advice string) {
	g.e.say("")
	var refusal *apiError
	if errors.As(err, &refusal) && refusal.Message != "" {
		g.e.say("%s did not accept the %s.  It said: %s.", service, item, trimPeriod(refusal.Message))
	} else if errors.As(err, &refusal) {
		g.e.say("%s did not accept the %s.", service, item)
	} else {
		g.e.say("%s", capitalize(trimPeriod(err.Error()))+".")
	}
	g.e.say("%s", advice)
	g.e.say(stillWaitingHere)
	g.e.say("")
}

// stillWaitingHere follows each refusal: a hidden prompt shows nothing
// while the person types, so without it the screen looks finished.
const stillWaitingHere = "The setup is still running.  It waits for you at the line below."

// Account 2 of 4: Cloudflare.

// r2OverviewLink opens the account's R2 page, where Cloudflare's checkout
// turns R2 on.
const r2OverviewLink = "https://dash.cloudflare.com/?to=/:account/r2/overview"

// r2CostLines states R2's price for a person who approves it, from
// Cloudflare's R2 pricing page (https://developers.cloudflare.com/r2/pricing/,
// read 2026-11-17, Standard storage): free up to 10 GB-month, 1 million
// Class A and 10 million Class B requests a month; then $0.015 per
// GB-month, $4.50 per million Class A (writes) and $0.36 per million Class B
// (reads); no egress fee. Check it again when Cloudflare changes its prices.
const r2CostLines = `     It costs nothing up to 10 GB of files a month.
     Above that:  $0.015 for each GB a month,
                  $4.50 for each million file writes after the first million,
                  $0.36 for each million file reads after the first 10 million.
     Downloads to your users cost nothing.`

func (g *goLive) cloudflare() (string, error) {
	e := g.e
	steps := []string{
		"Open  https://dash.cloudflare.com/sign-up  and make an account.",
		"Save the login in " + g.passwordManager() + ".",
		"Turn on two-step sign-in, which Cloudflare calls  Two-Factor Authentication:\n       https://dash.cloudflare.com/profile/authentication",
	}
	needsR2 := len(g.settings.appsWithUploads()) > 0
	if needsR2 {
		steps = append(steps, "Turn on R2, where your app keeps its uploaded files:\n       "+r2OverviewLink+
			"\n     Finish the checkout there.  It asks for a card.\n"+r2CostLines)
	}
	g.tokenStep = len(steps) + 1
	steps = append(steps, "Open this link.  It fills in the key for you:\n       "+tokenMakingLink(g.settings, e.person)+
		"\n     The page is long.  Scroll to the bottom, below the list of permissions."+
		"\n     Press  Review token,  then  Create token.")
	var screen strings.Builder
	screen.WriteString("\nAccount 2 of 4: Cloudflare (your web address and protection)\n\nWhat this is for:\n" +
		"  Cloudflare puts your site on the internet and keeps your private pages private.\n\nDo this now:\n")
	for i, step := range steps {
		fmt.Fprintf(&screen, "  %d. %s\n", i+1, step)
	}
	screen.WriteString("\nThen paste the token here.\n\n")
	e.show(screen.String())
	var link *cloudflareClient
	for link == nil {
		value, err := g.askHidden("  Cloudflare token (hidden): ")
		if err != nil {
			return "", err
		}
		var advice string
		link, advice, err = g.checkTheLinkToken(value)
		if err != nil && advice == "" {
			return "", err
		}
		if err != nil {
			g.refused("Cloudflare", "token", err, advice)
		}
	}
	e.say("Cloudflare accepted the token.")
	g.note("cloudflare_account_id", link.accountID)
	defer e.quietly(func() error { e.deleteTheLinkToken(link); return nil })
	err := e.quietly(func() error {
		zone, err := e.addTheDomain(link, g.settings, g.domain)
		g.zone = &zone
		return err
	})
	if err != nil {
		return "", err
	}
	plan, err := cloudflareAccountTokenPlan(g.settings, link.accountID)
	if err != nil {
		return "", err
	}
	for {
		var done cloudflareSetUp
		err := e.quietly(func() error {
			var err error
			done, err = e.setUpCloudflare(link, g.settings, link.accountID, plan, g.saved, g.oldKeys)
			return err
		})
		if err != nil {
			return "", err
		}
		if !done.r2IsOff {
			break
		}
		// The upload buckets and their keys need R2, so the run waits for it.
		e.show(fmt.Sprintf("\nR2 is not on yet, and your app needs it for its uploaded files.\nFinish the checkout from step %d:\n  %s\n\n", g.tokenStep-1, r2OverviewLink))
		if _, err := e.confirm("Press Enter when the page shows R2's overview.  "); err != nil {
			return "", err
		}
	}
	g.note("cloudflare_nameservers", strings.Join(g.zone.NameServers, " "))
	return stepDone, nil
}

// checkTheLinkToken finds the token's account and accepts the token there.
// advice is set when Cloudflare refused the token, so the person may paste
// another; other errors stop the run.
func (g *goLive) checkTheLinkToken(value string) (*cloudflareClient, string, error) {
	pasteAgain := fmt.Sprintf("Copy the whole token, then paste it again.\nIf Cloudflare no longer shows it, make a new one with the link in step %d.", g.tokenStep)
	if err := checkTokenValue("token", value); err != nil {
		return nil, pasteAgain, errors.New("that is not a whole Cloudflare token: it has a space or another character a token never has")
	}
	link := &cloudflareClient{baseURL: g.e.cloudflareAPIURL, token: value, who: "the link token"}
	accounts, err := link.accountIDs()
	var refusal *apiError
	if errors.As(err, &refusal) && refusal.Status != http.StatusForbidden {
		return nil, pasteAgain, err
	}
	if err != nil && !errors.As(err, &refusal) {
		return nil, "", err
	}
	if len(accounts) == 0 {
		// Cloudflare did not list the token's account, so the person copies
		// its ID from the dashboard.
		id, err := g.askForTheAccountID()
		if err != nil {
			return nil, "", err
		}
		accounts = []string{id}
	}
	for _, accountID := range accounts {
		link.accountID = accountID
		id, err := link.verifyAccountToken()
		if errors.As(err, &refusal) {
			continue
		}
		if err != nil {
			return nil, "", err
		}
		err = g.e.quietly(func() error { return g.e.acceptLinkToken(g.settings, link, id) })
		if errors.Is(err, errLinkTokenCannotMakeTokens) {
			return nil, fmt.Sprintf("Make the token with the link in step %d, and keep the settings the link fills in.", g.tokenStep), errors.New("this token cannot make keys")
		}
		return link, "", err
	}
	return nil, pasteAgain, errors.New("Cloudflare does not know this token")
}

// askForTheAccountID asks for the account's ID where Cloudflare's dashboard
// shows it: the R2 overview page's "Account Details", and the address bar of
// every dashboard page, as the 32 characters after dash.cloudflare.com/.
func (g *goLive) askForTheAccountID() (string, error) {
	g.e.show(`
Cloudflare did not tell me your account ID.  Copy it from Cloudflare's page:
  1. Open  ` + r2OverviewLink + `
  2. Under  Account Details,  press the copy button beside  Account ID.
     Or read it from the address bar of any page at  https://dash.cloudflare.com
     It is the 32 letters and digits right after  dash.cloudflare.com/
  3. Paste it here.

`)
	for {
		id, err := g.askVisible("  Account ID: ")
		if err != nil {
			return "", err
		}
		id = strings.ToLower(id)
		if cloudflareAccountIDPattern.MatchString(id) {
			return id, nil
		}
		g.e.say("")
		g.e.say("An account ID is 32 letters and digits.  Copy it again with step 2, then paste it.")
		g.e.say("")
	}
}

// Account 3 of 4: the domain's registrar.

func (g *goLive) registrar() (string, error) {
	e := g.e
	if g.zone == nil {
		// A rerun: read the domain with the desk's own token, which can read
		// every zone of the account.
		desk := &cloudflareClient{baseURL: e.cloudflareAPIURL, token: tokenFileValue(e.tokenFilePath(g.settings), deskTokenVariable),
			accountID: g.results.ForTheCodingAgent["cloudflare_account_id"], who: "your desk's Cloudflare token"}
		zone, err := desk.findZone(g.domain)
		if err != nil {
			return "", err
		}
		if zone == nil {
			return "", fmt.Errorf("Cloudflare has no domain %s in account %s", g.domain, desk.accountID)
		}
		g.zone = zone
	}
	if g.zone.Status == "active" {
		return stepNotNeeded, nil
	}
	registration := lookUpRegistration(e, g.domain)
	title := "your domain's registrar"
	where := "your domain's registrar, where you bought " + g.domain
	if registration.registrar != "" {
		title = "your domain's registrar (" + registration.registrar + ")"
		where = registration.registrar
	}
	var steps []string
	steps = append(steps, "Sign in at "+trimPeriod(where)+".")
	switch registration.dnssec {
	case dnssecOn:
		steps = append(steps, "Turn off DNSSEC for "+g.domain+".")
	case dnssecUnknown:
		steps = append(steps, "If DNSSEC is on for "+g.domain+", turn it off.")
	}
	steps = append(steps, "Open your domain's nameservers.  Choose custom nameservers.",
		"Put in these two, and remove the others:\n\n       "+strings.Join(g.zone.NameServers, "\n       ")+"\n",
		"Press save.")
	var screen strings.Builder
	fmt.Fprintf(&screen, "\nAccount 3 of 4: %s\n\nWhat this is for:\n  Your domain must point at Cloudflare.\n", title)
	if registration.dnssec == dnssecOn {
		screen.WriteString("\nTURN OFF DNSSEC FIRST.  YOUR SITE WILL NOT WORK WITH IT ON.\n")
	}
	screen.WriteString("\nDo this now:\n")
	for i, step := range steps {
		fmt.Fprintf(&screen, "  %d. %s\n", i+1, step)
	}
	screen.WriteString("\n")
	e.show(screen.String())
	if _, err := e.confirm("Press Enter here when you saved.  I check it from here."); err != nil {
		return "", err
	}
	if registration.registrar != "" {
		g.note("registrar", registration.registrar)
	}
	return stepDone, nil
}

// The domain's DNSSEC state, as its registry reports it.
const (
	dnssecUnknown = iota
	dnssecOff
	dnssecOn
)

type registration struct {
	registrar string
	dnssec    int
}

// lookUpRegistration reads the domain's registrar and DNSSEC state from its
// registry's RDAP service, the successor of whois, which IANA's bootstrap
// file names for each top-level domain. Either may stay unknown, such as for
// a top-level domain without RDAP; the screen then words its steps for any
// registrar.
// https://www.rfc-editor.org/rfc/rfc9224 (bootstrap), rfc9083 (answers)
func lookUpRegistration(e *environment, domain string) registration {
	found := registration{dnssec: dnssecUnknown}
	var bootstrap struct {
		Services [][][]string `json:"services"`
	}
	if _, err := doJSON("IANA", "the RDAP bootstrap file", http.MethodGet, e.rdapBootstrapURL, nil, nil, &bootstrap, readNoError); err != nil {
		return found
	}
	topLevel := domain[strings.LastIndex(domain, ".")+1:]
	server := ""
	for _, service := range bootstrap.Services {
		if len(service) == 2 && contains(service[0], topLevel) && len(service[1]) > 0 {
			server = service[1][0]
		}
	}
	if server == "" {
		return found
	}
	var answer struct {
		SecureDNS *struct {
			DelegationSigned bool `json:"delegationSigned"`
		} `json:"secureDNS"`
		Entities []struct {
			Roles      []string `json:"roles"`
			VCardArray []any    `json:"vcardArray"`
		} `json:"entities"`
	}
	if _, err := doJSON("The registry", "an RDAP lookup", http.MethodGet, strings.TrimSuffix(server, "/")+"/domain/"+url.PathEscape(domain), nil, nil, &answer, readNoError); err != nil {
		return found
	}
	if answer.SecureDNS != nil {
		found.dnssec = dnssecOff
		if answer.SecureDNS.DelegationSigned {
			found.dnssec = dnssecOn
		}
	}
	for _, entity := range answer.Entities {
		if contains(entity.Roles, "registrar") {
			found.registrar = vcardName(entity.VCardArray)
		}
	}
	return found
}

func readNoError([]byte) (string, string) { return "", "" }

// vcardName reads the fn (full name) of a jCard: ["vcard", [["fn", {}, "text", NAME], ...]].
// https://www.rfc-editor.org/rfc/rfc7095
func vcardName(card []any) string {
	if len(card) != 2 {
		return ""
	}
	properties, _ := card[1].([]any)
	for _, property := range properties {
		fields, _ := property.([]any)
		if len(fields) == 4 && fields[0] == "fn" {
			name, _ := fields[3].(string)
			// A name goes on the screen, so only printable text of a sane length.
			if len(name) <= 80 && !strings.ContainsFunc(name, func(r rune) bool { return r < ' ' || r == 0x7f }) {
				return strings.TrimSpace(name)
			}
		}
	}
	return ""
}

// Account 4 of 4: Backblaze.

// backblazeRegionName is the region's name on Backblaze's sign-up page, from
// the S3 endpoint in the settings: EU Central for s3.eu-central-003.backblazeb2.com.
func backblazeRegionName(endpoint string) string {
	region := strings.TrimSuffix(strings.TrimPrefix(endpoint, "s3."), ".backblazeb2.com")
	parts := strings.Split(region, "-")
	if len(parts) != 3 {
		return ""
	}
	return strings.ToUpper(parts[0]) + " " + capitalize(parts[1])
}

func (g *goLive) backblaze() (string, error) {
	e := g.e
	plan, err := backblazePlan(g.settings)
	if err != nil {
		return "", err
	}
	endpoint := g.settings.Vars.Backups.B2S3Endpoint
	region := " the region your coding agent named."
	if name := backblazeRegionName(endpoint); name != "" {
		region = "  " + name + "."
	}
	e.show(fmt.Sprintf(`
Account 4 of 4: Backblaze (your backups)

What this is for:
  Your database backups are stored at Backblaze, away from your servers.

Do this now:
  1. Open  https://www.backblaze.com/sign-up/cloud-storage
     Type your email and press  Get Started Free.  Then finish making the account.
  2. When Backblaze asks for a region, choose%s

  THE REGION CANNOT BE CHANGED LATER.

  3. Save the login in %s.
  4. Open  App Keys  and press  Generate New Master Application Key.

Then paste the two values here.

`, region, g.passwordManager()))
	if err := g.askForTheMasterKey(endpoint); err != nil {
		return "", err
	}
	err = e.quietly(func() error { return e.setUpBackblaze(g.b2, plan, g.saved, g.oldKeys) })
	if err != nil {
		return "", err
	}
	return stepDone, nil
}

// askForTheMasterKeyAgain is for a rerun whose Backblaze screen was done in
// an earlier run: the master key is never kept, so the recovery bundle's
// copy at Backblaze needs it once more.
func (g *goLive) askForTheMasterKeyAgain() error {
	g.e.show(fmt.Sprintf(`
Paste your Backblaze master key again.

What this is for:
  The setup needs it once more, to put a copy of your recovery bundle into your locked backup bucket.  It does not keep the key.

Do this now:
  1. Find the keyID and applicationKey, if you saved them in %s.
     If you did not, open  App Keys  at Backblaze and press  Generate New Master Application Key.
  2. Paste the two values here.

`, g.passwordManager()))
	return g.askForTheMasterKey(g.settings.Vars.Backups.B2S3Endpoint)
}

// askForTheMasterKey asks until Backblaze accepts a master key in an account
// the person keeps, and signs in with it.
func (g *goLive) askForTheMasterKey(endpoint string) error {
	e := g.e
	for g.b2 == nil {
		keyID, err := g.askVisible("  keyID: ")
		if err != nil {
			return err
		}
		applicationKey, err := g.askHidden("  applicationKey (hidden): ")
		if err != nil {
			return err
		}
		client, err := authorizeB2(e.b2AuthorizeURL, keyID, applicationKey)
		var refusal *apiError
		switch {
		case errors.As(err, &refusal):
			g.refused("Backblaze", "key", err, "Check that you copied both values whole, then paste them again.")
		case err != nil:
			return err
		case len(missingCapabilities(client.capabilities)) > 0:
			g.refused("Backblaze", "key", errors.New("this key is not the master key: it cannot make buckets and keys"),
				"Press  Generate New Master Application Key,  and paste its two values.")
		default:
			e.say("Backblaze accepted the key.")
			keep, err := g.keepTheAccountsRegion(client, endpoint)
			if err != nil {
				return err
			}
			if keep {
				g.b2 = client
			}
		}
	}
	return nil
}

// keepTheAccountsRegion asks the person, when the account's region differs
// from the planned one, whether to carry on with the account or make a new
// one in the planned region. The region cannot change, so carrying on makes
// the settings follow the account.
func (g *goLive) keepTheAccountsRegion(client *b2Client, endpoint string) (bool, error) {
	accountEndpoint := strings.TrimPrefix(client.s3APIURL, "https://")
	if client.hasS3Endpoint(endpoint) {
		return true, nil
	}
	if g.results.ForTheCodingAgent["b2_s3_endpoint"] == accountEndpoint {
		// The person chose this account in an earlier run.
		return true, nil
	}
	account, planned := backblazeRegionName(accountEndpoint), backblazeRegionName(endpoint)
	if account == "" {
		account = accountEndpoint
	}
	if planned == "" {
		planned = endpoint
	}
	g.e.show(fmt.Sprintf(`
Your Backblaze account is in  %s.  The plan was  %s,  near your servers.
An account's region cannot be changed.

Choose one:
  1. Carry on with  %s.  Your backups work the same, farther from your servers.
  2. Make a new Backblaze account in  %s.  It needs another email address.

`, account, planned, account, planned))
	for {
		answer, err := g.askVisible("  Type 1 or 2: ")
		if err != nil {
			return false, err
		}
		switch answer {
		case "1":
			g.note("b2_s3_endpoint", accountEndpoint)
			return true, nil
		case "2":
			g.e.show(fmt.Sprintf(`
Make the new account:
  1. Open  https://www.backblaze.com/sign-up/cloud-storage  and sign up with another email address.
  2. When Backblaze asks for a region, choose  %s.
  3. Save the login in %s.
  4. Open  App Keys  and press  Generate New Master Application Key.

Then paste the new account's two values here.

`, planned, g.passwordManager()))
			return false, nil
		}
	}
}

// The Git host's registry token.

func (g *goLive) containerRegistryToken() (string, error) {
	e := g.e
	const vaultKey = "container_registry_read_only_token"
	if g.saved.hasAll(vaultKey) {
		return stepDone, nil
	}
	image := g.firstAppImage()
	host, repository, _ := strings.Cut(image, "/")
	if host != "ghcr.io" || repository == "" {
		// This screen knows GitHub's token page only.
		g.note("container_registry_token", "the apps' images are not at ghcr.io: set-up-outside-services secrets asks for the registry's token")
		return stepNotNeeded, nil
	}
	link := "https://github.com/settings/tokens/new?scopes=read:packages&description=" + url.QueryEscape(strings.ToLower(strings.ReplaceAll(g.companyName(), " ", "-"))+"-servers")
	e.show(fmt.Sprintf(`
One more key: so your servers can download your app.

Do this now:
  1. Open this link.  It fills in the key for you:
       %s
     GitHub may first show  Confirm access  and ask for an authentication code or password.
     Enter it.  The link is not broken.
  2. Set  Expiration  to  No expiration.

  SET EXPIRATION TO "NO EXPIRATION".  OTHERWISE YOUR DEPLOYS STOP IN 30 DAYS.

  3. Press  Generate token.

Then paste the token here.

`, link))
	for {
		token, err := g.askHidden("  GitHub token (hidden): ")
		if err != nil {
			return "", err
		}
		check, advice, err := g.checkTheRegistryToken(token, repository)
		if err != nil && advice == "" {
			return "", err
		}
		if err != nil {
			g.refused("GitHub", "token", err, advice)
			continue
		}
		if !check.expiresAt.IsZero() {
			e.show(fmt.Sprintf(`
This token stops working on %s.

  After that, your servers cannot download your app.
  Deploys and new servers stop until you replace the token.
  Your coding agent reminds you in the weekly review.

  Type  yes  to use this token.
  Press Enter to paste a token with no end date instead.

`, check.expiresAt.Format("2006-01-02 15:04:05 UTC")))
			answer, err := e.confirm("  Use this token (yes): ")
			if err != nil {
				return "", err
			}
			if strings.ToLower(strings.TrimSpace(answer)) != "yes" {
				e.say("")
				e.say(stillWaitingHere)
				e.say("")
				continue
			}
			g.note("container_registry_read_only_token_expires_at", check.expiresAt.Format(time.RFC3339))
		}
		if err := g.saved.save(vaultKey, token); err != nil {
			return "", err
		}
		e.say("GitHub accepted the token.")
		g.note("container_registry_read_only_username", check.login)
		g.note("container_image_found", map[bool]string{true: "yes", false: "no, not built yet"}[check.imageFound])
		return stepDone, nil
	}
}

// firstAppImage is the first app's image, by app name, such as
// ghcr.io/example/shop. Every app's images come from one registry account.
func (g *goLive) firstAppImage() string {
	var names []string
	for name := range g.settings.Vars.Apps {
		names = append(names, name)
	}
	sort.Strings(names)
	if len(names) == 0 {
		return ""
	}
	image := g.settings.Vars.Apps[names[0]].Image
	image, _, _ = strings.Cut(image, ":")
	return image
}

type registryTokenCheck struct {
	login      string
	imageFound bool
	// expiresAt is when GitHub stops accepting the token; zero for a token
	// that never ends.
	expiresAt time.Time
}

// shortestRegistryTokenLife is the least time a token that ends may have
// left. A shorter token would stop the servers' deploys before the weekly
// review reminds the person to replace it.
const shortestRegistryTokenLife = 30 * 24 * time.Hour

// checkTheRegistryToken checks a GitHub token the way the servers use it:
// it never ends, it can only read packages, and it reads the app's image at
// ghcr.io. advice is set when the token is refused, so the person may paste
// another; other errors stop the run.
func (g *goLive) checkTheRegistryToken(token, repository string) (registryTokenCheck, string, error) {
	const fromTheLink = "Make a new token with the link in step 1"
	var check registryTokenCheck
	if checkTokenValue("token", token) != nil {
		return check, "Copy the whole token, then paste it again.", errors.New("that is not a whole GitHub token: it has a space or another character a token never has")
	}
	// https://docs.github.com/en/rest/users/users#get-the-authenticated-user
	request, err := http.NewRequest(http.MethodGet, g.e.githubAPIURL+"/user", nil)
	if err != nil {
		return check, "", err
	}
	request.Header.Set("Authorization", "Bearer "+token)
	request.Header.Set("Accept", "application/vnd.github+json")
	response, err := httpClient.Do(request)
	if err != nil {
		return check, "", &networkError{Provider: "GitHub", Call: "GET /user", Err: stripURLFromError(err)}
	}
	body, _ := io.ReadAll(io.LimitReader(response.Body, 1<<20))
	response.Body.Close()
	if response.StatusCode != http.StatusOK {
		var refusal struct {
			Message string `json:"message"`
		}
		_ = json.Unmarshal(body, &refusal)
		return check, "Copy the whole token, then paste it again.", &apiError{Provider: "GitHub", Call: "GET /user", Status: response.StatusCode, Message: refusal.Message}
	}
	var user struct {
		Login string `json:"login"`
	}
	if json.Unmarshal(body, &user) != nil || user.Login == "" {
		return check, "", errors.New("GitHub answered GET /user with something this command cannot read")
	}
	check.login = user.Login
	// GitHub names a classic token's end date and scopes in its headers.
	if ends := response.Header.Get("GitHub-Authentication-Token-Expiration"); ends != "" {
		// https://docs.github.com/en/rest/overview/resources-in-the-rest-api#authentication
		expiresAt, err := time.Parse("2006-01-02 15:04:05 MST", ends)
		if err != nil {
			return check, fromTheLink + ", with  Expiration  set to  No expiration.", fmt.Errorf("this token stops working on %s, and your deploys with it", ends)
		}
		if expiresAt.Sub(g.e.now()) < shortestRegistryTokenLife {
			return check, fromTheLink + ", with  Expiration  set to  No expiration.", fmt.Errorf("this token stops working on %s, less than 30 days from now, and your deploys with it", ends)
		}
		check.expiresAt = expiresAt.UTC()
	}
	scopes := map[string]bool{}
	for _, scope := range strings.Split(response.Header.Get("X-OAuth-Scopes"), ",") {
		if scope = strings.TrimSpace(scope); scope != "" {
			scopes[scope] = true
		}
	}
	if !scopes["read:packages"] {
		return check, fromTheLink + ".  It ticks  read:packages  for you.", errors.New("this token cannot download packages")
	}
	delete(scopes, "read:packages")
	if len(scopes) > 0 {
		return check, fromTheLink + ", with only  read:packages  ticked.", fmt.Errorf("this token can do more than download your app: it can also use %s.  Every server keeps it, so it may only read", strings.Join(sortedNames(scopes), ", "))
	}
	found, err := readImageTags(g.e.containerRegistryURL, repository, user.Login, token)
	var refusal *apiError
	if errors.As(err, &refusal) {
		return check, "Make the token while you are signed in to the GitHub account that owns the image.", fmt.Errorf("this token cannot read your app's image ghcr.io/%s", repository)
	}
	check.imageFound = found
	return check, "", err
}

// readImageTags reads an image's tags at a registry the way a server's pull
// does: a pull token for the repository, then its tag list. found is false
// when the image is not built yet.
// https://distribution.github.io/distribution/spec/auth/token/
func readImageTags(registryURL, repository, login, token string) (bool, error) {
	request, err := http.NewRequest(http.MethodGet, registryURL+"/token?service=ghcr.io&scope="+url.QueryEscape("repository:"+repository+":pull"), nil)
	if err != nil {
		return false, err
	}
	request.SetBasicAuth(login, token)
	var pull struct {
		Token string `json:"token"`
	}
	if err := registryCall(request, &pull); err != nil {
		return false, err
	}
	request, err = http.NewRequest(http.MethodGet, registryURL+"/v2/"+repository+"/tags/list", nil)
	if err != nil {
		return false, err
	}
	request.Header.Set("Authorization", "Bearer "+pull.Token)
	err = registryCall(request, nil)
	if refusedWith(err, http.StatusNotFound) {
		return false, nil
	}
	return err == nil, err
}

func registryCall(request *http.Request, result any) error {
	call := request.Method + " " + request.URL.Path
	response, err := httpClient.Do(request)
	if err != nil {
		return &networkError{Provider: "The registry", Call: call, Err: stripURLFromError(err)}
	}
	defer response.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(response.Body, 1<<20))
	if response.StatusCode != http.StatusOK {
		var refusal struct {
			Errors []struct {
				Code    string `json:"code"`
				Message string `json:"message"`
			} `json:"errors"`
		}
		_ = json.Unmarshal(body, &refusal)
		failure := &apiError{Provider: "The registry", Call: call, Status: response.StatusCode}
		if len(refusal.Errors) > 0 {
			failure.Code, failure.Message = refusal.Errors[0].Code, refusal.Errors[0].Message
		}
		return failure
	}
	if result != nil && json.Unmarshal(body, result) != nil {
		return fmt.Errorf("the registry answered %s with something this command cannot read", call)
	}
	return nil
}

// The apps' keys from outside services, each on its own screen.

func (g *goLive) appKeysFromOutsideServices() (string, error) {
	e := g.e
	state := stepNotNeeded
	for _, item := range secretsPlan(g.settings) {
		if item.App == "" {
			continue
		}
		state = stepDone
		if g.saved.hasAll(item.Key) {
			continue
		}
		title := "Key for " + item.App + ": " + item.Variable
		if item.Staging {
			title = "Key for " + item.App + " on staging01: " + item.Variable
		}
		var screen strings.Builder
		fmt.Fprintf(&screen, "\n%s\n\nWhat this is for:\n  %s\n\nDo this now:\n", title, screenText(item.Why))
		for i, step := range item.Steps {
			fmt.Fprintf(&screen, "  %d. %s\n", i+1, screenText(step))
		}
		screen.WriteString("\nThen paste it here.\n\n")
		e.show(screen.String())
		for {
			value, err := g.askHidden("  " + item.Variable + " (hidden): ")
			if err != nil {
				return "", err
			}
			if item.CheckedWith == "stripe" {
				if err := checkStripeKey(e.stripeAPIURL, value); err != nil {
					var refusal *apiError
					if !errors.As(err, &refusal) {
						return "", err
					}
					g.refused("Stripe", "key", err, "Copy the whole key from the steps above, then paste it again.")
					continue
				}
				e.say("Stripe accepted the key.")
			}
			if err := g.saved.save(item.Key, value); err != nil {
				return "", err
			}
			if item.CheckedWith == "" {
				e.say("Saved the key.")
			}
			break
		}
	}
	return state, nil
}

// screenText keeps a line from the settings to printable text, so it cannot
// move the cursor or clear the screen.
func screenText(text string) string {
	return strings.Map(func(r rune) rune {
		if r < ' ' || r == 0x7f {
			return ' '
		}
		return r
	}, strings.TrimSpace(text))
}

// checkStripeKey reads the account's balance with a secret or restricted
// key, which any working key may do.
// https://docs.stripe.com/api/balance/balance_retrieve
func checkStripeKey(stripeAPIURL, key string) error {
	var refusal struct {
		Error struct {
			Message string `json:"message"`
		} `json:"error"`
	}
	request, err := http.NewRequest(http.MethodGet, stripeAPIURL+"/v1/balance", nil)
	if err != nil {
		return err
	}
	request.Header.Set("Authorization", "Bearer "+key)
	response, err := httpClient.Do(request)
	if err != nil {
		return &networkError{Provider: "Stripe", Call: "GET /v1/balance", Err: stripURLFromError(err)}
	}
	defer response.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(response.Body, 1<<20))
	if response.StatusCode != http.StatusOK {
		_ = json.Unmarshal(body, &refusal)
		return &apiError{Provider: "Stripe", Call: "GET /v1/balance", Status: response.StatusCode, Message: refusal.Error.Message}
	}
	return nil
}

// The random vault secrets, made without a question.

// copiedIntoTheBundle are the vault keys the recovery bundle keeps a copy
// of, because the desk keeps them nowhere else readable: the backups'
// passphrase, without which no backup can be read, and the restore drill's
// read-only Backblaze key, which reads every backup.
var copiedIntoTheBundle = map[string]bool{
	"pgbackrest_repository_cipher_passphrase": true,
	"pgbackrest_b2_read_only_key_id":          true,
	"pgbackrest_b2_read_only_application_key": true,
}

func (g *goLive) randomVaultSecrets() (string, error) {
	e := g.e
	err := e.quietly(func() error {
		// util01 creates and deletes the restore drill's server with the
		// desk's own provider credential: the provider makes one per account.
		if !g.saved.hasAll("util01_provider_api_token") {
			if err := g.saved.save("util01_provider_api_token", g.providerCredential); err != nil {
				return err
			}
		}
		for _, item := range secretsPlan(g.settings) {
			if g.saved.hasAll(item.Key) {
				continue
			}
			switch {
			case item.Kind == randomSecret && copiedIntoTheBundle[item.Key]:
				// Made here, not inside MMX, so the bundle gets it too.
				value, err := randomText(item.Length)
				if err != nil {
					return err
				}
				if err := g.saved.save(item.Key, value); err != nil {
					return err
				}
			case item.Kind == randomSecret:
				if err := saveRandom(g.saved, item.Key, item.Length, item.HexLength); err != nil {
					return err
				}
			case item.Kind == consolePasswordSecret:
				password, err := newConsolePassword()
				if err != nil {
					return err
				}
				hash, err := consolePasswordHash(password)
				if err != nil {
					return err
				}
				// The bundle first: the vault keeps only the hash.
				if err := g.bundle.save("shared_root_console_password", password); err != nil {
					return err
				}
				if err := g.saved.save(item.Key, hash); err != nil {
					return err
				}
			}
		}
		return e.finishVaultChange(g.saved, goLiveCommand)
	})
	if err != nil {
		return "", err
	}
	return stepDone, nil
}

// randomText makes length random letters and digits.
func randomText(length int) (string, error) {
	const characters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
	text := make([]byte, length)
	for i := range text {
		n, err := rand.Int(rand.Reader, big.NewInt(int64(len(characters))))
		if err != nil {
			return "", err
		}
		text[i] = characters[n.Int64()]
	}
	return string(text), nil
}

// The lock: the recovery passphrase, then the phone code.

func (g *goLive) recoveryPassphrase() (string, error) {
	e := g.e
	words := strings.Fields(g.passphrase)
	e.setValueOnScreen(true)
	e.show(fmt.Sprintf(`
Last two steps.

Step 1 of 2: your recovery passphrase

What this is for:
  If you lose your desk, this one passphrase brings everything back.

  SAVE IT NOW.  IT IS SHOWN ONLY ONCE.

    %s

Do this now:
  1. Save it in %s as  "%s recovery passphrase".
  2. Type it here to prove you saved it.

`, strings.Join(words, "  "), g.passwordManager(), g.companyName()))
	for {
		typed, err := g.askHidden("  Recovery passphrase: ")
		if err != nil {
			e.clearValueFromScreen()
			return "", err
		}
		if strings.Join(strings.Fields(strings.ToLower(typed)), " ") == g.passphrase {
			break
		}
		e.say("")
		e.say("That is not the passphrase above.  Check the copy in %s, then type it again.", g.passwordManager())
		e.say(stillWaitingHere)
		e.say("")
	}
	e.clearValueFromScreen()
	return stepDone, nil
}

func (g *goLive) phoneCode() (string, error) {
	e := g.e
	e.show(`
Step 2 of 2: your phone code

What this is for:
  From now on, your desk needs your laptop AND a code from your phone.

Do this now:
  1. Open the authenticator app on your phone.
  2. Scan this code.
`)
	// A private folder of the person's own, so the root step's file is never
	// readable by another account.
	folder, err := os.MkdirTemp(e.home, ".phone-code-emergency-codes-")
	if err != nil {
		return "", err
	}
	defer os.RemoveAll(folder)
	path := filepath.Join(folder, "emergency_codes")
	if err := e.setUpThePhoneCode(path); err != nil {
		return "", err
	}
	codes, err := e.readRootFile(path)
	if err != nil || strings.TrimSpace(string(codes)) == "" {
		return "", fmt.Errorf("set-up-the-phone-code wrote no emergency codes to %s", path)
	}
	err = e.quietly(func() error { return g.bundle.save("phone_code_emergency_codes", strings.TrimSpace(string(codes))) })
	if err != nil {
		return "", err
	}
	return stepDone, nil
}
