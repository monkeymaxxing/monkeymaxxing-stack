# Rehearse a Vercel app migration

## Variances and guidance needs

A code export does not move users, private files, jobs, or service settings.
This guide rehearses a complete service replacement before a separate production cutover.
The [copyable app](../../examples/app-platform-migrations/from-vercel/) runs a private customer portal outside Vercel.
The [test record](../../examples/app-platform-migrations/from-vercel/testing.md) lists proved behavior and remaining live checks.

| Source difference | Guidance and destination behavior |
| --- | --- |
| v0 builds code; Vercel hosts the app. | The tested source was hand-written on Vercel. The rehearsal proves Vercel service portability, without another v0 generation or purchase. |
| Neon PostgreSQL 18 supplied the source database. | Preserve the original `pg_dump` archive. Use matching version 18 clients to read the archive. The tested schema restored into PostgreSQL 17. |
| Managed Neon Auth owns users and password hashes. | Export `neon_auth` as well as `public`. Import password credentials into app-owned accounts. Users keep passwords and log in again. |
| Native auth sessions and signing keys belong to the old identity service. | Preserve native material privately in the archive. Destination sessions start empty and use revocable PostgreSQL rows. |
| Private Vercel Blob is separate from Postgres. | Export every object's bytes. Match object keys, lengths, and SHA-256 before importing into a private S3-compatible bucket. |
| Vercel Functions dispatch reports through `after` and `waitUntil`. | A permanent destination jobs process claims PostgreSQL rows with `SKIP LOCKED`. Report output and completion commit together. |
| Vercel Cron calls an authenticated HTTP route at 03:00 UTC. | The jobs process schedules daily archiving through a database lock and a unique UTC date. No public Cron endpoint or shared Cron secret remains. |
| Platform settings contain variables outside Git. | Save every variable name separately. Recreate destination secrets through the destination secret store. Never copy native credentials into the destination image. |
| Vercel supplies process scaling and networking. | The destination reads `PORT` and `WEB_CONCURRENCY`, exposes `/healthz`, and uses the Stack's multi-host PostgreSQL helper. |
| Edge, middleware, and image features vary between incoming apps. | This source uses Node handlers, with no Edge middleware, `next/image`, ISR, or Server Actions. No replacement was needed for absent features. |

The rehearsal uses invented accounts and documents. The rehearsal changes no source rows, source jobs, source schedule, DNS, or deployment.
Source and destination reports have no external side effects. Real customer queues need exclusive ownership during cutover.
No purchase or plan change is part of the export or rehearsal.
Existing account plans and provider transfer allowances still govern access.

## Prepare the export package

The person supplies an existing source export and authorizes read-only access when an export is incomplete.
The coding agent inventories the following artifacts before running the destination:

- Source code, Git revision, dependency lockfile, and `vercel.json`.
- A custom-format `pg_dump` containing `public` and `neon_auth`.
- Downloaded Blob objects, object keys, original filenames, byte counts, and SHA-256.
- Every source environment-variable name, including integration-generated names.
- Job state and completed output, Cron definitions, and the source's active processing behavior.
- A protected copy of the existing synthetic users' password for the login check.

Reuse existing verified exports. Re-export only missing artifacts.
For a missing database archive, load source database credentials into protected PostgreSQL environment variables.
Run a matching `pg_dump`, without putting a connection password in command arguments:

```sh
umask 077
pg_dump --format=custom --schema=public --schema=neon_auth \
  --file "$NATIVE_ARCHIVE"
```

`NATIVE_ARCHIVE` names the private archive file. PostgreSQL reads connection settings from the protected environment.
Keep the archive and password hashes outside Git, with directory mode `700` and file mode `600`.
The full archive can contain signing keys and session tokens.

For missing files, use the source's authenticated private Blob download path.
Compare the Blob list with all database document rows, including pagination.
Stop if an object is missing or a digest differs.
Save downloaded files under original filenames, or name each file with the file's SHA-256.
Use digest filenames when original filenames collide.

