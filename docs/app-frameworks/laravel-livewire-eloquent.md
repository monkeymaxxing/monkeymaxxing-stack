# Run Laravel, Livewire and Eloquent on the Stack

The [Laravel example](../../examples/app-frameworks/laravel-livewire-eloquent/) stores private customer records and documents, and generates record-count reports.
Laravel handles accounts and requests. Livewire updates the records screen without a full page reload.
Eloquent maps PHP objects to PostgreSQL rows. FrankenPHP serves PHP and the included browser assets in one container.

Use the example to check your framework's connection to the Stack before adapting your own app.
The [test record](../../examples/app-frameworks/laravel-livewire-eloquent/testing.md) separates measured checks from remaining live checks.
Email verification, password recovery and account administration are outside the example.

## Check the example on an isolated Linux system

Copy `examples/app-frameworks/laravel-livewire-eloquent/` into your app repository.
Run commands below from the copied directory.
Keep the guide open from the Stack checkout while working in your app repository.

Use a disposable Linux system with Podman, PHP 8.4 or later, Composer 2, Python 3 and Python's `boto3` package.
PHP needs `pdo_pgsql`, `mbstring`, `dom`, `xml`, `curl`, `zip`, `intl` and `pcntl`.
The integration check starts PostgreSQL 17 and an S3-compatible test service in containers.
Port 9090 must be unused because the S3 test service listens on port 9090.
The test service also uses port 9191 for HTTPS.

```sh
COMPOSER_CACHE_DIR="${TMPDIR:-/tmp}/laravel-composer-cache" composer install --no-interaction --no-progress
podman build --build-arg RELEASE=local-check --tag localhost/laravel-portal:check .
python3 tests/check_local.py localhost/laravel-portal:check
```

The check creates unique container names, synthetic passwords and a private temporary evidence directory.
The check never uses your configured database or bucket.
The check removes the test containers on success and failure.
A failing check exits with an error. Read the evidence directory printed at the end.

Expect passing accounts, ownership, shared sessions, uploads, jobs, migrations, reconnection and graceful shutdown checks.
The exact checks and limits are listed in [testing.md](../../examples/app-frameworks/laravel-livewire-eloquent/testing.md).

## Configure an app environment

The app needs a PostgreSQL database and an existing private R2 bucket.
Keep each app and environment in separate databases and buckets.
Supply settings through a protected env file or the Stack's vault and role inputs.
Do not commit real secrets.

