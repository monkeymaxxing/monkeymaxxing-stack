# Railway migration test record

Export and standalone rehearsal passed on 2026-11-04.
An independent agent restored a separate database and bucket by following the guide, then passed all 11 customer checks.
The production cutover results are recorded below.

## Versions and revisions

| Component | Tested value |
| --- | --- |
| Source application revision | `d12bb6bf588979830164d74930107336c58a0e2c`, verified against the source repository |
| Database helper | Unchanged from the Stack |
| Source PostgreSQL / pg_dump | 18.6 / 18.6 |
| Destination PostgreSQL / pg_restore / psql | 17.11, Debian package `17.11-0+deb13u1` |
| Destination system | Debian 13, Linux AMD64, isolated test VM |
| Native Node.js / npm | 22.23.4 / 10.9.9 |
| Container Node.js | Node 22, `node:22-bookworm-slim` |
| Container base digest | `sha256:9f0dde62d10e7ff7a310ecaebd66225f6b46c17e6cb778449a77b05d3541bea2` |
| Final application image ID | `088b891c491a1ab7a1457b2e7c794be1f453502e2bfedbe1765c3f65768975df` |
| Express / pg / bcryptjs | 5.3.0 / 8.23.1 / 3.0.3 |
| AWS S3 client SDK | 3.1161.0 |
| Podman | 5.4.2 |
| S3 test service | `adobe/s3mock@sha256:ab01a6946750f451ca215a47e91030695b260e4003b8a5a6201d25029b8fca92` |

The dependency lockfile pins the installed package versions.
The copied database helper's SHA-256 is `1c4bd9fda5c588efa20d87d0866fa0cd63e27309953a86164c597e49b7d0364c`.
Original migration SQL remains byte-for-byte unchanged.

## What ran

The export read the actual Railway PostgreSQL public TCP proxy and native virtual-host S3 bucket.
A read-only transaction supplied the snapshot shared by the row inventory and `pg_dump`.
The saved earlier dump predated newer schedule receipts, so the rehearsal used a refreshed database export.
The new object reads matched the earlier saved object hashes.
No source setting or application row was changed by the migration commands.

```sh
node data-transfer.mjs export
python3 tests/prepare-rehearsal.py
node tests/create-rehearsal-bucket.mjs
node data-transfer.mjs restore
npm run check --prefix app
node tests/rehearsal.mjs
podman build -t localhost/railway-portal:phase1 app
```

The guide lists the required protected inputs and environment variables for those commands.
The first restore finished at 01:50:50 UTC. The first customer rehearsal passed at 01:51:16 UTC.
The independent restore finished at 01:51:33 UTC. The independent customer rehearsal passed at 01:51:36 UTC.
Each replay used separate app files, a fresh dependency install, database, bucket, private export copy, and web ports.
The replay reused the prepared PostgreSQL and S3 test services.

## Results

The restored baseline contained two users, zero sessions, two records, two documents, six jobs, four schedule receipts, and two migration versions.
Two jobs were pending and four jobs retained completed output.
Every table matched the source snapshot's exact row digest before login or worker execution.
The zero-session baseline does not prove restoring a pre-existing active session.
New destination sessions crossed two web servers with two worker processes each.

| Check | Result |
| --- | --- |
| Users, bcrypt hashes, stable IDs, owner mappings, job output and migration checksums | Exact source-to-destination comparison passed |
| PostgreSQL 18 to 17 | Passed after removing only the unsupported `transaction_timeout` session SET |
| Private object bytes | Two objects, 54 bytes total, original keys and SHA-256 preserved |
| Existing passwords | Barbara and Michael logged in with the existing fixture password |
| Authorization | Foreign record reads/mutations, documents, jobs and reports returned 404; non-admin worker control returned 403 |
| Records and new files | CRUD and new upload/download byte equality passed |
| Sessions | Login crossed servers; logout revoked the shared session |
| Imported pending work | Stayed paused until the disposable copy was explicitly resumed |
| Concurrent and interrupted jobs | SKIP LOCKED skipped a held job; a severed transaction rolled back; each pending report completed once |
| Scheduling | Two schedulers committed one UTC receipt and archived one eligible report |
| Jobs entry point | The real jobs process completed an HTTP-enqueued report |
| Migrations | Original migration ledger and checksums preserved; repeated migration commands made no row changes |
| Shutdown | Web clusters and jobs exited cleanly on SIGTERM |
| Container | Final non-root image served health, existing login, Secure/HttpOnly cookie attributes, and a restored document |
| Source after rehearsal | Health returned 200; anonymous native bucket object access returned 403 |

The independent agent reported no blocking guide gap in destination preparation, restoration, or customer checks.
A value-based scan found no source credentials, fixture password, or bcrypt hash values in the deliverable files.

## Limits and next proof

The source-18 to destination-17 result applies to this portal schema. PostgreSQL does not guarantee a general major-version downgrade.
S3Mock proves request shape and byte transfer. S3Mock does not enforce production bucket authorization.
Native Railway virtual-host reads passed. Real destination R2 permissions and virtual-host addressing remain unproved.
The HTTP container probe checked cookie attributes, not an HTTPS browser session.

