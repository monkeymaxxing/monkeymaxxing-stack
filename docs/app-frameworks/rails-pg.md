# Run Rails with PostgreSQL on the Stack

## Variances and guidance needs

Rails needs a database URL conversion before Active Record loads. Ruby's `pg`
driver accepts the Stack URL, but Rails' generic URL parser rejects multiple hosts.
`config/application.rb` consumes `DATABASE_URL` before Rails reads the environment.
`config/database.yml` uses libpq's parser and retains every host, port, and driver option.
The Stack URL stays unchanged outside the app.

Puma starts `WEB_CONCURRENCY` worker processes. Each worker defaults to four threads and a four-connection database pool. Budget connections for every app server, worker process,
job process, and overlapping release. The job command runs one worker per process.
Puma drains SIGTERM requests and disables its default signal exception for a clean exit.
The app reads the primary for immediate session and record consistency.
`DATABASE_READ_URL` is used only by the explicit replica report command below. HTTP reads stay on the primary.

Rails migrations run through `bin/portal migrate` before web and job containers start.
Rails' migration version table prevents repeat application. Rails uses a session
advisory lock to serialize migration runners, so migrations need direct PostgreSQL.
The Stack already gives the migration container a direct connection.
Jobs use transaction row locks with `SKIP LOCKED` and need no dedicated session.

Propshaft compiles fingerprinted CSS into `/app/public/assets`.
Set the Stack's `asset_directory` to that exact directory.
The Stack retains files from the previous release so open pages keep their stylesheet.
Build assets before publishing the image. Do not compile assets when starting web containers.

Database failures return a visible 503 and discard stale connections.
The app never replays an HTTP mutation automatically because a failed reply can follow a successful commit.
Inspect saved records before resubmitting a failed write.
A later request opens a connection and libpq selects the writable server again.

This guide prepares another app on a running Stack system.
Live deployment, real R2 permissions, PgBouncer, and Stack backup recovery need separate verification.
The [test record](../../examples/app-frameworks/rails-pg/testing.md) states the measured proof and limits.

## Copy and build

Copy [the app directory](../../examples/app-frameworks/rails-pg/) into your app repository.
Use Ruby 3.3 or newer and the supplied `Gemfile.lock` on a Linux build host.
Install a C compiler, libpq development files, and libyaml development files.
Run commands from the copied app directory:

```sh
export BUNDLE_PATH="${TMPDIR:-/tmp}/rails-portal-bundle"
bundle install
```

Keep credentials in your secret store or protected process environment.
Never commit credential values or store shared credentials in the copied repository.

| Variable | Required value |
| --- | --- |
| `DATABASE_URL` | `postgresql://rails_portal:PASSWORD@db01:5432,db02:5432/rails_portal?target_session_attrs=read-write&connect_timeout=3` |
| `RAILS_ENV` | `production`, including staging containers |
| `APP_ORIGIN` | Exact HTTPS origin, such as `https://portal.example.com`, without a trailing slash |
| `SECRET_KEY_BASE` | A randomly generated Rails secret, shared by all containers of this app and environment |
| `PORT` | Assigned listener port, such as `8007` |
| `WEB_CONCURRENCY` | Positive number of Puma worker processes |
| `R2_ENDPOINT` | `https://ACCOUNT_ID.r2.cloudflarestorage.com` |
| `R2_BUCKET` | Private bucket assigned to this app and environment |
| `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | Credentials restricted to the assigned bucket |
| `APP_ENV` | `development` or `staging` for synthetic seeding |
| `FIXTURE_PASSWORD` | Runtime seed/check password, 12 to 72 bytes |

Generate `SECRET_KEY_BASE` with `bundle exec ruby -rsecurerandom -e 'print SecureRandom.hex(64)'`.
Send the value directly to your secret store. Do not put the value in a report.
Rails assumes public HTTPS because the Stack terminates TLS before the app.
The browser requires HTTPS for the Secure session cookie.
Direct private HTTP tests explicitly send the cookie.
All mutations require an `Origin` header exactly equal to `APP_ORIGIN`.

Compile assets, migrate once, and start web:

```sh
export RAILS_ENV=production
bundle exec rake assets:precompile
bin/portal migrate
bin/portal web
```

In another terminal with the protected environment, run `bin/portal jobs`.
Open the HTTPS origin to register, manage records, upload private files, and request reports.
Click **Refresh data and reports** to read completed output.
The `/healthz` endpoint checks a real database connection.

The image build compiles assets with an explicit build-only key and no database credentials:

```sh
podman build --tag ghcr.io/example/rails-portal:REVIEWED_COMMIT .
```

Replace `REVIEWED_COMMIT` with the full reviewed app commit.
The image runs as UID 1000 and defaults to `bin/portal web`.
The image has no entrypoint, so Stack migration and job commands replace the default command.
Publish the reviewed image and verify its registry digest before changing server settings.

## Prove isolated services

Use an empty PostgreSQL 17 database and a separate private test bucket.
The database role must own its database and tables.
The test runner needs Python 3 with psycopg 3 installed.
On Debian, the test package is `python3-psycopg`.
No production data or customer credentials belong in this test.

Supply the settings above, including `APP_ENV=staging` and `RAILS_ENV=production`.
Choose two unused ports:

```sh
export TEST_WEB_PORTS=8041,8042
python3 tests/services.py
```

The runner applies migration 1, inserts title-only rows, and applies migration 2.
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
Sessions are random tokens. PostgreSQL stores only token hashes and expiry times.
Logout deletes the database session, including for requests reaching another app server.

Uploads are private and limited to 8 MiB to bound memory and transfer duration.
The database stores immutable object keys and SHA-256 checksums.
A metadata failure can leave an unreferenced object. Reconcile saved keys before deleting any object.
Never delete an object after an uncertain database commit.
This hosting example excludes password recovery, email verification, and abuse controls.
Public use needs ingress login limits.

## Prepare an additional Stack app

The coding agent edits the team's systems repository for this section.
Inventory existing apps, databases, buckets, ports, image tags, and host names first.
Reserve unused names and ports. The example uses `rails_portal` and ports 8007/8008.
Preserve all existing app entries and image tags.

Add under `vars.apps` in `mmx_project_settings.yml`:

```yaml
rails_portal:
  image: ghcr.io/example/rails-portal
  web_ports: [8007, 8008]
  health_url_path: /healthz
  migration_command: bin/portal migrate
  jobs_command: bin/portal jobs
  jobs_connect_directly_to_postgres: false
  asset_directory: /app/public/assets
  database_name: rails_portal
  env:
    RAILS_ENV: production
    R2_ENDPOINT: https://ACCOUNT_ID.r2.cloudflarestorage.com
  secrets_from_vault:
    - APP_ORIGIN
    - SECRET_KEY_BASE
    - R2_BUCKET
    - R2_ACCESS_KEY_ID
    - R2_SECRET_ACCESS_KEY
  production_uploads_r2_bucket: example-rails-portal-production
  restore_drill_check_queries:
    - name: the_migrations_came_back
      sql: SELECT count(*) = 2 FROM schema_migrations WHERE version IN ('20261104000100', '20261104000200')
