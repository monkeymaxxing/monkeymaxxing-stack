package main

import (
	"errors"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"

	"go.yaml.in/yaml/v3"
)

// The systems repository's settings that this command reads. The command
// reads them from the repository in the working directory, so the plan
// below always follows the team's own settings and never a second copy.
type projectSettings struct {
	ProjectName string `yaml:"project_name"`
	Vars        struct {
		CloudflareAccountID       string `yaml:"cloudflare_account_id"`
		StatusPageHostName        string `yaml:"status_page_host_name"`
		SystemsDeskProviderAPIURL string `yaml:"systems_desk_provider_api_url"`
		// token_in_a_header, or a signing method in requestSigningMethods.
		SystemsDeskProviderAPIAuthentication string `yaml:"systems_desk_provider_api_authentication"`
		TriageAgentCodingAgent               string `yaml:"triage_agent_coding_agent"`
		// PasswordManager names the team's password manager on go-live's
		// screens, such as 1Password. Without it they say "your password manager".
		PasswordManager string                 `yaml:"password_manager"`
		Apps            map[string]appSettings `yaml:"apps"`
		Backups         backupSettings         `yaml:"backups"`
	} `yaml:"vars"`
}

type appSettings struct {
	Image                           string `yaml:"image"`
	ProductionUploadsR2Bucket       string `yaml:"production_uploads_r2_bucket"`
	StagingUploadsR2Bucket          string `yaml:"staging_uploads_r2_bucket"`
	ProductionUploadsR2KeyVariables struct {
		AccessKeyID     string `yaml:"access_key_id"`
		SecretAccessKey string `yaml:"secret_access_key"`
	} `yaml:"production_uploads_r2_key_variables"`
	SecretsFromVault appSecrets `yaml:"secrets_from_vault"`
}

// appSecrets is an app's secrets_from_vault: each environment variable the
// app reads from the vault, and where its value comes from.
type appSecrets map[string]appSecret

// appSecret says where one of an app's secrets comes from, so the setup
// makes it or asks for it on its own screen, with no question about it.
type appSecret struct {
	// WhereTheValueComesFrom is secretGeneratedByTheSetup or
	// secretFromAnOutsideService.
	WhereTheValueComesFrom string `yaml:"where_the_value_comes_from"`
	// For a secret from an outside service: one sentence for the screen,
	// the steps that get it, one per line, and optionally a built-in check
	// of the value at the service, by its name in outsideServiceChecks.
	WhatItIsFor  string   `yaml:"what_it_is_for"`
	StepsToGetIt []string `yaml:"steps_to_get_it"`
	CheckedWith  string   `yaml:"checked_with"`
}

const (
	// The setup makes the value: a random one, or for an app's R2 key
	// variables, the key it makes at Cloudflare.
	secretGeneratedByTheSetup = "generated_by_the_setup"
	// A service outside the Stack gives the value, such as a Stripe key; the
	// person pastes it on its own screen.
	secretFromAnOutsideService = "an_outside_service"
)

// UnmarshalYAML refuses the earlier list form with the way to the new one.
func (secrets *appSecrets) UnmarshalYAML(node *yaml.Node) error {
	if node.Kind == yaml.SequenceNode {
		if len(node.Content) == 0 {
			*secrets = appSecrets{}
			return nil
		}
		return fmt.Errorf("line %d: secrets_from_vault is a list of names. Write it as a mapping that says where each value comes from, such as\n"+
			"      secrets_from_vault:\n        SECRET_KEY_BASE:\n          where_the_value_comes_from: %s", node.Line, secretGeneratedByTheSetup)
	}
	var plain map[string]appSecret
	if err := node.Decode(&plain); err != nil {
		return err
	}
	*secrets = plain
	return nil
}

// names lists the secrets' names in order.
func (secrets appSecrets) names() []string {
	var names []string
	for name := range secrets {
		names = append(names, name)
	}
	sort.Strings(names)
	return names
}

