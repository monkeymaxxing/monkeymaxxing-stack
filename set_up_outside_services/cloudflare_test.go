package main

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"io"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/monkeymaxxing/monkeymaxxing-stack/set_up_outside_services/internal/standins"
)

const (
	deskTokenNameForAlex      = "acme_systems: alex's systems desk sets up Cloudflare"
	postingTokenNameForAlex   = "acme_systems: alex posts to the status page"
	linkTokenNameForAlex      = "acme_systems: alex makes tokens with set-up-outside-services, deleted after the run"
	shortLivedAccessTokenName = "acme_systems: set-up-outside-services sets up Access, deleted after the run"
	statusBucket              = "mmhotline-status-status-example-org-0a1b2c3d"
)

func r2Secret(value string) string {
	digest := sha256.Sum256([]byte(value))
	return hex.EncodeToString(digest[:])
}

// groupID is the stand-in's ID of a permission group, by name and scope.
func groupID(name, scope string) string {
	for _, group := range standins.PermissionGroups {
		if group.Name == name && group.Scope == scope {
			return group.ID
		}
	}
	return "no such group"
}

func (h *harness) tokenFile() string {
	return filepath.Join(h.e.home, ".config", "monkeymaxxing-stack", "acme_systems.env")
}

func (h *harness) onlyLiveToken(name string) *standins.CloudflareToken {
	h.t.Helper()
	tokens := h.cloudflare.LiveTokensNamed(name)
	if len(tokens) != 1 {
		h.t.Fatalf("want one live token %q, got %d", name, len(tokens))
	}
	return tokens[0]
}

// The person makes one token by the link; the command makes every other
// token, saves each where it is used, and deletes the link token.
func TestCloudflareMakesEveryTokenFromOneLinkToken(t *testing.T) {
	h := newHarness(t, true, true)
	if err := h.runCloudflare(); err != nil {
		t.Fatalf("cloudflare: %v\n%s", err, h.out)
	}
	if !strings.Contains(h.out.String(), "permissionGroupKeys="+"%5B%7B%22key%22%3A%22account_api_tokens%22%2C%22type%22%3A%22edit%22%7D%5D") ||
		!strings.Contains(h.out.String(), "name=acme_systems%3A+alex+makes+tokens") {
		t.Fatalf("the link must fill in Account API Tokens Edit and the link token's name:\n%s", h.out)
	}
	// Cloudflare's form needs Review token before Create token, is long, shows
	// the token once, and may ask which account: the prompt says all three.
	for _, text := range []string{"scroll to the bottom, below the list of permissions", "Select Review token, then Create token.", "shows the token only once",
		"If Cloudflare asks which account, pick the one whose ID is " + testAccountID} {
		if !strings.Contains(h.out.String(), text) {
			t.Fatalf("the prompt must say %q:\n%s", text, h.out)
		}
	}

	// The desk's token: its permission groups, the zone ones on every zone
	// of the account, in the API proxy and the token file.
	desk := h.onlyLiveToken(deskTokenNameForAlex)
	requireDeskTokenRights(t, desk)
	zonePolicy := string(desk.Policies[1])
	if !strings.Contains(zonePolicy, `"com.cloudflare.api.account.zone.*":"*"`) || !strings.Contains(zonePolicy, groupID("Zone Read", scopeZone)) {
		t.Fatalf("the zone permissions must apply to every zone, with the zone's Zone Read: %s", zonePolicy)
	}
	if h.proxy["cloudflare"] != desk.Value || tokenFileValue(h.tokenFile(), "CLOUDFLARE_API_TOKEN") != desk.Value || tokenFileValue(h.tokenFile(), "CLOUDFLARE_ACCOUNT_ID") != testAccountID {
		t.Fatal("the systems desk's token must reach the proxy and the token file, with the account ID")
	}

	for _, tunnel := range h.cloudflare.Tunnels {
		vaultName := map[string]string{"acme_systems-apps": "apps_cloudflare_tunnel_token", "acme_systems-util01": "util01_cloudflare_tunnel_token", "acme_systems-staging_apps": "staging_apps_cloudflare_tunnel_token"}[tunnel.Name]
		if tunnel.ConfigSrc != "local" || vaultName == "" || h.vault.values[vaultName] != tunnel.Token {
			t.Fatalf("tunnel %s must be locally managed, named after the project, and in the vault", tunnel.Name)
		}
	}
	if len(h.cloudflare.Tunnels) != 3 || !h.cloudflare.R2Buckets["acme-shop-uploads"] || !h.cloudflare.R2Buckets["acme-shop-staging-uploads"] {
		t.Fatal("want three tunnels and the app's production and staging uploads buckets")
	}

	r2Keys := []struct{ name, idKey, secretKey, group, bucket string }{
		{"acme_systems: shop reads and writes its uploads", "shop_R2_ACCESS_KEY_ID", "shop_R2_SECRET_ACCESS_KEY", "Workers R2 Storage Bucket Item Write", "acme-shop-uploads"},
		{"acme_systems: shop on staging reads and writes its uploads", "staging_shop_R2_ACCESS_KEY_ID", "staging_shop_R2_SECRET_ACCESS_KEY", "Workers R2 Storage Bucket Item Write", "acme-shop-staging-uploads"},
		{"acme_systems: util01 reads the apps' uploads", "uploads_r2_read_only_access_key_id", "uploads_r2_read_only_secret_access_key", "Workers R2 Storage Bucket Item Read", "acme-shop-uploads"},
		{"acme_systems: MMHotline posts to the status page", "mmhotline_status_page_r2_access_key_id", "mmhotline_status_page_r2_secret_access_key", "Workers R2 Storage Bucket Item Write", statusBucket},
	}
	for _, key := range r2Keys {
		token := h.onlyLiveToken(key.name)
		if h.vault.values[key.idKey] != token.ID || h.vault.values[key.secretKey] != r2Secret(token.Value) {
			t.Fatalf("%q is not saved as an R2 key", key.name)
		}
		policy := string(token.Policies[0])
		if !strings.Contains(policy, "_default_"+key.bucket) || !strings.Contains(policy, groupID(key.group, scopeR2Bucket)) || strings.Count(policy, "com.cloudflare.edge.r2.bucket.") != 1 {
			t.Fatalf("%q has the wrong scope: %s", key.name, policy)
		}
	}
	downAlarm := h.onlyLiveToken("acme_systems: MMHotline uploads the MMHotline-down alarm")
	if h.vault.values["mmhotline_down_alarm_cloudflare_api_token"] != downAlarm.Value || !strings.Contains(string(downAlarm.Policies[0]), "com.cloudflare.api.account."+testAccountID) {
		t.Fatal("the MMHotline-down alarm's token must be saved as the token itself, on the account")
	}

	// The person's own posting key, in the token file where mmhotline
	// status-page on the desk reads it, for the page's bucket only.
	posting := h.onlyLiveToken(postingTokenNameForAlex)
	if tokenFileValue(h.tokenFile(), "MMHOTLINE_STATUS_PAGE_R2_ACCESS_KEY_ID") != posting.ID || tokenFileValue(h.tokenFile(), "MMHOTLINE_STATUS_PAGE_R2_SECRET_ACCESS_KEY") != r2Secret(posting.Value) ||
		!strings.HasSuffix(tokenFileValue(h.tokenFile(), "MMHOTLINE_STATUS_PAGE_R2_BUCKET_URL"), "/"+statusBucket) {
		t.Fatal("the token file must get the page's bucket address and the person's derived posting key")
	}
	if policy := string(posting.Policies[0]); !strings.Contains(policy, "_default_"+statusBucket) || strings.Count(policy, "r2.bucket.") != 1 {
		t.Fatalf("the posting key must reach the status page's bucket only: %s", policy)
	}

	// Access: One-time PIN and staging's service token, made with a
	// short-lived token that is deleted.
	if len(h.cloudflare.IdentityProviders) != 1 || h.cloudflare.IdentityProviders[0].Type != "onetimepin" {
		t.Fatal("the command must add the One-time PIN login method")
	}
	if len(h.cloudflare.ServiceTokens) != 1 || tokenFileValue(h.tokenFile(), stagingAccessClientSecretVariable) != h.cloudflare.ServiceTokens[0].ClientSecret {
		t.Fatal("staging's service token must be made and written into the token file")
	}
	for _, name := range []string{shortLivedAccessTokenName, linkTokenNameForAlex} {
		if len(h.cloudflare.LiveTokensNamed(name)) != 0 {
			t.Fatalf("the token %q must be deleted at the end", name)
		}
	}
	h.requireNoSecretInOutput(desk.Value, r2Secret(posting.Value), posting.Value, "link-token-value-00000001", h.cloudflare.ServiceTokens[0].ClientSecret)
}

