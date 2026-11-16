# Check a customer portal on an isolated system

The Go and Rust examples passed isolated Linux integration on 2026-11-03.
The run used Debian 13, PostgreSQL 17.11, Podman 5.4.2, and pinned Adobe S3Mock.
Each language had a separate database and bucket, two web containers, and two workers.
A later isolated primary/replica run also passed. No full Stack deployment is claimed.

## Verified outcomes and limits

| Check | Go | Rust |
| --- | --- | --- |
| Linux recipe, non-root runtime, configured ports | Pass | Pass |
| Empty-database health refusal and healthy migrated database | Pass | Pass |
| Migration and staging seed idempotence, unsafe seed refusal | Pass | Pass |
| Shared HTTP check, ownership, sessions across processes, logout revocation | Pass | Pass |
| Document upload/download bytes and SHA-256 | Pass | Pass |
| Two workers complete 20 reports | Pass | Pass |
| Killed worker's transaction leaves report available | Pass | Pass |
| Health query deadline | 2.006 seconds | 2.002 seconds |
| Ordinary database query deadline | 12.010 seconds | 12.002 seconds |
| Graceful web shutdown drains a blocked in-flight request | Pass, exit 0 | Pass, exit 0 |
| Graceful job shutdown commits an active report | Pass, exit 0 | Pass, exit 0 |
| Native title-only release remains running through migration 0002 | Pass | Pass |
| Logical dump/restore preserves all six tables exactly | Pass | Pass |
| Restored login and document download from an isolated copied bucket | Pass | Pass |

The first service run proved initial multi-host fallback with an unreachable host.
A separate run used a real PostgreSQL 17.11 primary and streaming hot standby.
Both apps selected the writer with the live standby listed first.
Go's actual configuration helper also selected a preferred standby with the
primary listed first, before and after a promotion. The Go HTTP fixture itself
uses the primary pool for reads. Rust intentionally uses the primary pool because
tokio-postgres does not support `prefer-standby`.

The primary/replica run kept two web and two job containers per language running
through planned promotion in both directions and a separate silent TCP fault.
All eight process IDs and start times stayed unchanged. Existing sessions, fresh
logins/writes, and background reports worked on each new primary.

| Fault | Go failed requests | Go recovery | Rust failed requests | Rust recovery |
| --- | --- | --- | --- | --- |
| Planned promotion forward | 27 | 0.439 seconds | 0 | 0.485 seconds |
| Planned promotion reverse | 27 | 0.489 seconds | 1 | 0.581 seconds |
| Silent TCP peer, then promotion | 1 | 9.744 seconds | 10 | 50.620 seconds |

Recovery is the first successful write acknowledgement after the database logged
`received promote request`. Counts describe one sequential writer per language.
The planned faults included about two seconds with no writable primary before
promotion. Rust's longest planned request waited about 2.9 seconds, so zero failed
requests did not mean requests continued without delay.

A run-only transparent relay enabled controlled transport faults. During the
silent fault, firewall rules dropped traffic to the old database and the app's
relay TCP peer, so the relay could not acknowledge the app's keepalive probes.
Host TCP settings were 30-second keepalive idle, 10-second interval, three probes,
and `tcp_retries2=7`. Go's longest silent-fault request took 12.012 seconds.
Rust's five-second bb8 checkout deadline returned repeated 503 responses while
old connections remained unusable. These measurements describe this isolated
Linux transport experiment, not every network failure or a full Stack failover.

To test an ambiguous commit, the relay buffered one mutation's database replies
until idle `ReadyForQuery`, then closed that connection without delivering the
replies. Each app returned 503 while the independently queried database held
exactly one committed row. The row stayed unique, and a new distinct write worked.
The app did not automatically replay the mutation. The caller must reconcile an
uncertain result before submitting another mutation.

S3Mock verifies object API behavior, not R2 credentials, TLS, or authorization.
Object recovery used S3 CopyObject into a separate bucket. Logical database restore
used pg_dump/pg_restore. Neither check exercises the Stack's backup chain or disaster
recovery procedure. Public HTTPS/browser replay, PgBouncer, R2, pg_auto_failover
orchestration, and the full Stack deployment/backup recovery remain unproved.

