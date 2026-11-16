# Chapter 7: Install everything on the production servers

**When:** after chapter 6 (create your three production servers: app,
database, and tools), and after steps 1 through 6 of chapter 5 (put your
site behind Cloudflare and lock your private pages).

**What this chapter does:** MMX sets up the servers from the systems
repository: the firewall, the private network between the servers,
Postgres, the app, and the tools on `util01`, with MMHotline's first
settings. The servers install their security updates and reboot for the
fixes that need a reboot. The first backup and the first restore drill
start by themselves.

**Who acts:** you, the coding agent, write the settings and run MMX from
this systems desk. The person gives the time zone and the names of the
people on call (step 1), adds `util01`'s deploy key at the Git host
(step 3), tests the shared root console password at one provider console
(step 4), opens the app (step 7), and runs the desk review in the person's
own terminal (step 9).

**Tell the person when the chapter starts:**

> Now MMX sets up the servers from your systems repository: the firewall, the private network between the servers, Postgres, your app, and the tools on `util01`.
> Later, I commit, push, and run MMX on `util01` for each change.
> `util01` is not set up yet, so your systems desk runs MMX for the first server setup.
> Plan for most of an hour, mostly for the servers' security updates.
> I tell you when each run starts and about how long it takes.

## Before you start

- **The messages to the person.** Each step says what to tell or ask the
  person, in quote blocks: "Tell the person first" before the step, "Ask
  the person" when the person must act or approve, "Tell the person while
  waiting" during a step that runs for minutes, and "Tell the person after"
  with the result and its link. Say each message when its step comes, in
  your own words, with the team's own names and links.
