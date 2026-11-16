# Coolify migration test record

Native migration evidence was recorded 2026-11-05 UTC. The source-route check and current-helper tests were rerun 2026-11-06 UTC with synthetic data.
The source was a real self-hosted Coolify installation. The destination was an independent Debian 13 rehearsal.

## Historical source and destination artifacts

| Part | Tested version or identity |
| --- | --- |
| Coolify | `4.6.0`, latest published release at the source check |
| Source Docker | `29.9.3` |
| Source and destination Node.js | `24.11.0` |
| npm | `11.6.1` |
| Source PostgreSQL | `17.11`, official `postgres:17` image |
| Destination PostgreSQL | `17.11`, Debian 13 packages |
| Source app image digest | `sha256:21d071fbb1acf94ded8527a44975c86f98b37a17bc3e77a09f060f01d2774a81` |
| Verified destination image digest | `sha256:64ce8e5c4af489cc787fd5c97a91e2c5f87c8a565a727da321b5e3dfedd1a457` |
| Source PostgreSQL image digest | `sha256:748a18a54d3842d43bc156f0840d78029b8d349e0feca98c12b9c4ce3404a6b3` |
| Pinned Node base image | `sha256:76d0ed0ed93bed4f4376211e9d8fddac4d8b3fbdb54cc45955696001a3c91152` |
| S3-compatible test service | `adobe/s3mock@sha256:cf5b4f0b6200c4b636b779b93db1847419f6bd082c0b6cd88ee409dcaa350f9b` |

The app copies the existing Fly portal schema, ownership checks, PostgreSQL queue, and multi-host database helper. The current helper is copied unchanged from the Stack.
Source-specific changes add mounted-file storage, runtime session signing, shared-setting verification, and native API inventory.
The destination combined jobs command owns both reports and hourly cleanup.

## Native source proof

Coolify created a project, a private PostgreSQL resource, an image application, a shared project variable, runtime-only variables, a persistent upload volume, and a Scheduled Task.
The application was deployed through Coolify's API.
Two users registered through the running app and created their records, exact private documents, and pending reports through HTTP.
The source used two ordered migrations.

Before export, the fixture contained two accounts, two records, two document rows, two pending reports, and a completed scheduled occurrence.
A separate login retained a source-issued session for the transition test.
The upload volume also held one unreferenced synthetic file.
The exporter copied all three regular files and every row from all eight public tables.
Database and file hashes matched independently.

The API checks proved:

- A normal `read` token omitted `SESSION_SIGNING_KEY` values.
- `read:sensitive` recovered the exact runtime signing key and its runtime-only flags.
- A shown-once probe remained hidden with sensitive access.
- A shared project reference resolved to the actual production value.
- Production settings, mounts, task definitions, task execution history, deployment history, and the native database resource were saved separately from Git.

The creation copies of runtime credentials were discarded before recovery through the API.
The actual production notice was generated outside the app code.
The native Scheduled Task ran the cleanup command successfully.
A valid signed GitHub push queued a real redeployment and applied a changed shared setting.

## Native shutdown proof

The final handoff disabled native tasks, automatic deploys, and previews.
The manual webhook secret was rotated.
Replaying the old signed push did not queue a deployment.
The old API deployment token was revoked and its deployment request returned HTTP 401.

The native application stop action removed running application containers.
Native task execution counts stayed unchanged after disabling tasks.
A controlled source reboot left the application stopped.
The old database was fenced, its replication slot removed, and its restart disabled before final source shutdown.

## Historical standalone database experiment

The destination first used the old PostgreSQL database through a WireGuard link.
All source rows matched the exported audit before destination requests changed sessions.
Files moved from the source mount to the independent S3-compatible bucket with unchanged keys and hashes.
A source-issued session worked on the destination.
Owned records, exact private downloads, wrong-owner refusal, and new record/file writes passed before the database moved.

A PostgreSQL 17 physical base backup created a streaming replica using a dedicated replication role and slot.
Thirty customer HTTP record writes committed while the replica streamed.
The final source database size was **8,148,659 bytes**.
After writes paused, the replica replayed the final source WAL position and contained all **33** records present at the fence.
The old primary stopped before promotion.

The measured interval from initiating the maintenance gate to the first successful destination HTTP write was **6.261 seconds**.
The measurement includes controller and SSH command overhead.
No post-promotion write probe failed, and the web processes kept their original process IDs through the switch.
All 30 streaming-period writes survived.
The destination retained the pre-replication uploaded bytes and stable owner links.

Customer actions passed with the entire source guest stopped.
The final destination removed the old database address, stopped its source-only WireGuard link, removed replication credentials, and completed both pending source reports with correct owner counts.
The cleanup occurrence ledger prevented duplicate hourly work.
The final built container image also served the source-session, ownership, private-byte, and new-write checks with the source guest and source-only WireGuard link stopped.

## Independent replay

A fresh reader used a fresh app copy, dependency installation, database, role, bucket, settings directory, and web ports.
The reader followed [testing.md](testing.md).

