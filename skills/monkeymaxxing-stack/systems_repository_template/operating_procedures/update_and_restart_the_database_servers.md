# Update and restart the database servers

**When to use this page:** the team's weekly window, `maintenance_window` in `mmx_project_settings.yml` (a weekday, a UTC start time, and a length in minutes; tell the person the time in the person's local time), arrives, or a change waits for a restart
of Postgres ([Making a change](../AGENTS.md#making-a-change)).

**What this page does:** `update_database_servers` installs waiting
database server updates and restarts Postgres where a setting waits, one
database server at a time, while writes continue.

**Who acts:** the coding agent runs every step from the systems desk.
Outside the weekly window, the person agrees to the quiet moment for the
run.

## Before you start

- Read [the systems repository rules](../AGENTS.md#the-rules) first.
- **Never make your own task with `pg_auto_failover_node` or
  `restart_postgresql_for_new_settings`.**
  `update_database_servers` handles the switchover in the required order.
  Use `switch_database_primary` for a switchover alone.
- **What users see:** with a replica, writes fail only for the seconds of
  the switchover (2-6 s measured). With `db01` alone, restarting Postgres
  causes a short outage in the window: the apps' requests fail for a few
  seconds.
- **Postgres's settings on the database servers** are in the input
  `postgresql_settings` of the task `postgres_under_pg_auto_failover` in `roles/database_server/main.yml`.
  The `postgresql_settings` input includes `shared_buffers` and the archive
  settings.

## Steps

1. **For a settings change only: apply the setting with `every_server`.**
   Change `postgresql_settings`, then commit, push, and run
   `./server_management_scripts/run_mmx_on_util01 run every_server`.
   Settings that need only a reload, such as `archive_timeout`, take effect on
   every database server once the coding agent's `every_server` run on `util01` passes.
   **A setting that waits for a restart of Postgres,** such as a new
   `shared_buffers` or `archive_mode`, does not stop `util01`'s run.
   The `every_server` run writes the setting on every database server, where
   the setting waits for a restart of Postgres.
   **Check:** the run passes. Each server's task
   `database_server/postgres_under_pg_auto_failover` names the waiting setting
   in its reason and output `postgresql_settings_waiting_for_a_restart`.
   Read the task's reason and `postgresql_settings_waiting_for_a_restart`
   output with `./server_management_scripts/run_mmx_on_util01 results RUN_ID --fleet-stage database_server --task database_server/postgres_under_pg_auto_failover --json`.
   MMX prints the run ID when the agent starts `every_server` on `util01`.
   `./server_management_scripts/run_mmx_on_util01 status` from the desk also names the latest run.
   For example, `Run 7f3a9c1e` has the ID `7f3a9c1e`.
   Replace `RUN_ID` with the actual MMX run ID.
   When no setting waits for a restart, the change is done.
2. **Run `update_database_servers`:**
   `./server_management_scripts/run_mmx_on_util01 run update_database_servers`,
   in the team's maintenance window (`maintenance_window`), or, for a
   setting that waits, in the team's window or in a quiet moment that the
   person agrees to.
   **Check:** the run passes. On `util01`,
   `sudo -u postgres pg_autoctl show state --pgdata /var/lib/postgresql/17/pg_auto_failover_monitor --formation production`
   shows the formation: one node as `primary`, or as `single` while the node
   is alone.
3. **Reboot the other servers,** as
   [Reboot servers after updates](reboot_servers_after_updates.md) says,
   when this run was the weekly window's.
   **Check:** the checks of that page.

## If something is different

- **Postgres refuses a value.** MMX has Postgres check each value, then
  reloads Postgres. If Postgres refuses a value, the run fails at the first
  database server without changing anything there.
  The failure reason contains Postgres's own words.
  Fix the value, then repeat step 1.
- **A reason says that the module refused a restart on the primary,**
  such as `the node db01 is the primary of the formation production, and
  shared_buffers takes a restart of PostgreSQL, which on the primary is a
  failover`: nothing restarted. In this repository only
  `update_database_servers` asks for a restart.
  The refusal to restart Postgres on the primary can happen if the primary
  changes during `update_database_servers`.
  For example, a failover may promote a replica before that replica's turn.
  On the database server whose restart was refused, Postgres keeps using the
  values from before the attempted restart.
  The new value waits in
  `/etc/postgresql/pg_auto_failover_node_settings.conf`, written by
  `every_server`.
  Once the database group, or formation, has settled, run
  `./server_management_scripts/run_mmx_on_util01 run update_database_servers` again.
  The formation shows as step 2's check says.
  `update_database_servers` makes a replica the primary before restarting
  the old primary.
- **`update_database_servers` stops partway.** `./server_management_scripts/run_mmx_on_util01 results` says
  where it stopped. Fix the cause, then run `update_database_servers` again.
  On a retry, each replica's turn ends any pg_auto_failover maintenance left by the stopped run.
  On each database server, the `database_server/postgres_under_pg_auto_failover`
  task in `update_database_servers` first waits up to five minutes for the
  formation to settle.
  Already-applied changes do nothing the second time.
  See [The alert pauses](#the-alert-pauses) for the stopped run's alerts.
- **Postgres does not start after its restart.** Postgres may accept a
  setting but fail to start with it.
  For example, `shared_buffers` may exceed the server's memory.
  If Postgres does not start after its restart, the run stops with: `restarted pgautofailover.service, as the node's
  PostgreSQL did not run, and a minute later the node's PostgreSQL ... does
  not accept connections on port 5432; read journalctl -u
  pgautofailover.service`.
  The journal of `pgautofailover.service` on the database server where
  Postgres failed to start names the cause, such as `could
  not map anonymous shared memory`.
  With a replica, the primary continues accepting writes.
  With `db01` alone, the apps stay down until the fix is applied.
  Whether a replica exists or `db01` runs alone, fix the value in
  `roles/database_server/main.yml`, then commit and push.
  The coding agent's `every_server` run on `util01`
  (`./server_management_scripts/run_mmx_on_util01 run every_server`) gives each
  database server the corrected `/etc/postgresql/pg_auto_failover_node_settings.conf`, one server
  at a time.
  Where Postgres is not running, the `pg_auto_failover_node` module restarts
  `pgautofailover.service` so Postgres starts with the corrected value.
  Meanwhile, pg_autoctl, the pg_auto_failover program run by
  `pgautofailover.service`, may replace the replica's data with a fresh copy
  from the primary.
  The replica's `pgautofailover.service` journal shows `pg_basebackup` when
  pg_autoctl replaces the replica's data.
  Replacing the replica's data with a fresh copy from the primary loses no
  data but takes longer for a big database.
  Once pg_autoctl has copied the data, run `update_database_servers` again.
- **A dryrun shows something unexpected.** See
  [What a dryrun shows](#what-a-dryrun-shows).

## How `update_database_servers` works

`update_database_servers` updates each replica first, with the replica in
pg_auto_failover maintenance. In pg_auto_failover maintenance, the primary
continues accepting writes without waiting for the replica.
`update_database_servers` then makes a replica the primary and updates the
old primary. Making a replica the primary in a planned switch is called a
switchover.

On each server's turn, Postgres restarts if a changed setting requires it.
The database server being updated also reboots when
`/var/run/reboot-required` exists. On Debian, unattended-upgrades' kernel
hook writes the marker when a kernel package is installed.
The marker means a new kernel needs a reboot. Library and service
restarts are needrestart's job, handled in the database server's turn.

The update playbook installs waiting database server updates and restarts Postgres where a setting waits:

- **With a replica,** `update_database_servers` restarts each replica in
  pg_auto_failover maintenance while the primary continues accepting writes.
  `update_database_servers` makes a restarted replica the primary, then
  puts the old primary in pg_auto_failover maintenance and restarts Postgres
  on the old primary.
  Writes fail only for the seconds of the switchover (2-6 s measured).
- **With `db01` alone,** `update_database_servers` restarts Postgres on
  `db01`: the apps' requests fail for a few seconds.

### The alert pauses

Each database server's alerts are paused only during its own turn and
during the switchover, and each pause lasts at most as long as the run
waits for that server: 75 minutes for a turn, and 22 minutes plus one for
each app for the switchover (the arithmetic is beside each pause in
`playbooks/update_database_servers.yml`). When the updates or the restarts
fail, the pause ends at once, so the server's own alerts say what is
wrong. When `update_database_servers` stopped elsewhere in a database
server's turn, such as in pg_auto_failover maintenance, the pause ends by
itself at its end. To end it sooner, once the cause is clear, run
`mmwatchdog maintenance off --every-check-group` on that database server.

## How the settings reach Postgres

MMX's `pg_auto_failover_node` module is the part of MMX that manages
Postgres under pg_auto_failover on a database server.
The `pg_auto_failover_node` module writes the `postgresql_settings` values into
`/etc/postgresql/pg_auto_failover_node_settings.conf`.
The last line of each database server's `postgresql.conf` includes
`/etc/postgresql/pg_auto_failover_node_settings.conf`.

The task's reason ends with a hint from the `pg_auto_failover_node`
module. The hint depends on the server:

- A replica can show `shared_buffers waits for a restart of PostgreSQL; run
this task with restart_postgresql_for_new_settings: on_a_replica on this
node`.
- The primary's hint says to make another node the primary with `pg_auto_failover_primary` first.
- For `db01` alone, the hint names `restart_postgresql_for_new_settings`
  with the value `on_a_replica_or_a_node_alone`.

For all three hints, follow the steps above for `update_database_servers`
in this systems repository.

### Why `every_server` does not restart Postgres

`every_server` restarts Postgres for a setting only when creating a database node that serves nobody yet.
`every_server` runs the database servers one after another.
Restarting Postgres for changed settings one server after another is unsafe
on existing database nodes.
Restarting the primary causes a failover.
Restarting the next server during the failover caused by restarting the
primary can leave different database histories and every write waiting.

The value waiting for a restart is already in
`/etc/postgresql/pg_auto_failover_node_settings.conf` on every database
server. Any Postgres restart, such as after a crash, also starts with the
value waiting for a restart.
A `switch_database_primary` switchover also applies the waiting value on
the old primary, because the old primary restarts as a replica.

### What a dryrun shows

A dryrun shows each value it would change, such as `would set
shared_buffers from 896MB to 1024MB in
/etc/postgresql/pg_auto_failover_node_settings.conf`, and each setting
that would then wait for a restart. A dryrun does not ask Postgres to check values.
A refused value therefore fails only in the real run, without changing
settings on the database server that rejects the value.

A setting removed from `postgresql_settings` may appear to need a restart in a dryrun even when it will not.
A dryrun changes nothing, so Postgres still reports the setting as it is, and the value a removed setting returns to is known only during the run.
For a few seconds after Postgres restarts on a replica, a dryrun reports that
database server's task `not_checked`, with `the formation production is
not settled`. The replica is catching up.
A real run waits for the formation to settle, for at most five minutes.
A failover or a switchover settled in about a minute on test servers, so a formation that takes longer needs a person to look at it.
