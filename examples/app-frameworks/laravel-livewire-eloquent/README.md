# Laravel customer portal

Keep private customer records and documents, and generate record-count reports.
The example uses Laravel 13, Livewire 4, Eloquent, PostgreSQL and private S3-compatible storage.
FrankenPHP serves the app in one container. PostgreSQL stores shared sessions and report jobs.

Read the [guide](../../../docs/app-frameworks/laravel-livewire-eloquent.md) to copy, test and prepare the app for the Stack.
The [test record](testing.md) lists measured checks and remaining live checks.

## Acceptance contracts

- The administrative replica report selects a standby when available and falls back to a reachable primary.

- Register, log in and log out using Laravel password hashing and PostgreSQL sessions.
- Share sessions across web containers. Logout revokes the old session across containers.
- Create, list, edit and delete only the signed-in account's records.
- Refuse another account's guessed record, document and report IDs.
- Store private S3 objects and PostgreSQL keys and SHA-256 hashes. Downloads verify exact bytes.
- Claim jobs with `FOR UPDATE SKIP LOCKED`. Commit report output and completion together.
- Make interrupted report transactions available to another worker.
- Apply ordered transactional migrations once. Migration 2 adds an empty-default description without removing rows.
- Use `PORT`, `WEB_CONCURRENCY`, `/healthz` and separate migrate, web, jobs and test-data seed commands.
- Finish active work on SIGTERM. Bound database queries and never replay an uncertain query automatically.
- Open new connections using the unchanged Stack multi-host writer URL after a database failure.
- Restore accounts, ownership, sessions, records, document references and report state. Check S3 bytes separately.

## Synthetic fixture

Supply `APP_ENV=development` or `APP_ENV=staging` and a runtime-only `FIXTURE_PASSWORD` of 12 to 72 bytes.
Run `php artisan portal:seed-test-data` after migrations, before workers.

| Email | Record title | Description | File name | Exact UTF-8 bytes |
| --- | --- | --- | --- | --- |
| `barbara@example.com` | Barbara invoice | First synthetic record | `barbara-note.txt` | `Barbara synthetic document` plus LF |
| `michael@example.com` | Michael invoice | Second synthetic record | `michael-note.txt` | `Michael synthetic document` plus LF |

Each account starts with exactly one record, one private document and one pending report.
Each initial report produces `record_count=1` followed by LF.
Seed reruns preserve existing passwords and records, and do not duplicate fixture documents or reports.

## Administrative replica report

Run `php scripts/replica_report.php` with the Stack environment available.
The report uses `DATABASE_READ_URL` for a stale record count and `DATABASE_URL` to identify the primary.
The report prints the server address and database role for each connection.
HTTP sessions, immediate reads, and job transactions stay on the primary.
The report includes all accounts and is an administrator command.

For laptop test data, migrate against your local PostgreSQL database and local bucket, then run:

```sh
APP_ENV=development php artisan portal:seed-test-data
```

`php artisan portal:seed-test-data --accounts 200000` makes enough invented rows to show slow queries.
The total defaults to two accounts. Larger totals add accounts and owned records without extra documents or reports.
One password hash and two set-based SQL inserts keep generated data fast.
Production data stays on production servers. Add a missing data shape to the seed or a test.
