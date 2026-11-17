# Move from Railway to your own system

## Variances and guidance needs

The Railway portal can run independently after exporting PostgreSQL and private bucket objects.
Phase 1 proves export and a standalone rehearsal. The live cutover also passed account, file, job, and schedule checks.
The [test record](../../examples/app-platform-migrations/from-railway/test-record.md) records the measured results and limits.
Full Stack recovery remains a separate check.

| Railway behavior | Destination behavior and guidance |
| --- | --- |
| Source PostgreSQL 18.6 | The Stack uses PostgreSQL 17. Rehearse the actual logical restore before accepting compatibility. |
| PostgreSQL 18 dump session settings | The restore removes exactly `SET transaction_timeout = 0;` for a source-18 to destination-17 restore. Every remaining SQL error stops restoration. |
| Railway private database hostname | Use the Stack's multi-host `DATABASE_URL` and the copied Node primary-discovery helper. |
| Bucket uses virtual-host addressing | Keep `S3_FORCE_PATH_STYLE=false` for Railway. Loopback storage uses `true`. Verify the selected destination's addressing independently. |
| Node sends `statement_timeout` at login | PgBouncer refuses this startup parameter. Keep a client query timeout and use `SET LOCAL statement_timeout` inside transactions. |
| First Stack start runs migrations | Create the empty destination database, import the final export, then start the app. The restore tool refuses a migrated database. |
| Separate worker and Railway cron services | `npm run jobs` handles reports and the five-minute UTC archive schedule inside the Stack job container. |
| Source worker pause controls reports | Destination pause controls reports and scheduled work, so imported work stays idle until explicitly resumed. |
| Application-owned bcrypt authentication | Restore `users.password_hash` unchanged. No password reset or external identity service is required. |
| Host-bound login cookies | Returning users log in at the new hostname. PostgreSQL sessions remain shared across destination web servers. |
| Trial account | Export while access remains. This guide requires no upgrade or paid source service. Check available credits before starting work. |

The example is a hand-written Express portal. Adapt the checks for an application with a different schema or authentication provider.
Do not claim a full exit while any destination connection still uses Railway database, bucket, worker, or cron services.

## 1. Collect the source facts

The coding agent inventories the running application before copying data.
Record the source Git revision, dependency lockfile, database version, bucket endpoint, addressing mode, and all service variable names.
Record cron expressions, timezone, command, and the destination for every external integration.
Record pending and completed jobs, including completed report output.

Obtain repository access, PostgreSQL credentials, the public TCP proxy address, and bucket credentials separately.
Railway private database hostnames are not reachable from the laptop.
Use the existing authenticated Railway console or CLI to read the variables and proxy settings.
Read variable values only into protected files. Print variable names without values.

Clone your source repository and record the exact revision:

```sh
git clone YOUR_SOURCE_REPOSITORY source-app
git -C source-app rev-parse HEAD
git -C source-app archive --output="$HOME/railway-export-code.tar" HEAD
chmod 600 "$HOME/railway-export-code.tar"
```

Replace `YOUR_SOURCE_REPOSITORY` with your repository URL.
Keep database exports and credentials outside the application repository.
The source repository supplies code, migration SQL, Dockerfile, and `package-lock.json`.
Code export does not include database rows or file bytes.

For a final production export, first pause source writes and disable source report and schedule execution through an approved maintenance plan.
During read-only rehearsal, reuse an already-paused source worker and leave source configuration unchanged.
The export command checks the application's worker pause but cannot disable Railway's separate cron service.
The exported PostgreSQL snapshot preserves receipts through the recorded export time.

## 2. Export PostgreSQL and objects

