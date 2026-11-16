# Move from Dokku to your own system

## Variances and guidance needs

Move the Dokku app, workers, uploads, and schedule first. Keep PostgreSQL on the Dokku host until the destination works.
Use [Move a database into the Stack][database-move] for the temporary WireGuard connection, logical replication, and the final database switch.
Use the [shared container procedure](from-any-container-platform.md) for the destination inventory, traffic route, and operational checks.

| Dokku source behavior | Migration guidance and example scope |
| --- | --- |
| Global and app config live on the host | Export each scope. App values override global values. Preserve runtime secrets separately from Git. |
| The PostgreSQL plugin owns a Docker service | Record plugin and database versions, every database, extensions, roles, and links. Retain a native plugin dump. |
| Docker-local scheduler | Stop web and worker processes and put cron in maintenance separately. Other Dokku schedulers need their own proof. |
| A private host directory mounts at `/uploads` | Copy bytes into private object storage with unchanged keys. Change the storage interface before removing the mount. |
| `app.json` schedules a one-shot command | One MMX-managed systemd timer replaces the source cron task. The worker remains `jobs_command`. |
| Heroku-style web and worker commands | Reuse the [Heroku mapping](from-heroku.md). The example declares migrations in `app.json` as Dokku predeploy work. |
| Plugin database remains during the app move | Publish only on the WireGuard address. Use the Stack's `database_moving_in` setting and database-move playbooks. |
| Plugin login can be `postgres` | The Stack app login must match `database_name`. Prepare that app role and its grants before moving runtime execution. |

## What the example proves

The [example](../../examples/app-platform-migrations/from-dokku/README.md) retains the Heroku portal's seven-table PostgreSQL schema.
Accounts use application-owned bcrypt verifiers and UUIDs. Files are private. PostgreSQL holds queue state and schedule receipts.
The source uses a Dockerfile, `Procfile`, a PostgreSQL plugin service, a private mount, and `app.json` cron.
The destination uses the same application with S3-compatible storage and a separate report worker.

The [test record](../../examples/app-platform-migrations/from-dokku/test_record.md) owns exact versions, measured results, and untested branches.
Standalone evidence does not establish a completed Stack deployment, traffic cutover, real bucket authorization, or backup recovery.

## Collect the source facts

Run these commands as an authorized administrator on the Dokku host. Keep the output outside the repository.
Use the actual application name in place of `portal` and the database service name in place of `portal-db`.

```sh
umask 077
export PRIVATE_DIR="$HOME/dokku-private"
mkdir -p "$PRIVATE_DIR"
dokku version > "$PRIVATE_DIR/dokku-version.txt"
dokku plugin:list > "$PRIVATE_DIR/plugins.txt"
dokku config:export --global > "$PRIVATE_DIR/global.env"
dokku config:export portal > "$PRIVATE_DIR/app.env"
dokku config:keys portal --merged > "$PRIVATE_DIR/config-names.txt"
dokku scheduler:report portal > "$PRIVATE_DIR/scheduler.txt"
dokku ps:report portal > "$PRIVATE_DIR/processes.txt"
dokku storage:report portal > "$PRIVATE_DIR/storage.txt"
dokku cron:list portal --format json > "$PRIVATE_DIR/cron.json"
dokku cron:report portal > "$PRIVATE_DIR/cron-settings.txt"
dokku domains:report portal > "$PRIVATE_DIR/domains.txt"
dokku ports:report portal > "$PRIVATE_DIR/ports.txt"
dokku postgres:list > "$PRIVATE_DIR/postgres-services.txt"
dokku postgres:info portal-db > "$PRIVATE_DIR/postgres-service.txt"
dokku postgres:links portal-db > "$PRIVATE_DIR/postgres-links.txt"
```

`postgres:info` and the config exports can contain credentials. Do not print the protected files.
Global values load before app values. Preserve values such as session-signing keys, encryption keys, and runtime-only secrets.
Move selected values into the systems repository's vault through its existing secret-input procedure.
Do not copy Dokku build credentials, plugin hostnames, or the source `UPLOAD_DIR` into destination runtime settings.

Record the app repository revision, image digest, Dockerfile or buildpack inputs, `Procfile`, `app.json`, and migration ledger.
Record live process counts and every service that links to the database. Include additional databases in the service inventory.
Inventory host timers, crontabs, plugin schedules, push hooks, and external writers in addition to `app.json`.
Record the host timezone, concurrency policy, missed-run policy, domains, proxy behavior, and TLS ownership.
The example's cron is daily at midnight on a UTC host, with concurrency forbidden and no downtime catch-up.