// outsideServiceChecks are the services whose keys the setup checks before
// saving them. Each address is fixed here, never read from the settings,
// so a pushed settings change can never send a key elsewhere.
var outsideServiceChecks = map[string]bool{"stripe": true}

// checkAppSecrets checks that each app secret says where its value comes
// from, and that a secret from an outside service has its screen's text.
func (s systemSettings) checkAppSecrets() error {
	for _, app := range sortedAppNames(s) {
		for _, name := range s.Vars.Apps[app].SecretsFromVault.names() {
			secret := s.Vars.Apps[app].SecretsFromVault[name]
			where := "vars.apps." + app + ".secrets_from_vault." + name
			switch secret.WhereTheValueComesFrom {
			case secretGeneratedByTheSetup:
			case secretFromAnOutsideService:
				if strings.TrimSpace(secret.WhatItIsFor) == "" || len(secret.StepsToGetIt) == 0 {
					return fmt.Errorf("%s in %s comes from an outside service, so it needs what_it_is_for, one sentence, and steps_to_get_it, one step per line: the setup shows them on the key's screen", where, projectSettingsFile)
				}
				if secret.CheckedWith != "" && !outsideServiceChecks[secret.CheckedWith] {
					return fmt.Errorf("%s.checked_with in %s is %q. The setup checks keys only with: %s. Leave checked_with out for another service", where, projectSettingsFile, secret.CheckedWith, strings.Join(sortedNames(outsideServiceChecks), ", "))
				}
			default:
				return fmt.Errorf("%s.where_the_value_comes_from in %s is %q. Write %s for a value the setup makes, or %s for one a service outside the Stack gives", where, projectSettingsFile,
					secret.WhereTheValueComesFrom, secretGeneratedByTheSetup, secretFromAnOutsideService)
			}
		}
	}
	return nil
}

func sortedAppNames(s systemSettings) []string {
	var names []string
	for name := range s.Vars.Apps {
		names = append(names, name)
	}
	sort.Strings(names)
	return names
}

type backupSettings struct {
	B2S3Endpoint        string   `yaml:"b2_s3_endpoint"`
	ProductionBucket    string   `yaml:"production_bucket"`
	UploadsBucket       string   `yaml:"uploads_bucket"`
	UploadsBackupRunsOn []string `yaml:"uploads_backup_runs_on"`
	// The three backup lengths, in days. A missing one reads as 0, which the
	// checks in backupLengths refuse.
	KeepDatabaseBackupsForDays            int    `yaml:"keep_database_backups_for_days"`
	LockBackupsAgainstDeletionForDays     int    `yaml:"lock_backups_against_deletion_for_days"`
	KeepPriorFileVersionsInBucketsForDays int    `yaml:"keep_prior_file_versions_in_buckets_for_days"`
	MMHotlineBackupReplicaURL             string `yaml:"mmhotline_backup_replica_url"`
}

type inventorySettings struct {
	Groups map[string]struct {
		Nodes []string `yaml:"nodes"`
	} `yaml:"groups"`
}

// systemSettings is what the plans need, read and checked once.
type systemSettings struct {
	projectSettings
	hasStagingServer bool
}

const (
	projectSettingsFile = "mmx_project_settings.yml"
	inventoryFile       = "inventories/servers.yml"
	// The template's example account ID, which a team replaces.
	exampleCloudflareAccountID = "0123456789abcdef0123456789abcdef"
)

var cloudflareAccountIDPattern = regexp.MustCompile(`^[0-9a-f]{32}$`)

