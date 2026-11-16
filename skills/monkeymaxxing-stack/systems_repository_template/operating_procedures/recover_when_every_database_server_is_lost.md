# Recover when every database server is lost

**When to use this page:** no usable database server remains. The
procedure **Recover when every database server is lost** also applies
when the system's only database server is lost, and when the whole
location or provider is lost. The page also brings the whole database
back to a chosen minute after damage.

**What this page does:** the database recovery uses `restore_database --var restore_mode=recovery`
on a new database server, which restores the backups. After the restore,
the new database server joins as the primary
([Every database server is lost](#every-database-server-is-lost)).

**Who acts:** database servers always need a person
([The rules](../AGENTS.md#the-rules), "What the triage agent may do
without a person"). The person approves the new server's price. The coding
agent does every step from the systems desk.

**How often:** rare.

## Find your situation

| What happened | Follow |
| --- | --- |
| Every server is gone: the MMHotline-down alarm wakes the person on call with "MMHotline is not checking in" | [The location or provider is lost](#the-location-or-provider-is-lost) |
| Every database server, or the only database server, is lost | [Every database server is lost](#every-database-server-is-lost) |
| A bad change, a bad release, or a break-in damaged much of the database, and the person chooses to go back to a minute before the damage | [Bring the whole database back to a chosen minute](#bring-the-whole-database-back-to-a-chosen-minute) |
| Only a few rows are wrong | [Recover rows lost to a bad change](recover_rows_lost_to_a_bad_change.md) |
| The database primary fails and a healthy replica remains | [Replace a server](replace_a_server.md#the-database-primary-dies) |

Follow the applicable section, including the preparation before the
restore. The steps after each push stay inside each section.

## Before you start

- **For a lost database: first, establish that no usable database server
  remains.**
- **For a lost database: tell the person before work:**

  > No working database server remains, so the site is down.
  > I will restore the backups onto a new server, then reconnect the app.
  > Recovery is complete only after the data checks and the public-site test pass.

  [Restoring the database](run_the_weekly_database_restore_drill.md#restoring-the-database)
  describes the data checks. The restore's run output holds the query
  results. Step 5 of [Every database server is lost](#every-database-server-is-lost)
  gives the public-site test.
- **Give the current server price before approval.**
- **Use the last restore result to explain what is known about recovery
  time.** State that the last restore did not measure the complete site
  recovery unless that separate test also occurred.
- **Do not promise a maximum data loss from the one-minute backup target.**
- **A push alone changes no server.** Apply each configuration change as
  [Making a change](../AGENTS.md#making-a-change) says: run `every_server`
  or the playbook the step names.

## The location or provider is lost

**When:** the MMHotline-down alarm in the team's Cloudflare account wakes the person on call with "MMHotline is not checking in".
No hub-outage alerter alerts because the hub-outage alerters are down too.

**What this section does:** the system is rebuilt at a new provider, or in
another location at the current provider, in the order below: `util01`
first, then the other servers, then the database.

### Before you start

- **Post a customer notice from a systems desk** ([Post to the status page](post_to_the_status_page.md)).
- **Tell the person before work:**

  > Every server is gone, so I rebuild the system in a new location from the backups.
  > I rebuild `util01` first, which brings back MMHotline, then create the app servers.
  > Then I restore the database onto a new server and connect the app servers to it.
  > While I work, MMHotline alerts about what is still down.
  > An urgent alert says that the app doesn't answer at its public host name.
  > Acknowledge the alert about the app's public host name in Pushover.
  > The alert about the app's public host name resolves once the app answers again.
  > Warnings about the servers that aren't back yet are expected too, and so are the triage agent's reports on them.

  In the location recovery's one test, for four servers and a small database,
  production answered again after about 80 minutes.
- **Check each step's result before the next one.**
- **Expect failed previews and runs on the lost database servers.**
  Until step 4 deletes the lost database servers from the inventory, previews and runs fail on them, because nothing answers at their addresses.
  Push even if previews and runs fail only because the lost database
  servers' addresses do not answer.

### Steps

1. **The new provider's access:** steps 1 and 3 of [Move the servers to another provider](move_the_servers_to_another_provider.md).
   Skip step 2 of the provider-move procedure.
   Step 3 of the location-recovery section registers the new `util01`'s
   key at the provider.
   **Check:** the checks of those two steps.
2. **`util01`:** [Rebuild the utility server util01](rebuild_the_utility_server_util01.md),
   from step 2, using the systems desk. The utility-server rebuild brings back
   MMHotline, the failover monitor, and the systems repository's controller
   copy. Skip rebuild steps 5 and 6: no database server remains.
   Complete the utility-server reboot in rebuild step 8. Defer fleet-wide
   verification until recovery step 6.

   Reason: the new utility key and public address are needed in every new
   server's first-boot peer list. Systems desk WireGuard access works before the
   new utility server has its copy of the systems repository.
   **Check:** the rebuild's checks, from step 2 to the reboot of step 8,
   such as step 3's check that MMHotline's data came back.
3. **The other new servers:** follow
   [initial setup chapter 6 (create your three production servers: app, database, and tools)](../initial_setup/06_create_your_three_production_servers.md) for the
   app servers, `staging01`, and any jobs or load-balancer servers.
   - Each new server takes a lost server's name and private address.
   - Generate each replacement key before creation, record the new public
     address in `public_ipv4_address`, and keep `address` equal to `private_ip`.
   - Delete the lost server's host-key line before trusting the replacement
     host key over WireGuard.
   - Commit and push the inventory and host keys.
   - Run `every_server` to add the new keys and configure the replacement
     servers.

   **Check:** the `every_server` run passes on the new servers. App stages
   can fail until recovery step 4 restores the database.
4. **The database:** steps 1 to 4 of [Every database server is lost](#every-database-server-is-lost).
   The restored server becomes the primary.
   Step 1 of the database-recovery section creates the server only now,
   so the new database server starts with the new `util01`'s SSH key.
   The restore logs in with the new `util01`'s `mmhotline` user key.
   `util01`'s runs never install the `mmhotline` user's public SSH key
   on the server in `database_restore_servers`.
   Once the restored database's configuration run passes, the apps start.
   Then reboot the step 3 servers to use the installed updates, following step 7
   of [Add a server](add_a_server.md).
   **Check:** the checks of those database steps, and of the reboot.
5. **Staging's data,** if the system has `staging01`: step 3 of [Replace staging01](replace_staging01.md),
   which fills staging's database with the seed command.
   **Check:** step 4 of [Replace staging01](replace_staging01.md).
6. **Verify:** step 5 of [Every database server is lost](#every-database-server-is-lost), and step 8 of
   [Add a server](add_a_server.md) on each new server, `util01` included.
   On `util01`, `sudo mmwatchdog fleet` lists every inventory server as reporting.
   **Check:** all of these hold. Then resolve the customer notice ([Post to the status page](post_to_the_status_page.md)).

## Every database server is lost

**When:** no usable database server remains, such as when the only
database server is lost.

**What this section does:** restore the first new database server with
the steps tested by the weekly drill. The other new database servers join
the first new database server as replicas.

### Before you start

- **Keep the lost servers in the inventory until step 3.** Reason:
  removing the lost servers would make `util01`'s next run drop the lost
  servers' records from the failover monitor, and the restore reads those
  records to refuse a recovery while the monitor reports any database
  server healthy.
- **Expect failed previews and runs on the lost database servers.**
  Until step 3 deletes the lost database servers, previews and runs fail
  on the lost database servers because nothing answers at the lost
  servers' addresses.
  Push even if previews and runs fail only because the lost database
  servers' addresses do not answer.

### Steps

1. **Create the new database server** with the next number, such as `db03`.
   - Install the person's systems desk SSH key and `util01`'s `mmhotline` user SSH key.
     Follow step 2 of [Add a server](add_a_server.md).
   - Put the new database server in `database_restore_servers`.
     Do not put the new database server in `database_servers` yet.
     Keeping the new database server outside `database_servers` prevents a
     run from making an empty primary before the restore.
   - Record the setup-generated WireGuard public key and public address as
     shown below. Commit and push, then apply only `every_server`'s
     `every_server` fleet stage on `util_server`, as step 3 of
     [Add a server](add_a_server.md) (shared step 3) describes.
   - Then give this desk its WireGuard peer for the new database server:

     ```sh
     sudo -n update-this-desks-wireguard-peers
     ```

     A server in `database_restore_servers` with a database server's
     address is a desk peer; `restore01` never is.
   - Trust the new database server's SSH host key over WireGuard with
     step 4 of [Add a server](add_a_server.md) (shared step 4), then
     commit and push the host key.

   ```yaml
   # inventories/servers.yml
   nodes:
     db03:
       address: 10.20.2.3
       ssh_user: root
       connection: ssh_only
       ssh_known_hosts: ssh/known_hosts
       ssh_config: ssh/config
       vars:
         private_ip: 10.20.2.3
         public_ipv4_address: 203.0.113.23
         server_type: cx23
         location: fsn1
         wireguard_public_key: PFHMlKh61wvN0/mEnwE2mCdTk3PCQmr/u0lh3F8JkT0=
   groups:
     database_restore_servers:
       nodes: [db03]
   ```

   Replace the example public address, server type, location and public
   key with `db03`'s actual setup values before committing. `db03` keeps
   `server_type` and `location` when it moves to `database_servers`.

   **Check:** the peer command prints `Added: db03 (10.20.2.3).`, and the
   host-key step's SSH connection to `10.20.2.3` succeeds.
2. **Restore the newest state** available from the backups and archived
   write-ahead logs onto the new database server:

   ```sh
   ./server_management_scripts/run_mmx_on_util01 run restore_database --var restore_mode=recovery --var server_name=db03 \
       --var recover_to=latest --var read_backup_bucket_as_of="2026-11-03 15:30:00+00"
   ```

   `read_backup_bucket_as_of` tells pgBackRest to read the production backup
   bucket's contents as the bucket stood at the given time.
   Later deletions and overwrites do not affect the selected bucket contents.
   Without an attack, use the restore's start time, with a time zone as
   in the command above.
   If an attacker may have changed the production backup bucket,
   set `read_backup_bucket_as_of` to a time before the attack.
   After the restore, rotate the production backup bucket's B2 keys
   ([Backblaze B2 keys](rotate_a_secret.md#backblaze-b2-keys)).

   **Check:** the run passes. If the restore fails or refuses, see
   "If something is different" below.
3. **Move `db03` to `database_servers` as a new database server,** in one commit:
   - Remove `db03`'s `connection: ssh_only`.
   - Add `db03`'s `https_address` (`https://10.20.2.3:7443`). Keep the existing
     `private_ip`, `public_ipv4_address`, and setup-generated WireGuard key.
   - Set `database_restore_servers` back to `nodes: []`.
   - In the commit moving `db03` between groups and changing `db03`'s
     network settings, delete the lost servers from the inventory.
   - Include removal of the lost servers' lines from `ssh/known_hosts`
     in the commit moving `db03`.

   Push the commit and run `every_server` on `util01`. The run removes the lost servers from the failover group and adds `db03`'s normal database peers.
   **Check:** the run passes; step 4 reads its result.
4. **Read the configuration run's result.** The run makes the restored
   database the formation's primary, turns its archiving on, and points
   the apps' `DATABASE_URL` at `db03`.
   **Check:** step 5 verifies the result.
5. **Verify:** each app's health URL answers through its public host name,
   `db03` is the primary, and the next daily backup passes.
   On the primary, the following `psql` command prints `f`:

   ```sh
   ssh -F ssh/config root@10.20.2.3 'sudo -u postgres psql -XAt -h /var/run/postgresql -p 5432 -c "select pg_is_in_recovery()"'
   ```

   **Check:** all of these hold.
   If the system had more database servers, create replacement replicas
   with new names, such as `db04`
   ([Add a second database server](add_a_second_database_server.md)).

### If something is different

- **SSH to `10.20.2.3` fails with "No route to host":** this desk has no
  WireGuard peer for the new database server. Run
  `sudo -n update-this-desks-wireguard-peers`, as step 1 says.
- **The restore refuses and names a server where a Postgres answers on
  port 5432.** The restore asks each server still in `database_servers`
  whether a Postgres answers on port 5432, and refuses while one does,
  naming the server: a recovery beside it would make two primaries. If the
  named server holds production, it is not lost; otherwise power it off at
  the provider and run the restore again.
- **The restore refuses while the failover monitor reaches a server's
  Postgres.** `restore_database` refuses while the failover monitor reaches the
  Postgres of any registered production database server. A database
  server that the monitor reaches survived, so this procedure does not
  apply: to recover rows from an earlier state, restore a separate copy
  instead.
- **The restore fails:** do not go on to the next step, and do not use
  the failed server again: `restore_database` refuses a second recovery
  on a server that a recovery already wrote to. Destroy that server,
  create a new one with the next unused name, such as `db04`, and run
  steps 1 and 2 for the new name. Reason: in a test, going on after a
  failed restore moved the old primary out of the failover monitor and
  left the system with no database server.

## Bring the whole database back to a chosen minute

**When:** a bad change, a bad release, or a break-in through an app damaged
much of the database, and the person chooses to bring the whole database
back to the minute before the damage, losing every change made since. When
only a few rows are wrong, [Recover rows lost to a bad change](recover_rows_lost_to_a_bad_change.md)
copies them back from a separate copy on `restore01` and keeps every later
customer change instead. During [Respond to a break-in](respond_to_a_break_in.md#4-rebuild-and-replace-exposed-keys),
decide before step 4's item 3 (Rebuild util01), and read
[A lock-out is on, or util01 may be compromised](#a-lock-out-is-on-or-util01-may-be-compromised) first.

**What this section does:** the site shows the status page, the old
database servers stop, and a new database server, such as `db03`, gets the
database as it stood at the chosen minute. These are the steps of
[Every database server is lost](#every-database-server-is-lost), with the
chosen minute in place of `latest`, in the order that `restore_database`
accepts: `restore_database` refuses a recovery while a database server in
`database_servers` answers on port 5432, or while the failover monitor on
`util01` reports one healthy.

**Who acts:** database servers always need a person. The person chooses
the minute, approves losing every later change, and approves the new
server's price. The coding agent does every step from the systems desk.

### Before you start

- **Tell the person before the run** (with the chosen time in UTC and in
  the person's own time zone):

  > Every change made after 14:01 UTC on 3 November is lost: the orders, sign-ups and edits your customers made since then.
  > The site shows the status page from when I power off the old database servers until the restored database answers.
  > That takes about 12 minutes on the smallest system, and longer for a larger database.

  Reason for the figure: on test servers (`docs/testing.md` in the Stack's
  repository), the restore took 224 seconds and
  the `every_server` run after it 260 seconds, on a small database; the
  restore time grows with the database's size.

- **State the new database server's current price and get approval,** as
  at the top of this page.
- **A push alone changes no server.** Apply each configuration change as
  [Making a change](../AGENTS.md#making-a-change) says.

### Steps

1. **Choose the time.** `recover_to` is one minute before the damage
   started: the bad change's or release's start, such as a run in
   `./server_management_scripts/run_mmx_on_util01 results`, or the first
   known access in a break-in's timeline (step 3 of the break-in
   procedure). Write it in UTC, with `+00`. For a start at 15:02 in Central
   European Time, run on the desk:

   ```sh
   date -u -d '2026-11-03 15:02 CET - 1 minute' '+%Y-%m-%d %H:%M:00+00'
   # prints 2026-11-03 14:01:00+00
   ```

   `read_backup_bucket_as_of` selects which versions of the backup bucket's files pgBackRest reads.
   Use the time the restore starts, such as `"2026-11-03 15:30:00+00"`, unless an intruder may have
   reached a database server or a B2 key: the app servers hold no backup key, so nothing an intruder reached
   through an app could change the bucket.
   When an intruder may have reached a database server or a B2 key, use the time of that first access instead,
   and set `recover_to` at least 3 minutes before it.
   Reason: a database server sends its newest changes to the bucket about once a minute (`archive_timeout = 60`),
   so changes from the last minute or two before that access may reach the bucket only after it.
   **Check:** the person confirms the time, read back in UTC and in the person's own time zone.
2. **Show the status page.** The coding agent sets
   `send_app_requests_to_the_status_page: true` in `mmx_project_settings.yml`, as
   [Send the app's requests to the status page](respond_to_a_break_in.md#send-the-apps-requests-to-the-status-page)
   shows, commits, pushes, and runs:

   ```sh
   ./server_management_scripts/run_mmx_on_util01 run every_server \
     --only-fleet-stages find_the_releases_the_app_servers_run,find_the_live_and_new_web_ports_on_the_app_servers,point_every_caddy_at_the_live_web_containers
   curl -fLsS https://shop.example.com/
   ```

   **Check:** the public request shows the independent status page at `status_page_host_name`.
   Note the time: the site shows the status page from now until step 6.
3. **Stop the old database servers.** At the provider, snapshot each old database server's disk,
   record the snapshot and server IDs, and power off each old database server
   (`./server_management_scripts/power_off_a_server_at_the_provider --server-id ID`).
   Keep the old database servers in the inventory until step 3 of
   [Every database server is lost](#every-database-server-is-lost) deletes them.
   Reason: the snapshots are evidence after a break-in, and a way back if the chosen minute was wrong.
   **Check:** `./server_management_scripts/list_the_servers_at_the_provider` shows each old database server `stopped`.
4. **Restore onto a new database server:** steps 1 to 4 of
   [Every database server is lost](#every-database-server-is-lost). Step 2's command
   is, with the two times from step 1 above:

   ```sh
   ./server_management_scripts/run_mmx_on_util01 run restore_database --var restore_mode=recovery --var server_name=db03 \
       --var recover_to="2026-11-03 14:01:00+00" --var read_backup_bucket_as_of="2026-11-03 15:30:00+00"
   ```

   **Check:** the run passes, and its result names each old database server "counted as lost".
5. **Verify** with step 5 of [Every database server is lost](#every-database-server-is-lost). Also read
   `newest_restored_transaction_committed_at` in the restore's result: the time is before `recover_to`.
   Ask the person to check in the app that a record made just before `recover_to` exists and that the damage is gone.
   **Check:** all of these hold. Otherwise keep the status page and tell the person what differs.
6. **Return requests to the app.** After a bad release, first deploy the earlier release
   ([Deploy and roll back an app release](deploy_and_roll_back_an_app_release.md)), so the release cannot
   damage the restored data again. Then the coding agent sets `send_app_requests_to_the_status_page: false`,
   commits, pushes, and runs the command of step 2 again.
   **Check:** the public request shows the app, and the person can tell customers the site is back
   ([Post to the status page](post_to_the_status_page.md)).

### If something is different

- **The restore's result says a server "answers as a running Postgres":**
  power that server off at the provider and run the command again.
- **The restore refuses because the failover monitor reaches a server's Postgres:**
  check at the provider that the server is powered off, wait until
  `pg_autoctl show state` on `util01` shows the server unhealthy, and run the command again.
- **The restore fails with "recovery ended before configured recovery target was reached":**
  `recover_to` is later than the newest change in the bucket. Choose an earlier `recover_to` on a new server.
  The time cannot change once the restore has run on a server: a second run with another time refuses and names both times.
- **An app's check query fails only because the query asks for data newer than `recover_to`,**
  such as an order from the last two days: stop and tell the person. The restore is in place,
  but the run stopped before turning archiving back on.
- **Uploaded files were deleted or overwritten too:** follow
  [Restore all of an app's uploaded files](restore_an_uploaded_file.md#restore-all-of-an-apps-uploaded-files)
  with the same time.

#### A lock-out is on, or util01 may be compromised

During [Respond to a break-in](respond_to_a_break_in.md), the steps above change:

- **Decide before the break-in procedure's step 4, item 3 (Rebuild util01),** because the database choice
  changes which rebuild steps run.
- **Step 2:** the status page goes on with the break-in procedure's command from the desk that keeps access
  (step 1, "If the attacker is destroying data").
- **Between steps 3 and 4, rebuild `util01`** as step 4 of the break-in procedure says, but skip rebuild steps 5 and 6 of
  [Rebuild the utility server util01](rebuild_the_utility_server_util01.md): those steps register the old
  database servers with the new failover monitor, and the restore refuses while the monitor knows a database server.
  The rebuild's step 7 run fails on the powered-off database servers, because nothing answers at their addresses.
  That failure is expected; read the run's other results.
- **Every MMX command runs from the desk that keeps access,** with the coding agent's MMX button,
  `sudo -n -u servers-mmx run-mmx-on-the-servers ... --connection ssh_only`, in place of `./server_management_scripts/run_mmx_on_util01`.
  The new server's first-boot data admits only the desk that keeps access, as the break-in procedure's step 4 says.
  In step 1 of [Every database server is lost](#every-database-server-is-lost), the `util_server` run is
  `sudo -n -u servers-mmx run-mmx-on-the-servers run every_server --connection ssh_only --only-fleet-stages every_server --limit util_server`.
  Step 4's restore command is:

  ```sh
  sudo -n -u servers-mmx run-mmx-on-the-servers run restore_database --connection ssh_only \
      --var restore_mode=recovery --var server_name=db03 \
      --var recover_to="2026-11-03 14:01:00+00" --var read_backup_bucket_as_of="2026-11-03 15:30:00+00"
  ```

  Step 3 of [Every database server is lost](#every-database-server-is-lost) runs
  `sudo -n -u servers-mmx run-mmx-on-the-servers run every_server --connection ssh_only`.
- **After step 6,** continue with the break-in procedure's step 4.

## Restore the database to a time before a break-in

This section moved to [Bring the whole database back to a chosen minute](#bring-the-whole-database-back-to-a-chosen-minute),
with [A lock-out is on, or util01 may be compromised](#a-lock-out-is-on-or-util01-may-be-compromised) for a break-in.
