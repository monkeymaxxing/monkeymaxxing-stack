package main

import (
	"crypto/rand"
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

const recoveryBundleFile = "recovery_bundle.age"

// The bundle's keys that the desk can read again at the end of the run.
// The others are made during the run and exist nowhere else: the console
// password, the emergency codes, and copiedIntoTheBundle.
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

// The desk's files the bundle copies. The desk role makes each.
const deskWireGuardPrivateKeyFile = "/etc/wireguard/wg0.private_key"

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

// recoveryPassphraseFile keeps the passphrase from the run's start until the
// bundle is pushed and copied, readable only by the person, so a rerun adds
// to the same bundle. MMX reads the bundle's passphrase from it.
func (g *goLive) recoveryPassphraseFile() string {
	return filepath.Join(g.e.home, ".config", "monkeymaxxing-stack", g.settings.ProjectName+"_recovery_passphrase_until_the_bundle_is_saved")
}

// openTheBundle reads the run's passphrase, or makes one on a first run, and
// opens the bundle with it.
func (g *goLive) openTheBundle() error {
	e := g.e
	path := g.recoveryPassphraseFile()
	text, err := os.ReadFile(path)
	switch {
	case err == nil:
		g.passphrase = strings.TrimSpace(string(text))
	case errors.Is(err, os.ErrNotExist):
		if _, err := os.Stat(filepath.Join(e.directory, recoveryBundleFile)); err == nil {
			return fmt.Errorf("%s exists, but its passphrase file %s is gone. Delete %s from the systems repository and run this command again: it makes a new bundle", recoveryBundleFile, path, recoveryBundleFile)
		}
		if g.passphrase, err = newRecoveryPassphrase(); err != nil {
			return err
		}
		if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
			return err
		}
		if err := os.WriteFile(path, []byte(g.passphrase+"\n"), 0o600); err != nil {
			return err
		}
	default:
		return err
	}
	// MMX runs from the passphrase's folder, which holds no project settings,
	// so the bundle never depends on the project's MMX settings.
	store := mmxVault{directory: filepath.Dir(path), file: filepath.Join(e.directory, recoveryBundleFile), passwordFile: path}
	names := map[string]bool{}
	if _, err := os.Stat(filepath.Join(e.directory, recoveryBundleFile)); err == nil {
		if names, err = store.keys(); err != nil {
			return err
		}
	}
	g.bundle = &savedKeys{store: store, names: names}
	g.saved.copyInto, g.saved.copied = g.bundle, copiedIntoTheBundle
	return nil
}

// recoveryBundle fills in the bundle's secrets that the desk keeps, checks
// that it holds everything, commits and pushes it, signed, and copies it into
// the locked backup bucket.
func (g *goLive) recoveryBundle() (string, error) {
	e := g.e
	tokenFile := e.tokenFilePath(g.settings)
	fromTheDesk := []struct{ key, path string }{
		{bundleVaultPassphrase, os.Getenv("MMX_VAULT_PASSWORD_FILE")},
		{bundleProductionKey, e.productionKeyFile()},
		{bundleWireGuardKey, deskWireGuardPrivateKeyFile},
	}
	wanted := []string{bundleVaultPassphrase, bundleProductionKey, bundleWireGuardKey, bundleProviderCredential, bundleCloudflareDeskToken,
		bundleConsolePassword, bundlePhoneCodeEmergencyCode}
	for key := range copiedIntoTheBundle {
		wanted = append(wanted, key)
	}
	err := e.quietly(func() error {
		for _, item := range fromTheDesk {
			content, err := e.readRootFile(item.path)
			if err != nil {
				return fmt.Errorf("reading %s for the recovery bundle failed: %v", item.path, err)
			}
			if err := g.bundle.save(item.key, strings.TrimSpace(string(content))); err != nil {
				return err
			}
		}
		// Staging's Access service token exists only with staging01.
		values := [][2]string{{bundleProviderCredential, g.providerCredential},
			{bundleCloudflareDeskToken, tokenFileValue(tokenFile, deskTokenVariable)},
			{bundleStagingAccessClientID, tokenFileValue(tokenFile, stagingAccessClientIDVariable)},
			{bundleStagingAccessSecret, tokenFileValue(tokenFile, stagingAccessClientSecretVariable)}}
		for _, value := range values {
			if value[1] == "" {
				continue
			}
			if err := g.bundle.save(value[0], value[1]); err != nil {
				return err
			}
		}
		return nil
	})
	if err != nil {
		return "", err
	}
	var lacks []string
	for _, key := range wanted {
		if !g.bundle.names[key] {
			lacks = append(lacks, key)
		}
	}
	if len(lacks) > 0 {
		// Such a key was made before this bundle, such as by an earlier
		// version's secrets step: the person's password manager keeps it.
		sort.Strings(lacks)
		g.note("recovery_bundle_lacks", strings.Join(lacks, " "))
	}
	if err := g.commitAndPushTheBundle(); err != nil {
		return "", err
	}
	if g.b2 == nil {
		// A rerun whose Backblaze screen was done in an earlier run: the
		// master key is never kept, so the copy needs it once more.
		if _, err := g.backblaze(); err != nil {
			return "", err
		}
	}
	err = e.quietly(func() error {
		content, err := os.ReadFile(filepath.Join(e.directory, recoveryBundleFile))
		if err != nil {
			return err
		}
		bucket, err := g.b2.findBucket(g.settings.Vars.Backups.ProductionBucket)
		if err != nil {
			return err
		}
		if bucket == nil {
			return fmt.Errorf("Backblaze has no bucket %s for the recovery bundle's copy", g.settings.Vars.Backups.ProductionBucket)
		}
		// The bucket's lock keeps the copy from deletion; no lifecycle rule
		// hides a current file, so it stays.
		name := "recovery_bundle/recovery_bundle_" + e.now().UTC().Format("20060102T150405Z") + ".age"
		_, err = g.b2.uploadFile(bucket.BucketID, name, "application/octet-stream", content)
		return err
	})
	if err != nil {
		return "", err
	}
	if err := os.Remove(g.recoveryPassphraseFile()); err != nil && !errors.Is(err, os.ErrNotExist) {
		return "", err
	}
	return stepDone, nil
}

func (g *goLive) commitAndPushTheBundle() error {
	e := g.e
	return e.quietly(func() error {
		status, err := e.git("status", "--porcelain", "--", recoveryBundleFile)
		if err != nil {
			return err
		}
		if strings.TrimSpace(status) != "" {
			if _, err := e.commitFiles("Add the recovery bundle with "+goLiveCommand, recoveryBundleFile); err != nil {
				return err
			}
		}
		_, err = e.git("push", "--quiet", "origin", "HEAD:main")
		return err
	})
}
