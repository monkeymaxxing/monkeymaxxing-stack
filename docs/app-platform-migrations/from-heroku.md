# Move from Heroku to your own system

## Variances and guidance needs

This guide exports a Heroku customer portal and proves the exported copy works on independent PostgreSQL and S3-compatible storage.
Phase 1 is export and standalone rehearsal. A production cutover and the live Stack checks come afterward.
Heroku's `Procfile` lists commands for web, worker, and clock processes. A clock waits for a selected time and starts scheduled work.

| Heroku source behavior | Migration guidance |
| --- | --- |
| Heroku Postgres 18.4 | Rehearse the actual logical restore on PostgreSQL 17. The tested fixture restored without rewriting SQL. |
| Provider-owned `_heroku` schema and `pg_stat_statements` | Retain a native dump if needed, but exclude provider diagnostics from the portable application dump. Inventory application dependencies first. |
| No native object storage | Export the separate S3-compatible store. A database dump holds object references, not uploaded bytes. |
| Application-owned bcrypt accounts | Keep password hashes and UUIDs unchanged. Returning users can use their existing passwords. |
| Host-bound cookies | Users sign in at the destination hostname. Database-held sessions remain shared across destination app servers. |
| Scheduler add-on | Jobs are configured only in the dashboard and have no export API. Record commands and UTC schedule settings separately. |
| A `clock` Procfile process | The command and timer are versioned in code. Export the daily UTC setting and dyno formation too. |
| Separate worker and clock dynos | The Stack's one jobs command supervises both processes. `JOBS_PAUSED=true` keeps both kinds of destination work idle. |
| Heroku Postgres TLS | Use TLS for source export. Use the Stack's private multi-host URL and its Node helper at the destination. |
| Prorated Basic dynos and Essential Postgres | Stop execution during export and delete source services after verified completion to end billing. |

The example is a handwritten Express app with seven application tables.
The exporter is specific to that schema. Inventory additional tables, functions, extensions, large objects, and external integrations before adapting another app.
Heroku's [clock process guide](https://devcenter.heroku.com/articles/scheduled-jobs-custom-clock-processes) describes the code-defined scheduling pattern.
A clock is useful when the Scheduler dashboard cannot be used or the team needs its schedule behavior in source control.
The simple archive task uses a bounded SQL transaction with one unique UTC-date occurrence.

## Collect the source facts

Record the source repository revision, dependency lockfile, runtime and PostgreSQL versions, services, and config-variable names.
Record user UUIDs, ownership, document keys/hashes, pending jobs, completed output, migrations, and scheduling state.
Do not print passwords, session tokens, database URLs, storage keys, or full password hashes.
Keep exports and credential files outside the code repository with `umask 077`.

Export the source code through the customer's private Git host or a local source checkout.
For example, an authenticated customer can archive the selected private GitHub revision:

```sh
umask 077
mkdir -p "$HOME/heroku-private"
gh api repos/GITHUB_OWNER/REPOSITORY/tarball/SOURCE_COMMIT \
  > "$HOME/heroku-private/source-code.tar.gz"
```

Replace the repository and commit placeholders with the recorded source revision.
Code export must retain `Procfile`, `package-lock.json`, ordered migrations, and the clock implementation.
Code export does not include database rows or uploaded documents.

## Stop source execution

Use an approved maintenance window before the final export of a live application.
Stop web writes, workers, and scheduled execution together. For this three-process source:

```sh
heroku ps:scale web=0 worker=0 clock=0 --app YOUR_SOURCE_APP
heroku ps --json --app YOUR_SOURCE_APP > "$HOME/heroku-private/source-dynos.json"
```

Replace `YOUR_SOURCE_APP` with the source app's name.
Verify there are no running source processes before marking the execution state stopped.
Disable any separate Scheduler jobs or external webhook writers too.
A read-only rehearsal can instead use an already-frozen source; do not change a production service merely to run a test.

Keep source work stopped until cutover or an explicit rollback decision.
Exactly one location may execute pending reports and daily archive work.

## Prepare the export inputs