// requireDeskTokenRights checks the desk token holds every zone right a
// team's site settings may need, besides the Stack's own, and nothing that
// makes tokens, adds Access login methods, or deletes a zone.
func requireDeskTokenRights(t *testing.T, desk *standins.CloudflareToken) {
	t.Helper()
	held := "|" + strings.Join(desk.Permissions, "|") + "|"
	for _, name := range []string{
		"Cloudflare Tunnel Write", "Access: Apps and Policies Write", "Workers R2 Storage Write",
		"DNS Write", "Zone Read", "Zone Settings Write", "Dynamic URL Redirects Write", "Bot Management Write",
		"Page Rules Write", "SSL and Certificates Write", "Zone WAF Write", "Firewall Services Write",
		"Config Settings Write", "Origin Write", "Cache Settings Write", "Zone Transform Rules Write", "Workers Routes Write",
	} {
		if !strings.Contains(held, "|"+name+"|") {
			t.Fatalf("the systems desk's token lacks %s: %v", name, desk.Permissions)
		}
	}
	for _, name := range []string{"API Tokens", "Identity Providers, and Groups Write", "|Zone Write|"} {
		if strings.Contains(held, name) {
			t.Fatalf("the systems desk's token must not hold %s: %v", name, desk.Permissions)
		}
	}
}

// A desk set up by an earlier Stack, whose token lacks the zone rights the
// desk token has now, gets them by one rerun: the same token, the same value.
func TestARerunWidensAnEarlierDeskTokenAndKeepsItsValue(t *testing.T) {
	h := newHarness(t, false, false)
	if err := h.runCloudflare(); err != nil {
		t.Fatalf("cloudflare: %v\n%s", err, h.out)
	}
	desk := h.onlyLiveToken(deskTokenNameForAlex)
	// The desk token as Stack 0.3.1 made it: four zone groups.
	h.cloudflare.Lock()
	narrow := `{"effect":"allow","resources":{"com.cloudflare.api.account.` + testAccountID + `":{"com.cloudflare.api.account.zone.*":"*"}},"permission_groups":[` +
		`{"id":"` + groupID("DNS Write", scopeZone) + `"},{"id":"` + groupID("Cache Settings Write", scopeZone) + `"},` +
		`{"id":"` + groupID("Zone Read", scopeZone) + `"},{"id":"` + groupID("Zone Transform Rules Write", scopeZone) + `"}]}`
	desk.Policies[1] = []byte(narrow)
	desk.Permissions = append(desk.Permissions[:len(deskAccountPermissions)], "DNS Write", "Cache Settings Write", "Zone Read", "Zone Transform Rules Write")
	h.cloudflare.Unlock()
	if err := h.runCloudflare(); err != nil {
		t.Fatalf("rerun: %v\n%s", err, h.out)
	}
	now := h.onlyLiveToken(deskTokenNameForAlex)
	if now.ID != desk.ID || now.Value != desk.Value || h.proxy["cloudflare"] != desk.Value {
		t.Fatal("the rerun must keep the desk token and its value")
	}
	requireDeskTokenRights(t, now)
	if !strings.Contains(h.out.String(), "Updated its rights to:") {
		t.Fatalf("the person must hear the desk token's rights changed:\n%s", h.out)
	}
}