Run the following steps on your assigned integration host, using separate databases,
private buckets, ports, app names, and release tags for Go and Rust.

## Before services

Record the Stack commit, app source tree/commit, lockfiles, compiler versions,
image digests, and exact operational-tool builds. Confirm resource ownership before
starting a run. Do not point these checks at a production app.

From this example directory, run its local checks:

```sh
cargo test --locked
cargo clippy --locked --all-targets -- -D warnings
```

The unit checks use no Postgres, S3 service, VM, or listener.
The [shared HTTP check](check_portal.py) uses Python's standard library.
The migrations in this example are embedded at build time.

## Database, worker, and HTTP checks

1. Build the selected image. Check that the non-root binary starts, listens only
   on `PORT`, and exits cleanly on `SIGTERM`.
2. Run `customer_portal migrate` twice against an empty assigned database.
   Confirm exactly two migration rows and no duplicate tables.
3. Before migrations, confirm `/healthz` returns 503. After migrations, confirm
   `/healthz` returns 200. Stop database access and check a response within two seconds.
4. With staging-only database and object credentials, run `seed-test-data` twice with `APP_ENV=staging`.
   Confirm two accounts, two records, two documents, and two waiting fixture jobs.
   Confirm seeding without `APP_ENV=staging` fails before modifying data.
5. Start two web instances on different assigned ports with matching database,
   bucket, and `APP_ORIGIN`. Start two job workers against the database.
6. Supply `FIXTURE_PASSWORD` through the environment and run the check from an
   assigned integration host. Use each instance's reachable address:

```sh
python3 check_portal.py \
  --server-a http://app001:8003 \
  --server-b http://app002:8003 \
  --origin https://portal.example.com
```

The check sends cookies explicitly to the private app addresses. Browsers must
use HTTPS because browser session cookies are Secure. The check never prints cookies
or passwords. Test accounts have random suffixes to avoid modifying seeded accounts.
The script keeps synthetic accounts, documents, and reports for restore inspection.

The script checks login/registration, cross-server session reuse, write-origin
refusal, ownership, CRUD, object bytes and hashes, report output, logout revocation,
and login after logout. The HTTP check alone does not prove transaction recovery,
primary switching, backup recovery, or container behavior.

Open the public HTTPS app in a browser. Repeat account creation, record editing,
upload, download, report completion, and logout. Confirm document/report content
appears on the page. Check input labels and keyboard navigation.

## Concurrent and interrupted work

After both fixture jobs complete, inspect `report_jobs`. Each fixture key must
have exactly one row, non-null `finished_at`, and output `record_count=1` plus LF.
Run two workers concurrently while queuing more reports and verify every output.

To prove interrupted work without timing a tiny report, hold a table lock on
`records` in an explicit test transaction. Queue a report. A worker locks the job
row before waiting on the count query. Inspect `pg_stat_activity` and `pg_locks`
to confirm that worker reached the waiting query. Stop only that worker's owned
process/container while the lock remains held. Roll back the lock transaction.
Verify another worker completes the waiting report once, with the expected count.
Never stop processes by name patterns. Record the assigned process/container IDs.

## Additive migration

Use a previous-release test build that knows only migration `0001_portal.sql`
and reads/inserts only `records.title`. Keep the previous release running while
applying `0002_record_descriptions.sql` with the reviewed release's migrator.
Verify old writes still work and existing records acquire the empty description.
Then deploy the new release and set a description. Record exact builds and SQL.
Do not edit the real shared source tree to create the previous-release fixture.
An isolated copy or test image must own the previous-release variation.

## Primary switch and reconnection

Use the Stack's `switch_database_primary` operating procedure after a healthy
replica exists. Keep both web processes and workers running throughout the switch.
Record process/container identities before and after the switch.

Log in once. Every half-second, submit a uniquely titled synthetic record through
the same session and note the time and HTTP result. Never retry a failed mutation
under the same assumption of success. A failed request can have committed.
Record the total failed requests and the interval until a new write succeeds.
Query the new primary for every acknowledged record and check sessions and jobs.
Repeat in the reverse direction. Stop the old primary's connectivity separately
if proving an abrupt failure, and record the different recovery measurement.

