# Private RDS through the Stack's managed relay

Move the app, private files, jobs and scheduling first. Keep RDS authoritative until the Stack's logical-replication switch completes.
Use the Stack procedure [Move a database into the Stack](../../../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md), especially **An old database behind a provider network**.
That procedure owns relay configuration, source grants, readiness, fencing, rollback and cleanup.
The native RDS move exercised this managed path on the Stack. The [test record](../test_record.md) records the managed measurements separately from the earlier standalone run.

## Prepare RDS and the relay

Keep RDS non-public. Create a temporary Debian 13 relay in its VPC, with a small instance and an auto-delete root volume.
Record its instance, volume, interface, security-group and imported public-key IDs outside Git.
Tag every taggable resource `project=ecs-migration-example`; name custom roles `portal-ecs-*`.
Allow relay SSH only from the operator and WireGuard UDP 443 from the Stack servers that need the database.
Allow RDS TCP 5432 from the relay security group.

Install PgBouncer **1.26.1 or newer from PostgreSQL's apt repository**, using the signing-key verification and exact configuration in the Stack procedure.
The distribution's older PgBouncer does not meet the migration startup-parameter contract.
The relay listens only on its WireGuard address and opens verified-TLS connections directly to the actual RDS PostgreSQL hostname.
This relay is the old-PostgreSQL endpoint presented to the Stack. Do not place another pooler between it and RDS.
No VPC forwarding, source NAT or source/destination-check exception is needed: PgBouncer opens the outgoing connections.

For database `portal`, configure three database entries:

- `portal`: the app entry, pointing directly to RDS database `portal`.
- The derived `database_moving_in_` copy entry for `portal`, pointing to the same RDS database.
- `postgres`: cluster-administrator queries against RDS database `postgres`.

Derive the copy-entry name with the Stack procedure's SHA-256 command; do not substitute the app entry or add a wildcard.
Keep session pooling, `track_extra_parameters = lock_timeout, statement_timeout, idle_in_transaction_session_timeout`, `server_tls_sslmode = verify-full` and the provider CA bundle.
The Portal pool sends statement and idle-transaction timeouts as startup settings. Track both along with the Stack migration lock guard; do not ignore them. Verify that subsequent clients without those settings return to their prior defaults on the reused backend. The tested RDS idle-transaction default was one day, not zero.
The user list contains `portal`, `postgres`, `database_moving_in_replication` and the PgBouncer-only console login `database_moving_in_relay_admin`.
The console login is not a PostgreSQL role. It has its own generated password.

