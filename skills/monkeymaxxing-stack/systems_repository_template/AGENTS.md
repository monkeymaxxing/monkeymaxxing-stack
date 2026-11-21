# Working in this systems repository

Read [Talking with the team](talking_with_the_team.md) before work, and
follow the writing rules in conversations, documentation, setup instructions,
and incident reports. `talking_with_the_team.md` holds the Plain English
rules, the person's words, technical terms, and example messages.

This repository is the company's whole production system: its servers,
settings, deploys, and fixes. Every coding agent reads `AGENTS.md` first:
the team's coding agent on a person's laptop, and the triage agent that
MMHotline runs on `util01` when an alert arrives. The system follows the
Monkeymaxxing Stack at the version named by `stack_version` in
`monkeymaxxing_stack_checklist.yml`.

## What this repository is

Read the [system summary and operating handover](README.md) for this
system's current servers, links, and tested protections. Update `README.md`
when an operation changes the servers, links, or tested protections, using
the inventory and checklist to verify each claim.

`README.md` is what the person reads, so it holds no instruction for a
coding agent: agent instructions belong in this file, `triage_agent_rules.md`,
or an operating procedure. Keep the README's next actions at most five, in
order, each with its responsible person and date or starting event (or
saying which detail is not agreed). Group related work into one action, and
remove an action once the checklist records its result. Reason: five
actions keep the person's first step easy to find, and the checklist holds
every other open item.