| Variable | Required value or purpose |
| --- | --- |
| `DATABASE_URL` | Stack-generated multi-host writer URL, described below |
| `APP_URL` | Public HTTPS origin, such as `https://portal.example.com` |
| `APP_KEY` | Random value made by the setup, shared by every web and jobs container; `config/app.php` derives the Laravel encryption key from it |
| `APP_ENV` | `production` normally, `staging` only for staging |
| `PORT` | Web port selected by the Stack |
| `WEB_CONCURRENCY` | PHP thread count selected by the Stack |
| `R2_ENDPOINT` | `https://ACCOUNT_ID.r2.cloudflarestorage.com` for your R2 account |
| `R2_BUCKET` | Existing private bucket for the selected environment |
| `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | Credentials restricted to the selected bucket |
| `FIXTURE_PASSWORD` | Runtime-only seed password, 12 to 72 bytes, needed only for staging seeds |

The setup makes `APP_KEY` as 64 random letters and digits. Laravel's AES-256-CBC needs a 32-byte key, so the app's `config/app.php` derives the key from the setup's value:

```php
'key' => 'base64:'.base64_encode(hash('sha256', env('APP_KEY'), true)),
```

The same value reaches every web and jobs container, so the derived key is stable.
Changing `APP_KEY` invalidates existing cookies.

Production cookies require HTTPS. The isolated test alone sets `SESSION_SECURE_COOKIE=false` for loopback HTTP.
The app uses PostgreSQL sessions, so login survives requests to another app server.
The app stores no customer state on a container's local disk.
Local writable directories hold only compiled views and framework cache files.
The Stack runs every container with a read-only file system, so list these directories in the app's `writable_temporary_directories` in `mmx_project_settings.yml` (the next section shows the line). Blade compiles views into `/app/storage/framework/views`, and FrankenPHP's Caddy saves its configuration in `/config/caddy` and `/data/caddy`. The Stack mounts each listed directory as memory-backed and empty at every start.

### Database connections

Keep `DATABASE_URL` in the Stack's original form:

```text
postgresql://portal:ENCODED_PASSWORD@db01:5432,db02:5432/portal?target_session_attrs=read-write&connect_timeout=3
```

The Stack supplies real server addresses and an encoded password.
For PgBouncer, the Stack supplies port `6432` for each server.
Leave Laravel's `DB_URL` unset.
Laravel's normal URL parser cannot preserve the Stack's multiple hosts.

`config/database.php` and `app/Database/` convert the URL into PDO's connection settings.
PDO uses libpq, PostgreSQL's client library, to select the writable primary whenever a connection opens.
The app uses the primary for reads because sessions and recent changes need current data.
`DATABASE_READ_URL` can remain supplied by the Stack. HTTP requests do not open a replica connection. The explicit report command below uses a replica.
The connector sets explicit TCP keepalive and TCP user timeout values, listed below.

The URL converter accepts `target_session_attrs=read-write` or `prefer-standby`, positive `connect_timeout`, and optional `sslmode`.
Unsupported URL settings fail explicitly. Job transactions set a 12-second statement timeout and a five-second lock timeout with `SET LOCAL`.
The PgBouncer change removed ordinary web deadlines. Web middleware now wraps session reads, authentication reads and controller queries in one transaction. `SET LOCAL` applies 12-second statement and five-second lock deadlines.
The health query uses a two-second `SET LOCAL` deadline inside a transaction. Connection time is additional, per listed server. The persistent PDO connection keeps normal requests from probing a dead first host repeatedly.

Laravel normally retries some queries after a lost connection.
`NoReplayPostgresConnection` returns the failed query instead because PostgreSQL could have committed before the reply disappeared.
Check a failed mutation's result before submitting another mutation.
Later requests and later job transactions connect again using the unchanged URL.

## Run each app process

The image's default command starts FrankenPHP on `PORT`.
The image runs as user `1000`, serves files from `/app/public`, and has an empty `/app/assets` directory.
Livewire serves the required JavaScript through Laravel. No Node build or outside asset host is required.
FrankenPHP uses `WEB_CONCURRENCY` PHP threads in classic request mode.

Run migrations before starting a new release:

```sh
podman run --rm --network host --env-file /secure/portal.env \
  localhost/laravel-portal:check php artisan migrate --force
```

The migration command runs ordered transactional migrations once.
Migration 2 adds `records.description` with an empty default and preserves existing rows.
Rolling back the image does not roll back database migrations.

Start web and jobs as separate processes:

```sh
podman run --name portal-web --network host --env-file /secure/portal.env \
  localhost/laravel-portal:check
podman run --name portal-jobs --network host --env-file /secure/portal.env \
  localhost/laravel-portal:check php artisan portal:jobs
```

Run the commands in separate terminals for a manual check.
The Stack uses managed services for web and jobs containers.
`GET /healthz` returns 200 only after the database answers and both migrations exist.
SIGTERM lets an active web request or report finish before shutdown.
The container runtime must allow at least 25 seconds before forcing termination.

Reports use a PostgreSQL `FOR UPDATE SKIP LOCKED` row lock.
A worker holds the lock while counting only the owner's records and committing the output and completion together.
Killing a worker rolls back the unfinished transaction, so another worker can claim the report.
The example deliberately uses `portal:jobs`, rather than Laravel's `queue:work`.
Laravel's standard database queue reserves and acknowledges work in separate transactions.

## Seed staging and check the portal

Use only staging's database, bucket and restricted credentials.
Supply `APP_ENV=development` or `APP_ENV=staging` and `FIXTURE_PASSWORD` through the process environment.

```sh
podman run --rm --network host --env-file /secure/portal-staging.env \
  localhost/laravel-portal:check php artisan portal:seed-test-data
