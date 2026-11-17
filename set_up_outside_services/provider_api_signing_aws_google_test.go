package main

import (
	"bytes"
	"context"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/json"
	"encoding/pem"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"testing"
	"time"
)

// AWS's published example, "Example: GET Object" in the Amazon S3 API
// Reference's "Signature Calculations for the Authorization Header:
// Transferring Payload in a Single Chunk (AWS Signature Version 4)",
// fetched 2026-11-12: its credentials, request and signature.
func TestAWSSignatureMatchesAWSsPublishedExample(t *testing.T) {
	request, _ := http.NewRequest(http.MethodGet, "https://examplebucket.s3.amazonaws.com/test.txt", nil)
	request.Header.Set("Range", "bytes=0-9")
	request.Header.Set("X-Amz-Content-Sha256", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
	request.Header.Set("X-Amz-Date", "20130524T000000Z")
	got := awsSignature(request, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
		[]string{"host", "range", "x-amz-content-sha256", "x-amz-date"}, "20130524T000000Z", "us-east-1", "s3",
		"wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
	if want := "f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"; got != want {
		t.Fatalf("got %s, want AWS's %s", got, want)
	}
}

// clientThatReaches sends every request, whatever its host, to server, so a
// test can use a provider's real address. The stand-in's certificate does
// not name the provider's host, so the client skips the name check.
func clientThatReaches(server *httptest.Server) *http.Client {
	transport := server.Client().Transport.(*http.Transport).Clone()
	address := server.Listener.Addr().String()
	transport.DialContext = func(ctx context.Context, network, _ string) (net.Conn, error) {
		return (&net.Dialer{}).DialContext(ctx, network, address)
	}
	transport.TLSClientConfig.InsecureSkipVerify = true
	return &http.Client{Transport: transport}
}

const (
	awsAccessKeyID     = "AKIAIOSFODNN7EXAMPLE"
	awsSecretAccessKey = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
	awsToken           = awsAccessKeyID + ":" + awsSecretAccessKey
	awsAPIAddress      = "https://ec2.eu-north-1.amazonaws.com/"
)

// awsStandIn plays EC2 in eu-north-1: it checks each request's Signature
// Version 4 as AWS does, for the request it received, and answers as EC2
// answers a wrong signature.
type awsStandIn struct {
	server   *httptest.Server
	received []*http.Request
	bodies   []string
}

var awsAuthorizationPattern = regexp.MustCompile(`^AWS4-HMAC-SHA256 Credential=([^/]+)/(\d{8})/([^/]+)/([^/]+)/aws4_request, SignedHeaders=([a-z0-9;-]+), Signature=([0-9a-f]{64})$`)

func newAWSStandIn(t *testing.T) *awsStandIn {
	s := &awsStandIn{}
	s.server = httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		match := awsAuthorizationPattern.FindStringSubmatch(r.Header.Get("Authorization"))
		valid := match != nil && match[1] == awsAccessKeyID && match[3] == "eu-north-1" && match[4] == "ec2" &&
			r.Host == "ec2.eu-north-1.amazonaws.com" && r.Header.Get("X-Amz-Content-Sha256") == sha256Hex(body) &&
			strings.HasPrefix(r.Header.Get("X-Amz-Date"), match[2])
		if valid {
			check := r.Clone(context.Background())
			check.URL.Host = r.Host
			valid = awsSignature(check, sha256Hex(body), strings.Split(match[5], ";"), r.Header.Get("X-Amz-Date"), "eu-north-1", "ec2", awsSecretAccessKey) == match[6] &&
				strings.Contains(match[5], "host") && strings.Contains(match[5], "x-amz-date")
		}
		if !valid {
			w.WriteHeader(http.StatusForbidden)
			fmt.Fprint(w, `<?xml version="1.0" encoding="UTF-8"?><Response><Errors><Error><Code>SignatureDoesNotMatch</Code><Message>The request signature we calculated does not match the signature you provided.</Message></Error></Errors><RequestID>1</RequestID></Response>`)
			return
		}
		s.received = append(s.received, r)
		s.bodies = append(s.bodies, string(body))
		fmt.Fprint(w, `<DescribeInstancesResponse xmlns="http://ec2.amazonaws.com/doc/2016-11-15/"><reservationSet/></DescribeInstancesResponse>`)
	}))
	t.Cleanup(s.server.Close)
	return s
}