func readSystemSettings(directory string) (systemSettings, error) {
	var settings systemSettings
	text, err := os.ReadFile(filepath.Join(directory, projectSettingsFile))
	if errors.Is(err, os.ErrNotExist) {
		return settings, fmt.Errorf("this directory has no %s. Run this command in your systems repository on this desk, such as ~/%s", projectSettingsFile, "example_systems")
	}
	if err != nil {
		return settings, err
	}
	if err := yaml.Unmarshal(text, &settings.projectSettings); err != nil {
		return settings, fmt.Errorf("%s: %v", projectSettingsFile, err)
	}
	if settings.ProjectName == "" {
		return settings, fmt.Errorf("%s has no project_name", projectSettingsFile)
	}
	inventoryText, err := os.ReadFile(filepath.Join(directory, inventoryFile))
	if err != nil {
		return settings, err
	}
	var inventory inventorySettings
	if err := yaml.Unmarshal(inventoryText, &inventory); err != nil {
		return settings, fmt.Errorf("%s: %v", inventoryFile, err)
	}
	settings.hasStagingServer = len(inventory.Groups["staging_server"].Nodes) > 0
	return settings, nil
}

// plainSetting refuses a value that is empty, still the template's example,
// or an MMX template that only a run can fill in.
func plainSetting(name, value string) error {
	switch {
	case value == "":
		return fmt.Errorf("%s in %s is empty. Set it first", name, projectSettingsFile)
	case strings.Contains(value, "{{"):
		return fmt.Errorf("%s in %s is a template. This command reads written-out values only", name, projectSettingsFile)
	case strings.HasPrefix(value, "example-") || strings.HasPrefix(value, "s3://example-") || value == "example.com" ||
		strings.HasSuffix(value, ".example.com") || value == exampleCloudflareAccountID:
		return fmt.Errorf("%s in %s is still the template's example, %s. Replace it with your own value first", name, projectSettingsFile, value)
	}
	return nil
}

func (s systemSettings) cloudflareAccountID() (string, error) {
	id := s.Vars.CloudflareAccountID
	if err := plainSetting("vars.cloudflare_account_id", id); err != nil {
		return "", err
	}
	if !cloudflareAccountIDPattern.MatchString(id) {
		return "", fmt.Errorf("vars.cloudflare_account_id in %s must be the account's 32-character ID, from the Cloudflare dashboard", projectSettingsFile)
	}
	return id, nil
}

// appsWithUploads lists the apps that keep uploaded files, sorted by name.
func (s systemSettings) appsWithUploads() []string {
	var apps []string
	for name, app := range s.Vars.Apps {
		if app.ProductionUploadsR2Bucket != "" {
			apps = append(apps, name)
		}
	}
	sort.Strings(apps)
	return apps
}

// stagingUploadsBucket is the R2 bucket of an app's uploads on staging01,
// which an app with uploads needs when the system has staging01.
func (s systemSettings) stagingUploadsBucket(app string) (string, error) {
	bucket := s.Vars.Apps[app].StagingUploadsR2Bucket
	if err := plainSetting("vars.apps."+app+".staging_uploads_r2_bucket", bucket); err != nil {
		return "", fmt.Errorf("%v. With staging01, an app that keeps uploads needs its own staging bucket, such as %s-staging-uploads", err, strings.ReplaceAll(app, "_", "-"))
	}
	if bucket == s.Vars.Apps[app].ProductionUploadsR2Bucket {
		return "", fmt.Errorf("vars.apps.%s.staging_uploads_r2_bucket is production's bucket. Give staging its own bucket, so staging01 never reaches production's uploads", app)
	}
	return bucket, nil
}

// uploadsAreBackedUp says whether the nightly copy of the uploads to B2 is
// part of this system: some app keeps uploads, and the uploads bucket is set.
func (s systemSettings) uploadsAreBackedUp() bool {
	return len(s.appsWithUploads()) > 0 && s.Vars.Backups.UploadsBucket != ""
}

// keyNamePrefix makes a provider key name from the project's name, such as
// example-systems for example_systems. B2 key names allow letters, digits,
// and hyphens only.
func (s systemSettings) keyNamePrefix() string {
	return strings.ReplaceAll(s.ProjectName, "_", "-")
}

// The capability lists of the B2 keys, as docs/design.md, "Account and
// secret setup from the systems desk", records them with their reasons.
var (
	b2DatabaseWriteCapabilities = []string{"listBuckets", "listFiles", "readFiles", "writeFiles", "deleteFiles"}
	b2ReadOnlyCapabilities      = []string{"listBuckets", "listFiles", "readFiles"}
	b2UploadsCopyCapabilities   = []string{"listBuckets", "listFiles", "readFiles", "writeFiles"}
	b2MMHotlineCapabilities     = []string{"listBuckets", "listFiles", "readFiles", "writeFiles", "deleteFiles"}
)