Save environment names in a non-secret JSON file:

```json
{"env_var_names":["DATABASE_URL","DATABASE_URL_UNPOOLED","NEON_AUTH_BASE_URL","NEON_AUTH_COOKIE_SECRET","BLOB_READ_WRITE_TOKEN","CRON_SECRET"]}
```

Add all integration-generated names from the project's environment inventory.
The verified source had 21 names, including `PG*`, `POSTGRES_*`, and `VITE_NEON_AUTH_URL` aliases.
The example JSON shows the app's six required names, rather than a complete project inventory.
Use the Vercel project environment API or dashboard to list names.
Discard values from reports and ordinary logs.

## Copy and build the portable app

Copy `examples/app-platform-migrations/from-vercel/` into your app repository.
Run the following commands from the copied app directory on your assigned Linux build host:

```sh
export npm_config_cache="${TMPDIR:-/tmp}/vercel-exit-npm"
export NEXT_TELEMETRY_DISABLED=1
npm ci
npm test
npm run build
```

Use Node 24. The build needs no database or storage credentials.
The lockfile pins Next.js 16.4.5 and the native-compatible password utility.
The app reuses the Next.js framework example's runtime, PostgreSQL helper, storage, and HTTP structure.
The portable browser forms and API paths replace the source UI and `/api/portal` routes.
Stable IDs are retained. Existing bookmarked API URLs need adaptation before a production cutover.

## Restore the archive for offline extraction

Use a new, isolated scratch database, separate from the destination app database.
The archive restore creates the original source tables in the scratch database.
The export command reads the scratch tables through a read-only transaction.
No source connection is needed when the existing archive is complete.

Supply the following paths through your protected process environment:

| Variable | Required value |
| --- | --- |
| `NATIVE_ARCHIVE` | Private custom archive containing the native schemas |
| `PG_RESTORE` | Path to matching version 18 `pg_restore` |
| `PRIVATE_EXPORT_DIR` | New protected directory for `native.sql`, `snapshot.json`, and `objects/` |
| `SOURCE_CODE_DIR` | Exported source directory containing `vercel.json` |
| `BLOB_EXPORT_DIR` | Previously verified downloaded object files |
| `SOURCE_ENV_NAMES_FILE` | JSON inventory containing `env_var_names` |
| `SOURCE_DATABASE_URL` | Protected connection URL for the isolated scratch database |

Convert the archive without exposing data in the terminal:

```sh
python3 scripts/prepare-archive.py
```

The script omits only the archive's redundant `CREATE SCHEMA public` entry.
A fresh PostgreSQL database already contains the `public` schema.
The script does not rewrite native table definitions or rows.
The script refuses an existing `native.sql` to protect prior exports.

Load scratch database connection settings into PostgreSQL's protected environment.
Verify the selected database is the newly assigned scratch database.
Then restore the SQL and create the canonical snapshot:

```sh
psql --set ON_ERROR_STOP=1 --file "$PRIVATE_EXPORT_DIR/native.sql"
npm run export-snapshot
```

