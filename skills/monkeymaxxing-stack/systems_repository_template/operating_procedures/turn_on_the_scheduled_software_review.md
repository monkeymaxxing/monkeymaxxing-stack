# Turn on the scheduled software review

**When to use this page:** the team wants the triage agent to review the
servers' software at an interval, or wants the review off again.

**What this page does:** the **scheduled software review** starts the
triage agent on `util01` at an interval the team chooses, with the team's
task in `scheduled_software_review_task.md`, such as checking every
server's packages and programs for known flaws.

**Who acts:** the coding agent does every step from the systems desk.
The person decides what the task leaves out (step 1) and the interval
(step 3). Each person runs `ssh desk01-review`
in the person's own terminal (step 3).

Read [the systems repository rules](../AGENTS.md#the-rules) first.

## Find your situation

| Situation | Follow |
| --- | --- |
| Turn the review on, or change its interval | [Steps](#steps) |
| Turn the review off | [Turn the review off again](#turn-the-review-off-again) |

## Before you start

- **The template turns the review off,**
  `triage_agent.software_review_interval_hours: off` in
  `mmhotline_settings.yml`. Reason: each review is one run of the coding
  agent, which the team pays for, so a team turns the review on knowingly,
  after it has seen what one review costs.
- **The triage agent must be set up.** Otherwise step 2 runs no review:
  see [If something is different](#if-something-is-different).
- **A push alone changes no server.** Each step that changes a setting
  ends with a run of `every_server` on `util01`, as
  [Making a change](../AGENTS.md#making-a-change) says.

## Steps

1. **The coding agent fits the task to the team's software.**
   - Read `scheduled_software_review_task.md`,
     `software_outside_the_distribution.yml`, and the inventory.
   - Rewrite the task for the software this team runs: for example, add
     the apps' container images or a program the team installed, and leave
     out a check the team does not need.
   - Keep the task short: MMHotline refuses a task file over 64 KiB, and
     every line costs tokens at every review.
   - Show the person the task in plain words and what it leaves out.
   - When the task needs a website that
     [the triage agent's allowed hosts](../triage_agent_rules.md#reading-the-system)
     do not include, add the host to `triage_agent.listed_hosts` in
     `mmhotline_settings.yml` in the same commit, such as
     `{host: example.org, port: 443}`.
   - Commit, synchronize, and push, as
     [Making a change](../AGENTS.md#making-a-change) says. With a changed
     `listed_hosts`, also run `every_server` on `util01`, as in step 3.

   Reason for pushing first: MMHotline reads the task file from its own copy
   of the systems repository at the commit the review starts from.
   **Check:** the person has seen the task, and the push succeeded.

2. **Run one review by hand and read its cost.** The command runs one
   review while the schedule is off. It is refused while another triage
   run is active; try again when that run ends.

   ```sh
   # From the coding agent's checkout on the systems desk:
   ssh -F ssh/config root@10.20.0.1 'mmhotline triage-agent run-software-review'
   ```

   A review takes a few minutes. Wait until
   `ssh -F ssh/config root@10.20.0.1 'mmhotline triage-agent show'`
   prints `Software review ended at:`. Then read the review:

   ```sh
   ssh -F ssh/config root@10.20.0.1 'mmhotline triage-agent show --json' | jq '.triage_agent.latest_software_review'
   ```

   **Check:** `state` must be `finished`, with an empty `failure_reason`.
   `report_counts_by_alert_severity` must add up to at most 1: a review
   sends one summary report, or no report when nothing is new or changed.
   The first review usually sends one report, because every finding is
   new. A `failed` or `stopped` review, or exit 4, is in
   [If something is different](#if-something-is-different).

   Then read the two numbers:
   - The time is `ended_at` minus `started_at`.
   - `cost_in_us_dollars` is the cost at API prices when the coding agent
     reports one, as Claude Code does. Codex reports only `input_tokens`,
     `cached_input_tokens`, and `output_tokens`: multiply each by the
     model's price.

   Read the report on MMHotline's dashboard with the person: the report
   shows what a person must do first, then what the review found. A warn
   report always names a playbook or procedure for the person to run.

   Tell the person the two numbers, and what a month costs at each
   interval the person considers: the cost of one review, times 24 divided
   by the interval in hours, times 30. As examples only, MMHotline measured
   on 2026-11-11, with Claude Code and Opus on two servers:
   - a review on a quiet day took 2 minutes 25 seconds and cost $1.12,
     about $34 a month every 24 hours and about $134 a month every 6 hours;
   - a first review, when every advisory was new, took 5 minutes 25
     seconds and cost $1.97.

   The team's own numbers replace these examples. With a subscription
   credential, the review uses the plan's limits instead of money.

3. **The person decides the interval; the coding agent sets it.** The
   person chooses a number of hours, from 1 to 8760, such as 24, or keeps
   the review off. Set the person's number in `mmhotline_settings.yml`:

   ```yaml
   triage_agent:
     software_review_interval_hours: 24
   ```

   Commit, synchronize, push, preview, and run `every_server` on `util01`,
   as [Change MMHotline settings](change_mmhotline_settings.md) says:

   ```sh
   sudo -n -u servers-mmx run-mmx-on-the-servers dryrun every_server --connection ssh_only
   ./server_management_scripts/run_mmx_on_util01 run every_server
   ```

   The run's stage `apply_the_mmhotline_settings` applies the interval.
   Tell each person to run `ssh desk01-review` (with the person's own desk name),
   as that procedure says.
   **Check:** the run passes; step 4 checks the interval.

4. **Verify.**
   **Check:** `ssh -F ssh/config root@10.20.0.1 'mmhotline triage-agent show'`
   prints `Scheduled software review: every 24 hours`, with the person's
   number.

   The Software review section of the Triage agent page on MMHotline's
   dashboard shows the interval, when the next review is due, and the
   latest review: give the person the link and the time of the next
   review. The next scheduled review starts one interval after the review
   of step 2. Record the interval and the measured cost in `last_result`
   of the checklist item `software_review`, with `state: done` and
   `verified_at`.

## Turn the review off again

1. Set `software_review_interval_hours: off` in `mmhotline_settings.yml`, and
   commit, push, preview, and run `every_server` on `util01` as in step 3.
   **Check:** `mmhotline triage-agent show` then prints
   `Scheduled software review: off`.
2. Keep `scheduled_software_review_task.md`: with `off`, nothing reads the
   file, and turning the review on again needs only the setting.
   **Check:** none; nothing changes.
3. Set the checklist item `software_review` back to `waits_for_its_trigger`,
   with `trigger` saying the team turned the review off.
   **Check:** `mmx validate` passes before the commit.

## If something is different

- **Step 2's command exits with 4 and prints
  `mmhotline: the triage agent is not set up`.** No review ran, and
  `latest_software_review` stays `null`: `mmhotline triage-agent show`
  prints `Triage agent: not set up`. Set up the triage agent first:
  - its credential, `mmhotline_triage_agent_credential`, from step 7 of
    [chapter 4 (set up your accounts and lock your systems desk)](../initial_setup/04_set_up_your_accounts_and_lock_your_desk.md);
  - its `triage_agent` section in `mmhotline_settings.yml`, from part 1 of
    [chapter 8 (check that alerts reach your phone and backups restore)](../initial_setup/08_check_that_alerts_reach_your_phone_and_backups_restore.md).

  Then run `every_server` on `util01` and step 2 again.
- **The review is `failed` or `stopped`.** The review names its cause in
  `failure_reason`, such as a missing task file or a stop for a triage
  session. Fix the cause and run the review again.

## What the review adds

While the review is off, the system still watches its software without a
coding agent:

- MMWatchdog's checks warn about the Debian packages' security updates and
  known exploited flaws.
- The check group `pinned_program_releases` on `util01` warns when a
  program pinned in `stack_software` has a newer release. The triage agent
  then starts for that warning only.
- A program from a vendor's apt repository, such as Caddy, updates itself.

The review adds what a plain check cannot do, such as reading the vendors'
advisories for the installed versions, or checking software the team added.

MMHotline's guide `docs/how-to/turn-on-the-scheduled-software-review.md`
describes the review. The guide is in the
[MMHotline source repository](https://github.com/monkeymaxxing/mmhotline),
at the release tag for `vars.stack_software.mmhotline.version` in
`mmx_project_settings.yml`.