// backupLengths checks the three backup lengths in vars.backups. Each
// minimum has a reason, which the message gives; the same checks run in
// files_used_by_several_roles/pgbackrest.conf when MMX applies the settings.
func (s systemSettings) backupLengths() (lockDays, priorVersionDays int, err error) {
	b := s.Vars.Backups
	keep, lock, prior := b.KeepDatabaseBackupsForDays, b.LockBackupsAgainstDeletionForDays, b.KeepPriorFileVersionsInBucketsForDays
	switch {
	case keep == 0:
		return 0, 0, fmt.Errorf("vars.backups.keep_database_backups_for_days in %s is missing. Set a whole number of days, 14 or more, such as 21", projectSettingsFile)
	case keep < 14:
		return 0, 0, fmt.Errorf("vars.backups.keep_database_backups_for_days in %s is %d, below the minimum of 14. A full backup runs every week, and the weekly restore drill needs the previous full backup still present", projectSettingsFile, keep)
	case lock == 0:
		return 0, 0, fmt.Errorf("vars.backups.lock_backups_against_deletion_for_days in %s is missing. Set a whole number of days from 8 up to keep_database_backups_for_days, such as 14", projectSettingsFile)
	case lock < 8:
		return 0, 0, fmt.Errorf("vars.backups.lock_backups_against_deletion_for_days in %s is %d, below the minimum of 8. The uploads job makes a full copy every 6 days and warns at 8 days, so a shorter lock could end before the next full copy protects an unchanged file", projectSettingsFile, lock)
	case lock > keep:
		return 0, 0, fmt.Errorf("vars.backups.lock_backups_against_deletion_for_days in %s is %d, more than keep_database_backups_for_days (%d). pgBackRest would try to delete backups that are still locked", projectSettingsFile, lock, keep)
	case prior < 1:
		return 0, 0, fmt.Errorf("vars.backups.keep_prior_file_versions_in_buckets_for_days in %s is %d. Set a whole number of days of at least 1, such as 14", projectSettingsFile, prior)
	}
	return lock, prior, nil
}

type b2BucketPlan struct {
	// LockDays is the Object Lock's default retention in a locked bucket;
	// PriorVersionDays is how long the lifecycle rule keeps a hidden version.
	LockDays         int
	PriorVersionDays int
	Purpose          string // shown to the person, such as "production's database backups"
	Why              string
	Name             string
	ObjectLock       bool
	Keys             []b2KeyPlan
}

type b2KeyPlan struct {
	Purpose         string
	KeyName         string
	Capabilities    []string
	VaultKeyIDName  string
	VaultSecretName string
}

