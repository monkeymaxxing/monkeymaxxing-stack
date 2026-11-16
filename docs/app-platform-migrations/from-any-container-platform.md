# Move from a platform you run yourself

## Variances and guidance needs

Move the app and files first. Keep the old database until the new app works against the old database over WireGuard.
Then copy PostgreSQL continuously and pause writes for the final database switch.

Use the source guide for platform-specific inventory and shutdown commands.
The [Compose example](../../examples/app-platform-migrations/from-docker-compose/README.md) provides a worked migration and customer checks.
The [test record](../../examples/app-platform-migrations/from-docker-compose/test_record.md) records the live Stack boundary and external-service limits.

| Requirement | Shared route | Variation to assess |
| --- | --- | --- |
| Application | Rebuildable web image and one jobs command | Extra services, privileged containers, shared filesystems and platform APIs need an explicit disposition. |
| PostgreSQL | Keep the source available over WireGuard, then use logical replication | Managed databases and cluster-only addresses can require a different private connection or migration order. |
| Files | Convert local uploads to private object storage before moving the app | A mount cannot become a bucket without an application change. |
| Execution | One location owns workers and schedules | Controllers, deploy hooks and external callers can restart source execution. |
| Traffic | Prepare destination routing before the database switch | Cookies, callbacks, webhooks and cached DNS can keep using the old endpoint. |

The Stack owns the database move through [Move a database into the Stack](../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md).
Use that procedure's `database_moving_in` setting and copy/switch playbooks.
The source guide owns platform inventory, shutdown, file conversion and final source retirement.

## Define the boundary

Record every runtime dependency as **move**, **replace**, **retain**, or **retire**, with the reason.
For example, leaving ECS while retaining RDS and S3 leaves an AWS dependency.
Retaining an identity provider also retains that provider's account and availability requirements.

Separate code, settings and state in a protected migration inventory:

| Part | Required facts |
| --- | --- |
| Code | Revision, Dockerfile, lockfiles, build inputs, runtime versions and deployed image digest |
| Configuration | Live variable names, mounted secret/config files, secret owner and authorized transfer route |
| Accounts | Stable IDs, password-verifier algorithm, external issuer/subject, encryption keys and session-signing keys |
| PostgreSQL | Every database, schema, extension, owner, role, grant, migration ledger and version |
| Files | Mount/bucket, object key, owner link, byte length, hash, overwrite and deletion behavior |
| Work | Pending, running, delayed, failed and completed jobs, outputs and external side effects |
| Scheduling | Command, timezone, concurrency, missed-run policy, occurrence ledger and restart mechanism |
| Traffic | Domains, TLS, cookies, callbacks, webhooks, proxy headers and required timeouts |

Save secret values through the authorized protected route. Record names and checksums in public evidence, never values or password verifiers.
Keep runtime secrets separate from image-build credentials.
A code archive, database backup and file export are separate artifacts.

## Check the application contract

Use the [Stack checklist](../../skills/monkeymaxxing-stack/systems_repository_template/monkeymaxxing_stack_checklist.yml) and the actual application settings.
The destination image must honor `PORT`, provide a health check, drain requests on shutdown and log to standard output.
Sessions must work across app servers. Mutable state belongs in PostgreSQL and object storage.

Provide separate web, migration and jobs commands. Preserve durable queue state in PostgreSQL.
Apply additive schema changes that keep the previous release usable. Retain previous-release assets during deployment.
New database connections must find the writable primary through the Stack database URL.

Record requirements with no direct Stack equivalent before selecting the migration boundary.
Examples include Kubernetes operators, IAM task identity, a Redis queue, SQS, shared writable disks and multi-zone placement.
Choose the adaptation or retained service before copying data.

## Prepare the destination beside the source

Build the destination through the [Stack setup](../../skills/monkeymaxxing-stack/SKILL.md).
Record the Stack revision, application image digest and selected versions.
Prepare the hostname, tunnel, TLS and empty destination database before the final database pause.
Keep destination workers and schedules paused.

Place the new servers close to the old database, preferably in the same region.
Measure real page latency over the private connection. Every query crosses that connection until the database moves.
A page with twenty sequential queries incurs roughly one second of network delay at a 50 ms round trip.

Follow the Stack procedure to enroll the old database as an unmanaged WireGuard peer and prepare database authentication.
Keep the old host outside the Stack's managed server groups.
A container database must publish PostgreSQL on the source WireGuard address, with source restrictions that include Docker's forwarding rules.

## Convert and transfer uploads

Change the application storage interface before replacing a disk mount with a bucket.
Preserve document IDs, owner links and storage keys where practical.
Pre-copy bytes while the source serves traffic, then freeze upload mutations for the final pass.
Check final document keys, lengths and hashes against the destination bytes.

Account for overwritten and deleted files between passes. A successful copy does not prove the final object set.
List unreferenced files separately and decide whether each file must be retained.
Check authenticated downloads and guessed-ID refusal through the destination app.
Verify real bucket permissions separately from an S3-compatible emulator.

