package main

import (
	"bufio"
	"crypto/sha1"
	"encoding/hex"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"testing"
)

const (
	ovhApplicationKey    = "applicationkey00"
	ovhApplicationSecret = "applicationsecret0000000000000000"
	ovhConsumerKey       = "consumerkey00000000000000000000000"
	ovhToken             = ovhApplicationKey + ":" + ovhApplicationSecret + ":" + ovhConsumerKey
	// OVHcloud's clock in the stand-in, far from the test machine's, so a
	// signer that used its own clock would fail.
	ovhStandInTime = 1366560945
)

// The expected values were computed outside Go, with
// printf '%s' 'SECRET+CONSUMER+METHOD+URL+BODY+TIME' | shasum -a 1,
// from OVHcloud's formula in "First steps with the OVHcloud API".
func TestOVHcloudSignatureFollowsOVHcloudsFormula(t *testing.T) {
	cases := []struct{ method, url, body, want string }{
		{"GET", "https://api.us.ovhcloud.com/1.0/cloud/project/0123/instance?region=US-EAST-VA-1", "", "$1$c46024249d818ffb5904025bbf08c88f487cba58"},
		{"POST", "https://api.us.ovhcloud.com/1.0/cloud/project/0123/instance", `{"name":"app001"}`, "$1$62bfe184bac721951e2eb02d6db5e3ac593af79a"},
	}
	for _, c := range cases {
		got := ovhcloudSignature("applicationsecret0000000000000000", "consumerkey00000000000000000000000", c.method, c.url, []byte(c.body), "1366560945")
		if got != c.want {
			t.Errorf("%s %s: got %s, want %s", c.method, c.url, got, c.want)
		}
	}
}

// ovhStandIn plays OVHcloud's API under /1.0/: it answers /auth/time with
// its own clock and checks every other request's signature as OVHcloud
// does, then records what it received.
type ovhStandIn struct {
	server   *httptest.Server
	received []*http.Request
	bodies   []string
}

func newOVHStandIn(t *testing.T) *ovhStandIn {
	s := &ovhStandIn{}
	s.server = httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/1.0/auth/time" {
			fmt.Fprint(w, ovhStandInTime)
			return
		}
		body, _ := io.ReadAll(r.Body)
		full := "https://" + r.Host + r.URL.RequestURI()
		sum := sha1.Sum([]byte(ovhApplicationSecret + "+" + ovhConsumerKey + "+" + r.Method + "+" + full + "+" + string(body) + "+" + r.Header.Get("X-Ovh-Timestamp")))
		// OVHcloud refuses a timestamp far from its own clock; a few seconds
		// pass during a test.
		timestamp, _ := strconv.Atoi(r.Header.Get("X-Ovh-Timestamp"))
		if r.Header.Get("X-Ovh-Application") != ovhApplicationKey || r.Header.Get("X-Ovh-Consumer") != ovhConsumerKey ||
			r.Header.Get("X-Ovh-Signature") != "$1$"+hex.EncodeToString(sum[:]) ||
			timestamp < ovhStandInTime || timestamp > ovhStandInTime+10 {
			// A wrong Application Secret: OVHcloud answered so on a real
			// project, 2026-11-12.
			w.WriteHeader(http.StatusBadRequest)
			fmt.Fprint(w, `{"message":"Invalid signature"}`)
			return
		}
		if strings.Contains(r.URL.Path, "/other-project/") {
			// A path outside the access rules, as OVHcloud answered on a
			// real project, 2026-11-12.
			w.WriteHeader(http.StatusForbidden)
			fmt.Fprint(w, `{"class":"Client::Forbidden","message":"This call has not been granted"}`)
			return
		}
		s.received = append(s.received, r)
		s.bodies = append(s.bodies, string(body))
		switch r.URL.Path {
		case "/1.0/moved":
			http.Redirect(w, r, "https://example.com/elsewhere", http.StatusFound)
		default:
			w.Header().Set("X-Pagination-Cursor-Next", "next-page")
			if r.Method == http.MethodPost {
				w.WriteHeader(http.StatusCreated)
			}
			fmt.Fprint(w, `[]`)
		}
	}))
	t.Cleanup(s.server.Close)
	return s
}

func (s *ovhStandIn) address() string { return s.server.URL + "/1.0/" }

