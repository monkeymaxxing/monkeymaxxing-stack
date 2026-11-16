# Django customer portal

A copyable Django app with accounts, private records and documents, and PostgreSQL report jobs.
Use Django 6.1.3, Gunicorn, psycopg 3, django-storages/boto3, and WhiteNoise.
The queue holds `FOR UPDATE SKIP LOCKED` row locks until report output and completion commit.

Copy this directory into your app repository. Keep `requirements.txt` with exact dependency versions.
Follow [the Django guide](https://github.com/monkeymaxxing/monkeymaxxing-stack/blob/main/docs/app-frameworks/django-pg.md)
for setup, tests, staging data, and adding another app to an existing Stack system.
Read [testing.md](testing.md) for measured checks and remaining live work.

Run from the app directory with the Python virtual environment active:

```sh
python manage.py collectstatic --noinput
bin/portal migrate
bin/portal web
bin/portal jobs
bin/portal seed-test-data
```

Supply the protected runtime environment described in the guide.
Synthetic seeding also requires `APP_ENV=staging` and `FIXTURE_PASSWORD`.
The browser requires HTTPS. Mutations require the exact configured `APP_ORIGIN`.
Native Django sessions live in PostgreSQL so requests can move between app servers.
Uploads live in private S3-compatible storage. Downloaded bytes must match their SHA-256 checksum.

The synthetic accounts are `barbara@example.com` and `michael@example.com`.
Each account starts with one invoice, one document, and one pending report.
Seeding twice preserves existing rows and passwords.
The guide lists exact titles, descriptions, filenames, and document bytes.

`portal/settings.py` parses the unchanged multi-host URL with psycopg's native parser.
The primary serves all reads for immediate consistency.
`gunicorn.conf.py` uses `PORT` and `WEB_CONCURRENCY` with four threads per process.
`collectstatic` writes fingerprinted assets into `/app/staticfiles` in the image.
WhiteNoise serves those public assets. Uploaded documents never use a public media URL.

`tests/services.py` needs an empty disposable PostgreSQL 17 database, separate private
bucket, and two unused ports. The runner retains synthetic data for restore inspection
and stops its own child processes. The app virtual environment includes the test driver.
Only an isolated, owned primary/replica environment may run the optional promotion check.

## Administrative replica report

Run `PYTHONPATH=. python scripts/replica_report.py` with the Stack environment available.
The report uses `DATABASE_READ_URL` for a stale record count and `DATABASE_URL` to identify the primary.
The report prints the server address and database role for each connection.
HTTP sessions, immediate reads, and job transactions stay on the primary.
The report includes all accounts and is an administrator command.

The replica report must select a standby when available and fall back to a reachable primary.

For laptop test data, migrate against your local PostgreSQL database and local bucket, then run:

```sh
APP_ENV=development bin/portal seed-test-data
```

`bin/portal seed-test-data --accounts 200000` makes enough invented rows to show slow queries.
The total defaults to two accounts. Larger totals add accounts and owned records without extra documents or reports.
Production data stays on production servers. Add a missing data shape to the seed or a test.
