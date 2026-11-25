package standins

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"slices"
	"strconv"
	"strings"
	"sync"
	"time"
)

// Cloudflare permissions a stand-in token can hold, by their API names.
// Each endpoint below accepts only a token with the permission its
// documentation names. The dashboard says Edit where the API says Write.
const (
	PermissionAccountAPITokensWrite    = "Account API Tokens Write"
	PermissionTunnelWrite              = "Cloudflare Tunnel Write"
	PermissionR2StorageWrite           = "Workers R2 Storage Write"
	PermissionZoneRead                 = "Zone Read"
	PermissionZoneWrite                = "Zone Write"
	PermissionDNSWrite                 = "DNS Write"
	PermissionWorkersScriptsWrite      = "Workers Scripts Write"
	PermissionTransformRulesWrite      = "Zone Transform Rules Write"
	PermissionAccessServiceTokensRead  = "Access: Service Tokens Read"
	PermissionAccessServiceTokensWrite = "Access: Service Tokens Write"
	PermissionAccessIdentityRead       = "Access: Organizations, Identity Providers, and Groups Read"
	PermissionAccessIdentityWrite      = "Access: Organizations, Identity Providers, and Groups Write"
)

// The resource scopes of permission groups.
const (
	ScopeAccount  = "com.cloudflare.api.account"
	ScopeZone     = "com.cloudflare.api.account.zone"
	ScopeR2Bucket = "com.cloudflare.edge.r2.bucket"
)

// AccessServiceToken is an Access service token. Its secret shows only in
// the answer that creates it.
type AccessServiceToken struct {
	ID           string `json:"id"`
	Name         string `json:"name"`
	ClientID     string `json:"client_id"`
	ClientSecret string `json:"-"`
	Duration     string `json:"duration"`
}

// PermissionGroup is one permission group as Cloudflare lists it, with a
// stand-in ID. Real IDs are read from Cloudflare by name and scope.
type PermissionGroup struct {
	ID    string
	Name  string
	Scope string
}

// PermissionGroups are the groups the stand-in knows. "Zone Read" is listed
// twice, for the account and for zones, as real groups can share a name
// across scopes, so a command must pick a group by its name and its scope.
var PermissionGroups = []PermissionGroup{
	{"2efd5506f9c8494dacb1fa10a3e7d5b6", "Workers R2 Storage Bucket Item Write", ScopeR2Bucket},
	{"6a018a9f2fc74eb6b293b0c548f38b39", "Workers R2 Storage Bucket Item Read", ScopeR2Bucket},
	{"e086da7e2179491d91ee5f35b3ca210a", PermissionWorkersScriptsWrite, ScopeAccount},
	{"1a71c399035b4950a1bd1466bbe4f420", "Workers Scripts Read", ScopeAccount},
	{"c07321b023e944ff818fec44d8203567", PermissionTunnelWrite, ScopeAccount},
	{"959972745952452f8be2452be8cbb9f2", "Access: Apps and Policies Write", ScopeAccount},
	{"26bc23f853634eb4bff59983b9064fde", PermissionAccessIdentityRead, ScopeAccount},
	{"bfe0d8686a584fa680f4c53b5eb0de6d", PermissionAccessIdentityWrite, ScopeAccount},
	{"3f376c8e6f764a938b848bd01b8995c4", PermissionAccessServiceTokensRead, ScopeAccount},
	{"a1c0fec57cf94af79479a6d827fa518c", PermissionAccessServiceTokensWrite, ScopeAccount},
	{"bf7481a1826f439697cb59a20b22293e", PermissionR2StorageWrite, ScopeAccount},
	{"4755a26eedb94da69e1066d98aa820be", PermissionDNSWrite, ScopeZone},
	{"e6d2666161e84845a636613608cee8d5", PermissionZoneWrite, ScopeZone},
	{"9ff81cbbe65c400b97d92c3c1033cab6", "Cache Settings Write", ScopeZone},
	{"c8fed203ed3043cba015a93ad1616f1f", PermissionZoneRead, ScopeZone},
	{"5c1b2c30ac6a4aa9bc95a2ff3c1df7f5", PermissionZoneRead, ScopeAccount},
	{"0ac90a90249747bca6b047d97f0803e9", PermissionTransformRulesWrite, ScopeZone},
	{"3030687196b94b638145a3953da2b699", "Zone Settings Write", ScopeZone},
	{"c03055bc037c4ea9afb9a9f104b7b721", "SSL and Certificates Write", ScopeZone},
	{"e17beae8b8cb423a99b1730f21238bed", "Cache Purge", ScopeZone},
	{"74e1036f577a48528b78d2413b40538d", "Dynamic URL Redirects Write", ScopeZone},
	{"ed07f6c337da4195b4e72a1fb2c6bcae", "Page Rules Write", ScopeZone},
	{"0fd9d56bc2da43ad8ea22d610dd8cab1", "Managed headers Write", ScopeZone},
	{"06f0526e6e464647bd61b63c54935235", "Config Settings Write", ScopeZone},
	{"a4308c6855c84eb2873e01b6cc85cbb3", "Origin Write", ScopeZone},
	{"fb6778dc191143babbfaa57993f1d275", "Zone WAF Write", ScopeZone},
	{"43137f8d07884d3198dc0ee77ca6e79b", "Firewall Services Write", ScopeZone},
	{"3b94c49258ec4573b06d51d99b6416c0", "Bot Management Write", ScopeZone},
	{"28f4b596e7d643029c524985477ae49a", "Workers Routes Write", ScopeZone},
	{"9c88f9c5bce24ce7af9a958ba9c504db", "Analytics Read", ScopeZone},
	{"5bdbde7e76144204a244274eac3eb0eb", PermissionAccountAPITokensWrite, ScopeAccount},
}

