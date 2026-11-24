# Rotate a secret

**When to use this page:** someone leaves, a secret leaks, or the rotation period is due. The period is `verify_again_every` of the checklist item `secret_rotation` (12 months in the template).

**What this page does:** a new secret replaces the old one in the vault or
at the company that issued it, the servers get the new secret, and the old
secret stops working.

**Who acts:** the person issues new secrets at outside companies, and
types each `set-up-outside-services` command this page gives, on the
laptop, with a phone code, because only the person handles secret values.
The command saves the secret, and commits and pushes the vault itself. The
coding agent, on the laptop, gives the person each command, publishes any
other file, runs `every_server` on `util01`, and checks the result.

## Find your situation

Follow [Rotating a secret](#rotating-a-secret) for the order, checks, and exceptions.
Then choose the section for the secret you need to replace.

| The secret | Its name | Follow |
| --- | --- | --- |
| The shared root console password | `shared_root_console_password_hash` | [The shared root console password](#the-shared-root-console-password) |
| An app secret | Such as `shop_STRIPE_API_KEY` or `shop_SECRET_KEY_BASE` | [App secrets](#app-secrets) |
| An app's database password | Such as `shop_database_password` | [App database passwords](#app-database-passwords) |
| The failover monitor password | `pg_auto_failover_autoctl_node_password` | [The failover monitor password](#the-failover-monitor-password) |
| The replication password | `pg_auto_failover_replication_password` | [The replication password](#the-replication-password) |
| A Cloudflare key: a tunnel's token, an app's R2 key, `util01`'s R2 key, the MMHotline-down alarm's token, the status page's R2 key, a person's desk token or posting key, or staging's Access service token | The table in [Cloudflare keys](#cloudflare-keys) | [Cloudflare keys](#cloudflare-keys) |
| The container registry token | `container_registry_read_only_token` | [The container registry token](#the-container-registry-token) |
| A Backblaze B2 key | Such as `pgbackrest_b2_write_key_id` | [Backblaze B2 keys](#backblaze-b2-keys) |
| The push app's keys | `pushover_application_token`, `mmwatchdog_pushover_user_or_group_key` | [Pushover keys](#pushover-keys) |
| The provider API token of `util01` | `util01_provider_api_token` | [The provider API token](#the-provider-api-token) |
| The triage agent's credential | `mmhotline_triage_agent_credential` | [The triage agent credential](#the-triage-agent-credential) |
| The MMHotline-down alarm's check-in token | Not in the vault | [The MMHotline-down alarm check-in token](#the-mmhotline-down-alarm-check-in-token) |
| The fleet hub's signing secret | `mmhotline_signing_secret_of_the_fleet_hub` | [The fleet hub signing secret](#the-fleet-hub-signing-secret) |
| The backup encryption passphrase | `pgbackrest_repository_cipher_passphrase` | Never replace it: see [Before you start](#before-you-start) |
| The vault's own passphrase | | [Adding or removing a person](add_or_remove_a_team_member.md#adding-or-removing-a-person) |
| A person's own token or key on a desk | | [Personal desk credentials](#personal-desk-credentials) |

## Before you start

**Two exceptions:**

- Never replace `pgbackrest_repository_cipher_passphrase` with the usual
  issue, vault, commit, push, verify, and revoke steps below.
  `pgbackrest_repository_cipher_passphrase` encrypts every backup in the
  production B2 bucket, named by `vars.backups.production_bucket` in
  `mmx_project_settings.yml`. A new passphrase could not read any existing
  backup.
  If `pgbackrest_repository_cipher_passphrase` may have leaked, rotate the
  B2 keys. The passphrase cannot read backups without the B2 keys.
- Change the vault's own passphrase as
  [Replace the vault passphrase and secrets](add_or_remove_a_team_member.md#replace-the-vault-passphrase-and-secrets)
  says.

**A push alone changes no server.** Apply each configuration change as
[Making a change](../AGENTS.md#making-a-change)
says: a push alone changes no server, so run `every_server` or the playbook the step names.

## Rotating a secret

Find the secret's section below. The usual order is:

1. **Issue the new secret and set it in the vault.** The person types,
   on the laptop, with the key's name, and a phone code:

   ```sh
   ssh -t desk01 set-up-outside-services secrets --replace KEY
   ```

   For a key a website gives, the command shows where to make it and asks
   for it at a hidden prompt. A random key, such as a database password,
   it makes itself, and nobody sees it. Then it commits and pushes the
   vault. You give the person the command.
   **Check:** the command ends without an error.
2. **Publish any other file the section changes,** as
   [Making a change](../AGENTS.md#making-a-change) says.
   **Check:** `git pull --ff-only` in your clone brings the vault commit.
3. **Run `every_server` on `util01`** and read `./server_management_scripts/run_mmx_on_util01 results` for the result.
   **Check:** the run passes.
4. **Verify the new secret works, then revoke the old one.**
   **Check:** the section's "Verify and revoke" check.

`util01` rewrites files that hold the secret. Each secret's section below
describes which services restart or read the rewritten files.
App containers restart one app server at a time.
Only an app's database password needs the additional `end_connections_that_use_an_old_database_password` playbook.
Some secrets need two commits or revoke the old secret earlier. Follow
the exceptions in the section for the secret you are replacing.

## The shared root console password

`shared_root_console_password_hash` holds the shared root console password's hash.
The team's password manager keeps the password as the item `Shared root console password`, and the recovery bundle keeps the one that lock-the-desk or make-a-new-recovery-bundle made.

1. **Check for a running `restore01`** before rotating the password, with
   `./server_management_scripts/list_the_servers_at_the_provider`.
   A restore drill or a
   [row recovery](recover_rows_lost_to_a_bad_change.md#restore-a-database-copy-and-recover-the-missing-rows)
   run creates `restore01` and destroys it before the run ends: wait for
   the run to end. A `restore01` left after a run ended is a leftover:
   destroy it as the row-recovery page's "If something is different" says.
   **Check:** the provider lists no `restore01`.

   Reason: `every_server` skips `database_restore_servers`, so a surviving
   restore server would retain the old shared root console password.
2. **The person makes the new password,** on the laptop, with a phone
   code:

   ```sh
   ssh -t desk01 set-up-outside-services secrets --replace shared_root_console_password_hash
   ```

   The command makes a new password for every server and shows it once.
   The person saves it in the password manager as
   `Shared root console password`, then types it back at a hidden prompt.
   The command saves only the new hash, then commits and pushes the vault.
   The recovery bundle keeps the first password, which no longer works:
   the password manager's entry is the current one.
   **Check:** the command ends after its push.
3. **Run `every_server` on `util01`.**
   MMX's `user` module sets root's `password_hash` with
   `apply_password_hash: on_every_run` on every ordinary server. If
   `restore01` remains, destroy it as step 1 says. SSH continues to
   refuse password authentication.
   **Check:** the run passes.
4. **Log in as root at one server's provider console with the new password.**
   **Check:** the login works, and the old password fails. Save the
   successful console test in the checklist item
   `provider_console_and_backup_mmhotline_logins`, retaining the item's MMHotline
   verification too.

Reason: the provider console remains available when WireGuard or SSH is
broken. Groups of letters are practical to type at a console. Updating every
server's hash revokes the old shared root console password without opening SSH passwords.
Rotate the password when a person leaves, after a leak, and when `secret_rotation`'s `verify_again_every` period passes.

## App secrets

An app secret, such as `shop_STRIPE_API_KEY`.

1. **Create the new secret.** Issue a new secret at the company that issued
   the old secret, such as Stripe for `shop_STRIPE_API_KEY`, and set it in
   the vault as [Rotating a secret](#rotating-a-secret) says.
   For an app secret the setup made, such as `shop_SECRET_KEY_BASE`, the
   same command makes a new random one.
   **Check:** the command pushed `secrets_vault.age`.
2. **Run `every_server` on `util01`.** The app's containers restart with the rewritten
   secrets file, such as `/etc/shop/shop.env` for `shop`.
   **Check:** the run passes.
3. **Verify and revoke.**
   **Check:** the app uses the new secret, for example
   with a test payment.
   Then revoke the old secret at the vendor.

## App database passwords

An app's database password, such as `shop_database_password` (staging's: `staging_shop_database_password`).

1. **Create the new secret:** `ssh -t desk01 set-up-outside-services secrets --replace shop_database_password`.
   It makes letters and digits only, so the password needs no escaping in
   `DATABASE_URL`.
   **Check:** the command pushed `secrets_vault.age`.
2. **Run `every_server` on `util01`.** The primary receives the new database password first.
   Then the app's containers restart with the new database password.
   Existing connections stay open meanwhile.
   **Check:** the run passes. The `every_server` run checks that each live web container's health URL
   answers, which fails when the app cannot reach its database. Job
   containers have no health check.
3. **Verify and revoke.** `./server_management_scripts/run_mmx_on_util01 run end_connections_that_use_an_old_database_password --var environment_name=production --var database_name=shop` ends existing connections opened with the old password.
   **Check:** the run passes.
   The old password cannot open new connections after `every_server` changes
   the primary's password. But existing connections stay open until
   `end_connections_that_use_an_old_database_password` ends the connections opened with the old password.

## The failover monitor password

`pg_auto_failover_autoctl_node_password`: the password for the failover monitor's login `autoctl_node`.
Each database server's pg_autoctl process, called its keeper, uses the
monitor's `autoctl_node` login to report to the monitor.

1. **Create the new secret:** `ssh -t desk01 set-up-outside-services secrets --replace pg_auto_failover_autoctl_node_password`.
   **Check:** the command pushed `secrets_vault.age`.
2. **Run `every_server` on `util01`.** Nothing restarts.
   The run changes the monitor's login on `util01` first.
   Then the `every_server` run writes each database server's password file,
   `~postgres/.pgpass`, one server at a time.
   Until its turn, a keeper cannot report to the monitor.
   The monitor causes no failover meanwhile, because it can still reach Postgres on each server itself.
   A primary whose replica still copies from it keeps serving.
   **Check:** the run passes.
3. **Verify and revoke.** After the run passes, on `util01`, run
   `sudo -u postgres psql -XAt -d pg_auto_failover -c "select nodename, round(extract(epoch from now() - reporttime)) from pgautofailover.node where formationid = 'production'"`.
   **Check:** it shows each database server, with only a few seconds since its keeper last reported.
   Nothing needs revoking.
   The login has one password, so the old one stopped working during the run.

## The replication password

`pg_auto_failover_replication_password`: the password for login `pgautofailover_replicator`, used by replicas to copy from the primary.

1. **Create the new secret:** `ssh -t desk01 set-up-outside-services secrets --replace pg_auto_failover_replication_password`.
   **Check:** the command pushed `secrets_vault.age`.
2. **Run `every_server` on `util01`.** Nothing restarts.
   The `every_server` run writes the new replication password into each
   database server's password file, one server at a time.
   The `every_server` run also sets the password for the primary's
   `pgautofailover_replicator` login.
   A replica already copying data keeps its connection.
   **Check:** the run passes.
3. **Verify and revoke.** After the run passes, check from each replica, such as `db02`.
   The primary is the database server that
   `sudo -u postgres pg_autoctl show state --pgdata /var/lib/postgresql/17/pg_auto_failover_monitor --formation production`
   on `util01` lists as `primary`.
   This example uses `db01`'s private address: `ssh -F ssh/config root@10.20.2.2 "sudo -u postgres psql -XAt 'host=10.20.2.1 dbname=postgres user=pgautofailover_replicator' -c 'select 1'"`.
   **Check:** a login to the primary using the replica's password file prints `1`.
   Nothing needs revoking.
   As above, changing the login's password invalidates the old one.

## Cloudflare keys

One command replaces each Cloudflare key. It makes a new key with the
old key's permissions and saves it where the old key was. A key the
servers use keeps its old key working while the servers' run brings them
the new one; the command deletes the old key at Cloudflare when the person
presses Enter after that run. [Backblaze B2 keys](#backblaze-b2-keys)
work the same way.

| Key | `--replace-key` name | The new key goes to |
| --- | --- | --- |
| A tunnel's token | `apps_cloudflare_tunnel_token`, `util01_cloudflare_tunnel_token`, with `staging01` `staging_apps_cloudflare_tunnel_token` | The vault. The tunnel gets a new secret, so the old token opens no new connection |
| An app's R2 key | The app's name and its access key ID variable, such as `shop_R2_ACCESS_KEY_ID`; with `staging01` also `staging_shop_R2_ACCESS_KEY_ID` | The vault, as both of the app's R2 secrets |
| `util01`'s R2 key for the uploads' copy | `uploads_r2_read_only_access_key_id` | The vault |
| The MMHotline-down alarm's token | `mmhotline_down_alarm_cloudflare_api_token` | The vault |
| The status page's R2 key | `mmhotline_status_page_r2_access_key_id` | The vault |
| The person's desk token | `CLOUDFLARE_API_TOKEN` | The API proxy and the person's token file |
| The person's key for posting to the status page | `MMHOTLINE_STATUS_PAGE_R2_ACCESS_KEY_ID` | The person's token file |
| With `staging01`, staging's Access service token | `STAGING_ACCESS_CLIENT_SECRET` | The person's token file. The service token keeps its ID and gets a new secret, so the staging pages' Service Auth policies stay as they are |

**Before you start:** replace a tunnel's token while all of the tunnel's
servers run, and run `every_server` right after the command (see
[Why the waiting](#why-the-waiting)).

1. **Create the new secret.** The person types, on the laptop, with the
   name of each key to replace from the table above, and a phone code:

   ```sh
   ssh -t desk01 set-up-outside-services cloudflare --replace-key shop_R2_ACCESS_KEY_ID
   ```

   `--replace-key` can be given several times. `--replace-every-key`
   replaces every key in the table. The command asks for a link token, made
   from the link it prints, as in
   [chapter 4 (set up your accounts and lock your systems desk)](../initial_setup/04_set_up_your_accounts_and_lock_your_desk.md).
   It commits and pushes the vault itself. Then it lists the old
   keys, prints the run's command, and waits in the person's terminal. The
   old keys keep working while it waits. After a break-in,
   [Respond to a break-in](respond_to_a_break_in.md) adds
   `--delete-the-old-keys-at-once` instead, and the command does not wait.
   **Check:** the command lists the old keys and prints the run's command.
2. **The run, while the command waits.** Every key in the vault reaches the
   servers only with a run. While the person's command waits, the coding
   agent runs the command the person's terminal printed, in its desk
   checkout through `ssh desk01-agent`:

   ```sh
   ./server_management_scripts/run_mmx_on_util01 run every_server
   ```

   During a lock-out, the coding agent runs instead
   `sudo -n -u servers-mmx run-mmx-on-the-servers run every_server --connection ssh_only`.
   The run rewrites each file that holds a replaced key:

   - A tunnel's token: `cloudflared` restarts with the new token from
     `/etc/cloudflared/tunnel_token.env` on each server of the tunnel.
   - An app's R2 key: the app's containers restart with the rewritten
     secrets file, such as `/etc/shop/shop.env` for `shop`.
   - `util01`'s R2 key: the next uploads' copy reads the rewritten
     `/var/lib/mmhotline/uploads_backup_rclone.conf` on `util01`.
   - The MMHotline-down alarm's token and the status page's R2 key:
     `util01`'s run applies them with `mmhotline settings apply`, which
     uploads the MMHotline-down alarm's Worker and waits for an accepted
     check-in, and publishes the status page with the new key.

   The person's desk token and posting key need no run: a new desk login
   loads the token file again. For staging's service token, each other team
   member enters the new secret from the password manager with
   `ssh -t desk02 set-up-outside-services personal-token staging-access`,
   with their own desk name; when CI tests against staging, replace CI's
   two secrets too.
   **Check:** the run passes, or, for a key no server holds, the person has
   opened a new desk login.
3. **Verify, then press Enter.**
   **Check,** for each replaced key:

   - A tunnel's token: the public host names answer, and Cloudflare lists
     each connector again.
   - An app's R2 key: an upload in the app works, and its file shows in the
     app's bucket.
   - `util01`'s R2 key: the next uploads' copy passes, in
     `journalctl -u copy_uploads_to_the_backup_bucket` on `util01`.
   - The MMHotline-down alarm's token: on `util01`, `sudo mmhotline settings show`
     shows the `mmhotline_down_alarm` part applied, and
     `sudo mmhotline down-alarm send-test` reaches a phone.
   - The status page's R2 key: on `util01`, `sudo mmhotline settings show`
     shows the `status_page` part applied.
   - The person's desk token: a Cloudflare read through
     `http://127.0.0.1:8082/` succeeds from `coding-agent`.
   - The person's posting key: in the person's own desk terminal,
     `. ~/.config/monkeymaxxing-stack/example_systems.env && mmhotline status-page show`
     lists the page's notices.
   - Staging's service token: the check of
     [A release](deploy_and_roll_back_an_app_release.md#a-release), step 2,
     prints `200` with the new values.

   After the run and the checks of the keys the servers use, the person
   presses Enter in the waiting terminal. The command deletes the old keys
   at Cloudflare, then the link token. A check that waits for a later job,
   such as the next uploads' copy, need not keep the terminal open: Ctrl-C
   leaves the old keys working, and the next run of
   `set-up-outside-services cloudflare`, with a new link token, lists them
   again and deletes them at Enter.

### Why the waiting

Reason for waiting: a routine replacement must not stop the apps'
uploads or the status page for the minutes until the run ends. The person's
desk token, posting key, and staging's service token need no wait, because
no server holds them: the command writes each new one before it deletes
the old one, or, for staging's service token, Cloudflare's renewal
replaces the secret in one step.

A tunnel has one secret, so a tunnel's old token stops working when the
command gives the tunnel its new secret: there is no waiting for a
tunnel. Whether the running `cloudflared` connectors stay connected until
the run restarts them is not yet proved; Cloudflare's website says its own
"Refresh token" keeps them up. A connector that restarts before the run
cannot connect, so run `every_server` right after the command, and replace
a tunnel's token while all of the tunnel's servers run.

## The container registry token

`container_registry_read_only_token`.

1. **Create the new secret.** Create a read-only token for the account named
   by `vars.container_registry_read_only_username` in
   `mmx_project_settings.yml`, and set it in the vault as
   [Rotating a secret](#rotating-a-secret) says.
   The token must read each app's image named by `vars.apps.<app>.image` in
   `mmx_project_settings.yml`.
   **Check:** the command pushed `secrets_vault.age`.
2. **Run `every_server` on `util01`.** Nothing restarts.
   Each image pull logs in.
   **Check:** the run passes.
3. **Verify and revoke.**
   **Check:** the next deploy passes. Revoke the old token after the next deploy passes.

## Backblaze B2 keys

A B2 application key has two vault entries. Replace the pair for the key
you are rotating:

- Database write key: `pgbackrest_b2_write_key_id` and
  `pgbackrest_b2_write_application_key`.
- Database read-only key: `pgbackrest_b2_read_only_key_id` and
  `pgbackrest_b2_read_only_application_key`.
- MMHotline's backup key: `mmhotline_backup_access_key_id` and
  `mmhotline_backup_secret_access_key`.
- Uploads backup key: `uploads_backup_b2_write_key_id` and
  `uploads_backup_b2_write_application_key`.

1. **Create the new secret.** The person types, on the laptop, with the
   key ID's vault name of the pair being rotated, and a phone code:

   ```sh
   ssh -t desk01 set-up-outside-services backblaze --replace-key pgbackrest_b2_write_key_id
   ```

   The command takes the master key at hidden prompts, makes a new key with
   the old key's bucket and capabilities, and saves it over the old pair with
   `--replace`, without printing it. It commits and pushes the vault itself.
   Then it waits, as for [Cloudflare keys](#cloudflare-keys): the
   old key keeps working at Backblaze while the coding agent runs
   `./server_management_scripts/run_mmx_on_util01 run every_server`, and the
   command deletes the old key when the person presses Enter after the
   checks below. After a break-in, `--delete-the-old-keys-at-once` deletes
   it without waiting.
   **Check:** the command waits in the person's terminal.
2. **Run `every_server` on `util01`,** with
   `./server_management_scripts/run_mmx_on_util01 run every_server`.
   pgBackRest reads the rewritten
   `/etc/pgbackrest/pgbackrest.conf` at the next pgBackRest command.
   MMHotline's backup restarts with the rewritten `/etc/mmhotline/backup.env`
   on `util01`.
   The uploads copy reads the rewritten
   `/var/lib/mmhotline/uploads_backup_rclone.conf` on `util01` on the next
   night.
   **Check:** the run passes.
3. **Verify and revoke.** Check the result for the key you changed.
   **Check:**

   - Database write key: the next daily backup passes, as recorded in the
     primary's journal for `pgbackrest_full_backup` or
     `pgbackrest_differential_backup`.
   - Database read-only key: the next drill passes, as recorded in
     `util01`'s journal for `weekly_database_restore_drill`. See
     [the drill's result](run_the_weekly_database_restore_drill.md#restoring-the-database).
   - MMHotline's key: `sudo mmhotline backup check-uploads` on `util01` exits 0.
   - Uploads key: the next uploads' copy passes, as shown in `journalctl -u copy_uploads_to_the_backup_bucket` on `util01`.

   Then press Enter in the waiting terminal, and the command deletes the old
   key. Most of these checks wait for a later job, so the person usually
   presses Ctrl-C first, which leaves the old key working, and runs
   `set-up-outside-services backblaze` again after the check passed: the run
   lists the old key and deletes it at Enter.

## Pushover keys

The push app's keys: `pushover_application_token` and `mmwatchdog_pushover_user_or_group_key` in the vault.
MMWatchdog's fleet hub on `util01` gives `pushover_application_token` and
`mmwatchdog_pushover_user_or_group_key` to the hub-outage alerters.
The hub-outage alerters use the Pushover keys to send the alert that `util01`
went silent.
MMHotline uses `pushover_application_token` for everyone's alerts
(`sending_services.pushover` in `mmhotline_settings.yml`).

1. **Create the new secret.** Create an application, or a group, in
   Pushover, and set the keys in the vault as
   [Rotating a secret](#rotating-a-secret) says.
   **Check:** the command pushed `secrets_vault.age`.
2. **Run `every_server` on `util01`.** The fleet hub restarts with the new keys. `util01`'s run applies MMHotline's sending service with `mmhotline settings apply`.
   `mmhotline settings apply` checks the new application token with Pushover
   first.
   If Pushover refuses the new application token, MMHotline keeps the old
   application token.
   MMHotline keeps every Pushover contact method, because a person's user
   key works with any Pushover application.
   **Check:** the run passes. When it fails because a Pushover emergency
   message is still open, see the paragraph after step 3.
3. **Verify and revoke.**
   **Check:** `sudo mmwatchdog send-notice --alert-severity info --title "Test of the push app. Nothing is wrong." --destination on_call_push_app` on `util01` must reach a phone.
   A contact method's test, `sudo mmhotline contact-methods send-test --contact-method-id ID`, must arrive from the new application.
   **Warn the person first:** the test rings like an alarm. It is an emergency-priority Pushover message that repeats every 30 seconds, for up to 10 minutes, until the person acknowledges it on the phone. It is only a test; nothing is wrong.
   Also check that `sudo mmhotline down-alarm send-test` reaches a phone.
   Then delete the old application in Pushover: MMHotline cannot revoke the
   old application token in Pushover.
   Until deletion, anyone with the old application token can send alerts
   under the old application's identity.

**If a Pushover emergency is open:** while a Pushover emergency repeats on someone's phone, MMHotline needs the old token to check and cancel it.
MMHotline therefore keeps the old token, and `util01`'s run fails because
a Pushover emergency message is still open.
Once the message is acknowledged, cancelled, or expired, explicitly rerun
`every_server` to apply the new token.
Expiry takes at most 25 minutes after the message began.

The MMHotline-down alarm holds alerts ready to send if MMHotline stops checking in.
At the next check-in, MMHotline replaces the application token in the
MMHotline-down alarm's held alerts with the new application token.

## The provider API token

`util01_provider_api_token`.

1. **Create the new secret.** Create a token in the provider's project,
   and set it in the vault as [Rotating a secret](#rotating-a-secret) says.
   **Check:** the command pushed `secrets_vault.age`.
2. **Run `every_server` on `util01`.** The restore drill's jobs read the new provider API
   token at the next start of each job.
   **Check:** the run passes.
3. **Verify and revoke.**
   **Check:** on `util01`,
   `journalctl -u check_for_a_leftover_restore01` must show the next run
   passed.
   Then delete the old token.

## The triage agent credential

The triage agent's credential, `mmhotline_triage_agent_credential` in the vault: an API key, a Claude Code subscription token, a Codex access token, or a ChatGPT sign-in's `auth.json`, which `mmhotline_settings.yml` reads as `triage_agent.credential`.

MMHotline warns 30 and 7 days before a subscription token or Codex access
token expires, and when the agent cannot sign in.

1. **Create the new secret.** Create an API key at the triage agent's AI
   provider, or use `claude setup-token` for a Claude Code subscription
   token.
   The person runs `claude setup-token` in their own terminal on the
   laptop, signed in to the subscription account used for the triage
   agent.

   - **Renew a Codex access token** before its end date: the person creates a
     new token on the workspace's Access tokens page and picks a new end date,
     up to 90 days away. Both change in one commit: the new token in the vault,
     and the new `triage_agent.credential_expires_on` (`"YYYY-MM-DD"`, not a
     secret) in `mmhotline_settings.yml`.
   - **Replace a ChatGPT sign-in** when MMHotline says it stopped working, or
     when a person who knew it leaves. The person signs in again on the
     laptop, in a new empty folder used only for MMHotline, with a ChatGPT
     account that has no connected apps (`export CODEX_HOME="$(mktemp -d)"`,
     `codex login`). The person copies the new `auth.json` to the desk with
     `scp "$CODEX_HOME/auth.json" desk01:` and a phone code, and saves it with
     `ssh -t desk01 set-up-outside-services secrets --replace mmhotline_triage_agent_credential`,
     which reads the file without showing it. Then the person deletes both
     copies, `rm -r "$CODEX_HOME"` and `ssh desk01 rm auth.json`, and never
     runs `codex logout` on the folder, which would end MMHotline's sign-in
     too.

   **Check:** the person has the new credential.
2. **Store the new triage agent credential in the vault** with
   `ssh -t desk01 set-up-outside-services secrets --replace mmhotline_triage_agent_credential`,
   at its hidden prompt (a sign-in, as above).
   If switching credential types, change `triage_agent.credential_type` in
   `mmhotline_settings.yml` in the commit that replaces the vault credential.
   Use `api_key` for an API key, `subscription_token` for a Claude Code
   subscription token, or for Codex `access_token` (with
   `credential_expires_on`) or `chatgpt_sign_in`.
   **Check:** the command pushed `secrets_vault.age`. Publish any change to
   `mmhotline_settings.yml` right after it, before the run.
3. **Run `every_server` on `util01`.** `util01`'s run applies the new triage agent credential
   with `mmhotline settings apply`.
   MMHotline first tests the credential with a prompt in the triage agent's
   sandbox, the restricted environment where MMHotline runs the agent.
   A failed test keeps the old credential and fails the run.
   While a triage session's run is active, MMHotline refuses the credential
   change, so `util01`'s run fails. Once the active session ends, explicitly
   rerun `every_server` to apply the new credential.
   **Check:** the run passes.
4. **Verify and revoke.**
   **Check:** on `util01`,
   `sudo mmhotline triage-agent check-sign-in` must pass.
   Then revoke the old key, or the old token in the Claude account.

## The MMHotline-down alarm check-in token

MMHotline also makes a check-in token and stores it in its own database,
as program data that MMHotline's backup keeps, not in the vault.
The MMHotline-down alarm check-in token proves that a check-in comes from MMHotline.
To replace the MMHotline-down alarm check-in token, set up the MMHotline-down alarm again in two
commits:

1. **Remove the `mmhotline_down_alarm` section** from `mmhotline_settings.yml`. Commit and push.
   MMHotline tells the Worker to hold no alerts and removes the setup.
   Until the MMHotline-down alarm setup is back, the MMHotline-down alarm cannot wake the person on
   call when MMHotline stops checking in.
   **Check:** none until step 2's run applies the change.
2. **Run `every_server` on `util01` and require success.** Restore the section
   in a second commit, push, and run `every_server` again.
   Applying the second commit creates a new MMHotline-down alarm check-in token.
   **Check:** both runs pass.
3. **Verify.**
   **Check:** on `util01`, `sudo mmhotline settings show` shows the
   `mmhotline_down_alarm` part applied, and `sudo mmhotline down-alarm send-test` reaches a
   phone.

## The fleet hub signing secret

The fleet hub signs its alerts and check-ins with `mmhotline_signing_secret_of_the_fleet_hub` in the vault.
`util01`'s run writes `mmhotline_signing_secret_of_the_fleet_hub` into the
hub's `/etc/mmwatchdog/secrets/mmhotline-signing-secret`.
The alert source `mmwatchdog_fleet_hub` in `mmhotline_settings.yml` lists
`mmhotline_signing_secret_of_the_fleet_hub` in `signing_secrets`.

**Use two commits.** MMHotline must accept the old and new signing
secrets while the second commit changes the hub's signing secret.

1. **Add the new secret beside the old one.** The person makes the new secret in a root-only file on the desk,
   and pipes it into a second key, so it never appears in output, as
   [Change the vault by hand](#change-the-vault-by-hand) says, with
   `sudo sh -c 'umask 077 && openssl rand -hex 32 > /root/next-fleet-hub-signing-secret'` and
   `sudo cat /root/next-fleet-hub-signing-secret | mmx secrets set --vault secrets_vault.age mmhotline_next_signing_secret_of_the_fleet_hub`.
   You add the vault template expression after the first entry in
   `signing_secrets` for `mmwatchdog_fleet_hub` in `mmhotline_settings.yml`:
   `"{{ .secrets.mmhotline_next_signing_secret_of_the_fleet_hub }}"`.
   Publish the vault and the settings, as
   [Making a change](../AGENTS.md#making-a-change) says, and run `every_server` on `util01`. MMHotline accepts the
   old and new signing secrets while the hub still signs with the old signing secret.
   **Check:** wait for `util01`'s run to pass.
2. **Make the new secret the only one.** The person sets it as the main key from the same file, as
   [Change the vault by hand](#change-the-vault-by-hand) says, with
   `sudo cat /root/next-fleet-hub-signing-secret | mmx secrets set --vault secrets_vault.age --replace mmhotline_signing_secret_of_the_fleet_hub`,
   then deletes the file: `sudo rm /root/next-fleet-hub-signing-secret`.
   The temporary key, `mmhotline_next_signing_secret_of_the_fleet_hub`, stays in the vault unused: MMX has no
   command that removes one key, and the next rotation replaces it with `--replace`.
   You remove the second entry from `signing_secrets`. Publish both files, and
   run `every_server` on `util01`.
   The second run restarts the hub with the new secret in its `util_server` stage.
   Then, in `every_server`'s final settings stage,
   `apply_the_mmhotline_settings`, MMHotline applies the source with only
   the new signing secret.
   [Startup order](change_mmhotline_settings.md#startup-order) explains how the settings
   stage follows the earlier `mmhotline` stage.
   Until MMHotline applies the source with only the new signing secret,
   MMHotline accepts the old and new signing secrets, so no alert is refused.
   **Check:** the run passes.
3. **Verify and revoke.**
   **Check:**

   - `ssh -F ssh/config root@10.20.0.1 'mmhotline alert-sources list'` must
     list one signing secret for `mmwatchdog_fleet_hub`.
   - On `util01`, send a test from the hub:
     `sudo mmwatchdog send-notice --alert-severity info --title "Test of the alerts. Nothing is wrong." --destination mmhotline_on_call`.
     The test alert must arrive.

   The old secret stopped working during the second run.
   Nothing needs revoking.

## Personal desk credentials

Production secrets stay in the vault and continue using the rotation sections above.
Personal tokens stay on the person's own desk, outside Git and outside `coding-agent`'s home.
The person types each personal-token command on the laptop, with a phone code.

- Provider token: issue the replacement at the provider.
  The person saves it with `ssh -t desk01 set-up-outside-services personal-token server-provider --server-listing-path PATH`
  (the provider guide's listing).
  The command checks the new token first, then updates the root-owned
  `/etc/systems-desk/provider-api-token.conf`,
  restarts the API proxy, and checks a request through it. A new token that fails a check
  changes nothing. Then revoke the old token.
  **Check:** the command's own check of a request through the API proxy passes.
- Cloudflare desk token and status-page posting key:
  `ssh -t desk01 set-up-outside-services cloudflare --replace-key CLOUDFLARE_API_TOKEN --replace-key MMHOTLINE_STATUS_PAGE_R2_ACCESS_KEY_ID`,
  as [Cloudflare keys](#cloudflare-keys) says. The command writes the new desk token into
  `/etc/systems-desk/cloudflare-api-token.conf` the same way, and deletes the old tokens at Cloudflare.
  **Check:** the checks of the person's desk token and posting key in
  [Cloudflare keys](#cloudflare-keys).
- Vault passphrase: follow
  [Replace the vault passphrase and secrets](add_or_remove_a_team_member.md#replace-the-vault-passphrase-and-secrets).
  It writes the new passphrase into each desk's `/etc/systems-desk/vault-passphrase` and into the recovery bundle,
  and gives `util01` the new passphrase with one run from the desk.
- Production SSH key: generate the replacement on the desk, add the new public key beside the old public key
  in `root_ssh_public_keys`, and register the new public key at the provider. The run that applies
  `root_ssh_public_keys` also lets the new key push to the main copy on `util01`.
  Update the desk's inventory `vars.production_ssh_public_key` to the replacement public key.
  During containment, first load both keys into the person's private SSH agent, because locked servers admit only the mapped key.
  Apply `every_server` before removing the old public key. Restart the desk's SSH agent to load the replacement.
  Verify production login and a push to the main copy, then save the new private key in the recovery bundle as
  `production_ssh_private_key`, as
  [Change an item in the recovery bundle](rebuild_a_systems_desk.md#change-an-item-in-the-recovery-bundle) says,
  with the file `~/.ssh/production_key`, without its `rm`. Then revoke the old public key everywhere.
- Laptop desk-login key: follow [Lost or stolen laptop](recover_from_a_lost_or_stolen_laptop.md) when compromise is possible.
- Phone-code secret: follow [Lost phone](recover_from_a_lost_phone.md).

Reason: a person's departure revokes personal access without changing production's account-owned tokens.

## Change the vault by hand

Most vault changes go through `set-up-outside-services`. A few steps
change a key it does not make, such as the fleet hub's second signing
secret. The person does those in their own desk login, `ssh desk01` and a
phone code, on a copy of the vault in a folder of their own:

```sh
# On the desk, as the person:
work=$(mktemp -d) && cd "$work"
cp /home/coding-agent/systems_repository/secrets_vault.age .
sudo install -o "$USER" -m 0600 /etc/systems-desk/vault-passphrase "$work/vault-passphrase"
export MMX_VAULT_PASSWORD_FILE="$work/vault-passphrase"
```

Then the step's own `mmx secrets` command, with `--vault secrets_vault.age`,
such as `mmx secrets set --vault secrets_vault.age KEY`. Then put the copy
back, and clean up:

```sh
# On the desk, as the person:
sudo install -o coding-agent -g coding-agent -m 0644 secrets_vault.age /home/coding-agent/systems_repository/secrets_vault.age
cd && rm -r "$work" && unset MMX_VAULT_PASSWORD_FILE
```

Then you commit `secrets_vault.age` in the desk's checkout and publish
it, as [Making a change](../AGENTS.md#making-a-change) says.

Reason for a copy: MMX never runs as root on the pulled repository on a
desk, so the person's own MMX opens only the vault file, outside the
checkout.

**Check:** the publishing step names the commit, and
`ssh desk01-agent sudo -n -u servers-mmx run-mmx-on-the-servers secrets list-keys`
lists the key.