// backblazePlan lists every B2 bucket and key this system uses, from the
// settings. A bucket the system does not use is not in the plan.
func backblazePlan(s systemSettings) ([]b2BucketPlan, error) {
	b := s.Vars.Backups
	prefix := s.keyNamePrefix()
	lockDays, priorVersionDays, err := s.backupLengths()
	if err != nil {
		return nil, err
	}
	if err := plainSetting("vars.backups.production_bucket", b.ProductionBucket); err != nil {
		return nil, err
	}
	plan := []b2BucketPlan{{
		LockDays: lockDays, PriorVersionDays: priorVersionDays,
		Purpose:    "production's database backups",
		Why:        "pgBackRest sends every database change and the backups here. A restore needs them after the worst kind of day.",
		Name:       b.ProductionBucket,
		ObjectLock: true,
		Keys: []b2KeyPlan{
			{Purpose: "the database servers' write key", KeyName: prefix + "-pgbackrest-write", Capabilities: b2DatabaseWriteCapabilities,
				VaultKeyIDName: "pgbackrest_b2_write_key_id", VaultSecretName: "pgbackrest_b2_write_application_key"},
			{Purpose: "the weekly restore drill's read-only key", KeyName: prefix + "-restore-drill-read-only", Capabilities: b2ReadOnlyCapabilities,
				VaultKeyIDName: "pgbackrest_b2_read_only_key_id", VaultSecretName: "pgbackrest_b2_read_only_application_key"},
		},
	}}
	if s.uploadsAreBackedUp() {
		if err := plainSetting("vars.backups.uploads_bucket", b.UploadsBucket); err != nil {
			return nil, err
		}
		plan = append(plan, b2BucketPlan{
			LockDays: lockDays, PriorVersionDays: priorVersionDays,
			Purpose: "the nightly copy of your apps' uploaded files", Why: "util01 copies each app's uploads from R2 here every night, so a deleted or overwritten upload comes back.",
			Name: b.UploadsBucket, ObjectLock: true,
			Keys: []b2KeyPlan{{Purpose: "util01's key for the uploads copy, which cannot delete", KeyName: prefix + "-util01-uploads-copy", Capabilities: b2UploadsCopyCapabilities,
				VaultKeyIDName: "uploads_backup_b2_write_key_id", VaultSecretName: "uploads_backup_b2_write_application_key"}},
		})
	}
	bucket, err := bucketOfReplicaURL(b.MMHotlineBackupReplicaURL)
	if err != nil {
		return nil, err
	}
	plan = append(plan, b2BucketPlan{
		PriorVersionDays: priorVersionDays,
		Purpose:          "MMHotline's backup", Why: "Litestream copies MMHotline's alert history here as it changes. This bucket has no Object Lock: Litestream cannot upload into a locked bucket.",
		Name: bucket, ObjectLock: false,
		Keys: []b2KeyPlan{{Purpose: "util01's key for MMHotline's backup", KeyName: prefix + "-mmhotline-backup", Capabilities: b2MMHotlineCapabilities,
			VaultKeyIDName: "mmhotline_backup_access_key_id", VaultSecretName: "mmhotline_backup_secret_access_key"}},
	})
	return plan, nil
}

// bucketOfReplicaURL reads the bucket from Litestream's address, such as
// s3://example-mmhotline-backup/mmhotline?endpoint=...
func bucketOfReplicaURL(replicaURL string) (string, error) {
	if err := plainSetting("vars.backups.mmhotline_backup_replica_url", replicaURL); err != nil {
		return "", err
	}
	parsed, err := url.Parse(replicaURL)
	if err != nil || parsed.Scheme != "s3" || parsed.Host == "" {
		return "", fmt.Errorf("vars.backups.mmhotline_backup_replica_url must look like s3://BUCKET/mmhotline?endpoint=...&region=..., not %q", replicaURL)
	}
	return parsed.Host, nil
}

type credentialForm int

const (
	// An R2 key: an account API token whose ID is the access key ID and
	// whose value's SHA-256 is the secret access key.
	r2KeyForm credentialForm = iota
	// A plain API token, saved as it is.
	apiTokenForm
)

// permissionGroup names one of Cloudflare's permission groups by its API
// name and the scope it applies to. Two groups can share a name across
// scopes, so the command finds each group's ID by both.
type permissionGroup struct {
	Name  string
	Scope string
}

// The scopes of permission groups, as Cloudflare lists them.
const (
	scopeAccount  = "com.cloudflare.api.account"
	scopeZone     = "com.cloudflare.api.account.zone"
	scopeR2Bucket = "com.cloudflare.edge.r2.bucket"
)