- **Commands that source the person's token file,** `~/.config/monkeymaxxing-stack/example_systems.env`,
  run only in the person's own desk terminal, as the secrets rule in
  [The rules](../AGENTS.md#the-rules) says.
- **Every MMX run in this chapter uses the systems desk's button,**
  `sudo -n -u servers-mmx run-mmx-on-the-servers`, until chapter 8 (check
  that alerts reach your phone and backups restore) applies the triage
  agent's settings. After that, run MMX on `util01` through the
  `./server_management_scripts/run_mmx_on_util01` helper
  ([the helper guide](../server_management_scripts/README.md#run-mmx-on-util01)).
  Use the systems desk for `util01`'s own
  reboot and the other exceptions in [the rules](../AGENTS.md#the-rules).
  [Why the chapter works this way](#why-the-chapter-works-this-way) says why.
- **How long the runs take.** The first run on each server installs the
  server's waiting security updates, which takes 3 to 7 minutes on Debian 13
  on a small server. App, jobs and load-balancer servers install theirs
  last, after they serve.
- **The link.** The person sees the servers' results on the app's page and,
  from chapter 8, on MMHotline's page.

## Part 1: MMHotline's first settings

1. **MMHotline's first settings:** edit the existing `mmhotline_settings.yml`
   in the systems repository. Keep chapter 5 (put your site behind Cloudflare and lock your private pages)'s `cloudflare_access` values.
   MMHotline starts in run 1 (prepare the utility server) and refuses to start without valid settings.
   Set `team_name` to the company's name from chapter 2 (set up your laptop and your systems desk).
   Replace the example administrator with the person, using the
   `sign_in_email_address` from the person's Access sign-in.

   **Tell the person first.** Say what the triage agent may do by itself,
   from the person's answer in chapter 6. The example below is the answer
   `routine_fixes`:

   > Next, I write MMHotline's first settings: who is on call, and what the triage agent may fix by itself.
   > With your answer from chapter 6, the triage agent makes only fixes that cannot lose data, such as restarting a failed service or freeing disk space, and reports each fix.
   > A fix that can cut off a server, a network, or a name waits for a person's approval, and so does anything that MMHotline cannot recognize.
   > Every start or stop of the database's failover program also waits for a person, because starting the wrong database server can bring back old data and lose newer changes.

   **Ask the person:**

   > To set up the alert schedule, I need your time zone and the people on call.
   > What is your time zone, and who goes on call? Give me each person's name and company email address.

   Put the person on call in `on_call_schedule`, with the agreed time zone
   and names. Set the rules for running the agent's playbooks and MMWatchdog's fleet hub on `util01` as the only alert
   source, as the YAML example below shows.

   `mmx_project_settings.yml` keeps only MMHotline's backup address,
   `backups.mmhotline_backup_replica_url` (chapter 4 (sign up for the outside services the Stack uses)).
   Every other MMHotline setting is in `mmhotline_settings.yml`.
   `mmhotline_settings.yml` is an MMX template.
   The `mmhotline` fleet stage renders the template onto `util01` as
   `/etc/mmhotline/mmhotline_settings.yml`.
   Each `.secrets.KEY` inserts the value of the named vault key.

   The template takes `web_url` from
   `util01_private_page_host_names` in `mmx_project_settings.yml`.
   The template takes `alert_intake_listen_address` from `util01`'s
   `private_ip` in `inventories/servers.yml`.
   `web_listen_address` stays at the loopback address shown below.

   The copied template holds the settings of every setup chapter. This
   chapter's file keeps only the parts in the YAML example below, which
   leaves `sending_services: {}` after `services_whose_changes_a_person_must_approve`.
   Leave out the `pushover` part of `sending_services` and the `triage_agent`,
   `mmhotline_down_alarm`, and `status_page` sections for now.
   Chapter 8 (check that alerts reach your phone and backups restore) adds
   these parts, and gives their complete text.
   To leave them out, make two cuts in the copied file. First, replace
   the `pushover:` entry under `sending_services:` with `sending_services: {}`.
   Second, delete everything from the comment line
   `# The triage agent: Claude Code or Codex` to the end of the file.
   Do not cut by top-level key: the `{{ if ... }}` and `{{ end }}` lines
   of the `triage_agent` section start at column 0, so a cut by key
   leaves an `{{ if }}` without its `{{ end }}` and the file does not
   render.
   A section absent from `mmhotline_settings.yml` needs no vault key, so
   the first run needs none of their keys.

   The YAML example below shows this chapter's settings with short notes.
   Keep `mmhotline_settings.yml`'s own comments when editing:

   ```yaml
   # mmhotline_settings.yml, in the systems repository: the parts this chapter needs
   team_name: Example Inc.                    # the company's name, from chapter 2 (set up your laptop and your systems desk)
   web_url: https://{{ .vars.util01_private_page_host_names.mmhotline }}
   web_listen_address: 127.0.0.1:8480         # where util01's tunnel reaches the pages
   alert_intake_listen_address: "{{ .vars.private_ip }}:8484"   # util01's WireGuard address: every server's MMWatchdog sends here
   cloudflare_access:                         # chapter 5 (put your site behind Cloudflare and lock your private pages)'s values
     team_domain: example.cloudflareaccess.com
     audience_tag: "0000000000000000000000000000000000000000000000000000000000000000"
   fleet_view_command: [/usr/local/bin/mmwatchdog, fleet, --json]
   people:
     - name: Ana Silva
       sign_in_email_address: ana@example.com
       role: administrator
   on_call_schedule:
     escalate_if_unclaimed_after_minutes: 5               # how long MMHotline waits for a claim before it reaches the next people
     schedule_type: weekly_rotation
     time_zone: Europe/Lisbon                 # the team's time zone
     handoff_weekday: 1                       # Monday
     handoff_hour: 9
     handoff_minute: 0
     first_start_date: "2026-11-02"           # the Monday that starts the first week: the initial setup's, or the one before
     rotation_sign_in_email_addresses: [ana@example.com]
     backup_option: everyone_available        # when nobody claims in time, everyone else who's available
   alert_sources:
     - alert_source_id: mmwatchdog_fleet_hub  # the ID that roles/util_server/files/alert_destinations.yml names
       name: MMWatchdog fleet hub on util01
       signing_secrets: ["{{ .secrets.mmhotline_signing_secret_of_the_fleet_hub }}"]
       warn_after_no_check_in_for_minutes: 2
       sos_after_no_check_in_for_minutes: 5
   rules_for_running_agent_playbooks:
     servers:                                 # the inventory's name: every inventory needs an entry
       preset: routine_fixes_without_permission
   services_whose_changes_a_person_must_approve: [pgautofailover.service]
   sending_services: {}
   ```

   - **`rules_for_running_agent_playbooks`:** the template writes this
     entry from the person's answer in chapter 6,
     `what_the_triage_agent_may_do_without_a_person` in
     `mmx_project_settings.yml`; never edit the entry by hand. The example
     above is the answer `routine_fixes`: the triage agent's routine
     fixes that cannot lose data, such as restarting a service that failed
     or freeing disk space, run at once, and the triage agent reports each
     fix. A fix that can cut off a server, a network, or a name, and
     anything MMHotline cannot recognize, waits for a person's approval.
     The answer `routine_fixes_and_server_work` adds four playbooks listed
     by name, which run without a person.
   - **`pgautofailover.service`** waits for a person whatever the rules for
     running the agent's playbooks say. The service name covers two programs: the keeper on each
     database server, and the failover monitor on `util01`.
     The keeper runs Postgres and follows the monitor's instructions.
     The failover monitor decides which database server is primary.
     [Why the chapter works this way](#why-the-chapter-works-this-way)
     says why a person starts and stops the two programs.
   - **The people:** put everyone who goes on call in `people` and in
     `rotation_sign_in_email_addresses`, so the first SOS after chapter 8 (check that alerts reach your phone and backups restore)
     reaches whoever's week it is.

   `mmhotline_settings.yml`'s comments say what each part does.
   `secrets usage` lists each vault key read by `mmhotline_settings.yml`
   beside the rendering task's line in `playbooks/every_server.yml`.
   The fleet stage `mmhotline` renders `mmhotline_settings.yml`.

   **Before run 1 (prepare the utility server):** `mmx validate` and `mmx explain every_server` must pass.
   Run the example-value search in
   [chapter 2 (set up your laptop and your systems desk)](02_set_up_the_laptop_and_the_systems_desk.md#check-remaining-example-values).
   Require only comments and usage examples in the result.
   Commit and push. Then
   `sudo -n -u servers-mmx run-mmx-on-the-servers secrets usage`, which
   reads the pushed commit and vault, must show no key `not defined` that a run needs.
   A key of a part that this system leaves off shows `not defined` and is
   not needed. For example, the uploads copy needs no keys when no app
   keeps uploads and `backups.uploads_backup_runs_on` is `[]`.

   **Tell the person after:**

   > Your alert schedule is set: [the first person] is on call first, and the next person takes over each Monday at 09:00, [the time zone] time.
   > If nobody claims an urgent alert within 5 minutes, MMHotline sends the alert to everyone else who is available.

   The 5 minutes are `on_call_schedule.escalate_if_unclaimed_after_minutes`
   (5 in the template).

   **Check:** `mmx validate` and `mmx explain every_server` pass, and
   `secrets usage` shows no key `not defined` that a run needs.

## Part 2: The first two MMX runs

2. **Run 1 (prepare the utility server),** the five fleet stages that prepare the utility server:

   ```sh
   # This systems desk, in the systems repository:
   sudo -n -u servers-mmx run-mmx-on-the-servers run every_server --connection ssh_only --only-fleet-stages install_jq_and_python3,every_server,util_server,read_the_mmwatchdog_fleet_hub_join_code,mmhotline
   ```

   `install_jq_and_python3` installs the two programs that the later stages
   run on each server. A fresh server may have neither: Debian 13's cloud
   image has no jq, and `util_server` fails without it.
   `every_server` sets every server up over WireGuard SSH, reuses the
   first-boot private keys, and adds each role's peers and the systems desk peers.
   `util_server` sets up `util01`, with MMWatchdog's fleet hub, and makes
   the utility server's two SSH keys. The SSH private keys stay on `util01`.
   Then the stage `mmhotline` restores MMHotline's database when its backup
   holds one, writes its settings file, and starts it, so the fleet hub's
   alerts have somewhere to go from the start. The remaining stages wait
   until run 2 (configure every server) installs the utility server's SSH keys and the Git host
   accepts `util01`'s deploy key.

   **Tell the person first:**

   > Next, the first MMX run prepares `util01`, the server that runs the system tools.
   > WireGuard already carries SSH from your systems desk to every server. MMX reuses each server's first-boot key and adds the private connections that each server's job needs. WireGuard encrypts the connections between the servers.

   **Tell the person while waiting:**

   > This run installs each server's waiting security updates first, which takes about 3 to 7 minutes.

   **Tell the person after:**

   > `util01` is ready, and MMHotline, your alert dashboard, runs on `util01`.
   > Before the second run, `util01` needs a key at your Git host.

   **Check:** run 1's summary shows every task passed.

3. **The public keys run 1 (prepare the utility server) made,** from
   `sudo -n -u servers-mmx run-mmx-on-the-servers results --node NAME --json`, each the
   `public_key` of a task:
   - **`util01`'s `mmhotline` user's key,** from
     `util_server/ssh_key_of_the_mmhotline_user` (fleet stage
     `util_server`): `util01` runs MMX with it, logs in to every server
     with it, and pushes to the Git host with it.
     Add the `mmhotline` user's public key to `root_ssh_public_keys` in
     `mmx_project_settings.yml`, with the comment `util01, the mmhotline user`.
     Ask the person to add the public key at the Git host as a deploy key
     on the systems repository. The person uses the repository's Settings,
     Deploy keys (at GitHub, `https://github.com/OWNER/REPOSITORY/settings/keys`),
     Add deploy key, with "Allow write access".
     Do not use `gh repo deploy-key add`, because a key added by `gh`
     disappears when the `gh` login is revoked.

     Register the `mmhotline` user's public key at the provider yourself,
     through the API proxy, `http://127.0.0.1:8081/`, as chapter 4
     registered the desk's production key. Use
     `util01_ssh_key_name_at_the_provider` as the registered name.
     Verify the registered key equals the utility key, so every new server
     and weekly `restore01` accepts the utility server's SSH login. The
     [provider guide](../provider_guides/) gives the provider's commands.

   - **The triage agent's key,** from `util_server/ssh_key_of_the_triage_agent`,
     as `triage_ssh_public_key`: it logs in as the read-only `triage` user.

   Commit and push.

   **Ask the person:**

   > `util01` pulls your systems repository and pushes its own changes to the repository, so `util01` needs a deploy key at your Git host.
   > Please open [the repository's deploy keys page] and select "Add deploy key". Paste this key: [the key]. Tick "Allow write access", then save.
   > You then see the key in the list of deploy keys. Tell me when you see it.

   **Tell the person after:** no message, because step 4 starts with the
   second run.

   **Check:** the Git host lists the deploy key with write access, and the
   key registered at the provider equals the utility key.

4. **Run 2 (configure every server):** repeat run 1 (prepare the utility server)'s `sudo -n -u servers-mmx run-mmx-on-the-servers run every_server --connection ssh_only`
   command without the `--only-fleet-stages` flag and the flag's stage list.
   Run 2 (configure every server) runs the whole `every_server` playbook.
   The `every_server` playbook preserves each server's WireGuard key
   and applies the recorded peer lists.
   Run 2 (configure every server) clones `util01`'s copy of the systems repository on
   `util01`. The coding agent runs later changes explicitly.
   Run 2 (configure every server) keeps MMHotline, which run 1 (prepare the utility server) started, installed and running.
   Verify a fresh SSH connection over wg0 from the systems desk to
   every server. The check of the firewall rules, the metadata block, and the
   refusal of direct desk connections to Postgres and MMX's HTTPS port is
   optional:
   [Check my system's protections](../operating_procedures/assess_a_running_system_and_recommend_changes.md#check-my-systems-protections).

   Run 2 (configure every server) sets up the database servers with the failover formation and the
   first full backup. The database setup also creates pgBackRest's stanza,
   the named settings for a database cluster, the cluster's backups, and
   the cluster's archived write-ahead log. One line in each database
   server's login rules, `pg_hba.conf`, looks unsafe and is not:
   [Why the chapter works this way](#why-the-chapter-works-this-way)
   explains the line.

   Run 2 (configure every server) joins every server to MMWatchdog's fleet hub and starts each app
   at the app's `deployed_image_tags` release, with migrations first.
   [The fleet stages](../playbooks/every_server.yml) give the full order.

   Near the end of run 2 (configure every server), the uploads copy starts if an app keeps uploads.
   Then `apply_the_mmhotline_settings` applies MMHotline's settings file
   again. If a settings part does not apply, run 2 (configure every server) fails with MMHotline's
   reason. From then on, `apply_the_mmhotline_settings` applies each change
   to `mmhotline_settings.yml`.
   At the end of run 2 (configure every server), the first restore drill starts in the background
   on `util01`. The restore drill waits for any running uploads copy to
   finish before restoring the database.

   **Tell the person first:**

   > Next, the second run installs `util01`'s SSH keys on every server, sets up the database, and starts your app and the system tools.
   > MMWatchdog, the program that watches every server, starts in this run. MMWatchdog checks your app's public address only from chapter 9, when your site goes live, so your app raises no alert before then.
   > Other alerts from the servers reach nobody yet. You see them on MMHotline's page in chapter 8, and from chapter 8 they can ring your phone.

   Do not call an unrelated failure an expected alert.

   **Tell the person while waiting:** the Stack's tests measured a whole
   `every_server` run at about 5 to 7 minutes (284 seconds until a new app
   server served, 397 seconds for the whole run).

   > The second run takes several minutes. I tell you when the run ends.

   **Ask the person,** once run 2 passed, to test the shared root console
   password at one provider console (the provider guide's "Console and rescue access" section, such as
   [Hetzner Cloud's](../provider_guides/hetzner_cloud.md#console-and-rescue-access)):

   > Please test the emergency way into your servers once: open `util01` in [the provider's web console, at the address in your provider guide's "The provider's web console"] and open its console.
   > Log in as `root` with the password manager item `Shared root console password`. You see a root prompt. That login is expected and changes nothing.
   > The console reaches the server without SSH, for the day SSH fails. Tell me whether the login worked.

   Record the result for `provider_console_and_backup_mmhotline_logins`.

   **Tell the person after:**

   > Your servers are set up. These services passed their checks: [the services].
   > The first backup and the first restore drill start by themselves. We read both results in chapter 8.

   **Check:** run 2's summary shows every task passed, and a fresh SSH
   connection over wg0 from the systems desk reaches every server.

5. **When a run fails,** its summary names the failed task. MMX hides the
   result of every node task that reads a secret, and of every one that
   starts after a role's node task used a secret on the server, so a
   failure there shows "details suppressed":
   read the reason on the server over SSH, such as
   `ssh -F ssh/config root@10.20.1.1 journalctl -u caddy`, or in the
   file that the failure names, which root reads, such as
   `ssh -F ssh/config root@10.20.0.1 'cat /run/mmx/private/JOB_ID-hidden-details-of-failed-node-tasks.txt'`.

   MMHotline's settings validation errors stay visible in the run output,
   under the `mmhotline` stage's task `write_the_mmhotline_settings`.
   MMX hides the settings file's differences but shows the check's message,
   with any secret value replaced by `[redacted]`.
   The `apply_the_mmhotline_settings` stage also shows each settings part
   that MMHotline failed to apply, with the reason, because the stage reads
   no secret.

   Fix the cause in the systems repository, commit, and run the failed
   command again.

   **Tell the person,** only when a run failed:

   > The run stopped at [the failed task] on [the server], because [the reason].
   > I fix the cause in your systems repository and run the run again.

   **Check:** the rerun of the failed command passes.

## Part 3: Reboot for the installed security fixes

6. **Apply the fixes that need a reboot, before going live.** Follow the
   systems repository's [update_and_restart_the_database_servers.md](../operating_procedures/update_and_restart_the_database_servers.md) and [reboot_servers_after_updates.md](../operating_procedures/reboot_servers_after_updates.md): the database servers first,
   then the other servers, then `util01` from this systems desk. The first restore
   drill takes `util01`'s lock: wait until the drill finishes before the
   reboot runs.

   **Tell the person first:**

   > Some of the installed security fixes, such as fixes to the kernel, take effect only after a server restarts.
   > No users use your system yet, so I restart the servers now, before your site goes live.
   > First, I wait for the first restore drill to finish.

   ```sh
   # This systems desk, in the systems repository; these runs execute on the systems desk,
   # because util01's helper refuses until chapter 8 applies the triage agent's settings:
   sudo -n -u servers-mmx run-mmx-on-the-servers run update_database_servers --connection ssh_only
   sudo -n -u servers-mmx run-mmx-on-the-servers run reboot_servers_after_updates --connection ssh_only
   ```

   Each run must pass before the next starts. The first command includes
   `db01`, which the second excludes.

   **Tell the person while waiting:** the restore drill took 3 to 5
   minutes at three providers in the Stack's tests. A cloud server came
   back from its reboot in under a minute, and the app was down for about
   20 seconds.

   > The restore drill takes a few minutes. Then each server restarts in turn, in about a minute each.

   Then reboot `util01` itself:

   ```sh
   # This systems desk, in the systems repository; this run executes on the systems desk:
   sudo -n -u servers-mmx run-mmx-on-the-servers run reboot_util01_after_updates --connection ssh_only
   ```

   `reboot_util01_after_updates` puts `util01` in MMWatchdog maintenance,
   which suppresses `util01`'s own alerts during the reboot.
   The hub-outage alerters can still send alerts: they already send a push
   alert to everyone in the Pushover group if `util01` stays down for more
   than two minutes.
   While another run holds `util01`'s lock, `reboot_util01_after_updates`
   stops before changing anything. Let the running job finish, pull the
   job's commits, and try `reboot_util01_after_updates` again.
   The two reboot playbooks change nothing on a server where no reboot is
   needed.

   **Tell the person first,** before `util01`'s reboot:

   > Next, `util01` restarts. The restart takes about a minute.
   > If `util01` stays down longer than two minutes, two other servers alert every phone in your Pushover group. That alert means `util01` did not come back.

   **Tell the person after:**

   > Every server has restarted with its security fixes, and passed its checks after the restart.

   **Check:** the runs passed their return-to-service checks before
   showing the app below.

## Part 4: See the app and record the results

7. **Show the person their app.** When the domain shows "Active", the
   person opens the app's public address in the laptop's browser. While the
   domain shows "Pending", show the person the answer of step 8's check
   through Caddy on `app001`; the person's browser cannot reach the
   servers' private network, and the person needs no port-forward.

   **Ask the person,** when the domain shows "Active":

   > Please open https://shop.example.com in your browser. You see your app's page.
   > Nobody is sent to your app yet, and no check watches the app. Chapter 9 checks the app from the internet and turns the checks on.
   > Tell me when you see the page.

   **Tell the person,** while the domain shows "Pending":

   > Your app runs on `app001`: here is its answer, [the answer of the check].
   > Your app's public address answers once Cloudflare shows your domain as "Active". Chapter 9 checks the app there and turns the checks on.

   **Check:** the person saw the app's page, or step 8's check answered.

8. **Mark the items run 2 (configure every server) proved,** each after its `verification`:
   `app001_db01_and_util01_created`, `production_ssh_keys_and_desk_phone_codes`,
   `journald_log_size_limits`, `automatic_security_updates`,
   `wireguard_network_and_firewall`, `postgres_under_pg_auto_failover`,
   `postgres_sends_backups_to_the_locked_bucket`,
   `secrets_in_the_vault_scoped_by_role`,
   `caddy_app_containers_and_the_first_deploy`, and each app item that
   the running containers prove.

   **Tell the person:** no message, because the checklist records the
   results, and chapter 10 shows them.

   **Check:** before the domain answers, check the app
   through Caddy on `app001`, which answers only for the app's host name:
   `ssh -F ssh/config root@10.20.1.1 "curl -fsS -H 'Host: shop.example.com' http://127.0.0.1/up"`.

## Part 5: Join the systems desk to monitoring

9. **Join the systems desk to monitoring.** After `util01` is configured, the
   person runs the full desk playbook from the person's desk repository:

   ```sh
   review-and-apply-the-systems-desk-settings
   ```

   **Ask the person:**

   > Next, MMWatchdog starts watching your systems desk too. Please run `review-and-apply-the-systems-desk-settings` in your own terminal, in your desk repository.
   > If the command shows changes, I explain each change before you type `yes`.
   > Tell me when the command has finished.

   Verify that `desk01` appears in the fleet (`sudo mmwatchdog fleet` on `util01`).
   The test of the desk's wrong-code alert is optional:
   [Check my system's protections](../operating_procedures/assess_a_running_system_and_recommend_changes.md#check-my-systems-protections).

   **Tell the person after:** no message, because the chapter's last
   message follows.

   **Check:** `sudo mmwatchdog fleet` on `util01` lists `desk01`.

## Part 6: The fuller system

10. **The fuller system,** when chapter 1 (pick your web address and start
    the team's password manager) recorded it, and `trigger` of
    `staging_server` and `second_app_server` in the checklist says so:
    follow [Add an app server](../operating_procedures/add_an_app_server.md)
    for `app002`, with "The second app server's test" at its end, then
    [Add staging01](../operating_procedures/add_staging01.md). The person
    approved both servers' prices in chapter 6 (create your three
    production servers: app, database, and tools). A check through a
    public host name, such as the second app server's test and the
    staging Access check, waits until the domain shows "Active", at the
    latest until chapter 9 (go live). The smallest system skips this step.

    **Tell the person:** no message here, because each of the two
    operating procedures has its own messages.

    **Check:** the checks of the two operating procedures.

**Tell the person when the chapter ends,** after step 9, or after step 10
with the fuller system:

> From now on, each change to a server goes the same way: I commit and push the change you approved, then run MMX on `util01` and check the result. Runs take turns.
> Pushing alone changes no server. Nobody changes a server by hand, because a later run can undo an unrecorded change.
> One limit for now: `db01` has no replica yet, so a failure of `db01` stops your site until a replacement database is ready.
> Next, in chapter 8, we check that alerts reach your phone and backups restore.

## If something is different

- **The domain still shows "Pending"** (step 7): the app's public address
  does not answer yet, so give step 7's second message.
- **A run fails** (steps 2, 4, and 6): follow step 5.
- **Another run holds `util01`'s lock** (step 6): step 6 says what to do.

## Why the chapter works this way

**The desk's button first.** Why: the helper runs only commits that MMHotline trusts, and MMHotline
learns which keys to trust from the triage agent's settings. Until a
run applies those settings, the helper refuses with "no commit signing
keys are applied", and the button is the way to make that run.

**Two runs.** Reason: WireGuard is ready at first boot, but `util01`'s SSH keys must
be registered before `util01` can operate every server and pull Git.

**A person starts and stops the failover programs.** A person may stop
the keeper or the monitor on purpose.
Starting a database server whose history split from the primary's can
let the server become primary at a later failover.
Making the split server primary loses every write since the split, as
[triage_agent_rules.md, "When to hand over"](../triage_agent_rules.md#when-to-hand-over) says. With `staging01`, its plain
Postgres stays off the list: it has no replica, so its restart can't
split the database's history.

**One line in each database server's login rules looks unsafe, and is
not.** You can see the line `hostssl all pgautofailover_monitor <util01's private address>/32 trust`
in `pg_hba.conf`, the file that says who may log in to Postgres.
pg_auto_failover adds the line by itself. The failover monitor on
`util01` uses the line to ask each database server whether Postgres is
healthy, so the monitor can promote a replica when the primary fails.
Here is what each word means:
- `hostssl` means the connection comes over the network and must use TLS.
- `all` and `pgautofailover_monitor` mean any database, for the one
  login `pgautofailover_monitor`, which pg_auto_failover made only for
  the monitor's health checks.
- `<util01's private address>/32` means exactly one address, the private
  WireGuard address of `util01`. No other address matches.
- `trust` means Postgres accepts the login without a password.

The line is safe because the line matches only `util01`. Postgres listens
only on the server's WireGuard address, and the firewall admits
Postgres connections only from the app servers, the database servers,
and `util01`, so no other machine reaches the line. MMX leaves the line
as pg_auto_failover wrote it. MMX changes only the `trust` lines of
initdb's six local login rules, which would let any account on the
server log in as the Postgres superuser.
Reason: without the line, the monitor cannot see a database server and
cannot fail over.

**No public checks yet.** The fleet hub does not check each app at the app's public host name
yet: `public_site_checks_run` in `mmx_project_settings.yml` stays
`false` until chapter 9 (go live), so no SOS can come from an app that
nobody has announced. Signing in to MMHotline in chapter 8 (check that alerts reach your phone and backups restore) requires MMHotline's own
host name to work through Cloudflare Access, after the domain is active.

**The reboots come now.** No users use the system yet, so the reboots
finish during chapter 7 (install everything on the production servers),
before going live.

**Every change is a commit and a run.** Runs take turns under a shared
lock. Nobody changes a server by hand, because an unrecorded change
leaves the saved settings out of date and a later run can undo the
change.

Next: [Chapter 8: Check that alerts reach your phone and backups restore](08_check_that_alerts_reach_your_phone_and_backups_restore.md).