func permissionGroupByID(id string) (PermissionGroup, bool) {
	for _, group := range PermissionGroups {
		if group.ID == id {
			return group, true
		}
	}
	return PermissionGroup{}, false
}

// IdentityProvider is an Access login method.
type IdentityProvider struct {
	ID     string         `json:"id"`
	Name   string         `json:"name"`
	Type   string         `json:"type"`
	Config map[string]any `json:"config,omitempty"`
}

type CloudflareToken struct {
	ID          string            `json:"id"`
	Name        string            `json:"name"`
	Value       string            `json:"value"`
	UserOwned   bool              `json:"user_owned"`
	Permissions []string          `json:"permissions"` // the permission groups' names
	Policies    []json.RawMessage `json:"policies"`
	// ExpiresOn is when the token ends by itself, as Cloudflare writes it,
	// or "" for a token without an end, as the website's form makes it.
	ExpiresOn string `json:"expires_on,omitempty"`
	Deleted   bool   `json:"deleted"`
}

type CloudflareTunnel struct {
	ID        string `json:"id"`
	Name      string `json:"name"`
	ConfigSrc string `json:"config_src"`
	Token     string `json:"token"`
	// Secret is the tunnel's secret. A PATCH replaces it, and the token
	// changes with it.
	Secret string `json:"-"`
}

// Cloudflare is a stand-in Cloudflare account with at most one zone.
type Cloudflare struct {
	mu        sync.Mutex
	AccountID string
	ZoneName  string
	// ZoneStatus is "active", "pending" before the domain moved, or "" while
	// the account has no zone yet; POST /zones adds ZoneName as pending.
	ZoneStatus  string
	NameServers []string
	// DNSScans counts the scans of the zone's DNS records.
	DNSScans int
	// WorkersSubdomain is the account's workers.dev address, "" for none;
	// TakenSubdomains are other accounts'.
	WorkersSubdomain string
	TakenSubdomains  map[string]bool
	// R2Off makes every R2 call fail as in an account that never turned R2 on.
	R2Off bool
	// RefuseAccountsList makes GET /accounts refuse, as Cloudflare may for an
	// account-owned token.
	RefuseAccountsList bool
	// TokenAlsoWorksIn lists other accounts where GET /accounts lists the
	// account and the token's check passes, as for a token that reaches
	// several accounts. Every other call there is refused.
	TokenAlsoWorksIn []string
	Tokens           []*CloudflareToken
	ServiceTokens    []*AccessServiceToken
	// IdentityProviders are Access's login methods. The stand-in answers
	// 409 to a duplicate login method of the same type.
	// OneTimePINConflictsUnlisted makes it answer 409 for One-time PIN
	// although the list shows none, as a real Cloudflare account did in a test.
	IdentityProviders           []*IdentityProvider
	OneTimePINConflictsUnlisted bool
	Tunnels                     []*CloudflareTunnel
	R2Buckets                   map[string]bool
	CustomDomains               map[string][]string
	Rulesets                    map[string]map[string]any
	Failures                    map[string]string // "METHOD path-prefix" -> drop, malformed, or refuse
	Calls                       []string
	next                        int
}

func NewCloudflare(accountID string) *Cloudflare {
	return &Cloudflare{AccountID: accountID, ZoneName: "example.org", ZoneStatus: "active", NameServers: []string{"ada.ns.cloudflare.com", "bob.ns.cloudflare.com"},
		TakenSubdomains: map[string]bool{}, R2Buckets: map[string]bool{}, CustomDomains: map[string][]string{},
		Rulesets: map[string]map[string]any{}, Failures: map[string]string{}}
}

