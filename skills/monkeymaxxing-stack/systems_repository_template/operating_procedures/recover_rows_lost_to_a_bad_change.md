# Recover rows lost to a bad change

**When to use this page:** a person notices rows lost after a bad database
change, such as a release or a script that deleted them. When much of the
database is wrong, restore the whole database instead:
[Bring the whole database back to a chosen minute](recover_when_every_database_server_is_lost.md#bring-the-whole-database-back-to-a-chosen-minute)
loses every later change, while this page keeps them.

**What this page does:** the playbook `recover_rows_from_a_restored_copy`
creates a temporary server, `restore01`, restores a separate copy of
production's database onto it as the database stood at the minute before
the bad change, copies the chosen rows from that copy back to the primary,
and destroys `restore01`, all in one run on `util01`
([Restore a database copy and recover the missing rows](#restore-a-database-copy-and-recover-the-missing-rows)).
A preview run shows what the real run would add and changes nothing; the
real run follows only after the person approves.

**Who acts:** database servers always need a person
([The rules](../AGENTS.md#the-rules), "What the triage agent may do
without a person"). The triage agent hands over to a person on missing
rows and does not follow this page
([When to hand over](../triage_agent_rules.md#when-to-hand-over)).
The coding agent does every step from the systems desk. The person tells
when the bad change occurred and which data is missing, approves the
temporary server's price, and approves the live-data correction. The
person runs nothing in the person's own terminal.

**Terms:** this page uses the Stack's terms, such as primary, inventory,
restore drill and B2.
[Technical terms](../talking_with_the_team.md#technical-terms) explains
each term. The primary is the database server that
`sudo -u postgres pg_autoctl show state --pgdata /var/lib/postgresql/17/pg_auto_failover_monitor --formation production`
on `util01` lists as `primary`, or as `single` while the server is alone;
the playbook finds it the same way.

## Before you start

- **Tell the person before work:**

  > First, I will restore the backup onto a separate temporary server.
  > Restoring the backup onto the temporary server will not change your live
  > database.
  > Then I will find the missing rows and show you what I would copy back.
  > I will ask for your approval before changing the live database.
  > When did the bad change occur?

- **Ask which data is missing** after the person answers.
- **State the temporary server's current price and get approval before
  the first run.** Read the price with
  `./server_management_scripts/read_the_monthly_price_at_the_provider --server-type TYPE --location LOCATION`,
  with `restore_drill_server_type` and `restore_drill_location` from
  `mmx_project_settings.yml`
  ([the provider-script contract](../server_management_scripts/README.md#write-the-teams-provider-scripts)).
  Each run creates `restore01` and destroys it again within the run.
- **Find the restore time: the minute before the bad change started.**
  The person's answer says when the rows went missing, such as "rows from
  14:00 to 14:20"; that is not the restore time. Find when the bad change
  itself started, such as a release's run in
  `./server_management_scripts/run_mmx_on_util01 results`, or the app's
  logs. Write the restore time in UTC, as `2026-11-03 14:01:00+00`. For a
  time in the person's own time zone, convert it on the desk, which runs
  Debian and GNU `date`:
  `date -u -d '2026-11-03 15:01 CET' '+%Y-%m-%d %H:%M:00+00'` prints
  `2026-11-03 14:01:00+00`.
- **The playbook needs the team's provider scripts,** as the weekly
  restore drill does: it creates and destroys `restore01` with them
  ([Write the team's provider scripts](../server_management_scripts/README.md#write-the-teams-provider-scripts)).
- **Nothing to commit.** The run takes its values on the command line.
  `restore01` and its SSH host key exist only in a throwaway copy of the
  systems repository on `util01`, so the desk needs no change and never
  connects to `restore01`.

## Restore a database copy and recover the missing rows

1. **Fill in the values.** The command of steps 2 and 4 takes:

   | Value | What to give |
   | --- | --- |
   | `recover_to` | The restore time from [Before you start](#before-you-start), such as `"2026-11-03 14:01:00+00"`. `latest` is refused: it would restore the bad change too. |
   | `read_backup_bucket_as_of` | The time the first run starts, such as `"2026-11-03 15:30:00+00"`. pgBackRest reads the backup bucket as it stood then, so later changes to the bucket don't count. Keep the same value for every run of this recovery. |
   | `database_name` | The app's `database_name` in `mmx_project_settings.yml`, such as `shop`. |
   | `table` | The table that lost rows, as SQL names it, such as `orders` or `billing.invoices`. The table needs a primary key. |
   | `rows_where` | An SQL condition that selects the lost rows, such as `created_at >= '2026-11-03 14:00:00+00' AND created_at < '2026-11-03 14:20:00+00'`, or `customer_id = 4711`. |
   | `when_a_primary_key_exists` | What happens to a copied row whose primary key the primary already holds. `skip_the_row`: the row is skipped, and the rest are added. `change_nothing`: one such row stops the run, and the primary keeps no change. Choose `skip_the_row` unless the person wants to look at every such row first. |

   Tell the person the values in plain words: which table, which rows,
   and from which minute.
   **Check:** the person agrees that the values describe the missing data.
2. **Preview: restore the copy and count the rows.**
   `add_the_rows_to_the_primary` is `false` by default, so the preview
   changes nothing on the primary:

   ```sh
   ./server_management_scripts/run_mmx_on_util01 run recover_rows_from_a_restored_copy \
       --var recover_to="2026-11-03 14:01:00+00" --var read_backup_bucket_as_of="2026-11-03 15:30:00+00" \
       --var database_name=shop --var table=orders \
       --var rows_where="created_at >= '2026-11-03 14:00:00+00' AND created_at < '2026-11-03 14:20:00+00'" \
       --var when_a_primary_key_exists=skip_the_row
   ```

   The run takes a few minutes, mostly the restore: the weekly drill's
   restore took 3 to 5 minutes on the Stack's tests. It runs the restore's
   check queries on the copy, then the whole correction on the primary in
   one transaction, and rolls the transaction back. Its output, which
   `./server_management_scripts/run_mmx_on_util01 results` shows on the
   desk after the run, holds the counts as one JSON line, and no row's values:

   ```json
   {"primary": "db01", "database_name": "shop", "table": "orders", "rows_from_the_restored_copy": 42, "rows_whose_primary_key_exists": 2, "rows_whose_primary_key_exists_with_other_values": 0, "rows_on_the_primary_before": 2, "rows_added": 40, "rows_on_the_primary_after": 42, "added_to_the_primary": false}
   ```

   - `rows_from_the_restored_copy`: the rows that `rows_where` selects on
     the copy, from just before the bad change.
   - `rows_whose_primary_key_exists`: of those, the rows whose primary key
     the primary holds now; `..._with_other_values`: of those, the rows the
     primary holds with other values.
   - `rows_on_the_primary_before`, `rows_added`, `rows_on_the_primary_after`:
     the rows that `rows_where` selects on the primary before and after,
     and the rows the real run adds.

   **Check:** the run passes, its results' last lines say "preview, nothing
   changed", and the counts describe the data that the person said is
   missing. When they don't, change `rows_where` and preview again with
   the same two times.
3. **Get the person's approval for the live-data correction.** Tell the
   person the preview's counts in plain words, such as "40 orders from
   14:00 to 14:20 come back; 2 are still there and stay as they are". Name
   any row whose primary key the primary holds with other values: a
   customer may have changed it since, and the run keeps the primary's
   version.
   **Check:** the person approves. Without approval, change nothing on the
   primary.
4. **Add the rows to the primary:** the same command with the same values,
   plus `--var add_the_rows_to_the_primary=true`.
   **Check:** the run passes; its results' last lines (`run_mmx_on_util01
   results`) say "added N rows to TABLE on PRIMARY", and its counts match the preview's, apart from changes
   customers made in between.
5. **Report to the person** which rows returned, with the run's counts:
   the rows before, the rows added, and the rows after.
   **Check:** none, because the report is the last step.

After each run, `restore01` is gone again: the run destroys it, removes its
WireGuard peer from `util01`, and deletes the throwaway copy, also after a
failure.

## If something is different

- **The run says "restore01 already exists at the provider" or "the
  inventory has a restore server":** a restore drill or an earlier run left
  `restore01`. Wait for a drill that runs to end; otherwise destroy the
  leftover as below, then run again.
- **The run says "destroying restore01 FAILED", or a run was stopped with
  `run_mmx_on_util01 stop`:** `restore01` still holds a copy of production's
  database. Destroy it with the command the run printed, or with
  `./server_management_scripts/destroy_a_server_at_the_provider --server-name restore01`
  after `./server_management_scripts/list_the_servers_at_the_provider` shows
  it. Then run `./server_management_scripts/run_mmx_on_util01 run every_server`
  to remove its WireGuard peer from `util01`.
  **Check:** the provider lists no `restore01`. Until then the weekly drill
  does not run, and the daily check `check_for_a_leftover_restore01` warns.
- **The run says "an SQL error ended the transaction on the primary":**
  nothing changed on the primary. psql's error above it says why, without
  row values:
  - `duplicate key value violates unique constraint "orders_pkey"` with
    `change_nothing`: the primary holds some of the rows' primary keys;
    the line before names how many. Show the person, and preview with
    `skip_the_row`, or narrow `rows_where`.
  - another unique constraint, such as `orders_email_key`: a row the
    primary holds now has the same value. Tell the person; narrow
    `rows_where` to leave that row out.
  - `the table ... has no primary key`: the playbook cannot tell a lost
    row from a row the primary holds. Tell the person; this page does not
    fit.
  - an error about a column, such as a missing or new column: the bad
    change also changed the table. The error may name one value. Tell the
    person; this page does not fit.
- **The run says "the failover monitor names no single primary":** a
  failover is under way. Wait until
  `pg_autoctl show state` on `util01` shows one primary, then run again.
- **The restore fails with "recovery ended before configured recovery
  target was reached":** `recover_to` is later than the newest change in
  the backup bucket at `read_backup_bucket_as_of`. Use a later
  `read_backup_bucket_as_of`, such as now.
- **Several tables lost rows:** run steps 1 to 4 for each table. Copy the
  rows of a table that others refer to first, such as `customers` before
  `orders`, so each insert finds the rows it refers to.
- **Much of the database is wrong:** restore the whole database instead,
  with [Bring the whole database back to a chosen minute](recover_when_every_database_server_is_lost.md#bring-the-whole-database-back-to-a-chosen-minute).
