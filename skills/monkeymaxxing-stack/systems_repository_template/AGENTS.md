# Working in this systems repository

Read [Talking with the team](talking_with_the_team.md) before work, and
follow the writing rules in conversations, documentation, setup instructions,
and incident reports. `talking_with_the_team.md` holds the Plain English
rules, the technical terms, and example messages.

This repository is the company's whole production system: its servers,
settings, deploys, and fixes. Every coding agent reads `AGENTS.md` first:
the team's coding agent on a person's laptop, and the triage agent. MMHotline runs the triage agent on
`util01` when an alert arrives. The system follows the Monkeymaxxing Stack,
at the version that `stack_version` in `monkeymaxxing_stack_checklist.yml`
names.

## What this repository is

Read the [system summary and operating handover](README.md) for this
system's current servers, links, and tested protections. Update `README.md`
when an operation changes the servers, links, or tested protections. Use
the inventory and the checklist to check each claim.

`README.md` is what the person reads, so `README.md` holds no instruction
for a coding agent: each instruction belongs in this file, in
`triage_agent_rules.md`, or in an operating procedure. Keep the README's
next actions at most five, in order, each with its responsible person and
its date or starting event, or saying which detail is not agreed. Group
related work into one action, such as the optional checks of the
system's protections. Remove an action once the checklist records the
action's result. Reason: five actions keep the person's first step easy
to find, and the checklist holds every other open item.

A **pool** is the servers that share one job, such as the app servers.
`staging01` runs every role on one server, for testing the apps.

A **failover formation** is the production database servers managed
together by pg_auto_failover, which can promote a replica when the primary
fails. `staging01` runs Postgres without pg_auto_failover, so staging tests
the apps, not automatic database failover.

The servers talk over one WireGuard network. A temporary restore server
peers only with `util01`, including SSH during the restore. A new database
server that `restore_database` restores after every database server is lost
also admits SSH from the systems desks, so the desk that keeps access can
run the restore during a lock-out.

Three tools apply the settings, watch the servers, and reach the team:
**MMX** applies this repository to the servers. **MMWatchdog** watches
every server and alerts, with MMWatchdog's fleet hub on `util01`; systemd restarts
a service that crashed.
**MMHotline**, on `util01`, receives the alerts, reaches the person on
call, runs the triage agent, and serves the dashboard behind Cloudflare
Access.

| Path | What the path holds |
| --- | --- |
| `README.md` | The first page, what the Monkeymaxxing Stack builds, with this system's servers; then the operating links, failure behavior, and the person's next actions |
| `talking_with_the_team.md` | The Plain English rules, how to talk with the team before, during, and after a step, example messages, and the technical terms |
| `AGENTS.md` | This file: the rules for every coding agent, and which operating procedure to follow when |
| `triage_agent_rules.md` | The triage agent's rules, which it reads in full |
| `initial_setup/` | The setup chapters, done once in order: chapters 1 to 9 are the first sitting, which puts the app live. Alerts, the triage agent, the status page and chapter 10 come in later sittings. The `initial_setup/` files record how the system was set up |
| `operating_procedures/` | One file per operating procedure: its steps and its verification, upgrading to a new stack version and assessing the running system included |
| `CLAUDE.md` | One line, `@AGENTS.md`, so Claude Code reads `AGENTS.md` |
| `monkeymaxxing_stack_checklist.yml` | Every item of the stack: done, open, or deviated, and why; and, in their own section, the growth and improvement items with their triggers |
| `mmx_project_settings.yml` | MMX's project settings, the apps, the people's SSH keys, and the pinned versions of the downloaded programs (`stack_software`) |
| `mmhotline_settings.yml` | MMHotline's settings: its people, who is on call, the alert sources, the rules for running the agent's playbooks, the triage agent, the sending services, the MMHotline-down alarm, and the status page. The sending services, such as Pushover, deliver MMHotline's alerts to people's contact methods. The file `mmhotline_settings.yml` is an MMX template. The run on `util01` renders `mmhotline_settings.yml` with vault secrets as `/etc/mmhotline/mmhotline_settings.yml`, then applies the rendered settings |
| `server_management_scripts/` | The helper that runs MMX on `util01`, provider scripts written by the coding agent, and server first-boot data |
| `provider_guides/` | Provider notes for writing the team's provider scripts, with the provider's command-line tool or the guide's request function |
| `inventories/servers.yml` | Every server, its pool and the pool's flag (such as `is_app_server`), its addresses, and its WireGuard public key; each pool's address block; which pools connect to which (`connections_between_server_pools`); the deployed image tags |
| `playbooks/` | `every_server.yml`, which brings every server to what this repository says, MMHotline included. A fleet stage is a playbook section that selects servers and runs tasks, including role calls. The fleet stage `mmhotline` sets up MMHotline. The folder also holds the playbooks for operating procedures that need a particular order |
| `roles/` | `every_server`, `app_server`, `tunnel_connector_and_caddy`, `database_server`, `util_server`, `uploads_backup`, `mmwatchdog_joined_node`, `jobs_server`, and `pgbouncer`. The role details below explain the later roles and the template locations |
| `mmwatchdog_checks/` | MMWatchdog's checks for each check group, with limits that MMX fills in from the inventory |
| `files_used_by_several_roles/` | Files that more than one role or playbook uses. The shared files are listed below |
| `one_time_playbooks/` | Dated one-off fixes; `completed/` holds the finished ones |
| `triage_agent_notes/` | The triage agent's notes, one file per triage session, with a section for each cause, and `open_software_findings.md`, the scheduled software review's notes of the open findings and the flaws with no fix yet, which says "No open findings." on a new system |
| `software_outside_the_distribution.yml` | Every program that doesn't come from the distribution |
| `scheduled_software_review_task.md` | The task of the scheduled software review, which is off until the team turns it on: what the triage agent checks, in which order, and the one report each review sends at most |
| `secrets_vault.age` | The MMX vault: every secret the servers use, encrypted |
| `ssh/known_hosts`, `ssh/config` | The servers' SSH host keys, and the SSH settings for MMX, util01, and the triage agent |

`everyone_locked_out` shares server admission between normal runs and the lock-out button.
`systems_desk_lockout` is the lock-out's small part on a desk: it installs the Cloudflare Access session revocation.
`lock_everyone_out` reaches no other desk. The other desks lose admission at the servers.

The roles include two later additions: `jobs_server` starts work when
[Add jobs servers](operating_procedures/add_jobs_servers.md) adds servers to
`jobs_servers`. The `pgbouncer` role starts work when
[Add PgBouncer](operating_procedures/add_pgbouncer.md) turns on
`pgbouncer_runs_in_front_of_postgres`.