Dokku's [backup guide](https://dokku.com/docs/advanced-usage/backup-recovery/) separates host configuration, code, datastores, and mounts.
An archive of the database directory is not a consistent PostgreSQL export.

## Freeze source execution and export

A read-only rehearsal can collect inventory and copy files without taking production ownership.
For the actual app move, prepare the destination route and pause every source writer before the final file copy.
The database stays online for destination traffic and later replication.

For this Docker-local fixture:

```sh
dokku cron:set portal maintenance true
dokku ps:scale portal web=0 worker=0
dokku cron:report portal > "$PRIVATE_DIR/stopped-cron.txt"
dokku ps:report portal > "$PRIVATE_DIR/stopped-processes.txt"
```

Check running one-off containers too. Cron maintenance prevents new scheduled launches but does not finish an already-running task.
Drain or stop those tasks before transferring execution. Disable outside deploy triggers that can restore source execution.
The Dokku database service continues running while source web, worker, and cron remain stopped.

Keep a native database export for recovery and compatibility checks:

```sh
dokku postgres:export portal-db > "$PRIVATE_DIR/plugin-postgres.dump"
```

The plugin's default export covers the service's default database. Export additional application databases explicitly.
A plugin dump proves neither replication nor exported file bytes.
Use a client version at least as new as the source when inspecting or restoring the archive.

The upload exporter runs with the source database URL in the environment and the actual private mount path.
Install the example's pinned dependencies with `npm ci --prefix app --ignore-scripts --no-audit --no-fund`.
Set `EXAMPLE_DIR` to the copied `from-dokku` directory, then run there:

```sh
cd "$EXAMPLE_DIR"
. "$PRIVATE_DIR/global.env"
. "$PRIVATE_DIR/app.env"
# The Dokku service hostname resolves inside app containers, not on this host.
export SOURCE_DATABASE_HOST="$(dokku postgres:info portal-db --internal-ip)"
DATABASE_URL="$(node --input-type=module -e 'const url=new URL(process.env.DATABASE_URL); url.hostname=process.env.SOURCE_DATABASE_HOST; process.stdout.write(url.toString())')"
export DATABASE_URL
export UPLOAD_DIR=/var/lib/dokku/data/storage/portal
export EXPORT_DIR="$PRIVATE_DIR/upload-export"
node scripts/transfer-uploads.mjs export
export SNAPSHOT_FILE="$PRIVATE_DIR/source-rows.json"
node scripts/snapshot-database.mjs > "$PRIVATE_DIR/source-row-checks.json"
```

Only source the trusted exports produced by the authorized Dokku host.
The exporter checks every document reference, length, and SHA-256 against the mount.
The manifest retains unreferenced regular files too. Symlinks and special files need separate investigation.
Exports contain private rows and bytes. Transfer the complete protected export through an authenticated encrypted connection.

## Restore on Linux while keeping the old database

Use the shared procedure's image, settings, private bucket, health checks, and execution-owner steps.
The example's web, migration, and jobs commands are `node web.mjs`, `node migrate.mjs`, and `node jobs.mjs`, from `app/`.
Keep schema migrations paused throughout the database copy, as the [Stack procedure][database-move] requires.
Set `jobs_command` to `node jobs.mjs`. Do not also run the Heroku clock for the external timer below.
Remove `UPLOAD_DIR` at the destination so the storage module uses S3.

Provide a protected `DESTINATION_STORAGE_CONFIG_FILE` with the S3 SDK settings and `bucket`, then import the files:

```sh
export EXPORT_DIR="$PRIVATE_DIR/upload-export"
export DESTINATION_STORAGE_CONFIG_FILE="$PRIVATE_DIR/destination-storage.json"
node scripts/transfer-uploads.mjs import
```

The JSON uses `endpoint`, `region`, `forcePathStyle`, `bucket`, and `credentials.accessKeyId` and `credentials.secretAccessKey`.
Use a fresh bucket or empty prefix. The import refuses overwriting a destination key and downloads each object for byte comparison.
Document metadata remains in the old PostgreSQL database during this stage.

### Reach and prepare the Dokku database

Follow [Prepare the old server][database-move] for WireGuard, PostgreSQL settings, credentials, and source grants.
Keep the Dokku host outside the Stack's managed `nodes` and `database_servers` groups.
Set `database_moving_in` in `inventories/servers.yml` using the old host's address and key, as the procedure describes.

