# Move from Render to your own system

## Variances and guidance needs

This guide rehearses moving a Render customer portal to PostgreSQL 17 and S3-compatible storage.
The [working example](../../examples/app-platform-migrations/from-render/) keeps accounts, existing passwords, ownership, documents, reports, and schedule state.
S3-compatible storage stores files through the same API as Amazon S3.
The source was handwritten Node.js/Express code in a private Git repository.
The destination pins AWS SDK 3.1161.0 because the historical source SDK tree had a critical dependency advisory.
The source code archive preserves the original dependency lockfile for comparison.

The tested source used application-owned accounts in Render Postgres with bcrypt password hashes.
A password hash checks a password without storing the original password. Returning users retain the hashes and stable IDs.
A source using Auth0, Clerk, or another identity provider needs that provider's own export and account-linking checks.
Preserve verified issuer, subject, and application-user mappings. Never link accounts by email alone.
Retaining an external identity service is a partial exit, and unavailable password verifiers require a tested reauthentication or password-reset route.

The tested files lived on a **Render persistent disk**, outside PostgreSQL.
A disk attaches to one service instance and prevents zero-downtime deploys. Cron services cannot mount the disk.
The destination stores the exported object keys in a private S3-compatible bucket.
A database restore alone cannot restore document bytes. See Render's [disk limitations](https://render.com/docs/disks).

The native source worker polled a PostgreSQL queue. The native source cron ran `node app.mjs schedule` at `0 3 * * *` in UTC.
The destination jobs process polls the same queue and checks the daily task after 03:00 UTC.
Preserve pending and completed jobs, outputs, schedule definitions, and occurrence records.
Only one execution location can process queued work during a cutover, so reports do not run on both platforms.

