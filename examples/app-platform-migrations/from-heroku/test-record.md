# Heroku migration test record

Verified on 2026-11-04. This record covers source construction, export, and standalone migration phase 1.
It does not claim a live Stack deployment or production cutover.

| Artifact or behavior | Observed result |
| --- | --- |
| Native source | Handwritten Express, Node 24.22.2, Heroku Postgres 18.4, Basic web/worker/clock dynos, and external private S3-compatible storage. |
| Schema rollout | First hosted release received fixture rows; second added description. Existing rows and title-only requests remained valid. |
| Native schedule | The Basic clock timer fired at the selected UTC time and committed the daily occurrence. The unused Scheduler add-on was removed. |
| Application export | Seven tables: 2 users, 8 sessions, 2 records, 2 documents, 3 reports, 1 schedule occurrence, 2 migration ledger rows. |
| Jobs at export | Two pending reports and one completed report with exact owner-only output. |
| Object export | Two original private objects, 27 bytes each, matching the source metadata SHA-256 values. Anonymous source requests returned 401. |
| PostgreSQL clients | Source-major pg_dump and pg_restore 18.2 exported the PostgreSQL 18.4 source. |
| Target restore | PostgreSQL 17.11 restored the application SQL without rewriting SQL. Every application row matched before rehearsal writes. |
| Returning accounts | Existing bcrypt passwords and original UUIDs worked. No reset or external auth dependency remained. |
| HTTP isolation | Owned CRUD, original and new private files, cross-instance sessions, logout, and foreign-owner refusals passed. |
| Report execution | Concurrent claims completed each job once. SIGKILL during a completion transaction left pending work for a replacement worker. |
| Clock execution | Overlap committed one occurrence. The combined jobs command ran reports and clock work and stopped both on SIGTERM. |
| Independent replay | Fresh app/export copies, dependency installation, database, bucket, settings, and ports passed all ten behavior groups. |
| Image | Built and ran Node 24.22.2, migrations, existing-password login, an owned record, a new private upload/download, and WEB_CONCURRENCY=2. |
| Database URL | The fresh replay and image proof tried an unreachable first host before the writable database. |

The independent reader found no blocking guide gap.
Source UUIDs, migration SQL, bcrypt verifiers, ownership, document keys, and completed output were preserved.
The source code archive and exported files were checked against manifest checksums.
Fifteen common runtime, web, and migration files matched the source archive byte-for-byte.
Destination changes are the primary-discovery integration, package metadata, one jobs supervisor, Docker files, and documentation.

Heroku-owned `_heroku` and `pg_stat_statements` diagnostics remain outside the portable application dump.
A raw native dump was retained separately for provenance. The fixture does not depend on provider diagnostics.
Private exports, passwords, and raw authentication snapshots are excluded from this example.

The remaining live Stack gates are two separate app servers, real primary switching without restart, PgBouncer, actual R2 privacy, and Stack backup/object recovery.
Source teardown and dedicated-bucket cleanup are recorded in the worker's operational report.

## Test data command proof

2026-11-05: `seed-test-data` fills laptops or staging and adds bulk `--accounts` generation without changing the fixed fixture. JavaScript syntax checks passed. On isolated Debian 13, Node 24.22.1, PostgreSQL 17 and pinned S3Mock, `node --test tests/seed-test-data.test.mjs` passed 1 test from the app directory, and `node tests/rehearsal.mjs` passed its existing assertions against a fresh synthetic snapshot. The seed test proved allowed/refused environments, exact fixed rows and bytes, 1,000 accounts twice, a shared generated hash and smaller-count preservation. No source platform was accessed. Recorded images predate this change.

- 2026-11-05: Invalid `--accounts` checks now require the exact usage message on stderr and unchanged database rows. The seed suite and full isolated service rehearsal passed with PostgreSQL 17 and S3-compatible storage.
