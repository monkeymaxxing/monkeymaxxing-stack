# Move a Docker Compose app to your own system

## Variances and guidance needs

Move a team-owned Compose app to the Stack while preserving accounts, private uploads and background work.
Follow the [shared container procedure](from-any-container-platform.md) for the app contract, database-last replication and cutover.
This guide adds the Compose inventory and shutdown commands.

| Compose source behavior | Migration guidance | Example coverage |
| --- | --- | --- |
| Base file plus production override | Resolve the exact file order, project name, profiles and interpolation inputs | Explicit `compose.yaml` and `compose.production.yaml` |
| Secret files | Read actual mounted values through the authorized protected route | A database URL mounted under `/run/secrets` |
| PostgreSQL named volume | Replicate through PostgreSQL rather than copying a live data directory | PostgreSQL 15 → Stack PostgreSQL 17, with a 3 GiB fixture |
| Private uploads in a bind mount | Convert the storage interface, copy bytes and check owner links | Local files become private S3-compatible objects |
| Worker with a restart policy | Stop the service and remove its restart/deployment authority | PostgreSQL queue with pending reports |
| Host systemd timer | Inventory outside Compose and disable the timer before handing off execution | Hourly expired-session cleanup with an occurrence ledger |
| Source container DNS names | Replace `postgres:5432` with the supported destination database connection | Stack app uses the old database over WireGuard |

The example targets web apps using PostgreSQL and application-owned accounts.
Arbitrary Compose graphs, privileged workloads and databases other than PostgreSQL need separate adaptation.

## What the example proves

The [example](../../examples/app-platform-migrations/from-docker-compose/README.md) reuses the existing portal's account, ownership and queue behavior.
The source runs Docker Compose on a Linux server, with a production override, mounted secret files, a database volume and local uploads.
The destination uses the normal Stack app services and primary/replica formation, with S3-compatible lab storage.
The [test record](../../examples/app-platform-migrations/from-docker-compose/test_record.md) states measured results and remaining limits.

The Stack database move uses its [native operating procedure](../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md).
The test record distinguishes the live Stack checks from standalone and external-service evidence.

## Inventory the running source

Find the command production actually runs before resolving configuration.
Record all `-f` files in order, `--project-name`, `--profile`, `--env-file`, working directory and interpolation variable names.
A production override can change commands, mounts and restart behavior absent from the base file.

Run the recorded command's configuration and inventory operations in a protected directory:

```sh
umask 077
mkdir -p /secure/compose-export
docker compose -f compose.yaml -f compose.production.yaml config \
  > /secure/compose-export/resolved-production.yaml
docker compose -f compose.yaml -f compose.production.yaml ps --all --format json \
  > /secure/compose-export/containers.json
docker compose -f compose.yaml -f compose.production.yaml images --format json \
  > /secure/compose-export/images.json
```

