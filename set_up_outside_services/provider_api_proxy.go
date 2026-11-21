package main

// The API proxy is the one program through which the coding agent
// uses the server provider's API and Cloudflare's API, without reading the
// person's token or credential. On http://127.0.0.1:8081/ it adds the
// provider credential to each request and forwards the request to the
// provider's API address: a token in a header (Hetzner, DigitalOcean,
// Vultr, Scaleway), a signature (OVHcloud and AWS sign each request with a
// secret) or a short-lived access token made from a service account key
// (Google Cloud). On http://127.0.0.1:8082/ it adds the desk's Cloudflare
// token and forwards to Cloudflare's API. systemd runs it as
// provider-api-proxy.service, under an account of its own
// (DynamicUser), and hands it the root-only files through LoadCredential.
// docs/design.md, "The coding agent and personal credentials", records the
// design.

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"slices"
	"strings"
)

const (
	apiProxyCommand = "run-the-provider-api-proxy"
	// The coding agent's address for its provider's API, the same at every
	// provider.
	providerAPIListenAddress = "127.0.0.1:8081"
	providerAPIProxyAddress  = "http://" + providerAPIListenAddress + "/"
	apiProxyService          = "provider-api-proxy"
	// The coding agent's address for Cloudflare's API, and where the proxy
	// forwards it. Reason for the fixed address: the desk's Cloudflare token
	// goes only to Cloudflare.
	cloudflareProxyListenAddress = "127.0.0.1:8082"
	cloudflareAPIAddress         = "https://api.cloudflare.com/client/v4/"
	// The unit's unitFile and the names under which systemd's LoadCredential
	// gives the proxy the token files.
	apiProxyUnitFile              = "/etc/systemd/system/provider-api-proxy.service"
	providerTokenCredentialName   = "provider-api-token"
	cloudflareTokenCredentialName = "cloudflare-api-token"
	// The desk's own server ID at the provider, a root-owned file that
	// systemd's LoadCredential gives the proxy under this name.
	deskServerIDFile           = "/etc/systems-desk/desk-server-id"
	deskServerIDCredentialName = "desk-server-id"
	// The desk's own name at the provider, which some providers put in the
	// path instead of an ID (an OVHcloud VPS, a Google Cloud instance). The
	// file may be empty: a name is checked only when recorded.
	deskServerNameFile           = "/etc/systems-desk/desk-server-name"
	deskServerNameCredentialName = "desk-server-name"
	// The credential file, root:root 0600. systemd's LoadCredential gives the
	// service a copy under this name that only the service's account reads.
	signingCredentialFile = "/etc/systems-desk/provider-api-signing-credential.json"
	signingCredentialName = "provider-api-signing-credential"
	// systems_desk_provider_api_authentication for a provider that takes a
	// token in a header.
	tokenInAHeader = "token_in_a_header"
)

// requestSigningMethod is one way a provider authenticates a request, named
// by systems_desk_provider_api_authentication. Every provider the proxy
// serves is one entry of requestSigningMethods; the proxy, personal-token
// and secrets read the entry and never branch on the provider.
type requestSigningMethod struct {
	// tokenParts are the values the person types, in order, under the names
	// the provider's page gives them. SERVER_PROVIDER_API_TOKEN holds them
	// joined with ":", and partFormat checks each.
	tokenParts []string
	partFormat *regexp.Regexp
	// pastesAKeyFile is set for a provider whose credential is a key file
	// of JSON: the person pastes the file's whole text at one prompt, and
	// SERVER_PROVIDER_API_TOKEN holds the text in base64, one line, with
	// tokenParts' one name for it. checkKeyFile checks the decoded text.
	pastesAKeyFile bool
	checkKeyFile   func(keyFile []byte) error
	// apiAddress matches the provider guides' API addresses. The credential
	// goes only to one of them. Reason: the coding agent can push
	// mmx_project_settings.yml, and a credential sent to an address taken
	// from it as it is would reach any host.
	apiAddress          *regexp.Regexp
	apiAddressesInWords string
	// otherAPIs are further API addresses of the same provider, each under
	// its own first path segment on the proxy, such as Google's price
	// catalog under /cloudbilling/. Every other path goes to the API address.
	otherAPIs map[string]string
	newSigner func(apiAddress string, parts []string, client *http.Client) (requestSigner, error)
	// util01TokenPage is where the person makes util01's own credential,
	// for set-up-outside-services secrets.
	util01TokenPage string
	// readRefusal turns the provider's answer to a refused check into its
	// message and, for the common refusals, which typed value to check or
	// what to do ("" when it has no advice).
	readRefusal func(answer []byte) (message, advice string)
}