```

The seed creates Barbara and Michael at `barbara@example.com` and `michael@example.com`.
Each account gets one record, one private document and one pending report.
Rerunning the seed preserves existing passwords and records, and creates no duplicate fixture document or report.
The exact fixture bytes are listed in the example's [README](../../examples/app-frameworks/laravel-livewire-eloquent/README.md).
Start workers only after recording the pending fixture jobs.

Open the public app and sign in with the runtime fixture password.
Add, edit and delete a record. Upload a document and download the document through the authenticated link.
Request a report. The report appears after a worker completes the report transaction.

For automated HTTP checks against two web containers, provide `PORTAL_URL_A`, `PORTAL_URL_B` and `FIXTURE_PASSWORD` through the environment.
Run `python3 tests/check_http.py` after a fresh seed and before starting workers.
The HTTP check creates synthetic test rows and verifies sessions and logout across app containers.
The HTTP check also checks ownership refusals, CSRF protection and exact uploaded bytes.

## Prepare an additional app on a running Stack

These steps prepare a new app without replacing an existing app.
Do not run a deployment until the system owner approves the target release and environment.
Build and publish the reviewed image first. Use the full app commit ID as the immutable image tag.

Add `laravel_portal` under the existing `vars.apps` mapping in your systems repository's `mmx_project_settings.yml`.
Choose two unused ports within the Stack's app port range, `8001` to `8099`.
Replace the example registry and bucket values:

```yaml
vars:
  apps:
    laravel_portal:
      image: ghcr.io/example/laravel-portal
      web_ports: [8005, 8006]
      health_url_path: /healthz
      migration_command: php artisan migrate --force
      jobs_command: php artisan portal:jobs
      jobs_connect_directly_to_postgres: false
      asset_directory: /app/assets
      writable_temporary_directories: [/app/storage/framework/views, /config/caddy, /data/caddy]
      database_name: laravel_portal
      env:
        APP_ENV: production
        APP_URL: https://portal.example.com
        R2_BUCKET: example-laravel-portal-production
        R2_ENDPOINT: https://ACCOUNT_ID.r2.cloudflarestorage.com
      secrets_from_vault:
        APP_KEY:
          where_the_value_comes_from: generated_by_the_setup
        R2_ACCESS_KEY_ID:
          where_the_value_comes_from: generated_by_the_setup
        R2_SECRET_ACCESS_KEY:
          where_the_value_comes_from: generated_by_the_setup
      production_uploads_r2_bucket: example-laravel-portal-production
      production_uploads_r2_key_variables:
        access_key_id: R2_ACCESS_KEY_ID
        secret_access_key: R2_SECRET_ACCESS_KEY
      restore_drill_check_queries:
        - name: the_migrations_came_back
          sql: >-
            select count(*) = 2 from migrations where migration in
            ('0001_01_01_000001_create_portal', '0001_01_01_000002_record_descriptions')
