package main

import (
	"crypto/rand"
	"encoding/json"
	"errors"
	"fmt"
	"math/big"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// The recovery bundle holds every secret a lost desk cannot be rebuilt
// without, in one MMX vault file of its own, recovery_bundle.age in the
// systems repository, encrypted with a six-word recovery passphrase that
// only the person's password manager keeps. A copy goes into the locked
// backup bucket at Backblaze, so the bundle outlives the Git host too. The
// phone code's secret stays out: the emergency codes replace a lost phone.
//
// The setup's account commands open the bundle on first use and copy each
// item into it the moment they make it, because some items exist nowhere
// else the desk can read again, such as the backups' passphrase. lock-the-desk
// adds the items only the person may see, checks that the bundle holds every
// item, and saves it.

const recoveryBundleFile = "recovery_bundle.age"

// The bundle's keys.
const (
	bundleVaultPassphrase        = "mmx_vault_passphrase"
	bundleProductionKey          = "production_ssh_private_key"
	bundleWireGuardKey           = "desk_wireguard_private_key"
	bundleProviderCredential     = "server_provider_api_credential"
	bundleCloudflareDeskToken    = "cloudflare_desk_api_token"
	bundleStagingAccessClientID  = "staging_access_client_id"
	bundleStagingAccessSecret    = "staging_access_client_secret"
	bundleConsolePassword        = "shared_root_console_password"
	bundlePhoneCodeEmergencyCode = "phone_code_emergency_codes"
)

// copiedIntoTheBundle are the vault keys the recovery bundle keeps a copy
// of, because the desk keeps them nowhere else readable: the backups'
// passphrase, without which no backup can be read, and the restore drill's
// read-only Backblaze key, which reads every backup. Each value goes into
// the bundle when the vault saves it.
var copiedIntoTheBundle = map[string]bool{
	"pgbackrest_repository_cipher_passphrase": true,
	"pgbackrest_b2_read_only_key_id":          true,
	"pgbackrest_b2_read_only_application_key": true,
}

// madeBy names the command that makes each bundle item, for a refusal that
// lists the missing ones.
var madeBy = map[string]string{
	"pgbackrest_repository_cipher_passphrase": "from-the-coding-agent random-secrets",
	"pgbackrest_b2_read_only_key_id":          "backblaze",
	"pgbackrest_b2_read_only_application_key": "backblaze",
	bundleCloudflareDeskToken:                 "cloudflare",
	bundleStagingAccessClientID:               "cloudflare",
	bundleStagingAccessSecret:                 "cloudflare",
}

// The desk's files the bundle copies. The desk role makes each.
const deskWireGuardPrivateKeyFile = "/etc/wireguard/wg0.private_key"

// backupWriteKeyFile keeps the database backups' write key from the
// backblaze command until lock-the-desk has uploaded the bundle's copy with
// it, so the person never gives the Backblaze master key twice. root:root
// 0600; lock-the-desk deletes it after the upload.
const backupWriteKeyFile = "/var/lib/monkeymaxxing-stack/backup_write_key_until_the_bundle_is_uploaded"

// The vault keys of the key the bundle's uploads use: the database
// servers' write key on the production backup bucket.
const (
	backupWriteKeyIDVaultName          = "pgbackrest_b2_write_key_id"
	backupWriteApplicationKeyVaultName = "pgbackrest_b2_write_application_key"
)

// productionKeyFile is the production private key, which the desk role
// makes in the person's own home (roles/systems_desk/main.yml,
// create_the_persons_production_key) for the desk's SSH agent.
func (e *environment) productionKeyFile() string {
	return filepath.Join(e.home, ".ssh", "production_key")
}

// recoveryPassphraseWords is how many words the passphrase has. Six words
// of the 2048 give 66 bits, and MMX's vault (age with scrypt) makes each
// guess cost a fixed amount of memory and time, so a copy of the bundle at
// the Git host or Backblaze cannot be opened by guessing. More words would
// cost the person typing at every recovery for no practical gain.
const recoveryPassphraseWords = 6

func newRecoveryPassphrase() (string, error) {
	words := make([]string, recoveryPassphraseWords)
	for i := range words {
		n, err := rand.Int(rand.Reader, big.NewInt(int64(len(passphraseWordList))))
		if err != nil {
			return "", err
		}
		words[i] = passphraseWordList[n.Int64()]
	}
	return strings.Join(words, " "), nil
}

// recoveryPassphraseFile keeps the passphrase from the first account
// command until lock-the-desk has saved the bundle, readable only by the
// person, so every command adds to the same bundle. MMX reads the bundle's
// passphrase from it.
func (e *environment) recoveryPassphraseFile(settings systemSettings) string {
	return filepath.Join(e.home, ".config", "monkeymaxxing-stack", settings.ProjectName+"_recovery_passphrase_until_the_bundle_is_saved")
}

// openTheBundle opens the recovery bundle with its passphrase, making the
// passphrase on first use. It returns no bundle when lock-the-desk saved it
// already: the bundle exists and its passphrase file is gone. A later run,
// such as a key rotation, then leaves the bundle as it is.
func (e *environment) openTheBundle(settings systemSettings) (*savedKeys, string, error) {
	path := e.recoveryPassphraseFile(settings)
	var passphrase string
	text, err := os.ReadFile(path)
	switch {
	case err == nil:
		passphrase = strings.TrimSpace(string(text))
	case errors.Is(err, os.ErrNotExist):
		if e.repositoryHas(recoveryBundleFile) {
			return nil, "", nil
		}
		if passphrase, err = newRecoveryPassphrase(); err != nil {
			return nil, "", err
		}
		if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
			return nil, "", err
		}
		if err := os.WriteFile(path, []byte(passphrase+"\n"), 0o600); err != nil {
			return nil, "", err
		}
		if err := e.giveToThePerson(path); err != nil {
			return nil, "", err
		}
	default:
		return nil, "", err
	}
	store := e.bundleVault(path)
	names := map[string]bool{}
	if e.repositoryHas(recoveryBundleFile) {
		if names, err = store.keys(); err != nil {
			return nil, "", err
		}
	}
	return &savedKeys{store: store, names: names}, passphrase, nil
}