Dokku's PostgreSQL process runs inside a container. Open its administrator session with:

```sh
dokku postgres:connect portal-db
```

Use that session for the procedure's source roles and publication, using the actual database name.
For PostgreSQL configuration values, use `ALTER SYSTEM` in the container's administrator session:

```sql
ALTER SYSTEM SET wal_level = 'logical';
ALTER SYSTEM SET wal_sender_timeout = '4s';
ALTER SYSTEM SET listen_addresses = '*';
```

Keep `listen_addresses='*'` for the container's private Docker interfaces.
The host's WireGuard address does not exist inside the container. Restrict the published host port instead.
Locate the persistent data directory with `dokku postgres:info portal-db --data-dir`.
Apply the procedure's `pg_hba.conf` rules there, before broader matching rules, with the actual app role and database names.
Check `SHOW hba_file` inside PostgreSQL when the image's directory layout differs.
Check the procedure's slot/sender capacity against this service's existing configuration options.
Restart with `dokku postgres:restart portal-db`, rather than a host Debian PostgreSQL unit.
Prepare required database restarts before destination traffic uses the old database.

The fixture's `portal-db` service creates database `portal_db` and initially links the `postgres` login.
Set the Stack app's `database_name` to `portal_db` and prepare a matching non-administrator app login on the source.
For this fixture, create the login and transfer only its application objects in the administrator session:

```sql
CREATE ROLE portal_db LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
ALTER DATABASE portal_db OWNER TO portal_db;
ALTER SCHEMA public OWNER TO portal_db;
ALTER TABLE public.users OWNER TO portal_db;
ALTER TABLE public.sessions OWNER TO portal_db;
ALTER TABLE public.records OWNER TO portal_db;
ALTER TABLE public.documents OWNER TO portal_db;
ALTER TABLE public.report_jobs OWNER TO portal_db;
ALTER TABLE public.schedule_runs OWNER TO portal_db;
ALTER TABLE public.schema_migrations OWNER TO portal_db;
```

Use an existing matching app login when one is already present.
For another application, inventory its owners and grants instead of copying this fixture's table list.
Use the procedure's app-password and role preparation, with `portal_db` in place of its `shop` example.
Keep the plugin's administrator credential separate for the procedure's source-administrator vault key.
Do not configure the Stack app to run as `postgres`.

The tested plugin's ambassador could not publish a listener from the internal application network.
Use the plugin's supported direct exposure mode on the database service instead:

```sh
dokku postgres:set portal-db expose-mode direct
dokku postgres:expose portal-db 10.20.11.1:5432 --force
```

Use the actual `database_moving_in.wireguard_address` in place of `10.20.11.1`.
For an already-exposed service, apply the changed mode with `dokku postgres:reexpose portal-db --force`.
Changing exposure mode recreates the database container.
Apply equivalent source restrictions to Docker-published traffic and confirm PostgreSQL refuses connections through the public address.