// A rerun keeps every token that is saved where it is used and still
// listed, and makes only what is missing, such as a new app's key.
func TestCloudflareRerunCreatesNothingAndAddsANewAppsBucketToTheReader(t *testing.T) {
	h := newHarness(t, false, true)
	if err := h.runCloudflare(); err != nil {
		t.Fatal(err)
	}
	desk := h.onlyLiveToken(deskTokenNameForAlex)
	posting := h.onlyLiveToken(postingTokenNameForAlex)
	reader := h.onlyLiveToken("acme_systems: util01 reads the apps' uploads")
	sets := len(h.vault.sets)
	path := filepath.Join(h.e.directory, projectSettingsFile)
	text, _ := os.ReadFile(path)
	writeFile(t, path, strings.Replace(string(text), "  backups:", `    blog:
      secrets_from_vault: {R2_KEY: {where_the_value_comes_from: generated_by_the_setup}, R2_SECRET: {where_the_value_comes_from: generated_by_the_setup}}
      production_uploads_r2_bucket: acme-blog-uploads
      production_uploads_r2_key_variables: {access_key_id: R2_KEY, secret_access_key: R2_SECRET}
  backups:`, 1))
	h.commitAll("Add the blog app")
	h.cloudflare.Lock()
	h.cloudflare.Calls = nil
	h.cloudflare.Unlock()
	if err := h.runCloudflare(); err != nil {
		t.Fatalf("rerun: %v\n%s", err, h.out)
	}
	calls := h.cloudflare.Snapshot()["calls"].([]string)
	// Two tokens: the short-lived one that checks the domain, and the new
	// app's key.
	if h.count(calls, "POST /accounts/"+testAccountID+"/cfd_tunnel") != 0 || h.count(calls, "POST /accounts/"+testAccountID+"/tokens") != 2 ||
		h.count(calls, "POST /accounts/"+testAccountID+"/access/identity_providers") != 0 {
		t.Fatalf("the rerun must make only the new app's key: %v", calls)
	}
	if len(h.vault.sets) != sets+2 || h.vault.values["blog_R2_KEY"] == "" {
		t.Fatal("the rerun must save only the new app's key")
	}
	if h.onlyLiveToken(deskTokenNameForAlex).ID != desk.ID || h.onlyLiveToken(postingTokenNameForAlex).ID != posting.ID {
		t.Fatal("the rerun must keep the person's own tokens")
	}
	reader = h.onlyLiveToken("acme_systems: util01 reads the apps' uploads")
	if !strings.Contains(string(reader.Policies[0]), "_default_acme-blog-uploads") || h.vault.values["uploads_r2_read_only_access_key_id"] != reader.ID {
		t.Fatal("the reader must gain the new bucket and keep its key")
	}
	if len(h.cloudflare.LiveTokensNamed(linkTokenNameForAlex)) != 0 {
		t.Fatal("the rerun's link token must be deleted too")
	}
}

// The rerun rule for the person's own tokens: one is kept only while it is
// the only token of its name and the token file holds it. Otherwise a new
// one is made, saved, and every other token of the name is deleted.
func TestThePersonsTokensAreRemadeWhenTheTokenFileOrCloudflareDisagree(t *testing.T) {
	h := newHarness(t, false, false)
	// A token the person made by hand before, which only the user verify
	// call accepts, sits in the token file.
	h.cloudflare.AddToken("Alex's own token", "users-own-token-value-0001", true)
	if err := updateTokenFile(h.tokenFile(), map[string]string{"CLOUDFLARE_API_TOKEN": "users-own-token-value-0001"}); err != nil {
		t.Fatal(err)
	}
	if err := h.runCloudflare(); err != nil {
		t.Fatalf("cloudflare: %v\n%s", err, h.out)
	}
	if !strings.Contains(h.out.String(), "https://dash.cloudflare.com/profile/api-tokens") {
		t.Fatal("the person must hear where to delete the earlier token of their own")
	}
	first := h.onlyLiveToken(deskTokenNameForAlex)
	// A second token of the same name, such as one an earlier desk left.
	h.cloudflare.AddToken(deskTokenNameForAlex, "left-by-an-earlier-desk-0001", false)
	if err := h.runCloudflare(); err != nil {
		t.Fatalf("rerun: %v\n%s", err, h.out)
	}
	now := h.onlyLiveToken(deskTokenNameForAlex)
	if now.ID == first.ID || h.proxy["cloudflare"] != now.Value || tokenFileValue(h.tokenFile(), "CLOUDFLARE_API_TOKEN") != now.Value {
		t.Fatal("two tokens of one name: the rerun must make a new one, save it, and delete both others")
	}
}

// A failed write of the proxy's file keeps the proxy's old token, so the new
// token is deleted and the token file keeps its line.
func TestAFailedProxyWriteDeletesTheNewDeskToken(t *testing.T) {
	h := newHarness(t, false, false)
	h.e.writeProxyFile = func(request proxyFileRequest) error { return errors.New("the proxy refused its settings") }
	err := h.runCloudflare()
	if err == nil || !strings.Contains(err.Error(), "the proxy refused") || !strings.Contains(err.Error(), "deleted the new token") {
		t.Fatalf("want the proxy's failure and the new token deleted, got %v", err)
	}
	if len(h.cloudflare.LiveTokensNamed(deskTokenNameForAlex)) != 0 || tokenFileValue(h.tokenFile(), "CLOUDFLARE_API_TOKEN") != "" {
		t.Fatal("nothing may be left of the new systems desk token")
	}
	if len(h.cloudflare.LiveTokensNamed(linkTokenNameForAlex)) != 0 {
		t.Fatal("a failed run deletes its link token too")
	}
}