// bundleVault is the bundle's MMX vault, which a test may replace. MMX runs
// from the passphrase's folder, which holds no project settings, so the
// bundle never depends on the project's MMX settings.
func (e *environment) bundleVault(passphraseFile string) vault {
	if e.bundleStore != nil {
		return e.bundleStore
	}
	return mmxVault{directory: filepath.Dir(passphraseFile), file: filepath.Join(e.directory, recoveryBundleFile), passwordFile: passphraseFile,
		asRoot: e.inTheCodingAgentsCheckout}
}

// beginAccountChange opens the vault for an account command and, during
// the setup, the recovery bundle, so each item the command saves goes into
// the bundle too.
func (e *environment) beginAccountChange(settings systemSettings) (*savedKeys, error) {
	saved, err := e.beginVaultChange()
	if err != nil {
		return nil, err
	}
	bundle, _, err := e.openTheBundle(settings)
	if err != nil {
		return nil, err
	}
	if bundle != nil {
		saved.copyInto, saved.copied = bundle, copiedIntoTheBundle
	}
	return saved, nil
}

// keepTheBackupWriteKey keeps the database backups' new write key, as root,
// for the bundle's upload at the lock.
func (e *environment) keepTheBackupWriteKey(keyID, applicationKey string) error {
	return e.writeFileAsRoot(e.backupWriteKeyFile, 0o600, []byte(keyID+"\n"+applicationKey+"\n"))
}

