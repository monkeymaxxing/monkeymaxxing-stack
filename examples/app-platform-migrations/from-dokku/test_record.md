# Variances and guidance needs

The current guide uses the Stack database-move procedure.
Its copy and switch playbooks replace the example-specific database harness.
The example carries the Stack's Node helper unchanged, including the writable-login check.

The native Dokku and standalone-destination evidence below predates that alignment.
A native Dokku source and standalone Debian destination passed the app-first, database-last migration on 2026-11-06.
The measured database write pause was **4.268 seconds** on this small synthetic fixture.
The result does not measure the earlier application/upload handoff, public traffic interruption, or the Stack's no-restart switch.

| Difference exercised | Result |
| --- | --- |
| App/global configuration outside Git | Protected exports retained the runtime-only secret, global-only value, and app-over-global precedence. Final container checks returned booleans only. |
| PostgreSQL plugin dump | A native custom archive restored every application row and migration checksum exactly on PostgreSQL 17. |
| Private upload mount | Two original objects exported with checked lengths/hashes, imported into S3Mock, and downloaded through owner-checked HTTP endpoints. |
| Docker-local cron | A real `cron:run` invocation produced a receipt. Cron maintenance and process scaling stopped source execution separately. |
| Plugin ambassador on an internal Docker network | Port configuration existed but no working listener appeared. The supported direct exposure mode published the WireGuard-only listener after a database container restart. |
| App first, database last | Destination accounts, uploads, CRUD, and reports worked against the source database over WireGuard before replication. |
| PostgreSQL logical replication | Seven tables copied, then subsequent customer writes replicated. Final stopped-writer row comparison matched exactly and the source slot was removed. |
| One external schedule | MMX created the singleton timer, an unchanged second apply passed, overlapping starts archived one old report once, and an automatic timer trigger succeeded. |
| Source independence | The Dokku virtual machine was stopped. Destination login, original bytes, new writes/uploads, reports, and the timer command still worked. |

## Versions and artifacts

| Component | Tested value |
| --- | --- |
| Application implementation | Independent copy of the Heroku portal, with a local/S3 storage boundary and external schedule |
| Operating system | Debian 13, x86-64, separate source and destination virtual machines |
| Dokku / scheduler | `0.38.34`, Docker-local |
| PostgreSQL plugin / datastore helper | `2.6.1` / `0.11.1` |
| Docker / destination Podman | `29.9.3` / `5.4.2` |
| Source database | `postgres:17.11`, server `17.11` (`17.11-1.pgdg13+2`) |
| Source image config digest | `sha256:397ede1de7bbd98a7e2ab1170f9c5ed5215277a807b9134a7871d8ed67c78029` |
| Source image manifest list | `sha256:5a4cd8cd9c0210016ad98c2028642f3452993291996aa8f88ee0f277dd625c8b` |
| Destination PostgreSQL | `17.11` (`17.11-0+deb13u1`) |
| Node.js | `24.22.2` |
| Node base image manifest | `sha256:01d566e8d94d8c619591d78652babfccd3c6992a3dffa9ed5ab39e11cf6c70e9` |
| Destination image ID | `sha256:1be0850ef73756b107f541afda8582795ed8a89641b3b5bea0b802ce1375b119` |
| S3-compatible rehearsal service | S3Mock, `sha256:cf5b4f0b6200c4b636b779b93db1847419f6bd082c0b6cd88ee409dcaa350f9b` |
| MMX controller | `0.1.0-proof.15`, protocol 1 |
| MMX executable SHA-256 | `6a8ac323a8678ef944c32fc74d671daf83fa3b6fd1910d6d86f33d0db67b2f1c` |
| MMX Linux runner SHA-256 | `311f4b8756d1b0d300c07d234a99f00085429c3af63ea5c5c6119317e9187c03` |

Dependencies are pinned by the copied `app/package-lock.json`.
The source database build and image digests were recovered from the protected native source records.
The independent replay used a fresh application and database on an existing Dokku installation.

## Dataset and commands

The source was populated through `node tests/customer-actions.mjs populate` against the native Dokku endpoint.
The fixture created two bcrypt accounts, two owned records, two private documents, and two pending report jobs.
Ten cross-owner access attempts returned 404. Logout and wrong-password refusal passed.
The synthetic password and account/object baseline stayed in separate protected files.