func TestCloudflareRevokesTheNewTokenWhenTheVaultFails(t *testing.T) {
	h := newHarness(t, false, false)
	h.vault.failOn["mmhotline_down_alarm_cloudflare_api_token"] = true
	err := h.runCloudflare()
	if err == nil || !strings.Contains(err.Error(), "so this command revoked the new Cloudflare token") {
		t.Fatalf("want the issued-but-unsaved outcome, got %v", err)
	}
	if len(h.cloudflare.LiveTokensNamed("acme_systems: MMHotline uploads the MMHotline-down alarm")) != 0 {
		t.Fatal("the new token must be revoked")
	}
	if len(h.cloudflare.LiveTokensNamed(linkTokenNameForAlex)) != 0 {
		t.Fatal("a failed run deletes its link token; a rerun takes a new one")
	}
	delete(h.vault.failOn, "mmhotline_down_alarm_cloudflare_api_token")
	if err := h.runCloudflare(); err != nil {
		t.Fatalf("rerun: %v\n%s", err, h.out)
	}
	h.onlyLiveToken("acme_systems: MMHotline uploads the MMHotline-down alarm")
	h.onlyLiveToken(deskTokenNameForAlex)
}

// A link token left by a run that stopped, such as one ended with Ctrl-C,
// is deleted by the next run.
func TestALinkTokenLeftByAStoppedRunIsDeleted(t *testing.T) {
	h := newHarness(t, false, false)
	h.addLinkToken()
	if err := h.runCloudflare(); err != nil {
		t.Fatalf("cloudflare: %v\n%s", err, h.out)
	}
	if len(h.cloudflare.LiveTokensNamed(linkTokenNameForAlex)) != 0 || !strings.Contains(h.out.String(), "left by a run that stopped") {
		t.Fatal("both link tokens must be gone")
	}
}

// linkTokenOfThisRun is the link token the run took, deleted or not.
func (h *harness) linkTokenOfThisRun() *standins.CloudflareToken {
	h.t.Helper()
	var found *standins.CloudflareToken
	for _, token := range h.cloudflare.Tokens {
		if token.Name == linkTokenNameForAlex {
			found = token
		}
	}
	if found == nil {
		h.t.Fatal("no link token")
	}
	return found
}

// The form makes the link token with no expiration, so before anything is
// made the run sets it to end by itself 24 hours later, keeping its name
// and its one policy.
func TestTheLinkTokenEndsByItselfAfter24Hours(t *testing.T) {
	h := newHarness(t, false, false)
	h.e.now = func() time.Time { return time.Date(2026, 11, 12, 15, 30, 20, 0, time.UTC) }
	if err := h.runCloudflare(); err != nil {
		t.Fatalf("cloudflare: %v\n%s", err, h.out)
	}
	link := h.linkTokenOfThisRun()
	if link.ExpiresOn != "2026-11-13T15:30:20Z" {
		t.Fatalf("the link token must end 24 hours after the run checked it, got %q", link.ExpiresOn)
	}
	policy := string(link.Policies[0])
	if len(link.Policies) != 1 || !strings.Contains(policy, `"effect":"allow"`) || !strings.Contains(policy, groupID("Account API Tokens Write", scopeAccount)) ||
		!strings.Contains(policy, "com.cloudflare.api.account."+testAccountID) {
		t.Fatalf("the update must keep the link token's one policy: %v", policy)
	}
	calls := h.cloudflare.Snapshot()["calls"].([]string)
	update := "PUT /accounts/" + testAccountID + "/tokens/" + link.ID
	for _, call := range calls {
		if call == update {
			break
		}
		if strings.HasPrefix(call, "POST ") {
			t.Fatalf("the link token's end must be set before anything is made: %v", calls)
		}
	}
	if h.count(calls, update) != 1 || !link.Deleted ||
		!strings.Contains(h.out.String(), "Set the link token to end by itself at 15:30 UTC tomorrow, in case this run is cut off. The run deletes it at its end.") {
		t.Fatalf("want one update, the line that says so, and the token deleted at the end:\n%s", h.out)
	}
}

// A link token that ends sooner already is left as it is.
func TestALinkTokenThatEndsSoonerIsLeftAlone(t *testing.T) {
	h := newHarness(t, false, false)
	h.e.now = func() time.Time { return time.Date(2026, 11, 12, 15, 30, 0, 0, time.UTC) }
	h.answers = []string{h.addLinkToken()}
	link := h.onlyLiveToken(linkTokenNameForAlex)
	link.ExpiresOn = "2026-11-12T18:00:00Z"
	if err := runCloudflare(h.e, nil); err != nil {
		t.Fatalf("cloudflare: %v\n%s", err, h.out)
	}
	calls := h.cloudflare.Snapshot()["calls"].([]string)
	if link.ExpiresOn != "2026-11-12T18:00:00Z" || h.count(calls, "PUT /accounts/"+testAccountID+"/tokens/"+link.ID) != 0 ||
		!strings.Contains(h.out.String(), "The link token ends by itself at 2026-11-12 18:00 UTC already") {
		t.Fatalf("an earlier end must stay unchanged:\n%s", h.out)
	}
}

// When Cloudflare refuses the update, the run stops before it makes any
// token, tunnel, or bucket, and says what to do.
func TestARefusedLinkTokenEndStopsTheRunBeforeAnythingIsMade(t *testing.T) {
	h := newHarness(t, true, true)
	h.cloudflare.Failures["PUT /accounts/"+testAccountID+"/tokens/"] = "refuse"
	err := h.runCloudflare()
	if err == nil || !strings.Contains(err.Error(), "so this run stopped before making anything") ||
		!strings.Contains(err.Error(), "Make a new link token with the link above") || !strings.Contains(err.Error(), "under TTL") {
		t.Fatalf("want the refusal and what to do, got %v", err)
	}
	calls := h.cloudflare.Snapshot()["calls"].([]string)
	for _, call := range calls {
		if strings.HasPrefix(call, "POST ") {
			t.Fatalf("nothing may be made after a refused update: %v", calls)
		}
	}
	if len(h.cloudflare.Tunnels) != 0 || len(h.cloudflare.R2Buckets) != 0 || len(h.vault.sets) != 0 {
		t.Fatal("no tunnel, bucket, or key may be made")
	}
	if len(h.cloudflare.LiveTokensNamed(linkTokenNameForAlex)) != 0 {
		t.Fatal("the refused link token is deleted, since the person makes a new one")
	}
}