From the Stack repository root, install [the example](../../examples/app-platform-migrations/from-heroku/README.md)'s pinned Node dependencies:

```sh
cd examples/app-platform-migrations/from-heroku
npm ci --prefix app --ignore-scripts --no-audit --no-fund
umask 077
```

Use Node.js 24 and PostgreSQL 18 client tools for the source-18 export.
`pg_dump` must be new enough for the source server. Newer-to-older loading is not guaranteed by PostgreSQL.
The [pg_dump documentation](https://www.postgresql.org/docs/18/app-pgdump.html) describes the version boundary and selective exports.
The tested fixture's schema and data restored on PostgreSQL 17.11 without SQL changes.
A different app needs its own real restore proof.

Create three mode-600 JSON inputs in the private directory.
Read authorized source values into the files without copying values into chat or command arguments.

`source-database.json` contains these required fields:

```json
{
  "host": "postgres.example.com",
  "port": 5432,
  "user": "portal",
  "password": "REPLACE_FROM_THE_PROTECTED_SOURCE_CREDENTIAL",
  "database": "portal",
  "ssl": {"rejectUnauthorized": false}
}
```

The source's managed connection follows [Heroku's pg TLS example](https://devcenter.heroku.com/articles/connecting-heroku-postgres).
`false` encrypts the connection but does not authenticate the server certificate. Use a trusted CA when available.
This source exception must not become a blanket destination TLS policy.

`source-storage.json` contains the separate bucket configuration:

```json
{
  "endpoint": "https://s3.example.com",
  "region": "us-east-1",
  "bucketName": "example-portal-uploads",
  "accessKeyId": "REPLACE_FROM_THE_PROTECTED_SOURCE_CREDENTIAL",
  "secretAccessKey": "REPLACE_FROM_THE_PROTECTED_SOURCE_CREDENTIAL",
  "forcePathStyle": true
}
```

Use the source provider's endpoint, region, addressing mode, and bucket-scoped key.
The tested source used a dedicated private Backblaze B2 bucket with path-style requests.
Do not reuse a public status-page bucket or another application's storage key.

`source-metadata.json` records the known source revision, schedule, and stopped execution state:

```json
{
  "source_commit": "REPLACE_WITH_THE_RECORDED_SOURCE_COMMIT",
  "code_archive_file": "/home/person/heroku-private/source-code.tar.gz",
  "execution_state": {
    "source_execution_stopped": true,
    "formation": [
      {"type": "web", "quantity": 0},
      {"type": "worker", "quantity": 0},
      {"type": "clock", "quantity": 0}
    ]
  },
  "variable_names": {
    "heroku_app": [
      "DATABASE_URL", "DATABASE_SSL", "COOKIE_SECURE", "JOBS_PAUSED",
      "ARCHIVE_DAILY_UTC_TIME", "NODE_ENV", "WEB_CONCURRENCY",
      "S3_ENDPOINT", "S3_REGION", "S3_BUCKET", "S3_FORCE_PATH_STYLE",
      "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY"
    ]
  },
  "schedule": {
    "process_type": "clock",
    "command": "node clock.mjs",
    "daily_utc_time": "00:00",
    "timezone": "UTC",
    "occurrence_table": "schedule_runs"
  },
  "source_facts": {}
}
```

Use the actual full archive path, selected commit, stopped formation, variable names, and source schedule.
Fill `source_facts` with the collected non-secret IDs, ownership, hashes, states, and versions.
For a fixture with a protected pre-export row snapshot, add `baseline_snapshot_file` with that snapshot's full path.
The exporter then refuses a source whose rows differ from the recorded baseline.
The metadata records facts already verified at the platform; setting a boolean alone does not stop execution.

## Export code, SQL, rows, and objects

```sh
export SOURCE_DATABASE_CONFIG_FILE="$HOME/heroku-private/source-database.json"
export SOURCE_STORAGE_CONFIG_FILE="$HOME/heroku-private/source-storage.json"
export SOURCE_METADATA_FILE="$HOME/heroku-private/source-metadata.json"
export EXPORT_DIR="$HOME/heroku-private/export-001"
export PG_DUMP=/usr/lib/postgresql/18/bin/pg_dump
export PG_RESTORE=/usr/lib/postgresql/18/bin/pg_restore
node data-transfer.mjs export
```

Use the actual installed PostgreSQL 18 client paths.
Expected output starts with `EXPORT_PASS`. The exporter refuses an existing export directory.
A repeatable-read snapshot holds the table reads and `pg_dump` at the same database view.

The exporter includes `users`, `sessions`, `records`, `documents`, `report_jobs`, `schedule_runs`, and `schema_migrations`.
Those tables contain every application row in this fixture, including bcrypt hashes, ownership, sessions, completed report output, and scheduling receipts.
The selective application dump excludes Heroku-owned diagnostic objects that the app does not use.
Keep a raw native database dump separately when customer-specific provider dependencies need investigation.

The export directory contains:

- `source-code.tar.gz`, with the private source revision.
- `postgres.dump`, the custom-format application database archive.
- `postgres.sql`, generated from that archive by the source-major `pg_restore` client.
- `snapshot.json`, exact table rows, including sensitive account and session data.
- `manifest.json`, versions, table counts/checksums, code/dump checksums, schedule settings, config names, and object metadata.
- `objects/`, all currently listed object bytes, including unreferenced current keys.

The exporter follows bucket listing pages and checks every document reference against downloaded bytes.
Object bytes are stored under checksum-derived local filenames, while original keys remain in the manifest.
A PostgreSQL restore cannot restore those object bytes.
If concurrent uploads cause a mismatch, preserve the failed export, freeze writes, and export into a fresh directory.

Keep the entire export together. Never commit SQL, snapshots, fixture passwords, or exports containing account data.

## Restore into an isolated destination

Use a fresh Debian 13 Linux test machine with PostgreSQL 17, Node.js 24, npm, Python 3, and Podman.
Copy the original export and synthetic fixture password over an authenticated encrypted connection.
Keep the password in a separate mode-600 file. No source database or storage credential is needed at the destination.

For a standalone S3-compatible test service:

```sh
podman run -d --name heroku-rehearsal-storage \
  --publish 127.0.0.1:9090:9090 \
  --env debug=false \
  docker.io/adobe/s3mock@sha256:cf5b4f0b6200c4b636b779b93db1847419f6bd082c0b6cd88ee409dcaa350f9b
```

Wait for the service to answer on loopback port 9090 before creating a bucket.
S3Mock proves API and byte compatibility. S3Mock does not prove destination bucket authorization.
Create a new role, database, bucket, and settings directory for every rehearsal:

```sh
export REHEARSAL_NAME=heroku_first
export REHEARSAL_FIRST_PORT=18081
export REHEARSAL_SETTINGS_DIR=/root/heroku-first-settings
python3 tests/prepare-rehearsal.py
. "$REHEARSAL_SETTINGS_DIR/destination.env"
node tests/create-rehearsal-bucket.mjs
export EXPORT_DIR=/root/heroku-private/export-001
export FIXTURE_PASSWORD_FILE=/root/heroku-private/fixture-password
node data-transfer.mjs restore
export ALLOW_DISPOSABLE_REHEARSAL=true
node tests/rehearsal.mjs
```

The settings helper refuses an existing directory and never removes an existing database or role.
The helper writes fresh destination credentials with mode 600.
The database URL tries an unreachable loopback address before the real primary, checking the copied multi-host helper's fallback.

Expected output includes `RESTORE_PASS`, followed by a JSON result with `passed: true`.
Restoration requires an empty destination database and refuses an existing destination object key.
SQL runs unchanged in one transaction with `ON_ERROR_STOP`, then every table must equal the source snapshot.
The restored objects must match exported lengths and SHA-256 values.
If object transfer fails after SQL restoration, preserve the export and create another empty destination before retrying.
Only restore trusted exports because SQL restoration executes source code in the destination database.

The behavior test logs in both returning users with existing passwords and preserved UUIDs.
The test checks owned records, exact private downloads, new uploads, CRUD, foreign-owner refusals, and cross-instance session revocation.
Report tests use concurrent workers and kill an actual worker during its open completion transaction.
Schedule tests prove one committed archive during overlap and run the actual combined report/clock command.
The test also checks new registration and graceful shutdown.
The rehearsal changes only its restored copy. Never reuse that mutated copy for a production import.

For a fresh-agent replay, use a separate app copy, export copy, installation, database, bucket, settings directory, and port pair.
Repeat the instructions without assistance from the implementation agent.

## Prepare the Stack release

Build `app/Dockerfile` with `app/` as its build context.
Keep restored migration SQL byte-for-byte because the database ledger checks migration checksums.
Run `npm run migrate` before web and jobs containers start.
The web and jobs entry points do not silently migrate on startup.

Add an app entry in your systems repository, replacing the example image, database, storage settings, and available ports:

```yaml
vars:
  apps:
    portal:
      image: ghcr.io/example/portal
      web_ports: [8001, 8002]
      health_url_path: /healthz
      migration_command: npm run migrate
      jobs_command: npm run jobs
      jobs_connect_directly_to_postgres: false
      asset_directory: /app/web
      database_name: portal
      env:
        NODE_ENV: production
        DATABASE_SSL: "false"
        COOKIE_SECURE: "true"
        JOBS_PAUSED: "true"
        ARCHIVE_DAILY_UTC_TIME: "00:00"
        S3_ENDPOINT: https://s3.example.com
        S3_REGION: auto
        S3_BUCKET: example-portal-uploads
        S3_FORCE_PATH_STYLE: "true"
      secrets_from_vault: [S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY]
      production_uploads_r2_bucket: example-portal-uploads
```

Use the selected destination's real S3 endpoint, region, addressing mode, and fresh bucket-scoped keys.
The Stack supplies `DATABASE_URL`, `PORT`, and `WEB_CONCURRENCY` through its normal configuration.
The copied Node helper finds a writable database server without replaying uncertain requests.
The jobs use transaction-scoped row locks, so `jobs_connect_directly_to_postgres` is false.
The source's external B2 bucket must not remain the destination store if the migration claims a complete storage move.

Keep JOBS_PAUSED=true for exact restore checks. Change JOBS_PAUSED=false and deploy only when destination execution is explicitly selected.
A jobs container restart applies the setting. Multiple containers can overlap because report rows and daily occurrences are protected by PostgreSQL transactions.

## Cutover, rollback, and cleanup

Before production cutover, prove two actual app servers, database-primary switching without app restarts, PgBouncer, real destination bucket privacy, and Stack backup/object recovery.
The standalone rehearsal and same-machine web instances do not prove those outcomes.
Run a migration-only restore check before fixture-dependent assertions in the first Stack deployment.

Repeat the approved source write freeze and final export before moving real traffic.
Verify exact destination rows and bytes before resuming jobs and clock work.
Record measured downtime, pending/completed states, final source time, and the selected execution location.

Before destination writes, rollback can return traffic and execution to the frozen source.
After destination writes, reconcile new records, files, job outputs, and occurrences before rollback.
Never resume both source and destination work against separate copies of pending jobs.

After verified completion, delete the owned Heroku source app and verify the app and add-ons are absent.
Delete only the dedicated source bucket's objects, including retained versions or delete markers when the provider keeps versions.
Verify both the current-object and version listings are empty.
The bucket/key owner then deletes the bucket and scoped access key.
Keep protected exports and the original code revision for the named recovery or later deployment step.

## Fill a laptop or staging with test data

The command fills a developer's laptop database or staging with invented test data.
After the guide's local database and bucket setup, run migrations and start the app.
Set `APP_URL` to that app and supply `FIXTURE_PASSWORD`, then run from `app/`:

```sh
APP_ENV=development npm run seed-test-data
```

For staging, use `APP_ENV=staging` with its own database and bucket.
`npm run seed-test-data -- --accounts 200000` makes enough rows to show slow queries.
The count includes the two fixed accounts. Extra accounts use bulk SQL through
`DATABASE_URL`; they get one record each and no files or report jobs.
Reruns add missing rows, and a smaller count removes nothing.
