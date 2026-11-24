# Change the triage agent's run limit

**When to use this page:** MMHotline warned "Agent run limit reached.
Alerts continue.", or the team wants a higher or lower limit, or no limit.

**What this page does:** the cause of the many runs is found first, then
`triage_agent.most_runs_in_24_hours` in `mmhotline_settings.yml` changes,
and MMHotline on `util01` applies it.

**Who acts:** the coding agent reads the numbers, proposes the change,
edits, pushes and runs it from the systems desk. The person decides the
new limit, and runs `ssh desk01-review` in the person's own terminal
(step 5).

Read [the systems repository rules](../AGENTS.md#the-rules) first.

## Before you start

- **The limit stops only agent runs, never alerts.** Past the limit,
  MMHotline sends every alert straight to people, as it would without a
  triage agent, and tells the person on call once. Runs already started
  finish. When the runs of the last 24 hours fall to 80% of the limit, the
  agent looks at new alerts again, and MMHotline says so once.
- **The template's limit is 50 runs in a rolling 24 hours,** with the
  reason beside the setting in `mmhotline_settings.yml`. It counts the runs
  MMHotline starts by itself: triage sessions' runs, scheduled software
  reviews, and commit reviews. It does not count a run that a restart cut
  short, a person's hand-over, or a playbook review.
- **The value** is a whole number of 1 or more, or `no_limit`, which
  counts runs and never stops one. A team that wants no triage agent at
  all removes the agent, not the limit.

## Steps

1. **Read what used the runs.** MMHotline's warning names the three
   biggest uses. Read the numbers of the last 24 hours, with the time 24
   hours ago in UTC as `SINCE`, such as `2026-11-23T14:05:00Z`:

   ```sh
   # From the coding agent's checkout on the systems desk:
   ssh -F ssh/config root@10.20.0.1 "mmhotline triage-agent usage --since SINCE"
   ssh -F ssh/config root@10.20.0.1 "mmhotline alerts list --received-since SINCE"
   ```

   **Check:** you can say which alert or review used most of the runs, and
   whether the runs were needed.
2. **Fix a runaway before you pay for it.** A check that fails over and
   over, with a new alert each time, is a fault to fix, not a reason for a
   higher limit: fix the check or its cause, as
   [the operating procedure table](../AGENTS.md#when-this-happens-follow-this-operating-procedure)
   or a one-time playbook does. Tell the person what you found and the
   fix. Change the limit only when the runs were real work, such as a long
   incident, a large fleet, or the scheduled review at a short interval.
   **Check:** the person has the cause and agreed on a new limit, or on
   keeping the limit.
3. **Change the setting.** Set `triage_agent.most_runs_in_24_hours` in
   `mmhotline_settings.yml` to the new number, or `no_limit`, and write the
   team's reason in the comment beside it. Commit and push, as
   [Making a change](../AGENTS.md#making-a-change) says.
   **Check:** `mmx validate` passes, and the push succeeded.
4. **Apply it on `util01`:**

   ```sh
   ./server_management_scripts/run_mmx_on_util01 run every_server --limit util_server
   ```

   A higher limit, or `no_limit`, ends a limit that holds at once, and
   MMHotline sends its "can run again" message.
   **Check:** the run passes, and
   `ssh -F ssh/config root@10.20.0.1 "mmhotline triage-agent usage --since SINCE"`
   prints the new run limit.
5. **The person reviews the systems desk's settings.** Every change to
   `mmhotline_settings.yml` reaches the lock-out button only after the next
   desk review. Tell the person to run, in the person's own terminal:

   ```sh
   ssh desk01-review
   ```

   **Check:** the review shows the `mmhotline_settings.yml` change, and the
   person typed `yes`.

## If something is different

- **The warning came from the scheduled software review:** a review at a
  short interval uses runs every time. Lengthen
  `triage_agent.software_review_interval_hours` instead
  ([Turn on the scheduled software review](turn_on_the_scheduled_software_review.md)).
- **Many runs for one finding across many servers:** MMWatchdog's fleet
  hub sends one alert per finding, so this points to a finding whose
  exact finding keeps changing. Read the alerts' first lines, and report
  the check to the person as the fault to fix.
