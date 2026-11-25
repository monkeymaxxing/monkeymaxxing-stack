# Add or remove a team member

**When to use this page:** a person joins or leaves the team.

**What this page does:** a joining person gets their own systems desk,
admitted to every server, to the systems repository, and to MMHotline. A
leaving person's desk, keys, tokens, and accounts are removed, and the
team replaces the vault passphrase and every secret the person could read.

**Who acts:** each step names who acts. Each person has their own coding
agent on their own laptop, which reaches only that person's desk. The
people give and remove accounts, type the commands this page gives them,
and send items from the recovery bundle straight to their desk, unseen. The coding
agents edit the systems repository, publish each change, and run
`every_server` on `util01`.

**The examples** add `blair`, with the desk `desk02` at `10.20.9.2` and
the laptop at `10.20.10.2`. An existing member, `alex`, works on `desk01`.

## Find your situation

| Situation | Follow |
| --- | --- |
| A person joins | [Joining](#joining) |
| A person leaves | [Leaving](#leaving), then [Replace the vault passphrase and secrets](#replace-the-vault-passphrase-and-secrets) |

## Before you start

- **Each person gets a separate systems desk,** `desk01`, `desk02`, and upward.
  Never share a desk login, production private key, or personal provider token.
  Reason: deleting a person's desk and revoking the person's access must leave colleagues' desks usable.
- The single-branch and synchronization rules in [Making a change](../AGENTS.md#making-a-change) apply to a solo person too.
- **A push alone changes no server.** Apply each configuration change as
  [Making a change](../AGENTS.md#making-a-change) says: run `every_server`
  or the playbook the step names.

## Adding or removing a person

### Joining

1. **Alex gives Blair the accounts.** The team's password manager, which
   holds the recovery passphrase; the Git host's organization; the server
   provider's project; and the Cloudflare account. Blair's Cloudflare
   Access sign-in must match the team's Allow policy.
   **Check:** Blair signs in to the password manager and the Git host.
2. **Blair's coding agent clones the backup at the Git host,** into
   `~/code/example_systems`, with Blair's own Git login, from
   `systems_repository.backup_url_at_the_git_host`. It is a starting copy
   only. First it shows Blair the Git host's push activity, as
   ["The main copy and the backup at the Git host"](../AGENTS.md#the-main-copy-and-the-backup-at-the-git-host)
   says.

   EVERY PUSH MUST BE A TEAM MEMBER'S OWN. ANY OTHER PUSH IS A BREAK-IN.

   Never copy a fresh template, start another repository, or make another
   vault: Blair joins the team's own.
   **Check:** every push came from a team member's laptop login, and the
   clone holds `inventories/servers.yml`.
3. **Blair's coding agent prepares the desk,** as
   [chapter 3 (make your server account and your systems desk)](../initial_setup/03_make_your_server_account_and_your_systems_desk.md)
   says, with `desk02` in place of `desk01` and `blair` in place of `alex`:
   - "The provider account", step 1: Blair makes their own key in the
     team's existing project, and types it into the laptop key command.
   - "Create desk01 through WireGuard", steps 1 to 3: Blair's laptop keys,
     the desk, and the laptop's way in, with the SSH entries `desk02`,
     `desk02-agent` and the others.

   In the clone, on a branch `add-desk02`, it adds `desk02` to `nodes` and
   `groups.systems_desks.nodes` in `inventories/servers.yml`:
   - the connection lines of `desk01` (`address: 127.0.0.1`, `ssh_user`,
     `connection`, `ssh_identity_file`, `ssh_known_hosts`) and
     `ssh_config: ssh/desk02`;
   - an unused address of `vars.private_ip_ranges.systems_desks`, such as
     `10.20.9.2`;
   - `person_unix_username: blair`, and Blair's laptop under
     `allowed_laptops`, with the next unused address of
     `vars.private_ip_ranges.systems_desk_laptops`, such as `10.20.10.2`.
     The same laptop address goes into the desk's first-boot peer and the
     laptop's `desk02.conf`.

   It copies `ssh/desk01` to `ssh/desk02` with `HostKeyAlias desk02`, adds
   the desk's host-key lines to `ssh/known_hosts`, and commits.
   Reason for one address per laptop across the team: each desk's login
   records then name one laptop.
   **Check:** the checks of chapter 3's steps, and `git show --stat HEAD`
   lists only `inventories/servers.yml`, `ssh/desk02` and `ssh/known_hosts`.
4. **Blair's coding agent copies the clone to the desk, with its history,
   and runs the bootstrap,** as
   [Rebuild a systems desk](rebuild_a_systems_desk.md)'s step 12 says,
   with `desk02`.
   **Check:** the run stops at `start_the_systems_repository`, saying that
   a desk that joins a team's repository gets the vault passphrase from
   the recovery bundle. That stop is expected.
5. **Blair gives the desk the team's vault passphrase,** with the
   vault passphrase lines of
   [Give a desk its keys from the recovery bundle](rebuild_a_systems_desk.md#give-a-desk-its-keys-from-the-recovery-bundle),
   on Blair's laptop and then on desk02.
   Skip the production key lines: a new desk keeps the key its bootstrap made.
   **Check:** the vault passphrase check of that section.
6. **Blair's coding agent runs the bootstrap again,** and moves the
   provider key to the desk, as chapter 3's step 4 says.
   **Check:** the run prints `The desk is ready.` and the desk's
   production public key.
7. **Blair's coding agent adds the production key to the branch.** It
   puts the printed key, with the comment `blair on desk02`, into
   `root_ssh_public_keys` in `mmx_project_settings.yml`, and into
   `desk02.vars.production_ssh_public_key`. It keeps every other key.
   It commits, and writes the branch to one file:
   `git format-patch --stdout main..add-desk02 > ~/add-desk02.patch`.
   Blair sends the file to Alex, in the team's usual chat.
   **Check:** the file holds only public keys and addresses.
8. **Alex's coding agent adds the new desk to `main`.** It applies the
   file on a branch in its own clone, `git am ~/add-desk02.patch`, shows
   Alex the change, publishes it, as
   [Making a change](../AGENTS.md#making-a-change) says, and runs
   `every_server` on `util01`. The run gives every server the new desk's
   WireGuard peer and lets its key in, `util01`'s main copy included.
   **Check:** the run passes.
9. **Blair's coding agent joins the team's `main`, on the new desk,** as
   [Rebuild a systems desk](rebuild_a_systems_desk.md)'s step 15 says, with
   `desk02`. The reset drops the desk's own branch: `main` now holds it.
   **Check:** `git log -1 --format=%s origin/main` on the desk shows Alex's
   commit that added `desk02`, and `git status` says `main` is up to date
   with `origin/main`.
10. **Blair makes their own Cloudflare key:**
    `ssh -t desk02 set-up-outside-services cloudflare`. The command
    prints a link. Blair makes the link token there and pastes it. The run
    makes Blair's desk token and status-page posting key, named after
    Blair, and leaves the servers' tokens as they are.
    **Check:** the run ends with "Deleted the link token at Cloudflare."
11. **Lock the desk.** Blair makes the phone code:
    `ssh -t desk02 'sudo -n set-up-the-phone-code --emergency-codes-to ~/phone-code-emergency-codes'`,
    and scans the QR code. Blair saves the five emergency codes in the
    team's password manager, as "desk02 phone code emergency codes", then
    deletes the file: `ssh desk02 rm phone-code-emergency-codes`, with a
    code from the phone. Then Blair's coding agent runs the lock stage
    and cleans the laptop, as chapter 4's step 8 says, and clones the
    desk's checkout, as chapter 4's step 1 says.
    **Check:** `ssh root@desk02 true` is refused, and
    `ssh desk02-agent true` works.
12. **Blair joins monitoring:** `ssh desk02-update` and a phone code.
    **Verify:** a fresh phone-code login; production SSH through
    `ssh desk02-agent`; the provider list script through the API proxy;
    `desk02` in the MMWatchdog fleet; and every production server has the
    desk's peer and no laptop peer.
13. **Every other member runs a desk update:** `ssh desk01-update` on
    their laptop, with their own desk name, and a phone code.
    **Check:** their coding agent names the change it applies: the new
    desk's SSH settings file, `ssh/desk02`, and its key in
    `root_ssh_public_keys` (they can pass `--review` to
    `review-and-apply-the-systems-desk-settings` to inspect the diff first).
    Reason: each desk's lock-out button uses the SSH settings files of
    that desk's last desk review. Until then it refuses with
    "nodes.desk02.ssh_config in the inventory is ssh/desk02, which is not
    one of the SSH settings files of your last desk review … Nothing
    changed.".
14. **Add Blair to MMHotline.** A coding agent adds Blair to `people` in
    `mmhotline_settings.yml` with `role: member` and Blair's Access sign-in
    email, and to `on_call_schedule.rotation_sign_in_email_addresses`
    when Blair joins on-call. It publishes, and runs `every_server` on
    `util01`. Blair signs in to MMHotline and adds personal contact
    methods.
    **Warn Blair first:** the test rings like an alarm. It is an
    emergency-priority Pushover message that repeats every 30 seconds, for
    up to 10 minutes, until Blair acknowledges it on the phone. It is only
    a test; nothing is wrong.
    Blair's own R2 key for [status posting](post_to_the_status_page.md)
    came with step 10.
    **Check:** the run passes, and the contact method's test reaches
    Blair's phone.

### Leaving

1. **Remove the departing person's password-manager, Cloudflare Access, and Git-host access.**
   First hand over, in MMHotline's dashboard, any incident the person has claimed and any on-call shift the person has taken,
   because MMHotline refuses removal while those duties remain.
   Then remove the person from MMHotline's `people` and on-call rotation.
   **Check:** the departing person no longer appears at the Git host or in MMHotline's `people`.
2. **Remove the departing desk from the repository.** Remove the departing desk's production public key from `root_ssh_public_keys`.
   Remove the departing desk from `nodes` and `groups.systems_desks.nodes` and remove the departing desk's `ssh/deskNN` and known-host entry.
   A remaining member's coding agent publishes the change, as [Making a change](../AGENTS.md#making-a-change) says,
   and runs `every_server` on every production and staging server.
   Then each remaining member types `ssh desk01-update`, with their own desk name, and a phone code, so their
   lock-out button no longer knows the departing desk.
   Reason: `root_ssh_public_keys` also decides who can push to the team's main copy on `util01`, so the run on
   `util01` takes the departing desk's push rights too. A copy of the desk's production key can outlive the desk.
   **Check:** verify the departing desk's WireGuard peer and SSH public key are absent on every server, `util01` included.
3. **Delete the departing person's desk and tokens.** Delete the departing person's desk by verified provider ID.
   Revoke the departing person's provider credential.
   A remaining member deletes the departing person's Cloudflare tokens, the desk token and the status-page posting key,
   by their names, with the departing person's `vars.person_unix_username`, such as `sam`:
   `ssh -t desk01 set-up-outside-services cloudflare --delete-tokens-of-person sam`, and a phone code.
   The command asks for a link token, as in step 10 of joining, lists each token it deletes, and changes nothing else.
   Deleting a desk alone does not revoke a copied provider or Cloudflare token.
   **Check:** confirm the desk's absence with a fresh provider listing, and
   the command lists each of the departing person's tokens as deleted.

### Replace the vault passphrase and secrets

After a person leaves, replace the vault passphrase and secrets. The
departing person knew the recovery passphrase, so the recovery bundle gets
a new passphrase too.

1. **A new vault passphrase,** on Alex's desk. Alex types `ssh desk01` and
   a phone code, then runs this block. It works on copies in a folder of
   Alex's own. Nobody sees the new vault passphrase:

   ```sh
   # On the desk, as the person:
   work=$(mktemp -d) && cd "$work"
   cp /home/coding-agent/systems_repository/secrets_vault.age /home/coding-agent/systems_repository/recovery_bundle.age .
   sudo install -o "$USER" -m 0600 /etc/systems-desk/vault-passphrase "$work/old-vault-passphrase"
   (umask 077 && openssl rand -base64 32 > "$work/vault-passphrase")
   MMX_VAULT_PASSWORD_FILE="$work/old-vault-passphrase" mmx secrets passwd --vault secrets_vault.age --new-vault-password-file "$work/vault-passphrase"
   MMX_VAULT_PASSWORD_FILE="$work/vault-passphrase" mmx secrets set --vault secrets_vault.age --replace mmx_vault_passphrase < "$work/vault-passphrase"
   ```

   **Check:** the block prints no error.
2. **The recovery bundle gets the new vault passphrase and a new recovery
   passphrase.** The departing person knew the old recovery passphrase.
   Alex first saves a new six-word passphrase in the team's password
   manager, in place of the old one. Then, in the same folder:

   ```sh
   # On the desk, as the person. Type the old recovery passphrase, then press Enter. It does not show.
   # When the bundle refuses it as typed, a run of spaces counts as one, so a copy saved with two spaces between words still opens the bundle.
   read -rs MMX_VAULT_PASSWORD && export MMX_VAULT_PASSWORD
   mmx secrets list-keys --vault recovery_bundle.age >/dev/null 2>&1 || export MMX_VAULT_PASSWORD=$(printf '%s' "$MMX_VAULT_PASSWORD" | tr -s ' ')
   # Each line runs only when the one before it worked, so nothing is installed
   # unless the bundle took the new vault passphrase and the new recovery passphrase.
   # The new recovery passphrase is typed at the second hidden prompt.
   mmx secrets list-keys --vault recovery_bundle.age >/dev/null &&
     mmx secrets set --vault recovery_bundle.age --replace mmx_vault_passphrase < "$work/vault-passphrase" &&
     (umask 077 && read -rs new_passphrase && printf '%s\n' "$new_passphrase" | tr -s ' ' > "$work/new-recovery-passphrase") &&
     mmx secrets passwd --vault recovery_bundle.age --new-vault-password-file "$work/new-recovery-passphrase" &&
     sudo install -o coding-agent -g coding-agent -m 0644 secrets_vault.age recovery_bundle.age /home/coding-agent/systems_repository/ &&
     sudo cp "$work/vault-passphrase" /etc/systems-desk/vault-passphrase &&
     echo "Installed the new vault and recovery bundle."
   # (cp onto the existing file keeps its owner, root:servers-mmx, and its mode, 0640.)
   unset MMX_VAULT_PASSWORD
   ```

   **Check:** the block ends with "Installed the new vault and recovery
   bundle." When it does not, nothing was installed and the desk still
   uses the old vault: keep the folder (`$work`), fix what the error names
   (most often the old recovery passphrase), and run this block again.
   When it does, `cd && rm -r "$work"`, and after step 3's publish
   [Read an item from the recovery bundle](rebuild_a_systems_desk.md#read-an-item-from-the-recovery-bundle)
   opens the bundle with the new recovery passphrase.

   When nobody has the old recovery passphrase, run only the block's
   `sudo install`, `sudo cp` and `cd` lines, without `recovery_bundle.age`
   in the `install` line. Publish only the vault in step 3, and after
   step 3 follow
   [Make a new recovery passphrase](make_a_new_recovery_passphrase.md):
   its new bundle takes the new vault passphrase from the desk.
3. **Publish both files, then give `util01` the new passphrase.** Alex's
   coding agent commits `secrets_vault.age` and `recovery_bundle.age` in
   the desk's checkout, publishes them, as
   [Making a change](../AGENTS.md#making-a-change) says, and runs
   `ssh desk01-agent sudo -n -u servers-mmx run-mmx-on-the-servers run every_server --connection ssh_only --limit util_server`.
   Finish this run before any run on `util01`.
   **Check:** the run passes.

   Reason: a push changes no server. The desk opens the new vault, while
   `util01` still holds the old passphrase until this run.
4. **Every other desk gets the new vault passphrase.** Each remaining
   member runs the vault passphrase lines of
   [Give a desk its keys from the recovery bundle](rebuild_a_systems_desk.md#give-a-desk-its-keys-from-the-recovery-bundle),
   on their own laptop and then their own desk, with their own desk's name.
   **Check:** the vault passphrase check of that section, on each desk.
5. **Replace every secret the departing person could read.** For every secret the departing person could read, follow
   [Rotating a secret](rotate_a_secret.md#rotating-a-secret).
   Replace the secrets in the vault, including the shared root
   console password's hash and MMHotline's secrets, using each
   secret's section.
   Also replace the MMHotline-down alarm's check-in token.
   MMHotline makes the MMHotline-down alarm's check-in token and keeps the token in
   MMHotline's own database.
   Setting up the MMHotline-down alarm again creates a new token.
   [The MMHotline-down alarm check-in token](rotate_a_secret.md#the-mmhotline-down-alarm-check-in-token)
   explains how to set up the MMHotline-down alarm again.
   Replace every Cloudflare key the servers use, and with `staging01` staging's Access service token,
   which every desk's token file holds, with `ssh -t desk01 set-up-outside-services cloudflare --replace-every-key`,
   as [Cloudflare keys](rotate_a_secret.md#cloudflare-keys) says.
   **Check:** the checks of each secret's section.
6. **Remove the departing person's remaining access.** Revoke the departing person's own API token in the server provider
   account; Leaving step 3 deleted the departing person's Cloudflare tokens.
   The departing person's API tokens live only on the departing person's
   systems desk.
   Remove the departing person from the Cloudflare account.
   Remove what admits the departing person through Cloudflare Access's
   Allow policy: the company email account, or the membership of the
   company's GitHub organization.
   **Check:** the provider account and the Cloudflare account no longer
   list the departing person or the person's token.

## If something is different

- **The bootstrap does not stop in joining step 4, but starts a new
  repository:** the copy had no `.git`. Stop. Delete the new desk at the
  provider, and start again at joining step 3's desk creation.
- **`git am` stops on a conflict in joining step 8:** `main` changed the
  same lines. Alex's coding agent tells Alex, and makes the same change
  by hand on a new branch from `main`.
- **A desk's lock-out button refuses** with "nodes.desk02.ssh_config in the
  inventory is ssh/desk02, which is not one of the SSH settings files of
  your last desk review … Nothing changed.": that desk has not run joining
  step 13's desk review yet.
- **MMHotline refuses to remove a person:** the person still has a claimed
  incident or an on-call shift. Hand those over first, as leaving step 1 says.
