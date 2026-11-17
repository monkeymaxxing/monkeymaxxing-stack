# Run SvelteKit with PostgreSQL on the Stack

## Variances and guidance needs

SvelteKit 3.1.1 does not include accounts, sessions, migrations, a job queue or a process manager.
This example uses adapter-node 6.0.1, pg, PostgreSQL tables, bcrypt, the AWS S3 SDK and Node cluster.
Node 24 is required. Exact dependencies and the copied database helper ship with the app.

Plain pg cannot consume the Stack's multi-host URL or select a writable database server.
Every connection goes through the unchanged `lib/pg_with_multiple_database_servers.mjs`.
The helper selects a server when opening a connection, never for each query.
Never pass `DATABASE_URL` to pg directly or replace the URL with a fixed primary.
HTTP reads use the primary for immediate session consistency. `DATABASE_READ_URL` is used only by the explicit replica report command below. HTTP reads stay on the primary.
No Stack URL or database architecture change is required.

Each cluster worker defaults to a pool of four connections. `WEB_CONCURRENCY` sets the worker count.
Budget connections for every app server, both releases during deploy, and separate job processes.
The helper handles idle and held connection errors without ending the Node process.
Failed transactions discard their connection. Later requests select the current primary again.
The app never replays failed HTTP mutations. A lost reply can follow a successful commit.
Inspect saved records before resubmitting. Queries have a five-second server deadline
and an eight-second client deadline. Pool checkout also has an eight-second deadline.
Host TCP keepalive settings still govern silent network failures.

Ordered SQL migrations and their ledger commit together under a transaction advisory lock.
Migration 2 adds records.description with an empty database default, preserving title-only inserts.
The report queue holds a `FOR UPDATE SKIP LOCKED` row lock through output and completion.
A killed transaction leaves its report pending. No external broker or dedicated session is needed.

Node cluster starts the web workers. SIGTERM stops accepting requests and drains current work.
Each web worker allows 25 seconds before forced exit. Job workers finish the current transaction.
Build with `npm run build`. The adapter writes Node server output under `build/`.
The image retains `build/client`, including fingerprinted frontend assets and the portal stylesheet.
Keep `asset_directory: /app/build/client` to retain previous-release files.
The Node launcher in `scripts/web.mjs` serves `/_app/immutable/` and `/assets/` before the compiled SvelteKit handler.
`lib/retained-assets.mjs` reads the mounted files for each request instead of consulting a build-time asset list.
The handler accepts GET and HEAD, detects content types, and rejects dot segments, hidden paths, and escaping symlinks.
Copy the complete example, including the locked `mime-types` dependency.
Content-hashed JavaScript and CSS files are cached for a year because content-hashed names never change their bytes.
Pages and API responses are never cached.
A live release with changed asset names preserved all 36 old asset URLs with exact bytes and correct content types.
The 36 URLs include directly requested compressed variants. The origin checks bypassed Cloudflare.

Sessions use random cookie tokens whose SHA-256 hashes live in PostgreSQL.
Every mutation requires the exact configured Origin. Secure cookies require public HTTPS.
No signing secret is needed. The API and home page send `Cache-Control: no-store`.
This example excludes password recovery, email verification and public abuse controls.

The [test record](../../examples/app-frameworks/sveltekit-pg/testing.md) separates measured
isolated checks from remaining live Stack proof.

## Copy and build

Copy [the app directory](../../examples/app-frameworks/sveltekit-pg/) into your app repository.
Use Node 24 on a Linux build host. Run commands from the copied app directory:

```sh
export npm_config_cache="${TMPDIR:-/tmp}/sveltekit-portal-npm"
npm ci --no-audit --no-fund
npm run check
npm run build
npm ls pg
npm ls pg-native
```

`npm ls pg` must show one copy of pg 8. `npm ls pg-native` must show an empty tree
and exits with status 1 when the package is absent. That result is expected.
Do not install pg-native or another database driver.

Keep credentials in your secret store or protected process environment.
Never commit credential values or store shared credentials in the copied repository.

