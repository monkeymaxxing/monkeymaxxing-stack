# Review the system

**When:** when a person asks, such as "Review my system", or at the
team's optional monthly check-in (the README's "Running the system"). No
review is required: every check that fails already sends an alert, the
automatic weekly maintenance installs updates and reboots by itself, and
`util01` refuses a push that adds a secret.

**What this page does:** one short report of what needs a person's
judgment since the last review: the alerts, the restarts that wait for a
person, the restore drill's result, and the checklist items and growth
triggers that are due.

**Who acts:** the coding agent gathers the parts below without the
person. Then the coding agent shows the person one short report, with a
proposal for each thing that needs a change. The person decides each
proposal.

## Before you start

- **Run each command from the coding agent's checkout on the systems desk.**
  `10.20.0.1` is `util01`.
- **Write the start of the review as `SINCE`,** in UTC, such as
  `2026-10-25T09:00:00Z`: the date of the last review in `git log
  --grep '^Review the system'`, or 30 days ago when there was none.

## What the coding agent gathers

1. **The alerts since `SINCE`.** List every alert and every SOS incident,
   and the triage agent's report on each:

   ```sh
   ssh -F ssh/config root@10.20.0.1 "mmhotline alerts list --received-since SINCE"
   ssh -F ssh/config root@10.20.0.1 "mmhotline incidents list --opened-since SINCE"
   git log --since=SINCE --stat -- triage_agent_notes/
   ```

   `alerts list` shows at most 100 alerts. When the list says that older
   alerts were left out, repeat the command with
   `--older-than-alert-id` and the oldest listed alert's ID.

   Then the triage agent's runs, what they cost, whether its run limit was
   reached, and what happened to the warnings held for it:

   ```sh
   ssh -F ssh/config root@10.20.0.1 "mmhotline triage-agent usage --since SINCE"
   ```

   Claude Code reports the runs' cost in US dollars; Codex reports only
   tokens. Report the runs and cost in one line. When the run limit was
   reached, or the runs nearly reached it, follow
   [Change the triage agent's run limit](change_the_triage_agent_run_limit.md)
   from its step 1.
   **Check:** for each alert, say whether the cause is known and fixed.
2. **The restarts that wait for a person, and the open findings.** The
   automatic weekly maintenance restarts every server whose restart costs
   the users nothing. A production pool's only server, such as `app001`
   alone or `db01` alone, waits for a person:

   ```sh
   ssh -F ssh/config root@10.20.1.1 "mmwatchdog check-now security_updates"
   ssh -F ssh/config root@10.20.2.1 "mmwatchdog check-now services_restarted_after_library_updates"
   ```

   - Run the first command on each production pool's only server, with its
     WireGuard address, and the second on `db01` alone. A plain
     `mmwatchdog check-now` shows the results and closes no warning.
   - Read the last weekly maintenance's result on `util01`:
     `ssh -F ssh/config root@10.20.0.1 "journalctl -u weekly_maintenance -u reboot_util01_after_the_weekly_maintenance --since SINCE --no-pager"`.
     A run that ended early, or a `util01` reboot that waited, says why.
   - Read `triage_agent_notes/open_software_findings.md` too. The section
     "Findings a person must act on" names each finding's program or
     package, flaw, fix, and the playbook or procedure that installs the
     fix: tell the person each open item. "Flaws with no fix yet" needs
     nobody until a fix appears. "No open findings." means no finding is
     open.
   - **The findings set aside after investigation,** which no server
     alerts about, only when the person asks:
     `ssh -F ssh/config root@10.20.0.1 "mmwatchdog fleet set-aside-findings --json"`.
     An entry whose `matches_no_node_now` is `true` and whose
     `nodes_that_cannot_check_now` is `0` quiets nothing and costs
     nothing. The person may remove it from
     `triage_agent_notes/set_aside_findings.yml` (keep
     `set_aside_findings: []` when none is left), then run
     `./server_management_scripts/run_mmx_on_util01 run apply_set_aside_findings`.

   **Check:** each server that waits for a person is on the list for the
   report, with what waits and since when.
3. **The restore drill's result.** Read the latest drill's result on
   `util01`, as
   [Read the result](run_the_weekly_database_restore_drill.md#read-the-result)
   says:

   ```sh
   ssh -F ssh/config root@10.20.0.1 "cat /var/lib/restore_drill/latest_result.json"
   ```

   **Check:** with `"passed": true`, record the measured result in
   `backups_restore_every_week` in `monkeymaxxing_stack_checklist.yml` and
   in the README's recovery results. Any other answer is in
   [If something is different](#if-something-is-different).
4. **The checklist items and the growth triggers.** In
   `monkeymaxxing_stack_checklist.yml`:

   - In `items`, find each `open` item whose `waits_for` has happened, such
     as `deploy_and_rollback` after the first rollback. An item to which
     the team added its own `verify_again_every` counts as open once
     `verified_at` is older: run its `verification` again.
   - In `growth_and_improvement_items`, check only whether a trigger
     arrived. A measured trigger arrives as an MMWatchdog warning among
     the alerts. For an event that only the person knows, such as the
     first paying customers, ask the person in one line.
   - One measured trigger has no warning: an app pool that mixes server
     sizes. A pool of equal servers skips this check. With mixed sizes,
     check by hand that the other servers can carry the load when the
     biggest one fails: the pool's peak CPU use over the last week must
     stay below 70% of the combined CPUs of all app servers except the
     biggest. `nproc` on each app server gives its CPUs, and on `util01`
     `mmwatchdog fleet readings app001 app_server_capacity --last 7d`, and
     the same for each other app server, gives its CPU use over the week.
     Past that limit, the trigger of `second_app_server` or
     `bigger_servers` has arrived. The reason is under
     [Why the review covers these parts](#why-the-review-covers-these-parts).
   - The app pool's changes: `git log --since=SINCE --grep '^Server-pool:
     app_servers'` lists each app server added, removed or replaced, with
     its commit. On `util01`, `sudo mmwatchdog status --json` gives the
     latest message of the checks `app_servers_to_add_for_the_load` and
     `app_servers_to_remove_for_the_load` (only with
     `routine_fixes_and_server_work`): a check that still fails is a
     change someone stopped with Stop, which waits. Its message says
     whether the load still calls for it. With the other two answers, and
     an app pool above its `smallest_number_of_servers`, propose
     `remove_server` without `server_name` when the week's readings were
     low ([Remove a server](remove_a_server.md)): it removes a server only
     by the same rule, and otherwise says "nothing to remove" and changes
     nothing.

   **Check:** each item that is due is verified or on the list for the
   report, and each arrived trigger is on the list for the report.

## Move the finished one-time playbooks

5. **Without the person, move each finished one-time playbook out of the
   way.** `mmx check-one-time-playbooks` lists the one-time playbooks
   outside `one_time_playbooks/completed/`. For each one-time playbook
   that ran on every server it selects, run
   `mmx complete-one-time-playbook NAME`, which moves the file and commits
   nothing. Then commit and push the moves.
   **Check:** `mmx check-one-time-playbooks` lists no finished one-time
   playbook.

## The report and the proposals

6. **Show the person the parts in order,** each in a few lines: what
   happened, what needs a decision, and what does not. Prepare each
   proposal as a commit or a playbook run, checked with `mmx validate` and
   ready to push:

   - **The restart of each production pool's only server that waits,**
     in the maintenance window (`maintenance_window` in
     `mmx_project_settings.yml`), with the short outage it costs:
     [Update and restart the database servers](update_and_restart_the_database_servers.md)
     for `db01` alone,
     [Reboot servers after updates](reboot_servers_after_updates.md) for
     the others.
   - **The operating procedure for each trigger that arrived,** with its
     measured numbers. A server inside the growth limits (`growth_limits` in
     `mmx_project_settings.yml`) is no proposal: follow its operating
     procedure at once, without waiting for the person, and report it in the
     review. For example: "The app pool's peak CPU passed 47% on 3 of the
     last 7 days, so I added `app004`", with its monthly cost from the
     provider's current price, as step 1 of
     [Add a server](add_a_server.md) says. Propose,
     and wait for the person, only what is outside the limits, such as a
     fifth app server when the limit is 4, `staging01`, or a step that the
     operating procedure says the person decides. Propose only what the
     [operating procedure table](../AGENTS.md#when-this-happens-follow-this-operating-procedure)
     lists. A step beyond the Stack, such as a second location, needs a
     business requirement and the team's decision, never a number alone.
   - **An investigation of each alert or failure with no known cause.**

   **Check:** each proposal passes `mmx validate`.
7. **After the person approves a proposal,** push, preview the pushed commit
   with `sudo -n -u servers-mmx run-mmx-on-the-servers dryrun`, and run the
   proposal, as "Making a change" in [AGENTS.md](../AGENTS.md#making-a-change)
   says.
   **Check:** the run passes, and the proposal's own verification passes.
8. **Record the review** with an empty commit whose message starts with
   `Review the system`, such as `git commit --allow-empty -m "Review the
   system: nothing needs a person"`, and publish it, so the next review
   knows its `SINCE`.
   **Check:** the commit is on `main`.

## If something is different

The restore drill's result in part 3 is not `"passed": true`:

- **`"passed": false` and `gave_way_to` but no `attempt_dir`.** The
  drill ended for an MMHotline run that waited, such as the triage
  agent's replacement of a failed server, and systemd runs it again 2
  hours later. Record nothing, check that it waits to run again with
  `ssh -F ssh/config root@10.20.0.1 "systemctl status weekly_database_restore_drill.service --no-pager"`
  (`activating (auto-restart)`), and report "the drill gave way to" the
  line in `gave_way_to`, with the time it runs again. When no drill has
  passed in 8 days, MMWatchdog's `restore_drill` warning is open too:
  report that as a failure to investigate (step 6).
- **`"passed": false` otherwise.** The drill failed, and MMWatchdog has warned:
  record nothing, read the cause with
  `ssh -F ssh/config root@10.20.0.1 "journalctl -u weekly_database_restore_drill -n 100 --no-pager"`,
  and report it as a failure to investigate (step 6).
- **The command answers `No such file or directory`.** No drill has
  finished yet. Each `every_server` run starts a drill on `util01` until
  one passes; read whether one runs now with
  `ssh -F ssh/config root@10.20.0.1 "systemctl status weekly_database_restore_drill.service --no-pager"`,
  and report "no drill result yet" with what the status shows.

## Why the review covers these parts

Every other check already sends an alert when it fails, so the alerts
cover it. The review is on demand because a routine that asks a person to
look every week, when nothing needs them, teaches the team to skip it.

The mixed app pool needs a check by hand because MMWatchdog's CPU warning
assumes equal app servers. 70% is the fixed limit of MMWatchdog's
app-server CPU check in `mmwatchdog_checks/app_servers.yml`, which keeps
30% of CPU unused as headroom.
