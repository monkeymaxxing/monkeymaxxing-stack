# Customer portal moved from Replit

A complete Node.js portal keeps accounts, invoice records, private documents, and queued reports when leaving Replit.
The destination uses PostgreSQL and an S3-compatible private bucket.
Existing bcrypt password hashes and stable application IDs remain unchanged.

Follow [the migration guide](../../../docs/app-platform-migrations/from-replit.md) before exporting or restoring data.
Read [the test record](test_record.md) for evidence and unproved live checks.

Run commands from this directory after supplying the protected destination environment:

```sh
npm ci
npm run migrate
npm run web
```

Run `npm run jobs` in a separate process.
The web command uses `PORT` and `WEB_CONCURRENCY`.
Background work remains paused when the restored database says the worker is paused.

`npm test` mutates a disposable restored destination and requires the protected source export and fixture password.
Use `npm run test:staging` only with a separate empty staging database and bucket.
The guide explains the test setup and safety checks.

## Acceptance contracts

- Preserve source users, bcrypt hashes, identity mappings, record ownership, sessions, file metadata, jobs, schedules, controls, and migration checksums.
- Export file bytes separately from PostgreSQL, then verify destination downloads by byte equality and SHA-256.
- Authenticate returning users with existing passwords. Share and revoke sessions across independent web processes.
- Refuse another user's records, documents, and jobs, including guessed UUIDs.
- Commit report output and completion in the transaction holding the job lock. Recover uncommitted work after worker death.
- Apply ordered migrations transactionally at deploy. Preserve existing rows through the additive description migration.
- Run jobs and schedules separately from web processes. Use one execution location during cutover.
- Reconnect to the writable PostgreSQL server with unchanged URLs and no automatic replay of an uncertain mutation.
- Keep test data synthetic and idempotent. Never seed a laptop or staging from source exports.

## Files

`server.mjs` owns HTTP behavior and authorization. `storage.mjs` owns the S3 API.
`database.mjs` owns transactions and migrations. `jobs.mjs` owns queue claims and persisted schedules.
`pg_with_multiple_database_servers.mjs` is copied unchanged from the Stack's Node integration files.
`web.mjs`, `jobs_runner.mjs`, and `seed_test_data.mjs` provide the runtime commands.
`scripts/` contains the source exporter, checksum verifier, and destination object importer.

`APP_ENV=development npm run seed-test-data` fills a developer's laptop database
with invented test data after migrations. Use `APP_ENV=staging` for staging.
Supply `FIXTURE_PASSWORD` and the separate database and bucket settings at runtime.
`npm run seed-test-data -- --accounts 200000` makes enough rows to show slow queries.
The count includes the two fixed accounts. Rerunning adds missing rows; it removes nothing.
