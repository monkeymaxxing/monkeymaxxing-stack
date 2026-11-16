# Move a Supabase app to your own system

## Variances and guidance needs

A Supabase exit moves the app's managed services as well as its Postgres tables.
This guide covers a manually authored React portal with email/password accounts, owned records, private documents, queued reports and a scheduled task.
The destination uses the Monkeymaxxing Stack's app processes, Postgres and private S3-compatible storage.

- Passwords were portable for the tested confirmed email accounts. Both original bcrypt hashes worked without a reset.
- Existing Supabase sessions are not portable into this reduced API. Users log in again with their existing passwords.
- Supabase logout revokes refresh tokens. Issued access tokens can remain usable until expiry, as the source check confirmed.
- The destination uses shared database sessions. Logout on one process immediately prevents access through another.
- Row Level Security policies become explicit server authorization checks. Copying the policy SQL alone does not protect a new API.
- Storage metadata is not object data. Every private file must be downloaded, uploaded and verified separately.
- The Edge Function becomes a server API plus a separate transaction-based report worker.
- The known pg_cron minute marker becomes a worker task. Other SQL commands, cron expressions and time zones need explicit mapping.
- Native SQL permission blocked direct updates to `cron.job`. Use `cron.alter_job` to disable the source job.
- After the additive schema migration, PostgREST briefly returned `PGRST204`. Reloading the schema cache resolved the mismatch.
- Email verification, recovery mail, OAuth, SSO, anonymous users and MFA need their own auth design before a production move.

The example refuses unsupported account states, unknown application columns, unmapped schedules and an active source cron job.
Those refusals prevent losing security rules or silently discarding data. Extend the mapping when the real app uses more features.
The [example](../../examples/app-platform-migrations/from-supabase/README.md) and [design](../../examples/app-platform-migrations/from-supabase/design.md) describe the exact implementation.

## What has been proved

The native source used a free Nano project, PostgreSQL 17.11, Supabase Auth, RLS, private Storage, an Edge Function and pg_cron.
A separately hosted Vite/React frontend called those services directly.
The source was written by hand. No platform AI generated the app.
Both fixture users registered through the app's normal Auth API and populated rows, files and jobs through its normal service endpoints.
The second real deployment added `records.description` with an empty default, then applied the fixture descriptions through the API.

The independent rehearsal uses PostgreSQL 17 and an S3-compatible local service.
The [test record](../../examples/app-platform-migrations/from-supabase/test-record.md) states measured results and limits.
A local rehearsal does not prove a production Stack deployment, primary switch, actual R2 permissions or operational alerts.

## Inventory before exporting

Record the frontend URL, project reference, region, framework versions and dependency lockfile.
Read the app's actual service calls. List every database schema, RLS policy, SQL function, Edge Function and scheduled command.
Check Auth account methods, identity providers, verified status, bans, MFA and any password verifier that the destination cannot read.
Do not merge identities by email. Preserve the source issuer and subject alongside the destination user UUID.
Inventory private and public buckets, object keys, names, sizes, hashes and orphaned objects.
Check Realtime subscriptions, webhooks, database extensions, secrets and external services before choosing an exit design.
The included exporter targets only the example's named schemas, bucket and function. Extend the inventory for a different app.

Write a source facts manifest before conversion. Include:

- User UUIDs and owner mapping for every record, document and report.
- Exact file keys, lengths and SHA-256 values.
- Pending and completed jobs, including outputs and timestamps.
- Schedules, time zones, last execution and the intended next execution.
- Applied migrations, code hashes, lockfiles and configuration variable names.

Keep password hashes, identity exports and archives private. Protect files with `umask 077` and directories with mode 700.
Never print passwords, administrator keys, database URLs with passwords or auth export rows.

## Export as the customer

