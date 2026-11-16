# Variances and guidance needs

A Docker Compose source moved onto the Stack on **2026-11-06**.
The Stack app first served customer actions against the old PostgreSQL database over WireGuard, after local uploads became S3-compatible objects.
The native copy/switch playbooks then moved PostgreSQL 15.19 into the normal Stack PostgreSQL 17.11 primary/replica formation.
The old system was powered off while the app still held its old-first database URL.

The accepted run preserved **227 acknowledged HTTP writes on both database servers**, with **zero missing UUID/title pairs**.
The internal database write pause was **2.491 seconds**. The customer HTTP success gap was **7.120 seconds**, measured with a one-second request interval and five-second request timeout.
Neither web nor jobs container restarted during the switch or source-off checks.

Public Cloudflare routing, real object-provider authorization, native B2 upload backup and external alert delivery remain unproved.
The test used synthetic outside services with real Stack Caddy, WireGuard, application services, database formation and pgBackRest.
The fixture kept `COOKIE_SECURE=false`; the production secure-cookie setting was not exercised.
A fresh reader independently repeated the migration from a prepared source/Stack checkpoint.

| Source difference | Result |
| --- | --- |
| Compose base file plus production override | Resolved configuration, production marker, restart policy, file-secret mapping, named database volume and upload bind mount checked. |
| Mounted database URL secret | Source non-root app used `DATABASE_URL_FILE`; Stack supplied its normal multi-server `DATABASE_URL`. |
| Local private uploads | Three referenced files retained keys, byte lengths and hashes; destination accepted new private object uploads. |
| Worker and host timer | Source web/worker stopped and host timer became disabled/inactive before destination execution. The destination timer was applied and run through MMX. |
| Database-last move | Destination customer checks passed against old PostgreSQL over WireGuard before native logical replication began. |
| Cross-major state | Sized tables, non-public rows, sequence state, large objects, ownership and semantic grants survived PostgreSQL 15 → 17. |
| Source retirement | Source-off customer actions and a fresh database connection succeeded without restarting the app containers. |

## Versions and artifacts

| Artifact | Recorded value |
| --- | --- |
| Deployed database-move program SHA-256 | `689f97109d1193aa11f7a9a12117666c0ae1cd37bad5d92c7627e49bffe7707a` |
| Operating system | Debian 13 AMD64 |
| Docker / Compose | `26.1.5+dfsg1` / `2.26.1-4` |
| Source PostgreSQL | `15.19`, official Debian-bookworm container |
| Source PostgreSQL image digest | `sha256:19b8449e2187e8a174b40c8832a7ed9da45813b74c2779b1c614e7e7d0ee47f0` |
| Stack PostgreSQL | `17.11`, Debian package `17.11-0+deb13u1` |
| pg_auto_failover / pgBackRest | `2.2-2` / `2.55.1` |
| Application Node.js | `24.11.0` |
| Node image digest | `sha256:76d0ed0ed93bed4f4376211e9d8fddac4d8b3fbdb54cc45955696001a3c91152` |
| Accepted application image ID | `sha256:a5099130e3ae5124413123356cf48bd61a6bcb97727a0537c33927f7d7dfacd2` |
| Podman / Caddy | `5.4.2` / `2.11.9` |
| MMX | `0.1.0-dev`, protocol 1; exact binary hashes retained with operational evidence |
| S3-compatible test service | Moto `5.2.5` |
| Dependencies | Locked `pg 8.23.1`, `express 5.3.0`, `bcryptjs 3.0.3`, AWS S3 client `3.1161.0` |
| Resources | Six guests, each 4 GiB RAM, 2 vCPUs, 40 GiB root disk |

The application source carries the current Stack Node helper unchanged. The native cutover exercised its writable-login selection.
All fifteen Stack Node-helper tests passed against live primary/standby databases.
The example adds source file-secret loading, local-file storage selection and a report loop that survives temporary database unavailability.

## Source and app handoff

Two synthetic users registered through the running Compose app.
Each created an owned record, private document and pending report through HTTP.
The source host timer ran hourly expired-session cleanup with a durable occurrence receipt.
The source preparation command also had a separate fresh-project replay during the earlier standalone rehearsal.

Customer checks captured stable user, record, document, object and report identities.
The same checks passed through destination HTTPS/Caddy against the old database, during copying, and with the old system powered off.
They covered existing passwords, original private bytes, owner refusals, CRUD, new private uploads and logout revocation.
Source database sessions showed the destination app's WireGuard address.

