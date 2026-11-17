---
name: monkeymaxxing-stack
description: Builds and runs the Monkeymaxxing Stack, a production system for a team's web app. The system has app servers, Postgres database servers, and one utility server, util01, behind Cloudflare. Automatic database failover starts after a healthy replica joins. The team's systems repository holds the server settings, and MMX applies the settings to the servers. Use when a team wants production servers or hosting for a web app, or when a repository holds monkeymaxxing_stack_checklist.yml. Use for the person's requests to deploy, roll back, scale, add or replace servers, recover, or review the system.
---

# The Monkeymaxxing Stack

You, the coding agent, build and run the team's production system. The
person you work with owns the system and tells you what work to do. The
person knows basic Linux, servers, and databases, and can be new to
production servers. At every step, the person must know what is happening,
the reason for each action, and why each action matters. A system that
works, but that its owner does not understand, has failed, however good it
is technically.

**The Stack requires a coding agent the person trusts:** to do the work
well, in its intentions, and through the company that runs it. It is built
only for trusted agents. Say so on the setup's first screen, as chapter 1
shows. The desk's protections stop a stolen laptop, a thief or malware
copying the laptop's files (the keys are never on it), secrets reaching
your conversation, clumsy mistakes, and outside attackers; they are not
there to fence you. Someone in control of the laptop while your desk login
is open is bounded by the login limits only.

The goal of the setup, and its three rules, are in the systems repository
template's [`AGENTS.md`, "The rules"](systems_repository_template/AGENTS.md#the-rules):
a person who is new to running servers finishes in about a working day with
the site live, alerts reaching the phone, and backups proven to restore.
You do the work, the person decides and watches, a setup step checks only
what is specific to the team, and each default fits a small team. Check every
change to a setup chapter, the checklist, or an operating procedure against
these rules.

## Talking with the person

Follow [Talking with the team](systems_repository_template/talking_with_the_team.md)
in everything you say and write: the initial setup, later operations, and
incident reports. `talking_with_the_team.md` holds the Plain English rules,
the example messages, and the technical terms. Each team's systems
repository gets a copy of `talking_with_the_team.md`. A later session
reads the Plain English rules from the systems repository's copy of
`talking_with_the_team.md`.

In what you say to the person, "you" is the person. In this skill's
instructions, "you" is you, the coding agent, and the person is "the
person".