// The permission groups the command gives its tokens, by their API names.
// Their IDs are read from Cloudflare.
var (
	permissionR2BucketItemWrite = permissionGroup{"Workers R2 Storage Bucket Item Write", scopeR2Bucket}
	permissionR2BucketItemRead  = permissionGroup{"Workers R2 Storage Bucket Item Read", scopeR2Bucket}
	permissionWorkersScripts    = permissionGroup{"Workers Scripts Write", scopeAccount}
	// The person's desk token: what the coding agent does through the API
	// token proxy, and the person's own commands. docs/design.md, "Account
	// and secret setup from the systems desk", gives each group's reason.
	deskAccountPermissions = []permissionGroup{
		{"Cloudflare Tunnel Write", scopeAccount},
		{"Access: Apps and Policies Write", scopeAccount},
		{"Access: Organizations, Identity Providers, and Groups Read", scopeAccount},
		{"Access: Service Tokens Read", scopeAccount},
		{"Workers R2 Storage Write", scopeAccount},
	}
	deskZonePermissions = []permissionGroup{
		{"DNS Write", scopeZone},
		{"Cache Settings Write", scopeZone},
		{"Zone Read", scopeZone},
		{"Zone Transform Rules Write", scopeZone},
	}
	// The short-lived Access token: it adds the One-time PIN login method
	// and makes or renews staging's Access service token, then is deleted.
	accessSetUpPermissions = []permissionGroup{
		{"Access: Organizations, Identity Providers, and Groups Write", scopeAccount},
		{"Access: Service Tokens Write", scopeAccount},
	}
)

// tokenPolicyPlan is one policy of a token: its permission groups and the
// resources they apply to.
type tokenPolicyPlan struct {
	Groups    []permissionGroup
	Resources map[string]any
}

func onBuckets(group permissionGroup, resources map[string]any) tokenPolicyPlan {
	return tokenPolicyPlan{Groups: []permissionGroup{group}, Resources: resources}
}

func onAccount(accountID string, groups ...permissionGroup) tokenPolicyPlan {
	return tokenPolicyPlan{Groups: groups, Resources: map[string]any{"com.cloudflare.api.account." + accountID: "*"}}
}

// onEveryZone applies zone permissions to every zone of the account, so a
// domain the team adds later needs no new token.
func onEveryZone(accountID string, groups ...permissionGroup) tokenPolicyPlan {
	return tokenPolicyPlan{Groups: groups, Resources: map[string]any{
		"com.cloudflare.api.account." + accountID: map[string]any{"com.cloudflare.api.account.zone.*": "*"}}}
}

// cloudflareCredentialPlan is one account-owned token the command makes.
type cloudflareCredentialPlan struct {
	Purpose   string
	Why       string
	TokenName string
	Policies  []tokenPolicyPlan
	Form      credentialForm
	// VaultNames, for a token the servers use: R2 key: access key ID,
	// secret access key. API token: the token. Empty for the person's own
	// tokens, which go into the token file instead.
	VaultNames []string
	// UpdateResourcesWhenSaved makes a rerun bring the saved token's
	// resources up to date, keeping its value: util01's reader gains a new
	// app's bucket without a new key.
	UpdateResourcesWhenSaved bool
}

func r2BucketResource(accountID, bucket string) string {
	return "com.cloudflare.edge.r2.bucket." + accountID + "_default_" + bucket
}

