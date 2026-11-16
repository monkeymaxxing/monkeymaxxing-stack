# Variances and guidance needs

Phase 1 proves a free export and independent local conversion. A fresh agent replayed the guide successfully on 2026-11-04.

| Difference | Guidance |
| --- | --- |
| TanStack Start needs a server | Use Nitro's Node preset. Exercise real server functions, not only static pages. |
| GitHub verification can block free sync | The person completes verification. Free per-file Code copy/download remains an alternative. |
| Storage downloads have ZIP wrappers | Inspect actual file formats. Unpack objects before hashing and database archives before direct pg_restore use. |
| Archive tools differ from the database version | The source is PostgreSQL 17.11. The archive was produced by pg_dump 18.6. PostgreSQL 18's client read the archive. |
| Managed services do not leave with code | Replace auth, data APIs, private storage and jobs explicitly. |
| Source RLS becomes server ownership checks | Keep database credentials private. Prove exact-ID cross-user refusals. |
| Source sessions cannot transfer | Preserve bcrypt hashes and UUIDs. Require a new login and use shared PostgreSQL sessions. |
| Source descriptions are absent | Destination migration 2 adds empty descriptions. Refuse unexpected source columns rather than discarding values. |
| Source jobs are pending | Preserve pending IDs and empty outputs. Generate completed evidence only at the destination. |
| Maintenance is paused | Preserve the real cron row as metadata. Import does not enable schedules. |
| Cluster IPC outlives HTTP shutdown | Disconnect worker IPC when stopping the app. The final test proves clean process exit. |
| Shell-sourced database URLs contain `&` | Quote the URL. Node env-file loading alone does not test shell instructions. |
| Manual import populates the database | Use another empty database for the automated rehearsal. |
| Older S3 SDK pulls an affected XML parser | Update the added SDK. The final production audit has zero critical advisories. Keep the test substitute private and prune development dependencies. |
| Local storage needs an explicit start/stop path | The guide supplies S3rver settings and process-specific stop commands. |
| Stronger identity requirements are unsupported | Refuse MFA, passkeys, SSO, anonymous and unconfirmed users pending a separate migration design. |

## Versions and revisions

The source has no Git commit because GitHub sync is pending verification. The complete source export contains 105 files.

Source file-manifest SHA-256: `2421a4d42864febc04cedd186e477a0a411068ad3c2bb6db950d4a2fc6d484e9`.

Destination app-manifest SHA-256: `a0e3a06d7f240a4815d3c27bebf0f30dff10e5dd04e5d8ad2928e2b01aafe644`.

Destination `package-lock.json` SHA-256: `03537a0a2a0a65f3da89aaeff0afdde9afc4ea9f9488d2973df742a12af2c219`.

| Component | Tested version |
| --- | --- |
| Node | 24.22.2 |
| npm | 11.19.1 |
| PostgreSQL server | 17.11, Debian 17.11-0+deb13u1 |
| TanStack Start | 1.168.60 |
| TanStack Router | 1.170.41 |
| React / React DOM | 19.2.8 |
| Vite | 8.1.5 |
| Lovable build configuration | 2.26.5 |
| Nitro | 3.0.260603-beta |
| pg | 8.23.1 |
| bcryptjs | 3.0.3 |
| AWS S3 client / presigner | 3.1161.0 |
| S3rver, test substitute | 3.7.1 |

Original direct dependency versions were pinned from the exported Bun lockfile. The independent app adds its backend dependencies and uses a frozen npm lockfile.

## What ran

A first reader exported the real code, database and private objects through native free routes. A second reader replayed archive conversion and compared exact source values.

The archive contains two users, two identities, two records, two documents, two pending jobs, two source migration rows and one paused cron row.

Both original object downloads are 27 bytes after unpacking. Each SHA-256 equals the source inventory and document metadata.

