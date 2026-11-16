# Supabase exit example design

The source uses React, Supabase Auth, PostgREST Row Level Security, private Storage, an Edge Function and pg_cron.
The destination keeps the customer interface and replaces the managed service calls with one Node HTTP API.
Running the full self-hosted Supabase service set is another option. The smaller API fits the services used by this fixture.

## Ownership

`web.mjs` owns worker count and shutdown. `server.mjs` owns HTTP validation, origin checks, sessions and object authorization.
`backend.mjs` owns Postgres transactions, password verification, shared sessions, S3 transfers and report execution.
`operations.mjs` owns ordered migrations, export validation, one-time import, laptop and staging test data and worker execution.
`app/src/main.jsx` owns the same account, records, documents and report screens as the source.
The destination browser never receives database, S3 or administrative credentials.

## Data

User UUIDs are retained. `auth.users.encrypted_password` becomes `users.password_hash` without rewriting the bcrypt verifier.
The source issuer, subject, email identity and metadata remain in `users.source_identity`.
Source bearer and refresh tokens are deliberately not imported. Returning users log in again with their existing passwords.
Sessions use random opaque tokens. Only SHA-256 token hashes and expiration live in Postgres.
Logout removes the user's sessions, so every app process refuses those tokens immediately.
The fixture has confirmed email accounts and no MFA, external provider, anonymous account or deleted identity.
Import refuses unsupported account states and unreviewed application columns. Other authentication designs need a separate conversion.

Records, documents and report jobs keep their IDs, owner UUIDs and timestamps.
The API puts the authenticated owner into writes and requires that owner on reads, edits and deletes.
RLS does not carry across into the reduced schema. Application checks replace each used policy.
Only the app role and administrative operators can access the destination database and private bucket.

Document keys, names, lengths and hashes remain unchanged.
An import verifies each local object, uploads it and downloads it again before publishing database references.
A differing existing object is refused. Failed imports can leave unreferenced objects for a safe rerun.
An upload with an uncertain database commit retains its object because deleting could destroy a committed reference.
The HTTP upload limit is 50 MiB because requests are buffered and the source's free upload limit is 50 MiB.

Report execution claims a pending row with `FOR UPDATE SKIP LOCKED`.
Count, output and completion commit in the same transaction. A killed transaction leaves the pending row available.
Source cron definitions remain as JSON and text. The known minute marker becomes the worker's minute occurrence insert.
A unique minute key prevents duplicate committed occurrences during concurrent worker ticks.
The worker stays disabled until the final source freeze and explicit destination activation.
This fixture records current minutes and does not replay minutes missed during downtime.

## Runtime and recovery

The supplied database helper chooses the current primary when opening a connection.
Pool queries have deadlines. Failed requests are never automatically replayed.
`PORT` selects one web process's port. The Node cluster starts the `WEB_CONCURRENCY` number of workers on the same `PORT`.
The cluster forwards shutdown to its workers and replaces a failed worker. The jobs process is separate and exits after current work on SIGTERM.
App, migrate, jobs and test-data seed commands share one dependency lockfile and image.

A raw native archive preserves the original managed schemas for inspection.
The reduced snapshot maps only this portal into the independent destination.
Original cron history stays in the native archive and snapshot. App occurrence rows and the schedule definition enter destination tables.
A destination backup preserves accounts, sessions, records, file metadata, jobs, schedules and migration checksums.
Recovery must also copy private file bytes and verify each referenced SHA-256.
Production Stack deployment, primary promotion, real R2 authorization and alerting require separate evidence.

## Test data

`operations.mjs seed-test-data` accepts only `APP_ENV=development` or `staging`.
It recognizes `barbara@example.com`, `michael@example.com`, and generated
`test-account-000003@example.com` and later account numbers. It checks for other
accounts before writes or uploads, holding account writes until the transaction
commits. This keeps test data out of databases holding other data and lets
laptop reruns preserve existing test values. Fixed accounts are created only
when missing. `--accounts` bulk-adds generated accounts and one owned record
each, using one password hash and no extra file or report-job writes.
