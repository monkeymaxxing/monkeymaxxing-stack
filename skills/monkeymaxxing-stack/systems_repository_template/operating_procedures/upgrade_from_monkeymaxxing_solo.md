# Upgrade from Monkeymaxxing Solo

**When:** a team runs its app on Monkeymaxxing Solo's single server,
`solo01`, and moves the app onto the Stack.

**What this page does:** the Stack's servers are built beside `solo01`,
and `solo01` keeps serving customers until the switch. The app moves
first, while the app still uses `solo01`'s database over WireGuard. Then
[Move a database into the Stack](move_a_database_into_the_stack.md)
copies the data into `db01` and switches the database with a short write
pause. Last, `solo01` and Solo's leftover Cloudflare parts are removed.
The app's code does not change, because Solo and the Stack share one app
contract.

This example moves the app `shop`, at `shop.example.com`, from `solo01`
into a new systems repository, `acme_stack_systems`.

**Who acts:** you, the coding agent, read Solo's settings, build the
Stack, and prepare `solo01`. You run the copy and the switch, and change
the DNS record through the systems desk. You reach `solo01` from the laptop with
Solo's own SSH settings, as Solo's `AGENTS.md` says. Only a person:

- Announces the work in the team's chat, and agrees the maintenance window.
- Copies each app secret from Solo's vault into the Stack's vault, in the
  person's own terminal and desk login.
- Approves the switch of live traffic, the power-off of `solo01`, and each
  deletion at Cloudflare and at the server provider.

## Before you start

- **The Stack builds new servers beside `solo01`.** The servers are your
  systems desk `desk01`, `util01`, `app001`, and `db01`.
  [Add a second database server](add_a_second_database_server.md) adds
  `db02` when the team is ready for failover.
  `solo01` keeps serving customers until step 5 switches live traffic.
  No step changes a customer's data on `solo01`.
- **The app needs no rewrite.** Solo and the Stack share one app contract.
  The contract is the `Containerfile`, Postgres 17, and Cloudflare R2 for
  uploaded files. The contract also holds the `/health` URL, the `PORT` and
  `WEB_CONCURRENCY` settings, and separate migrate, web, and jobs commands.
  The app's repository, the tests at
  GitHub, the images at GitHub, the `DATABASE_URL` setting, and the R2
  uploads bucket all stay as they are.