// AddToken adds a token that the person made on the website.
func (c *Cloudflare) AddToken(name, value string, userOwned bool, permissions ...string) *CloudflareToken {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.next++
	token := &CloudflareToken{ID: fmt.Sprintf("%032x", c.next), Name: name, Value: value, UserOwned: userOwned, Permissions: permissions}
	// The website's form writes one allow policy on the account, as a
	// link token made on the website showed in a test.
	if len(permissions) > 0 {
		policy := tokenPolicy{Effect: "allow", Resources: map[string]any{"com.cloudflare.api.account." + c.AccountID: "*"}}
		for _, permission := range permissions {
			for _, group := range PermissionGroups {
				if group.Name == permission && group.Scope == ScopeAccount {
					policy.PermissionGroups = append(policy.PermissionGroups, policyGroup{ID: group.ID, Name: group.Name})
				}
			}
		}
		encoded, _ := json.Marshal(policy)
		token.Policies = []json.RawMessage{encoded}
	}
	c.Tokens = append(c.Tokens, token)
	return token
}

func (c *Cloudflare) id() string {
	c.next++
	return fmt.Sprintf("%032x", 0x1000+c.next)
}

type cfRefusal struct {
	status  int
	code    int
	message string
}

func writeEnvelope(w http.ResponseWriter, status int, result any, refusal *cfRefusal) {
	w.Header().Set("Content-Type", "application/json")
	envelope := map[string]any{"success": refusal == nil, "errors": []any{}, "messages": []any{}, "result": result}
	if refusal != nil {
		status = refusal.status
		envelope["errors"] = []any{map[string]any{"code": refusal.code, "message": refusal.message}}
		envelope["result"] = nil
	}
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(envelope)
}

var (
	accountPath = regexp.MustCompile(`^/client/v4/accounts/([^/]+)(/.*)$`)
	zonePath    = regexp.MustCompile(`^/client/v4/zones/([^/]+)(/.*)$`)
)

func (c *Cloudflare) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	c.mu.Lock()
	defer c.mu.Unlock()
	call := r.Method + " " + strings.TrimPrefix(r.URL.Path, "/client/v4")
	c.Calls = append(c.Calls, call)
	failure := ""
	for prefix, mode := range c.Failures {
		if strings.HasPrefix(call, prefix) {
			failure = mode
			delete(c.Failures, prefix)
			break
		}
	}
	if failure == "malformed" {
		w.Header().Set("Content-Type", "application/json")
		_, _ = io.WriteString(w, `{"result": [`)
		return
	}
	if failure == "refuse" {
		writeEnvelope(w, 0, nil, denied)
		return
	}
	token := c.tokenOf(r)
	if token == nil {
		writeEnvelope(w, 0, nil, &cfRefusal{400, 6003, "Invalid request headers"})
		return
	}
	result, refusal := c.route(token, r)
	if refusal == nil && failure == "drop" {
		if hijacker, ok := w.(http.Hijacker); ok {
			if connection, _, err := hijacker.Hijack(); err == nil {
				connection.Close()
				return
			}
		}
	}
	writeEnvelope(w, http.StatusOK, result, refusal)
}

func (c *Cloudflare) tokenOf(r *http.Request) *CloudflareToken {
	value := strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
	for _, token := range c.Tokens {
		if token.Value == value && !token.Deleted {
			return token
		}
	}
	return nil
}

func (t *CloudflareToken) may(permission string) bool {
	for _, p := range t.Permissions {
		if p == permission {
			return true
		}
	}
	return false
}

var denied = &cfRefusal{403, 10000, "Authentication error"}
var malformed = &cfRefusal{400, 10040, "The JSON you provided was not well formed."}

