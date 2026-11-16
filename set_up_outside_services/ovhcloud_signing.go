package main

// OVHcloud's API signs each request with the application's secret, as
// OVHcloud's "First steps with the OVHcloud API" gives it:
//
//	"$1$" + SHA1_HEX(AS+"+"+CK+"+"+METHOD+"+"+QUERY+"+"+BODY+"+"+TSTAMP)
//
// where QUERY is the whole URL and TSTAMP is OVHcloud's own clock, from
// GET /auth/time. The request carries the application key, the consumer key,
// the timestamp and the signature in the X-Ovh-* headers; the application
// secret never leaves the desk.

import (
	"crypto/sha1"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"
)

type ovhcloudSigner struct {
	apiAddress                                     string
	applicationKey, applicationSecret, consumerKey string
	client                                         *http.Client
	now                                            func() time.Time

	mutex sync.Mutex
	// clockDifference is OVHcloud's clock minus this desk's, read once, as
	// OVHcloud's own client libraries do. Reason: the desk keeps its clock
	// with the network time service, so the difference stays put.
	clockDifference *time.Duration
}

func newOVHcloudSigner(apiAddress string, parts []string, client *http.Client) (requestSigner, error) {
	return &ovhcloudSigner{apiAddress: apiAddress, applicationKey: parts[0], applicationSecret: parts[1], consumerKey: parts[2], client: client, now: time.Now}, nil
}

func ovhcloudSignature(applicationSecret, consumerKey, method, fullURL string, body []byte, timestamp string) string {
	sum := sha1.Sum([]byte(strings.Join([]string{applicationSecret, consumerKey, method, fullURL, string(body), timestamp}, "+")))
	return "$1$" + hex.EncodeToString(sum[:])
}

func (s *ovhcloudSigner) sign(request *http.Request, body []byte) error {
	timestamp, err := s.providerTime()
	if err != nil {
		return err
	}
	request.Header.Set("X-Ovh-Application", s.applicationKey)
	request.Header.Set("X-Ovh-Consumer", s.consumerKey)
	request.Header.Set("X-Ovh-Timestamp", timestamp)
	request.Header.Set("X-Ovh-Signature", ovhcloudSignature(s.applicationSecret, s.consumerKey, request.Method, request.URL.String(), body, timestamp))
	return nil
}

// providerTime is OVHcloud's time now, in seconds, as /auth/time counts.
func (s *ovhcloudSigner) providerTime() (string, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	if s.clockDifference == nil {
		response, err := s.client.Get(s.apiAddress + "auth/time")
		if err != nil {
			return "", err
		}
		defer response.Body.Close()
		text, err := io.ReadAll(io.LimitReader(response.Body, 64))
		if err != nil {
			return "", err
		}
		seconds, err := strconv.ParseInt(strings.TrimSpace(string(text)), 10, 64)
		if response.StatusCode != http.StatusOK || err != nil {
			return "", fmt.Errorf("%sauth/time answered HTTP %d without a time", s.apiAddress, response.StatusCode)
		}
		difference := time.Unix(seconds, 0).Sub(s.now())
		s.clockDifference = &difference
	}
	return strconv.FormatInt(s.now().Add(*s.clockDifference).Unix(), 10), nil
}

// readOVHcloudRefusal reads OVHcloud's error answer, {"errorCode", "message"}.
func readOVHcloudRefusal(answer []byte) (string, string) {
	var refusal struct {
		ErrorCode string `json:"errorCode"`
		Message   string `json:"message"`
	}
	_ = json.Unmarshal(answer, &refusal)
	return refusal.Message, ovhcloudRefusalAdvice(refusal.ErrorCode, refusal.Message)
}

// ovhcloudRefusalAdvice turns OVHcloud's common refusals of a credential into
// what the person checks or does. OVHcloud names the refusal in errorCode
// (the codes OVHcloud's own Python client reads) and in its message; a real
// wrong Application Secret answered HTTP 400 "Invalid signature", and a path
// outside the access rules HTTP 403 "This call has not been granted".
func ovhcloudRefusalAdvice(errorCode, message string) string {
	message = strings.ToLower(message)
	switch {
	case strings.Contains(message, "signature"):
		return "OVHcloud could not verify the request's signature, which the three values make together. " +
			"Check the Application Secret first, then the Consumer Key, and that all three come from the same credential"
	case errorCode == "NOT_GRANTED_CALL" || strings.Contains(message, "not been granted"):
		return "The credential works, but its access rules do not cover this project's server listing. " +
			"Check the project ID in --server-listing-path; if it is right, make a new credential from the link your coding agent gives you, " +
			"from the OVHcloud guide with this project's ID, and run this command again"
	case errorCode == "INVALID_KEY" || strings.Contains(message, "application key"):
		return "OVHcloud does not know this Application Key. Check that you pasted the Application Key, from the same credential as the other two values"
	case errorCode == "INVALID_CREDENTIAL" || errorCode == "NOT_CREDENTIAL" || strings.Contains(message, "credential"):
		return "OVHcloud does not accept this Consumer Key: it is mistyped, or the credential was deleted, its validity ended, " +
			"or its page was left before Create keys finished. Check the Consumer Key; if it is right, make a new credential " +
			"from the link your coding agent gives you, with Validity: Unlimited, and run this command again"
	}
	return ""
}