func TestAPIProxySignsForAWSWithTheRegionAndServiceOfItsAddress(t *testing.T) {
	standIn := newAWSStandIn(t)
	credential := signingCredential{Authentication: "aws_signed_requests", APIAddress: awsAPIAddress, Token: awsToken}
	proxy, err := newAPIProxy(credential, signingAPIAddresses, clientThatReaches(standIn.server))
	if err != nil {
		t.Fatal(err)
	}
	server := httptest.NewServer(proxy)
	t.Cleanup(server.Close)

	// The AWS command-line tool's form: a POST of the query, with its own
	// x-amz-* headers, which the proxy replaces.
	request, _ := http.NewRequest(http.MethodPost, server.URL+"/", strings.NewReader("Action=DescribeInstances&Version=2016-11-15"))
	request.Header.Set("Content-Type", "application/x-www-form-urlencoded; charset=utf-8")
	request.Header.Set("X-Amz-Date", "20000101T000000Z")
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		t.Fatal(err)
	}
	answer, _ := io.ReadAll(response.Body)
	response.Body.Close()
	if response.StatusCode != http.StatusOK || !strings.Contains(string(answer), "DescribeInstancesResponse") {
		t.Fatalf("want EC2's answer, got HTTP %d %s", response.StatusCode, answer)
	}
	// curl's form: a GET with the query in the address.
	response, err = http.Get(server.URL + "/?Action=DescribeRegions&Version=2016-11-15")
	if err != nil {
		t.Fatal(err)
	}
	response.Body.Close()
	if response.StatusCode != http.StatusOK || len(standIn.received) != 2 || standIn.bodies[0] != "Action=DescribeInstances&Version=2016-11-15" ||
		standIn.received[1].URL.RawQuery != "Action=DescribeRegions&Version=2016-11-15" {
		t.Fatalf("want both requests signed and forwarded as sent, got HTTP %d after %d", response.StatusCode, len(standIn.received))
	}
}

func TestAWSCredentialGoesOnlyToEC2(t *testing.T) {
	for _, address := range []string{"https://ec2.eu-north-1.amazonaws.com.example.com/", "https://s3.eu-north-1.amazonaws.com/",
		"http://ec2.eu-north-1.amazonaws.com/", "https://ec2.eu-north-1.amazonaws.com/other/"} {
		_, err := newAPIProxy(signingCredential{"aws_signed_requests", address, awsToken}, signingAPIAddresses, &http.Client{})
		if err == nil || !strings.Contains(err.Error(), "https://ec2.REGION.amazonaws.com/") {
			t.Errorf("%s: want a refusal naming EC2's address, got %v", address, err)
		}
	}
}

func useSigningProvider(h *harness, authentication, apiAddress string, client *http.Client) {
	h.t.Helper()
	path := filepath.Join(h.e.directory, projectSettingsFile)
	text, _ := os.ReadFile(path)
	text = []byte(strings.Replace(string(text), h.provider.URL+"/v1/", apiAddress, 1))
	text = []byte(strings.Replace(string(text), "systems_desk_provider_api_authentication: token_in_a_header", "systems_desk_provider_api_authentication: "+authentication, 1))
	writeFile(h.t, path, string(text))
	h.e.signingAPIAddresses = signingAPIAddresses
	httpClient = client
	h.commitAll("Use " + authentication)
}

func TestPersonalTokenForAWSTakesTwoValuesAndChecksThemSigned(t *testing.T) {
	h := newHarness(t, false, false)
	standIn := newAWSStandIn(t)
	useSigningProvider(h, "aws_signed_requests", awsAPIAddress, clientThatReaches(standIn.server))
	listing := "?Action=DescribeInstances&Version=2016-11-15"
	h.answers = []string{awsAccessKeyID, awsSecretAccessKey}
	if err := runPersonalToken(h.e, []string{"server-provider", "--server-listing-path", listing}); err != nil {
		t.Fatalf("%v\n%s", err, h.out)
	}
	if len(standIn.received) != 1 || h.proxy["server-provider"] != awsToken {
		t.Fatalf("want one signed check and the joined token for the proxy, got %d checks and %q", len(standIn.received), h.proxy["server-provider"])
	}
	h.requireNoSecretInOutput(awsSecretAccessKey)

	h.proxy = map[string]string{}
	h.answers = []string{awsAccessKeyID, "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEXXX"}
	err := runPersonalToken(h.e, []string{"server-provider", "--server-listing-path", listing})
	if err == nil || !strings.Contains(err.Error(), "HTTP 403: The request signature we calculated does not match the signature you provided. AWS could not verify the request's signature. Check the Secret access key") ||
		len(h.proxy) != 0 || strings.Contains(err.Error(), "EXAMPLEXXX") {
		t.Fatalf("want a refusal that names the value to check and shows no secret, got %v", err)
	}
}

// googleStandIn plays Google's token address and Compute Engine and its
// price catalog: the token address checks the JWT's signature with the
// service account's public key, as Google does, and its claims.
type googleStandIn struct {
	server    *httptest.Server
	publicKey *rsa.PublicKey
	mutex     sync.Mutex
	minted    int
	received  []string
}