func (c *Cloudflare) route(token *CloudflareToken, r *http.Request) (any, *cfRefusal) {
	path := r.URL.Path
	// https://developers.cloudflare.com/api/resources/user/subresources/tokens/methods/verify/
	if path == "/client/v4/user/tokens/verify" && r.Method == http.MethodGet {
		if !token.UserOwned {
			return nil, &cfRefusal{401, 1000, "Invalid API Token"}
		}
		return map[string]any{"id": token.ID, "status": "active"}, nil
	}
	// https://developers.cloudflare.com/api/resources/zones/methods/list/
	if path == "/client/v4/zones" && r.Method == http.MethodGet {
		if !token.may(PermissionZoneRead) {
			return nil, denied
		}
		zones := []any{}
		if r.URL.Query().Get("name") == c.ZoneName && c.ZoneStatus != "" {
			zones = append(zones, c.zoneView())
		}
		return zones, nil
	}
	// https://developers.cloudflare.com/api/resources/zones/methods/create/
	if path == "/client/v4/zones" && r.Method == http.MethodPost {
		if !token.may(PermissionZoneWrite) {
			return nil, denied
		}
		var body struct {
			Name    string            `json:"name"`
			Account map[string]string `json:"account"`
			Type    string            `json:"type"`
		}
		if !decodeCloudflare(r, &body) || body.Account["id"] != c.AccountID || body.Type != "full" {
			return nil, malformed
		}
		if body.Name != c.ZoneName {
			return nil, &cfRefusal{400, 1099, "the stand-in knows only the zone " + c.ZoneName}
		}
		if c.ZoneStatus != "" {
			return nil, &cfRefusal{400, 1061, body.Name + " already exists"}
		}
		c.ZoneStatus = "pending"
		return c.zoneView(), nil
	}
	// https://developers.cloudflare.com/api/resources/accounts/methods/list/
	if path == "/client/v4/accounts" && r.Method == http.MethodGet {
		if c.RefuseAccountsList {
			return nil, &cfRefusal{403, 9109, "Unauthorized to access requested resource"}
		}
		accounts := []any{map[string]any{"id": c.AccountID, "name": "Stand-in account"}}
		for _, id := range c.TokenAlsoWorksIn {
			accounts = append(accounts, map[string]any{"id": id, "name": "Another account"})
		}
		return accounts, nil
	}
	if match := zonePath.FindStringSubmatch(path); match != nil {
		return c.zoneRoute(token, r, match[1], match[2])
	}
	match := accountPath.FindStringSubmatch(path)
	if match == nil {
		return nil, &cfRefusal{404, 7003, "No route for that URI"}
	}
	rest := match[2]
	if match[1] != c.AccountID {
		if slices.Contains(c.TokenAlsoWorksIn, match[1]) && rest == "/tokens/verify" {
			return c.tokenRoute(token, r, rest)
		}
		return nil, denied
	}
	switch {
	case strings.HasPrefix(rest, "/tokens"):
		return c.tokenRoute(token, r, rest)
	case strings.HasPrefix(rest, "/cfd_tunnel"):
		if !token.may(PermissionTunnelWrite) {
			return nil, denied
		}
		return c.tunnelRoute(r, rest)
	case strings.HasPrefix(rest, "/r2/buckets"):
		if !token.may(PermissionR2StorageWrite) {
			return nil, denied
		}
		if c.R2Off {
			return nil, &cfRefusal{403, 10042, "Please enable R2 through the Cloudflare Dashboard."}
		}
		return c.r2Route(r, rest)
	// https://developers.cloudflare.com/api/resources/workers/subresources/subdomains/
	case rest == "/workers/subdomain":
		if !token.may(PermissionWorkersScriptsWrite) {
			return nil, denied
		}
		if r.Method == http.MethodGet {
			if c.WorkersSubdomain == "" {
				return nil, &cfRefusal{404, 10007, "This account does not have a workers.dev subdomain."}
			}
			return map[string]any{"subdomain": c.WorkersSubdomain}, nil
		}
		var body struct {
			Subdomain string `json:"subdomain"`
		}
		if r.Method != http.MethodPut || !decodeCloudflare(r, &body) || body.Subdomain == "" {
			return nil, malformed
		}
		if c.TakenSubdomains[body.Subdomain] {
			return nil, &cfRefusal{409, 10032, "This subdomain is not available."}
		}
		c.WorkersSubdomain = body.Subdomain
		return map[string]any{"subdomain": body.Subdomain}, nil
	// https://developers.cloudflare.com/api/resources/zero_trust/subresources/access/subresources/service_tokens/
	case rest == "/access/service_tokens" || strings.HasPrefix(rest, "/access/service_tokens/"):
		if r.Method == http.MethodGet && !token.may(PermissionAccessServiceTokensRead) && !token.may(PermissionAccessServiceTokensWrite) ||
			r.Method != http.MethodGet && !token.may(PermissionAccessServiceTokensWrite) {
			return nil, denied
		}
		// https://developers.cloudflare.com/api/resources/zero_trust/subresources/access/subresources/service_tokens/methods/rotate/
		if strings.HasSuffix(rest, "/rotate") && r.Method == http.MethodPost {
			id := strings.TrimSuffix(strings.TrimPrefix(rest, "/access/service_tokens/"), "/rotate")
			for _, t := range c.ServiceTokens {
				if t.ID == id {
					t.ClientSecret = c.id() + c.id()
					return map[string]any{"id": t.ID, "name": t.Name, "client_id": t.ClientID, "client_secret": t.ClientSecret}, nil
				}
			}
			return nil, &cfRefusal{404, 12130, "service token not found"}
		}
		if rest != "/access/service_tokens" {
			return nil, &cfRefusal{404, 7003, "No route for that URI"}
		}
		if r.Method == http.MethodGet {
			listed := []any{}
			for _, t := range c.ServiceTokens {
				if want := r.URL.Query().Get("name"); want == "" || want == t.Name {
					listed = append(listed, t)
				}
			}
			return listed, nil
		}
		var body struct {
			Name     string `json:"name"`
			Duration string `json:"duration"`
		}
		if r.Method != http.MethodPost || !decodeCloudflare(r, &body) || body.Name == "" {
			return nil, malformed
		}
		created := &AccessServiceToken{ID: c.id(), Name: body.Name, ClientID: c.id() + ".access", ClientSecret: c.id() + c.id(), Duration: body.Duration}
		c.ServiceTokens = append(c.ServiceTokens, created)
		return map[string]any{"id": created.ID, "name": created.Name, "client_id": created.ClientID, "client_secret": created.ClientSecret, "duration": created.Duration}, nil
	// https://developers.cloudflare.com/api/resources/zero_trust/subresources/identity_providers/
	case rest == "/access/identity_providers":
		if r.Method == http.MethodGet {
			if !token.may(PermissionAccessIdentityRead) && !token.may(PermissionAccessIdentityWrite) {
				return nil, denied
			}
			listed := []any{}
			for _, provider := range c.IdentityProviders {
				listed = append(listed, provider)
			}
			return listed, nil
		}
		if r.Method != http.MethodPost || !token.may(PermissionAccessIdentityWrite) {
			return nil, denied
		}
		var body struct {
			Name   string         `json:"name"`
			Type   string         `json:"type"`
			Config map[string]any `json:"config"`
		}
		if !decodeCloudflare(r, &body) || body.Name == "" || (body.Type != "onetimepin" && body.Type != "passkeys") || body.Config == nil {
			return nil, malformed
		}
		exists := body.Type == "onetimepin" && c.OneTimePINConflictsUnlisted
		for _, provider := range c.IdentityProviders {
			exists = exists || provider.Type == body.Type
		}
		if exists {
			return nil, &cfRefusal{409, 12130, "access.api.error.conflict: identity provider already exists"}
		}
		created := &IdentityProvider{ID: c.id(), Name: body.Name, Type: body.Type, Config: body.Config}
		c.IdentityProviders = append(c.IdentityProviders, created)
		return created, nil
	}
	return nil, &cfRefusal{404, 7003, "No route for that URI"}
}