// requestSigner adds the credential to one request to the provider. body is
// the request's whole body, which some providers sign.
type requestSigner interface {
	sign(request *http.Request, body []byte) error
}

var requestSigningMethods = map[string]requestSigningMethod{
	"ovhcloud_signed_requests": {
		tokenParts:          []string{"Application Key", "Application Secret", "Consumer Key"},
		partFormat:          regexp.MustCompile(`^[A-Za-z0-9]{1,128}$`),
		apiAddress:          regexp.MustCompile(`^https://(api\.us\.ovhcloud\.com|eu\.api\.ovh\.com|ca\.api\.ovh\.com)/1\.0/$`),
		apiAddressesInWords: "https://api.us.ovhcloud.com/1.0/, https://eu.api.ovh.com/1.0/ or https://ca.api.ovh.com/1.0/",
		newSigner:           newOVHcloudSigner,
		// OVHcloud's page takes the project's ID in its link, so the coding
		// agent makes the link.
		util01TokenPage: "the link your coding agent gives you from provider_guides/ovhcloud_public_cloud.md, \"util01's credential\", with Validity: Unlimited",
		readRefusal:     readOVHcloudRefusal,
	},
	"aws_signed_requests": {
		// AWS's access keys: the ID is 16 to 128 letters and digits (IAM's
		// AccessKey type), the secret 40 characters of base64.
		tokenParts: []string{"Access key ID", "Secret access key"},
		partFormat: regexp.MustCompile(`^[A-Za-z0-9/+=]{16,128}$`),
		// EC2's address in one region, from which the signer takes the
		// region and the service it signs for.
		apiAddress:          regexp.MustCompile(`^https://ec2\.[a-z]{2}(-[a-z]+)+-[0-9]+\.amazonaws\.com/$`),
		apiAddressesInWords: "https://ec2.REGION.amazonaws.com/, with the region of the servers, such as https://ec2.eu-north-1.amazonaws.com/",
		newSigner:           newAWSSigner,
		util01TokenPage:     "https://console.aws.amazon.com/iam/home#/users, the user util01-restore-drill that the AWS EC2 guide (monkeymaxxing-recipes, providers/aws-ec2.md), \"util01's credential\", describes, Security credentials, Create access key (Command Line Interface)",
		readRefusal:         readAWSRefusal,
	},
	"google_cloud_service_account_tokens": {
		tokenParts:          []string{"Service account key file"},
		pastesAKeyFile:      true,
		checkKeyFile:        checkGoogleServiceAccountKey,
		apiAddress:          regexp.MustCompile(`^https://compute\.googleapis\.com/compute/v1/$`),
		apiAddressesInWords: "https://compute.googleapis.com/compute/v1/",
		// The public price catalog, for the price request.
		otherAPIs:       map[string]string{"cloudbilling": "https://cloudbilling.googleapis.com/"},
		newSigner:       newGoogleTokenSigner,
		util01TokenPage: "Cloud Shell, with the commands of the Google Compute Engine guide (monkeymaxxing-recipes, providers/google-compute-engine.md), \"util01's credential\"; then cat util01-restore-drill.json there",
		readRefusal:     readGoogleRefusal,
	},
}

// signingAPIAddresses are the provider guides' API addresses for each
// signing method, from the table; tests replace them with a stand-in's.
var signingAPIAddresses = func() map[string]*regexp.Regexp {
	addresses := map[string]*regexp.Regexp{}
	for name, method := range requestSigningMethods {
		addresses[name] = method.apiAddress
	}
	return addresses
}()

// signingCredential is the content of the credential file.
type signingCredential struct {
	Authentication string `json:"provider_api_authentication"`
	APIAddress     string `json:"provider_api_address"`
	Token          string `json:"server_provider_api_token"`
}

