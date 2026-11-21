# Test the alarm for a silent MMHotline

**When to use this page:** the person wants to see the MMHotline-down alarm
wake the person on call when MMHotline goes silent, such as during
[Check my system's protections](assess_a_running_system_and_recommend_changes.md#check-my-systems-protections).
This test is optional. The setup proves the MMHotline-down alarm with
`mmhotline down-alarm send-test`.

**What this page does:** the MMHotline-down alarm test stops MMHotline so
the MMHotline-down alarm detects missing check-ins and wakes the person on
call. Then MMHotline starts again. The MMHotline-down alarm test changes
nothing else on `util01`.

**Who acts:** the coding agent runs every command from a systems desk. The
person on call agrees on the time, because the person on call's phone will
ring, and acknowledges the alert in Pushover.

[The MMHotline-down alarm and the status page](#the-mmhotline-down-alarm-and-the-status-page),
below, explains what the alarm is and how it works.

## Before you start

- **Choose a quiet time with no open incident and no team mute.** Agree on
  the time with the person on call, whose phone will ring.
  Reason: while stopped, MMHotline cannot contact anyone. MMWatchdog's
  fleet hub on `util01` keeps each alert and retries until MMHotline
  accepts it. The dashboard and triage agent are also off.
- **Run no configuration playbook during the test.** Reason: a
  configuration run could start MMHotline again and end the test early.
- **Use MMX from a systems desk to stop and start MMHotline.** Reason:
  stopping and starting MMHotline through MMX records the test in
  `util01`'s run history.

## Steps

1. **See who would be woken.** On `util01`, run
   `sudo mmhotline down-alarm show`.
   **Check:** the output names who would be woken, and after how many
   minutes.
2. **Stop MMHotline:**
   `./server_management_scripts/run_mmx_on_util01 run-command --nodes util01 -- systemctl stop mmhotline`.
   **Check:** the run passes. Note the time of the stop for step 4.
3. **Wait for the phone.** Within the minutes of
   `wake_the_person_on_call_after_minutes_without_a_check_in`
   (5 by default), the person on call's phone sounds an emergency
   Pushover notification, "MMHotline is not checking in", which repeats
   until they acknowledge it in Pushover.
   **Check:** the phone sounds. When it stays silent, see
   [If something is different](#if-something-is-different).
4. **As soon as the phone sounds, restart MMHotline:**
   `./server_management_scripts/run_mmx_on_util01 run-command --nodes util01 -- systemctl start mmhotline`.
   Restart MMHotline before the minutes of
   `wake_the_backup_after_minutes_without_a_check_in` (10 by default) have
   passed since the stop, so the backup is not woken too.
   MMHotline's first check-in stops the MMHotline-down alarm's sends.
   **Check:** the run passes. Step 5 checks the result.
5. **Verify:** on `util01`, run `sudo mmhotline down-alarm show --json`.
   **Check:** the command's JSON output lists the send in
   `mmhotline_down_alarm.recent_sends`, with `send_outcome` `delivered`
   and `http_status_code` 200. The people woken receive the info alert
   "MMHotline runs again: it was down, and the MMHotline-down alarm woke you".
6. **Record the result** in `last_result` of `optional_protection_checks`, as
   [Check my system's protections](assess_a_running_system_and_recommend_changes.md#check-my-systems-protections) says.
   **Check:** none; the record is the result of steps 1 to 5.

## If something is different

- **The phone stays silent for 2 minutes longer than the first setting's
  minutes (7 minutes by default):** start MMHotline immediately, as in
  step 4. Read the cause with `sudo mmhotline down-alarm show`.
  The MMHotline-down alarm holds an alert only for a person whose Pushover
  contact method receives SOS alerts.
  Reason for the 2 minutes: they are a fixed margin of this test.
  MMHotline checks in once a minute, and the alert still has to reach the
  phone.
- **A team mute is on:** the MMHotline-down alarm's alert comes only
  `mmhotline_down_alarm.wake_the_person_on_call_after_minutes_without_a_check_in`
  after the mute ends.

## The MMHotline-down alarm and the status page

The MMHotline-down alarm and status page run in the team's own Cloudflare account.
The MMHotline-down alarm and status page keep working while `util01`, or the whole
location, is down.

The **MMHotline-down alarm** is a small program in the team's Cloudflare account, a
Cloudflare Worker.
Every minute, MMHotline checks in with the MMHotline-down alarm and gives the
MMHotline-down alarm a prepared SOS alert for the person on call.
The prepared SOS alert can wake the person on call at night.
When check-ins stop, the MMHotline-down alarm sends the alert to the person on call after the minutes in
`mmhotline_down_alarm.wake_the_person_on_call_after_minutes_without_a_check_in` in `mmhotline_settings.yml` (5 by default).
The MMHotline-down alarm then alerts the backup after the minutes in
`mmhotline_down_alarm.wake_the_backup_after_minutes_without_a_check_in` (10 by default):
the named backup, or, under `backup_option: everyone_available` (the template's default),
everyone else who is available.

The **status page**, such as `https://status.example.com/`, consists of three files in an R2 bucket:
`index.html` is the public page, `status.json` holds the page's settings and notices,
and `feed.xml` is the Atom feed that customers can subscribe to.
MMHotline rewrites the three status page files at each post, edit, deletion or resolution.
The page shows only what a person posts.

The stack's initial setup configured the MMHotline-down alarm and status page.
The MMHotline-down alarm's settings are the `mmhotline_down_alarm` part of `mmhotline_settings.yml`.
The status page's settings are the `status_page` part of
`mmhotline_settings.yml`.
The MMHotline-down alarm's and status page's keys are in the vault.

A rebuilt `util01` therefore gets the MMHotline-down alarm and status page back from
this systems repository.
On `util01`, inspect the MMHotline-down alarm with `sudo mmhotline down-alarm show`.
On `util01`, inspect the status page with `sudo mmhotline status-page show`.

A **team mute** temporarily stops the team's Pushover notifications and calls.
An administrator starts a team mute on MMHotline's
"On call" page.
A team mute also holds back the MMHotline-down alarm: the alarm's delay starts when
the mute ends.
The MMHotline-down alarm therefore alerts `mmhotline_down_alarm.wake_the_person_on_call_after_minutes_without_a_check_in` after the mute ends.
An administrator ends a mute early on MMHotline's
"On call" page.
Under "Mute the team", the administrator selects "Unmute the team".