func (s *ovhStandIn) addresses() map[string]*regexp.Regexp {
	return map[string]*regexp.Regexp{"ovhcloud_signed_requests": regexp.MustCompile("^" + regexp.QuoteMeta(s.address()) + "$")}
}

func startAPIProxy(t *testing.T, standIn *ovhStandIn) string {
	t.Helper()
	credential := signingCredential{Authentication: "ovhcloud_signed_requests", APIAddress: standIn.address(), Token: ovhToken}
	proxy, err := newAPIProxy(credential, standIn.addresses(), standIn.server.Client())
	if err != nil {
		t.Fatal(err)
	}
	server := httptest.NewServer(proxy)
	t.Cleanup(server.Close)
	return server.URL
}

func TestAPIProxySignsEachRequestAndForwardsItToTheAPIAddress(t *testing.T) {
	standIn := newOVHStandIn(t)
	proxy := startAPIProxy(t, standIn)

	request, _ := http.NewRequest(http.MethodPost, proxy+"/cloud/project/0123/instance?region=US-EAST-VA-1", strings.NewReader(`{"name":"app001"}`))
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("Authorization", "Bearer something-else")
	request.Header.Set("X-Ovh-Signature", "$1$made-up")
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		t.Fatal(err)
	}
	answer, _ := io.ReadAll(response.Body)
	response.Body.Close()
	if response.StatusCode != http.StatusCreated || string(answer) != "[]" || response.Header.Get("X-Pagination-Cursor-Next") != "next-page" {
		t.Fatalf("want the provider's own answer with its headers, got HTTP %d %q", response.StatusCode, answer)
	}
	if len(standIn.received) != 1 {
		t.Fatalf("the provider received %d signed requests, want 1", len(standIn.received))
	}
	got := standIn.received[0]
	if got.URL.RequestURI() != "/1.0/cloud/project/0123/instance?region=US-EAST-VA-1" || standIn.bodies[0] != `{"name":"app001"}` ||
		got.Header.Get("Content-Type") != "application/json" || got.Header.Get("Authorization") != "" {
		t.Fatalf("the provider got %s %q with Content-Type %q and Authorization %q",
			got.URL.RequestURI(), standIn.bodies[0], got.Header.Get("Content-Type"), got.Header.Get("Authorization"))
	}

	// A redirect goes back to the caller; the signed headers never follow it.
	noRedirects := &http.Client{CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	response, err = noRedirects.Get(proxy + "/moved")
	if err != nil {
		t.Fatal(err)
	}
	response.Body.Close()
	if response.StatusCode != http.StatusFound || len(standIn.received) != 2 {
		t.Fatalf("want the redirect passed back, got HTTP %d after %d requests", response.StatusCode, len(standIn.received))
	}
}

func TestAPIProxyRefusesAWholeAddressAndAPathThatClimbsUp(t *testing.T) {
	standIn := newOVHStandIn(t)
	proxy := startAPIProxy(t, standIn)
	for _, target := range []string{"http://example.com/cloud/project", "/cloud/project/0123/../../../me"} {
		connection, err := net.Dial("tcp", strings.TrimPrefix(proxy, "http://"))
		if err != nil {
			t.Fatal(err)
		}
		fmt.Fprintf(connection, "GET %s HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n", target)
		response, err := http.ReadResponse(bufio.NewReader(connection), nil)
		if err != nil {
			t.Fatal(err)
		}
		response.Body.Close()
		connection.Close()
		if response.StatusCode != http.StatusBadRequest {
			t.Errorf("%s: want HTTP 400, got %d", target, response.StatusCode)
		}
	}
	if len(standIn.received) != 0 {
		t.Fatalf("a refused request reached the provider")
	}
}

func TestSigningCredentialGoesOnlyToAProviderGuidesAddress(t *testing.T) {
	cases := []struct {
		name       string
		credential signingCredential
		want       string
	}{
		{"another host", signingCredential{"ovhcloud_signed_requests", "https://api.example.com/1.0/", ovhToken}, "not a provider guide's API address"},
		{"an unknown way of signing", signingCredential{"made_up", "https://api.us.ovhcloud.com/1.0/", ovhToken}, "not a way of signing requests"},
		{"two parts", signingCredential{"ovhcloud_signed_requests", "https://api.us.ovhcloud.com/1.0/", ovhApplicationKey + ":" + ovhConsumerKey}, "it needs 3"},
		{"a space in a part", signingCredential{"ovhcloud_signed_requests", "https://api.us.ovhcloud.com/1.0/", "a b:c:d"}, "the Application Key has a character"},
	}
	for _, c := range cases {
		_, err := newAPIProxy(c.credential, signingAPIAddresses, &http.Client{})
		if err == nil || !strings.Contains(err.Error(), c.want) {
			t.Errorf("%s: want a refusal containing %q, got %v", c.name, c.want, err)
		}
	}
}

