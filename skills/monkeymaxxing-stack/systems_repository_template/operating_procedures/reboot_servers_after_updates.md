# Reboot servers after updates

**When to use this page:** MMWatchdog's `no_reboot_waits` warns on a
production pool's only server, such as `app001` alone (after 30 days), or
the person wants such a server rebooted now, such as for a flaw that
attackers exploit. Every other server reboots by itself in the automatic
weekly maintenance, which needs no step here. This page also says what to
do when the automatic weekly maintenance stops short.

**What this page does:** each server whose installed updates wait for a
reboot reboots, one at a time, and then MMWatchdog confirms that no reboot
waits.

**Who acts:** the coding agent runs every step from the systems desk. Only
the person decides to reboot the only server of a pool, because that
server's users see the reboot. Plan it in the maintenance window
(`maintenance_window` in `mmx_project_settings.yml`, in UTC), the quiet
hour the team chose.

## Before you start

- **No server reboots at an hour nobody chose.** On Debian,
  unattended-upgrades' kernel hook writes `/var/run/reboot-required` when
  a kernel package is installed. The marker means a new kernel needs a
  reboot. Library and service restarts are needrestart's job.
- **The automatic weekly maintenance** (`automatic_weekly_maintenance` in
  `mmx_project_settings.yml`, `true` in the template) runs at the start of
  the maintenance window on `util01`. It never takes the site down:
  1. With two or more database servers, it updates and restarts them, but
     only when one of them waits for something
     ([Update and restart the database servers](update_and_restart_the_database_servers.md)).
     `db01` alone waits for a person.
  2. It runs `reboot_servers_after_updates` for the servers of each pool
     of two or more, and `staging01`. A production pool's only server,
     including a jobs server alone, waits for a person, as it does before
     go-live. Right before each reboot, the other servers of the pool run
     `check-that-this-server-does-its-work`; when none of them passes, the
     server waits for next week instead of taking the pool's work down.
  3. When that run ended with success, `util01` reboots itself, but only
     when its updates wait for a reboot, the maintenance did not end
     early, the window is still open, nothing holds or waits for its lock,
     and no SOS incident is open.
  4. Each systems desk reboots itself at the same hour, when its updates
     wait for a reboot and nobody uses it.

  It gives way: when MMHotline waits for `util01`'s lock, for a run that
  the triage agent or a person asked for, or when the window has ended,
  it finishes the server it works on and ends. What it did not reach waits
  for next week, and MMWatchdog reminds after 15 days.

## Steps

