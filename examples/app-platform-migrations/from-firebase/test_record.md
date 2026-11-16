# Variances and guidance needs

Firebase password portability requires its modified scrypt algorithm, each
user's hash and salt, and the project's secret hash settings. Standard scrypt
alone is not enough. The Admin SDK and CLI can encode the same hash bytes with
different base64 alphabets. The portable export normalizes the encoding and
compares decoded bytes with the native CLI export.

Firebase sessions do not move into the destination. Users sign in again with
their existing password. Firestore security rules become server authorization,
private Storage objects move separately from metadata, and Cloud Functions and
Cloud Scheduler become a separate jobs process with PostgreSQL transactions.

## Source and export proof

The source portal was written by hand and deployed with native Firebase Auth,
Firestore, Cloud Storage, callable and scheduled Cloud Functions, and Hosting.
The Auth API reported subtype `IDENTITY_PLATFORM`; Identity Platform was enabled
before source registration. The source ran on Blaze. Actual billed usage was not
measured. The source used React 19.2.0, Firebase web SDK 13.2.0, Functions SDK 7.4.0,
Admin SDK 14.5.0, Functions Node.js 22, esbuild 0.25.11 and Firebase CLI 15.34.2.
The second release added descriptions without removing old records or requiring
old clients to send the new field.

The verified snapshot contains two users, two owned records, two private
27-byte documents, two pending reports, one completed report, one daily schedule,
one recorded scheduled occurrence and two source schema migration documents.
The completed report contains `record_count=1` followed by LF. Each document's
bytes match the shared synthetic fixture and its recorded SHA-256.

All 31 source-fact and configuration comparison checks passed: account IDs,
email, disabled and claim fields, decoded password fingerprints, native CLI versus SDK password bytes,
canonical export encoding, every Firestore document and field, owners, exact
fixture values, controls, report states/output, schedule/occurrence/migration
ledgers, object keys/lengths/hashes, all manifest checksums, source archive bytes
and private file permissions. Native function, scheduler, Firestore, bucket
and Hosting configuration files are included in the checked manifest; observed
runtime environment variable names match the source facts.

The protected snapshot's manifest SHA-256 is
`5e6a4ece0334080933c76dbabf9a5048bec126811af4a035f1c70f4d75d83d46`.
The actual exports contain credentials and are not part of this example.

## Destination environment

The final rehearsal ran on 2026-11-04 in an isolated Debian 13 amd64 VM with
PostgreSQL 17.11 (`17.11-0+deb13u1`), Node.js 24.22.1, npm 11.19.1 and Podman 5.4.2.
The S3-compatible service was Adobe S3Mock, pinned as
`docker.io/adobe/s3mock@sha256:ab01a6946750f451ca215a47e91030695b260e4003b8a5a6201d25029b8fca92`.
The source was frozen before export. Destination report and schedule processing
stayed paused until each disposable behavior check explicitly enabled them.

## Final independent replay

A separate reader followed the guide into a new empty PostgreSQL database and
separate private S3 buckets. The replay independently verified the final manifest,
all 17 checksums, full file coverage, native/portable Auth verifier equality and
both original objects before import. Both original passwords authenticated after
import without reset. Repeated migrations and repeated exact object imports
succeeded. All 13 reported tests passed; none failed, skipped or was cancelled.

| Final suite | Result | Test duration |
| --- | --- | --- |
| Official Firebase password vector | 2 passed, 0 failed | 147.70 ms |
| Export/import and portal behavior | 10 passed, 0 failed | 3309.33 ms |
| Separate staging migration/seed behavior | 1 passed, 0 failed | 2394.83 ms |

The ten behavior results include nine subtests and their parent. The behavior
suite has a 120 second deadline. Its connection check keeps the existing
15 second recovery bound. The final measured health recovery was 30 ms, with
both probes returning HTTP 200 and both web process IDs unchanged. A terminated
idle connection can expose HTTP 503 before recovery; the check records such
responses and polls only read-only health requests. It then proves the old
session, owner isolation and one fresh write, without replaying a mutation.

An actual browser check also passed for both existing users through the sign-in
and sign-out forms. Each user saw only their invoice and private document list;
the other user's content was absent. Authenticated document downloads matched
the original bytes, and sign-out returned to the account form. The rendered
page was checked visually in the browser.

## What the behavior checks establish

- Returning users retain their stable IDs and passwords. Portable account
  fields and all raw Firestore documents match the export. Destination migration
  commands run twice without changing their ledger.
- PostgreSQL sessions work across two web processes and logout revokes access
  across both. Owned reads/changes refuse another owner's records, files and jobs.
- CRUD, new registration and private upload/download work. Imported file hashes
  match. Conditional S3 writes refuse overwrite; repeated exact imports succeed.
- A real PostgreSQL trigger forces a document metadata insert to fail. The API
  returns failure, the newly uploaded private bytes survive, and every existing
  metadata row stays unchanged. The test removes only its trigger and object.
- Concurrent workers complete each pending job once. A killed transaction
  releases its locked job for another worker. Output and completion commit
  together, and the separate jobs command processes new work.
- Concurrent schedule workers record one due occurrence and archive an old
  completed report once. The daily schedule advances by 24 hours in UTC.
- After PostgreSQL drops existing connections, read-only health probes record
  transient errors and recovery within the existing 15 second bound. The same
  web processes retain sessions/ownership and accept one fresh write. No
  interrupted mutation is replayed automatically.
- A separate staging suite proves the additive description migration preserves
  an old-release row, transaction rollback leaves no partial user, staging seeds
  are idempotent, file bytes match and production seeding is refused.

## Limits

The rehearsal uses one real PostgreSQL server and S3Mock. It does not prove a
Stack deployment, a live primary/replica promotion, PgBouncer behavior, real R2
permissions, traffic cutover, full-system recovery or production scale.
Dropped-connection recovery is separate from a primary/replica failover.

The source's historical upload compensation could remove bytes after an
uncertain metadata commit. The destination keeps private objects on metadata
errors for manual reconciliation. No automatic retry or reconciliation service
was added. The final replay verifies that retention behavior.

## Test data command checks

2026-11-05: `seed-test-data` now fills laptop or staging databases and accepts `--accounts`. JavaScript syntax checks passed. In an isolated Debian 13 guest with Node 24.22.1, PostgreSQL 17 and pinned S3Mock, `node --test tests/staging.test.mjs` passed 1 test, `npm run test:password` passed 2 tests, and `npm test` passed all 10 tests against a freshly generated synthetic Firebase-shaped export using the public verifier vector. Seed checks proved exact fixture preservation, 1,000 accounts twice, shared generated hash, smaller-count preservation and both allowed environments plus production/unset refusals. No source-platform account was accessed. Previously recorded images predate this change.
