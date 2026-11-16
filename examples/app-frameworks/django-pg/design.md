# Django portal design

PostgreSQL owns native Django accounts and sessions, account-owned records,
private document references, report jobs, and ordered migration versions.
S3-compatible storage owns immutable file bytes. Document rows hold object keys and SHA-256.

Django's auth library owns password hashing, login, shared database sessions, and logout.
The API scopes records, documents, and reports to the authenticated account.
The same-origin mutation middleware requires an exact Origin match and replaces form-token CSRF protection.
Live session cookies use Secure, HttpOnly, and SameSite=Lax.
The HTML fixture puts user values into text nodes or form values, never HTML strings.

Django models own relations and the native migration graph.
Migration 2 adds a description with Python and database defaults.
The database default preserves title-only inserts from the earlier release.
The migration command holds a transaction advisory lock around the supplied transactional migrations.
Concurrent deploy commands serialize before inspecting migration versions.

The report worker holds one job row lock through counting and completion.
`SKIP LOCKED` permits multiple workers. A killed transaction releases its lock,
leaving the job pending. Output and completion share the transaction.
A stopping worker completes its transaction and then exits.

Psycopg parses the original multi-host URL into Django's connection settings.
Django retains one connection per active thread, checks health on reuse,
and closes failed connections. The next connection discovers the writable server.
HTTP mutations are never replayed automatically.
Ordinary SQL has a 12-second statement timeout and a five-second lock timeout.
TCP keepalive and TCP user timeout bound dead-connection detection.

Gunicorn owns workers, threads, and graceful shutdown.
WhiteNoise owns public fingerprinted assets from collectstatic.
Django-storages owns private S3 bytes. All persistent app data lives outside the container.

A shared cross-language SQL/service layer was rejected because native framework
behavior is the subject of the example. The small transaction-locked queue avoids an external broker.
Password recovery, email verification, and account administration are outside this hosting example.

## Connection budget

`WEB_THREADS` bounds persistent web connections by thread count. Jobs keep one connection.

## Replica reporting and transaction pooling

The administrative replica report uses `DATABASE_READ_URL` for a stale aggregate.
HTTP reads and durable job transactions stay on `DATABASE_URL`.
Transaction-local timeout settings avoid PgBouncer startup and session-state assumptions.

The app owns `seed-test-data`. `APP_ENV` must be `development` or `staging`.
The optional `--accounts` total defaults to two. PostgreSQL generates extra accounts and owned records in two set-based inserts.
A single password hash serves the generated accounts. Extra accounts need no object writes or report jobs.