```

The setup (`set-up-outside-services`) makes the app's vault keys: the database password and `laravel_portal_<VARIABLE>` for each name in `secrets_from_vault`, and with staging01 their `staging_` copies. Nobody adds them by hand.
Pass the following entries through `app_secrets` in the production `app_server` and `jobs_server` role calls:

```yaml
laravel_portal_database_password: "{{ .secrets.laravel_portal_database_password }}"
laravel_portal_APP_KEY: "{{ .secrets.laravel_portal_APP_KEY }}"
laravel_portal_R2_ACCESS_KEY_ID: "{{ .secrets.laravel_portal_R2_ACCESS_KEY_ID }}"
laravel_portal_R2_SECRET_ACCESS_KEY: "{{ .secrets.laravel_portal_R2_SECRET_ACCESS_KEY }}"
```

For staging, retain the left-hand names and use separate `staging_laravel_portal_...` vault keys on the right.
`env:` gives every environment the same value, so with staging01 staging reads production's `APP_URL`, `APP_ENV`, and `R2_BUCKET`. Tell the person this before adding staging01.
Staging's bucket and credentials must reach staging objects only.
Pass the app password where the database roles receive app passwords, following the Stack's initial setup.
Record the reviewed image tag under `deployed_image_tags` and the public hostname under `public_host_names` in `inventories/servers.yml`.
Keep all existing apps, tags, hostnames and secrets.

Run `mmx validate` before applying the systems configuration.
Follow the Stack's [app configuration in chapter 2 (get your app ready to deploy)](../../skills/monkeymaxxing-stack/systems_repository_template/initial_setup/02_get_your_app_ready_to_deploy.md)
and [deploy-and-rollback procedure](../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/deploy_and_roll_back_an_app_release.md).
A push alone changes no server. The approved MMX run applies the selected release.
The deployment runs migrations before switching traffic to healthy new web containers.

The first restore drill must use only `the_migrations_came_back`, before users create data.
After seeding, add checks for fixture ownership, documents and report output.
A PostgreSQL restore brings back object keys and hashes, but a PostgreSQL restore does not bring back S3 object bytes.
Verify the uploads backup and downloaded bytes separately.
An upload with an uncertain metadata commit can leave an unreferenced immutable object.
Reconcile unreferenced objects against retained database backups before removing objects.

## Prove the live release

Record the image ID, release string, migration versions and HTTP results from every app server.
Confirm real R2 credentials enforce private access and bucket separation.
Reuse a signed-in cookie across two app servers and confirm logout revokes the cookie on the second server.
Run two workers and confirm owner-only report counts and interrupted-work recovery.

Keep the web and jobs containers running while the Stack runs `switch_database_primary` to the replica and back.
Record failed requests and the time until fresh writes succeed.
Confirm ownership, sessions and report completion after each switch without changing URLs or restarting app containers.
Repeat through PgBouncer when PgBouncer is enabled.
The Node.js driver check does not prove PHP behavior.

Run the Stack backup and restore procedures separately, including uploaded-byte checks.
Record recovery time and the recovery boundaries.
The isolated restart and logical-restore checks do not establish a live Stack recovery claim.

## Set the database connection budget

Laravel uses one request connection per PHP thread instead of a shared application pool.
`WEB_CONCURRENCY` controls FrankenPHP threads. The Stack defaults this setting to the server CPU count.
Set `WEB_CONCURRENCY=2` for one FrankenPHP process with two PHP threads. The single jobs process uses one connection.

On four eight-CPU servers, the default web concurrency and connection settings allow 36 connections, including jobs.
A rolling release can raise that allowance to 68 connections because old and new web processes overlap.
With one app server, web allowance two and jobs allowance one, steady use is at most three connections.
A release overlapping both web generations allows five. Add other apps, migrations, and system connections before comparing with PostgreSQL capacity.
These figures are connection allowances, not measured request throughput.

## Run FrankenPHP with the Stack security settings

The base image marks `/usr/local/bin/frankenphp` with `cap_net_bind_service=ep`.
The Stack drops every Linux capability and prevents new privileges. Linux then refuses to execute that marked binary with `Operation not permitted`.
Remove the file capability in the app image with `RUN setcap -r /usr/local/bin/frankenphp`, before changing users.
The Stack assigns ports above 1024, so FrankenPHP needs no privileged-port capability. Keep the Stack security settings enabled.
Verify the built image with `docker run --rm --cap-drop ALL --security-opt no-new-privileges IMAGE frankenphp version`.

## Production admission check

A Stack deployment passed public health, fixture sign-in, record creation, and reading the saved record.
The app ran on one app server, with a web allowance of two PostgreSQL connections and a jobs allowance of one.
Web and jobs used direct multi-host PostgreSQL URLs. Both synthetic seed passes completed against real private R2 storage.
This admission check does not prove database switchover, silent-primary loss, replica reads, PgBouncer, browser release overlap, or memory sizing.

## Replica aggregate and database disruptions

Run the administrative report command inside the app container with the Stack's environment file:

```sh
php scripts/replica_report.php
```

Laravel provides a named connection. The connector preserves `target_session_attrs=prefer-standby` and `connect_timeout` in the libpq DSN.
The command prints `connection_purpose`, `database_server_address`, `is_replica`, and `record_count`.
The `read` connection uses `DATABASE_READ_URL`. The `write` connection uses `DATABASE_URL`.
The write connection reports the primary's role and count without changing data.
A stale aggregate can use the replica. Account sessions, job reservations, and reads after a write keep the primary.
The command is administrative because the aggregate includes all accounts.
Do not expose the command as an unauthenticated HTTP endpoint.

Set `PDO::ATTR_TIMEOUT` from the URL's `connect_timeout`, and set `PDO::ATTR_PERSISTENT: true`. Set `PDO::PGSQL_ATTR_DISABLE_PREPARES: true` so PDO sends bound parameters without named server statements. Native named PDO statements aborted multi-query report transactions through PgBouncer, even when simple web writes succeeded. PHP already applies `PDO::ATTR_TIMEOUT` to libpq. Persistent connections avoid probing a dead first host on every HTTP request. Repeated three-second probes exceeded the proxy's three-second health timeout during silent-primary loss. The connector also sets `keepalives=1`, `keepalives_idle=30`, `keepalives_interval=5`, `keepalives_count=3`, and `tcp_user_timeout=10000`. Set job timeouts with `SET LOCAL`, rather than a session `SET` at login.

The shared two-server test on 2026-11-04 ran authenticated writes and reads every second, with queued jobs every five seconds.
Planned switches to the second server and back recovered without restarting the example's web or job container.
A silent database traffic drop promoted the standby in 29.64 seconds.
The initial silent-loss test recovered automatically for ten examples while the old primary stayed isolated.
Laravel required persistent PDO connections as described above. The persistent-connection fix passed the repeat silent-loss check.
The failover keeper safely rejoined the returning database as a replica without a manual Postgres restart.
The system procedure describes permanent replacement but lacks an explicit temporary-isolation return procedure.

## Real R2 upload checks

The production check on 2026-11-04 uploaded a 4,097-byte binary file and a 8 MiB binary file to real Cloudflare R2. Both authenticated downloads matched the original bytes and SHA-256.
The larger file used this example's 8 MiB limit; it did not test a 20 MiB upload. The limit bounds buffered request memory.

The tested client was Flysystem with aws/aws-sdk-php 3.402.5. Keep the account-specific `R2_ENDPOINT`, region `auto`, and path-style addressing in `config/filesystems.php`.
The pinned client passed with its checksum defaults. No checksum-calculation override was needed in this run.
PHP uses `upload_max_filesize=8M` and `post_max_size=10M`, leaving room for the multipart envelope.
The example proxies private downloads through its authenticated `/documents/{id}` route. It has no presigned-download route.
These results cover the pinned client and settings, not every checksum algorithm or an untested SDK upgrade.

The completed live check passed replica reporting directly and through PgBouncer.
The replica aggregate reached the standby. The writer connection reached the primary.
Authenticated writes, reads, and background jobs passed through PgBouncer after switches in both directions.
No web or job container restarted during the successful failover checks.
All eleven examples recovered while the silently missing primary remained isolated.
The recovery measurements include proxy health checks and client queues, not only driver reconnect time.
The procedure's connection reading one day later remains pending.

The final pooled job check found that a successful enqueue did not prove worker completion.
The PDO named-statement version left durable jobs queued with SQLSTATE `25P02`.
With `PDO::PGSQL_ATTR_DISABLE_PREPARES: true`, the normal worker drained the queue.
The final check verifies each acknowledged job's completed output after a switchover.

## Browser release overlap and measured memory

The original Livewire component saved a record after the real release without reloading, and an independent request read it back. The vendor JavaScript URL and bytes were unchanged. A database-drill error dialog was excluded from the verdict; the old component passed after that dialog was dismissed. This does not test a Livewire library upgrade or Vite asset changes.
The fixture has one application page. Its in-page actions do not cover lazy navigation to an additional client route. Test such routes separately when the incoming application has them.

The final production memory check on 2026-11-04 used two PHP threads and one jobs process on the same Debian 13 x86-64 server. It had 1,778 records when sampled. RSS means resident process memory; the numbers include master and worker processes. The warm-idle and observed-load peaks were:

| Process group | Warm idle RSS, MiB | Observed load peak RSS, MiB |
| --- | ---: | ---: |
| Web | 122.1 | 165.1 |
| Jobs | 60.7 | 60.7 |

The sampler read each process group every 100 ms for about 18 seconds. The short load used four read clients and one client that queued twelve reports and uploaded two files at the application limit. The database-disruption workload and test-browser polling were stopped first. All measured processes ran on the same app server, with transaction-mode PgBouncer and the explicit connection limits above.
For a conservative RAM planning model, reserve 488.7 MiB per app for two peak web generations and one jobs generation, including 25% growth room. With 1 GiB reserved for shared services and 10% of server RAM kept free, that gives 5 such apps in 4 GiB or 28 in 16 GiB. These are RAM-only projections at the measured worker/thread settings, not load-tested app counts. CPU, data growth, and PostgreSQL/PgBouncer capacity can require fewer apps. RSS can count shared pages twice, so this model is conservative. Do not substitute the Stack's CPU-count default for the explicit worker count used here.

For laptop test data, migrate against your local PostgreSQL database and local bucket, then run:

```sh
APP_ENV=development php artisan portal:seed-test-data
```

`php artisan portal:seed-test-data --accounts 200000` makes enough invented rows to show slow queries.
The total defaults to two accounts. Larger totals add accounts and owned records without extra documents or reports.
One password hash and two set-based SQL inserts keep generated data fast.
Production data stays on production servers. Add a missing data shape to the seed or a test.
