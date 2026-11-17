# Go with net/http and pgx customer portal

The portal lets customers create accounts, keep private records and documents,
and request record-count reports. Postgres holds sessions, records, and jobs.
A private S3-compatible bucket holds uploaded documents.

Copy this directory whole into your app repository. Each example has its own
migrations, templates, dependencies, container recipe, and HTTP check.
Use a separate database and bucket for every app and environment.

The pages are [templ](https://templ.guide) templates in `pages.templ`.
`pages_templ.go` is generated from them and committed, so a build needs no
templ. After you change `pages.templ`, run `go generate` in this directory
and commit the new `pages_templ.go`. `testdata/` holds each page as it
should render; `go test -run RenderedPages -update-golden` rewrites it after a
wanted change.

Follow the [Stack guide](https://github.com/monkeymaxxing/monkeymaxxing-stack/blob/main/docs/app-frameworks/go-net-http-pgx.md) for checks,
settings, image builds, and deployment preparation. The
[test record](test-record.md) separates verified results from remaining checks.
The [integration checks](testing.md) describe service and recovery tests.
The [design](design.md) explains sessions, ownership, and queue transactions.

## Local checks

Use Go 1.27.4. Run from this directory:

```sh
go test ./...
go vet ./...
go build -o "$TMPDIR/customer_portal_go" .
```

Set `TMPDIR` to a writable temporary directory before the Go build when your shell
does not already define `TMPDIR`. Keep compiler caches outside the copied example.
The tests require no database or object store. The service checks require a real
Postgres server, an S3-compatible store, two web instances, and job workers.

## Acceptance contracts

- The administrative replica report selects a standby when available and falls back to a reachable primary.

- Accounts use bcrypt passwords and random seven-day sessions stored in Postgres.
  Logout revokes the session across app servers. Cookies require HTTPS.
- Only an account's owner can list or change records, download documents, or see reports.
- CRUD persists in Postgres. Private uploads round-trip through the S3 API with matching SHA-256.
- Postgres stores the report queue and output. Concurrent workers use `FOR UPDATE SKIP LOCKED`.
  Interrupted transactions leave work waiting. Output and completion commit together.
- Ordered migrations are transactional and repeatable. Migration 0002 adds a description without removing existing data.
- The web server uses `PORT`. Go uses `WEB_CONCURRENCY` for `GOMAXPROCS` and concurrent goroutines.
  Rust uses `WEB_CONCURRENCY` for Tokio runtime threads.
- `/healthz` requires a working database and the newest migration within two seconds.
  Web shutdown allows current requests to finish. Job shutdown finishes the current transaction.
- New connections find the writable primary from the Stack's unchanged multi-host `DATABASE_URL`.
  Requests have deadlines. Failed mutations are not replayed automatically.
- Restore checks cover account ownership, records, sessions, document references, and report output.
  Uploaded bytes require a separate object-storage recovery check.


Email verification, password recovery, and account administration are outside the example's scope.

## Synthetic staging fixture

Run `customer_portal seed-test-data` with `APP_ENV=staging` and a protected runtime `FIXTURE_PASSWORD`.
Use staging's database and private bucket. Run the seed twice before starting workers.
Seed reruns preserve passwords and existing records without duplicating documents or jobs.

| Email | Record title | Description | File name | Exact UTF-8 bytes |
| --- | --- | --- | --- | --- |
| `barbara@example.com` | Barbara invoice | First synthetic record | barbara-note.txt | `Barbara synthetic document` followed by LF |
| `michael@example.com` | Michael invoice | Second synthetic record | michael-note.txt | `Michael synthetic document` followed by LF |

Each account receives one pending report job. Before CRUD adds records, each report
produces `record_count=1` followed by LF. The SQL checks in `testing.md` verify the
fixture owners, object keys, hashes, and completed report output.

An upload writes an immutable object before inserting metadata in Postgres.
An uncertain database commit can leave an unreferenced object.
Check database references and the restore retention boundary before deleting such objects.

## Administrative replica report

Run `replica_report` with the Stack environment available.
The report uses `DATABASE_READ_URL` for a stale record count and `DATABASE_URL` to identify the primary.
The report prints the server address and database role for each connection.
HTTP sessions, immediate reads, and job transactions stay on the primary.
The report includes all accounts and is an administrator command.

For laptop test data, migrate against your local PostgreSQL database and local bucket, then run:

```sh
APP_ENV=development customer_portal seed-test-data
```

`customer_portal seed-test-data --accounts 200000` makes enough invented rows to show slow queries.
The total defaults to two accounts. Larger totals add accounts and owned records without extra documents or reports.
Production data stays on production servers. Add a missing data shape to the seed or a test.
