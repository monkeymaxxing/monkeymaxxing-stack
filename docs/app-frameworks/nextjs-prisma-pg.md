# Run a Next.js app on the Stack

This guide adds a private customer portal as another app on an existing Stack
system. The portal uses Next.js, PostgreSQL, and private S3-compatible uploads.
Your existing apps keep their databases, ports, buckets, and image tags.

The [copyable app](../../examples/app-frameworks/nextjs-prisma-pg/) includes
working files, tests, a Containerfile, and staging data.
The [test record](../../examples/app-frameworks/nextjs-prisma-pg/testing.md)
separates isolated checks from the remaining live Stack checks.

## What changes from Vercel hosting

The Stack runs persistent Node.js containers behind HTTPS. Route handlers use
`runtime = 'nodejs'`. Vercel functions, Edge bindings, cron configuration, Blob,
and managed database credentials do not move with exported frontend code.
List each source service before migrating an incoming app. Move data, permissions,
schedules, and jobs separately. Keep exactly one active queue during cutover.

The app uses `output: 'standalone'`. Next.js produces a small runtime directory.
The packaging script also copies static assets and CLI files that tracing omits.
The [Next.js output documentation](https://nextjs.org/docs/app/api-reference/config/next-config-js/output)
describes the standalone layout.

The Stack gives Node one multi-host database URL. Plain `pg` cannot read the
server list. The app copies the Stack's `pg_with_multiple_database_servers.mjs`
unchanged. Every pool uses that helper. Prisma is an alternative, but this
example deliberately uses `pg` for connection-level discovery.

`WEB_CONCURRENCY` forks Node workers through `scripts/web.mjs`. Each worker has
four database connections. Next.js drains requests before returning signal exit
codes 143 or 130. The launcher converts the requested clean shutdown into exit 0.

Private API responses bypass caches. Sessions live in PostgreSQL, so requests
can move between app servers. No session depends on process memory.
No private data appears in the static home page.

This example uses no Server Actions, ISR, image optimizer, or private RSC pages.
An incoming app using those features needs separate multi-instance checks.
Use one image across app servers. Follow the
[Next.js self-hosting guide](https://nextjs.org/docs/app/guides/self-hosting)
for shared caches, action encryption keys, and version skew when those features apply.
Never put secrets in `NEXT_PUBLIC_` variables. Public variables are embedded at build time.

## Prepare the app

Copy `examples/app-frameworks/nextjs-prisma-pg/` into your own app repository.
Use Node 24 on your Linux build or integration host.
Run commands from the copied app directory:

```sh
export npm_config_cache="${TMPDIR:-/tmp}/nextjs-portal-npm"
export NEXT_TELEMETRY_DISABLED=1
npm ci
npm test
npm run build
```

The build needs no database, bucket credentials, or app secrets.
Keep the lockfile. Build on the target architecture before publishing an image.

Supply settings through your protected process environment or secret store:

| Variable | Value or purpose |
| --- | --- |
| `DATABASE_URL` | `postgresql://nextjs_portal:PASSWORD@db01:5432,db02:5432/nextjs_portal?target_session_attrs=read-write&connect_timeout=3` |
| `APP_ORIGIN` | Exact HTTPS origin, such as `https://portal.example.com`, without a trailing slash |
| `PORT` | The assigned web port, such as `8005` |
| `WEB_CONCURRENCY` | Positive Node worker count, supplied by the Stack |
| `R2_ENDPOINT` | `https://ACCOUNT_ID.r2.cloudflarestorage.com` |
| `R2_BUCKET` | Existing private bucket assigned to this app and environment |
| `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | Credentials restricted to that bucket |
| `APP_ENV` | `development` or `staging` when running the synthetic seed |
| `FIXTURE_PASSWORD` | Runtime seed/check password of 12 to 72 bytes |

HTTP reads use the primary. The administrative replica report uses `DATABASE_READ_URL`.
Immediate session and record reads must see recent writes.
`BIND_ADDRESS` optionally selects the listener address. The default is `0.0.0.0`.
The Stack firewall keeps web ports private.

Run migrations before starting web and job processes:

```sh
npm run migrate
npm run web
```

In a separate terminal with the same environment, start the job worker:

```sh
npm run jobs
```

Open the HTTPS origin. Register an account, save a record, upload a file, and
request a report. Click **Refresh reports** to read completed output.
Cookies require HTTPS. A browser on plain HTTP cannot retain the login cookie.
The API tests send cookies explicitly to private HTTP ports.

## Prove the isolated services

Use a new, empty PostgreSQL 17 database and an existing private test bucket.
Use synthetic data only. Supply the settings above, including `APP_ENV=staging`.
Select two unused ports through `TEST_WEB_PORTS`, for example `8031,8032`.

```sh
export TEST_WEB_PORTS=8031,8032
node tests/services.mjs
```

The check builds on `npm run build`. The check starts two clustered web processes
and its own workers. The check retains synthetic data for restore inspection.
Never reuse an existing customer database. The check requires no existing accounts
table and intentionally exercises migration 0002 against the title-only schema.

To simulate database reconnection, set `TEST_DATABASE_RESTART_ARGV` before running
the check. The value is a JSON command array. For an assigned Debian test guest:

```sh
export TEST_DATABASE_RESTART_ARGV='["pg_ctlcluster","17","main","restart"]'
node tests/services.mjs
```

Run that command only where you own the database service and every dependent app.
The restart command also requires permission to manage PostgreSQL, such as root
inside your assigned test guest. Do not grant the app database role server privileges.
A database restart is not a primary promotion. The live switch remains a separate check.
The script prints named passes and `SERVICE_RESULTS` without passwords or cookies.
An assertion failure exits nonzero and stops the script's child processes.

## Build the image

The image runs as the unprivileged `node` user. The image uses a pinned Node 24
base and includes the standalone output. Supply your reviewed source commit:

```sh
podman build --build-arg RELEASE="$(git rev-parse HEAD)" \
  --tag ghcr.io/example/nextjs-portal:"$(git rev-parse HEAD)" .
```

The image's default command is `node scripts/web.mjs`.
Migration, job, and seed commands are `node scripts/manage.mjs migrate`,
`node scripts/manage.mjs jobs`, and `node scripts/manage.mjs seed-test-data`.
The image has no entrypoint that hides command overrides.

Publish the reviewed image to your registry. Verify the registry digest before
changing a running system. A local build changes no server.

## Prepare another app on a running Stack

The coding agent performs this preparation in your systems repository.
First inventory existing apps, used ports, databases, bucket ownership, and tags.
Pick an unused app name, two ports, a database, and distinct staging/production buckets.
The example uses `nextjs_portal` and ports 8005/8006. Replace colliding values.

Add this entry under the existing `vars.apps` mapping in `mmx_project_settings.yml`:

```yaml
nextjs_portal:
  image: ghcr.io/example/nextjs-portal
  web_ports: [8005, 8006]
  health_url_path: /healthz
  migration_command: node scripts/manage.mjs migrate
  jobs_command: node scripts/manage.mjs jobs
  jobs_connect_directly_to_postgres: false
  asset_directory: /app/.next/static
  database_name: nextjs_portal
  env:
    R2_ENDPOINT: https://ACCOUNT_ID.r2.cloudflarestorage.com
  secrets_from_vault:
    - APP_ORIGIN
    - R2_BUCKET
    - R2_ACCESS_KEY_ID
    - R2_SECRET_ACCESS_KEY
  production_uploads_r2_bucket: example-nextjs-portal-production
  restore_drill_check_queries:
    - name: the_migrations_came_back
      sql: select count(*) = 2 from schema_migrations where version in ('0001_portal.sql', '0002_record_descriptions.sql')
```

`asset_directory` must be `/app/.next/static`. The Stack mounts the current and
previous release's assets at that path. An old browser page can still fetch its
JavaScript after a release switch. Do not point the asset setting at an empty directory.

Provision private buckets and bucket-scoped keys through your existing account procedure.
Add production vault entries named `nextjs_portal_database_password`,
`nextjs_portal_APP_ORIGIN`, `nextjs_portal_R2_BUCKET`,
`nextjs_portal_R2_ACCESS_KEY_ID`, and `nextjs_portal_R2_SECRET_ACCESS_KEY`.
Add separate staging entries with the prefix `staging_nextjs_portal_`.
Production's bucket value must match `production_uploads_r2_bucket`.

In `playbooks/every_server.yml`, preserve existing entries. Add the database
password to production's database role input:

```yaml
database_passwords:
  nextjs_portal: "{{ .secrets.nextjs_portal_database_password }}"
```

Add the staging equivalent to staging's database role input:

```yaml
database_passwords:
  nextjs_portal: "{{ .secrets.staging_nextjs_portal_database_password }}"
```

Extend `app_secrets` for production's `app_server` and `jobs_server` role calls:

```yaml
nextjs_portal_database_password: "{{ .secrets.nextjs_portal_database_password }}"
nextjs_portal_APP_ORIGIN: "{{ .secrets.nextjs_portal_APP_ORIGIN }}"
nextjs_portal_R2_BUCKET: "{{ .secrets.nextjs_portal_R2_BUCKET }}"
nextjs_portal_R2_ACCESS_KEY_ID: "{{ .secrets.nextjs_portal_R2_ACCESS_KEY_ID }}"
nextjs_portal_R2_SECRET_ACCESS_KEY: "{{ .secrets.nextjs_portal_R2_SECRET_ACCESS_KEY }}"
```

For staging's `app_server`, retain the left names and use these staging values:

```yaml
nextjs_portal_database_password: "{{ .secrets.staging_nextjs_portal_database_password }}"
nextjs_portal_APP_ORIGIN: "{{ .secrets.staging_nextjs_portal_APP_ORIGIN }}"
nextjs_portal_R2_BUCKET: "{{ .secrets.staging_nextjs_portal_R2_BUCKET }}"
nextjs_portal_R2_ACCESS_KEY_ID: "{{ .secrets.staging_nextjs_portal_R2_ACCESS_KEY_ID }}"
nextjs_portal_R2_SECRET_ACCESS_KEY: "{{ .secrets.staging_nextjs_portal_R2_SECRET_ACCESS_KEY }}"
```

Extend `deployed_image_tags.staging`, `deployed_image_tags.production`,
`public_host_names.staging`, and `public_host_names.production` in `inventories/servers.yml`.
Each mapping needs a `nextjs_portal` entry. Use the reviewed image's full commit tag
and your distinct public host names. Follow your initial setup's account steps
to add tunnel routing and Access protection for staging. Preserve existing app routes.

Run `mmx validate` in the systems repository. Review the resulting changes and
the app's checklist entries with the person before applying configuration.
Use the existing `every_server` procedure to create the additional database,
settings, and containers. Read MMX's result before continuing.

Follow `operating_procedures/deploy_and_roll_back_an_app_release.md` for staging,
the production release and its approval setting, and rollback. The ordinary deploy command is:

```sh
./server_management_scripts/run_mmx_on_util01 run deploy --var environment_name=staging
```

That command deploys the selected environment's configured releases. Check every
app's requested tag first. A shared environment must not contain another app's
unapproved pending tag.

## Seed and verify staging

On the staging server only, run the seed in the tested image with staging's
settings and secrets files. Supply `FIXTURE_PASSWORD` through the protected
process environment. Replace `REVIEWED_COMMIT` with the deployed tag:

```sh
podman run --rm --network host \
  --env-file /etc/nextjs_portal/nextjs_portal_settings.env \
  --env-file /etc/nextjs_portal/nextjs_portal.env \
  --env APP_ENV=staging --env FIXTURE_PASSWORD \
  ghcr.io/example/nextjs-portal:REVIEWED_COMMIT \
  node scripts/manage.mjs seed-test-data
```

Run the seed twice. Expect two fixture accounts, records, documents, and jobs.
Workers can complete fixture jobs before inspection. Expect `record_count=1`
plus LF before adding further records. Never run staging seeds against production.

Use the private app server addresses to verify sessions across two servers:

```sh
python3 tests/check_portal.py \
  --server-a http://app001:8005 --server-b http://app002:8005 \
  --origin https://portal.example.com
```

Run from a machine that reaches those private addresses. Supply `FIXTURE_PASSWORD`
through the environment. The check prints no cookies or passwords.
Repeat login, record editing, upload, download, report, and logout in the public
HTTPS browser. Confirm keyboard navigation and meaningful field labels.

## Switch, restore, and roll back

Keep web and job processes running through `switch_database_primary`.
Follow `operating_procedures/test_a_nodejs_app_during_a_database_switchover.md`
for the driver check. Also exercise this app's HTTP session, unique writes,
file downloads, and jobs during switches in both directions.
Record failed requests and time to the next successful write. Never blindly
resubmit a failed mutation. Inspect saved data to resolve an uncertain result.

Repeat HTTP, job, and switch checks through transaction-mode PgBouncer when enabled.
The job queue holds row locks inside one transaction and uses no session lock.
The migration command connects directly through the Stack's existing migration helper.

The first restore drill checks only `the_migrations_came_back`, before app data exists.
After seeding, add fixture checks for accounts, ownership, documents, and job output.
Record row values, session hashes, pending jobs, completed output, and object hashes
before backup. Compare the restored database against that saved manifest.
Restore object bytes to an isolated bucket, then download and compare every fixture.
A Postgres restore cannot recover an S3 object.

An image rollback keeps the additive migrations. The title-only SQL shape must
still work after migration 0002. Use the Stack's normal rollback procedure and
verify every app server's actual release, rather than relying on inventory tags.

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

The old page saved a record after the real release without reloading, and an independent request read it back. Old JS/CSS URLs were also checked directly at the new origin for matching bytes and content types. Those origin checks passed.
The fixture has one application page. Its in-page actions do not cover lazy navigation to an additional client route. Test such routes separately when the incoming application has them.

The final production memory check on 2026-11-04 used one web worker and one jobs process on the same Debian 13 x86-64 server. It had 1,536 records when sampled. RSS means resident process memory; the numbers include master and worker processes. The warm-idle and observed-load peaks were:

| Process group | Warm idle RSS, MiB | Observed load peak RSS, MiB |
| --- | ---: | ---: |
| Web | 159.5 | 256.3 |
| Jobs | 85.0 | 85.1 |

The sampler read each process group every 100 ms for about 18 seconds. The short load used four read clients and one client that queued twelve reports and uploaded two files at the application limit. The database-disruption workload and test-browser polling were stopped first. All measured processes ran on the same app server, with transaction-mode PgBouncer and the explicit connection limits above.
For a conservative RAM planning model, reserve 747.0 MiB per app for two peak web generations and one jobs generation, including 25% growth room. With 1 GiB reserved for shared services and 10% of server RAM kept free, that gives 3 such apps in 4 GiB or 18 in 16 GiB. These are RAM-only projections at the measured worker/thread settings, not load-tested app counts. CPU, data growth, and PostgreSQL/PgBouncer capacity can require fewer apps. RSS can count shared pages twice, so this model is conservative. Do not substitute the Stack's CPU-count default for the explicit worker count used here.

For laptop test data, migrate against your local PostgreSQL database and local bucket, then run:

```sh
APP_ENV=development npm run seed-test-data
```

`npm run seed-test-data -- --accounts 200000` makes enough invented rows to show slow queries.
The total defaults to two accounts. Larger totals add accounts and owned records without extra documents or reports.
Production data stays on production servers. Add a missing data shape to the seed or a test.
