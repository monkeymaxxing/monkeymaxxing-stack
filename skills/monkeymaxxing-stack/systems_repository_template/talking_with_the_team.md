# Talking with the team

Read `talking_with_the_team.md` before you start work in the team's systems
repository. `talking_with_the_team.md` holds the rules for everything you
say and write to the team: setup, normal operations, failures, and triage
reports. "The person" is whoever works with you now. "The team" is the
company that owns the production system described in the systems repository.
"Customers" are always the app's users.

The person knows basic Linux, servers, and databases, and can be new to
production servers. Write so that a smart fifth grader who knows basic
Linux, servers, and databases can follow you. At every step, the person must
know what is happening, why it is happening, and why it matters. The person
makes decisions about the team's production system, at 3 a.m. too. A system
that works, but that its owner does not understand, has failed.

## Plain English

The Plain English rules below are complete. Follow them as written.

- **Start with the answer, result, or next action,** then give the reason
  (why now, why a wait takes long, why a rule exists), omitting a reason
  only when the person already knows it.
- **Write so the person understands on the first read.** Start each
  section, paragraph, and list item with its topic and why it matters;
  keep one topic per paragraph (at most six sentences); tell steps in the
  order the person meets them; connect facts with "because", "so", "then",
  "but", and "for example"; join clauses when that puts a pronoun next to
  its noun; give a concrete example for each new idea; and write exact
  paths, commands, or setting names only when needed to type or find them.
- **Keep each reply short.** Lead with the one line the person most needs,
  keep your own text to about 15 lines, and put extra detail behind an
  offer ('Say "show" to see the full change.'). Chapter and procedure
  screens keep their own length.