The `uploads_backup` role copies the apps' uploaded files from R2 to B2
while an app keeps uploaded files. Each role's templates are in the role's
own `files/` directory. For example, the Caddy template lists the apps'
web containers and where to send requests. The WireGuard template holds
the private network settings.

`files_used_by_several_roles/` holds:

- Cloudflare's apt signing key.
- pgBackRest's settings, shared by the backups and restores.
- The apps' env files, the background-job container template, and the
  weekly image cleanup, shared by the app servers and jobs servers.
- MMHotline's backup settings, used by the fleet stage `mmhotline`.

`.mmx/`, which Git ignores, holds MMX's run history on each machine.

### Your login on the desk

You are the team's coding agent, on the person's laptop. There is no coding
agent on the desk. Each person has a systems desk, such as `desk01`: a small
server that is a locked key box. The desk holds the production private key,
the vault passphrase, and the person's provider and Cloudflare tokens. You use
them through the desk, and you can never copy them. The laptop reaches only
the person's desk, through doubleshell and WireGuard.

You reach the desk through one SSH entry on the laptop, `desk01-agent`, as the
desk's `coding-agent` user. The entry keeps one shared connection open, so one
phone code opens a working session, and every later command reuses the
connection. The desk closes the connection after one hour unused
(`coding_agent_login_idle_minutes` in `mmx_project_settings.yml`) and after ten
hours at most (`coding_agent_login_longest_hours`). Both are settings, with
their reasons beside them.

Run a request to a public address, such as an app's health URL at its public host name, on
the laptop, not on the desk. Reason: the desk works with the servers over WireGuard, and the
laptop's request shows what the app's users see.

When the connection is closed, `ssh -O check desk01-agent` says so. Ask the
person for one code in the chat, in one short message:

```text
I need one code from your phone to work on your desk.

Type the 6 digits here.
```

When the person just typed a code for something else, add the line
`WAIT FOR A NEW CODE.  The code you just typed works only once.`, in bold
capitals, before the last line. Then open the connection with the code:

```sh
# On the laptop. CODE: the 6 digits the person typed.
code_script=$(mktemp) && printf '#!/bin/sh\necho %s\n' CODE > "$code_script" && chmod 700 "$code_script"
SSH_ASKPASS="$code_script" SSH_ASKPASS_REQUIRE=force ssh desk01-agent true < /dev/null
rm -f "$code_script"
```

A code works once and for 30 seconds, so a refused code needs a new one.
Five wrong codes within ten minutes lock the laptop out for five minutes
(`phone_code_lockout` in `mmx_project_settings.yml`).

Every command block in this repository that says "This systems desk, as the
coding agent" runs through that connection: `ssh desk01-agent 'COMMAND'`,
from the laptop. The desk's checkout of the systems repository is
`/home/coding-agent/systems_repository`, `systems_repository` from your
login, and the servers' SSH settings work from there. For example, to
inspect `app001`:
`ssh desk01-agent 'cd systems_repository && ssh -F ssh/config root@10.20.1.1 uptime'`.
The desk uses `/run/desk-ssh-agent/socket` for production SSH and for pushes to the main copy.
Reach a service that listens only on a server's loopback address through an
SSH port forward on the desk, such as
`ssh -F ssh/config -L 8480:127.0.0.1:8480 root@10.20.0.1` for MMHotline's
pages on `util01`.
The desk uses kernel `wg0`; no doubleshell inventory connection is required on
the desk. Production servers peer with systems desks, including when `util01`
is lost. Only the desk knows the laptop's keys and address.

The person logs in to the desk only for a few things, each one short command
on the laptop plus one phone code: `ssh desk01-secrets` for a new secret,
`ssh desk01-review` for a change to the desk itself, and the lock-out
button, `ssh -t desk01 sudo lock-everyone-out`.

The desk's WireGuard peers for the servers follow pushed `main` through `sudo -n update-this-desks-wireguard-peers`,
which takes no arguments and needs nothing from the person. Run it after you push a change that adds, replaces or
removes a server, at the start of each session, and whenever SSH to a server times out. It prints each peer it added,
changed or removed. When it refuses a server's value, correct the inventory and push; never edit `wg0` by hand.
At the start of a session, first pull, then run `sudo -n update-this-desks-wireguard-peers`.
Reason: the command takes the servers' keys and addresses from pushed `main`.

Your direct MMX button, on the desk, is `sudo -n -u servers-mmx run-mmx-on-the-servers`.
The button works from its own execution checkout at the **pushed `main` commit**, as your desk checkout last
fetched it from the main copy on `util01` (`origin/main`), or your desk checkout's own `main` before `util01`
exists. So run `git pull --ff-only` in the desk checkout before the button, and before
`sudo -n update-this-desks-wireguard-peers`, which reads pushed `main` the same way.
The button never sees uncommitted or unpushed edits.
Production and staging are in scope. The desk itself is outside the button's scope.
Provider API calls use `http://127.0.0.1:8081/`; Cloudflare calls use `http://127.0.0.1:8082/`.
The API proxy adds the person's token on both ports; for a provider whose API needs each request signed or a token made
from a key, such as OVHcloud, AWS or Google Cloud, it signs the request on `8081` instead. Never read the person's token files.

The person manages the desk with one command on the laptop, plus a phone
code:

```sh
ssh desk01-review
```

`ssh desk01-review` runs `review-and-apply-the-systems-desk-settings` on the
desk, as the person.

The command runs `playbooks/systems_desk.yml` as root. It first compares what the desk playbook would do
with the person's last desk review: unchanged, it runs at once; changed, it shows the changes
and runs only after the person types `yes`. The record of the reviewed run is root-only on the desk.
You cannot answer the question, and you never ask the person to answer it without reading the changes.
The setup recorded the first desk review itself. For each later review, give the person a short plain
summary of what changes and why, before the person types `yes`.
When your pushed change touches the desk playbook, tell the person which change the desk review will show,
and explain each change before the person types `yes`.
Reason: the desk playbook applies pushed `main` as root, beside the person's production key, phone-code secret
and tokens, so the person reviews each change to it. The desk's root-owned loopback key must never enter
the coding agent's socket.
The same holds for the lock-out button, `sudo lock-everyone-out`: it runs the copies of the lock-out
programs that the last desk review installed, so tell the person when your pushed change touches
`playbooks/lock_everyone_out.yml`, the `everyone_locked_out`, `systems_desk_lockout` or
`work_out_who_this_server_talks_to` roles,
`server_management_scripts/start_break_in_lockout.py`, `ssh/`, `roles/every_server/files/wireguard_wg0.conf`,
`roles/every_server/files/sudoers_triage`, `roles/util_server/files/sudoers_triage_mmwatchdog_fleet_readings`,
or `mmhotline_settings.yml`, and that it reaches the button only after the next desk review.

## The rules

