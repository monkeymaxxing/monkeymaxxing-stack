# Chapter 8: Check that alerts reach your phone and backups restore

**When:** in four parts of the setup.

- **The first part of the setup** runs only part 1 (read the backup results), right
  after chapter 7 (install everything on the production servers). Then
  chapter 9 puts the app live.
- **The alerts part of the setup,** when the person says "set up alerts", runs
  part 2 (phone alerts). It needs the domain to show "Active" at
  Cloudflare.
- **The triage agent's part of the setup,** when the person asks for it, runs
  part 3 (the triage agent).
- **The status page's part of the setup,** when the person asks for it, runs part 4
  (the status page). It needs the domain to show "Active" too.

Until the alerts part of the setup is done, say plainly that the site has no phone
alerts, whenever you report on the system. Keep the parts that are
still open in the README's next actions, so the person sees what is left.

**What this chapter does:** the first backup's and the first restore
drill's results are read. MMHotline gets Pushover and the MMHotline-down
alarm, and one test SOS proves that an alert wakes the person on call.
Later the triage agent gets its key, and the status page, where the team
tells customers about a problem, gets its settings and a test notice.

**Who acts:** you, the coding agent, write the settings, run MMX through
the desk, and run every test. The person makes the outside accounts, types
each secret at a hidden prompt on the desk, and presses Acknowledge on the
phone.

**Tell the person when the chapter starts,** in the first part of the setup:

> I am reading the first backup and the first restore drill.

## Before you start

- **The messages to the person.** Each step says what to tell or ask the
  person, in quote blocks: "Tell the person first" before the step, "Ask
  the person" when the person must act, and "Tell the person after" with
  the result and its link. Say each message when its step comes, in your
  own words, with the team's own names and links. Show each screen in a
  code block, as it is written.
