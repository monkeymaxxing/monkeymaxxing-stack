# Add PgBouncer

Read [the systems repository rules](../AGENTS.md#the-rules) first.

**When:** Postgres warns about the number of connections.

**What this page does:** PgBouncer lets many app connections share fewer
Postgres connections. [Adding PgBouncer](#adding-pgbouncer) uses three settings, each in its own commit.
Start PgBouncer, send staging's apps through PgBouncer, then send
production's apps through PgBouncer.

**Who acts:** you, the coding agent, do the steps from the systems desk.
The person reviews each app fix of step 1 in the app's repository. The
person on call hears in step 2 to expect possible installation warnings.

**Terms:** this page uses the Stack's terms, such as primary, replica
and fleet hub.
[Technical terms](../talking_with_the_team.md#technical-terms) explains
each term.

## Before you start

- **Change three settings in `mmx_project_settings.yml`, in separate commits,
  in the order below.**
  PgBouncer must run on every database server before any app connects through it.
  Move staging's apps first to check them before changing production.
- **A push alone changes no server.** Apply each configuration change as
  [Making a change](../AGENTS.md#making-a-change)
  says: a push alone changes no server, so run `every_server` or the playbook the step names.

## Adding PgBouncer

1. **Check each app for transaction-mode compatibility.** The app cannot keep its Postgres session between transactions.
   - Work that only one copy may do at a time must use `pg_advisory_xact_lock`, which ends with the transaction.
     Except in migrations, which connect directly, never use session-level
     `pg_advisory_lock` for work only one copy may do at a time.
   - The app must not rely on session state surviving between transactions.
     Session state includes a `SET` other than `SET LOCAL`, `LISTEN`, a
     temporary table, or a cursor `WITH HOLD`.
     PgBouncer does carry each client's encoding, `DateStyle`, `TimeZone`, `IntervalStyle`, and `application_name` to its assigned Postgres connection.
     A framework's connection settings for encoding, `DateStyle`,
     `TimeZone`, `IntervalStyle`, and `application_name`, such as Rails',
     are therefore fine.
     Action Cable's `postgresql` adapter uses `LISTEN` in web containers, so an app with that adapter must switch to an adapter without `LISTEN`, such as Solid Cable, Rails 8's own adapter.
   - Check the app's job worker.
     If the app's job worker waits with `LISTEN`/`NOTIFY` or holds a
     session-level advisory lock, set `jobs_connect_directly_to_postgres`
     to `true`.
     Rails' good_job uses `LISTEN`/`NOTIFY` or session-level advisory locks.
     Use `false` if each job's work stays inside transactions.
     Correct the setting if the app has changed its job library.
   - Database settings must not send a setting at login, such as `options=-c statement_timeout=...` in the URL.
     PgBouncer refuses logins that send a setting through URL `options`.
     PgBouncer would also refuse migrations' `PGOPTIONS` if migrations
     connected through PgBouncer.
     The app must use `SET LOCAL` inside each transaction instead.
     Check Rails' `variables:` in `database.yml` too.
     Rails sends the `variables:` settings as a session `SET` once per
     connection, and transaction mode loses the `variables:` settings.
   - Django's server-side cursors for `.iterator()` live across transactions.
     Set `DISABLE_SERVER_SIDE_CURSORS: True` in that app's database settings.
   - A driver requiring TLS (`sslmode=require` or `verify-full` in its settings) cannot log in.
     PgBouncer offers no client TLS. WireGuard encrypts the connection instead.
     Leave `sslmode` out of the app's settings, or use `prefer`.
   - Each framework's own PgBouncer settings, such as where its timeouts
     go and which prepared-statement setting it needs, are in the
     "PgBouncer settings needed" column of the stack repository's
     `docs/app-frameworks/README.md`, with the details in that
     framework's guide.

   A fix goes to the app's repository as a change the person reviews, and the fixed release must be deployed before step 3 sends the apps through PgBouncer.

   **Check:** each app meets every point above, or its fixed release is
   deployed.

2. **PgBouncer on:** tell the person on call to expect possible installation warnings from the `pgbouncer` check group
   ([Warnings while PgBouncer installs](#warnings-while-pgbouncer-installs)).
   In `mmx_project_settings.yml`, set
   `pgbouncer_runs_in_front_of_postgres: true`.
   Commit and push.
   `util01`'s run installs PgBouncer on database servers one at a time, and on `staging01` when the system has it.
   Every app still connects directly to Postgres.

   **Check:** on each server, verify that PgBouncer 1.21 or later and the service watching for Postgres changes are running:
   `./server_management_scripts/run_mmx_on_util01 run-command --nodes database_servers,staging_server -- "pgbouncer --version && systemctl is-active pgbouncer.service refresh_pgbouncer_when_postgres_starts_or_changes_role.path"`.
   Without `staging01`, leave `,staging_server` out of `--nodes`.
   In MMWatchdog's status on every database server and on `staging01`,
   verify that `pgbouncer/pgbouncer_runs`,
   `pgbouncer/pgbouncer_answers`, and `pgbouncer/pgbouncer_follows_postgres` pass.
   PgBouncer 1.21 is the first release that keeps prepared statements working in transaction mode, and drivers such as pgx, Ruby's pg, and psycopg prepare statements by name.

3. **Staging's apps through PgBouncer.** Without `staging01`, skip this step:
   step 4 sends production's apps through PgBouncer, and step 5's checks test them there.
   With `staging01`, set
   `apps_connect_through_pgbouncer.staging: true`; commit and push.
   While `pgbouncer_runs_in_front_of_postgres` is `false`, the run refuses
   `apps_connect_through_pgbouncer.staging: true` and
   `apps_connect_through_pgbouncer.production: true`.
   The run restarts staging's containers with the new settings.

   **Check:** verify that each app works at its staging host name, including writes and jobs.
   Then check that PgBouncer serves each staging app:
   `./server_management_scripts/run_mmx_on_util01 run-command --nodes staging01 --run-as-node-user-account postgres -- "psql -X -h /var/run/postgresql -p 6432 -U pgbouncer -d pgbouncer -c 'SHOW POOLS'"`
   lists each app's database, with clients in `cl_active` and `pool_mode`
   `transaction`.

4. **Production's apps through PgBouncer:** set
   `apps_connect_through_pgbouncer.production: true`; commit and push. The
   run restarts each app server's containers, one server at a time.

   **Check:** the run passes; step 5 verifies production's apps.

5. **Complete every verification below,** including the readings a day
   later, then set the checklist item `pgbouncer` done:
   - the same `SHOW POOLS` on `database_servers` lists each app's clients
     on the primary. On a replica, `SHOW POOLS` lists clients only for
     apps sending reads to the replica (`DATABASE_READ_URL`).
     When no app sends reads to a replica, `SHOW POOLS` lists no clients
     on the replica;
   - each app answers at its public host name and can write, for example by placing a test order.
     With `db02`, check again after `./server_management_scripts/run_mmx_on_util01 run switch_database_primary --var server_name=db02`, and again after switching back with the former primary's name, such as `--var server_name=db01`.
     Each time, verify that the driver found the new primary through
     PgBouncer;
   - after each switchover, check libpq too.
     Rails, Django, and PHP use libpq to connect.
     For each app, run a one-off container with `psql` on an app server
     to read the app's settings.
     In the example below, use an app server's WireGuard `address` from
     `inventories/servers.yml` in place of `10.20.1.1`.
     Use the app's `/etc/<app>/<app>.env` path in place of
     `/etc/shop/shop.env`.
     The `psql` command must print `f`: the server reached through
     PgBouncer is out of recovery, meaning the server is the primary.
     The command gives `psql` the app's `DATABASE_URL` without its
     password and the password in `PGPASSWORD`, so the password never
     shows in the app server's process list.

     ```sh
     ssh -F ssh/config root@10.20.1.1 \
       "podman run --rm --network host --env-file /etc/shop/shop.env docker.io/library/postgres:17 sh -c 'userinfo=\${DATABASE_URL#postgresql://}; userinfo=\${userinfo%%@*}; PGPASSWORD=\${userinfo#*:} psql \"postgresql://\${userinfo%%:*}@\${DATABASE_URL#*@}\" -XAtc \"select pg_is_in_recovery()\"'"
     ```
   - for each Node.js app, the check of
     [A Node app through a switchover](test_a_nodejs_app_during_a_database_switchover.md#a-node-app-through-a-switchover)
     passed during the switch to `db02` and the switch back, through the
     PgBouncers, whose port the app's env file now names;
   - work that only one copy may do takes `pg_advisory_xact_lock`, and the
     apps whose jobs use `LISTEN`/`NOTIFY` have
     `jobs_connect_directly_to_postgres: true` (step 1);
   - a day later, the readings of
     `postgres/connections_are_below_70_percent` on the database servers
     stay below 70% of `max_connections`.
     MMWatchdog's fleet hub on `util01` keeps the connection readings.

   **Check:** every point above passed.

## If something is different

- **To go back,** set the environment's `apps_connect_through_pgbouncer` to
  `false` and push. The reverted environment's apps connect directly again.
  PgBouncer keeps running, but the reverted environment's apps no longer
  use PgBouncer.
- **To stop PgBouncer's role:** setting `pgbouncer_runs_in_front_of_postgres` back to `false` makes MMX skip `roles/pgbouncer`, and skipping the role removes nothing:
  PgBouncer and the watcher that restarts PgBouncer when Postgres changes stay installed and start at boot.
  MMWatchdog's `pgbouncer` check group is removed, so MMWatchdog no longer checks PgBouncer.
- **The run refuses an `apps_connect_through_pgbouncer` setting:** the run
  refuses it while `pgbouncer_runs_in_front_of_postgres` is `false`. Do
  step 2 first.

## How PgBouncer works

This part explains the steps, for the reader who wants the reasons.

### PgBouncer in front of Postgres

PgBouncer lets many app connections share fewer Postgres connections.
PgBouncer runs on each database server and on `staging01`, in front of
each server's Postgres, at port 6432.
Debian 13 supplies PgBouncer 1.24.1 through the distribution's `pgbouncer` package.
PgBouncer uses transaction mode: a client borrows a Postgres connection
for one transaction only.
Thousands of mostly idle app connections can then share a few dozen Postgres connections.

Setting `apps_connect_through_pgbouncer.staging` to `true` makes MMX
change staging's app URLs.
Setting `apps_connect_through_pgbouncer.production` to `true` makes MMX
change production's app URLs.
MMX sets each app's `DATABASE_URL` and `DATABASE_READ_URL` to use
PgBouncer's port on every database server.
The driver still finds the primary by itself (`target_session_attrs`).
Work that must keep a Postgres connection between transactions keeps
connecting directly to Postgres at port 5432:

- app migrations;
- the job container of an app whose `jobs_connect_directly_to_postgres` is `true`;
- replication, the failover monitor, pgBackRest, and MMWatchdog's checks.

Whenever its Postgres starts, becomes a replica, or becomes the primary, PgBouncer restarts automatically.
After a failover, PgBouncer's automatic restart lets the apps reconnect
to the new primary.
The role, `roles/pgbouncer`, is present from the start.
The `roles/pgbouncer` role is off by default through
`pgbouncer_runs_in_front_of_postgres: false` in `mmx_project_settings.yml`.

### Warnings while PgBouncer installs

At the start of the run that turns PgBouncer on, MMWatchdog receives
PgBouncer's checks on every database server and on `staging01`.
The checks arrive before PgBouncer is installed.
A server reached late in the run may therefore warn that `pgbouncer/pgbouncer_answers` fails.
The server reached late in the run can also warn that MMWatchdog cannot
check `pgbouncer/pgbouncer_runs` and `pgbouncer/pgbouncer_follows_postgres`.
Once PgBouncer runs, MMWatchdog sends recovery notifications for
`pgbouncer/pgbouncer_answers`, `pgbouncer/pgbouncer_runs`, and
`pgbouncer/pgbouncer_follows_postgres`.

By default, a check in the `pgbouncer` group warns once the check has
failed for 2 minutes (`alert_after_failing_for`), and each check runs
every minute (`check_every`), both in the `pgbouncer` group of
`mmwatchdog_checks/database_servers.yml`. Each check confirms the
failure before warning.
The warning therefore comes about 3 to 4 minutes after failure starts.
On test servers, a hung PgBouncer warned after 3 minutes 28 seconds.
During installation on the servers used for the hung-PgBouncer test,
PgBouncer started in time everywhere and no warning occurred.
PgBouncer installation warnings wake nobody.
