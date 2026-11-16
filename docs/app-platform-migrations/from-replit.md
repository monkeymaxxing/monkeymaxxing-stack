# Move a Replit app to your own system

## Variances and guidance needs

This guide rehearses moving a Replit customer portal to PostgreSQL and S3-compatible storage.
The example keeps existing accounts, passwords, ownership, private files, jobs, and schedules.
The [working files](../../examples/app-platform-migrations/from-replit/) are a complete destination app.

The tested source used Replit's **development** database and development preview.
Publishing had failed on the free plan. No public source deployment is claimed.
Development and published production databases are separate. Identify the populated database before exporting.

The tested source used custom bcrypt authentication. Existing password hashes transfer unchanged.
Neither inspected source app used Replit Auth. A managed-auth exit remains untested.

Replit App Storage uses a different API from S3.
A database dump includes file references, but excludes file bytes.
The export script downloads every object and checks each document against its database hash.
SDK 1.0.0 returned a Buffer tuple during the rehearsal. The exporter accepts that verified return type.

The tested source ran PostgreSQL 16.10. The rehearsal destination uses PostgreSQL 17.
Use a `pg_dump` version compatible with the source and restore into the same or a newer PostgreSQL major version.
The tested exports required no upgrade, payment, or Agent credits. Provider limits can change.

The daily archive task lives in the database and runs in the job process.
No Replit Scheduled Deployment was present. Inventory provider schedules separately for another app.

Phase 1 leaves the source unchanged except export files. Phase 1 does not switch traffic or stop the source.
The [test record](../../examples/app-platform-migrations/from-replit/test_record.md) separates rehearsal evidence from live deployment checks.

## What you and your coding agent do

You identify the source environment and approve the later cutover window.
Your coding agent exports the source, restores an isolated destination, and checks returning users and private files.
Keep the source running until the later cutover has passed its checks.

A snapshot is a consistent view of the database at one moment.
The exporter uses one snapshot for `pg_dump` and the row audit.
Object storage has no shared database snapshot. A final cutover requires paused writes before exporting SQL and objects.

## Prepare the source inventory

Ask your agent to record:

- The project URL, project ID, Git revision, lockfile, runtime versions, and populated database environment.
- User IDs, account identifiers, password-hash format, identity issuer/subject pairs, and session storage.
- Record IDs and owners, file keys and SHA-256 values, pending jobs, completed output, schedules, and pause controls.
- Secret **names**, service connections, OAuth callbacks, webhooks, and external scheduled tasks. Do not print secret values.

A SHA-256 value is a checksum used to compare file bytes.
Keep exports outside Git, inside an encrypted working location. Exports contain password hashes and session records.
Set export directories to mode `700` and export files to mode `600`.

The tested app stores custom identities as `(issuer, subject, user_id)`.
Preserve existing rows, even when the issuer names Replit. Existing ownership refers to stable application UUIDs.
New registrations use `AUTH_ISSUER`, whose default is `urn:portal:password`.

For a real Replit Auth or Clerk source, inspect actual identity rows and provider export capabilities.
Record issuer, subject, stable application ID, verification state, OAuth links, MFA requirements, and recovery paths separately.
Never match identities by email alone. Confirm the mapping through a returning user's owned records.
Managed providers may not expose password verifiers or portable sessions.
Use a tested account-linking or password-reset flow when credential export is unavailable.
Keeping managed authentication after moving code is a partial platform exit.
See Replit's [identity migration guidance](https://docs.replit.com/features/auth-and-identity/plan-custom-auth-migration).
That guidance concerns migration into Clerk and establishes no verified export route from managed authentication.

## Export through the native Replit Shell

Open the correct project and choose **Shell** from the tool picker.
Use the Shell in the populated development environment for this example.
Do not substitute a production database unless production holds the records you intend to move.

Copy `scripts/export_replit.mjs` from the working files into the source project root as `export_replit.mjs`.
The source needs its existing `pg` and `@replit/object-storage` dependencies installed.
The tested source pins SDK version `1.0.0`.

Check `git status --short`. Commit intended application changes before exporting, using your team's normal review process.
`git archive` exports committed files only. Review untracked and ignored files separately for required application assets.
Do not add credentials to Git.

Run from the source project root:

```sh
umask 077
pg_dump --version
export EXPORT_DIR=migration-export
node export_replit.mjs
```

Expected output starts with `EXPORT_COMPLETE`.
The script refuses an existing export directory, so use a fresh directory for each snapshot.
A failure leaves a private partial export. Investigate the failure before using any partial file.
The script performs no source database or App Storage writes.

The export contains:

