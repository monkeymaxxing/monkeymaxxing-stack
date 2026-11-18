# Rebuild the utility server util01

**When to use this page:** the two hub-outage alerters alert that `util01`
is unavailable. The MMHotline-down alarm also alerts after the minutes in
`mmhotline_down_alarm.wake_the_person_on_call_after_minutes_without_a_check_in`
without MMHotline check-ins.
The hub-outage alerters are the first reporting app server and database
server in their inventory pools. While `util01` works,
`sudo mmwatchdog fleet` on `util01` names the hub-outage alerters.

**What this page does:** a new `util01` replaces the lost one, built from
this systems repository from a systems desk. In step 3, MMHotline restores
its own database, including the MMHotline-down alarm and status page setup.
The database servers register again with the new failover monitor.

**Who acts:** the coding agent does every step from a systems desk that
holds this systems repository and the vault passphrase. The coding agent
runs MMX on that systems desk until the coding agent can run MMX on the
new `util01`. The person on call, and any backup person named in the
schedule, acknowledge each alarm in Pushover, and the person on call claims
an open SOS when step 3 asks.

## Before you start

- **The replacement keeps the name `util01` and the inventory's existing
  private address,** such as `10.20.0.1`.
  Reason: every other server's settings name this single utility server.
- **Follow the numbered rebuild steps below in order.** Two of them use
  [Add a server](add_a_server.md):
  - Use steps 2–4 of [Add a server](add_a_server.md) within rebuild
    step 2, for server creation, inventory edits, and SSH host-key
    acceptance.
  - Use steps 7–8 of [Add a server](add_a_server.md) within rebuild
    step 8, for the reboot and verification.
