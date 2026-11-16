# Reboot servers after updates

**When to use this page:** in the team's weekly window
(`maintenance_window` in `mmx_project_settings.yml`), after updating the
database servers.

**What this page does:** each server whose installed updates wait for a
reboot reboots, one at a time, and then MMWatchdog confirms that no reboot
waits.

**Who acts:** the coding agent runs every step from the systems desk. Only
the person decides to reboot the only server of a pool outside the weekly
window, because that server's users see the reboot.

## Before you start

- **No server reboots by itself.** On Debian, unattended-upgrades' kernel
  hook writes `/var/run/reboot-required` when a kernel package is installed.
  The marker means a new kernel needs a reboot. Library and service
  restarts are needrestart's job.
- **Update the database servers first,** with `update_database_servers`
  ([Update and restart the database servers](update_and_restart_the_database_servers.md)).
  `update_database_servers` reboots the database servers itself.
- **Run the two playbooks in order:** `reboot_servers_after_updates`, then
  `reboot_util01_after_updates`.

## Steps

1. **Reboot the servers other than `util01`:**
   `./server_management_scripts/run_mmx_on_util01 run reboot_servers_after_updates`.
   `reboot_servers_after_updates` reboots servers whose updates require a
   reboot, one at a time.
   `reboot_servers_after_updates` skips database servers, which
   `update_database_servers` reboots, and `util01`, which needs a run from a systems desk.
   MMX waits for the rebooted server's services to work again before
   rebooting the next server
   ([service checks](../playbooks/reboot_servers_after_updates.yml)).
   While a server reboots, the remaining servers in the rebooting server's
   pool handle requests or run background jobs.
   **Check:** the run passes. A server that waits for the window is
   skipped, with the line that says until when (see
   [If something is different](#if-something-is-different)).
2. **Reboot `util01`, from a systems desk:**
   `sudo -n -u servers-mmx run-mmx-on-the-servers run reboot_util01_after_updates --connection ssh_only`.
   MMX never reboots the machine it runs on.
   **Check:** the run passes. If a run on `util01` holds its lock, the run
   from the systems desk stops without changing anything (see
   [If something is different](#if-something-is-different)).
3. **Verify,** after `update_database_servers`, `reboot_servers_after_updates`,
   and `reboot_util01_after_updates` pass: run MMWatchdog's `security_updates`
   check group on every server, including `util01`.
   Count the `security_updates` run as the scheduled run so a warning from
   the `security_updates` check group closes:

   ```sh
   # This systems desk, in the coding agent's checkout: every server in the inventory, systems desks left out.
   mmx nodes --json |
     jq -r '.nodes[] | select(.groups | index("systems_desks") | not) | "\(.name) \(.address)"' |
     while read -r name address; do
       echo "== $name"
       ssh -n -F ssh/config "root@$address" 'mmwatchdog check-now security_updates --count-as-scheduled-run'
     done
   ```

   **Check:** the SSH command shows `no_reboot_waits ok` on every server, and
   `no_security_update_waits ok` too on every database server, whose updates
   of Postgres, pg_auto_failover, PgBouncer, and the kernel only
   `update_database_servers` installs.
4. **Mark the checklist item `weekly_window_updates_and_reboots` done.**
   **Check:** none needed: step 3 is the item's proof.

## If something is different

- **A server waits for the maintenance window.** The only server of an app
  or load-balancer pool, such as `app001` alone, reboots only inside the
  weekly window, because its users see the reboot. Outside the window the
  run skips it and says until when, such as
  "app001 waits for the maintenance window: tuesday 2026-11-17 21:00 UTC,
  for 60 minutes". A reboot runs at any time on a pool with another
  server, a jobs server, `staging01`, and before go-live
  (`public_site_checks_run: false`).
- **The person wants such a server rebooted outside the window,** knowing
  that its users see the reboot: add
  `--var reboot_the_only_server_of_a_pool_outside_the_maintenance_window=true`
  to the command of step 1. The triage agent's requests never carry it.
- **A server does not come back** within the run's come-back wait
  (`come_back_wait_after_a_reboot` in `mmx_project_settings.yml`,
  3 minutes by default; a cloud server came back in under a minute): the run
  fails, and with that answer the triage agent replaces the server at
  once ([Replace a server](replace_a_server.md#a-failed-server-the-three-replacement-playbooks)).
- **A run on `util01` holds its lock during step 2.** The run from the
  systems desk stops without changing anything.
  After the run holding `util01`'s lock ends, run
  `sudo -n -u servers-mmx run-mmx-on-the-servers run reboot_util01_after_updates --connection ssh_only` again.

## What users see

With `app001` alone, the apps are down while `app001` reboots.
The app downtime lasts about 20 seconds on a cloud VPS.
A dedicated server takes a few minutes because its firmware checks run first.

## When the triage agent runs the reboots

With `what_the_triage_agent_may_do_without_a_person:
routine_fixes_and_server_work`, the triage agent requests the run of
`reboot_servers_after_updates` by itself when MMWatchdog's
`no_reboot_waits_that_may_run_now` alerts, and MMHotline runs it after its
warning unless someone presses Stop. After a Stop, nothing runs and no new
alert comes; the weekly review lists the reboot that waits.

## Background

`reboot_servers_after_updates` and `reboot_util01_after_updates` leave a
server unchanged when `/var/run/reboot-required` is absent.

`mmx nodes --json` lists the servers of `inventories/servers.yml` with
their WireGuard addresses and reads no secret, and `ssh -n` keeps each SSH
connection from reading the list meant for the loop.
