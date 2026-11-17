# Chapter 8: Check that alerts reach your phone and backups restore

**When:** in three sittings.

- **The first sitting** runs only part 4 (read the backup results), right
  after chapter 7 (install everything on the production servers). Then
  chapter 9 puts the app live.
- **The alerts sitting,** when the person says "set up alerts", runs
  parts 1 to 3 without the `triage_agent` section, and chapter 7's part 5
  (join the systems desk to monitoring). The person types
  `ssh desk01-alerts` for the Pushover screen. Parts 2 and 3 need the
  domain to show "Active" at Cloudflare.
- **Later sittings** add part 1's `triage_agent` section, with
  `ssh desk01-secrets` for the triage agent's credential, and part 5 (the
  status page).

Until the alerts sitting is done, say plainly that the site has no phone
alerts, whenever you report on the system.

**What this chapter does:** the first backup's and the first restore
drill's results are read. MMHotline gets its alerting settings: Pushover,
the MMHotline-down alarm, and later the triage agent. Each person on call
connects a phone, and a test proves the path from the servers to the
phone. The status page, where the team tells customers about a problem,
gets its settings and a test notice.

**Who acts:** you, the coding agent, write the settings, run MMX, and
read the results through the desk. In the alerts sitting, each person on
call signs in to MMHotline, adds a phone, and acknowledges the test
notifications (parts 2 and 3).

**Tell the person when the chapter starts,** in the first sitting:

> I am reading the first backup and the first restore drill.

## Before you start

- **The messages to the person.** Each step says what to tell or ask the
  person, in quote blocks: "Tell the person first" before the step, "Ask
  the person" when the person must act or approve, "Tell the person while
  waiting" during a step that runs for minutes, and "Tell the person after"
  with the result and its link. Say each message when its step comes, in
  your own words, with the team's own names and links.
