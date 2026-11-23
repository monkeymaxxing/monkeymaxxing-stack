package main

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"maps"
	"net/http"
	"os"
	"os/exec"
	"regexp"
	"slices"
	"strings"
	"time"
)

// A person's provider token lives in one place on the desk: the API token
// proxy's file, which only root reads, for the coding agent's requests
// through the proxy. The desk's bootstrap puts it there, and personal-token
// server-provider replaces it, after the new token passed a check, so the
// old token keeps working until the new one is known to work. The
// Cloudflare token goes into the proxy and the person's token file; set-up-
// outside-services cloudflare and go-live make it.

const writeProxyFileCommand = "write-api-token-proxy-file"

// proxyFileRequest is one token for one of the API proxy's files, with
// what the root step needs to check it through the proxy.
type proxyFileRequest struct {
	API   string // server-provider or cloudflare
	Token string
	// ServerListingPath and TokenHeader are the provider guide's, for
	// server-provider.
	ServerListingPath string
	TokenHeader       string
	// Authentication and APIAddress are set for a provider whose requests
	// the API proxy signs: the token goes into its credential file.
	Authentication string
	APIAddress     string
	// CloudflareAccountID names the account whose verify call checks an
	// account-owned token.
	CloudflareAccountID string
}

// The API proxy's two token files and their addresses. Each file belongs to
// its own service (roles/systems_desk/files/provider-api-proxy.service and
// cloudflare-api-proxy.service).
var proxyAPIs = map[string]struct {
	file    string
	address string
}{
	"server-provider": {file: "/etc/systems-desk/provider-api-token.conf", address: "http://127.0.0.1:8081/"},
	"cloudflare":      {file: "/etc/systems-desk/cloudflare-api-token.conf", address: "http://127.0.0.1:8082/"},
}

// providerGuideAPIAddresses are the API addresses of the provider guides
// whose providers take a token in a header (provider_guides/*.md here and
// providers/*.md in monkeymaxxing-recipes, "Set systems_desk_provider_api_url").
// The person's typed token goes only to one of them. A new header-token
// provider needs its API address added here by a one-line change. Reason: the coding agent can push mmx_project_settings.yml,
// and an address taken from it as it is would send the token to any host
// the agent chose.
var providerGuideAPIAddresses = []string{
	"https://api.hetzner.cloud/v1/",
	"https://api.digitalocean.com/v2/",
	"https://api.vultr.com/v2/",
	"https://api.scaleway.com/",
}

// A listing path may start with "?" for an API whose listing is a query on
// the API address itself, such as AWS EC2's ?Action=DescribeInstances.
var listingPathPattern = regexp.MustCompile(`^[A-Za-z0-9?][A-Za-z0-9/_.?=&-]*$`)

