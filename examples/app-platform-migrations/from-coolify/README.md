# Customer portal moved from Coolify

This example recovers Coolify-held production settings, native schedules, PostgreSQL state, and mounted private files.
The [guide](../../../docs/app-platform-migrations/from-coolify.md) covers inventory, shutdown, destination verification, and the database-last boundary.
The [test record](test_record.md) distinguishes native source proof from standalone and full Stack checks.

## Acceptance contracts

- Git is insufficient to reproduce the source: a shared production setting, a runtime-only signing key, a mount, and a Scheduled Task come from Coolify.
- Authorized API exports recover ordinary secret values without printing them. Read-only and shown-once behavior are checked separately.
- The protected native inventory retains application settings, variable scopes, shared references, mounts, tasks, execution history, and deployments.
- The state export captures every public table and every regular mounted file, including unreferenced files. Document rows match file lengths and SHA-256.
- Accounts retain stable UUIDs and bcrypt verifiers. Returning users keep passwords, record ownership, private downloads, and pending report work.
- The preserved signing key lets a source-issued session work at the destination. Logout revokes sessions across independent web processes.
- Source scheduling and deployment triggers cannot restart source work after handoff. Exactly one location owns workers and schedules.
- The native PostgreSQL resource uses a WireGuard-bound Port mappings entry with its public proxy disabled. The bind, original client address and data survive native restart/redeployment.
- The destination performs customer actions against the old database over WireGuard before the database moves.
- The Stack's logical-replication procedure and copy/switch playbooks own the database move. Verify destination customer actions with the source stopped.
- A standalone destination result is recorded separately from MMX-managed routing, R2 authorization, backup recovery, and alerts.

## Run the app

Build `Containerfile` with this directory as the build context.
For a fresh local database, load protected values from `environment.example` and apply migrations before starting the app.
During a Stack database move, follow the [database procedure](../../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md) and freeze schema migrations until the move finishes.

| Command | Purpose |
| --- | --- |
| `node database.mjs` | Apply ordered migrations and check existing migration checksums |
| `node server.mjs` | Serve the portal on `PORT`, with `WEB_CONCURRENCY` processes |
| `node jobs.mjs` | Process reports and hourly cleanup until SIGTERM |
| `node jobs.mjs --once` | Attempt one report and exit |
| `node schedule.mjs` | Commit one expired-session cleanup per UTC hour |
| `node seed-test-data.mjs` | Populate a laptop or staging through customer HTTP actions |

The source uses `FILE_STORAGE=disk` with `UPLOADS_DIR` mounted persistently.
The destination uses `FILE_STORAGE=s3` with the bucket settings in `environment.example`.
`SESSION_SIGNING_KEY` is required by the web process.
`PORTAL_NOTICE` is a non-secret setting returned by `/healthz` to check shared-variable resolution.

## Create the synthetic Coolify source

Use a fresh Coolify v4.6.0 instance, an authorized token, and a server with working Docker access.
Build and publish the example image to a registry reachable by the Coolify host.
The fixture creates a project, PostgreSQL resource, image application, production variables, persistent upload volume, and Scheduled Task.

```sh
umask 077
export COOLIFY_API_URL=https://coolify.example.com/api/v1
export COOLIFY_API_TOKEN_FILE=/secure/coolify-fixture-token
export COOLIFY_SERVER_UUID=REPLACE_WITH_SERVER_UUID
export SOURCE_IMAGE_NAME=registry.example.com/portal
export SOURCE_IMAGE_TAG=REPLACE_WITH_BUILT_IMAGE_TAG
export SOURCE_SETTINGS_FILE=/secure/source-fixture.json
python3 scripts/create-source.py
```

The fixture token needs `read`, `write`, and `deploy`.
The output file contains generated synthetic credentials and resource identifiers.
The script saves identifiers after each create so a partial failure still leaves an inventory for cleanup.
Use the recorded resource IDs to investigate a failed creation rather than running the script again against the same settings file.

Wait for the native PostgreSQL resource to become ready.
Load the generated app variables through the API into a protected environment file for the one-shot migration command.
Run `node database.mjs` in the built image on the Coolify resource network.
Start the application through `POST /applications/{uuid}/start`.

Inspect the actual application volume, then make the upload directory writable by the image's `node` user, UID 1000.
Do not replace an existing application's ownership with the fixture's UID.
Wait for `/healthz` and check the resolved shared notice.
Populate through `seed-test-data.mjs` with `APP_ENV=staging`, `APP_URL`, and the generated `FIXTURE_PASSWORD`.
The seed command only uses HTTP for the two fixture accounts, records, private documents, and pending reports.

After creation, keep only resource IDs and the synthetic customer password in the fixture record.
Discard temporary creation copies of the runtime signing key, database password, and webhook secret once Coolify holds them.
The migration export must recover runtime settings from Coolify, not reuse the creation input.

## Export and replay

Follow the guide to export native API state, stop source execution, and export rows and bytes.
Keep `coolify.json`, generated runtime configuration, code/image identities, and state exports outside Git.
The export contains bcrypt verifiers and session hashes.

Use [testing.md](testing.md) for the disposable restore checks.
Use a fresh database and bucket for replay because the checks mutate the restored copy.
The source fixture's minute schedule dispatches an hourly idempotent application command.
Preserve that application behavior when replacing the native scheduler.

## Fill a laptop or staging

Provide a private test database and bucket, run migrations, and start the app.
Set `APP_URL` and supply `FIXTURE_PASSWORD` through protected runtime settings.
Run `APP_ENV=development npm run seed-test-data` or use `APP_ENV=staging`.
`npm run seed-test-data -- --accounts 200000` adds invented accounts and records for query checks.
Reruns preserve existing passwords, rows, documents, and reports.