// cloudflareAccountTokenPlan lists the account-owned tokens and R2 keys the
// servers use, except the status page's, whose bucket name comes from
// MMHotline's set-up during the run.
func cloudflareAccountTokenPlan(s systemSettings, accountID string) ([]cloudflareCredentialPlan, error) {
	var plan []cloudflareCredentialPlan
	readerResources := map[string]any{}
	for _, name := range s.appsWithUploads() {
		app := s.Vars.Apps[name]
		variables := app.ProductionUploadsR2KeyVariables
		if variables.AccessKeyID == "" || variables.SecretAccessKey == "" {
			return nil, fmt.Errorf("vars.apps.%s keeps uploads, so it needs production_uploads_r2_key_variables: the two names in its secrets_from_vault that hold its R2 key, access_key_id and secret_access_key", name)
		}
		for _, variable := range []string{variables.AccessKeyID, variables.SecretAccessKey} {
			if _, listed := app.SecretsFromVault[variable]; !listed {
				return nil, fmt.Errorf("vars.apps.%s.production_uploads_r2_key_variables names %s, which its secrets_from_vault does not list", name, variable)
			}
		}
		resource := r2BucketResource(accountID, app.ProductionUploadsR2Bucket)
		readerResources[resource] = "*"
		plan = append(plan, cloudflareCredentialPlan{
			Purpose:   name + "'s key for its uploads bucket " + app.ProductionUploadsR2Bucket,
			Why:       name + " reads and writes its uploaded files in R2 with this key.",
			TokenName: s.ProjectName + ": " + name + " reads and writes its uploads",
			Policies:  []tokenPolicyPlan{onBuckets(permissionR2BucketItemWrite, map[string]any{resource: "*"})}, Form: r2KeyForm,
			VaultNames: []string{name + "_" + variables.AccessKeyID, name + "_" + variables.SecretAccessKey},
		})
		if !s.hasStagingServer {
			continue
		}
		// staging01 reads each secret under the production name with
		// staging_ in front, so its app gets its own key to its own bucket,
		// never production's.
		stagingBucket, err := s.stagingUploadsBucket(name)
		if err != nil {
			return nil, err
		}
		plan = append(plan, cloudflareCredentialPlan{
			Purpose:   name + "'s staging key for its staging uploads bucket " + stagingBucket,
			Why:       "On staging01, " + name + " reads and writes its uploaded files in this bucket, apart from production's.",
			TokenName: s.ProjectName + ": " + name + " on staging reads and writes its uploads",
			Policies:  []tokenPolicyPlan{onBuckets(permissionR2BucketItemWrite, map[string]any{r2BucketResource(accountID, stagingBucket): "*"})}, Form: r2KeyForm,
			VaultNames: []string{"staging_" + name + "_" + variables.AccessKeyID, "staging_" + name + "_" + variables.SecretAccessKey},
		})
	}
	if s.uploadsAreBackedUp() {
		plan = append(plan, cloudflareCredentialPlan{
			Purpose:   "util01's read-only key for every app's uploads bucket",
			Why:       "util01's nightly copy reads the uploads with a key that can only read, so the copy can never change an upload.",
			TokenName: s.ProjectName + ": util01 reads the apps' uploads",
			Policies:  []tokenPolicyPlan{onBuckets(permissionR2BucketItemRead, readerResources)}, Form: r2KeyForm,
			VaultNames:               []string{"uploads_r2_read_only_access_key_id", "uploads_r2_read_only_secret_access_key"},
			UpdateResourcesWhenSaved: true,
		})
	}
	plan = append(plan, cloudflareCredentialPlan{
		Purpose:   "the MMHotline-down alarm's token",
		Why:       "The MMHotline-down alarm is the alarm that wakes you if MMHotline itself goes silent. MMHotline uploads it to Cloudflare with this token.",
		TokenName: s.ProjectName + ": MMHotline uploads the MMHotline-down alarm",
		Policies:  []tokenPolicyPlan{onAccount(accountID, permissionWorkersScripts)}, Form: apiTokenForm,
		VaultNames: []string{"mmhotline_down_alarm_cloudflare_api_token"},
	})
	return plan, nil
}

// statusPageVaultKeyID is the first vault key of the status page's R2 key,
// which --replace-key names before the run knows the page's bucket.
const statusPageVaultKeyID = "mmhotline_status_page_r2_access_key_id"

func statusPageCredentialPlan(s systemSettings, accountID, bucket string) cloudflareCredentialPlan {
	return cloudflareCredentialPlan{
		Purpose:   "MMHotline's key for the status page's bucket " + bucket,
		Why:       "MMHotline posts your status page's notices into this bucket.",
		TokenName: s.ProjectName + ": MMHotline posts to the status page",
		Policies:  []tokenPolicyPlan{onBuckets(permissionR2BucketItemWrite, map[string]any{r2BucketResource(accountID, bucket): "*"})}, Form: r2KeyForm,
		VaultNames: []string{statusPageVaultKeyID, "mmhotline_status_page_r2_secret_access_key"},
	}
}

// The person's own tokens, each named after the person's account on the
// desk, so a person reading Cloudflare's token list sees whose each one is,
// and a leaving person's tokens are found by name.

