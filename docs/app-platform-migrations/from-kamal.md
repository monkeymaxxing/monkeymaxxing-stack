# Move a Kamal app to your own system

## Variances and guidance needs

This guide covers a Rails 8 app already using PostgreSQL and private S3-compatible storage.
Move the app, workers, and scheduling first. Keep PostgreSQL on the source host until the destination app passes customer checks.
Move PostgreSQL only by logical replication through [Move a database into the Stack][database-move].
SQLite conversion is outside this guide.

Use [the shared container migration procedure](from-any-container-platform.md) for common inventory, file transfer, and traffic cutover.
The Stack database procedure owns database preparation, copying, fencing, switching, and cleanup.
The [copyable example](../../examples/app-platform-migrations/from-kamal/README.md) adds Kamal-specific source configuration and Rails destination checks.

| Kamal difference | Guidance and example coverage |
| --- | --- |
| Base configuration plus `-d production` | Inventory the resolved destination, role commands, hooks, image and runtime settings. |
| Common and destination secrets | `.kamal/secrets-common` loads before `.kamal/secrets.production`. Destination values override common values. `.kamal/secrets` is not selected. |
| PostgreSQL accessory | Preserve the actual database, users, extensions, storage, and rows. Accessory YAML is no database export. |
| Separate worker and clock roles | Stop both roles and the automation that can deploy or restart each role. Run one destination jobs command. |
| Rails fixed-port defaults | The example uses Puma directly and honors `PORT`. Inventory Thruster and fixed listeners in an incoming app. |
| Release asset bridging | Preserve fingerprinted Propshaft CSS through `/app/public/assets`, including files referenced by an old page. |
| Existing Rails accounts and queues | Keep bcrypt verifiers, IDs, ownership, sessions, report state, and Rails migration versions unchanged. |
| An unmanaged source database | Set `database_moving_in` for the accessory host. Keep the old host outside Stack inventory nodes and groups. |