func decodeCloudflare(r *http.Request, into any) bool {
	decoder := json.NewDecoder(io.LimitReader(r.Body, 1<<20))
	decoder.DisallowUnknownFields()
	return decoder.Decode(into) == nil
}

type tokenPolicy struct {
	Effect           string         `json:"effect"`
	Resources        map[string]any `json:"resources"`
	PermissionGroups []policyGroup  `json:"permission_groups"`
}

type policyGroup struct {
	ID   string `json:"id"`
	Name string `json:"name,omitempty"`
}

// checkPolicies enforces the resource each permission group applies to: an
// R2 bucket item permission on a bucket, an account permission on the
// account, and a zone permission on the account's zones, written as
// {"com.cloudflare.api.account.ID": {"com.cloudflare.api.account.zone.*": "*"}}.
// A token made through the API cannot make tokens: Cloudflare refuses it
// with "sub-token is not allowed to have permissions to manage other tokens".
// Only a token that holds Account API Tokens Write already, made on the
// website, may keep it in an update (keepsTokenMaking), as a link token made on
// the website did in a test.
// It returns the names of the permission groups, which the new token holds.
// https://developers.cloudflare.com/r2/api/tokens/
// https://developers.cloudflare.com/fundamentals/api/how-to/create-via-api/
func (c *Cloudflare) checkPolicies(policies []tokenPolicy, keepsTokenMaking bool) ([]string, *cfRefusal) {
	if len(policies) == 0 {
		return nil, &cfRefusal{400, 1001, "a token needs at least one policy"}
	}
	bucketResource := regexp.MustCompile(`^com\.cloudflare\.edge\.r2\.bucket\.` + c.AccountID + `_default_[a-z0-9-]{3,63}$`)
	account := "com.cloudflare.api.account." + c.AccountID
	var names []string
	for _, policy := range policies {
		if policy.Effect != "allow" && policy.Effect != "deny" || len(policy.PermissionGroups) == 0 || len(policy.Resources) == 0 {
			return nil, &cfRefusal{400, 1001, "each policy needs an effect, permission groups, and resources"}
		}
		for _, group := range policy.PermissionGroups {
			known, ok := permissionGroupByID(group.ID)
			if !ok {
				return nil, &cfRefusal{400, 1001, "unknown permission group " + group.ID}
			}
			if known.Name == PermissionAccountAPITokensWrite && !keepsTokenMaking {
				return nil, &cfRefusal{400, 1001, "sub-token is not allowed to have permissions to manage other tokens"}
			}
			for resource, value := range policy.Resources {
				fits := false
				switch known.Scope {
				case ScopeR2Bucket:
					fits = bucketResource.MatchString(resource) && value == "*"
				case ScopeAccount:
					fits = resource == account && value == "*"
				case ScopeZone:
					zones, isMap := value.(map[string]any)
					fits = resource == account && isMap && len(zones) == 1 && zones["com.cloudflare.api.account.zone.*"] == "*"
				}
				if !fits {
					return nil, &cfRefusal{400, 1001, fmt.Sprintf("the permission group %s does not apply to %s", known.Name, resource)}
				}
			}
			names = append(names, known.Name)
		}
	}
	return names, nil
}

