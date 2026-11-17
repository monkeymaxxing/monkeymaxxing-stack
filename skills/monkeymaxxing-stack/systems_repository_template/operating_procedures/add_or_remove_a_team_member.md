# Add or remove a team member

**When to use this page:** a person joins or leaves the team.

**What this page does:** a joining person gets their own systems desk,
admitted to every server, to the systems repository, and to MMHotline. A
leaving person's desk, keys, tokens, and accounts are removed, and the
team replaces the vault passphrase and every secret the person could read.

**Who acts:** each step names who acts. The people give and remove
accounts, run the commands in their own desk terminals, administer the Git
host, and handle the vault passphrase. Each desk's coding agent edits the
repository, commits, pushes, and runs `every_server` on `util01`. Commands
that source the person's token file,
`~/.config/monkeymaxxing-stack/example_systems.env`, run only in the
person's own desk terminal, as the secrets rule in
[The rules](../AGENTS.md#the-rules) says.

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

1. **Give the new person the required account and password-manager access,** the Git host's included.
   The new person's Cloudflare Access sign-in must match the team's Allow policy.
   **Check:** the new person signs in to the password manager and the Git host.
2. **The new person makes the laptop and the desk.** The new person joins the company's existing systems
   repository and vault: never copy a fresh template, create another Git repository, or create another vault.
   The new person's laptop coding agent clones the team's systems repository into `~/code/example_systems`,
   with the new person's own Git host access, and follows
   [chapter 3 (make your server account and your systems desk)](../initial_setup/03_make_your_server_account_and_your_systems_desk.md)'s
   "Create desk01 through WireGuard" in that clone, with the next desk name, such as `desk02`, in place of `desk01`.
   In the clone it adds `desk02` to `nodes` and `groups.systems_desks.nodes` in `inventories/servers.yml`, with the
   connection lines of `desk01` (`address: 127.0.0.1`, `ssh_user`, `connection`, `ssh_identity_file`,
   `ssh_known_hosts`) and `ssh_config: ssh/desk02`, an unused `vars.private_ip_ranges.systems_desks` address, such as
   `10.20.9.2`, the person's Unix account under `vars.person_unix_username`, and the person's laptop keys under
   `vars.allowed_laptops`. The laptop takes the next address in `vars.private_ip_ranges.systems_desk_laptops` not used
   by any desk, such as `10.20.10.2`, in the desk's first-boot peer and the laptop's `desk02.conf` too.
   Reason: one address per laptop across the team makes each desk's login records name one laptop.
   It copies `ssh/desk01` to `ssh/desk02` with `HostKeyAlias desk02`. Then the new person bootstraps the desk and
   enrolls the phone code, as chapter 3's steps 3 to 5 say. The bootstrap's temporary edits stay in the laptop's
   own copy and are cleared there, as chapter 3 says.
   **Check:** the checks of chapter 3's steps 3 to 5.
3. **The new person sends the new desk's public values.** In the new person's own desk terminal:

   ```sh
   cd ~/example_systems
   git diff; git diff --no-index /dev/null ssh/desk02
   cat /etc/systems-desk/production_key.pub
   ```

   The new person sends the output to an existing member, in the team's usual chat.
   **Check:** the output holds only public keys and
   addresses: the desk's inventory entry, `ssh/desk02`, the desk's lines in `ssh/known_hosts`, and the production
   public key that the bootstrap made.
4. **An existing member adds the new desk, first.** On the existing member's desk, that desk's coding agent adds the
   new desk's changes from the message, then puts the new desk's production public key into `root_ssh_public_keys`
   in `mmx_project_settings.yml` and into the desk's `vars.production_ssh_public_key` in `inventories/servers.yml`,
   with the comment `blair on desk02`, the new person's account and desk. It keeps every existing member's key and
   `util01`'s. It commits, synchronizes, pushes, and runs `every_server` on `util01`, which gives every server the
   new desk's WireGuard peer and lets its key in. Then it tells the existing member the pushed commit's full ID, and
   the existing member gives that ID to the new person.
   **Check:** the `every_server` run passes, and the new person has the pushed commit's full ID.
   Reason: the new desk takes the team's `main` as root in its first desk review, and checks first that main lists
   the desk and that its newest commit is signed by a desk; the commit ID from a colleague is what the new person
   compares it with.
5. **The new person finishes the repository on the new desk.** The new desk reaches the team's main copy on `util01`
   as root with its production key, which step 4's run let in; no key goes to the Git host. In the new person's own
   desk terminal:

   ```sh
   cd ~/example_systems
   set-up-the-systems-repository --author-name "Blair Example" --author-email blair@example.com
   ```

   The command sees that the team's repository has commits, so it joins it, as
   [chapter 3's "Finish the systems repository on the desk"](../initial_setup/03_make_your_server_account_and_your_systems_desk.md#create-desk01-through-wireguard)
   describes: it checks main and names its newest commit and signer. The command keeps the bootstrap copy's
   edits in `git stash`, asks for the team's vault passphrase, which the new person pastes from the password manager,
   runs the first desk review, and makes the coding agent's checkout.
   **Check:** the new person compares the newest commit the command names with the
   ID from step 4, and stops at the desk review's question if they differ.
6. **Tokens, monitoring and checks.** The new person brings the provider token to the desk, as chapter 3's "Bring
   the provider token to the desk" says, and makes their own Cloudflare tokens in their own desk terminal, in the
   systems repository: `. ~/.config/monkeymaxxing-stack/example_systems.env && set-up-outside-services cloudflare`.
   The command prints a link; the new person, a member of the Cloudflare account since step 1, makes the link token
   there and pastes it. The run makes the new person's desk token and status-page posting key, named after the new
   person, writes them into the API proxy and the token file, deletes the link token, and leaves the servers'
   tokens unchanged.
   To join monitoring, the person runs the full desk playbook in the person's repository on the new desk:
   `review-and-apply-the-systems-desk-settings`.
   The command takes the desk's name, such as `desk02`, from the desk's host name, which the desk role set at bootstrap.
   The person starts the coding agent with `start-the-coding-agent`.
   **Check:** verify a fresh phone-code login, a signed commit and push from the person's repository, production SSH, and
   provider API access from `coding-agent`. For the signed commit, `git log --show-signature -1` in the person's
   repository prints `Good "git" signature for blair_on_desk02`.
   Verify production servers have the desk peer and have no laptop peer.
7. **Every other desk runs a desk review.** Each existing member runs, in their own desk terminal, in their systems
   repository: `review-and-apply-the-systems-desk-settings`.
   **Check:** their coding agent tells them the change it shows: the
   new desk's SSH settings file, `ssh/desk02`, and its key in `root_ssh_public_keys`.
   Reason: each desk's lock-out button uses the SSH settings files of that desk's last desk review, and until then
   it refuses with "nodes.desk02.ssh_config in the inventory is ssh/desk02, which is not one of the SSH settings
   files of your last desk review … Nothing changed."; the same desk review lets that desk's Git verify the new
   desk's signed commits.
8. **Add the person to MMHotline.** Add the person to `people` in `mmhotline_settings.yml` with `role: member` and the person's Access sign-in email.
   Add the email to `on_call_schedule.rotation_sign_in_email_addresses` when the person joins on-call.
   Commit, synchronize, push, and run `every_server` on `util01`.
   The person signs into MMHotline and adds personal contact methods.
   **Warn the person first:** the test rings like an alarm. It is an emergency-priority Pushover message that repeats every 30 seconds, for up to 10 minutes, until the person acknowledges it on the phone. It is only a test; nothing is wrong. Tell the person this before the person saves a contact method.
   The person's own R2 key for [status posting](post_to_the_status_page.md) came with step 6.
   **Check:** the run passes, and the contact method's test reaches the person's phone.

### Leaving

1. **Remove the departing person's password-manager, Cloudflare Access, and Git-host access.**
   First hand over, in MMHotline's dashboard, any incident the person has claimed and any on-call shift the person has taken,
   because MMHotline refuses removal while those duties remain.
   Then remove the person from MMHotline's `people` and on-call rotation.
   **Check:** the departing person no longer appears at the Git host or in MMHotline's `people`.
2. **Remove the departing desk from the repository.** Remove the departing desk's production public key from `root_ssh_public_keys`.
   Remove the departing desk from `nodes` and `groups.systems_desks.nodes` and remove the departing desk's `ssh/deskNN` and known-host entry.
   A remaining member commits, synchronizes, pushes, and runs `every_server` on every production and staging server.
   Then each remaining member runs `review-and-apply-the-systems-desk-settings` in their own desk terminal, so their
   lock-out button and their Git no longer know the departing desk's key.
   Reason: `root_ssh_public_keys` also decides who can push to the team's main copy on `util01`, so the run on
   `util01` takes the departing desk's push rights too. A copy of the desk's production key can outlive the desk.
   **Check:** verify the departing desk's WireGuard peer and SSH public key are absent on every server, `util01` included.
3. **Delete the departing person's desk and tokens.** Delete the departing person's desk by verified provider ID.
   Revoke the departing person's provider and coding-agent credentials.
   A remaining member deletes the departing person's Cloudflare tokens, the desk token and the status-page posting key,
   by their names, in the remaining member's own desk terminal, with the departing person's `vars.person_unix_username`, such as `sam`:
   `. ~/.config/monkeymaxxing-stack/example_systems.env && set-up-outside-services cloudflare --delete-tokens-of-person sam`.
   The command asks for a link token, as in step 6 of joining, lists each token it deletes, and changes nothing else.
   Deleting a desk alone does not revoke a copied provider or Cloudflare token.
   **Check:** confirm the desk's absence with a fresh provider listing, and
   the command lists each of the departing person's tokens as deleted.

### Replace the vault passphrase and secrets

After a person leaves, replace the vault passphrase and secrets:

1. **A new passphrase.** On a remaining team member's systems desk, generate the
   new passphrase as during setup, without displaying the passphrase.
   Encrypt the vault again with the new passphrase.
   On the systems desk used for the passphrase change, replace the passphrase
   file named by `MMX_VAULT_PASSWORD_FILE`.
   Also replace the vault key `mmx_vault_passphrase`, which `util01` reads:

   ```sh
   # This systems desk, in the systems repository:
   . ~/.config/monkeymaxxing-stack/example_systems.env &&
     (umask 077 && openssl rand -base64 32 > "$MMX_VAULT_PASSWORD_FILE.new") &&
     mmx secrets passwd --new-vault-password-file "$MMX_VAULT_PASSWORD_FILE.new" &&
     mv "$MMX_VAULT_PASSWORD_FILE.new" "$MMX_VAULT_PASSWORD_FILE" &&
     cat "$MMX_VAULT_PASSWORD_FILE" | mmx secrets set mmx_vault_passphrase --replace
   ```

   The team member replacing the passphrase reads the file named by
   `MMX_VAULT_PASSWORD_FILE` with `cat` in a personal terminal.
   The team member replacing the passphrase copies the new passphrase
   into the password manager.
   Each remaining team member copies the new passphrase from the password
   manager into the person's protected desk passphrase file.
   Each person then runs `review-and-apply-the-systems-desk-settings --only-fleet-stages systems_desk`, which installs the new passphrase as `/etc/systems-desk/vault-passphrase`, root:servers-mmx, mode `0640`.
   Update the initiating desk's button passphrase before using `run-mmx-on-the-servers` for the next run.
   **Check:** each person's desk review passes.
2. **Commit and push the changed vault,** then run
   `sudo -n -u servers-mmx run-mmx-on-the-servers run every_server --connection ssh_only --limit util_server` from
   the systems desk. The systems desk supplies the new passphrase to `util01`.
   Complete the run from the systems desk before starting a utility-server run.
   **Check:** the run passes.

   Reason: pushing changes no server. The systems desk can open the new vault
   while `util01` still holds the old passphrase.
3. **Replace every secret the departing person could read.** For every secret the departing person could read, follow
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
   which every desk's token file holds, with `set-up-outside-services cloudflare --replace-every-key`,
   as [Cloudflare keys](rotate_a_secret.md#cloudflare-keys) says.
   **Check:** the checks of each secret's section.
4. **Remove the departing person's remaining access.** Revoke the departing person's own API token in the server provider
   account; leaving step 3 deleted the departing person's Cloudflare tokens.
   The departing person's API tokens live only on the departing person's
   systems desk.
   Remove the departing person from the Cloudflare account.
   Remove what admits the departing person through Cloudflare Access's
   Allow policy: the company email account, or the membership of the
   company's GitHub organization.
   **Check:** the provider account and the Cloudflare account no longer
   list the departing person or the person's token.

## If something is different

- **The commit that `set-up-the-systems-repository` names differs from the
  ID from joining step 4:** the new person stops at the desk review's
  question and tells the team.
- **A desk's lock-out button refuses** with "nodes.desk02.ssh_config in the
  inventory is ssh/desk02, which is not one of the SSH settings files of
  your last desk review … Nothing changed.": that desk has not run joining
  step 7's desk review yet.
- **MMHotline refuses to remove a person:** the person still has a claimed
  incident or an on-call shift. Hand those over first, as leaving step 1 says.
