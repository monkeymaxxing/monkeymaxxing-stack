# Rails customer portal

A copyable Rails app with accounts, private records and documents, and PostgreSQL report jobs.
Use Rails 8.1.4, Puma, Active Record, Propshaft, bcrypt, and the AWS S3 SDK.
The queue uses `FOR UPDATE SKIP LOCKED` inside the same transaction that saves report output.

Copy this directory into your app repository. Keep the dependency lockfile.
Follow [the Rails guide](https://github.com/monkeymaxxing/monkeymaxxing-stack/blob/main/docs/app-frameworks/rails-pg.md)
for setup, tests, staging data, and adding another app to an existing Stack system.
Read [testing.md](testing.md) for measured checks and remaining live work.

Commands, run from the app directory:

```sh
bin/portal migrate
bin/portal web
bin/portal jobs
bin/portal seed-test-data
```

Supply the protected runtime environment described in the guide.
`RAILS_ENV=production` applies to production and staging.
The synthetic seed also requires `APP_ENV=development` or `APP_ENV=staging` and `FIXTURE_PASSWORD`.
The browser requires HTTPS. Mutations require the exact configured `APP_ORIGIN`.
The app stores sessions in PostgreSQL so requests can move between app servers.
Uploads live in private S3-compatible storage. Downloaded bytes must match their SHA-256 checksum.

The synthetic accounts are `barbara@example.com` and `michael@example.com`.
Each account starts with one invoice, one document, and one pending report.
Seeding twice preserves existing fixture rows and passwords.
The guide lists exact titles, descriptions, filenames, and document bytes.

`config/database.yml` passes the libpq-parsed host and port lists to Active Record.
Do not feed the multi-host Stack URL to Rails' generic URL parser.
The primary serves all reads for immediate consistency.
`config/puma.rb` uses `PORT` and `WEB_CONCURRENCY`.
Propshaft writes fingerprinted CSS to `/app/public/assets` in the image.

`tests/services.py` requires psycopg 3 in the Python test runner.
The runner needs an empty disposable database, separate test bucket, and two unused ports.
The runner leaves synthetic data for restore inspection and stops its child processes.
No test may restart or promote a database shared with another app.

## Administrative replica report

Run `bundle exec ruby scripts/replica_report.rb` with the Stack environment available.
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
