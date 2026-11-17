# Talking with the team

Read `talking_with_the_team.md` before you start work in the team's systems
repository. `talking_with_the_team.md` holds the rules for everything you
say and write to the team: setup, normal operations, failures, and triage
reports. "The person" is whoever works with you now. "The team" is the
company that owns the production system described in the systems repository.
"Customers" are always the app's users.

The person knows basic Linux, servers, and databases, and can be new to
production servers. Write so that a smart fifth grader who knows basic
Linux, servers, and databases can follow you. At every step, the person must know what is happening,
why it is happening, and why it matters. The person
makes decisions about the team's production system, at 3 a.m. too. A system
that works, but that its owner does not understand, has failed.

## Plain English

The Plain English rules below are complete. Follow the Plain English rules
as written.

- **Start with the answer, the result, or the next action.** Then give the
  reason for the answer, result, or next action. Say why a step comes now,
  why a wait takes long, and why a rule exists. Leave a reason out only
  when the person already knows the reason.
- **Write so the person understands on the first read.** Clarity, ease of
  understanding, and correctness come first. Longer text is fine when the
  longer text is easier to understand.
  - Start each section, paragraph, and list item with its topic and why
    the topic matters to the person.
  - Keep one topic in each paragraph or list item.
  - Tell steps and events in the order the person meets them: what the person
    does, what happens next, and what can delay or stop the step.
  - Connect facts with "because", "so", "then", "but", and "for example".
    "Because", "so", "then", "but", and "for example" carry meaning and
    are never filler.
  - Join two related clauses into one sentence when the join puts a
    word such as "it" or "that" next to the thing's name: "Claiming the
    alert stops the repeats, but the claim does not fix the fault."
  - Give a concrete example for each new idea.
  - Explain a technical term the first time the person needs the term. Leave
    out a term that the person does not need.
  - Write an exact file path, command, or setting name when the person or the
    agent must type the path, command, or name, or must find the file or
    setting. Otherwise, describe the thing in plain words.
- **Keep every fact.** When you shorten or split a sentence, keep each
  number, name, condition, step order, actor, and reason. Never replace a
  fact with a general word. "util01: MMHotline stopped after 5 failed
  starts. I restarted MMHotline. MMHotline works again." says
  what happened.
  "util01: MMHotline operates correctly after a restart" does not. When
  the source gives no number or cause, keep the general statement.
- **Name the actor.** Say who or what does each action: "I", the person, a
  named person, or a named program. Use "I" for your own actions. Use "we"
  only when the shared action and each person's part are clear.
- **Name the exact thing.** The person must know which thing each word
  means, without guessing and without looking back. The rules for naming
  the exact thing are strict, because vague text is the most common failure:
  - Do not use "it", "its", "this", "that", "these", "those", "they",
    "them", "their", "there" or "here" for a place, "one" as in "one of
    them", "the other", "both", "either", "the former", "the latter", or
    "the same" to point to a thing, unless the thing's name is in the same
    sentence. A heading does not count, and the sentence before does not
    count. Write the name instead.
  - Use the shortest name that can mean only one thing, such as "the new
    server" or "the first run". Do not repeat a long name in every
    sentence. Rewrite the sentence instead.
  - Name the thing when a phrase such as "the file", "the fix", "the
    change", "the procedure", "the step", or "the server" could mean more
    than one thing. For a file, write its path.
  - Use plain, literal verbs that say what happens: "add a server", not
    "grow the pool"; "waits for the other run to finish", not "holds its
    turn".
  - The rules for naming the exact thing apply to bold lead-ins, list
    items, and table cells too.
  - Examples that failed in the stack's repository:
    - "Two operating procedures grow it" becomes "Two operating
      procedures add capacity to the system".
    - "I updated both procedures" becomes "I updated
      `operating_procedures/add_an_app_server.md` and
      `operating_procedures/remove_a_server.md`".
    - "Cloudflare sends the request down one of them" becomes "Cloudflare
      sends the request down the tunnel of one of your app servers".