Live Stack deployment, real primary switching, PgBouncer, backup recovery, production traffic switching, and production downtime remain unmeasured.
Migration 002's original source deployment is documented separately. This rehearsal checks the restored ledger and idempotency, not another rolling additive deployment.
The independent replay did not repeat source exports or dependency-service installation.
Source cron continued to run during read-only rehearsal. Disable source cron through the approved final cutover plan before enabling destination execution.
The disposable destinations were changed by testing and cannot be reused as final production imports.

## Production cutover, 2026-11-04

The portal ran on two production app servers with PostgreSQL 17.11, PgBouncer, and private Cloudflare R2 storage.
The destination release was `69f2b6d86898f6f903946da23eb54d0f43997527`.
The published image index digest was `sha256:e2cf7ffa94a5182be31e3ba6347ab2501491a46dbfee7e642be17b5306381eb9`.
CI checked JavaScript and built the actual non-root Node 22 image.
The runtime read-only registry token fetched the exact image manifest.

PgBouncer rejected the original Node startup `statement_timeout` parameter.
The corrected app retained `query_timeout=12000` and used `SET LOCAL statement_timeout='10s'` inside transactions.
The real app pool and transaction passed through the production PgBouncer after the change.
Migration commands continued to connect directly to Postgres.

The source web and worker deployments stopped before export. The native cron schedule was disabled.
Railway retained historical deployment status `SUCCESS` after stopping. Runtime `deploymentStopped=true` proved execution had stopped.
The final export finished at 05:51:29.777 UTC. Exact restoration finished at 05:51:36.303 UTC.
The final snapshot held two users, two sessions, two records, two documents, six jobs, and 53 schedule receipts.
Two jobs were pending. Two private objects totalled 54 bytes.
Every table digest and object SHA-256 matched before destination logins changed the sessions table.
A later read-only source snapshot still matched the final export exactly.

| Live check | Result |
| --- | --- |
| Returning users | Both existing passwords accepted over public HTTPS, with stable user IDs and administrator permissions |
| Records | Exact owned record content and timestamps preserved |
| Private files | Both original files downloaded with unchanged SHA-256 values |
| Ownership | Foreign records, files, and jobs refused; ordinary user worker control refused |
| Cookies and sessions | Secure, HttpOnly, SameSite=Strict cookies; one HTTPS-issued session worked on both app servers |
| Existing reports | Completed report output preserved |
| Pending reports | Both imported pending reports completed after the existing administrator resumed the destination worker |
| Schedule | All 53 original receipts preserved; a new five-minute UTC receipt committed without duplicates |
| Destination writes | New record creation returned 201; the temporary acceptance record was removed with 204 |
| Runtime independence | Neither app server's runtime connection values referenced Railway |
| Private R2 | Anonymous S3 request denied with HTTP 400; managed public domain disabled; no custom public domains |
| Upload backup | Copy service succeeded; locked backup contained two objects and 54 bytes |
| After source deletion | Both existing logins and both original private file downloads still passed |

The write freeze started at 05:47:32.492 UTC. Account and job checks passed at 05:53:13.567 UTC.
The explicit new-entrypoint write check passed at 05:54:55.934 UTC.
The conservative freeze-to-switch window was 7 minutes 23 seconds.
The first stop checker waited on historical deployment status, adding an avoidable delay before export.
This measured cutover window does not guarantee another application's downtime.

The source database was stopped before project deletion.
The authenticated provider dashboard then showed zero active projects and one deleted project.
Railway's native 48-hour deletion grace period remains. Permanent physical removal was not claimed or forced.
The retained final export supports recovery. Destination writes after the export still require reconciliation before rollback.
The new provider hostname requires a fresh login. No customer-owned custom domain was supplied or changed.

No paid Railway upgrade or subscription was started.
No new database-failover or full recovery drill ran for this cutover because those shared-system checks were outside the migration-specific brief.
The schedule had no report older than 30 days. New receipts prove execution, but not a positive archive count.
The existing standalone rehearsal separately proved archiving an eligible report.

## Test data command proof

2026-11-05: `seed-test-data` fills laptops or staging and adds bulk `--accounts` generation without changing the fixed fixture. JavaScript syntax checks passed. On isolated Debian 13, Node 24.22.1, PostgreSQL 17 and pinned S3Mock, `node --test tests/seed-test-data.test.mjs` from `app/` passed 1 test, and `node tests/rehearsal.mjs` passed its existing 11 behavior checks against a fresh synthetic snapshot. The seed test proved both allowed environments, production/unset refusals, exact fixture rows and bytes, 1,000 accounts twice, one generated hash and smaller-count preservation. No source platform was accessed. Recorded images predate this change.

- 2026-11-05: Invalid `--accounts` checks now require the exact usage message on stderr and unchanged database rows. The seed suite and full isolated service rehearsal passed with PostgreSQL 17 and S3-compatible storage.