The source needed a paid web instance because the source used a disk. Postgres used the free tier.
Render [cron billing](https://render.com/docs/cronjobs#compute-plans-and-billing) has a $1 monthly minimum per cron service.
Worker and web compute are prorated by the second. The [pricing page](https://render.com/pricing) lists current rates.
No separate code export fee or AI credit was needed. Do not activate a paid service or accept prepayment without the person's cost approval.

Free Render web instances cannot attach a disk or provide SSH access and spin down after inactivity.
Free Render Postgres expires after 30 days and has no managed backups. Customer-run `pg_dump` remains available.
Check [free-service limits](https://render.com/docs/free) before choosing an export route.

## What phase 1 proves

Phase 1 exports the source and restores an isolated rehearsal. Phase 1 does not switch public traffic or deploy a complete Stack system.
The synthetic source can be deleted after the verified rehearsal. A real customer keeps the source until the later cutover passes.
The [test record](../../examples/app-platform-migrations/from-render/test_record.md) separates measured behavior from remaining production checks.

The person identifies the populated source environment and approves the pause window.
The coding agent inventories services, exports code and state, restores an isolated destination, and verifies returning users and exact files.
For a real app, agree when writes resume and what happens if the rehearsal fails before pausing production.

## Inventory the source

Record the Git revision, lockfile, runtime versions, app URL, service IDs, database, disk mount path, and populated environment.
Export service configuration, native cron expressions, commands, regions, secret variable **names**, custom domains, and external integrations.
Store actual secret values separately in a protected env file. Never print credentials or commit database exports.
The source database and disk must belong to the app being moved.

Record user IDs, password-hash format, identities, sessions, record owners, document keys, byte lengths, SHA-256 values, and job state/output.
SHA-256 is a checksum for comparing exact bytes. Keep the source inventory so the restored data can be checked independently.

Export code from the original Git provider at the recorded revision, including the dependency lockfile and migrations.
For example, a customer with GitHub CLI access can download the repository's archive through `gh api`.
A code archive does not contain database rows, uploaded documents, platform schedules, or env variable values.

## Freeze the source and export database plus disk

Pause report workers and scheduled work first. Block application mutations using the app's maintenance control.
Log out verification sessions, then enable Render's native maintenance mode to block all source HTTP traffic during the final snapshot.
The native maintenance page also prevents new registrations and session changes during export.
An app-only mutation control does not necessarily block account and session routes.
Suspend the native background worker and cron service before enabling any destination executor.
Keep the database and disk-backed source web instance available for the export's SSH session.

Use the source service's **Connect → SSH** address. Add an existing public SSH key through Account Settings if needed.
Verify the host fingerprint against Render's [published regional fingerprints](https://render.com/docs/ssh#renders-public-key-fingerprints).
Do not use an ephemeral shell or one-off job to export a disk: those instances cannot access the service's attached disk.

Copy `scripts/export_render.mjs` from the example to the running source project root as `migration_export.mjs`.
Run from that root, where the source's existing `pg` dependency is installed:

```sh
umask 077
export EXPORT_DIR=/tmp/portal-migration-export
export UPLOADS_DIR=/var/data/uploads
node migration_export.mjs
```

The example mount path is `/var/data`. Use the source app's actual upload directory when the mount differs.
The command refuses an existing export directory. Use a fresh directory after investigating a failed partial export.
Expected output begins `EXPORT_COMPLETE`.

The exporter holds one repeatable-read database snapshot for both `pg_dump` and the row audit.
The exporter copies each document from disk and checks the recorded byte length and SHA-256.
The export contains `database.dump`, `tables.json`, `objects.json`, `export_manifest.json`, and files below `objects/`.
Password hashes and session rows make the export sensitive. Keep directories mode `700` and files mode `600`.
Download the whole directory through SSH or SCP and keep the export outside Git.

A `pg_dump` version must support the source server version. The tested Render runtime supplied PostgreSQL 18.6 client tools for a PostgreSQL 17 server.
The exported custom-format archive restored successfully using PostgreSQL 17 client tools in the rehearsal.
Check the actual tool versions for another app. See Render's [database export guide](https://render.com/docs/postgresql-backups).

## Restore into isolated PostgreSQL 17 and S3

Prepare a new empty PostgreSQL 17 database and a dedicated private S3-compatible bucket.
The rehearsal uses a local S3-compatible test service. A real R2 bucket's authorization remains a separate production check.
Install Node.js 24 and `pg_restore` on the isolated Linux environment.
Copy the example app and the protected export to the isolated environment.

Copy the example's `environment.example` to a protected env file outside Git.
Replace the database, endpoint, bucket, and credential examples with the isolated destination values.
`RESTORE_DATABASE_URL` names one primary for the restore. `DATABASE_URL` can list the Stack's database servers for app connections.
The Stack uses its private network for database traffic. Preserve TLS verification when restoring through an external database endpoint.

Set `EXPORT_DIR` to the downloaded directory and `FILE_STORAGE=s3`.
Set `RESTORE_CONFIRM=isolated-destination` only after checking both destination targets.
From the destination app directory:

```sh
npm ci --ignore-scripts
node scripts/verify_export.mjs
node scripts/restore_database.mjs
node scripts/import_objects.mjs
node app.mjs migrate
```

The restore refuses any destination database with existing user tables. A failed restore leaves a partial isolated database to discard.
The object importer verifies bytes before and after upload. A rerun accepts matching objects but refuses to overwrite different bytes.
The migration command validates already-applied checksums and does not rerun the source migrations.
Compare every restored row and object before unpausing destination work.

## Verify returning users and work

For the supplied synthetic fixture, load the original `FIXTURE_PASSWORD` from the protected password file without printing the value.
Set `REHEARSAL_CONFIRM=disposable-destination`, then run:

```sh
node --test tests/rehearsal.test.mjs
```

The rehearsal first compares every exported table, including hashes, sessions, schedule rows, and migration state.
The rehearsal then changes only the isolated destination and checks:

- Existing passwords and stable user IDs across two web processes, each with multiple Node workers.
- Owned records, description values, other-owner refusals, private downloads, new uploads, CRUD, and logout revocation.
- Pending reports, concurrent claims, an interrupted claim, owner-only output, and the real jobs command.
- A new daily schedule occurrence, duplicate-call refusal, and session survival after app restart.

Do not run the synthetic fixture suite against production data. The suite creates a new invented account and changes job and schedule state.
For a real customer, write equivalent checks using agreed safe accounts and a new isolated copy.

Start destination web and jobs with `node app.mjs web` and `node app.mjs jobs` after the data comparison passes.
Use `/healthz` for readiness. Configure `PORT` and `WEB_CONCURRENCY` through the destination runtime.
An administrator unpauses destination maintenance, workers, and the scheduler only after source workers and schedules are stopped.
The schedule checks today's UTC occurrence after 03:00. Earlier missed days do not execute separately.

## Later cutover and cleanup

Before a real cutover, prove the destination's TLS, domain routing, real object-store authorization, database-primary switching, backups, and recovery.
Keep source writes and executors paused through the final export and traffic switch.
Record the last accepted source write and the first accepted destination write.
If the destination accepts writes, returning traffic to the source requires reconciling those new writes first.

After the synthetic rehearsal passes, delete only the source services created for the exercise.
Delete the attached disk and source database only after verified exports exist. Check fresh service and database listings for absence.
For a real customer, retention and final deletion require the customer's agreed recovery window and approval.

## Fill a laptop or staging with test data

The command fills a developer's laptop database or staging with invented test data.
After the guide's local database and bucket setup, run migrations and start the app.
Set `APP_URL` to that app and supply `FIXTURE_PASSWORD`, then run:

```sh
APP_ENV=development npm run seed-test-data
```

For staging, use `APP_ENV=staging` with its own database and bucket.
`npm run seed-test-data -- --accounts 200000` makes enough rows to show slow queries.
The count includes the two fixed accounts. Extra accounts use bulk SQL through
`DATABASE_URL`; they get one record each and no files or report jobs.
Reruns add missing rows, and a smaller count removes nothing.