```

Create separate private staging and production buckets with scoped keys.
Production's `R2_BUCKET` must equal `production_uploads_r2_bucket`.
Extend the upload-backup reader's bucket scope and enable uploads backups when needed.
A database backup does not include uploaded object bytes.

Add vault keys `rails_portal_database_password`, `rails_portal_APP_ORIGIN`,
`rails_portal_SECRET_KEY_BASE`, `rails_portal_R2_BUCKET`, `rails_portal_R2_ACCESS_KEY_ID`,
and `rails_portal_R2_SECRET_ACCESS_KEY`.
Add separate staging keys prefixed `staging_rails_portal_`.
Use your existing vault procedure. Keep secret values out of Git.

Extend `database_passwords` in production's database role call in `playbooks/every_server.yml`:

```yaml
database_passwords:
  rails_portal: "{{ .secrets.rails_portal_database_password }}"
```

Extend staging's database role call:

```yaml
database_passwords:
  rails_portal: "{{ .secrets.staging_rails_portal_database_password }}"
```

Add these mappings to production's `app_secrets` for `app_server` and `jobs_server` role calls:

```yaml
rails_portal_database_password: "{{ .secrets.rails_portal_database_password }}"
rails_portal_APP_ORIGIN: "{{ .secrets.rails_portal_APP_ORIGIN }}"
rails_portal_SECRET_KEY_BASE: "{{ .secrets.rails_portal_SECRET_KEY_BASE }}"
rails_portal_R2_BUCKET: "{{ .secrets.rails_portal_R2_BUCKET }}"
rails_portal_R2_ACCESS_KEY_ID: "{{ .secrets.rails_portal_R2_ACCESS_KEY_ID }}"
rails_portal_R2_SECRET_ACCESS_KEY: "{{ .secrets.rails_portal_R2_SECRET_ACCESS_KEY }}"
```

For staging's `app_server` call, keep each left-hand name above.
Use the corresponding `staging_rails_portal_` vault key on each right-hand side.
Extend the app's mappings in `playbooks/end_connections_that_use_an_old_database_password.yml` using the existing app's pattern.
The database password and all five app secrets need rotation mappings.

In `inventories/servers.yml`, extend `deployed_image_tags.staging`,
`deployed_image_tags.production`, `public_host_names.staging`, and `public_host_names.production`.
Every mapping needs a `rails_portal` entry.
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
  --env-file /etc/rails_portal/rails_portal_settings.env \
  --env-file /etc/rails_portal/rails_portal.env \
  --env APP_ENV=staging --env FIXTURE_PASSWORD \
  ghcr.io/example/rails-portal:REVIEWED_COMMIT bin/portal seed-test-data
```

Run the seed twice. Supply the password through the protected process environment.
Verify exact fixture values and completed reports before further CRUD.
From a host with application-network access, verify two app servers:

