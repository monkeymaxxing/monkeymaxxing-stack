package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"sort"
	"strings"
	"time"
)

// The keys only a person can give, which the vault keeps for the servers:
// the registry's read-only token and each app's key from an outside service.
// save-a-key and secrets check each one at its service before saving it,
// each at an address fixed here, never one from the settings, which the
// coding agent can push.

const registryTokenVaultKey = "container_registry_read_only_token"

// keyOnlyAPersonGives finds key among the keys only a person gives that
// save-a-key saves: the registry's token and the apps' keys from an
// outside service.
func keyOnlyAPersonGives(settings systemSettings, key string) (secretPlan, bool) {
	for _, item := range secretsPlan(settings) {
		if item.Key == key && (item.Key == registryTokenVaultKey || item.App != "") {
			return item, true
		}
	}
	return secretPlan{}, false
}

// keysOnlyAPersonGives lists them, for a refusal.
func keysOnlyAPersonGives(settings systemSettings) []string {
	var keys []string
	for _, item := range secretsPlan(settings) {
		if _, ok := keyOnlyAPersonGives(settings, item.Key); ok {
			keys = append(keys, item.Key)
		}
	}
	return keys
}

// checkAKeyBeforeSaving checks a key only a person gives at its service, as
// the servers use it, and adds what the coding agent needs to notes. An
// error says why the service refused it and what to do.
func (e *environment) checkAKeyBeforeSaving(settings systemSettings, item secretPlan, value string, notes map[string]string) error {
	if strings.ContainsAny(value, "\r\n") {
		return fmt.Errorf("the value for %s has more than one line. Give the one value only", item.Key)
	}
	switch {
	case item.Key == registryTokenVaultKey:
		image := firstAppImage(settings)
		host, repository, _ := strings.Cut(image, "/")
		if host != "ghcr.io" || repository == "" {
			// This command knows GitHub's checks only.
			e.say("The apps' images are not at ghcr.io, so this command saves the registry's token without a check.")
			return nil
		}
		check, err := e.checkTheRegistryToken(value, repository)
		if err != nil {
			return err
		}
		e.say("GitHub accepted the token: it can only download packages, and it belongs to %s.", check.login)
		notes["container_registry_read_only_username"] = check.login
		notes["container_image_found"] = map[bool]string{true: "yes", false: "no, not built yet"}[check.imageFound]
		if !check.expiresAt.IsZero() {
			e.say("The token stops working on %s. After that the servers cannot download your app until the token is replaced; the weekly review reminds you.", check.expiresAt.Format("2006-01-02"))
			notes["container_registry_read_only_token_expires_at"] = check.expiresAt.Format(time.RFC3339)
		}
	case item.CheckedWith == "stripe":
		if err := checkStripeKey(e.stripeAPIURL, value); err != nil {
			return fmt.Errorf("%v. Copy the whole key from Stripe's page, then give it again", err)
		}
		e.say("Stripe accepted the key.")
	}
	return nil
}

// firstAppImage is the first app's image, by app name, such as
// ghcr.io/example/shop. Every app's images come from one registry account.
func firstAppImage(settings systemSettings) string {
	var names []string
	for name := range settings.Vars.Apps {
		names = append(names, name)
	}
	sort.Strings(names)
	if len(names) == 0 {
		return ""
	}
	image, _, _ := strings.Cut(settings.Vars.Apps[names[0]].Image, ":")
	return image
}

type registryTokenCheck struct {
	login      string
	imageFound bool
	// expiresAt is when GitHub stops accepting the token; zero for a token
	// that never ends.
	expiresAt time.Time
}

// shortestRegistryTokenLife is the least time a token that ends may have
// left. A shorter token would stop the servers' deploys before the weekly
// review reminds the person to replace it.
const shortestRegistryTokenLife = 30 * 24 * time.Hour

// registryTokenPage makes a GitHub token that can only read packages.
const registryTokenPage = "https://github.com/settings/tokens/new?scopes=read:packages"

