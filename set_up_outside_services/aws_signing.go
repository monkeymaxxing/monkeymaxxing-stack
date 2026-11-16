package main

// AWS signs each request with Signature Version 4, as AWS's "Create a
// signed AWS API request" gives it: a canonical request (method, path,
// sorted query, the signed headers, the body's SHA-256), a string to sign
// with the date and the credential scope DATE/REGION/SERVICE/aws4_request,
// and an HMAC-SHA256 chain from "AWS4"+secret over the date, the region, the
// service and "aws4_request". The request carries the access key ID, the
// scope, the signed headers' names and the signature in Authorization; the
// secret access key never leaves the desk.

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/xml"
	"fmt"
	"net/http"
	"net/url"
	"regexp"
	"slices"
	"strings"
	"time"
)

// awsServiceAndRegion reads an AWS API host, such as
// ec2.eu-north-1.amazonaws.com, as its service and region.
var awsServiceAndRegion = regexp.MustCompile(`^([a-z0-9-]+)\.([a-z]{2}(?:-[a-z]+)+-[0-9]+)\.amazonaws\.com$`)

type awsSigner struct {
	accessKeyID, secretAccessKey string
	service, region              string
	now                          func() time.Time
}

func newAWSSigner(apiAddress string, parts []string, _ *http.Client) (requestSigner, error) {
	address, err := url.Parse(apiAddress)
	if err != nil {
		return nil, err
	}
	match := awsServiceAndRegion.FindStringSubmatch(address.Host)
	if match == nil {
		return nil, fmt.Errorf("%s is not an AWS API address with a service and a region, such as https://ec2.eu-north-1.amazonaws.com/", apiAddress)
	}
	return &awsSigner{accessKeyID: parts[0], secretAccessKey: parts[1], service: match[1], region: match[2], now: time.Now}, nil
}

func (s *awsSigner) sign(request *http.Request, body []byte) error {
	amzDate := s.now().UTC().Format("20060102T150405Z")
	payloadHash := sha256Hex(body)
	request.Header.Set("X-Amz-Date", amzDate)
	request.Header.Set("X-Amz-Content-Sha256", payloadHash)
	signed := []string{"host", "x-amz-content-sha256", "x-amz-date"}
	if request.Header.Get("Content-Type") != "" {
		signed = append(signed, "content-type")
	}
	slices.Sort(signed)
	signature := awsSignature(request, payloadHash, signed, amzDate, s.region, s.service, s.secretAccessKey)
	request.Header.Set("Authorization", fmt.Sprintf("AWS4-HMAC-SHA256 Credential=%s/%s/%s/%s/aws4_request, SignedHeaders=%s, Signature=%s",
		s.accessKeyID, amzDate[:8], s.region, s.service, strings.Join(signed, ";"), signature))
	return nil
}

// awsSignature is Signature Version 4's signature of request, whose headers
// named in signed (lowercase, sorted) are already set, at amzDate.
func awsSignature(request *http.Request, payloadHash string, signed []string, amzDate, region, service, secretAccessKey string) string {
	var headers strings.Builder
	for _, name := range signed {
		value := request.Header.Get(name)
		if name == "host" {
			value = request.URL.Host
		}
		headers.WriteString(name + ":" + strings.Join(strings.Fields(value), " ") + "\n")
	}
	path := request.URL.EscapedPath()
	if path == "" {
		path = "/"
	}
	canonicalRequest := strings.Join([]string{request.Method, path, awsCanonicalQuery(request.URL.RawQuery),
		headers.String(), strings.Join(signed, ";"), payloadHash}, "\n")
	scope := amzDate[:8] + "/" + region + "/" + service + "/aws4_request"
	stringToSign := "AWS4-HMAC-SHA256\n" + amzDate + "\n" + scope + "\n" + sha256Hex([]byte(canonicalRequest))
	key := []byte("AWS4" + secretAccessKey)
	for _, part := range []string{amzDate[:8], region, service, "aws4_request"} {
		key = hmacSHA256(key, part)
	}
	return hex.EncodeToString(hmacSHA256(key, stringToSign))
}

// awsCanonicalQuery encodes each name and value as AWS's UriEncode does and
// sorts the pairs by name, then value.
func awsCanonicalQuery(rawQuery string) string {
	values, _ := url.ParseQuery(rawQuery)
	var pairs []string
	for name, list := range values {
		for _, value := range list {
			pairs = append(pairs, awsURIEncode(name)+"="+awsURIEncode(value))
		}
	}
	slices.Sort(pairs)
	return strings.Join(pairs, "&")
}

// awsURIEncode encodes every byte but A-Z, a-z, 0-9, '-', '.', '_' and '~',
// with uppercase hexadecimal, as AWS's UriEncode() says.
func awsURIEncode(text string) string {
	var out strings.Builder
	for _, b := range []byte(text) {
		if b >= 'A' && b <= 'Z' || b >= 'a' && b <= 'z' || b >= '0' && b <= '9' || strings.IndexByte("-._~", b) >= 0 {
			out.WriteByte(b)
		} else {
			fmt.Fprintf(&out, "%%%02X", b)
		}
	}
	return out.String()
}

func sha256Hex(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

func hmacSHA256(key []byte, data string) []byte {
	mac := hmac.New(sha256.New, key)
	mac.Write([]byte(data))
	return mac.Sum(nil)
}

// readAWSRefusal reads EC2's error answer,
// <Response><Errors><Error><Code>..</Code><Message>..</Message>.
func readAWSRefusal(answer []byte) (string, string) {
	var refusal struct {
		Code    string `xml:"Errors>Error>Code"`
		Message string `xml:"Errors>Error>Message"`
	}
	_ = xml.Unmarshal(answer, &refusal)
	switch refusal.Code {
	case "AuthFailure", "InvalidClientTokenId":
		return refusal.Message, "AWS does not know this Access key ID, or the key was deactivated or deleted. Check the Access key ID; if it is right, make a new access key and run this command again"
	case "SignatureDoesNotMatch":
		return refusal.Message, "AWS could not verify the request's signature. Check the Secret access key, and that it belongs to the same access key as the Access key ID"
	case "UnauthorizedOperation":
		return refusal.Message, "The access key works, but its user's policy does not allow listing the servers (ec2:DescribeInstances). Give the user the policy your provider guide names, and run this command again"
	}
	return refusal.Message, ""
}