func TestCloudflareRefusesATokenThatIsNoLinkToken(t *testing.T) {
	h := newHarness(t, false, false)
	h.cloudflare.AddToken("Alex's own token", "users-own-token-value-0001", true, standins.PermissionAccountAPITokensWrite)
	h.answers = []string{"users-own-token-value-0001"}
	err := runCloudflare(h.e, nil)
	if err == nil || !strings.Contains(err.Error(), "Make a new link token with the link") {
		t.Fatalf("a user token is no link token, got %v", err)
	}
	if strings.Contains(err.Error(), "with the link token with") ||
		!strings.Contains(err.Error(), "from the link token with HTTP 401") ||
		!strings.Contains(err.Error(), "Most likely the token was not copied whole, or it was made in another account than "+testAccountID) {
		t.Fatalf("the refusal must read plainly and name the likely causes, got %v", err)
	}
	h.cloudflare.AddToken("Another account token", "account-token-value-0001", false, standins.PermissionTunnelWrite)
	h.answers = []string{"account-token-value-0001"}
	if err := runCloudflare(h.e, nil); err == nil || !strings.Contains(err.Error(), "needs Account API Tokens Edit") {
		t.Fatalf("a token that cannot list tokens is no link token, got %v", err)
	}
	if len(h.cloudflare.Tunnels) != 0 || len(h.vault.sets) != 0 {
		t.Fatal("nothing may change with a wrong token")
	}
}

// A real Cloudflare account answered 409 to the One-time PIN although its
// list showed none: the command takes that as the login method being there.
func TestOneTimePINThatExistsAlreadyIsSuccess(t *testing.T) {
	h := newHarness(t, false, false)
	h.cloudflare.OneTimePINConflictsUnlisted = true
	if err := h.runCloudflare(); err != nil {
		t.Fatalf("cloudflare: %v\n%s", err, h.out)
	}
	if !strings.Contains(h.out.String(), "One-time PIN is a login method already") || len(h.cloudflare.LiveTokensNamed(shortLivedAccessTokenName)) != 0 {
		t.Fatal("a 409 means the login method is there, and the short-lived token is deleted")
	}
}

// Without the One-time PIN missing and without staging01, no short-lived
// Access token is made at all.
func TestNoShortLivedTokenWhenAccessHasEverything(t *testing.T) {
	h := newHarness(t, false, false)
	h.cloudflare.IdentityProviders = append(h.cloudflare.IdentityProviders, &standins.IdentityProvider{ID: "pin", Name: "One-time PIN", Type: "onetimepin"})
	if err := h.runCloudflare(); err != nil {
		t.Fatalf("cloudflare: %v\n%s", err, h.out)
	}
	if strings.Contains(h.out.String(), "sets up Access") {
		t.Fatal("no short-lived Access token is needed")
	}
}

// Replacing a key truly replaces it: a new one where the old one was, and
// the old one deleted at Cloudflare.
func TestReplaceKeyMakesNewKeysAndDeletesTheOldOnes(t *testing.T) {
	h := newHarness(t, true, true)
	if err := h.runCloudflare(); err != nil {
		t.Fatal(err)
	}
	oldApp := h.onlyLiveToken("acme_systems: shop reads and writes its uploads")
	oldDesk := h.onlyLiveToken(deskTokenNameForAlex)
	oldPosting := h.onlyLiveToken(postingTokenNameForAlex)
	oldTunnel := h.vault.values["apps_cloudflare_tunnel_token"]
	oldStagingSecret := tokenFileValue(h.tokenFile(), stagingAccessClientSecretVariable)
	oldReader := h.onlyLiveToken("acme_systems: util01 reads the apps' uploads")
	h.out.Reset()
	// While the command waits, the vault is pushed with the new key, and the
	// old key and the link token still work.
	asked := false
	h.e.confirm = func(string) (string, error) {
		asked = true
		if len(h.cloudflare.LiveTokensNamed("acme_systems: shop reads and writes its uploads")) != 2 ||
			len(h.cloudflare.LiveTokensNamed(linkTokenNameForAlex)) != 1 {
			t.Fatal("while it waits, the old key and the link token must still work")
		}
		h.requirePushedVaultCommit("cloudflare")
		return "", nil
	}
	if err := h.runCloudflare("--replace-key", "shop_R2_ACCESS_KEY_ID", "--replace-key", "apps_cloudflare_tunnel_token",
		"--replace-key", "CLOUDFLARE_API_TOKEN", "--replace-key", "MMHOTLINE_STATUS_PAGE_R2_ACCESS_KEY_ID",
		"--replace-key", "STAGING_ACCESS_CLIENT_SECRET"); err != nil {
		t.Fatalf("replace: %v\n%s", err, h.out)
	}
	app := h.onlyLiveToken("acme_systems: shop reads and writes its uploads")
	if app.ID == oldApp.ID || h.vault.values["shop_R2_ACCESS_KEY_ID"] != app.ID || h.vault.values["shop_R2_SECRET_ACCESS_KEY"] != r2Secret(app.Value) {
		t.Fatal("the app's key must be new, in the vault, and the old one deleted")
	}
	desk := h.onlyLiveToken(deskTokenNameForAlex)
	if desk.ID == oldDesk.ID || h.proxy["cloudflare"] != desk.Value || tokenFileValue(h.tokenFile(), "CLOUDFLARE_API_TOKEN") != desk.Value {
		t.Fatal("the systems desk's token must be new, in the proxy and the token file, and the old one deleted")
	}
	posting := h.onlyLiveToken(postingTokenNameForAlex)
	if posting.ID == oldPosting.ID || tokenFileValue(h.tokenFile(), "MMHOTLINE_STATUS_PAGE_R2_ACCESS_KEY_ID") != posting.ID {
		t.Fatal("the posting key must be new and the old one deleted")
	}
	tunnel := h.cloudflare.Tunnels[0]
	if tunnel.Name != "acme_systems-apps" || h.vault.values["apps_cloudflare_tunnel_token"] == oldTunnel || h.vault.values["apps_cloudflare_tunnel_token"] != tunnel.Token {
		t.Fatal("the tunnel must get a new secret and its new token in the vault")
	}
	if secret := tokenFileValue(h.tokenFile(), stagingAccessClientSecretVariable); secret == oldStagingSecret || secret != h.cloudflare.ServiceTokens[0].ClientSecret || len(h.cloudflare.ServiceTokens) != 1 {
		t.Fatal("staging's service token must keep its ID and get a new secret")
	}
	if h.onlyLiveToken("acme_systems: util01 reads the apps' uploads").ID != oldReader.ID {
		t.Fatal("a key not named must stay")
	}
	if !asked || !strings.Contains(h.out.String(), "./server_management_scripts/run_mmx_on_util01 run every_server") ||
		len(h.cloudflare.LiveTokensNamed(linkTokenNameForAlex)) != 0 {
		t.Fatal("the person must get the run's command and an Enter before the old keys go, then the link token goes")
	}
	h.requireNoSecretInOutput(desk.Value, posting.Value, r2Secret(posting.Value))
}

