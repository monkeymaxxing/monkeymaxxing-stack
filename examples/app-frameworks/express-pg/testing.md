# Variances and guidance needs

Express uses the unchanged Stack pg helper for the multi-host DATABASE_URL.
Each Node cluster worker owns a four-connection pool. Reads use the primary.
Native SQL migrations and PostgreSQL jobs use transaction locks.
Hashed PostgreSQL session tokens span app instances and bcrypt hashes protect passwords.

## Test state

Real isolated services, primary promotion, final image execution, logical recovery and fault checks passed.
Independent final-source guide replay passed. No live Stack deployment has run.

## Versions and artifact identity

Checked 2026-11-04 on Debian 13 x86_64 with PostgreSQL 17.11, Node 24.22.2,
Express 5.3.0, pg 8.23.1, @aws-sdk/client-s3 3.1161.0, bcryptjs 3.0.3,
multer 2.5.0 and Podman 5.4.2. Python 3.13.5 and psycopg 3.2.6 ran service checks.
Exact transitive Node dependencies and integrity hashes are in package-lock.json.

Express's version was checked against the [official package registry](https://registry.npmjs.org/express/latest).
HTTP behavior follows the [Express 5 API](https://expressjs.com/en/5x/api/).
Worker behavior follows [Node 24's cluster documentation](https://nodejs.org/docs/latest-v24.x/api/cluster.html).
The native Node archive was verified against its published SHA-256 checksum.

source-sha256.json identifies executable, build and test inputs.
The copied pg helper was byte-identical to the Stack's helper when tested.
The Node base is pinned by digest in Containerfile.
S3Mock used docker.io/adobe/s3mock@sha256:ab01a6946750f451ca215a47e91030695b260e4003b8a5a6201d25029b8fca92.
The final tested image ID is b102f7ff87a66452bba29514760defad9641f6285d429b1cff4ddaf3dcfeb6f6.

## Executed proof

- 2026-11-05: The full isolated PostgreSQL 17/S3 suite passed with complete first-run fixture snapshots. Every fixed row and password hash survived reruns, two 1,000-account runs, and a different `FIXTURE_PASSWORD`. Previously recorded image IDs predate the test changes.

- 2026-11-05: `seed-test-data` now supports development and staging plus `--accounts`. JavaScript syntax checks, the cache unit test, and `python3 tests/services.py` passed on Debian 13 with PostgreSQL 17.11 and S3Mock. The suite checked refusals, exact fixtures, 1,000 accounts twice, unchanged documents/jobs, HTTP ownership and storage, workers, and shutdown. The image ID above predates this change.

- Fresh npm installation, JavaScript syntax checks and one deduplicated pg 8 tree passed.
- Migration 1, old title-only rows, concurrent migration runners, migration 2 and repeat migration passed.
- Production seeding refused. Staging seeding twice preserved exact accounts, records, files, hashes and jobs.
- Two web instances, each with two Node cluster workers, shared sessions and logout revocation.
- Registration, password login, owner-scoped CRUD, guessed document/report IDs and foreign-Origin refusal passed.
- Private upload/download bytes and SHA-256 matched.
- Two workers skipped a deliberately locked job and completed 22 initial reports.
- Killing a worker inside a blocked transaction left its report available for another worker.
- SIGTERM finished an active job and an in-flight HTTP write before clean process exit.
- A real streaming standby came first in the unchanged URL. Writes selected the writable second host.
- Stopping the primary and promoting the standby preserved the surviving web/job processes.
  Existing sessions, private document access, fresh writes and report completion passed afterward.
  Promotion through recovery checks took 3.770 seconds. This observation is not a recovery ceiling.
- HTTP startup refuses missing APP_ORIGIN. The final image includes this required-setting check.
- The actual final image ran as UID 1000 with two web containers and two job containers.
  HTML and fingerprinted CSS loaded, and the full shared HTTP checks passed.
- Logical dump/create/restore comparison on the final image took 2.262 seconds.
  Nine accounts, nine sessions, six records, five documents, 28 reports and two migration versions matched exactly.
  The restored app accepted a saved session and password login.
  Object copies in a separate bucket matched restored metadata and original bytes.
  These results measure isolated logical recovery, not Stack backup recovery.

## Reproduce and remaining proof

Follow the [complete guide](../../../docs/app-frameworks/express-pg.md).
Supply an empty PostgreSQL 17 database, separate private S3-compatible bucket,
protected runtime environment and two unused ports. Run `python tests/services.py`.
An optional `TEST_PROMOTE_ARGV` JSON command array stops an owned primary and promotes
its synchronized standby. Never use that setting on a shared database service.

Full live Stack deployment, real R2 credentials/TLS, public HTTPS/browser accessibility,
Stack switchover in both directions, silent TCP failure, transaction-mode PgBouncer,
previous-image rollback and mounted previous-release assets remain unproved.
Stack database/object backup drills remain separate.

## Failure boundaries

A blocked mutation returned HTTP 503 after 5.013 seconds and inserted no row.
A PostgreSQL relay dropped replies through the successful COMMIT's idle ReadyForQuery.
The app returned HTTP 503 with exactly one committed row and no automatic replay.
A later distinct write succeeded. These checks ran against the final image.

## Independent guide replay

A fresh agent installed pinned Node dependencies and a Python virtual environment
with psycopg 3.3.7, then replayed the full local guide on a separate empty database
and private bucket. The final source passed the complete service suite, explicit
missing-APP_ORIGIN startup refusal and standalone migrate, seed twice, web, jobs and healthz.
No material local or deployment-preparation guide gap remained.
Promotion, final image, restore and fault injection have separate evidence above.
