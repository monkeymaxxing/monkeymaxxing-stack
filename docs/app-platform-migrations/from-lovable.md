# Move a Lovable portal to your own system

Keep the generated TanStack pages, export every backend component, and rehearse with a new Postgres database and private S3 bucket.

This guide covers the matching customer portal in [the example](../../examples/app-platform-migrations/from-lovable/README.md). Another generated app needs an inventory and conversion of its actual service calls.

Read [the file and service map](../../examples/app-platform-migrations/from-lovable/design.md) first. The map explains every generated file, the request paths, database policies and managed services.

Phase 1 ends after export and an independent rehearsal. Keep source hosting and data intact. Deployment and cutover require a separate phase.

## What changes

The source uses Lovable Cloud for auth, PostgreSQL, private files and scheduling. The example replaces those managed interfaces with Node, Postgres and S3.

| Part | Source | Independent destination |
| --- | --- | --- |
| Pages | TanStack Start and React | Generated pages retained, service calls changed |
| Auth | Managed email/password API and JWTs | Preserved bcrypt hashes and shared PostgreSQL sessions |
| Records | Browser REST requests and database RLS | Server API with authenticated owner checks |
| Private files | Managed storage policies and signed URLs | Server-checked ownership and private S3 signed URLs |
| Reports | SQL function, customer-triggered execution | Transactional PostgreSQL queue, customer trigger and separate jobs command |
| Maintenance | Paused cron schedule | Preserved schedule metadata, explicit maintenance command |
| Database connections | Managed API | Stack's primary-discovery driver |
| Migrations | Exported Drizzle records and SQL | Separate ordered destination migrations, with source history retained |

The converted server has no Lovable backend URL. Google-hosted fonts remain an optional presentation dependency. Operating auth, sessions and the server becomes your responsibility.

## Prepare private exports

The person opens the intended project in Lovable. The agent records the app URL, project ID, framework, lockfile hash and observation time privately.

The person must already have project-management access. Stop for the person at sign-in or account verification. Do not use paid features to bypass verification.

The agent creates a private export directory outside Git:

```sh
umask 077
mkdir -p /path/to/private-export/code /path/to/private-export/objects
```

Use actual absolute paths in place of `/path/to/private-export`. Every export containing rows, identities, hashes or configuration values must have mode `600`.

Record pending source changes before exporting. For example, a requested description field is not exported data until the live schema and rows contain the field.

### Export code without paying

GitHub sync is a free export route. If GitHub requests verification, the person must complete verification before the agent continues that route.

A free alternative worked in the Code view. Expand all folders and inventory every file, including root files below the initial viewport.

Select each text file and use **Copy file content**. Save the exact text at the original relative path. Download binary assets using **Download**.

An agent using browser automation must use a tab-local clipboard. Do not overwrite the person's system clipboard. Wait until the selected file's content has loaded before copying.

Individual file downloads also worked on Free. Bulk ZIP export is a different feature. Do not assume bulk download entitlement from an individual download.

Keep `.env` private. Inventory its variable names without printing values. Keep the original `bun.lock` even when the destination uses npm.

Hash every exported file and record the file count. If no source commit exists yet, the manifest identifies the exported source snapshot.

Run the static inspector from the Stack repository root:

```sh
node examples/app-platform-migrations/from-lovable/inspect-project.mjs /path/to/private-export/code
```

`tanstack-start-server` requires server hosting. A static file server cannot execute Account or report server functions. The inspector does not prove a working build.

### Export the full database

Open **More → Database → Manage → Settings**. Under **Export project data**, select **Export data**, then **Export**, then **Start export**.

The native export saves an archive in Cloud storage and sends the platform's standard download email. Record the export time and retain the source database.

Open **More → Storage**. Open the database-export bucket and select the archive's **File actions → Download**.

The observed download was a ZIP wrapper despite the displayed `.backup` filename. Inspect the actual format before choosing a restore command.

