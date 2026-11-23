package main

import (
	"net/http"
	"net/url"
	"strings"
)

// The domain's registrar and DNSSEC state, which the coding agent needs
// before the person moves the domain to Cloudflare: DNSSEC must be off
// first, or the site stops working.

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
// a top-level domain without RDAP; the results file then leaves it out.
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
			// A name goes to the coding agent, so only printable text of a sane length.
			if len(name) <= 80 && !strings.ContainsFunc(name, func(r rune) bool { return r < ' ' || r == 0x7f }) {
				return strings.TrimSpace(name)
			}
		}
	}
	return ""
}