- **Use "must" for a requirement and "can" for a possibility.** Do not
  write "should". A required step uses "must", and an optional step says
  that it is optional. Do not soften a fact you know with "usually", "may",
  or "might". The backups are locked for the number of days in
  `backups.lock_backups_against_deletion_for_days`, not "usually" that long.
- **Write short, complete sentences.** Use active voice and simple tenses.
  Put a condition before the action it controls: "If the build fails, read
  the log." Give one instruction per sentence. In documents, keep
  instructions within 20 words per sentence and descriptions within 25.
  The limits apply to each sentence, not to the length of the text.
  Keep one topic per paragraph, with at most six sentences. Split a long
  sentence without dropping a fact.
- **Use ordinary technical language.** "I will check the logs" is fine. Use
  full forms such as "do not". Do not use semicolons or em dashes. Write
  two sentences, or name the relation with "because", "but", or "so".
- **Explain an unfamiliar term before the step that needs it,** in a few
  words, including a product's purpose. Do not define familiar terms, such
  as files, logs, or repositories, or standard names, such as Postgres. Use
  one term for each thing, from [Technical terms](#technical-terms).
- **State the fact, not its importance.** Delete words
  that carry no fact, such as "simply", "seamlessly", "robust", "crucial",
  and "in order to".
  Leave out stock introductions, sales language, and closing offers.
  Words that connect facts, such as "because" and "so", are not filler.
- **Keep a routine chat reply to the facts and the next action.** Add
  detail for a decision, a risk, or a question. Do not turn every reply
  into a lesson or repeat facts the person already has.
- **Use prose for ordinary replies.** Use a list, a table, or a heading
  only when it makes steps or a comparison easier to read.
- **Keep exact text exact:** commands, identifiers, file paths, software
  names, interface labels, error messages, and quoted source text. Do not
  shorten a security warning or the confirmation before a destructive
  action.

**Before you send a message or save a document,** check it:

- The person can tell what happened, who acts next, and what they must do.
- The message or document still contains every condition, cost, risk,
  location, reason, and unknown fact.
- Search for "should", "usually", "may", "might", ";", and "—". Fix each
  word that softens a known fact, and each ";" or "—" that joins two sentences.
- Search for the words in "Name the exact thing". For each listed word
  that points to a thing, find the thing's name in the same sentence. If
  the sentence does not contain the name, replace the word with the name. In a repository,
  `git diff -U0 | grep '^+' | grep -n -i -w -E 'it|its|this|that|these|those|they|them|their|there|here|one|other|both|either|former|latter|same'`
  lists the words from "Name the exact thing" in the new lines. Then read
  each sentence as the person, and name the thing wherever a phrase such
  as "the file" could mean more than one thing.
- Read the text once as the person. Wherever the person would stop and
  reread, rewrite the passage.
- In a document, count the words in the three longest sentences. Split
  each of the three sentences that is longer than 20 words for an
  instruction or 25 for a description.
- Each step names the server, the flag, or the earlier step that its
  command depends on.

## Times on the servers

Every server schedule and log is in UTC. `nightly_work_starts_at`,
`weekly_work_day`, and `maintenance_window` in `mmx_project_settings.yml`
are UTC. The person never has to handle UTC: when you name a time, say it
in the person's local time first, such as "Tuesday at 9 pm your time (Tuesday
21:00 UTC, in `maintenance_window`)". A person who wants every time shown in
local time can add that instruction to `AGENTS.md`.

## Before a step

Say the step's purpose first, and why it comes now. Introduce a technical
term only when the person needs the term for the step you are about to
take. Give an example when the connection between the term and the step is
not clear. Do not read the glossary or a whole procedure to the person.

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
step 4). Read the provider's
current price first. Show the known costs together. Label a subtotal, and
name the charges that it leaves out. A server inside the growth limits
(`growth_limits` in `mmx_project_settings.yml`) needs no approval: add it
when its operating procedure's trigger arrives, then tell the person which
server you added, why, and its monthly cost from the provider's current
price.

