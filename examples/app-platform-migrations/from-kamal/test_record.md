# Variances and guidance needs

The native Kamal source and standalone database-last migration passed on 2026-11-05 UTC.
The run covers PostgreSQL, destination secrets, separate worker/clock roles, private objects, replication, and Rails release assets.
Current database instructions use the Stack logical-replication procedure and its copy/switch playbooks.
The original standalone measurements below are earlier evidence, not measurements of those playbooks.
SQLite conversion, arbitrary accessories, and a production public-hostname cutover were not tested.

## Artifact identity

| Component | Tested version or identity |
| --- | --- |
| Source | Debian 13 x86-64 VM, Docker `26.1.5+dfsg1`, Kamal `2.12.0`, controller Ruby `3.3.8` |
| Source accessory | PostgreSQL `17.11 (Debian 17.11-1.pgdg13+2)` |
| Destination | Debian 13 x86-64 system container, PostgreSQL `17.11`, Podman `5.4.2` |
| App | Ruby `3.4.7` pinned base, Rails `8.1.4`, Puma `7.2.1`, pg `1.7.0`, Propshaft `1.3.2`, aws-sdk-s3 `1.237.0` |
| Source r1 image ID | `sha256:3ebb7f9634db5d96003ece0f81af112e02cbf822898d46b80d72db84cf9a1ce3` |
| Published r1 digest | `sha256:2bace1ba4502c96fa536795562cccfe543f75e01204ce8172e9013f1ff5e1afd` |
| Destination CSS-only r2 image ID | `sha256:f68b98120ce3818d521525a280d22383d9b08fe170f08500e0ed75cd11f15ac8` |
| Source/destination S3 stand-ins | `docker.io/adobe/s3mock@sha256:cf5b4f0b6200c4b636b779b93db1847419f6bd082c0b6cd88ee409dcaa350f9b` |

The copied app keeps both Rails framework migrations and adds `20261106000100_create_schedule_runs.rb`.
The runtime image uses UID 1000. Root runs only protected transfer operations.
The destination test container required `--security-opt=apparmor=unconfined` for nested Podman.
The source VM used ordinary Docker security settings.

## Native source

Built a prelabelled image, published to the fixture's loopback registry, and ran:

```sh
export VERSION=r1
kamal accessory boot postgres -d production
kamal deploy --skip-push --version r1 -d production
```

The first full source deployment completed in 35.5 seconds.
Kamal started web, worker, and clock containers plus its real proxy.
Each source role applied Rails migrations before starting its command.
The database accessory enabled logical replication and retained a persistent data directory.

The existing Rails HTTP checks passed accounts, sessions/logout, CRUD, owner refusal, exact file bytes, and report completion.
Kamal then stopped worker and clock roles, with both containers exiting 0.
Two additional users registered through HTTP and created owned records, documents, and pending reports.
Their mode-600 manifest retained original sessions, IDs, expected bytes, and synthetic emails.
A native custom-format database backup and three current object bytes were exported independently.

The running web container's signing key equaled the production destination value.
The value differed from the common value and the deliberately wrong `.kamal/secrets` value.
Only equality results were reported. Secret values were never printed.

## App moves before PostgreSQL

The source and destination had a real WireGuard connection on an isolated private network.
Source web execution stopped after exporting the quiescent synthetic fixture.
Destination object import preserved all three keys and downloaded bytes for exact comparison.
Two destination web containers and one combined jobs container used the old source PostgreSQL over WireGuard.

Returning original sessions and passwords, stable record/document/report IDs, owner checks, downloads, and pending-report completion passed.
The copied Rails HTTP checks passed shared sessions and logout revocation across the two destination web processes.
Source workers and clock stayed stopped.
This was a standalone runtime handoff, not an MMX-managed Stack deployment.

## Database moves last

The earlier standalone run used a fixture-specific logical-replication helper, followed by an explicit container stop/restart.
That helper is no longer part of this example. Current migrations use [the Stack procedure][database-move] and its playbooks.
The following results describe the earlier fixture run only.

The initial copy and confirmed source WAL position passed.
All 75 writes made after replication started appeared in the destination database.
Final exact comparison covered every public table, including credentials, sessions, queue output, scheduling receipts, and Rails metadata.
Every public sequence's value and `is_called` state were synchronized.
The subscription, publication, and replication slot were removed. The helper asserted source slot absence.

The final write pause was **10.494 seconds**.
Timing started before stopping all destination writers and ended after a new destination record was saved and independently read.
The first confirmed new record had ID 80, verifying that sequence state did not restart from the initial copy.
The app's original session survived, and the full returning-user and shared HTTP checks passed after switching databases.
The small synthetic dataset does not establish a pause bound for a larger database.

