# Dokku migration example

## Variances and guidance needs

This example moves a Docker-local Dokku portal, its host-held configuration, private upload mount, PostgreSQL plugin data, and cron task.
The app and worker move before the database. PostgreSQL stays on the Dokku host over WireGuard until the destination passes customer actions.
The [guide](../../../docs/app-platform-migrations/from-dokku.md) keeps the Dokku-specific source preparation.
[Move a database into the Stack][database-move] owns logical replication and switching.
The [test record](test_record.md) distinguishes standalone proof from live Stack checks.

## Acceptance contracts

- Native Dokku runs the actual app, PostgreSQL plugin, web and worker processes, a private mount, and `app.json` cron.
- Source population uses the app's HTTP endpoints for accounts, records, private files, and queued reports.
- Accounts keep bcrypt verifiers and UUIDs. Every record, document, and report retains its owner.
- Global and application configuration are exported separately. App values override global values, and runtime-only secrets survive protected transfer.
- Upload export preserves every regular file key, byte length, and SHA-256. Import reads back every object and refuses overwrites.
- Source cron and process scaling are paused independently. Destination work begins only after source execution stops.
- Destination customer actions work while PostgreSQL remains on the source over WireGuard.
- The Stack's database-move procedure owns copying, fencing, sequence/large-object transfer, and switching. Customer accounts, ownership, private bytes, and job state must survive the move.
- A single MMX-managed timer invokes the active job container. Repeated or overlapping archive calls commit one receipt per UTC date.
- After the database switch, the destination accepts new customer writes with the Dokku guest stopped.
- Another Dokku scheduler or plugin needs source-specific proof. The Stack procedure defines supported database data and transfer checks.

## Source fixture

Use a disposable Debian 13 Linux host with Dokku `v0.38.34`, Docker, and the copied example.
The source installer needs `curl`, `wget`, and the vendor's pinned bootstrap:

```sh
curl -fsSL https://dokku.com/install/v0.38.34/bootstrap.sh -o bootstrap.sh
DOKKU_TAG=v0.38.34 bash bootstrap.sh
```

Set `EXAMPLE_DIR` to the absolute copied example path and `PRIVATE_DIR` to a mode-700 directory outside Git.
Run `bash "$EXAMPLE_DIR/scripts/create-source.sh"` on the fresh host.
The script installs `dokku-postgres` `2.6.1`, creates PostgreSQL `17.11`, and deploys the app from a protected archive.
Plugin-install permissions differ from export permissions. The script uses a normal file mask for shared executable installation and source archive deployment.
Operational logs remain private.

The source has global `HOST_CONFIG_SCOPE=global`, app `HOST_CONFIG_SCOPE=app`, and global-only `GLOBAL_ONLY_SETTING=preserved`.
`app.json` generates `RUNTIME_SECRET` on the host at each deploy. No secret value is committed.
The PostgreSQL plugin generates and links the database credential. Keep deployment output private because Dokku can print generated values.
The source worker starts paused so the fixture can retain pending work.
The app uses `/uploads`, mounted from `/var/lib/dokku/data/storage/portal`, owned by the image's UID 1000.
Dokku's `app.json` predeploy hook runs migrations. `Procfile` holds web and worker commands.

Install Node.js 24 and PostgreSQL 17 client tools on the test controller, then run `npm ci --prefix app --ignore-scripts --no-audit --no-fund`.
Generate a synthetic password into a mode-600 file. Keep the filename in `FIXTURE_PASSWORD_FILE`.
Set `APP_URL` to the source hostname, resolving to the source host, and `CUSTOMER_BASELINE_FILE` to a private JSON path.
Populate through HTTP:

```sh
node tests/customer-actions.mjs populate
```

The baseline stores account and object identifiers and hashes. The password stays in its separate input file.
The check creates two accounts, owned records, private documents, and pending reports, then tests ten cross-owner refusals.

## Export and destination inputs

Follow the guide's source inventory and freeze before the final upload copy.
`transfer-uploads.mjs export` reads `DATABASE_URL`, `UPLOAD_DIR`, and a new `EXPORT_DIR`.
On the source host, `UPLOAD_DIR` names the host directory rather than the container mount path.
`uploads.json` records object keys, lengths, hashes, and document count. `objects/` holds bytes by checksum.
`snapshot-database.mjs` reads `DATABASE_URL` and writes sensitive rows to `SNAPSHOT_FILE`, with counts and checksums on standard output.
The native `dokku postgres:export` archive remains a separate protected database recovery copy.