Use Node.js 22 or newer and PostgreSQL 18 `pg_dump` for the source-18 database.
PostgreSQL does not guarantee loading a newer-major dump into an older server.
The [PostgreSQL pg_dump documentation](https://www.postgresql.org/docs/18/app-pgdump.html) describes the version boundary.
The narrow compatibility change applies only to the tested portal schema.

From the copied `from-railway/` directory, install dependencies:

```sh
export npm_config_cache="${TMPDIR:-/tmp}/railway-npm-cache"
npm ci --prefix app --omit=dev --no-audit --no-fund
umask 077
```

In a protected directory outside Git, create the three JSON inputs below.
Fill credential values from existing authorized source exports without printing the values.

`source-database.json` contains `host`, numeric `port`, `user`, `password`, `database`, and `ssl`.
`host` and `port` identify the public TCP proxy.
For a verified public certificate, use `"ssl":{"rejectUnauthorized":true}`.
The tested Railway image has a self-signed certificate, so the rehearsal used `false` for that source connection only.
TLS still encrypts the connection, but `false` does not authenticate the database server.
Use a trusted certificate when available.

`source-storage.json` contains `endpoint`, `region`, `bucketName`, `accessKeyId`, `secretAccessKey`, and `"forcePathStyle":false`.
Use the bucket's physical name and native S3 credentials.
The [Railway bucket documentation](https://docs.railway.com/storage-buckets) describes the native bucket interface.

`variable-names.json` maps each service name to an array of variable names.
Include the database, web, worker, and cron services. Do not include secret values.
Record the source schedule as `*/5 * * * *`, UTC, `npm run cron` for the example portal.
For a different source schedule, update the export manifest's schedule and the destination implementation before rehearsal.

Set the input locations and choose a new export directory:

```sh
export SOURCE_DATABASE_CONFIG_FILE="$HOME/railway-private/source-database.json"
export SOURCE_STORAGE_CONFIG_FILE="$HOME/railway-private/source-storage.json"
export SOURCE_VARIABLE_NAMES_FILE="$HOME/railway-private/variable-names.json"
export EXPORT_DIR="$HOME/railway-private/export-001"
export PG_DUMP=/usr/lib/postgresql/18/bin/pg_dump
node data-transfer.mjs export
```

Use your installed PostgreSQL 18 binary path for `PG_DUMP`.
Expected output starts with `EXPORT_PASS`.
The command refuses an existing export directory to preserve previous exports.
The command uses a read-only PostgreSQL transaction and passes the transaction's snapshot to `pg_dump`.
The manifest records every table's row count and SHA-256, migration checksums, job states, and variable names.
`snapshot.json` contains exact rows, including user password hashes and session token hashes. Treat `snapshot.json` as private account data.
The object export follows every listing page and retains every object, including objects without database references.
Document metadata must match exported byte lengths and SHA-256 hashes.
Freeze uploads and repeat into a new export directory if concurrent file changes cause a mismatch.

Preserve `postgres.dump`, `snapshot.json`, `manifest.json`, and `objects/` together.
Copy the export directory into the rehearsal machine through an authenticated encrypted connection.
Store the existing synthetic fixture password in a separate mode-600 file for the test.
Do not put passwords in command arguments, source files, reports, or Git.

## 3. Prepare a disposable destination

The following commands run as root inside an isolated Debian 13 Linux test machine.
PostgreSQL 17 must already be running on loopback port 5432.
Install Python 3, Node.js 22, npm, Podman, and PostgreSQL client tools before continuing.
Use `pg_restore` 18 if your installed client cannot read the archive.
The tested PostgreSQL 17 client can read the example source archive.

Use a local S3 test service for the standalone rehearsal:

```sh
podman run -d --name railway-rehearsal-storage --network host \
  --env SERVER_ADDRESS=127.0.0.1 \
  docker.io/adobe/s3mock@sha256:ab01a6946750f451ca215a47e91030695b260e4003b8a5a6201d25029b8fca92
```

Wait until `curl --fail http://127.0.0.1:9090/` succeeds.
The test service proves S3 request and byte compatibility. The test service does not prove production bucket authorization.
Use a new PostgreSQL database and a new bucket for each rehearsal.

```sh
export REHEARSAL_NAME=railway_first
export REHEARSAL_SETTINGS_DIR=/root/railway-first-settings
python3 tests/prepare-rehearsal.py
. "$REHEARSAL_SETTINGS_DIR/destination.env"
node tests/create-rehearsal-bucket.mjs
```

The helper creates a new database role and database, then writes destination credentials into mode-600 `destination.env`.
The database URL deliberately tries an unreachable loopback address before the real primary.
Successful restoration therefore also checks multi-host fallback.
The helper refuses existing settings. The helper never removes an existing database or role.

## 4. Restore and run customer checks

Keep destination jobs stopped until exact restored rows and object bytes pass comparison.
Restore only a trusted source archive because restore SQL runs inside the destination database.
The [pg_restore documentation](https://www.postgresql.org/docs/18/app-pgrestore.html) explains archive execution.

```sh
export EXPORT_DIR=/root/railway-private/export-001
export FIXTURE_PASSWORD_FILE=/root/railway-private/fixture-password
node data-transfer.mjs restore
npm run check --prefix app
export ALLOW_DISPOSABLE_REHEARSAL=true
node tests/rehearsal.mjs
```

Expected output includes `RESTORE_PASS` and `REHEARSAL_PASS`.
The restore requires an empty database and refuses overwriting destination object keys.
Every restored table must match the source snapshot exactly before any login creates a new session.
The source-18 to destination-17 path removes only the unsupported `transaction_timeout` session setting.
Restoration uses one SQL transaction and stops on every remaining SQL error.
If object import fails after database restoration, preserve the failed export and use another empty destination for the next rehearsal.

The rehearsal logs in Barbara and Michael using their existing passwords and checks preserved UUIDs.
The rehearsal also checks sessions across two web servers, owner restrictions, CRUD, file bytes, logout, and new registration.
Queue checks resume only the isolated copy, interrupt a locked transaction, and run concurrent workers.
Schedule checks run two schedulers for one UTC occurrence and verify a single committed archive operation.
The actual jobs entry point completes an HTTP-enqueued report and exits cleanly on SIGTERM.
Results are saved in `restore-result.json` and `rehearsal-result.json` inside `EXPORT_DIR`.
The rehearsal changes the restored copy. Do not use the tested copy as a final production import.

For an independent replay, copy the original export into a separate private directory.
Choose a different `REHEARSAL_NAME`, settings directory, and `REHEARSAL_FIRST_PORT`.
Repeat sections 3 and 4 without help from the implementation session.

## 5. Prepare the Stack release

Build the application image from `app/Dockerfile` with `app/` as the build context.
Keep the original migration SQL files byte-for-byte because the restored ledger records migration checksums.
Run `npm run migrate` during deployment before starting web and jobs containers.
The web and job entry points do not apply migrations themselves.

Add the following app entry under `vars.apps` in your systems repository's `mmx_project_settings.yml`.
Replace the example image, database name, R2 endpoint, and bucket with your destination values.
Choose two available web ports from the Stack's app-port range, TCP 8001 through 8099.
Start with one web process per app server and count each process's database pool.
Include both release generations, job processes, and direct migration connections in the peak connection budget.
Follow the Stack's admission rule and add PgBouncer before the calculated total exceeds 70 connections.
Size the combined PgBouncer backend pools for every admitted database. The default pool size does not fit an unlimited number of apps.

```yaml
vars:
  apps:
    railway_portal:
      image: registry.example.com/team/railway-portal
      web_ports: [8001, 8002]
      health_url_path: /healthz
      migration_command: npm run migrate
      jobs_command: npm run jobs
      jobs_connect_directly_to_postgres: false
      asset_directory: /app/web
      database_name: railway_portal
      env:
        NODE_ENV: production
        WEB_CONCURRENCY: "1"
        S3_ENDPOINT: https://example-account.r2.cloudflarestorage.com
        S3_REGION: auto
        S3_BUCKET: example-portal-uploads
        S3_FORCE_PATH_STYLE: "false"
      secrets_from_vault:
        S3_ACCESS_KEY_ID:
          where_the_value_comes_from: generated_by_the_setup
        S3_SECRET_ACCESS_KEY:
          where_the_value_comes_from: generated_by_the_setup
      production_uploads_r2_bucket: example-portal-uploads
      production_uploads_r2_key_variables:
        access_key_id: S3_ACCESS_KEY_ID
        secret_access_key: S3_SECRET_ACCESS_KEY
      restore_drill_check_queries:
        - name: the_migrations_came_back
          sql: select count(*) = 2 from schema_migrations
```

The Stack supplies `DATABASE_URL`, `DATABASE_READ_URL`, `PORT`, and `WEB_CONCURRENCY`.
The portal reads through the primary pool. `DATABASE_READ_URL` is available but unused.
The uploads stay in R2, so the two S3 key variables are the app's R2 key. The setup makes that key and its vault keys, and `production_uploads_r2_key_variables` names its two variables.
Pass the app's vault keys through the deployment playbook's `app_secrets`. Never retain Railway credentials in destination containers.
For the app named `railway_portal`, add the following entries to each production app-server and jobs-server `app_secrets` mapping:

```yaml
app_secrets:
  railway_portal_database_password: "{{ .secrets.railway_portal_database_password }}"
  railway_portal_S3_ACCESS_KEY_ID: "{{ .secrets.railway_portal_S3_ACCESS_KEY_ID }}"
  railway_portal_S3_SECRET_ACCESS_KEY: "{{ .secrets.railway_portal_S3_SECRET_ACCESS_KEY }}"
```

The setup (`set-up-outside-services`) makes the three matching vault keys. Nobody adds them by hand. Preserve existing apps' entries in each mapping.
Staging uses the corresponding `staging_railway_portal_*` vault values with the unprefixed mapping keys shown above.
For a laptop or staging, run `npm run seed-test-data` with its own `APP_URL` and runtime `FIXTURE_PASSWORD`.
Do not import production accounts or documents into a developer's laptop database or staging test data.
Do not install a server cron timer or a second Railway-style cron container.
Every job container may attempt the archive occurrence because the PostgreSQL receipt prevents duplicate committed work.

For a production-only migration, exclude the app from staging before running the shared playbooks.
Use the installed Stack's tested environment-selection mechanism. A missing staging tag alone does not exclude an app.
Keep staging's own database and credentials separate.

Create the destination database before the final import. Do not start the portal or run its migrations yet.
Apply only the required database stages and their dependencies through the Stack's utility-server procedure.
Verify that the database is empty and the imported `controls.worker_paused` value will keep jobs idle.
After the final import passes, run the normal configuration and deployment procedures.
The preserved migration ledger makes the deployment migration command a checked no-op.

Before opening production traffic, verify the actual image, secure cookies over HTTPS, real private R2 access, and sessions across two app servers.
Run the Stack's Node database-switchover check and portal HTTP writes through `switch_database_primary`, without restarting the app.
Run an initial migration-only restore drill before adding data-dependent restore queries.
Then verify accounts, ownership, records, jobs, and separately restored object bytes.
Follow the systems repository's deployment and rollback procedure for the production release.

## 6. Freeze, import, and switch users

Phase 1 changes no DNS and stops no source service.
A live cutover needs approval for source maintenance, destination deployment, and the later source deletion.
Approval of a rehearsal does not authorize deleting production resources.

Before maintenance, prepare the destination image, private storage, hostname, credentials, and empty database.
Verify the runtime pull token can read the exact private image.
Prepare uploaded-file backups through the Stack's uploads-backup procedure before admitting an app with uploads.
Keep the protected original export until the final export and destination checks pass.

Record each cutover event in UTC:

1. Record the last successful source request and the maintenance start time.
   Stop the source web deployment so every HTTP write stops, including login sessions and file uploads.
   The example portal has no read-only maintenance switch.
   Stopping only its worker leaves customer writes enabled.
2. Stop the source worker. Disable Railway's cron schedule and stop any cron execution already running.
   Re-read the service settings and runtime stop flags. Confirm the old web endpoint no longer serves requests.
   Railway can retain deployment status `SUCCESS` after stopping a deployment. Check `deploymentStopped=true` instead.
   Keep source PostgreSQL and the bucket running for the export.
3. Export into a new protected directory with section 2's command.
   The saved export includes pending jobs, completed outputs, schedule receipts, password hashes, permissions, and object bytes.
   Verify source rows and receipts remain unchanged after execution stops.
4. Import into the empty destination database and private bucket using section 4's restore command.
   Require exact table digests and object byte hashes before logging in.
   Do not run the destructive disposable-rehearsal suite against the final production copy.
5. Start the app through the Stack's normal configuration and release procedures.
   Keep the imported worker pause enabled during account and file checks.
   Verify the exact release on each destination app server.
6. Log in as both existing users with their existing passwords over the destination HTTPS hostname.
   Check stable user IDs, administrator permission, owned records, document bytes, and completed report output.
   Check that each user cannot read another user's record, document, or report.
   A non-administrator must not control the worker.
7. Confirm source report and cron execution remain disabled.
   As the existing administrator, select **Resume worker** at the destination.
   Verify each imported pending report completes with the expected output.
   Verify the destination's five-minute UTC schedule creates a new receipt without duplicate occurrences.
8. Publish the destination hostname as the application's entry point and update links and integrations.
   Record the first successful destination request after maintenance.
   Measure downtime from source unavailability until the verified destination is available to users.
   Record export, import, deployment, verification, and traffic-switch durations separately.

Only one location may execute reports or scheduled work after the export boundary.
For the example, schedules archive reports older than 30 days.
A new schedule receipt proves execution, but does not prove archiving when no report is old enough.
The destination schedule records the current five-minute occurrence. Missed occurrences are not replayed automatically.
The next run still finds every completed report older than 30 days.
For schedules that send messages or charge customers, define and test catch-up behavior before migration.

Do not report a rehearsal duration as guaranteed production downtime.
An HTTP health check alone does not prove accounts, private storage, or jobs work.
Keep the source intact until destination checks pass without any Railway connection.

## 7. Your own domain and rollback

Railway owns the `up.railway.app` hostname. You cannot move that hostname to another provider.
A different destination hostname requires users to log in again because login cookies are bound to their hostname.
Restored password hashes preserve the existing passwords. No password reset is required for this portal.
Update bookmarks, website links, webhook destinations, and authentication redirect URLs where applicable.

If you own a custom domain, give the coding agent access to its DNS provider.
The agent must add the chosen hostname to the destination's routing and verify HTTPS before changing public DNS.
Lower a changeable DNS record's TTL before maintenance when the DNS provider supports that change.
Then replace the source DNS target with the destination's target and verify resolution and actual requests.
Keep users out of the old source during DNS propagation so customer writes cannot split between databases.
For Cloudflare Tunnel, the hostname needs both tunnel ingress and the Stack's application routing configuration.
A saved DNS record alone does not prove that requests reach the right app.

Before destination writes begin, rollback can restart the frozen source and restore its cron setting.
Reverse any traffic switch and verify source account access before ending maintenance.
After destination writes begin, rollback requires reconciling destination database rows, file bytes, jobs, and schedule receipts.
Pointing DNS back alone can lose customer changes or repeat work.
During Railway's deletion grace period, cancelling deletion can recover the source project.
Destination writes still need reconciliation before traffic returns to the source.
After permanent deletion, rollback requires rebuilding the source or another destination from the retained export.
The retained export excludes every write made after its snapshot.

## 8. Stop and delete the source

Use the approved cleanup scope to identify the exact source project and environment.
Confirm all destination runtime database and storage addresses are independent of Railway.
Record the destination checks and the protected final export location before deletion.
Stop the remaining source database deployment, then delete the approved Railway project.
The project deletion covers its services, database volume, native bucket, and provider hostname.
Railway presents a 48-hour deletion grace period. Record whether deletion is pending or permanent.
A deleted project can disappear from the active list while remaining in the deleted-project list.
Keep the native grace period unless the approved cleanup requires immediate permanent deletion.
Never delete unrelated projects, the Railway account, or billing settings.

Re-read the active and deleted project lists through an account-level credential or the authenticated dashboard.
Report zero active projects separately from permanent removal.
A rejected project-scoped token alone does not prove deletion because the token can also expire or lose access.
Check that the destination still serves existing users and files after deletion.
Record what was deleted, the observed result, remaining retained exports, measured downtime, and rollback limits.

## Fill a laptop or staging with test data

The command fills a developer's laptop database or staging with invented test data.
After the guide's local database and bucket setup, run migrations and start the app.
Set `APP_URL` to that app and supply `FIXTURE_PASSWORD`, then run from `app/`:

```sh
APP_ENV=development npm run seed-test-data
```

For staging, use `APP_ENV=staging` with its own database and bucket.
`npm run seed-test-data -- --accounts 200000` makes enough rows to show slow queries.
The count includes the two fixed accounts. Extra accounts use bulk SQL through
`DATABASE_URL`; they get one record each and no files or report jobs.
Reruns add missing rows, and a smaller count removes nothing.