Follow the [database driver instructions](https://github.com/monkeymaxxing/monkeymaxxing-stack/blob/main/skills/monkeymaxxing-stack/files_for_your_app/database_driver_finds_the_primary.md)
for keepalive, deadlines, and PgBouncer. A Node helper's test is not proof of
Go or Rust HTTP reconnection. With transaction-mode PgBouncer enabled, rerun the
HTTP/worker and switch checks using the Stack-generated URLs.

## Restore checks

Keep only `the_migrations_came_back` for the first drill, before data exists.
After synthetic data and completed reports exist, add data-dependent checks to
`restore_drill_check_queries` in the systems repository. For example:

```yaml
- name: fixture_accounts_came_back
  sql: >-
    select count(*) = 2 from accounts
    where email in ('barbara@example.com', 'michael@example.com')
      and length(password_hash) = 60
- name: fixture_records_and_owners_came_back
  sql: >-
    select count(*) = 2 from records r join accounts a on a.id = r.account_id
    where (a.email = 'barbara@example.com' and r.title = 'Barbara invoice'
      and r.description = 'First synthetic record')
      or (a.email = 'michael@example.com' and r.title = 'Michael invoice'
      and r.description = 'Second synthetic record')
- name: fixture_documents_and_owners_came_back
  sql: >-
    select count(*) = 2 from documents d join accounts a on a.id = d.account_id
    where (a.email = 'barbara@example.com' and d.object_key = 'fixtures/barbara-note.txt'
      and d.sha256 = '05fc126dc203e0579d73a6365e130ba77d1f422d87042b362456a2885029d32a')
      or (a.email = 'michael@example.com' and d.object_key = 'fixtures/michael-note.txt'
      and d.sha256 = '784483c538543c904f1232e9c939417711e771b531e3f04c3d45f6699ad65c55')
- name: fixture_reports_came_back
  sql: >-
    select count(*) = 2 from report_jobs j join accounts a on a.id = j.account_id
    where j.fixture_key = a.email
      and a.email in ('barbara@example.com', 'michael@example.com')
      and j.finished_at is not null and j.output = E'record_count=1\n'
```

Record expected fixture hashes before the backup. Check restored hashes against
that pre-backup manifest, not against values computed from the restored database.
Record a session digest and a pending report ID before backup. Query the restored
session's owner/expiry and the pending report's owner/state without printing tokens.

Run check queries read-only on the restored database. Never point a restored worker
at the live app's queue or bucket as a side effect of a drill.
To prove returning users, start a separate restored app with an isolated bucket
containing recovered uploads. Reuse a test session only if the restored session
has not expired. Otherwise log in using the fixture password.
Download every restored fixture reference and compare bytes with the table in
the README. Record database recovery time and uploads recovery separately.

## Evidence to keep

Keep commands, exact builds, assigned resources, timestamps, HTTP outcomes, SQL
booleans, object hashes, failed writes, and recovery measurements. Exclude secrets.
List each unrun check explicitly. A guide becomes live-verified only after the
steps work from a clean starting point and an independent reader replays the guide.

## Repeat the test-data service suite

Build the app image and supply the protected runtime environment for an empty disposable PostgreSQL 17 database and bucket.
The runner needs Python with psycopg 3 and boto3, plus Podman.
Run as root inside a disposable Linux guest with local PostgreSQL.
Use database `portal_rust`, owned by login role `portal_rust`. The recovery check creates `portal_rust_restored_v2`.

```sh
podman build --build-arg RELEASE=test-data-check --tag localhost/portal-rust:integration .
export TEST_LOG_DIR="$(mktemp -d)"
python3 tests/services.py
```

The suite checks both allowed environments, refused environments and counts, exact fixtures and 1,000 accounts twice.
The suite also checks HTTP behavior, deadlines, worker interruption, graceful shutdown and logical database/object recovery.
The runner retains its containers and synthetic rows for inspection. Use only a disposable test system.
The protected log directory contains runtime environment files. Keep the directory out of Git.

## Seed test-data proof

- 2026-11-05: `seed-test-data` now supports development and staging plus `--accounts`. The full real-service suite passed on Debian 13 with PostgreSQL 17.11 and S3Mock. Checks covered refused environments and counts, exact fixtures, 1,000 accounts twice, unchanged documents/jobs, HTTP ownership and storage, workers, and shutdown. Previously recorded image IDs predate this change.