- **One thing in the app needs a check before failover.** The Stack's
  `DATABASE_URL` lists every database server. When `db02` joins, the app's
  database driver must find the new primary after a failover. The skill's
  `files_for_your_app/database_driver_finds_the_primary.md` says how for
  each language. A Node.js app copies `pg_with_multiple_database_servers.mjs`
  into the app, as step 4 of
  [Prepare the Stack and move the app](move_a_database_into_the_stack.md#prepare-the-stack-and-move-the-app)
  says.
- **The Stack gets a new systems repository.** Keep Solo's systems
  repository unchanged until step 7. Name the Stack's repository so the
  name differs from Solo's, such as `acme_stack_systems` beside Solo's
  `acme_systems`. Reason: both repositories live under `~/code/` on the
  laptop, and the Stack names its Cloudflare tunnels after `project_name`.
- **Solo's MMX does not run from step 3 until `solo01` is retired.** Solo's
  MMX rewrites `solo01`'s WireGuard settings and firewall. So a Solo run
  removes step 3's temporary changes on `solo01`. A Solo
  release also waits, because a release runs on `solo01`. If a Solo run
  cannot wait, repeat step 3's WireGuard and firewall changes after the
  Solo run.
- **The Stack uses a different private network from Solo.** Solo's
  WireGuard network is `10.20.0.0/16`, and `solo01` is `10.20.1.1`. The
  Stack's default network is also `10.20.0.0/16`, where `app001` is
  `10.20.1.1`. So `solo01` could not reach `app001`. The Stack therefore
  uses `10.21.0.0/16` (step 2), and the moving database's address becomes
  `10.21.11.1`.

**What happens to each Cloudflare part.** The Stack uses the team's
Cloudflare account and domain, where Solo's setup already made five
parts. The table says what happens to each part, so live traffic never
breaks.

| Solo's Cloudflare part | What happens |
| --- | --- |
| The app's R2 uploads bucket, such as `acme-shop-uploads` | The Stack reuses the bucket. `production_uploads_r2_bucket` keeps the bucket's name, so no file is copied. The Stack's Cloudflare setup finds the bucket and leaves the bucket unchanged. The Stack's `uploads_backup` role then copies the bucket to Backblaze B2. |
| The proxied CNAME record of each public host name, pointing at `solo01`'s tunnel | The record stays on `solo01`'s tunnel while the Stack is built. Step 5 changes the record's target to the Stack's `acme_stack_systems-apps` tunnel. Customers see no change, because a proxied record always answers with Cloudflare's addresses. |
| `solo01`'s Cloudflare tunnel, named `solo01` | The tunnel serves customers until step 5. Step 7 deletes the tunnel after `solo01` is powered off. |
| Solo's outside alarm Worker, `solo-outside-alarm` | The Worker keeps watching `solo01` until step 7. Step 7 deletes the Worker before `solo01` stops, so the Worker sends no false alert. The Stack's MMHotline-down alarm replaces the Worker. |
| Solo's R2 backup bucket, named in Solo's `backups.bucket_name`, such as `acme-systems-backups` | The bucket stays unchanged until the Stack's B2 backups and weekly restore drill pass. The bucket also stays for Solo's `lock_backups_against_deletion_for_days` (14 by default) after `solo01` stops. Then the person can delete the bucket in step 7. |

## Steps

1. **Read what `solo01` runs today.** Read Solo's `mmx_project_settings.yml`
   and `inventories/servers.yml`. Write down, for each app under
   `vars.apps`: `image`, `database_name`, `health_url_path`,
   `asset_directory`, `migration_command`, `jobs_command`,
   `production_uploads_r2_bucket`, `env`, `secrets_from_vault`, and
   `restore_drill_check_queries`. From the inventory, write down
   `deployed_image_tags`, `public_host_names`, and `solo01`'s
   `public_ipv4_address`. Solo runs Postgres 17 from Debian 13, as Solo's
   `postgresql_major_version` says. Also write down Solo's
   `backups.bucket_name` and `backups.lock_backups_against_deletion_for_days`
   for step 7.
   **Check:** each app under Solo's `vars.apps` has a written entry, and
   `postgresql_major_version` is 17.

2. **Build the Stack beside `solo01`, through the setup's sixth chapter.**
   Follow the setup chapters 1 to 6 with the new systems repository.
   Stop before chapter 7 installs everything. Chapter 7's run starts the
   app, and the app's first start runs migrations. The copy in step 6
   refuses a Stack database that already holds app tables. So step 4 runs
   chapter 7 only after the Stack's settings point the app at `solo01`.

   Make these Solo-specific changes during the setup chapters:

   - **The private network.** Before the setup creates the systems desk,
     set `wireguard_network: 10.21.0.0/16` in the Stack's
     `inventories/servers.yml`. Change every `10.20.` value in the
     inventory (`private_ip_ranges`, `restore01_private_ip`, each server's
     `address`, `https_address`, `private_ip`, and
     `allowed_laptops[].private_ip`) and every literal `10.20.` in
     chapters 3 to 7's commands (such as the desk's `--wireguard-private-ip`,
     the laptop's `desk01.conf`, `~/.ssh/config`, and the bootstrap checks)
     to `10.21.`. For example, `app001` is `10.21.1.1`, `desk01` is
     `10.21.9.1`, and the moving database is `10.21.11.1`. The Stack's
     address table in `AGENTS.md` then reads `10.21.` for each `10.20.`.
   - **The app's settings.** Copy step 1's values into the Stack's
     `vars.apps`, `deployed_image_tags`, and `public_host_names`, keeping
     Stack-only keys such as `web_ports` (for example `[8001, 8002]`) and
     `production_uploads_r2_key_variables` while dropping Solo-only keys
     such as `web_port_a` and `web_port_b`. Use Solo's
     `deployed_image_tags`, so the Stack starts the version that customers
     use now. Keep `production_uploads_r2_bucket` as Solo's bucket name.
   - **The app's secrets.** Each value in Solo's `secrets_from_vault`
     must keep its value in the Stack. For example, a new
     `SECRET_KEY_BASE` signs every customer out, and a new encryption key
     makes encrypted rows unreadable. Copy each value **after chapter 3's
     desk start and before chapter 4 step 2 creates `~/example-setup/desk-ready`**
     (so `set-up-outside-services` finds them already in the vault and does
     not generate replacements). The person reads each value from Solo's
     vault in the person's own terminal, with
     `~/.local/bin/mmx secrets show KEY` in Solo's systems repository, and
     saves it into the Stack's vault as
     [Change the vault by hand](rotate_a_secret.md#change-the-vault-by-hand)
     says. Copy `shop_database_password` too, so the Stack's app and
     Solo's app both log in to `solo01`'s Postgres with one password.
     Leave out `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY`, because
     `set-up-outside-services cloudflare` makes the Stack's own R2 key for
     the bucket.
   - **The DNS record of each public host name.** In chapter 5's DNS step,
     create records only for the new host names, such as MMHotline's
     dashboard. Never create, change, or delete the record of an app's
     public host name in this step. The record keeps live traffic on
     `solo01`'s tunnel until step 5.
   - **The app's database driver.** Check the app's driver against
     `files_for_your_app/database_driver_finds_the_primary.md`, and record
     the result in the checklist item
     `<app>_database_driver_finds_the_primary`.

   **Check:** the checks of chapters 1 to 6 pass, the Stack's servers have
   `10.21.` addresses, and the app's DNS record still points at the tunnel
   `solo01`. The person confirmed that each app secret was copied from
   Solo's vault.

3. **Prepare `solo01` for the move.** Follow
   [Prepare the old server](move_a_database_into_the_stack.md#prepare-the-old-server)
   on `solo01`, with the Solo-specific changes below. `solo01` already
   runs Debian 13, Postgres 17, `wireguard-tools`, and `ufw`, and Solo
   created each database with the `C.UTF-8` collation that the Stack uses.
   Each change below stays on `solo01` until step 7 removes `solo01`.

   - **Step 1, the backup.** Solo's backups already run. Read the result
     of Solo's last weekly restore check on `solo01`. Run a full Solo
     backup first if the last full backup is older than one day.
   - **Step 3, the key.** Skip key generation: `wg0` already has Solo's
     private key. Read `wg show wg0 public-key` on `solo01` and record
     that public key as `database_moving_in.wireguard_public_key` in
     step 4's inventory block.
   - **Step 4, WireGuard.** `solo01`'s `wg0` already exists. Merge into
     `/etc/wireguard/wg0.conf`, keeping Solo's private key, address, and
     laptop peer. Add `10.21.11.1/16` to the `Address` line, so the line
     reads `Address = 10.20.1.1/16, 10.21.11.1/16`. Add the Stack peers
     with their `10.21.` addresses as `AllowedIPs`. Apply without dropping
     live connections: `ip address add 10.21.11.1/16 dev wg0` followed by
     `wg syncconf wg0 <(wg-quick strip wg0)` (or run
     `systemctl restart wg-quick@wg0` inside the maintenance window and
     reconnect).
   - **Step 5, the UDP 443 redirect.** Skip step 5's redirect. `solo01`
     already redirects UDP 443 to WireGuard's port 51820. Run step 5's
     check, `wg show wg0 allowed-ips`.
   - **Step 6, the firewall.** Solo already allows UDP 51820. Add only the
     three Postgres rules, with the `10.21.` ranges, such as
     `ufw allow in on wg0 from 10.21.1.0/24 to 10.21.11.1 port 5432 proto tcp`.
   - **Step 7, the Postgres settings.** Write the settings into a new
     file, `/etc/postgresql/17/main/conf.d/20-move-into-the-stack.conf`,
     because Solo's MMX owns `10-monkeymaxxing-solo.conf`. Postgres reads
     the later file last, so the new values win. Copy Solo's current
     `listen_addresses` value from `10-monkeymaxxing-solo.conf` and add
     `10.21.11.1`, for example `listen_addresses = '10.20.1.1,10.21.11.1'`.
     Put the `pg_hba.conf` lines above the `include_if_exists` line, with
     the `10.21.` ranges.
   - **Step 8, the restart.** Run `systemctl restart postgresql@17-main`
     in the agreed maintenance window. Customers see a few seconds of
     errors while Postgres restarts.
   - **Step 9, the roles.** Skip `\password shop`, because the Stack's
     vault already holds Solo's password from step 2. Solo's `postgres`
     login has no password, so the person sets one with `\password postgres`.

   **Check:** the checks of
   [Prepare the old server](move_a_database_into_the_stack.md#prepare-the-old-server)
   pass, and `https://shop.example.com/health` still answers through
   `solo01` after the restart.

4. **Start the app on the Stack against `solo01`'s database.** Follow
   [Prepare the Stack and move the app](move_a_database_into_the_stack.md#prepare-the-stack-and-move-the-app),
   steps 2 to 7, with the changes below. This page's step 2 replaces step 1
   of `Prepare the Stack and move the app`.

   - **Step 3, the inventory block.** Use `wireguard_address: 10.21.11.1`,
     `solo01`'s `public_ipv4_address`, and `through_relay: false`.
   - **Step 5, stop the old work.** On `solo01`, stop and disable each
     app's job service, such as `systemctl disable --now shop-jobs.service`.
     Keep `solo01`'s web containers serving customers until step 5 of this
     page. Two web fleets can share one database, but two job fleets can
     run one job twice.
   - **Step 6, the run.** Run chapter 7 (install everything on the
     production servers) as written. Chapter 7's run is the `every_server`
     run of step 6. The app's first start runs migrations against
     `solo01`'s database, where the migrations find nothing to do.
     The first restore drill on `db01` will fail until step 6 moves the
     app's tables into `db01`: leave `backups_restore_every_week` open
     with `waits_for: step 6 of upgrade_from_monkeymaxxing_solo.md`, and
     note that chapter 7 part 4's public URL check still routes through
     `solo01` until step 5.
   - **Step 7, the check.** Customers still reach `solo01`, so check the
     Stack's app on `app001` itself from the systems desk:
     `ssh desk01-agent 'cd systems_repository && ssh -F ssh/config root@10.21.1.1 "curl -fsS http://127.0.0.1:8001/health"'`.
   - **Phone alerts before switching traffic.** Run chapter 8 (both part 1,
     skipping part 1 step 2's restore-drill check until step 6, and part 2
     so MMHotline phone alerts are active and tested) and set
     `public_site_checks_run: true` before step 5 switches live traffic.
     That way `app001` is watched by the Stack's alerts from the first
     customer request.

   Then put `solo01`'s `job_containers` check group in Solo's MMWatchdog
   maintenance, with the reason "jobs moved to the Stack". Keep `solo01`'s Postgres,
   backup, and disk checks on, because `solo01` still holds the live data.
   **Check:** the checks of `Prepare the Stack and move the app` pass,
   the app on `app001` answers the app's health URL, and a test alert
   reaches the person's phone through MMHotline.

5. **Switch live traffic to `app001`.** Ask the person to approve the
   switch first. Customers then reach `app001`, and `app001`'s app writes
   to `solo01`'s database over WireGuard until step 6.

   1. Read the record of each public host name through the API proxy:
      `GET http://127.0.0.1:8082/zones/ZONE_ID/dns_records?name=shop.example.com`,
      and save its current `content` (`solo01`'s tunnel target) for
      rollback. Look up the Stack's apps tunnel ID via
      `GET http://127.0.0.1:8082/accounts/ACCOUNT_ID/cfd_tunnel?name=acme_stack_systems-apps&is_deleted=false`.
   2. Change only the record's target:
      `PATCH http://127.0.0.1:8082/zones/ZONE_ID/dns_records/RECORD_ID`
      with `{"content": "TUNNEL_ID.cfargotunnel.com", "proxied": true}`.
   3. Check the app from the laptop through Cloudflare:
      `curl -fsS https://shop.example.com/health`. Check that Cloudflare
      lists a healthy connector of the Stack's apps tunnel on `app001`, as
      chapter 9's step 1 says.
   4. Stop and disable each app's web service on `solo01`, such as
      `systemctl disable --now shop-web-8001.service`, and put
      `solo01`'s `tunnel_connector_and_caddy` check group in Solo's
      MMWatchdog maintenance. `solo01`'s tunnel then serves no host name.
   5. Continue the setup with chapter 9's verification checks (now
      reaching `app001` through the public host name), **leaving chapter 9
      step 3 (the first release and migrations) until after step 6 ends**.

   Never run Solo's `set-up-solo-services cloudflare` after step 5. The
   command points an existing CNAME record back at the tunnel `solo01`.
   Keep app releases waiting until step 6 ends, because the copy carries
   no schema change.

   **Check:** the public health URL answers through Cloudflare. Each
   app's DNS record targets the Stack's apps tunnel. A test sign-in and a
   test write through the app succeed.

6. **Move the database from `solo01` into `db01`.** Follow
   [Copy the database](move_a_database_into_the_stack.md#copy-the-database),
   then steps 1 to 6 of
   [Switch and verify](move_a_database_into_the_stack.md#switch-and-verify).
   Keep `solo01` powered on, because this page's step 7 replaces step 7 of
   `Switch and verify`.
   Step 3's changes on `solo01` stay until step 7 removes `solo01`. After
   `Switch and verify` step 5, no Stack server peers with `solo01`.

   Then verify the Stack's protections for the moved data:

   - A test write through the public host name lands in `db01`. Once
     `db02` exists, `db02` holds the write too.
   - A test alert reaches the person's phone through MMHotline.
   - The full backup of `Switch and verify` step 4 reached Backblaze B2.
   - The restore drill passes with the app's `restore_drill_check_queries`,
     as [Run the weekly database restore drill](run_the_weekly_database_restore_drill.md)
     says, and `backups_restore_every_week` is marked `done`.
   - Finish chapter 9 step 3 (the first Stack release) now that the
     database lives on `db01`.

   Record the move in `existing_database_moved_into_the_stack` in the
   checklist and in the Stack's `README.md`.
   **Check:** each item above passed, and `solo01`'s Postgres has no
   publication and no replication slot left.

7. **Retire `solo01` and Solo's Cloudflare parts.** Ask the person to
   approve each deletion first, because none of the deletions can be
   undone. Start only after step 6's checks passed and the Stack ran
   cleanly for the time the person chose, such as one week.

   1. **The outside alarm.** Check that the Stack's phone alerts passed
      their test in chapter 8. Then delete the Worker `solo-outside-alarm`
      at Cloudflare (Workers & Pages), and stop and disable
      `solo_outside_alarm_check_in.timer` on `solo01`. Delete the Worker
      first, so a missing check-in raises no false alert.
   2. **The power-off.** Put every check group of Solo's MMWatchdog in
      maintenance with a reason. Power off `solo01` at the provider. Repeat
      a customer write and read through the public host name.
   3. **The tunnel and the R2 keys.** Delete the tunnel `solo01` at
      Cloudflare (Networks, Tunnels). In the account API tokens, delete
      `solo-r2-backup` and each `solo-r2-<app>-uploads` key, such as
      `solo-r2-shop-uploads`. The Stack's app uses the Stack's own R2 key
      for the bucket since step 4.
   4. **The server.** After a safety wait the person chooses, such as
      seven days, delete `solo01` at the provider. Check a fresh provider
      listing.
   5. **Solo's backup bucket.** The bucket keeps each backup for Solo's
      `lock_backups_against_deletion_for_days`. Wait until that many days
      have passed since `solo01` stopped. Also wait until the Stack's B2
      backups and a weekly restore drill pass. Then, if the person
      confirms, remove the bucket's lock rules (`solo-backup-wal-lock` and
      `solo-backup-data-lock`) and delete the bucket at Cloudflare (R2).
   6. **The laptop and the Solo repository.** Keep Solo's systems
      repository as a private archive at GitHub. Delete
      `~/.config/doubleshell/solo01.conf` on the laptop when the person
      agrees.

   **Check:** customer writes and reads work with `solo01` powered off.
   Cloudflare lists no `solo-outside-alarm` Worker and no tunnel `solo01`.
   A fresh provider listing shows no `solo01`.

## If something is different

- **The copy refuses because the Stack database is not empty:** the app
  started on `db01` before the `database_moving_in` block existed. The
  Stack database holds the migrations' empty tables, never customer data.
  Tell the person, and drop and recreate the Stack database only with the
  person's approval.
- **Solo's MMX ran on `solo01` during the move:** the run removed step 3's
  WireGuard and firewall changes, and `app001` lost `solo01`'s database.
  Repeat step 3's WireGuard and firewall changes, then check
  `wg show wg0 allowed-ips` on `solo01`.
- **The public health URL fails after step 5's DNS change:** change the
  record's target back to `solo01`'s tunnel ID, and start `solo01`'s web
  services again. `solo01`'s database still holds every write, so nothing
  is lost.
- **The team already chose another network than `10.20.0.0/16` for Solo:**
  keep the Stack's default `10.20.0.0/16`, if the two networks do not
  overlap.
- **Solo runs several apps:** move every app on `solo01`'s Postgres
  together. List each app in the `apps` list of the `database_moving_in`
  block.

## Why it works this way

The order follows [Move a database into the Stack](move_a_database_into_the_stack.md).
The app moves first, so the database switch only redirects connections
that the Stack's app already holds. Live traffic switches between the two
moves, because Solo's app on `solo01` cannot follow the database to
`db01`. Solo's `DATABASE_URL` names `solo01` alone.

The Stack reuses the uploads bucket, because the Stack and Solo both keep
uploaded files in R2. A second bucket would need a copy of every file and
a second switch. The Stack's `uploads_backup` role adds the copy in
Backblaze B2 that Solo did not have.

Solo's backup bucket stays until the Stack's own backups have proved a
restore. Until then, Solo's last backups are the only tested copy of the
data from before the move.
