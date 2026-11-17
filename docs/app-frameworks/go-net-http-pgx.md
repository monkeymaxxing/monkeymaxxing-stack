# Run Go with net/http and pgx on the Stack

This guide shows how Go apps using net/http and pgx follow the Stack's database and deployment rules.
The customer portal exercises accounts, private records, documents, and background reports.
The [working files](../../examples/app-frameworks/go-net-http-pgx/README.md) can be copied into an app repository.

Local checks pass. Isolated Linux integration and native database reconnection passed before packaging.
The [test record](../../examples/app-frameworks/go-net-http-pgx/test-record.md) gives versions and limits.
Stack admission, real R2 fixture creation, and public HTTPS sign-in and record writes passed.
Browser checks, complete uploads/downloads, PgBouncer, and Stack recovery still need separate proof.

## Start with the app copy

Copy all of `examples/app-frameworks/go-net-http-pgx/` into your app repository.
Keep `migrations/` inside the app copy because the compiler embeds the SQL files.
Use Go 1.27.4 and the committed dependency lockfiles.
From the copied directory, run:

```sh
go test ./...
go vet ./...
go build -o "$TMPDIR/customer_portal_go" .
```

The tests need no services. Set `TMPDIR` to a writable temporary directory if your shell leaves `TMPDIR` unset.
Run the [service checks](../../examples/app-frameworks/go-net-http-pgx/testing.md) on an isolated integration host.
The service checks create synthetic accounts and files, so use dedicated test resources.

## Supply settings

Use protected process environment settings or the Stack's vault.
Do not put credentials in source files, shell history, command arguments, or reports.
The app does not create buckets or credentials.

| Variable | Required value |
| --- | --- |
| `DATABASE_URL` | Stack-generated multi-host writer URL, including `target_session_attrs=read-write&connect_timeout=3` |
| `APP_ORIGIN` | Exact HTTPS origin without a trailing slash, such as `https://go-portal.example.com` |
| `PORT` | Web port selected by the Stack from the app's two ports |
| `WEB_CONCURRENCY` | Positive CPU count supplied by the Stack to web containers |
| `R2_ENDPOINT` | S3 endpoint, such as `https://example-account-id.r2.cloudflarestorage.com` |
| `R2_BUCKET` | Existing private bucket for the selected app and environment |
| `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | Credentials restricted to the selected bucket |
| `APP_ENV` | `development` or `staging` when running the synthetic seed |
| `FIXTURE_PASSWORD` | Runtime-only seed/check password, 12 to 72 bytes |

Run `customer_portal migrate` before starting web and job processes.
Use `customer_portal web` for HTTP and `customer_portal jobs` for reports.
Only web and seed commands require object-storage settings.
Run `customer_portal seed-test-data` with a development or staging database and bucket.
Set `APP_ENV=staging` and supply `FIXTURE_PASSWORD` through the protected environment.
Run the seed twice before workers start. Expect two accounts, records, documents, and pending reports.
The [fixture table](../../examples/app-frameworks/go-net-http-pgx/README.md#synthetic-staging-fixture) gives exact seed values.
The example's `testing.md` supplies ownership and hash checks.

Open the configured HTTPS origin. Register, edit a record, upload a document,
download the document, request a report, and log out.
Browser cookies require HTTPS. Every POST must send the exact `APP_ORIGIN` in the `Origin` header.
Uploads are limited to 5 MiB to bound memory per request.
The example omits email verification, password recovery, and account administration.
All responses use `Cache-Control: no-store`. No separate static assets are needed.
The image includes an empty `/app/assets` directory for the Stack's asset-copy step.

## Database reconnection

pgx accepts the Stack's multi-host URL unchanged. The `databaseConfig` function in
`main.go` enables TCP keepalive using the host's timing. `pgxpool` replaces broken
connections. New connections try the listed hosts and require a writable server.
Go uses `WEB_CONCURRENCY` for `GOMAXPROCS`, with concurrent requests in goroutines.

The portal reads from the primary because sessions and immediate CRUD results must see recent writes.
`DATABASE_READ_URL` is used only by the explicit replica report command below. HTTP reads stay on the primary. pgx supports preferred-standby selection, but the portal does not route HTTP reads to replicas.
The app requires no Node.js helper or additional primary-selection service.
The [driver guide](../../skills/monkeymaxxing-stack/files_for_your_app/database_driver_finds_the_primary.md#go) explains the native settings.

`/healthz` requires a working database and migration 0002 within two seconds.
Ordinary database requests have a twelve-second deadline. Each process defaults to at most eight database connections.
Account for web and job pools across all app servers when reviewing database connection capacity.
A failed mutation returns an error without replaying the mutation.
An error can mean the write committed but the reply was lost.
Reconcile the stored result before resubmitting an uncertain mutation.

The report worker polls Postgres and locks a job with `FOR UPDATE SKIP LOCKED`.
Report output and completion commit in the job's transaction.
An interrupted transaction leaves the unfinished report available to another worker.
No `LISTEN` or session-level advisory lock is needed, so `jobs_connect_directly_to_postgres` is `false`.
The completed live PgBouncer check is recorded below.

## Prepare an additional app on a running Stack

The following steps prepare a deployment. Review the changed systems files before running server commands.
Keep existing app entries, image tags, host names, secrets, and production data.
Check the running system's Stack version before applying the settings.
Use `customer_portal_go` for the app key and database name in this example.
Choose unused ports in 8001 to 8099. The example uses `[8003, 8004]`.

### Build and publish the image

On your Linux build host, run from the copied app directory at a reviewed app commit:

```sh
release=$(git rev-parse HEAD)
podman build --platform linux/amd64 --build-arg RELEASE="$release" \
  --tag "ghcr.io/example/customer_portal_go:$release" .
