# Variances and guidance needs

SvelteKit 3.1.1 uses adapter-node 6.0.1 and configuration in `vite.config.js`.
Version 3 removed the adapter's `ORIGIN` variable.
The custom Node launcher overwrites canonical host/protocol headers using runtime `APP_ORIGIN` before the generated handler runs.
The launcher keeps builds free of database/storage credentials and supports different staging and production origins from one image.
The generated handler retains SvelteKit's origin checks. The portal independently checks every mutation's exact Origin.
Node cluster shares one PORT listener across WEB_CONCURRENCY workers.
Shutdown drains active HTTP requests, closes each framework pool and disconnects cluster IPC.

Plain pg cannot consume a multi-host Stack URL. Every pool uses the unchanged supplied helper.
Reads use the primary for immediate session consistency. DATABASE_READ_URL is unused.
Migrations and jobs need only transaction locks, so direct PostgreSQL sessions are unnecessary.
Fingerprint assets live in `/app/build/client`. Keep the complete directory for Stack release bridging.
Uploaded bytes live in S3-compatible storage. Database backups restore metadata, not object bytes.

## Tested revisions and versions

Recorded 2026-11-04. `source-sha256.json` identifies exact executable/build/test inputs.
`package-lock.json` records exact direct and transitive dependencies.

| Component | Tested version |
| --- | --- |
| OS / architecture | Debian 13 / x86_64 |
| Node | 24.22.2 |
| SvelteKit / adapter-node | 3.1.1 / 6.0.1 |
| Svelte / Vite | 5.57.3 / 8.3.5 |
| TypeScript / svelte-check | 6.0.3 / 4.7.8 |
| pg / bcryptjs | 8.23.1 / 3.0.3 |
| AWS S3 SDK | 3.1161.0 |
| PostgreSQL | 17.11 |
| Podman | 5.4.2 |
| Service test Python | 3.13.5 with psycopg 3.2.6 |

Node image: `docker.io/library/node:24-bookworm-slim@sha256:a43f7fc3e52e87d12a905f46eea0275def84ca8f2981a5b53fed44d7fb398ee0`.
S3Mock: `docker.io/adobe/s3mock@sha256:ab01a6946750f451ca215a47e91030695b260e4003b8a5a6201d25029b8fca92`.
Tested app image ID: `e5a09a1cae693dece38f1ad024e2855528fb602849ae01dcbe9a110c66554516`.
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
- Measured promotion command through recovery checks: 1.398 seconds. This observation is not a recovery ceiling.
- `podman build` passed. Actual UID 1000 images served rendered HTML, stylesheet, two webs and two job processes.
- Logical dump/restore preserved all account/hash, session, record, document metadata, report/output and migration rows.
- Restored sessions and password login worked. Separate object copies matched original bytes and database hashes.
- Measured logical restore comparison: 1.263 seconds. Database restore is not whole-system recovery.
- Snapshot contained 7 accounts, 6 sessions, 6 records, 4 documents, 27 reports and 2 migrations.

- A blocked write returned HTTP 503 after 5.010 seconds and inserted no row.
- A transparent PostgreSQL relay withheld replies until COMMIT reached idle ReadyForQuery, then closed the connection.
- The mutation returned HTTP 503 with exactly one committed row, no automatic replay, and a successful later distinct write.

- A fresh independent agent copied the app into a separate source directory and installed from the lockfile.
- Independent check/build, driver-tree checks, pinned psycopg test environment and complete real-service suite passed.
- The replay also downloaded all retained objects and verified metadata SHA-256, completed jobs and stopped listeners.
- The replay found a missing Debian `python3-venv` prerequisite. The corrected guide was verified during the replay.

## Repeat the proof

Follow [the guide](../../../docs/app-frameworks/sveltekit-pg.md) using an empty database and separate private bucket.
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
All 36 old asset URLs returned the original bytes and correct content types at the new loopback origin.
The held page saved a record without reloading. An independent authenticated request read back the saved record.
The memory figures above come from the earlier release.

## Seed test-data proof

- 2026-11-05: `seed-test-data` now supports development and staging plus `--accounts`. The full real-service suite passed on Debian 13 with PostgreSQL 17.11 and S3Mock. Checks covered refused environments and counts, exact fixtures, 1,000 accounts twice, unchanged documents/jobs, HTTP ownership and storage, workers, and shutdown. Previously recorded image IDs predate this change.