// splitProviderToken checks a token against its method and returns its
// parts: the typed values, or the decoded key file.
func splitProviderToken(method requestSigningMethod, token string) ([]string, error) {
	if method.pastesAKeyFile {
		keyFile, err := decodeKeyFileToken(token)
		if err == nil {
			err = method.checkKeyFile(keyFile)
		}
		if err != nil {
			return nil, err
		}
		return []string{string(keyFile)}, nil
	}
	parts := strings.Split(token, ":")
	if len(parts) != len(method.tokenParts) {
		return nil, fmt.Errorf("the credential has %d parts; it needs %d, joined with a colon: %s", len(parts), len(method.tokenParts), strings.Join(method.tokenParts, ", "))
	}
	for i, part := range parts {
		if !method.partFormat.MatchString(part) {
			return nil, fmt.Errorf("the %s has a character the provider never uses. Check that you pasted the whole value and nothing else", method.tokenParts[i])
		}
	}
	return parts, nil
}

// checkSigningCredential checks a credential before it is written and again
// when the proxy reads it, and returns its method and token parts.
func checkSigningCredential(credential signingCredential, addresses map[string]*regexp.Regexp) (requestSigningMethod, []string, error) {
	method, known := requestSigningMethods[credential.Authentication]
	if !known {
		return method, nil, fmt.Errorf("%q is not a way of signing requests this program knows", credential.Authentication)
	}
	if !addresses[credential.Authentication].MatchString(credential.APIAddress) {
		return method, nil, fmt.Errorf("%q is not a provider guide's API address for %s. The credential goes only to %s",
			credential.APIAddress, credential.Authentication, method.apiAddressesInWords)
	}
	parts, err := splitProviderToken(method, credential.Token)
	return method, parts, err
}

// headerTokenFile is the content of a token file, as set-up-outside-services
// writes it: one line, proxy_set_header NAME "VALUE";
// Only the name and value matter now. The format is kept from the time nginx
// read these files, so desks that already have the root-only files keep
// working without rewriting them.
var headerTokenFile = regexp.MustCompile(`^proxy_set_header ([A-Za-z0-9-]{1,64}) "([A-Za-z0-9._~+/=: -]+)";\n?$`)

// headerTokenSigner adds a token in a header to each request. Set replaces
// a header of the same name that the coding agent sent.
type headerTokenSigner struct{ header, value string }

func (s headerTokenSigner) sign(request *http.Request, _ []byte) error {
	request.Header.Set(s.header, s.value)
	return nil
}

func readHeaderTokenSigner(path string) (headerTokenSigner, error) {
	text, err := os.ReadFile(path)
	if err != nil {
		return headerTokenSigner{}, err
	}
	match := headerTokenFile.FindStringSubmatch(string(text))
	if match == nil {
		return headerTokenSigner{}, fmt.Errorf("%s is not a token file: it holds one line, proxy_set_header NAME \"TOKEN\";", path)
	}
	return headerTokenSigner{header: match[1], value: match[2]}, nil
}

// newHeaderTokenProxy forwards each request to apiAddress with the token.
func newHeaderTokenProxy(apiAddress string, signer headerTokenSigner, client *http.Client) *apiProxy {
	// A redirect is passed back, never followed: the token would follow it.
	client.CheckRedirect = func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }
	return &apiProxy{apiAddress: apiAddress, signer: signer, client: client}
}