// No answer at the wait, as with Ctrl-C, keeps the old key working; the
// next run asks again and deletes exactly that key.
func TestAnUnansweredWaitKeepsTheOldKeyForTheNextRun(t *testing.T) {
	h := newHarness(t, false, true)
	if err := h.runCloudflare(); err != nil {
		t.Fatal(err)
	}
	old := h.onlyLiveToken("acme_systems: shop reads and writes its uploads")
	if err := h.runCloudflare("--replace-key", "shop_R2_ACCESS_KEY_ID"); err != nil {
		t.Fatalf("replace: %v\n%s", err, h.out)
	}
	tokens := h.cloudflare.LiveTokensNamed("acme_systems: shop reads and writes its uploads")
	if len(tokens) != 2 || !strings.Contains(h.out.String(), "The old keys keep working") || len(h.cloudflare.LiveTokensNamed(linkTokenNameForAlex)) != 0 {
		t.Fatal("without an answer, the old key keeps working and the link token is deleted")
	}
	h.e.confirm = func(string) (string, error) { return "", nil }
	if err := h.runCloudflare(); err != nil {
		t.Fatalf("rerun: %v\n%s", err, h.out)
	}
	now := h.onlyLiveToken("acme_systems: shop reads and writes its uploads")
	if now.ID == old.ID || h.vault.values["shop_R2_ACCESS_KEY_ID"] != now.ID {
		t.Fatal("the next run must delete exactly the old key")
	}
}

// After a break-in the old keys go at once, without a question.
func TestDeleteTheOldKeysAtOnce(t *testing.T) {
	h := newHarness(t, false, true)
	if err := h.runCloudflare(); err != nil {
		t.Fatal(err)
	}
	asked := false
	h.e.confirm = func(string) (string, error) { asked = true; return "", nil }
	if err := h.runCloudflare("--replace-every-key", "--delete-the-old-keys-at-once"); err != nil {
		t.Fatalf("replace: %v\n%s", err, h.out)
	}
	if asked {
		t.Fatal("the at-once form asks nothing")
	}
	for _, name := range []string{"acme_systems: shop reads and writes its uploads", "acme_systems: util01 reads the apps' uploads",
		"acme_systems: MMHotline uploads the MMHotline-down alarm", "acme_systems: MMHotline posts to the status page"} {
		h.onlyLiveToken(name)
	}
	if !strings.Contains(h.out.String(), "next run of every_server") {
		t.Fatal("the person must hear that the servers need a run now")
	}
}

func TestReplaceEveryKeyReplacesEachServersKey(t *testing.T) {
	h := newHarness(t, false, true)
	if err := h.runCloudflare(); err != nil {
		t.Fatal(err)
	}
	before := map[string]string{}
	for key, value := range h.vault.values {
		before[key] = value
	}
	h.e.confirm = func(string) (string, error) { return "", nil }
	if err := h.runCloudflare("--replace-every-key"); err != nil {
		t.Fatalf("replace: %v\n%s", err, h.out)
	}
	for key, value := range before {
		if h.vault.values[key] == value {
			t.Fatalf("%s kept its old value", key)
		}
	}
	for _, name := range []string{"acme_systems: shop reads and writes its uploads", "acme_systems: util01 reads the apps' uploads",
		"acme_systems: MMHotline uploads the MMHotline-down alarm", "acme_systems: MMHotline posts to the status page", deskTokenNameForAlex, postingTokenNameForAlex} {
		h.onlyLiveToken(name)
	}
}

func TestReplaceKeyRefusesAnUnknownNameBeforeAsking(t *testing.T) {
	h := newHarness(t, false, false)
	h.answers = []string{"unused"}
	err := runCloudflare(h.e, []string{"--replace-key", "shop_R2_ACCESS_KEY_ID"})
	if err == nil || !strings.Contains(err.Error(), "names no Cloudflare key of this system") || len(h.answers) != 1 {
		t.Fatalf("an app without uploads has no R2 key to replace, and nothing is asked: %v", err)
	}
	if err := runCloudflare(h.e, []string{"--replace-key", "STAGING_ACCESS_CLIENT_SECRET"}); err == nil {
		t.Fatal("without staging01 there is no staging service token to replace")
	}
}

