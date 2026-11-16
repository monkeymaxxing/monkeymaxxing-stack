# TanStack Start PostgreSQL test record

## Variances and guidance needs

The Node adapter needs an explicit `node_server` preset and `node.exclusive=false`
for a shared cluster listener. A Nitro close hook drains requests before closing
the database pool and disconnecting cluster IPC. CLI files need explicit image
copies. The Stack pg helper stays unchanged. Reads use the primary. The pinned
Nitro release is a release candidate, although TanStack Start is a stable release.
The [guide](../../../docs/app-frameworks/tanstack-start-pg.md) explains hosted
Vercel/Netlify dependencies and release overlap checks.

## Versions and artifact

Checked on 2026-11-04: Debian 13 x86_64, PostgreSQL 17.11, Node 24.22.2,
npm 11.19.1. TanStack Start 1.169.4, Router 1.170.46, React 19.3.1,
Vite 8.3.5, Nitro 3.0.261103-rc, pg 8.23.1, bcryptjs 3.0.3 and
AWS S3 client 3.1161.0 are pinned in the lockfile.
The test recorded source hashes and the tested image ID.

## Executed checks

- 2026-11-05: The full isolated PostgreSQL 17/S3 suite passed with complete first-run fixture snapshots. Every fixed row and password hash survived reruns, two 1,000-account runs, and a different `FIXTURE_PASSWORD`. Previously recorded image IDs predate the test changes.

- 2026-11-05: `seed-test-data` now supports development and staging plus `--accounts`. The full real-service suite passed on Debian 13 with PostgreSQL 17.11 and S3Mock. Checks covered refused environments and counts, exact fixtures, 1,000 accounts twice, unchanged documents/jobs, HTTP ownership and storage, workers, and shutdown. Previously recorded image IDs predate this change.


- Clean dependency install, two password/session tests, production build and TypeScript check passed on Node 24.
- Real PostgreSQL 17 and an isolated S3-compatible service passed all 14 service checks. Migrations apply once. Migration 0002 preserves existing title-only SQL readers and writers. Staging seed reruns preserve passwords and avoid duplicate fixture documents/jobs. Production seeding is refused.
- Two clustered web instances passed login, registration, session sharing, logout revocation, origin refusal, owned CRUD and private upload/download byte equality.
- Two workers completed 22 reports. A killed worker left work available. A signaled worker committed the active report before exiting.
- Blocked health SQL returned 503 in 1.504 seconds. The running web processes reconnected after database restart in 3.327 seconds including restart. The existing session and a new write passed.
- Clustered SIGTERM drained an in-flight HTTP mutation and exited 0.
- Chromium 145 / Playwright 1.58.2 passed production SSR and hydration, browser login, record read/create through actual server-function endpoints, anonymous refusal, owner isolation, server-function CSRF refusal and logout. No page error occurred. The browser test used loopback HTTP, where Chromium permits Secure cookies. Public HTTPS remains a live check.
- The Containerfile built successfully. Two web and two job containers passed the shared HTTP checker. The web process ran as UID 1000. A generated JavaScript asset returned HTTP 200. All four containers stopped with exit 0.
- The built web/job containers reconnected after a database restart in 3.178 seconds. Container states and every child PID stayed unchanged. The existing session, a fresh mutation and report completion passed.
- A blocked mutation returned 503 in 12.005 seconds and inserted no row. A PostgreSQL relay then withheld a committed mutation's reply through idle ReadyForQuery and closed the connection. The app returned 503 while exactly one row existed. No automatic replay occurred. A distinct later write passed.
- Physical PostgreSQL streaming replicas passed planned promotions in both directions with the standby listed first in the unchanged database URL. Fresh HTTP writes recovered in 0.860 seconds forward and 0.947 seconds back, including the switch. The checks recorded 10 and 11 visible failed requests. Two web containers and two job containers kept every process ID. Sessions, ownership refusals and report completion passed. Each successful unique probe existed exactly once afterward. These measurements use two clusters in one isolated Linux guest, outside the Stack's switchover playbook.
- Logical dump/restore took 0.904 seconds, including dump and new database creation. Exact rows matched across six accounts, seven sessions, seven records, four documents, 26 report jobs and two migration versions. Pending jobs and completed output were preserved. The restored app accepted a pre-backup session and password login. Four objects copied to a separate bucket matched the original bytes.
- A fresh agent independently installed and built a clean copy, passed both unit tests and TypeScript, and passed 13 service checks plus the guide's separate shared HTTP checker. The optional database restart was excluded from the replay. No source repair or manual configuration fix was needed.
- The systems repository template passed `mmx validate`. Local Markdown links, public-content checks and whitespace checks passed. All 30 non-Markdown source/config/test files matched the tested remote source by SHA-256.

Tested image ID: `c772ed83159a463524e297c58651addf039f93022f946a5d5ae63f105d1fc30a`.
Lockfile SHA-256: `675319b557542fa330e544c587c8c8a55920b0e48a55c13b2a5b8942618baf4d`.

## Reproduce

Use the [guide](../../../docs/app-frameworks/tanstack-start-pg.md) from a clean
copy. Run `npm ci`, `npm test`, `npm run build`, and `npm run typecheck`.
Use a new assigned PostgreSQL 17 database and an isolated private bucket.
Run `node tests/services.mjs` with the documented environment and two unused
`TEST_WEB_PORTS`. The check retains only synthetic data and stops its children.
The optional database restart requires ownership of the entire database service.
The shared HTTP checker, `tests/check_portal.py`, exercises running web and job
containers without restarting services.

## Remaining live Stack proof

The isolated tests are preparation for the full Stack deployment. The shared
system must still prove MMX deploy and previous-image rollback, actual
`switch_database_primary` in both directions, PgBouncer, public HTTPS and ingress
limits, real R2 authorization/TLS, current/previous asset mounts, open-browser
server-function behavior across two releases, and Stack backup recovery.
A database restart is not a primary promotion. Physical promotion tests, when
recorded below, do not execute the Stack playbook. Logical restore and copied S3
objects do not prove pgBackRest or upload backup recovery. An additive migration
check uses the previous SQL shape, not a separate previous app image.

## Retained asset fix

The retained-file tests pass for GET, HEAD, exact bytes, MIME types, missing files, unsupported methods, and path traversal refusal.
The tests reject encoded dot segments, hidden paths, backslashes, NUL bytes, and escaping symlinks.
CI tested and built the fixed source on Node 24 from the pinned image.
A fixed release followed by a changed-asset release passed on the shared Stack.
All 3 old asset URLs returned the original bytes and correct content types at the new loopback origin.
The held page saved a record without reloading. An independent authenticated request read back the saved record.
The memory figures above come from the earlier release.