podman push "ghcr.io/example/customer_portal_go:$release"
podman manifest inspect "ghcr.io/example/customer_portal_go:$release"
```

Replace `ghcr.io/example/customer_portal_go` with your registry path before running the commands.
Use your server architecture if your servers differ from Linux amd64.
Record the app commit, image digest, compiler versions, and dependency lockfile hashes.
The Go recipe builds a static binary and uses distroless static Debian 13.
The runtime is non-root. The default command is `customer_portal web`, without an entrypoint.
The same image runs migrations, jobs, and staging seeds by overriding the command.

### Edit the systems repository

In `mmx_project_settings.yml`, merge this entry under the existing `vars.apps`:

```yaml
vars:
  apps:
    customer_portal_go:
      image: ghcr.io/example/customer_portal_go
      web_ports: [8003, 8004]
      health_url_path: /healthz
      migration_command: customer_portal migrate
      jobs_command: customer_portal jobs
      jobs_connect_directly_to_postgres: false
      asset_directory: /app/assets
      database_name: customer_portal_go
      env:
        R2_ENDPOINT: https://example-account-id.r2.cloudflarestorage.com
      secrets_from_vault: [APP_ORIGIN, R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY]
      production_uploads_r2_bucket: example-customer-portal-go-production
      restore_drill_check_queries:
        - name: the_migrations_came_back
          sql: select count(*) = 2 from schema_migrations where version in ('0001_portal.sql', '0002_record_descriptions.sql')