```sh
python3 tests/check_portal.py \
  --server-a http://app001:8007 --server-b http://app002:8007 \
  --origin https://portal.example.com
```

Repeat registration, editing, upload, download, reports, and logout in the HTTPS browser.
Check labels, keyboard navigation, and stylesheet delivery.
Keep web and job processes running during `switch_database_primary` in each direction.
Record failed requests, process IDs, and time until a unique new write succeeds.
Verify sessions, owned files, and jobs afterward. Never blindly replay a failed mutation.
Repeat through transaction-mode PgBouncer when enabled.

The first restore drill checks only `the_migrations_came_back` before app data exists.
After seeding, save a manifest of accounts, password hashes, session hashes, records,
object keys/checksums, pending jobs, completed output, and migration versions.
Compare restored rows to the manifest. Restore objects into an isolated bucket.
Download every restored reference and compare bytes.
Record recovery time and distinguish database recovery from whole-system recovery.

Rollback reuses the previous image while keeping the additive description migration.
Verify a title-only insert and existing records after rollback.
Test previous-release asset delivery through the Stack's mounted asset directory.
Verify the actual running image on every app server.

## Set the database connection budget

`DATABASE_POOL_MAX_CONNECTIONS` sets the maximum pool size per process. The example default is 4.
Set `DATABASE_POOL_MAX_CONNECTIONS=2` for web and migrations.
Set `jobs_environment: {DATABASE_POOL_MAX_CONNECTIONS: "1"}` in the Stack app entry for the job container.
For standalone runs, pass the value through the process environment. Distroless images have no `env` executable.
Set `WEB_CONCURRENCY=1` to keep one web worker. Set `WEB_THREADS=2` to match the two-connection pool. Puma defaults to four threads per worker.

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
bundle exec ruby scripts/replica_report.rb
```

Active Record provides a separate connection. libpq selects the standby from the unchanged multi-host URL.
The command prints `connection_purpose`, `database_server_address`, `is_replica`, and `record_count`.
The `read` connection uses `DATABASE_READ_URL`. The `write` connection uses `DATABASE_URL`.
The write connection reports the primary's role and count without changing data.
A stale aggregate can use the replica. Account sessions, job reservations, and reads after a write keep the primary.
The command is administrative because the aggregate includes all accounts.
Do not expose the command as an unauthenticated HTTP endpoint.

Remove timeout `variables:` from `database.yml`. Set timeouts with `SET LOCAL` inside the request and job transactions. The existing example has `prepared_statements: false`.

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

The tested client was aws-sdk-s3 Ruby. Keep the account-specific `R2_ENDPOINT`, region `auto`, and path-style addressing in `lib/object_storage.rb`.
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

The old page saved a record after the real release without reloading, and an independent request read it back. Old JS/CSS URLs were also checked directly at the new origin for matching bytes and content types. Those origin checks passed.
The fixture has one application page. Its in-page actions do not cover lazy navigation to an additional client route. Test such routes separately when the incoming application has them.

The final production memory check on 2026-11-04 used one web worker and one jobs process on the same Debian 13 x86-64 server. Puma used two threads. It had 1,535 records when sampled. RSS means resident process memory; the numbers include master and worker processes. The warm-idle and observed-load peaks were:

| Process group | Warm idle RSS, MiB | Observed load peak RSS, MiB |
| --- | ---: | ---: |
| Web | 198.1 | 297.2 |
| Jobs | 104.7 | 104.9 |

The sampler read each process group every 100 ms for about 18 seconds. The short load used four read clients and one client that queued twelve reports and uploaded two files at the application limit. The database-disruption workload and test-browser polling were stopped first. All measured processes ran on the same app server, with transaction-mode PgBouncer and the explicit connection limits above.
For a conservative RAM planning model, reserve 874.2 MiB per app for two peak web generations and one jobs generation, including 25% growth room. With 1 GiB reserved for shared services and 10% of server RAM kept free, that gives 3 such apps in 4 GiB or 15 in 16 GiB. These are RAM-only projections at the measured worker/thread settings, not load-tested app counts. CPU, data growth, and PostgreSQL/PgBouncer capacity can require fewer apps. RSS can count shared pages twice, so this model is conservative. Do not substitute the Stack's CPU-count default for the explicit worker count used here.

Use a distinct filename for each upload in this fixture. Reusing an account/filename violates the document uniqueness constraint; the example currently reports that as HTTP 503. The first load check hit that constraint. A corrected unique-filename load passed; the misleading duplicate-filename response remains an application issue.

For laptop test data, migrate against your local PostgreSQL database and local bucket, then run:

```sh
APP_ENV=development bin/portal seed-test-data
```

`bin/portal seed-test-data --accounts 200000` makes enough invented rows to show slow queries.
The total defaults to two accounts. Larger totals add accounts and owned records without extra documents or reports.
Production data stays on production servers. Add a missing data shape to the seed or a test.