func (c *Cloudflare) tokenView(token *CloudflareToken, withValue bool) map[string]any {
	view := map[string]any{"id": token.ID, "name": token.Name, "status": "active", "policies": token.Policies}
	if token.ExpiresOn != "" {
		view["expires_on"] = token.ExpiresOn
	}
	if withValue {
		view["value"] = token.Value
	}
	return view
}

// https://developers.cloudflare.com/api/resources/accounts/subresources/tokens/
func (c *Cloudflare) tokenRoute(token *CloudflareToken, r *http.Request, rest string) (any, *cfRefusal) {
	if rest == "/tokens/verify" && r.Method == http.MethodGet {
		if token.UserOwned {
			return nil, &cfRefusal{401, 1000, "Invalid API Token"}
		}
		verified := map[string]any{"id": token.ID, "status": "active"}
		if token.ExpiresOn != "" {
			verified["expires_on"] = token.ExpiresOn
		}
		return verified, nil
	}
	if !token.may(PermissionAccountAPITokensWrite) {
		return nil, denied
	}
	switch {
	case rest == "/tokens/permission_groups" && r.Method == http.MethodGet:
		groups := []any{}
		for _, group := range PermissionGroups {
			if want := r.URL.Query().Get("name"); want == "" || want == group.Name {
				groups = append(groups, map[string]any{"id": group.ID, "name": group.Name, "scopes": []string{group.Scope}})
			}
		}
		return groups, nil
	case rest == "/tokens" && r.Method == http.MethodGet:
		perPage, _ := strconv.Atoi(r.URL.Query().Get("per_page"))
		page, _ := strconv.Atoi(r.URL.Query().Get("page"))
		if perPage < 5 || perPage > 50 || page < 1 {
			return nil, &cfRefusal{400, 1001, "per_page must be 5 to 50 and page at least 1"}
		}
		var live []any
		for _, t := range c.Tokens {
			if !t.Deleted && !t.UserOwned {
				live = append(live, c.tokenView(t, false))
			}
		}
		start, end := (page-1)*perPage, page*perPage
		if start > len(live) {
			start = len(live)
		}
		if end > len(live) {
			end = len(live)
		}
		return append([]any{}, live[start:end]...), nil
	case rest == "/tokens" && r.Method == http.MethodPost:
		var body struct {
			Name     string        `json:"name"`
			Policies []tokenPolicy `json:"policies"`
		}
		if !decodeCloudflare(r, &body) || body.Name == "" || len(body.Name) > 120 {
			return nil, malformed
		}
		permissions, refusal := c.checkPolicies(body.Policies, false)
		if refusal != nil {
			return nil, refusal
		}
		created := &CloudflareToken{ID: c.id(), Name: body.Name, Value: "cfat_" + random(20), Permissions: permissions}
		for _, policy := range body.Policies {
			encoded, _ := json.Marshal(policy)
			created.Policies = append(created.Policies, encoded)
		}
		c.Tokens = append(c.Tokens, created)
		return c.tokenView(created, true), nil
	}
	id := strings.TrimPrefix(rest, "/tokens/")
	for _, t := range c.Tokens {
		if t.ID != id || t.Deleted || t.UserOwned {
			continue
		}
		switch r.Method {
		case http.MethodGet:
			return c.tokenView(t, false), nil
		case http.MethodDelete:
			t.Deleted = true
			return map[string]any{"id": t.ID}, nil
		case http.MethodPut:
			var body struct {
				Name      string        `json:"name"`
				Policies  []tokenPolicy `json:"policies"`
				Status    string        `json:"status"`
				ExpiresOn string        `json:"expires_on"`
			}
			if !decodeCloudflare(r, &body) || body.Name == "" || body.Status != "" && body.Status != "active" {
				return nil, malformed
			}
			if body.ExpiresOn != "" {
				if _, err := time.Parse("2006-01-02T15:04:05Z", body.ExpiresOn); err != nil {
					return nil, &cfRefusal{400, 1001, "expires_on must be written as 2006-01-02T15:04:05Z"}
				}
			}
			permissions, refusal := c.checkPolicies(body.Policies, t.may(PermissionAccountAPITokensWrite))
			if refusal != nil {
				return nil, refusal
			}
			t.Name, t.Policies, t.Permissions, t.ExpiresOn = body.Name, nil, permissions, body.ExpiresOn
			for _, policy := range body.Policies {
				encoded, _ := json.Marshal(policy)
				t.Policies = append(t.Policies, encoded)
			}
			return c.tokenView(t, false), nil
		}
	}
	return nil, &cfRefusal{404, 1003, "token not found"}
}