Point `database_moving_in` at Dokku's PostgreSQL service itself, not at PgBouncer or another pooler in front of the service.
Use the direct WireGuard port published above, confirmed with `dokku postgres:info portal-db --exposed-ports`.
An intervening pooler defeats the read-only fence and can lose writes.
The old Dokku app can keep its pooler until the switch.
Add [the Stack's PgBouncer](../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/add_pgbouncer.md) after the move.

### Fence the plugin database

The Stack switch fences each moving database through the administrator connection, using `ALTER DATABASE`.
The switch ends the listed app sessions. No Dokku process restart performs the database fence.
Keep the plugin's original PostgreSQL data mount until acceptance, because the data mount holds the database defaults.
Check plugin configuration options and PostgreSQL role/database overrides for forced writable defaults, as the [switch procedure][database-move] requires.
Keep source web, worker, cron, one-off tasks, and deployment triggers stopped after the app move.
No outside writer may explicitly bypass a moving database's read-only default.

The fence changes only the listed databases' defaults.
Inventory `dokku postgres:links portal-db` and every writer to the moving databases before choosing the move boundary.
Every writer sharing a moving database must belong to the migration.
A separate Dokku PostgreSQL service has a separate cluster and needs its own move plan.

Complete [Prepare the Stack and move the app][database-move], then verify customer actions against the old database.
The Stack generates the old-first URLs and keeps the unfinished Stack app roles read-only.
Copy the [current Node database helper][node-helper] into the app and rebuild the image before that stage.
The example includes that helper unchanged, so connection selection checks whether the login can write.

## Verify accounts and execution

Before moving the database, run real customer actions against the destination while the database remains on the Dokku host.
Verify returning passwords, account and record UUIDs, private downloads, and guessed-ID refusals.
Create, edit, and delete a record. Upload and download a new file. Enqueue a report and check its owner-specific output.
Verify pending source reports complete once under destination execution ownership.

Copy [the schedule playbook](../../examples/app-platform-migrations/from-dokku/systems-repository/playbooks/portal_schedule.yml) into the team's systems repository.
Add `portal_schedule_server` containing exactly one server that runs `portal-jobs`.
Set `vars.portal_archive_calendar` to `"*-*-* 00:00:00 UTC"` in project settings.
Apply `mmx run portal_schedule` after the source cron is stopped and destination job ownership is established.

MMX's `systemd_scheduled_job` creates `portal-archive-completed-reports.service` and its timer.
The timer executes `podman exec portal-jobs node schedule.mjs` on the active release.
Systemd prevents overlapping local runs. The task's database occurrence key prevents duplicate daily effects.
`run_missed_job_after_downtime: false` preserves the source cron's missed-run behavior.

Check the next trigger and a one-shot invocation on the designated server:

```sh
systemctl list-timers portal-archive-completed-reports.timer
systemctl start portal-archive-completed-reports.service
journalctl -u portal-archive-completed-reports.service
```

Verify one `schedule_runs` receipt for the UTC date, including after a second invocation and timer restart.
Moving schedule ownership means stopping and disabling the old timer before enabling a replacement server's timer.
The shared container guide owns this scheduling convention for the other source guides.

## Move the database last

Follow [Move a database into the Stack][database-move] for the copy, switch, failure recovery, cleanup, and backup checks.
Use its [copy_the_database_moving_in playbook][database-copy] and [switch_to_the_database_moving_in playbook][database-switch].
Do not import the plugin dump into the destination before the copy. The copy playbook requires an empty application database.
Keep schema migrations paused while logical replication runs.

Keep customer traffic and the destination worker and timer running for the Stack switch.
The Stack fences old sessions and lets the updated driver reconnect through unchanged URLs, without restarting app containers.
Record acknowledged customer writes and their recovery time using the procedure's HTTP writer checks.
Do not apply the earlier standalone test's stop-and-restart sequence to the Stack.

The fixture uses UUID keys and has no sequences or large objects. The Stack procedure owns their transfer when another app needs those objects.
Inventory extensions, owners, grants, and every application database rather than limiting the migration to the fixture's seven tables.
Use the procedure's supported-data limits and its recovery steps if copying or switching fails.

Before another `every_server` run, remove the completed `database_moving_in` block as the procedure requires.
Complete the procedure's replica, backup, slot-cleanup, and old-system-off checks before retiring Dokku resources.
After the Stack accepts writes, reopening the old database requires reconciliation and must not happen automatically.

## Retire the source

After acceptance and the agreed retention period, remove source apps, plugin databases, mounts, cron entries, and deploy credentials by recorded ownership.
Check other application links before removing a plugin database or global configuration.
Follow the [Stack procedure][database-move] to remove the temporary peer and old URL address after verification.
Remove the plugin's temporary database port exposure with `dokku postgres:unexpose portal-db` when the move is accepted.
Retain protected exports according to the team's data policy.
Enroll the destination in backup, restore-drill, and alert checks using the Stack checklist.

## Evidence

See the [test record](../../examples/app-platform-migrations/from-dokku/test_record.md) for measured native source and standalone results.
Dokku's [environment guide](https://dokku.com/docs/configuration/environment-variables/),
[cron guide](https://dokku.com/docs/processes/scheduled-cron-tasks/), and
[PostgreSQL plugin](https://github.com/dokku/dokku-postgres) describe the source commands and scope boundaries.

[database-move]: ../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md
[database-copy]: ../../skills/monkeymaxxing-stack/systems_repository_template/playbooks/copy_the_database_moving_in.yml
[database-switch]: ../../skills/monkeymaxxing-stack/systems_repository_template/playbooks/switch_to_the_database_moving_in.yml
[node-helper]: ../../skills/monkeymaxxing-stack/files_for_your_app/node/pg_with_multiple_database_servers.mjs
