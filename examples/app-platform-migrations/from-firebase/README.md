# Customer portal migrated from Firebase

This app runs Firebase-exported accounts, invoice records, private documents,
report jobs and a daily archive task on PostgreSQL and S3-compatible storage.
The app calls no Firebase service at runtime. Returning email/password users
keep their Firebase UID and password. Firebase browser sessions end at the
move; users sign in again and receive a PostgreSQL-backed session.

Read the [migration guide](../../../docs/app-platform-migrations/from-firebase.md)
for the source inventory, separate exports, freeze, cutover and rollback steps.
The example imports the guide's small portal. A different Firestore shape needs
an explicit table mapping before import.

## What moves

| Source | Destination |
| --- | --- |
| Firebase Auth UID and email/password verifier | `users` and `identities`, with stable text IDs; portable account export fields in `source_auth_users` |
| Project's modified-scrypt hash settings | Protected `firebase_auth_config` row |
| Firestore records and document metadata | `records` and `documents` tables |
| Every exported Firestore document and field | `source_documents` audit table |
| Storage object bytes | Private S3 bucket, keeping object keys and SHA-256 |
| PENDING, COMPLETED and ARCHIVED report documents | Durable `jobs` rows; ARCHIVED becomes COMPLETED with `archived=true`, retaining output |
| Daily UTC archive function and occurrence ledger | Separate jobs process and persisted PostgreSQL schedule |

The importer keeps disabled accounts disabled. It does not join accounts by
email. The Firebase issuer and UID identify each imported account. Exported
`admin: true` custom claims preserve access to the portal's global controls.
New registrations use bcrypt with cost 12. Imported users keep their modified
scrypt verifiers; the app uses Node's `crypto` library and the algorithm Firebase
publishes. A known-answer test uses Firebase's public synthetic vector.
The Admin SDK may return URL-safe base64 for password fields while the Firebase
CLI export uses standard base64. The supplied exporter normalizes the decoded
bytes to standard base64; compare decoded bytes when reconciling both exports.
A missing exported password hash stops the import and needs a reset plan.

## Export the source

Run the exporter on a trusted operator machine after completing the guide's
source freeze. The control flags alone do not stop direct Firebase SDK writes
or new Auth registrations; the guide also freezes those service boundaries.
Archive the reviewed source code separately, including dependency lockfiles,
Hosting settings, Functions, security rules and indexes, and exclude secrets.

`firebase-admin` is pinned as a development dependency for this source exporter.
The runtime container installs production dependencies only and does not need
Firebase credentials. Install the development dependencies on the operator
machine and use its authorized Application Default Credentials. A credential
file, when needed, stays outside the app directory.

```sh
npm ci --no-audit --no-fund
export GOOGLE_APPLICATION_CREDENTIALS=/secure/firebase-operator.json
export FIREBASE_PROJECT_ID=example-firebase-project
export FIREBASE_STORAGE_BUCKET=example-firebase-project.firebasestorage.app
export SOURCE_CODE_ARCHIVE=/secure/reviewed-source.tar.gz
export EXPORT_DIR=/secure/firebase-export
npm run export-firebase
npm run verify-export
```

Replace the example project and bucket with the source values. The exporter
reads all flat Firestore collections, Auth users and project hash settings,
private objects, and service setting names. The portable `users.json` fields
stay in `source_auth_users`; the separate full native CLI user export remains
a protected artifact, including native fields not mapped into this app. The
exporter compares object bytes with Firestore metadata and writes private files
with checksums. Nested Firestore collections
stop this small example so their table and ownership mapping can be made
explicit. Follow the guide for the additional native CLI Auth export and the
managed Firestore export; a source-code archive contains neither.

## Prepare a destination

Use Node.js 24 and PostgreSQL 17. Create an empty database and a separate private
S3 bucket. Supply the settings in `environment.example` through a protected env
file outside the source tree. Database URLs list all Stack database servers.
The copied PostgreSQL helper selects the writer; requests with uncertain commits
are never replayed automatically.

```sh
npm ci --no-audit --no-fund
set -a
. /secure/portal-destination.env
set +a
export EXPORT_DIR=/secure/firebase-export
npm run verify-export
npm run migrate
npm run import-firebase
npm run import-objects
```

