# Express portal design

A copied app must show that accounts, owned records, private files and queued reports
work across two web instances and a database primary change.

PostgreSQL owns accounts, hashed revocable sessions, owner-keyed records, document
metadata, a row-locked report queue and an ordered migration ledger. S3 owns private bytes.
The database module owns pooled transactions and pg connections. Storage owns S3
and integrity checks. The HTTP module owns authorization, request policy and forms.
The command module owns ordered migrations, fixture creation and job transactions.
Tests exercise these boundaries through real HTTP and services.

An ORM-generated scaffold was considered. The Stack pg helper keeps the Stack
multi-host URL unchanged and makes the queue's transaction boundary explicit with fewer
dependencies. Every request reads the primary for immediate session consistency.
No request is automatically replayed after a database failure.

Build slices: migrations/seed/queue; authenticated HTTP and UI; isolated services and
promotion/image/recovery checks; independent replay of the guide.

## Connection budget

`DATABASE_POOL_MAX_CONNECTIONS` bounds each process pool. Web and jobs may use separate limits.

## Replica reporting and transaction pooling

The administrative replica report uses `DATABASE_READ_URL` for a stale aggregate.
HTTP reads and durable job transactions stay on `DATABASE_URL`.
Transaction-local timeout settings avoid PgBouncer startup and session-state assumptions.

The app owns `seed-test-data`. `APP_ENV` must be `development` or `staging`.
The optional `--accounts` total defaults to two. PostgreSQL generates extra accounts and owned records in two set-based inserts.
A single password hash serves the generated accounts. Extra accounts need no object writes or report jobs.
