# Supabase exit example

This example moves the included customer portal's Supabase services onto Postgres and private S3-compatible storage.
Read the [migration guide](../../../docs/app-platform-migrations/from-supabase.md) before exporting or changing traffic.
The [design](design.md) explains the service replacements and data mapping.

## Commands

Use Node.js 24 and PostgreSQL 17 tools. Install and build with `npm ci` and `npm run build`.
Keep private runtime values in a mode-600 file outside the repository.
`environment.example` names every destination setting. Replace every `REPLACE_` value and the example hostnames.

```sh
node --env-file=/secure/portal.env operations.mjs migrate
node --env-file=/secure/portal.env operations.mjs import
node --env-file=/secure/portal.env web.mjs
node --env-file=/secure/portal.env operations.mjs jobs
```

The import requires an empty destination and a pre-created private S3 bucket.
Both job flags remain false during preparation. After cutover, set only the chosen destination's flags to true.
The Node cluster uses `WEB_CONCURRENCY` to select worker count. Workers share the instance's `PORT`.
`seed-test-data` fills a developer's laptop database or staging with invented test data.
After setting up the local database and bucket, run migrations and supply `FIXTURE_PASSWORD` at runtime.
It must contain at least 8 characters and at most 72 UTF-8 bytes:

```sh
APP_ENV=development npm run seed-test-data
```

Use `APP_ENV=staging` for staging. `npm run seed-test-data -- --accounts 200000`
makes enough rows to show slow queries. The count includes the two fixed accounts.
Extra accounts get one owned record each, no documents and no report jobs.
Reruns leave existing fixture accounts and generated test accounts unchanged.
A larger count adds only missing accounts and records; a smaller count removes nothing.

The command refuses before changing rows or uploading files when any account has
an email outside the fixed fixture or generated test-account names. This guard
keeps test data out of a database that holds other data, while allowing laptop
reruns. Never use a production export to fill a laptop or staging database.

## Synthetic rehearsal

Provision an empty PostgreSQL 17 database and an unused local port for S3rver on a Linux test host.
The test starts its own S3rver and two web processes, then stops those processes.
Set `DATABASE_URL`, `PUBLIC_ORIGIN`, `PORT`, `S3_ENDPOINT`, `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY`.
For S3rver, use access key and secret `S3RVER`. Its endpoint must use an unused loopback port.
Set `EXPORT_SNAPSHOT_FILE`, `EXPORT_OBJECT_DIR`, `FIXTURE_PASSWORD_FILE`, `REHEARSAL_S3_DIR` and `REHEARSAL_RESULT_FILE`.
Use the real synthetic source export and the original fixture password file. No source service is contacted during rehearsal.

```sh
node --env-file=/secure/rehearsal.env tests/rehearse.mjs
```

The test changes only its dedicated database and bucket. A second run needs a fresh database and bucket.
The test proves migration compatibility while two web processes keep running, import, original passwords, ownership, byte equality and logout.
The test also proves concurrent reports, interrupted transactions, schedule uniqueness and graceful web shutdown.

For backup recovery, create another empty database and a distinct bucket name.
Add `RESTORE_DATABASE_URL`, `RESTORE_S3_BUCKET`, `RESTORE_DUMP_FILE` and `RESTORE_RESULT_FILE` to the rehearsal environment.
Keep the original rehearsal database and S3 directory for this check.

```sh
node --env-file=/secure/rehearsal.env tests/restore-proof.mjs
```

The restore check proves every table, existing sessions, original passwords, private file bytes and pending work after a logical restore.
See [the test record](test-record.md) for the measured results and remaining boundaries.

## Acceptance contracts

- Native source services are inspected and exported before conversion. Code export alone is insufficient.
- Import preserves UUIDs, owner mapping, supported password verifiers, private file references, pending jobs and completed outputs.
- Every request uses the authenticated owner. Guessed IDs and forged owner values cannot expose or change another user's data.
- Both users log in with existing passwords. Sessions work across web instances and logout revokes access across those instances.
- Report claiming and completion are transactional. Interrupted work remains available and concurrent workers cannot complete a job twice.
- Database recovery and private file recovery are checked separately. A retained Supabase dependency cannot be called a full exit.
- Unsupported auth methods, unmapped columns and unmapped schedules require an explicit design before import.
- A phase-1 result states its unproved deployment, primary-switch and real-bucket boundaries.

- Test-data seeds accept only `APP_ENV=development` or `APP_ENV=staging`, preserve their fixture on reruns, and refuse unrelated accounts without changing rows or files.
