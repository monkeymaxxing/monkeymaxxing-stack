# Kubernetes logical-migration test record

## Variances and guidance needs

The real Stack copy and switch playbooks passed from PostgreSQL 15.19 inside k3s to PostgreSQL 17.11.
All 76 acknowledged HTTP writes survived on the destination primary and synchronous replica.
The source machine then powered off, and destination customer checks passed without the source.

| Difference | Verified result |
| --- | --- |
| PostgreSQL runs in a Pod | PostgreSQL listened on the Pod network, while the node's WireGuard address exposed the transition Service. |
| NodePort can translate client addresses | `externalTrafficPolicy: Local` preserved the primary and replica's WireGuard client addresses at PostgreSQL. |
| The new primary initially has a read-only app login | The current Node helper skipped that login and selected the old writable database. |
| Logical replication does not copy DDL | Schema and grants were prepared before copying. All nine tables reached ready. |
| Non-public schema with identity sequence and large object | Table rows, sequence state, large-object OID, bytes, owner, and reader grant survived the switch. |
| A StatefulSet can recreate PostgreSQL | A recreated source Pod retained the read-only fence from the original PVC. |
| Source retirement | Scaling PostgreSQL to zero and powering off the whole source did not interrupt accepted destination customer behavior. |

## Versions and artifact boundary

Run date: **2026-11-06 UTC**.
The Node helper is copied unchanged from the Stack, with SHA-256:

`cbcfc4fd275dc797acd017a516a61ec4f970ca011817f18b5ba7cc0727f01e42`

| Component | Observed version or immutable input |
| --- | --- |
| Source | Debian 13, k3s `v1.37.2+k3s1`, PostgreSQL `15.19` |
| Source PostgreSQL image | `postgres:15.19-bookworm@sha256:19b8449e2187e8a174b40c8832a7ed9da45813b74c2779b1c614e7e7d0ee47f0` |
| Destination | Debian PostgreSQL `17.11-0+deb13u1`, independently initialized primary and synchronous replica |
| Node / Express / pg | `24.11.0` / `5.3.0` / `8.23.1` |
| bcryptjs / S3 SDK / Podman | `3.0.3` / `3.1161.0` / `5.4.2` |
| App image ID | `47bf3d0ac8bb44ebd33011f2fc9610e8681ee14823f5d3910d36adf319074dfb` |
| S3 stand-in | `adobe/s3mock@sha256:cf5b4f0b6200c4b636b779b93db1847419f6bd082c0b6cd88ee409dcaa350f9b` |

The destination used native PostgreSQL clusters and unchanged Stack copy/switch playbooks and roles.
A small test role rendered the unchanged Stack database-URL template with its normal inputs.
This was a targeted Stack-shaped test, not a full initial setup or automated formation-failover test.
The new primary's normal replica streamed from the primary. The Kubernetes source data directory was never copied into the destination.

## Native source and app-first move

The source contained web/worker Deployments, Service, Ingress, CronJob, ConfigMap, mounted Secret, and PostgreSQL/upload PVCs.
Two synthetic users registered, created owned records, uploaded two 27-byte documents, and queued reports through HTTP.
A native Job created from the CronJob template completed hourly cleanup.
Source web/worker desired counts were zero, and the CronJob stayed suspended before destination execution.
PostgreSQL stayed running for copying and switching.

The initial eight-table audit matched before destination writes.
The separate file import preserved two keys and 54 bytes with matching SHA-256 values.
Destination probes against the old database preserved original session tokens, passwords, UUIDs, private bytes, ownership refusals, and CRUD.
Browser hostname and TLS behavior were not exercised.

A deliberately destination-first URL skipped the new primary's read-only app login and selected the old writable database.
The ordinary source-node address refused the PostgreSQL NodePort.
Both destination database peers reached PostgreSQL through WireGuard with preserved peer addresses.

The four portal behavior tests passed in **12.817 seconds** against PostgreSQL 15.
The tests covered interrupted worker rollback, concurrent claims, shared logout, private bytes, uploads, migrations, scheduling, and connection recovery.
The current Stack Node-helper suite passed **15 tests** in **13.102 seconds** inside a Linux guest.
The portal tests drained the initial pending reports before copying. The logical copy preserved the completed reports and outputs.
Workers were paused during the database switch. New queued reports completed after source shutdown.
Pending-state restore and seed behavior retain their separate disposable-replay evidence.

## Logical copy and non-public-schema probe

The source used `wal_level=logical` and `wal_sender_timeout=4s`.
The initial application database occupied **8,215,911 bytes**.
The publication covered the eight portal tables and `migration_probe.values`, a non-public table.
The probe carried an identity sequence, large-object OID, app owner, and reader grant.
The required owner/grantee roles existed at the destination before schema loading.