// useOVHcloud switches the harness's settings to OVHcloud, with the
// stand-in as the guide's only API address, and commits the change.
func useOVHcloud(h *harness, standIn *ovhStandIn) {
	h.t.Helper()
	path := filepath.Join(h.e.directory, projectSettingsFile)
	text, _ := os.ReadFile(path)
	text = []byte(strings.Replace(string(text), h.provider.URL+"/v1/", standIn.address(), 1))
	text = []byte(strings.Replace(string(text), "systems_desk_provider_api_authentication: token_in_a_header", "systems_desk_provider_api_authentication: ovhcloud_signed_requests", 1))
	writeFile(h.t, path, string(text))
	h.e.signingAPIAddresses = standIn.addresses()
	httpClient = standIn.server.Client()
	h.commitAll("Use OVHcloud")
}

func TestPersonalTokenForOVHcloudTakesThreeValuesChecksThemSignedAndFillsTheAPIProxy(t *testing.T) {
	h := newHarness(t, false, false)
	standIn := newOVHStandIn(t)
	useOVHcloud(h, standIn)
	h.answers = []string{ovhApplicationKey, ovhApplicationSecret, ovhConsumerKey}
	if err := runPersonalToken(h.e, []string{"server-provider", "--server-listing-path", "cloud/project/0123/instance"}); err != nil {
		t.Fatalf("%v\n%s", err, h.out)
	}
	if len(standIn.received) != 1 || standIn.received[0].URL.Path != "/1.0/cloud/project/0123/instance" {
		t.Fatal("the command must check the credential with one signed listing at the provider")
	}
	if h.proxy["server-provider"] != ovhToken {
		t.Fatalf("the root step got %q", h.proxy["server-provider"])
	}
	h.requireNoSecretInOutput(ovhApplicationSecret, ovhConsumerKey)
	// One word for OVHcloud's three values: credential, as its page and the guide say.
	for _, want := range []string{"Your server provider credential lets", "The provider accepted the new credential:",
		"Your coding agent uses the new credential from now on."} {
		if !strings.Contains(h.out.String(), want) {
			t.Errorf("the output lacks %q:\n%s", want, h.out.String())
		}
	}
	if strings.Contains(h.out.String(), "token:") || strings.Contains(h.out.String(), "provider token") {
		t.Errorf("the output calls the credential a token:\n%s", h.out.String())
	}

	// A wrong secret fails the check, nothing changes, and the refusal says
	// which values to check.
	h.proxy = map[string]string{}
	h.answers = []string{ovhApplicationKey, "wrongsecret", ovhConsumerKey}
	err := runPersonalToken(h.e, []string{"server-provider", "--server-listing-path", "cloud/project/0123/instance"})
	if err == nil || !strings.Contains(err.Error(), "the new credential failed its check, so nothing changed") ||
		!strings.Contains(err.Error(), "HTTP 400: Invalid signature. OVHcloud could not verify the request's signature") ||
		!strings.Contains(err.Error(), "Check the Application Secret first, then the Consumer Key") || len(h.proxy) != 0 {
		t.Fatalf("want a failed check that changes nothing and names the values to check, got %v", err)
	}

	// A project outside the credential's access rules: the refusal says what to do.
	h.answers = []string{ovhApplicationKey, ovhApplicationSecret, ovhConsumerKey}
	err = runPersonalToken(h.e, []string{"server-provider", "--server-listing-path", "cloud/project/other-project/instance"})
	if err == nil || !strings.Contains(err.Error(), "HTTP 403: This call has not been granted. The credential works, but its access rules do not cover") ||
		len(h.proxy) != 0 {
		t.Fatalf("want a refusal that explains the access rules, got %v", err)
	}

	// A provider whose requests are signed takes no token header.
	h.answers = []string{ovhApplicationKey, ovhApplicationSecret, ovhConsumerKey}
	if err := runPersonalToken(h.e, []string{"server-provider", "--server-listing-path", "cloud/project/0123/instance", "--token-header", "X-Auth-Token"}); err == nil {
		t.Fatal("--token-header must be refused for a signed provider")
	}
}