// readProviderCredential reads the server provider's credential from the
// desk's API proxy, where the desk's bootstrap put it. util01 uses the same
// credential, and the recovery bundle keeps it.
func (e *environment) readProviderCredential(settings systemSettings) (string, error) {
	path := proxyAPIs["server-provider"].file
	if _, signs := requestSigningMethods[settings.Vars.SystemsDeskProviderAPIAuthentication]; signs {
		path = signingCredentialFile
	}
	content, err := e.readRootFile(path)
	if err != nil {
		return "", fmt.Errorf("this systems desk has no server provider key in its API proxy yet (%v). Your coding agent puts it there when it sets up your systems desk; ask your coding agent", err)
	}
	if path == signingCredentialFile {
		var credential signingCredential
		if json.Unmarshal(content, &credential) != nil || credential.Token == "" {
			return "", fmt.Errorf("%s is not the API proxy's credential file", path)
		}
		return credential.Token, nil
	}
	// The proxy's one line: proxy_set_header HEADER "TOKEN";
	_, quoted, found := strings.Cut(strings.TrimSpace(string(content)), `"`)
	token, _, closed := strings.Cut(quoted, `"`)
	token = strings.TrimPrefix(token, "Bearer ")
	if !found || !closed || checkTokenValue("token", token) != nil {
		return "", fmt.Errorf("%s does not hold the API proxy's token line", path)
	}
	return token, nil
}

// bundleItemsFromTheAccounts lists the bundle items the account commands make,
// with the values lock-the-desk reads from the desk, so lock-the-desk can
// refuse before its first screen when an account command has not run.
func (e *environment) bundleItemsFromTheAccounts(settings systemSettings, bundle *savedKeys) (map[string]string, []string) {
	tokenFile := e.tokenFilePath(settings)
	values := map[string]string{bundleCloudflareDeskToken: tokenFileValue(tokenFile, deskTokenVariable)}
	if settings.hasStagingServer {
		values[bundleStagingAccessClientID] = tokenFileValue(tokenFile, stagingAccessClientIDVariable)
		values[bundleStagingAccessSecret] = tokenFileValue(tokenFile, stagingAccessClientSecretVariable)
	}
	var missing []string
	for key, value := range values {
		if value == "" {
			missing = append(missing, key)
		}
	}
	for key := range copiedIntoTheBundle {
		if !bundle.names[key] {
			missing = append(missing, key)
		}
	}
	sort.Strings(missing)
	return values, missing
}

// rotatedBy names the rotation that makes a bundle item's value again when
// the vault holds it already: the command that made it skips a key the vault
// holds, so running it again would never fill the bundle.
var rotatedBy = map[string]string{
	"pgbackrest_repository_cipher_passphrase": "secrets --replace pgbackrest_repository_cipher_passphrase",
	"pgbackrest_b2_read_only_key_id":          "backblaze --replace-key pgbackrest_b2_read_only_key_id",
	"pgbackrest_b2_read_only_application_key": "backblaze --replace-key pgbackrest_b2_read_only_key_id",
}

// refuseMissingItems names each missing item and the command that makes it,
// or the rotation that makes it again when the vault holds it already.
func refuseMissingItems(missing []string, vault *savedKeys) error {
	var named []string
	for _, key := range missing {
		command := madeBy[key]
		if rotation := rotatedBy[key]; rotation != "" && vault != nil && vault.hasAll(key) {
			command = rotation
		}
		if command != "" {
			named = append(named, key+" (set-up-outside-services "+command+")")
		} else {
			named = append(named, key)
		}
	}
	return fmt.Errorf("the recovery bundle lacks %s. Run the command named beside each, then run lock-the-desk again", strings.Join(named, ", "))
}

