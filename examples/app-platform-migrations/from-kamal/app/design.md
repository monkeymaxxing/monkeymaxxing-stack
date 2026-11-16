# Rails portal design

PostgreSQL owns accounts, hashed login sessions, account-owned records, document
references, report jobs, and Rails migration versions. S3-compatible storage owns
immutable object bytes. A document row keeps the object key and SHA-256 checksum.

Rails models and database foreign keys enforce the stored relationships.
The controller scopes each record, document, and report query to the logged-in account.
Exact Origin checks protect mutations. Secure, HttpOnly, SameSite cookies carry random tokens.
Only token hashes and expiration times live in PostgreSQL. Logout deletes the shared session.

The report worker holds one job row lock through counting and completion.
`FOR UPDATE SKIP LOCKED` permits concurrent workers. A terminated transaction releases
its lock and leaves the unfinished job pending. Output and completion commit together.
The worker finishes an active transaction on SIGTERM and then exits.

Native Active Record migrations own ordered schema changes.
Migration 2 adds a defaulted description without breaking title-only SQL from release 1.
The deploy command runs migrations before replacing web and job containers.
Migration runners use direct PostgreSQL because Rails uses session advisory locks.

The app converts the driver URL at Rails' configuration boundary with libpq's parser.
Every new connection retains all database hosts and writable-server selection.
Failed requests discard stale pooled connections and return a visible error.
No controller retries a database mutation. Ordinary SQL has a 12-second statement timeout.
A five-second lock timeout bounds lock waits. Connections use TCP keepalive and a TCP user timeout.

Puma owns process and thread concurrency and signal draining.
Propshaft owns fingerprinted CSS and its build manifest. The Stack mounts the
current and previous release's files over `/app/public/assets`.

A shared cross-language SQL layer was rejected because native framework behavior
is the subject of this example. A small transaction-locked queue avoids an external broker.
The example excludes password recovery, account administration, and email delivery.

## Connection budget

`DATABASE_POOL_MAX_CONNECTIONS` bounds each process pool. Web and jobs may use separate limits.

## Replica reporting and transaction pooling

The administrative replica report uses `DATABASE_READ_URL` for a stale aggregate.
HTTP reads and durable job transactions stay on `DATABASE_URL`.
Transaction-local timeout settings avoid PgBouncer startup and session-state assumptions.

The app owns `seed-test-data`. `APP_ENV` must be `development` or `staging`.
The optional `--accounts` total defaults to two. PostgreSQL generates extra accounts and owned records in two set-based inserts.
A single password hash serves the generated accounts. Extra accounts need no object writes or report jobs.

## Kamal migration schedule

`schedule_runs` records one session-cleanup occurrence per UTC date.
The receipt and expired-session deletion commit together. A unique date prevents duplicate cleanup during overlapping clocks.
A late start runs the current day once and does not replay every missed day.
Source Kamal runs separate worker and clock roles. The destination's `bin/migration-jobs` supervises both commands.
The PostgreSQL schema and object keys stay unchanged during the move.

## Database migration ownership

The Stack's `database_moving_in` setting and copy/switch playbooks own the database move.
The Kamal example owns only source accessory access, source execution shutdown, private objects, and customer checks.
Native libpq keeps writable-login selection in the unchanged multi-host URL while the Stack fences each listed source database.
No application schema or identity conversion is required.
