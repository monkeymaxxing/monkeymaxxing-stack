# TanStack Start PostgreSQL example

## Purpose

A team needs copyable files that run a private customer portal on the Stack. The example must preserve sessions, ownership, files and jobs when requests reach another server or the database primary changes. The shared Stack app contract defines the outcomes.

## Modules and data

PostgreSQL owns accounts, hashed session tokens, account-owned records, document references and hashes, report jobs and output, and ordered migration versions. S3 owns immutable document bytes. Job completion and output commit in one transaction.

- `lib/database.mjs` owns bounded connections and transactions through the unchanged Stack helper.
- `lib/accounts.mjs` owns password and shared session handling.
- `lib/storage.mjs` owns S3 bytes and integrity checks.
- `lib/jobs.mjs` owns the locked report transaction.
- `lib/http.mjs` owns validation, ownership and portal operations.
- `src/routes/$.ts` exposes operations as HTTP routes. `src/portal.functions.ts` adapts record reads and creation to TanStack server functions, calling the operation handler in process. No second ownership or validation path is introduced.
- `src/routes/index.tsx` owns browser forms. Private state is fetched after login and never pre-rendered into a shared page.
- `scripts/manage.mjs` owns ordered migrations, staging seed and queue polling. `scripts/web.mjs` owns worker count and signal forwarding. `server.ts` allows Node cluster to share the listener. The explicitly registered Nitro close hook closes the pool and disconnects IPC after HTTP requests drain.

The rejected alternative is a separate API service beside a static React export. That split would avoid exercising Start server functions and SSR, and add another service to deploy. The Node server preset keeps the framework behavior inside one image.

## Slices and proof

1. Reuse the account/database contract, then build real Start routes and private record server functions. Check install, build, types and password boundaries.
2. Add the portal UI, S3 documents and transactional report workers. Check two web instances, ownership refusals, exact bytes, concurrent/interrupted jobs and migration preservation against real PostgreSQL 17.
3. Package the Node server, CLI modules and static assets. Check configured ports, clustered shutdown, reconnection without process replacement and restore equality.
4. Explain copy/deploy steps, Vercel/Netlify differences, variances and proof limits. Replay the guide from a clean copy.

`PORT`, `WEB_CONCURRENCY`, `APP_ORIGIN`, `APP_ENV`, `FIXTURE_PASSWORD`, `DATABASE_URL`, and the `R2_*` names follow the existing Stack examples. `DATABASE_READ_URL` is deliberately unused: sessions and newly created records need current primary data.

## Connection budget

`DATABASE_POOL_MAX_CONNECTIONS` bounds each process pool. Web and jobs may use separate limits.

## Replica reporting and transaction pooling

The administrative replica report uses `DATABASE_READ_URL` for a stale aggregate.
HTTP reads and durable job transactions stay on `DATABASE_URL`.
Transaction-local timeout settings avoid PgBouncer startup and session-state assumptions.

The app owns `seed-test-data`. `APP_ENV` must be `development` or `staging`.
The optional `--accounts` total defaults to two. PostgreSQL generates extra accounts and owned records in two set-based inserts.
A single password hash serves the generated accounts. Extra accounts need no object writes or report jobs.
