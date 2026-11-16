package main

// Google Cloud takes a short-lived OAuth access token in Authorization:
// Bearer. The proxy makes one from the service account's key with Google's
// "Using OAuth 2.0 for Server to Server Applications": a JWT, signed with
// the key's RSA private key (RS256), whose claims name the service account,
// the scopes, the token address and an hour's validity, is traded at
// https://oauth2.googleapis.com/token for an access token, which the proxy
// keeps until shortly before it expires. The key never leaves the desk.

import (
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/json"
	"encoding/pem"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"
)

const (
	googleTokenAddress = "https://oauth2.googleapis.com/token"
	// The narrowest scopes the provider scripts need: Compute Engine's read
	// and write scope, which has no narrower form that creates servers, and
	// the price catalog's read-only scope. The service account's roles
	// decide what the token may do inside them.
	googleTokenScopes = "https://www.googleapis.com/auth/compute https://www.googleapis.com/auth/cloud-billing.readonly"
	// A token is used until a minute before it expires. Reason: a request
	// signed in its last seconds could reach Google after it expired.
	googleTokenMargin = time.Minute
)

// googleServiceAccountKey is the part of a service account's JSON key file
// the proxy reads.
type googleServiceAccountKey struct {
	Type         string `json:"type"`
	ClientEmail  string `json:"client_email"`
	PrivateKey   string `json:"private_key"`
	PrivateKeyID string `json:"private_key_id"`
	TokenURI     string `json:"token_uri"`
}

// decodeKeyFileToken reads SERVER_PROVIDER_API_TOKEN's form of a key file:
// its text in standard base64, on one line.
func decodeKeyFileToken(token string) ([]byte, error) {
	keyFile, err := base64.StdEncoding.DecodeString(token)
	if err != nil {
		return nil, errors.New("the credential is not a key file's text in base64, as SERVER_PROVIDER_API_TOKEN holds it")
	}
	return keyFile, nil
}

func parseGoogleServiceAccountKey(keyFile []byte) (googleServiceAccountKey, *rsa.PrivateKey, error) {
	var key googleServiceAccountKey
	if json.Unmarshal(keyFile, &key) != nil || key.Type != "service_account" || key.ClientEmail == "" {
		return key, nil, errors.New("this is not a service account's JSON key file: it lacks \"type\": \"service_account\" or client_email. Paste the whole file Google downloaded, from { to }")
	}
	// The token address is fixed. Reason: the signed JWT is itself a
	// credential for an hour, and goes only to Google.
	if key.TokenURI != googleTokenAddress {
		return key, nil, fmt.Errorf("the key file's token_uri is %q; a Google Cloud key file names %s", key.TokenURI, googleTokenAddress)
	}
	block, _ := pem.Decode([]byte(key.PrivateKey))
	if block == nil {
		return key, nil, errors.New("the key file's private_key is not a PEM private key. Paste the whole file Google downloaded")
	}
	parsed, err := x509.ParsePKCS8PrivateKey(block.Bytes)
	privateKey, isRSA := parsed.(*rsa.PrivateKey)
	if err != nil || !isRSA {
		return key, nil, errors.New("the key file's private_key is not an RSA key in PKCS #8, as Google's key files have")
	}
	return key, privateKey, nil
}

func checkGoogleServiceAccountKey(keyFile []byte) error {
	_, _, err := parseGoogleServiceAccountKey(keyFile)
	return err
}

type googleTokenSigner struct {
	key          googleServiceAccountKey
	privateKey   *rsa.PrivateKey
	tokenAddress string
	client       *http.Client
	now          func() time.Time

	mutex       sync.Mutex
	accessToken string
	expires     time.Time
}

func newGoogleTokenSigner(_ string, parts []string, client *http.Client) (requestSigner, error) {
	key, privateKey, err := parseGoogleServiceAccountKey([]byte(parts[0]))
	if err != nil {
		return nil, err
	}
	return &googleTokenSigner{key: key, privateKey: privateKey, tokenAddress: googleTokenAddress, client: client, now: time.Now}, nil
}