The export directory holds `manifest.json`, `users.json`, `auth-config.json`,
`firestore.json`, `objects.json`, source code and object files. The manifest names
the source project, export time and SHA-256 checksums. Verify every export before
changing the destination. Keep the directory private: the user verifiers and
project signer key are secrets. Never put exports inside a build context.

`import-firebase` checks owner IDs and source object references. It imports the
accounts and database rows in one transaction and refuses a destination that
already holds app data. It preserves raw Firestore fields beside the mapped
rows, so the table conversion does not discard unmapped source data. Importing
objects separately verifies each upload by downloading the destination bytes.
Uploads use a conditional create to refuse overwriting an existing object; a
resumed import accepts an existing object only when its bytes already match.
If a later step fails, fix that step on the isolated destination; keep source
traffic frozen until the full verification passes.

The final source export must have `controls/runtime.worker_paused` and
`controls/runtime.scheduler_paused` set to true. The importer retains both
pauses and maintenance. In-flight source jobs must settle before export. The
example maps one schedule named `archive_reports`, at `0 0 * * *` in UTC.
Other schedules require their own mapping. Source occurrence timestamps become
`scheduled_runs.occurrence_at`; this source task records no archive count, so
those imported counts are zero and the original source document stays in the
audit table.

## Run the app

```sh
npm run web
```

Set `PORT` and `WEB_CONCURRENCY` for the web container. `/healthz` checks the
PostgreSQL connection and description migration. Run migrations as a separate
release step. When verification and cutover are complete, an administrator can
clear maintenance in the portal. Enable report and schedule processing only at
the destination, then run its separate process:

```sh
npm run jobs
```

Sessions live in PostgreSQL. A cookie works across web processes and logout
revokes the session for every process. Each record, document and report query
checks the owner. Private file downloads also verify the stored SHA-256 before
returning bytes. Uploads are limited to 1 MiB because the server buffers bytes in
memory. If a metadata write fails after upload, the private object stays for
manual reconciliation: the database write may have committed despite a lost
reply, so deleting the object could lose a referenced document. Queries have deadlines and web and jobs processes stop gracefully.
The worker claims jobs with `FOR UPDATE SKIP LOCKED`; output and completion
commit together. An interrupted transaction leaves work available. The daily
task archives completed reports older than 30 days and records each due UTC
occurrence once, even with concurrent workers.

The container runs as the `node` user. Use `Containerfile` to build it. Keep
secrets and exports outside the app directory; `.containerignore` and
`.dockerignore` exclude environment files and migration exports.

## Prove the migration in a disposable environment

The tests change data. Use a disposable destination database and bucket after
importing the protected export. Supply the original fixture password through a
protected environment file; never put it in a command argument or a test report.

```sh
npm run test:password
export REHEARSAL_CONFIRM=disposable-destination
npm test
```

The suite checks exported verifiers, stable identities, raw source documents,
owned rows and object hashes before exercising the app. It proves existing
password login, cross-process sessions and logout, owner isolation, CRUD,
private file bytes, safe retention after a forced metadata failure, new
registration, concurrent report claims, a killed job
transaction, the real jobs command and the persisted daily task. It also drops
existing database connections, records transient health failures and recovery
time within 15 seconds, then proves the same web processes retain sessions and
ownership and accept one fresh write. It never replays an interrupted write.
That connection test is not a live primary/replica failover proof.

Use another empty disposable database and bucket for staging checks. The suite
applies the first migration itself, creates an old-release row, then proves the
additive description migration and idempotent invented-data seed:

```sh
export APP_ENV=staging
npm run test:staging
```

`npm run seed-test-data` requires `APP_ENV=development` or `APP_ENV=staging`, and `FIXTURE_PASSWORD`. It never
reads a production export. Running it again preserves existing passwords,
records, private documents and jobs. It refuses `APP_ENV=production`.

After migrations, `APP_ENV=development npm run seed-test-data` fills a developer's
laptop database using its local bucket. The same command with `APP_ENV=staging`
fills staging. `npm run seed-test-data -- --accounts 200000` makes enough rows
to show slow queries. The count includes the two fixed accounts. Reruns add only
missing rows; a smaller count removes nothing.