The source web/worker services and timer stayed stopped after the app handoff. PostgreSQL alone remained for replication.
A real MMX `systemd_scheduled_job` owned the destination hourly cleanup.
Container images were delivered by Docker save/Podman load; registry authorization was outside this proof.

## Sized native copy

The immutable table held **49,152 rows of 65,536 bytes**, exactly **3,221,225,472 payload bytes**.
`STORAGE EXTERNAL` disabled TOAST compression. Payloads repeat per-row MD5 blocks; this is a sized transfer, not a production throughput benchmark.
Ten published tables included two rows in the non-public `migration_history.events` table.
Those rows also exercised the all-schema large-object fix in the selected Stack revision.

The normal utility helper ran `copy_the_database_moving_in`.
All tables became ready in **128.780 seconds**, including command startup and readiness polling.
Acknowledged writes increased from **17 to 139** across that interval; customer CRUD/upload checks also ran during copying.
The unfinished Stack login remained read-only.

Source, Stack primary and replica returned:

```text
49152|3221225472|0|757703b0aacbe81c8f1b65e809ef5737
```

This audits row count, payload bytes, per-row MD5 mismatches and ordered ID/digest coverage.
Schema changes stayed frozen. The large object changed on the old server before the switch.

## Native switch and write audit

The utility helper ran `switch_to_the_database_moving_in` with the ordinary `database_moving_in` configuration.
The source retained the procedure's four-second walsender timeout in the accepted run.

| Native pause part | Seconds |
| --- | ---: |
| Fence | 0.469 |
| Catch-up | 0.076 |
| Sequences | 0.917 |
| Large objects | 0.337 |
| Subscription cleanup | 0.523 |
| Open Stack logins | 0.168 |
| Total internal write pause | **2.491** |
| Complete helper invocation | 6.981 |

The HTTP writer submitted distinct mutations and never retried an uncertain request.
Every UUID and submitted title from all **227 HTTP 201 replies** existed on **both** database servers.
The longest consecutive-success gap intersecting the actual switch invocation was **7.120 seconds**.
One request hit its five-second client timeout; its row was subsequently found once on both servers. It was not counted as acknowledged.
Internal pause, HTTP recovery and helper invocation time measure different boundaries.

Final old rows were preserved, including account/session verifiers, ownership, queue state and migration checksums; intentional new destination rows were checked separately.
Sequence state retained three skipped identity values, unused value 700 with `is_called=false`, and the descending sequence.
The execution check then received default ID **49156** and descending value **-20**.
Large object **44101** retained 1,100,000 bytes, final MD5 `204eb3aae5b10e1d48be36fbc097f7e5`, owner and read ACL.
Table/sequence ownership, grantors, grantees, privileges, grant options and default privileges matched by meaning.
PostgreSQL 17's added owner `MAINTAIN` privilege explains the expected raw ACL-text difference.

The old cluster stayed read-only. Source migration slots and destination subscriptions were zero after switching.
Both app container start times remained unchanged through switch and source power-off.
Another **59 writes** succeeded after source power-off. Returning-user/private-byte/ownership checks passed too.
A fresh Node connection using the unchanged old-first URL selected the Stack primary after approximately three seconds of old-host timeout.

## Execution and backup recovery

An actual worker was killed after its update and before commit. Both original reports remained pending.
Concurrent workers completed the original report IDs once with owner-specific output.
Repeated hourly schedule commands retained one receipt for the occurrence.
Migrations reran twice without changing the two-entry ledger.
The resumed normal Stack jobs service completed another report queued through HTTP.
The read-only role read the migrated table and large object; an insert was refused.

A protected source backup was restored and checked before the move.
After a native switch, the ordinary Stack full-backup helper, invoked through MMX, produced a **3,397,859,912-byte** full database backup.
The backup used the encrypted pgBackRest S3 repository against the test service.
Its **200.704 seconds** included waiting for a regular checkpoint; an explicit checkpoint was requested during that wait.

An isolated restore on a separate local PostgreSQL port recovered both accounts, both migration-ledger entries, both non-public rows, all 3 GiB with zero hash mismatches and the final large object.
The restored test cluster was stopped afterward.
This checks recovery of the backup's contents; provider restore-server creation and the full automated restore-drill workflow were not repeated.
The backup check used the earlier native-switch attempt with the same Stack revision and database schema; the later worker-only correction does not alter stored data.