// https://developers.cloudflare.com/api/resources/zero_trust/subresources/tunnels/subresources/cloudflared/
func (c *Cloudflare) tunnelRoute(r *http.Request, rest string) (any, *cfRefusal) {
	switch {
	case rest == "/cfd_tunnel" && r.Method == http.MethodGet:
		tunnels := []any{}
		for _, tunnel := range c.Tunnels {
			if name := r.URL.Query().Get("name"); name == "" || name == tunnel.Name {
				tunnels = append(tunnels, map[string]any{"id": tunnel.ID, "name": tunnel.Name, "deleted_at": nil})
			}
		}
		return tunnels, nil
	case rest == "/cfd_tunnel" && r.Method == http.MethodPost:
		var body struct {
			Name      string `json:"name"`
			ConfigSrc string `json:"config_src"`
		}
		if !decodeCloudflare(r, &body) || body.Name == "" || (body.ConfigSrc != "local" && body.ConfigSrc != "cloudflare") {
			return nil, malformed
		}
		tunnel := &CloudflareTunnel{ID: c.id(), Name: body.Name, ConfigSrc: body.ConfigSrc, Token: "eyJhIjoi" + random(24), Secret: random(32)}
		c.Tunnels = append(c.Tunnels, tunnel)
		return map[string]any{"id": tunnel.ID, "name": tunnel.Name}, nil
	// A new tunnel secret, at least 32 bytes in base64, gives the tunnel a
	// new token.
	// https://developers.cloudflare.com/api/resources/zero_trust/subresources/tunnels/subresources/cloudflared/methods/edit/
	case strings.HasPrefix(rest, "/cfd_tunnel/") && r.Method == http.MethodPatch:
		var body struct {
			TunnelSecret string `json:"tunnel_secret"`
		}
		if !decodeCloudflare(r, &body) || len(body.TunnelSecret) < 44 {
			return nil, malformed
		}
		id := strings.TrimPrefix(rest, "/cfd_tunnel/")
		for _, tunnel := range c.Tunnels {
			if tunnel.ID == id {
				tunnel.Secret, tunnel.Token = body.TunnelSecret, "eyJhIjoi"+random(24)
				return map[string]any{"id": tunnel.ID, "name": tunnel.Name}, nil
			}
		}
		return nil, &cfRefusal{404, 1003, "tunnel not found"}
	case strings.HasSuffix(rest, "/token") && r.Method == http.MethodGet:
		id := strings.TrimSuffix(strings.TrimPrefix(rest, "/cfd_tunnel/"), "/token")
		for _, tunnel := range c.Tunnels {
			if tunnel.ID == id {
				return tunnel.Token, nil
			}
		}
		return nil, &cfRefusal{404, 1003, "tunnel not found"}
	}
	return nil, &cfRefusal{404, 7003, "No route for that URI"}
}

// https://developers.cloudflare.com/api/resources/r2/subresources/buckets/
func (c *Cloudflare) r2Route(r *http.Request, rest string) (any, *cfRefusal) {
	parts := strings.Split(strings.TrimPrefix(rest, "/r2/buckets"), "/")
	switch {
	case len(parts) == 1 && r.Method == http.MethodGet:
		buckets := []any{}
		for name := range c.R2Buckets {
			buckets = append(buckets, map[string]any{"name": name, "location": "WEUR"})
		}
		return map[string]any{"buckets": buckets}, nil
	case len(parts) == 1 && r.Method == http.MethodPost:
		var body struct {
			Name string `json:"name"`
		}
		if !decodeCloudflare(r, &body) || body.Name == "" {
			return nil, malformed
		}
		if c.R2Buckets[body.Name] {
			return nil, &cfRefusal{409, 10004, "The bucket you tried to create already exists, and you own it."}
		}
		c.R2Buckets[body.Name] = true
		return map[string]any{"name": body.Name, "location": "WEUR"}, nil
	case len(parts) == 2 && r.Method == http.MethodGet:
		if !c.R2Buckets[parts[1]] {
			return nil, &cfRefusal{404, 10006, "The specified bucket does not exist."}
		}
		return map[string]any{"name": parts[1], "location": "WEUR"}, nil
	case len(parts) == 4 && parts[2] == "domains" && parts[3] == "custom":
		bucket := parts[1]
		if !c.R2Buckets[bucket] {
			return nil, &cfRefusal{404, 10006, "The specified bucket does not exist."}
		}
		if r.Method == http.MethodGet {
			domains := []any{}
			for _, domain := range c.CustomDomains[bucket] {
				domains = append(domains, map[string]any{"domain": domain, "enabled": true, "status": map[string]string{"ownership": "active", "ssl": "active"}})
			}
			return map[string]any{"domains": domains}, nil
		}
		var body struct {
			Domain  string `json:"domain"`
			ZoneID  string `json:"zoneId"`
			Enabled bool   `json:"enabled"`
			MinTLS  string `json:"minTLS"`
		}
		if !decodeCloudflare(r, &body) || body.ZoneID != "zone0001" || !strings.HasSuffix(body.Domain, "."+c.ZoneName) {
			return nil, malformed
		}
		c.CustomDomains[bucket] = append(c.CustomDomains[bucket], body.Domain)
		return map[string]any{"domain": body.Domain, "zoneId": body.ZoneID, "enabled": body.Enabled}, nil
	}
	return nil, &cfRefusal{404, 7003, "No route for that URI"}
}

