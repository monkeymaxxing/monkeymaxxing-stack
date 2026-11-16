# Move from Coolify to your own system

## Variances and guidance needs

Move a Coolify-hosted portal by exporting the live resource settings as well as code, database rows, and mounted files.
Git does not contain Coolify's production variables, storage settings, or Scheduled Tasks.
Use the Stack's [database-move procedure][database-move] to move PostgreSQL last, by logical replication.
The Stack owns database preparation, copying, write fencing, switching, and cleanup.
This guide adds Coolify's settings, storage, scheduler, and database-container details.

| Coolify source behavior | Migration guidance and example scope |
| --- | --- |
| Coolify v4.6.0 image application | Export resource settings, image identity, generated container configuration, and the source revision separately. |
| Shared project variable | Export shared scopes and the application variable reference. Compare the resolved production value with the running container. |
| Runtime-only signing key | An authorized `read:sensitive` token can recover ordinary values. Preserve the key to retain the fixture's session hashes. |
| Shown-once or locked value | Record the missing value and use the owning secret store or reissue it. The API does not promise universal secret recovery. |
| Persistent upload volume | Export the mount definition through the API. Copy the actual host files separately, including unreferenced files. |
| Native Scheduled Task | Export command, frequency, target container, timeout, enabled state, and execution history. Disable the task before handing over execution. |
| Automatic and manual deployment triggers | Disable automatic deployment and preview deployment, rotate manual webhook secrets, and revoke deployment tokens after inventory. |
| Coolify-managed PostgreSQL | Keep the old database private during the app move. Move PostgreSQL last through `database_moving_in` and the Stack logical-replication playbooks. |

## What the example proves

The [example](../../examples/app-platform-migrations/from-coolify/README.md) reuses the portal's PostgreSQL accounts, bcrypt verifiers, ownership checks, and report queue.
The source stores private files in a Coolify persistent volume.
The destination stores private bytes through an S3-compatible API with unchanged object keys.

The native checks proved recovering Coolify-held settings, stopping execution, and preserving customer actions on an independent destination.
The earlier standalone database experiment used physical replication. Its timing is historical evidence, not evidence for the Stack logical-replication procedure.

The source fixture adds `SESSION_SIGNING_KEY` at runtime and resolves `PORTAL_NOTICE` from a shared project variable.
Neither value belongs in the app repository.
The application signs session hashes with the key, so preserving the key has a visible continuity check.

The [test record](../../examples/app-platform-migrations/from-coolify/test_record.md) records measured results, exact versions, and limits.
A standalone destination proves independence from Coolify.
It does not establish a complete MMX-managed deployment, production routing, real R2 authorization, backups, or alert delivery.
Use the current Stack procedure for the database move; this example does not repeat its formation-level tests.

## Inventory the source

Keep the native inventory outside Git with `umask 077`.
Record the actual production environment, not a preview environment.

| Part | Collect |
| --- | --- |
| Code and image | Repository revision, lockfile, Containerfile, deployed digest, and any Coolify build/start overrides |
| Runtime settings | Variable names, production/preview scope, build/runtime flags, literal/multiline behavior, shared references, resolved values, and signing/encryption keys |
| Database | Resource type, version, extensions, role/database names, PGDATA mount, application schema and migration ledger |
| Authentication | Stable IDs, password verifiers, session format, external identity providers, and retained identity dependencies |
| Private files | Mounts, host paths or volume names, all bytes, object keys, lengths, hashes, and owner references |
| Execution | Web and worker resources, active jobs, Scheduled Tasks, timezone, timeout, missed-run behavior, and task receipts |
| Triggers and services | Automatic deploys, previews, manual webhooks, API deploy tokens, external writers, DNS/TLS, mail, and other connectors |

