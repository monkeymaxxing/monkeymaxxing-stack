# Variances and guidance needs

The migration rehearsal passed on November 4, 2026. A separate reader replayed the final guide against a new empty database and bucket.
The final replay reported **9 tests passed, 0 failed, 0 skipped**, plus all seven command checks.
The native Render source was deleted after export and restore verification. No public traffic cutover or complete Stack deployment is claimed.

## Source and exported fixture

The handwritten source ran Node.js 24.22.1, Express 5.3.0, pg 8.23.1, and bcryptjs 3.0.3.
Render hosted a disk-backed web service, PostgreSQL 17.11, one background worker, and one cron service.
The source's custom bcrypt accounts used cost 12. The original private Git archive and dependency lockfile were exported.
The destination updated AWS SDK from the source's 3.922.0 to 3.1161.0 after a dependency audit found a critical advisory.
The final destination dependency audit reported zero vulnerabilities.

The SQL snapshot contains two users, two identity mappings, two records, two document rows, five jobs, and three session rows.
Two jobs are pending and three contain completed output. The snapshot also contains controls, a schedule, an occurrence, and both migration versions.
The second source deployment added `records.description`. Existing records remained, then descriptions were filled through authenticated edits.
Native disk deployment stops the previous web instance, so overlapping old/new release behavior was not proved.

| Account | Record and description | Exact private document | SHA-256 |
| --- | --- | --- | --- |
| barbara@example.com | Barbara invoice; First synthetic record | `Barbara synthetic document` followed by LF, 27 bytes | `05fc126dc203e0579d73a6365e130ba77d1f422d87042b362456a2885029d32a` |
| michael@example.com | Michael invoice; Second synthetic record | `Michael synthetic document` followed by LF, 27 bytes | `784483c538543c904f1232e9c939417711e771b531e3f04c3d45f6699ad65c55` |

Both users were registered and populated through the hosted app.
Hosted checks proved owned reads, cross-owner refusals, CRUD, exact private downloads, pending jobs, and logout.
The native worker produced `record_count=1` followed by LF for owner-only reports.
The configured native cron was manually triggered and persisted a scheduled occurrence. No daily timer occurrence was awaited.

## Export and destination evidence

Native SSH exported a shared database snapshot, every public application table, and the mounted document bytes.
SQL and file exports matched the independently recorded source IDs, owners, values, lengths, and hashes.
PostgreSQL 18.6 `pg_dump` exported the PostgreSQL 17.11 source. PostgreSQL 17.11 `pg_restore` accepted the custom-format archive.
The destination used Debian 13, native Node.js 24.22.2, PostgreSQL 17.11, and a separate S3-compatible test service.
The container check used Node.js 24.22.1 and the final lockfile.

| Check | Measured result |
| --- | --- |
| Export artifact and object checksums | Passed before restore |
| Exact restored rows, password hashes, sessions, migrations, schedules | Passed before destination mutation |
| Existing passwords, stable IDs, shared sessions across two web processes | Passed |
| Owned data, cross-owner record/file/job refusals, exact old/new file bytes | Passed |
| CRUD, registration, origin refusal, cross-process logout | Passed |
| Staging seed reruns | Preserved passwords and did not duplicate fixtures |
| Concurrent and interrupted job claims | Each job completed once with owner-only output |
| Daily schedule occurrence | Concurrent calls committed one new occurrence |
| App restart | Existing sessions survived, then logout revoked the sessions |
| Object import rerun | Identical objects accepted twice |
| Restore into populated database | Refused before `pg_restore` ran |
| Container | Built, returned HTTP 200 health, exited 0 after SIGTERM |

The replay used an unreachable first database address before the live primary.
That result proves connection selection through the copied Stack helper. The rehearsal did not promote a replica or prove database failover.
The initial replay environment had a database-URL substitution bug. Correcting the environment wrapper required no product change or source-data reset.
The final dependency-updated replay completed all checks in about 6.5 seconds, excluding restore and setup.

## Completion limits

The rehearsal proves portability of this source app's code, application authentication, SQL state, native disk files, queue, and schedule state.
The rehearsal does not prove destination domain/TLS routing, real R2 permissions, database-primary switching, backup recovery, or production cutover.
The source native cron was triggered manually, and the destination occurrence check called the scheduler directly.
The source Git revision and protected export remain available for review. No export containing password hashes or secret values belongs in this example.

## Test data command proof

2026-11-05: Renamed the seed to `seed-test-data` for laptops and staging and added `--accounts`. The fixed HTTP fixture keeps its empty descriptions. Syntax checks passed. On isolated Debian 13, Node 24.22.1, PostgreSQL 17 and pinned S3Mock, `node --test tests/seed-test-data.test.mjs` passed 1 test and `node --test tests/rehearsal.test.mjs` passed all 9 tests against fresh synthetic data. Checks proved allowed/refused environments, exact fixture rows and bytes, 1,000 accounts twice, a shared generated hash and smaller-count preservation. No source platform was accessed. Recorded images predate this change.

- 2026-11-05: Invalid `--accounts` checks now require the exact usage message on stderr and unchanged database rows. The seed suite and full isolated service rehearsal passed with PostgreSQL 17 and S3-compatible storage.