A **pool** is the servers that share one job, such as the app servers.
`staging01` runs every role on one server for testing the apps. A
**failover formation** is the production database servers managed together
by pg_auto_failover (`staging01` runs Postgres without it). Servers and
systems desks talk over one WireGuard network
([Server names and private addresses](#server-names-and-private-addresses)).

Three tools operate the system: **MMX** applies this repository to the
servers; **MMWatchdog** watches every server and alerts, with its fleet
hub on `util01` (systemd restarts crashed services); and **MMHotline**, on
`util01`, receives alerts, reaches the person on call, runs the triage
agent, and serves the dashboard behind Cloudflare Access.

| Path | What the path holds |
| --- | --- |
| `README.md` | The first page (what the Stack builds, with this system's servers), operating links, failure behavior, and next actions |
| `talking_with_the_team.md` | Plain English rules, the person's words, how to talk before/during/after steps, example messages, and technical terms |
| `AGENTS.md` | This file: rules for every coding agent and the operating procedure table |
| `triage_agent_rules.md` | The triage agent's rules, which it reads in full |
| `initial_setup/` | The ten setup chapters (chapters 1 to 9 put the app live; alerts, triage agent, status page, and chapter 10 follow) |
| `operating_procedures/` | One file per operating procedure, with steps and verification (including stack upgrades and system assessment) |
| `CLAUDE.md` | One line, `@AGENTS.md`, so Claude Code reads `AGENTS.md` |
| `monkeymaxxing_stack_checklist.yml` | Every stack item (`done`, `open`, or `deviated`, with reason), trigger-gated `growth_and_improvement_items`, and `custom_extensions` |
| `mmx_project_settings.yml` | Project settings, apps, SSH keys, and pinned downloaded programs (`stack_software`) |
| `mmhotline_settings.yml` | MMX template for MMHotline (people, on-call, alert sources, playbook rules, triage agent, sending services, MMHotline-down alarm, status page), rendered with vault secrets to `/etc/mmhotline/mmhotline_settings.yml` on `util01` |
| `server_management_scripts/` | `run_mmx_on_util01`, provider scripts written by the coding agent, and server first-boot data |
| `provider_guides/` | Provider notes for writing the team's provider scripts |
| `inventories/servers.yml` | Servers, pools and pool flags, addresses, WireGuard public keys, pool address blocks, `connections_between_server_pools`, and deployed image tags |
| `playbooks/` | `every_server.yml` (whose fleet stages, including `mmhotline`, bring every server to match this repository) plus ordered operating-procedure playbooks |
| `roles/` | `every_server`, `app_server`, `tunnel_connector_and_caddy`, `database_server`, `util_server`, `uploads_backup`, `mmwatchdog_joined_node`, `jobs_server`, `pgbouncer`, plus the lock-out roles (`everyone_locked_out` for server admission, `systems_desk_lockout` for Cloudflare Access revocation on a desk) |
| `mmwatchdog_checks/` | MMWatchdog checks per check group, with limits filled from the inventory; the team's own files start with `custom_` |
| `custom_recipes/` | Copies of the recipes the team applied, each stamped with where it came from; read-only background notes (created with the first recipe) |
| `files_used_by_several_roles/` | Shared files: Cloudflare's apt signing key, pgBackRest settings, app env files / job container template / weekly image cleanup (app and jobs servers), and MMHotline backup settings |
| `one_time_playbooks/` | Dated one-off fixes (`completed/` holds finished ones) |
| `triage_agent_notes/` | One note per triage session (a section per cause) and `open_software_findings.md` (scheduled software review findings; `"No open findings."` on a new system) |
| `software_outside_the_distribution.yml` | Programs that do not come from Debian |
| `scheduled_software_review_task.md` | Task for the optional scheduled software review (off until turned on) |
| `secrets_vault.age` | Encrypted MMX vault holding every secret the servers use |
| `ssh/known_hosts`, `ssh/config` | Server SSH host keys and SSH settings for MMX, `util01`, and the triage agent |

Later roles activate by setting or inventory: `jobs_server` when
[Add jobs servers](operating_procedures/add_jobs_servers.md) adds nodes to
`jobs_servers`; `pgbouncer` when [Add PgBouncer](operating_procedures/add_pgbouncer.md)
turns on `pgbouncer_runs_in_front_of_postgres`; `uploads_backup` copies R2
uploads to B2 while an app keeps uploaded files. Each role keeps its
templates in its own `files/` directory. `.mmx/` (gitignored) holds MMX
run history on each machine.

### Your login on the desk

You are the team's coding agent, on the person's laptop. No coding agent
runs on the desk. Each person has a systems desk (such as `desk01`), a
small server that is a locked key box holding the production private key,
vault passphrase, and personal provider and Cloudflare tokens. You use them
through the desk and can never copy them. The laptop reaches only the
person's desk, through doubleshell and WireGuard; the desk uses kernel
`wg0` directly to the servers
([Server names and private addresses](#server-names-and-private-addresses)).

You reach the desk through one SSH entry on the laptop, `desk01-agent`, as
`coding-agent`. One phone code opens a shared connection reused by every
later command until the desk closes it after `coding_agent_login_idle_minutes`
(60) unused or `coding_agent_login_longest_hours` (10) at most.

Run requests to public addresses (such as an app's public health URL) on
the laptop, not on the desk, so you see what users see.

In the commands below, replace `example_systems` with this repository's
`project_name`. `~/code/example_systems/ssh/open-the-desk-login --check`
returns exit 0 when the connection is open, 1 when closed. When closed,
ask the person for one code in one short message:

```text
I need one code from your phone to work on your systems desk.

Type the 6 digits here. This is safe: the code works once, for 30 seconds,
and only from this laptop.
```

When the person just typed a code for something else, add
`WAIT FOR A NEW CODE.  The code you just typed works only once.` in bold
capitals before the last line. Then open the connection:

```sh
# On the laptop. CODE: the 6 digits the person typed.
~/code/example_systems/ssh/open-the-desk-login CODE
```

Run it by its full path so it never needs a second approval. It hands the
6-digit code to SSH without writing a file, uses no code if already open,
and prints `The desk login desk01-agent is open.` or a failure. Five wrong
codes within ten minutes lock the laptop out for five minutes
(`phone_code_lockout` in `mmx_project_settings.yml`).

Every command block labelled "This systems desk, as the coding agent" runs
through `ssh desk01-agent 'COMMAND'`. The desk checkout is
`/home/coding-agent/systems_repository` (`systems_repository` from your
login), where `ssh -F ssh/config` works using `/run/desk-ssh-agent/socket`
(for example,
`ssh desk01-agent 'cd systems_repository && ssh -F ssh/config root@10.20.1.1 uptime'`).
Reach a loopback-only server service through an SSH port forward on the
desk (such as `ssh -F ssh/config -L 8480:127.0.0.1:8480 root@10.20.0.1` for
MMHotline on `util01`).

The desk's buttons and services for `coding-agent`:

- **WireGuard peers:** `sudo -n update-this-desks-wireguard-peers` syncs
  the desk's server peers from pushed `main` (pull first). Run it at the
  start of each session, after pushing a server add/replace/remove, and
  whenever SSH to a server times out. Never edit `wg0` by hand.
- **Direct MMX button:** `sudo -n -u servers-mmx run-mmx-on-the-servers`
  runs from its own checkout at pushed `main` (fetched `origin/main`, or
  desk `main` before `util01` exists; run `git pull --ff-only` in the desk
  checkout first). Scope is production and staging only, never the desk
  itself. Never edit the vault through `run-mmx-on-the-servers secrets`
  (the next call resets its checkout).
- **API proxy:** `http://127.0.0.1:8081/` (server provider, adding the
  person's token or signing requests for OVHcloud, AWS, or Google Cloud)
  and `http://127.0.0.1:8082/` (Cloudflare). Never read the person's token
  files.

The person logs in to the desk only for a few short laptop commands plus a
phone code: `ssh desk01-secrets` for new secrets,
`ssh -t desk01 sudo lock-everyone-out` for a break-in lock-out, and
`ssh desk01-review` to manage the desk itself:

```sh
ssh desk01-review
```

`ssh desk01-review` runs `review-and-apply-the-systems-desk-settings` on
the desk, applying `playbooks/systems_desk.yml` as root. Unchanged since
the person's last desk review, it runs at once; changed, it shows each
change and waits for the person to type `yes` (you cannot answer it, and
must give a short plain summary of what changes and why beforehand). The
desk's root-owned loopback key must never enter the coding agent's socket.
Because the lock-out button (`sudo lock-everyone-out`) runs only the copies
installed by the last desk review, tell the person whenever your pushed
change touches `playbooks/systems_desk.yml`,
`playbooks/lock_everyone_out.yml`, the `everyone_locked_out`,
`systems_desk_lockout`, or `work_out_who_this_server_talks_to` roles,
`server_management_scripts/start_break_in_lockout.py`, `ssh/`,
`roles/every_server/files/wireguard_wg0.conf`,
`roles/every_server/files/sudoers_triage`,
`roles/util_server/files/sudoers_triage_mmwatchdog_fleet_readings`, or
`mmhotline_settings.yml`, and explain that it reaches the desk or lock-out
button only after the next `ssh desk01-review`.

## The rules

- **Check every change against the goal.** A newcomer finishes with a live
  site, phone alerts, and proven restores, confident in how the system
  works. Every setup chapter, checklist item, and operating procedure must
  meet three rules: the agent and APIs do the work while the person decides
  and watches; each step checks only what is specific to this team; and
  defaults fit a team of one or two people (stronger options are settings,
  never requirements). Full text: `docs/acceptance.md`, "The goal".
- **Everything is a commit.** Settings, deploys, fixes, and scaling are
  commits to this repository, applied by an MMX run. Write commit messages
  that say what changed and why.
- **The coding agent applies each change.** Edit, validate locally
  (`~/.local/bin/mmx validate`), commit, publish to `main`, preview, then
  run MMX on `util01` ([Making a change](#making-a-change)). A push alone
  changes no server. Use `every_server` for configuration and `deploy` for
  a release (run `every_server` first when a deploy needs new settings).

  `./server_management_scripts/run_mmx_on_util01` runs MMX on `util01` at
  the desk's clean pushed `main` commit in `/var/lib/mmhotline/systems_repository`,
  holding `/var/lib/mmhotline/systems_repository.lock` (shared with
  MMHotline, the daily settings comparison, and the restore drill). When
  the triage agent or a playbook pushed a commit since your last pull, the
  helper refuses with `"HEAD must equal pushed main"`: pull `main` on the
  desk (`git pull --ff-only`) if you have no unpushed commits, or republish
  your branch with `publish-branch-to-main` (steps 1 to 4 of
  [Making a change](#making-a-change)), then run the helper again. If
  MMHotline does not answer, the helper refuses and runs nothing. While
  waiting for the lock, it reports every minute who holds it, how long it
  waited, and how to stop that run
  ([the helper guide](server_management_scripts/README.md#run-mmx-on-util01)).

  MMX keeps 30 days of history (`run_history_retention`) in `.mmx/` on
  `util01`; read results, status, or stop a run with `run_mmx_on_util01`
  without taking the lock. Failed runs need investigation and an agent-run
  retry. Use the desk button (`sudo -n -u servers-mmx run-mmx-on-the-servers`)
  for previews, initial setup, `util01` recovery or reboot, a changed vault
  passphrase, and lock-outs. The desk button does not wait for `util01`'s
  lock, so run it only when no run holds `util01`'s lock (MMX refuses
  overlapping runs on a server, and `app_server` stops if the live port
  changed). Reason: one controller keeps run history together and ensures
  every run applies a reviewed commit.
- **Only a person starts or undoes a lock-out.** Follow
  [Respond to a break-in](operating_procedures/respond_to_a_break_in.md).
  Find out how the intruder got in first; recommend a lock-out only for the
  cases in
  [The lock-out: only for these cases](operating_procedures/respond_to_a_break_in.md#the-lock-out-only-for-these-cases)
  (`util01` or triage agent suspect, unknown root access/process/MMX run,
  or unknown compromised desk/credential). Otherwise a lock-out harms more
  than it helps. To start one, push `everyone_locked_out_except_desk: DESK`
  under top-level `vars` in `inventories/servers.yml` and give the person
  `ssh -t desk01 sudo lock-everyone-out` (`lock_everyone_out` reaches no
  other desk; other desks lose server admission). To undo, push the removal
  and give the same command. The button runs only the copies installed by
  the last desk review ([Your login on the desk](#your-login-on-the-desk)).
  While locked out, work from the desk that keeps access using
  `sudo -n -u servers-mmx run-mmx-on-the-servers run PLAYBOOK --connection ssh_only`
  (because `util01` lost admission and MMX's HTTPS service is stopped).
  `every_server` refuses any lock-out start, undo, or change to the
  keeping desk's `private_ip`, `wireguard_public_key`, or
  `production_ssh_public_key` not recorded by the lock-out button; the
  person must press the button again for those changes.
- **Never change a server by hand.** Reading over SSH is fine; every change
  goes through MMX. Exceptions: starting a scheduled job now (such as the
  restore drill or uploads copy), test power-offs in operating procedures,
  and the person's setup/recovery commands on a systems desk
  (`set-up-outside-services`, phone code, restored keys).

  Start the restore drill over SSH rather than
  `run_mmx_on_util01 run-command`, because `run-command` holds `util01`'s
  lock while waiting for the drill, which itself needs `util01`'s lock
  (deadlock).

  When an incident leaves no other way (such as stopping a harmful service
  until replacement), first put the server in MMWatchdog maintenance with a
  reason so the triage agent does not undo it:
  `mmwatchdog maintenance on --every-check-group --for 24h --reason "pgautofailover stopped by hand: db02 is being replaced"`,
  and end it with `mmwatchdog maintenance off --every-check-group`.
- **Servers are replaced, never upgraded in place.** Bigger size, VPS to
  dedicated, new Debian release, failed hardware, and a failed mirrored
  drive on a dedicated database server are all "Replace a server". Never
  upgrade Debian in place via apt sources.
- **Every configured production secret lives in the vault,** `secrets_vault.age`,
  MMHotline's included: never in another repo file, commit message, image,
  or log. The person types each secret once at a hidden prompt of
  `set-up-outside-services` on the desk (`ssh desk01-setup` during initial
  setup, `ssh desk01-secrets` later, or
  `ssh -t desk01 set-up-outside-services secrets --replace KEY` for a
  rotation), which generates random keys and commits and pushes the vault
  ([Secrets in chapter 3](initial_setup/03_make_your_server_account_and_your_systems_desk.md#secrets)).

  You never open or print secrets: no `mmx secrets edit` or `mmx secrets show`,
  no playbook or `run-command` that prints a secret, and no reading rendered
  secret files such as `/etc/<app>/`. Check key names only through your
  button after pushing files that reference new keys:
  `ssh desk01-agent sudo -n -u servers-mmx run-mmx-on-the-servers secrets usage`
  (or `secrets list-keys`; `secrets usage` exits 1 while any key is
  `not defined`, including unused optional features like `staging_`, so
  read the list rather than the exit code). Reason: your provider stores
  the conversation. App secret keys are `<app>_<VAR>` (such as
  `shop_SECRET_KEY_BASE`). Personal tokens stay in the person's desk token
  file; `recovery_bundle.age` holds everything a lost desk needs (opened by
  the recovery passphrase in the password manager); account logins and
  **break-glass access** (listed in `provider_console_and_backup_mmhotline_logins`)
  live in the team's password manager.
- **MMHotline owns triage approval and execution.** MMHotline trusts every
  commit on `main` in the main copy
  (`systems_repository_commits.trusted_commits: every_commit_on_origin` in
  `mmhotline_settings.yml`), updating its shared copy to `main` before each
  run; commits are not signed because only keys in `root_ssh_public_keys`
  can push there (never add a Git host as `origin` or let anyone else push
  there). MMHotline commits no run output (results appear on the request's
  page) and pushes the triage agent's commits to `main` only when they
  change nothing outside `one_time_playbooks/` and `triage_agent_notes/`;
  any other change waits for a person. The triage agent cannot push to the
  main copy itself (root-owned, mode 0700). Reason: the triage agent reads
  untrusted logs, so the push limit stops a log injection from altering
  server settings.
- **What the triage agent may do without a person** is one setting,
  `what_the_triage_agent_may_do_without_a_person` in
  `mmx_project_settings.yml`: `every_fix_waits_for_a_person`,
  `routine_fixes` (default), or `routine_fixes_and_server_work`. Database
  servers, `util01`, and `staging01` always need a person. Full server-work
  rules live in [triage_agent_rules.md](triage_agent_rules.md). The four
  server-work playbooks (`replace_failed_servers`, `destroy_replaced_servers`,
  `add_an_app_server_for_the_load`, and `remove_server` without
  `server_name`) commit to `main` as `util01`'s `mmhotline` user
  (`git log --grep '^Server-pool: '`), so pull before your next run. To
  change the setting, edit that line when asked, commit, and run
  `every_server`.
- **CI is the recommended way to test, build, and push the app image.**
  Use `files_for_your_app/test_build_and_push_the_app_image.yml` (GitHub
  Actions) so no image-publishing password sits on the desk and CI needs no
  server SSH key or vault passphrase. Edit the app on the laptop, show each
  change, push with the person's Git login after approval, then commit the
  new image tag in the systems repository and run `deploy`.
- **Run the app's install, test, and build commands only inside a
  container on the laptop** (`podman` or `docker`, mounting only the app's
  folder, such as
  `podman run --rm -v /Users/alex/code/shop:/app -w /app IMAGE npm test`),
  never on the desk. Reason: a poisoned app package on the laptop could
  otherwise use your open desk login
  ([chapter 2](initial_setup/02_get_your_app_ready_to_deploy.md#before-you-start)).
- **A server's name never changes, and "primary" is a state.** After a
  failover, `db02` may be primary and `db01` a replica; never rename them.
- **One home for each kind of thing:** code and settings in Git, data in
  Postgres, uploaded files in R2, backups in B2, secrets in the vault, and
  access records in Cloudflare Access, the systems repository, and the
  password manager. App servers keep nothing on disk: web and job
  containers run with a read-only filesystem (`writable_temporary_directories`
  are memory-backed and cleared on start) and their own user namespace
  (`UserNS=auto`, so files in mounted directories must be world-readable).
- **Production data stays on the production servers.** Never copy
  production's database (even anonymized) to a laptop, `staging01`, or CI.
  Keep only the Stack's copies (R2, B2, and temporary `restore01`). Laptops
  and `staging01` use the app's seed command
  ([chapter 2](initial_setup/02_get_your_app_ready_to_deploy.md#chapter-2-get-your-app-ready-to-deploy));
  reproduce bugs with synthetic seed/test records, and run read-only
  production queries on the production servers without copying data out.
  Reason: laptops, laptop backups, AI providers, staging, and imperfect
  anonymization scripts all leak personal data.
- **Follow the stack; ask only for facts.** Every design decision is
  already made with its reason; a different choice is a `deviated`
  checklist item with its reason.
- **Change files with your edit tool,** not `sed`, `awk`, `python`, or
  `perl`, so the person sees each change.

### The two windows agree

The person reads the chat and their own terminal. A tool call's
description and command scroll past, its output is folded away, and text
you write between tool calls is collapsed to one short line on the
person's screen. Only the text that ends your turn is shown in full. Two
windows that disagree cost the person a refused tool call and a question.

- **Screen last.** Anything the person must read or act on (a screen,
  question, price approval, or exact terminal command and expected output)
  is the last thing in your reply and ends your turn: never a tool call
  after it, and never only in a tool call's description or summary.
- **Start the wait first, in the background.** While the person works in
  their terminal, wait only on a result you can read:
  `ssh desk01-agent wait-for-the-setup --at-most-minutes 60`,
  `ssh desk01-agent wait-for-a-desk-job NAME --at-most-minutes 60`, or the
  file a laptop script writes. Start the wait as a background command (in
  Claude Code, run-in-background), then write the screen and end your turn.
  Its completion wakes you so you report what happened; questions the
  person types meanwhile reach you at once. Never wait a fixed time on
  something you cannot see.
- **Every background wait has a bound.** Use `--at-most-minutes N` on wait
  commands, or `timeout` around your own loop (such as
  `timeout 10m bash -c 'until CHECK; do sleep 10; done'`), never an
  unbounded `until` loop. Its end wakes you whatever happened; reply with
  the result (done, failed, or still waiting), giving a failed background
  command the same plain failure line before any retry.
- Never ask the person to say "done" for a result your wait reads (the key
  file, `desk-ready`, `wait-for-the-setup`, or a job's exit). Ask for
  "done" only when nothing you can read shows the result (such as a
  website-only step), and say so.
- **An agent with no background commands** ends its turn with the screen
  and asks the person to say "done" when their window shows the result,
  then runs the same wait in the foreground (which ends at once).
- When a wait hits its bound (exit 124), restart it in the background and
  end your turn with one line saying what you still wait for. When a wait
  ends with a stop, say in one plain sentence what stopped and what
  happens next (`wait-for-the-setup` prints the stop reason, including if
  `go-live` refused before its first screen).

Reason: the person reads only the text ending your reply, and a background
wait keeps the chat free for screens and questions.

### Making a change

Use one branch, `main`, even for a solo developer. Pushed means ready to
run. Reason: every desk must agree which settings the next run applies.

Edit on the laptop in your clone of the desk's repository,
`~/code/example_systems` (replace `example_systems` with `project_name`),
cloned with `git clone desk01-agent:systems_repository`. The desk publishes
each change because only the desk holds the production key that pushes to
the main copy.

1. Update the clone from the desk:
   `git -C ~/code/example_systems pull --ff-only`. Edit the required files,
   run `~/.local/bin/mmx validate`, and review the diff.
2. Stage only intended paths with `git -C ~/code/example_systems add PATH`,
   create a branch named for the change (`git -C ~/code/example_systems switch -c add-app002`),
   and commit (`git -C ~/code/example_systems commit -m "Describe the change and reason"`).
3. Push the branch to the desk:
   `git -C ~/code/example_systems push origin add-app002`.
4. Publish the branch on the desk:

   ```sh
   # On the laptop:
   ssh desk01-agent publish-branch-to-main add-app002
   ```

   `publish-branch-to-main` rebases the branch onto `main` on the desk,
   advances `main`, pushes `main` to `util01` (before `util01` exists, desk
   `main` is the main copy), and deletes the branch. Show the person any
   incoming commits it prints before running MMX (say nothing if none). On
   a conflict, it changes nothing and names the conflicting files: tell the
   person, never resolve a conflict yourself, and stop before running MMX.
   Then sync the laptop clone:
   `git -C ~/code/example_systems switch main && git -C ~/code/example_systems pull --ff-only && git -C ~/code/example_systems branch -d add-app002`.
5. For configuration, preview the pushed commit while `util01` runs nothing:
   `ssh desk01-agent sudo -n -u servers-mmx run-mmx-on-the-servers dryrun every_server --connection ssh_only`.
   On a server MMX has never reached, the first dryrun copies `mmx-runner`
   over SSH without starting a service or opening a port (tell the person
   in one line); the first `mmx run` also sets up `mmx-https-api.service`
   on TCP port 7443 (tell the person before that run, in the person's
   words). Exit codes: 0 no change, 2 proposed changes, 3 incomplete
   preview (`not_checked` prints its reason above `Run ...:`), 1 failed, 4
   command error. Until the first restore drill passes, previews exit 2 for
   `start_the_restore_drill_in_the_background` alone. A "size or SHA-256
   mismatch" against an all-zeros pin means an unreleased Stack checkout:
   copy pins from a released version. Proceed only when every `not_checked`
   task depends on an earlier task in the planned run.
6. Run the procedure on `util01`:
   `ssh desk01-agent 'cd systems_repository && git pull --ff-only && ./server_management_scripts/run_mmx_on_util01 run every_server'`.
   Before `util01` exists or while it is broken, use
   `ssh desk01-agent sudo -n -u servers-mmx run-mmx-on-the-servers run every_server --connection ssh_only`.
   Read the result before verifying. A documentation-only commit needs no
   server run.
7. Verify the outcome, update the checklist and `README.md` if links,
   duties, or tested protections changed, publish those edits with steps 2
   to 4, and report using [Talking with the team](talking_with_the_team.md).

**A run longer than a few minutes is a desk job,** so the laptop may sleep
and the connection may close without stopping it. Start it with
`systemd-run --user` and a unique log/exit name:

```sh
# On the laptop. NAME: the run's name, such as every-server-2026-11-17-1405.
ssh desk01-agent 'mkdir -p ~/runs && systemd-run --user --unit=NAME --collect bash -c "cd ~/systems_repository && sudo -n -u servers-mmx run-mmx-on-the-servers run every_server --connection ssh_only > ~/runs/NAME.log 2>&1; echo \$? > ~/runs/NAME.exit"'
```

A desk job does not inherit sshd's login environment, so a job that pushes
with Git (other than `publish-branch-to-main`, which sets them itself) must
pass `-E SSH_AUTH_SOCK=/run/desk-ssh-agent/socket -E GIT_CONFIG_SYSTEM=/etc/systems-desk/coding-agent-gitconfig`
right after `systemd-run --user`.

Wait for the job with one background command (never a `sleep` loop), then
end your reply with a one-line status as [The two windows agree](#the-two-windows-agree) says:

```sh
# On the laptop, as a background command. NAME: the name you gave the desk job.
ssh desk01-agent wait-for-a-desk-job NAME --at-most-minutes 60
```

It returns the job's exit code with the last 30 log lines and a plain
summary line (exit 125 = invalid exit file; exit 124 = still running at
bound, so restart the wait in the background and say what it is doing).
Re-run it to read an ended job's result or after reopening a closed
connection; never restart a run just because the connection closed, and
give every new run a new name.

To refresh MMHotline's dashboard after a checklist-only change, run
`./server_management_scripts/run_mmx_on_util01 validate` (changes no server).

**After fixing a MMWatchdog warning,** confirm on the server with
`sudo mmwatchdog check-now GROUP --count-as-scheduled-run` (for example,
`ssh -F ssh/config root@10.20.1.1 'mmwatchdog check-now clock --count-as-scheduled-run'`);
a plain `check-now` never closes a warning, and hourly checks otherwise
keep warning until their next scheduled run.

**When a run fails,** inspect `mmx results` on the controller (`--node`,
`--fleet-stage`, `--task`), report the cause, commit and push the fix, and
rerun; no automatic retry runs. For failed daily settings comparison or
restore drill timers, confirm their MMWatchdog check after fixing.

**On a database server, a one-time playbook or `run_mmx_on_util01 run-command`
needs a person's approval before starting, stopping, or restarting
`pgautofailover` or Postgres,** and is safe only on a server whose history
matches the primary's (a replica copying from the primary, or a server in
maintenance with a fresh copy of the primary's data). The procedures
`update_database_servers`, `switch_database_primary`, and `remove_server`
restart them safely in order. Restarting a server with a split history
(different writes after a failover) lets it rejoin as a replica and later
become primary, losing every write since the split.

### The main copy and the backup at the Git host

The team's main copy is a root-owned bare repository on `util01`
(`systems_repository.main_copy_path_on_util01`), configured as `origin` on
each desk and reached by `util01`'s `mmhotline` user as `root@127.0.0.1`.
Only keys in `root_ssh_public_keys` can push; force pushes and branch
deletions are refused. Before `util01` exists, the first desk's checkout is
the main copy. If `util01` is lost, only commits unique to `util01` are
lost; desks and the laptop keep the rest.

The Git host keeps a private backup
(`systems_repository.backup_url_at_the_git_host`), pushed from the laptop's
clone as remote `backup` using the person's Git login. No desk or server
has a key there, and changes at the Git host never reach a server.

- **Push the backup; never pull from it or force-push to it.** Update the
  desk (`ssh desk01-agent 'cd systems_repository && git pull --ff-only'`)
  and laptop clone (`git -C ~/code/example_systems pull --ff-only`), then
  `git -C ~/code/example_systems push backup main`. Reason: anyone with
  Git-host access could alter it, so commits never flow back.
- **A refused backup push means the Git host has commits the main copy
  lacks.** Inspect as evidence only:
  `git -C ~/code/example_systems fetch backup main` and
  `git -C ~/code/example_systems log main..FETCH_HEAD`. Never merge them;
  an unknown commit is a break-in
  ([Respond to a break-in](operating_procedures/respond_to_a_break_in.md#an-unknown-commit-in-the-systems-repository)).
- **Check the Git host's push activity before restoring from it** (only if
  `util01`, every desk, and the laptop are all lost): any push not from the
  person's own laptop login is a break-in.
- **Push the backup at the end of each working session.**

## When this happens, follow this operating procedure

The table below lists the tested operating procedures for growth, routine
operations, and recovery. Each ends with verification and runs either as:

- **A pushed commit plus `every_server`** (most procedures), or
- **A separate ordered playbook:** `deploy`, `switch_database_primary`,
  `update_database_servers`, `reboot_servers_after_updates`,
  `reboot_util01_after_updates`, `remove_server`, `restore_database`,
  `recover_rows_from_a_restored_copy`,
  `end_connections_that_use_an_old_database_password`, failed-server
  replacement (`replace_failed_servers`, `every_server`,
  `destroy_replaced_servers`), and load scaling
  (`add_an_app_server_for_the_load`, then `every_server`). Run with
  `./server_management_scripts/run_mmx_on_util01 run NAME` (check
  `command_line_vars` in `playbooks/NAME.yml`); `reboot_util01_after_updates`
  alone runs through the desk button:
  `sudo -n -u servers-mmx run-mmx-on-the-servers run reboot_util01_after_updates --connection ssh_only`.

A fix for one particular problem, such as freeing disk space, is a
[one-time playbook](triage_agent_rules.md#changing-things), not an
operating procedure.

| When this happens | Follow this operating procedure |
| --- | --- |
| **Growing** | |
| App servers warn about CPU or memory | [Add an app server](operating_procedures/add_an_app_server.md) |
| `util01`'s `app_servers_to_add_for_the_load` or `app_servers_to_remove_for_the_load` warns (only with `routine_fixes_and_server_work`) | The triage agent requests `add_an_app_server_for_the_load`, or `remove_server` without `server_name`, then `every_server` ([Adding and removing app servers with the load](triage_agent_rules.md#adding-and-removing-app-servers-with-the-load)) |
| The team wants to try each release on a test server before production, or no longer wants one | [Add staging01](operating_procedures/add_staging01.md) |
| A deploy lacks memory for the live and new releases together | [Memory for both releases](operating_procedures/deploy_and_roll_back_an_app_release.md#memory-for-both-releases) |
| An existing app and its database move into the Stack | [Move a database into the Stack](operating_procedures/move_a_database_into_the_stack.md) |
| An app on Monkeymaxxing Solo's `solo01` moves onto the Stack | [Upgrade from Monkeymaxxing Solo](operating_procedures/upgrade_from_monkeymaxxing_solo.md) |
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

The inventory's `vars.wireguard_network` sets the network (`10.20.0.0/16`
by default; the third octet identifies the pool, so it needs a `/16`).

| Servers | Inventory group | Private address |
| --- | --- | --- |
| `util01` | `util_server` | `10.20.0.1` |
| `staging01` | `staging_server` | `10.20.0.2` |
| `app001`, `app002`, ... | `app_servers` | `10.20.1.N` |
| `db01`, `db02`, ... | `database_servers` | `10.20.2.N` |
| `jobs001`, ... | `jobs_servers` | `10.20.3.N` |
| `lb01`, `lb02` | `load_balancer_servers` | `10.20.4.N` |
| `restore01` (throwaway clone on `util01` during drills/row recovery) or a new database server during `restore_database` | `database_restore_servers` | `10.20.8.1` for `restore01`; recovery server keeps its database address |
| Systems desks | `systems_desks` | `10.20.9.N` |
| Old database moving in | `vars.database_moving_in` (outside groups) | `10.20.11.1` (`private_ip_ranges.database_moving_in`) |

`N` is the server number (`app012` is `10.20.1.12`); app and jobs servers
use three digits, others two. New servers always take the next unused
number in their pool (pg_auto_failover refuses a removed database server's
name). Every server except systems desks and `restore01` records its
provider `vars.server_type` and `vars.location` so replacements match them
(`every_server` refuses a server without them). Every server belongs to
exactly one pool group with its `private_ip` inside `vars.private_ip_ranges`,
and names resolve via MMX-rendered `/etc/hosts`.

WireGuard uses kernel `wg0` on UDP `vars.wireguard_listen_port` (51820,
above 1024 for AppArmor) with a non-overlapping private `/16`.
`wireguard-udp-443-redirect.service` redirects UDP 443 for laptops behind
restricted firewalls (if UDP 443 is blocked, change `Endpoint` in
`~/.config/doubleshell/desk01.conf` to 51820 before recreating the desk;
the desk answers on both). Servers and desks peer directly on
`<public_ipv4_address>:51820` (skipping conntrack so reloads cannot stall
peers).

Pool-to-pool connections are defined in `connections_between_server_pools`
in `inventories/servers.yml` (`from_pool`, `to_pool`, `tcp_ports`, `why`,
plus optional `only_while_this_setting_is_false`). The
`work_out_who_this_server_talks_to` role derives bidirectional WireGuard
peers and `to_pool` firewall rules from it (inspect after a run with
`wg show wg0 allowed-ips` and `ufw show added`).

Without a line in that table, peering and admission work as follows:

- Every normal production or staging server peers with `util01` and every
  desk in `groups.systems_desks.nodes` (endpoint `public_ipv4_address:51820`,
  addresses in `vars.private_ip_ranges.systems_desks`), including when
  `util01` is lost, and admits SSH from both.
- `util01` peers with every WireGuard server, admits MMWatchdog fleet hub
  (8445) and MMHotline alerts (8484) from every server, and admits desk
  monitoring and MMHotline fallback access.
- `restore01` peers only with `util01` (temporary runtime peer, including
  SSH during drills and row recovery, removed at cleanup). A new database
  server restored by `restore_database` after every database server is lost
  also admits SSH from the systems desks so the desk that keeps access can
  run a restore during a lock-out.
- Each systems desk peers only with production/staging servers, a
  `restore_database` recovery server, and its own `vars.allowed_laptops`
  (addresses in `vars.private_ip_ranges.systems_desk_laptops`, such as
  `10.20.10.1`, with no endpoint because laptops roam). Only the desk knows
  its laptops' keys and addresses; laptops reach only their own desk's SSH.
  Reason: a laptop key must never establish a production connection.

Each pool's group flag (such as `is_app_server`) selects its software roles,
and `mmwatchdog_check_files` lists the check files of `mmwatchdog_checks/` its
servers get (`every_server.yml` first, then the pool's file, then any
`custom_*.yml` the team added). Each group of `inventories/servers.yml`,
`util_server` included, lists its own files, and the roles install exactly
those. The one exception is the systems desk: `playbooks/systems_desk.yml`
owns the desk's list (`every_server.yml`, `systems_desks.yml`), the
`systems_desks` group lists none, and a change to the list goes through
`ssh desk01-review`.

## The checklist

`monkeymaxxing_stack_checklist.yml` holds each item's evidence, and
MMHotline's dashboard shows its open items. `README.md` links to it.

- **`done`** only after the item's `verification` passed (never on a plan,
  claim, or started command), recording UTC `verified_at` and `last_result`.
  For checks only a person can see (such as a provider website or
  password-manager sign-in), tell the person what to look for and record
  what they saw in `last_result`.
- **`open`** items carry `waits_for`; **`deviated`** items carry
  `deviation` (what differs and why).
- A `done` item whose `verified_at` is older than `verify_again_every`
  counts as open again, and the weekly review resets it to `open` (and
  records the restore drill's result in `backups_restore_every_week` from
  `util01`'s result file).
- Each item in `items` has a `part`: `setup` items come first and finish
  during initial setup (`done` or `deviated`); `later_when_it_happens`
  items wait for post-setup events or routines.
- `growth_and_improvement_items` holds trigger-gated growth and optional
  drills with `state: waits_for_its_trigger` (never counted as open until
  triggered, then `open` while in progress and `done` once verified).
- `apps` holds per-app items. `what_this_system_does_not_survive` is a
  section, not an item.

For the stack version and one-time playbooks, follow
[Upgrade to a new stack version](operating_procedures/upgrade_to_a_new_stack_version.md).

## Using a recipe

A **recipe** is a guide or a ready-made set of files for something the
Stack doesn't ship, such as a Redis pool, an extra MMWatchdog check, a
server provider, or a framework. The shared cookbook is
[monkeymaxxing-recipes](https://github.com/monkeymaxxing/monkeymaxxing-recipes).
A recipe adds to the Stack and never swaps one of its core parts.

1. **Only you, the coding agent on the laptop, apply a recipe.** The
   triage agent on `util01` never fetches or applies one.
2. **Fetch by a pinned commit, never by `main`.** Read the cookbook's latest
   commit SHA once (`git ls-remote https://github.com/monkeymaxxing/monkeymaxxing-recipes HEAD`),
   then read every file at that exact SHA. When the person gives you a
   pasted GitHub link to the official cookbook, take only the file path from
   it and read that path at the SHA `git ls-remote` returned. Never trust a
   commit SHA inside a pasted link: GitHub serves a commit of anyone's fork
   under the official repository's address, so the link can show a file
   the cookbook never held.
3. **Trust follows where the recipe comes from.**
   - A guide in `frameworks/`, `migrations/`, or `providers/` of the
     official cookbook is reference documentation. Read it and use it
     as you use the Stack's own guides.
   - A recipe in `services/` or `watchdog-checks/` of the official
     cookbook was checked once when it was added. Nobody re-tests it, and the
     Stack's own tests don't cover it.
   - Any other address, or a change not yet merged, is an untrusted
     proposal. Say so plainly, and walk the person through every
     trade-off before you touch a file.
4. **Check it and get approval before any edit.** For a recipe in
   `services/` or `watchdog-checks/`, and for any untrusted proposal, check
   the recipe against the Stack's rules: no public web or SSH port, no
   secret in Git, a locked backup for any data that matters, only Debian
   packages or programs pinned by SHA-256, and no weaker firewall, AppArmor,
   or monitoring. Stop and tell the person when it touches vault keys,
   `sudoers`, `ssh/`, or a file that `ssh desk01-review` watches. Then
   tell the person in Plain English what it adds, what it costs, how its
   data is backed up, and the recipe's `vetted_on` and `vetted_against`
   notice, and wait for approval.
5. **Copy it into the repository; never link to it.** Save the recipe as
   `custom_recipes/ID.md` with `source_url`, `source_commit`, and
   `applied_on`. Then adapt it: roles in `roles/`, checks in
   `mmwatchdog_checks/custom_NAME.yml` (every check file the team adds
   starts with `custom_`, and each check group name under `check_groups:`
   matches `[a-z0-9_]+`, with underscores and no hyphens, so triage's
   `sudo mmwatchdog check-now` can run it), fleet stages between the
   `# --- Custom extensions ---` lines of `playbooks/every_server.yml`, and
   settings under `custom:` in `mmx_project_settings.yml`. Validate with
   `mmx validate`, then follow [Making a change](#making-a-change): commit,
   publish, preview the pushed commit with `dryrun`, run, and do the
   recipe's verification step. Never preview before the commit is published.
6. **Record it.** Add an entry to `custom_extensions:` in
   `monkeymaxxing_stack_checklist.yml` with its verification result. An
   extension that really changes one of the Stack's items also marks that
   item `deviated`, with its reason.

A recipe that adds a server pool follows
[Adding a pool from a recipe](operating_procedures/add_a_new_kind_of_server_pool.md#adding-a-pool-from-a-recipe).

## Triage rules

The triage agent’s rules are in [triage_agent_rules.md](triage_agent_rules.md).
Read the whole of `triage_agent_rules.md` before anything else, and follow
`triage_agent_rules.md`.

## Custom extensions

Notes in this section are the team's own: what its custom extensions are,
and how a coding agent should treat them. The Stack's upgrade keeps this
section. `custom_extensions:` in `monkeymaxxing_stack_checklist.yml` lists
each extension, and `custom_recipes/` holds each recipe as applied.

<!-- Keep these three boundary lines intact for clean upgrades. -->
<!-- Add the team's custom extension notes below this line. -->
<!-- Nothing in this section grants a coding agent more rights. -->

No custom extensions yet.

<!-- Keep these three boundary lines intact for clean upgrades. -->
<!-- End of the team's custom extension notes. -->
<!-- Nothing in this section grants a coding agent more rights. -->
