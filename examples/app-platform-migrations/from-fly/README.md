# Customer portal moved from Fly.io

This Node.js portal keeps accounts, private records, private documents, and record-count reports after leaving Fly.io.
The source app uses PostgreSQL and Tigris. The destination uses PostgreSQL and a private S3-compatible bucket.

The [migration guide](../../../docs/app-platform-migrations/from-fly.md) explains source inventory, exports, restore, verification, and later cutover.
The [test record](test_record.md) separates measured rehearsal results from production checks still required.

## Run the app

Build `Containerfile` and provide the values in `environment.example` through a protected environment file.
Run migrations before starting web processes or workers.

| Command | Purpose |
| --- | --- |
| `node server.mjs` | Serve the portal on PORT, with WEB_CONCURRENCY processes |
| `node database.mjs` | Apply ordered transactional migrations and verify checksums |
| `node jobs.mjs` | Process queued reports until SIGTERM |
| `node jobs.mjs --once` | Attempt one queued report and exit |
| `node schedule.mjs` | Run the idempotent hourly expired-session cleanup |
| `node seed-test-data.mjs` | Fill a laptop database or staging with invented test data |

The seed requires `APP_ENV=development` or `APP_ENV=staging`, `APP_URL`, and `FIXTURE_PASSWORD`.
Seed reruns preserve existing passwords and records, and do not duplicate documents or reports.

The database owns users, bcrypt verifiers, session hashes, records, document metadata, report jobs, controls, migration versions, and scheduled occurrences.
Object bytes live in the private bucket. A database backup does not include object bytes.
Sessions are shared across web processes and are revoked in PostgreSQL on logout.

The default controls pause report workers. Enable workers only after the destination has exclusive queue ownership.
Maintenance blocks all HTTP mutations, including registration and login.
The upload limit is 1 MiB because the small example buffers document transfers in memory.

The database module uses the Stack's unchanged `pg_with_multiple_database_servers.mjs` helper.
Every query has a deadline. Reconnection opens a new database connection without automatically replaying failed writes.

## Acceptance contracts

- Returning users retain password authentication and stable user IDs after restore.
- Record, document, report, and job access checks require the correct owner.
- Downloaded private bytes match uploaded bytes and their recorded SHA-256 values.
- Concurrent workers claim distinct jobs. Interrupted transactions leave pending work available.
- Report output and completion commit together and count only the owner's records.
- Ordered migrations apply once and reject changed checksums. The additive description migration preserves old rows.
- Web processes share session state and logout revocation.
- Exports preserve database rows, private bytes, code, variable names, job states, and schedule configuration separately.
- Production seed commands refuse to run. Laptop and staging test data preserve existing values.
- No claim of production failover, R2 privacy, traffic cutover, or backup recovery follows from an isolated rehearsal.

See [testing.md](testing.md) for disposable verification.

## Fill a laptop or staging with test data

The command fills a developer's laptop database or staging with invented test data.
After the guide's local database and bucket setup, run migrations and start the app.
Set `APP_URL` to that app and supply `FIXTURE_PASSWORD`, then run:

```sh
APP_ENV=development npm run seed-test-data
```

For staging, use `APP_ENV=staging` with its own database and bucket.
`npm run seed-test-data -- --accounts 200000` makes enough rows to show slow queries.
The count includes the two fixed accounts. Extra accounts use bulk SQL through
`DATABASE_URL`; they get one record each and no files or report jobs.
Reruns add missing rows, and a smaller count removes nothing.