- **The team's main copy of the systems repository was on the lost
  `util01`.** The desk's checkout becomes the main copy until step 4
  pushes `main` to the new `util01`. Commits that only the lost `util01`
  had, such as the triage agent's newest notes or a server replacement's
  inventory commit, are gone; a failing run or a leftover server shows
  such a gap
  ([The main copy and the backup at the Git host](../AGENTS.md#the-main-copy-and-the-backup-at-the-git-host)).
- **A push alone changes no server.** Apply each configuration change as
  [Making a change](../AGENTS.md#making-a-change) says: run `every_server`
  or the playbook the step names.
- **Without the provider scripts,** use the provider's own command-line
  tool, as
  [Without the provider scripts](../server_management_scripts/README.md#without-the-provider-scripts)
  says.

## Steps

1. **Tell the person on call, and any backup person named in the schedule,
   before destroying the old `util01`.**
   If the old `util01` still runs, destroy the old `util01` first
   (`./server_management_scripts/destroy_a_server_at_the_provider --server-name util01`), so
   only one MMHotline writes to its backup.
   The hub-outage alerters alert at once. After MMHotline's check-ins stop, the
   MMHotline-down alarm wakes the person on call after the minutes in
   `mmhotline_down_alarm.wake_the_person_on_call_after_minutes_without_a_check_in`
   and the backup (the named backup, or everyone else available) after
   `mmhotline_down_alarm.wake_the_backup_after_minutes_without_a_check_in`,
   5 and 10 in the template.
   A rebuild takes longer than both of the MMHotline-down alarm's delays.
   The alarms continue until the new `util01`'s MMHotline checks in again.
   Each person who receives an alarm acknowledges the alarm in Pushover.
   **Check:** the destroy script returns `"deleted": true`
   ([the provider-script contract](../server_management_scripts/README.md#write-the-teams-provider-scripts)),
   or the old `util01` was already gone.
2. **Prepare the new `util01` on the systems desk,** following steps 2 to 4 of
   [Add a server](add_a_server.md), with the utility-server exceptions below.
   - First make the desk's checkout the main copy again, so
     publishing, as [Making a change](../AGENTS.md#making-a-change) says, works without the lost `util01`:
     `ssh desk01-agent 'cd systems_repository && git remote remove origin'`.
   - Run `wg genkey` and pipe the private key to `wg pubkey`.
     Hold the pair only in memory.
   - Render first-boot data with util01's existing private address and every
     systems desk as a peer; omit a utility-server self-peer.
   - Pass the private key once to the provider and keep no copy.
   - Delete the old `util01` host-key line from `ssh/known_hosts`.
   - Keep `util01.address` and `private_ip` at the existing private address.
     Set `public_ipv4_address` to the new provider address, `server_type` and
     `location` to the create script's, and replace
     `wireguard_public_key` with the setup-generated public key.
   - Trust the new SSH host key over wg0, as shared step 4 shows.
   - Commit the inventory and host key, and publish them, as
     [Making a change](../AGENTS.md#making-a-change) says. Skip shared step 3's
     utility-server run: the new `util01` is not configured yet.

   Reason: systems desk access reaches the new utility server directly. A
   utility-server self-peer or the lost server's private key is unnecessary.
   **Check:** shared step 4's SSH connection over wg0 succeeds, and `main`
   on the desk holds the new inventory values and host-key line.
3. **Configure the new `util01`:** run
   `sudo -n -u servers-mmx run-mmx-on-the-servers run every_server --connection ssh_only --limit util_server`
   from the systems desk. MMX reuses the first-boot WireGuard key and creates
   the new `mmhotline` and triage SSH keys, and the empty main copy of the
   systems repository.
   Remaining servers still know the old utility key until steps 6 and 7
   apply the replacement utility peer and SSH keys from the systems desk.
   Tell the person on call what to expect from the restored MMHotline, as
   [What the restored MMHotline does in step 3](#what-the-restored-mmhotline-does-in-step-3)
   lists.

   The step 3 run installs the server settings comparison and restore drill timers. The scheduled
   jobs need `util01`'s copy of the systems repository, cloned in step 7; read any early job
   failure before treating the rebuild as complete.

   **Check that MMHotline's data came back.** In the step 3 result, the
   task `restore_the_mmhotline_database_from_its_backup` prints
   "restored mmhotline.db from the backup at ..." when the backup held a
   copy. If it prints "holds no copy of mmhotline.db" instead, stop, as
   [If something is different](#if-something-is-different) says.
   (The task is skipped without a message only when
   `/var/lib/mmhotline/mmhotline.db` already exists, which a new server
   does not have.) Then open MMHotline's page and check that each
   person on the schedule still has a contact method listed (each person
   added those, such as a Pushover user key, after the first install).
4. **Push `main` to the new `util01`, then replace the old utility SSH
   keys.** Make the new main copy the checkout's `origin` again, as chapter
   7's step 3 does:

   ```sh
   # On the laptop:
   ssh desk01-agent 'cd systems_repository && git remote add origin root@10.20.0.1:/var/lib/systems_repository.git && git push --quiet -u origin main'
   ```

   Each other desk of the team trusts the old `util01`'s host key, so its
   pull fails with a changed host key. On each such desk, its coding agent
   puts the new `util01` line of `ssh/known_hosts` into its checkout by
   hand from this desk's commit, pulls with `git pull --ff-only`, and
   drops the hand edit if the pull keeps it changed.

   Then read the SSH public keys with
   `sudo -n -u servers-mmx run-mmx-on-the-servers results --node util01 --json`.
   Replace the old utility SSH keys with each task's `public_key`:

   - `util_server/ssh_key_of_the_mmhotline_user`.
     Replace the `mmhotline` user's line in `root_ssh_public_keys` in
     `mmx_project_settings.yml`.
   - `util_server/ssh_key_of_the_triage_agent`. The two SSH tasks are in fleet stage `util_server`.
     Set `triage_ssh_public_key` in `mmx_project_settings.yml`.

   Commit, and publish, as [Making a change](../AGENTS.md#making-a-change) says.
   Then register the new `mmhotline` user's public key at the server
   provider under the name `util01, the mmhotline user`.
   Every new server and each week's `restore01` start with the public key
   registered as `util01, the mmhotline user`.
   MMX on `util01` uses the `mmhotline` user's SSH key to log in to new
   servers, including each week's `restore01`.
   Replace the old registered key with the command or request the
   [provider guide](../provider_guides/) gives.
   **Check:** `git ls-remote origin main` on the desk shows the desk's
   `main`, and the registered public key equals the new utility key.
5. **Find the database primary.** The new failover monitor knows no
   database server. Each database server must register again in the
   database server's own `database_server` stage.
   Register the primary first: a replica waits up to five minutes for a primary.
   The stage runs one database server at a time, in name order, and stops at the first failure.
   After a failover, a replica's name may come first. A replica processed
   before the primary would wait, fail, and prevent the primary from
   registering.
   On each database server, run the following SSH command:

   ```sh
   ssh -F ssh/config root@10.20.2.1 'sudo -u postgres psql -XAt -h /var/run/postgresql -p 5432 -c "select pg_is_in_recovery()"'
   ```

   **Check:** the command prints `f` on the primary and `t` on a replica.
6. **Register the primary first,** here `db02`: run only its `every_server` and
   `database_server` stages. The `every_server` stage gives the primary
   the new `util01`'s keys. The `database_server` stage registers the
   primary with the new monitor.
   Step 4 published its key changes before the run.

   ```sh
   sudo -n -u servers-mmx run-mmx-on-the-servers run every_server --connection ssh_only --only-fleet-stages every_server,database_server --limit db02
   ```

   **Check:** MMX reports: "registered the node
   db02, the primary, with the monitor at 10.20.0.1:5432, which had no
   record of it".
7. **Run `every_server` again from the systems desk, for every server:**

   ```sh
   sudo -n -u servers-mmx run-mmx-on-the-servers run every_server --connection ssh_only
   ```

   The step 7 run gives the new `util01`'s keys to every other
   server and registers each replica with the monitor.
   The step 7 run also clones `util01`'s copy of the systems repository, `/var/lib/mmhotline/systems_repository`.
   MMHotline trusts every commit on the main copy
   (`systems_repository_commits.trusted_commits: every_commit_on_origin`), so the new
   `util01` needs nothing more before it runs `main`.

   Then compare every environment's live web and job images
   with the inventory's requested tags. Run `deploy` on `util01` for any
   environment requiring deployment, including a release selected while
   `util01` was down.
   No automatic catch-up or timed deployment retry runs.

   At the end of the step 7 run, the first restore drill starts, as on a
   new system. The new `util01` has no record of a drill that passed.
   The restore drill holds `util01`'s lock until the drill ends, about as
   long as the last drill took.
   Read `/var/lib/restore_drill/latest_result.json` and the drill journal
   on `util01`. Update `backups_restore_every_week` from the evidence.

   **Check:** the run passes, and each running release is verified after
   the deploy.
8. **Reboot and verify.** From a systems desk, reboot the replacement `util01` to use the updates
   installed during the rebuild.
   Follow step 7 of [Add a server](add_a_server.md) for `util01`.
   Step 8's reboot refuses to start while the drill runs: rerun step 8's
   reboot once the shared lock is free.
   Verify the replacement `util01` with step 8 of
   [Add a server](add_a_server.md).
   **Check:** step 8 of Add a server passes, and on `util01`,
   `sudo mmwatchdog fleet` lists every inventory server as reporting.

## If something is different

- **Step 3 prints "holds no copy of mmhotline.db":** stop. This
  `util01` starts MMHotline with no people and no contact methods, so an
  SOS would reach nobody. Check that `backups.mmhotline_backup_replica_url`
  in `mmx_project_settings.yml` is the address the old `util01` backed up
  to, then restore before going on.
- **Step 3's `apply_the_mmhotline_settings` task fails** with MMHotline's
  reason ("wait for MMHotline to close the open Pushover emergency
  messages"): a new Pushover application token is refused while an SOS
  that rings through Pushover is still unclaimed. Have the person on call
  claim the SOS, then run `every_server` again to apply the new token.
- **Step 8's reboot refuses to start:** the restore drill still runs and
  holds the shared lock. Read the drill's result as step 7 says, then rerun
  step 8's reboot once the shared lock is free.
- **Every database server is lost too, or the database goes back to an
  earlier minute:** skip steps 5 and 6, as
  [The location or provider is lost](recover_when_every_database_server_is_lost.md#the-location-or-provider-is-lost)
  and [A lock-out is on, or util01 may be compromised](recover_when_every_database_server_is_lost.md#a-lock-out-is-on-or-util01-may-be-compromised)
  say.

## What the restored MMHotline does in step 3

The Stack's own test, recorded in the stack's repository's
`docs/testing.md`, "Restored MMHotline alerts on a rebuilt util01", showed
the following. The run restores MMHotline's database before it writes and
installs the settings, and `apply_the_mmhotline_settings` comes near
the end of the run. The wait looks long, but MMHotline reads
`/etc/mmhotline/mmhotline_settings.yml` itself within seconds of
starting, so the settings in force are the repository's current ones,
not the old ones. Tell the person on call to expect:

- An SOS that nobody claimed before the loss is not sent again at the
  start. It continues with its saved times: at the time saved with
  the SOS, MMHotline contacts everyone available. The incident page
  lists whom MMHotline contacted before the loss, even when the
  repository's on-call schedule has since changed. The test did not
  cover an SOS whose saved time passed while `util01` was down;
  MMHotline's startup is documented to catch up on such work.
- A part of the settings that needs a test with an outside service
  (the sending services, the MMHotline-down alarm, the status page) keeps its
  earlier, restored setup until that test passes.
- A new Pushover application token is refused while an SOS that
  rings through Pushover is still unclaimed. MMHotline keeps the
  restored token and sends that SOS with it, and the run's
  `apply_the_mmhotline_settings` task fails with MMHotline's reason
  ("wait for MMHotline to close the open Pushover emergency
  messages"). Have the person on call claim the SOS, then run
  `every_server` again to apply the new token.