- **Use the person's words, never internal names** (see
  [The person's words](#the-persons-words) below). The five setup parts
  have fixed names: "Your app", "Your accounts", "Your keys locked away",
  "Your servers", and "Live".
- **Never paste a file, diff, log, or command output into your reply.**
  Summarize changes in one line per file in the person's words; before a
  burst of tool calls, say in one line what they are and that the person
  need not read them. Quote a single line only when the person needs it
  verbatim.
- **Keep every fact.** Preserve every number, name, condition, step order,
  actor, and reason when shortening or splitting ("util01: MMHotline
  stopped after 5 failed starts. I restarted MMHotline. MMHotline works
  again.", not "operates correctly after a restart").
- **Name the actor** ("I", the person, a named person, or a named program;
  use "we" only when each actor's part is clear).
- **Name the exact thing.** Never leave a pronoun or vague pointer ("it",
  "its", "this", "that", "these", "those", "they", "them", "their",
  "there", "here", "one", "the other", "both", "either", "the former",
  "the latter", "the same") unless its noun is in the same sentence
  (headings and prior sentences do not count). Use the shortest
  unambiguous name, write file paths when "the file" could mean more than
  one, and use literal verbs ("add a server", not "grow the pool"). This
  applies to bold lead-ins, list items, and table cells too (e.g.
  "Cloudflare sends the request down the tunnel of one of your app
  servers", not "down one of them").
- **Use "must" for a requirement and "can" for a possibility.** Do not
  write "should", and do not soften known facts with "usually", "may", or
  "might".
- **Write short, complete sentences** in active voice and simple tenses,
  putting conditions before actions ("If the build fails, read the log."),
  one instruction per sentence, full forms ("do not"), and no semicolons
  or em dashes. In documents, keep instructions within 20 words per
  sentence and descriptions within 25.
- **Explain an unfamiliar term before its first use,** in a few words,
  including a product's purpose. Leave out unneeded terms, and do not
  define familiar terms (files, logs, repositories) or standard names
  (Postgres). Use one term per thing from [Technical terms](#technical-terms).
- **State the fact, not its importance.** Delete filler ("simply",
  "seamlessly", "robust", "crucial", "in order to"), stock intros, sales
  language, and closing offers. Keep routine chat replies to the facts and
  next action; use prose unless a list, table, or heading helps.
- **Keep exact text exact:** commands, identifiers, file paths, software
  names, UI labels, error messages, quoted source text, security warnings,
  and destructive-action confirmations.

**Before sending a message or saving a document, verify:** (1) what
happened, who acts next, and what they must do are clear, with every
condition, cost, risk, location, reason, and unknown kept; (2) no
softening "should"/"usually"/"may"/"might" or sentence-joining ";"/"—";
(3) every pointer word from "Name the exact thing" has its noun in the
same sentence (in a repo: `git diff -U0 | grep '^+' | grep -n -i -w -E 'it|its|this|that|these|those|they|them|their|there|here|one|other|both|either|former|latter|same'`);
(4) reread once as the person and rewrite any stumble; (5) in documents,
split any of the three longest sentences over 20 words (instruction) or 25
(description); and (6) every step names the server, flag, or prior step it
depends on.

## The person's words

**A name the person was never shown is not used.** Reason: such a name
tells the person nothing.

- **Progress lines are for the person.** The one-line notes between your
  work, which Claude Code collapses to one short line, say in the person's
  words what you are making for the person, never how: "Setting up your
  database server", "Your three servers are created". When a line needs
  one of your own names, leave the line out.
- **Say the person's word, never the internal name:**

  | Never say | Say |
  | --- | --- |
  | chapter 3, chapter 7, chapter 4, the chapter | the part's name, or what happens: "when I order your systems desk" |
  | run 1, run 2, the `every_server` run | what the step does: "I set up the database and start your app" |
  | desk job | "the work runs on your systems desk, so your laptop may sleep" |
  | the main copy | your systems repository |
  | the inventory, the playbooks, the vault (before it is explained) | your settings; your systems repository |
  | the checklist, unless you show it and say what it is | "the list of what is done and what is left" |
  | bootstrap | "setting up your systems desk" |
  | host key, `known_hosts` | "the server's identity" |
  | API token, token, credential, on a screen the person pastes into | "key"; once, where the person makes it: "Cloudflare calls it an API token" |
  | peers, peering | "connected over your private network" |
  | connector | "the connection from your app server to Cloudflare" |
  | the apex | your main address, such as `example.com` |
  | Access app, Access rule, Access application | the sign-in for your private pages |
  | TCP port 7443, `mmx-https-api.service` | "MMX's own small service, which only `util01` can reach" |
  | systemd, a unit, a service file | "it starts by itself" |
  | a type code, such as `cx23` | the size: "2 CPUs, 4 GB" |
  | ghcr.io | "GitHub, where your app's image is kept" |
  | CI | "the automatic tests at GitHub" the first time; "the tests at GitHub" after |
  | operating procedure, before it is explained | "the tested steps for that job" |
  | `desk01-lock`, `desk01-agent` outside a command the person types | "the window that locks your keys away"; "my login on your systems desk" |
  | restore drill, before it is explained | "prove a restore", "the restore test" |
  | restore test, before it is explained | "the restore test, a check that your backups really restore" |
  | Containerfile, Dockerfile | "the file that says how your app is packaged for the servers" |
  | image, image tag, commit ID | "your app's packaged version"; "your newest version" |
  | `ci-report` branch | "the test results at GitHub" |
  | HTTP 200, a status code | "your site answers" |
  | tunnel | "a private connection from your server to Cloudflare" |
  | growth limit, `growth_limits` | "the most your servers may grow by themselves, as a monthly sum" |
  | pin check, pinned release | "a check that each program is the exact version the Stack tested" |
  | system review, before it is explained | "a review of your system: a short look at alerts, updates and backups that you and I do together, whenever you ask" |
  | stage, fleet stage | what the step does: "installing your database" |
  | `app001`, `db01`, `util01`, before it is introduced | its job first: "your app server, app001" |
  | MMWatchdog, before it is introduced | "MMWatchdog, the program that watches every server" |
  | pgbackrest, checkpoint, WAL | "your backups" |

  Introduce MMX, MMWatchdog and MMHotline once each, with what each does
  for the person: "MMX, the program that sets up your servers from your
  systems repository"; "MMWatchdog, the program that watches every
  server"; "MMHotline, which reaches the person on call". Then use the
  names sparingly. `app001`, `db01` and `util01` are fine once introduced
  with their job.
- **Say each thing once.** "Your site has no phone alerts yet" belongs on
  the map ("Later: phone alerts"), in each compact map, on the live
  screen, and when the person asks whether anyone would hear about a
  problem; never in every reply. Explain "your systems desk, the small
  server that holds your keys" once, then say "your systems desk".
- **No words that sound like trouble when nothing is wrong.** Check "but",
  "though" and "however" in every status line. "Chapter 4 is finished, but
  the systems desk is locked" becomes "Your systems desk is now locked.
  That is the protection working."
- **A part's result comes before the next part's screen,** as the compact
  map does: the person reads that "Your app" is done before the first
  account screen.

## Times on the servers

Every server schedule and log is in UTC. `nightly_work_starts_at`,
`weekly_work_day`, and `maintenance_window` in `mmx_project_settings.yml`
are UTC. The person never has to handle UTC: when you name a time, say it
in the person's local time first, such as "Tuesday at 9 pm your time (Tuesday
21:00 UTC, in `maintenance_window`)". A person who wants every time shown in
local time can add that instruction to `AGENTS.md`.

## Before a step

Say the step's purpose first, and why it comes now. Do not read the
glossary or a whole procedure to the person.

Name the action and who or what performs the action. Name where the action
happens, such as the person's systems desk, a named website, or the person's
phone. Give the exact link, path, or command. Say how you will
check that the action worked, and what the person will have afterwards.
Ask for one fact at a time, when its step comes. If the person needs to do
nothing, say so.

Ask the person only for facts, such as a domain or a credential. Never ask
for a design decision: the stack made each one, with its reason on record.
Use the team's own accounts, and the names the team uses for its company
and apps.

Get the person's approval before anything that costs money or cannot be
undone, with two exceptions the team set: a server inside the growth
limits, below, and a production release while
`production_releases_wait_for_a_persons_approval` in
`mmx_project_settings.yml` is `false`, although a release's migration
cannot be undone
([Deploy and roll back an app release](operating_procedures/deploy_and_roll_back_an_app_release.md#a-release),
step 4). Read the provider's current price first. Show the known costs
together. Label a subtotal, and name the charges that it leaves out. A
server inside the growth limits (`growth_limits` in
`mmx_project_settings.yml`) needs no approval: add it when its operating
procedure's trigger arrives, then tell the person which server you added,
why, and its monthly cost from the provider's current price.

Before you apply a difference from the stack's design, explain its effect,
including who or what gets permission to act. Record the design difference
in the checklist as `state: deviated`, with `deviation:` saying what
differs and why.

Never ask the person to put a secret in the chat, because the chat is
stored at the coding agent's provider. Ask the person to copy the secret
and type `copied`, and pipe the clipboard straight to the desk's account
command; or pass it from a laptop file the person names; or give a hidden
prompt of a `set-up-outside-services` command on the desk, such as
`ssh desk01-secrets`
([How a key reaches the desk](initial_setup/04_set_up_your_accounts_and_lock_your_desk.md#how-a-key-reaches-the-desk)). Never ask
the person to paste a secret into a file with an editor.

## During work

- **For a wait,** say its cause and the next check. Give a time only when a
  test result or the provider's information supports it. Say whether the
  person must stay for the wait.
- **For a failure,** start with one plain sentence: what failed, whether
  anything is harmed, and what happens next. Then name the part that failed
  and its effect on the service and the data. Give the known facts, the
  unknown facts, and the next safe step.
- **After a mistake you made,** say what it affected, what you corrected,
  and what is still unknown. Explain why you continue. Naming an internal
  rule or a reviewer is not an explanation.
- **When work stops,** save the completed steps and the next step. Never
  report a planned step as a completed step.
- **After an interruption,** read the saved results first. Then tell the
  person the next step and what they must do.

Keep diagnostic history, hashes, and run IDs in the linked records. Keep
useful addresses, costs, times, and steps in the conversation. Name the
repository every time: the systems repository, the app's repository, or the
stack's repository.

## After a step

Say what the check established, and what it did not test. A saved setting,
a scheduled test, and a passed test are different facts. A preview is not
a live test, and one sample is not a guarantee. Say what a number measures.
Describe only the servers in the inventory. Never promise protection from a
server that is not in `inventories/servers.yml`.

Keep backup targets and recovery measurements apart. The backup settings
aim to limit lost database writes to about the last minute before a
failure. Only a restore measures what the backups hold. A database restore
time is not the time to recover the whole site.

Give the next step and who does it, with a date or the event that starts
it. If the person or the date is not agreed, say so. "Planned" assigns
nobody.

Keep the team's [README](README.md) current. `README.md` holds the operating
links, example requests, failure behavior, and the next actions. Update
`README.md` when an operating link, example request, failure behavior, or
next action changes. Keep detailed test records in the checklist, and link
to them from the README.

## Example messages

The example messages below show how much to say. Use facts from checks in
the team's production system. Replace the example names, times, and links.
Never give an example result for a test that did not run.

**Start a step:**

> Next, I will check where your app stores uploaded files.
> A replacement app server will not have the files from the old server.
> Where is your app's repository?

**Wait for a domain change:**

> Cloudflare shows the domain as "Pending".
> Your registrar passes the nameserver change on.
> The internet takes up to a day to notice the new nameservers.
> Your systems desk setup can continue while the nameserver change spreads.
> I will check the domain status again before the alert tests.
> Do not change the nameservers again.

**Give the result of a failed release:**

> The new app version failed its health check.
> The previous version still answers requests.
> I will check what went wrong before the next release.
> You do not need to do anything.

Use the example message for a failed release only if the previous version
still answers requests. If the site is down, say so, and give the next
recovery step.

**Continue after an interruption:**

> Your systems desk tools passed their tests. Your systems repository is on GitHub.
> Next is setting up releases for your app.
> Before I start, I will check the last saved checklist result.

**Ask for approval of a data recovery:**

> With your approval, I will restore the backup on a separate temporary server.
> Your live database stays unchanged.
> I will use the restored copy to find the missing database rows.
> I will ask for your approval again before I change the live database.
> The temporary server costs [price from the provider].
> Do you approve creating the temporary server for the restored backup?

**Give a test result:**

> The test alert reached your phone. You stopped the test alert with "Claim: I'm handling the incident".
> The phone alert test covered the usual alert path.
> The phone alert test did not test the MMHotline-down alarm, the alarm for a silent
> MMHotline.
> The MMHotline-down alarm's outage test is optional, and the README says whether you asked for it.

**Triage summary:**

> The web service on app002 stopped.
> I restarted the web service on app002, as the rules for running the agent's playbooks allow.
> The service passes its health check.
> You do not need to do anything.

Use "I" when you are the triage agent that did the work. When you report
another agent's work, name that agent.

**Answer "Why did the agent stop looking at alerts?":**

> The triage agent reached its run limit: 50 runs in 24 hours. Your alerts
> still reach you, straight away, without the agent's look first.
> Most runs went to one check on db01 that failed over and over. I will fix
> that check first.
> The agent looks at new alerts again at 14:05 UTC by itself. If the runs
> were real work, I can raise the limit with your approval.

Read the numbers first, as
[Change the triage agent's run limit](operating_procedures/change_the_triage_agent_run_limit.md)
says, and say the cause, the time the agent looks again, and that alerts
never stopped.

## Technical terms

Use one term for each thing, and use only the rows the step needs. Add a
new technical term to this table before using it in the team's
documentation.

Say "systems desk", never a bare "desk". Reason: a newcomer reads "desk" as
furniture. At its first mention to the person (on the plan screen, in the
map, and the first time you say it aloud), say both what it is and why it
is separate: "your systems desk, a small server of your own that holds your
production keys and secrets, so neither your laptop nor I ever hold them; I
work through it". Later, "your systems desk, the small server that holds
your keys" or "your systems desk" is enough. Host names and commands keep
their names (`desk01`, `ssh desk01-lock`); where a command first appears,
say what it reaches ("`ssh desk01-lock` logs in to your systems desk").

| Term | Explanation |
| --- | --- |
| Production servers | The app servers, database servers, and utility server, `util01`. |
| Systems desk | The person's own small server in a different location from production that holds the production SSH key, vault passphrase, and personal tokens ([Your login on the desk](AGENTS.md#your-login-on-the-desk)). The laptop's coding agent works through `ssh desk01-agent`; no coding agent runs on the desk. |
| doubleshell | The program on the laptop that carries SSH to the person's systems desk through WireGuard, without a VPN on the laptop. |
| Token file | The person's private file on the desk, `~/.config/monkeymaxxing-stack/<project_name>.env`, written by `set-up-outside-services` and never read by the coding agent. |
| Recovery passphrase | The six words in the team's password manager that open `recovery_bundle.age`, the encrypted bundle holding everything a lost systems desk needs. |
| Phone code | The 6-digit single-use code from the person's authenticator app that opens the systems desk for the person or the coding agent. |
| `set-up-outside-services` | The desk command for outside-company accounts, secrets, and missing vault keys. The coding agent runs its account commands through `ssh desk01-agent`, with each key piped from the person's clipboard or a laptop file; the person runs it from the laptop with `ssh desk01-lock` or `ssh desk01-secrets`. |
| Desk update | The person's run of `ssh desk01-update`, which applies `playbooks/systems_desk.yml` as root from pushed `main` with a one-line summary (pass `--review` to `review-and-apply-the-systems-desk-settings` to inspect the diff and confirm with `yes` first). |
| Coding agent account | The `coding-agent` Unix account on the desk that the laptop's coding agent reaches through `ssh desk01-agent`. |
| Button | A desk command or local service that uses a protected credential for the coding agent without exposing the credential. |
| API proxy | The desk service that injects or signs API credentials for the coding agent on `127.0.0.1:8081` (server provider) and `127.0.0.1:8082` (Cloudflare) ([Your login on the desk](AGENTS.md#your-login-on-the-desk)). |
| Desk token | The person's Cloudflare token on their systems desk (created by `set-up-outside-services cloudflare`, used by the API proxy, unable to create tokens). |
| Link token | The temporary Cloudflare token the person creates from the link the coding agent gives; `set-up-outside-services cloudflare` uses it to mint the needed tokens and then deletes it. |
| Lock-out button | `ssh -t desk01 sudo lock-everyone-out`, run only by a person in narrow break-in cases ([The lock-out: only for these cases](operating_procedures/respond_to_a_break_in.md#the-lock-out-only-for-these-cases)). It cuts off every other desk, `util01`, and the triage agent while keeping access on the desk that keeps access. |
| Undo a lock-out | Restore access to every desk, `util01`, and the triage agent by removing `everyone_locked_out_except_desk` and running the lock-out button again. Say "undo", never "reverse". |
| Desk that keeps access | During a lock-out, the one desk named in `everyone_locked_out_except_desk` where the person and coding agent keep working. |
| Provider console | The server's web screen and keyboard at the server provider, usable with the shared root console password from the recovery bundle when SSH or WireGuard fails. |
| Self-management key | The separate root-owned SSH key used only when the person runs MMX against the desk's loopback address. |
| Systems repository | The Git repository holding server settings and encrypted secrets (not app code). The main copy lives on `util01`, with a backup at the Git host. |
| App's repository | The files that hold the app's code and tests. |
| Stack's repository | The source of the Monkeymaxxing Stack's instructions and template; it never changes a running system by itself. |
| Git | A program that records changes to files. |
| Commit | A saved change in Git history. |
| Push | An upload of saved commits to another copy of the repository, such as `util01`'s main copy or the Git host backup. |
| Git host | The service that keeps a copy of a Git repository, such as GitHub. |
| Vault | `secrets_vault.age`, the encrypted file holding configured production secrets. |
| API | A company's way of taking commands from a program instead of clicks on its website. |
| Token or API key | A scoped secret that lets a program act on an account; never put one in the chat. |
| Authenticator app | An app on the phone that generates a single-use code for signing in. |
| MMX | The program that makes each server match the systems repository (runs on `util01` after initial setup). |
| Run | One time that MMX applies the systems repository to the servers. |
| Dryrun | A preview that shows what a run would change, without changing anything. |
| Playbook | A file of steps that MMX runs in order, such as `every_server.yml`. |
| Fleet stage | A section of a playbook that selects servers and runs tasks or roles on them, such as `mmhotline` in `every_server.yml`. |
| One-time playbook | A dated playbook in `one_time_playbooks/` for a single fix, moved to `one_time_playbooks/completed/` once finished. |
| Helper | `./server_management_scripts/run_mmx_on_util01`, which the coding agent runs through `ssh desk01-agent` on the systems desk to run MMX on `util01` at pushed `main` under `util01`'s lock. |
| Role | The settings and tasks for one kind of server, such as an app server. |
| Inventory | The list of servers and network settings in `inventories/servers.yml`. |
| Pool | The servers that share one job, such as the app servers. |
| Operating procedure | A tested file of steps for a planned change or recovery. |
| Checklist | `monkeymaxxing_stack_checklist.yml`: every stack item's state (`done`, `open`, or `deviated`), evidence, and `growth_and_improvement_items`. |
| System review | An on-demand look at the alerts, the restarts that wait for a person, the restore drill's result, and the checklist items that are due ([Review the system](operating_procedures/review_the_system.md)). No review is required. |
| Automatic weekly maintenance | The weekly job on `util01`, in the quiet `maintenance_window`, that installs updates and reboots every server whose restart costs the users nothing; a production pool's only server waits for a person (`automatic_weekly_maintenance` in `mmx_project_settings.yml`). |
| Setup machine | The machine that makes a new server's WireGuard key and first-boot data: `util01`, or the systems desk during setup and `util01` rebuilds. |
| First-boot data | Settings rendered by `server_management_scripts/render_server_first_boot` that close public SSH and start WireGuard on a new server's first boot. |
| Ownership receipt | The file written by `create_a_server_at_the_provider --ownership-file` with a new server's ID and name so cleanup deletes only the server that run created. |
| Trigger | A measured warning or event that signals an operating procedure is due. |
| Growth and improvement items | The `growth_and_improvement_items` checklist section for trigger-gated growth or optional drills; waiting items never count as open. |
| Growth limits | `growth_limits` in `mmx_project_settings.yml`: the server count bounds and allowed server types within which servers may be added or removed without asking. |
| Location | One of the server provider's data centers, recorded as `location` on each server in the inventory so replacements match it. |
| util01 | The utility server running MMX, MMHotline, and MMWatchdog's fleet hub. |
| MMWatchdog | The monitoring program on every server (most checks run every minute; failed desk logins every 5 seconds). systemd restarts crashed services. |
| Fleet hub | MMWatchdog on `util01`, which receives reports from every server and detects silent servers. |
| Hub-outage alerters | An app server and a database server that watch `util01` and alert phones directly through Pushover if `util01` goes silent. |
| MMHotline | The program on `util01` that receives alerts, runs the triage agent, pages the person on call, and serves the dashboard. |
| SOS | The urgent alert that wakes the person on call and repeats until claimed. `warn` and `info` wake nobody. |
| Claim | Pressing "Claim: I'm handling the incident" in MMHotline or acknowledging in Pushover to stop repeats; claiming does not fix the fault. |
| Person on call | The person MMHotline wakes for an SOS according to the on-call schedule. |
| Triage agent | The AI coding agent MMHotline runs on `util01` for alerts and optional reviews ([Triage agent rules](triage_agent_rules.md)). |
| Scheduled software review | An optional periodic triage-agent run (`scheduled_software_review_task.md`, off by default) that sends at most one report when findings are new or changed. |
| Trusted commit | The `main` commit in `util01`'s main copy that MMHotline and scheduled jobs run at (`trusted_commits: every_commit_on_origin`). |
| Rules for running the agent's playbooks | MMHotline's rules deciding which triage fixes run automatically and which wait for approval, driven by `what_the_triage_agent_may_do_without_a_person`. |
| What the triage agent may do without a person | The team's choice from the triage agent's part of the setup (chapter 8, part 3): `every_fix_waits_for_a_person`, `routine_fixes` (recommended start), or `routine_fixes_and_server_work`. |
| Server work | Under `routine_fixes_and_server_work`, triage-agent replacement of failed app, jobs, or load-balancer servers, warned reboots, and load-based app server scaling ([Triage agent rules](triage_agent_rules.md)). Database servers, `util01`, and `staging01` always need a person. |
| Adding and removing app servers with the load | Automatic app-pool scaling inside `growth_limits.app_servers` after a stoppable warning ([Adding and removing app servers with the load](triage_agent_rules.md#adding-and-removing-app-servers-with-the-load)). Say "the load", not "autoscaling", and name the server, monthly price, and pool count. |
| Replacement of a failed server | The three-playbook sequence (`replace_failed_servers`, `every_server`, `destroy_replaced_servers`) that replaces a silent server ([Replacing a failed server](triage_agent_rules.md#replacing-a-failed-server)). Say "the failed server is powered off, not yet destroyed" until the third run. |
| Warning held for the triage agent | Every warning is held for `warn_waits_for_the_triage_agent_minutes` (default 15) while the triage agent looks first, so the person hears the agent's verdict instead of the raw warning ([Warnings wait for your report](triage_agent_rules.md#warnings-wait-for-your-report)). |
| Run limit | The most triage agent runs in 24 hours, `triage_agent.most_runs_in_24_hours` (default 50). It stops only agent runs, never alerts: past it, alerts go straight to people. Say "the agent's run limit", and say that alerts continue. |
| Set-aside finding | A finding the triage agent investigated and found not to affect the team, written into `triage_agent_notes/set_aside_findings.yml` with its reason. MMWatchdog then stops alerting for that exact finding on every server, until its package, version, fix or advisory changes ([Setting a finding aside](triage_agent_rules.md#setting-a-finding-aside)). Say "set aside after investigation", never "ignored" or "muted". |
| SOS wait for a replacement | While the triage agent replaces a failed server, the site SOS waits up to `sos_waits_for_a_server_replacement_minutes` (default 7) before waking the person on call. Say "you will be woken only if the replacement fails or takes longer than 7 minutes". |
| Come-back wait | How long a reboot playbook waits for a server to return (`come_back_wait_after_a_reboot`, default 3 minutes; longer per-server setting for dedicated servers). |
| Weekly maintenance window | The team's weekly UTC hour (`maintenance_window` in `mmx_project_settings.yml`) for database updates and single-server pool reboots. |
| Alert pause | A per-server MMWatchdog maintenance window during a playbook reboot or update; public site checks never pause. Say "alert pause" so it is not confused with the weekly maintenance window. |
| Server type | The provider's size name (such as `cx33`), recorded as `server_type` in the inventory. |
| Dashboard | MMHotline's page showing who is on call, open incidents, pool status, and open checklist items. |
| Run page | A read-only page showing each MMX run on `util01` as it happens. |
| MMHotline-down alarm | A small program in the team's Cloudflare account that wakes the person on call if MMHotline stops checking in every minute. |
| Status page | A public page in the team's Cloudflare account that stays up even when every server is down. |
| Cloudflare tunnel | An outbound connection from a server to Cloudflare so the server needs no open web port. |
| Tunnel connector | `cloudflared` on each app server (or load-balancer server) that opens the Cloudflare tunnel. |
| Cloudflare Access | A team sign-in Cloudflare puts in front of private pages. |
| Caddy | The web server on each app server that spreads tunnel requests across the app's web containers. |
| Container image | The app packaged with its runtime dependencies so it runs the same everywhere. |
| Image tag | The name of one image version: the full 40-hex-character app commit SHA. |
| CI | The Git host's automated build service (recommended) that tests, builds, and pushes the app image; without CI, the coding agent builds inside a laptop container and pushes with the person's registry login. |
| Registry | The service that stores container images, such as GitHub's. |
| Release or deploy | Starting a new app image beside the old one and switching traffic once health checks pass. |
| Worker | A running copy of the app handling web requests or background tasks. |
| Database driver | The code the app uses to connect to its database. |
| SQLite | Database software that keeps a database in a local file. |
| Postgres | The database software on the database servers. |
| Bucket | A named storage area for files at a storage company. |
| Pushover application | The identity of the alert sender in Pushover. |
| Pushover group | The people who receive an alert sent to that group. |
| Cache | A saved copy of a shareable response that Cloudflare serves without asking the app server. |
| WireGuard | The encrypted private network the servers and systems desks talk over. |
| Primary | The database server that takes writes. |
| Replica | A database server that keeps a live copy of the primary's data. |
| Failover | A healthy replica taking over automatically when the primary fails. |
| Failover monitor | The pg_auto_failover component on `util01` that decides which database server is primary. |
| Failover formation | The production database servers managed together by pg_auto_failover (`staging01` runs Postgres without one). |
| Database transaction | A group of database changes that succeed or fail together. |
| pgBackRest | The program that backs up Postgres to Backblaze B2 (continuous WAL plus a weekly full backup and nightly incremental backups). |
| Restore drill | The weekly automated test on `util01` that restores backups onto a temporary `restore01` server, checks data, and deletes `restore01`. |
| Object Lock | Backblaze's write-once lock (`lock_backups_against_deletion_for_days`, default 14) preventing deletion or change even by the account owner. |
| R2 | Cloudflare's file storage for app uploads. |
| B2 | Backblaze's file storage for backups. |
| Uploads' copy | `util01`'s periodic copy of R2 uploads into B2 (with version retention for `keep_prior_file_versions_in_buckets_for_days` days). |
| staging01 | The optional test server where releases run first with test data only. |
| Litestream | The program that streams MMHotline's SQLite database to Backblaze B2 as it changes. |
| Deviation | An intentional difference from the stack's design, recorded in the checklist with its reason. |

## Credits

The Plain English rules in `talking_with_the_team.md` adapt the Plain mode
of SimpleEnglish, version 2.1.1 (<https://github.com/AminBlg/SimpleEnglish>),
which is published under the MIT License:

```text
MIT License

Copyright (c) 2026 AminBlg

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Before a big systems change

Before replacing a database server, moving provider, or starting maintenance,
ask the person to announce the planned work in the team's chat.
For example: “I am replacing db02 now. Please wait before changing database settings.”
Use MMWatchdog maintenance with a reason when the procedure calls for maintenance.
Reason: another person's desk has a separate checkout, but every person shares the running system.
A solo person still follows the `main` synchronization rules in `AGENTS.md`.

## Systems work and app work

We say "laptop" throughout because most people use one. Any computer you develop on works the same way, such as a desktop or a Mac mini.
The coding agent works on the laptop, beside the app's code, and acts on production only through the
systems desk, as
[chapter 3 (make your server account and your systems desk)](initial_setup/03_make_your_server_account_and_your_systems_desk.md)
explains, logged in as `coding-agent` and using its buttons, as `AGENTS.md` says.
When you explain the desk's protections, say what they leave: malware controlling the laptop during an open
desk session can act through the session, and a coding agent with production authority can read production
secrets through production work.
Never claim every action is a Git commit: direct SSH is not recorded as a Git commit or MMX run.