// completeTheBundle adds the items the desk keeps in files and checks that
// the bundle holds every item.
func (e *environment) completeTheBundle(settings systemSettings, bundle *savedKeys, providerCredential string) error {
	fromTheDesk := []struct{ key, path string }{
		{bundleVaultPassphrase, deskVaultPassphraseFile},
		{bundleProductionKey, e.productionKeyFile()},
		{bundleWireGuardKey, deskWireGuardPrivateKeyFile},
	}
	for _, item := range fromTheDesk {
		content, err := e.readRootFile(item.path)
		if err != nil {
			return fmt.Errorf("reading %s for the recovery bundle failed: %v", item.path, err)
		}
		if err := bundle.save(item.key, strings.TrimSpace(string(content))); err != nil {
			return err
		}
	}
	values, missing := e.bundleItemsFromTheAccounts(settings, bundle)
	if len(missing) > 0 {
		return refuseMissingItems(missing, nil)
	}
	values[bundleProviderCredential] = providerCredential
	for _, key := range sortedKeys(values) {
		if err := bundle.save(key, values[key]); err != nil {
			return err
		}
	}
	var lacks []string
	for _, key := range []string{bundleConsolePassword, bundlePhoneCodeEmergencyCode} {
		if !bundle.names[key] {
			lacks = append(lacks, key)
		}
	}
	if len(lacks) > 0 {
		return fmt.Errorf("the recovery bundle lacks %s. Run lock-the-desk again: it asks for each", strings.Join(lacks, ", "))
	}
	return nil
}

func sortedKeys(values map[string]string) []string {
	var keys []string
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

// uploadTheBundle copies the pushed bundle into the locked backup bucket
// with the kept write key; lock-the-desk deletes the kept key's file once
// the upload is recorded.
func (e *environment) uploadTheBundle(settings systemSettings) error {
	kept, err := e.readRootFile(e.backupWriteKeyFile)
	if err != nil {
		return fmt.Errorf("the backup write key the backblaze command keeps for this upload is gone (%v). Run set-up-outside-services backblaze --replace-key %s, which makes a new one and keeps it, then run lock-the-desk again", err, backupWriteKeyIDVaultName)
	}
	lines := trimmedLines(string(kept))
	if len(lines) != 2 {
		return fmt.Errorf("%s does not hold a key ID and a key", e.backupWriteKeyFile)
	}
	upload, err := e.backupBucketUpload(settings, lines[0], lines[1])
	if err != nil {
		return err
	}
	content, err := e.readRepositoryFile(recoveryBundleFile)
	if err != nil {
		return err
	}
	return upload(content)
}

// backupBucketUpload signs in to Backblaze with a write key on the
// production backup bucket, finds the bucket, and returns the upload of one
// copy of a bundle. The bucket's lock keeps each copy from deletion; no
// lifecycle rule hides a current file, so each copy stays.
func (e *environment) backupBucketUpload(settings systemSettings, keyID, applicationKey string) (func(content []byte) error, error) {
	client, err := authorizeB2(e.b2AuthorizeURL, keyID, applicationKey)
	if err != nil {
		return nil, err
	}
	bucket, err := client.findBucket(settings.Vars.Backups.ProductionBucket)
	if err != nil {
		return nil, err
	}
	if bucket == nil {
		return nil, fmt.Errorf("Backblaze has no bucket %s for the recovery bundle's copy", settings.Vars.Backups.ProductionBucket)
	}
	return func(content []byte) error {
		name := "recovery_bundle/recovery_bundle_" + e.now().UTC().Format("20060102T150405Z") + ".age"
		if _, err := client.uploadFile(bucket.BucketID, name, "application/octet-stream", content); err != nil {
			return err
		}
		e.say("Copied the recovery bundle into the locked backup bucket %s as %s.", bucket.BucketName, name)
		return nil
	}, nil
}

// trimmedLines splits a file's text into its non-empty lines.
func trimmedLines(text string) []string {
	var lines []string
	for _, line := range strings.Split(text, "\n") {
		if line = strings.TrimSpace(line); line != "" {
			lines = append(lines, line)
		}
	}
	return lines
}