The snapshot contains account hashes, stable IDs, owned data, jobs, schedule history, source migration history, and environment names.
Object files are copied under their SHA-256 names and checked against metadata.
The export refuses unsupported identity states, external identity providers, organizations, or an unexpected Cron schedule.
Add explicit mappings before migrating apps with those features.
A PostgreSQL downgrade is not generally guaranteed. Test each incoming schema on the chosen destination version.
See the [PostgreSQL export documentation](https://www.postgresql.org/docs/current/app-pgdump.html).

## Supply destination settings

The person assigns an empty destination PostgreSQL database and an empty private S3-compatible bucket.
The coding agent verifies database and bucket ownership before importing.
Do not use another app's database or bucket.

| Variable | Required value |
| --- | --- |
| `DATABASE_URL` | `postgresql://portal:PASSWORD@db01:5432,db02:5432/portal?target_session_attrs=read-write&connect_timeout=3` |
| `APP_ORIGIN` | Exact HTTPS origin, such as `https://portal.example.com`, without a trailing slash |
| `PORT` | Assigned free web port, such as `8007` |
| `WEB_CONCURRENCY` | Positive web worker count |
| `R2_ENDPOINT` | Private test S3 endpoint, or `https://ACCOUNT_ID.r2.cloudflarestorage.com` |
| `R2_BUCKET` | Bucket assigned only to this app and environment |
| `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | Credentials restricted to the assigned bucket |
| `PRIVATE_EXPORT_DIR` | Protected canonical snapshot directory |

The literal `PASSWORD` and `ACCOUNT_ID` values are placeholders. Store actual credentials in your protected environment or secret store.
Remove source credentials from the destination environment.
The destination needs no `NEON_AUTH_*`, `BLOB_READ_WRITE_TOKEN`, `CRON_SECRET`, or Vercel token.
Use a loopback S3 mock only for isolated tests. Real R2 authorization needs its own live check.

## Import without starting jobs

Keep destination web and job processes stopped while importing.
Run migrations and import the snapshot:

```sh
npm run migrate
npm run migrate
npm run import-snapshot
npm run import-snapshot
```

Expect two destination migration versions and a successful import.
The repeated import verifies storage and recognizes the identical snapshot.
A changed snapshot or populated destination without an import receipt is refused.
Do not modify `snapshot.json` after importing.

The import preserves account, record, document, and report UUIDs.
Native passwords remain unchanged. Source migration history stays in the import receipt.
Document keys remain unchanged. Conditional object writes protect existing object bytes.
A failed database import can leave verified objects in the assigned bucket.
An unchanged retry reuses identical bytes. Conflicting bytes cause a visible failure.

Native sessions are intentionally invalidated. Returning users must log in again.
If importing through a container, mount only the protected snapshot directory read-only.
Give the container's `node` user ownership of the mounted copy, while retaining directory mode `700` and file mode `600`.
Do not make credential exports readable by every local user.
No native signing key is used by destination authentication.
Password reset, social login, organization roles, and email delivery are outside this two-account fixture.

## Replay the source behavior

Use another fresh destination database and bucket for the automated rehearsal.
The rehearsal creates, edits, and processes synthetic destination data.
The rehearsal refuses an existing `accounts` table.
Supply `FIXTURE_PASSWORD` through the protected environment, without printing the value.
Select two unused local ports:

```sh
export TEST_WEB_PORTS=8041,8042
npm run test-rehearsal
```

The rehearsal runs migrations, imports twice, and starts two destination web processes.
The rehearsal uses each exported user's original password.
The rehearsal verifies stable IDs, ownership, descriptions, exact file hashes, cross-server sessions, jobs, scheduling, and logout revocation.
Only the rehearsal's child processes are stopped at completion.
The rehearsal leaves synthetic destination data for inspection.

Start a separate imported copy for a person to inspect:

```sh
npm run web
```

Use the HTTPS origin to log in with each existing account.
Confirm the account's record and file. Download the file and compare the original SHA-256.
A browser needs HTTPS because the session cookie uses `Secure`.
API tests explicitly send cookies to private HTTP ports.

After verifying the imported pending jobs, start the destination worker:

```sh
npm run jobs
```

The jobs process polls the queue and schedules daily archiving at or after 03:00 UTC.
The scheduler catches the current day's run after a late start.
Several workers share one unique daily row. Archiving and the schedule receipt commit together.
Archiving marks completed reports older than 30 days and retains report output.
To check the archive operation immediately on synthetic data, run:

```sh
node scripts/manage.mjs archive-reports
```

The command records a manual run without consuming the scheduled daily run.
A stopped worker's open transaction rolls back, leaving unfinished reports available.

## Check new destination behavior

Use another empty PostgreSQL database and private test bucket for the inherited framework suite.
Set `APP_ENV=staging` and the protected `FIXTURE_PASSWORD`.
Then run:

```sh
export TEST_WEB_PORTS=8051,8052
node tests/services.mjs
```

The suite checks registration, owned CRUD, uploads, concurrent and interrupted workers, additive migrations, deadlines, and graceful shutdown.
The test-data command is `npm run seed-test-data` and requires `APP_ENV=development` or `APP_ENV=staging`.
The seed must never replace an imported source dataset.

If the database service belongs entirely to your test guest, enable the restart check:

```sh
export TEST_DATABASE_RESTART_ARGV='["pg_ctlcluster","17","main","restart"]'
node tests/services.mjs
```

A database restart proves reconnection after disconnection. A restart does not prove a primary promotion.

## Prepare the later Stack deployment

Build the reviewed source on the target architecture:

```sh
podman build --build-arg RELEASE=REVIEWED_COMMIT \
  --tag ghcr.io/example/vercel-exit:REVIEWED_COMMIT .
```

The image runs as the unprivileged `node` user.
The image commands are `node scripts/web.mjs`, `node scripts/manage.mjs migrate`, and `node scripts/manage.mjs jobs`.
The coding agent adds another app to the existing systems repository.
Inventory existing ports, databases, buckets, vault entries, and release tags before editing.
Choose unused names and ports. The following example uses `vercel_portal` and ports 8007/8008.

Add this entry under the existing `vars.apps` mapping in `mmx_project_settings.yml`:

```yaml
vercel_portal:
  image: ghcr.io/example/vercel-exit
  web_ports: [8007, 8008]
  health_url_path: /healthz
  migration_command: node scripts/manage.mjs migrate
  jobs_command: node scripts/manage.mjs jobs
  jobs_connect_directly_to_postgres: false
  asset_directory: /app/.next/static
  database_name: vercel_portal
  env:
    R2_ENDPOINT: https://ACCOUNT_ID.r2.cloudflarestorage.com
  secrets_from_vault:
    - APP_ORIGIN
    - R2_BUCKET
    - R2_ACCESS_KEY_ID
    - R2_SECRET_ACCESS_KEY
  production_uploads_r2_bucket: example-vercel-exit-production
  restore_drill_check_queries:
    - name: the_migrations_came_back
      sql: select count(*) = 2 from schema_migrations where version in ('0001_portal.sql', '0002_record_descriptions.sql')
```

`asset_directory` must be `/app/.next/static`. The Stack mounts the current and
previous release's assets at that path. An old browser page can still fetch its
JavaScript after a release switch. Do not point the asset setting at an empty directory.

Provision private buckets and bucket-scoped keys through your existing account procedure.
Add production vault entries named `vercel_portal_database_password`,
`vercel_portal_APP_ORIGIN`, `vercel_portal_R2_BUCKET`,
`vercel_portal_R2_ACCESS_KEY_ID`, and `vercel_portal_R2_SECRET_ACCESS_KEY`.
Add separate staging entries with the prefix `staging_vercel_portal_`.
Production's bucket value must match `production_uploads_r2_bucket`.

In `playbooks/every_server.yml`, preserve existing entries. Add the database
password to production's database role input:

```yaml
database_passwords:
  vercel_portal: "{{ .secrets.vercel_portal_database_password }}"
```

Add the staging equivalent to staging's database role input:

```yaml
database_passwords:
  vercel_portal: "{{ .secrets.staging_vercel_portal_database_password }}"
```

Extend `app_secrets` for production's `app_server` and `jobs_server` role calls:

```yaml
vercel_portal_database_password: "{{ .secrets.vercel_portal_database_password }}"
vercel_portal_APP_ORIGIN: "{{ .secrets.vercel_portal_APP_ORIGIN }}"
vercel_portal_R2_BUCKET: "{{ .secrets.vercel_portal_R2_BUCKET }}"
vercel_portal_R2_ACCESS_KEY_ID: "{{ .secrets.vercel_portal_R2_ACCESS_KEY_ID }}"
vercel_portal_R2_SECRET_ACCESS_KEY: "{{ .secrets.vercel_portal_R2_SECRET_ACCESS_KEY }}"
```

For staging's `app_server`, retain the left names and use these staging values:

```yaml
vercel_portal_database_password: "{{ .secrets.staging_vercel_portal_database_password }}"
vercel_portal_APP_ORIGIN: "{{ .secrets.staging_vercel_portal_APP_ORIGIN }}"
vercel_portal_R2_BUCKET: "{{ .secrets.staging_vercel_portal_R2_BUCKET }}"
vercel_portal_R2_ACCESS_KEY_ID: "{{ .secrets.staging_vercel_portal_R2_ACCESS_KEY_ID }}"
vercel_portal_R2_SECRET_ACCESS_KEY: "{{ .secrets.staging_vercel_portal_R2_SECRET_ACCESS_KEY }}"
```

Extend `deployed_image_tags.staging`, `deployed_image_tags.production`,
`public_host_names.staging`, and `public_host_names.production` in `inventories/servers.yml`.
Each mapping needs a `vercel_portal` entry. Use the reviewed image's full commit tag
and your distinct public host names. Follow your initial setup's account steps
to add tunnel routing and Access protection for staging. Preserve existing app routes.

Run `mmx validate` in the systems repository. Review the resulting changes and
the app's checklist entries with the person before applying configuration.
Use the existing `every_server` procedure to create the additional database,
settings, and containers. Read MMX's result before continuing.

Follow `operating_procedures/deploy_and_roll_back_an_app_release.md` for staging,
the production release and its approval setting, and rollback. The ordinary deploy command is:

```sh
./server_management_scripts/run_mmx_on_util01 run deploy --var environment_name=staging
```

That command deploys the selected environment's configured releases. Check every
app's requested tag first. A shared environment must not contain another app's
unapproved pending tag.

Use `asset_directory: /app/.next/static` so old browser bundles survive a release switch.
The first restore check covers migrations only. Add data checks after the import is verified.

No production deployment is part of phase 1.

## Keep cutover and rollback explicit

Phase 2 requires the person's approval and the shared Stack system.
Freeze source writes and explicit job dispatch before taking final exports.
Disable the source Cron schedule before destination scheduling becomes authoritative.
Import the final snapshot into a fresh destination, then verify all account, row, object, and job mappings.
Switch traffic only after the final checks pass.

Prove the destination works with source services inaccessible.
Keep app processes running through real primary switches in each direction.
Check HTTP sessions, unique writes, private downloads, and report output after reconnecting.
Repeat through transaction-mode PgBouncer if enabled.
Restore the database and objects independently, then compare the saved manifest.

Before destination writes begin, rollback can return traffic to the unchanged source.
After destination writes begin, source and destination differ.
Rollback then requires reconciling destination changes before returning traffic.
Never blindly repeat an uncertain write or restore an old snapshot over newer data.
Record actual downtime, remaining data gaps, and rollback boundaries during the live cutover.

For incoming apps using images, middleware, caching, or Server Actions, inventory every dependency before cutover.
Follow the [Next.js self-hosting guide](https://nextjs.org/docs/app/guides/self-hosting) for shared caches, action keys, and release skew.
The [private Blob documentation](https://vercel.com/docs/vercel-blob/private-storage) explains why object credentials and bytes need separate export.

## Fill a laptop or staging with test data

The command fills a developer's laptop database or staging with invented test data.
Use the guide's local database and bucket settings and run migrations first.
Supply `FIXTURE_PASSWORD` and run:

```sh
APP_ENV=development npm run seed-test-data
```

For staging, use `APP_ENV=staging` with its own database and bucket.
`npm run seed-test-data -- --accounts 200000` makes enough rows to show slow queries.
The count includes the two fixed accounts. Extra accounts get one owned record each
and no documents or report jobs. Reruns add missing rows; a smaller count removes nothing.