1. **Reboot the only server of a pool,** in the maintenance window:
   `./server_management_scripts/run_mmx_on_util01 run reboot_servers_after_updates`.
   `reboot_servers_after_updates` reboots servers whose updates require a
   reboot, one at a time, and skips database servers, which
   `update_database_servers` reboots, and `util01`. MMX waits for the
   rebooted server's services to work again before rebooting the next
   server ([service checks](../playbooks/reboot_servers_after_updates.yml)).
   While a server of a pool of two or more reboots, the remaining servers
   carry the requests or the jobs. While the only app server reboots,
   `util01` pauses its public site checks for 3 minutes, so the planned
   minute of downtime raises no SOS, and ends the pause once the server
   does its work again (its containers and tunnel have started).
   **Check:** the run passes. A server that waits for the window is
   skipped, with the line that says until when (see
   [If something is different](#if-something-is-different)).
2. **Verify:** run MMWatchdog's `security_updates` check group on each
   server that rebooted. Count it as the scheduled run so a warning from
   the `security_updates` check group closes:

   ```sh
   # This systems desk, in the coding agent's checkout. ADDRESS: the server's WireGuard address, such as 10.20.1.1.
   ssh -n -F ssh/config root@ADDRESS 'mmwatchdog check-now security_updates --count-as-scheduled-run'
   ```

   **Check:** the SSH command shows `no_reboot_waits ok`.

## When the automatic weekly maintenance stops short

`util01`'s MMWatchdog warns about a failed `weekly_maintenance.service`
(`no_systemd_unit_has_failed`), or `no_reboot_waits` reminds on a server
that the maintenance reboots (after 15 days: two weekly runs passed
without the reboot). Read why on `util01`:

```sh
# This systems desk, in the coding agent's checkout.
ssh -F ssh/config root@10.20.0.1 'journalctl -u weekly_maintenance -u reboot_util01_after_the_weekly_maintenance --since -15d --no-pager'
```

- **"ended early ... gives way to MMHotline" or "the maintenance window
  ... has ended":** nothing failed. A run that MMHotline waited for, or
  a long night, took the time. The next window goes on.
- **"... waits for next week's maintenance: no other server of
  app_servers does its work now":** the other servers of that pool failed
  `check-that-this-server-does-its-work` right before the reboot, so
  rebooting this one would have stopped the pool's work. Their own alerts
  say why; fix them, and the next window reboots the server.
- **A run failed:** the journal names the playbook, and
  `./server_management_scripts/run_mmx_on_util01 results` names the
  server and the task. A server that did not come back is replaced like
  any failed server
  ([Replace a server](replace_a_server.md#a-failed-server-the-three-replacement-playbooks)).
  Fix the cause, then let the next window run, or run step 1 now.
- **`util01`'s reboot waited:** the journal of
  `reboot_util01_after_the_weekly_maintenance` says why: an early end of
  the maintenance, a closed window, a held lock or an MMHotline run that
  waits for it, an open SOS incident, or a lock-out. To reboot `util01` now, from a systems
  desk:
  `sudo -n -u servers-mmx run-mmx-on-the-servers run reboot_util01_after_updates --connection ssh_only`.
  If a run on `util01` holds its lock, that run stops without changing
  anything: run it again when the other run ends.
- **A desk's reboot waited:** a login, a desk job or an `mmx` run was going
  on, the desk could not tell (a `loginctl`, `systemctl` or `pgrep` that
  failed), or the desk is the one that keeps access during a lock-out. The
  desk's person can read why with `journalctl -u reboot_systems_desk_after_updates`
  on the desk. The desk tries again at next week's quiet hour.

## If something is different

- **A server waits for the maintenance window.** In a person's run, the
  only server of an app or load-balancer pool, such as `app001` alone,
  reboots only inside the window, because its users see the reboot.
  Outside the window the run skips it and says until when, such as
  "app001 waits for the maintenance window: wednesday 2026-11-25 03:00 UTC,
  for 120 minutes". A person's run reboots at any time a server of a pool
  with another server, a jobs server, `staging01`, and any server before
  go-live (`public_site_checks_run: false`).
- **The person wants such a server rebooted outside the window,** knowing
  that its users see the reboot, such as for a flaw that attackers exploit
  now: add
  `--var reboot_the_only_server_of_a_pool_outside_the_maintenance_window=true`
  to the command of step 1.
- **A server does not come back** within the run's come-back wait
  (`come_back_wait_after_a_reboot` in `mmx_project_settings.yml`,
  3 minutes by default; a cloud server came back in under a minute): the
  run fails, the 3-minute pause of the public site checks ends by itself,
  and with `routine_fixes_and_server_work` the triage agent replaces the
  server at once
  ([Replace a server](replace_a_server.md#a-failed-server-the-three-replacement-playbooks)).

## What users see

With `app001` alone, the apps are down while `app001` reboots, 32 to 55
seconds on a cloud server. A dedicated server takes a few minutes because
its firmware checks run first; past the 3-minute pause, the public site
checks raise their SOS, which waits for the triage agent and resolves
without waking anyone once the site answers.

## Background

`reboot_servers_after_updates` and `reboot_util01_after_updates` leave a
server unchanged when `/var/run/reboot-required` is absent.
