package main

import (
	"bytes"
	"crypto/rand"
	"crypto/sha1"
	"encoding/hex"
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

// B2's native API, version 4: https://www.backblaze.com/apidocs/introduction-to-the-b2-native-api
const b2AuthorizeURL = "https://api.backblazeb2.com/b2api/v4/b2_authorize_account"

// Links the person opens to see the result. Backblaze's dashboard has no
// address for one bucket, so the links name the account's pages and the
// output names each bucket.
const (
	b2BucketsPage = "https://secure.backblaze.com/b2_buckets.htm"
	b2KeysPage    = "https://secure.backblaze.com/app_keys.htm"
)

// The master key's capabilities this command uses: create and change
// buckets, set their lock, check the lock with a test file, and make and
// revoke keys.
var b2CapabilitiesNeeded = []string{"listBuckets", "writeBuckets", "readBucketRetentions", "writeBucketRetentions",
	"listFiles", "writeFiles", "deleteFiles", "readFileRetentions", "listKeys", "writeKeys", "deleteKeys"}

type b2Client struct {
	accountID    string
	apiURL       string
	s3APIURL     string
	token        string
	capabilities []string
}

func readB2Error(body []byte) (string, string) {
	var refusal struct {
		Code    string `json:"code"`
		Message string `json:"message"`
	}
	_ = json.Unmarshal(body, &refusal)
	return refusal.Code, refusal.Message
}

// https://www.backblaze.com/apidocs/b2-authorize-account
func authorizeB2(authorizeURL, keyID, applicationKey string) (*b2Client, error) {
	request, err := http.NewRequest(http.MethodGet, authorizeURL, nil)
	if err != nil {
		return nil, err
	}
	request.SetBasicAuth(keyID, applicationKey)
	response, err := httpClient.Do(request)
	if err != nil {
		return nil, &networkError{Provider: "Backblaze", Call: "b2_authorize_account", Err: stripURLFromError(err)}
	}
	defer response.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(response.Body, 1<<20))
	if response.StatusCode != http.StatusOK {
		code, _ := readB2Error(body)
		return nil, &apiError{Provider: "Backblaze", Call: "b2_authorize_account", Status: response.StatusCode, Code: code}
	}
	var answer struct {
		AccountID          string `json:"accountId"`
		AuthorizationToken string `json:"authorizationToken"`
		APIInfo            struct {
			StorageAPI struct {
				APIURL   string `json:"apiUrl"`
				S3APIURL string `json:"s3ApiUrl"`
				Allowed  struct {
					Capabilities []string `json:"capabilities"`
				} `json:"allowed"`
			} `json:"storageApi"`
		} `json:"apiInfo"`
	}
	if err := json.Unmarshal(body, &answer); err != nil || answer.AuthorizationToken == "" || answer.APIInfo.StorageAPI.APIURL == "" {
		return nil, errors.New("Backblaze answered b2_authorize_account with something this command cannot read")
	}
	return &b2Client{accountID: answer.AccountID, apiURL: answer.APIInfo.StorageAPI.APIURL, s3APIURL: answer.APIInfo.StorageAPI.S3APIURL,
		token: answer.AuthorizationToken, capabilities: answer.APIInfo.StorageAPI.Allowed.Capabilities}, nil
}

func (c *b2Client) call(name string, body, result any) error {
	_, err := doJSON("Backblaze", name, http.MethodPost, c.apiURL+"/b2api/v4/"+name, map[string]string{"Authorization": c.token}, body, result, readB2Error)
	return err
}

type b2LifecycleRule struct {
	FileNamePrefix            string `json:"fileNamePrefix"`
	DaysFromHidingToDeleting  *int   `json:"daysFromHidingToDeleting"`
	DaysFromUploadingToHiding *int   `json:"daysFromUploadingToHiding"`
}

type b2RetentionPeriod struct {
	Duration int    `json:"duration"`
	Unit     string `json:"unit"`
}

type b2DefaultRetention struct {
	Mode   *string            `json:"mode"`
	Period *b2RetentionPeriod `json:"period"`
}