```

Create separate production and staging buckets using the Stack's
[account setup in chapter 4 (set up your accounts and lock your desk)](../../skills/monkeymaxxing-stack/systems_repository_template/initial_setup/04_set_up_your_accounts_and_lock_your_desk.md).
The production `R2_BUCKET` must match `production_uploads_r2_bucket`.
Extend the existing uploads-backup read credential to include the production bucket.
If uploads backups were disabled, configure the uploads-backup bucket and credentials first.
Set `vars.backups.uploads_backup_runs_on: [util_server]` once uploads backups are ready.
The [uploads recovery procedure](../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/restore_an_uploaded_file.md)
explains how object versions are restored separately from Postgres.

Add these vault keys through `mmx secrets`, following the systems repository's secret procedure:

| Production key | Staging key | Content |
| --- | --- | --- |
| `customer_portal_go_database_password` | `staging_customer_portal_go_database_password` | Separate generated database passwords |
| `customer_portal_go_APP_ORIGIN` | `staging_customer_portal_go_APP_ORIGIN` | `https://go-portal.example.com` / `https://staging.go-portal.example.com` |
| `customer_portal_go_R2_BUCKET` | `staging_customer_portal_go_R2_BUCKET` | Separate private bucket names |
| `customer_portal_go_R2_ACCESS_KEY_ID` | `staging_customer_portal_go_R2_ACCESS_KEY_ID` | Bucket-scoped access key IDs |
| `customer_portal_go_R2_SECRET_ACCESS_KEY` | `staging_customer_portal_go_R2_SECRET_ACCESS_KEY` | Bucket-scoped secret keys |

In `playbooks/every_server.yml`, extend production's `app_server` and `jobs_server` role inputs under `app_secrets`:

```yaml
customer_portal_go_database_password: "{{ .secrets.customer_portal_go_database_password }}"
customer_portal_go_APP_ORIGIN: "{{ .secrets.customer_portal_go_APP_ORIGIN }}"
customer_portal_go_R2_BUCKET: "{{ .secrets.customer_portal_go_R2_BUCKET }}"
customer_portal_go_R2_ACCESS_KEY_ID: "{{ .secrets.customer_portal_go_R2_ACCESS_KEY_ID }}"
customer_portal_go_R2_SECRET_ACCESS_KEY: "{{ .secrets.customer_portal_go_R2_SECRET_ACCESS_KEY }}"
```

For `app_server_on_staging01`, keep the left-hand names and use `staging_` vault keys on the right.
For example:

```yaml
customer_portal_go_database_password: "{{ .secrets.staging_customer_portal_go_database_password }}"
customer_portal_go_APP_ORIGIN: "{{ .secrets.staging_customer_portal_go_APP_ORIGIN }}"
customer_portal_go_R2_BUCKET: "{{ .secrets.staging_customer_portal_go_R2_BUCKET }}"
customer_portal_go_R2_ACCESS_KEY_ID: "{{ .secrets.staging_customer_portal_go_R2_ACCESS_KEY_ID }}"
customer_portal_go_R2_SECRET_ACCESS_KEY: "{{ .secrets.staging_customer_portal_go_R2_SECRET_ACCESS_KEY }}"
```

Also extend each `database_server` role's `database_passwords` mapping in `playbooks/every_server.yml`:

```yaml
# Production mapping:
customer_portal_go: "{{ .secrets.customer_portal_go_database_password }}"
# Staging mapping, in its separate role call:
customer_portal_go: "{{ .secrets.staging_customer_portal_go_database_password }}"
```

In `playbooks/end_connections_that_use_an_old_database_password.yml`, add the app to production and staging `database_passwords` inputs and outputs.
Use the production vault key for production and the `staging_` key for staging.
The rotation procedure needs the password mappings to validate the app's password later.
Do not edit role implementations or database URLs.

In `inventories/servers.yml`, merge the following entries under the existing `vars` maps:

```yaml
vars:
  deployed_image_tags:
    production:
      customer_portal_go: REPLACE_WITH_FULL_REVIEWED_APP_COMMIT
    staging:
      customer_portal_go: REPLACE_WITH_FULL_REVIEWED_APP_COMMIT
  public_host_names:
    production:
      customer_portal_go: go-portal.example.com
    staging:
      customer_portal_go: staging.go-portal.example.com
```

Use the published app commit as each image tag. Keep unrelated apps' tags unchanged.
The app image must be readable by the Stack's existing registry credential.

### Prepare Cloudflare routing

