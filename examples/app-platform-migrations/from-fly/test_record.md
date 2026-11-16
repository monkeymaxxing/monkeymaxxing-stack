# Fly.io migration test record

2026-11-05: Renamed the seed to `seed-test-data` for laptops and staging and added bulk `--accounts` generation. JavaScript syntax checks passed. On isolated Debian 13, Node 24.22.1, PostgreSQL 17 and pinned S3Mock, `node --test tests/seed-test-data.test.mjs` passed 1 test and `node --test tests/portal.test.mjs` passed all 4 existing tests against fresh synthetic data. Seed checks covered both allowed environments, production/unset refusals, exact fixture preservation, 1,000 accounts twice, shared generated hash and smaller-count preservation. No source platform was accessed. The recorded images predate this change.

## Measured source and destination

The hand-authored source ran on Fly Machines in November 2026.
The source used Node.js 24.11.0, Express 5.3.0, pg 8.23.1, bcryptjs 3.0.3, and AWS S3 SDK 3.1161.0.
The native unmanaged image tag was `flyio/postgres-flex:18.1`; the running server reported PostgreSQL 18.6.
A private Tigris bucket held two documents, each exactly 27 bytes.

A first deploy created the schema and exact synthetic fixture through the hosted HTTP API.
A second deploy added the description column and preserved the existing records with empty defaults.
The fixture descriptions were then applied through the hosted app.
The native hourly Machine recorded a completed session-cleanup occurrence.

The final source export contains two users with bcrypt verifiers, two records, two documents, two pending reports, eight tables, and two migration versions.
The source contains no active sessions because the source logout checks revoked every fixture session.
The export preserves the completed scheduled occurrence.
The source job worker was deployed but paused to preserve pending fixture reports.

The database dump and full row audit share one repeatable-read snapshot.
Source object keys, owner IDs, titles, descriptions, job states, byte lengths, and SHA-256 values match the recorded API facts.
A native filesystem code archive and separate object downloads accompanied the database dump.
The export helper was corrected through native SSH after an initial failed connection-settings attempt.
The failed attempt produced no accepted export.

The isolated Linux destination used Debian 13, PostgreSQL 17.11, Podman 5.4.2, and the same pinned Node runtime.
A pinned S3Mock image provided the destination S3 API.
The PostgreSQL 18.6 dump restored into PostgreSQL 17.11 with no SQL transformation and no ignored errors.
Every restored row matched the source audit before destination mutation, including password hashes and owner links.
Both original objects were imported and downloaded with matching SHA-256 values.

The initial behavior suite passed four tests with zero failures.
Checks covered existing-password login, stable UUIDs, two independent web processes with WEB_CONCURRENCY=2, logout revocation, ownership refusals, CRUD, exact bytes, and destination uploads.
The real jobs command was killed after an uncommitted update. Pending jobs remained available and concurrent workers completed each job once.
Each report retained `record_count=1` followed by LF.
The suite also checked schedule idempotence, repeated migrations, old-column SQL compatibility, connection termination/recovery, malformed input, and production seed refusal.

## Independent replay

An independent replay used a separate app copy, build, empty PostgreSQL database, private test bucket, and web ports.
The replay restored the original export and matched every row before mutations.
Both original documents passed import and downloaded-byte checks.
The four updated behavior tests passed with zero failures in about 12.57 seconds.
The updated hourly test forced a new occurrence, removed an expired session, and recorded exactly one occurrence under concurrent invocation.
Registration and duplicate-registration refusal also passed.

A separate staging database and bucket proved seed idempotence after existing records were edited.
The rerun preserved password hashes, edited records, document rows, and report jobs without duplication.
The production seed command was refused.

The final verifier requires the original and paused Machine inventories, database Volume inventory, and checksummed native configuration sidecar.
The independent reviewer verified the sidecar and rebuilt the final image after the verifier change.
The final image ran the updated verifier successfully, used UID 1000, and excluded credentials, exports, tests, and canary files.

After the verified replay, all run-created Fly source apps, Machines, database Volume, Tigris objects, and bucket were deleted.
Fresh app, Machine, Volume, and bucket inventories proved absence.
The temporary organization tokens were revoked, and the revoked CLI token was refused.
The isolated rehearsal guest and project were also removed.
Protected export evidence remains available for later production integration.

## Boundaries

- The app uses application-owned bcrypt authentication. No managed identity-provider export was tested.
- Native source and destination HTTP checks passed. Background browser screenshots returned blank, so visual UI acceptance is unproved.
- Source fixture reports were pending. Completion and output were proved at the restored destination.
- Active source-cookie continuity is unproved because all source sessions were revoked before export.
- S3Mock proves API and byte behavior, not private bucket authorization at R2.
- Database connection termination proves reconnection, not a real primary/replica switch.
- Old-column SQL compatibility was checked. A running previous-release binary was not exercised throughout the schema deployment.
- Production traffic cutover, PgBouncer, backup recovery, real primary switching, and production rollback remain separate checks.
- PostgreSQL 18-to-17 portability is specific to the fixture's schema and data.

- 2026-11-05: Invalid `--accounts` checks now require the exact usage message on stderr and unchanged database rows. The seed suite and full isolated service rehearsal passed with PostgreSQL 17 and S3-compatible storage.