- **Commands on the desk.** Every command block below runs from the
  laptop, through your login on the desk, `desk01-agent`. When the person
  types a desk command right after you used a code, add the line
  **WAIT FOR A NEW CODE.** before the command, as
  [Your login on the desk](../AGENTS.md#your-login-on-the-desk) says.
- **MMX runs.** Publish each settings change with the
  [Making a change](../AGENTS.md#making-a-change) steps. Run `every_server`
  with the desk's button, `sudo -n -u servers-mmx run-mmx-on-the-servers`,
  as a desk job, until a run has applied the triage agent's settings in
  part 3. After that, use the helper,
  `./server_management_scripts/run_mmx_on_util01 run every_server`.
  Reason: the helper runs only commits that MMHotline trusts, and
  MMHotline learns that it trusts every commit on `origin` with the
  triage agent's settings (`trusted_commits`).
- **The domain must be active for parts 2 and 4.** Signing in to MMHotline
  and the status page need the domain active at Cloudflare. While the
  domain is pending, tell the person which part waits, and when you check
  the domain next, instead of an unexplained pause.
- **The links.** The person sees the alerts on MMHotline's page,
  `https://ops.example.com`, and the status page at
  `https://status.example.com/`.

## Part 1: Read the backup results

This part runs in the first part of the setup. The person does nothing.

1. **Read the first uploads copy.** During chapter 7 (install everything
   on the production servers), MMX's `every_server` run started the first
   uploads copy. MMX also started the first restore drill, which waited
   for the uploads copy to finish. Read the copy's journal:

   ```sh
   # On the laptop:
   ssh desk01-agent 'cd systems_repository && ssh -F ssh/config root@10.20.0.1 journalctl -u copy_uploads_to_the_backup_bucket'
   ```

   With no app that keeps uploads (`backups.uploads_backup_runs_on: []`),
   no uploads copy runs: mark
   `uploads_copied_to_the_locked_bucket_every_night` as `deviated`, with
   no app keeping uploads as the reason.

   **Tell the person:** no message of its own, because step 2's message
   gives both results.

   **Check:** the copy's journal shows a passed copy, or the item is
   `deviated` with its reason.

2. **Read the first restore drill.** Read the drill's journal,
   `journalctl -u weekly_database_restore_drill`, and
   `/var/lib/restore_drill/latest_result.json` on `util01`, the same way
   as step 1. Record the verified result in checklist item
   `backups_restore_every_week`. Measure how long the drill took, from
   creating `restore01` until the drill's data checks answered, and how
   old the newest restored transaction was when the drill began. State
   whether the evidence identifies missing records or measures recovery
   during active writes; if it doesn't, say so.

   **Tell the person after:**

   > Your backups restore: the drill restored your database onto a temporary server in [the measured time], and the data checks passed. The newest restored change was [the age] old when the drill began.
   > The drill measures how long the database takes to come back, not how long your whole site takes to recover. [What the evidence shows about missing records.]

   **Check:** `backups_restore_every_week` holds the verified result from
   `latest_result.json`.

3. **Prove `util01`'s provider token.** The drill created and destroyed
   `restore01` with `util01`'s own provider token. Prove the token's
   second use now, without waiting for the daily timer: once the drill
   has finished, start the daily check for a leftover `restore01`, which
   starts a scheduled job and changes no setting, then read its journal:

   ```sh
   # On the laptop:
   ssh desk01-agent 'cd systems_repository && ssh -F ssh/config root@10.20.0.1 "systemctl start check_for_a_leftover_restore01.service && journalctl -u check_for_a_leftover_restore01"'
   ```

   The timer then repeats the check every day, and MMWatchdog alerts when
   a run fails.

   **Tell the person:** no message, because the check only confirms the
   drill's cleanup that step 2 reported.

   **Check:** mark `server_provider_account` once that run passed.

## Part 2: Phone alerts

This part is the alerts part of the setup. The person makes a Pushover account,
types two keys on the desk, and presses Acknowledge twice on the phone.
You do the rest. It takes about 15 minutes.

4. **Who is on call.** Read `people` and
   `rotation_sign_in_email_addresses` in `mmhotline_settings.yml`: chapter
   7 put the person there.

   **Ask the person:**

   ```text
   Who gets woken up when your site breaks?

     1. Alex  (alex@example.com)   you

   Add others, or say "just me".
   ```

   Add each other person to `people` and to
   `rotation_sign_in_email_addresses`, with their sign-in address at the
   company's domain. When the person has no address at the domain, ask for
   the address they use for work, and add it to MMHotline's Access policy
   as a named person (chapter 5, step 4).

   **Check:** `people` names everyone on call, each with an address that
   MMHotline's Access policy admits.

5. **Pushover.** Pushover is the phone app that rings for an alert.

   **Ask the person:**

   > Phone alerts use Pushover. It costs $5 once for each phone, after a free 30-day trial. Say "yes" to use it.

   When the person says yes, show the screen, with the person's password
   manager and the company's name:

   ```text
   Pushover (your phone alerts)

   What this is for:
     Pushover makes your phone ring when your site breaks, even at night.

   Do this now:
     1. Open  https://pushover.net/signup  and make an account.
     2. Save the login in 1Password.
     3. Install Pushover on your phone, and sign in.

     ALLOW CRITICAL ALERTS FOR PUSHOVER ON YOUR PHONE.  WITHOUT THEM, NIGHT ALARMS ARE SILENT.

     4. Open  https://pushover.net/apps/build.  Name it  Example alerts.  Press  Create Application.
     5. Open  https://pushover.net/groups.  Make a group named  Example on call,  and add yourself.

   Then paste your own user key here, in the chat.
   It is at the top of  https://pushover.net, under "Your User Key".
   It is not the group's key. It is not a secret.

   Optional: to get alerts on one device only, such as your phone and not
   your tablet, also tell me that device's name. It is listed at
   https://pushover.net under "Your Devices". Leave it out to get alerts
   on every device on your account.
   ```

   Each other person on call does steps 1 to 3 on their own phone, and
   sends you their own user key, and a device name if they want one; the
   person adds each one to the group.
   A delivery group's key lets the hub-outage alerters wake everyone in
   it at once, when `util01` goes silent. MMHotline needs each person's
   own user key instead, because an acknowledgement from a group key
   cannot claim an incident.

   **Check:** you have a user key of 30 letters and digits for each
   person on call, and none of them is the group's key.

6. **Add Pushover and the MMHotline-down alarm to the settings.** Copy two
   sections back from the Stack template's `mmhotline_settings.yml`
   (`skills/monkeymaxxing-stack/systems_repository_template/mmhotline_settings.yml`
   in the Stack's repository), each with its comments, and make one more change:

   - `sending_services`, with its `pushover` entry, in place of
     `sending_services: {}`;
   - `mmhotline_down_alarm`, from the comment line
     `# The MMHotline-down alarm is a small program` to
     `wake_the_backup_after_minutes_without_a_check_in`;
   - `phone_alerts_are_set_up` in `mmx_project_settings.yml`: change
     `false` to `true`. Until then, `every_server` asks for no Pushover key
     and gives MMWatchdog's fleet hub no push destination.

   Leave `triage_agent` and `status_page` out: parts 3 and 4 add them.
   `go-live` already saved the MMHotline-down alarm's Cloudflare token in
   the vault. Check with `mmx validate`, then publish the change with the
   [Making a change](../AGENTS.md#making-a-change) steps.

   **Tell the person:** no message, because step 7 asks for the keys.

   **Check:** pushed `main` has both sections, and
   `ssh desk01-agent sudo -n -u servers-mmx run-mmx-on-the-servers secrets usage`
   lists `pushover_application_token` and
   `mmwatchdog_pushover_user_or_group_key` as `not defined`.

7. **The person types the two Pushover keys on the desk.**

   **Ask the person:**

   > Please type this in your terminal, plus a code from your phone:
   >
   > `ssh desk01-secrets`
   >
   > It asks for two keys. Paste each one at its prompt:
   >
   > 1. The app's token: open https://pushover.net/apps, then Example alerts, and copy its API Token/Key.
   > 2. The group's key: open https://pushover.net/groups, then Example on call, and copy its group key.
   >
   > I carry on by myself when both keys are saved. You need not tell me.

   The command saves each key in the vault, and commits and publishes the
   vault itself. Wait on that result, as
   [`AGENTS.md`, "The two windows agree"](../AGENTS.md#the-two-windows-agree)
   says: run `secrets usage` every 10 seconds, for at most 9 minutes,
   until both keys show as defined.

   **Check:** `secrets usage` shows both keys as defined.

8. **Apply the settings.** Run `every_server` with the desk's button, as
   a desk job ([Making a change](../AGENTS.md#making-a-change)). The run
   writes `/etc/mmhotline/mmhotline_settings.yml`, and its
   `apply_the_mmhotline_settings` stage runs `mmhotline settings apply`.
   MMHotline tests each new part before it accepts it: Pushover's
   application token, and the MMHotline-down alarm's upload and first
   check-in. A part whose test fails keeps the earlier settings and fails
   the run. Read the reason in the run's results, correct the cause, and
   run `every_server` again. No automatic retry applies settings later.

   **Tell the person while waiting:** the Stack's tests measured a whole
   `every_server` run at about 5 to 7 minutes.

   > MMHotline now tests Pushover and the MMHotline-down alarm before using them. The run takes several minutes.

   **Check:** the run's results show the stage `util_push_app_keys` ran
   (it is skipped while `phone_alerts_are_set_up` is `false`), and
   `mmhotline settings show` on `util01` shows the `sending_services` and
   `mmhotline_down_alarm` parts applied.

9. **Add each phone to MMHotline.** For each person on call, add a
   Pushover contact method with their own user key. The key reaches
   `mmhotline` on `util01` on standard input, never on its command line. Add `--pushover-device-name NAME`
   only for a person who named one device; leave it out to send to every
   device on the person's account:

   ```sh
   # On the laptop. USER_KEY: the person's own Pushover user key, never the group's key. EMAIL: the person's sign-in address in people.
   ssh desk01-agent 'cd systems_repository && printf "%s\n" USER_KEY | ssh -F ssh/config root@10.20.0.1 "mmhotline contact-methods add --sign-in-email-address EMAIL --contact-method-type pushover_notification --pushover-user-key-file -"'
   # With one device (up to 25 letters, digits, _ and -), add to the end of the mmhotline command: --pushover-device-name NAME
   ```

   You add the contact method yourself. Do not send the person to
   MMHotline's Contact methods page for it.

   MMHotline refuses a device name that Pushover does not list for the
   key, and names the devices Pushover lists. With a group key, MMHotline
   saves the contact method and prints a warning in capitals: use the
   person's own user key instead (remove the contact method, then add it
   again).

   Saving the contact method sends that phone a quiet notification titled
   "MMHotline can reach this phone". It needs no acknowledgement. The
   command ends with the line "THIS PHONE HAS NOT PROVED IT WAKES YOU YET.
   RUN: sudo mmhotline incidents send-test-sos --sign-in-email-address
   EMAIL"; step 10 does that.

   **Tell the person first:**

   > Your phone shows a quiet Pushover notification, "MMHotline can reach this phone". Nothing to do.

   **Check:** `mmhotline contact-methods list` on `util01` says
   `Last test message: accepted` for each person, and the person says the
   notification arrived. `contact-methods list` shows only the last four
   characters of each user key.

10. **The test SOS.** MMHotline sends itself a test SOS and wakes one
    person's phone as a real SOS does, whether or not that person is on
    call. It waits up to 10 minutes for the acknowledgement. It closes the
    test itself after the claim, so there is nothing to resolve. Run it for
    each person on call, with their sign-in address:

    ```sh
    # On the laptop. EMAIL: the person's sign-in address in people.
    ssh desk01-agent 'cd systems_repository && ssh -F ssh/config root@10.20.0.1 mmhotline incidents send-test-sos --sign-in-email-address EMAIL --json'
    ```

    **Tell the person first:**

    > Next, a test SOS. An SOS is the most urgent alert: it wakes the person on call, even at night, and repeats until someone acknowledges it.
    > Your phone rings with "Test of the alerts. Nothing is wrong: acknowledge this." Press Acknowledge on it.
    > Please put the phone in Silent Mode first. Critical alerts should still sound.

    Exit 0 means the person acknowledged it: `test_sos.claimed_by`,
    `claimed_how` and `claimed_at` say who, how, and when, and
    `contact-methods list` then says `Emergency test: acknowledged at TIME.`
    Exit 1 has two causes. Read the command's message:

    - Nobody acknowledged within 10 minutes, and the test stays open. Ask the
      person to check that Pushover is signed in on the phone and that
      critical alerts are allowed for Pushover in the phone's settings.
      Run the command again: a new test closes the old one.
    - Someone pressed Acknowledge, but the acknowledgement came from another
      Pushover user, so it did not claim the test. This happens with a
      Pushover group key. The command stops at once and the test stays
      open. Remove that person's contact method (`mmhotline contact-methods
      remove --contact-method-id ID`, with the ID from `contact-methods
      list`), add it again with the person's own user key (step 9), and run
      the test again.

    **Ask the person after,** with `test_sos.incident_page_url`:

    > The test SOS reached you: [who] acknowledged it [how], at [the time].
    > Please open [the incident's link]. Sign in with your company email address and the code it emails you. You see the test, claimed by you and closed by MMHotline.

    Then read MMHotline's Access policy through the desk's Cloudflare API
    proxy. Access's page says a code was emailed for any address, so the
    page proves nothing about who is admitted; the policy states it
    exactly. `ACCOUNT_ID` is `vars.cloudflare_account_id` in
    `mmx_project_settings.yml`:

    ```sh
    # On the laptop:
    ssh desk01-agent curl -fsS http://127.0.0.1:8082/accounts/ACCOUNT_ID/access/apps
    ```

    Read the `policies` of the application whose `domain` is
    `ops.example.com`: each one's `decision`, `include` and `exclude`.

    Every `allow` policy must include only the company's email domain (an
    `email_domain` rule such as `example.com`), named people, or its
    GitHub organization. An `everyone` rule, or a domain the company does
    not own, fails the check. When `policies` lists only IDs, read each
    with `GET .../accounts/ACCOUNT_ID/access/policies/POLICY_ID`. Also
    check that `mmhotline backup check-uploads` on `util01` exits 0.

    **Check:** the command exited 0, the person opened the incident page
    after the sign-in, the Access policy passed, and
    `mmhotline backup check-uploads` exited 0. Then mark
    `mmhotline_reaches_the_person_on_call` and `company_email` done.

11. **The MMHotline-down alarm.** MMHotline goes down if `util01` goes
    down. So MMHotline checks in every minute with a small program in the
    team's Cloudflare account, the MMHotline-down alarm. When the
    check-ins stop, the alarm wakes the person on call after
    `mmhotline_down_alarm.wake_the_person_on_call_after_minutes_without_a_check_in`
    (5 by default), and the backup after
    `wake_the_backup_after_minutes_without_a_check_in` (10 by default).

    First check that `mmhotline down-alarm show` on `util01` names the
    person on call. Then send the alarm's test. MMHotline reads Pushover's
    receipt, which proves that Pushover accepted the notification, and
    cancels its repeats at once:

    ```sh
    # On the laptop:
    ssh desk01-agent 'cd systems_repository && ssh -F ssh/config root@10.20.0.1 mmhotline down-alarm send-test --json'
    ```

    **Tell the person first:**

    > Last test: the alarm for when MMHotline itself is down.

    > **YOUR PHONE MAY SOUND ONCE MORE.  THERE IS NOTHING TO DO.**

    Exit 0 means each held message was accepted and its repeats were
    cancelled. Exit 1 names, for each person, what failed: read each
    `test_sends` entry's `send_outcome` and `pushover_receipt_outcome`.
    For `cancel_failed`, the phone may sound again for up to 10 minutes:
    tell the person to press Acknowledge on it.

    The outage test, which stops MMHotline, and the hub-outage alerters'
    test are optional, in
    [Check my system's protections](../operating_procedures/assess_a_running_system_and_recommend_changes.md#check-my-systems-protections).
    Offer them once, at the end of the setup.

    **Check:** `down-alarm show` names the person on call, and
    `down-alarm send-test` exited 0. Then mark
    `mmhotline_down_alarm_alerts_when_the_location_goes_silent` done.

12. **Join the desk to monitoring.** The full desk playbook joins the desk
    to MMWatchdog, as
    [chapter 7, part 5](07_install_everything_on_the_production_servers.md#part-5-join-the-systems-desk-to-monitoring)
    says. It runs as root on the desk, so the person runs it. Give the
    person a short plain summary of what the desk review changes first, as
    [Your login on the desk](../AGENTS.md#your-login-on-the-desk) says.

    **Ask the person:**

    > Last step: your systems desk joins the monitoring, so you hear when it has trouble too.
    > Please type this in your terminal, plus a code from your phone:
    >
    > `ssh desk01-review`
    >
    > It shows what changes on your systems desk: [the short summary]. Type yes.

    **Tell the person after,** which ends the alerts part of the setup:

    > Your phone alerts work. The test SOS woke you, and the MMHotline-down alarm reaches your phone too: [MMHotline's link].
    > Only addresses that end in `@example.com` can sign in to MMHotline.
    > Next, when you want: the triage agent, which looks into each alert before it wakes you, and your status page.

    **Check:** `sudo mmwatchdog fleet` on `util01` lists `desk01`.

## Part 3: The triage agent

This part is the triage agent's part of the setup. The person picks what the agent
may do alone, makes one key, and types it on the desk.

13. **What the triage agent may do alone.** The answer is
    `what_the_triage_agent_may_do_without_a_person` in
    `mmx_project_settings.yml`, `routine_fixes` until now.

    **Ask the person:**

    ```text
    The triage agent looks into each alert before it wakes you.
    What may it do without asking you first?

      1. Nothing.  Every fix waits for you.
      2. Routine fixes:  restart a failed service, free disk space, pull an image again.  (I recommend this.)
      3. Routine fixes, and replace a failed app server, reboot for updates,
         and add or remove app servers with the load.

    Say 1, 2 or 3.
    ```

    Write the answer as `every_fix_waits_for_a_person`, `routine_fixes`
    or `routine_fixes_and_server_work`. Database servers and `util01`
    always need a person.

    **Check:** the setting holds the person's answer.

14. **The triage agent's key.** The triage agent runs on
    `triage_agent_coding_agent` in `mmx_project_settings.yml`: Claude Code
    by default. An API key belongs to the company's account, keeps working
    when a person leaves, and has its own usage limits, so it is the
    default.

    Copy the `triage_agent` section back from the Stack template's
    `mmhotline_settings.yml`, from the comment line
    `# The triage agent: Claude Code or Codex` to the `{{ end }}` line
    after the section. Keep `credential_type: api_key` unless the person
    asks for another kind. With `triage_agent_coding_agent: codex`, set
    `model` to one that `codex debug models` lists on `util01`. Check with
    `mmx validate`, then publish the change.

    **Ask the person:**

    ```text
    The triage agent (your night-time helper)

    What this is for:
      It looks into each alert, at any hour, and writes up the cause.
      Its work is billed to this key's account.

    Do this now:
      1. Open  https://console.anthropic.com/settings/keys
      2. Press  Create Key.  Name it  Example triage agent.
      3. Type this in your terminal, plus a code from your phone.
         It logs in to your systems desk:

           ssh desk01-secrets

         Press Enter at its question for an API key, then paste the key.
    ```

    For Codex, the page is `https://platform.openai.com/api-keys`. The
    command explains the other kinds of credential itself. When the person
    picks one, its last line names the setting to write, such as
    `credential_type: subscription_token`; ask the person to paste that
    line in the chat. The line holds no secret.

    **Check:** `secrets usage` shows `mmhotline_triage_agent_credential`
    as defined.

15. **Apply the triage agent's settings.** Run `every_server` with the
    desk's button, as a desk job. MMHotline gives the triage agent a test
    prompt in a sandbox, as a Unix user with no sudo and internet access
    only through MMHotline's proxy, before it accepts the settings. The
    proxy lets the agent reach the coding agent's service, OSV.dev, the
    servers, the pages in `software_outside_the_distribution.yml`, and
    `listed_hosts`. The scheduled software review stays off, so the agent
    wakes only for alerts; a team turns it on later with
    [Turn on the scheduled software review](../operating_procedures/turn_on_the_scheduled_software_review.md).
    From now on, run MMX on `util01` with the helper.

    **Tell the person after:**

    > The triage agent passed its test. From now on it looks into each alert first, and it [does nothing alone / does routine fixes alone / does routine fixes and server work alone].

    **Check:** `mmhotline settings show` on `util01` shows the
    `triage_agent` part applied, `mmhotline triage-agent show` names the
    coding agent, and `mmhotline agent-playbook-rules show` prints a line
    beginning with
    `Services whose changes a person must approve, on every inventory: pgautofailover.service`.
    Mark `triage_agent_investigates_alerts` done. Mark
    `agent_runs_mmx_on_util01` done after the next helper run applied a
    commit and you checked the result in MMX's history on `util01`.

## Part 4: The status page

This part is the status page's part of the setup. The person runs one Cloudflare
command on the desk, looks at the page, and resolves one test notice.

16. **The page's address.** Set `vars.status_page_host_name` in
    `mmx_project_settings.yml`: `status.example.com`, with no question,
    when the domain has no DNS record for `status`. The page's title is
    the company's name from chapter 1. The page is public, so it gets no
    Access application. Publish the change.

    When an app keeps uploads, `go-live` turned R2 on already. Otherwise
    check R2 through the API proxy
    (`GET http://127.0.0.1:8082/accounts/ACCOUNT_ID/r2/buckets`).

    **Ask the person,** only when R2 is off:

    > Your status page lives in Cloudflare's file storage, R2. It costs nothing up to 10 GB a month.
    > Please open https://dash.cloudflare.com/?to=/:account/r2/overview and finish the checkout there. It asks for a card. I carry on by myself when R2 is on.

    Wait on the same R2 request every 10 seconds, for at most 9 minutes,
    until it answers, as
    [`AGENTS.md`, "The two windows agree"](../AGENTS.md#the-two-windows-agree)
    says, and never ask the person to say "done".

    **Check:** the setting is pushed, and the R2 request answers.

17. **Make the page and its keys.** `set-up-outside-services cloudflare`
    runs `mmhotline status-page set-up`, which makes the page's R2 bucket,
    connects the host name to it, and adds the rule that serves
    `index.html`. Then it saves MMHotline's key for the bucket in the vault,
    as `mmhotline_status_page_r2_access_key_id` and
    `mmhotline_status_page_r2_secret_access_key`, and writes the person's
    own posting key into the person's token file on the desk. Never make
    the page's DNS record yourself.

    **Ask the person:**

    > Please type this in your terminal, plus a code from your phone:
    >
    > `ssh -t desk01 set-up-outside-services cloudflare`
    >
    > It shows a link. Open it, press Continue to summary, then Create Token, and paste the token at its prompt.
    > It makes only what is missing. I carry on by myself when the keys are saved.

    Wait on `secrets usage` every 10 seconds, for at most 9 minutes,
    until both R2 vault keys show as defined.

    **Check:** the page's bucket is in the R2 bucket list, and
    `secrets usage` shows both R2 vault keys as defined.

18. **Add the `status_page` section.** Copy it back from the Stack
    template's `mmhotline_settings.yml`, from the comment line
    `# The status page uses two files` to the end. Set `page_title` to
    the company's name, and `r2_bucket_url` to
    `https://ACCOUNT_ID.r2.cloudflarestorage.com/BUCKET`, with the bucket's
    name from the R2 bucket list. Publish, then run `every_server` with the
    helper. MMHotline checks that the key can write the bucket, and
    publishes "Everything is working." on the page. A key that cannot
    write fails the run, with MMHotline's reason in its results.

    **Check:** `mmhotline settings show` on `util01` shows the
    `status_page` part applied.

19. **Post a test notice, and resolve it from the desk.** Once the host
    name's certificate is issued, a few minutes after step 17,
    `curl -fsS https://status.example.com/` shows "Everything is working.".
    Post a test notice from `util01`:

    ```sh
    # On the laptop:
    ssh desk01-agent 'cd systems_repository && ssh -F ssh/config root@10.20.0.1 mmhotline status-page post --json --message "This is a test of our status page. Nothing is wrong."'
    ```

    **Tell the person first:**

    > Next, I post a test notice to your status page. You then close it from your systems desk, the way you post while `util01` is down.
    > Customers can see the test under "Recently resolved" until five later notices push it off.

    **Ask the person,** with the `notice_id` the post printed:

    > Please open https://status.example.com/. You see the test notice.
    > Then type this in your terminal, plus a code from your phone:
    >
    > `ssh -t desk01 '. ~/.config/monkeymaxxing-stack/example_systems.env && mmhotline status-page resolve --notice-id 1 --closing-message "The test is over."'`
    >
    > Then reload the page. It says "Everything is working." again.

    When the desk's resolve fails, resolve the notice from `util01` at
    once, the same way as the post, because customers must not see an open
    test. Then fix the person's posting key with step 17's command.

    **Tell the person after,** which ends the status page's part of the setup:

    > Your status page works: [the page's link]. You can post to it from MMHotline, and from your systems desk while `util01` is down.

    **Check:** the page says "Everything is working." again, with the
    test under "Recently resolved". Mark `status_page_for_customers` done.

## If something is different

- **The domain is still pending:** in the first part of the setup, part 1 needs
  nothing from the domain. Parts 2 and 4 wait, as
  [Before you start](#before-you-start) says.
- **A settings part fails to apply** (steps 8, 15 and 18): read the reason
  in the run's results, correct the cause, and run `every_server` again.
- **A drill or a copy failed** (steps 1 and 2): a drill or a copy that
  failed starts again in each run of `every_server` until one passes: fix
  the cause, publish, and run `every_server` again.
- **The test SOS is not acknowledged** (step 10): the command exits 1 and
  the test stays open. Check Pushover on the phone and its critical
  alerts, then run the command again.
- **The acknowledgement did not claim the test** (step 10): the contact
  method holds a Pushover group key. Add it again with the person's own
  user key.
- **Resolving the test notice from the desk fails** (step 19): resolve it
  from `util01` at once.

## Why the chapter works this way

**Go live first, alerts the same day.** The site goes live without phone
alerts, and the alerts part of the setup adds them in about 15 minutes. Reason: the
first part of the setup is long already, and each extra account in it is one more
chance to stop before the site is live.

**The button until the triage agent's settings.** `util01`'s helper runs
only commits that MMHotline trusts, and MMHotline learns that it trusts
every commit on `origin` from the triage agent's settings
(`trusted_commits`). Before they are applied, the helper refuses with
"MMHotline did not answer the commit check".

**MMHotline's own test SOS.** `mmhotline incidents send-test-sos` pages the
person you name exactly as a real SOS does, and closes the test itself
after the claim. So the person presses Acknowledge once, and nobody
resolves a test by hand. It does not pass through MMWatchdog: MMWatchdog's
signed check-ins prove that path every minute, and MMHotline warns when
they stop.

**The Access policy, not a test email.** The policy is what Access
enforces. Reading it takes seconds and proves more than a wait for an
email to an outside address.

**The restore drill measures the database only.** It measures database
recovery time, not the time to recover the whole site.

**The status page lives at Cloudflare.** It lives in the team's Cloudflare
account, so the page works while every server is down, and the desk can
post with the person's own R2 key while `util01` is down.

Next, in the same reply once part 1's checks passed, as the skill's "Now
and next" rule says: [Chapter 9: Go live](09_go_live.md), still in the
first part of the setup.
