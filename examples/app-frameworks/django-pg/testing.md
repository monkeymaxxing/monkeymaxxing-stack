# Variances and guidance needs

Django does not parse DATABASE_URL itself. Psycopg's native connection-string parser
retains the multi-host URL settings in Django's database configuration.
Reads use the primary for immediate consistency. DATABASE_READ_URL is unused.

Gunicorn uses WEB_CONCURRENCY processes with four threads each. Django keeps one
connection per active thread, with a 600-second lifetime and health checks before reuse.
The queue holds transaction row locks with SKIP LOCKED. No external broker is required.
The migration command holds a transaction advisory lock around ordered native migrations.
WhiteNoise serves fingerprinted collectstatic output at /app/staticfiles.
Native Django auth and database sessions need one shared SECRET_KEY per environment.
Every mutation requires the exact Origin. Live cookies are Secure and HttpOnly.
Django's empty deletion cookie omits those flags because the cookie contains no token.

This record covers isolated services. Full live Stack deployment remains separate.

## Versions and artifact identity

Checked 2026-11-04 on Debian 13 x86_64, PostgreSQL 17.11, Python 3.13.5,
Django 6.1.3, Gunicorn 26.2.0, psycopg 3.3.7, django-storages 1.14.6,
boto3 1.43.123, WhiteNoise 6.12.0, and Podman 5.4.2.
The image uses Python 3.13.18.
The exact transitive versions are pinned in requirements.txt.

The Django version was checked against [Django downloads](https://www.djangoproject.com/download/).
Connection behavior follows [Django's database documentation](https://docs.djangoproject.com/en/6.1/ref/databases/)
and [psycopg connection information](https://www.psycopg.org/psycopg3/docs/api/conninfo.html).
Static serving follows [WhiteNoise's Django guide](https://whitenoise.readthedocs.io/en/stable/django.html).

source-sha256.json identifies executable/configuration,
build, and test inputs. The Containerfile pins the Python base by digest.
S3Mock used docker.io/adobe/s3mock@sha256:ab01a6946750f451ca215a47e91030695b260e4003b8a5a6201d25029b8fca92.

## Executed native proof

- 2026-11-05: The full isolated PostgreSQL 17/S3 suite passed with complete first-run fixture snapshots. Every fixed row and password hash survived reruns, two 1,000-account runs, and a different `FIXTURE_PASSWORD`. Previously recorded image IDs predate the test changes.

- 2026-11-05: `seed-test-data` now supports development and staging plus `--accounts`. The full real-service suite passed on Debian 13 with PostgreSQL 17.11 and S3Mock. Checks covered refused environments and counts, exact fixtures, 1,000 accounts twice, unchanged documents/jobs, HTTP ownership and storage, workers, and shutdown. Previously recorded image IDs predate this change.


- Framework checks, migration/model consistency, dependency installation, and collectstatic passed.
- Initial schema, title-only insert, concurrent migration runners, repeated migrate, and additive migration preservation passed.
- Production seeding refused. Staging seeding twice preserved exact accounts, records, files, hashes, and jobs.
- Two web processes, each with two Gunicorn workers, shared sessions and logout revocation.
- Registration, password login, owner-scoped CRUD, guessed private document/report IDs, and foreign-Origin refusal passed.
- Private uploads and downloads matched exact bytes and SHA-256.
- Two workers completed 22 initial reports. Killing a worker inside a locked transaction left its job available.
- SIGTERM completed an in-flight report and HTTP write, with clean process exit.
- A real streaming standby came first in the unchanged database URL. Writes selected the writable second host.
- Stopping the primary and promoting the standby preserved the surviving web/job processes.
  Existing sessions, documents, fresh writes, and report completion passed afterward.
  Recovery checks took 1.366 seconds from the promotion command. This observation is not a recovery ceiling.

## Image, recovery, and uncertain-write proof

The tested image ID is `c0776ad27b58e0c3f30ac6de747a536e77f952e499cb59bb841e027871e276eb`.
The image ran as UID 1000, with two web and two job containers.
The image served the HTML document and fingerprinted CSS and passed the shared HTTP checks.

A logical dump/create/restore comparison took 1.384 seconds.
Saved rows matched across seven accounts, six sessions, six records, four documents,
27 report jobs, and 17 migration records, including the two portal migrations.
The restored app accepted a saved session and password login.
Copied object bytes in a separate bucket matched restored document references.
Those checks measure isolated logical recovery, not Stack backup recovery.

A blocked mutation returned 503 in 5.005 seconds and inserted no row.
A PostgreSQL relay withheld the reply after a committed mutation, then closed the connection.
The app returned 503 while exactly one row existed. No automatic replay occurred.
A later distinct write succeeded.

An independent fresh reader replayed the complete guide with a new Python virtual environment,
a separate empty database, and a separate private bucket. Dependency checks, model/migration
consistency, asset compilation, and the full service suite passed. No material guide gap remained.
The replay did not repeat promotion, image execution, or restore, which have separate evidence.

## Reproduce

Follow the complete [Django guide](https://github.com/monkeymaxxing/monkeymaxxing-stack/blob/main/docs/app-frameworks/django-pg.md).
Supply an empty PostgreSQL 17 database, separate private S3-compatible bucket,
protected runtime environment, and two unused ports. Install psycopg 3 for the test runner.

```sh
python -m pip install -r requirements.txt
python manage.py collectstatic --noinput
python tests/services.py
```

The service runner intentionally retains synthetic rows for restore inspection.
The runner stops its own processes on success or failure.
Only an isolated, owned primary/replica environment may supply `TEST_PROMOTE_ARGV`.
Never restart or promote a service shared with another app.

## Remaining shared-system checks

The later deployment must prove real R2 authorization and TLS, public browser flows,
Stack `switch_database_primary` in both directions, silent network loss, PgBouncer,
previous-release asset delivery, image rollback, and the Stack backup chain.
The old SQL shape was checked after migration 2. A separately built previous Django
image still needs the real deploy/rollback check.

A first restore drill checks migration versions only. Later drills must compare
accounts, password hashes and session rows, ownership, records, document metadata, pending jobs,
completed output, and migration versions against a saved manifest.
Object bytes need a separate backup and byte comparison.
A logical database restore is not a whole-system recovery measurement.