// runProviderAPIProxy is the service's program. It reads the files
// systemd handed it and serves 8081 and 8082 until it is stopped. A provider
// that takes a token in a header gets --provider-api-url (the unit's
// argument) and provider-api-token; a provider whose requests are signed
// gets provider-api-signing-credential, which holds the API address.
func runProviderAPIProxy(arguments []string) error {
	flags := flag.NewFlagSet(apiProxyCommand, flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	providerAPIURL := flags.String("provider-api-url", "", "")
	if err := flags.Parse(arguments); err != nil || flags.NArg() > 0 {
		return fmt.Errorf("%s takes only --provider-api-url, for a provider that takes a token in a header: %w", apiProxyCommand, errUsage)
	}
	directory := os.Getenv("CREDENTIALS_DIRECTORY")
	if directory == "" {
		return fmt.Errorf("%s runs only as %s.service, which hands it the credential files", apiProxyCommand, apiProxyService)
	}
	var providerProxy *apiProxy
	if *providerAPIURL != "" {
		// Reason: the unit's argument comes from mmx_project_settings.yml,
		// which the coding agent can push; the token goes only to a provider
		// guide's address.
		if !slices.Contains(providerGuideAPIAddresses, *providerAPIURL) {
			return fmt.Errorf("--provider-api-url %q is not a provider guide's API address: %s", *providerAPIURL, strings.Join(providerGuideAPIAddresses, ", "))
		}
		signer, err := readHeaderTokenSigner(filepath.Join(directory, providerTokenCredentialName))
		if err != nil {
			return err
		}
		providerProxy = newHeaderTokenProxy(*providerAPIURL, signer, &http.Client{})
		fmt.Fprintf(os.Stderr, "Adding the token to requests to %s on %s.\n", *providerAPIURL, providerAPIProxyAddress)
	} else {
		text, err := os.ReadFile(filepath.Join(directory, signingCredentialName))
		if err != nil {
			return err
		}
		var credential signingCredential
		if err := json.Unmarshal(text, &credential); err != nil {
			return fmt.Errorf("%s is not the credential file's JSON", signingCredentialFile)
		}
		providerProxy, err = newAPIProxy(credential, signingAPIAddresses, &http.Client{})
		if err != nil {
			return err
		}
		fmt.Fprintf(os.Stderr, "Signing requests to %s on %s.\n", credential.APIAddress, providerAPIProxyAddress)
	}
	idText, err := os.ReadFile(filepath.Join(directory, deskServerIDCredentialName))
	if err != nil || strings.TrimSpace(string(idText)) == "" {
		return fmt.Errorf("%s must hold the systems desk's own server ID at the provider; record it as provider_server_id in the systems desk's entry of inventories/servers.yml", deskServerIDFile)
	}
	providerProxy.deskServerID = strings.TrimSpace(string(idText))
	nameText, err := os.ReadFile(filepath.Join(directory, deskServerNameCredentialName))
	if err != nil {
		return fmt.Errorf("%s must exist (empty when the provider names no server in a path)", deskServerNameFile)
	}
	providerProxy.deskServerName = strings.TrimSpace(string(nameText))
	cloudflareSigner, err := readHeaderTokenSigner(filepath.Join(directory, cloudflareTokenCredentialName))
	if err != nil {
		return err
	}
	cloudflareProxy := newHeaderTokenProxy(cloudflareAPIAddress, cloudflareSigner, &http.Client{})
	fmt.Fprintf(os.Stderr, "Adding the Cloudflare token to requests to %s on http://%s/.\n", cloudflareAPIAddress, cloudflareProxyListenAddress)
	return serveBoth(providerProxy, cloudflareProxy)
}

// serveBoth listens on both addresses before it serves either, so a port in
// use stops the service at once, and returns when either server stops.
func serveBoth(providerProxy, cloudflareProxy http.Handler) error {
	providerListener, err := net.Listen("tcp", providerAPIListenAddress)
	if err != nil {
		return err
	}
	cloudflareListener, err := net.Listen("tcp", cloudflareProxyListenAddress)
	if err != nil {
		return err
	}
	stopped := make(chan error, 2)
	go func() { stopped <- http.Serve(providerListener, providerProxy) }()
	go func() { stopped <- http.Serve(cloudflareListener, cloudflareProxy) }()
	return <-stopped
}

// apiProxy forwards each request to the API address, signed.
type apiProxy struct {
	apiAddress string
	otherAPIs  map[string]string
	signer     requestSigner
	client     *http.Client
	// deskServerID is the desk's own server ID at the provider; empty on the
	// Cloudflare proxy, whose API has no servers.
	deskServerID string
	// deskServerName is the desk's own name at the provider, empty when not recorded.
	deskServerName string
}

// changesTheDeskItself reports whether a request other than GET names the
// desk's own server ID or provider-side name: as a path segment, or as a
// whole word in the query or body (a JSON value, or a form value such as
// AWS's InstanceId.1). Reason: a cleanup must never delete or rebuild the
// desk by mistake; the desk is managed by its own guide.
func (p *apiProxy) changesTheDeskItself(r *http.Request, body []byte) bool {
	if r.Method == http.MethodGet {
		return false
	}
	for _, name := range []string{p.deskServerID, p.deskServerName} {
		if name == "" {
			continue
		}
		if slices.Contains(strings.Split(r.URL.Path, "/"), name) {
			return true
		}
		whole := regexp.MustCompile(`(^|[^A-Za-z0-9_.-])` + regexp.QuoteMeta(name) + `($|[^A-Za-z0-9_.-])`)
		if whole.MatchString(r.URL.RawQuery) || whole.Match(body) {
			return true
		}
	}
	return false
}

func newAPIProxy(credential signingCredential, addresses map[string]*regexp.Regexp, client *http.Client) (*apiProxy, error) {
	method, parts, err := checkSigningCredential(credential, addresses)
	if err != nil {
		return nil, err
	}
	// A redirect is passed back, never followed. Reason: following it would
	// send the signed headers to the redirect's host.
	client.CheckRedirect = func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }
	signer, err := method.newSigner(credential.APIAddress, parts, client)
	if err != nil {
		return nil, err
	}
	return &apiProxy{apiAddress: credential.APIAddress, otherAPIs: method.otherAPIs, signer: signer, client: client}, nil
}