The [official export instructions](https://docs.lovable.dev/features/database-backups) document the whole-database export and separate storage download. Check the project's current export availability and cooldown before a final freeze.

Use a PostgreSQL client capable of reading the archive. The default PostgreSQL 15 client rejected archive version 1.16. PostgreSQL 18's client read the observed archive.

The helper accepts the ZIP wrapper or the extracted `.backup`. The helper renders SQL to memory and reads COPY rows without executing source SQL:

```sh
python3 examples/app-platform-migrations/from-lovable/read-export.py \
  /path/to/private-export/database-download \
  /path/to/private-export/snapshot.json \
  --pg-restore /path/to/postgresql/bin/pg_restore
```

The output file is created exclusively with mode `600`. An existing output path is refused. Do not overwrite the original archive to rerun a conversion.

The helper requires the matching portal tables, auth rows, storage metadata, cron rows and migration history. Unsupported identity providers, password formats, MFA, passkeys or unconfirmed accounts stop conversion. Design those account flows before migrating such users.

Preserve the whole archive too. The reduced snapshot excludes source sessions and provider tokens. The whole archive remains the source evidence for omitted managed schemas.

### Export private files

Open the private `documents` bucket. Download every object, including objects without a document row. Preserve each full object key and its owner.

Native Storage downloads wrapped text files in ZIP. Unpack the actual object bytes before hashing. Hashing the ZIP produces a different value.

Place each file under `objects/<original object key>`. For example, preserve `<user UUID>/<file UUID>/barbara-note.txt` exactly.

Compare object metadata with `storage.objects` and application document rows. Record object key, content type, byte count, SHA-256, bucket privacy and owner mapping.

The synthetic fixture has two files, each exactly 27 UTF-8 bytes including LF:

| File | Exact text before LF | SHA-256 |
| --- | --- | --- |
| `barbara-note.txt` | `Barbara synthetic document` | `05fc126dc203e0579d73a6365e130ba77d1f422d87042b362456a2885029d32a` |
| `michael-note.txt` | `Michael synthetic document` | `784483c538543c904f1232e9c939417711e771b531e3f04c3d45f6699ad65c55` |

### Export operational state

Open **More → Settings → Secrets**. Save names only. Never paste secret values into a report, browser log or repository.

The observed native list contained `LOVABLE_CRON_SECRET` and `LOVABLE_API_KEY`. The file map distinguishes injected settings, public browser values and unused helper inputs.

Inspect **Database → Manage → Jobs**. Record schedule name, expression, timezone, active state, command, last run and next run when available.

Use the archive's `cron.job` row to confirm dashboard state. The observed maintenance job was paused at `0 3 * * *`, UTC, with no run history.

Save every pending and completed job, including output and attempt count. The observed source has two pending jobs and no completed jobs.

Do not run a source report to create completed evidence. Test completed reports only at the rehearsal destination.

## Compare before conversion

Compare actual exported values with the source inventory. Counts alone cannot detect wrong ownership or changed titles.

Check every user UUID and email, record UUID/title/owner, document UUID/key/hash/owner, report UUID/state/output, migration row and schedule definition.

Verify actual file bytes separately. Neither a database archive nor storage metadata contains the private object bytes.

Keep the comparison in a private test record. Record missing values as missing. Do not invent deferred descriptions or completed job output.

## Prepare the independent app

Copy `examples/app-platform-migrations/from-lovable/app/` into the destination app repository. The directory contains the converted generated pages and the replacement backend.

Use Node 24 and a PostgreSQL 17 database. Supply a private S3-compatible bucket. Keep every rehearsal resource separate from production.

The destination database must be empty. The importer refuses existing accounts or records. Reconcile source RUNNING jobs before import because uncertain in-flight work cannot be silently requeued.

Copy `settings.example.env` to a private file outside the repository. Replace every marked value. The file contains these required settings:

| Name | Value |
| --- | --- |
| `PUBLIC_ORIGIN` | Exact browser origin, including scheme and any non-default port. Used to reject cross-site writes. |
| `HOST` | Listening address, such as the assigned private app-server address. |
| `PORT` | Assigned web port. |
| `WEB_CONCURRENCY` | Positive count of web worker processes. |
| `DATABASE_URL` | Stack primary-discovery URL, including every database server. |
| `S3_ENDPOINT` | R2-compatible S3 endpoint. |
| `S3_REGION` | `auto` for R2, or the service's region. |
| `S3_BUCKET` | Private destination bucket. |
| `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | Bucket-scoped server credentials. |

Use HTTPS for a real customer origin. HTTPS origins enable Secure cookies. Plain HTTP is limited to an isolated local rehearsal.

Quote shell values containing `&`, spaces or other shell characters. The example quotes `DATABASE_URL` because database query parameters contain `&`.

Load the private file without printing values:

```sh
set -a
. /path/to/private-settings.env
set +a
npm ci
NITRO_PRESET=node-server npm run build
```

Run commands from the copied app directory. Keep package caches in your temporary directory when required by your environment.

The example updates the added S3 SDK to avoid the older SDK's affected XML parser.

The tested source [Vite](https://github.com/advisories/GHSA-9jrq-w75r-8gcw) and [Zod](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5) versions retain high-severity registry advisories. The production command runs built Nitro, and the portal has no direct Zod imports.

Review those advisories before public exposure or enabling new code paths. Keep Vite development and the S3 substitute private. The Dockerfile removes development dependencies after building.

The source lockfile remains with the export. `package-lock.json` pins the converted app's dependencies. New backend packages are pg, bcryptjs and the AWS S3 SDK.

`migrate` uses a session advisory lock and transactional SQL. Give migration operations a direct PostgreSQL session, rather than a transaction-pooling proxy.

Import before starting workers:

```sh
npm run migrate
node operations.mjs import /path/to/private-export/snapshot.json /path/to/private-export/objects
npm start
```

The importer preserves user, record, document and job UUIDs. The importer verifies file hashes before copying and downloads destination objects to verify byte equality.

Imported schedules remain metadata, so import never enables a scheduler. Do not start `npm run jobs` during this read-only source rehearsal.

The example matches the source fixture's disabled email confirmation. Email verification, password-recovery delivery and MFA need separate implementation before offering those flows.

A new login uses the imported bcrypt hash. The app does not need a password reset for the verified email/password fixture. Old source sessions do not transfer.

The destination's second migration adds `records.description` with an empty default. Empty descriptions preserve the exported source state.

## Run the complete synthetic rehearsal

The automated rehearsal requires the exact Barbara/Michael synthetic source and the shared fixture password in a private file.

Stop any web processes started by the manual import path. Give the automated rehearsal another empty database, because the manual import populated the first database.

Use a separate private bucket. The test starts two local web servers on ports 8001 and 8002.

The test writes new destination records and completes imported destination jobs. Never run the rehearsal against a customer production database.

Set the following paths in the private settings file, then reload the file:

```sh
REHEARSAL_SNAPSHOT=/path/to/private-export/snapshot.json
REHEARSAL_OBJECT_DIR=/path/to/private-export/objects
REHEARSAL_PASSWORD_FILE=/path/to/private-fixture-password
REHEARSAL_RESULT_FILE=/path/to/private-rehearsal-result.json
```

Run:

```sh
npm run rehearse
```

The test applies migration 1, imports the snapshot, starts the previous schema's web servers, then applies migration 2 with those processes running.

The test checks retained passwords and UUIDs, shared sessions, two-way ownership refusals, CRUD, S3 uploads/downloads, logout, transactional jobs and repeated migrations.

The result file records versions and each passed check. A failing check stops completion. Save logs privately and correct the failure before calling the migration ready.

For a local protocol substitute, run S3rver on the rehearsal machine. Add these settings to the private rehearsal file:

```sh
S3_ENDPOINT=http://127.0.0.1:4569
S3_REGION=us-east-1
S3_BUCKET=portal-rehearsal
S3_ACCESS_KEY_ID=S3RVER
S3_SECRET_ACCESS_KEY=S3RVER
REHEARSAL_S3_DIR=/path/to/private-s3-rehearsal
```

`S3RVER` is S3rver's public test credential, never a production credential. Replace the directory path, then reload the private file.

Start the substitute before `npm run rehearse`. Stop only the process you started after the test:

```sh
node s3-rehearsal.mjs > /path/to/private-s3.log 2>&1 &
S3_REHEARSAL_PROCESS_ID=$!
npm run rehearse
kill -TERM "$S3_REHEARSAL_PROCESS_ID"
```

The script creates the bucket named by `S3_BUCKET`. Check the private service log for readiness before starting the app test.

S3rver proves API and byte handling. S3rver does not prove R2 permissions, private bucket policy, or public signed-URL reachability.

## Phase 2: deploy and cut over later

The local rehearsal does not prove Stack deployment, actual R2 authorization, primary switching or two physical app servers. Keep those checks visibly open.

Build the supplied Dockerfile and record the image digest. Configure the Stack with `/healthz`, `npm run migrate`, `npm run jobs`, the app settings and bucket.

Set the first restore drill to check migrations only. Add data checks only after importing data. Follow the Stack's deploy and switchover procedures.

During a planned switchover, leave web and job processes running. Record errors and the first successful write through the unchanged database URL.

For final cutover, freeze source writes, uploads, webhooks and job triggers. Reconcile in-flight work, then take the final database and object export.

Restore with destination workers stopped. Compare rows and file hashes again. Switch traffic, then enable exactly one report execution location.

Keep the source maintenance schedule paused unless the recorded operating decision enables the replacement. Test overdue work and avoid duplicate external side effects.

Block the destination from old Lovable backend endpoints in an isolated check. Verify login, server functions, records, private files and reports with the source unavailable.

Before destination writes, rollback can return traffic to the intact source. After destination writes, freeze and reconcile changed rows, files, accounts and jobs before returning.

Keep the source until the rollback window closes. Source removal is a separate destructive action. A fresh agent must replay the guide before marking the item finished.

## Fill a laptop or staging with test data

The command fills a developer's laptop database or staging with invented test data.
Use the guide's local database and bucket settings and run migrations first.
Supply `FIXTURE_PASSWORD` and run from `app/`:

```sh
APP_ENV=development npm run seed-test-data
```

For staging, use `APP_ENV=staging` with its own database and bucket.
`npm run seed-test-data -- --accounts 200000` makes enough rows to show slow queries.
The count includes the two fixed accounts. Extra accounts get one owned record each
and no documents or report jobs. Reruns add missing rows; a smaller count removes nothing.
