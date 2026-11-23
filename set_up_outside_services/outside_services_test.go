package main

import (
	"fmt"
	"net/http"
	"strings"
	"time"
)

// Stand-ins for the services whose keys the setup checks, and for the
// domain's registry.

const (
	registryToken         = "ghp_registrytokenvalue0000000000000001"
	expiringRegistryToken = "ghp_registrytokenvalue0000000000000002"
	// endsTooSoonRegistryToken ends in 10 days, expiringRegistryToken in 90.
	endsTooSoonRegistryToken = "ghp_registrytokenvalue0000000000000003"
	vaultPassphrase          = "vault-passphrase-value"
	emergencyCodes           = "11111111\n22222222\n33333333"
	stripeKey                = "sk_live_stripekeyvalue000000000001"
	stripeTestKey            = "sk_test_stripekeyvalue000000000002"
)

// github stands in for GitHub's API and ghcr.io: each token's scopes, end
// date, and whether the image is built.
type github struct {
	scopes     map[string]string
	ends       map[string]string
	imageBuilt bool
}

func (g *github) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	switch {
	case r.URL.Path == "/user":
		token := strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
		scopes, known := g.scopes[token]
		if !known {
			// GitHub's message names no token, but a provider's message may
			// repeat what it was sent: this one does, so a test sees that no
			// message reaches the output.
			w.WriteHeader(http.StatusUnauthorized)
			fmt.Fprintf(w, `{"message": "Bad credentials: %s"}`, token)
			return
		}
		w.Header().Set("X-OAuth-Scopes", scopes)
		if ends := g.ends[token]; ends != "" {
			w.Header().Set("GitHub-Authentication-Token-Expiration", ends)
		}
		fmt.Fprint(w, `{"login": "alex-acme"}`)
	case r.URL.Path == "/token":
		login, token, _ := r.BasicAuth()
		if login != "alex-acme" || g.scopes[token] == "" || r.URL.Query().Get("scope") != "repository:acme/shop:pull" {
			w.WriteHeader(http.StatusUnauthorized)
			fmt.Fprint(w, `{"errors": [{"code": "UNAUTHORIZED", "message": "authentication required"}]}`)
			return
		}
		fmt.Fprintf(w, `{"token": "pull-%s"}`, token)
	case r.URL.Path == "/v2/acme/shop/tags/list" && strings.HasPrefix(r.Header.Get("Authorization"), "Bearer pull-"):
		if !g.imageBuilt {
			w.WriteHeader(http.StatusNotFound)
			fmt.Fprint(w, `{"errors": [{"code": "NAME_UNKNOWN", "message": "repository name not known to registry"}]}`)
			return
		}
		fmt.Fprint(w, `{"name": "acme/shop", "tags": ["main"]}`)
	default:
		w.WriteHeader(http.StatusForbidden)
		fmt.Fprint(w, `{"errors": [{"code": "DENIED", "message": "denied"}]}`)
	}
}

// stripe stands in for Stripe's balance call, which any working key reads.
func stripe(keys ...string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/v1/balance" && contains(keys, strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")) {
			fmt.Fprint(w, `{"object": "balance"}`)
			return
		}
		// Stripe's message repeats part of the key; this one repeats all of it,
		// so a test sees that no message reaches the output.
		w.WriteHeader(http.StatusUnauthorized)
		fmt.Fprintf(w, `{"error": {"code": "api_key_invalid", "message": "Invalid API Key provided: %s"}}`, strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer "))
	}
}

// rdap stands in for IANA's bootstrap file and the registry of .org.
func rdap(dnssec bool) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/dns.json":
			fmt.Fprintf(w, `{"services": [[["com", "net"], ["https://rdap.example.net/com/"]], [["org"], ["http://%s/org/"]]]}`, r.Host)
		case "/org/domain/example.org":
			fmt.Fprintf(w, `{"secureDNS": {"delegationSigned": %t}, "entities": [{"roles": ["registrar"],
				"vcardArray": ["vcard", [["version", {}, "text", "4.0"], ["fn", {}, "text", "Namecheap, Inc."]]]}]}`, dnssec)
		default:
			w.WriteHeader(http.StatusNotFound)
		}
	}
}

// tokenEnd is a token's end date in GitHub's format, days from now.
func tokenEnd(days int) string {
	return time.Now().UTC().AddDate(0, 0, days).Format("2006-01-02 15:04:05 UTC")
}