func deskTokenName(s systemSettings, person string) string {
	return s.ProjectName + ": " + person + "'s systems desk sets up Cloudflare"
}

func statusPagePostingTokenName(s systemSettings, person string) string {
	return s.ProjectName + ": " + person + " posts to the status page"
}

// linkTokenName is the name the prepared link gives the token the person
// makes by hand. The command deletes that token when it ends.
func linkTokenName(s systemSettings, person string) string {
	return s.ProjectName + ": " + person + " makes tokens with set-up-outside-services, deleted after the run"
}

func accessSetUpTokenName(s systemSettings) string {
	return s.ProjectName + ": set-up-outside-services sets up Access, deleted after the run"
}

func deskTokenPlan(s systemSettings, accountID, person string) cloudflareCredentialPlan {
	return cloudflareCredentialPlan{
		Purpose:   "your systems desk's Cloudflare token",
		Why:       "Your coding agent sets up tunnels, DNS, Access, the cache rule, and R2 buckets with it, through the API proxy, without reading it.",
		TokenName: deskTokenName(s, person),
		Policies:  []tokenPolicyPlan{onAccount(accountID, deskAccountPermissions...), onEveryZone(accountID, deskZonePermissions...)},
		Form:      apiTokenForm,
	}
}

func statusPagePostingTokenPlan(s systemSettings, accountID, person, bucket string) cloudflareCredentialPlan {
	return cloudflareCredentialPlan{
		Purpose:   "your own key for posting to the status page",
		Why:       "You post to the status page from this desk with it while util01 is down.",
		TokenName: statusPagePostingTokenName(s, person),
		Policies:  []tokenPolicyPlan{onBuckets(permissionR2BucketItemWrite, map[string]any{r2BucketResource(accountID, bucket): "*"})},
		Form:      r2KeyForm,
	}
}

func accessSetUpTokenPlan(s systemSettings, accountID string) cloudflareCredentialPlan {
	return cloudflareCredentialPlan{
		Purpose:   "a short-lived token for Access",
		TokenName: accessSetUpTokenName(s),
		Policies:  []tokenPolicyPlan{onAccount(accountID, accessSetUpPermissions...)},
		Form:      apiTokenForm,
	}
}

type tunnelPlan struct {
	Name      string
	VaultName string
	Routes    string
}

// tunnelsPlan names each tunnel after the project, such as
// example_systems-apps, so two systems in one Cloudflare account never share
// a tunnel. Unlike a token name, a tunnel name has no space or colon, so it
// goes into an API query or a cloudflared command as it is.
func tunnelsPlan(s systemSettings) []tunnelPlan {
	plan := []tunnelPlan{
		{Name: s.ProjectName + "-apps", VaultName: "apps_cloudflare_tunnel_token", Routes: "each app's production host name"},
		{Name: s.ProjectName + "-util01", VaultName: "util01_cloudflare_tunnel_token", Routes: "MMHotline's dashboard"},
	}
	if s.hasStagingServer {
		plan = append(plan, tunnelPlan{Name: s.ProjectName + "-staging_apps", VaultName: "staging_apps_cloudflare_tunnel_token", Routes: "each app's staging host name"})
	}
	return plan
}

func contains(list []string, value string) bool {
	for _, item := range list {
		if item == value {
			return true
		}
	}
	return false
}

// domain is the domain the system runs on: status_page_host_name without its
// first label, such as example.com for status.example.com. The status page
// sits right under the domain, as the template has it.
func (s systemSettings) domain() (string, error) {
	host := s.Vars.StatusPageHostName
	if err := plainSetting("vars.status_page_host_name", host); err != nil {
		return "", err
	}
	_, domain, _ := strings.Cut(host, ".")
	if !strings.Contains(domain, ".") {
		return "", fmt.Errorf("vars.status_page_host_name in %s is %s. Set it to a name right under your domain, such as status.example.com", projectSettingsFile, host)
	}
	return domain, nil
}