- **Check every change against the goal.** The goal: a person who is new to
  running servers runs a production system with a coding agent, with the
  site live, alerts reaching the phone, and backups proven to restore, and
  is confident that the system works and understands how. A change to a
  setup chapter, the checklist, or an operating procedure must meet three
  rules. First, the agent and the APIs do the work, and the person decides
  and watches: the person's part is the smallest and safest part, and the
  person gets a link to see each result. Second, a step checks what is
  specific to this team, and the Stack's own tests prove the Stack's
  software. Third, each default fits a team of one or two people, and a
  stronger option is a setting a team can turn on, never a requirement.
  The full text is "The goal" in the Stack repository's
  `docs/acceptance.md`.
  Reason: a setup that feels hard sends people to a system they build
  themselves, full of holes.
- **Everything is a commit.** Settings, deploys, fixes, and scaling are
  commits to this repository, and an MMX run applies them. The Git log is
  the system's history, so each commit message says what changed and why.
- **The coding agent applies each change.** Edit, validate locally, commit,
  synchronize, push, preview the pushed commit, then run MMX on `util01`. A push alone changes no server. Use
  `every_server` for configuration and `deploy` for a release. Run
  `every_server` first when a deploy needs new settings.

  The helper `./server_management_scripts/run_mmx_on_util01` takes MMX
  arguments, runs exactly the desk's clean pushed `main` commit, and
  holds `/var/lib/mmhotline/systems_repository.lock`. When the triage
  agent or a playbook pushed a commit since your last pull, the helper
  refuses with "HEAD must equal pushed main": run `git pull --rebase`
  (step 3 of [Making a change](#making-a-change)), then run the helper again. The scheduled server
  settings comparison and restore drill use the same lock.

  MMHotline trusts every commit on `main` in the main copy
  (`trusted_commits: every_commit_on_origin` in `mmhotline_settings.yml`).
  Commits are not signed, and no commit waits for review. Reason: only
  the keys in `root_ssh_public_keys` can push to the main copy, and those
  keys already log in as root on every server, so a signature would
  protect nothing more. Never add a Git host as `origin` of the main copy
  or let anyone else push there. MMHotline checks `main` before each of its
  runs, the helper's runs and `util01`'s scheduled jobs, and moves its copy
  forward to the tip of `main`.

  While MMHotline does not answer, such as while it is stopped, the helper
  refuses every run and dryrun and says so; nothing ran. While the helper
  waits for the lock, it says every minute
  who holds the lock, how long it has waited, and how to stop that run
  ([the helper guide](server_management_scripts/README.md#run-mmx-on-util01)).

  MMX keeps 30 days of history by default (`run_history_retention` in
  `mmx_project_settings.yml`) in `.mmx/` on `util01`. Read results with
  `./server_management_scripts/run_mmx_on_util01 results`. Reading results, a run's status, or stopping a run takes
  no lock, because a run in progress holds the lock. Failed work needs investigation and
  an agent-run retry.

  Run `mmx validate` locally for uncommitted structural checks.
  Use `sudo -n -u servers-mmx run-mmx-on-the-servers` on the desk for direct production commands,
  including previews, production playbooks, initial production setup, recovery,
  a changed vault passphrase, and `util01`'s reboot. Push before using the button.
  MMX refuses a preview or run on a server where another MMX job is running; the desk's button does not wait for `util01`'s lock. Run the button only when no run holds `util01`'s lock (the helper names the holder). If a deploy still switches a live port in between, the `app_server` role stops with "the live port changed" before it changes anything. The person enters
  secrets with `set-up-outside-services` on the desk, which commits and pushes the vault. You never read the person's files.
  Do not edit the vault through `run-mmx-on-the-servers secrets`: the next button invocation resets its execution checkout.

  Reason: one controller keeps run history together. The matching commit
  prevents a helper run from applying files the agent did not review.
- **Only a person starts or undoes a lock-out.** Follow [Respond to a break-in](operating_procedures/respond_to_a_break_in.md).
  First find out with the person how the intruder got in. Recommend a lock-out only in the cases that
  [The lock-out: only for these cases](operating_procedures/respond_to_a_break_in.md#the-lock-out-only-for-these-cases) names:
  `util01` or the triage agent is suspect, an unknown root login, process or MMX run is on the servers, or a desk or a
  kept credential is suspect and nobody knows which. In every other case, such as a break-in through the app, the
  lock-out harms more than it helps, because the lock-out cuts off the people and agents that the team needs.
  When the person asks for a lock-out, prepare and push the one-line commit `everyone_locked_out_except_desk: DESK`
  under the top-level `vars` of `inventories/servers.yml`, with the person's desk, then give the person the command
  `ssh -t desk01 sudo lock-everyone-out`, the lock-out button, to type on the laptop with a phone code. To undo it, push the commit
  that removes the line, and give the person the same command. The lock-out button runs the lock-out
  programs that the person's last desk review installed, never pushed `main`'s, so a change you
  push to the lock-out reaches the lock-out button only after the person reviews it in a desk review.
  While `everyone_locked_out_except_desk` is set, you keep working on the desk that keeps access and run MMX with your button,
  `sudo -n -u servers-mmx run-mmx-on-the-servers run PLAYBOOK --connection ssh_only`.
  Reason: `util01` and every other desk have lost admission at the servers, and MMX's HTTPS service is stopped on every server.
  `every_server` refuses to start or undo a lock-out that the lock-out button did not make on the desk that runs it, and
  refuses a lock-out whose desk, `private_ip`, `wireguard_public_key` or `production_ssh_public_key` in the inventory differs
  from what the button recorded at the press, so never try to apply `everyone_locked_out_except_desk`, or change those
  values of the desk that keeps access, yourself: the person presses the button again for such a change.
- **Never change a server by hand.** Reading over SSH is fine. Every change
  goes through MMX, so any server can be rebuilt from this repository.
  Starting a scheduled job now, such as the restore drill or the uploads
  copy, and powering a server off for a test are actions, not changes.
  The operating procedures perform the scheduled-job starts and test
  power-offs over SSH. The person's own commands on a systems desk in setup
  and recovery (`set-up-outside-services`, the phone code, restored keys)
  are the other exception; each procedure names them.

  Start the restore drill over SSH because `./server_management_scripts/run_mmx_on_util01 run-command` would
  make the drill wait forever. `./server_management_scripts/run_mmx_on_util01 run-command` holds `util01`'s
  lock while waiting for the drill to finish. But the restore drill needs
  `util01`'s lock before the drill can start. So `./server_management_scripts/run_mmx_on_util01 run-command` and
  the restore drill cannot finish.

  When an incident leaves no other way, such as stopping a service that
  does harm until its server is replaced, first put the server in
  MMWatchdog maintenance with a reason, on the server:
  `mmwatchdog maintenance on --every-check-group --for 24h --reason "pgautofailover stopped by hand: db02 is being replaced"`.
  During maintenance, the server's alerts wait, so the triage agent gets
  no alert from the server and does not undo the change.
  `mmwatchdog maintenance off --every-check-group` ends the maintenance.
- **Servers are replaced, never upgraded in place.** A bigger size, moving
  from VPS to dedicated, a new Debian release, and failed hardware are all
  "Replace a server". One replacement procedure avoids improvised work on
  a live system. Never upgrade a server's Debian release in place by
  changing apt's sources and running a full upgrade.
  A failed drive on a dedicated database server is also "Replace a server".
  The surviving mirrored drive keeps the database running while a
  replacement server is prepared.
- **Every configured production secret lives in the vault,** `secrets_vault.age`,
  MMHotline's included: never in another file of this repository, a commit
  message, an image, or a log. The person types each secret once, at a hidden
  prompt of `set-up-outside-services` on the desk, never in the chat. In the
  first sitting, `ssh desk01-setup` asks for each key a website gives and makes
  every random key itself
  ([chapter 4 (set up your accounts and lock your desk)](initial_setup/04_set_up_your_accounts_and_lock_your_desk.md)).
  Later, give the person `ssh desk01-secrets`: it asks for each key the vault
  still lacks, at a hidden prompt, makes the random ones, and commits and
  pushes the vault. To enter one key again, such as for a rotation, give the
  person `ssh -t desk01 set-up-outside-services secrets --replace KEY`.
  [Secrets in chapter 3](initial_setup/03_make_your_server_account_and_your_systems_desk.md#secrets)
  lists every secret and where it lives.

  You never open or print the vault's contents: no
  `mmx secrets edit`, no playbook or `run-command` that prints a secret,
  and no reading of a rendered secret file on a server, such as an app's
  env file in `/etc/<app>/`. To learn which keys exist or are missing, run
  `secrets list-keys` and `secrets usage` through your button, which holds
  the vault passphrase and shows key names only:
  `ssh desk01-agent sudo -n -u servers-mmx run-mmx-on-the-servers secrets usage`.
  The button reads pushed `main`, so push the files that read a new key
  before the check. `secrets usage` exits 1 while any key is `not defined`,
  and it lists the keys of parts this system leaves off too, such as
  `staging_` keys without `staging01`: read the list, not the exit code.
  Reason: your provider stores the conversation, so a secret you read
  leaves the team's control. An app secret's key is the app's name and the
  variable's name, such as `shop_SECRET_KEY_BASE`. A person's own tokens,
  such as their provider and Cloudflare API tokens, live only on the
  person's desk, in files only the API proxy and the person read. The
  recovery bundle, `recovery_bundle.age`, holds every item a lost desk
  needs, encrypted with the recovery passphrase in the team's password
  manager. Logins to the provider, Cloudflare, and B2 live in the team's
  password manager, along with **break-glass access**, the emergency ways
  in when the usual ways fail. The checklist item
  `provider_console_and_backup_mmhotline_logins` lists the emergency ways
  in.
- **MMHotline owns triage approval and execution.** MMHotline runs `mmx`
  at the judged commit in `/var/lib/mmhotline/systems_repository`, using
  `/var/lib/mmhotline/systems_repository.lock`. The helper and
  timers use the shared copy and lock too. MMHotline commits no run output.

  Before every MMX run, MMHotline moves its copy to the tip of `main`
  in the main copy. After a run ends, the request's page in MMHotline
  shows the run output. MMHotline pushes the triage agent's commits to
  `main` only when they change nothing outside `one_time_playbooks/` and
  `triage_agent_notes/`; a commit of the agent's that changes anything
  else is not pushed and waits for a person.

  Reason: the triage agent reads untrusted logs. The push limit prevents
  a log instruction from becoming a server-setting change on `main`.
  The triage agent cannot push to the main copy itself: the copy is root-owned,
  mode 0700. Reason: MMHotline trusts every commit on `main`, so a push by the
  agent would skip the push limit above.
- **What the triage agent may do without a person** is the team's one
  answer, `what_the_triage_agent_may_do_without_a_person` in
  `mmx_project_settings.yml` (the triage agent's sitting asks it): `every_fix_waits_for_a_person`,
  `routine_fixes`, or `routine_fixes_and_server_work`. With the third,
  the triage agent replaces a failed server of the pools that
  `triage_agent_server_work` lists, with `replace_failed_servers` (the
  playbook's own refusals decide each time, not a rule of the agent's),
  `every_server` and `destroy_replaced_servers`, and, after MMHotline's
  warning, reboots servers for installed updates and adds and removes app
  servers with the load, inside `growth_limits.app_servers`
  (`add_an_app_server_for_the_load`, and `remove_server` without
  `server_name`), with no person; with the other two, one approval covers
  the three replacement runs, and a person adds and removes app servers.
  Database servers and `util01` always need a person. With every answer,
  while `replace_failed_servers` runs, the site's SOS waits up to
  `triage_agent_server_work.sos_waits_for_a_server_replacement_minutes`
  (7) before it wakes the person on call, and wakes at once when a run
  fails; the triage agent's progress reports are info, and MMHotline's
  resolved message ends the night.
  `replace_failed_servers`, `destroy_replaced_servers`,
  `add_an_app_server_for_the_load` and `remove_server` without
  `server_name` commit to `main` themselves, as `util01`'s
  `mmhotline` user (`git log --grep '^Server-pool: '` lists them): pull
  before your next run. To change the answer, edit that one line when the
  person asks, commit, and run `every_server`; MMHotline's rules, the
  reboot check and `util01`'s two load checks follow it.
- **CI is the recommended way to test, build, and push the app image.**
  CI builds on a clean machine, and no password that can publish an image
  sits on the desk. The ready file is
  `files_for_your_app/test_build_and_push_the_app_image.yml` (GitHub
  Actions). CI needs no server SSH key or vault passphrase; it logs in to
  the registry with a short-lived or publish-only token. You work on the
  app in the app's folder on the laptop, show the person each change, and
  push it with the person's own Git login after the person approves. Then
  you record the image tag in the systems repository, commit, push, and run
  `deploy`.
- **Run the app's install, test and build commands only inside a
  container on the laptop.** Run them with `podman` or `docker`, mounting
  only the app's folder, such as
  `podman run --rm -v "$PWD":/app -w /app IMAGE npm test`. Never run them
  on the desk. Reason: those commands run code from the app's packages, and
  a poisoned package on the laptop could use your open desk login, as
  [chapter 2](initial_setup/02_get_your_app_ready_to_deploy.md#before-you-start)
  says.
- **A server's name never changes, and "primary" is a state.** After a
  failover, `db02` may be the primary and `db01` a replica; nothing is
  renamed.
- **One home for each kind of thing:** code and settings in Git, data in
  Postgres, uploaded files in R2, backups in B2, secrets in the vault, and
  the record of who may get in, in Cloudflare Access, the systems repository (SSH keys and systems desk
  WireGuard keys), and the password manager. An app server keeps nothing on the app server's own disk:
  every web and job container has a read-only file system, so an app that
  writes a file to its own disk fails at once, on `staging01` or, without
  `staging01`, at the production deploy, not silently at the next deploy. An app lists scratch directories it needs in its
  `writable_temporary_directories`; they are memory-backed and emptied at
  every start. Every container also runs in its own user namespace
  (`UserNS=auto`): root inside it is an unprivileged user on the server that
  owns no file, so a file an app reads from a mounted directory must be
  readable by anyone.
- **Production data stays on the production servers.** Never copy
  production's database, or a part of it, to a laptop, `staging01`, or
  CI, even with the personal data removed. The Stack's own copies stay as
  they are: uploaded files in R2, backups in B2, and the temporary
  `restore01` during a restore drill or a recovery. A laptop and
  `staging01` get invented test data from the app's seed command
  ([chapter 2 (get your app ready to deploy)](initial_setup/02_get_your_app_ready_to_deploy.md#chapter-2-get-your-app-ready-to-deploy)
  says how to write it). When a bug needs particular records, such as an
  account with no orders, add invented records like them to the seed
  command or to a test, and add a test that checks the bug stays fixed.
  To investigate production, run read-only queries on the production
  servers and keep the results there.
  Reason: any program that runs as the developer, such as a poisoned
  package, can copy what a laptop holds, and a laptop's backups go to a backup
  company. A coding agent on a laptop can send what it reads to the
  company that runs the agent's AI model. Staging gets less care than
  production. A script that removes personal data from a copy can miss a
  new column that holds personal data, and the missed column then leaks
  without anyone noticing.
- **Follow the stack; ask only for facts.** Every design decision is made,
  with its reason on record. Ask a person only for facts, such as a
  credential or a domain. A different choice is a deviation, recorded in
  the checklist with its reason.

### Making a change

Use one branch, `main`, including when the team has only one person.
Pushed means ready to run: a run applies everything on `main`.
Reason: every desk must agree which settings the next run applies.

You edit on the laptop, in your clone of the desk's repository,
`~/code/example_systems`, cloned with
`git clone desk01-agent:systems_repository`. The desk publishes
each change, because only the desk holds the production key that lets a push into the main copy.

1. Bring the clone up to date: `git pull --ff-only` from the desk. Edit the
   required files. Run `mmx validate` to check the local structure. Review
   the diff.
2. Stage only the intended paths with `git add PATH`, then commit on a
   branch named for the change, such as `add-app002`:
   `git switch -c add-app002 && git commit -m "Describe the change and reason"`.
3. Push the branch to the desk: `git push origin add-app002`.
4. Publish the branch on the desk:

   ```sh
   # On the laptop:
   ssh desk01-agent publish-branch-to-main add-app002
   ```

   `publish-branch-to-main` rebases the branch onto `main` on the desk,
   moves `main` forward, pushes `main`
   to the team's main copy on `util01`, and deletes the branch. Before
   `util01` exists, `main` on the desk is the main copy, and nothing is
   pushed. It prints the commits that
   arrived at `main` from elsewhere, if any. Show the person any incoming
   commits before running MMX. Say nothing when no commits arrived. On a
   conflict, `publish-branch-to-main` changes nothing and names the
   files: tell the person which files conflicted. Never resolve a conflict
   yourself. Stop before running MMX. Then `git switch main && git pull --ff-only`
   in the clone, and delete the local branch.
5. For configuration, preview the pushed commit with
   `ssh desk01-agent sudo -n -u servers-mmx run-mmx-on-the-servers dryrun every_server --connection ssh_only` while `util01` runs nothing.
   Exit 0 means no change; 2 means proposed changes; 3 means incomplete preview;
   1 means failed work; 4 means command error. Until the first restore drill has passed,
   every preview exits 2 for `start_the_restore_drill_in_the_background` alone. An MMX
   message "size or SHA-256 mismatch" for a pin whose SHA-256 is all zeros means the
   template came from a Stack checkout that is not a release: copy the pins from a
   released Stack version. Read each unchecked task's reason.
   Proceed only when each unchecked task depends on an earlier task in the planned run.
6. Run the procedure on `util01`, for example
   `ssh desk01-agent 'cd systems_repository && git pull --ff-only && ./server_management_scripts/run_mmx_on_util01 run every_server'`.
   Before `util01` exists or while `util01` is broken, use
   `ssh desk01-agent sudo -n -u servers-mmx run-mmx-on-the-servers run every_server --connection ssh_only`.
   Read the result before verifying the outcome.
   Reason: a push records settings; the explicit run applies settings.
   A documentation-only commit needs no server run.
7. Verify the procedure's result. Update the checklist and README when the operation changes links, duties, or tested protections.
   Commit the results, and publish them with steps 2 to 4. Report the outcome using [Talking with the team](talking_with_the_team.md).

**A run longer than a few minutes is a desk job,** so the laptop may sleep
and the connection may close without stopping the run. Start the run with
`systemd-run --user`, with a log file and an exit file named after the run:

```sh
# On the laptop. NAME: the run's name, such as every-server-2026-11-17-1405.
ssh desk01-agent 'mkdir -p ~/runs && systemd-run --user --unit=NAME --collect bash -c "cd ~/systems_repository && sudo -n -u servers-mmx run-mmx-on-the-servers run every_server --connection ssh_only > ~/runs/NAME.log 2>&1; echo \$? > ~/runs/NAME.exit"'
```

A desk job does not get the two values sshd sets for your logins, because
`systemd-run --user` starts it in your own systemd, not in the login. A
job that pushes with Git, such as a `git push` from your checkout, passes
both, right after `systemd-run --user`
(`publish-branch-to-main` sets them itself):
`-E SSH_AUTH_SOCK=/run/desk-ssh-agent/socket -E GIT_CONFIG_SYSTEM=/etc/systems-desk/coding-agent-gitconfig`.
Without them, Git cannot reach the main copy on `util01`.

Read `~/runs/NAME.log` for progress. The run is over when
`~/runs/NAME.exit` exists, and the file holds the run's exit code. After a
closed connection, ask the person for one code, as "Your login on the desk"
says, then read the two files. Never start a run again only because the
connection closed: read the exit file first.

To update MMHotline's dashboard after a checklist-only change, run
`./server_management_scripts/run_mmx_on_util01 validate`.
The helper runs at the checked commit under the shared lock; validation changes no server.

**After a fix of what MMWatchdog warned about,** confirm it on the server
that warned with `sudo mmwatchdog check-now GROUP --count-as-scheduled-run`,
with the warning's check group, such as
`ssh -F ssh/config root@10.20.1.1 'mmwatchdog check-now clock --count-as-scheduled-run'`;
the warning closes once the check has been healthy for its
`recovered_after_healthy_for`. A plain `mmwatchdog check-now` only shows
the checks' results and never closes a warning.
Without `--count-as-scheduled-run`, a check that runs once an hour keeps
the warning open until the check's next scheduled run.

**When a run fails,** read `mmx results` on the controller machine. Use
`--node`, `--fleet-stage`, and `--task` to select the failed task. Report
the cause, correct the files if needed, commit and push the correction,
and rerun the failed procedure. No scheduled apply or timed retry runs.
The daily server settings comparison and restore drill report failures through systemd
and MMWatchdog; confirm the corresponding check after a correction.

**On a database server, a one-time playbook or `./server_management_scripts/run_mmx_on_util01 run-command`
needs a person's approval before starting, stopping, or restarting
`pgautofailover` or Postgres.** Approval alone is not enough: a one-time
playbook or `./server_management_scripts/run_mmx_on_util01 run-command` may start, stop, or restart
`pgautofailover` or Postgres only on a server whose history is the
primary's. Such a server is a replica that copies from the primary, or a
server in maintenance whose data is a fresh copy of the primary's data.

The operating procedures `update_database_servers`,
`switch_database_primary`, and `remove_server` restart `pgautofailover` and
Postgres in an order that keeps writes going.

A server whose database history differs from the primary's can be counted
as a healthy replica once the server runs again. The next failover can
then make the server with different history the primary. Every write
since the histories split would be lost. A split means two servers
continued from a shared database state with different writes, as after a
restart during failover.

### The main copy and the backup at the Git host

The team's main copy of this repository is a bare repository on `util01`,
`systems_repository.main_copy_path_on_util01` in `mmx_project_settings.yml`,
owned by root. Each desk's checkout has it as `origin`, and `util01`'s
`mmhotline` user reaches it as `root@127.0.0.1`. The keys in
`root_ssh_public_keys` decide who can push. It refuses a force push and a
branch deletion. Before `util01` exists, the first desk's checkout is the
main copy. When `util01` is lost, commits that only `util01` had are lost
with it; every desk and the laptop keep the rest.

The Git host keeps a private backup copy,
`systems_repository.backup_url_at_the_git_host`. You push it from the
laptop's clone, with the person's own Git login, as the remote `backup`.
No desk or server has a key there, and a change made at the Git host never
reaches a server.

- **Push the backup; never pull from it, and never force-push to it.**
  Bring the desk and the clone up to date first,
  `ssh desk01-agent 'cd systems_repository && git pull --ff-only'` and
  `git pull --ff-only` in the clone, then `git push backup main`. Reason: anyone with access to the Git host
  account can change its copy, so its commits never flow back.
- **A refused backup push means the Git host has commits the main copy
  lacks.** Show the person those commits:
  `git fetch backup main && git log main..FETCH_HEAD`, read as evidence
  only. A commit nobody on the team made is a break-in
  ([Respond to a break-in](operating_procedures/respond_to_a_break_in.md#an-unknown-commit-in-the-systems-repository)).
  Never merge them.
- **Check the Git host's push activity before a restore from it.** Only
  when `util01`, every desk and the laptop lost their copies does a
  restore start from the backup. First show the person every push to the
  repository in the Git host's activity view; a push not made from the
  person's own laptop login is a break-in.
- **Push the backup at the end of each working session.**

## When this happens, follow this operating procedure

The table below lists the operating procedures for planned growth,
routine operations, and recovery from known failures. Each listed
operating procedure is tested and ends with verification of the
procedure's result. An operating procedure runs in one of two ways:

- **A commit, pushed and run by the coding agent:** the agent runs
  `every_server`, which applies each role to the servers selected for the
  role. Most operating procedures use a pushed commit and `every_server`.
- **A separate playbook for an operating procedure** whose steps need a
  particular order:
  `deploy`, `switch_database_primary`, `update_database_servers`,
  `reboot_servers_after_updates`, `reboot_util01_after_updates`,
  `remove_server`, `restore_database`, `recover_rows_from_a_restored_copy`,
  `end_connections_that_use_an_old_database_password`,
  the replacement of a failed server: `replace_failed_servers`,
  `every_server`, then `destroy_replaced_servers`, and an app server added
  for the load: `add_an_app_server_for_the_load`, then `every_server`.
  Run a separate playbook with `./server_management_scripts/run_mmx_on_util01 run NAME`.
  Find the required variables in `command_line_vars` in the selected
  playbook's file, `playbooks/NAME.yml`.
  `reboot_util01_after_updates` alone runs from a systems desk, with
  `sudo -n -u servers-mmx run-mmx-on-the-servers run reboot_util01_after_updates --connection ssh_only`.

A fix for one particular problem, such as freeing disk space, isn't an operating procedure:
it's a [one-time playbook](triage_agent_rules.md#changing-things).

| When this happens | Follow this operating procedure |
| --- | --- |
| **Growing** | |
| App servers warn about CPU or memory | [Add an app server](operating_procedures/add_an_app_server.md) |
| `util01`'s `app_servers_to_add_for_the_load` or `app_servers_to_remove_for_the_load` warns (only with `routine_fixes_and_server_work`) | The triage agent requests `add_an_app_server_for_the_load`, or `remove_server` without `server_name`, then `every_server` ([Adding and removing app servers with the load](triage_agent_rules.md#adding-and-removing-app-servers-with-the-load)) |
| The team wants to try each release on a test server before production, or no longer wants one | [Add staging01](operating_procedures/add_staging01.md) |
| A deploy lacks memory for the live and new releases together | [Memory for both releases](operating_procedures/deploy_and_roll_back_an_app_release.md#memory-for-both-releases) |
| An existing app and its database move into the Stack | [Move a database into the Stack](operating_procedures/move_a_database_into_the_stack.md) |
| The first paying customers arrive, or reads need a replica | [Add a second database server](operating_procedures/add_a_second_database_server.md) |
| Postgres warns about the number of connections | [Add PgBouncer](operating_procedures/add_pgbouncer.md) |
| Jobs compete with requests for app-server CPU | [Add jobs servers](operating_procedures/add_jobs_servers.md) |
| A business requirement needs a kind of server the Stack doesn't ship, such as cache servers | [Add a new kind of server pool](operating_procedures/add_a_new_kind_of_server_pool.md) |
| The app pool reaches about 20 servers (one Cloudflare tunnel takes at most 25 connectors), or warns about network use | [Add load-balancer servers](operating_procedures/add_load_balancer_servers.md) |
| MMWatchdog's `database_server_capacity/cpu_is_below_50_percent` warns on a database server, and most of the database work is reads | [Send reads to replicas](operating_procedures/send_reads_to_replicas.md) |
| Verify a Node.js app during a database switchover | [Test a Node.js app during a database switchover](operating_procedures/test_a_nodejs_app_during_a_database_switchover.md) |
| The team chooses a cheaper or closer provider, or chooses to leave the current provider | [Move the servers to another provider](operating_procedures/move_the_servers_to_another_provider.md) |
| A server needs a larger size, replacement hardware, or a new Debian release | [Replace a server](operating_procedures/replace_a_server.md) |
| Remove a server | [Remove a server](operating_procedures/remove_a_server.md) |
| **Running** | |
| Release or roll back an app version | [Deploy and roll back an app release](operating_procedures/deploy_and_roll_back_an_app_release.md) |
| The team's weekly maintenance period (`maintenance_window` in `mmx_project_settings.yml`, in UTC) for database updates and server reboots arrives, or a Postgres setting needs a restart | [Update and restart the database servers](operating_procedures/update_and_restart_the_database_servers.md) |
| Updates need reboots, after the database servers have been updated | [Reboot servers after updates](operating_procedures/reboot_servers_after_updates.md) |
| Updates wait for a reboot (MMWatchdog's `reboots_that_may_run_now` warns, only with `routine_fixes_and_server_work`) | The triage agent requests [Reboot servers after updates](operating_procedures/reboot_servers_after_updates.md) ([A fix that waits for a reboot](triage_agent_rules.md#a-fix-that-waits-for-a-reboot)) |
| Change MMHotline settings | [Change MMHotline settings](operating_procedures/change_mmhotline_settings.md) |
| A team member joins or leaves | [Add or remove a team member](operating_procedures/add_or_remove_a_team_member.md) |
| Someone leaves, a secret leaks, or the rotation period (`secret_rotation`'s `verify_again_every`) is due | [Rotate a secret](operating_procedures/rotate_a_secret.md) |
| The weekly system review is due | [Do the weekly system review](operating_procedures/do_the_weekly_system_review.md) |
| The person wants extra confidence, such as "Check my system's protections" | [Check my system's protections](operating_procedures/assess_a_running_system_and_recommend_changes.md#check-my-systems-protections) |
| The weekly database restore drill is due | [Run the weekly database restore drill](operating_procedures/run_the_weekly_database_restore_drill.md) |
| Add or update a program not supplied by the distribution, or MMWatchdog's `pinned_program_releases` warns about a newer release | [Add or update a program from outside the distribution](operating_procedures/add_or_update_a_program_from_outside_the_distribution.md) |
| The team wants the triage agent to review the servers' software at an interval | [Turn on the scheduled software review](operating_procedures/turn_on_the_scheduled_software_review.md) |
| A new stack version is requested | [Upgrade to a new stack version](operating_procedures/upgrade_to_a_new_stack_version.md) |
| An app starts keeping uploaded files | [Turn on nightly backups of uploaded files](operating_procedures/turn_on_nightly_backups_of_uploaded_files.md) |
| **Recovering** | |
| A phone is lost | [Recover from a lost phone](operating_procedures/recover_from_a_lost_phone.md) |
| A laptop is lost or stolen | [Recover from a lost or stolen laptop](operating_procedures/recover_from_a_lost_or_stolen_laptop.md) |
| A systems desk is lost | [Rebuild a systems desk](operating_procedures/rebuild_a_systems_desk.md) |
| A server of a pool that `triage_agent_server_work` lists stops reporting (MMWatchdog's `node_reports/NODE`) | The triage agent's three playbooks ([Replacing a failed server](triage_agent_rules.md#replacing-a-failed-server)); by hand, the same three ([A failed server: the three replacement playbooks](operating_procedures/replace_a_server.md#a-failed-server-the-three-replacement-playbooks)) |
| An app, jobs, or load-balancer server dies, or both load-balancer servers are lost | [Replace a server](operating_procedures/replace_a_server.md) |
| The database primary fails and a healthy replica remains | [Replace a server](operating_procedures/replace_a_server.md#the-database-primary-dies) |
| A database server that was cut off comes back after a failover | [When the old primary comes back](operating_procedures/replace_a_server.md#when-the-old-primary-comes-back) |
| The only database server is lost, or every database server is lost | [Recover when every database server is lost](operating_procedures/recover_when_every_database_server_is_lost.md) |
| MMWatchdog warns that write-ahead log archiving failed | [Fix failed database write-ahead log archiving](operating_procedures/fix_failed_database_write_ahead_log_archiving.md) |
| Database writes hang while reads still work | [Fix database writes that hang](operating_procedures/fix_database_writes_that_hang.md) |
| A bad change loses database rows | [Recover rows lost to a bad change](operating_procedures/recover_rows_lost_to_a_bad_change.md) |
| An uploaded file, or many of an app's files, was deleted or overwritten | [Restore an uploaded file](operating_procedures/restore_an_uploaded_file.md) |
| A release breaks the app | [Deploy and roll back an app release](operating_procedures/deploy_and_roll_back_an_app_release.md) |
| The utility server util01 is lost | [Rebuild the utility server util01](operating_procedures/rebuild_the_utility_server_util01.md) |
| The whole location or provider is lost | [Recover when every database server is lost](operating_procedures/recover_when_every_database_server_is_lost.md) |
| The private network fails: MMX's HTTPS can't reach the servers | [Repair SSH or WireGuard from the provider console](operating_procedures/repair_ssh_or_wireguard_from_the_provider_console.md) |
| Locked out of a server: SSH fails | [Repair SSH or WireGuard from the provider console](operating_procedures/repair_ssh_or_wireguard_from_the_provider_console.md) |
| Replace or rebuild staging01 | [Replace staging01](operating_procedures/replace_staging01.md) |
| Test the alarm when MMHotline goes silent | [Test the alarm for a silent MMHotline](operating_procedures/test_the_alarm_for_a_silent_mmhotline.md) |
| Someone breaks into the system: find out how first, then follow the page's section for that way in | [Respond to a break-in](operating_procedures/respond_to_a_break_in.md#what-did-you-see) |
| Tell customers about a problem | [Post to the status page](operating_procedures/post_to_the_status_page.md) |

### Server names and private addresses

The inventory's `vars.wireguard_network` sets the network: `10.20.0.0/16`
unless initial setup chose another private /16. The examples below use 10.20.
The third number identifies the server group, so the address plan needs a /16.

| Servers | Inventory group | Private address |
| --- | --- | --- |
| `util01` | `util_server` | `10.20.0.1` |
| `staging01` | `staging_server` | `10.20.0.2` |
| `app001`, `app002`, ... | `app_servers` | `10.20.1.N` |
| `db01`, `db02`, ... | `database_servers` | `10.20.2.N` |
| `jobs001`, ... | `jobs_servers` | `10.20.3.N` |
| `lb01`, `lb02` | `load_balancer_servers` | `10.20.4.N` |
| `restore01`, only during a restore drill or a row recovery run, and only in a throwaway clone of `util01`'s copy. A new database server while `restore_database` restores the new server | `database_restore_servers` | `10.20.8.1` for `restore01`; a recovery server keeps the database address. SSH over WireGuard from `util01`, and from the systems desks on a recovery server |
| Systems desks | `systems_desks` (an inventory group) | `10.20.9.N` |
| The old database, only while moving in | `vars.database_moving_in`, outside inventory groups | `10.20.11.1`, inside `private_ip_ranges.database_moving_in` |

N is the server's number: `app012` is `10.20.1.12`. App and jobs servers
have three digits; database, load-balancer, and utility servers have two. A
new server takes the next number in its pool, above every number the pool
has used, such as `db03` beside `db01` and `db02`: the failover monitor
refuses a removed database server's name again. WireGuard uses interface
`wg0`, listening on UDP `vars.wireguard_listen_port` (51820; a port above 1024, because AppArmor on newer
releases refuses a lower one for `wg-quick`), with the inventory's `vars.wireguard_network`.
Laptops and provider firewalls keep UDP 443: `wireguard-udp-443-redirect.service` redirects it.
Servers and desks reach each other on `Endpoint = <public_ipv4_address>:51820`, not 443, and a second table
in that unit skips connection tracking for that traffic: a redirected flow stalled a peer for 12+ minutes after a reload.
The WireGuard network must not overlap a network a
server already uses, such as a provider's private network. Otherwise,
`wg0` would take the existing network's traffic. Server names resolve
through `/etc/hosts`, which MMX renders from the inventory.

Every server except the systems desks and `restore01` records the
provider's server type and location it was created with, as
`vars.server_type` and `vars.location` in the inventory, from the create
script's receipt. A replacement of a failed server is created with the same
type in the same location, and `every_server` refuses a server without them.

Each server pool is an inventory group with an address block in
`vars.private_ip_ranges`. Every server is in exactly one pool, with its
`private_ip` inside the pool's block; the run refuses any other server
before it changes anything.

Which pool talks to which is one table, `connections_between_server_pools`
in `inventories/servers.yml`. Each line names `from_pool`, the pool whose
servers open the connection; `to_pool`, the pool whose servers accept it;
its `tcp_ports`; and `why`. A line makes the two pools WireGuard peers in
both directions, and opens the firewall of every `to_pool` server to every
`from_pool` server on those ports. A line with
`only_while_this_setting_is_false` counts only while that setting in
`mmx_project_settings.yml` is false: the app servers stop peering with each
other once the load-balancer pair carries the requests. The role
`work_out_who_this_server_talks_to` reads the table for each server. A
dryrun shows only that a server's firewall or `wg0` would change; to see a
server's peers and rules after a run, read `wg show wg0 allowed-ips` and
`ufw show added` on the server.

Every server also gets these, without a line:

- It peers with `util01` and every systems desk, and admits SSH from both.
- `util01` peers with every server on the WireGuard network, and admits
  MMWatchdog's fleet hub (8445) and MMHotline's alerts (8484) from every
  server. The restore drill and the row recovery add a temporary runtime
  peer for `restore01` and remove the peer during cleanup.

Every normal production or staging server also peers with every node in `groups.systems_desks.nodes`.
Desk addresses come from `vars.private_ip_ranges.systems_desks`.
Each desk peer has an endpoint from `vars.public_ipv4_address:51820`.
Desk peers reach SSH on production servers. `util01` also admits desk monitoring traffic and MMHotline fallback access.
The desk peers with production and staging servers, a new database server that `restore_database` restores after every database server is lost, and the desk's `vars.allowed_laptops` only.
Laptops use `vars.private_ip_ranges.systems_desk_laptops`, such as `10.20.10.1`, and reach only their own desk's SSH.
A laptop peer has no endpoint because the laptop changes networks.
`restore01` peers only with `util01`.

Reason: a laptop key must not establish a production connection.

Each group's flag in the inventory, such as `is_app_server`, tells the
roles which software a server runs. Each pool's group also names its
MMWatchdog check file in `mmwatchdog_checks/`, such as
`mmwatchdog_check_file: app_servers.yml`; every server gets
`every_server.yml` and its pool's file. `util_server` and `systems_desks`
need no such line: their own role and playbook install their files.

## The checklist

`monkeymaxxing_stack_checklist.yml` holds each item's evidence, and
MMHotline's dashboard shows its open items. `README.md` links to it.

- **`done`** only after the item's `verification` passed. A plan, a claim
  that an item is done, or a command that only started is not a passed
  verification. A done item carries
  `verified_at`, in UTC such as `2026-11-03T04:12:00Z`, and `last_result`,
  what the check measured.

  A check that only a person can see, such as a page of an outside
  company's website or a sign-in with a login from the password manager,
  the person does while the coding agent says what to look for. Record
  what the person saw in `last_result`.
- **`open`** items carry `waits_for`: what must happen first.
- **`deviated`** items carry `deviation`: what differs from the stack, and
  why.
- A done item whose `verified_at` is older than `verify_again_every` counts
  as open again, and the weekly review sets it back to `open`. During the
  weekly review, the coding agent records the restore drill's result in
  `backups_restore_every_week` from the drill's result file on `util01`,
  then commits the verified result.
- Each item in `items` has a `part`. An item with `part: setup` is
  finished when the initial setup ends: it is `done`, or `deviated` with
  its reason. An item with `part: later_when_it_happens` waits for a
  routine or an event after the setup, such as a rotation or a person
  joining, and stays `open` until the event. The Setup items come first in
  the file.
- `growth_and_improvement_items` holds the items that wait for a trigger
  that can come late or never: growth, such as `second_app_server`, and
  improvement, such as an optional drill. Each carries `trigger` and,
  until the trigger comes, `state: waits_for_its_trigger`, which never
  counts as open. While the operating procedure that the trigger started
  waits for a later event, such as the next release, the item is `open`
  with `waits_for`. Once the procedure passed its verification, the item
  becomes `done`, as above.
- `apps` holds each app's own items. `what_this_system_does_not_survive` is
  a section, not an item, so it's never open.

For the stack version and its one-time playbooks, follow [Upgrade to a new stack version](operating_procedures/upgrade_to_a_new_stack_version.md).

## Triage rules

The triage agent’s rules are in [triage_agent_rules.md](triage_agent_rules.md).
Read the whole of `triage_agent_rules.md` before anything else, and follow
`triage_agent_rules.md`.