// The error codes are those OVHcloud's own Python client reads (ovh/client.py);
// only the two messages were seen from OVHcloud itself.
func TestOVHcloudRefusalsSayWhichValueToCheck(t *testing.T) {
	for _, c := range []struct{ errorCode, message, want string }{
		{"", "Invalid signature", "Check the Application Secret first, then the Consumer Key"},
		{"", "This call has not been granted", "its access rules do not cover"},
		{"NOT_GRANTED_CALL", "", "its access rules do not cover"},
		{"INVALID_KEY", "", "Check that you pasted the Application Key"},
		{"INVALID_CREDENTIAL", "", "Check the Consumer Key; if it is right, make a new credential"},
		{"NOT_CREDENTIAL", "", "Check the Consumer Key; if it is right, make a new credential"},
		{"", "Internal server error", ""},
	} {
		got := ovhcloudRefusalAdvice(c.errorCode, c.message)
		if (c.want == "") != (got == "") || !strings.Contains(got, c.want) {
			t.Errorf("%q %q: got %q, want %q", c.errorCode, c.message, got, c.want)
		}
	}
}

func TestPersonalTokenRefusesAnAuthenticationSettingItDoesNotKnow(t *testing.T) {
	h := newHarness(t, false, false)
	path := filepath.Join(h.e.directory, projectSettingsFile)
	text, _ := os.ReadFile(path)
	writeFile(t, path, strings.Replace(string(text), "  systems_desk_provider_api_authentication: token_in_a_header\n", "", 1))
	h.answers = []string{providerToken}
	err := runPersonalToken(h.e, []string{"server-provider", "--server-listing-path", "servers"})
	if err == nil || !strings.Contains(err.Error(), "systems_desk_provider_api_authentication") || len(h.answers) != 1 {
		t.Fatalf("want a refusal before the prompt, got %v", err)
	}
}

func TestSecretsTakesUtil01sOVHcloudCredentialAsThreeValues(t *testing.T) {
	h := newHarness(t, false, false)
	standIn := newOVHStandIn(t)
	h.vault.referenced = []string{"util01_provider_api_token"}
	useOVHcloud(h, standIn)
	h.answers = []string{"restoreapp000000", "restoresecret0000000000000000000", "restoreconsumer00000000000000000"}
	if err := runSecrets(h.e, nil); err != nil {
		t.Fatalf("secrets: %v\n%s", err, h.out)
	}
	if got := h.vault.values["util01_provider_api_token"]; got != "restoreapp000000:restoresecret0000000000000000000:restoreconsumer00000000000000000" {
		t.Fatalf("saved %q", got)
	}
	if !strings.Contains(h.out.String(), "util01's credential") {
		t.Fatalf("the step must name the guide's link:\n%s", h.out)
	}
}

// headerStandIn plays a provider that takes a token in a header: it records
// what it received.
func headerStandIn(t *testing.T) (*httptest.Server, *[]*http.Request) {
	t.Helper()
	var received []*http.Request
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		received = append(received, r)
		if r.URL.Path == "/v1/moved" {
			http.Redirect(w, r, "https://example.com/elsewhere", http.StatusFound)
			return
		}
		fmt.Fprint(w, `{"servers":[]}`)
	}))
	t.Cleanup(server.Close)
	return server, &received
}

func TestHeaderTokenFileHoldsTheLineThePersonalTokenCommandWrites(t *testing.T) {
	dir := t.TempDir()
	for _, c := range []struct{ line, header, value string }{
		{`proxy_set_header Authorization "Bearer abc.DEF_123~+/=:-";` + "\n", "Authorization", "Bearer abc.DEF_123~+/=:-"},
		{`proxy_set_header X-Auth-Token "scw-secret";` + "\n", "X-Auth-Token", "scw-secret"},
	} {
		path := filepath.Join(dir, "token.conf")
		os.WriteFile(path, []byte(c.line), 0o600)
		signer, err := readHeaderTokenSigner(path)
		if err != nil || signer.header != c.header || signer.value != c.value {
			t.Errorf("%q: got %+v, %v", c.line, signer, err)
		}
	}
	for _, bad := range []string{"", `proxy_set_header Authorization "a" "b";`, "proxy_pass http://elsewhere/;\n", `proxy_set_header Authorization "x";` + "\nproxy_pass http://elsewhere/;\n"} {
		path := filepath.Join(dir, "bad.conf")
		os.WriteFile(path, []byte(bad), 0o600)
		if _, err := readHeaderTokenSigner(path); err == nil {
			t.Errorf("%q must be refused", bad)
		}
	}
}

