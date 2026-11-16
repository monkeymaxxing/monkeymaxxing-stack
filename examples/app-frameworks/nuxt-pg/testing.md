# Variances and guidance needs

Nuxt 4.6.4 builds through Nitro 2.13.6's `node-server` preset.
Server routes use H3 1.15.11 to adapt framework events to standard Request/Response objects.
The Vue page renders on the server and attaches browser controls after mounting.
The Node launcher maps WEB_CONCURRENCY to cluster processes sharing PORT.
The launcher copies PORT to NITRO_PORT so a hosting-specific alias cannot replace the assigned listener.
Nitro's native shutdown drains requests and invokes the plugin's asynchronous database close hook.
The portal checks every mutation's exact Origin and stores session tokens only as hashes in PostgreSQL.
The build needs no database/storage credentials. CLI dependencies and commands ship beside the standalone Nitro output.

Plain pg cannot consume a multi-host Stack URL. Every pool uses the unchanged supplied helper.
Reads use the primary for immediate session consistency. DATABASE_READ_URL is unused.
Migrations and jobs need only transaction locks, so direct PostgreSQL sessions are unnecessary.
Fingerprint assets live in `/app/.output/public`. Keep the complete directory for Stack release bridging.
Uploaded bytes live in S3-compatible storage. Database backups restore metadata, not object bytes.

## Tested revisions and versions

Recorded 2026-11-04. `source-sha256.json` identifies exact executable/build/test inputs.
`package-lock.json` records exact direct and transitive dependencies.

| Component | Tested version |
| --- | --- |
| OS / architecture | Debian 13 / x86_64 |
| Node | 24.22.2 |
| Nuxt / Nitro | 4.6.4 / 2.13.6 |
| Vue / H3 | 3.5.44 / 1.15.11 |
| pg / bcryptjs | 8.23.1 / 3.0.3 |
| AWS S3 SDK | 3.1161.0 |
| PostgreSQL | 17.11 |
| Podman | 5.4.2 |
| Service test Python | 3.13.5 with psycopg 3.2.6 |

Node image: `docker.io/library/node:24-bookworm-slim@sha256:a43f7fc3e52e87d12a905f46eea0275def84ca8f2981a5b53fed44d7fb398ee0`.
S3Mock: `docker.io/adobe/s3mock@sha256:ab01a6946750f451ca215a47e91030695b260e4003b8a5a6201d25029b8fca92`.
Tested app image ID: `1e62ed2fb6b7549cbc252a62cceb8e58eeec60dc71a41b1eca783ea97d1ddb1f`.
These checks ran in an owned disposable Linux guest using existing shared guest slots.

## Commands and results

- 2026-11-05: The full isolated PostgreSQL 17/S3 suite passed with complete first-run fixture snapshots. Every fixed row and password hash survived reruns, two 1,000-account runs, and a different `FIXTURE_PASSWORD`. Previously recorded image IDs predate the test changes.

- Exact dependency installation, `npm run check`, and `npm run build` passed.
- `python3 tests/services.py` passed against real PostgreSQL and S3Mock.
- Migration 1 accepted title-only rows. Concurrent migration commands applied migration 2 once and preserved rows.
- Repeated migrations retained exactly two versions. Production seed refused. Two staging seeds preserved exact fixtures.
- Two instances, each with two web workers, passed registration/login, shared sessions, logout revocation, CRUD and ownership refusals.
- Upload/download bytes and SHA-256 matched. Reports were private and counted only owned records.
- Two job processes skipped a locked report and completed 22 reports with `record_count=1` followed by LF.
- Killing a report worker inside a blocked transaction left the report recoverable.
- SIGTERM finished an active report transaction and a blocked HTTP write, then exited cleanly.
- A streaming standby was first in the unchanged URL. Writes selected the writable second server.
- Stopping the primary and promoting the standby preserved surviving app/job processes, sessions, documents, fresh writes and jobs.
- Measured promotion command through recovery checks: 2.290 seconds. This observation is not a recovery ceiling.
- `podman build` passed. Actual UID 1000 images served rendered HTML, stylesheet, two webs and two job processes.
- Logical dump/restore preserved all account/hash, session, record, document metadata, report/output and migration rows.
- Restored sessions and password login worked. Separate object copies matched original bytes and database hashes.
- Measured logical restore comparison: 0.866 seconds. Database restore is not whole-system recovery.
- Snapshot contained 7 accounts, 6 sessions, 6 records, 4 documents, 27 reports and 2 migrations.

- A blocked write returned HTTP 503 after 5.008 seconds and inserted no row.
- A transparent PostgreSQL relay withheld replies until COMMIT reached idle ReadyForQuery, then closed the connection.
- The mutation returned HTTP 503 with exactly one committed row, no automatic replay, and a successful later distinct write.


- A fresh independent agent installed from the lockfile in a separate source directory, database and bucket.
- Independent check/build, driver-tree checks, pinned psycopg 3.3.7 environment and the complete service suite passed.
- Independent seeded-account checks verified Barbara/Michael sessions across app instances, exact seeded document bytes/hashes and completed fixture reports.
- The independent replay stopped its web/job processes and verified closed listeners. No guide blocker remained.

## Repeat the proof

Follow [the guide](../../../docs/app-frameworks/nuxt-pg.md) using an empty database and separate private bucket.
The service suite leaves synthetic rows and objects for recovery inspection.
The optional promotion command must own every dependent service and promote a synchronized standby.
Never promote or restart a shared database for this test.

## Limits and live checks

The framework guide records the completed shared Stack checks for R2, HTTPS, database disruptions, PgBouncer, and release overlap.
Previous-image rollback and Stack database/object backup drills remain separate checks.
The portal excludes password recovery, email verification and public abuse protection.
Public operation needs ingress login limits. Uploads buffer at most 8 MiB plus multipart overhead.
An uncertain metadata commit can leave an unreferenced object. Inspect saved metadata before deleting any object or replaying a mutation.

## Retained asset fix

The retained-file tests pass for GET, HEAD, exact bytes, MIME types, missing files, unsupported methods, and path traversal refusal.
The tests reject encoded dot segments, hidden paths, backslashes, NUL bytes, and escaping symlinks.
CI tested and built the fixed source on Node 24 from the pinned image.
A fixed release followed by a changed-asset release passed on the shared Stack.
All 7 old asset URLs returned the original bytes and correct content types at the new loopback origin.
The held page saved a record without reloading. An independent authenticated request read back the saved record.
The memory figures above come from the earlier release.

## Seed test-data proof

- 2026-11-05: `seed-test-data` now supports development and staging plus `--accounts`. The full real-service suite passed on Debian 13 with PostgreSQL 17.11 and S3Mock. Checks covered refused environments and counts, exact fixtures, 1,000 accounts twice, unchanged documents/jobs, HTTP ownership and storage, workers, and shutdown. Previously recorded image IDs predate this change.