func runPersonalToken(e *environment, arguments []string) error {
	if len(arguments) == 0 {
		return fmt.Errorf("personal-token needs server-provider or staging-access: %w", errUsage)
	}
	settings, err := readSystemSettings(e.readRepositoryFile)
	if err != nil {
		return err
	}
	which := arguments[0]
	flags := flag.NewFlagSet("personal-token "+which, flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	listingPath := flags.String("server-listing-path", "", "")
	tokenHeader := flags.String("token-header", "", "")
	if err := flags.Parse(arguments[1:]); err != nil || flags.NArg() > 0 {
		return fmt.Errorf("personal-token %s: unknown arguments: %w", which, errUsage)
	}
	if *tokenHeader != "" && which != "server-provider" {
		return fmt.Errorf("--token-header belongs to personal-token server-provider: %w", errUsage)
	}
	switch which {
	case "server-provider":
		return installServerProviderToken(e, settings, *listingPath, *tokenHeader)
	case "staging-access":
		if *listingPath != "" {
			return fmt.Errorf("--server-listing-path belongs to personal-token server-provider: %w", errUsage)
		}
		return installStagingAccessToken(e, settings)
	}
	return fmt.Errorf("unknown personal token %q: %w", which, errUsage)
}

// tokenHeaderPattern is an HTTP header's name, such as X-Auth-Token.
var tokenHeaderPattern = regexp.MustCompile(`^[A-Za-z0-9-]{1,64}$`)

// tokenHeaders sends the token as most providers take it, Authorization:
// Bearer, or in the provider guide's own header, such as Scaleway's
// X-Auth-Token.
func tokenHeaders(header, token string) map[string]string {
	if header == "" {
		return map[string]string{"Authorization": "Bearer " + token}
	}
	return map[string]string{header: token}
}

func checkWithBearerToken(provider, url, token string, result any) error {
	return checkWithToken(provider, url, "", token, result)
}

func checkWithToken(provider, url, header, token string, result any) error {
	_, err := doJSON(provider, "a check of the new token", http.MethodGet, url, tokenHeaders(header, token), nil, result, readCloudflareError)
	return err
}

func installServerProviderToken(e *environment, settings systemSettings, listingPath, tokenHeader string) error {
	apiURL := settings.Vars.SystemsDeskProviderAPIURL
	authentication := settings.Vars.SystemsDeskProviderAPIAuthentication
	method, signs := requestSigningMethods[authentication]
	if !signs && authentication != tokenInAHeader {
		return fmt.Errorf("vars.systems_desk_provider_api_authentication in %s is %q. It must be %s, or the one your provider guide gives: %s. Nothing was sent",
			projectSettingsFile, authentication, tokenInAHeader, strings.Join(slices.Sorted(maps.Keys(requestSigningMethods)), ", "))
	}
	if signs && !e.signingAPIAddresses[authentication].MatchString(apiURL) {
		return fmt.Errorf("vars.systems_desk_provider_api_url in %s is %q, which is not a provider guide's API address for %s. "+
			"This command sends your credential only to %s. Nothing was sent. "+
			"Set the address your provider guide gives, with its trailing slash", projectSettingsFile, apiURL, authentication, method.apiAddressesInWords)
	}
	if !signs && !slices.Contains(e.providerGuideAPIAddresses, apiURL) {
		return fmt.Errorf("vars.systems_desk_provider_api_url in %s is %q, which is not a provider guide's API address for %s. "+
			"This command sends your token only to one of these: %s. Nothing was sent. "+
			"Set the address your provider guide gives, with its trailing slash", projectSettingsFile, apiURL, authentication, strings.Join(e.providerGuideAPIAddresses, ", "))
	}
	if !listingPathPattern.MatchString(listingPath) || strings.Contains(listingPath, "..") {
		return fmt.Errorf("give --server-listing-path, the provider guide's server listing after the API address, such as servers for Hetzner Cloud or droplets for DigitalOcean: %w", errUsage)
	}
	if tokenHeader != "" && (signs || !tokenHeaderPattern.MatchString(tokenHeader) || strings.EqualFold(tokenHeader, "Authorization")) {
		return fmt.Errorf("--token-header takes the provider guide's header name, such as X-Auth-Token for Scaleway; leave it out for Authorization: Bearer and for a provider whose requests are signed: %w", errUsage)
	}
	// One word per thing: a provider whose requests are signed gives a
	// credential of several values, such as OVHcloud's three; the others give
	// a token.
	noun := "token"
	if signs {
		noun = "credential"
	}
	e.say("Your server provider %s lets this systems desk create and list servers at the provider.", noun)
	if signs {
		e.say("It goes into the systems desk's API proxy, which signs your coding agent's requests with it, so your coding agent uses it without reading it.")
	} else {
		e.say("It goes into the systems desk's API proxy, which adds it to your coding agent's requests, so your coding agent uses it without reading it.")
	}
	e.say("This command checks it at %s%s, your provider guide's address.", apiURL, listingPath)
	var token string
	var err error
	if signs {
		token, err = e.promptSignedProviderToken(method, "")
	} else {
		token, err = e.prompt("Server provider token (hidden): ")
	}
	if err != nil {
		return err
	}
	if signs && token == "" {
		return errors.New("nothing was entered, so nothing changed")
	}
	if err := checkTokenValue("token", token); err != nil {
		return err
	}
	if signs {
		parts, _ := splitProviderToken(method, token)
		var signer requestSigner
		if signer, err = method.newSigner(apiURL, parts, httpClient); err == nil {
			err = checkSignedRequest(method, signer, apiURL+listingPath)
		}
	} else {
		err = checkWithToken("The server provider", apiURL+listingPath, tokenHeader, token, nil)
	}
	if err != nil {
		return fmt.Errorf("the new %s failed its check, so nothing changed: %v", noun, err)
	}
	e.say("The provider accepted the new %s: %s%s answered.", noun, apiURL, listingPath)
	request := proxyFileRequest{API: "server-provider", Token: token, ServerListingPath: listingPath, TokenHeader: tokenHeader}
	if signs {
		request.Authentication, request.APIAddress = authentication, apiURL
	}
	if err := e.writeProxyFile(request); err != nil {
		return err
	}
	e.say("Your coding agent uses the new %s from now on. Go back to your coding agent.", noun)
	return nil
}

// promptSignedProviderToken asks for each part of a signed provider's
// token at its own hidden prompt, under the name the provider's page gives
// it, and returns them joined with ":", as SERVER_PROVIDER_API_TOKEN holds
// them. indent starts each prompt. Enter at the first prompt returns "",
// which the vault step reads as "later".
//
// For a key file, the person pastes the file's whole text at one prompt;
// the lines are read until they make one JSON object, and the token is the
// compact JSON in base64.
func (e *environment) promptSignedProviderToken(method requestSigningMethod, indent string) (string, error) {
	if method.pastesAKeyFile {
		var text strings.Builder
		label := indent + method.tokenParts[0] + ", its whole text from { to } (hidden): "
		// A key file is about a dozen lines; 200 leave room for any layout.
		for lines := 0; lines < 200; lines++ {
			line, err := e.prompt(label)
			if err != nil {
				return "", err
			}
			if lines == 0 && strings.TrimSpace(line) == "" {
				return "", nil
			}
			text.WriteString(line + "\n")
			if json.Valid([]byte(text.String())) {
				var compact bytes.Buffer
				_ = json.Compact(&compact, []byte(text.String()))
				token := base64.StdEncoding.EncodeToString(compact.Bytes())
				_, err := splitProviderToken(method, token)
				return token, err
			}
			label = ""
		}
		return "", errors.New("the pasted text never closed its JSON. Paste the whole key file, from { to }")
	}
	var parts []string
	for i, label := range method.tokenParts {
		value, err := e.prompt(indent + label + " (hidden): ")
		if err != nil {
			return "", err
		}
		value = strings.TrimSpace(value)
		if i == 0 && value == "" {
			return "", nil
		}
		parts = append(parts, value)
	}
	token := strings.Join(parts, ":")
	_, err := splitProviderToken(method, token)
	return token, err
}

// checkSignedRequest sends one signed GET and wants HTTP 200. A refusal
// carries the method's advice on which typed value to check.
func checkSignedRequest(method requestSigningMethod, signer requestSigner, address string) error {
	request, err := http.NewRequest(http.MethodGet, address, nil)
	if err != nil {
		return err
	}
	if err := signer.sign(request, nil); err != nil {
		return stripURLFromError(err)
	}
	response, err := httpClient.Do(request)
	if err != nil {
		return stripURLFromError(err)
	}
	defer response.Body.Close()
	answer, _ := io.ReadAll(io.LimitReader(response.Body, 4096))
	if response.StatusCode != http.StatusOK {
		message, advice := method.readRefusal(answer)
		err := fmt.Errorf("%s answered HTTP %d: %s", address, response.StatusCode, trimPeriod(message))
		if advice != "" {
			err = fmt.Errorf("%v. %s", err, advice)
		}
		return err
	}
	return nil
}

// writeProxyFileWithSudo runs this program's root step through sudo, with
// the token on standard input. The person's desk account may use sudo; the
// rest of this command runs without root.
func writeProxyFileWithSudo(request proxyFileRequest) error {
	program, err := os.Executable()
	if err != nil {
		return err
	}
	arguments := []string{"-n", program, writeProxyFileCommand, "--api", request.API}
	if request.ServerListingPath != "" {
		arguments = append(arguments, "--server-listing-path", request.ServerListingPath)
	}
	if request.TokenHeader != "" {
		arguments = append(arguments, "--token-header", request.TokenHeader)
	}
	if request.Authentication != "" {
		arguments = append(arguments, "--provider-api-authentication", request.Authentication, "--provider-api-address", request.APIAddress)
	}
	if request.CloudflareAccountID != "" {
		arguments = append(arguments, "--cloudflare-account-id", request.CloudflareAccountID)
	}
	command := exec.Command("sudo", arguments...)
	command.Stdin = strings.NewReader(request.Token + "\n")
	// The root step's lines are for the coding agent, not the person's
	// screen; a failure brings its last line, the reason, into the error.
	var output bytes.Buffer
	command.Stdout, command.Stderr = &output, &output
	if err := command.Run(); err != nil {
		lines := strings.Split(strings.TrimSpace(output.String()), "\n")
		reason := strings.TrimPrefix(lines[len(lines)-1], "Stopped: ")
		if reason == "" {
			reason = err.Error()
		}
		return fmt.Errorf("the API proxy kept its old token: the root step failed: %s", trimPeriod(reason))
	}
	return nil
}

// runWriteAPITokenProxyFile is the root step: it replaces one token file of
// the API proxy, restarts that file's service, and checks a request through
// it. On any failure it puts the old file back, so the proxy keeps working
// with the old token.
func runWriteAPITokenProxyFile(arguments []string, stdin io.Reader, out io.Writer) error {
	if os.Geteuid() != 0 {
		return fmt.Errorf("%s is the root step of personal-token and cloudflare, run through sudo", writeProxyFileCommand)
	}
	flags := flag.NewFlagSet(writeProxyFileCommand, flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	api := flags.String("api", "", "")
	listingPath := flags.String("server-listing-path", "", "")
	tokenHeader := flags.String("token-header", "", "")
	accountID := flags.String("cloudflare-account-id", "", "")
	authentication := flags.String("provider-api-authentication", "", "")
	apiAddress := flags.String("provider-api-address", "", "")
	if err := flags.Parse(arguments); err != nil || flags.NArg() > 0 {
		return errUsage
	}
	if *tokenHeader != "" && (!tokenHeaderPattern.MatchString(*tokenHeader) || *api != "server-provider") {
		return fmt.Errorf("--token-header is a header name, for server-provider only: %w", errUsage)
	}
	target, ok := proxyAPIs[*api]
	if !ok {
		return fmt.Errorf("--api must be server-provider or cloudflare: %w", errUsage)
	}
	// The desk's Cloudflare token is account-owned, which only the account's
	// verify call accepts.
	checkPath := "accounts/" + *accountID + "/tokens/verify"
	if *api == "cloudflare" && !cloudflareAccountIDPattern.MatchString(*accountID) {
		return fmt.Errorf("--cloudflare-account-id, the account's 32-character ID, is required: %w", errUsage)
	}
	if *api == "server-provider" {
		if !listingPathPattern.MatchString(*listingPath) || strings.Contains(*listingPath, "..") {
			return fmt.Errorf("--server-listing-path is required: %w", errUsage)
		}
		checkPath = *listingPath
	}
	line, err := io.ReadAll(io.LimitReader(stdin, 4096))
	if err != nil {
		return err
	}
	token := strings.TrimSpace(string(line))
	if err := checkTokenValue("token", token); err != nil {
		return err
	}
	if *authentication != "" {
		if *api != "server-provider" || *tokenHeader != "" {
			return fmt.Errorf("--provider-api-authentication belongs to server-provider, without --token-header: %w", errUsage)
		}
		return writeSigningCredential(signingCredential{Authentication: *authentication, APIAddress: *apiAddress, Token: token}, checkPath, out)
	}
	// The proxy reads this one line (headerTokenFile).
	proxyLine := `proxy_set_header Authorization "Bearer ` + token + `";` + "\n"
	if *tokenHeader != "" {
		proxyLine = `proxy_set_header ` + *tokenHeader + ` "` + token + `";` + "\n"
	}
	return writeFileAndRestartProxy(target.file, []byte(proxyLine), target.address+checkPath, "token", out)
}

// writeSigningCredential is the root step for a provider whose requests
// the API proxy signs: it replaces the proxy's credential file,
// restarts the proxy, and checks a request through it. On any failure it
// puts the old file back, so the proxy keeps working with the old
// credential.
func writeSigningCredential(credential signingCredential, checkPath string, out io.Writer) error {
	if _, _, err := checkSigningCredential(credential, signingAPIAddresses); err != nil {
		return err
	}
	content, err := json.Marshal(credential)
	if err != nil {
		return err
	}
	return writeFileAndRestartProxy(signingCredentialFile, append(content, '\n'), providerAPIProxyAddress+checkPath, "credential", out)
}

// writeFileAndRestartProxy replaces one of the API proxy's root-only
// files, restarts the service that reads that file (the Cloudflare token's
// is cloudflare-api-proxy, every other is provider-api-proxy), and checks a
// request through it. Each service starts once its own file exists, so
// the other's file never holds this one back. On any failure it puts the old
// file back, so the service keeps working with the old one.
func writeFileAndRestartProxy(path string, content []byte, checkAddress, noun string, out io.Writer) error {
	service, unitFile := apiProxyService, apiProxyUnitFile
	if path == proxyAPIs["cloudflare"].file {
		service, unitFile = cloudflareProxyService, cloudflareProxyUnitFile
	}
	if _, err := os.Stat(unitFile); err != nil {
		return fmt.Errorf("%v. A systems desk review installs the proxy; run review-and-apply-the-systems-desk-settings first", err)
	}
	old, readErr := os.ReadFile(path)
	hadOld := readErr == nil
	if err := writeRootFile(path, content); err != nil {
		return err
	}
	restore := func(reason error) error {
		if hadOld {
			_ = writeRootFile(path, old)
			_ = exec.Command("systemctl", "restart", service).Run()
		} else {
			_ = os.Remove(path)
			_ = exec.Command("systemctl", "stop", service).Run()
		}
		return fmt.Errorf("%v. The API proxy keeps its old %s", reason, noun)
	}
	for _, step := range [][]string{{"systemctl", "enable", "--quiet", service}, {"systemctl", "restart", service}} {
		if output, err := exec.Command(step[0], step[1:]...).CombinedOutput(); err != nil {
			return restore(fmt.Errorf("%s failed: %s. A systems desk review installs the proxy; run review-and-apply-the-systems-desk-settings first", strings.Join(step, " "), firstLine(string(output), err)))
		}
	}
	if err := checkThroughProxy(checkAddress, out, noun); err != nil {
		return restore(err)
	}
	return nil
}

// checkThroughProxy wants HTTP 200 from address within ten seconds, the
// time a restarted proxy takes to listen, with room to spare.
func checkThroughProxy(address string, out io.Writer, noun string) error {
	var lastErr error
	for attempt := 0; attempt < 20; attempt++ {
		response, err := httpClient.Get(address)
		if err == nil {
			io.Copy(io.Discard, response.Body)
			response.Body.Close()
			if response.StatusCode == http.StatusOK {
				fmt.Fprintf(out, "The API proxy has the new %s: %s answered through it.\n", noun, address)
				return nil
			}
			lastErr = fmt.Errorf("%s answered HTTP %d through the API proxy", address, response.StatusCode)
		} else {
			lastErr = err
		}
		time.Sleep(500 * time.Millisecond)
	}
	return lastErr
}

func writeRootFile(path string, content []byte) error {
	temporary := path + ".new"
	if err := os.WriteFile(temporary, content, 0o600); err != nil {
		return err
	}
	if err := os.Chmod(temporary, 0o600); err != nil {
		return err
	}
	if err := os.Chown(temporary, 0, 0); err != nil {
		return err
	}
	return os.Rename(temporary, path)
}

// installStagingAccessToken enters staging's Access service token on a
// desk whose token file lacks it, such as a second person's desk: Cloudflare
// showed its Client Secret once, when set-up-outside-services cloudflare
// made it, and the team's password manager keeps both values.
func installStagingAccessToken(e *environment, settings systemSettings) error {
	if !settings.hasStagingServer {
		return errors.New("this system has no staging01, so it has no staging Access service token")
	}
	path := e.tokenFilePath(settings)
	e.say("Staging's Access service token opens your staging pages without a sign-in, for your local app tests and checks.")
	e.say("Copy its two values from your password manager's entry %q.", settings.ProjectName+" staging Access service token")
	clientID, err := e.prompt("Client ID (hidden): ")
	if err != nil {
		return err
	}
	clientSecret, err := e.prompt("Client Secret (hidden): ")
	if err != nil {
		return err
	}
	clientID, clientSecret = strings.TrimSpace(clientID), strings.TrimSpace(clientSecret)
	if !strings.HasSuffix(clientID, ".access") || clientSecret == "" {
		return errors.New("a Client ID ends in .access, and the Client Secret is the other value of the same entry. Check what you pasted. Nothing changed")
	}
	if err := updateTokenFile(path, map[string]string{stagingAccessClientIDVariable: clientID, stagingAccessClientSecretVariable: clientSecret}); err != nil {
		return err
	}
	e.say("Saved it in %s as %s and %s.", path, stagingAccessClientIDVariable, stagingAccessClientSecretVariable)
	return nil
}