The revised synthetic source has separate Secrets Manager values for the `postgres` RDS administrator and the `portal` app login.
The [source bootstrap](README.md#prepare-the-managed-source-logins) creates the app owner, source grants and `database_moving_in FOR ALL TABLES` publication.
RDS uses `rds_replication` for the replication login instead of native `REPLICATION`.
Set `rds.logical_replication=1` and `wal_sender_timeout=4000` milliseconds, and verify parameter application before copying.
Inventory extensions, ownership, grants, sequences, large objects and row security. Resolve unsupported objects before copying.

## Configure the Stack and move the app

Copy the current Stack Node helper into the app unchanged and rebuild its image.
Its writable-server check must inspect `transaction_read_only`, including the unfinished Stack roles' read-only defaults.
Use the normal Stack `DATABASE_URL`; keep TLS URL settings unchanged because the Stack-to-relay connection is already encrypted by WireGuard.
Only the relay's connection to RDS uses provider TLS.

Set these source credentials in the systems repository's vault without printing them:

```sh
mmx secrets set portal_database_password
mmx secrets set database_moving_in_replication_password
mmx secrets set database_moving_in_superuser_password
mmx secrets set database_moving_in_relay_admin_password
```

The app password must match RDS `portal`; the superuser vault key holds the permitted RDS administrator `postgres` password.
Add the relay under inventory `vars`, outside managed `nodes` and groups:

```yaml
database_moving_in:
  wireguard_address: 10.20.11.1
  wireguard_public_key: REPLACE_WITH_RELAY_PUBLIC_KEY
  public_ipv4_address: 203.0.113.50
  postgres_port: 5432
  copy_onto: db01
  apps: [portal]
  through_relay: true
```

Use the actual app key under `apps`; the example above names it `portal` and its database `portal`.
Use the actual relay addresses/key, and keep its WireGuard address in `private_ip_ranges.database_moving_in`, outside other role ranges.
Keep db01/db02 in `database_servers`; the relay is never a managed database server.
Keep `apps_connect_through_pgbouncer.production: false` during the move. This setting concerns a separate Stack pooler, not the source relay.
Configure independent destination object storage and `QUEUE_BACKEND=postgres`, with no source queue URL or task credentials.

Before enabling Stack execution, freeze and export the source, disable native launchers, and prove ECS services/tasks stopped as in the migration guide.
Import and verify private object bytes. The SQL archive is a recovery/replay artifact: do not restore it into the Stack formation.
Synchronize the systems repository through its normal process, then run:

```sh
./server_management_scripts/run_mmx_on_util01 run every_server
```

The Stack renders the relay first in normal URLs, holds its new app roles read-only, and temporarily uses the primary for reads.
The first app setup still invokes `migration_command`. Use the already-applied source image and verify its migration checksums before starting it; this fixture had no pending migration. Run no schema change during logical copy or catch-up.
Resume the fixture's SQL controls through the old database only after Stack execution owns reports and schedules.
Check returning passwords, ownership, downloads, uploads, queued work and cross-process logout through the managed Stack app while RDS remains authoritative.
Before copying, perform the procedure's **warm app pool fence probe**: `DISABLE portal` then `KILL portal` must close existing clients and refuse new ones, while the separate copy entry stays reachable.
Restore the source default and `ENABLE`/`RESUME` the app entry after that probe.

## Copy, switch and verify

Hold DDL changes and keep an HTTP writer running through the managed app.
Save every acknowledged write's complete returned row and timestamp, not only its UUID.
Capture app/jobs container start times before switching.

```sh
./server_management_scripts/run_mmx_on_util01 run copy_the_database_moving_in
```

The Stack loads schema into empty destination databases and starts its postgres-owned logical subscription; do not create a second manual subscription.
Require every relation ready and the subscription streaming. Verify db02 receives the copy through physical replication.
Check retained WAL and source disk while waiting.
Reset source role/database read-only overrides as required by the operating procedure, then switch. With `through_relay: true`, the playbook runs its relay fleet stage:

```sh
./server_management_scripts/run_mmx_on_util01 run switch_to_the_database_moving_in
./server_management_scripts/run_mmx_on_util01 results --node db01 \
  --fleet-stage switch_to_the_database_moving_in_through_relay --json
```

The switch disables and kills relay app entries before fencing RDS, preserving copy/admin entries for catch-up.
It checks durable replay, copies sequences and large objects, opens Stack roles and removes subscriptions/slots with the procedure's rollback boundaries.
Drivers reconnect through unchanged URLs. Both web and continuous jobs code must tolerate the brief interval when no database is writable. This example retries database availability errors on its next jobs cycle; a one-shot job and other errors still fail visibly. Do not stop or restart containers as a migration step.
Keep source execution stopped and successful relay app entries disabled.

Measure actual HTTP recovery separately from the command's pause parts.
Require no old write after the relay fence and an exact full-row match for every acknowledged write on db01 and db02, including timestamp precision.
Check both original customer accounts, private bytes, new CRUD/uploads, reports, session revocation, migration history and unchanged container start times.
Require no destination subscription or source migration slot left, and a successful Stack full backup before retirement.
Do not reopen RDS after the Stack has accepted writes; rollback then needs another freeze and reconciliation.

## Retire the temporary path

Remove `database_moving_in` before another `every_server` run, or that run would restore the move's read-only role defaults.
Synchronize and run `every_server`; verify the old URL entry and WireGuard peer disappeared and replica-preferring reads returned.
Remove the relay-to-RDS ingress, terminate the recorded relay, confirm its auto-delete disk is gone, and delete its dedicated security group/key pair.
Retire the accepted AWS source by recorded IDs and fresh lists as described in [source cleanup](README.md#cleanup-by-recorded-identity).