// Headers that belong to one connection, or carry another credential, and
// so never pass the proxy (RFC 9110, section 7.6.1), and the providers'
// own authentication headers, which only the signer sets.
var headersThatStayBehind = []string{"Connection", "Keep-Alive", "Proxy-Authenticate", "Proxy-Authorization",
	"Proxy-Connection", "Te", "Trailer", "Transfer-Encoding", "Upgrade", "Authorization", "Cookie", "Host"}
var headerPrefixesThatStayBehind = []string{"x-ovh-", "x-amz-", "x-goog-"}

func copyHeaders(to, from http.Header) {
	for name, values := range from {
		lower := strings.ToLower(name)
		if slices.ContainsFunc(headersThatStayBehind, func(h string) bool { return strings.EqualFold(h, name) }) ||
			slices.ContainsFunc(headerPrefixesThatStayBehind, func(prefix string) bool { return strings.HasPrefix(lower, prefix) }) {
			continue
		}
		for _, value := range values {
			to.Add(name, value)
		}
	}
}

func refuse(w http.ResponseWriter, status int, format string, values ...any) {
	message := fmt.Sprintf(format, values...)
	fmt.Fprintf(os.Stderr, "Refused: %s\n", message)
	http.Error(w, "API proxy: "+message, status)
}

// target is the provider's address for a path on the proxy: under one of
// otherAPIs when the path's first segment names it, else under the API
// address.
func (p *apiProxy) target(escapedPath string) string {
	path := strings.TrimPrefix(escapedPath, "/")
	first, rest, _ := strings.Cut(path, "/")
	if address, ok := p.otherAPIs[first]; ok {
		return address + rest
	}
	return p.apiAddress + path
}

func (p *apiProxy) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	// Reason for both refusals: the request goes only to a path under the
	// API address, and the provider checks its access rules against the
	// path as signed.
	if !strings.HasPrefix(r.RequestURI, "/") {
		refuse(w, http.StatusBadRequest, "send a path, such as /cloud/project/PROJECT_ID/instance, not a whole address")
		return
	}
	if slices.Contains(strings.Split(r.URL.Path, "/"), "..") {
		refuse(w, http.StatusBadRequest, "a path with .. is refused; give the path under %s as it is", p.apiAddress)
		return
	}
	body, err := io.ReadAll(r.Body)
	if err != nil {
		refuse(w, http.StatusBadRequest, "the request's body could not be read: %v", err)
		return
	}
	if p.changesTheDeskItself(r, body) {
		refuse(w, http.StatusForbidden, "this would change your systems desk itself; the systems desk is managed by its own guide")
		return
	}
	target := p.target(r.URL.EscapedPath())
	if r.URL.RawQuery != "" {
		target += "?" + r.URL.RawQuery
	}
	var reader io.Reader
	if len(body) > 0 {
		reader = bytes.NewReader(body)
	}
	out, err := http.NewRequestWithContext(r.Context(), r.Method, target, reader)
	if err != nil {
		refuse(w, http.StatusBadRequest, "%v", err)
		return
	}
	copyHeaders(out.Header, r.Header)
	if err := p.signer.sign(out, body); err != nil {
		refuse(w, http.StatusBadGateway, "the request could not be signed: %v", stripURLFromError(err))
		return
	}
	response, err := p.client.Do(out)
	if err != nil {
		refuse(w, http.StatusBadGateway, "the provider did not answer: %v", stripURLFromError(err))
		return
	}
	defer response.Body.Close()
	copyHeaders(w.Header(), response.Header)
	w.WriteHeader(response.StatusCode)
	io.Copy(w, response.Body)
}
