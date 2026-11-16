# Replit migration phase-1 test record

Status: **phase-1 export and independent destination replay passed on 2026-11-04**. Live Stack migration remains separate.

The native source export was checked on 2026-11-04.
Source Git revision: `5073b62ef952208e50a5424eea4c9901c0556c85`.
Runtime: Node.js 24.22.1. Source PostgreSQL and pg_dump: 16.10.
Source App Storage SDK: `@replit/object-storage` 1.0.0.

The source code ZIP SHA-256 is `084df485e04ebcea317e59e9af1284a244b4b38df256850ef81041e393e903f2`.
The native snapshot dump SHA-256 is `441b39dc2af1c56a185364304d9210b09f04fdaeffbadb0c3c468e2b0575a964`.
The full table-audit SHA-256 is `5fd4e9782db9d4a564c2b3795ec3b74c0e1ff812f33cfdcb32fc0cd83c68df4a`.
Sensitive exports remain outside the customer example.

The export contains two users, two identity mappings, four revoked sessions, two records, and two document references.
The queue contains two pending reports and one completed report with `record_count=1` followed by LF.
The snapshot also contains controls, one persisted schedule, an empty schedule-run ledger, and two migration entries.
Every row ID, owner mapping, relevant field, source code hash, and object checksum matches the source inventory.
The exported code ZIP also matches the independently recorded source archive byte for byte.

| Document | Bytes | SHA-256 |
| --- | --- | --- |
| `barbara-note.txt` | 27 | `05fc126dc203e0579d73a6365e130ba77d1f422d87042b362456a2885029d32a` |
| `michael-note.txt` | 27 | `784483c538543c904f1232e9c939417711e771b531e3f04c3d45f6699ad65c55` |

The source exporter ran from the native Shell with `umask 077`.
`pg_dump` and the table audit shared a read-only repeatable-read snapshot.
The SDK listed and downloaded all two source objects.
No application files, database rows, pause controls, jobs, or source objects were changed.
Only export artifacts were created on the source.
No plan upgrade, trial, payment, publish, or Agent run was used for exports.

## Destination checks

2026-11-05: Renamed the command to `seed-test-data` for laptops and staging, added `--accounts`, and preserved the fixed fixture. JavaScript syntax checks passed. On an isolated Debian 13 guest with Node 24.22.1, PostgreSQL 17 and the pinned S3Mock, `node --test tests/staging.test.mjs` passed 1 test (environment refusals, exact fixture preservation, 1,000 accounts twice, shared generated hash and smaller-count preservation), then `npm test` passed all 9 tests against a fresh synthetic snapshot. This rerun did not access the source platform. The recorded image below predates this change.

An isolated Debian 13 guest provides PostgreSQL 17.11 and S3Mock.
S3Mock is pinned to `docker.io/adobe/s3mock@sha256:ab01a6946750f451ca215a47e91030695b260e4003b8a5a6201d25029b8fca92`.
The app image uses `docker.io/library/node:24.22.1-alpine` and the committed npm lockfile.
The source-only Replit SDK is absent from destination dependencies.

Pinned destination dependencies: Express 5.3.0, pg 8.23.1, bcryptjs 3.0.3, AWS S3 SDK 3.922.0.
Npm version: 11.19.1. Podman version: 5.4.2.
Package-lock SHA-256: `01fd3bf15458d8d8160d5f321e9d19934c0d4c193c879e7c6d7428d543a6f3f1`.

| Check | Result |
| --- | --- |
| Native `git archive`, `pg_dump`, SDK object export and checksum transfer | Passed |
| All restored public-table rows, including bcrypt hashes and revoked sessions | Exact source equality |
| Two existing accounts logging in with original passwords and stable UUIDs | Passed |
| Sessions and logout across two independent web processes, each with two workers | Passed |
| Ownership refusals for records, documents and jobs | Passed in each direction |
| CRUD, registration, bad-password refusal, and private upload/download | Passed |
| Original objects downloaded through destination API | 27 bytes each, exact source hashes |
| Killed worker, pending-job recovery, concurrent claims, actual jobs command | Passed |
| Owner-specific report output and atomic completion | `record_count=1` followed by LF |
| Concurrent persisted schedule catch-up | One recorded occurrence |
| Database connection termination followed by fresh writes | Passed with unchanged web process IDs |
| Ordered migrations rerun after restore | No ledger or row changes |
| Additive description migration over existing rows and old-column queries | Passed |
| Failed transaction rollback | No partial row retained |
| Staging seed twice, original hashes and exact fixture counts retained | Passed |
| Staging seed with `APP_ENV=production` | Refused |
| Final image health, malformed JSON no-store response, home page, SIGTERM | Passed |
| JavaScript syntax and local guide links | Passed |

The main rehearsal passed 9 tests with 0 failures in about 4.5 seconds.
The final staging suite passed 1 test with 0 failures in about 2.5 seconds.
The staging additive-migration check uses old-column SQL queries, not an actual running previous-release binary.

A fresh agent followed the guide using another empty PostgreSQL database and another S3 bucket.
The fresh agent built an independent image and passed all 9 tests with 0 failures in about 4.3 seconds.
Fresh replay image ID: `38bbf46122e38e239a18bb4029af2985198d342d8393cbfa4fe5e3521c03a93a`.
The fresh agent independently checked export checksums and the two destination object downloads.
The fresh agent did not repeat the export on Replit.

The replay caught a credential-file build exclusion gap. The container and Git ignore files now exclude `destination.env` and `.env` variants.
The fresh agent built with a protected `destination.env` present and verified the image excludes that file.
The image also excludes exports and tests. The normal runtime user is UID 1000.
The source-only object importer uses container user `0` to read protected mode-600 export files.

No source worker was resumed and no source schedule was changed during the rehearsal.
Destination-only tests consumed restored pending jobs, changed controls, and advanced a test schedule.
No live traffic was switched.

## Limits

The source was a development environment with custom bcrypt authentication.
No public source deployment, production database export, or Replit Auth export is proved.
All exported source sessions were revoked. Preserving active source browser sessions across domains is not proved.

S3Mock proves API and byte behavior. S3Mock does not prove R2 permissions or private-access enforcement by the storage provider.
The app enforces ownership before requesting private file bytes.
A SQL snapshot cannot guarantee file consistency while source uploads continue.
Pause source writes for the final SQL and object export.

Live Stack deployment, actual two-server sessions, primary switchover, PgBouncer, upload backups, backup restore, source shutdown, and traffic cutover remain later checks.
No live downtime or production rollback result is claimed.
