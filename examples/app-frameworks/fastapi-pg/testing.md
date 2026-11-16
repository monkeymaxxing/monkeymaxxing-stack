# Variances and guidance needs

Psycopg/libpq reads the unchanged multi-host URL. Primary-only reads preserve immediate
session consistency. Each Gunicorn/Uvicorn worker owns a four-connection pool.
Native SQL migrations use a transaction advisory lock. Static files ship in /app/assets.
The PostgreSQL queue holds a SKIP LOCKED row lock through completion.
Sessions are hashed revocable PostgreSQL tokens; passwords use Argon2.

## Test state

Real isolated services, primary promotion, image execution and logical recovery passed.
Failure checks and an independent fresh guide replay also passed. No live Stack deployment has run.

## Versions and artifact identity

Checked 2026-11-04 on Debian 13 x86_64 with PostgreSQL 17.11, Python 3.13.5,
FastAPI 0.162.0, Gunicorn 26.2.0, Uvicorn 0.54.0, uvicorn-worker 0.4.0,
psycopg 3.3.7, psycopg-pool 3.3.3, boto3 1.43.123 and Argon2-cffi 25.1.0.
The image uses Python 3.13.18 and Podman 5.4.2 built and ran the image.
Exact transitive dependencies are in requirements.txt.

Versions were checked against [FastAPI on PyPI](https://pypi.org/project/fastapi/).
Connection reuse follows [psycopg's pool documentation](https://www.psycopg.org/psycopg3/docs/advanced/pool.html).
Gunicorn uses the separate [uvicorn-worker package](https://pypi.org/project/uvicorn-worker/).

source-sha256.json identifies executable, build and test inputs.
The Python base is pinned by digest in Containerfile.
S3Mock used docker.io/adobe/s3mock@sha256:ab01a6946750f451ca215a47e91030695b260e4003b8a5a6201d25029b8fca92.
The tested image ID is 6369b544531de262c42b9c84ff702e05f89ffb1875d95a96a97c3e272fe32750.

## Executed proof

- 2026-11-05: The full isolated PostgreSQL 17/S3 suite passed with complete first-run fixture snapshots. Every fixed row and password hash survived reruns, two 1,000-account runs, and a different `FIXTURE_PASSWORD`. Previously recorded image IDs predate the test changes.

- 2026-11-05: `seed-test-data` now supports development and staging plus `--accounts`. Python syntax checks, the cache unit test, and `python3 tests/services.py` passed on Debian 13 with PostgreSQL 17.11 and S3Mock. The suite checked refusals, exact fixtures, 1,000 accounts twice, unchanged documents/jobs, HTTP ownership and storage, workers, and shutdown. Previously recorded image IDs predate this change.

- Exact dependencies installed and Python syntax passed.
- Migration 1, old title-only rows, concurrent migration runners, migration 2 and repeat migration passed.
- Production seeding refused. Two staging seeds preserved exact fixture accounts, records, files, hashes and jobs.
- Two web instances, each with two Gunicorn/Uvicorn workers, shared sessions and logout revocation.
- Registration, password login, owner-scoped CRUD, guessed document/report IDs and foreign-Origin refusal passed.
- Private upload/download bytes and SHA-256 matched.
- Two workers skipped a deliberately locked job and completed 22 initial reports.
- Killing a worker inside a blocked transaction left its report available for another worker.
- SIGTERM finished an active job and an in-flight HTTP write before clean process exit.
- A real streaming standby came first in the unchanged URL. Writes selected the writable second host.
- Stopping the primary and promoting the standby preserved the surviving web/job processes.
  Saved sessions, private document access, fresh writes and report completion passed afterward.
  Promotion through recovery checks took 6.954 seconds. This observation is not a recovery ceiling.
- The actual image ran as UID 1000 with two web containers and two job containers.
  HTML and fingerprinted CSS loaded and the shared HTTP checks passed.
- Logical dump/create/restore comparison took 1.900 seconds.
  Seven accounts, six sessions, six records, four documents, 27 reports and two migration versions matched exactly.
  A restored app accepted the saved session and password login.
  Copies of object bytes in a separate bucket matched restored metadata and original bytes.
  This measures isolated logical recovery, not Stack backup recovery.

## Reproduce and remaining proof

Follow the [complete guide](../../../docs/app-frameworks/fastapi-pg.md).
Supply an empty PostgreSQL 17 database, separate private S3-compatible bucket,
protected runtime environment and two unused ports. Run `python tests/services.py`.
An optional `TEST_PROMOTE_ARGV` JSON command array stops an owned primary and promotes
its synchronized standby. Never use that setting on a shared database service.

Full live Stack deployment, real R2 credentials/TLS, public HTTPS/browser accessibility,
Stack switchover in both directions, silent TCP failure, transaction-mode PgBouncer,
previous-image rollback and mounted previous-release assets remain unproved.
Stack database/object backup drills also remain separate.

## Failure boundaries

A blocked mutation returned HTTP 503 after 5.007 seconds and inserted no row.
A PostgreSQL relay dropped replies through the successful COMMIT's idle ReadyForQuery.
The app returned HTTP 503 with exactly one committed row and no automatic replay.
A later distinct write succeeded. The real primary-promotion check used the native app;
these fault checks used the actual image.

## Independent guide replay

A fresh agent used a clean Linux app copy, fresh pinned dependency installation,
a separate empty database and separate bucket. The complete local service suite passed.
The reader also ran migrate, seed twice, web, jobs and healthz from the guide.
No material local or deployment-preparation guide gap remained.
Promotion, image execution, restore and fault injection have separate evidence above.