func (s *googleTokenSigner) sign(request *http.Request, _ []byte) error {
	token, err := s.token()
	if err != nil {
		return err
	}
	request.Header.Set("Authorization", "Bearer "+token)
	return nil
}

// token returns the kept access token, or a new one when it expires within
// googleTokenMargin. One request at a time makes a new token.
func (s *googleTokenSigner) token() (string, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	if s.accessToken != "" && s.now().Add(googleTokenMargin).Before(s.expires) {
		return s.accessToken, nil
	}
	now := s.now()
	assertion, err := googleJWT(s.key, s.privateKey, now)
	if err != nil {
		return "", err
	}
	form := url.Values{"grant_type": {"urn:ietf:params:oauth:grant-type:jwt-bearer"}, "assertion": {assertion}}
	response, err := s.client.PostForm(s.tokenAddress, form)
	if err != nil {
		return "", fmt.Errorf("Google's token address did not answer: %v", stripURLFromError(err))
	}
	defer response.Body.Close()
	text, _ := io.ReadAll(io.LimitReader(response.Body, 64<<10))
	var answer struct {
		AccessToken      string `json:"access_token"`
		ExpiresIn        int    `json:"expires_in"`
		Error            string `json:"error"`
		ErrorDescription string `json:"error_description"`
	}
	_ = json.Unmarshal(text, &answer)
	if response.StatusCode != http.StatusOK || answer.AccessToken == "" || answer.ExpiresIn <= 0 {
		// Google's error and its description name the refusal and never
		// repeat the assertion.
		return "", fmt.Errorf("Google refused an access token for %s: HTTP %d %s %s", s.key.ClientEmail, response.StatusCode, answer.Error, trimPeriod(answer.ErrorDescription))
	}
	s.accessToken, s.expires = answer.AccessToken, now.Add(time.Duration(answer.ExpiresIn)*time.Second)
	return s.accessToken, nil
}

// googleJWT is the signed assertion Google trades for an access token.
func googleJWT(key googleServiceAccountKey, privateKey *rsa.PrivateKey, now time.Time) (string, error) {
	header, _ := json.Marshal(map[string]string{"alg": "RS256", "typ": "JWT", "kid": key.PrivateKeyID})
	claims, _ := json.Marshal(map[string]any{"iss": key.ClientEmail, "scope": googleTokenScopes, "aud": googleTokenAddress,
		"iat": now.Unix(), "exp": now.Add(time.Hour).Unix()})
	unsigned := base64.RawURLEncoding.EncodeToString(header) + "." + base64.RawURLEncoding.EncodeToString(claims)
	digest := sha256.Sum256([]byte(unsigned))
	signature, err := rsa.SignPKCS1v15(rand.Reader, privateKey, crypto.SHA256, digest[:])
	if err != nil {
		return "", err
	}
	return unsigned + "." + base64.RawURLEncoding.EncodeToString(signature), nil
}

// readGoogleRefusal reads Google's error answer, {"error": {"message", "status"}}.
func readGoogleRefusal(answer []byte) (string, string) {
	var refusal struct {
		Error struct {
			Message string `json:"message"`
			Status  string `json:"status"`
		} `json:"error"`
	}
	_ = json.Unmarshal(answer, &refusal)
	message := refusal.Error.Message
	switch {
	case strings.Contains(message, "has not been used in project") || strings.Contains(message, "is disabled"):
		return message, "The project's Compute Engine API is off. Turn it on at https://console.cloud.google.com/apis/library/compute.googleapis.com for the project, wait a minute, and run this command again"
	case refusal.Error.Status == "PERMISSION_DENIED" || refusal.Error.Status == "FORBIDDEN":
		return message, "The key works, but its service account has no role that lists this project's servers. Check the project ID in --server-listing-path; if it is right, give the service account the role your provider guide names, and run this command again"
	case refusal.Error.Status == "NOT_FOUND":
		return message, "Google knows no such project. Check the project ID in --server-listing-path"
	}
	return message, ""
}