// A remaining member deletes a leaving person's tokens by their names; the
// remaining member's own tokens and the servers' tokens stay.
func TestDeleteTokensOfPersonDeletesOnlyThatPersonsTokens(t *testing.T) {
	h := newHarness(t, false, false)
	h.e.person = "sam"
	if err := h.runCloudflare(); err != nil {
		t.Fatalf("sam's run: %v\n%s", err, h.out)
	}
	h.addLinkToken() // a link token sam's stopped run left
	h.e.person = "alex"
	if err := h.runCloudflare(); err != nil {
		t.Fatalf("alex's run: %v\n%s", err, h.out)
	}
	sets := len(h.vault.sets)
	if err := h.runCloudflare("--delete-tokens-of-person", "sam"); err != nil {
		t.Fatalf("delete: %v\n%s", err, h.out)
	}
	for _, name := range []string{"acme_systems: sam's systems desk sets up Cloudflare", "acme_systems: sam posts to the status page",
		"acme_systems: sam makes tokens with set-up-outside-services, deleted after the run"} {
		if len(h.cloudflare.LiveTokensNamed(name)) != 0 {
			t.Fatalf("%q must be deleted", name)
		}
	}
	h.onlyLiveToken(deskTokenNameForAlex)
	h.onlyLiveToken(postingTokenNameForAlex)
	h.onlyLiveToken("acme_systems: MMHotline uploads the MMHotline-down alarm")
	if len(h.vault.sets) != sets || len(h.cloudflare.LiveTokensNamed(linkTokenNameForAlex)) != 0 {
		t.Fatal("the deletion changes no vault key and deletes its own link token")
	}
	h.answers = []string{"unused"}
	if err := runCloudflare(h.e, []string{"--delete-tokens-of-person", "alex"}); err == nil || !strings.Contains(err.Error(), "names you") {
		t.Fatalf("a person cannot delete their own tokens this way, got %v", err)
	}
}

func TestAnAppWithUploadsNamesItsKeyVariables(t *testing.T) {
	h := newHarness(t, false, true)
	path := filepath.Join(h.e.directory, projectSettingsFile)
	text, _ := os.ReadFile(path)
	writeFile(t, path, strings.ReplaceAll(string(text), "access_key_id: R2_ACCESS_KEY_ID", "access_key_id: NOT_LISTED"))
	if err := h.runCloudflare(); err == nil || !strings.Contains(err.Error(), "does not list") {
		t.Fatalf("want the variable check, got %v", err)
	}
}

// The root step that hands the API proxy a token prints its check for the
// coding agent. The person's terminal must not show it; a failed
// step still names its reason.
func TestTheProxyStepPrintsNothingOnThePersonsScreen(t *testing.T) {
	bin := t.TempDir()
	t.Setenv("PATH", bin+string(os.PathListSeparator)+os.Getenv("PATH"))
	fakeSudo := func(script string) {
		writeFile(t, filepath.Join(bin, "sudo"), "#!/bin/sh\ncat > /dev/null\n"+script)
		if err := os.Chmod(filepath.Join(bin, "sudo"), 0o755); err != nil {
			t.Fatal(err)
		}
	}
	screen := func(work func() error) (string, error) {
		reader, writer, err := os.Pipe()
		if err != nil {
			t.Fatal(err)
		}
		stdout, stderr := os.Stdout, os.Stderr
		os.Stdout, os.Stderr = writer, writer
		workErr := work()
		os.Stdout, os.Stderr = stdout, stderr
		writer.Close()
		shown, _ := io.ReadAll(reader)
		return string(shown), workErr
	}
	request := proxyFileRequest{API: "cloudflare", Token: "a-token", CloudflareAccountID: testAccountID}

	fakeSudo("echo 'The API proxy has the new token: http://127.0.0.1:8082/accounts/x/tokens/verify answered through it.'\n")
	shown, err := screen(func() error { return writeProxyFileWithSudo(request) })
	if err != nil || shown != "" {
		t.Fatalf("a working step: want no screen text and no error, got %q, %v", shown, err)
	}

	fakeSudo("echo 'Stopped: systemctl restart failed: no such unit.' >&2\nexit 1\n")
	shown, err = screen(func() error { return writeProxyFileWithSudo(request) })
	if shown != "" || err == nil || !strings.Contains(err.Error(), "systemctl restart failed: no such unit") {
		t.Fatalf("a failed step: want its reason in the error and no screen text, got %q, %v", shown, err)
	}
}

// useTheTemplatesAccountID puts back the template's example account ID, as
// at a first setup, before the coding agent knows the account.
func (h *harness) useTheTemplatesAccountID() {
	h.t.Helper()
	path := filepath.Join(h.e.directory, projectSettingsFile)
	writeFile(h.t, path, strings.Replace(mustRead(h.t, path), `cloudflare_account_id: "`+testAccountID+`"`, `cloudflare_account_id: "`+exampleCloudflareAccountID+`"`, 1))
	h.commitAll("The template's settings")
}

// At a first setup the command finds the account from the link token, adds
// the domain, has Cloudflare copy its records, gives the account its
// workers.dev address, and notes the registrar's facts for the domain's move.
func TestCloudflareFindsTheAccountAddsTheDomainAndNotesTheRegistrar(t *testing.T) {
	h := newHarness(t, false, false)
	h.useTheTemplatesAccountID()
	h.cloudflare.ZoneStatus = ""
	registry := httptest.NewServer(rdap(true))
	t.Cleanup(registry.Close)
	h.e.rdapBootstrapURL = registry.URL + "/dns.json"
	code, out, errorOut := h.fromTheCodingAgent(h.addLinkToken()+"\n", "cloudflare")
	if code != 0 {
		t.Fatalf("exit code %d:\n%s%s", code, out, errorOut)
	}
	if h.cloudflare.ZoneStatus != "pending" || h.cloudflare.DNSScans != 1 || h.cloudflare.WorkersSubdomain != "acme-systems" {
		t.Fatalf("zone %q, %d scans, workers.dev %q", h.cloudflare.ZoneStatus, h.cloudflare.DNSScans, h.cloudflare.WorkersSubdomain)
	}
	for name, want := range map[string]string{"cloudflare_account_id": testAccountID, "cloudflare_nameservers": "ada.ns.cloudflare.com bob.ns.cloudflare.com",
		"cloudflare_domain_status": "pending", "domain_registrar": "Namecheap, Inc.", "domain_dnssec_on": "yes"} {
		if got := h.results().ForTheCodingAgent[name]; got != want {
			t.Errorf("for_the_coding_agent.%s = %q, want %q", name, got, want)
		}
	}
	for _, name := range []string{linkTokenNameForAlex, "acme_systems: set-up-outside-services adds the domain, deleted after the run"} {
		if len(h.cloudflare.LiveTokensNamed(name)) != 0 {
			t.Errorf("the token %q is left", name)
		}
	}
}

