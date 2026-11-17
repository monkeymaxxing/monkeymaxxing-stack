# Change MMHotline settings

**When to use this page:** a change to MMHotline's alerts, people, waiting
times, or other features.

**What this page does:** a change to `mmhotline_settings.yml` reaches
MMHotline on `util01`, and every desk's lock-out button gets the new
settings.

**Who acts:** the coding agent edits, previews, pushes, and runs the
change. The person sets any new secret in the vault, in the person's own
desk terminal. Each person runs the desk review in the person's own
terminal, and adds and changes the person's own contact methods.

## Before you start

- Read [the systems repository rules](../AGENTS.md#the-rules) first.
- **MMHotline's settings** control its alerts, people, and other features.
  Edit `mmhotline_settings.yml` at the systems repository's root.
  The comments in `mmhotline_settings.yml` explain each part.
  MMHotline's settings file reference, `docs/reference/settings-file.md`,
  lists every key. How to apply a change is in `docs/how-to/change-the-settings.md`.
  Both are in the
  [MMHotline source repository](https://github.com/monkeymaxxing/mmhotline),
  at the release tag for `vars.stack_software.mmhotline.version` in
  `mmx_project_settings.yml`.
- **Contact methods are not in this file.** Each person adds and changes
  their own on MMHotline's page, and MMHotline sends a test message at once.
  Warn the person before they save one: the test rings like an alarm. It is
  an emergency-priority Pushover message that repeats every 30 seconds, for
  up to 10 minutes, until the person acknowledges it on the phone. It is
  only a test; nothing is wrong.
- **A waiting time** before a person hears of a problem may live in
  another file: see [The waiting times](#the-waiting-times).

## Steps

1. **Edit the settings.** Change `mmhotline_settings.yml`, or the file that
   [The waiting times](#the-waiting-times) names for a waiting time.
   **Check:** `mmx validate` passes.
2. **Put each new secret in the vault, with the section that uses it.**
   A secret's value is stored under a key in the vault.
   In the MMX template, `{{ .secrets.KEY }}` inserts the value stored under
   `KEY`. Commit a new section in `mmhotline_settings.yml` together with the
   section's new secret keys in the vault.
   **Check:** none needed when the change adds no secret. Otherwise the
   person has pushed `secrets_vault.age` with the new keys.
3. **Preview the change.** Use the dryrun in step 5 of
   [Making a change](../AGENTS.md#making-a-change).
   MMX checks the new settings rendered from your local
   `mmhotline_settings.yml`, with secrets from the vault.
   The preview runs the pinned release's `mmhotline settings check` on
   `util01`. The check reads the new rendered settings, rather than the
   installed `/etc/mmhotline/mmhotline_settings.yml`.
   **Check:** the preview's `mmhotline/write_the_mmhotline_settings` task
   does not fail. A settings validation error makes that task fail.
   The dryrun output includes the check's message, naming each problem by
   the setting's key, such as
   `triage_agent.reasoning_effort: required`.
4. **Apply the change.** After the push, run `every_server` on `util01` to apply
   `/etc/mmhotline/mmhotline_settings.yml`, rendered from the repository template,
   with `mmhotline settings apply`, in the stage `apply_the_mmhotline_settings`.
   **Check:** the run passes. Read
   `./server_management_scripts/run_mmx_on_util01 results` from the desk.
   MMX records each settings part's apply output and refusal reason without
   secret values.
5. **Review and apply each desk's settings.** Tell each person to run
   `review-and-apply-the-systems-desk-settings` and read the
   MMHotline change it shows.
   **Check:** each person's desk review shows the MMHotline change and
   applies it.
   Reason: the lock-out button applies the MMHotline settings of the
   person's last desk review, so until then a lock-out would bring back the earlier
   people and on-call rotation. The lock-out button applies MMHotline's settings as root on `util01`,
   so it must not apply settings that an outside attacker could push to the Git host.

## If something is different

- **A part fails.** MMHotline tests each changed part.
  For example, MMHotline tests a new triage agent credential with one prompt.
  If a part fails, MMHotline keeps the failed part's earlier setting and
  `util01`'s run fails. Changes to parts that pass remain applied.
  Correct the cause and rerun `every_server` explicitly. A later attempt
  can apply a temporarily refused setting without another settings edit
  once the blocking condition ends. No automatic retry runs.
- **A new Pushover token is refused.** MMHotline refuses a new Pushover
  token while a Pushover emergency message is open: still repeating on
  someone's phone. MMHotline needs the old token to check and cancel the
  open emergency. Once the emergency is acknowledged, cancelled, or
  expired, MMHotline can accept the new token on a later attempt.
- **MMHotline restarts.** Changing `web_url`, `web_listen_address`,
  `alert_intake_listen_address`, or `cloudflare_access` restarts MMHotline
  for a few seconds.
  MMWatchdog's fleet hub on `util01` resends its alerts until MMHotline accepts them.
- **The dryrun hides the file's changes.**
  MMX hides changes to `/etc/mmhotline/mmhotline_settings.yml` because the
  rendered settings hold secrets.
  MMX shows the check's message with secret values replaced by `[redacted]`
  (`output_holds_no_secret` on the check).

## The waiting times

**The waiting times before a person hears of a problem** live in four
files. Each setting's reason is in the comment beside it; change a time
there, with a reason of your own.

| What waits | Setting | File | Default |
| --- | --- | --- | --- |
| An SOS waits for the triage agent before waking the person on call | `triage_agent.sos_waits_for_the_agent_minutes` | `mmhotline_settings.yml` | 3 minutes |
| A warning that starts a triage session is held while the triage agent tries first; the agent's request or report in that time takes the warning over, otherwise it sounds at the end of the wait, at once when the agent cannot run. 0 turns holding off; at most 15, MMHotline's limit | `triage_agent_server_work.warn_waits_for_the_triage_agent_minutes`, which `mmhotline_settings.yml` renders as `triage_agent.warn_waits_for_the_agent_minutes` | `mmx_project_settings.yml` | 3 minutes |
| While the triage agent replaces a failed server, an SOS waits from the replacement's start before waking the person on call; a failed run, an SOS report or a request for a person wakes at once. 0 turns the longer wait off; at most 60, because MMHotline stops an MMX run after an hour | `triage_agent_server_work.sos_waits_for_a_server_replacement_minutes`, which `mmhotline_settings.yml` renders as `triage_agent.sos_waits_for_a_server_replacement_minutes` | `mmx_project_settings.yml` | 7 minutes |
| An unclaimed SOS reaches the people of `backup_option` | `on_call_schedule.escalate_if_unclaimed_after_minutes` | `mmhotline_settings.yml` | 5 minutes |
| The fleet hub on `util01` stops checking in with MMHotline: a warn, then an SOS | `warn_after_no_check_in_for_minutes` and `sos_after_no_check_in_for_minutes` of `alert_sources` | `mmhotline_settings.yml` | 2, then 5 minutes |
| MMHotline stops checking in with the MMHotline-down alarm: the person on call, then the backup (the named backup, or everyone else available) | `mmhotline_down_alarm.wake_the_person_on_call_after_minutes_without_a_check_in` and `wake_the_backup_after_minutes_without_a_check_in` | `mmhotline_settings.yml` | 5, then 10 minutes |
| A public address stops answering | `alert_after_failing_for` of `public_sites` | `mmwatchdog_checks/util_server.yml` | 30 seconds |
| The servers cannot reach the fleet hub on `util01` | `alert_after_hub_unreachable_for` | `roles/util_server/files/mmwatchdog_node_settings.yml` | 2 minutes |

## How MMHotline applies settings in parts

MMHotline tests and accepts settings in separate groups, called parts,
such as `people`, `on_call_schedule`, and each sending service.
MMHotline's `docs/how-to/change-the-settings.md`, "Change the settings by hand",
shows the parts and what the apply command prints for each. The reference,
`docs/reference/settings-file.md`, lists the keys.

## Startup order

Each `every_server` run follows the order below,
including settings changes, initial installation, and rebuilding `util01`.
MMHotline starts before database and app setup so alerts do not wait for
database and app setup to finish.
The stage `mmhotline` installs and starts MMHotline just after
`util_server` and `read_the_mmwatchdog_fleet_hub_join_code`, before the
database and app stages.
`every_server` has already set `util01`'s WireGuard address.
`util_server` has created MMHotline's `mmhotline` user and group, and the
user's home, `/var/lib/mmhotline`, and attempted to clone the systems
repository.

MMHotline's alert listener needs no clone.
The restore drill waits until a desk pushed `main` to the main copy on
`util01`, root there accepts the `mmhotline` user's SSH key, and the
systems repository clone exists on `util01`.

Before installation, the `mmhotline` stage restores MMHotline's SQLite
database from Litestream's backup, only when `/var/lib/mmhotline/mmhotline.db`
does not exist. With no backup yet, as during initial installation,
MMHotline's install creates the database.
A settings-change run skips the restore when the database already exists.
The `mmhotline` stage also checks and writes
`/etc/mmhotline/mmhotline_settings.yml`, which installation requires.

The hub retries alerts while MMHotline starts, without waiting for
database and app setup.
`apply_the_mmhotline_settings` remains after the database and app stages
so an apply refusal cannot delay database and app setup.
`start_the_restore_drill_until_one_has_passed` stays last so a failure
starting the drill cannot delay the servers' work.
A refusal in `apply_the_mmhotline_settings` holds back only the drill's
first start. The earlier settings validation happens in the
`mmhotline` stage, before database and app setup.