## Independent prepared-checkpoint replay

A fresh reader followed the public guide and linked native procedure, deriving its own migration commands and audits.
It used a rebuilt image, `sha256:a6a11ac137e7104ddd798972e172978a55438e68e5585b2cd0fdece56b4313b0`; the jobs and database-helper build-input files matched the selected example, and the source and destination image IDs matched.
Source provisioning and initial Stack provisioning were inherited.
The checkpoint lacked completed monitoring setup; the normal primary-switch playbook refused before changing databases, and the reader completed the normal setup roles before continuing.

| Independent check | Result |
| --- | --- |
| Source/app handoff | Production override, file secret, mounts and restart policy inspected; four referenced uploads copied and byte-verified; source execution stopped. |
| Native copy | All ten tables ready, streaming feedback matched, all three 3 GiB audits matched; customer actions and HTTP writes continued. |
| Native write pause | **2.437 seconds**, one switch invocation, original four-second source setting unchanged. |
| HTTP recovery | **3.293-second** consecutive-success gap at a one-second interval; two HTTP 500 responses, no mutation retries. |
| Acknowledged writes | **400 UUID/title pairs**, individually checked on both database servers; zero missing or changed rows. |
| Source independence | Old system powered off, fresh old-first URL connection selected writable Stack primary, customer actions passed, **38 further writes** succeeded. |
| Container continuity | Both web/jobs start times remained unchanged through switch and source-off checks. |
| State and execution | Source small rows and semantic grants preserved; large object and pre-probe sequences matched; interrupted/concurrent worker, normal HTTP report, schedule and migration checks passed. |

The reader confirmed that the source endpoint was the Docker PostgreSQL service's direct published port, with no pooler.
Readiness monitoring recorded source walsender disconnects during bulk I/O; the reader waited for recovery and matched streaming positions before switching.
After the consuming sequence probes, the physical replica's sequence state advanced ahead through PostgreSQL WAL prelogging. Both servers matched the source before those probes; the primary returned the required new values.

## Failures and corrections

- An initial 100 ms writer exceeded the shared test system's synchronous subscriber throughput. The four-second source walsender setting caused repeated disconnects under bulk I/O. The native switch refused before fencing, and old writes remained available. A diagnostic attempt used a longer replication-login timeout; the accepted fresh run kept the ordinary four-second setting and used sustainable one-second load.
- The first completed native switch exposed an uncaught jobs-loop error while neither login was writable. The process now keeps polling durable queue state after a failed attempt; `--once` still fails visibly. The accepted fresh run proved unchanged web/jobs containers.
- A supplied `Host` header did not override Node `fetch` routing. Tests now use the configured HTTPS hostname and normal trust.
- The initial scheduled-task script embedded MMX template expressions in a literal script. The image now enters through `env`; real validation, timer application and execution passed.

No failed attempt supplies the accepted copy/switch timing.

## Remaining limits

- Independent initial source and Stack provisioning were not repeated; the independent migration began from the recorded prepared checkpoint.
- Cloudflare public DNS/tunnel routing, real R2/B2 authorization and retention, native B2 upload backup, registry authorization, provider conditional-write enforcement and phone alerts were not tested. TLS ingress and S3 test services establish the recorded API/data behavior only.
- PostgreSQL major pairs other than 15.19 → 17.11, live DDL, row-security policies, partitions, unlogged/foreign tables and extension upgrades were not exercised.
- The large object is 1.1 MB. A large mutable collection changes the final pause because logical replication omits large objects.
- Upload keys are immutable. Mutable-key overwrite, document deletion and orphan-file policy need application-specific checks.
- OAuth, MFA, password reset, two destination app servers and multi-database moves were not repeated here.

## Cleanup

Normal Stack reconciliation removed `database_moving_in`, the old WireGuard peers and old database URL addresses.
The normal read URL selected the Stack replica afterward. Both unused old password files were removed.
The source publication and replication role were removed during administrative cleanup while the source cluster stayed fenced.
Customer checks passed again with the source off.

All six disposable guests, their root volumes and snapshots, and the synthetic outside services were removed after saving evidence.
Fresh instance and volume lists confirmed absence. No real cloud resource was created.