type b2Bucket struct {
	BucketID              string `json:"bucketId"`
	BucketName            string `json:"bucketName"`
	BucketType            string `json:"bucketType"`
	FileLockConfiguration struct {
		IsClientAuthorizedToRead bool `json:"isClientAuthorizedToRead"`
		Value                    *struct {
			IsFileLockEnabled bool               `json:"isFileLockEnabled"`
			DefaultRetention  b2DefaultRetention `json:"defaultRetention"`
		} `json:"value"`
	} `json:"fileLockConfiguration"`
	LifecycleRules []b2LifecycleRule `json:"lifecycleRules"`
}

// The one lifecycle rule every bucket gets: a hidden version is deleted
// keep_prior_file_versions_in_buckets_for_days after it was hidden; a current
// file is never hidden by age.
func wantedLifecycleRules(priorVersionDays int) []b2LifecycleRule {
	days := priorVersionDays
	return []b2LifecycleRule{{FileNamePrefix: "", DaysFromHidingToDeleting: &days, DaysFromUploadingToHiding: nil}}
}

func lifecycleMatches(rules []b2LifecycleRule, priorVersionDays int) bool {
	return len(rules) == 1 && rules[0].FileNamePrefix == "" && rules[0].DaysFromUploadingToHiding == nil &&
		rules[0].DaysFromHidingToDeleting != nil && *rules[0].DaysFromHidingToDeleting == priorVersionDays
}

func (b b2Bucket) lockEnabled() bool {
	return b.FileLockConfiguration.Value != nil && b.FileLockConfiguration.Value.IsFileLockEnabled
}

func (b b2Bucket) retentionMatches(lockDays int) bool {
	if b.FileLockConfiguration.Value == nil {
		return false
	}
	retention := b.FileLockConfiguration.Value.DefaultRetention
	return retention.Mode != nil && *retention.Mode == "compliance" && retention.Period != nil &&
		retention.Period.Duration == lockDays && retention.Period.Unit == "days"
}

// https://www.backblaze.com/apidocs/b2-list-buckets
func (c *b2Client) findBucket(name string) (*b2Bucket, error) {
	var answer struct {
		Buckets []b2Bucket `json:"buckets"`
	}
	if err := c.call("b2_list_buckets", map[string]any{"accountId": c.accountID, "bucketName": name}, &answer); err != nil {
		return nil, err
	}
	for i := range answer.Buckets {
		if answer.Buckets[i].BucketName == name {
			return &answer.Buckets[i], nil
		}
	}
	return nil, nil
}