| Variable | Required value |
| --- | --- |
| `DATABASE_URL` | `postgresql://sveltekit_portal:PASSWORD@db01:5432,db02:5432/sveltekit_portal?target_session_attrs=read-write&connect_timeout=3` |
| `APP_ORIGIN` | Exact HTTPS origin, such as `https://portal.example.com`, without a trailing slash |
| `PORT` | Assigned listener port, such as `8017` |
| `WEB_CONCURRENCY` | Positive number of Node cluster worker processes |
| `R2_ENDPOINT` | `https://ACCOUNT_ID.r2.cloudflarestorage.com` |
| `R2_BUCKET` | Private bucket assigned to this app and environment |
| `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | Credentials restricted to the assigned bucket |
| `APP_ENV` | `development` or `staging` for synthetic seeding |
| `FIXTURE_PASSWORD` | Runtime seed/check password, 12 to 72 bytes |

The browser requires HTTPS for the Secure session cookie.
Direct private HTTP tests explicitly send the cookie.
All mutations require an `Origin` header exactly equal to `APP_ORIGIN`.

Migrate once, then start web:

```sh
bin/portal migrate
bin/portal web
```

In another terminal with the protected environment, run `bin/portal jobs`.
Open the HTTPS origin to register, manage records, upload private files, and request reports.
Click **Refresh data and reports** to read completed output.
The `/healthz` endpoint checks a real database connection.

Build the image without database credentials:

```sh
podman build --tag ghcr.io/example/sveltekit-portal:REVIEWED_COMMIT .
```

Replace `REVIEWED_COMMIT` with the full reviewed app commit.
The image runs as UID 1000 and defaults to `bin/portal web`.
The image has no entrypoint, so Stack migration and job commands replace the default command.
Publish the reviewed image and verify its registry digest before changing server settings.

## Prove isolated services

Use an empty PostgreSQL 17 database and a separate private test bucket.
The database role must own its database and tables.
The test runner needs Python 3 with psycopg 3 installed.
On Debian, install `python3-venv` before creating the test environment.
Prepare a separate test virtual environment. Node runs the actual app processes:

```sh
python3 -m venv "${TMPDIR:-/tmp}/sveltekit-tests-venv"
. "${TMPDIR:-/tmp}/sveltekit-tests-venv/bin/activate"
export PIP_CACHE_DIR="${TMPDIR:-/tmp}/sveltekit-tests-pip"
python -m pip install 'psycopg[binary]==3.3.7'
```
No production data or customer credentials belong in this test.

Supply the settings above, including `APP_ENV=staging`.
Choose two unused ports:

```sh
export TEST_WEB_PORTS=8073,8074
python tests/services.py
```

The runner applies migration 1, inserts title-only rows, and runs concurrent migration commands for migration 2.
The runner seeds twice, starts two web processes, and runs two report workers.
Checks cover shared sessions, logout revocation, ownership, CRUD, exact document bytes,
interrupted jobs, and graceful web/job shutdown. Synthetic rows remain for restore inspection.
Child logs go under `${TEST_LOG_DIR:-/tmp}` and contain no passwords or cookies.

An optional promotion command comes from `TEST_PROMOTE_ARGV`, a JSON command array.
Use that setting only in an isolated environment where you own every dependent service.
The command must stop the old primary and promote an existing synchronized standby.
Keep the host list unchanged. The runner checks the surviving web process and existing session afterward.
A restart alone does not prove primary selection.

## Synthetic staging data

Run `bin/portal seed-test-data` twice before starting workers.
Seeding requires `APP_ENV=development` or `APP_ENV=staging` and a runtime `FIXTURE_PASSWORD`.
A rerun preserves saved passwords, records, documents, and jobs.

| Account | Record title | Description | Document | Exact UTF-8 bytes |
| --- | --- | --- | --- | --- |
| `barbara@example.com` | Barbara invoice | First synthetic record | `barbara-note.txt` | `Barbara synthetic document` plus LF |
| `michael@example.com` | Michael invoice | Second synthetic record | `michael-note.txt` | `Michael synthetic document` plus LF |

Each account starts with one record, one document, and one pending report.
Each completed report contains `record_count=1` plus LF before later CRUD checks add records.
Sessions store hashed random tokens in PostgreSQL.
Accounts store bcrypt password hashes.
Logout deletes the database session, including for requests reaching another app server.

Uploads are private and limited to 8 MiB to bound memory and transfer duration.
URL-encoded forms are limited to 64 KiB. Multipart requests accept one file and 64 KiB of envelope overhead.
These limits bound memory and parsing work. Passwords accept 12 to 72 UTF-8 bytes
because bcrypt uses at most 72 bytes.
The database stores immutable object keys and SHA-256 checksums.
A metadata failure can leave an unreferenced object. Reconcile saved keys before deleting any object.
Never delete an object after an uncertain database commit.
This hosting example excludes password recovery, email verification, and abuse controls.
Public use needs ingress login limits.

## Prepare an additional Stack app

The coding agent edits the team's systems repository for this section.
Inventory existing apps, databases, buckets, ports, image tags, and host names first.
Reserve unused names and ports. The example uses `sveltekit_portal` and ports 8017/8018.
Preserve all existing app entries and image tags.

Add under `vars.apps` in `mmx_project_settings.yml`:

```yaml
sveltekit_portal:
  image: ghcr.io/example/sveltekit-portal
  web_ports: [8017, 8018]
  health_url_path: /healthz
  migration_command: bin/portal migrate
  jobs_command: bin/portal jobs
  jobs_connect_directly_to_postgres: false
  asset_directory: /app/build/client
  database_name: sveltekit_portal
  env:
    APP_ORIGIN: https://portal.example.com
    R2_BUCKET: example-sveltekit-portal-production
    R2_ENDPOINT: https://ACCOUNT_ID.r2.cloudflarestorage.com
  secrets_from_vault:
    R2_ACCESS_KEY_ID:
      where_the_value_comes_from: generated_by_the_setup
    R2_SECRET_ACCESS_KEY:
      where_the_value_comes_from: generated_by_the_setup
  production_uploads_r2_bucket: example-sveltekit-portal-production
  production_uploads_r2_key_variables:
    access_key_id: R2_ACCESS_KEY_ID
    secret_access_key: R2_SECRET_ACCESS_KEY
  restore_drill_check_queries:
    - name: the_migrations_came_back
      sql: SELECT count(*) = 2 FROM schema_migrations WHERE version IN ('0001_portal.sql', '0002_record_descriptions.sql')