The source used `scripts/create-source.sh`, its `app.json` cron and predeploy migration hook, and its `Procfile` web/worker commands.
The source worker was present but paused until ownership transferred. The daily archive command was exercised through native `dokku cron:run`.
The final source shutdown used `dokku cron:set portal maintenance true` and `dokku ps:scale portal web=0 worker=0`.
The source database stayed online.

`dokku config:export --global` and `dokku config:export portal` retained their separate scopes.
The final destination web container had the original generated runtime value, `HOST_CONFIG_SCOPE=app`, and `GLOBAL_ONLY_SETTING=preserved`.
No secret value or operational export is part of this example.

`dokku postgres:export portal-db` produced an 11,753-byte native archive.
A PostgreSQL 17 restore used `pg_restore --exit-on-error --no-owner --no-acl --role=portal` into a separate empty test database.
`scripts/snapshot-database.mjs` produced matching source and restored counts and row checksums across all seven tables.

`scripts/transfer-uploads.mjs export` retained two regular objects and verified both document references.
`import` uploaded into a separate S3Mock bucket and downloaded every object for byte equality.
A second import into the populated bucket was refused.
The destination ran the app image with `node web.mjs` and a separate `node jobs.mjs` container.
Two web processes shared PostgreSQL-backed sessions.

`node tests/customer-actions.mjs verify` passed against the old database over WireGuard before replication.
The same check passed again after replication started, creating further session, document, and queue changes during catch-up.
Returning passwords, stable IDs, original private bytes, ten ownership refusals, new CRUD/uploads, and report completion passed.
The original queued reports and later reports returned the correct owner-only `record_count=1` output.
The new storage adapter's local byte-roundtrip and path-escape tests passed.
The inherited test-data test passed on its own empty database and exercised 1,000 synthetic accounts without changing the migration fixture.

## Database switch measurement

The original standalone database harness copied the public schema and created the publication and subscription.
Those steps are now owned by [Move a database into the Stack][database-move] and its [copy][database-copy] and [switch][database-switch] playbooks.
The fixture contained no sequence and no PostgreSQL large object, checked before setup.
The subscription reached ready state `r` for all seven tables. A subsequent check reported an active slot with zero byte lag.
Schema changes remained frozen during the copy.

The final switch stopped the destination timer, any current timer service, and the report worker, then stopped web.
The measurement began when the test issued that final web stop.
The helper compared every application row after writers stopped:

| Table | Rows at final comparison |
| --- | ---: |
| `users` | 2 |
| `sessions` | 6 |
| `records` | 2 |
| `documents` | 6 |
| `report_jobs` | 6 |
| `schedule_runs` | 1 |
| `schema_migrations` | 2 |

The helper dropped the subscription and publication and verified that the replication slot was absent.
The destination containers restarted with the new database URL and the transferred runtime configuration.
The measurement ended at the first successful HTTP 201 record creation: **4.268 seconds**.
The temporary test record was deleted through HTTP after timing ended. The timer then resumed.

The entire Dokku source virtual machine was stopped before the final customer verification.
The destination passed the same login, private-file, ownership, write/upload, report, logout, and wrong-password checks with the source stopped.
The archive service also succeeded against the new database.

The measurement uses two accounts and a small database. It is not a production downtime promise or a sized replication benchmark.
The Stack procedure defines sequence/large-object transfer, ownership/grants, supported data, and failure recovery.
The earlier standalone timings are not measurements of those playbooks.

## Scheduled task proof

The public `systems-repository/playbooks/portal_schedule.yml` ran through MMX against a one-node schedule group.
The first apply installed and enabled the daily UTC timer. A second apply reported unchanged.
The service ran `podman exec portal-jobs node schedule.mjs`, so the job used the active release and its existing runtime settings.

The timer test reset only the disposable receipt and aged one completed report.
Overlapping service starts left one UTC-date receipt with `archived_job_count=1`, and that report had `archived_at` set.
The timer was restarted and repeated invocations retained the single receipt.

For an automatic-trigger test, the test project's calendar briefly changed through MMX to every minute.
The timer's last trigger and service start both read `2026-11-05 22:29:06 UTC`, with `Result=success`.
MMX then restored the public daily UTC schedule.
The timer does not make up missed runs, matching the source cron behavior.

## Failures and corrections