// ensureBucket makes the bucket match its plan: creates it when missing,
// then sets whatever differs. It returns sentences that say what changed.
func (c *b2Client) ensureBucket(plan b2BucketPlan) (*b2Bucket, []string, error) {
	var changes []string
	bucket, err := c.findBucket(plan.Name)
	if err != nil {
		return nil, nil, err
	}
	if bucket == nil {
		// https://www.backblaze.com/apidocs/b2-create-bucket
		body := map[string]any{"accountId": c.accountID, "bucketName": plan.Name, "bucketType": "allPrivate",
			"fileLockEnabled": plan.ObjectLock, "lifecycleRules": wantedLifecycleRules(plan.PriorVersionDays)}
		var created b2Bucket
		if err := c.call("b2_create_bucket", body, &created); err != nil {
			var refusal *apiError
			if errors.As(err, &refusal) && refusal.Code == "duplicate_bucket_name" {
				return nil, nil, fmt.Errorf("the bucket name %s is taken in another Backblaze account. Bucket names are unique across all of Backblaze: choose another name in %s, then run this command again", plan.Name, projectSettingsFile)
			}
			return nil, nil, err
		}
		changes = append(changes, "Created the private bucket "+plan.Name+".")
		bucket = &created
	} else if bucket.BucketType != "allPrivate" {
		return nil, nil, fmt.Errorf("the bucket %s exists with type %s, not private. This command changes no bucket's type: make it private on Backblaze's website, or choose another name, then run this command again", plan.Name, bucket.BucketType)
	}
	if !bucket.FileLockConfiguration.IsClientAuthorizedToRead {
		return nil, nil, errors.New("this key cannot read the buckets' lock settings. Use the account's master application key")
	}
	update := map[string]any{}
	if plan.ObjectLock {
		if !bucket.lockEnabled() {
			// https://www.backblaze.com/docs/cloud-storage-enable-object-lock-with-the-native-api
			if err := c.call("b2_update_bucket", map[string]any{"accountId": c.accountID, "bucketId": bucket.BucketID, "fileLockEnabled": true}, nil); err != nil {
				return nil, nil, err
			}
			changes = append(changes, "Turned on Object Lock.")
		}
		if !bucket.retentionMatches(plan.LockDays) {
			mode := "compliance"
			update["defaultRetention"] = b2DefaultRetention{Mode: &mode, Period: &b2RetentionPeriod{Duration: plan.LockDays, Unit: "days"}}
			changes = append(changes, fmt.Sprintf("Set the lock's default retention: compliance mode, %d days.", plan.LockDays))
		}
	} else if bucket.lockEnabled() {
		return nil, nil, fmt.Errorf("the bucket %s has Object Lock on, and Litestream cannot upload into a locked bucket. Object Lock cannot be turned off: choose another name for MMHotline's backup bucket in vars.backups.mmhotline_backup_replica_url, then run this command again", plan.Name)
	}
	if !lifecycleMatches(bucket.LifecycleRules, plan.PriorVersionDays) {
		update["lifecycleRules"] = wantedLifecycleRules(plan.PriorVersionDays)
		changes = append(changes, fmt.Sprintf("Set the lifecycle rule: a deleted or replaced version is kept %d days, then deleted.", plan.PriorVersionDays))
	}
	if len(update) > 0 {
		// https://www.backblaze.com/apidocs/b2-update-bucket
		update["accountId"], update["bucketId"] = c.accountID, bucket.BucketID
		if err := c.call("b2_update_bucket", update, nil); err != nil {
			return nil, nil, err
		}
	}
	// Read the bucket back: the settings count only as Backblaze reports them.
	bucket, err = c.findBucket(plan.Name)
	if err != nil {
		return nil, nil, err
	}
	if bucket == nil {
		return nil, nil, fmt.Errorf("Backblaze does not list the bucket %s after creating it. Run this command again", plan.Name)
	}
	if plan.ObjectLock && (!bucket.lockEnabled() || !bucket.retentionMatches(plan.LockDays)) {
		return nil, nil, fmt.Errorf("Backblaze reports the bucket %s without compliance-mode Object Lock of %d days. Do not use the bucket; check it on Backblaze's website", plan.Name, plan.LockDays)
	}
	if !lifecycleMatches(bucket.LifecycleRules, plan.PriorVersionDays) {
		return nil, nil, fmt.Errorf("Backblaze reports the bucket %s without the %d-day lifecycle rule", plan.Name, plan.PriorVersionDays)
	}
	return bucket, changes, nil
}