For a standalone destination, copy `environment.example` into a protected Podman `--env-file` input and replace the documented values.
For Stack deployment, `database_moving_in` generates the old-first database URLs. Omit `UPLOAD_DIR`.
`environment.example` is a standalone test input, not a replacement for Stack-managed database settings.
`DESTINATION_STORAGE_CONFIG_FILE` is mode-600 JSON with this shape:

```json
{
  "endpoint": "https://s3.example.com",
  "region": "us-east-1",
  "forcePathStyle": true,
  "bucket": "example-portal-uploads",
  "credentials": {
    "accessKeyId": "REPLACE_FROM_THE_PROTECTED_CREDENTIAL",
    "secretAccessKey": "REPLACE_FROM_THE_PROTECTED_CREDENTIAL"
  }
}
```

Run `node scripts/transfer-uploads.mjs import` against a new private bucket.
The synthetic rehearsal uses S3Mock for byte compatibility. S3Mock does not prove real bucket privacy or permissions.
Follow [Prepare the Stack and move the app][database-move] to configure `database_moving_in` and start the Stack app against the old database.
Use the guide's Dokku login-name, container-listener, and database-fence instructions.
The copied Node helper checks `transaction_read_only` when selecting a writable server.
Start web with `node web.mjs` and the worker with `node jobs.mjs`, from `app/`.
Use `PORT` for the web port, `WEB_CONCURRENCY=2`, and `JOBS_PAUSED=false` after source execution stops.
Keep `COOKIE_SECURE=true` behind the destination HTTPS route. Plain HTTP disposable tests use `false`.
Run `node tests/customer-actions.mjs verify` with the original password and baseline files.
The verifier checks returning passwords, stable IDs, original bytes, ownership refusals, new CRUD/uploads, queued output, and logout.

## External schedule

Copy `systems-repository/playbooks/portal_schedule.yml` into the team's systems repository.
Define one-node group `portal_schedule_server`, containing a server that runs `portal-jobs`.
Set `vars.portal_archive_calendar` to `"*-*-* 00:00:00 UTC"` and run `mmx run portal_schedule`.
The guide explains ownership, inspection, missed-run behavior, and the database receipt check.
The report worker does not start a second scheduler.

## Move the database last

Follow [Move a database into the Stack][database-move] and its two playbooks:

- [copy_the_database_moving_in][database-copy] copies into the Stack's normal database formation.
- [switch_to_the_database_moving_in][database-switch] fences each listed source database, ends the listed app sessions, and opens the new app roles without restarting containers.

The fixture's plugin database is `portal_db`, so the Stack app's `database_name` and old app login must be `portal_db`.
Its original plugin link uses an administrator login. Prepare the matching app role as the [Dokku guide](../../../docs/app-platform-migrations/from-dokku.md) describes.
Keep the source host outside managed database inventory groups.
Include every writer sharing a moving database. The source fence changes only the listed databases' defaults.

Keep migrations paused during the copy. Keep the destination app, worker, and timer running during the Stack switch.
Use the procedure's HTTP writer, acknowledged-write checks, replica checks, failure recovery, and backup before removing source resources.
Then stop the Dokku host and repeat `node tests/customer-actions.mjs verify` with the original password and baseline files.
The earlier standalone test's measured stop-and-restart switch is separate evidence and is not the Stack switch procedure.

## Targeted checks

With Node.js 24, run `npm ci --prefix app --ignore-scripts --no-audit --no-fund`, then `npm test --prefix app`.
These local tests check private upload bytes, overwrite/path refusal, and writable-login selection during the database fence.
The database-selection test supplies session states without starting PostgreSQL. The copied helper stays identical to the Stack's current file.

The inherited `app/tests/seed-test-data.test.mjs` needs an empty dedicated PostgreSQL database, storage, `FIXTURE_PASSWORD`, and `REHEARSAL_CONFIRM=disposable-destination`.
The seed test populates its own data and starts its own HTTP process. Keep that database separate from the migration fixture.
The HTTP and timer checks need their configured disposable services. See the test record for their native-source evidence.

[database-move]: ../../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md
[database-copy]: ../../../skills/monkeymaxxing-stack/systems_repository_template/playbooks/copy_the_database_moving_in.yml
[database-switch]: ../../../skills/monkeymaxxing-stack/systems_repository_template/playbooks/switch_to_the_database_moving_in.yml