Before you apply a difference from the stack's design, explain its effect,
including who or what gets permission to act. Record the design difference
in the checklist as `state: deviated`, with `deviation:` saying what
differs and why.

Never ask the person to put a secret in the chat, because the chat is
stored at the coding agent's provider. Tell the person where to type the
secret instead: a hidden prompt of a `set-up-outside-services` command on
the desk, such as `ssh desk01-secrets`, or the password manager. Never ask
the person to paste a secret into a file with an editor.

## During work

- **For a wait,** say its cause and the next check. Give a time only when a
  test result or the provider's information supports it. Say whether the
  person must stay for the wait.
- **For a failure,** start with one plain sentence: what failed, whether
  anything is harmed, and what happens next. Then name the part that failed and its effect on the
  service and the data. Give the known facts, the unknown facts, and the
  next safe step.
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

## Technical terms

Use one term for each thing. Explain an unfamiliar term before the person
needs the term. Use only the rows that the step needs. Add a new technical
term to the Technical terms table in `talking_with_the_team.md` before
using the term in the team's documentation.

| Term | Explanation |
| --- | --- |
| Production servers | The app servers, database servers, and utility server, `util01`. |
| Systems desk | The person's own small server at the server provider, in a different location from the production servers, where the person and the coding agent do all systems work. The production SSH key, the vault passphrase and the person's tokens stay on the desk, never on the laptop. The laptop reaches only the person's desk. [Chapter 3 (make your server account and your systems desk)](initial_setup/03_make_your_server_account_and_your_systems_desk.md) sets it up. |
| Phone code | A six-digit authenticator code needed with the laptop's SSH key to log in to the desk. |
| doubleshell | The program on the laptop that carries the SSH login to the person's desk through WireGuard, without a VPN on the laptop. |
| Token file | The person's private file on the desk, `~/.config/monkeymaxxing-stack/<project_name>.env`, readable only by the person: the person's own Cloudflare tokens, such as the key for posting to the status page. `set-up-outside-services` writes it; nobody edits it, and the coding agent never reads it. |
| Recovery passphrase | The six words in the team's password manager that open the recovery bundle, `recovery_bundle.age`: every item a lost desk needs, encrypted. |
| Phone code | The 6 digits from the authenticator app on the person's phone that open the desk, for the person and for the coding agent. Each code works once. |
| `set-up-outside-services` | The Stack's command on the desk for the person's accounts and secrets at outside companies, such as Cloudflare, Backblaze and the server provider, and for the vault's missing keys. The person starts it from the laptop with a short command, such as `ssh desk01-setup` or `ssh desk01-secrets`. |
| Desk review | The person's run of `review-and-apply-the-systems-desk-settings`, with `ssh desk01-review` on the laptop. It applies the desk playbook, `playbooks/systems_desk.yml`, as root, and first shows each change since the person's last desk review and waits for `yes`. |
| Coding agent account | The separate Unix account `coding-agent` on the desk. The coding agent on the laptop logs in to it through `ssh desk01-agent`, and uses the desk's buttons from it. |
| Button | A command or local service that uses a protected credential for the coding agent without giving the coding agent the credential. |
| API proxy | The desk's one local service between the coding agent and the outside APIs. At `http://127.0.0.1:8081/` it adds the person's server provider token to each request, or signs it, such as at OVHcloud and AWS, or adds a short-lived token it makes from a key, such as at Google Cloud. At `http://127.0.0.1:8082/` it adds the desk token to the coding agent's Cloudflare requests. The coding agent never reads the token or credential. |
| Desk token | The person's own Cloudflare token on their systems desk, named after the person. The API proxy adds it to the coding agent's Cloudflare requests. It cannot make tokens. `set-up-outside-services cloudflare` makes it. |
| Link token | The one Cloudflare token the person makes by hand, from the link that `set-up-outside-services cloudflare` prints. It can only make tokens, and the command deletes it when the command ends. |
| Lock-out button | The command `sudo lock-everyone-out`, which only a person runs, with `ssh -t desk01 sudo lock-everyone-out` on the laptop, and only in the narrow break-in cases that [The lock-out: only for these cases](operating_procedures/respond_to_a_break_in.md#the-lock-out-only-for-these-cases) names, such as a suspect `util01`. In every other break-in, such as one through the app, the lock-out harms more than it helps. It cuts off every other desk and `util01` at the servers and stops the triage agent; the person and the coding agent keep working from that desk, the desk that keeps access. The coding agent prepares the one-line inventory commit, `everyone_locked_out_except_desk`. |
| Undo a lock-out | Give every desk, `util01` and the triage agent their access back after a lock-out: the coding agent removes `everyone_locked_out_except_desk` and pushes, and the person runs the lock-out button again. Say "undo", never "reverse". |
| Desk that keeps access | During a lock-out, the one desk named in `everyone_locked_out_except_desk`: the desk where the person ran the lock-out button. The person and the coding agent keep working there; every other desk and `util01` lose access at the servers. |
| Provider console | The server's screen and keyboard on the server provider's website. It works without SSH and WireGuard, so the person can log in there as root with the shared root console password from the password manager and repair them. |
| Self-management key | The separate root-owned SSH key used only when the person runs MMX against the desk's loopback address. |
| Systems repository | The files that hold the server settings and the encrypted secrets. The systems repository does not hold the app's code. Git records the systems repository's history. The team's main copy is on `util01`, and the Git host keeps a backup copy. |
| App's repository | The files that hold the app's code and tests. |
| Stack's repository | The source of the Monkeymaxxing Stack's instructions and of the example system that the systems repository is copied from. The stack's repository never changes the team's system by itself. |
| Git | A program that records changes to files. |
| Commit | A saved change in Git history. |
| Push | An upload of saved commits to another copy of the repository, such as the main copy on `util01` or the backup at the Git host. |
| Git host | The service that keeps a copy of a Git repository, such as GitHub. |
| Vault | The encrypted file that holds configured production secrets. A long, random passphrase opens the vault file, `secrets_vault.age`. |
| API | A company's way of taking commands from a program instead of clicks on its website. I can use the API from the person's systems desk to set things up exactly and repeatably. |
| Token or API key | A secret that lets a program act on an account, with only the rights granted to the token. Whoever holds the token can act on the account with the token's permissions, so the token never goes into the chat. |
| Authenticator app | An app on the phone that generates an extra code for signing in, as well as the password. |
| MMX | The program that makes each server match the systems repository. After the initial setup, MMX runs on util01. |
| Run | One time that MMX applies the systems repository to the servers. |
| Dryrun | A preview that shows what a run would change. A dryrun changes nothing. |
| Playbook | A file of steps that MMX runs in order, such as `every_server.yml`. |
| Fleet stage | A section of a playbook that selects servers and runs tasks on them, including role calls, such as the fleet stage `mmhotline` in `every_server.yml`. |
| One-time playbook | A dated playbook in `one_time_playbooks/` for one particular fix, such as freeing disk space, made with `mmx new-one-time-playbook` and moved to `one_time_playbooks/completed/` once every server has run it. |
| Helper | `./server_management_scripts/run_mmx_on_util01`, which the coding agent runs on its desk: it runs MMX on `util01` at the desk's pushed `main` commit, under `util01`'s lock. |
| Role | The settings and tasks for one kind of server, such as an app server. |
| Inventory | The list of the servers, in `inventories/servers.yml`. |
| Pool | The servers that share one job, such as the app servers. |
| Operating procedure | One of the tested ways the system changes, such as adding a server to a pool. |
| Checklist | `monkeymaxxing_stack_checklist.yml`: every item of the stack, with its state (done, open, or deviated), its evidence, and, in their own section, the growth and improvement items. |
| Weekly system review | The weekly look at the week's alerts, the waiting updates, the restore drill's result, and the checklist items that are due, as [Do the weekly system review](operating_procedures/do_the_weekly_system_review.md) says. |
| Setup machine | The machine that makes a new server's WireGuard key and first-boot data: `util01`, or the systems desk during initial setup and when `util01` is rebuilt. |
| First-boot data | The settings, rendered by `server_management_scripts/render_server_first_boot`, that a new server runs at its first boot: they close public SSH and start WireGuard with the new server's key, so MMX reaches the server over WireGuard from the start. |
| Ownership receipt | The file that `create_a_server_at_the_provider --ownership-file` writes with the new server's ID and name as soon as the provider accepts the server, so a cleanup deletes only the server that this run created. |
| Trigger | A measured sign or an event that says an operating procedure is due, such as MMWatchdog's warning that the app servers are busy, or the first paying customers. |
| Growth and improvement items | The checklist's own section, `growth_and_improvement_items`, for steps that wait for a trigger that can come late or never: growth, such as a second app server, and improvement, such as an optional drill. An item waiting for its trigger never counts as open. |
| Growth limits | The servers that may be added and removed without asking the team, by the coding agent or, with server work, the triage agent, set once at setup: the largest number of servers in each pool, the server types each pool may use, and the smallest number of app servers, below which the triage agent never removes one for low load (`growth_limits` in `mmx_project_settings.yml`). |
| Location | One of the server provider's data centers. Production servers share a location. Systems desks run in a different location. Each server's location is recorded as `location` on the server in the inventory, so a replacement is created where the failed server was. |
| util01 | The utility server. It runs MMX, MMHotline, and MMWatchdog's fleet hub on util01. |
| MMWatchdog | The watchdog on every server. Most checks run every minute; the desk watches failed phone-code logins every five seconds. MMWatchdog sends an alert when a person must look. systemd restarts a service that crashed. |
| Fleet hub | MMWatchdog on util01. Every server reports to the fleet hub, so the fleet hub notices a server that goes silent. |
| Hub-outage alerters | An app server and a database server that watch util01. If util01 goes silent, the hub-outage alerters alert the phones directly through Pushover. |
| MMHotline | The program on util01 that takes every alert, runs the triage agent, reaches the person on call, and shows the dashboard. |
| SOS | The urgent alert. An SOS wakes the person on call, even at night, and repeats until someone claims the SOS. The other levels, warn and info, wake nobody. |
| Claim | Pressing "Claim: I'm handling the incident" on an SOS in MMHotline, or acknowledging it in Pushover. Claiming the SOS says "I have got this", so the alert stops reaching anyone else. Claiming the SOS does not fix the fault. |
| Person on call | The person whom MMHotline wakes for an SOS now, by the on-call schedule. |
| Triage agent | An AI coding agent that MMHotline runs on util01 for each alert. The triage agent investigates, writes up the cause, and proposes a fix. The fix runs by itself or waits for a person's approval, as the rules for running the agent's playbooks say. |
| Scheduled software review | An optional run of the triage agent at an interval the team chooses, with the team's task in `scheduled_software_review_task.md`, such as checking every server's software for known flaws. Off by default, because each review costs a run of the coding agent. A review sends at most one report, and none when nothing is new or changed. The report is warn only when a person must act, such as installing a fix the nightly updates missed; otherwise the report is info. |
| Trusted commit | The commit of `main` in the main copy that MMHotline, its MMX runs and `util01`'s scheduled jobs work at. MMHotline trusts every commit on `main` in the main copy, and only the keys in `root_ssh_public_keys` can push there. |
| Rules for running the agent's playbooks | The rules that say which of the triage agent's fixes run by themselves and are reported, and which wait for a person's approval. The team sets them with one answer, `what_the_triage_agent_may_do_without_a_person` in `mmx_project_settings.yml`. |
| What the triage agent may do without a person | The team's one answer, chosen in chapter 6: every fix waits for a person; routine fixes, such as restarting a service that failed, run at once and are reported (the recommended start); or routine fixes and server work. |
| Server work | With the answer "routine fixes and server work", the triage agent's work on whole servers without a person: replacing a failed app server, jobs server or load-balancer server with a new one of the same type, inside the growth limits, at once; and, after a warning that anyone on the team can stop, rebooting servers for installed updates and adding and removing app servers with the load. Database servers, `util01` and `staging01` always wait for a person. With the other two answers, a person's one approval lets the triage agent replace such a failed server, and a person adds and removes app servers. |
| Adding and removing app servers with the load | With "routine fixes and server work": one app server is added when the app servers' CPU, spread over one server fewer, stayed above 70% for 15 minutes, and the newest is removed when a whole week's busiest moment would fit on the smaller pool with a server to spare below 50%, always between the smallest and the largest number of app servers. Say "the load", not "autoscaling", and name the server, its monthly price and the number of app servers now. The person hears one sound, MMHotline's warning with Stop at the start (the busy-servers warning is held for the triage agent, which requests the change, so only MMHotline's warning sounds); the progress reports and the report at the end are silent, and only a failed or refused change warns. |
| Replacement of a failed server | Three runs, in order: `replace_failed_servers` powers the failed server off, keeping its disk, creates a new server of the same type in the same location and commits it to the inventory; `every_server` installs it; `destroy_replaced_servers` destroys the failed server once the new one does its work. Each commit is made by "util01, the mmhotline user". Say "the failed server is powered off, not yet destroyed" until the third run. The playbook's own refusals decide whether it replaces; the triage agent requests it each time. |
| Warning held for the triage agent | A warning that starts a triage session waits up to `triage_agent_server_work.warn_waits_for_the_triage_agent_minutes` in `mmx_project_settings.yml` (3 minutes by default; 0 to 15, and 0 holds nothing) before it reaches people, because the triage agent tries first. If the agent asks for a playbook run, or sends its report, in that time, MMHotline's own warning or approval request, or the report, is the sound and the held warning is never sent. Nothing is dropped: otherwise the warning sounds at the end of the wait, at once when the triage agent cannot run. A warning that joins a session already running is not held. |
| SOS wait for a replacement | While the triage agent replaces a failed server, the site's urgent alert (SOS) waits up to `triage_agent_server_work.sos_waits_for_a_server_replacement_minutes` in `mmx_project_settings.yml` (7 minutes by default) from the replacement's start before it wakes the person on call, instead of the usual few minutes. MMHotline sends one warning as the replacement starts, and wakes the person at once when a run fails, the triage agent reports an SOS or asks for a person. The SOS's resolved message, with a sound, says the site answers again. Say "you will be woken only if the replacement fails or takes longer than 7 minutes". |
| Come-back wait | How long a reboot playbook waits for a rebooted server to come back before the run fails: `come_back_wait_after_a_reboot` in `mmx_project_settings.yml`, 3 minutes by default (a cloud server came back in under a minute); a dedicated server gets its own, longer value in the inventory. With server work, the triage agent replaces a server that did not come back in that time, without waiting for its alert pause to end. |
| Weekly maintenance window | The team's weekly hour for database updates and reboots, `maintenance_window` in `mmx_project_settings.yml`, in UTC. The only server of an app or load-balancer pool reboots for updates only inside it, because its users see the reboot. |
| Alert pause | An MMWatchdog maintenance window on one server while a playbook reboots or updates that server: the server's own alerts, and the fleet hub's alert that the server stopped reporting, wait until the pause ends. A pause lasts at most as long as the playbook waits for that server; the public site check on `util01` is never paused, not even during `util01`'s own reboot. Say "alert pause" to the person, so it is not mixed up with the team's weekly maintenance window. |
| Server type | The provider's name for a server's size, such as `cx33` at Hetzner Cloud, recorded as `server_type` on each server in the inventory. |
| Dashboard | MMHotline's page: who is on call, the open incidents, one box per pool, and the checklist's open items. |
| Run page | A read-only page that shows each MMX run on util01 as it happens. |
| MMHotline-down alarm | A small program in the team's Cloudflare account. MMHotline checks in with the MMHotline-down alarm every minute. When the check-ins stop, the MMHotline-down alarm wakes the person on call. |
| Status page | A public page in the team's Cloudflare account, where the team tells its customers about a problem. The status page works while every server is down. |
| Cloudflare tunnel | A connection that a server opens out to Cloudflare. Cloudflare sends the requests through the tunnel, so the server needs no open web port. |
| Tunnel connector | `cloudflared`, the program on each app server, or on each load-balancer server once they carry the requests, that opens the Cloudflare tunnel. |
| Cloudflare Access | A sign-in that Cloudflare puts in front of a private page. The Cloudflare Access rule names who gets in: email addresses at the company's domain, or members of its GitHub organization. Only the company's people get in. |
| Caddy | The web server on each app server. Caddy takes the requests from the tunnel and spreads the requests over the app's web containers on every app server. |
| Container image | The app, packaged with the software it needs, so it runs the same everywhere. |
| Image tag | The name of one image version. In the Monkeymaxxing Stack, the image tag is the full app commit (40 hexadecimal characters) that the image was built from. |
| CI | The Git host's automated service. CI, which the Stack recommends, runs the app's tests, builds the container image, and pushes the image to a registry. The coding agent deploys the image. Without CI, the coding agent tests and builds inside a container on the laptop, and pushes the image with the person's registry login. |
| Registry | The service that stores the app's container images, such as GitHub's. |
| Release or deploy | Putting a new app version live. util01 starts the new version beside the old version on the environment's app servers. util01 switches the requests after the new version's health check passes. |
| Worker | A running copy of the app's program that handles requests or background tasks. |
| Database driver | The code that the app uses to connect to its database. |
| SQLite | Database software that keeps a database in a local file. |
| Postgres | The database software on the database servers. |
| Bucket | A named storage area for files at a storage company. |
| Pushover application | The identity of the alert sender in Pushover. |
| Pushover group | The people who receive an alert sent to that group. |
| Cache | A saved copy of a response that Cloudflare can send again without asking the app server. Only responses that the app allows for shared use go into Cloudflare's cache. |
| WireGuard | The encrypted private network that the servers talk over, so nothing between them crosses the internet in the open. |
| Primary | The database server that takes the writes. |
| Replica | A database server that keeps a live copy of the primary's data. |
| Failover | A healthy replica taking over automatically when the primary fails. |
| Failover monitor | The program on util01 that decides which database server is the primary. The failover monitor is part of pg_auto_failover. |
| Failover formation | The production database servers that pg_auto_failover manages together, so it can promote a replica when the primary fails. `staging01` runs Postgres without one. |
| Database transaction | A group of database changes that succeed or fail together. |
| pgBackRest | The program that sends every change of the database to Backblaze B2, with a full backup every `weekly_work_day` and a backup of the changes since that full backup on the other nights. |
| Restore drill | Each `weekly_work_day`, util01 creates a temporary server, restore01, restores the backups onto it, checks the data, and deletes it. The restore drill never touches the live database. |
| Object Lock | Backblaze's lock. For the lock length (`backups.lock_backups_against_deletion_for_days`, 14 in the template) after a backup is written into a locked bucket, nobody can delete or change the backup. The lock applies even to someone with the key or the account's owner. |
| R2 | Cloudflare's file storage, where the app keeps its uploaded files. |
| B2 | Backblaze's file storage, where the backups go. |
| Uploads' copy | `util01`'s copy of every app's R2 bucket into the uploads' B2 bucket, every `backups.uploads_copy_every_hours` hours (every night in the template). A file deleted or replaced in R2 is hidden in B2 at the next copy: B2 keeps the file's earlier versions for `backups.keep_prior_file_versions_in_buckets_for_days` days, so a restore can bring the file back. |
| staging01 | The optional test server, part of the fuller system or added later. With staging01, every release runs on staging01 first, with test data only. |
| Litestream | The program that copies MMHotline's own database, its alerts and their history, to Backblaze as it changes. |
| Deviation | Something the team's production system does differently from the stack, recorded in the checklist with the reason. |

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
