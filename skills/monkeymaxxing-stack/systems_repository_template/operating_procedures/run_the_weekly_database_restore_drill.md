# Run the weekly database restore drill

**When:** checking that production's backups restore, after changing backup
settings, or during a system review.

**What this page does:** the drill restores production's database from B2
onto a temporary server, `restore01`, checks the restored data and one
uploaded file per app, and destroys `restore01` again. It never touches
the live database.

**Who acts:** `util01` runs the drill by itself each week
([The weekly drill](#the-weekly-drill)). The coding agent reads the
result, records it, and starts or stops a drill from the systems desk.
Before a leftover `restore01` is destroyed, the person confirms that no
recovery uses the server.

## Find your situation

| Situation | Follow |
| --- | --- |
| Read the latest drill's result, such as in a system review | [Read the result](#read-the-result) |
| Start a drill now, such as after changing backup settings, or stop one | [Start or stop a drill now](#start-or-stop-a-drill-now) |
| A `restore01` is left over at the provider or in the inventory | [Remove a leftover restore server](#remove-a-leftover-restore-server) |
| Run `restore_database` yourself, for a recovery | [Restoring the database](#restoring-the-database) |

## Before you start

- **Start the drill over SSH, never with the helper.** The helper must not
  start the service, because the helper would hold the same lock the
  service needs.
- **Results stay on `util01`; scheduled jobs never commit files.** The
  coding agent records the verified measurements.

## Read the result

1. **On `util01`, read:**

   ```sh
   journalctl -u weekly_database_restore_drill
   cat /var/lib/restore_drill/latest_result.json
   cat /var/lib/restore_drill/latest_passed_drill
   ```

   The result gives `passed`, `started_at`, `restore_duration_seconds`, and
   `seconds_of_writes_missing_at_most`; a failure gives `attempt_dir` for
   recovery.
   **Check:** `"passed": true`. Any other result is in
   [If something is different](#if-something-is-different).
2. **Record the verified measurements** in `backups_restore_every_week` in
   the checklist, and update the README's recovery results.
   The duration measures database recovery including server
   creation, not recovery of the whole site. The write-age number is an upper
   bound on missing writes and can overstate loss on a quiet database.
   **Check:** the checklist item carries the measured numbers and their date.

## Start or stop a drill now

1. **To start, use a separate SSH session:**

   ```sh
   ssh -F ssh/config root@10.20.0.1 'systemctl start --no-block weekly_database_restore_drill.service'
   ```

   The command starts the existing scheduled service; follow the drill in
   its journal.
   While the drill waits 2 hours to run again after giving way, the start
   command above starts it at once, in place of the waiting run, so the
   drill does not run twice.
   **Check:** the journal shows the drill running, then
   [Read the result](#read-the-result).
2. **To stop, use
   `systemctl stop weekly_database_restore_drill.service`.** MMX finishes the
   current node task, including cleanup, before the service releases the
   lock. A hard server loss can still leave a restore server. The stop
   command cancels the waiting run of a drill that gave way.
   **Check:** the daily check for a leftover `restore01` passes, as below.

## Remove a leftover restore server

The daily `check_for_a_leftover_restore01.service` checks the provider
listing and inventory, after any drill has ended; a drill that gave way
has destroyed `restore01` already, so the check passes while the drill
waits to run again. The next drill also refuses a leftover server.

1. **Before removing a leftover, establish ownership and confirm no
   recovery uses the server.**
   **Check:** the person confirms.
2. **Run `destroy_a_server_at_the_provider --server-id` with the recorded
   ID,** which waits until the provider's listing lacks the ID.
   **Check:** the command ends; the provider's listing lacks the ID.
3. **Remove retained temporary files.**
   **Check:** `check_for_a_leftover_restore01.service` passes.

## If something is different

- **The drill gave way to MMHotline.** The result gives `"passed": false`
  and `gave_way_to`, the line of the MMHotline run that waited, and no
  `attempt_dir`: nothing is left, and systemd runs the drill again 2 hours
  later. Read when with
  `systemctl status weekly_database_restore_drill.service`, which shows
  `activating (auto-restart)` since the drill ended. Record nothing.
- **The drill gave way but could not finish its cleanup** (the destroy
  failed, or `mmx mark-node-work-failed` exited 2, 3 or 4). The result
  gives `gave_way_to`, `attempt_dir` and, for the second case,
  `cleanup_failure_reason`. The drill fails its service, and does not run
  again: remove the leftover as
  [Remove a leftover restore server](#remove-a-leftover-restore-server) says.
- **The drill stopped before it created anything,** at fleet stage
  `push_the_newest_database_changes`: the journal says the primary did not
  archive its write-ahead log segment within 5 minutes. Archiving is
  failing, so the backups miss the newest changes. `latest_result.json`
  still holds the drill before, with its older `started_at`. Read
  `pg_stat_archiver`'s `failed_count` and `last_failed_wal` on the primary
  and its pgBackRest log, fix the cause, then
  [start a drill now](#start-or-stop-a-drill-now).
- **The drill failed.** A failure gives `attempt_dir` for recovery. Name
  the cause only from the drill's own record: the journal's line
  `restore drill failed at fleet stage ...` names the failed fleet stage
  of `restore_database` and its error, and
  `ATTEMPT_DIR/restore_result.json` holds the whole run, where the
  failed stage's entry has `"status": "failed"`. When no fleet stage of
  the restore failed, the journal says so, and the lines above it give
  the cause, such as a failed create of `restore01` or a failed uploads
  check. Lines in which SSH tries
  `restore01` again while the new server boots are normal, not a cause.
  Reason: a coding agent that read only those SSH lines once called a
  failed check query "a slow boot".

The success marker changes only after restore, queries, uploaded-file
checks, and cleanup pass. MMWatchdog warns when the success marker is
missing or older than eight days, so a drill that gives way and passes 2
hours later warns nobody, and a drill that gives way every time still
warns. A failed service also warns; a service that waits to run again is
not failed.

## Restoring the database

`restore_database` restores production's database from B2 onto one server in `database_restore_servers`.
Except for `restore_database`, every playbook, including `every_server`,
skips the `database_restore_servers` inventory group.
The restore then runs each app's `restore_drill_check_queries` from
`mmx_project_settings.yml` on the restored copy. Each query must answer true.
An app without `restore_drill_check_queries` fails the check.
`staging01` keeps no backups: a new `staging01` gets its data from the
seed command ([Replace staging01](replace_staging01.md)).

If you run `restore_database` separately, supply the following variables.
For the weekly drill, the MMX playbook supplies the
`restore_database` variables automatically.

- `restore_mode`: the purpose of the restore. `copy_on_restore01` restores a
  production copy onto `restore01`, outside the failover group, for the
  weekly drill or for recovering rows lost to a bad change. `recovery` restores
  production onto a new database server after every database server is
  lost. The weekly drill uses `copy_on_restore01`.
- `server_name`: the server to restore onto.
- `recover_to`: the database state to restore. `latest` restores through
  the newest transaction in the archive available at
  `read_backup_bucket_as_of`. A time such as `"2026-11-03 14:01:00+00"` stops
  recovery at the specified time instead.
- `read_backup_bucket_as_of`: the time that selects which versions of the
  bucket's files pgBackRest reads. `recover_to` selects how far to replay
  the archived writes available at `read_backup_bucket_as_of`.
  The bucket keeps every file version. Later deletions
  or overwrites by an attacker do not affect the bucket contents read as
  of `read_backup_bucket_as_of`.
  Use the time you start `restore_database`, or a time before anything
  could have changed the bucket.

## The weekly drill

On `weekly_work_day` at two hours after `nightly_work_starts_at` (03:00 UTC on Sunday in the template), `weekly_database_restore_drill.service` runs the
MMX playbook `weekly_database_restore_drill` on `util01`, at the trusted
commit, under `/var/lib/mmhotline/systems_repository.lock`, shared with
ordinary agent runs.

- The first or rebuilt-system `every_server` run also starts a drill until
  a drill passes.
- The drill waits for an active uploads copy.
- A timeout of `restore_drill_time_limit_hours` (six in the template) sends a
  handled stop to the drill; cleanup can run longer if the provider is slow.

The drill does these steps by itself:

1. Make the primary database server send its newest changes to the
   bucket (fleet stage `push_the_newest_database_changes`): it closes
   its current write-ahead log segment with `pg_switch_wal()` and waits,
   up to 5 minutes, until `pg_stat_archiver` shows that segment archived.
   Reason: the drill restores the bucket as it stood at the drill's start,
   and the primary otherwise sends its changes only about once a minute,
   so a drill right after an app's first migrations restored a copy
   without the app's tables.
2. Refuse an existing `restore01` at the provider or in the inventory,
   or any member of `database_restore_servers`.
3. Generate `restore01`'s WireGuard key pair in memory on `util01`.
   Use `render_server_first_boot` to render first-boot data with
   the inventory's `vars.restore01_private_ip` and only `util01`
   as a peer. Create `restore01` with the team's provider script, the
   database servers' size and location, and the utility server's SSH key.
   The create script records the accepted server ID before waiting for
   provisioning. Pass the private key once in first-boot data and keep no copy.
4. Make a temporary project copy outside the working repository. Add
   `restore01` with `address` and `private_ip` from `vars.restore01_private_ip`, the
   setup-generated public key, and the provider's `public_ipv4_address`.
   Add `restore01` as a runtime peer on `util01` through root SSH in the MMX drill, retaining
   the peer's public key for cleanup. Accept the SSH host key seen over
   WireGuard and save the known-hosts line only in the temporary copy.
   Run `restore_database --var restore_mode=copy_on_restore01 --var server_name=restore01
   --var recover_to=latest --var read_backup_bucket_as_of=DRILL_START_TIME`.
5. Run every app's `restore_drill_check_queries`; every query must answer
   true. Measure the duration until the queries answer and the age of the
   newest restored transaction at drill start. A null transaction-age
   measurement means no replayed transaction supplied a measurement.
6. Compare one eligible uploaded file per app byte for byte between R2 and
   B2 as B2 stood at drill start. Eligible files were unchanged before the
   last passed uploads copy. An empty eligible set is reported explicitly.
7. After success, failure, or a handled stop, remove only the runtime
   peer with the recorded `restore01` public key from `util01` through root SSH in the MMX drill.
   Destroy only the server ID in the create receipt. Remove temporary
   inventory and host keys after provider destruction succeeds. A
   destruction failure keeps the temporary copy and receipt for recovery.
   A peer-removal failure keeps the attempt directory, receipt, and
   WireGuard public-key file for cleanup, and fails the drill.

Reason: a frozen archive measures the backups available at a real failure.
Temporary inventory keeps normal server runs separate from the restore.
An immutable provider ID prevents destruction of another server. The
uploaded-file comparison tests the backup copy without saving customer
file contents on `util01`. The runtime peer avoids changing Git or
reconfiguring the utility server during each drill. Only `util01` peers
with `restore01`; desks need no restore peer or inventory change.

### The drill gives way to MMHotline

An outage comes first. While the drill holds the lock, MMHotline may wait
for the lock: for a run the triage agent asked for, such as replacing a
failed server, for the fetch that starts a triage agent run, or for a
person's `run_mmx_on_util01`. MMHotline then keeps the marker
`/var/lib/mmhotline/systems_repository.lock.waiting`, one line that says
who waits and since when. The drill looks for the marker before it
creates anything, then every 5 seconds, and when it finds one it ends:

1. It destroys `restore01` by the ID in its receipt, so the restore ends
   with its server.
2. It stops its inner MMX run with `mmx stop`. `mmx stop` contacts the
   destroyed `restore01` once (10 seconds) and exits 3, because
   `restore01`'s work stays unconfirmed: that is expected here, and any
   other exit status is a failed cleanup.
3. It ends the inner `mmx run` process at once (TERM, then KILL after 10
   seconds if the process remains): the server is gone, so
   nothing is lost. Left alone, the inner `mmx run` may take up to
   `restore_unless_controller_confirms_within` (2 minutes) plus about 6
   minutes to end after `mmx stop`, because the drill's restore changes
   `ufw` under a confirmation window. Ending it at once is safe,
   because `mmx mark-node-work-failed` records the work that is left.
4. It runs `mmx mark-node-work-failed --node restore01 --json` in the
   attempt's project, which records `restore01`'s unconfirmed work as failed
   because the team says the server is gone. Exit 0 is clean. Exit 2 (MMX
   reached `restore01`, which the provider says is destroyed), 3 (MMX could
   not tell) or 4 (a command error) is a failed cleanup: the drill exits 1,
   never 75, and `latest_result.json` keeps `attempt_dir` and gives the
   reason as `cleanup_failure_reason`, with the reasons of `runs_not_recorded` when the command lists any.
5. It removes the runtime peer, writes `latest_result.json` with
   `"gave_way_to"`, the marker's line, and ends with exit status 75.
6. systemd runs the drill again 2 hours later.

The lock is free about 30 to 40 seconds after the provider has destroyed
`restore01` (`mmx stop` up to 10 seconds, the inner process about 5
seconds, `mmx mark-node-work-failed` up to 10 seconds; an estimate that
the next run on real servers measures). When the drill was creating
`restore01` just then, the create script first finishes its wait for the
server's boot, about a minute. util01's own scheduled jobs never make the
drill give way: they ask MMHotline nothing while another job holds the
lock.

Reason: MMHotline's wait counts toward its run's one-hour limit. Releasing
only the lock would not help: the drill's MMX run holds `util01` for the
whole drill, so a waiting `every_server` would be refused as busy, and
`every_server` would remove the drill's runtime peer for `restore01`.
A marker that MMHotline stopped rewriting, after MMHotline stopped during
a wait, is ignored.