Use the customer's existing Management API token, database password and Storage administrator key.
A free project does not need a paid export feature for the tested SQL and Storage routes.
Use PostgreSQL tools matching the source major version. A PostgreSQL 15 client cannot dump a PostgreSQL 17 server.
Use TLS and the dashboard's Session pooler on port 5432 when direct IPv6 is unavailable.
The [Supabase backup guide](https://supabase.com/docs/guides/platform/migrating-within-supabase/backup-restore) explains the connection routes.
A service-role key is for server-side export only. It must never enter a frontend build.

Export code from the customer's source repository with its lockfile and SQL migrations.
Do not treat downloaded frontend JavaScript as complete source code.
For the included manual source, the authored source tree supplied the complete source archive.
For a Git project, review tracked files for secrets before making an archive:

```sh
git archive --format=tar.gz --output=/secure/source-code.tar.gz HEAD
```

Stop all other writers, webhooks, service-role clients and queue producers before the final snapshot.
The example exporter revokes authenticated table writes and report RPC execution, then disables the named cron job.
Those revocations do not freeze arbitrary administrator clients or unknown functions. Stop those writers separately.
Only one source/destination location may execute pending reports during cutover.

Create a private exported-variable file outside the source tree. Required export variables are:

| Name | Value |
| --- | --- |
| `SUPABASE_PROJECT_REF` | The customer's project reference |
| `SUPABASE_ACCESS_TOKEN` | Existing Management API token |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-only Storage export key |
| `PGHOST` | Dashboard's session-pooler host |
| `PGPORT` | `5432` |
| `PGUSER` | Dashboard's pooler database user |
| `PGDATABASE` | `postgres` |
| `PGPASSWORD` | Existing database password |
| `PGSSLMODE` | `require` |
| `PGCONNECT_TIMEOUT` | `15` |
| `SOURCE_CODE_ARCHIVE` | Reviewed source archive path |
| `EXPORT_DIR` | A new private export directory |
| `FREEZE_SOURCE_FOR_EXPORT` | `true`, only after the final freeze is approved |

Run the exporter from the example directory, with those values already exported in the shell:

```sh
umask 077
. /secure/supabase-export.env
python3 export-source.py
```

The exporter keeps the source frozen if a later export step fails. Resolve the failure before changing traffic or enabling workers.
It creates a repeatable-read JSON snapshot, a native custom-format database archive, Storage bytes, function body, code archive and SHA-256 manifest.
The snapshot includes users and bcrypt hashes, identities, MFA inventory, app rows, bucket metadata, migrations, cron definitions and cron history.
The native archive includes `public`, `auth`, `storage`, `cron` and `supabase_migrations` schemas.
Roles and grants are deliberately not reapplied to the reduced destination. Preserve a separate role inventory if a different design needs those roles.
The native dump is an inspection and recovery source, not SQL to apply blindly to an independent app database.

Compare every exported value with the source facts manifest. List storage objects and compare the complete set with document metadata.
An extra object, missing object, changed owner, unsupported column or password verifier blocks import until the mapping is corrected.
Store secrets and the fixture password outside the code archive. The synthetic rehearsal receives its original password through a private file.

## Build the independent app

Install the example with Node.js 24. Run `npm ci` and `npm run build`.
Use [environment.example](../../examples/app-platform-migrations/from-supabase/environment.example) to create the destination's private runtime settings.
Supply the Stack's full `DATABASE_URL` with every database server. The included driver helper chooses the primary for each new connection.
Create a private S3-compatible bucket and give the app only the required bucket permissions.
Set `PUBLIC_ORIGIN` to the browser-facing HTTPS origin. The API refuses mutations from a different origin.
Keep `RUN_REPORT_JOBS=false` and `RUN_SCHEDULE=false` during preparation.

```sh
node --env-file=/secure/portal.env operations.mjs migrate
node --env-file=/secure/portal.env operations.mjs import
node --env-file=/secure/portal.env web.mjs
```

The importer requires an empty destination. It refuses an unexpected object rather than overwriting different bytes.
A retry after a database rollback can reuse matching uploaded objects. A successful import cannot be repeated over populated tables.
Import preserves stable UUIDs, bcrypt verifiers, owner mapping, descriptions, file references, completed output and pending work.
Supabase tokens are not imported. New sessions live in the destination database.
The [Supabase signout guide](https://supabase.com/docs/guides/auth/signout) explains native logout scopes and refresh-token behavior.

Use the example's synthetic rehearsal on a dedicated Linux database and bucket before a real deployment.
Run the fresh replay with another empty database and a distinct bucket. The replay needs only the export, original fixture password and guide.
The README lists every rehearsal and restore setting and command.
`seed-test-data` fills a developer's laptop database or staging with invented data. It accepts only `APP_ENV=development` or `APP_ENV=staging` and refuses a database with accounts outside its fixed fixture or generated test-account names.

## Prepare the Stack deployment

Build the included `Containerfile` and deploy that image through the team's normal app procedure.
Use `node web.mjs` for web, `node operations.mjs migrate` for migrations and `node operations.mjs jobs` for workers.
Use `/healthz` as the database-backed health route.
The Node cluster uses `WEB_CONCURRENCY`; workers share the web instance's `PORT`.
Keep the web processes and worker on the same imported database and private bucket.
Use a separate local or staging database and bucket for `node operations.mjs seed-test-data`.

Before accepting production traffic, verify login with existing passwords, all ownership refusals, file hashes and report outputs through the real route.
Test a primary switch while app and worker processes remain running. Record errors and time until a new write succeeds.
Do not automatically repeat a mutation whose commit result is uncertain. Check the resulting records before a person retries.
Verify real bucket permissions, backup schedules, restoration and alerts. Local S3 protocol checks do not prove those controls.

## Cut over and recover

Repeat the approved write freeze and final export after any earlier rehearsal.
Reimport into a fresh verified destination, compare manifests and keep destination workers stopped.
Change traffic only after the final data check passes. Confirm logins, owned files and a fresh write through the public route.
Enable report jobs and the mapped schedule at the chosen destination only. Keep source execution disabled.
Record the cutover time and all new destination writes.

Before destination writes begin, rollback means restoring source privileges, re-enabling the source cron and routing traffic back.
For this example, the operator can run the following as the authorized database administrator:

```sql
begin;
grant insert,update,delete on public.records,public.documents to authenticated;
grant execute on function public.queue_report(),public.process_report() to authenticated;
select cron.alter_job((select jobid from cron.job where jobname='portal-minute-marker'), active:=true);
commit;
```

Stop destination execution before that rollback. Never run both queues at once.
After destination writes begin, routing back alone would lose those writes. Reconcile data or restore a chosen recovery point first.
A backup must include database rows and file bytes. Restore into a new database and bucket and verify both before serving traffic.
Delete only the identified source project and frontend after verified completion and the agreed retention decision.
The synthetic phase-1 fixture is removed after replay because the brief explicitly requires that cleanup.

## Free-plan boundaries

At verification, Supabase's free plan allowed two active projects, 500 MB database, 1 GB files, 50,000 monthly active users and 5 GB egress.
Cached egress had a separate 5 GB allowance. Inactive projects pause after one week.
See [Supabase pricing](https://supabase.com/pricing) for current limits.
The account's captured entitlements also limited uploads to 50 MiB, functions to 100 and function bundles to 20 MB.
Daily backup downloads, point-in-time recovery, dedicated IPv4, custom domains and higher observability had no free entitlement in this run.
The export used SQL and authenticated file downloads, so none of those add-ons was purchased.
Netlify hosts only static frontend files here. Its own [credit-based limits](https://docs.netlify.com/manage/accounts-and-billing/billing/billing-for-credit-based-plans/credit-based-pricing-plans/) also apply.
No paid plan, add-on, trial or payment step was started.

## Fill a laptop or staging with test data

After the local database and bucket setup, run migrations, supply `FIXTURE_PASSWORD`, and run:

```sh
APP_ENV=development npm run seed-test-data
```

Use `APP_ENV=staging` for staging. `npm run seed-test-data -- --accounts 200000`
makes enough rows to show slow queries. The count includes the two fixed accounts.
Reruns preserve existing fixture and generated accounts; a larger count adds only
missing generated accounts and owned records. A smaller count removes nothing.
The account guard refuses other data before any row change or file upload.