// checkLockRefusesDeletion proves the lock by its behavior, not only by its
// settings: a new file gets the default retention, and Backblaze refuses to
// delete it, with the master key, which may delete files. A refusal from a
// key without deleteFiles would prove nothing, so the master key's
// capabilities are checked first (b2CapabilitiesNeeded).
func (c *b2Client) checkLockRefusesDeletion(bucket *b2Bucket, lockDays int, now time.Time) error {
	random := make([]byte, 4)
	_, _ = rand.Read(random)
	fileName := "set_up_outside_services_lock_check/" + now.UTC().Format("20060102T150405Z") + "-" + hex.EncodeToString(random) + ".txt"
	file, err := c.uploadFile(bucket.BucketID, fileName, "text/plain", []byte("Monkeymaxxing Stack Object Lock check\n"))
	if err != nil {
		return err
	}
	// https://www.backblaze.com/apidocs/b2-get-file-info
	var info struct {
		FileRetention struct {
			IsClientAuthorizedToRead bool `json:"isClientAuthorizedToRead"`
			Value                    *struct {
				Mode                 *string `json:"mode"`
				RetainUntilTimestamp *int64  `json:"retainUntilTimestamp"`
			} `json:"value"`
		} `json:"fileRetention"`
	}
	if err := c.call("b2_get_file_info", map[string]any{"fileId": file.FileID}, &info); err != nil {
		return err
	}
	retention := info.FileRetention.Value
	earliest := now.Add(time.Duration(lockDays-1) * 24 * time.Hour).UnixMilli()
	if !info.FileRetention.IsClientAuthorizedToRead || retention == nil || retention.Mode == nil || *retention.Mode != "compliance" ||
		retention.RetainUntilTimestamp == nil || *retention.RetainUntilTimestamp < earliest {
		return fmt.Errorf("the lock check failed: a new file in %s did not get compliance-mode retention of %d days. Do not use the bucket", bucket.BucketName, lockDays)
	}
	// https://www.backblaze.com/apidocs/b2-delete-file-version
	err = c.call("b2_delete_file_version", map[string]any{"fileName": file.FileName, "fileId": file.FileID}, nil)
	var refusal *apiError
	switch {
	case err == nil:
		return fmt.Errorf("the lock check failed: Backblaze deleted the locked test file in %s. Do not use the bucket", bucket.BucketName)
	case errors.As(err, &refusal) && refusal.Status == http.StatusUnauthorized && refusal.Code == "access_denied":
	default:
		return fmt.Errorf("the lock check could not finish: %v. A refusal counts only as Backblaze's access_denied", err)
	}
	// Hide the test file, so the lifecycle rule deletes it once its lock ends.
	// https://www.backblaze.com/apidocs/b2-hide-file
	return c.call("b2_hide_file", map[string]any{"bucketId": bucket.BucketID, "fileName": file.FileName}, nil)
}

// b2File is an uploaded file, by its ID and name.
type b2File struct {
	FileID   string `json:"fileId"`
	FileName string `json:"fileName"`
}

// uploadFile uploads one small file into a bucket.
func (c *b2Client) uploadFile(bucketID, fileName, contentType string, content []byte) (b2File, error) {
	// https://www.backblaze.com/apidocs/b2-get-upload-url
	var upload struct {
		UploadURL          string `json:"uploadUrl"`
		AuthorizationToken string `json:"authorizationToken"`
	}
	if err := c.call("b2_get_upload_url", map[string]any{"bucketId": bucketID}, &upload); err != nil {
		return b2File{}, err
	}
	checksum := sha1.Sum(content)
	// https://www.backblaze.com/apidocs/b2-upload-file
	request, err := http.NewRequest(http.MethodPost, upload.UploadURL, bytes.NewReader(content))
	if err != nil {
		return b2File{}, err
	}
	request.Header.Set("Authorization", upload.AuthorizationToken)
	request.Header.Set("X-Bz-File-Name", url.PathEscape(fileName))
	request.Header.Set("Content-Type", contentType)
	request.Header.Set("X-Bz-Content-Sha1", hex.EncodeToString(checksum[:]))
	response, err := httpClient.Do(request)
	if err != nil {
		return b2File{}, &networkError{Provider: "Backblaze", Call: "b2_upload_file", Err: stripURLFromError(err)}
	}
	body, _ := io.ReadAll(io.LimitReader(response.Body, 1<<20))
	response.Body.Close()
	if response.StatusCode != http.StatusOK {
		code, _ := readB2Error(body)
		return b2File{}, &apiError{Provider: "Backblaze", Call: "b2_upload_file", Status: response.StatusCode, Code: code}
	}
	var file b2File
	if err := json.Unmarshal(body, &file); err != nil || file.FileID == "" {
		return b2File{}, errors.New("Backblaze answered b2_upload_file with something this command cannot read")
	}
	return file, nil
}

// https://www.backblaze.com/apidocs/b2-list-keys
func (c *b2Client) keyIDsNamed(name string) ([]string, error) {
	var ids []string
	start := ""
	for {
		body := map[string]any{"accountId": c.accountID, "maxKeyCount": 1000}
		if start != "" {
			body["startApplicationKeyId"] = start
		}
		var answer struct {
			Keys []struct {
				KeyName          string `json:"keyName"`
				ApplicationKeyID string `json:"applicationKeyId"`
			} `json:"keys"`
			NextApplicationKeyID *string `json:"nextApplicationKeyId"`
		}
		if err := c.call("b2_list_keys", body, &answer); err != nil {
			return nil, err
		}
		for _, key := range answer.Keys {
			if key.KeyName == name {
				ids = append(ids, key.ApplicationKeyID)
			}
		}
		if answer.NextApplicationKeyID == nil || *answer.NextApplicationKeyID == "" {
			return ids, nil
		}
		start = *answer.NextApplicationKeyID
	}
}