- **The domain must be active for three parts.** Signing in to MMHotline and checking the public status page need the
  domain active at Cloudflare. While the domain is pending, continue part 1 (add MMHotline's alerting settings) and part 4 (read the backup results). Part 2 (each person on call signs in and adds a phone), part 3 (the MMHotline-down alarm), and part 5 (the status page) wait until
  Cloudflare shows the domain as "Active". While the domain is pending,
  tell the person which parts wait, and when you check the domain next,
  instead of an unexplained pause.
- **The links.** The person sees the alerts on MMHotline's page,
  `https://ops.example.com`, and the status page at
  `https://status.example.com/`.

## Part 1: Add MMHotline's alerting settings

1. **Add MMHotline's alerting settings to `mmhotline_settings.yml`.**
   Add the complete YAML below, replacing `sending_services: {}` from
   chapter 7 (install everything on the production servers). The YAML adds three of the four parts that chapter 7 (install everything on the production servers) left out.
   The source is `skills/monkeymaxxing-stack/systems_repository_template/mmhotline_settings.yml`
   in the stack's repository. Replace the example Cloudflare account ID
   with `{{ .vars.cloudflare_account_id }}`, the account ID in
   `mmx_project_settings.yml`:

   ```yaml
   # mmhotline_settings.yml, in the systems repository: added in chapter 8 (check that alerts reach your phone and backups restore)
   sending_services:
     pushover:
       application_token: {{ .secrets.pushover_application_token | toJson }}
   triage_agent:
     commit_signing_public_key: "{{ .vars.triage_ssh_public_key }}"
     coding_agent: {{ .vars.triage_agent_coding_agent }}     # claude_code or codex, from mmx_project_settings.yml
     credential_type: api_key                 # the kind the person chose in the triage agent's sitting
     credential: {{ .secrets.mmhotline_triage_agent_credential | toJson }}
     model: opus                              # the newest of the provider's most capable family that answers within minutes
     reasoning_effort: high
     internet_access: listed_hosts_only
     listed_hosts: []                         # MMHotline lists the pages of software_outside_the_distribution.yml itself
     software_review_interval_hours: off      # the scheduled software review, off until the team turns it on
   mmhotline_down_alarm:
     cloudflare_account_id: "{{ .vars.cloudflare_account_id }}"   # the Cloudflare account's ID, from mmx_project_settings.yml
     cloudflare_api_token: {{ .secrets.mmhotline_down_alarm_cloudflare_api_token | toJson }}
   ```

   `opus` is a Claude Code model. With `triage_agent_coding_agent: codex`,
   set `model` to one that `codex debug models` lists, run on `util01`
   after chapter 7 (install everything on the production servers)
   installed Codex there, and set `reasoning_effort` to a level that model
   lists. The dryrun below checks only the model's form; the test prompt
   when `util01` applies the settings proves the model works.
   Each secret is written with `toJson`, as in the template, so a value
   with quotes or several lines, such as a ChatGPT sign-in, stays one
   YAML value.

   MMHotline's logging proxy forwards the triage agent's internet
   connections only to allowed destinations. The agent cannot connect
   directly to internet hosts. The allowed destinations are:

   - the coding agent's service, OSV.dev, and the servers;
   - the hosts of `releases_page` and `security_advisories_page` in
     `software_outside_the_distribution.yml`, which MMHotline lists from
     MMHotline's copy of the systems repository;
   - extra hosts the team adds to `listed_hosts`, which starts empty.

   The scheduled software review stays off, so the triage agent wakes only
   for alerts and costs nothing otherwise; a team turns the review on later
   with [Turn on the scheduled software review](../operating_procedures/turn_on_the_scheduled_software_review.md).

   **Tell the person first.** Explain the rules for running the agent's
   playbooks in `mmhotline_settings.yml` before the triage agent gets
   permission to act:

   > Next, I turn on the alerting. MMWatchdog sends each failure that needs a person to MMHotline.
   > MMHotline first starts the triage agent with the alert's details. The triage agent investigates, writes up the cause, and gets a fix ready.
   > The rules you chose in chapter 6 decide which fixes run at once and are reported, and which wait for your approval.

   **Tell the person after:** no message, because step 2 applies the
   settings.

   **Check:** `mmx validate` passes on the edited file.

2. **Preview and apply the alerting settings.**
   Commit, synchronize, and push, then show the person `sudo -n -u servers-mmx run-mmx-on-the-servers dryrun every_server --connection ssh_only`.
   The button previews the pushed `main` commit, so push first.
   The dryrun uses the pinned MMHotline release's `mmhotline settings check`
   on `util01` to check the proposed, rendered contents of
   `/etc/mmhotline/mmhotline_settings.yml`. A mistake fails
   the task `mmhotline/write_the_mmhotline_settings`, and the dryrun's
   output lists each problem by its key, such as
   `triage_agent.reasoning_effort: required`.
   `/etc/mmhotline/mmhotline_settings.yml` holds secret values, so MMX
   hides the rendered settings' changes. MMX shows the check's message,
   with any secret value replaced by `[redacted]`.

   Then run `every_server`. The first run applies the triage agent's
   settings, so it uses the systems desk's button:

   ```sh
   # This systems desk, in the coding agent's checkout, after the push:
   sudo -n -u servers-mmx run-mmx-on-the-servers run every_server --connection ssh_only
   ```

   After this run, every later settings
   change in this chapter uses the helper:
   `./server_management_scripts/run_mmx_on_util01 run every_server`.

   The run writes
   `/etc/mmhotline/mmhotline_settings.yml`. Then the run's
   `apply_the_mmhotline_settings` stage runs `mmhotline settings apply`.
   MMHotline tests each changed part before accepting the new settings:

   - the triage agent receives a test prompt in a sandbox, as a Unix user
     with no sudo and internet access only through MMHotline's proxy;
   - MMHotline tests Pushover's application token;
   - MMHotline tests the MMHotline-down alarm's upload and first check-in.

   If a part's test fails, MMHotline keeps the earlier settings for the
   failed part. A settings part that fails to apply fails `util01`'s run.
   Read the run's results from `util01`'s MMX history with
   `./server_management_scripts/run_mmx_on_util01 results`. Select the failed apply task to read
   the exit code, output, and each settings part's refusal reason.
   Correct the cause, then explicitly rerun `every_server` (with the button until a run has applied the triage agent's settings). No automatic
   retry applies settings later.

   **Tell the person while waiting:** the Stack's tests measured a whole
   `every_server` run at about 5 to 7 minutes (284 to 397 seconds).

   > MMHotline now tests each new setting before using it: the triage agent answers a test question, and Pushover and the MMHotline-down alarm get a test call. The run takes several minutes.

   **Tell the person after:**

   > The triage agent, Pushover, and the MMHotline-down alarm are set up on MMHotline.
   > The triage agent passed its test, and its rules now apply.

   **Check:**
   `ssh -F ssh/config root@10.20.0.1 'mmhotline settings show'` shows
   every part applied, or why one didn't, and `mmhotline agent-playbook-rules show`
   on `util01` prints a line beginning with
   `Services whose changes a person must approve, on every inventory: pgautofailover.service`.
   The line also records who changed the list and when.

   Mark `triage_agent_investigates_alerts` done after the `triage_agent`
   part applied and the agent-playbook-rules command printed the required line.
   Mark `agent_runs_mmx_on_util01` done after the agent-run MMX operation
   applied the alerting-settings commit and the agent verified the result
   in MMX's utility-server history.

## Part 2: Each person on call signs in and adds a phone

3. **Each person on call signs in and adds a phone.** The person opens MMHotline's page, `https://ops.example.com`, signs in
   through Access,
   and adds a contact method there: Pushover, with their own Pushover user
   key, which isn't a secret. MMHotline sends that phone a test as soon as
   the contact method is saved.

   **Ask the person,** and warn the person before saving: the test rings
   like an alarm. It is an emergency-priority Pushover message that repeats every 30 seconds, for up to 10 minutes, until the person acknowledges it on the phone.

   > Please open https://ops.example.com, sign in with your company email address and the emailed code, and add a contact method: Pushover, with your Pushover user key.
   > When you save it, your phone rings like an alarm, every 30 seconds, until you acknowledge the message in Pushover. It is only a test. Nothing is wrong.
   > Tell me when you see the test on your phone and have acknowledged it.

   The contact method's card says "Accepted by Pushover" once Pushover
   accepts the test notification. Acceptance does not prove phone delivery.
   Each person must see the test
   notification on the phone and acknowledge the notification in Pushover.
   The phone observations prove delivery and acknowledgement for each
   person's contact method.

   **Tell the person after:** no message, because step 4 sends the test
   SOS.

   **Check:** each person on call saw and acknowledged the test on the
   phone, and each contact method's card says "Accepted by Pushover".

4. **The test SOS.** Once everyone has added a Pushover contact
   method, one test SOS from MMWatchdog's fleet hub on `util01` proves the path from
   the fleet hub to the phone of whoever is on call now. MMHotline first
   gives the triage agent the minutes in `triage_agent.sos_waits_for_the_agent_minutes`
   in `mmhotline_settings.yml` (3 by default) to investigate the test SOS.
   Then the phone rings until the person on call claims the test SOS in
   MMHotline:

   ```sh
   # This systems desk, in the systems repository:
   ssh -F ssh/config root@10.20.0.1 'mmwatchdog send-notice --alert-severity sos --title "Test of the alerts. Nothing is wrong: claim this." --destination mmhotline_on_call'
   ```

   **Tell the person first:**

   > Next, I send a test SOS. An SOS is the most urgent alert: it wakes the person on call, even at night, and repeats until someone claims it.
   > MMHotline first gives the triage agent 3 minutes. Then the phone of the person on call rings.

   **Ask the person on call:**

   > Your phone rings with "Test of the alerts. Nothing is wrong: claim this." That alert is expected.
   > Claim it with "Claim: I'm handling the incident" on the incident's page in MMHotline, or acknowledge it in Pushover. Claiming stops the alert from reaching anyone else.
   > Then select resolve on the incident's page, and tell me when you have.

   The test SOS sent with `mmwatchdog send-notice` has no health check
   whose recovery would close the test incident automatically.
   After claiming the test SOS, the person on call must resolve the test
   incident on the incident's MMHotline page. The MMHotline-down alarm's test in part 3 (the MMHotline-down alarm)
   needs no open incident, because the test stops MMHotline, which then
   contacts nobody.

   **Tell the person after:** no message, because step 5 reports the
   result with the Access check.

   **Check:** the person on call's phone rang, the person claimed the test
   SOS, and the test incident shows as resolved.

5. **Check who MMHotline's sign-in admits, and MMHotline's backup.**
   Then complete the remaining verification for
   `mmhotline_reaches_the_person_on_call`. The person signs in to
   `https://ops.example.com` with a company address and the emailed code.
   You then read the Access policy through Cloudflare's API, instead of
   waiting to see whether a code reaches an outside address. Access's page
   says a code was emailed for any address, so the page proves nothing
   about who is admitted; the policy states it exactly:

   `ACCOUNT_ID` is `vars.cloudflare_account_id` in `mmx_project_settings.yml`.
   The coding agent runs this through the desk's Cloudflare API proxy, which adds the person's token:

   ```sh
   # This systems desk, in the systems repository:
   curl -fsS http://127.0.0.1:8082/accounts/ACCOUNT_ID/access/apps |
     jq -r '.result[] | select(.domain == "ops.example.com") | .policies[] |
            "\(.decision) \(.name): include \(.include | tostring), exclude \(.exclude | tostring)"'
   ```

   Every `allow` policy must include only the company's email domain (an
   `email_domain` rule such as `example.com`), named people, or its GitHub
   organization. An `everyone` rule, or a domain the company does not own,
   fails the check. When `policies` lists only IDs, read each with
   `GET .../accounts/ACCOUNT_ID/access/policies/POLICY_ID`.
   Also check that
   `ssh -F ssh/config root@10.20.0.1 'mmhotline backup check-uploads'`
   exits 0.

   **Tell the person after.** Say what you read, and give the person the
   link to the same policy in the Cloudflare dashboard (Zero Trust, Access
   controls, Applications, MMHotline):

   > Alerts reach your phone: the test SOS rang [the person on call]'s phone, and the claim stopped it.
   > Only addresses that end in `@example.com` can sign in to MMHotline: [the Access policy].

   **Check:** after the phone, Access, and
   backup checks pass, mark `mmhotline_reaches_the_person_on_call` done.

6. **Optional: try the phone-code lockout alert.** Nothing here requires it.
   The person can make wrong codes on purpose to see the alerts: one
   wrong code at `ssh desk01` makes an `info` alert, and
   `wrong_codes_before_lockout` wrong codes lock the laptop out and send
   the alert set by `alert_severity_when_a_laptop_is_locked_out` (see
   `phone_code_lockout` in `mmx_project_settings.yml`). The laptop can
   log in again after `lockout_minutes`. Offer the test once, and skip it
   when the person declines. When the severity is `sos`, tell the person
   on call first, because the test wakes them.

   **Ask the person,** once:

   > If you want to see the phone-code alerts, you can type wrong codes at `ssh desk01` on purpose. This test is optional.
   > One wrong code sends a quiet alert. [The number] wrong codes lock your laptop out for [the minutes] and send [the alert].
   > Do you want to try it?

   **Check:** none, because the test is optional.

## Part 3: The MMHotline-down alarm

7. **The MMHotline-down alarm,** which part 1 (add MMHotline's alerting settings) set up, stores a prepared Pushover
   notification for a person whose Pushover contact method receives SOS
   alerts. Without a qualifying contact method, the MMHotline-down alarm has no
   notification for the person. So the MMHotline-down alarm check comes after part 2 (each person on call signs in and adds a phone).

   The MMHotline-down alarm answers at the MMHotline-down alarm's workers.dev
   address and needs no host name. Every minute MMHotline checks in with
   the MMHotline-down alarm and uploads a prepared SOS for whoever is on call.
   The SOS is a Pushover emergency notification, which repeats until the
   recipient acknowledges the notification in Pushover.
   When the check-ins stop, the MMHotline-down alarm sends the prepared notification
   to the person on call and then to the backup, each after the minutes
   that `mmhotline_down_alarm` in `mmhotline_settings.yml` names (5 and 10
   by default): the person on call after
   `mmhotline_down_alarm.wake_the_person_on_call_after_minutes_without_a_check_in`,
   and the people `on_call_schedule.backup_option` in
   `mmhotline_settings.yml` selects after
   `mmhotline_down_alarm.wake_the_backup_after_minutes_without_a_check_in`.
   The template uses `everyone_available`: everyone else who is available.

   The MMHotline-down alarm is a Cloudflare Worker: a program in the team's Cloudflare
   account, not an app process on a server. The MMHotline-down alarm's Worker is named
   after MMHotline's host name, such as
   `mmhotline-down-alarm-ops-example-com-7db8a22e`, and each upgrade of
   MMHotline uploads its new one with the token from the vault.

   First, `ssh -F ssh/config root@10.20.0.1 'mmhotline down-alarm show'`
   shows which person's Pushover notification would be sent after
   the minutes in `mmhotline_down_alarm.wake_the_person_on_call_after_minutes_without_a_check_in`
   (5 by default) without check-ins. The command inspects the prepared
   notification without waiting. Then
   `ssh -F ssh/config root@10.20.0.1 'mmhotline down-alarm send-test'`
   sends the person on call the MMHotline-down alarm's test now, an emergency
   notification titled "Test of the MMHotline-down alarm",
   which repeats until the person on call acknowledges the notification
   in Pushover.

   **Tell the person first:**

   > MMHotline goes down if `util01` goes down. So MMHotline checks in every minute with a small alarm in your Cloudflare account.
   > When the check-ins stop, the alarm wakes the person on call after 5 minutes, and everyone else who is available after 10 minutes, even if the whole server location is down.
   > Two other servers also watch `util01`. If `util01` goes silent, they alert the phones directly through Pushover.

   **Ask the person on call:**

   > Your phone now gets "Test of the MMHotline-down alarm". That alert is expected, and it repeats until you acknowledge it in Pushover.
   > Tell me when you see it and have acknowledged it.

   - **The outage test is optional.** It stops MMHotline and wakes
     the person on call, so it is not part of the setup. Offer it with
     the other protection checks at the end of the setup:
     [Check my system's protections](../operating_procedures/assess_a_running_system_and_recommend_changes.md#check-my-systems-protections).
     The `send-test` above proves that the MMHotline-down alarm's notification reaches
     the phone, which is the setup's proof for
     `mmhotline_down_alarm_alerts_when_the_location_goes_silent`.
   - **The hub-outage alerters,** an app server and a database server that alert
     the Pushover group straight from MMWatchdog when `util01` goes silent
     (`sudo mmwatchdog fleet` on `util01` names them). Their outage test,
     with MMWatchdog's fleet hub stopped on `util01`, is optional too, in the same
     section. Their item, `hub_outage_alerters_alert_when_util01_goes_silent`, is
     in the checklist's `growth_and_improvement_items`.

   **Tell the person after:**

   > The MMHotline-down alarm reaches your phone.
   > A real outage test stops MMHotline and wakes the person on call, so it waits for a quiet time that you choose, after the setup.

   **Check:** `mmhotline down-alarm show` names the person on call, and
   the person on call saw and acknowledged the `send-test` notification.

## Part 4: Read the backup results

8. **Read the first uploads copy.** During chapter 7 (install everything on the production servers), MMX's
   `every_server` run started the first uploads copy automatically.
   MMX also started the first restore drill, which waited for the uploads
   copy to finish. Read the copy and drill results with the person.
   The copy: `ssh -F ssh/config root@10.20.0.1 'journalctl -u copy_uploads_to_the_backup_bucket'`;
   with no app that keeps uploads
   (`backups.uploads_backup_runs_on: []`), no uploads copy runs.
   If no app keeps uploads, mark
   `uploads_copied_to_the_locked_bucket_every_night` as `deviated`,
   with no app keeping uploads as the reason.

   **Tell the person:** no message of its own, because step 9's message
   gives both results.

   **Check:** the copy's journal shows a passed copy, or the item is
   `deviated` with its reason.

9. **Read the first restore drill.** The drill:
   `ssh -F ssh/config root@10.20.0.1 'journalctl -u weekly_database_restore_drill'`.
   Read `/var/lib/restore_drill/latest_result.json` on `util01` and
   record the verified result in checklist item `backups_restore_every_week`.
   Measure how long the drill took, from creating
   `restore01` until the drill's data checks answered, and how old the
   newest restored transaction was when the drill began. State whether the
   evidence identifies missing records or measures recovery during active
   writes; if it doesn't, say so.

   **Tell the person after:**

   > Your backups restore: the drill restored your database onto a temporary server in [the measured time], and the data checks passed. The newest restored change was [the age] old when the drill began.
   > The drill measures how long the database takes to come back, not how long your whole site takes to recover. [What the evidence shows about missing records.]

   **Check:** `backups_restore_every_week` holds the verified result from
   `latest_result.json`.

10. **Prove `util01`'s provider token.** The drill created and destroyed
    `restore01` with `util01`'s own provider token. Prove the token's
    second use now, without waiting for the daily timer: once the drill has
    finished, start the daily check for a leftover `restore01` over SSH
    (`ssh -F ssh/config root@10.20.0.1 'systemctl start check_for_a_leftover_restore01.service'`,
    which starts a scheduled job and changes no setting), then read its
    journal (`ssh -F ssh/config root@10.20.0.1 'journalctl -u check_for_a_leftover_restore01'`).
    The timer then repeats the check every day, and MMWatchdog alerts when
    a run fails.

    **Tell the person:** no message, because the check only confirms the
    drill's cleanup that step 9 reported.

    **Check:** mark `server_provider_account` once that run passed.

## Part 5: The status page

11. **The status page's Cloudflare resources and key.** The status page's
    host name is `vars.status_page_host_name` in
    `mmx_project_settings.yml`: `status.example.com` by default, which you
    set in the status page's sitting.
    Check that `vars.cloudflare_account_id` there is the account ID used for the MMHotline-down alarm and Access session revocation.
    The status page's title is the company's name, from chapter 1 (answer two questions).
    The status page is public, so the page gets no Access application.

    `set-up-outside-services cloudflare`, which the person runs in the
    status page's sitting with `ssh -t desk01 set-up-outside-services cloudflare`,
    runs `mmhotline status-page set-up` with the person's desk token, which
    MMHotline never stores. R2 must be on first: the person approves
    Cloudflare's payment on R2's page, `https://dash.cloudflare.com/?to=/:account/r2/overview`. MMHotline created the R2 bucket, named after
    the host name, such as `mmhotline-status-status-example-com-18a8ea11`;
    connected the host name to the bucket, so Cloudflare created the host
    name's DNS record and certificate; and added a URL rewrite rule that
    serves `index.html` at the page's root address, such as
    `https://status.example.com/`. Never make the status page's DNS
    record yourself. A rerun creates only missing resources.

    The key MMHotline posts with is in the vault too, made by the same
    command: an account API token for the page's bucket only, so that
    posts keep working when the person who made the token leaves, as
    `mmhotline_status_page_r2_access_key_id` and
    `mmhotline_status_page_r2_secret_access_key`.
    The page's `r2_bucket_url` is the one the command printed, also in
    the person's own token file on the desk as `MMHOTLINE_STATUS_PAGE_R2_BUCKET_URL`, and
    `https://ACCOUNT_ID.r2.cloudflarestorage.com/BUCKET` with
    the bucket's name from `GET http://127.0.0.1:8082/accounts/ACCOUNT_ID/r2/buckets`.

    **Tell the person first:**

    > Next, I set up your status page, `status.example.com`, where you tell your customers about a problem.
    > The page lives in your Cloudflare account, so the page works while every server is down.

    **Check:** the bucket is in the list from
    `GET http://127.0.0.1:8082/accounts/ACCOUNT_ID/r2/buckets`, and
    `secrets usage` shows both R2 vault keys as defined.

12. **Add the `status_page` section to `mmhotline_settings.yml`.**
    Add the complete YAML below, using the company's name, the chosen
    host name, and the `r2_bucket_url` printed by setup.
    The YAML adds the last part that chapter 7 (install everything on the production servers) left out.
    Then commit and push.

    Run `every_server` on `util01` with part 1's command; the run applies the status-page settings,
    using the R2 key from the vault. A successful apply publishes the
    message "Everything is working." on the page.
    If the key cannot write the bucket, MMHotline refuses the
    `status_page` settings, and `util01`'s run fails.
    The run's summary contains MMHotline's reason.
    MMHotline keeps any earlier working settings for the failed part.
    On first setup, MMHotline has no earlier status-page settings to keep.

    ```yaml
    # mmhotline_settings.yml, in the systems repository
    status_page:
      page_title: Example Inc.
      host_name: "{{ .vars.status_page_host_name }}"
      r2_bucket_url: R2_BUCKET_URL           # as the set-up printed it
      r2_access_key_id: "{{ .secrets.mmhotline_status_page_r2_access_key_id }}"
      r2_secret_access_key: "{{ .secrets.mmhotline_status_page_r2_secret_access_key }}"
    ```

    **Tell the person:** no message, because step 14 shows the page.

    **Check:** the run passed, and `mmhotline settings show` on `util01`
    shows the `status_page` part applied.

13. **The systems desk can post while `util01` is down:** the person's
    own R2 key for the page's bucket is in the person's own token file on
    the desk, made in the same step as the page, as
    [post_to_the_status_page.md](../operating_procedures/post_to_the_status_page.md),
    "A person's own R2 key for posting from a systems desk", says.

    **Tell the person:** no message, because step 14 shows how the
    systems desk posts.

    **Check:** step 14's read from the systems desk.

14. **Check the page, a post, and a resolution,** once the host name's certificate is issued, a few minutes
    after the set-up. Then:
    - `curl -fsS https://status.example.com/` shows "Everything is
      working.";
    - before posting, the systems desk reads the page using the person's R2
      key. A successful read verifies the desk's bucket URL and R2
      credentials in the person's own token file. The person types, on
      the laptop, with a phone code:

      ```sh
      # On the laptop, in the person's own terminal:
      ssh -t desk01 mmhotline status-page show
      ```

    - a test notice from `util01`,
      `ssh -F ssh/config root@10.20.0.1 'mmhotline status-page post --json --message "This is a test of our status page. Nothing is wrong."'`,
      shows on the page with its time in UTC;
    - the systems desk resolves the test notice posted from `util01`, using
      the `notice_id` printed by the post command:

      ```sh
      # On the laptop, in the person's own terminal:
      ssh -t desk01 mmhotline status-page resolve --notice-id 1 --closing-message "The test is over."
      ```

      If resolving the test notice from the systems desk fails, resolve the
      test notice from `util01` at once. Customers must not see an open
      test. Run `mmhotline status-page resolve --notice-id 1 --closing-message "The test is over."`
      over `ssh -F ssh/config root@10.20.0.1`.
      Replace `1` with the `notice_id` printed by the post command.
      Fix the desk's key or settings before marking
      `status_page_for_customers` done.

    **Tell the person first,** before the test notice. The test notice
    stays on the public page under "Recently resolved" until five later
    notices push it off, and in the page's `status.json` for good:

    > Next, I post a test notice to your status page, then resolve it from your systems desk, the way you post while `util01` is down.
    > Customers can see the test under "Recently resolved" until five later notices push it off.

    **Ask the person:**

    > Please open https://status.example.com/. You see "Everything is working.", with the test notice under "Recently resolved".
    > Tell me when you see it.

    **Tell the person after,** which also ends the chapter. Name the
    checks that passed and any tests that still need a person or a date:

    > Your alerts reach your phone, your backups restore, and your status page works: [the checks that passed].
    > Still open: [the tests that need a person or a date].
    > Your status page is ready.

    **Check:** the page says "Everything is working." again, with the test under
    "Recently resolved". Mark `status_page_for_customers` done after
    setup, the settings apply, the public page check, the post from
    `util01`, and the desk's resolution of the test notice all pass.

## If something is different

- **The domain is still pending:** in the first sitting, part 4 needs
  nothing from the domain. In the alerts sitting, continue part 1, and
  tell the person when you check the domain next, as
  [Before you start](#before-you-start) says.
- **A settings part fails to apply** (steps 2 and 12): read the reason in
  the run's results, correct the cause, and rerun `every_server`, as step 2
  says.
- **A drill or a copy failed** (steps 8 and 9): a drill or a copy that
  failed starts again in each run of `every_server` until one passes: fix
  the cause, commit, push, and run `every_server` again.
- **Resolving the test notice from the systems desk fails** (step 14):
  resolve the test notice from `util01` at once, as step 14 says.

## Why the chapter works this way

**The button for the first run.** Why the button: `util01`'s helper runs only commits that MMHotline
trusts, and MMHotline learns its trusted signing keys from these
settings. Before the settings are applied, the helper refuses with "no
commit signing keys are applied".

**The Access policy, not a test email.** Reason: the policy is what Access enforces. Reading it takes seconds
and proves more than a 5-minute wait without an email.

**The restore drill measures the database only.** The restore drill measures database recovery time, not
the time to recover the whole site.

**The status page lives at Cloudflare.** The status page lives in the
team's Cloudflare account, so the page works while every server is down,
and the systems desk can post with the person's own R2 key while `util01`
is down.

Next, in the first sitting: [Chapter 9: Go live](09_go_live.md), once part 4's checks passed.
