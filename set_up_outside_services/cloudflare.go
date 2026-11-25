package main

import (
	"bytes"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"os/exec"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

const cloudflareAPIURL = "https://api.cloudflare.com/client/v4"

type cloudflareClient struct {
	baseURL   string
	token     string
	accountID string
	// who names the token in messages, such as "the link token".
	who string
	// id is the token's own ID, once verified.
	id string
}

func readCloudflareError(body []byte) (string, string) {
	var envelope struct {
		Errors []struct {
			Code    int    `json:"code"`
			Message string `json:"message"`
		} `json:"errors"`
	}
	_ = json.Unmarshal(body, &envelope)
	if len(envelope.Errors) == 0 {
		return "", ""
	}
	return strconv.Itoa(envelope.Errors[0].Code), envelope.Errors[0].Message
}

// call sends one v4 API request and decodes the envelope's result.
// https://developers.cloudflare.com/fundamentals/api/how-to/make-api-calls/
func (c *cloudflareClient) call(method, path string, body, result any) error {
	var envelope struct {
		Result json.RawMessage `json:"result"`
	}
	name := method + " " + strings.SplitN(path, "?", 2)[0]
	_, err := doJSON("Cloudflare", name+" from "+c.who, method, c.baseURL+path, map[string]string{"Authorization": "Bearer " + c.token}, body, &envelope, readCloudflareError)
	if err != nil {
		return err
	}
	if result != nil && len(envelope.Result) > 0 {
		if err := json.Unmarshal(envelope.Result, result); err != nil {
			return fmt.Errorf("Cloudflare answered %s with something this command cannot read", name)
		}
	}
	return nil
}

func (c *cloudflareClient) account(path string) string {
	return "/accounts/" + c.accountID + path
}

func refusedWith(err error, status int) bool {
	var refusal *apiError
	return errors.As(err, &refusal) && refusal.Status == status
}

type cloudflareTokenPolicy struct {
	Effect           string              `json:"effect"`
	Resources        map[string]any      `json:"resources"`
	PermissionGroups []map[string]string `json:"permission_groups"`
}

type cloudflareToken struct {
	ID       string `json:"id"`
	Name     string `json:"name"`
	Value    string `json:"value"`
	Policies []struct {
		Resources        map[string]any `json:"resources"`
		PermissionGroups []struct {
			ID string `json:"id"`
		} `json:"permission_groups"`
	} `json:"policies"`
}

// holdsPlan says whether the token holds exactly the plan's permission
// groups on the plan's resources, so a rerun can tell a token made before a
// change of the plan, such as a desk token made before the desk gained
// zone rights, and update it.
func (t cloudflareToken) holdsPlan(plan cloudflareCredentialPlan, ids map[permissionGroup]string) bool {
	have := map[string]bool{}
	for _, policy := range t.Policies {
		for _, group := range policy.PermissionGroups {
			for resource := range policy.Resources {
				have[group.ID+" on "+resource] = true
			}
		}
	}
	want := map[string]bool{}
	for _, policy := range plan.Policies {
		for _, group := range policy.Groups {
			for resource := range policy.Resources {
				want[ids[group]+" on "+resource] = true
			}
		}
	}
	if len(have) != len(want) {
		return false
	}
	for pair := range want {
		if !have[pair] {
			return false
		}
	}
	return true
}

// verifyAccountToken checks an account-owned token. Cloudflare's
// /user/tokens/verify answers 401 for one (tested at Cloudflare on
// 2026-11-12).
// https://developers.cloudflare.com/api/resources/accounts/subresources/tokens/methods/verify/
func (c *cloudflareClient) verifyAccountToken() (string, error) {
	var answer struct {
		ID     string `json:"id"`
		Status string `json:"status"`
	}
	if err := c.call(http.MethodGet, c.account("/tokens/verify"), nil, &answer); err != nil {
		return "", err
	}
	if answer.Status != "active" {
		return "", fmt.Errorf("Cloudflare says %s is %s, not active", c.who, answer.Status)
	}
	return answer.ID, nil
}

// permissionGroupIDs reads each permission group's ID by its name and its
// scope, since two groups can share a name across scopes.
// https://developers.cloudflare.com/api/resources/accounts/subresources/tokens/subresources/permission_groups/methods/list/
func (c *cloudflareClient) permissionGroupIDs(groups []permissionGroup) (map[permissionGroup]string, error) {
	type listedGroup struct {
		ID     string   `json:"id"`
		Name   string   `json:"name"`
		Scopes []string `json:"scopes"`
	}
	listed := map[string][]listedGroup{}
	ids := map[permissionGroup]string{}
	for _, group := range groups {
		if ids[group] != "" {
			continue
		}
		if _, done := listed[group.Name]; !done {
			var answer []listedGroup
			if err := c.call(http.MethodGet, c.account("/tokens/permission_groups?name="+url.QueryEscape(group.Name)), nil, &answer); err != nil {
				return nil, err
			}
			listed[group.Name] = answer
		}
		var matches []string
		for _, candidate := range listed[group.Name] {
			if candidate.Name == group.Name && contains(candidate.Scopes, group.Scope) {
				matches = append(matches, candidate.ID)
			}
		}
		if len(matches) != 1 {
			return nil, fmt.Errorf("Cloudflare lists %d permission groups named %q for the scope %s, not one", len(matches), group.Name, group.Scope)
		}
		ids[group] = matches[0]
	}
	return ids, nil
}

// https://developers.cloudflare.com/api/resources/accounts/subresources/tokens/methods/list/
func (c *cloudflareClient) accountTokensNamed(name string) ([]cloudflareToken, error) {
	var named []cloudflareToken
	for page := 1; ; page++ {
		var tokens []cloudflareToken
		if err := c.call(http.MethodGet, c.account(fmt.Sprintf("/tokens?page=%d&per_page=50", page)), nil, &tokens); err != nil {
			return nil, err
		}
		for _, token := range tokens {
			if token.Name == name {
				named = append(named, token)
			}
		}
		if len(tokens) < 50 {
			return named, nil
		}
	}
}

func tokenIDs(tokens []cloudflareToken) []string {
	var ids []string
	for _, token := range tokens {
		ids = append(ids, token.ID)
	}
	return ids
}

func policiesFor(plan cloudflareCredentialPlan, ids map[permissionGroup]string) []cloudflareTokenPolicy {
	var policies []cloudflareTokenPolicy
	for _, policy := range plan.Policies {
		var groups []map[string]string
		for _, group := range policy.Groups {
			groups = append(groups, map[string]string{"id": ids[group]})
		}
		policies = append(policies, cloudflareTokenPolicy{Effect: "allow", Resources: policy.Resources, PermissionGroups: groups})
	}
	return policies
}

// https://developers.cloudflare.com/api/resources/accounts/subresources/tokens/methods/create/
func (c *cloudflareClient) createAccountToken(plan cloudflareCredentialPlan, ids map[permissionGroup]string) (cloudflareToken, error) {
	var token cloudflareToken
	err := c.call(http.MethodPost, c.account("/tokens"), map[string]any{"name": plan.TokenName, "policies": policiesFor(plan, ids)}, &token)
	return token, err
}

// https://developers.cloudflare.com/api/resources/accounts/subresources/tokens/methods/update/
func (c *cloudflareClient) updateAccountToken(id string, plan cloudflareCredentialPlan, ids map[permissionGroup]string) error {
	return c.call(http.MethodPut, c.account("/tokens/"+id), map[string]any{"name": plan.TokenName, "policies": policiesFor(plan, ids)}, nil)
}

// linkTokenLifetime is how long the link token lives at most, counted from
// the moment the run checks it. Cloudflare's form makes it with "No
// expiration", so a run cut off by Ctrl-C or a dropped connection would
// otherwise leave a token that can make tokens for ever. 24 hours is long
// enough for a setup session and a rerun the same day, which takes a new
// link token anyway, and short enough that a forgotten token ends by itself.
// It is fixed, not a setting: each link token lives for one run only, so
// there is nothing a team would tune.
const linkTokenLifetime = 24 * time.Hour

// cloudflareExpiryLayout is how Cloudflare writes a token's expires_on.
const cloudflareExpiryLayout = "2006-01-02T15:04:05Z"

// endAccountTokenBy makes the token end by itself at latest, unless it
// already ends sooner. It returns the token's end and whether it changed.
// A PUT replaces the whole token, so it sends back the name, the status, and
// the policies the GET read. Tested at Cloudflare on 2026-11-12: a link token
// may set its own expires_on this way.
// https://developers.cloudflare.com/api/resources/accounts/subresources/tokens/methods/get/
// https://developers.cloudflare.com/api/resources/accounts/subresources/tokens/methods/update/
func (c *cloudflareClient) endAccountTokenBy(id string, latest time.Time) (time.Time, bool, error) {
	var token struct {
		Name      string `json:"name"`
		Status    string `json:"status"`
		ExpiresOn string `json:"expires_on"`
		Policies  []struct {
			Effect           string           `json:"effect"`
			Resources        map[string]any   `json:"resources"`
			PermissionGroups []map[string]any `json:"permission_groups"`
		} `json:"policies"`
	}
	if err := c.call(http.MethodGet, c.account("/tokens/"+id), nil, &token); err != nil {
		return time.Time{}, false, err
	}
	if token.ExpiresOn != "" {
		ends, err := time.Parse(time.RFC3339, token.ExpiresOn)
		if err != nil {
			return time.Time{}, false, fmt.Errorf("Cloudflare gave %s the end time %q, which this command cannot read", c.who, token.ExpiresOn)
		}
		if !ends.After(latest) {
			return ends, false, nil
		}
	}
	var policies []cloudflareTokenPolicy
	for _, policy := range token.Policies {
		var groups []map[string]string
		for _, group := range policy.PermissionGroups {
			id, _ := group["id"].(string)
			groups = append(groups, map[string]string{"id": id})
		}
		policies = append(policies, cloudflareTokenPolicy{Effect: policy.Effect, Resources: policy.Resources, PermissionGroups: groups})
	}
	ends := latest.UTC().Truncate(time.Second)
	body := map[string]any{"name": token.Name, "status": token.Status, "policies": policies, "expires_on": ends.Format(cloudflareExpiryLayout)}
	if err := c.call(http.MethodPut, c.account("/tokens/"+id), body, nil); err != nil {
		return time.Time{}, false, err
	}
	return ends, true, nil
}

// https://developers.cloudflare.com/api/resources/accounts/subresources/tokens/methods/delete/
func (c *cloudflareClient) deleteAccountToken(id string) error {
	return c.call(http.MethodDelete, c.account("/tokens/"+id), nil, nil)
}

// https://developers.cloudflare.com/api/resources/zero_trust/subresources/tunnels/subresources/cloudflared/methods/list/
// https://developers.cloudflare.com/api/resources/zero_trust/subresources/tunnels/subresources/cloudflared/methods/create/
func (c *cloudflareClient) ensureTunnel(name string) (string, bool, error) {
	var tunnels []struct {
		ID        string  `json:"id"`
		Name      string  `json:"name"`
		DeletedAt *string `json:"deleted_at"`
	}
	if err := c.call(http.MethodGet, c.account("/cfd_tunnel?is_deleted=false&name="+url.QueryEscape(name)), nil, &tunnels); err != nil {
		return "", false, err
	}
	var ids []string
	for _, tunnel := range tunnels {
		if tunnel.Name == name && tunnel.DeletedAt == nil {
			ids = append(ids, tunnel.ID)
		}
	}
	switch len(ids) {
	case 1:
		return ids[0], false, nil
	case 0:
	default:
		return "", false, fmt.Errorf("the Cloudflare account has %d tunnels named %s. Delete the extra ones on Cloudflare's website, then run this command again", len(ids), name)
	}
	// A locally managed tunnel keeps its routes in the systems repository.
	var created struct {
		ID string `json:"id"`
	}
	if err := c.call(http.MethodPost, c.account("/cfd_tunnel"), map[string]any{"name": name, "config_src": "local"}, &created); err != nil {
		return "", false, err
	}
	return created.ID, true, nil
}

// https://developers.cloudflare.com/api/resources/zero_trust/subresources/tunnels/subresources/cloudflared/subresources/token/methods/get/
func (c *cloudflareClient) tunnelToken(id string) (string, error) {
	var token string
	if err := c.call(http.MethodGet, c.account("/cfd_tunnel/"+id+"/token"), nil, &token); err != nil {
		return "", err
	}
	if token == "" {
		return "", errors.New("Cloudflare returned an empty tunnel token")
	}
	return token, nil
}

// giveTunnelANewSecret replaces a locally managed tunnel's secret, 32
// random bytes in base64, so the tunnel's token changes and the old token
// opens no new connection.
// https://developers.cloudflare.com/api/resources/zero_trust/subresources/tunnels/subresources/cloudflared/methods/edit/
func (c *cloudflareClient) giveTunnelANewSecret(id string) error {
	secret := make([]byte, 32)
	if _, err := rand.Read(secret); err != nil {
		return err
	}
	return c.call(http.MethodPatch, c.account("/cfd_tunnel/"+id), map[string]any{"tunnel_secret": base64.StdEncoding.EncodeToString(secret)}, nil)
}

// https://developers.cloudflare.com/api/resources/r2/subresources/buckets/methods/get/
// https://developers.cloudflare.com/api/resources/r2/subresources/buckets/methods/create/
func (c *cloudflareClient) ensureR2Bucket(name string) (bool, error) {
	err := c.call(http.MethodGet, c.account("/r2/buckets/"+url.PathEscape(name)), nil, nil)
	if err == nil {
		return false, nil
	}
	if !refusedWith(err, http.StatusNotFound) {
		return false, err
	}
	return true, c.call(http.MethodPost, c.account("/r2/buckets"), map[string]any{"name": name}, nil)
}

// r2IsOn says whether R2 is turned on in the account, from the list of
// its buckets, which Cloudflare refuses with code 10042 while R2 is off.
// https://developers.cloudflare.com/api/resources/r2/subresources/buckets/methods/list/
func (c *cloudflareClient) r2IsOn() (bool, error) {
	err := c.call(http.MethodGet, c.account("/r2/buckets"), nil, nil)
	if r2IsTurnedOff(err) {
		return false, nil
	}
	return err == nil, err
}

// r2Credentials turns a new R2 token into its S3 key: the access key ID is
// the token's ID, the secret access key the SHA-256 of its value.
// https://developers.cloudflare.com/r2/api/tokens/
func r2Credentials(token cloudflareToken) (string, string) {
	digest := sha256.Sum256([]byte(token.Value))
	return token.ID, hex.EncodeToString(digest[:])
}

type statusPageSetUp struct {
	BucketName  string `json:"bucket_name"`
	R2BucketURL string `json:"r2_bucket_url"`
	PageURL     string `json:"page_url"`
}

// zoneOf finds the account's zone that a host name belongs to, and its
// status, such as "active" or "pending".
// https://developers.cloudflare.com/api/resources/zones/methods/list/
func (c *cloudflareClient) zoneOf(hostName string) (string, string, error) {
	labels := strings.Split(hostName, ".")
	for i := 1; i < len(labels)-1; i++ {
		name := strings.Join(labels[i:], ".")
		var zones []struct {
			Name   string `json:"name"`
			Status string `json:"status"`
		}
		if err := c.call(http.MethodGet, "/zones?name="+url.QueryEscape(name)+"&account.id="+c.accountID, nil, &zones); err != nil {
			return "", "", err
		}
		for _, zone := range zones {
			if zone.Name == name {
				return name, zone.Status, nil
			}
		}
	}
	return "", "", fmt.Errorf("Cloudflare has no domain in account %s that %s belongs to. Add the domain at Cloudflare first: your coding agent does it with the Cloudflare account, in \"Your accounts\"", c.accountID, hostName)
}

// runMMHotlineStatusPageSetUp reuses MMHotline's own set-up of the status
// page's bucket, host name, and rewrite rule, with the desk's token on
// standard input.
func runMMHotlineStatusPageSetUp(accountID, hostName, token string) (statusPageSetUp, error) {
	var result statusPageSetUp
	command := exec.Command("mmhotline", "status-page", "set-up", "--cloudflare-account-id", accountID,
		"--host-name", hostName, "--cloudflare-api-token-file", "-", "--json")
	command.Stdin = strings.NewReader(token + "\n")
	var output, errorOutput bytes.Buffer
	command.Stdout, command.Stderr = &output, &errorOutput
	if err := command.Run(); err != nil {
		return result, fmt.Errorf("mmhotline status-page set-up failed: %s", firstLine(errorOutput.String(), err))
	}
	if err := json.Unmarshal(output.Bytes(), &result); err != nil || result.BucketName == "" || result.R2BucketURL == "" {
		return result, errors.New("mmhotline status-page set-up printed something this command cannot read")
	}
	return result, nil
}

// tokenMakingLink opens Cloudflare's form for the link token, the one token
// the person makes by hand, with its one permission, Account API Tokens
// Edit, and its name filled in (form tested at Cloudflare on 2026-11-08).
// A token made through the API cannot make tokens, so this one must be
// made on the website.
// https://developers.cloudflare.com/fundamentals/api/how-to/account-owned-token-template/
func tokenMakingLink(settings systemSettings, person string) string {
	keys := url.QueryEscape(`[{"key":"account_api_tokens","type":"edit"}]`)
	return "https://dash.cloudflare.com/?to=/:account/api-tokens&permissionGroupKeys=" + keys +
		"&name=" + url.QueryEscape(linkTokenName(settings, person))
}

// The token file's variables that the command writes.
const (
	deskTokenVariable                 = "CLOUDFLARE_API_TOKEN"
	accountIDVariable                 = "CLOUDFLARE_ACCOUNT_ID"
	statusPageBucketURLVariable       = "MMHOTLINE_STATUS_PAGE_R2_BUCKET_URL"
	postingKeyIDVariable              = "MMHOTLINE_STATUS_PAGE_R2_ACCESS_KEY_ID"
	postingSecretVariable             = "MMHOTLINE_STATUS_PAGE_R2_SECRET_ACCESS_KEY"
	stagingAccessClientIDVariable     = "STAGING_ACCESS_CLIENT_ID"
	stagingAccessClientSecretVariable = "STAGING_ACCESS_CLIENT_SECRET"
)

const stagingServiceTokensPage = "https://one.dash.cloudflare.com/, then Access controls, Service credentials, Service Tokens"

// cloudflareReplaceableKeys lists the names --replace-key takes: the first
// vault key of each token the servers use, each tunnel's vault key, and the
// token file's variables of the person's own tokens.
func cloudflareReplaceableKeys(settings systemSettings, plan []cloudflareCredentialPlan) []string {
	var names []string
	for _, tunnel := range tunnelsPlan(settings) {
		names = append(names, tunnel.VaultName)
	}
	for _, credential := range plan {
		names = append(names, credential.VaultNames[0])
	}
	names = append(names, statusPageVaultKeyID, deskTokenVariable, postingKeyIDVariable)
	if settings.hasStagingServer {
		names = append(names, stagingAccessClientSecretVariable)
	}
	return names
}

var unixUserNamePattern = regexp.MustCompile(`^[a-z_][a-z0-9_-]{0,31}$`)

// cloudflareArguments are the cloudflare command's arguments.
type cloudflareArguments struct {
	replace map[string]bool
	atOnce  bool
	// leaving names a person whose tokens the run deletes.
	leaving string
	// accountID names the Cloudflare account when the link token reaches
	// several, or Cloudflare does not list the token's account.
	accountID string
}

// readCloudflareArguments reads --replace-key NAME (repeated),
// --replace-every-key, --delete-the-old-keys-at-once,
// --delete-tokens-of-person NAME, and --account-id ID.
func readCloudflareArguments(arguments []string, known []string, person string) (cloudflareArguments, error) {
	read := cloudflareArguments{replace: map[string]bool{}}
	for i := 0; i < len(arguments); i++ {
		switch {
		case arguments[i] == deleteTheOldKeysAtOnceFlag:
			read.atOnce = true
		case arguments[i] == "--replace-every-key":
			for _, name := range known {
				read.replace[name] = true
			}
		case arguments[i] == "--replace-key" && i+1 < len(arguments):
			i++
			if !contains(known, arguments[i]) {
				return read, fmt.Errorf("--replace-key %s names no Cloudflare key of this system. Give one of: %s", arguments[i], strings.Join(known, ", "))
			}
			read.replace[arguments[i]] = true
		case arguments[i] == "--delete-tokens-of-person" && i+1 < len(arguments):
			i++
			read.leaving = arguments[i]
			if !unixUserNamePattern.MatchString(read.leaving) {
				return read, fmt.Errorf("--delete-tokens-of-person takes the leaving person's account name on their systems desk, vars.person_unix_username, such as alex: %w", errUsage)
			}
			if read.leaving == person {
				return read, errors.New("--delete-tokens-of-person names you. A remaining team member runs it for the person who leaves")
			}
		case arguments[i] == "--account-id" && i+1 < len(arguments):
			i++
			if !cloudflareAccountIDPattern.MatchString(arguments[i]) {
				return read, fmt.Errorf("--account-id takes the Cloudflare account's 32-character ID, such as %s: %w", exampleCloudflareAccountID, errUsage)
			}
			read.accountID = arguments[i]
		default:
			return read, fmt.Errorf("cloudflare takes only --account-id ID, --replace-key NAME, --replace-every-key, %s, or --delete-tokens-of-person NAME: %w", deleteTheOldKeysAtOnceFlag, errUsage)
		}
	}
	if read.leaving != "" && (len(read.replace) > 0 || read.atOnce) {
		return read, fmt.Errorf("--delete-tokens-of-person runs on its own, without --replace-key: %w", errUsage)
	}
	return read, nil
}

// r2OverviewPage opens the account's R2 page, where Cloudflare's checkout
// turns R2 on.
func r2OverviewPage(accountID string) string {
	return "https://dash.cloudflare.com/" + accountID + "/r2/overview"
}

// r2CostLines states R2's price for a person who approves it, from
// Cloudflare's R2 pricing page (https://developers.cloudflare.com/r2/pricing/,
// read 2026-11-17, Standard storage): free up to 10 GB-month, 1 million
// Class A and 10 million Class B requests a month; then $0.015 per
// GB-month, $4.50 per million Class A (writes) and $0.36 per million Class B
// (reads); no egress fee. Check it again when Cloudflare changes its prices.
const r2CostLines = `  It costs nothing up to 10 GB of files a month.
  Above that:  $0.015 for each GB a month,
               $4.50 for each million file writes after the first million,
               $0.36 for each million file reads after the first 10 million.
  Downloads to your users cost nothing.`

// runCloudflare sets up the Cloudflare account from the link token, the
// first time and on each later run: it finds the account, adds the domain
// and has Cloudflare copy its DNS records, gives the account its
// workers.dev address, reads the registrar's facts while the domain is not
// on Cloudflare yet, then makes the tokens, tunnels, and R2 buckets.
func runCloudflare(e *environment, arguments []string) error {
	e.named("cloudflare")
	return e.asStep("cloudflare", func(notes map[string]string) (string, error) {
		settings, err := readSystemSettings(e.readRepositoryFile)
		if err != nil {
			return "", err
		}
		domain, err := settings.domain()
		if err != nil {
			return "", err
		}
		// The plan's checks and key names do not depend on the account, which
		// may be known only once Cloudflare answers for the link token.
		names, err := cloudflareAccountTokenPlan(settings, exampleCloudflareAccountID)
		if err != nil {
			return "", err
		}
		read, err := readCloudflareArguments(arguments, cloudflareReplaceableKeys(settings, names), e.person)
		if err != nil {
			return "", err
		}
		e.replaceKeys, e.deleteOldKeysAtOnce = read.replace, read.atOnce
		oldKeys := e.oldKeysFilePath(settings)
		if read.leaving != "" {
			accountID, err := settings.cloudflareAccountID()
			if err != nil {
				return "", err
			}
			return stepDone, e.deleteTheTokensOfALeavingPerson(settings, accountID, read.leaving)
		}
		saved, err := e.beginAccountChange(settings)
		if err != nil {
			return "", err
		}
		if len(read.replace) > 0 {
			e.say("Cloudflare: this command replaces these keys and saves each new one where the old one was:")
			e.say("  %s", strings.Join(sortedNames(read.replace), ", "))
			if read.atOnce {
				e.say("It deletes each old key at Cloudflare at once, so the servers that use one fail until their next run.")
			} else {
				e.say("A key the servers use keeps its old key working until the servers' run passed and you press Enter.")
			}
		} else {
			e.say("Cloudflare: this command adds your domain, makes your systems desk's Cloudflare token, your tunnels, R2 buckets, and the keys")
			e.say("your servers use, the status page, and Access's Passkeys and One-time PIN login methods. It saves every secret straight into the vault or your token file.")
		}
		accountID := read.accountID
		if accountID == "" {
			// A rotation or a joining person: the coding agent wrote the
			// account's ID into the settings at the first setup.
			accountID, _ = settings.cloudflareAccountID()
		}
		link, err := e.askForTheLinkToken(settings, accountID)
		if err != nil {
			return "", err
		}
		linkDeleted := false
		defer func() {
			if !linkDeleted {
				e.deleteTheLinkToken(link)
			}
		}()
		accountID = link.accountID
		notes["cloudflare_account_id"] = accountID

		e.say("")
		e.say("Your domain %s at Cloudflare:", domain)
		zone, err := e.addTheDomain(link, settings, domain)
		if err != nil {
			return "", err
		}
		notes["cloudflare_nameservers"] = strings.Join(zone.NameServers, " ")
		notes["cloudflare_domain_status"] = zone.Status
		if zone.Status != "active" {
			// The domain moves to Cloudflare at its registrar, after the
			// records are copied and with DNSSEC off.
			registration := lookUpRegistration(e, domain)
			if registration.registrar != "" {
				notes["domain_registrar"] = registration.registrar
			}
			switch registration.dnssec {
			case dnssecOn:
				notes["domain_dnssec_on"] = "yes"
			case dnssecOff:
				notes["domain_dnssec_on"] = "no"
			}
			e.say("  The domain points at Cloudflare once its registrar names these two nameservers: %s.", strings.Join(zone.NameServers, ", "))
		}

		plan, err := cloudflareAccountTokenPlan(settings, accountID)
		if err != nil {
			return "", err
		}
		done, err := e.setUpCloudflare(link, settings, accountID, plan, saved, oldKeys)
		if err != nil {
			return "", err
		}
		statusPage := done.statusPage

		e.say("")
		e.say("See the account's tokens: https://dash.cloudflare.com/%s/api-tokens", accountID)
		e.say("See the R2 buckets: %s", r2OverviewPage(accountID))
		e.say("See the tunnels: https://dash.cloudflare.com/one/, then Networks, Tunnels.")
		e.say("")
		e.say("For your coding agent's settings, none of which is a secret:")
		if settings.uploadsAreBackedUp() {
			notes["uploads_r2_s3_endpoint"] = "https://" + accountID + ".r2.cloudflarestorage.com"
			e.say("  vars.backups.uploads_r2_s3_endpoint: %s", notes["uploads_r2_s3_endpoint"])
		}
		if statusPage.R2BucketURL != "" {
			notes["status_page_r2_bucket_url"] = statusPage.R2BucketURL
			e.say("  status_page.r2_bucket_url in mmhotline_settings.yml: %s", statusPage.R2BucketURL)
		}
		tokensPage := "https://dash.cloudflare.com/" + accountID + "/api-tokens"
		if read.atOnce {
			if err := e.deleteOldKeys(oldKeys, "cloudflare", false, link.deleteAccountToken, tokensPage); err != nil {
				return "", err
			}
		}
		if err := e.finishVaultChange(saved, e.commandLine); err != nil {
			return "", err
		}
		if read.atOnce && len(read.replace) > 0 {
			e.say("The servers get the new keys at the next run of every_server: tell your coding agent to run it now.")
		}
		// The vault is pushed, so the run can bring the new keys to the servers.
		// The link token stays in this command's memory only while it waits.
		if err := e.deleteOldKeys(oldKeys, "cloudflare", true, link.deleteAccountToken, tokensPage); err != nil {
			return "", err
		}
		linkDeleted = true
		e.deleteTheLinkToken(link)
		if done.r2IsOff {
			// The upload buckets and their keys need R2, and turning it on asks
			// for a card at Cloudflare's checkout, which only the person does.
			return "", fmt.Errorf("R2 is off in this Cloudflare account, and your app keeps its uploaded files in R2. Everything else is set up.\n"+
				"Turn R2 on once at %s: Cloudflare's checkout asks for a card.\n%s\n"+
				"Then run this command again, with a new link token: it makes only what is missing", r2OverviewPage(accountID), r2CostLines)
		}
		e.say(sayTheCodingAgentCarriesOn)
		return stepDone, nil
	})
}

// cloudflareSetUp is what setUpCloudflare leaves for its caller to say.
type cloudflareSetUp struct {
	statusPage statusPageSetUp
	// r2IsOff says R2 is not turned on in the account yet, so the apps'
	// upload buckets, their keys, and the status page wait for a rerun.
	r2IsOff bool
}

// setUpCloudflare makes, with the link token, the person's desk token, the
// tunnels, the R2 buckets, the status page once the domain is Active, the
// servers' tokens, the posting key, and Access's login method. Each part
// keeps what exists already.
func (e *environment) setUpCloudflare(link *cloudflareClient, settings systemSettings, accountID string, plan []cloudflareCredentialPlan,
	saved *savedKeys, oldKeys string) (cloudflareSetUp, error) {
	groups := append(append(append([]permissionGroup{}, deskAccountPermissions...), deskZonePermissions...), accessSetUpPermissions...)
	groups = append(groups, permissionR2BucketItemWrite)
	for _, credential := range plan {
		for _, policy := range credential.Policies {
			groups = append(groups, policy.Groups...)
		}
	}
	ids, err := link.permissionGroupIDs(groups)
	if err != nil {
		return cloudflareSetUp{}, err
	}

	e.say("")
	e.say("Your systems desk's Cloudflare token: your coding agent sets up tunnels, DNS, Access, the cache rule, and R2 with it,")
	e.say("through the API proxy, without reading it. It cannot make tokens. It is yours, named after you, and deleted when you leave.")
	desk, err := e.ensureDeskToken(link, settings, accountID, ids)
	if err != nil {
		return cloudflareSetUp{}, err
	}

	e.say("")
	e.say("Tunnels: your servers open these connections out to Cloudflare, so no server needs an open web port.")
	for _, tunnel := range tunnelsPlan(settings) {
		if err := e.stopIfInterrupted(); err != nil {
			return cloudflareSetUp{}, err
		}
		if err := e.ensureTunnelToken(desk, tunnel, saved); err != nil {
			return cloudflareSetUp{}, err
		}
	}

	r2IsOff := false
	if apps := settings.appsWithUploads(); len(apps) > 0 {
		e.say("")
		e.say("R2 buckets: your apps keep their uploaded files in R2, outside the app servers.")
	buckets:
		for _, name := range apps {
			buckets := [][2]string{{"uploads bucket", settings.Vars.Apps[name].ProductionUploadsR2Bucket}}
			if settings.hasStagingServer {
				// Staging holds seed data, so nothing copies this bucket to B2.
				buckets = append(buckets, [2]string{"staging uploads bucket", settings.Vars.Apps[name].StagingUploadsR2Bucket})
			}
			for _, bucket := range buckets {
				created, err := desk.ensureR2Bucket(bucket[1])
				if r2IsTurnedOff(err) {
					r2IsOff = true
					e.say("  R2 is not turned on in this account yet, so the buckets and their keys wait.")
					break buckets
				}
				if err != nil {
					return cloudflareSetUp{}, err
				}
				if created {
					e.say("  Created %s's %s %s.", name, bucket[0], bucket[1])
				} else {
					e.say("  %s's %s %s exists already. Unchanged.", capitalize(name), bucket[0], bucket[1])
				}
			}
		}
	}

	e.say("")
	e.say("The status page at %s tells your customers about a problem, even while your servers are down.", settings.Vars.StatusPageHostName)
	// Cloudflare connects the page's host name to its bucket only in a zone
	// that is Active, so a Pending domain leaves the page for a rerun.
	zone, zoneStatus, err := desk.zoneOf(settings.Vars.StatusPageHostName)
	if err != nil {
		return cloudflareSetUp{}, err
	}
	// The page keeps its files in R2. Without an app that keeps uploads,
	// nothing above checked R2, so a domain that is Active asks R2 here.
	statusPageWaitsForR2 := r2IsOff
	if zoneStatus == "active" && len(settings.appsWithUploads()) == 0 {
		on, err := desk.r2IsOn()
		if err != nil {
			return cloudflareSetUp{}, err
		}
		statusPageWaitsForR2 = !on
	}
	var statusPage statusPageSetUp
	switch {
	case zoneStatus != "active":
		e.say("  The status page waits until your domain %s is Active at Cloudflare; Cloudflare shows the domain as %s now.", zone, zoneStatus)
		e.say("  Run set-up-outside-services cloudflare again then: it makes only what is missing. See the domain's status: https://dash.cloudflare.com/%s/%s", accountID, zone)
	case statusPageWaitsForR2:
		e.say("  The status page keeps its files in R2, which is off in this account, so the page waits. The rest of this run carries on.")
		e.say("  Turn R2 on once at %s: Cloudflare's checkout asks for a card, and the page's few files cost nothing.", r2OverviewPage(accountID))
		e.say("  Then run set-up-outside-services cloudflare again, with a new link token: it adds only the status page.")
	default:
		statusPage, err = e.runMMHotlineStatusPageSetUp(accountID, settings.Vars.StatusPageHostName, desk.token)
		if err != nil {
			return cloudflareSetUp{}, err
		}
		e.say("  MMHotline set up the page's bucket %s, its host name, and the rule that serves the page.", statusPage.BucketName)
		plan = append(plan, statusPageCredentialPlan(settings, accountID, statusPage.BucketName))
		if err := e.updateTokenFile(e.tokenFilePath(settings), map[string]string{statusPageBucketURLVariable: statusPage.R2BucketURL}); err != nil {
			return cloudflareSetUp{}, err
		}
		e.say("  Wrote the page's bucket address, which is not a secret, into your token file as %s.", statusPageBucketURLVariable)
	}

	e.say("")
	e.say("The servers' tokens: each belongs to the Cloudflare account, not to you, so it keeps working when a person leaves.")
	for _, credential := range plan {
		if err := e.stopIfInterrupted(); err != nil {
			return cloudflareSetUp{}, err
		}
		if r2IsOff && credential.Form == r2KeyForm {
			continue
		}
		if err := e.ensureCloudflareCredential(link, credential, ids, saved, oldKeys); err != nil {
			return cloudflareSetUp{}, err
		}
	}

	if statusPage.BucketName != "" {
		e.say("")
		e.say("Your own key for posting to the status page from this systems desk while util01 is down.")
		if err := e.ensureStatusPagePostingKey(link, settings, accountID, statusPage.BucketName, ids); err != nil {
			return cloudflareSetUp{}, err
		}
	}

	if err := e.ensureAccess(link, desk, settings, accountID, ids); err != nil {
		return cloudflareSetUp{}, err
	}
	return cloudflareSetUp{statusPage: statusPage, r2IsOff: r2IsOff}, nil
}

// r2IsTurnedOff says Cloudflare refused an R2 call because the account has
// not turned R2 on: Cloudflare's error 10042, "Please enable R2 through the
// Cloudflare Dashboard". Turning R2 on asks for a payment method on the
// website, so it waits for the person.
func r2IsTurnedOff(err error) bool {
	var refusal *apiError
	return errors.As(err, &refusal) && refusal.Code == "10042"
}

func sortedNames(set map[string]bool) []string {
	var names []string
	for name := range set {
		names = append(names, name)
	}
	sort.Strings(names)
	return names
}

// askForTheLinkToken takes the link token, from a hidden prompt with the
// prepared link above it, or from the coding agent's standard input; finds
// its account when accountID is empty; checks it; and deletes any earlier
// link token of the same name that a stopped run left.
func (e *environment) askForTheLinkToken(settings systemSettings, accountID string) (*cloudflareClient, error) {
	if !e.forTheCodingAgent {
		e.say("")
		e.say("Making tokens needs one token that only you can make, on Cloudflare's website: the link token.")
		e.say("Open this link, which fills in its one permission, Account API Tokens Edit, and its name:")
		e.say("  %s", tokenMakingLink(settings, e.person))
		if accountID != "" {
			e.say("If Cloudflare asks which account, pick the one whose ID is %s (cloudflare_account_id).", accountID)
		}
		e.say("Keep the link's settings. The page is long: scroll to the bottom, below the list of permissions.")
		e.say("Select Review token, then Create token.")
		e.say("Cloudflare shows the token only once: copy all of it and paste it below.")
		e.say("This command sets the link token to end by itself after 24 hours and deletes it when the run ends, so no token that can make tokens stays behind.")
		e.say("")
	}
	value, err := e.prompt("Link token (hidden): ")
	if err != nil {
		return nil, err
	}
	if err := checkTokenValue("link token", value); err != nil {
		return nil, err
	}
	link := &cloudflareClient{baseURL: e.cloudflareAPIURL, token: value, accountID: accountID, who: "the link token"}
	if accountID == "" {
		if link.accountID, err = findTheLinkTokensAccount(link); err != nil {
			return nil, err
		}
	}
	id, err := link.verifyAccountToken()
	if err != nil {
		return nil, fmt.Errorf("%v. Most likely the token was not copied whole, or it was made in another account than %s. "+
			"Make a new link token with the link, in account %s, copy all of it, and run this command again", err, link.accountID, link.accountID)
	}
	e.say("The link token works in account %s.", link.accountID)
	if err := e.acceptLinkToken(settings, link, id); err != nil {
		return nil, err
	}
	return link, nil
}

// whereTheAccountIDIs says where a person reads a Cloudflare account's ID.
const whereTheAccountIDIs = "the address bar of any page at https://dash.cloudflare.com shows it as the 32 letters and digits right after dash.cloudflare.com/"

// findTheLinkTokensAccount finds the one account where the link token
// works, among the accounts Cloudflare lists for it. An account-owned token
// works in its own account only. When Cloudflare lists none, or the token
// works in several, the run stops and names the way to give --account-id.
// A token that works in several accounts is deleted before the stop, so no
// token that can make tokens stays behind when the person never runs the
// command again. A token Cloudflare lists no account for cannot be reached
// to delete; the next run deletes it, as an earlier link token of its name.
func findTheLinkTokensAccount(link *cloudflareClient) (string, error) {
	accounts, err := link.accounts()
	if err != nil && !refusedWith(err, http.StatusForbidden) {
		return "", err
	}
	if len(accounts) == 0 {
		return "", fmt.Errorf("Cloudflare does not list the account of this link token. Run this command again with --account-id ID, with a new link token; %s", whereTheAccountIDIs)
	}
	var works []cloudflareAccount
	tokenIDs := map[string]string{}
	for _, account := range accounts {
		link.accountID = account.ID
		id, err := link.verifyAccountToken()
		var refusal *apiError
		switch {
		case err == nil:
			works = append(works, account)
			tokenIDs[account.ID] = id
		case !errors.As(err, &refusal):
			return "", err
		}
	}
	link.accountID = ""
	switch len(works) {
	case 1:
		return works[0].ID, nil
	case 0:
		return "", errors.New("Cloudflare does not know this link token in any account it lists. Most likely the token was not copied whole. Make a new link token with the link and run this command again")
	}
	var listed []string
	for _, account := range works {
		listed = append(listed, fmt.Sprintf("%s (%s)", screenText(account.Name), account.ID))
	}
	deleted := "Deleting this link token failed: delete it on Cloudflare's website, at the account's API Tokens page"
	for _, account := range works {
		link.accountID = account.ID
		if link.deleteAccountToken(tokenIDs[account.ID]) == nil {
			deleted = "This link token is deleted"
			break
		}
	}
	link.accountID = ""
	return "", fmt.Errorf("the link token works in %d Cloudflare accounts: %s. %s. Run this command again with --account-id ID for the account this system uses, with a new link token", len(works), strings.Join(listed, ", "), deleted)
}

// errLinkTokenCannotMakeTokens says the token passed its check but lacks
// Account API Tokens Edit, so it was not made with the prepared link.
var errLinkTokenCannotMakeTokens = errors.New("the link token needs Account API Tokens Edit: make it with the link above")

// acceptLinkToken takes a link token that passed its check in its account,
// with id its token ID: it deletes any earlier link token of the same name
// that a stopped run left, and makes this one end by itself within
// linkTokenLifetime.
func (e *environment) acceptLinkToken(settings systemSettings, link *cloudflareClient, id string) error {
	earlier, err := link.accountTokensNamed(linkTokenName(settings, e.person))
	if err != nil {
		if refusedWith(err, http.StatusForbidden) {
			return errLinkTokenCannotMakeTokens
		}
		return err
	}
	for _, token := range earlier {
		if token.ID == id {
			continue
		}
		if err := link.deleteAccountToken(token.ID); err != nil {
			return err
		}
		e.say("Deleted an earlier link token (ID %s), left by a run that stopped.", token.ID)
	}
	link.id = id
	// After the check that it can manage tokens and before anything is
	// made, so a run cut off half way leaves no token that can make tokens
	// for longer than linkTokenLifetime.
	ends, changed, err := link.endAccountTokenBy(id, e.now().Add(linkTokenLifetime))
	if err != nil {
		e.deleteTheLinkToken(link)
		return fmt.Errorf("%v. Cloudflare did not let the link token set its own end, so this run stopped before making anything. "+
			"Make a new link token with the link above and run this command again. If this happens again, "+
			"give the link token an end date on Cloudflare's form, under TTL, before you select Review token", err)
	}
	if changed {
		e.say("Set the link token to end by itself at %s UTC tomorrow, in case this run is cut off. The run deletes it at its end.", ends.Format("15:04"))
	} else {
		e.say("The link token ends by itself at %s UTC already, sooner than 24 hours from now. Unchanged. The run deletes it at its end.", ends.UTC().Format("2006-01-02 15:04"))
	}
	return nil
}

func (e *environment) deleteTheLinkToken(link *cloudflareClient) {
	e.say("")
	if err := link.deleteAccountToken(link.id); err != nil {
		e.say("Deleting the link token failed (%v). Delete it on Cloudflare's website: https://dash.cloudflare.com/%s/api-tokens", err, link.accountID)
		return
	}
	e.say("Deleted the link token at Cloudflare. A later run takes a new one from the same link.")
}

// ensurePersonsToken keeps a person's own token while Cloudflare lists
// exactly one token of its name and the token file holds that one (heldID).
// Otherwise it makes a new token, saves it, and then deletes every other
// token of that name, such as one a stopped run or an earlier desk left.
// replacing makes a new one in any case.
func (e *environment) ensurePersonsToken(link *cloudflareClient, plan cloudflareCredentialPlan, ids map[permissionGroup]string,
	heldID string, replacing bool, save func(cloudflareToken) error) (cloudflareToken, bool, error) {
	named, err := link.accountTokensNamed(plan.TokenName)
	if err != nil {
		return cloudflareToken{}, false, err
	}
	if !replacing && heldID != "" && len(named) == 1 && named[0].ID == heldID {
		return named[0], false, nil
	}
	e.enterCriticalSection()
	token, err := link.createAccountToken(plan, ids)
	if err != nil {
		e.leaveCriticalSection()
		var lost *networkError
		if errors.As(err, &lost) {
			return token, false, fmt.Errorf("%v. Cloudflare may have made the token %q anyway. Run this command again: it deletes such a token", err, plan.TokenName)
		}
		return token, false, err
	}
	if token.ID == "" || token.Value == "" {
		e.leaveCriticalSection()
		return token, false, fmt.Errorf("Cloudflare made the token %q without returning its value. Run this command again: it deletes that token", plan.TokenName)
	}
	if err := save(token); err != nil {
		revoked := "so this command deleted the new token"
		if deleteErr := link.deleteAccountToken(token.ID); deleteErr != nil {
			revoked = fmt.Sprintf("and deleting the new token (ID %s) failed too (%v): a rerun deletes it", token.ID, deleteErr)
		}
		e.leaveCriticalSection()
		return token, false, fmt.Errorf("%v. The new token %q is not saved, %s", err, plan.TokenName, revoked)
	}
	e.leaveCriticalSection()
	for _, old := range named {
		if err := link.deleteAccountToken(old.ID); err != nil {
			e.say("  Deleting the earlier token %q (ID %s) failed (%v). Delete it by hand: https://dash.cloudflare.com/%s/api-tokens", plan.TokenName, old.ID, err, link.accountID)
			continue
		}
		e.say("  Deleted the earlier token %q (ID %s) at Cloudflare.", plan.TokenName, old.ID)
	}
	return token, true, nil
}

// ensureDeskToken makes the person's desk token, which the API proxy
// adds to the coding agent's requests and the person's own commands read
// from the token file, and returns a client that uses it.
func (e *environment) ensureDeskToken(link *cloudflareClient, settings systemSettings, accountID string, ids map[permissionGroup]string) (*cloudflareClient, error) {
	path := e.tokenFilePath(settings)
	plan := deskTokenPlan(settings, accountID, e.person)
	held := tokenFileValue(path, deskTokenVariable)
	heldID := ""
	if held != "" {
		heldClient := &cloudflareClient{baseURL: e.cloudflareAPIURL, token: held, accountID: accountID, who: "your token file's Cloudflare token"}
		heldID, _ = heldClient.verifyAccountToken()
	}
	token, made, err := e.ensurePersonsToken(link, plan, ids, heldID, e.replaceKeys[deskTokenVariable], func(token cloudflareToken) error {
		// The proxy first: a failure there keeps the proxy's old token, so the
		// new one can be deleted.
		if err := e.writeProxyFile(proxyFileRequest{API: "cloudflare", Token: token.Value, CloudflareAccountID: accountID}); err != nil {
			return err
		}
		if err := e.updateTokenFile(path, map[string]string{deskTokenVariable: token.Value, accountIDVariable: accountID}); err != nil {
			return fmt.Errorf("the API proxy has the new token, but writing %s failed: %v", path, err)
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	if !made && !token.holdsPlan(plan, ids) {
		// A desk set up by an earlier Stack: its token gains the rights the
		// desk token has now, and keeps its value, so the API proxy and the
		// token file stay as they are.
		if err := link.updateAccountToken(token.ID, plan, ids); err != nil {
			return nil, fmt.Errorf("updating the rights of your systems desk's token %q (ID %s) failed: %v. It still works with its earlier rights; run this command again", plan.TokenName, token.ID, err)
		}
		e.say("  Your systems desk's token %q (ID %s) is in your token file and the API proxy already. Updated its rights to: %s. Its value stays the same.", plan.TokenName, token.ID, describePolicies(plan.Policies))
		return &cloudflareClient{baseURL: e.cloudflareAPIURL, token: held, accountID: accountID, who: "your systems desk's Cloudflare token"}, nil
	}
	if !made {
		e.say("  Your systems desk's token %q (ID %s) is in your token file and the API proxy already. Unchanged.", plan.TokenName, token.ID)
		return &cloudflareClient{baseURL: e.cloudflareAPIURL, token: held, accountID: accountID, who: "your systems desk's Cloudflare token"}, nil
	}
	e.say("  Made your systems desk's token %q (ID %s): %s.", plan.TokenName, token.ID, describePolicies(plan.Policies))
	e.say("  Saved it in the API proxy and in %s as %s.", path, deskTokenVariable)
	if held != "" && heldID == "" {
		e.say("  Your token file held an earlier Cloudflare token that is not an account token of account %s, such as a token you made yourself.", accountID)
		e.say("  This command cannot delete it. Delete it on your profile's API Tokens page if it is yours: https://dash.cloudflare.com/profile/api-tokens")
	}
	return &cloudflareClient{baseURL: e.cloudflareAPIURL, token: token.Value, accountID: accountID, who: "your systems desk's Cloudflare token"}, nil
}

// ensureStatusPagePostingKey makes the person's own R2 key for the status
// page's bucket and writes it into the token file, where mmhotline
// status-page on the desk reads it.
func (e *environment) ensureStatusPagePostingKey(link *cloudflareClient, settings systemSettings, accountID, bucket string, ids map[permissionGroup]string) error {
	path := e.tokenFilePath(settings)
	plan := statusPagePostingTokenPlan(settings, accountID, e.person, bucket)
	heldID := ""
	if tokenFileValue(path, postingSecretVariable) != "" {
		heldID = tokenFileValue(path, postingKeyIDVariable)
	}
	token, made, err := e.ensurePersonsToken(link, plan, ids, heldID, e.replaceKeys[postingKeyIDVariable], func(token cloudflareToken) error {
		accessKeyID, secretAccessKey := r2Credentials(token)
		return e.updateTokenFile(path, map[string]string{postingKeyIDVariable: accessKeyID, postingSecretVariable: secretAccessKey})
	})
	if err != nil {
		return err
	}
	if !made {
		e.say("  Your posting key %q (ID %s) is in your token file already. Unchanged.", plan.TokenName, token.ID)
		return nil
	}
	e.say("  Made your posting key %q (ID %s): %s.", plan.TokenName, token.ID, describePolicies(plan.Policies))
	e.say("  Saved it in %s as %s and %s.", path, postingKeyIDVariable, postingSecretVariable)
	return nil
}

func (e *environment) ensureTunnelToken(client *cloudflareClient, tunnel tunnelPlan, saved *savedKeys) error {
	replacing := e.replaceKeys[tunnel.VaultName]
	if saved.hasAll(tunnel.VaultName) && !replacing {
		e.say("  Tunnel %s: its token is already in the vault as %s. Unchanged.", tunnel.Name, tunnel.VaultName)
		return nil
	}
	id, created, err := client.ensureTunnel(tunnel.Name)
	if err != nil {
		return err
	}
	if replacing && !created {
		if err := client.giveTunnelANewSecret(id); err != nil {
			return err
		}
	}
	token, err := client.tunnelToken(id)
	if err != nil {
		return err
	}
	// The token belongs to the tunnel: a failed save leaves nothing to
	// revoke, and a rerun reads the same tunnel's token again.
	if err := saved.save(tunnel.VaultName, token); err != nil {
		return fmt.Errorf("%v. The tunnel %s exists at Cloudflare; a rerun saves its token", err, tunnel.Name)
	}
	switch {
	case replacing && !created:
		e.say("  Gave the tunnel %s (ID %s) a new secret, so its old token opens no new connection. Saved its new token in the vault as %s.", tunnel.Name, id, tunnel.VaultName)
	case created:
		e.say("  Created the tunnel %s (ID %s), for %s. Saved its token in the vault as %s.", tunnel.Name, id, tunnel.Routes, tunnel.VaultName)
	default:
		e.say("  Found the tunnel %s (ID %s), for %s. Saved its token in the vault as %s.", tunnel.Name, id, tunnel.Routes, tunnel.VaultName)
	}
	return nil
}

func (e *environment) ensureCloudflareCredential(client *cloudflareClient, plan cloudflareCredentialPlan, ids map[permissionGroup]string, saved *savedKeys, oldKeys string) error {
	replacing := e.replaceKeys[plan.VaultNames[0]]
	outcome, id, err := e.issueAndSave(saved, issuedCredential{
		provider: "Cloudflare", item: "token", name: strconv.Quote(plan.TokenName), vaultNames: plan.VaultNames,
		deletePage: "https://dash.cloudflare.com/" + client.accountID + "/api-tokens", replaceSaved: replacing,
		idsNamed: func() ([]string, error) {
			tokens, err := client.accountTokensNamed(plan.TokenName)
			return tokenIDs(tokens), err
		},
		delete: client.deleteAccountToken,
		create: func() (string, []string, string, error) {
			token, err := client.createAccountToken(plan, ids)
			if err != nil {
				return "", nil, "", err
			}
			if token.ID == "" || token.Value == "" {
				return token.ID, nil, "without returning its value", nil
			}
			values := []string{token.Value}
			if plan.Form == r2KeyForm {
				accessKeyID, secretAccessKey := r2Credentials(token)
				values = []string{accessKeyID, secretAccessKey}
			}
			return token.ID, values, "", nil
		},
	})
	if err != nil {
		return err
	}
	if outcome == alreadySaved {
		e.say("  %s: already in the vault as %s. Unchanged.", capitalize(plan.Purpose), strings.Join(plan.VaultNames, " and "))
		if plan.UpdateResourcesWhenSaved {
			return e.updateSavedTokenResources(client, plan, ids)
		}
		return nil
	}
	e.say("  Made %s, the token %q (ID %s): %s.", plan.Purpose, plan.TokenName, id, describePolicies(plan.Policies))
	e.say("    Why: %s", plan.Why)
	e.say("    Saved in the vault as %s.", strings.Join(plan.VaultNames, " and "))
	if !replacing {
		return nil
	}
	// The old token keeps working until the servers run with the new one.
	// The end of the run deletes it: after the person's Enter, or at once.
	tokens, err := client.accountTokensNamed(plan.TokenName)
	if err != nil {
		return fmt.Errorf("%v. The old token %q still works: delete it by hand at https://dash.cloudflare.com/%s/api-tokens once the servers run with the new one", err, plan.TokenName, client.accountID)
	}
	var old []oldKey
	for _, token := range tokens {
		if token.ID != id {
			old = append(old, oldKey{Provider: "cloudflare", ID: token.ID, Name: plan.TokenName})
		}
	}
	return recordOldKeys(oldKeys, old...)
}

// updateSavedTokenResources brings a saved token's buckets up to date. Its
// value stays the same, so the vault keeps working.
func (e *environment) updateSavedTokenResources(client *cloudflareClient, plan cloudflareCredentialPlan, ids map[permissionGroup]string) error {
	tokens, err := client.accountTokensNamed(plan.TokenName)
	if err != nil {
		return err
	}
	if len(tokens) != 1 {
		e.say("    Cloudflare has %d tokens named %q, so this command cannot check its buckets.", len(tokens), plan.TokenName)
		e.say("    If an app was added since the key was made, add its bucket to the key on Cloudflare's website.")
		return nil
	}
	if tokens[0].holdsPlan(plan, ids) {
		return nil
	}
	want := map[string]any{}
	for _, policy := range plan.Policies {
		for name, value := range policy.Resources {
			want[name] = value
		}
	}
	if err := client.updateAccountToken(tokens[0].ID, plan, ids); err != nil {
		return err
	}
	e.say("    Updated its buckets to %s. Its key stays the same.", describeResources(want))
	return nil
}

func describeResources(resources map[string]any) string {
	var names []string
	for name, value := range resources {
		switch {
		case strings.HasPrefix(name, "com.cloudflare.edge.r2.bucket."):
			parts := strings.SplitN(strings.TrimPrefix(name, "com.cloudflare.edge.r2.bucket."), "_default_", 2)
			names = append(names, "the bucket "+parts[len(parts)-1])
		case strings.HasPrefix(name, "com.cloudflare.api.account."):
			if _, zones := value.(map[string]any); zones {
				names = append(names, "every zone of the account")
			} else {
				names = append(names, "the account")
			}
		default:
			names = append(names, name)
		}
	}
	sort.Strings(names)
	return strings.Join(names, " and ")
}

func describePolicies(policies []tokenPolicyPlan) string {
	var parts []string
	for _, policy := range policies {
		var groups []string
		for _, group := range policy.Groups {
			groups = append(groups, group.Name)
		}
		parts = append(parts, strings.Join(groups, ", ")+", on "+describeResources(policy.Resources))
	}
	return strings.Join(parts, "; ")
}

// accessServiceToken is an Access service token as Cloudflare lists it.
type accessServiceToken struct {
	ID   string `json:"id"`
	Name string `json:"name"`
}

type accessLoginMethod struct {
	name   string
	idType string
	config map[string]any
}

// defaultAccessLoginMethods are the login methods ensureAccess adds to
// Cloudflare Access. Passkeys let returning users sign in with Touch ID,
// Face ID, or a security key (auto-prompted on the login page), while
// One-time PIN lets teammates without a Cloudflare account or passkey sign in
// with an emailed code.
var defaultAccessLoginMethods = []accessLoginMethod{
	{name: "One-time PIN", idType: "onetimepin", config: map[string]any{}},
	{name: "Passkeys", idType: "passkeys", config: map[string]any{"login_page_auto_prompt": true}},
}

// ensureAccess adds Access's Passkeys and One-time PIN login methods and
// staging's Access service token when any is missing, and renews the service
// token's secret on --replace-key STAGING_ACCESS_CLIENT_SECRET. The desk's
// token can only read both, on purpose: a login method decides whose address
// Access believes, so a token in the API proxy that could add one could admit
// anyone. So a short-lived token with the two Write permissions does the
// change and is deleted at once.
func (e *environment) ensureAccess(link, desk *cloudflareClient, settings systemSettings, accountID string, ids map[permissionGroup]string) error {
	e.say("")
	e.say("Access's login methods: Passkeys (Touch ID, Face ID, or a security key) and One-time PIN (an emailed code for teammates without a Cloudflare account or passkey).")
	var providers []struct {
		Type string `json:"type"`
	}
	if err := desk.call(http.MethodGet, desk.account("/access/identity_providers"), nil, &providers); err != nil {
		return err
	}
	existingTypes := map[string]bool{}
	for _, provider := range providers {
		existingTypes[provider.Type] = true
	}
	var missingMethods []accessLoginMethod
	for _, method := range defaultAccessLoginMethods {
		if !existingTypes[method.idType] {
			missingMethods = append(missingMethods, method)
		}
	}
	var stagingToken *accessServiceToken
	stagingName := settings.ProjectName + ": staging tests"
	stagingNeedsWrite := false
	if settings.hasStagingServer {
		var existing []accessServiceToken
		if err := desk.call(http.MethodGet, desk.account("/access/service_tokens?name="+url.QueryEscape(stagingName)), nil, &existing); err != nil {
			return err
		}
		for i := range existing {
			if existing[i].Name == stagingName {
				stagingToken = &existing[i]
			}
		}
		stagingNeedsWrite = stagingToken == nil || e.replaceKeys[stagingAccessClientSecretVariable]
	}
	if len(missingMethods) == 0 && !stagingNeedsWrite {
		for _, method := range defaultAccessLoginMethods {
			e.say("  %s is a login method already. Unchanged.", method.name)
		}
		return e.sayStagingServiceTokenState(settings, stagingToken != nil, stagingName)
	}

	return e.withShortLivedToken(link, accessSetUpTokenPlan(settings, accountID), ids, "the short-lived Access token", func(access *cloudflareClient) error {
		return e.addAccessLoginMethodsAndStagingToken(access, settings, existingTypes, stagingNeedsWrite, stagingToken, stagingName)
	})
}

// withShortLivedToken makes a token for one job, runs the job with it, and
// deletes it, so no token with these permissions stays behind. A token of
// the same name that a stopped run left is deleted first.
func (e *environment) withShortLivedToken(link *cloudflareClient, plan cloudflareCredentialPlan, ids map[permissionGroup]string, who string, job func(*cloudflareClient) error) error {
	leftover, err := link.accountTokensNamed(plan.TokenName)
	if err != nil {
		return err
	}
	for _, token := range leftover {
		if err := link.deleteAccountToken(token.ID); err != nil {
			return err
		}
		e.say("  Deleted the token %q (ID %s), left by a run that stopped.", plan.TokenName, token.ID)
	}
	short, err := link.createAccountToken(plan, ids)
	if err != nil {
		return err
	}
	defer func() {
		if err := link.deleteAccountToken(short.ID); err != nil {
			e.say("  Deleting the token %q (ID %s) failed (%v). A rerun deletes it, or delete it by hand: https://dash.cloudflare.com/%s/api-tokens", plan.TokenName, short.ID, err, link.accountID)
			return
		}
		e.say("  Deleted the short-lived token %q at Cloudflare.", plan.TokenName)
	}()
	e.say("  Made the short-lived token %q (ID %s): %s.", plan.TokenName, short.ID, describePolicies(plan.Policies))
	return job(&cloudflareClient{baseURL: e.cloudflareAPIURL, token: short.Value, accountID: link.accountID, who: who})
}

// addAccessLoginMethodsAndStagingToken is ensureAccess's work with the
// short-lived Access token.
func (e *environment) addAccessLoginMethodsAndStagingToken(access *cloudflareClient, settings systemSettings, existingTypes map[string]bool, stagingNeedsWrite bool,
	stagingToken *accessServiceToken, stagingName string) error {
	path := e.tokenFilePath(settings)
	for _, method := range defaultAccessLoginMethods {
		if existingTypes[method.idType] {
			e.say("  %s is a login method already. Unchanged.", method.name)
			continue
		}
		// https://developers.cloudflare.com/api/resources/zero_trust/subresources/identity_providers/methods/create/
		err := access.call(http.MethodPost, access.account("/access/identity_providers"), map[string]any{"name": method.name, "type": method.idType, "config": method.config}, nil)
		switch {
		case err == nil:
			e.say("  Added %s as a login method.", method.name)
		case refusedWith(err, http.StatusConflict):
			// Cloudflare answers 409 when the account has the login method already.
			e.say("  %s is a login method already. Unchanged.", method.name)
		default:
			return err
		}
	}
	if !stagingNeedsWrite {
		return e.sayStagingServiceTokenState(settings, stagingToken != nil, stagingName)
	}
	e.say("")
	e.say("Staging's Access service token opens your staging pages without a person's sign-in, for CI and your local app tests.")
	var values struct {
		ID           string `json:"id"`
		ClientID     string `json:"client_id"`
		ClientSecret string `json:"client_secret"`
	}
	if stagingToken == nil {
		// https://developers.cloudflare.com/api/resources/zero_trust/subresources/access/subresources/service_tokens/methods/create/
		if err := access.call(http.MethodPost, access.account("/access/service_tokens"), map[string]any{"name": stagingName, "duration": "8760h"}, &values); err != nil {
			var lost *networkError
			if errors.As(err, &lost) {
				return fmt.Errorf("%v. Cloudflare may have made the service token %q anyway; a rerun says so", err, stagingName)
			}
			return err
		}
	} else {
		// Renewing the secret keeps the token's ID, so the staging pages'
		// Service Auth policies need no change.
		// https://developers.cloudflare.com/api/resources/zero_trust/subresources/access/subresources/service_tokens/methods/rotate/
		if err := access.call(http.MethodPost, access.account("/access/service_tokens/"+stagingToken.ID+"/rotate"), nil, &values); err != nil {
			return err
		}
		values.ID = stagingToken.ID
	}
	if values.ClientID == "" || values.ClientSecret == "" {
		return fmt.Errorf("Cloudflare answered for the service token %q (ID %s) without its values. Delete it at %s and run this command again", stagingName, values.ID, stagingServiceTokensPage)
	}
	if err := e.updateTokenFile(path, map[string]string{stagingAccessClientIDVariable: values.ClientID, stagingAccessClientSecretVariable: values.ClientSecret}); err != nil {
		return fmt.Errorf("%v. Cloudflare made the service token %q (ID %s), whose secret nobody can read again: delete it at %s and run this command again", err, stagingName, values.ID, stagingServiceTokensPage)
	}
	if stagingToken == nil {
		e.say("  Made the service token %q (ID %s), valid for a year, and wrote its values into your token file", stagingName, values.ID)
		e.say("  as %s and %s.", stagingAccessClientIDVariable, stagingAccessClientSecretVariable)
		e.say("  Your coding agent gives each staging Access application a Service Auth policy with the ID %s. See it at %s.", values.ID, stagingServiceTokensPage)
	} else {
		e.say("  Gave the service token %q (ID %s) a new secret; the old one stopped working. Wrote it into your token file as %s.", stagingName, values.ID, stagingAccessClientSecretVariable)
		e.say("  Each team member enters it from the password manager with set-up-outside-services personal-token staging-access; replace CI's two secrets too.")
	}
	e.say("  Save both in your password manager, and in CI's secrets when CI tests staging. lock-the-desk keeps both in the recovery bundle.")
	return nil
}

// sayStagingServiceTokenState tells a person whose token file lacks the
// existing service token's values where they are.
func (e *environment) sayStagingServiceTokenState(settings systemSettings, exists bool, name string) error {
	if !settings.hasStagingServer || !exists {
		return nil
	}
	path := e.tokenFilePath(settings)
	e.say("")
	e.say("Staging's Access service token opens your staging pages without a person's sign-in, for CI and your local app tests.")
	if tokenFileValue(path, stagingAccessClientIDVariable) != "" && tokenFileValue(path, stagingAccessClientSecretVariable) != "" {
		e.say("  Its values are already in your token file. Unchanged.")
		return nil
	}
	e.say("  Cloudflare has the service token %q already, but this systems desk's token file lacks its values.", name)
	e.say("  Its Client ID and Client Secret are in your password manager. Enter them with: set-up-outside-services personal-token staging-access")
	return nil
}

// deleteTheTokensOfALeavingPerson deletes, by name, the tokens the command
// made for a person who leaves the team: the desk's token, the posting key,
// and a link token a stopped run left.
func (e *environment) deleteTheTokensOfALeavingPerson(settings systemSettings, accountID, leaving string) error {
	e.say("Cloudflare: this command deletes the tokens it made for %s, who leaves the team, found by their names.", leaving)
	link, err := e.askForTheLinkToken(settings, accountID)
	if err != nil {
		return err
	}
	defer e.deleteTheLinkToken(link)
	deleted := 0
	for _, name := range []string{deskTokenName(settings, leaving), statusPagePostingTokenName(settings, leaving), linkTokenName(settings, leaving)} {
		tokens, err := link.accountTokensNamed(name)
		if err != nil {
			return err
		}
		for _, token := range tokens {
			if err := link.deleteAccountToken(token.ID); err != nil {
				return err
			}
			deleted++
			e.say("  Deleted the token %q (ID %s).", name, token.ID)
		}
	}
	if deleted == 0 {
		e.say("  Cloudflare has no token named after %s. Nothing to delete.", leaving)
	}
	e.say("See the account's tokens: https://dash.cloudflare.com/%s/api-tokens", accountID)
	return nil
}

// cloudflareAccount is an account a token reaches, by its ID and name.
type cloudflareAccount struct {
	ID   string `json:"id"`
	Name string `json:"name"`
}

// accounts lists the accounts a token reaches.
// https://developers.cloudflare.com/api/resources/accounts/methods/list/
func (c *cloudflareClient) accounts() ([]cloudflareAccount, error) {
	var listed []cloudflareAccount
	if err := c.call(http.MethodGet, "/accounts", nil, &listed); err != nil {
		return nil, err
	}
	var accounts []cloudflareAccount
	for _, account := range listed {
		if cloudflareAccountIDPattern.MatchString(account.ID) {
			accounts = append(accounts, account)
		}
	}
	return accounts, nil
}

// screenText keeps a line from a provider or the settings to printable
// text, so it cannot move the cursor or clear the screen.
func screenText(text string) string {
	return strings.Map(func(r rune) rune {
		if r < ' ' || r == 0x7f {
			return ' '
		}
		return r
	}, strings.TrimSpace(text))
}

// cloudflareZone is a domain at Cloudflare, with the two nameservers
// Cloudflare gave it, which the domain's registrar must point at.
type cloudflareZone struct {
	ID          string   `json:"id"`
	Name        string   `json:"name"`
	Status      string   `json:"status"`
	NameServers []string `json:"name_servers"`
}

// findZone finds the account's zone of exactly this name, or nil.
// https://developers.cloudflare.com/api/resources/zones/methods/list/
func (c *cloudflareClient) findZone(name string) (*cloudflareZone, error) {
	var zones []cloudflareZone
	if err := c.call(http.MethodGet, "/zones?name="+url.QueryEscape(name)+"&account.id="+c.accountID, nil, &zones); err != nil {
		return nil, err
	}
	for i := range zones {
		if zones[i].Name == name {
			return &zones[i], nil
		}
	}
	return nil, nil
}

// The short-lived token that adds the domain, copies its DNS records, and
// gives the account its workers.dev address. Zone Write can also delete a
// zone, so neither the desk's token nor any other token that stays holds it.
var domainSetUpPermissions = []permissionGroup{{"Zone Write", scopeZone}, {"Zone Read", scopeZone}, {"DNS Write", scopeZone}}

func domainSetUpTokenPlan(s systemSettings, accountID string) cloudflareCredentialPlan {
	return cloudflareCredentialPlan{
		Purpose:   "a short-lived token that adds your domain",
		TokenName: s.ProjectName + ": set-up-outside-services adds the domain, deleted after the run",
		Policies:  []tokenPolicyPlan{onEveryZone(accountID, domainSetUpPermissions...), onAccount(accountID, permissionWorkersScripts)},
		Form:      apiTokenForm,
	}
}

// addTheDomain adds the domain to the Cloudflare account when it is not
// there yet, copies the DNS records Cloudflare finds at the domain's current
// nameservers, and gives the account its workers.dev address, where the
// MMHotline-down alarm answers. It returns the zone with its nameservers.
func (e *environment) addTheDomain(link *cloudflareClient, settings systemSettings, domain string) (cloudflareZone, error) {
	plan := domainSetUpTokenPlan(settings, link.accountID)
	ids, err := link.permissionGroupIDs(append(append([]permissionGroup{}, domainSetUpPermissions...), permissionWorkersScripts))
	if err != nil {
		return cloudflareZone{}, err
	}
	var zone cloudflareZone
	err = e.withShortLivedToken(link, plan, ids, "the short-lived domain token", func(client *cloudflareClient) error {
		found, err := client.findZone(domain)
		if err != nil {
			return err
		}
		if found != nil {
			zone = *found
			e.say("  The domain %s is in the Cloudflare account already, %s. Unchanged.", domain, zone.Status)
		} else {
			// https://developers.cloudflare.com/api/resources/zones/methods/create/
			body := map[string]any{"name": domain, "account": map[string]string{"id": link.accountID}, "type": "full"}
			if err := client.call(http.MethodPost, "/zones", body, &zone); err != nil {
				return err
			}
			e.say("  Added the domain %s to Cloudflare.", domain)
			// Cloudflare reads the records at the domain's current
			// nameservers, so the site keeps working when the domain moves.
			// https://developers.cloudflare.com/api/resources/dns/subresources/records/methods/scan/
			var scan struct {
				RecordsAdded int `json:"recs_added"`
			}
			if err := client.call(http.MethodPost, "/zones/"+zone.ID+"/dns_records/scan", nil, &scan); err != nil {
				return err
			}
			e.say("  Copied %d DNS records from the domain's current nameservers.", scan.RecordsAdded)
		}
		return e.ensureWorkersSubdomain(client, settings)
	})
	if err == nil && len(zone.NameServers) == 0 {
		err = fmt.Errorf("Cloudflare gave the domain %s no nameservers", domain)
	}
	return zone, err
}

// ensureWorkersSubdomain gives the account its workers.dev address when it
// has none: the project's name, or the name with a random ending when another
// account has it.
// https://developers.cloudflare.com/api/resources/workers/subresources/subdomains/
func (e *environment) ensureWorkersSubdomain(client *cloudflareClient, settings systemSettings) error {
	var current struct {
		Subdomain string `json:"subdomain"`
	}
	err := client.call(http.MethodGet, client.account("/workers/subdomain"), nil, &current)
	var refusal *apiError
	if err != nil && !errors.As(err, &refusal) {
		return err
	}
	if err == nil && current.Subdomain != "" {
		e.say("  The account's workers.dev address is %s.workers.dev already. Unchanged.", current.Subdomain)
		return nil
	}
	random := make([]byte, 3)
	if _, err := rand.Read(random); err != nil {
		return err
	}
	name := settings.keyNamePrefix()
	for _, candidate := range []string{name, name + "-" + hex.EncodeToString(random)} {
		err = client.call(http.MethodPut, client.account("/workers/subdomain"), map[string]string{"subdomain": candidate}, nil)
		if err == nil {
			e.say("  Gave the account the workers.dev address %s.workers.dev.", candidate)
			return nil
		}
		if !errors.As(err, &refusal) {
			return err
		}
	}
	return err
}