- The minimal host lacked `wget`, needed by the pinned Dokku bootstrap. Installation succeeded after adding the prerequisite.
- Installing the plugin under a private-export file mask made its helper inaccessible to the Dokku user. Shared executable installation now uses the normal mask; logs and exports stay protected.
- A concurrent redeploy met Dokku's deployment lock. The run waited for the owned deployment to finish, then repeated the changed archive without unlocking an active deployment.
- Dokku emitted the generated synthetic runtime value in a deployment log. The fixture value was rotated and subsequent log inspection excluded secret-bearing output.
- Node's request to the source IP did not supply the required virtual hostname. The source hostname was resolved explicitly for HTTP population.
- The plugin ambassador's port binding did not produce a listener from its internal network. Direct exposure, with the planned database restart, produced the WireGuard-only listener. The ordinary guest network refused the database port.
- Initial schema-copy attempts used incorrect `pg_dump` options and a client invocation that selected the local default despite a URI-valued `PGDATABASE`. The helper now uses explicit libpq environment fields and the PostgreSQL 17 options.
- A fresh database already contained `public`. The helper now drops only an empty default schema before copying and refuses occupied schemas.
- A fresh read found that host exports needed the plugin's host-reachable internal address, and that pre-restoring tables conflicted with helper setup. The instructions were corrected before replay.
- Fresh native replay found unreadable root-owned source files after archive deployment under the private-export mask. Archive deployment now uses a normal source-file mask in a subshell while its log remains private.

## Replay and remaining limits

A separate reader followed the public guide on a reset native source fixture and an isolated destination.
The reader found the archive file-mask fault, then verified the exact corrected deployment invocation and its dependent steps.
The complete installer was not restarted after that correction. The corrected deployment, process setup, and exports were replayed.

The independent run passed source HTTP population, native cron/shutdown, host-local export, two-file import, and exact native dump restoration.
Destination customer actions passed against the old database, then again after replication started and after the source stopped.
The independent switch measured **3.670 seconds**, with the same final row counts and verified slot removal.
An occupied-schema test refused setup without changing the restored tables' checksums.
The non-superuser subscription owner had `pg_create_subscription` and ownership of the new database.

The replay used a private bridge connection for the old-database stage. WireGuard and MMX timer results remain the original run's evidence.
The replay repeated the scheduled command directly after source shutdown and retained one receipt.
The fresh source image ID was `sha256:cb40cd6316a449af30c63a45c6848b990ee8d5ac12c0219e5f945ce2140a086a`.
The independent destination image ID was `sha256:b13ed49bf4328ef750b96a0b442f82e25464e1bd96435e2c27b87c10aaa43ade`.
The independent native dump was 11,750 bytes and restored with identical seven-table row checksums.

All disposable source and destination guests were removed after evidence collection. No cloud resource was created for this example.
The shared container guide must be integrated before these links can be published.

Not live-tested by this Dokku example: the Stack database-move playbooks, complete Stack deployment, public hostname/TLS/DNS cutover, real R2/S3 authorization, pgBackRest enrollment/restore, and delivered operational alerts.
The guide links to the Stack's implemented database-move procedure for the old-server peer, generated URLs, copy, fence, and no-restart switch.

Other Dokku schedulers, arbitrary plugins and buildpacks, extra databases or schemas, role-grant transfer, sequences, large objects, and different PostgreSQL majors remain untested.
The unchanged portal's general queue interruption and primary-selection behavior reuse the [Heroku evidence](../from-heroku/test-record.md).
This run adds native Dokku shutdown, private-mount conversion, database-last replication, and the external timer interaction.

## Alignment checks

After alignment to the Stack database-move procedure, `npm test --prefix app` passed all three local checks on Node.js 24.22.2.
The database-selection check kept one URL unchanged while the old login became read-only and the new login became writable.
The check refused both read-only choices before opening the destination. It uses supplied session states, not PostgreSQL servers.
The two upload checks passed again. The copied helper matched the Stack file byte-for-byte.
No native source, seed-database, HTTP, timer, or Stack server test was repeated for this alignment.
Their earlier results remain separate evidence. The alignment changes the guide and copied driver, without another platform lab run.

[database-move]: ../../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md
[database-copy]: ../../../skills/monkeymaxxing-stack/systems_repository_template/playbooks/copy_the_database_moving_in.yml
[database-switch]: ../../../skills/monkeymaxxing-stack/systems_repository_template/playbooks/switch_to_the_database_moving_in.yml