Helper commands passed four Python tests and three Node tests:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 examples/app-platform-migrations/from-lovable/read_export_test.py
node --test examples/app-platform-migrations/from-lovable/inspect-project.test.mjs
```

The fresh runtime replay ran these commands against isolated PostgreSQL 17 and S3-compatible storage:

```sh
npm ci
NITRO_PRESET=node-server npm run build
npm run rehearse
```

All commands exited zero. The final rehearsal recorded `passed=true` and 15 checks:

1. Existing fixture passwords verify against exported bcrypt hashes.
2. Initial-schema import preserves fixture counts.
3. Repeat import refuses a nonempty destination.
4. An unexpected source column stops conversion.
5. Exact rows, ownership, hashes, object bytes, queues and schedules match the export.
6. Two web servers each run two workers, listen on assigned ports and return `/healthz`.
7. Original-password login and shared sessions work across servers. Wrong passwords fail.
8. Ordered migrations run once. The description migration preserves rows with previous-schema web processes running.
9. Two-way ownership refusals, forged ownership, CRUD and private S3 byte equality pass.
10. Anonymous reads and cross-site writes are refused.
11. A held job is skipped. Terminating the owning database connection rolls back unfinished work. Concurrent workers finish each job once.
12. Customer-triggered queue and report execution work.
13. Logout revokes access on the second server immediately.
14. New registration starts with no owned data.
15. All web processes exit gracefully on SIGTERM.

After pruning development dependencies, five additional runtime checks passed: the S3 substitute was absent, the current SDK remained, health responded, imported-account login and owned data worked, and shutdown completed.

The built output contains no literal old backend host, old public source domain or HTTP(S) Lovable/gpteng CDN/error-reporting URL. This static scan does not prove behavior with the source blocked.

The generated routing unit test also passed. A real browser logged in with an existing password, displayed Account through a TanStack server function, queued a report and completed the report through the second server function.

The browser report output was `record_count=1` plus LF. Logout returned the browser to Login. The browser view and server-function responses were inspected directly.

## Limits

The proof used S3rver for API compatibility and byte equality. Real R2 policy, bucket privacy and external signed-URL reachability remain separate checks.

The Node build ran directly on Linux. The supplied Dockerfile was not built into a container image during phase 1.

No Stack deployment, primary switchover, two physical app servers, source shutdown, final freeze, traffic switch, downtime measurement or post-cutover rollback was run.

Email verification, password-recovery delivery, MFA and external identity-provider migration are outside this matching fixture. The source fixture disables email confirmation.

The final production dependency audit reports zero critical, zero moderate and two high advisories. The retained source versions are Vite 8.1.5 and Zod 3.25.76.

The app runs prebuilt Nitro, and the portal source has no direct Zod import. Review the advisories before public exposure or new code paths.

The test-only S3rver dependency has older parser/multipart advisories. The substitute binds loopback, and the Dockerfile prunes development dependencies before copying runtime files.

The source remains intact. Native database export triggers the platform's standard download email. No paid plan, source application edit or source job execution was used.

## Test data command proof

2026-11-05: `seed-test-data` fills laptops or staging and adds bulk `--accounts` generation. The fixed fixture keeps its blank descriptions. Syntax checks passed. On isolated Debian 13, Node 24.22.1, PostgreSQL 17 and pinned S3Mock, the seed suite passed 1 test, `npm test` passed 1 test, the production Node-server build passed, and `node rehearse.mjs` passed all 15 checks using a fresh synthetic snapshot. Source-inspector tests passed 3 tests and export-reader tests passed 4 tests. Seed checks proved allowed/refused environments, exact fixed rows and bytes, 1,000 accounts twice, a shared generated hash and smaller-count preservation. No source platform was accessed. Recorded images predate this change.

- 2026-11-05: Invalid `--accounts` checks now require the exact usage message on stderr and unchanged database rows. The seed suite, unit tests, build, export-reader checks, and full isolated PostgreSQL 17/S3 rehearsal passed.