```

Create separate private staging and production buckets with scoped keys.
Production's `R2_BUCKET` must equal `production_uploads_r2_bucket`.
Extend the upload-backup reader's bucket scope and enable uploads backups when needed.
A database backup does not include uploaded object bytes.

The setup (`set-up-outside-services`) makes the vault keys `sveltekit_portal_database_password` and `sveltekit_portal_<VARIABLE>` for each name in `secrets_from_vault`, and with staging01 their `staging_` copies. Nobody adds them by hand. Keep secret values out of Git.

Extend `database_passwords` in production's database role call in `playbooks/every_server.yml`:

```yaml
database_passwords:
  sveltekit_portal: "{{ .secrets.sveltekit_portal_database_password }}"
```

Extend staging's database role call:

```yaml
database_passwords:
  sveltekit_portal: "{{ .secrets.staging_sveltekit_portal_database_password }}"
```

Add these mappings to production's `app_secrets` for `app_server` and `jobs_server` role calls:

```yaml
sveltekit_portal_database_password: "{{ .secrets.sveltekit_portal_database_password }}"
sveltekit_portal_R2_ACCESS_KEY_ID: "{{ .secrets.sveltekit_portal_R2_ACCESS_KEY_ID }}"
sveltekit_portal_R2_SECRET_ACCESS_KEY: "{{ .secrets.sveltekit_portal_R2_SECRET_ACCESS_KEY }}"
```

For staging's `app_server` call, keep each left-hand name above.
Use the corresponding `staging_sveltekit_portal_` vault key on each right-hand side.
`env:` gives every environment the same value, so with staging01 staging reads production's `APP_ORIGIN` and `R2_BUCKET`. Tell the person this before adding staging01.
Extend the app's mappings in `playbooks/end_connections_that_use_an_old_database_password.yml` using the existing app's pattern.
The database password and both app secrets need rotation mappings.

In `inventories/servers.yml`, extend `deployed_image_tags.staging`,
`deployed_image_tags.production`, `public_host_names.staging`, and `public_host_names.production`.
Every mapping needs a `sveltekit_portal` entry.
Use the reviewed full commit tag and distinct HTTPS host names.
Create proxied CNAME records to the existing tunnel IDs.
The inventory renders locally managed tunnel ingress to Caddy.
Preserve existing routes and protect staging through Cloudflare Access.
Check that cache rules cover the new host names.

Run `mmx validate` in the systems repository.
Review the changes before applying `every_server` through the existing procedure.
The initial configuration can start the new app in every configured environment.
Read MMX's result before continuing.

Follow `operating_procedures/deploy_and_roll_back_an_app_release.md` for later releases:

```sh
./server_management_scripts/run_mmx_on_util01 run deploy --var environment_name=staging
```

The deploy affects the environment's configured releases.
Check every app's requested tag before running a shared-environment deploy.
Production deployment follows the operating procedure's approval step.

## Seed, switch, restore, and roll back

On staging only, run the tested image with staging's settings and secrets:

```sh
podman run --rm --network host \
  --env-file /etc/sveltekit_portal/sveltekit_portal_settings.env \
  --env-file /etc/sveltekit_portal/sveltekit_portal.env \
  --env APP_ENV=staging --env FIXTURE_PASSWORD \
  ghcr.io/example/sveltekit-portal:REVIEWED_COMMIT bin/portal seed-test-data