Switch file ownership together with app execution. Once the destination accepts uploads, the source filesystem becomes stale.
Rollback after that point includes reconciling file changes, even while the database still lives on the old host.

## Move app execution before the database

Disable source schedules and deployment triggers. Drain source workers and stop source web mutations.
Wait for active jobs and requests to finish, then make the final upload pass.
Start the destination app against the old database over WireGuard.
Keep the old web endpoint unable to accept mutations while cached DNS drains.

Use real customer actions to verify returning users, stable IDs, CRUD, ownership, private bytes and queued reports.
Verify an interrupted job and a worker restart. A retry must not duplicate a customer-visible side effect.
Enable destination workers only after source workers are stopped.
Enable destination scheduling only after the source scheduler cannot restart.

Prefer the framework's scheduler inside the jobs command when available.
For an external one-shot command, record a systemd timer through the systems repository and MMX.
Record `OnCalendar`, timezone, `Persistent`, concurrency and the application's occurrence key.
The Stack has no generic cron importer. Copying a cron line does not establish exclusive execution.

## Move PostgreSQL through the Stack procedure

Follow [Move a database into the Stack](../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md) after the app works on the Stack against the old database.
That procedure owns source preparation, version compatibility, schema copying, replication, fencing, sequences, large objects, switch recovery and cleanup.
Do not substitute a separate restore or hand-written subscription procedure.

For the container-platform migration, supply the facts the Stack procedure needs:

- The actual PostgreSQL version, database/login names, extensions, owner/grantee roles and additional state outside ordinary tables.
- The old cluster's service manager and safe restart command. A Compose PostgreSQL service restarts through Compose.
- Every application sharing a moving database, because the final source fence changes each listed database's default to read-only.
  The switch ends the listed app sessions and, for relay moves, disables and kills the relay's app entries.
- Every writer and schema-migration trigger, including workers, schedules, CI and external tools.
- The old host's WireGuard address and the container's published PostgreSQL port.
- A protected route for the existing app and administrator credentials and the dedicated replication credential.

Point `database_moving_in` at the old Postgres itself, not at PgBouncer or another pooler in front of it; a pooler can defeat the read-only fence.
The old platform can keep its pooler until the switch.
Add the Stack's PgBouncer after the move, following [Add PgBouncer](../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/add_pgbouncer.md).

Keep the old app's network listeners until the app handoff finishes.
Publish the container database on WireGuard without making PostgreSQL public.
Set the source's application login password to the matching Stack vault value, as the Stack procedure requires.
For Node.js, copy the current Stack database helper before rebuilding the image. The helper must check login writability.

The Stack creates its normal primary/replica formation. `copy_the_database_moving_in` loads the empty app database and starts logical replication.
Keep schema migrations paused during copying and wait for every table to become ready.
The shared procedure's source disk/WAL monitoring still matters when PostgreSQL runs inside a container volume.

Keep a customer HTTP writer running through `switch_to_the_database_moving_in`.
Record each acknowledged identifier and response time, then find every acknowledged row on the primary and replica.
Record failed requests separately. Do not retry uncertain writes automatically.
Compare web/jobs container start times before and after the switch.

Record the Stack command's pause parts separately from the customer-visible write interruption.
A running replication worker alone does not prove catch-up or zero lost acknowledged writes.
After the switch, follow the Stack procedure for backup, removal of the temporary setting/peers/credentials, and old-system power-off.
Repeat returning-user, file, ownership and new-write checks with the old system stopped.

## Cutover and rollback

There are two state changes: moving app/files/execution, then moving the database.
Before destination writes, return traffic to the preserved source and deliberately restore source execution if verification fails.
After destination writes, reconcile files, database changes and external side effects before returning traffic.

Sharing the old database during the first stage avoids a database fork, but does not keep the old upload mount current.
After the database switch, the source database is stale too.
A one-way subscription does not provide automatic reverse replication or failback.

Check the actual public hostname, callbacks, cookies, webhooks, proxy headers and upload URLs.
Keep the old address fenced throughout the DNS-cache interval.
Record the agreed retention period and cleanup owner in the migration brief.

## Prove operation and retire the source

Verify app/database health, backup enrollment, restored application data and an alert reaching the intended person.
Use the Stack checklist for the established backup, restore, monitoring and urgent alert checks.
Retain a required historical log/tracing service explicitly rather than assuming operational monitoring replaces historical search.

Follow the Stack database-move procedure to remove migration publication, credentials and temporary network access after acceptance.
Delete only inventoried source resources. Re-list servers, disks, buckets, schedules and deployment triggers to verify absence.
List retained backups and dependencies, with their retention and cleanup owner.

## Evidence

Record source/tool versions, image digests, Stack revision, dataset bytes, commands, failures, exact checks and write-pause measurements.
Separate standalone rehearsal, live Stack cutover, real object-provider permissions and fresh-reader replay.
Reuse existing framework/Stack proof where behavior and versions match. Repeat checks only for a changed interaction.
Source-specific guides add native inventory and shutdown details without repeating this procedure.