const googleServiceAccount = "util01-restore-drill@example-project.iam.gserviceaccount.com"

func newGoogleStandIn(t *testing.T) (*googleStandIn, []byte) {
	privateKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	der, _ := x509.MarshalPKCS8PrivateKey(privateKey)
	keyFile, _ := json.MarshalIndent(map[string]string{
		"type": "service_account", "project_id": "example-project", "private_key_id": "0123abcd",
		"private_key":  string(pem.EncodeToMemory(&pem.Block{Type: "PRIVATE KEY", Bytes: der})),
		"client_email": googleServiceAccount, "client_id": "1", "auth_uri": "https://accounts.google.com/o/oauth2/auth",
		"token_uri": "https://oauth2.googleapis.com/token",
	}, "", "  ")
	s := &googleStandIn{publicKey: &privateKey.PublicKey}
	s.server = httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		s.mutex.Lock()
		defer s.mutex.Unlock()
		if r.Host == "oauth2.googleapis.com" && r.URL.Path == "/token" && r.Method == http.MethodPost {
			_ = r.ParseForm()
			if r.Form.Get("grant_type") != "urn:ietf:params:oauth:grant-type:jwt-bearer" || !s.validJWT(r.Form.Get("assertion")) {
				w.WriteHeader(http.StatusBadRequest)
				fmt.Fprint(w, `{"error":"invalid_grant","error_description":"Invalid JWT Signature."}`)
				return
			}
			s.minted++
			fmt.Fprintf(w, `{"access_token":"ya29.standin-%d","expires_in":3599,"token_type":"Bearer"}`, s.minted)
			return
		}
		if r.Header.Get("Authorization") != fmt.Sprintf("Bearer ya29.standin-%d", s.minted) {
			w.WriteHeader(http.StatusUnauthorized)
			fmt.Fprint(w, `{"error":{"code":401,"message":"Request had invalid authentication credentials.","status":"UNAUTHENTICATED"}}`)
			return
		}
		s.received = append(s.received, r.Host+r.URL.RequestURI())
		if strings.Contains(r.URL.Path, "/other-project/") {
			w.WriteHeader(http.StatusForbidden)
			fmt.Fprint(w, `{"error":{"code":403,"message":"Required 'compute.instances.list' permission for 'projects/other-project'","status":"PERMISSION_DENIED"}}`)
			return
		}
		fmt.Fprint(w, `{"items":{}}`)
	}))
	t.Cleanup(s.server.Close)
	return s, keyFile
}

func (s *googleStandIn) validJWT(assertion string) bool {
	parts := strings.Split(assertion, ".")
	if len(parts) != 3 {
		return false
	}
	signature, _ := base64.RawURLEncoding.DecodeString(parts[2])
	digest := sha256.Sum256([]byte(parts[0] + "." + parts[1]))
	if rsa.VerifyPKCS1v15(s.publicKey, crypto.SHA256, digest[:], signature) != nil {
		return false
	}
	var header struct{ Alg string }
	var claims struct {
		Iss, Scope, Aud string
		Iat, Exp        int64
	}
	headerText, _ := base64.RawURLEncoding.DecodeString(parts[0])
	claimsText, _ := base64.RawURLEncoding.DecodeString(parts[1])
	if json.Unmarshal(headerText, &header) != nil || json.Unmarshal(claimsText, &claims) != nil {
		return false
	}
	return header.Alg == "RS256" && claims.Iss == googleServiceAccount && claims.Aud == "https://oauth2.googleapis.com/token" &&
		claims.Scope == "https://www.googleapis.com/auth/compute https://www.googleapis.com/auth/cloud-billing.readonly" &&
		claims.Exp-claims.Iat == 3600
}

// googleToken is SERVER_PROVIDER_API_TOKEN's form of a key file.
func googleToken(keyFile []byte) string {
	var compact bytes.Buffer
	_ = json.Compact(&compact, keyFile)
	return base64.StdEncoding.EncodeToString(compact.Bytes())
}