The Stack uses locally managed tunnels. Inventory host names render the tunnel routes during `every_server`.
No new tunnel or tunnel token is needed for an additional app.
Keep `roles/tunnel_connector_and_caddy/files/cloudflared_config.yml` unchanged.
The rendered route sends each host to `http://localhost:80`, where Caddy selects the app by host name.
Preserve the requested Host header. Do not send requests directly to a container port.

Check that `go-portal.example.com` has no conflicting DNS record before adding DNS.
Create a proxied CNAME for `go-portal.example.com` pointing to the existing production tunnel's `TUNNEL_ID.cfargotunnel.com`.
With staging, create the corresponding CNAME for `staging.go-portal.example.com` using staging's tunnel ID.
Create a self-hosted Access application for the staging host, using the existing company policy and staging service token.
Verify the existing cache rule covers the new hosts and follows the app's `Cache-Control` headers.
The [tunnel and Access instructions in chapter 5 (put your site behind Cloudflare and lock your private pages)](../../skills/monkeymaxxing-stack/systems_repository_template/initial_setup/05_put_your_site_behind_cloudflare_and_lock_your_private_pages.md)
give the existing routing and cache policy.

### Review the future server run

Run `mmx validate` in the edited systems repository.
Review and commit the systems changes, including the encrypted vault.
Push through the team's normal workflow.
The app and systems repository commits are separate revisions.
A push changes no server.

Adding `vars.apps` makes the app available in every configured environment.
The initial configuration run can start the new production app as well as staging.
Obtain approval for that scope before running `every_server`.
From the systems repository, the later deployment agent runs:

```sh
./server_management_scripts/run_mmx_on_util01 run every_server
```

Read MMX's result before continuing. First-start configuration runs migrations before starting the new app.
Verify `/healthz` and the release on every app server.
Run the first restore drill with only `the_migrations_came_back` for this app.
After data exists, add the data queries in the example's `testing.md`.
For later releases, follow
[Deploy and roll back](../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/deploy_and_roll_back_an_app_release.md).
That procedure deploys staging, verifies staging, then releases to production, after the person's approval when `production_releases_wait_for_a_persons_approval` is true.
Rollback selects the previous image tag and leaves additive migrations applied.

## Verify the running app

Follow the example's [service checks](../../examples/app-frameworks/go-net-http-pgx/testing.md).
Run `check_portal.py` from a host that can reach two private web instances.
Systems desks reach production SSH only, so use an assigned integration host with application-network access.
Supply `FIXTURE_PASSWORD` through the environment before running:

```sh
python3 check_portal.py \
  --server-a http://app001:8003 \
  --server-b http://app002:8003 \
  --origin https://go-portal.example.com
```

Use each app server's actual live port. A later deploy can switch to the second configured port.
The HTTP check prints only success or a failed assertion. The check leaves synthetic data for restore inspection.
Repeat the account, record, file, report, and logout flow in a browser through public HTTPS.
Confirm sessions work across app servers and logout revokes the old cookie on another app server.

Keep web and worker processes running during `switch_database_primary` to the replica and back.
Record process identities, unique write titles, HTTP outcomes, and time until a fresh write succeeds.
Check sessions, ownership, and queued reports after each switch.
Never treat the Node switchover helper as proof for a Go or Rust app.
After enabling transaction-mode PgBouncer, repeat the HTTP, job, and switchover checks.
Record R2 authorization and exact downloaded bytes separately from S3Mock results.
Prove database backup recovery and uploaded-file recovery separately before claiming Stack recovery.

## Set the database connection budget

`DATABASE_POOL_MAX_CONNECTIONS` sets the maximum pool size per process. The example default is 8.
Set `DATABASE_POOL_MAX_CONNECTIONS=2` for web and migrations.
Set `jobs_environment: {DATABASE_POOL_MAX_CONNECTIONS: "1"}` in the Stack app entry for the job container.
For standalone runs, pass the value through the process environment. Distroless images have no `env` executable.
Set `WEB_CONCURRENCY=1` to keep one web worker. Each additional process creates another pool.

