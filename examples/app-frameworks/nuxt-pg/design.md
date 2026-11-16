# Nuxt portal design

The portal shows how a Nuxt app runs on the Stack without changing database URLs.
The customer registers, manages owned records, stores private documents, and queues record-count reports.

## Module plan

Nuxt owns page rendering, request routing and Nitro node-server packaging.
`lib/portal.mjs` owns the HTTP contract using standard Request and Response objects.
`lib/accounts.mjs` owns password validation and database-backed sessions.
`lib/database.mjs` owns transactions and deadlines through the unchanged Stack helper.
`lib/storage.mjs` owns immutable S3 object keys, bytes and integrity checks.
`lib/jobs.mjs` owns one report transaction. `scripts/manage.mjs` owns migrations, jobs and staging fixtures.
The process launcher maps WEB_CONCURRENCY to Node cluster workers sharing PORT.
The Nitro Node server drains HTTP and invokes the close hook to close the database pool.

The alternative was generated ORM/auth modules with framework-specific persistence.
Direct pg and standard HTTP objects keep the Stack helper and transaction boundaries visible.
Each copy contains every runtime file. No sibling source tree or shared package is required.

## Data shape

PostgreSQL is the source of truth for accounts, hashed expiring sessions, owner-keyed records,
document metadata, report jobs/output and ordered migration versions.
Private S3 objects hold document bytes. Every query includes the authenticated account ID.
The queue keeps its row lock through report completion and output in one transaction.
A killed transaction rolls back, leaving the report available.

Migrations 0001 and 0002 use a transaction advisory lock and one transactional ledger.
Migration 0002 adds an empty description default, preserving old title-only writes.
Reads use the primary so a new session or record is immediately visible on another app server.
Failures discard broken connections. Requests never replay after uncertain commit acknowledgement.

## Slices and checks

Build data/commands, then native Vue page/H3 routes and process handling, then isolated services and documentation replay.
`tests/services.py` runs migrations, exact fixtures, two instances, two workers, interrupted jobs and shutdown.
`tests/check_portal.py` verifies ownership, session sharing/revocation, CRUD, bytes/hash and private reports.
A disposable primary/standby pair verifies reconnection with unchanged URLs and processes.
Live Stack orchestration, real R2 and backup recovery stay separate from isolated service evidence.

## Connection budget

`DATABASE_POOL_MAX_CONNECTIONS` bounds each process pool. Web and jobs may use separate limits.

## Replica reporting and transaction pooling

The administrative replica report uses `DATABASE_READ_URL` for a stale aggregate.
HTTP reads and durable job transactions stay on `DATABASE_URL`.
Transaction-local timeout settings avoid PgBouncer startup and session-state assumptions.

The app owns `seed-test-data`. `APP_ENV` must be `development` or `staging`.
The optional `--accounts` total defaults to two. PostgreSQL generates extra accounts and owned records in two set-based inserts.
A single password hash serves the generated accounts. Extra accounts need no object writes or report jobs.