```

Run the seed twice. Supply the password through the protected process environment.
Verify exact fixture values and completed reports before further CRUD.
From a host with application-network access, verify two app servers:

```sh
python3 tests/check_portal.py \
  --server-a http://app001:8017 --server-b http://app002:8017 \
  --origin https://portal.example.com
```

Repeat registration, editing, upload, download, reports, and logout in the HTTPS browser.
Check labels, keyboard navigation, and stylesheet delivery.
Keep web and job processes running during `switch_database_primary` in each direction.
Record failed requests, process IDs, and time until a unique new write succeeds.
Verify sessions, owned files, and jobs afterward. Never blindly replay a failed mutation.
Repeat through transaction-mode PgBouncer when enabled.

The first restore drill checks only `the_migrations_came_back` before app data exists.
After seeding, save a manifest of accounts, password hashes, session rows, records,
object keys/checksums, pending jobs, completed output, and migration versions.
Compare restored rows to the manifest. Restore objects into an isolated bucket.
Download every restored reference and compare bytes.
Record recovery time and distinguish database recovery from whole-system recovery.

Rollback reuses the previous image while keeping the additive description migration.
Verify a title-only insert and existing records after rollback.
Test previous-release asset delivery through the Stack's mounted asset directory.
Verify the actual running image on every app server.

## Move from Vercel or Netlify

Replace the hosting-specific adapter with `@sveltejs/adapter-node`. Keep server routes and hooks in the Node build.
SvelteKit 3 config lives in `vite.config.js`. SvelteKit 3 removed `ORIGIN`. The custom Node server supplies canonical host/protocol headers from runtime `APP_ORIGIN`.
The launcher overwrites those headers before calling the generated adapter handler. Client headers cannot override the configured origin.
The launcher sets the upload body limit and listener host. SIGTERM drains HTTP before the shutdown hook closes the database pool.
Keep secrets in runtime server variables. Never bundle secrets into public environment variables.

Inventory provider functions, Edge bindings, scheduled tasks, image transformations and storage before moving.
Replace provider functions with Node server routes and run recurring work through your chosen scheduler.
Move long-running reports into the database job command. Static output cannot run private server routes.
Provider authentication, object storage and databases need separate migration plans.
An exported frontend alone does not move user accounts or uploaded files.

The fixture uses standard route handlers and a Svelte page with browser controls.
Incoming apps using remote functions, form actions, streaming or image services need additional checks.
Verify exact public origins, proxy settings, Secure cookies and cross-release frontend assets.
Use [adapter-node documentation](https://svelte.dev/docs/kit/adapter-node) when adapting an existing app.

## Set the database connection budget

`DATABASE_POOL_MAX_CONNECTIONS` sets the maximum pool size per process. The example default is 4.
Set `DATABASE_POOL_MAX_CONNECTIONS=2` for web and migrations.
Set `jobs_environment: {DATABASE_POOL_MAX_CONNECTIONS: "1"}` in the Stack app entry for the job container.
For standalone runs, pass the value through the process environment. Distroless images have no `env` executable.
Set `WEB_CONCURRENCY=1` to keep one web worker. Each additional process creates another pool.

On four eight-CPU servers, the default web concurrency and connection settings allow 144 connections, including jobs.
A rolling release can raise that allowance to 272 connections because old and new web processes overlap.
With one app server, web allowance two and jobs allowance one, steady use is at most three connections.
A release overlapping both web generations allows five. Add other apps, migrations, and system connections before comparing with PostgreSQL capacity.
These figures are connection allowances, not measured request throughput.

## Production admission check

A Stack deployment passed public health, fixture sign-in, record creation, and reading the saved record.
The app ran on one app server, with a web allowance of two PostgreSQL connections and a jobs allowance of one.
Web and jobs used direct multi-host PostgreSQL URLs. Both synthetic seed passes completed against real private R2 storage.
This admission check does not prove database switchover, silent-primary loss, replica reads, PgBouncer, browser release overlap, or memory sizing.

## Replica aggregate and database disruptions

Run the administrative report command inside the app container with the Stack's environment file:

```sh
node scripts/replica_report.mjs
```

The existing multi-host helper implements `prefer-standby`. node-postgres alone does not implement multi-host routing.
The command prints `connection_purpose`, `database_server_address`, `is_replica`, and `record_count`.
The `read` connection uses `DATABASE_READ_URL`. The `write` connection uses `DATABASE_URL`.
The write connection reports the primary's role and count without changing data.
A stale aggregate can use the replica. Account sessions, job reservations, and reads after a write keep the primary.
The command is administrative because the aggregate includes all accounts.
Do not expose the command as an unauthenticated HTTP endpoint.

Remove `statement_timeout` and `idle_in_transaction_session_timeout` from node-postgres startup settings. Set statement and lock timeouts with `SET LOCAL` after `BEGIN`. Keep `query_timeout`, which bounds the client request.

The shared two-server test on 2026-11-04 ran authenticated writes and reads every second, with queued jobs every five seconds.
Planned switches to the second server and back recovered without restarting the example's web or job container.
A silent database traffic drop promoted the standby in 29.64 seconds.
The initial silent-loss test recovered automatically for ten examples while the old primary stayed isolated.
Laravel required the connection timeout correction above.
The failover keeper safely rejoined the returning database as a replica without a manual Postgres restart.
The system procedure describes permanent replacement but lacks an explicit temporary-isolation return procedure.

## Real R2 upload checks

The production check on 2026-11-04 uploaded a 4,097-byte binary file and a 8 MiB binary file to real Cloudflare R2. Both authenticated downloads matched the original bytes and SHA-256.
The larger file used this example's 8 MiB limit; it did not test a 20 MiB upload. The limit bounds buffered request memory.

The tested client was @aws-sdk/client-s3 3.1161.0. Keep the account-specific `R2_ENDPOINT`, region `auto`, and path-style addressing in `lib/storage.mjs`.
The pinned client passed with its checksum defaults. No checksum-calculation override was needed in this run.
The example proxies private downloads through its authenticated `/documents/{id}` route. It has no presigned-download route.
These results cover the pinned client and settings, not every checksum algorithm or an untested SDK upgrade.

The completed live check passed replica reporting directly and through PgBouncer.
The replica aggregate reached the standby. The writer connection reached the primary.
Authenticated writes, reads, and background jobs passed through PgBouncer after switches in both directions.
No web or job container restarted during the successful failover checks.
All eleven examples recovered while the silently missing primary remained isolated.
The recovery measurements include proxy health checks and client queues, not only driver reconnect time.
The procedure's connection reading one day later remains pending.

## Browser release overlap and measured memory

The fixed example passed two live releases on 2026-11-04. The second release changed asset names.
All 36 old asset URLs returned HTTP 200 with the original bytes and correct content types from the new origin.
The signed-in old page saved a record without reloading. An independent authenticated request read the saved record.
The fixture has one application page. Its in-page actions do not cover lazy navigation to an additional client route. Test such routes separately when the incoming application has them.

The final production memory check on 2026-11-04 used one web worker and one jobs process on the same Debian 13 x86-64 server. It had 1,546 records when sampled. RSS means resident process memory; the numbers include master and worker processes. The warm-idle and observed-load peaks were:

| Process group | Warm idle RSS, MiB | Observed load peak RSS, MiB |
| --- | ---: | ---: |
| Web | 144.4 | 219.5 |
| Jobs | 86.6 | 86.6 |

The sampler read each process group every 100 ms for about 18 seconds. The short load used four read clients and one client that queued twelve reports and uploaded two files at the application limit. The database-disruption workload and test-browser polling were stopped first. All measured processes ran on the same app server, with transaction-mode PgBouncer and the explicit connection limits above.
For a conservative RAM planning model, reserve 657.0 MiB per app for two peak web generations and one jobs generation, including 25% growth room. With 1 GiB reserved for shared services and 10% of server RAM kept free, that gives 4 such apps in 4 GiB or 20 in 16 GiB. These are RAM-only projections at the measured worker/thread settings, not load-tested app counts. CPU, data growth, and PostgreSQL/PgBouncer capacity can require fewer apps. RSS can count shared pages twice, so this model is conservative. Do not substitute the Stack's CPU-count default for the explicit worker count used here.

For laptop test data, migrate against your local PostgreSQL database and local bucket, then run:

```sh
APP_ENV=development bin/portal seed-test-data
```

`bin/portal seed-test-data --accounts 200000` makes enough invented rows to show slow queries.
The total defaults to two accounts. Larger totals add accounts and owned records without extra documents or reports.
Production data stays on production servers. Add a missing data shape to the seed or a test.