// https://www.backblaze.com/apidocs/b2-delete-key
func (c *b2Client) deleteKey(id string) error {
	return c.call("b2_delete_key", map[string]any{"applicationKeyId": id}, nil)
}

type b2NewKey struct {
	ApplicationKeyID string   `json:"applicationKeyId"`
	ApplicationKey   string   `json:"applicationKey"`
	Capabilities     []string `json:"capabilities"`
	BucketIDs        []string `json:"bucketIds"`
}

// https://www.backblaze.com/apidocs/b2-create-key
func (c *b2Client) createKey(plan b2KeyPlan, bucketID string) (b2NewKey, error) {
	var key b2NewKey
	err := c.call("b2_create_key", map[string]any{"accountId": c.accountID, "keyName": plan.KeyName,
		"capabilities": plan.Capabilities, "bucketIds": []string{bucketID}}, &key)
	return key, err
}

func sameSet(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	a, b = append([]string(nil), a...), append([]string(nil), b...)
	sort.Strings(a)
	sort.Strings(b)
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func missingCapabilities(have []string) []string {
	var missing []string
	for _, capability := range b2CapabilitiesNeeded {
		if !contains(have, capability) {
			missing = append(missing, capability)
		}
	}
	return missing
}

func runBackblaze(e *environment, arguments []string) error {
	e.named("backblaze")
	return e.asStep("backblaze", func(notes map[string]string) (string, error) {
		settings, err := readSystemSettings(e.readRepositoryFile)
		if err != nil {
			return "", err
		}
		plan, err := backblazePlan(settings)
		if err != nil {
			return "", err
		}
		replace, atOnce, err := keysToReplace(plan, arguments)
		if err != nil {
			return "", err
		}
		e.replaceKeys, e.deleteOldKeysAtOnce = replace, atOnce
		oldKeys := e.oldKeysFilePath(settings)
		saved, err := e.beginAccountChange(settings)
		if err != nil {
			return "", err
		}
		e.say("Backblaze B2 keeps your backups, separate from your server provider and Cloudflare.")
		e.say("This command creates each bucket your system uses, locks the database and uploads backups for %d days,", settings.Vars.Backups.LockBackupsAgainstDeletionForDays)
		e.say("checks each lock with a test file, makes each server's key with only the access it needs, and saves every key straight into the vault.")
		e.say("Your master key stays in this command's memory and is never saved. Nobody else sees it, your coding agent included.")
		e.say("")
		keyID, err := e.prompt("Backblaze master key's keyID (hidden): ")
		if err != nil {
			return "", err
		}
		applicationKey, err := e.prompt("Backblaze master key's applicationKey (hidden): ")
		if err != nil {
			return "", err
		}
		client, err := e.signInToBackblaze(keyID, applicationKey)
		if err != nil {
			return "", err
		}
		if endpoint := settings.Vars.Backups.B2S3Endpoint; !client.hasS3Endpoint(endpoint) {
			// An account's region cannot change, so the person chooses: keep
			// this account, and the coding agent sets the settings to its
			// region, or make an account in the planned region.
			accountEndpoint := strings.TrimPrefix(client.s3APIURL, "https://")
			region := strings.TrimSuffix(strings.TrimPrefix(accountEndpoint, "s3."), ".backblazeb2.com")
			notes["b2_account_s3_endpoint"], notes["b2_account_region"] = accountEndpoint, region
			return "", fmt.Errorf("saved nothing: the Backblaze account is in the region %s (S3 endpoint %s), but vars.backups.b2_s3_endpoint in %s is %s. "+
				"An account's region cannot change. To keep this account, set b2_s3_endpoint and b2_region to the account's; or make a new Backblaze account in the planned region. Then run this command again",
				region, accountEndpoint, projectSettingsFile, endpoint)
		}
		e.say("Signed in to Backblaze account %s.", client.accountID)
		if err := e.setUpBackblaze(client, plan, saved, oldKeys); err != nil {
			return "", err
		}
		e.say("")
		e.say("See the buckets on Backblaze's website: %s", b2BucketsPage)
		e.say("See the keys: %s", b2KeysPage)
		if atOnce {
			if err := e.deleteOldKeys(oldKeys, "backblaze", false, client.deleteKey, b2KeysPage); err != nil {
				return "", err
			}
		}
		if err := e.finishVaultChange(saved, e.commandLine); err != nil {
			return "", err
		}
		if atOnce && len(replace) > 0 {
			e.say("The servers get the new keys at the next run of every_server: tell your coding agent to run it now.")
		}
		// The vault is pushed, so the run can bring the new keys to the servers.
		// The master key stays in this command's memory only while it waits.
		if err := e.deleteOldKeys(oldKeys, "backblaze", true, client.deleteKey, b2KeysPage); err != nil {
			return "", err
		}
		e.say(sayTheCodingAgentCarriesOn)
		if settings.uploadsAreBackedUp() && len(settings.Vars.Backups.UploadsBackupRunsOn) == 0 {
			e.say("The uploads' bucket and key are ready, so your coding agent can now set vars.backups.uploads_backup_runs_on to [util_server].")
		}
		return stepDone, nil
	})
}

// signInToBackblaze signs in with the master application key, and refuses
// a key that lacks a capability this command uses, before anything changes.
func (e *environment) signInToBackblaze(keyID, applicationKey string) (*b2Client, error) {
	client, err := authorizeB2(e.b2AuthorizeURL, keyID, applicationKey)
	if err != nil {
		return nil, err
	}
	if missing := missingCapabilities(client.capabilities); len(missing) > 0 {
		return nil, fmt.Errorf("this key lacks %s. Use the account's master application key, from Backblaze's App Keys page: %s", strings.Join(missing, ", "), b2KeysPage)
	}
	return client, nil
}

// hasS3Endpoint says whether the account's S3 endpoint is endpoint, such as
// s3.eu-central-003.backblazeb2.com. An empty one on either side matches.
func (c *b2Client) hasS3Endpoint(endpoint string) bool {
	return endpoint == "" || c.s3APIURL == "" || strings.HasSuffix(c.s3APIURL, "//"+endpoint)
}

// setUpBackblaze makes each bucket of the plan match it, checks each lock
// before the bucket's first key, and saves each server's key in the vault.
func (e *environment) setUpBackblaze(client *b2Client, plan []b2BucketPlan, saved *savedKeys, oldKeys string) error {
	for _, bucketPlan := range plan {
		if err := e.stopIfInterrupted(); err != nil {
			return err
		}
		e.say("")
		e.say("Bucket %s, for %s.", bucketPlan.Name, bucketPlan.Purpose)
		e.say("  Why: %s", bucketPlan.Why)
		bucket, changes, err := client.ensureBucket(bucketPlan)
		if err != nil {
			return err
		}
		if len(changes) == 0 {
			changes = []string{"The bucket already had the right settings."}
		}
		for _, change := range changes {
			e.say("  %s", change)
		}
		if bucketPlan.ObjectLock {
			e.say("  Backblaze reports: private, Object Lock on in compliance mode, %d days of default retention, prior versions kept %d days.", bucketPlan.LockDays, bucketPlan.PriorVersionDays)
		} else {
			e.say("  Backblaze reports: private, no Object Lock, prior versions kept %d days.", bucketPlan.PriorVersionDays)
		}
		needsKeys := false
		for _, key := range bucketPlan.Keys {
			needsKeys = needsKeys || !saved.hasAll(key.VaultKeyIDName, key.VaultSecretName)
		}
		if bucketPlan.ObjectLock && needsKeys {
			if err := client.checkLockRefusesDeletion(bucket, bucketPlan.LockDays, e.now()); err != nil {
				return err
			}
			e.say("  Lock check passed: Backblaze gave a new test file %d days of compliance-mode retention and refused to delete it.", bucketPlan.LockDays)
			e.say("  The test file is hidden now, and the lifecycle rule deletes it once its lock ends.")
		}
		for _, keyPlan := range bucketPlan.Keys {
			if err := e.ensureB2Key(client, bucket, keyPlan, saved, oldKeys); err != nil {
				return err
			}
		}
	}
	return nil
}

func (e *environment) ensureB2Key(client *b2Client, bucket *b2Bucket, plan b2KeyPlan, saved *savedKeys, oldKeys string) error {
	names := []string{plan.VaultKeyIDName, plan.VaultSecretName}
	rotating := e.replaceKeys[plan.VaultKeyIDName]
	var before []string
	if rotating {
		ids, err := client.keyIDsNamed(plan.KeyName)
		if err != nil {
			return err
		}
		before = ids
	}
	var applicationKey string
	outcome, id, err := e.issueAndSave(saved, issuedCredential{
		provider: "Backblaze", item: "key", name: plan.KeyName, vaultNames: names,
		deletePage: b2KeysPage, replaceSaved: rotating,
		idsNamed: func() ([]string, error) { return client.keyIDsNamed(plan.KeyName) },
		delete:   client.deleteKey,
		create: func() (string, []string, string, error) {
			key, err := client.createKey(plan, bucket.BucketID)
			if err != nil {
				return "", nil, "", err
			}
			problem := ""
			if key.ApplicationKey == "" || !sameSet(key.Capabilities, plan.Capabilities) || !sameSet(key.BucketIDs, []string{bucket.BucketID}) {
				problem = "with other access than asked for"
			}
			applicationKey = key.ApplicationKey
			return key.ApplicationKeyID, []string{key.ApplicationKeyID, key.ApplicationKey}, problem, nil
		},
	})
	if err != nil {
		return err
	}
	if outcome == alreadySaved {
		e.say("  %s: already in the vault as %s and %s. Unchanged.", capitalize(plan.Purpose), names[0], names[1])
		return nil
	}
	e.say("  Made %s, %s (ID %s): %s, on this bucket only.", plan.Purpose, plan.KeyName, id, strings.Join(plan.Capabilities, ", "))
	e.say("    Saved in the vault as %s and %s.", names[0], names[1])
	// During the setup, the recovery bundle's copy at the lock goes up with
	// this key, so the person never gives the master key twice.
	if plan.VaultKeyIDName == backupWriteKeyIDVaultName && saved.copyInto != nil {
		if err := e.keepTheBackupWriteKey(id, applicationKey); err != nil {
			return fmt.Errorf("keeping the new write key for the recovery bundle's upload failed: %v", err)
		}
	}
	// The old key keeps working until the servers run with the new one.
	// The end of the run deletes it: after the person's Enter, or at once.
	var old []oldKey
	for _, oldID := range before {
		if oldID != id {
			old = append(old, oldKey{Provider: "backblaze", ID: oldID, Name: plan.KeyName})
		}
	}
	return recordOldKeys(oldKeys, old...)
}

// keysToReplace reads --replace-key VAULT_KEY_ID_NAME, which makes a new key
// for that pair even though the vault has one: a rotation; and
// --delete-the-old-keys-at-once.
func keysToReplace(plan []b2BucketPlan, arguments []string) (map[string]bool, bool, error) {
	replace := map[string]bool{}
	atOnce := false
	for i := 0; i < len(arguments); i++ {
		if arguments[i] == deleteTheOldKeysAtOnceFlag {
			atOnce = true
			continue
		}
		if arguments[i] != "--replace-key" || i+1 >= len(arguments) {
			return nil, false, fmt.Errorf("backblaze takes only --replace-key VAULT_KEY, such as --replace-key pgbackrest_b2_write_key_id, and %s: %w", deleteTheOldKeysAtOnceFlag, errUsage)
		}
		name := arguments[i+1]
		known := false
		for _, bucket := range plan {
			for _, key := range bucket.Keys {
				known = known || key.VaultKeyIDName == name
			}
		}
		if !known {
			return nil, false, fmt.Errorf("--replace-key %s names no key of this system. Give a key ID's vault name, such as pgbackrest_b2_write_key_id", name)
		}
		replace[name] = true
		i++
	}
	return replace, atOnce, nil
}

func capitalize(text string) string {
	if text == "" {
		return text
	}
	return strings.ToUpper(text[:1]) + text[1:]
}
