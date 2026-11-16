# Fix failed database write-ahead log archiving

**When to use this page:** MMWatchdog's
`write_ahead_log_archiving/archived_within_5_minutes` warns on the primary,
and the archiver repeatedly fails to copy one segment (steps 1 and 2 check
both).

**What this page does:** the server whose database history differs from
the primary's leaves, a new replica becomes the primary on a new timeline,
and a one-time playbook marks the split timeline's waiting segments as
archived, so archiving works again and a full backup starts the new
timeline.

**Who acts:** database servers always need a person
([The rules](../AGENTS.md#the-rules), "What the triage agent may do
without a person"). The triage agent hands over to a person and does not
follow this page ([When to hand over](../triage_agent_rules.md#when-to-hand-over)).
The coding agent does every step from the systems desk. The person
approves the removal and decides about the removed server in step 4, and
approves the one-time playbook's run in step 11.
The person runs nothing in the person's own terminal.

**Terms:** this page uses the Stack's terms, such as primary, replica,
failover monitor, one-time playbook and pgBackRest.
[Technical terms](../talking_with_the_team.md#technical-terms) explains
each term. This page also uses these terms:

- The write-ahead log records database changes in files called segments.
  Postgres's archiver uses pgBackRest to copy finished segments to B2.
- The primary is the database server that
  `sudo -u postgres pg_autoctl show state --pgdata /var/lib/postgresql/17/pg_auto_failover_monitor --formation production`
  on `util01` lists as `primary`.
- The production backup bucket in B2 is named by
  `vars.backups.production_bucket` in `mmx_project_settings.yml`.
- A timeline identifies one branch of database history.
  The split timeline is the branch where the primary and the server to
  remove wrote segments with matching names but different contents.
- Waiting segments are segments that Postgres has not archived.

## Before you start

- **Act soon.** Until archiving works again, the primary's `pg_wal` grows
  because Postgres keeps each segment it could not archive.
  If the disk fills, the database stops. MMWatchdog's disk check warns first.
- **A push alone changes no server.** Apply each configuration change as
  [Making a change](../AGENTS.md#making-a-change) says: run `every_server`
  or the playbook the step names.

## Steps

1. **Check that the archiver repeatedly fails to copy one segment,** on
   the primary. From the systems desk, run the query as root through
   `ssh/config`, with the primary's private address (`private_ip` in
   `inventories/servers.yml`):
   `ssh -F ssh/config root@10.20.2.1 'sudo -u postgres psql -XAt -h /var/run/postgresql -p 5432 -d postgres -c "select failed_count, last_failed_wal from pg_stat_archiver"'`.
   The triage agent runs the same query as
   `ssh triage@db01 'psql -h /var/run/postgresql -d postgres -XAtc "select failed_count, last_failed_wal from pg_stat_archiver"'`:
   MMHotline gives the triage agent's sessions SSH settings that reach the
   servers by name, and the `triage` user logs in to Postgres as the
   read-only role `triage`
   ([Reading the system](../triage_agent_rules.md#reading-the-system)).
   Run the query twice, a minute apart. Reason: Postgres's archiver tries
   a failed segment again about every 60 seconds.
   **Check:** the command shows the count rising and names the segment
   that failed. When the count does not rise, this page does not fit: stop
   and tell the person what the command showed.
2. **Confirm why pgBackRest refuses the primary's segments:** archived
   segments have matching names but different contents.
   Read the newest file in
   `/var/lib/postgresql/17/pg_auto_failover_node/log/` on the primary:
   `ssh -F ssh/config root@10.20.2.1 'tail -n 20 "$(ls -t /var/lib/postgresql/17/pg_auto_failover_node/log/* | head -1)"'`.
   **Check:** the file repeats
   `WAL file '0000000F00000001000000BD' already exists in the repo1 archive with a different checksum`.
   The first 8 characters of the segment name, `0000000F` in the example,
   identify the split timeline: write the split timeline down for step 9.
   When the file does not repeat that line, the cause is a different one:
   stop and tell the person.
3. **Find the server whose history differs from the primary's.** Find the
   server that does not copy from the primary.
   On the primary, the following `pg_stat_replication` query lists each
   replica copying from the primary, by private address, as `streaming`:

   ```sh
   ssh -F ssh/config root@10.20.2.1 'sudo -u postgres psql -XAt -h /var/run/postgresql -p 5432 -c "select client_addr, state from pg_stat_replication"'
   ```

   **Check:** the database server missing from the list is the server
   whose history differs. With two database servers, the replica has a
   history different from the primary's.
   **Never make the server with the different history the primary.**
   Reason: promoting the server with the different history would lose every
   write since the split. The failover monitor may still count the server
   with the different history as a healthy replica. The failover monitor
   counted a server with a different history as healthy for two minutes on
   test servers.
4. **Remove the server with the different history from the inventory,** by
   following steps 4 to 11 of
   [Fix database writes that hang](fix_database_writes_that_hang.md#remove-the-replica-that-does-not-copy-from-the-primary).
   Those steps also power the removed server off at the provider and keep
   it until the person decides whether its writes matter, because the
   removed server's history may hold writes that the primary lacks.
   Until the person decides, the daily `check_for_a_leftover_restore01`
   job on `util01` reports the removed server as a server at the provider
   that is not in the inventory, and MMWatchdog warns about the failed
   job: this is expected.
   **Check:** the checks of those steps.
5. **Add a new database server, such as `db03`, which copies from the
   primary.** Follow [Add a server](add_a_server.md) for the
   `database_servers` group.
   **Check:** the checks of Add a server.
6. **Check that the new server copies from the primary:** repeat the
   `pg_stat_replication` query from step 3 on the primary.
   **Check:** the query lists the new server's private address, its
   `private_ip` in `inventories/servers.yml`, such as `10.20.2.3`, as
   `streaming`. Until then, do not go on to step 7.
   Reason: step 7 makes the new server the primary.
7. **Make the new database server the primary:**
   `./server_management_scripts/run_mmx_on_util01 run switch_database_primary --var server_name=db03`.
   Reason: promoting the new database server starts a new timeline.
   Segments on the new timeline have new names, so archiving can copy the
   new segments to the production backup bucket.
   **Check:** the run passes. Its tasks `make_the_server_the_primary` and
   `wait_until_each_app_answers_through_its_public_host_name` pass: the
   command waits until the old primary is a replica, at most five minutes,
   then checks each app through its public host name
   ([Replace a database server](replace_a_server.md#replace-a-database-server),
   and the header of `playbooks/switch_database_primary.yml`).
8. **Create the one-time playbook:**
   `mmx new-one-time-playbook mark_the_split_timeline_as_archived_on_the_database_servers`.
   **Check:** the command names the playbook with today's date, such as
   `2026-11-03_mark_the_split_timeline_as_archived_on_the_database_servers`.
   Use the generated name in the commands below, and the date at the start
   of the generated name in each `run_only_once_marker_file` path below.
   MMX takes the date from the clock of the machine that runs the command.
   Reason: an existing marker makes MMX skip the command.
9. **Write the playbook's fleet stages.** Replace the generated one-time
   playbook's `fleet_stages` block, with the block's example fleet stage,
   by the `fleet_stages` block below. Set `split_timeline` to the split
   timeline from step 2.
   Write the timeline in the `set_vars.split_timeline` value below because
   command-line variables for a one-time playbook need a default.
   The playbook marks the split timeline's waiting segments as archived on
   every database server, then checks the archive and takes a full backup
   ([Why every database server is marked](#why-every-database-server-is-marked)).

   ```yaml
   fleet_stages:
     # One server at a time, each while its MMWatchdog holds its alerts.
     - id: mark_the_split_timeline_as_archived
       nodes: database_servers
       max_nodes_at_once: 1
       on_node_failure: stop_run
       node_tasks:
         # The first 8 characters of the refused segment's name.
         - id: name_the_split_timeline
           set_vars:
             split_timeline: "0000000F"
         - id: refuse_a_timeline_that_is_not_8_hexadecimal_characters
           assert:
             that: {matches: ["{{ .vars.split_timeline }}", "^[0-9A-F]{8}$"]}
             message: >-
               split_timeline is "{{ .vars.split_timeline }}": write the first 8
               characters of the refused segment's name, with capitals as the
               name has them, such as 0000000F for 0000000F00000001000000BD.
         # The marking takes seconds; 2 minutes cover the hub's acceptance
         # and the marking, so a run that stops here leaves the alerts
         # paused no longer.
         - id: hold_the_alerts_of_the_server
           shell:
             script: /usr/local/bin/mmwatchdog maintenance on --every-check-group --for 2m --reason "marking the split timeline's segments as archived"
         # The primary's own timeline is never marked: its segments would then
         # never reach the archive.
         - id: mark_the_waiting_segments_of_the_split_timeline_as_archived
           shell:
             script: |
               set -eu
               if [ "$(runuser -u postgres -- psql -XAt -h /var/run/postgresql -p 5432 -d postgres -c 'select pg_is_in_recovery()')" = f ]; then
                 writing=$(runuser -u postgres -- psql -XAt -h /var/run/postgresql -p 5432 -d postgres -c 'select substr(pg_walfile_name(pg_current_wal_lsn()), 1, 8)')
                 if [ "$writing" = "$SPLIT_TIMELINE" ]; then
                   echo "$SPLIT_TIMELINE is the timeline this primary writes now, not the split one; nothing was marked" >&2
                   exit 1
                 fi
               fi
               cd "$ARCHIVE_STATUS_DIRECTORY"
               for f in "$SPLIT_TIMELINE"*.ready; do
                 [ -e "$f" ] || continue
                 mv -n "$f" "${f%.ready}.done"
               done
             env:
               ARCHIVE_STATUS_DIRECTORY: "/var/lib/postgresql/{{ .vars.postgresql_major_version }}/pg_auto_failover_node/pg_wal/archive_status"
               SPLIT_TIMELINE: "{{ .vars.split_timeline }}"
             run_only_once_marker_file: /var/lib/mmx/commands_run_once/2026-11-03_mark_the_split_timeline_as_archived
         - id: release_the_alerts_of_the_server
           shell:
             script: /usr/local/bin/mmwatchdog maintenance off --every-check-group

     # On the primary: the archive's check, then a full backup at once, so the
     # backups have a base on the new timeline. The backup's program does
     # nothing on a replica.
     - id: check_the_archive_and_take_a_full_backup
       nodes: database_servers
       on_node_failure: stop_run
       node_tasks:
         - id: check_the_archive_on_the_primary
           shell:
             script: |
               set -eu
               [ "$(psql -XAt -h /var/run/postgresql -p 5432 -d postgres -c 'select pg_is_in_recovery()')" = f ] || exit 0
               pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=main check
             run_as_user_account: postgres
             run_only_once_marker_file: /var/lib/mmx/commands_run_once/2026-11-03_check_the_archive_after_the_split
         - id: take_a_full_backup_on_the_primary
           shell:
             script: systemctl start pgbackrest_full_backup.service
             run_only_once_marker_file: /var/lib/mmx/commands_run_once/2026-11-03_full_backup_after_the_split
           time_limit: 3h
   ```

   **Check:** step 10's `mmx validate`. At run time, the playbook refuses
   an invalid timeline. The primary also refuses to mark the timeline it
   currently writes.
10. **Validate, commit and push the one-time playbook:**
    `mmx validate 2026-11-03_mark_the_split_timeline_as_archived_on_the_database_servers`,
    commit the one-time playbook, push.
    **Check:** `mmx validate` passes, and the push succeeds.
11. **Run the one-time playbook, after the person approves:**
    `./server_management_scripts/run_mmx_on_util01 run 2026-11-03_mark_the_split_timeline_as_archived_on_the_database_servers`.
    The run ends after the full backup ends: `systemctl start` waits for
    the backup's one-shot service, and the task allows 3 hours
    (`time_limit: 3h`).
    **Check:** the run passes. A failure that says
    "is the timeline this primary writes now, not the split one; nothing
    was marked" means `split_timeline` names the new primary's timeline:
    correct `split_timeline` from step 2, then repeat steps 10 and 11.
12. **Check the archiver on the new primary:** repeat step 1's
    `pg_stat_archiver` query on the new primary, using the new primary's
    name in place of `db01`.
    **Check:** the archiver's `failed_count` stops rising.
13. **Check that MMWatchdog's `write_ahead_log_archiving` check recovers,**
    on the new primary, as
    [Making a change](../AGENTS.md#making-a-change) says after a fix of
    what MMWatchdog warned about:
    `ssh -F ssh/config root@10.20.2.3 'mmwatchdog check-now write_ahead_log_archiving --count-as-scheduled-run'`,
    with the new primary's private address.
    **Check:** the check passes, and the warning closes once the check has
    been healthy for its `recovered_after_healthy_for`, 1 minute for
    `write_ahead_log_archiving` (`mmwatchdog_checks/database_servers.yml`).
14. **Confirm the new full backup:**
    `ssh -F ssh/config root@10.20.2.3 'sudo -u postgres pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=main info'`
    on the new primary, with the new primary's private address.
    **Check:** the output lists the new full backup.
15. **Complete the one-time playbook:**
    `mmx complete-one-time-playbook 2026-11-03_mark_the_split_timeline_as_archived_on_the_database_servers`,
    commit the file move, and push.
    **Check:** the playbook is in `one_time_playbooks/completed/`.

## If something is different

- **Step 7 stops before the switchover** when the fleet hub does not
  confirm a database server's alert hold within 25 seconds: the run stops
  during `hold_the_alerts_of_the_database_servers`, and the primary does
  not change. **Step 7 needs a healthy replica:**
  the failover monitor must report the named server as healthy and in the
  assigned `secondary` state. Both come from the header of
  `playbooks/switch_database_primary.yml`. Read the run's result with
  `./server_management_scripts/run_mmx_on_util01 results`, then repeat
  step 6's check before running step 7 again.
- **A restore to a time inside the recovery limit:** read
  [The recovery limit](#the-recovery-limit) before choosing the time.

## Why the archive refuses the primary's segments

The cause that this procedure fixes: two servers continued from the same
point with different data histories, as after a restart during failover.
After the histories split, the primary and the server whose history
differs from the primary's wrote log segments with matching names but
different contents.
The production backup bucket holds segments from the server whose history
differs from the primary's, so pgBackRest refuses to overwrite the
archived segments and refuses the primary's copies.

## Why every database server is marked

The primary replaced in step 7 keeps markers for the split timeline's
segments (`.ready` files in `pg_wal/archive_status/`).
pg_rewind copies the split timeline's `.ready` markers when pg_rewind
makes a server's data match the primary's.
A server with the split timeline's `.ready` markers will try the refused
segments again when the server becomes primary.
The split timeline's refused segments can never be archived.
The production backup bucket holds the removed server's segments under
names matching the refused segments' names, but with different contents.

## The recovery limit

A restore to a time between the split and the end of step 11's full
backup reads the removed server's history.
A restore within the interval does not restore the history the apps saw
between the split and the end of step 11's full backup.
Earlier and later times restore as usual.