// The URL rewrite rule of MMHotline's status page set-up.
// https://developers.cloudflare.com/rules/transform/url-rewrite/create-api/
func (c *Cloudflare) zoneRoute(token *CloudflareToken, r *http.Request, zone, rest string) (any, *cfRefusal) {
	// https://developers.cloudflare.com/api/resources/dns/subresources/records/methods/scan/
	if rest == "/dns_records/scan" && r.Method == http.MethodPost {
		if zone != "zone0001" || c.ZoneStatus == "" || !token.may(PermissionDNSWrite) {
			return nil, denied
		}
		c.DNSScans++
		return map[string]any{"recs_added": 3, "total_records_parsed": 3}, nil
	}
	if zone != "zone0001" || !token.may(PermissionTransformRulesWrite) {
		return nil, denied
	}
	switch {
	case rest == "/rulesets/phases/http_request_transform/entrypoint" && r.Method == http.MethodGet:
		if c.Rulesets[zone] == nil {
			return nil, &cfRefusal{404, 10003, "Could not find entrypoint ruleset in the http_request_transform phase"}
		}
		return c.Rulesets[zone], nil
	case rest == "/rulesets" && r.Method == http.MethodPost:
		var body map[string]any
		if json.NewDecoder(r.Body).Decode(&body) != nil || body["phase"] != "http_request_transform" || c.Rulesets[zone] != nil {
			return nil, malformed
		}
		rules, _ := body["rules"].([]any)
		for i := range rules {
			if rule, ok := rules[i].(map[string]any); ok {
				rule["id"] = c.id()
			}
		}
		c.Rulesets[zone] = map[string]any{"id": c.id(), "rules": rules}
		return c.Rulesets[zone], nil
	case strings.HasPrefix(rest, "/rulesets/") && strings.HasSuffix(rest, "/rules") && r.Method == http.MethodPost:
		ruleset := c.Rulesets[zone]
		var rule map[string]any
		if ruleset == nil || json.NewDecoder(r.Body).Decode(&rule) != nil {
			return nil, malformed
		}
		rule["id"] = c.id()
		ruleset["rules"] = append(ruleset["rules"].([]any), rule)
		return ruleset, nil
	}
	return nil, &cfRefusal{404, 7003, "No route for that URI"}
}

func (c *Cloudflare) zoneView() map[string]any {
	return map[string]any{"id": "zone0001", "name": c.ZoneName, "status": c.ZoneStatus, "name_servers": c.NameServers}
}

// LiveTokensNamed lists the account tokens of that name not deleted.
func (c *Cloudflare) LiveTokensNamed(name string) []*CloudflareToken {
	c.mu.Lock()
	defer c.mu.Unlock()
	var tokens []*CloudflareToken
	for _, token := range c.Tokens {
		if token.Name == name && !token.Deleted {
			tokens = append(tokens, token)
		}
	}
	return tokens
}

// Snapshot is the account's state, for checks in tests.
func (c *Cloudflare) Snapshot() map[string]any {
	c.mu.Lock()
	defer c.mu.Unlock()
	return map[string]any{"tokens": c.Tokens, "tunnels": c.Tunnels, "r2_buckets": c.R2Buckets, "custom_domains": c.CustomDomains,
		"service_tokens": c.ServiceTokens, "identity_providers": c.IdentityProviders, "calls": c.Calls}
}

func (c *Cloudflare) Lock()   { c.mu.Lock() }
func (c *Cloudflare) Unlock() { c.mu.Unlock() }