Kamal documents [destination secret precedence](https://kamal-deploy.org/docs/configuration/environment-variables/),
[separate accessory management](https://kamal-deploy.org/docs/configuration/accessories/), and [role commands](https://kamal-deploy.org/docs/configuration/roles/).
A normal app deploy does not update accessories.

## What the example proves

The [test record](../../examples/app-platform-migrations/from-kamal/test_record.md) is the authority for executed checks and exact versions.
The tested source used Kamal 2.12.0, Rails 8.1.4, PostgreSQL 17, separate web/worker/clock roles, and a PostgreSQL accessory.
The destination passed returning sessions/passwords, stable IDs, owner checks, private bytes, reports, scheduling, and release assets.
The source VM was stopped before final destination checks.
PostgreSQL replication carried 75 HTTP writes made after copying began.
The earlier standalone rehearsal measured 10.494 seconds with stopped/restarted containers. That result does not measure the Stack switch playbook.
The destination uses the existing Rails portal contract and its private object storage interface.

The example keeps the PostgreSQL schema rather than translating identities or queue rows.
The added `schedule_runs` table records one daily UTC session-cleanup occurrence.
The queue completion and schedule receipt each commit with their associated changes.

Use the supported [Stack database procedure][database-move] for the production migration.
The Rails app uses native libpq writable-login selection and carries no Node database helper.

## Collect the source facts

Record the source code revision, dependency lockfile, Containerfile, release tag, image digest, and selected Kamal destination.
Keep the resolved inventory and secret values in protected storage outside Git.

| Part | Inventory |
| --- | --- |
| Deployment | `config/deploy.yml`, `config/deploy.production.yml`, `.kamal/hooks/`, aliases, registry, SSH targets and release automation |
| Roles | Every host, command, health check, proxy setting, restart policy and stop timeout for web, worker and schedule roles |
| Secrets | Common/destination files, substitution commands, secret-manager owners, encryption keys and authorized value-transfer route |
| PostgreSQL | Accessory host, actual image/version, bind address, mount, database names, roles/grants, extensions, large objects and Rails migration versions |
| Accounts | Account IDs, password-verifier format, session behavior and any external identity-provider dependency |
| Objects | Bucket, current keys, referenced owners, lengths, hashes, version retention and private-download behavior |
| Execution | Pending/running/completed reports, output, clock command, timezone, missed-run rule and occurrence ledger |
| External writers | Cron, CI, deploy hooks, administrative scripts, integrations and webhooks that can mutate state or restart execution |

For the production destination, run these commands from the source app directory:

```sh
umask 077
kamal version
kamal app details -d production > /secure/kamal/app-details.txt
kamal accessory details postgres -d production > /secure/kamal/postgres-details.txt
```

Create `/secure/kamal` with private permissions first, or use your protected export directory.
These commands inspect live containers. Preserve destination YAML and hooks separately.
Avoid printing `kamal config` or secret-file contents into a shared log.
Resolve authorized secret values directly into the destination vault.
Preserve Rails signing/encryption keys needed by existing data or cookies.
Separate registry/build credentials from runtime secrets.

The [Kamal environment documentation](https://kamal-deploy.org/docs/configuration/environment-variables/) describes substitution and aliases.
A placeholder such as `$PRODUCTION_SECRET_KEY_BASE` is not the value to store in the destination vault.
Re-run secret resolution for the selected destination, then verify names and successful application behavior without printing values.

## Freeze and export

Rehearse on the populated synthetic source before freezing production.
A source code archive contains no PostgreSQL rows or private file bytes.
Keep a protected database backup and independent object copy even when continuous replication is the cutover method.

Freeze schema changes before creating the destination schema and starting replication.
Keep the source database running throughout the app-first stage.
Pre-copy private objects, stop upload mutations for the final object pass, and compare every referenced key and hash.
The example's [object transfer command](../../examples/app-platform-migrations/from-kamal/app/scripts/transfer_objects.rb) exports all current keys and preserves document references.

At the app handoff, pause deployment triggers, host schedules, and hooks that can restart source app execution.
Drain active report transactions and stop worker and clock roles before enabling destination jobs:

```sh
kamal app stop --roles worker,clock -d production
kamal app details --roles worker,clock -d production > /secure/kamal/execution-stopped.txt
```

Stop source web execution when the destination becomes the only web writer.
A Docker restart policy can restart a source container after a host reboot, so verify stopped state after restart-policy or deployment-trigger changes.
Do not stop or remove the PostgreSQL accessory at the app handoff.

The final database pause happens later, after customer actions pass against the old database.
Leave Stack web and jobs containers running during the switch, as [the database procedure][database-move] requires.
Disable source administration scripts and outside writers that explicitly request writable transactions.

## Restore on Linux

Follow [the Rails integration guide](../app-frameworks/rails-pg.md) for settings, assets, driver configuration, image builds, and app registration.
Keep the three existing migration versions, `jobs_command: bin/migration-jobs`, and `asset_directory: /app/public/assets`.
Freeze schema changes throughout the copy. The source role commands run migrations, so keep Kamal redeploy triggers disabled.

Prepare the accessory host using [Prepare the old server][database-move].

Point `database_moving_in` at the PostgreSQL accessory itself, not at PgBouncer or another pooler in front of PostgreSQL.
Find the direct published Postgres port in `accessories.postgres.port` in the selected Kamal configuration.
A pooler between the Stack apps and old PostgreSQL defeats the read-only fence.
The old deployment can keep its pooler until the switch.
Add the Stack's PgBouncer after the move, following [Add PgBouncer](../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/add_pgbouncer.md).

Bind the accessory's published PostgreSQL port to the old host's WireGuard address, matching `database_moving_in.postgres_port`.
In this fixture, `SOURCE_DATABASE_BIND` supplies that address and the container listens on port 5432.
The WireGuard address belongs to the host, not the bridge-network container.
Keep PostgreSQL's container listener at `listen_addresses = '*'`; do not copy the procedure's host listener addresses into the container.
Apply source restrictions to Docker-published traffic as well as the host firewall. Keep public PostgreSQL closed.
The source host joins WireGuard; the database container does not become a Stack inventory node.

Enter the actual running accessory's administrator session on its host:

```sh
docker exec -it migration-portal-postgres psql -X -U portal -d portal
```

The fixture's `POSTGRES_USER=portal` makes `portal` the initial administrator.
If the accessory has no `postgres` role, create the administrator login expected by the Stack procedure:

```sql
CREATE ROLE postgres LOGIN SUPERUSER;
\password postgres
```

Reconnect as `postgres` and verify administrator access before demoting the fixture's application role:

```sql
\connect portal postgres
SELECT current_user, rolsuper FROM pg_roles WHERE rolname = current_user;
ALTER ROLE portal NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
```

For an existing accessory, substitute the actual bootstrap administrator in the initial `docker exec` command.
The Stack administrator login must still be named `postgres`.
Changing `POSTGRES_USER` or `POSTGRES_PASSWORD` in accessory YAML does not update roles in an existing data directory.
Use `SHOW config_file` and `SHOW hba_file` to locate settings in the recorded persistent accessory mount.
Continue the procedure's role grants, passwords, publication, `pg_hba.conf`, and source PostgreSQL settings inside this accessory.
Keep the selected Kamal destination's protected connection/password references consistent with the matching Stack vault password.
The fixture's database name and application role are `portal`; use `portal` wherever the procedure uses `shop`.
The Stack app entry must have `database_name: portal` and matching vault credentials.

The fixture enables logical WAL, four slots/senders, and the procedure's four-second `wal_sender_timeout`.
Check slot/sender capacity using the Stack procedure.
Changed port publishing or command settings require recreating the accessory, rather than only restarting PostgreSQL.
Use `kamal accessory reboot postgres -d production` in the agreed maintenance window, retaining the recorded data mount.
An accessory reboot interrupts its database; normal app deployment does not update the accessory.

The Stack fence sets each moving database's default to read-only and ends the listed app sessions.
Include every app and writer sharing a moving database.
Check role/database read-only overrides and explicit writable transactions using [Switch and verify][database-move].
The Rails example uses ordinary transactions and libpq `target_session_attrs=read-write`.
The fixture uses PostgreSQL 17 and no large objects. The procedure owns large-object handling and other source compatibility limits.

Import private objects into the destination bucket using the example's separate object-transfer command.
Set `database_moving_in` in the systems inventory and complete the procedure's app-first `every_server` run.
Verify customer actions against the old database before copying.
Run the Stack's [copy playbook][database-copy] and [switch playbook][database-switch] exactly as the procedure describes.
There is no separate Kamal database copy or switch command.

## Verify accounts and execution

Run the [returning-user check](../../examples/app-platform-migrations/from-kamal/tests/check_migrated.py) against the destination before and after the database switch.
Returning users must log in with the original password and retain record, document, and report IDs.
Verify foreign-owner refusal, exact private downloads, fresh writes, and completed report output.

Reuse [the Rails destination checks](../app-frameworks/rails-pg.md#seed-switch-restore-and-roll-back) for cross-server sessions, worker interruption, primary selection, and release assets.
Run destructive fixture checks on a disposable copy.
The source-specific test must separately show stopped Kamal workers and clock roles.

For scheduling, preserve UTC timezone, one daily occurrence, transactional receipts, and the missed-run policy.
Run two overlapping schedule commands and verify one receipt and the expected expired-session count.
Restart destination jobs and verify the completed occurrence stays completed.
Keep all source schedule triggers disabled.

Save a page from the old release, deploy changed CSS, and fetch the old CSS URL through the destination.
Compare bytes and content type. Save a record from the old page without reloading.
The portal's single page does not exercise lazy navigation or additional frontend asset types.

After moving PostgreSQL, stop the source accessory and repeat customer actions.
Prove the destination works while the source host is stopped.
A retained source bucket or database address means that source dependency still exists.

## Cut over and define rollback

Prepare routing and TLS through the shared procedure before directing production traffic to the destination.
The app-first stage keeps one PostgreSQL database, so returning web execution can still use current database rows.
Returning execution also requires restoring the selected file-store settings and preserving newly written objects.
Pause jobs during any execution handoff so pending work has one owner.

Follow [Switch and verify][database-move] for the write fence, failure recovery, measurements, and rollback boundaries.
Keep an HTTP writer running through the switch and verify every acknowledged identifier afterward.
The procedure retains the generated URLs and reconnects drivers without restarting app containers.
Use MMX's pause measurements together with actual HTTP recovery time.

Do not start Kamal web, worker, or clock roles as a rollback shortcut.
After Stack writes begin, returning to the accessory requires reconciling rows, files, job outputs, and schedule receipts.

## Retire the source

Complete the database procedure's backup, temporary-peer removal, and source-off customer checks first.
After acceptance and the agreed retention period, remove the recorded Kamal app containers, accessory container, and PostgreSQL storage.
Keep the source export and source code for the named recovery step.
Remove obsolete hooks, CI deploy credentials, cron entries, proxy routes, and temporary WireGuard access.
Revoke source-only runtime and registry credentials after confirming no retained integration needs those credentials.

Kamal accessory removal can remove persistent storage when explicitly requested.
Review the recorded mount before removing accessory directories.
Re-list Docker containers, volumes, host directories, schedules, and retained object storage to verify cleanup.
Deleting the web container alone leaves accessories and their data behind.

## Evidence

Read [test_record.md](../../examples/app-platform-migrations/from-kamal/test_record.md) for versions, commands, checks, timing, failures, and untested branches.
The shared Stack checks and a fresh independent replay require their own recorded results.
An isolated private-IP rehearsal does not prove public routing, bucket authorization, alert delivery, or the Stack backup chain.

[database-move]: ../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md
[database-copy]: ../../skills/monkeymaxxing-stack/systems_repository_template/playbooks/copy_the_database_moving_in.yml
[database-switch]: ../../skills/monkeymaxxing-stack/systems_repository_template/playbooks/switch_to_the_database_moving_in.yml