| Check | Result |
| --- | --- |
| Export checksum and document inventory | Passed |
| Exact restored-row comparison before mutations | Passed for every public table |
| S3 import and byte readback | All three source files passed |
| Portal behavior | All five tests passed, zero failures, 17.55 seconds |
| Interrupted transaction and concurrent report workers | Passed |
| Combined report/scheduler pause, resume and restart | Passed |
| Conflicting object import | Refused different existing bytes without overwriting |
| Separate empty-database seed replay | One test passed, zero failures, 9.19 seconds |
| Returning-user actions with source confirmed stopped | Stable ID, owned record, exact private bytes, new record/upload and logout passed |

The seed replay covered development/staging, repeat runs, invalid counts without mutation, 1,000 accounts, smaller-count preservation, and production/unset refusal.
The final independent source-stopped check ran after a separate controlled source reboot audit.
The replay resources used only destination-local database and storage addresses throughout.

## Logical-move source route and helper rerun

The source-route check used Coolify 4.6.0, Docker 29.9.3, PostgreSQL 17.11 and WireGuard.
The Coolify control-plane image ID was `sha256:8821fbb5d1eb083a7378d9c0f6c85eae56ba0171b69947ebcb415eb8133706d7`.
A peer used PostgreSQL 17.11 and Node 24.11.0. No full Stack formation was deployed for this check.
The Stack tested includes the logical-move procedure.

| Source setting or check | Result |
| --- | --- |
| Custom Docker options `-p` and `--publish` | The settings form saved both strings, but neither created a published port |
| REST updates for `custom_docker_run_options` and `ports_mappings` | Both rejected with HTTP 422 |
| Native settings-form Port mappings | Created exactly one binding on the host's WireGuard IPv4 address |
| Coolify public access | Stayed Private; no Nginx database proxy was enabled |
| Native restart | New container, same volume, marker data and private bind preserved |
| Native stop/start redeployment | Regenerated container configuration retained the same volume, data and private bind |
| PostgreSQL client address | Original peer WireGuard address preserved after both lifecycle checks |
| Non-WireGuard reachability | Ethernet address refused; an Ethernet route to the private address was blocked by the forwarding guard |
| Logical source preparation | `wal_level=logical`, publication, SELECT/BYPASSRLS replication role and logical replication startup protocol worked |
| Administrative reachability | The procedure's `postgres` login worked through the direct private bind |
| Source read-only fence | New application logins became read-only while the source remained a primary |
| Current Node helper | Skipped the fenced source and selected a writable primary; refused two candidates read-only for the login |

The fence was reset after the check.
The Docker forwarding guard admits the recorded WireGuard source ranges in the original connection direction; replies remain allowed.
An additional authenticated WireGuard source outside the allowed range was refused.
The nftables/proxy fallback was unnecessary and was not tested.
The source check exercised Docker's iptables backend and database lifecycle operations, not host-reboot ordering.

The example's current-helper tests also passed against an isolated restore of the protected synthetic export:

- Exact restored rows and all three exported file bytes passed.
- All five portal tests passed in 17.710 seconds.
- Conflicting destination object refusal passed without overwriting bytes.
- The separate empty-database seed suite passed one test in 10.711 seconds.

These checks retain the standalone proof boundary. No new production routing, R2, backup, alert, or formation-level switch claim follows.

## Failures and corrections

The installer did not create the synthetic administrator from its supplied bootstrap values.
The test created that administrator locally, then used scoped API tokens for source operations.
An initial virtual-disk resize needed a guest reboot to become visible.
The destination initially inherited the source's fixed `PORT`; removing that value let each web service supply its own port.

Fresh review found an unconditional object overwrite, an omitted maintenance-unpause step, and production settings that permitted seeding.
The importer now checks existing bytes and conditionally creates missing objects.
The conflict test proved refusal without replacing different bytes.
The guide now names the maintenance transition, and the production environment sets `APP_ENV=production`.

## Limits and remaining production checks

This is native Coolify source proof and a standalone destination/replication proof.
The current guide follows the Stack logical-replication procedure.
The physical-replication experiment above predates that procedure and does not prove the logical move or its write pause.
The [Stack procedure](../../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md) and its copy/switch playbooks own database migration.
The source-specific direct publication and fence checks below now cover the native Coolify route needed by that procedure.
The current helper is byte-identical to the Stack's helper when tested, including its writable-login check.
This run did not execute a full Stack copy or switch; it does not assign a logical-switch pause from the historical physical test.

No production DNS/TLS cutover, real R2 authorization, Stack backup/object restore, alert delivery, or multi-server MMX deployment was tested here.
The small database is a source-specific continuity check, not a sized replication benchmark.
Other Coolify build packs, catalogue services, preview environments, locked/shared-secret access policies, external secret providers, and control-plane backup restoration were not live-tested.
The fixture used PostgreSQL 17 with UUID keys and no large objects, user sequences, extra tablespaces, or non-core extensions.
Shown-once omission was tested. Universal secret export was not claimed.
