# Vercel migration rehearsal test record

## Variances and guidance needs

The source archive and objects are reusable migration inputs. Code alone cannot recreate managed accounts, files, or scheduling.
This record covers phase 1. The production cutover, full Stack deployment, real database promotion, and backup recovery remain separate checks.

## Versions and artifact identity

- Exported source code revision: `88f7a580c27039c61877eaafeebf1b207c39da8c`.
- Deployed source application revision: `507ab168e6cb3fb55eefda0a9ea755d058c8813c`.
- Next.js 16.4.5, React 19.3.1, pg 8.23.1. Exact dependencies are pinned in `package-lock.json`.
- Native PostgreSQL 18.6 archive, produced by pg_dump 18.6.
- Native archive SHA-256: `a05b7b87ea1fbda357ede36ec190c90460db34d2ed0af014883f6e6f6c60a7c4`.
- Source code ZIP SHA-256: `f730c95235bbc04b84098192000319a089c13cfcf6e687dc9fd7946f6ab80f76`.

The destination ran on Debian 13 x86_64, Node 24.22.2, npm 11.19.1, and PostgreSQL 17.11.
Storage used Adobe S3Mock pinned to `sha256:ab01a6946750f451ca215a47e91030695b260e4003b8a5a6201d25029b8fca92`.
Password hashes use `@better-auth/utils` 0.4.2, matching the verified native verifier.
The final tested image ID is `69a23aaaf43f9b190cf881dd47e96ae5a925b9ca40617f5cd1f9d2dc3f989e48`.
The migration source is uncommitted. A file SHA-256 manifest identifies the reviewed runtime files.
No image was published and no source revision was invented for the new example.

## Executed checks

2026-11-05: Renamed the command to `seed-test-data` for laptops and staging and added `--accounts`. JavaScript syntax checks passed. On isolated Debian 13, Node 24.22.1, PostgreSQL 17 and pinned S3Mock, `node --test tests/seed-test-data.mjs` passed 1 test, `npm test` passed 2 tests, the optimized build passed, `node tests/services.mjs` passed 13 groups, and `node tests/rehearsal.mjs` passed 5 groups using a fresh synthetic snapshot. Seed checks proved both allowed environments, production/unset refusals, exact fixtures, 1,000 accounts twice, one generated hash and smaller-count preservation. No source platform was accessed. The recorded image above predates this change.

All checks ran on 2026-11-04 in an isolated Linux guest.
Only synthetic source data was used.

| Check | Result |
| --- | --- |
| Reuse original code ZIP and native database dump | Checksums match the source export record. No duplicate provider export was needed. |
| Native Blob inventory | Two objects match the two database references and byte counts. |
| Configuration inventory | Read-only project API exported 21 environment-variable names. Values were discarded. |
| Native archive restore | Version 18.6 archive restored into isolated PostgreSQL 17.11, including native auth. |
| Canonical extraction | Two password accounts, records, documents, jobs, and object files; zero native sessions. |
| Install, unit tests, optimized build | Pass. Two unit tests. No build-time database credentials. |
| Empty database health and ordered migrations | Pass. Two versions applied once; additive description preserves old SQL behavior. |
| Staging seeds | Pass. Repeat seed preserves password hashes. Production seed is refused. |
| Imported source data | Exact native user hashes, stable IDs, owners, timestamps, record text, pending state, and object bytes retained. |
| Repeated import | Identical snapshot accepted. A different snapshot is refused. |
| Import failure safety | Conflicting destination bytes survive. Corrupt export bytes are refused. Failed imports commit no app rows. Corrected imports succeed. |
| Existing account login | Existing passwords work with independent destination auth. Sessions work across two clustered web processes. |
| Ownership, CRUD, files, and logout | Pass. Foreign record mutation and file access return 404. Logout on server A revokes access on server B. |
| Destination queue | Two workers finish imported pending reports. Separate offline completed-job case retains prior output. |
| Worker interruption | Killed transaction rolls back. Another worker completes the waiting report. SIGTERM finishes an active transaction. |
| Manual archive | Marks completed reports older than 30 days while retaining output. |
| Due UTC schedule | Controlled guest clock after 03:00 produced exactly one daily run across concurrent callers. Repeated calls produced no duplicate. Clock restored. |
| Health deadline | Locked migration table returns 503 in approximately 1,505 ms. |
| Database reconnection | Database restart recovers without changing web processes or URLs. Approximately 10,784 ms includes the restart itself. |
| Web shutdown | An in-flight HTTP mutation drains and the clustered launcher exits 0. |
| Container artifact | Build passes. User ID 1000, packaged migration/import commands, two clustered containers, existing login, exact download, and logout pass. |
| Source independence | Container runtime passes while every non-loopback guest connection is rejected. |
| Fresh-agent replay | Independent app copy, install, tests, build, offline export, fresh database import, and all five rehearsal groups pass. |
| Guide review | Fresh reader found and resolved the scheduler proof gap. Final guide links and deployment settings pass review. |

The automatic rehearsal's initial scheduler assertion permits zero runs before 03:00 UTC.
A separate controlled-clock proof establishes due execution, atomic archiving, and daily duplicate protection.
The test does not claim a real wall-clock Cron delivery was awaited.

The source's final native dump contains pending reports only.
The completed-output import check adds a synthetic completed row to a separate offline restore.
No completed job or extra row was written to the live source.

## Remaining live checks

- Deploy on the shared Stack system and verify public HTTPS behavior.
- Switch the real database primary in each direction while web and job processes keep running.
- Check transaction-mode PgBouncer if enabled.
- Verify real R2 bucket authorization and restore uploaded objects independently.
- Restore Stack backups and compare accounts, sessions, rows, jobs, and object bytes.
- Freeze source writers and dispatch, transfer final deltas, disable native Cron, switch traffic, and measure downtime.
- Prove rollback boundaries after destination writes begin.

The source fixture is hand-written on Vercel. The rehearsal does not prove v0's AI-generation or browser GitHub-sync workflow.
No Edge middleware, image optimizer, ISR, or Server Action existed in the tested source.
Incoming apps using additional platform features need explicit replacement and multi-instance checks.
Native sessions are invalidated deliberately. Password reset, external identity providers, organizations, and email delivery need additional mappings.
No purchase, plan upgrade, source deployment, source schedule change, or production cutover was performed.

- 2026-11-05: Invalid `--accounts` checks now require the exact usage message on stderr and unchanged database rows. The seed suite, unit tests, build, full service suite, and independent import rehearsal passed with isolated PostgreSQL 17/S3 storage.