// When Cloudflare does not list the link token's account, the command
// stops and says where the person reads the account's ID; the rerun with
// --account-id and a new link token deletes the first link token.
func TestCloudflareAsksForTheAccountIDWhenCloudflareDoesNotListIt(t *testing.T) {
	h := newHarness(t, false, false)
	h.useTheTemplatesAccountID()
	h.cloudflare.RefuseAccountsList = true
	code, _, errorOut := h.fromTheCodingAgent(h.addLinkToken()+"\n", "cloudflare")
	if code != 1 || !strings.Contains(errorOut, "--account-id ID") || !strings.Contains(errorOut, "right after dash.cloudflare.com/") {
		t.Fatalf("exit %d, want the stop that asks for --account-id: %s", code, errorOut)
	}
	if code, out, errorOut := h.fromTheCodingAgent(h.addLinkToken()+"\n", "cloudflare", "--account-id", testAccountID); code != 0 {
		t.Fatalf("the rerun with --account-id: exit %d\n%s%s", code, out, errorOut)
	}
	if len(h.cloudflare.LiveTokensNamed(linkTokenNameForAlex)) != 0 {
		t.Fatal("a link token is left")
	}
}

// With no app that keeps uploads, R2 may be off on an Active domain: the
// status page waits with a note, and the rest of the run finishes, the
// down alarm's token and the tunnels' tokens included.
func TestCloudflareSkipsTheStatusPageWhileR2IsOffAndNoAppNeedsIt(t *testing.T) {
	h := newHarness(t, false, false)
	h.cloudflare.R2Off = true
	h.e.runMMHotlineStatusPageSetUp = func(accountID, hostName, token string) (statusPageSetUp, error) {
		return statusPageSetUp{}, errors.New("Cloudflare refused the bucket with code 10042: R2 is off")
	}
	code, out, errorOut := h.fromTheCodingAgent(h.addLinkToken()+"\n", "cloudflare")
	if code != 0 || !strings.Contains(out, "R2, which is off in this account, so the page waits") {
		t.Fatalf("exit %d, want a finished run with the page's note:\n%s%s", code, out, errorOut)
	}
	for _, key := range []string{"mmhotline_down_alarm_cloudflare_api_token", "apps_cloudflare_tunnel_token", "util01_cloudflare_tunnel_token"} {
		if h.vault.values[key] == "" {
			t.Errorf("%s was not saved", key)
		}
	}
	if h.vault.values["mmhotline_status_page_r2_access_key_id"] != "" || len(h.cloudflare.LiveTokensNamed(linkTokenNameForAlex)) != 0 {
		t.Fatal("want no status page key and the link token deleted")
	}
}

// A link token that works in several accounts stops the run, and the stop
// deletes it, so no token that can make tokens stays live when the person
// never runs the command again.
func TestCloudflareDeletesALinkTokenThatWorksInSeveralAccounts(t *testing.T) {
	h := newHarness(t, false, false)
	h.useTheTemplatesAccountID()
	h.cloudflare.TokenAlsoWorksIn = []string{"fedcba9876543210fedcba9876543210"}
	code, _, errorOut := h.fromTheCodingAgent(h.addLinkToken()+"\n", "cloudflare")
	if code != 1 || !strings.Contains(errorOut, "works in 2 Cloudflare accounts") || !strings.Contains(errorOut, "This link token is deleted") {
		t.Fatalf("exit %d, want the stop that lists the accounts and says the token is deleted: %s", code, errorOut)
	}
	if len(h.cloudflare.LiveTokensNamed(linkTokenNameForAlex)) != 0 {
		t.Fatal("the link token is left live")
	}
}

// R2 off: everything else is made, then the command stops with R2's price
// and the page that turns it on. The rerun after the person turned it on
// makes the upload buckets and keys.
func TestCloudflareStopsWithR2sPriceWhileR2IsOff(t *testing.T) {
	h := newHarness(t, false, true)
	h.cloudflare.R2Off = true
	code, _, errorOut := h.fromTheCodingAgent(h.addLinkToken()+"\n", "cloudflare")
	if code != 1 {
		t.Fatalf("exit code %d, want 1", code)
	}
	for _, line := range []string{"R2 is off", "Everything else is set up.", "$0.015 for each GB a month", "https://dash.cloudflare.com/" + testAccountID + "/r2/overview"} {
		if !strings.Contains(errorOut, line) {
			t.Errorf("the stop lacks %q:\n%s", line, errorOut)
		}
	}
	if h.vault.values["apps_cloudflare_tunnel_token"] == "" || h.vault.values["shop_R2_ACCESS_KEY_ID"] != "" || len(h.cloudflare.LiveTokensNamed(linkTokenNameForAlex)) != 0 {
		t.Fatal("want the tunnel saved, no upload key, and the link token deleted")
	}
	h.cloudflare.Lock()
	h.cloudflare.R2Off = false
	h.cloudflare.Unlock()
	if code, out, errorOut := h.fromTheCodingAgent(h.addLinkToken()+"\n", "cloudflare"); code != 0 || h.vault.values["shop_R2_ACCESS_KEY_ID"] == "" || !h.cloudflare.R2Buckets["acme-shop-uploads"] {
		t.Fatalf("the rerun with R2 on: exit %d\n%s%s", code, out, errorOut)
	}
}