// checkTheRegistryToken checks a GitHub token the way the servers use it:
// it lasts at least 30 more days, it can only read packages, and it reads
// the app's image at ghcr.io.
func (e *environment) checkTheRegistryToken(token, repository string) (registryTokenCheck, error) {
	fromTheLink := "Make a new token at " + registryTokenPage + ", with Expiration set to No expiration and only read:packages ticked"
	var check registryTokenCheck
	if checkTokenValue("token", token) != nil {
		return check, errors.New("that is not a whole GitHub token: it has a space or another character a token never has. Copy the whole token, then give it again")
	}
	// https://docs.github.com/en/rest/users/users#get-the-authenticated-user
	request, err := http.NewRequest(http.MethodGet, e.githubAPIURL+"/user", nil)
	if err != nil {
		return check, err
	}
	request.Header.Set("Authorization", "Bearer "+token)
	request.Header.Set("Accept", "application/vnd.github+json")
	response, err := httpClient.Do(request)
	if err != nil {
		return check, &networkError{Provider: "GitHub", Call: "GET /user", Err: stripURLFromError(err)}
	}
	body, _ := io.ReadAll(io.LimitReader(response.Body, 1<<20))
	response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return check, fmt.Errorf("%v. Copy the whole token, then give it again", &apiError{Provider: "GitHub", Call: "GET /user", Status: response.StatusCode})
	}
	var user struct {
		Login string `json:"login"`
	}
	if json.Unmarshal(body, &user) != nil || user.Login == "" {
		return check, errors.New("GitHub answered GET /user with something this command cannot read")
	}
	check.login = user.Login
	// GitHub names a classic token's end date and scopes in its headers.
	if ends := response.Header.Get("GitHub-Authentication-Token-Expiration"); ends != "" {
		// https://docs.github.com/en/rest/overview/resources-in-the-rest-api#authentication
		expiresAt, err := time.Parse("2006-01-02 15:04:05 MST", ends)
		if err != nil {
			return check, fmt.Errorf("this token stops working on %s, and your deploys with it. %s", ends, fromTheLink)
		}
		if expiresAt.Sub(e.now()) < shortestRegistryTokenLife {
			return check, fmt.Errorf("this token stops working on %s, less than 30 days from now, and your deploys with it. %s", ends, fromTheLink)
		}
		check.expiresAt = expiresAt.UTC()
	}
	scopes := map[string]bool{}
	for _, scope := range strings.Split(response.Header.Get("X-OAuth-Scopes"), ",") {
		if scope = strings.TrimSpace(scope); scope != "" {
			scopes[scope] = true
		}
	}
	if !scopes["read:packages"] {
		return check, fmt.Errorf("this token cannot download packages. %s", fromTheLink)
	}
	delete(scopes, "read:packages")
	if len(scopes) > 0 {
		return check, fmt.Errorf("this token can do more than download your app: it can also use %s. Every server keeps it, so it may only read. %s", strings.Join(sortedNames(scopes), ", "), fromTheLink)
	}
	found, err := readImageTags(e.containerRegistryURL, repository, user.Login, token)
	var refusal *apiError
	if errors.As(err, &refusal) {
		return check, fmt.Errorf("this token cannot read your app's image ghcr.io/%s. Make the token while signed in to the GitHub account that owns the image", repository)
	}
	check.imageFound = found
	return check, err
}

// readImageTags reads an image's tags at a registry the way a server's pull
// does: a pull token for the repository, then its tag list. found is false
// when the image is not built yet.
// https://distribution.github.io/distribution/spec/auth/token/
func readImageTags(registryURL, repository, login, token string) (bool, error) {
	request, err := http.NewRequest(http.MethodGet, registryURL+"/token?service=ghcr.io&scope="+url.QueryEscape("repository:"+repository+":pull"), nil)
	if err != nil {
		return false, err
	}
	request.SetBasicAuth(login, token)
	var pull struct {
		Token string `json:"token"`
	}
	if err := registryCall(request, &pull); err != nil {
		return false, err
	}
	request, err = http.NewRequest(http.MethodGet, registryURL+"/v2/"+repository+"/tags/list", nil)
	if err != nil {
		return false, err
	}
	request.Header.Set("Authorization", "Bearer "+pull.Token)
	err = registryCall(request, nil)
	if refusedWith(err, http.StatusNotFound) {
		return false, nil
	}
	return err == nil, err
}

func registryCall(request *http.Request, result any) error {
	call := request.Method + " " + request.URL.Path
	response, err := httpClient.Do(request)
	if err != nil {
		return &networkError{Provider: "The registry", Call: call, Err: stripURLFromError(err)}
	}
	defer response.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(response.Body, 1<<20))
	if response.StatusCode != http.StatusOK {
		var refusal struct {
			Errors []struct {
				Code string `json:"code"`
			} `json:"errors"`
		}
		_ = json.Unmarshal(body, &refusal)
		failure := &apiError{Provider: "The registry", Call: call, Status: response.StatusCode}
		if len(refusal.Errors) > 0 {
			failure.Code = refusal.Errors[0].Code
		}
		return failure
	}
	if result != nil && json.Unmarshal(body, result) != nil {
		return fmt.Errorf("the registry answered %s with something this command cannot read", call)
	}
	return nil
}

// checkStripeKey reads the account's balance with a secret or restricted
// key, which any working key may do.
// https://docs.stripe.com/api/balance/balance_retrieve
func checkStripeKey(stripeAPIURL, key string) error {
	var refusal struct {
		Error struct {
			Code string `json:"code"`
		} `json:"error"`
	}
	request, err := http.NewRequest(http.MethodGet, stripeAPIURL+"/v1/balance", nil)
	if err != nil {
		return err
	}
	request.Header.Set("Authorization", "Bearer "+key)
	response, err := httpClient.Do(request)
	if err != nil {
		return &networkError{Provider: "Stripe", Call: "GET /v1/balance", Err: stripURLFromError(err)}
	}
	defer response.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(response.Body, 1<<20))
	if response.StatusCode != http.StatusOK {
		_ = json.Unmarshal(body, &refusal)
		return &apiError{Provider: "Stripe", Call: "GET /v1/balance", Status: response.StatusCode, Code: refusal.Error.Code}
	}
	return nil
}
