# Move from Fly.io to your own system

## Variances and guidance needs

Leaving Fly.io requires separate exports of the app, PostgreSQL data, object bytes, secrets, and Machine execution settings.
A Docker image or Git repository contains no database rows or Tigris document bytes.

The [example portal](../../examples/app-platform-migrations/from-fly/README.md) preserves the source schema, UUIDs, bcrypt password hashes, and private object keys.
The example uses application-owned authentication. A Fly app using Clerk, Auth0, or another identity provider needs that provider's separate export assessment.
Retaining an external identity provider is not a complete exit from that provider.

The verified source used unmanaged PostgreSQL 18.6. The example's simple schema restored into PostgreSQL 17.11 without SQL changes.
That result does not establish that arbitrary PostgreSQL 18 extensions, types, or queries work on PostgreSQL 17.
Inspect the source version and extensions before choosing the destination version.

Fly Managed Postgres is a different service from an unmanaged Postgres app on Machines and Volumes.
The [published pricing](https://docs.fly.io/about/pricing) lists a $38/month Managed Postgres Basic plan plus storage.
The fixture used an unmanaged database to avoid that base price.
An unmanaged database leaves operations, upgrades, and disaster recovery with the team.

Fly's `storage create --yes` also accepts the Tigris service terms and privacy policy.
Review those terms before provisioning a bucket. Do not use automatic confirmation when acceptance needs a person's decision.

## What the example proves

The source was hand-authored and deployed through flyctl from a Dockerfile.
The source used separate web and worker process groups, a private Tigris bucket, and a native hourly scheduled Machine.
A first deployment created the schema. A second deployment added `records.description` with an empty default and preserved the existing records.

Two synthetic users registered through the running app, created their own records, uploaded exact documents, and queued reports.
The source checks verified login, owned lists, guessed-ID refusals, CRUD, downloaded bytes, and logout.
Each user retained one PENDING report for the final export.
The native scheduled Machine completed an hourly session cleanup before migration preparation.

The destination rehearsal restored every database row and imported both objects through an S3 API.
Returning users logged in with their existing passwords and stable user IDs.
Independent web processes shared sessions and logout revocation.
The worker checks covered interrupted transactions, concurrent claims, and owner-specific report output.

The [test record](../../examples/app-platform-migrations/from-fly/test_record.md) names the versions, checks, and remaining boundaries.
The rehearsal does not prove a production traffic cutover, real R2 permissions, Stack backups, or a primary switch between real database servers.

## Inventory the source

Before editing or stopping the app, record the following information in a protected inventory.

| Part | Record | Export |
| --- | --- | --- |
| App | Framework, runtime, dependency lockfile, Dockerfile, release image and source revision | Git archive or native filesystem archive |
| Database | Managed or unmanaged service, version, extensions, database and role names | Consistent `pg_dump` plus a row audit |
| Authentication | Provider, user IDs, password algorithm, sessions and reset policy | Supported identity export or application tables |
| Private files | Bucket, object keys, lengths, hashes and owner links | Downloaded object bytes and manifest |
| Jobs | Queue, IDs, owners, states, outputs and active workers | Database snapshot and worker configuration |
| Schedule | Machine ID, command, image, interval and completed occurrences | Machine configuration plus database ledger |
| Configuration | Variable names and destination replacements | Protected secret transfer or replacement |
| Networking | App hostnames, private database addresses and public traffic entry | Destination DNS and routing plan |

Use `fly apps list`, `fly machine list -a YOUR_APP --json`, and `fly volumes list -a YOUR_DATABASE_APP --json`.
Save deployment configuration and the original scheduled Machine configuration before disabling source execution.
Save the first app listing as `source-machines-before-freeze.json` and the database Volume listing as `source-database-volumes.json`.
After disabling source schedules, save the fresh app listing as `source-machines-paused.json`.
Fly process groups run in separate Machines. A scheduled Machine created with `fly machine run` can be outside `fly deploy` management.
Do not assume the app's `fly.toml` lists every Machine or scheduled task.

Tigris's S3 API provides object access. Fly app secrets are not a reusable plaintext secret export.
The [Tigris integration guide](https://docs.fly.io/tigris) says bucket creation prints access credentials once.
Save newly issued credentials securely. Use the Tigris console to issue replacement keys when original keys are unavailable.
Never commit tokens, exports, password hashes, or destination credentials.

## Freeze and export

First rehearse the full export and restore on disposable destination resources.
For the final export, stop new mutations and enable execution at exactly one location.
In this portal, set `controls.maintenance=true` and `controls.jobs_paused=true` through an authenticated administrative database connection.
The maintenance setting also blocks registration and new login sessions.

Stop the source worker Machines. Disable each source Machine schedule, then stop the scheduled Machines.
A stopped Machine with an active schedule can run again. Re-read the Machine configuration until the schedule is absent.
Keep the original interval and command in the inventory for destination scheduling.
Wait for in-flight requests and job transactions to finish before taking the final snapshot.

For this portal, adapt [scripts/export-source.mjs](../../examples/app-platform-migrations/from-fly/scripts/export-source.mjs) to the deployed file layout.
The helper imports the app's database and storage modules. Upload the helper through `fly ssh sftp put`.
Run the helper through `fly ssh console -a YOUR_APP -g web -C 'node /app/scripts/export-source.mjs'`.
The source image needs a PostgreSQL client that supports the source database version and the `tar` program.

The helper requires maintenance and job pause before export.
The helper keeps a repeatable-read transaction open while `pg_dump` and the table audit use the same exported snapshot.
The helper downloads objects separately and checks SHA-256 against database metadata during verification.
The code archive includes deployed application files and excludes `node_modules`.
The code archive does not export Fly secret values.

Keep the three native inventory JSON files beside `manifest.json` after downloading and extracting the trusted export.
Generate the separate execution-inventory checksums from the example directory:

```sh
node scripts/checksum-native-config.mjs /secure/exports
```

The command verifies that each originally scheduled Machine is now stopped with no schedule.
The command writes `native-configuration-manifest.json`. Keep the original source manifest unchanged.
The verifier requires both manifests, so Machine schedules cannot disappear silently from a verified export.

Use a protected directory and private file permissions before downloading the archive:

```sh
umask 077
mkdir -p exports
fly ssh sftp get /tmp/fly-export.tar.gz exports/source-export.tar.gz -a YOUR_APP -g web
```

Compare the downloaded archive's SHA-256 with the helper's recorded archive hash.
Extract only the trusted export into a mode-700 directory. Inspect the archive member names before extraction.
Keep `database.dump`, `table-audit.json`, `manifest.json`, `code.tar.gz`, and `objects/` together.
The audit and dump contain password hashes and require the same protection as database backups.

No source plan upgrade was required for these native exports.
Machines, Volumes, and network use remain metered. Check current account allowances and prices before running a rehearsal.
Tigris has separate storage and request allowances. Fly can charge outbound transfer even when Tigris does not charge egress.

## Restore on Linux

Create a dedicated PostgreSQL database and role. Create a private destination bucket with new credentials.
Use the Stack's configured PostgreSQL version. Verify compatibility before restoring a source from a newer major version.
Keep all destination web processes, workers, and schedules stopped during restore.

Build the customer-copy app from the example directory:

```sh
podman build -t customer-portal -f Containerfile .
```

Copy `environment.example` to a protected file outside the build context.
Set the destination database URL, bucket, endpoint, access credentials, and runtime values.
Keep `COOKIE_SECURE=true` behind production HTTPS.
For an isolated HTTP rehearsal only, set `COOKIE_SECURE=false`.

Use a PostgreSQL client compatible with the dump format.
Set `PGHOST`, `PGPORT`, `PGUSER`, and `PGDATABASE` for the actual destination primary.
Load `PGPASSWORD` from the protected credential source without printing the password.
Do not pass a credential-bearing URL as a command argument.

```sh
pg_restore --no-owner --no-acl --exit-on-error --dbname=portal exports/database.dump
```

`portal` names the dedicated empty database. The PostgreSQL environment variables supply the connection settings.
If PostgreSQL rejects a source feature, stop and assess compatibility. Do not ignore restore errors.

Verify the export and compare restored rows before any destination login or worker changes the database:

```sh
podman run --rm --user 0 --network host \
  --env-file /secure/portal.env -v /secure/exports:/export:ro \
  customer-portal node scripts/verify-export.mjs
podman run --rm --user 0 --network host \
  --env-file /secure/portal.env -v /secure/exports:/export:ro \
  customer-portal node scripts/compare-database.mjs
podman run --rm --user 0 --network host \
  --env-file /secure/portal.env -v /secure/exports:/export:ro \
  customer-portal node scripts/import-objects.mjs
```

The one-shot tools use user 0 to read mode-600 exports on the host-mounted directory.
The production application image runs as the `node` user.
The importer preserves object keys and downloads each imported object to verify its hash.
An S3-compatible test server proves API and byte behavior. Verify real destination bucket permissions separately.

Run `node database.mjs` in the app image to validate and apply ordered migrations.
The copied migrations must match the source ledger checksums. Do not rewrite an applied migration.
The example uses the Stack's unchanged PostgreSQL helper to interpret URLs listing multiple database servers.
New connections find a writable primary. Failed HTTP mutations are not replayed automatically.

## Verify accounts and execution

After the exact row comparison, clear destination maintenance for the disposable rehearsal.
Keep workers paused until accounts, owner links, and document downloads pass.
Test both users through two independent web processes and verify logout on either process revokes the session everywhere.
Test guessed record, document, and report IDs as the wrong user.
Use the existing fixture password through a protected runtime variable, never a committed value.

Run the example's [testing instructions](../../examples/app-platform-migrations/from-fly/testing.md).
The tests mutate destination data. Run the tests only against a disposable restore.
Use another fresh restore for the final cutover.

The jobs command is `node jobs.mjs`. `--once` attempts one report and exits.
Workers use `FOR UPDATE SKIP LOCKED`. Record count, report output, and completion commit in the same transaction.
Killing a worker before commit leaves the job pending.
Clear `controls.jobs_paused` only when the destination owns execution.

The scheduled command is `node schedule.mjs`. Run the command hourly through the destination's scheduler.
The occurrence ledger prevents duplicate work for the same UTC hour.
Fly's hourly schedule is an interval mechanism, not an exact wall-clock cron promise.
Do not keep the source schedule enabled when destination scheduling starts.

## Cutover, rollback, and cleanup

Confirm the final source freeze, fresh export, object hashes, and exact restore before sending production traffic to the destination.
Install new destination secrets, set HTTPS routing, and verify fresh writes, sessions, and private downloads through the public hostname.
Start destination workers and scheduling only after source execution is disabled.
Preserve completed job output as well as pending jobs.

Before destination writes, rollback can return traffic to the still-frozen source after restoring source execution deliberately.
After destination writes, source data is stale. Reconcile destination changes before any rollback that would discard data.
Do not run both queues or schedules as a rollback shortcut.

After acceptance, delete only the recorded source resources.
Delete the source web app, worker Machines, scheduled Machines, database app, database Volumes, and unused network resources.
Delete the source Tigris objects and bucket separately. Verify Tigris cleanup through a fresh bucket listing.
Managed Postgres, when used, also needs separate cleanup. Deleting a web app does not delete Managed Postgres.
Re-list apps, Machines, Volumes, and buckets to prove absence. Revoke temporary tokens after the final inventory.

## Fill a laptop or staging with test data

The command fills a developer's laptop database or staging with invented test data.
After the guide's local database and bucket setup, run migrations and start the app.
Set `APP_URL` to that app and supply `FIXTURE_PASSWORD`, then run:

```sh
APP_ENV=development npm run seed-test-data
```

For staging, use `APP_ENV=staging` with its own database and bucket.
`npm run seed-test-data -- --accounts 200000` makes enough rows to show slow queries.
The count includes the two fixed accounts. Extra accounts use bulk SQL through
`DATABASE_URL`; they get one record each and no files or report jobs.
Reruns add missing rows, and a smaller count removes nothing.