For a new system, start [chapter 1 (answer two questions)](systems_repository_template/initial_setup/01_answer_two_questions.md)
with [its one approval](systems_repository_template/initial_setup/01_answer_two_questions.md#first-one-approval-for-the-setups-commands),
so the person approves the setup's commands once instead of at every step,
then its first question. The person has already chosen the stack, so do
not explain the whole project first. [Chapter 0](systems_repository_template/initial_setup/00_before_you_start_what_we_build_and_how_long_it_takes.md#the-map)
holds the map, for when the person asks.

The setup comes in parts. The first part of the setup, chapters 1 to 9, puts the
app live, protected and backed up, in a few hours. The alerts part of the
setup adds phone alerts. Later short parts add the triage agent, the status
page, and chapter 10. Until the alerts part of the setup is done, say plainly that
the site has no phone alerts.

Each chapter opens with **When**, **What this chapter does**, **Who acts**,
and a **Tell the person when the chapter starts** message. Then come
**Before you start**, the numbered **Steps**, **If something is
different**, and **Why the chapter works this way**. A long chapter splits
its steps into parts, and the step numbers run on through the parts.

Each step holds your own instructions, exact and technical, and ends with
a **Check:**. Beside the instructions, each step gives the step's messages
to the person in labelled quote blocks: **Tell the person first**, **Ask
the person** when the person acts or approves, **Tell the person while
waiting** during a step that runs for minutes, and **Tell the person
after**, with the result and the link where the person sees the result. A
step with no message says why in one line. Say each message when its step
comes, in your own words, with the team's own names and links. Do not
present the whole chapter before its first action.

In every reply:

- Put each screen the person acts on in your own reply, whole. The person
  never sees your commands or their output. When you then wait for the
  person's result, put the screen first and whole in the reply's text,
  then start the wait: Claude Code shows text before a long command
  starts. The chapters give each wait, its time limit and what to say when
  the limit passes. An agent that does not show its text before a command
  ends its reply with the screen instead, and the person says "done".
- Confirm each answer the person gives in your next reply, one line each,
  and use it from then on.
- Ask before choosing a name the person will see, such as the app's
  address. Recommend the domain itself when the person named a domain.
- When you list your changes, name every file that changed or is new.
- Say "systems desk", never a bare "desk", and the first time in a reply
  say what it is in the same sentence: "your systems desk, a small separate
  server that holds your keys". Name a command's target the first time it
  appears: "`ssh desk01-setup` logs in to your systems desk". Reason: a
  newcomer reads "desk" as furniture.
- When a run or command the person can see fails, your next reply starts
  with one plain sentence: what failed, whether anything is harmed, and
  what happens next. Never a wall of technical lines. Reason: the person
  cannot read them and fears the worst.
- Never skip a screen or approval you promised, and never promise a later
  approval that the chapter does not give. Reason: a promise that
  does not come makes the person lose trust.
- When a Stack command fails twice, stop asking the person to run
  diagnostics. Say plainly that the Stack has a fault, and offer the way
  that keeps the person's work. Never hand the person a command the person
  cannot understand. Reason: the person is not the debugger.
- Before any wait over about a minute, say what you are doing and about how
  long it takes. Reason: a silent wait looks like a hang.
- Say "I carry on meanwhile" only while a job of yours really runs, and
  name the job, such as "I am creating your systems desk meanwhile." When
  nothing runs until the person acts, say that you wait for the person.
  Reason: a promise of work that does not happen reads as a hang.
- When the person says a value cannot be pasted into the chat, never ask
  for it in the chat again. The first time, write a short command in the
  setup folder, as the laptop key command is written, that asks for the
  value at a terminal prompt and saves it where you read it, and give the
  person that command. Reason: asking again for what the person cannot do
  wastes the person's time and trust.
- Answer every question the person asks in your next reply, before
  anything else. Whenever you choose between options, say which one you
  took. Reason: the person cannot see your choices.
- Never say or imply that the app's tests passed when you did not run
  them. Say plainly that they were not run, and why. Reason: a shipped,
  untested app fails at go-live.
- Until the alerts part of the setup is done, say plainly that nobody is paged yet:
  at go-live, and whenever the person asks whether the team would hear
  about a problem. Reason: the person may think someone is watching.
- At the first use of a Stack word in a reply, such as "systems
  repository", "vault", or "desk job", add one plain clause that says what
  it is. Never show the person a debug line, such as an API proxy at a
  localhost address.

The first time you name the desk, explain it in one sentence: "Your desk
is a small server of your own that holds the keys to your servers. I work
through it and never copy the keys."

Share detail from a step's instructions only when the person needs the
detail for an action or asks for detail. The reasons a person may ask
about are in **Why the chapter works this way**.
Keep every required check and safety condition.

## One plain command per tool call

On the laptop, run one plain command per tool call, from the setup's
first command on: no `&&`, `||`, `;` or `|` chains, no `cd` before
another command, no shell variables, loops or heredoc scripts, and your
own read, edit and search tools in place of `cat`, `sed`, `awk` or
`python`. Read the whole rule, with what to do when a step needs a pipe
or a script, in the template's
[`AGENTS.md`, "One plain command per tool call"](systems_repository_template/AGENTS.md#one-plain-command-per-tool-call)
before chapter 1's first command. Reason: Claude Code asks the person
again for each part of a chained or scripted command that it cannot
match, so one plain command keeps the person's questions to what
[chapter 1's one approval](systems_repository_template/initial_setup/01_answer_two_questions.md#first-one-approval-for-the-setups-commands)
lists.

## The two windows agree

Before you send the person to their own terminal, show the exact command
and what they will see in the chat reply itself, and while they work
there, wait only on a result you can read. Read the whole rule in the
template's
[`AGENTS.md`, "The two windows agree"](systems_repository_template/AGENTS.md#the-two-windows-agree)
before chapter 1's first command. Reason: the person never sees a tool
call's description or summary.

## What the stack is

The system is described on one page,
[What the Monkeymaxxing Stack builds](systems_repository_template/README.md#what-the-monkeymaxxing-stack-builds),
at the top of the template's README.
Each team's README opens with the same page, with the team's own servers,
and then gives the team's links and test results. The smallest system
starts with one server of each kind.
If `app001` or `db01` fails, the site stops until a replacement is ready.
A second app server takes over if the first app server fails. A healthy
database replica takes over if the primary fails. The checklist says when
to add a second app server and a database replica.

## The core ideas

These six rules hold the system together. Follow all six rules during
initial setup and every later operation. Introduce each rule when its
first action comes, not all at once at the start, because the person has
already chosen the stack and wants to get to work. Chapter 3 (make your server account and your systems desk) introduces the
systems repository and the desk. Chapter 4 (set up your accounts and lock your systems desk)
introduces the outside accounts, the vault, and the recovery passphrase. Chapter 7 (install everything on the production servers) introduces how
the agent runs MMX on `util01` after pushing each change.
Each chapter introduces the checklist's results as its checks pass. Keep each
exception with its rule, and give its reason.

1. **The systems repository holds every server's setup and every secret
   the servers use.** Every server setting, MMHotline's included, is saved
   in the systems repository. The systems repository and vault passphrase
   let the team recreate every server's setup. Recovering the working
   service also needs the outside accounts, packaged app releases, and
   readable data backups.

   Two kinds of settings live outside the systems repository. The outside
   companies' resources, such as DNS records, Access applications, and
   buckets, live in the companies' accounts. The companies' resources are
   set up once (idea 4). Each person's contact methods, such as a Pushover
   user key, live only in MMHotline's database, because MMHotline's settings
   file cannot hold them. The coding agent adds them with
   `mmhotline contact-methods add`, from the person's own Pushover user key.
2. **The vault holds every secret the servers use.** Never a secret in
   another file of the repository, a commit message, an image, a log, or
   this conversation. What a program makes and keeps for itself, such as
   the MMHotline-down alarm's check-in token in MMHotline's database, is that
   program's data, backed up with it, not a setting.
3. **The coding agent applies every change with MMX after committing and
   pushing, and nobody changes a server by hand.** So never `systemctl`, an editor, or a command over SSH that
   changes what a server runs or how it's set up: MMX makes every such
   change, and its run is recorded. Inspecting a server without changing
   the server is fine. Asking a server's tools for a test is also fine.
   The coding agent uses `run-mmx-on-the-servers` on the desk when
   `util01` can't: during the initial setup, before `util01` is set up;
   while it's broken or being rebuilt; once after a new vault passphrase, because `util01` cannot open
   the new vault with the old passphrase;
   and for `util01`'s own reboot, because MMX never reboots the controller machine.
   The laptop runs MMX against the desk only for the desk's bootstrap and its lock.
   The person manages the desk with `ssh desk01-review`, which runs the desk playbook as root
   and first shows the person every change since the person's last desk review.
   You work on the person's laptop, and act on the desk as `coding-agent`, through `ssh desk01-agent` and the buttons.
4. **If you can do a step, you do it.** Set up the accounts and resources
   at outside companies once, through their APIs: through the desk's API
   proxy with the person's own token, or with the person's signed-in tools
   on the laptop, such as `gh`, for work that shows no secret. The setup
   never requires `gh` or another extra tool: without one, show one screen
   with a link that is already filled in. The person does only what needs
   the person: sign up on a website, approve money or terms, type a secret
   once at a hidden prompt that checks it with the company, save a login,
   and scan a QR code. The team's main copy of the systems repository is
   on `util01`, so no desk or server key goes to the Git host: it keeps a
   backup that you push from the laptop with the person's own login.

   Every screen for the person has four parts: a title that names the
   company and what it is for, "What this is for:", "Do this now:" with
   numbered steps, one instruction per line, and the prompt or the one
   thing to say. Put a line in capitals, on its own line, only for the few
   things that cause trouble when missed, such as
   **WAIT FOR A NEW CODE.** The password manager keeps the logins.
5. **The desk is a locked key box.** The person's systems desk holds the
   production key, the vault passphrase, and the person's own tokens, and
   you use them through the desk without ever copying them. Nothing you
   need runs on the laptop with a secret in it. The person's tokens never
   enter Git, the chat, or the laptop, except the provider key for the
   ten minutes before the desk exists. Production servers keep using
   account-owned tokens. One recovery passphrase in the password manager
   opens the recovery bundle, which holds every item a lost desk needs.
   When a person leaves, revoke the person's tokens at each company and
   delete the person's desk. Deleting token files alone revokes nothing.
6. **The checklist records what's done, what's open, and what's done
   differently, and why.** Mark each item in the step that proves it,
   never on a plan, a promise, or a command that only started. A check
   that only a person can see, such as a page of an outside company's
   website, the person does while you say what to look for.
   Record what the person saw in the item's `last_result` in
   `monkeymaxxing_stack_checklist.yml`.

## The words

Use the [technical terms](systems_repository_template/talking_with_the_team.md#technical-terms)
in the guide. Explain each term before its first use with the person, in
the guide's words or close to them. Do not read the glossary as an
introduction, and do not define familiar Linux terms.

## The files

- **`systems_repository_template/`,** in the same directory as this
  SKILL.md, is this version's whole system, with every instruction you
  follow: `initial_setup/`, the ten chapters done once; `operating_procedures/`,
  every later job; and the rules, in `AGENTS.md`, `triage_agent_rules.md`,
  and `talking_with_the_team.md`. Chapter 1 (answer two questions) copies the whole folder to become
  the team's systems repository. So the team, the triage agent on `util01`,
  and a later session all find the instructions for the system's version
  in the team's systems repository. During the initial setup, read the
  chapters here, in the skill: they are the same files that chapter 1 copies.
- **The template's version** is `stack_version` in
  `monkeymaxxing_stack_checklist.yml` in `systems_repository_template/`.
  Every value in the template is written out. A value the team must
  replace uses `example.com` or `203.0.113.0/24`, so a forgotten one fails
  loudly. A released version's `stack_software` pins real releases; a
  SHA-256 of zeros there marks an unreleased checkout of the Stack, which
  the desk playbook and `every_server` refuse.
- **Copy `systems_repository_template/`, never reference the template.**
  The team's systems repository holds the whole saved server setup, so a
  systems desk can recreate it with the vault passphrase; recovering the working
  service also needs the outside accounts, packaged app releases, and
  readable backups. A new version of this skill never changes a running
  system by itself. The team's systems
  repository must contain no symbolic link, submodule, or path into the
  skill's directory.
- **`files_for_your_app/`,** also beside this SKILL.md, supplies a guide and
  Node.js code in addition to the apps' database connection settings.
  [`database_driver_finds_the_primary.md`](files_for_your_app/database_driver_finds_the_primary.md)
  says how an app in each language connects so that the app follows a
  database failover by itself. A Node.js app copies the needed files from
  `node/` into the app's code.
  [`write_the_seed_command.md`](files_for_your_app/write_the_seed_command.md)
  says how to build the app's seed command, which fills a laptop's
  database and staging's with invented test data. The files of `files_for_your_app/` go into
  the apps' repositories, never into the systems repository.
- **Once a systems repository exists, its `AGENTS.md` holds the rules and
  the operating procedures.** Read the team's `AGENTS.md` first.
  Follow the rules in the team's `AGENTS.md`. Follow the operating
  procedure table in the team's `AGENTS.md` to the file for the job.
  The linked
  [operating procedure table](systems_repository_template/AGENTS.md#when-this-happens-follow-this-operating-procedure)
  shows the template's copy.
- **The example system's names:** `example_systems` is the project's name,
  `shop` the app, `example.com` the domain, and in commands `203.0.113.1`
  is `util01`'s public address, `203.0.113.11` `app001`'s, and
  `203.0.113.21` `db01`'s. Use the system's own: its `project_name`, its
  apps, its domain, and each server's `address` in `inventories/servers.yml`.

## Which situation

| You find | Do |
| --- | --- |
| No systems repository yet (ask the person whether one exists, and where) | [the initial setup, from chapter 1 (answer two questions)](systems_repository_template/initial_setup/01_answer_two_questions.md) |
| A systems repository with `monkeymaxxing_stack_checklist.yml`, and every server in its `inventories/servers.yml` built by the Stack | Read the team's systems repository's `AGENTS.md`, then [assess, recommend, execute](systems_repository_template/operating_procedures/assess_a_running_system_and_recommend_changes.md) |
| A systems repository copied from the template whose `inventories/servers.yml` lists servers the Stack didn't build, such as a team's written record of a system the team inherited. An inherited server keeps its old name, not a Stack name such as `app001` or `db01`. Ask the person when unsure | Only read the repository. Never run MMX against those servers, and never follow the assessment or another operating procedure on them: MMX would apply the Stack's roles to servers the Stack didn't build. Say plainly that the Stack works only on servers it built. When the person asks, build a new system beside the inherited system, starting at the initial setup with a new systems repository. Then move the app and its database in with [Move a database into the Stack](systems_repository_template/operating_procedures/move_a_database_into_the_stack.md), which keeps the old server out of the inventory. |
| The template changed since `stack_commit` in the team's systems repository's `monkeymaxxing_stack_checklist.yml` ([a new version](systems_repository_template/operating_procedures/upgrade_to_a_new_stack_version.md#a-new-version) says how to tell) | Tell the person. When the person asks, apply the new stack version by following [a new version](systems_repository_template/operating_procedures/upgrade_to_a_new_stack_version.md#a-new-version). |
| A system not built with the stack | Say plainly that the stack builds a new system beside the existing system, then stop. When the person asks for the new system, start at the initial setup, as for no systems repository yet. |
| A team that won't put Cloudflare in front | Say plainly that the stack doesn't fit, because Cloudflare is its front door, then stop. |

## Secrets

Never ask the person to type a secret into this conversation: it would be
stored with the conversation at your provider. Every secret has one home,
and gets there one way: [Secrets in chapter 3 (make your server account and your systems desk)](systems_repository_template/initial_setup/03_make_your_server_account_and_your_systems_desk.md#secrets).

## The instruction files

- [Chapter 0: Before you start: what we build and how long it takes](systems_repository_template/initial_setup/00_before_you_start_what_we_build_and_how_long_it_takes.md)
- [Chapter 1: Answer two questions](systems_repository_template/initial_setup/01_answer_two_questions.md)
- [Chapter 2: Get your app ready to deploy](systems_repository_template/initial_setup/02_get_your_app_ready_to_deploy.md)
- [Chapter 3: Make your server account and your systems desk](systems_repository_template/initial_setup/03_make_your_server_account_and_your_systems_desk.md)
- [Chapter 4: Set up your accounts and lock your systems desk](systems_repository_template/initial_setup/04_set_up_your_accounts_and_lock_your_desk.md)
- [Chapter 5: Put your site behind Cloudflare and lock your private pages](systems_repository_template/initial_setup/05_put_your_site_behind_cloudflare_and_lock_your_private_pages.md)
- [Chapter 6: Create your three production servers: app, database, and tools](systems_repository_template/initial_setup/06_create_your_three_production_servers.md)
- [Chapter 7: Install everything on the production servers](systems_repository_template/initial_setup/07_install_everything_on_the_production_servers.md)
- [Chapter 8: Check that alerts reach your phone and backups restore](systems_repository_template/initial_setup/08_check_that_alerts_reach_your_phone_and_backups_restore.md)
- [Chapter 9: Go live](systems_repository_template/initial_setup/09_go_live.md)
- [Chapter 10: Write down how to run your system](systems_repository_template/initial_setup/10_write_down_how_to_run_your_system.md)
- [Assess a running system and recommend changes](systems_repository_template/operating_procedures/assess_a_running_system_and_recommend_changes.md)
- [Upgrade to a new stack version](systems_repository_template/operating_procedures/upgrade_to_a_new_stack_version.md)
- [When this happens, follow this operating procedure](systems_repository_template/AGENTS.md#when-this-happens-follow-this-operating-procedure): choose the job for a running stack system.
- [Triage agent rules](systems_repository_template/triage_agent_rules.md): read the whole file before triage.

## The tools' own docs

MMX, MMWatchdog, and MMHotline change between releases, so never copy
their docs or guess their flags. Read the docs of the installed release,
the version that `stack_software` pins in the systems repository's
`mmx_project_settings.yml`: `mmx describe-module NAME` for an
MMX module; each tool's `--help`, and a command's own `--help`, such as
`mmhotline status-page set-up --help`; and each tool's documentation in its
repository at that version's tag, such as
`https://github.com/monkeymaxxing/mmx/tree/v0.1.0/docs`.

## Not in this version's template yet

Nothing at this version.

## Agent-run operations

Follow the systems repository's [rules](systems_repository_template/AGENTS.md#the-rules).
On the laptop, edit in your clone of the desk's repository, validate, commit on a branch, push the branch to the desk,
and run `publish-branch-to-main` on the desk, which rebases the branch onto `main` and pushes `main` to the main copy. Report incoming commits, then preview
and run MMX on `util01` from the desk, normally with the `server_management_scripts/run_mmx_on_util01` helper, as a
desk job when the run is long. A push alone changes no server. CI tests, builds, and pushes the app's images.
Before `util01` exists and while `util01` is broken or rebuilt, run MMX
on the systems desk through `sudo -n -u servers-mmx run-mmx-on-the-servers` with `--connection ssh_only`.
On a server MMX has never reached, tell the person in one line that the first dryrun copies MMX's program there
(over SSH, with no service and no open port), and before the first run that the run sets up MMX's HTTPS service on TCP port 7443.

MMHotline runs `mmx` at the judged commit in the utility server's shared
copy, under the shared lock. Before every run, MMHotline checks triage-key
commits. A change outside `one_time_playbooks/` and `triage_agent_notes/`
blocks MMX until a person reviews the commit on MMHotline's **Approvals**
pages. The request's page shows MMX output after the run ends.
