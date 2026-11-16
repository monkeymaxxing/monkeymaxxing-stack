# Next.js customer portal with PostgreSQL

Copy this directory into your app repository. The app keeps private records,
documents, and record-count reports. Next.js uses the App Router and the Node.js
runtime. The database driver is `pg`. The directory name also identifies the
Prisma-or-pg integration category. This example uses no Prisma client.

Start with the [setup and deployment guide](../../../docs/app-frameworks/nextjs-prisma-pg.md).
Read [testing.md](testing.md) for the checks and their limits.

## Acceptance contracts

- The administrative replica report selects a standby when available and falls back to a reachable primary.

- Register, log in, and log out with bcrypt passwords and seven-day database sessions.
- Share sessions between web processes. Logout revokes the session for every process.
- Create, list, edit, and delete owned records. Refuse another account's guessed IDs.
- Store private files through an S3-compatible API. Check downloaded bytes against stored SHA-256.
- Keep document keys, hashes, and sizes in Postgres. Never use the container filesystem for uploads.
- Run report jobs with `FOR UPDATE SKIP LOCKED`. Commit output and completion together.
- Release unfinished jobs when a worker dies. Count only the job owner's records.
- Apply ordered migrations transactionally once. Migration 0002 adds descriptions without removing old rows.
- Use `PORT` and fork `WEB_CONCURRENCY` Node workers. Drain web requests and finish active job transactions on SIGTERM.
- Expose `/healthz`. Refuse health until both migrations exist. Set database statement deadlines.
- Find the primary from the unchanged Stack multi-host URL after broken connections end.
- Never replay a failed HTTP mutation automatically. A missing acknowledgement can hide a successful commit.
- Provide separate web, migrate, jobs, and seed-test-data commands.
- Allow test-data seeds only in development or staging. `--accounts` sets the total without changing fixed fixtures.
- Restore accounts, sessions, ownership, records, document metadata, and job output together.
  Recover object bytes separately.

This hosting example excludes email verification, password recovery, account
administration, and production abuse controls. Put the public app behind the
Stack's HTTPS proxy. Apply login rate limits at your ingress before public use.

## Design

The seed command uses PostgreSQL set-based inserts for generated accounts and owned records.
A single password hash avoids repeated hashing work. Generated accounts need no object writes or report jobs.

`app/page.jsx` owns the browser forms. `app/[...path]/route.js` sends dynamic
Node route requests to `lib/http.mjs`. React escapes user content.
Every API response uses `Cache-Control: no-store`. No private response uses
Next.js static generation or a shared page cache.

`lib/accounts.mjs` owns bcrypt and hashed random session tokens.
`lib/database.mjs` owns pools, transactions, deadlines, and health.
The unchanged `lib/pg_with_multiple_database_servers.mjs` comes from the Stack.
Every new connection discovers a suitable server. Reads use the primary because
sessions and recently saved records require current data.

`lib/storage.mjs` owns immutable object keys and byte-integrity checks.
`lib/jobs.mjs` owns one locked queue transaction. `scripts/manage.mjs` owns
migrations, staging fixtures, and the job loop. PostgreSQL is the source of truth
for accounts, sessions, records, document metadata, and the job queue.

The alternative was Prisma with a separately resolved single-host URL.
The `pg` design keeps discovery on every new pool connection, including workers
and migrations. No process restart or rewritten URL is required after a primary switch.

The implementation slices are database/accounts, owned records/files, then jobs
and runtime packaging. Tests cover the public HTTP behavior and actual service
transactions. No existing Stack implementation is replaced.

Uploads are limited to 8 MiB because this example buffers each upload in memory.
An upload writes an immutable object before saving metadata. A failed database
commit can leave an unreferenced object. Check database references and backup
retention before deleting any object.

The report transaction uses no session-scoped state, so transaction-mode
PgBouncer can be tested with `jobs_connect_directly_to_postgres: false`.
Each web worker has a pool of four connections. Include worker count when
calculating the system's database connection budget.

## Synthetic test fixture

Supply `APP_ENV=development` or `APP_ENV=staging` and a runtime `FIXTURE_PASSWORD` of 12 to 72 bytes.
Never put the fixture password in a command argument or a committed file.
Each framework and environment must have a separate database and private bucket.

| Email | Record title | Description | File name | Exact bytes |
| --- | --- | --- | --- | --- |
| barbara@example.com | Barbara invoice | First synthetic record | barbara-note.txt | `Barbara synthetic document` plus LF |
| michael@example.com | Michael invoice | Second synthetic record | michael-note.txt | `Michael synthetic document` plus LF |

Each account receives one pending report. Before CRUD changes, each report
produces `record_count=1` followed by LF. Seed reruns preserve passwords and
existing rows. Seeding never reads production data.

## Administrative replica report

Run `node scripts/replica_report.mjs` with the Stack environment available.
The report uses `DATABASE_READ_URL` for a stale record count and `DATABASE_URL` to identify the primary.
The report prints the server address and database role for each connection.
HTTP sessions, immediate reads, and job transactions stay on the primary.
The report includes all accounts and is an administrator command.

For laptop test data, migrate against your local PostgreSQL database and local bucket, then run:

```sh
APP_ENV=development npm run seed-test-data
```

`npm run seed-test-data -- --accounts 200000` makes enough invented rows to show slow queries.
The total defaults to two accounts. Larger totals add accounts and owned records without extra documents or reports.
Production data stays on production servers. Add a missing data shape to the seed or a test.