Use the real production invocation, including project, profiles and environment-file options.
`docker compose config` merges files and resolves interpolation. The output can expose secret values. [Docker reference](https://docs.docker.com/reference/cli/docker/compose/config/)

Inspect each recorded container ID and save the full result privately:

```sh
docker inspect RECORDED_CONTAINER_ID > /secure/compose-export/container-inspect.json
docker volume inspect RECORDED_VOLUME_NAME > /secure/compose-export/volume-inspect.json
systemctl list-timers --all > /secure/compose-export/host-timers.txt
crontab -l > /secure/compose-export/user-crontab.txt
```

Repeat for every container and volume with separate filenames.
Record bind-mount source paths, named-volume identities, file owners and restart policies.
Inspect system timers, cron directories, CI deploys, webhooks and external writers outside Compose.
The example's `portal-session-cleanup.timer` is not listed in `compose.yaml`.

Record secret names, mounted destinations and the protected transfer route.
An environment variable containing `/run/secrets/database_url` is a filename, not the database URL.
Preserve session/encryption keys needed by returning users and existing encrypted data.

Save the source revision and image digest separately. Preserve Dockerfiles, lockfiles, migrations, overrides and host timer units.
A database volume's name establishes neither its consistency nor the contents of an application export.

## Freeze and export

Rehearse first without stopping a production app.
For the real app/files handoff, stop source mutations, drain requests and jobs, then disable every source executor.
For the example host schedule and services:

```sh
systemctl disable --now portal-session-cleanup.timer
systemctl stop portal-session-cleanup.service
docker compose -f compose.yaml -f compose.production.yaml stop worker web
systemctl show portal-session-cleanup.timer -p ActiveState -p UnitFileState
docker compose -f compose.yaml -f compose.production.yaml ps --all
```

The example uses `restart: unless-stopped`. A deployment command can still recreate stopped services.
Disable CI, host service units and deploy hooks that can run `compose up` too.
Check pending/running jobs and active database sessions before declaring source execution stopped.
Leave the PostgreSQL service and volume running for the database-last stage.
Do not use `down --volumes` as a migration step.

Take an independent protected database export and final file manifest for recovery.
Use the shared procedure for replication. Keep the database available to the new app through WireGuard.
Pre-copy local uploads, stop upload mutations for the final pass, and verify final byte hashes and owner links.

## Restore on Linux

Build the Stack beside the existing Compose server, following the Stack setup.
Adapt the application before deploying: settings from environment variables, standard-output logs, shared sessions and no mutable upload mount.
Move workers to the single jobs command. Record the hourly one-shot command through MMX if the app has no scheduler.

The example's `UPLOADS_DIR` selects local-file storage only at the source.
Omit `UPLOADS_DIR` at the destination and supply private S3-compatible storage settings.
`file-secrets.mjs` loads the source `DATABASE_URL_FILE`; the Stack supplies `DATABASE_URL` directly.
The [upload copier](../../examples/app-platform-migrations/from-docker-compose/scripts/copy-uploads.mjs) retains keys and verifies downloaded destination bytes.
The copier refuses existing objects with different bytes.
Inventory orphaned local files separately because the copier follows the document table.

Point `database_moving_in` at the old Compose PostgreSQL service itself, not at a PgBouncer service or another pooler in front of it; a pooler can defeat the read-only fence.
Find the PostgreSQL service's published port in the resolved production Compose configuration and container port mappings.
In this example, the `postgres` service's container port 5432 is published on the source WireGuard address at port 5432.
Use that address and port, rather than a pooler's listener. Existing source services can keep their pooler until the switch.
Add the Stack's PgBouncer after the move, following [Add PgBouncer](../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/add_pgbouncer.md).

For the database-last route, point all destination processes at the old database using supported Stack configuration.
Keep source execution stopped, then verify the destination app against the old database.
Complete replication and the final database switch through the shared procedure.
Use `database_moving_in`, `copy_the_database_moving_in` and `switch_to_the_database_moving_in` from that Stack procedure.
Copy the current Node database helper before rebuilding; the helper checks whether the login can write.

## Verify accounts and execution

Check returning passwords, stable user IDs, original record IDs, owner links and private downloaded bytes.
Try record, document and report IDs as the wrong user.
Create, edit and delete a record. Upload and download a new private document.
Verify logout revokes the session.

Retain pending reports, completed output and schema-migration checksums.
Interrupt an actual worker transaction and verify unfinished work remains pending.
Run concurrent workers and verify each report completes once with owner-specific output.
Restart scheduling and verify a repeated occurrence does not run twice.

Run the [example checks](../../examples/app-platform-migrations/from-docker-compose/README.md#replay) only against the disposable fixture.
The checks create sessions, records and files.

## Cut over and define rollback

Prepare destination routing before either execution handoff.
Record the app/files pause separately from the final database write pause.
Test the actual public hostname and keep the old endpoint unable to accept mutations while DNS caches drain.

Before destination writes, restore source routing and execution deliberately if needed.
After destination writes, reconcile new objects and external side effects before returning to the source app.
After the database switch, source rows are stale too.
Preserve the source database and uploads for the agreed recovery period, with a named cleanup owner.

## Retire the source

After acceptance, remove replication slots, publication, temporary credentials and temporary network access.
Verify a fresh source slot listing before retiring PostgreSQL.
Stop and remove only the inventoried Compose services and the recorded project volume.
Archive the disabled host timer units and remove obsolete deployment authority.

Re-list containers, volumes, host timers and source ports.
Record retained snapshots, independent exports and their cleanup owner.
Removing a Compose project does not remove an unrelated bind-mount directory or an external database.

## Evidence

See the [test record](../../examples/app-platform-migrations/from-docker-compose/test_record.md) for versions, commands, dataset size, failures and measured results.
The [Stack procedure](../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md) owns database replication and switching.
The shared guide owns the container migration contract and execution handoff.
Source-specific scripts and config remain in this example so the build does not depend on another platform directory.
