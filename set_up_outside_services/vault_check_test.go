package main

import (
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func originOf(t *testing.T, directory string) string {
	output, err := exec.Command("git", "-C", directory, "remote", "get-url", "origin").Output()
	if err != nil {
		t.Fatal(err)
	}
	return strings.TrimSpace(string(output))
}

// pushFromAnotherCheckout pushes a newer vault from a second checkout, as a
// teammate's run does, so the harness's checkout is behind origin.
func pushFromAnotherCheckout(t *testing.T, run func(string, ...string) string, directory string) {
	other := filepath.Join(t.TempDir(), "other")
	run(t.TempDir(), "clone", "--quiet", originOf(t, directory), other)
	writeFile(t, filepath.Join(other, vaultFile), "vault from another checkout\n")
	run(other, "commit", "--quiet", "-am", "Add keys elsewhere")
	run(other, "push", "--quiet")
}

// requirePushedVaultCommit checks that origin's main is a signed commit that
// changes only the vault, with the command's name in its message.
func (h *harness) requirePushedVaultCommit(command string) {
	h.t.Helper()
	pushed := h.git(h.e.directory, "--git-dir", h.origin, "cat-file", "commit", "main")
	if !strings.Contains(pushed, "vault keys with set-up-outside-services "+command) {
		h.t.Fatalf("origin's main is not a vault commit by %s:\n%s", command, pushed)
	}
	if files := strings.TrimSpace(h.git(h.e.directory, "--git-dir", h.origin, "diff-tree", "--no-commit-id", "--name-only", "-r", "main")); files != vaultFile {
		h.t.Fatalf("the pushed commit changes %q, not only the vault", files)
	}
	if h.git(h.e.directory, "status", "--porcelain") != "" {
		h.t.Fatalf("the run left changes that are not committed")
	}
	if strings.Contains(h.out.String(), "git add") || !strings.Contains(h.out.String(), "published to the main copy on util01") {
		h.t.Fatalf("the output does not say the vault was pushed, or still tells the person to push:\n%s", h.out)
	}
}

func TestBackblazeAndCloudflareCommitAndPushTheVaultSigned(t *testing.T) {
	h := newHarness(t, true, true)
	if err := h.runBackblaze(); err != nil {
		t.Fatalf("backblaze: %v\n%s", err, h.out)
	}
	h.requirePushedVaultCommit("backblaze")
	h.out.Reset()
	if err := h.runCloudflare(); err != nil {
		t.Fatalf("cloudflare: %v\n%s", err, h.out)
	}
	h.requirePushedVaultCommit("cloudflare")
	// A rotation pushes the new key the same way.
	h.out.Reset()
	h.answers = []string{masterKeyID, masterKey}
	if err := runBackblaze(h.e, []string{"--replace-key", "pgbackrest_b2_write_key_id"}); err != nil {
		t.Fatalf("backblaze --replace-key: %v\n%s", err, h.out)
	}
	h.requirePushedVaultCommit("backblaze")
	// A rerun with every key saved commits nothing.
	h.out.Reset()
	before := h.git(h.e.directory, "rev-parse", "HEAD")
	if err := h.runBackblaze(); err != nil || h.git(h.e.directory, "rev-parse", "HEAD") != before || !strings.Contains(h.out.String(), "nothing was committed") {
		t.Fatalf("a rerun with nothing new committed: %v\n%s", err, h.out)
	}
}

func TestVaultRunsRefuseAnUnreadyRepositoryBeforeAnyAccountChange(t *testing.T) {
	h := newHarness(t, false, false)
	writeFile(t, filepath.Join(h.e.directory, "inventories/servers.yml"), "groups: {}\n# an edit not committed\n")
	h.answers = []string{masterKeyID, masterKey}
	if err := runBackblaze(h.e, nil); err == nil || !strings.Contains(err.Error(), "inventories/servers.yml") {
		t.Fatalf("want a refusal naming the changed file, got %v", err)
	}
	if len(h.answers) != 2 || len(h.b2.Buckets) != 0 {
		t.Fatalf("backblaze asked for the master key or made a bucket before refusing")
	}
	h.commitAll("An edit")
	h.git(h.e.directory, "commit", "--quiet", "--allow-empty", "-m", "Not pushed")
	if err := h.runCloudflare(); err == nil || !strings.Contains(err.Error(), "1 commits that are not pushed") {
		t.Fatalf("want a refusal of the unpushed commit, got %v", err)
	}
	if len(h.answers) != 1 || len(h.cloudflare.LiveTokensNamed("acme_systems: MMHotline uploads the MMHotline-down alarm")) != 0 {
		t.Fatalf("cloudflare asked for the link token or made a token before refusing")
	}
}

func TestAVaultChangeLeftUncommittedIsPushedByTheNextRun(t *testing.T) {
	h := newHarness(t, false, false)
	h.vault.failOn["pgbackrest_b2_write_application_key"] = true
	if err := h.runBackblaze(); err == nil {
		t.Fatal("want the failed save to stop the run")
	}
	delete(h.vault.failOn, "pgbackrest_b2_write_application_key")
	writeFile(t, h.vault.file, "vault\nchanged by an interrupted run\n")
	if err := h.runBackblaze(); err != nil {
		t.Fatalf("rerun: %v\n%s", err, h.out)
	}
	h.requirePushedVaultCommit("backblaze")
	if log := h.git(h.e.directory, "--git-dir", h.origin, "log", "--format=%s", "main"); !strings.Contains(log, "Save the vault changes left uncommitted") {
		t.Fatalf("the left-over vault change was not pushed:\n%s", log)
	}
}

// A run deletes a same-name key it finds at the provider as left over only
// once it has pulled the team's vault: a checkout behind origin can lack a
// key the servers' vault holds.
func TestALeftoverIsDeletedOnlyAfterTheTeamsVaultIsPulled(t *testing.T) {
	h := newHarness(t, false, false)
	h.b2.Failures["b2_create_key"] = "drop"
	if err := h.runBackblaze(); err == nil || !strings.Contains(err.Error(), "may have made the key") {
		t.Fatalf("want the lost-answer message, got %v", err)
	}
	delete(h.b2.Failures, "b2_create_key")
	pushFromAnotherCheckout(t, h.git, h.e.directory)
	if err := h.runBackblaze(); err != nil {
		t.Fatalf("rerun: %v\n%s", err, h.out)
	}
	if !strings.Contains(h.vault.fileWhenListed, "vault from another checkout") {
		t.Fatalf("the run listed the vault's keys before it pulled the team's vault: %q", h.vault.fileWhenListed)
	}
	keys := h.b2.LiveKeysNamed("acme-systems-pgbackrest-write")
	if len(keys) != 1 || h.vault.values["pgbackrest_b2_write_key_id"] != keys[0].ID || !strings.Contains(h.out.String(), "left over from an earlier run") {
		t.Fatalf("want the leftover deleted and exactly the saved key left, got %d keys", len(keys))
	}
	if log := h.git(h.e.directory, "--git-dir", h.origin, "log", "--format=%s", "main"); !strings.Contains(log, "Add keys elsewhere") {
		t.Fatalf("the push lost the teammate's vault commit:\n%s", log)
	}
}

func TestAFailedRevokeNamesTheKeyAndWhereToDeleteIt(t *testing.T) {
	h := newHarness(t, false, false)
	h.vault.failOn["pgbackrest_b2_write_application_key"] = true
	h.b2.Failures["b2_delete_key"] = "drop"
	err := h.runBackblaze()
	if err == nil || !strings.Contains(err.Error(), "revoking the new Backblaze key acme-systems-pgbackrest-write") ||
		!strings.Contains(err.Error(), "failed too") || !strings.Contains(err.Error(), "delete it by hand at "+b2KeysPage) {
		t.Fatalf("want the failed revoke reported with the key's name and the keys page, got %v", err)
	}

	h = newHarness(t, false, false)
	h.vault.failOn["mmhotline_down_alarm_cloudflare_api_token"] = true
	h.cloudflare.Lock()
	h.cloudflare.Failures["DELETE /accounts/"+testAccountID+"/tokens"] = "drop"
	h.cloudflare.Unlock()
	err = h.runCloudflare()
	if err == nil || !strings.Contains(err.Error(), `revoking the new Cloudflare token "acme_systems: MMHotline uploads the MMHotline-down alarm"`) ||
		!strings.Contains(err.Error(), "failed too") || !strings.Contains(err.Error(), "delete it by hand at https://dash.cloudflare.com/"+testAccountID+"/api-tokens") {
		t.Fatalf("want the failed revoke reported with the token's name and the tokens page, got %v", err)
	}
}

func TestTwoKeysWithOneNameAfterARotationAreNeverBothDeleted(t *testing.T) {
	h := newHarness(t, false, false)
	if err := h.runBackblaze(); err != nil {
		t.Fatal(err)
	}
	h.answers = []string{masterKeyID, masterKey}
	if err := runBackblaze(h.e, []string{"--replace-key", "pgbackrest_b2_write_key_id"}); err != nil {
		t.Fatal(err)
	}
	name := "acme-systems-pgbackrest-write"
	if len(h.b2.LiveKeysNamed(name)) != 2 {
		t.Fatal("a rotation leaves the old and the new key")
	}
	// The vault holds part of the pair, which may name either key.
	delete(h.vault.values, "pgbackrest_b2_write_application_key")
	if err := h.runBackblaze(); err != nil {
		t.Fatalf("rerun with part of the pair: %v", err)
	}
	if keys := h.b2.LiveKeysNamed(name); len(keys) != 3 || !strings.Contains(h.out.String(), "Kept 2 Backblaze keys") {
		t.Fatalf("both keys must stay beside the new one, got %d", len(keys))
	}
}