## Source shutdown and release assets

Stopped the entire source VM before the destination release check.
The destination kept serving its own PostgreSQL and object store.
The tested r2 image changes only CSS by adding `.release-proof { color: rgb(1, 2, 3); }` in the copied working directory.

Ran the Stack's unmodified `fill_web_asset_directory` helper with r1 as `PREVIOUS_IMAGE` and r2 as `IMAGE`.
Replaced each web container with r2 and mounted the helper's asset directory over `/app/public/assets`.
Each web process served the new CSS fingerprint and the old CSS URL with identical bytes and `text/css`.
An original pre-migration session saved a new record after release, and the second process read the saved record.
The source stayed stopped throughout these checks.
No real browser window or lazy frontend route was exercised by this HTTP asset check.

## Scheduling and process ownership

On a separate freshly migrated database, inserted one expired and one current synthetic session.
Two overlapping `schedule-once` containers committed one daily receipt, removed exactly one expired session, and preserved the current session.
A repeated command kept the existing receipt and performed no duplicate cleanup.

Killed the exact report-worker PID inside the assigned combined jobs container.
The supervisor stopped the clock and exited nonzero.
After restart, SIGTERM drained both commands and the container exited 0.
A further restart preserved the existing main schedule receipt.

## Failures that changed the instructions

- Docker could not read AppArmor profiles inside the initial unprivileged source container. The source was replaced with a VM.
- A copied archive lacks Git metadata. Kamal needs `VERSION=r1`, and Kamal still requires the Git executable.
- A first `app exec` cannot use an app secret file before boot. Source roles now migrate before their commands start.
- Special `localhost` registry forwarding collides on the combined source/controller host. The fixture uses explicit `127.0.0.1` registry access.
- A prebuilt image without Kamal's service label is rejected. The documented build supplies `--label service=migration-portal`.
- Whole-tree ownership changes copied installed dependencies in overlay storage. Only writable tmp/log directories now change owner.
- The minimal image has no standalone `kill` executable. The interruption test uses the shell builtin with an exact container PID.

Python and Ruby syntax checks passed. Owned changes passed whitespace checks.

## Replay and remaining boundaries

An independent reader reviewed source bootstrap, hostname handling, working directories, and protected object mounts before live population.
A fresh independent reader restored the saved backup into a separate database owned by a new scoped role.
The copied backup checksum and original artifact bytes matched before and after replay.
The restore had four accounts, two records, three documents, two pending reports, and all three migration versions.
All three objects imported into a fresh bucket.
Original sessions/passwords/IDs, owner isolation, exact bytes, and pending report state passed before jobs started.
After jobs started, returning-user completion and full cross-process HTTP checks passed.
The replay used the database endpoint authorized for its scoped role, rather than inheriting the implementation fixture's WireGuard access rule.
Replay containers, database, role, bucket, and objects were removed, and fresh listings verified absence.
An independent native-source replay also passed the exact documented registry/build/push/VERSION/accessory/deploy commands.
The new app copy used fresh generated secrets, an empty PostgreSQL data directory, and a new S3Mock bucket.
The reviewer verified zero accounts before HTTP population.
Population, original sessions/passwords/IDs, owner checks, private bytes, reports, and full customer actions passed.
Native secret loading verified common/destination precedence, non-destination exclusion, and retained common values without exposing values.
Worker and clock stopped through Kamal and exited 0.
The replay reused installed tools and image cache, then removed its Docker execution and verified an empty container list.
The replay image ID was `sha256:b577b1ca45c23bd9e367f4c56a734f983d29a6b391e0a597ca3b5f0f16b4811d`.

## Alignment to the Stack procedure

The guide and example now delegate database preparation, copy, fence, switch, and cleanup to [the Stack procedure][database-move].
The former fixture-specific copy/switch helper and dump-restore migration instructions were removed.
Kamal-specific instructions cover the accessory's WireGuard port publication, administrator login, app-role preparation, and native source shutdown.
The accessory command includes the procedure's four-second `wal_sender_timeout`.
The app is Ruby/libpq and contains no copy of `pg_with_multiple_database_servers.mjs`.

This alignment reruns offline example checks. No new source/destination lab or live playbook run is claimed.
The existing real-service and independent replay results above remain the application/source evidence.

Public DNS/TLS cutover, actual R2 bucket authorization, alert delivery, and the Stack backup chain were not rerun.
S3Mock proves API and byte behavior, not provider authorization.
The separately tested [Rails framework checks](../../../docs/app-frameworks/rails-pg.md) remain the authority for real R2, failover, PgBouncer, and shared-system behavior.

[database-move]: ../../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md