The actual `copy_the_database_moving_in` playbook passed, and every table reached ready.
The synchronous replica received the copied data.
An HTTP writer ran through the destination app during copying.
Pausing only the synthetic writer allowed a full-precision comparison of all eight application tables, which passed.
The writer resumed before the actual switch playbook ran.

The comparison contained three users, four sessions, 52 records, three documents, two reports, controls, schedule history, and two migrations.
Its normalized SHA-256 was:

`8f89b79bb759807fce7d2fa7468f536af0111da187ae58468369b8932283c700`

The actual `switch_to_the_database_moving_in` playbook then passed.
It fenced the old cluster, caught up replication, copied sequences and large objects, removed the subscription/slot, and opened destination app logins.
The non-public probe compared equal across source, primary, and replica, including large-object OID, SHA-256, owner, and ACL.
Sequence state matched before a destination insert verified forward progress.
No non-public table row was reloaded during the large-object transfer.

## Write pause and acknowledged-write loss

The synthetic writer attempted a new HTTP record creation roughly every 200 milliseconds, after each response completed.
The client logged every HTTP status, acknowledged record ID, and request start/finish time.
The client did not retry failed mutations.

| Measurement | Result |
| --- | ---: |
| Total HTTP mutation attempts | 79 |
| Acknowledged HTTP 201 writes | 76 distinct IDs |
| Failed attempts during switch and recovery | 3 HTTP 500 responses |
| Missing acknowledged IDs on destination primary | **0** |
| Missing acknowledged IDs on destination replica | **0** |
| Playbook-reported write pause | **1.140 seconds** |
| Sampled HTTP failure interval | **0.735 seconds** |
| Largest acknowledgement gap during switch/recovery | **0.937 seconds** |

The playbook's pause parts were:

| Phase | Seconds |
| --- | ---: |
| Fence and end old app sessions | 0.535 |
| Durable catch-up | 0.061 |
| Sequence transfer | 0.125 |
| Large-object transfer | 0.169 |
| Subscription and slot cleanup | 0.134 |
| Open destination logins | 0.116 |
| Total reported pause | 1.140 |

The HTTP interval starts at the first failed request and ends when the first request after the last failure is acknowledged.
The interval is sampled client behavior, not the exact duration of the server fence.
The acknowledgement gap measures adjacent successful response times and includes the client's normal request spacing.
The small dataset and single writer do not establish production-scale throughput or a universal pause.

The harness verified every acknowledged ID on the primary and replica.
An independent reader recomputed the timing metrics and re-queried both live databases, finding zero missing acknowledged IDs.
The two web containers retained their original start times throughout switching and source-offline checks.
The switch required no web restart or URL change.

## Source fence and operation after shutdown

The old source's migration-slot count and the destination's subscription count were zero after switching.
The source retained its read-only default.
Deleting the PostgreSQL Pod allowed the StatefulSet to create a new Pod from the original PVC.
The new Pod still reported the read-only default.
The PostgreSQL StatefulSet was then scaled to zero, and the entire source machine powered off.

With the source off, returning-password and original-session probes, original private downloads, ownership checks, and CRUD passed.
Two new private uploads passed exact-byte checks, and two newly queued reports completed with owner-specific counts.
Four total reports remained completed.
Restarting the destination jobs service preserved completed work.
The actual destination hourly service removed a forced expired-session fixture and recorded one hourly occurrence.
A second invocation reported the occurrence already completed, and the destination timer owned scheduling.

A native fixture database dump was saved for replay.
The dump does not establish Stack pgBackRest enrollment or backup recovery.
Protected exports, native inventories, credentials, and database rows remain outside public files.

## Limits

- EKS, GKE, and DigitalOcean Kubernetes remain **documented, not live-tested**.
- Natural clock-triggered CronJob firing, custom operators, GitOps, HPA/KEDA, meshes, and multi-zone placement were not exercised.
- The cross-major pair tested is PostgreSQL 15.19 to 17.11. Other schemas, extensions, and version pairs require compatibility checks.
- Report workers were paused during the switch. Concurrent job execution throughout the write fence was not tested.
- S3Mock proves S3 API and byte behavior, not real R2 authorization or cloud storage retention.
- Public TLS/tunnel routing, browser cookie-domain behavior, full initial setup, automated formation failover, Stack backup recovery, and alerts were not tested.

The [guide](../../../docs/app-platform-migrations/from-kubernetes.md) and [testing procedure](testing.md) link the canonical Stack database move and keep Kubernetes-specific routing and controller steps.

## Cleanup

Protected exports and secret-free evidence were saved before teardown.
The destination subscription count was zero. The source migration slot had already been removed by the switch.
All five remaining test objects and their bucket were deleted, and a fresh bucket listing was empty.
The source, primary, and replica test guests were deleted. A fresh full guest listing confirmed absence.
Guest deletion removed container storage, database volumes, WireGuard keys, and timer services.
Per-run controller credentials and shared guest-slot reservations were removed.
No cloud resources were created.