| File | Contents |
| --- | --- |
| `source.zip` | Git revision, application code, migrations, and lockfile |
| `database.dump` | Custom-format PostgreSQL dump without source roles or grants |
| `tables.json` | Full public-table audit, including users, hashes, sessions, jobs, and schedules |
| `objects/<sha256>` | Every listed App Storage object's bytes |
| `manifest.json` | Revision, versions, table counts, object keys, checksums, and environment variable names |

`secret_env_names` lists all environment variable names. The list includes ordinary runtime names as well as secret names.
Compare the list with the project's Secrets tool and application configuration.
Provision destination credentials separately. Replit-managed storage credentials are not portable.

Transfer the export directory with the project file download tools or a protected archive.
For a small fixture, an authenticated Shell can transfer an archive in base64 chunks.
Decode chunks directly into a protected local file. Never paste exports into chat or reports.
Check the archive checksum before extraction, then check every manifest checksum.
The rehearsal used native `git archive`, native `pg_dump`, and SDK downloads without a paid plan.
The documented [App Storage SDK](https://docs.replit.com/cloud-services/storage-and-databases/object-storage/typescript-api-reference) describes the storage methods.

## Prepare an independent destination

Use a disposable PostgreSQL 17 database and a private S3-compatible bucket for the rehearsal.
Do not restore into an existing database. Restoring SQL can overwrite or conflict with existing data.
Use dedicated credentials with access only to the rehearsal database and bucket.
The rehearsal uses S3Mock for isolated S3 API checks. Real R2 authorization needs a separate live test.

Copy the working directory into your app repository.
The destination uses Node.js 24.22.1, Express, `pg`, bcryptjs, and the AWS S3 SDK.
The destination imports no Replit package during normal operation.
The exporter remains a source-only script and needs the source's SDK.

Create a protected destination environment file from `environment.example`.
Replace every `REPLACE_WITH_...` value and the example database hosts.
Keep credential values in your deployment's protected environment or secret manager.
Do not commit the completed environment file.

Required destination settings:

| Setting | Meaning |
| --- | --- |
| `DATABASE_URL` | PostgreSQL URL, with every Stack database server and `target_session_attrs=read-write` |
| `S3_ENDPOINT`, `S3_REGION` | S3 API endpoint and signing region; R2 uses region `auto` |
| `S3_BUCKET` | Private destination bucket |
| `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | Destination bucket credentials |
| `PORT`, `WEB_CONCURRENCY` | Web port and worker-process count |
| `AUTH_ISSUER` | Issuer for new local password identities |
| `APP_ENV` | `production`, or `staging` for invented test data |

The app sends all database operations to the primary.
`pg_with_multiple_database_servers.mjs` selects the writable database server when opening a connection.
The app never automatically repeats a failed HTTP mutation with an uncertain commit.
After an ambiguous error, inspect the record or job before repeating the action.

Build the image from the copied working directory:

```sh
podman build -t localhost/portal-from-replit:rehearsal .
```

For a different CPU architecture, add `--platform linux/amd64` when building for AMD64 servers.
Keep the build result and source revision in your test record.

## Restore and rehearse

Run PostgreSQL client commands with destination connection settings supplied privately through `PGHOST`, `PGPORT`, `PGUSER`, `PGDATABASE`, and `PGPASSWORD`.
For the restore, select one destination primary. Do not pass a multi-server URL directly to Node's ordinary `pg` client.
Set the database owner's role before restoring, then run:

```sh
pg_restore --no-owner --no-acl --exit-on-error --dbname "$PGDATABASE" migration-export/database.dump
```

Keep `worker_paused=true` and pause destination schedules while preparing a final cutover.
In this fixture, the source already has the worker paused. SQL restoration preserves source controls.
The phase-1 checks deliberately exercise workers only in the isolated destination.

Assume `destination.env` is a mode-600 file in your working directory.
Assume `migration-export/` is the transferred protected directory beside `destination.env`.
The one-shot import uses container user `0` to read protected export files. The production web process still runs as `node`.
Import file bytes and download the destination objects for exact comparison:

```sh
podman run --rm --user 0 --network host --env-file destination.env \
  -e EXPORT_DIR=/export -v "$PWD/migration-export:/export:ro" \
  localhost/portal-from-replit:rehearsal node scripts/verify_export.mjs
podman run --rm --user 0 --network host --env-file destination.env \
  -e EXPORT_DIR=/export -v "$PWD/migration-export:/export:ro" \
  localhost/portal-from-replit:rehearsal node scripts/import_objects.mjs
podman run --rm --network host --env-file destination.env \
  localhost/portal-from-replit:rehearsal node database.mjs
```

Expect `Imported and downloaded 2 objects with exact byte equality.` for the supplied fixture.
The migration command must preserve the restored ledger and all source row IDs.
Running the migration command again must change nothing.
The original migration checksums stay unchanged.

For the automated replay, use a fresh disposable restore.
The test mutates destination records, sessions, controls, schedules, and jobs. Never run the test against the live destination.
Use the original fixture password through `FIXTURE_PASSWORD`. Never write the password into a command or report.

The container excludes tests from the production image. Run tests through the Node image with the app source mounted.
Install dependencies in the disposable copy first:

```sh
podman run --rm --network host --env-file destination.env \
  -e npm_config_cache=/tmp/npm-cache -v "$PWD:/app" -w /app \
  docker.io/library/node:24.22.1-alpine npm ci --no-audit --no-fund
podman run --rm --network host --env-file destination.env \
  -e EXPORT_DIR=/export -e REHEARSAL_CONFIRM=disposable-destination \
  -v "$PWD:/app:ro" -v "$PWD/migration-export:/export:ro" -w /app \
  docker.io/library/node:24.22.1-alpine npm test
```

The test checks every restored row before changing destination data.
Checks cover existing-password login, stable IDs, cross-process sessions and logout, ownership refusals, CRUD, and private file bytes.
Queue checks cover concurrent claims, a killed worker's rollback, completion output, and the actual jobs command.
Schedule checks cover persisted due occurrences and concurrent processing.
Connection termination checks prove reconnection without restarting web processes.
Connection termination is not a real primary switchover.

The command fills a developer's laptop database or staging with invented test data.
Use the local database and bucket from the rehearsal steps, run migrations, then run:

```sh
APP_ENV=development node seed_test_data.mjs
```

Supply `FIXTURE_PASSWORD` at runtime. For staging, use `APP_ENV=staging` and a separate bucket.
Add `--accounts 200000` to make enough rows to show slow queries. The count includes the two fixed accounts.
Rerunning adds only missing data; a smaller count removes nothing. The command never imports production data.

## Prepare the Stack app entry

Use the [Stack app contract](../design.md#the-app-contract) and your systems repository's setup instructions.
The example's commands are:

| Purpose | Command |
| --- | --- |
| Web | `node web.mjs` |
| Migrations | `node database.mjs` |
| Jobs and persisted schedules | `node jobs_runner.mjs` |
| Laptop or staging test data | `node seed_test_data.mjs` |
| Health | `/healthz` |

Web processes do not run migrations, jobs, or schedules.
The Stack runs the migration command before switching the release.
Migrations use transaction-level advisory locks and a five-second lock deadline.
Jobs also use transaction locks, so `jobs_connect_directly_to_postgres` is `false`.
Set `asset_directory` to `/app/assets`. The portal embeds CSS and JavaScript in its HTML and needs no separate static assets.

Register the image, database name, two free web ports, commands, bucket, and S3 settings under `vars.apps.portal`.
Add S3 credential names to `secrets_from_vault` and pass the corresponding secrets through your app-server role calls.
Follow the existing app-secret mapping convention in the systems repository.
The Stack supplies `DATABASE_URL`, `PORT`, and the server's worker count.
Set `production_uploads_r2_bucket` to the destination bucket, so the Stack includes file bytes in upload backups.

For the first restore drill, use only:

```yaml
restore_drill_check_queries:
  - name: the_migrations_came_back
    sql: SELECT count(*) = 2 FROM schema_migrations
```

After the fixture exists, add account, ownership, document metadata, and job checks.
Download the restored objects separately and compare bytes. A successful SQL restore proves no object-storage recovery.

## Later live checks and cutover

Phase 1 does not authorize a live cutover. Your agent must complete the following checks on the destination system.

1. Deploy through the systems repository's ordinary release procedure.
2. Prove sessions and logout across two actual app servers.
3. Run `switch_database_primary` with unchanged app processes and URLs. Check fresh writes, owned reads, sessions, and worker recovery.
4. Run the Node database switchover check from the Stack skill. Repeat through PgBouncer if PgBouncer is enabled.
5. Prove real R2 permissions, private access, uploaded bytes, and independent upload recovery.
6. Restore database backups and check accounts, IDs, password verifiers, ownership, jobs, schedules, migration ledger, and file references.

For final cutover, pause source writes, drain in-flight requests, then stop source workers and schedules.
Take a final SQL snapshot and object export. Compare counts, ownership, hashes, and pending/completed work again.
Restore into the prepared destination while destination workers and schedules remain paused.
Enable exactly one execution location for jobs and schedules after the final data checks.
Switch traffic, sign in as a returning user, and check private downloads and owned records.
Confirm the destination works after stopping the source. Record measured downtime and the last accepted source write.

Before the destination accepts writes, rollback can return traffic to the unchanged source.
After destination writes begin, the old source is stale. Pause writes and reconcile changed rows and objects before reversing traffic.
Never enable workers on two independently restored databases. A row lock protects only workers sharing one database.
Keep exports until rollback and recovery checks pass, then dispose of exports through your team's protected-file cleanup process.