func TestAPIProxyMakesGoogleAccessTokensAndKeepsThemUntilTheyExpire(t *testing.T) {
	standIn, keyFile := newGoogleStandIn(t)
	credential := signingCredential{Authentication: "google_cloud_service_account_tokens", APIAddress: "https://compute.googleapis.com/compute/v1/", Token: googleToken(keyFile)}
	proxy, err := newAPIProxy(credential, signingAPIAddresses, clientThatReaches(standIn.server))
	if err != nil {
		t.Fatal(err)
	}
	clock := time.Date(2026, 11, 12, 12, 0, 0, 0, time.UTC)
	proxy.signer.(*googleTokenSigner).now = func() time.Time { return clock }
	server := httptest.NewServer(proxy)
	t.Cleanup(server.Close)
	get := func(path string) int {
		response, err := http.Get(server.URL + path)
		if err != nil {
			t.Fatal(err)
		}
		response.Body.Close()
		return response.StatusCode
	}
	if get("/projects/example-project/aggregated/instances") != 200 || get("/cloudbilling/v1/services/6F81-5844-456A/skus?pageSize=5000") != 200 {
		t.Fatalf("want both calls answered, got %v", standIn.received)
	}
	want := []string{"compute.googleapis.com/compute/v1/projects/example-project/aggregated/instances",
		"cloudbilling.googleapis.com/v1/services/6F81-5844-456A/skus?pageSize=5000"}
	if strings.Join(standIn.received, " ") != strings.Join(want, " ") || standIn.minted != 1 {
		t.Fatalf("want %v with one token, got %v with %d", want, standIn.received, standIn.minted)
	}
	// 59 minutes later the token has a minute left, so the proxy makes a new one.
	clock = clock.Add(58 * time.Minute)
	get("/projects/example-project/zones")
	clock = clock.Add(time.Minute)
	if get("/projects/example-project/zones") != 200 || standIn.minted != 2 {
		t.Fatalf("want a new token a minute before the old one expires, got %d tokens", standIn.minted)
	}
}

func TestGoogleKeyFileIsChecked(t *testing.T) {
	_, keyFile := newGoogleStandIn(t)
	for _, c := range []struct{ name, token, want string }{
		{"not base64", "{not base64}", "not a key file's text in base64"},
		{"another JSON", base64.StdEncoding.EncodeToString([]byte(`{"type":"authorized_user"}`)), "not a service account's JSON key file"},
		{"another token address", googleToken([]byte(strings.Replace(string(keyFile), "https://oauth2.googleapis.com/token", "https://example.com/token", 1))), "token_uri"},
	} {
		_, err := newAPIProxy(signingCredential{"google_cloud_service_account_tokens", "https://compute.googleapis.com/compute/v1/", c.token}, signingAPIAddresses, &http.Client{})
		if err == nil || !strings.Contains(err.Error(), c.want) {
			t.Errorf("%s: want %q, got %v", c.name, c.want, err)
		}
	}
}

func TestPersonalTokenForGoogleCloudTakesThePastedKeyFile(t *testing.T) {
	h := newHarness(t, false, false)
	standIn, keyFile := newGoogleStandIn(t)
	useSigningProvider(h, "google_cloud_service_account_tokens", "https://compute.googleapis.com/compute/v1/", clientThatReaches(standIn.server))
	// The person pastes the file as Google wrote it: one line per field.
	h.answers = strings.Split(string(keyFile), "\n")
	if err := runPersonalToken(h.e, []string{"server-provider", "--server-listing-path", "projects/example-project/aggregated/instances?maxResults=1"}); err != nil {
		t.Fatalf("%v\n%s", err, h.out)
	}
	if len(h.answers) != 0 || len(standIn.received) != 1 || h.proxy["server-provider"] != googleToken(keyFile) {
		t.Fatalf("want the whole file read, one check and the base64 token for the proxy, got %d left and %d checks", len(h.answers), len(standIn.received))
	}
	h.requireNoSecretInOutput("PRIVATE KEY")

	h.proxy = map[string]string{}
	h.answers = strings.Split(string(keyFile), "\n")
	err := runPersonalToken(h.e, []string{"server-provider", "--server-listing-path", "projects/other-project/aggregated/instances?maxResults=1"})
	if err == nil || !strings.Contains(err.Error(), "HTTP 403: Required 'compute.instances.list' permission") ||
		!strings.Contains(err.Error(), "give the service account the role your provider guide names") || len(h.proxy) != 0 {
		t.Fatalf("want a refusal that names the role, got %v", err)
	}
}

func TestSecretsTakesUtil01sGoogleKeyFile(t *testing.T) {
	h := newHarness(t, false, false)
	standIn, keyFile := newGoogleStandIn(t)
	h.vault.referenced = []string{"util01_provider_api_token"}
	useSigningProvider(h, "google_cloud_service_account_tokens", "https://compute.googleapis.com/compute/v1/", clientThatReaches(standIn.server))
	h.answers = strings.Split(string(keyFile), "\n")
	if err := runSecrets(h.e, nil); err != nil {
		t.Fatalf("secrets: %v\n%s", err, h.out)
	}
	if got := h.vault.values["util01_provider_api_token"]; got != googleToken(keyFile) {
		t.Fatalf("saved %q", got)
	}
}
