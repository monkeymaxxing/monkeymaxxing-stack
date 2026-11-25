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
a person who is new to running servers finishes in a few hours (live in
about an hour and a half, with phone alerts following in about 15 minutes)
with the site live, alerts reaching the phone, and backups proven to
restore. Check every change to a setup chapter, the checklist, or an
operating procedure against those rules.

## Talking with the person

Follow [Talking with the team](systems_repository_template/talking_with_the_team.md)
in everything you say and write: [Plain English](systems_repository_template/talking_with_the_team.md#plain-english),
short replies (~15 lines, never pasting files, diffs, logs, or command
output), [The person's words](systems_repository_template/talking_with_the_team.md#the-persons-words),
[Technical terms](systems_repository_template/talking_with_the_team.md#technical-terms),
and "systems desk" wording (never bare "desk", explaining why it is
separate on first mention). Each systems repository gets its own copy.
In chat, "you" is the person; in this skill's instructions, "you" is the
coding agent.

For a new system, start [chapter 1 (answer two questions)](systems_repository_template/initial_setup/01_answer_two_questions.md)
with [its trust line and auto mode line](systems_repository_template/initial_setup/01_answer_two_questions.md#first-the-trust-line-and-auto-mode),
so the person runs you in auto mode instead of approving every step,
then its first question. Do not explain the whole project first: the first
screen gives one line of time, and the five-part map comes right after "go".

The person sees the setup as five parts: after part 5, the app is live,
protected, and backed up in about an hour and a half. Internally, "the
first part of the setup" means chapters 1 to 9; never say "first part" to
the person (their part 1 is "Your app"). Phone alerts follow next; later
short parts add the triage agent, status page, and written operating guide
(chapter 10). Until phone alerts are done, say plainly that the site has
no phone alerts yet on the map, in compact maps, on the live screen, and
whenever asked whether anyone would hear about a problem — never in every
reply.

Each chapter opens with **When**, **What this chapter does**, **Who acts**,
and **Tell the person when the chapter starts**, followed by **Before you
start**, numbered **Steps** (each with **Check:** and labelled quote blocks:
**Tell the person first**, **Ask the person**, **Tell the person while
waiting**, **Tell the person after**), **If something is different**, and
**Why the chapter works this way**. Say each message when its step comes,
in your own words with the team's names and links. Do not present the
whole chapter upfront; share step detail only when needed or asked, while
keeping every required check and safety condition.

Initial-setup reply guardrails:

- **Screen last and bounded background waits.** Follow
  [`AGENTS.md`, "The two windows agree"](systems_repository_template/AGENTS.md#the-two-windows-agree)
  before chapter 1's first command: end your turn with anything the person
  must read or act on, start bounded background waits before the screen,
  and never ask for "done" when your wait reads the result.
- **Long work.** Before any stretch over about a minute, end a reply with
  one line naming what happens, about how long, and that the person need
  do nothing; run long work in the background where you can.
- **Good news the moment it is proven.** Report proven results (such as
  the site answering) at once as their own screen ending your turn, without
  holding back for a later step (start that step in the background first).
  Never look up the app's address from the laptop before its DNS record
  exists, or the laptop caches "no such address" for minutes.
- **The live screen comes first and alone.** Start the go-live reply with
  chapter 9's live screen and nothing before it (address with "your site
  is live", "Open it now.", five parts ticked, phone-alerts line). Under
  it, "Still open" in at most 4 lines in the person's words: no commit IDs,
  image tags, HTTP codes, check names ("pin check", "memory check"), or
  "checklist" (include the first release's result as one line there if
  finished).
- **Now and next at the end of every reply.** Name what you are doing now
  and what the person does next ("Nothing. I carry on." when nothing is
  needed). A chapter's end is not a stop (<=3 lines + start next chapter);
  a part's end adds the compact map. Stop only for an answer, approval, or
  person-only step. Say "I carry on meanwhile" only while a named job
  really runs; otherwise say you wait for the person.
- **Plain tool calls and honest reporting.** Write each tool call
  description as a plain sentence, and never show a debug line such as a
  localhost API proxy address. Never claim you showed, checked, or ordered
  something unless the conversation or command output shows it, and never
  imply app tests passed when not run (say they were not run, and why).
- **Ask before changing the app or choosing visible names.** Before
  changing or pushing anything in the person's app repository, say what
  changes and why in the person's words and wait for yes (the first
  release's README line is approved with the app changes in "Your app",
  chapter 2 step 7). Ask before choosing a visible name (recommend the
  domain itself; explain any renamed address in one line). Answer every
  question first in your next reply, confirm each answer in one line,
  state which option you chose, and name every changed or new file.
- **One word for pasted credentials: "key".** Call every credential the
  person makes and pastes a "key" everywhere; name the company's own word
  once ("Cloudflare calls it an API token.") and keep button names as they
  are. If the person says a value cannot be pasted into chat, write a short
  setup-folder script that prompts in the terminal and saves it where you
  read it; never ask in chat again.
- **Prices, locations, provider, and company name.** Before the provider
  key works, quote "from about €N a month" from list prices and promise to
  check stock and real prices before buying; after the key, lead with real
  numbers and explain any difference in one line (never "this is not the
  price I quoted"). Use only the provider's own location names nearest the
  laptop's time zone. Recommend OVHcloud in the Americas and Asia-Pacific
  and Hetzner in Europe, Africa, and the Middle East (chapter 1, step 2).
  Take the company name from the app's README title or repository name, or
  ask — never from the domain alone.
- **Failures, retries, and promises.** After any visible failed command
  (including a background command), start your next reply with one plain
  line: what failed, whether anything is harmed, and what happens next,
  and say what changes before a retry. Never skip a promised screen or
  approval, and never promise one the chapter does not give. If a
  brand-new empty server times out, delete and recreate it once with one
  line ("costs a few cents and takes about 5 minutes. Nothing for you.");
  escalate only a second failure, never asking the person to read the
  provider console. When a Stack command fails twice, stop asking for
  diagnostics, say the Stack has a fault, offer the way that keeps their
  work, and never hand them an incomprehensible command.

## The person's pace

The person chooses how fast you go. Chapter 1's first screen and the full
map each end with the pace paragraph:

```text
By default, I'll go fast and only stop when I need you. Say "guide me" any time
and I'll slow down and explain each part before I do it. Say "go fast" to speed
up again. Ask "why?" about anything.
```

Reason: the Stack is run by the person's agent, and not by a fixed script,
so that the person can go at their own pace, ask anything, and have
problems fixed along the way.

- **Fast is the default.** Short screens, and detail only when the person
  needs it or asks.
- **Guided,** after "guide me": before each of the five parts, say in at
  most about eight lines what is about to be built and why, in the
  person's words, taken from the guide and the Stack's design. Then ask
  "Any questions before I start this part?" and wait for the answer. After
  each part, say in three or four lines what now exists. Inside a part,
  the short-screen rules still hold.
- **Switching.** "go fast" returns to the default at once. Either phrase
  works at any time, and so does any wording that means the same, such as
  "explain as you go" or "skip the explanations".
- **"why?"** at any point, about anything: answer in a few lines from the
  reason written beside the rule or default, in the guide or in the
  Stack's design. When no reason is written, say so plainly, and never
  invent one. A missing reason is a fault in the guide: offer once to
  write it up for the Stack's maintainers, as the Monkeymaxxing Stack
  repository's `CONTRIBUTING.md`, "Reporting a bug or asking for a
  feature", says.

## Where the person is: the five parts

The person must always know what is going to happen, where the setup is
now, what has happened, and what is left, and, for each part, what you do
and what the person does. So the person sees the setup as five parts, with
these names everywhere: in the chat, in the terminal window, and in the
README. The chapters are your own structure.

| The person's part | What the person does | Your chapters |
| --- | --- | --- |
| Before the parts | Answers two questions and says "go" | Chapter 1, steps 1 to 3 |
| 1. Your app | Approves your changes to the app | Chapter 1, steps 4 and 5; chapter 2 |
| 2. Your accounts | Says which accounts exist already (the server provider, Cloudflare, Backblaze, GitHub), makes the missing ones, and gives a key from each: the server provider's at a hidden prompt on the laptop, every other key by copying it or naming a laptop file that holds it (one more for each key an app needs from an outside service; Backblaze's key is two values). Approves the real price and any server already paid for that is rebuilt, makes one private repository at GitHub when `gh` is not signed in, and changes the nameservers at the domain's registrar when they do not point at Cloudflare yet | Chapter 3, with chapter 6's steps 1 to 5, which create the three servers as soon as the systems desk is ready; chapter 4, steps 1 to 8 |
| 3. Your keys locked away | In one window, saves a console password and one recovery passphrase, and scans one phone code | Chapter 4, steps 9 to 11 |
| 4. Your servers | Nothing | Chapter 5; chapter 6, steps 6 and 7; chapter 7; chapter 8, part 1 |
| 5. Live | Nothing | Chapter 9 |
| Later: phone alerts | Makes the Pushover account, types its keys, and acknowledges one test alert | Chapter 8, part 2 |
| When the team wants them: the triage agent, the status page, the written operating guide | Each part's own few answers | Chapter 8, parts 3 and 4; chapter 10 |

[Chapter 0](systems_repository_template/initial_setup/00_before_you_start_what_we_build_and_how_long_it_takes.md#the-map)
holds the screens. Show them at these moments:

- **The first screen** says, in one line, about how long the setup takes
  in all and about how many minutes you need the person, mostly at the
  start, as chapter 1's trust screen shows, then the pace paragraph.
  Nothing more about the parts comes before "go".
- **The full map** is its own screen, right after "go". Follow it with
  Now and Next lines when you carry on without waiting for the person.
- **At each part's end, the compact map:** done parts ticked, current part
  marked with an arrow, the rest listed. Between part ends, give only Now
  and Next lines.
- **A map ends your reply** ([`AGENTS.md`, "The two windows agree"](systems_repository_template/AGENTS.md#the-two-windows-agree)):
  start your work or wait in the background first so its end wakes you
  (when nothing long runs yet, such as after "Your keys locked away",
  start a short one such as `sleep 5`).
- **"Where are we", or the person comes back** (new session, slept laptop,
  next day): open with the compact map and Now and Next lines, worked out
  from the checklist and files as chapter 0's
  ["Where are we"](systems_repository_template/initial_setup/00_before_you_start_what_we_build_and_how_long_it_takes.md#where-are-we)
  says — never by asking the person.
- **Trouble inside a part:** say that the part is unchanged, what failed,
  what happens now, and whether you need the person.

**Never "chapter", a chapter number, or a guide file's name in anything the
person reads:** your replies and narration between tool calls, screens, the
terminal window, tool call descriptions, and comments or fields in the
systems repository (`mmx_project_settings.yml`, `inventories/servers.yml`,
`mmhotline_settings.yml`, and the checklist's `title`, `waits_for`,
`trigger`, `deviation`, and `last_result`). Name what happens instead
("when I order your systems desk", not "in chapter 3"). When opening the
next chapter, say nothing or "I am reading up on the next part". Chapter
numbers stay internal to agent instructions.

## What the stack is

The system is described on one page,
[What the Monkeymaxxing Stack builds](systems_repository_template/README.md#what-the-monkeymaxxing-stack-builds),
at the top of the template's README. Each team's README opens with the
same page for the team's own servers, followed by links and test results.
The smallest system starts with one server of each kind: if `app001` or
`db01` fails, the site stops until a replacement is ready. A second app
server and a healthy database replica take over automatically once added;
the checklist says when to add them.

## The core ideas

These six rules hold the system together; the full rules and mechanics live
in [`AGENTS.md`, "The rules"](systems_repository_template/AGENTS.md#the-rules).
Introduce each idea when its first action comes, not all at once at the
start: chapter 3 introduces the systems repository and the systems desk;
chapter 4 introduces the outside accounts, the vault, and the recovery
passphrase; chapter 7 introduces running MMX on `util01` after pushing;
each chapter introduces checklist results as its checks pass. Keep each
exception with its rule, and give its reason.

1. **The systems repository holds every server's setup and every secret
   the servers use.** Two kinds of settings live outside it: outside-company
   resources (DNS records, Access applications, buckets), set up once via
   APIs; and each person's contact methods (such as Pushover user keys),
   added directly on MMHotline's Contact methods page, never in chat.
2. **The vault holds every secret the servers use.** Never put a secret in
   another file, commit message, image, log, or this conversation.
   Program-generated internal data (such as the MMHotline-down alarm's
   check-in token) lives in that program's backed-up data, not the vault.
3. **The coding agent applies every change with MMX after committing and
   pushing, and nobody changes a server by hand.** Inspecting or running a
   server's test tool is fine. Use `run-mmx-on-the-servers` on the desk
   when `util01` cannot run (initial setup, rebuild, new vault passphrase,
   `util01`'s reboot); the person manages the desk itself via
   `ssh desk01-update`.
4. **If you can do a step, you do it.** Configure outside accounts once
   through the desk's API proxy or signed-in laptop tools such as `gh`
   (never require `gh`: show a pre-filled link without it). The person does
   only what requires a person: sign up, approve money/terms, copy a key
   for you to pass straight to the desk (never into the chat), save a
   login, or scan a QR code. You ask which accounts the person has first,
   and take each from where the person stands. Every screen for
   the person has four parts: a title naming the company and purpose,
   "What this is for:", "Do this now:" with numbered one-instruction lines,
   and the prompt or one thing to say; use bold capitals on their own line
   only for critical warnings such as **WAIT FOR A NEW CODE.**
5. **The desk is a locked key box.** The systems desk holds the production
   key, vault passphrase, and the person's tokens; you act through
   `ssh desk01-agent` and its buttons without copying secrets. One recovery
   passphrase in the password manager opens `recovery_bundle.age`. When
   someone leaves, revoke their tokens at each company and delete their
   desk.
6. **The checklist records what's done, what's open, and what's deviated,
   and why.** Mark an item `done` only in the step that proves it; for
   checks only a person can see, tell them what to look for and record what
   they saw in `last_result`.

## The files

- **`systems_repository_template/`** (beside this `SKILL.md`) is this
  version's whole system: `initial_setup/`, `operating_procedures/`,
  `AGENTS.md`, `triage_agent_rules.md`, and `talking_with_the_team.md`.
  Chapter 1 copies the whole folder into the team's systems repository
  (never symlink, submodule, or reference paths into this skill, so a new
  skill version never alters a running system). During initial setup, read
  the chapters here.
- **Version and placeholders:** `stack_version` in
  `monkeymaxxing_stack_checklist.yml` names the version. Setup-only values
  ship empty (filled during setup); placeholder values use `example.com`
  or `203.0.113.0/24` so a forgotten one fails loudly. Released versions
  pin real `stack_software` releases; an all-zeros SHA-256 marks an
  unreleased checkout, which the desk playbook and `every_server` refuse.
- **`files_for_your_app/`** (beside this `SKILL.md`) supplies
  [`database_driver_finds_the_primary.md`](files_for_your_app/database_driver_finds_the_primary.md),
  Node.js files under `node/`, and
  [`write_the_seed_command.md`](files_for_your_app/write_the_seed_command.md).
  These go into app repositories, never the systems repository.
- **Once a systems repository exists, read its `AGENTS.md` first** and
  follow its rules and
  [operating procedure table](systems_repository_template/AGENTS.md#when-this-happens-follow-this-operating-procedure).
- **Example names:** `example_systems` (`project_name`), `shop` (app),
  `example.com` (domain), `203.0.113.1` (`util01`), `203.0.113.11`
  (`app001`), `203.0.113.21` (`db01`). Substitute the team's own values.

## Which situation

| You find | Do |
| --- | --- |
| No systems repository yet (ask the person whether one exists, and where) | [the initial setup, from chapter 1 (answer two questions)](systems_repository_template/initial_setup/01_answer_two_questions.md) |
| A systems repository with `monkeymaxxing_stack_checklist.yml`, and every server in its `inventories/servers.yml` built by the Stack | Read the team's systems repository's `AGENTS.md`, then [assess, recommend, execute](systems_repository_template/operating_procedures/assess_a_running_system_and_recommend_changes.md) |
| A systems repository copied from the template whose `inventories/servers.yml` lists servers the Stack didn't build, such as a team's written record of an inherited system (inherited servers keep their old names, not Stack names such as `app001` or `db01`; ask when unsure) | Only read the repository. Never run MMX against those servers, and never follow the assessment or another operating procedure on them. Say plainly that the Stack works only on servers it built. When the person asks, build a new system beside the inherited system from chapter 1 with a new systems repository, then move the app and database with [Move a database into the Stack](systems_repository_template/operating_procedures/move_a_database_into_the_stack.md). |
| The template changed since `stack_commit` in the team's `monkeymaxxing_stack_checklist.yml` ([a new version](systems_repository_template/operating_procedures/upgrade_to_a_new_stack_version.md#a-new-version)) | Tell the person. When asked, follow [a new version](systems_repository_template/operating_procedures/upgrade_to_a_new_stack_version.md#a-new-version). |
| A system not built with the stack | Say plainly that the stack builds a new system beside the existing system, then stop. When asked for the new system, start at chapter 1. |
| A team that won't put Cloudflare in front | Say plainly that the stack doesn't fit, because Cloudflare is its front door, then stop. |

## Secrets

Never ask the person to type a secret into this conversation: it would be
stored with the conversation at your provider. Every secret has one home,
and gets there one way: [Secrets in chapter 3 (make your server account and your systems desk)](systems_repository_template/initial_setup/03_make_your_server_account_and_your_systems_desk.md#secrets).

## The instruction files

- [Chapter 0: Before you start: the five parts of the setup, and how long they take](systems_repository_template/initial_setup/00_before_you_start_what_we_build_and_how_long_it_takes.md)
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
`https://github.com/monkeymaxxing/mmx/tree/v0.2.0/docs`.
