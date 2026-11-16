# Customer portal example design

A team needs a small app that exercises accounts, private data, files, and
background work on the Stack. Infrastructure health alone cannot prove ownership
or a returning user's session after a database switch.

## Boundaries

Two standalone apps use the same SQL schema and invented fixture requirements.
Each app runs against its own database and private object-storage bucket.

The selected design has four small modules: HTTP and authentication, database
and migrations, private object storage, and transactional report jobs. HTTP owns
request validation, browser forms, authorization, and sessions. Database code owns
connections, time limits, schema versions, and synthetic seeding. Storage owns S3
requests. Jobs own row locking and atomic report completion. Tests live beside
code and in the shared HTTP integration check.

A rejected design uses a shared application service behind two HTTP adapters.
A shared service would hide framework-specific driver and lifecycle behavior.
Standalone examples keep ordinary language conventions and can be copied alone.
Each copy carries its own SQL files and the same fixture expectations.

## Data

Postgres holds accounts, sessions, records, documents, report_jobs, and
schema_migrations. Foreign keys and owner-qualified queries enforce ownership.
Sessions use random opaque tokens, store only SHA-256 digests, and expire after
seven days. Browser cookies are HttpOnly, Secure, and SameSite=Lax. Every write
checks the exact configured APP_ORIGIN, including login, to prevent cross-site
requests. Passwords use bcrypt. File keys are random and never come from a URL.
Uploads are capped at 5 MiB to bound request memory. Downloads are attachments.

A report job locks its row inside one transaction, counts the owner's records,
and writes the report before commit. There are no external side effects to
repeat if a worker dies. Additive migration 0002 adds record descriptions.
Migrations and jobs use transaction-scoped advisory/row locks, so transaction
pooling needs no dedicated Postgres session.

## Slices

1. Go accounts, owned CRUD, sessions, migrations, and health checks.
2. Go private documents, durable reports, fixture seed, and behavioral checks.
3. Rust counterpart using native Axum extractors and Tokio tasks.
4. Deployment and isolated integration proof using the shared checks.

Go uses a pgx dialer with host keepalive timing. Rust uses bb8/tokio-postgres
with keepalives_idle=30 seconds and primary reads. A read-replica helper would
add a second connection strategy without helping the scoped acceptance checks.
No Node helper is copied because both chosen drivers select a writable primary.
Queries have deadlines. Failed mutations return errors rather than retrying an
uncertain commit. Database errors never appear in HTTP responses or logs.

## Acceptance contracts

The README's acceptance contracts and fixture describe the required behavior.
Unit checks establish validation and browser security. Integration checks must
exercise real Postgres and an S3-compatible store. The test record separates the isolated checks already run from the live Stack
checks that remain.

## Connection budget

`DATABASE_POOL_MAX_CONNECTIONS` bounds each process pool. Web and jobs may use separate limits.

## Replica reporting and transaction pooling

The administrative replica report uses `DATABASE_READ_URL` for a stale aggregate.
HTTP reads and durable job transactions stay on `DATABASE_URL`.
Transaction-local timeout settings avoid PgBouncer startup and session-state assumptions.

The app owns `seed-test-data`. `APP_ENV` must be `development` or `staging`.
The optional `--accounts` total defaults to two. PostgreSQL generates extra accounts and owned records in two set-based inserts.
A single password hash serves the generated accounts. Extra accounts need no object writes or report jobs.