On four servers, the default 8-connection web and jobs pools allow 64 connections total.
A rolling release can raise that allowance to 96 connections because old and new web processes overlap.
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
replica_report
```

The driver accepts the Stack multi-host URL and `target_session_attrs=prefer-standby` directly.
The command prints `connection_purpose`, `database_server_address`, `is_replica`, and `record_count`.
The `read` connection uses `DATABASE_READ_URL`. The `write` connection uses `DATABASE_URL`.
The write connection reports the primary's role and count without changing data.
A stale aggregate can use the replica. Account sessions, job reservations, and reads after a write keep the primary.
The command is administrative because the aggregate includes all accounts.
Do not expose the command as an unauthenticated HTTP endpoint.

PgBouncer tracks named prepared statements with `max_prepared_statements = 200`. No prepared-statement change was needed for this example.

The shared two-server test on 2026-11-04 ran authenticated writes and reads every second, with queued jobs every five seconds.
Planned switches to the second server and back recovered without restarting the example's web or job container.
A silent database traffic drop promoted the standby in 29.64 seconds.
The initial silent-loss test recovered automatically for ten examples while the old primary stayed isolated.
Laravel required the connection timeout correction above.
The failover keeper safely rejoined the returning database as a replica without a manual Postgres restart.
The system procedure describes permanent replacement but lacks an explicit temporary-isolation return procedure.

## Real R2 upload checks

The production check on 2026-11-04 uploaded a 4,097-byte binary file and a 5 MiB binary file to real Cloudflare R2. Both authenticated downloads matched the original bytes and SHA-256.
The larger file used this example's 5 MiB limit; it did not test a 20 MiB upload. The limit bounds buffered request memory.

The tested client was aws-sdk-go-v2/service/s3. Keep the account-specific `R2_ENDPOINT`, region `auto`, and path-style addressing in `storage.go`.
Keep `RequestChecksumCalculationWhenRequired` and `ResponseChecksumValidationWhenRequired` in `storage.go`.
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

This example has no external JavaScript or CSS. A form rendered before the real release still saved a record after it. An independent request read the record back; normal form navigation reloaded the document.
The fixture has one application page. Its in-page actions do not cover lazy navigation to an additional client route. Test such routes separately when the incoming application has them.

The final production memory check on 2026-11-04 used one web worker and one jobs process on the same Debian 13 x86-64 server. It had 1,553 records when sampled. RSS means resident process memory; the numbers include master and worker processes. The warm-idle and observed-load peaks were:

| Process group | Warm idle RSS, MiB | Observed load peak RSS, MiB |
| --- | ---: | ---: |
| Web | 20.5 | 35.7 |
| Jobs | 19.1 | 19.1 |

The sampler read each process group every 100 ms for about 18 seconds. The short load used four read clients and one client that queued twelve reports and uploaded two files at the application limit. The database-disruption workload and test-browser polling were stopped first. All measured processes ran on the same app server, with transaction-mode PgBouncer and the explicit connection limits above.
For a conservative RAM planning model, reserve 113.1 MiB per app for two peak web generations and one jobs generation, including 25% growth room. With 1 GiB reserved for shared services and 10% of server RAM kept free, that gives 23 such apps in 4 GiB or 121 in 16 GiB. These are RAM-only projections at the measured worker/thread settings, not load-tested app counts. CPU, data growth, and PostgreSQL/PgBouncer capacity can require fewer apps. RSS can count shared pages twice, so this model is conservative. Do not substitute the Stack's CPU-count default for the explicit worker count used here.

For laptop test data, migrate against your local PostgreSQL database and local bucket, then run:

```sh
APP_ENV=development customer_portal seed-test-data
```

`customer_portal seed-test-data --accounts 200000` makes enough invented rows to show slow queries.
The total defaults to two accounts. Larger totals add accounts and owned records without extra documents or reports.
Production data stays on production servers. Add a missing data shape to the seed or a test.