Enable the Coolify API and create an export token authorized for the production resource.
Use `read` and `read:sensitive` for the inventory.
Use a separate authorized token with `write` and `deploy` when disabling execution.
Token scope and team membership still apply.
The [API documentation](https://coolify.io/docs/api/overview) explains API enablement and authentication.

From the example directory, set the instance URL, token-file path, and the recorded production resource UUIDs:

```sh
umask 077
export COOLIFY_API_URL=https://coolify.example.com/api/v1
export COOLIFY_API_TOKEN_FILE=/secure/coolify-export-token
export COOLIFY_APPLICATION_UUID=REPLACE_WITH_APPLICATION_UUID
export COOLIFY_PROJECT_UUID=REPLACE_WITH_PROJECT_UUID
export COOLIFY_ENVIRONMENT_UUID=REPLACE_WITH_PRODUCTION_ENVIRONMENT_UUID
export COOLIFY_DATABASE_UUID=REPLACE_WITH_POSTGRESQL_RESOURCE_UUID
export EXPORT_DIR=/secure/coolify-before-freeze
python3 scripts/coolify_inventory.py
```

The helper creates a new directory and saves `coolify.json` without printing responses.
The inventory includes the resource, variables, shared team/project/environment values, storage, tasks, task history, deployment history, and the selected native database resource.
Run the helper for every web and worker resource in the application boundary.

Inspect the protected responses for missing values before stopping a production service.
Ordinary `read` omits sensitive settings.
Shown-once values remain hidden even with sensitive access.
Locked and externally referenced values need their own authorized recovery route.
Preserve `SESSION_SIGNING_KEY` and any encryption keys rather than silently generating replacements.
See [environment variables](https://coolify.io/docs/applications/configuration/environment-variables) and the [environment API](https://coolify.io/docs/api/endpoints/applications/list-envs-by-application-uuid).

On the source Docker host, save protected `docker inspect` output for the actual web, worker, and database containers.
Save the generated Compose and environment files from the resource directory too.
`docker inspect` exposes runtime secrets, so redirect the output into the protected inventory.
Compare the running environment, mounts, image digest, command, health check, restart policy, and timezone against Git and the API inventory.
Export the actual repository revision through its authenticated Git host.

A Coolify instance backup protects the control plane, not the application migration.
Preserve its `/data/coolify/source/.env` and `APP_KEY` separately if retaining the instance for rollback.
The [instance-backup guide](https://coolify.io/docs/core/backup-and-recovery/instance-backup) explains why the key is required.

## Freeze and export

A read-only inventory does not require stopping the source.
For the final file handoff, pause all app mutations and background writers, disable source tasks, and drain active transactions.
Keep PostgreSQL running while the destination app is verified against the old database.

For this portal, set `controls.maintenance=true` and `controls.jobs_paused=true` through the authorized database connection.
Maintenance blocks registration, login, and other HTTP mutations.
Disable every Scheduled Task with `PATCH /applications/{uuid}/scheduled-tasks/{task_uuid}` and `{"enabled":false}`.
Re-read the tasks and wait for any active execution to finish.
Export the original frequency, command, container, timeout, timezone, and receipts before disabling execution.
Coolify's scheduler runs separately from the app container lifecycle.
See [Scheduled Tasks](https://coolify.io/docs/core/automation/scheduled-tasks/overview).

Disable `is_auto_deploy_enabled` and `is_preview_deployments_enabled` with `PATCH /applications/{uuid}`.
Rotate configured manual webhook secrets and remove obsolete Git-provider hooks.
Stop web and worker resources with `POST /applications/{uuid}/stop`.
Check both native resource state and Docker container state.
Revoke source deployment tokens after the final inventory so an old API client cannot start the resource again.
A configured restart policy must not restore source execution after a host reboot.

Run the state exporter on the source host with Node.js 24, PostgreSQL 17 client tools, and the app's pinned dependencies.
Load the database connection and upload directory from protected runtime settings.
`UPLOADS_DIR` must name the actual host-mounted directory for this command.

```sh
export EXPORT_DIR=/secure/coolify-state
node scripts/export-state.mjs
```

The exporter requires paused HTTP mutations and reports.
A PostgreSQL snapshot gives `pg_dump` and the row audit one consistent view.
The output contains `database.dump`, `table-audit.json`, `manifest.json`, and checksum-named files under `objects/`.
The file walk includes unreferenced regular files and verifies every document row against the actual bytes.
Keep native inventory, code, generated configuration, and the portable state export together in the protected migration record.

## Prepare Coolify PostgreSQL for the Stack procedure

Identify the application database resource separately from Coolify's own control-plane database.
Record the resource UUID, container, generated Compose file, published ports, persistent volume, database name, and administrator login.
For a Compose service, use that service's configuration rather than the standalone database-resource API.
Include every app and writer sharing a moving database.
The Stack fence sets each listed database's default to read-only and ends the listed app sessions.

Point `database_moving_in` at the old PostgreSQL server itself, not at PgBouncer or another pooler in front of it.
The old Coolify app can keep its pooler until the switch.
The fixture's native PostgreSQL resource uses container port `5432` directly.
If the app uses a separate pooler service, confirm the PostgreSQL container's port with `SHOW port` and use its WireGuard host mapping below.
Add the [Stack's PgBouncer](../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/add_pgbouncer.md) after the move.

Follow [Prepare the old server][prepare-old] for logical replication, publications, roles, passwords, and WireGuard.
Apply PostgreSQL settings inside the actual database container or its persistent configuration.
Preserve listeners needed by the old application.
The WireGuard address belongs to the host; PostgreSQL inside the container keeps its container-interface listener.
Start WireGuard before restarting the database container.
For a team-managed Compose database, preserve its existing volume and add the private publication in that service's source configuration.

For a native PostgreSQL resource on Coolify v4.6.0, open Configuration, then Access → Public access.
Leave Access set to **Private** and enter this value in **Port mappings**:

```text
10.20.11.1:5432:5432
```

Use the old host's actual `database_moving_in.wireguard_address` and the recorded PostgreSQL ports.
Save the resource and restart it during the procedure's preparation window.
This creates a direct Docker publication on the WireGuard address, with the original client address preserved.
Access = Private disables Coolify's Nginx proxy; the Port mappings entry still publishes a socket.
The tested bind survived a native restart and a stop/start redeployment, with the same volume and data.

The database REST update endpoint rejected both `ports_mappings` and `custom_docker_run_options` with HTTP 422 on this version.
Use the settings form to save the mapping and the read API to inventory it.
Both `-p` and `--publish` in Custom Docker options were saved but ignored when Coolify generated Compose.
The native Port mappings field supplies the direct route without enabling the public-port proxy.

Apply the Stack procedure's source restrictions on Docker's forwarding path.
For Docker's iptables backend, install this rule before publishing the port:

```sh
iptables -N COOLIFY_DATABASE_MOVING_IN
iptables -A COOLIFY_DATABASE_MOVING_IN -i wg0 -s 10.20.1.0/24 -j RETURN
iptables -A COOLIFY_DATABASE_MOVING_IN -i wg0 -s 10.20.2.0/24 -j RETURN
iptables -A COOLIFY_DATABASE_MOVING_IN -i wg0 -s 10.20.3.0/24 -j RETURN
iptables -A COOLIFY_DATABASE_MOVING_IN -j DROP
iptables -I DOCKER-USER 1 -p tcp -m conntrack --ctdir ORIGINAL \
  --ctorigdst 10.20.11.1 --ctorigdstport 5432 -j COOLIFY_DATABASE_MOVING_IN
```

Use the recorded address, host port, interface, and app/jobs/database ranges from the Stack inventory.
Create this dedicated chain once and retain the host's other firewall rules.
Persist the rule through the old host's firewall configuration before Docker starts the database.
The original-direction match preserves replies while allowing only the listed WireGuard source ranges.
Matching the original destination accounts for Docker's address translation before `DOCKER-USER`.
Keep existing source-app access and the procedure's role-specific `pg_hba.conf` rules.

After a restart or redeploy, inspect the rendered port bindings, volume, and PostgreSQL settings.
Verify that connections work through WireGuard, that `SELECT inet_client_addr()` returns the Stack peer address, and that non-WireGuard addresses refuse connections.
The test also blocked an Ethernet route directly to the private bind address and an unlisted WireGuard source.
For Docker's nftables backend, apply the equivalent forwarding restriction through the host's firewall configuration.
That backend was not exercised by this example.

Restart a standalone resource through `POST /databases/{uuid}/restart`.
For stop/start redeployment, wait for `GET /databases/{uuid}` to report `exited` before `POST /databases/{uuid}/start`.
The native API's status update can lag behind the container stopping.
For a Compose database, use its existing service manager.
Keep PostgreSQL running when stopping Coolify web and worker resources for the app handoff.

The fixture uses `portal` as its initial PostgreSQL administrator.
The Stack procedure connects as `postgres` for administration.
If that login does not exist, create it from the existing administrator session with `CREATE ROLE postgres LOGIN SUPERUSER`, then set its password as the procedure describes.
Keep `portal` as the app role name and set its password to the Stack vault's matching app database password.
The Stack destination app role is not an imported source administrator.

The fixture's tables have primary keys and use the `public` schema.
For another app, follow the procedure's checks for replica identity, extra schemas, extensions, unsupported relations, sequences, and large objects.
Freeze schema migrations during copying.
The source PostgreSQL restart, container exposure, and logical replication preparation are part of the shared procedure, not a second Coolify copy method.

## Restore files and move the app

Follow [Prepare the Stack and move the app][move-app].
Set `database_moving_in` under inventory `vars` as shown there; leave the template's default empty outside the migration.
Keep the old host outside the Stack's managed inventory groups.
Copy the current [Node database helper][node-helper] into the app unchanged before building.
It checks `transaction_read_only` for the login, so the unfinished Stack copy cannot be selected as writable.
Use the recorded source values to resolve production settings into the systems repository and vault.
Do not copy Coolify-generated service names or internal database URLs into the final destination.

Build the example's `Containerfile` and supply the values in `environment.example`.
Set `FILE_STORAGE=s3` at the destination.
The source's `FILE_STORAGE=disk` and `UPLOADS_DIR` are replaced by the destination bucket configuration.
Preserve `SESSION_SIGNING_KEY`, `PORTAL_NOTICE`, schema, IDs, object keys, and the ordered migration checksums.
Keep `COOKIE_SECURE=true` for production HTTPS.

Verify the protected export, then import files through the destination S3 API:

```sh
node scripts/verify-export.mjs
node scripts/import-objects.mjs
```

The importer downloads each imported file again and compares SHA-256.
Use a fresh destination bucket for rehearsal and a final frozen file sync for production.
File writes must have one owner while database rows still point to the copied keys.

A standalone dump/restore rehearsal can restore `database.dump` into a fresh PostgreSQL 17 database.
Pass credentials through PostgreSQL environment variables or a protected passfile.
Then run `node scripts/compare-database.mjs` before allowing destination mutations.
That optional rehearsal does not replace the database-last production sequence.

## Verify accounts and execution

Start destination web processes with workers and destination scheduling paused.
After exact row and file checks, clear `controls.maintenance` through the authorized database connection.
Keep the old web endpoint fenced before enabling destination HTTP writes.
Verify existing passwords, stable user IDs, shared sessions, owned records, wrong-owner refusals, and exact private downloads.
Check the resolved shared setting through `/healthz`.
Check a source-issued session at the destination before logging in again.
Create and retrieve a new record and file through the destination while still using the old database.

After source execution is disabled, give the destination exclusive worker and schedule ownership.
After source workers and Scheduled Tasks stop, set `controls.jobs_paused=false` through the authorized database connection.
The combined report and scheduler command is `node jobs.mjs`.
The cleanup command is `node schedule.mjs` and records at most one occurrence per UTC hour.
Coolify's fixture invokes cleanup every minute to exercise native dispatch quickly.
The destination preserves the hourly application behavior.

The combined jobs command checks for due cleanup once per minute when `controls.jobs_paused=false`.
Set `jobs_command: node jobs.mjs` in the app settings so the app owns scheduling.
The standalone `node schedule.mjs` command remains available for native source dispatch and tests.
The Stack does not import Coolify tasks automatically.
The example's [testing instructions](../../examples/app-platform-migrations/from-coolify/testing.md) cover interrupted reports, concurrent workers, and duplicate schedule attempts.

## Cut over and define rollback

Verify app traffic against the old private database before starting the database move.
Run the Stack's [copy playbook][copy-playbook] through the systems repository:

```sh
./server_management_scripts/run_mmx_on_util01 run copy_the_database_moving_in
```

Follow [Copy the database][copy-database] for readiness, replica, and retained-WAL checks.
Then use [Switch and verify][switch-database] and the Stack's [switch playbook][switch-playbook]:

```sh
./server_management_scripts/run_mmx_on_util01 run switch_to_the_database_moving_in
```

The procedure owns the write fence, final catch-up, sequences, large objects, subscription cleanup, and opening destination writes.
Keep Coolify web processes, workers, Scheduled Tasks, and deployment triggers stopped throughout that switch.
Use the procedure's measurements and continuous HTTP writer to record the actual pause.
Use its failure and recovery rules rather than reopening the old database independently.

Before destination writes, rollback can restore source execution and traffic after checking file ownership.
After destination file or database writes, rollback needs reconciliation of rows, bytes, job output, and external effects.
During the old-database stage, the database is shared but the source upload volume is already stale after a destination upload.
After the Stack accepts writes, do not reopen the old database without reconciling subsequent data.

## Retire the source

Complete the Stack procedure's backup, `database_moving_in` removal, peer/URL cleanup, and credential cleanup before retiring the source.
Keep the forwarding restriction until the source container is stopped or its private Port mappings entry is removed.
After acceptance, stop the migrated PostgreSQL resource and repeat customer actions at the destination.
For a dedicated instance, also stop Coolify and the old host.
Record any other resources retained on a shared instance.
Check for connections to the source database, source mount, source registry, and Coolify API.
Agree the recovery retention period and cleanup owner for the actual migration.

Delete only the recorded source resources after the retained rollback copy is no longer required.
Resource deletion, instance deletion, persistent volumes, backups, Git hooks, deploy tokens, and registry retention need separate decisions.
Re-list resources and inspect the host's containers, volumes, and retained mounts to verify the intended cleanup.

## Evidence

The example's [test record](../../examples/app-platform-migrations/from-coolify/test_record.md) distinguishes native source proof, standalone destination results, and untested production branches.

[database-move]: ../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md
[prepare-old]: ../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md#prepare-the-old-server
[move-app]: ../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md#prepare-the-stack-and-move-the-app
[copy-database]: ../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md#copy-the-database
[switch-database]: ../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md#switch-and-verify
[copy-playbook]: ../../skills/monkeymaxxing-stack/systems_repository_template/playbooks/copy_the_database_moving_in.yml
[switch-playbook]: ../../skills/monkeymaxxing-stack/systems_repository_template/playbooks/switch_to_the_database_moving_in.yml
[node-helper]: ../../skills/monkeymaxxing-stack/files_for_your_app/node/pg_with_multiple_database_servers.mjs
