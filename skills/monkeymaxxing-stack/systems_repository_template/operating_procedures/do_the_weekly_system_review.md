# Do the weekly system review

**When:** once a week, when a person asks, such as "Do the weekly system
review". The README's next actions name who does the review, and when.

**What this page does:** the weekly review covers the four things that
need a person's judgment each week: the week's alerts, the waiting
updates, the restore drill's result, and the checklist items that are due.

**Who acts:** the coding agent gathers the four parts below without the
person. Then the coding agent shows the person one short report, with a
proposal for each thing that needs a change. The person decides each
proposal.

## Before you start

- **Run each command from the coding agent's checkout on the systems desk.**
  `10.20.0.1` is `util01`.
- **Write the time seven days ago as `SINCE`,** in UTC, such as
  `2026-11-05T09:00:00Z`.

## What the coding agent gathers

1. **The week's alerts.** List every alert and every SOS incident of the
   week, and the triage agent's report on each:

   ```sh
   ssh -F ssh/config root@10.20.0.1 "mmhotline alerts list --received-since SINCE"
   ssh -F ssh/config root@10.20.0.1 "mmhotline incidents list --opened-since SINCE"
   git log --since=7.days --stat -- triage_agent_notes/
   ```

   `alerts list` shows at most 100 alerts. When the list says that older
   alerts were left out, repeat the command with
   `--older-than-alert-id` and the oldest listed alert's ID.

   Then the triage agent's week: its runs, what they cost, whether its run
   limit was reached, and what happened to the warnings held for it:

   ```sh
   ssh -F ssh/config root@10.20.0.1 "mmhotline triage-agent usage --since SINCE"
   ```

   Claude Code reports the runs' cost in US dollars; Codex reports only
   tokens. Report the week's runs and cost in one line. When the run limit
   was reached, or the runs nearly reached it, follow
   [Change the triage agent's run limit](change_the_triage_agent_run_limit.md)
   from its step 1.
   **Check:** for each alert, say whether the cause is known and fixed.
   A warning that is still open can be a waiting update (part 2) or a
   trigger (part 4).
2. **The waiting updates.** Each server's waiting security updates and
   reboots:

   ```sh
   ssh -F ssh/config root@10.20.1.1 "mmwatchdog check-now security_updates"
   ```

   - Run the first command on every server in `inventories/servers.yml`,
     with each server's WireGuard address, except the systems desks: the
     coding agent cannot log in to a desk as root, its own included. A
     desk's MMWatchdog checks its own waiting updates too, so a desk's
     update waiting too long is a `security_updates` warning from that desk
     in part 1; tell that desk's person.
   - A plain `mmwatchdog check-now` shows the results and closes no warning.
   - A reboot that waits on a server of the app, jobs, or load-balancer
     pools while the team chose `routine_fixes_and_server_work` is a reboot
     a person stopped, with Stop on MMHotline's warning, or one that waits
     for the weekly window: say which, from MMHotline's incident of
     `no_reboot_waits_that_may_run_now`.
   - Read `triage_agent_notes/open_software_findings.md` too. The section
     "Findings a person must act on" names each finding's program or
     package, flaw, fix, and the playbook or procedure that installs the
     fix: tell the person each open item. "Flaws with no fix yet" needs
     nobody until a fix appears. "No open findings." means no finding is
     open.
   - **The findings set aside after investigation,** which no server
     alerts about:

     ```sh
     ssh -F ssh/config root@10.20.0.1 "mmwatchdog fleet set-aside-findings --json"
     ```

     For each entry, tell the person the finding, its reason, and how many
     servers it covers now. Remove an entry only when its
     `matches_no_node_now` is `true` and its `nodes_that_cannot_check_now`
     is `0`: then no server has that exact finding, and none is unable to
     say. Remove such entries from `triage_agent_notes/set_aside_findings.yml`
     without the person, keep `set_aside_findings: []` when none is left,
     publish the commit, and run
     `./server_management_scripts/run_mmx_on_util01 run apply_set_aside_findings`.
     Reason: an entry no server matches only makes the list longer, and a
     later server with the same exact finding is unlikely; it would alert
     and be investigated again. Keep every other entry: the entries have
     no end date, because a date would alert again on a finding that has
     not changed.

   **Check:** every server except the desks has a result, and each
   set-aside entry is kept or removed by the rule above.
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
4. **The checklist items that are due.** In
   `monkeymaxxing_stack_checklist.yml`:

   - In `items`, set each `done` item whose `verified_at` is older than
     its `verify_again_every` back to `open`, and run its `verification`
     again. For example, `secrets_in_the_vault_scoped_by_role` is due every
     week. Scan the week's commits for a secret in clear text, in the
     repository:

     ```sh
     gitleaks detect --redact --verbose --log-opts="--since=7.days"
     ```

     The desk's gitleaks is Debian's, whose scan of Git history is
     `detect`. `--redact` replaces each secret it finds with `REDACTED`,
     so the output names the file, line and commit but never the secret.
     Exit 0 means no finding; exit 1 lists each finding. Check
     that no app's `env` in `mmx_project_settings.yml` holds a secret
     value; secrets belong in `secrets_from_vault`, each with where its
     value comes from. A secret in Git
     history has already reached everyone who can read the repository,
     including the triage agent's model provider. Replace the secret
     ([Rotate a secret](rotate_a_secret.md)) and tell the person.
   - In `items`, find each `open` item whose `waits_for` has happened, such
     as `deploy_and_rollback` after the first rollback.
   - In `growth_and_improvement_items`, check only whether a trigger
     arrived. A measured trigger arrives as an MMWatchdog warning in the
     week's alerts. For an event that only the person knows, such as the
     first paying customers, ask the person in one line.
   - One measured trigger has no warning: an app pool that mixes server
     sizes. A pool of equal servers skips this check. With mixed sizes,
     check by hand that the other servers can carry the load when the
     biggest one fails: the pool's peak CPU use over the week must stay
     below 70% of the combined CPUs of all app servers except the biggest.
     `nproc` on each app server gives its CPUs, and on `util01`
     `mmwatchdog fleet readings app001 app_server_capacity --last 7d`, and
     the same for each other app server, gives its CPU use over the week. Past
     that limit, the trigger of `second_app_server` or `bigger_servers`
     has arrived. The reason is under
     [Why the review covers these four parts](#why-the-review-covers-these-four-parts).
   - The app pool's changes of the week: `git log --since='7 days ago'
     --grep '^Server-pool: app_servers'` lists each app server added,
     removed or replaced, with its commit. On `util01`, `sudo mmwatchdog
     status --json` gives the latest message of the checks
     `app_servers_to_add_for_the_load` and
     `app_servers_to_remove_for_the_load` (only with
     `routine_fixes_and_server_work`): a check that still fails is a
     change someone stopped with Stop, which waits. Its message says
     whether the load still calls for it. With the other two answers, and
     an app pool above its `smallest_number_of_servers`, propose
     `remove_server` without `server_name` when the week's readings were
     low ([Remove a server](remove_a_server.md)): it removes a server only
     by the same rule, and otherwise says "nothing to remove" and changes
     nothing.

   - The registry token's end date. Read
     `container_registry_read_only_token_expires_at` in the setup's results
     file. It is the date the servers can no longer download the app, so
     deploys and new servers stop:

     ```sh
     ssh desk01-agent cat /var/lib/monkeymaxxing-stack/setup_results.json
     ```

     `for_the_coding_agent` holds the field only when the person chose a
     token that ends. The file is root's, so after a replacement the new
     date is a line in the README's "Next actions", such as "The registry
     token ends 2027-05-01"; the later of the two dates counts. With no
     date, or a date more than 30 days away, there is nothing to do. With
     a date within 30 days, put the date on the list for the report, with
     the steps of
     [The container registry token](rotate_a_secret.md#the-container-registry-token):
     the person makes the new token with the link on the setup's Git host
     token screen (GitHub may first ask for an authentication code), and
     sets it in the vault as that section says. Ask for the new token's end date, and write it in
     "Next actions".

   **Check:** each due item is `open` again or verified, each arrived
   trigger is on the list for the report, and a registry token that ends
   within 30 days is on it with its date.

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

6. **Show the person the four parts in order,** each in a few lines: what
   happened, what needs a decision, and what does not. Prepare each proposal
   as a commit or a playbook run, checked with `mmx validate` and ready to
   push:

   - **The weekly maintenance,** if the team's window (`maintenance_window` in
     `mmx_project_settings.yml`) has not run since the last review: first
     `update_database_servers`, then `reboot_servers_after_updates`, and from
     a systems desk `reboot_util01_after_updates`
     ([Reboot servers after updates](reboot_servers_after_updates.md)).
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
   - **The verification of each item that is open again.**
   - **An investigation of each alert or failure with no known cause.**

   **Check:** each proposal passes `mmx validate`.
7. **After the person approves a proposal,** push, preview the pushed commit
   with `sudo -n -u servers-mmx run-mmx-on-the-servers dryrun`, and run the
   proposal, as "Making a change" in [AGENTS.md](../AGENTS.md#making-a-change)
   says.
   **Check:** the run passes, and the proposal's own verification passes.
8. **Update `dashboard_and_weekly_review` in the checklist** with the date
   of the review.
   **Check:** the commit with the date is pushed.

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

## Why the review covers these four parts

Every other check already sends an alert when it fails, so the week's
alerts cover it.

The mixed app pool needs a check by hand because MMWatchdog's CPU warning
assumes equal app servers. 70% is the fixed limit of MMWatchdog's
app-server CPU check in `mmwatchdog_checks/app_servers.yml`, which keeps
30% of CPU unused as headroom.