func TestHeaderTokenProxyAddsTheTokenAndForwardsToTheProviderAddress(t *testing.T) {
	for _, c := range []struct{ header, value string }{{"Authorization", "Bearer hetzner-token"}, {"X-Auth-Token", "scaleway-token"}} {
		standIn, received := headerStandIn(t)
		proxy := httptest.NewServer(newHeaderTokenProxy(standIn.URL+"/v1/", headerTokenSigner{c.header, c.value}, standIn.Client()))
		defer proxy.Close()

		request, _ := http.NewRequest(http.MethodGet, proxy.URL+"/servers?per_page=1", nil)
		request.Header.Set(c.header, "agents-own-value")
		request.Header.Set("Cookie", "x=1")
		response, err := http.DefaultClient.Do(request)
		if err != nil {
			t.Fatal(err)
		}
		answer, _ := io.ReadAll(response.Body)
		response.Body.Close()
		if response.StatusCode != http.StatusOK || string(answer) != `{"servers":[]}` || len(*received) != 1 {
			t.Fatalf("want the provider's answer, got HTTP %d %q after %d requests", response.StatusCode, answer, len(*received))
		}
		got := (*received)[0]
		if got.URL.RequestURI() != "/v1/servers?per_page=1" || got.Header.Get(c.header) != c.value || got.Header.Get("Cookie") != "" || got.ProtoMajor < 1 {
			t.Fatalf("the provider got %s with %s %q and Cookie %q", got.URL.RequestURI(), c.header, got.Header.Get(c.header), got.Header.Get("Cookie"))
		}

		// A redirect goes back to the caller; the token never follows it.
		noRedirects := &http.Client{CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
		response, err = noRedirects.Get(proxy.URL + "/moved")
		if err != nil {
			t.Fatal(err)
		}
		response.Body.Close()
		if response.StatusCode != http.StatusFound || len(*received) != 2 {
			t.Fatalf("want the redirect passed back, got HTTP %d", response.StatusCode)
		}
	}
}

func TestCloudflareTokenGoesOnlyToCloudflaresAddressAndThePathStaysUnderIt(t *testing.T) {
	standIn, received := headerStandIn(t)
	// The test stands in for api.cloudflare.com/client/v4/ with its own address.
	proxy := httptest.NewServer(newHeaderTokenProxy(standIn.URL+"/v1/", headerTokenSigner{"Authorization", "Bearer cloudflare-token"}, standIn.Client()))
	defer proxy.Close()
	response, err := http.Get(proxy.URL + "/zones?per_page=1")
	if err != nil {
		t.Fatal(err)
	}
	response.Body.Close()
	if response.StatusCode != http.StatusOK || (*received)[0].Header.Get("Authorization") != "Bearer cloudflare-token" || (*received)[0].URL.Path != "/v1/zones" {
		t.Fatalf("want /zones forwarded with the token, got HTTP %d", response.StatusCode)
	}
	// A path that climbs out of the address is refused, as for a signed provider.
	conn, _ := net.Dial("tcp", strings.TrimPrefix(proxy.URL, "http://"))
	fmt.Fprint(conn, "GET /../../other HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
	line, _ := bufio.NewReader(conn).ReadString('\n')
	conn.Close()
	if !strings.Contains(line, "400") || len(*received) != 1 {
		t.Fatalf("want a refusal of a path with .., got %q after %d requests", line, len(*received))
	}
	if cloudflareAPIAddress != "https://api.cloudflare.com/client/v4/" {
		t.Fatal("the Cloudflare token goes only to Cloudflare's API address")
	}
}

func TestProxyRefusesAProviderAddressNoProviderGuideGives(t *testing.T) {
	t.Setenv("CREDENTIALS_DIRECTORY", t.TempDir())
	err := runProviderAPIProxy([]string{"--provider-api-url", "https://attacker.example/v1/"})
	if err == nil || !strings.Contains(err.Error(), "not a provider guide's API address") {
		t.Fatalf("got %v", err)
	}
}

// The paths and bodies below are the shapes of each provider's delete and
// rebuild requests (Hetzner, DigitalOcean, Vultr, Scaleway, OVHcloud, AWS
// and Google Cloud), with the desk's own server ID at the provider.
func TestProxyRefusesARequestThatWouldChangeTheDeskItself(t *testing.T) {
	const deskID = "4242424242"
	standIn, received := headerStandIn(t)
	proxy := newHeaderTokenProxy(standIn.URL+"/v1/", headerTokenSigner{"Authorization", "Bearer token"}, standIn.Client())
	proxy.deskServerID = deskID
	server := httptest.NewServer(proxy)
	defer server.Close()
	send := func(method, path, body string) (int, string) {
		request, _ := http.NewRequest(method, server.URL+path, strings.NewReader(body))
		response, err := http.DefaultClient.Do(request)
		if err != nil {
			t.Fatal(err)
		}
		defer response.Body.Close()
		answer, _ := io.ReadAll(response.Body)
		return response.StatusCode, string(answer)
	}
	refused := []struct{ name, method, path, body string }{
		{"Hetzner delete", "DELETE", "/servers/" + deskID, ""},
		{"Hetzner rebuild", "POST", "/servers/" + deskID + "/actions/rebuild", `{"image":"debian-13"}`},
		{"DigitalOcean delete", "DELETE", "/droplets/" + deskID, ""},
		{"DigitalOcean rebuild", "POST", "/droplets/" + deskID + "/actions", `{"type":"rebuild","image":"debian-13-x64"}`},
		{"Vultr reinstall", "POST", "/instances/" + deskID + "/reinstall", ""},
		{"Scaleway action", "POST", "/servers/" + deskID + "/action", `{"action":"terminate"}`},
		{"OVHcloud delete", "DELETE", "/cloud/project/PROJECT/instance/" + deskID, ""},
		{"OVHcloud reinstall", "POST", "/cloud/project/PROJECT/instance/" + deskID + "/reinstall", `{"imageId":"x"}`},
		{"a JSON body that names it", "POST", "/servers/bulk", `{"servers":["1","` + deskID + `"]}`},
		{"a JSON number that names it", "POST", "/servers/bulk", `{"server_id":` + deskID + `}`},
		{"AWS terminate", "POST", "/", "Action=TerminateInstances&InstanceId.1=" + deskID},
		{"Google delete", "DELETE", "/projects/P/zones/Z/instances/" + deskID, ""},
	}
	for _, c := range refused {
		before := len(*received)
		status, answer := send(c.method, c.path, c.body)
		if status != http.StatusForbidden || !strings.Contains(answer, "this would change your desk itself; the desk is managed by its own guide") || len(*received) != before {
			t.Errorf("%s: want a refusal and nothing sent on, got HTTP %d %q after %d requests", c.name, status, answer, len(*received)-before)
		}
	}
	passed := []struct{ name, method, path, body string }{
		{"a GET of the desk", "GET", "/servers/" + deskID, ""},
		{"a GET of the listing", "GET", "/servers?per_page=50", ""},
		{"a delete of another server", "DELETE", "/servers/4242424243", ""},
		{"a delete of a server whose ID only starts like the desk's", "DELETE", "/servers/" + deskID + "9", ""},
		{"a create", "POST", "/servers", `{"name":"app002","size":42424242420}`},
	}
	for _, c := range passed {
		before := len(*received)
		status, answer := send(c.method, c.path, c.body)
		if status != http.StatusOK || len(*received) != before+1 {
			t.Errorf("%s: want it passed on, got HTTP %d %q", c.name, status, answer)
		}
	}
}

func TestProxyNeedsTheDesksServerID(t *testing.T) {
	directory := t.TempDir()
	t.Setenv("CREDENTIALS_DIRECTORY", directory)
	os.WriteFile(filepath.Join(directory, "provider-api-token"), []byte(`proxy_set_header Authorization "Bearer t";`+"\n"), 0o600)
	err := runProviderAPIProxy([]string{"--provider-api-url", providerGuideAPIAddresses[0]})
	if err == nil || !strings.Contains(err.Error(), "desk's own server ID") {
		t.Fatalf("got %v", err)
	}
}
