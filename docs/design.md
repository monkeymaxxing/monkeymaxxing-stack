# Design of the Monkeymaxxing Stack repository

The Monkeymaxxing Stack repository holds the skill a coding agent follows
to build and run the Monkeymaxxing Stack. The stack's repository also holds
the systems repository template the skill copies into each team's own
systems repository. `docs/design.md` records the conventions that every
file follows, and the reason for each choice. A file that disagrees with
`docs/design.md` is wrong, or `docs/design.md` must change first.

## Why these tools

Each choice names its cost.

- **MMWatchdog, not Prometheus with Grafana or a hosted monitoring
  service.** Prometheus is several services (the server, exporters,
  Alertmanager, Grafana), built for metrics at large scale, with alert
  rules written by hand. A hosted service charges per server and keeps the
  team's monitoring at another company. MMWatchdog is one program per
  server; each check comes with the next action to take; its settings are
  readable files that the agent writes and a person reads; and it is free.
  Cost: fewer graphs and dashboards, and a younger tool.
- **MMHotline, not PagerDuty or Opsgenie.** MMHotline runs in the team's
  own accounts, with no per-user bill, and hands each alert to the triage
  agent, which investigates first and asks a person to approve the fix.
  Cost: the team runs it on `util01`, which is why the MMHotline-down alarm exists for
  when `util01` dies.
- **Cloudflare as the required front door.** The tunnel connects outward,
  so no server has an open web port, and one account covers the tunnel,
  Access for private pages, caching, attack filtering, and R2 for files.
  The alternative, Caddy facing the internet, opens port 443 and puts attack
  traffic on the team's own servers. Cost: a Cloudflare outage takes the
  site down.
- **Backblaze B2 for backups.** The requirements: a different company from
  the servers and from Cloudflare, a compliance lock that even the account
  owner can't remove, and keys that can write but never delete. B2 meets all
  three with a simple setup; any store with a compliance lock would also
  work.
- **pgBackRest, not `pg_dump`.** A dump is a snapshot, so a total loss costs
  every write since the last dump, and restoring a big database is slow.
  pgBackRest also archives every change, so it restores to a chosen minute,
  checks its own backups, and can restore from before an attacker touched
  the backup storage. WAL-G is a similar tool.
- **Postgres, not MySQL.** Postgres can also be the job queue and the search
  index, so the team runs fewer services, and pg_auto_failover gives it
  simple automatic failover. MySQL is a fine database, but in this stack it
  would mean more pieces.
- **Only the app runs in a container.** The app changes daily and brings its
  own language runtime, so a container makes a deploy or a rollback a swap of
  one image for another. Postgres and Caddy change rarely and come as
  ordinary Debian packages, so they get security updates through Debian's
  normal path and appear in MMWatchdog's update check; containers would add
  a layer and hide them from that check.

## Layout

```text
monkeymaxxing-stack/
  README.md                               what the stack is, how to give it to a coding agent, and where everything is
  AGENTS.md                               how to change the stack itself
  docs/design.md                          this document
  docs/testing.md                         how changes to the stack are tested
  skills/monkeymaxxing-stack/
    SKILL.md                              what the coding agent follows first: which situation, which file
    systems_repository_template/          copied, whole, into a team's systems repository, with every instruction
      initial_setup/                      the ten chapters, done once
      operating_procedures/               every later job, upgrading and assessing a running system included
    files_for_your_app/                   what the team's apps take from the stack, into their own repositories
      database_driver_finds_the_primary.md   how an app in each language follows a database failover
      node/                               the files a Node.js app copies to follow a database failover, the switchover check, and the files' tests
  examples/app-frameworks/                independent apps a team can copy, with tests and pinned build inputs
  docs/app-frameworks/                    each framework's Stack integration guide and test-record links
  reference_app/                          the app the stack's tests and courses deploy
  set_up_outside_services/                the Go command the person runs on a systems desk for the account and secret setup, with its tests and release build
  examples/app-platform-migrations/       standalone application files and migration rehearsal checks
  docs/app-platform-migrations/           migration guides with variances, export steps, and test boundaries
  tests/run_mmx_on_util01_test.py        the helper that runs MMX on util01, with fake external commands
  tests/sudoers_triage_test.py            that the triage user may confirm a fix of every MMWatchdog check group
```

The systems repository template sits inside the skill's directory, so an
installed skill always carries the files of its own version. The
installed skill then needs no other file of the stack to build a system.

**Every instruction lives in the template:** the initial setup's chapters sit
beside the operating procedures and the rules. Reason: a reader looks in
one place for every instruction, in the stack and in each team's systems
repository. The template is copied whole, so the team keeps the
instructions of its own version. The triage agent on `util01` has no skill installed, so the triage
agent reads the instructions in the team's systems repository. The initial
setup is used once, but the team keeps the record of how its system was
set up. SKILL.md stays outside the systems repository template, because a
coding agent's skill folder needs SKILL.md at the top.

The apps' files sit in the skill's directory, outside the systems
repository template, because they go into each app's own repository: the
systems repository holds the system, and an app's code belongs to the app.
The upgrade procedure's
[A new version](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/upgrade_to_a_new_stack_version.md#a-new-version)
lists the files of `files_for_your_app/` that changed. So each app that
copied such a file gets the file's new version as a change the team
reviews.

The reference app sits outside the skill's directory, because a team
brings its own app and the skill never copies the reference app. The
reference app is a small Go program on Postgres whose home page shows
which app server and which database server answered, so a deploy, a
failover, or a restore shows on the page, and it meets every point of
[the app contract](#the-app-contract).
The reference app's [README](../reference_app/README.md) gives the
reference app's values for `apps.<app>` in the project settings, including
its `restore_drill_check_queries`.

The framework examples sit outside the skill because a team copies an app into
its own app repository. Each framework directory carries its own migrations,
templates, dependencies, container recipe, HTTP check, and test record. Independent
copies keep each build context complete. The Go and Rust SQL starts with the same
schema, but neither app needs files from the other app. The guides under
`docs/app-frameworks/` explain additional-app settings and native database
reconnection. A recorded isolated service test is distinct from a live Stack proof.

Migration examples also live outside the skill because an application owns
its code and exported data. Each example provides copied application files,
a guide, and a versioned test record. The
[Railway guide](app-platform-migrations/from-railway.md) separates read-only
export and standalone rehearsal from production cutover. Export archives,
credentials, password hashes, and private documents stay outside Git.
An independent replay checks that the guide needs no hidden setup knowledge.

**Versions are Git tags** of the Monkeymaxxing Stack repository: `v`
and the version, the value of `stack_version` in the template's
checklist, such as `v0.1.0` for `0.1.0`. Versions follow semantic
versioning, as MMX, MMWatchdog and MMHotline do, with the smallest step
that is honest. While the major number is 0, fixes and text changes raise
the last number, such as `0.2.1`, even a guide change that changes what a
new setup builds. Only a release that makes existing teams act, such as a
changed setting or a step of
[A new version](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/upgrade_to_a_new_stack_version.md#a-new-version)
beyond copying the template's changes, raises the middle number, such as
`0.3.0`, and so does a new feature of the Stack's program
`set-up-outside-services`, such as a new command. Small text fixes wait on `main` and go out together, unless one
fixes something people would otherwise get wrong. Reason: one numbering
for every Monkeymaxxing tool, which Git hosts, `sort -V` and dependency
tools order correctly, and a version number that tells a team whether it
has work to do. Publishing a version creates the version's tag.
A team clones the stack's repository, checks out the newest version tag,
and uses the skill from that tag. A new version is `git fetch --tags` and
a checkout of the new version's tag. Reason: between releases, `main`
pins the Stack's programs with SHA-256 values of zeros, which
`every_server` and the desk playbook refuse
([A Stack release pins its own programs](#a-stack-release-pins-its-own-programs)).

The team's checklist also records the source commit of the copied files
in `stack_commit`. The coding agent writes `stack_commit` when copying the
template from a clone. During an upgrade, the coding agent follows
[A new version](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/upgrade_to_a_new_stack_version.md#a-new-version)
and compares the team's systems repository with the template at the
recorded commit. A checklist without `stack_commit` falls back to the
checklist's version tag, such as the checklist that the initial setup
copies from a skill that was copied out of a clone, with no way to tell
the clone's commit.

## Framework examples

`examples/app-frameworks/<name>/` holds an independent app a team can copy into
its app repository. Each app carries source, templates, assets, dependency locks,
migrations, runtime commands, a Containerfile, synthetic staging data, tests and
a test record. No app needs sibling examples or systems template files at build
or runtime. App code belongs in the team's app repository, so examples stay
outside the skill and systems repository template. The infrastructure reference
app remains separate.

The [framework index](app-frameworks/README.md) links every integration guide
and compares recorded results. Each guide explains framework differences,
copying, building, deployment, recovery and additional-app settings on a running
Stack system. FastAPI and Express also carry design notes in the app directories.
Test records distinguish isolated service evidence from live Stack deployment,
real R2 authorization and Stack backup recovery.

The portals exercise accounts, shared revocable sessions, owned records,
private document metadata and PostgreSQL report jobs. Private object bytes stay
in S3-compatible storage. Immutable keys and SHA-256 checks connect metadata to
bytes. A report worker holds a `FOR UPDATE SKIP LOCKED` row lock until output
and completion commit together, so the queue needs no external broker.
HTTP reads use the primary because sessions and recent edits need current values.

Native database drivers take precedence over a shared cross-language framework.
New connections select the writable primary from the unchanged Stack URL.
Requests never replay uncertain writes because a failed reply can follow a
successful commit. Ordered, additive migrations preserve the previous release.
Web, migrations, the test-data seed (`seed-test-data`, for laptops and
staging) and workers have separate commands.
The guides explain worker counts, query deadlines and graceful request draining.

- [Laravel, Livewire and Eloquent](app-frameworks/laravel-livewire-eloquent.md):
  Eloquent owns accounts, records, document metadata and report jobs. Livewire
  owns the interactive records screen. PostgreSQL stores shared web sessions.
  A small transactional job table replaces Laravel's database queue because
  the default queue reserves and acknowledges jobs in separate transactions.
  The app converts the multi-host URL to PDO/libpq settings and disables
  Laravel's automatic lost-connection query replay.

  FrankenPHP serves PHP and local Livewire assets in one container.
  `PORT` sets the only listening port,
  and `WEB_CONCURRENCY` sets PHP threads. Classic request mode and disconnecting
  between jobs let later work open a new connection.
- [Rails](app-frameworks/rails-pg.md): Active Record uses libpq-parsed settings,
  Puma runs web workers, Propshaft builds assets, and PostgreSQL row locks
  protect report transactions. Primary reads keep shared sessions and recent
  writes current.
- [Django](app-frameworks/django-pg.md): native auth and database sessions use
  psycopg settings. Gunicorn runs workers, WhiteNoise serves `collectstatic`
  assets, and PostgreSQL row locks protect report transactions.
- [SvelteKit](app-frameworks/sveltekit-pg.md) and [Nuxt](app-frameworks/nuxt-pg.md):
  SvelteKit uses adapter-node. Nuxt uses Nitro's node-server preset. Each
  framework owns pages, routes and Node output. Each app uses `pg` and the
  unchanged Stack multi-host helper. PostgreSQL owns sessions, ownership and
  job state. A Node cluster launcher maps `WEB_CONCURRENCY` to processes
  sharing `PORT`.
- [FastAPI](app-frameworks/fastapi-pg.md) and [Express](app-frameworks/express-pg.md):
  FastAPI passes the unchanged URL to psycopg/libpq. Express copies the Stack's
  `pg` helper unchanged. PostgreSQL stores hashed, revocable session tokens.
  Gunicorn/Uvicorn and Node cluster honor worker counts,
  query deadlines and shutdown draining.

  Ordered SQL migrations and the ledger
  commit together under a transaction advisory lock. The additive second
  migration keeps an empty database default for old releases. Content-hashed
  static files remain under `/app/assets` for release overlap.

  Password recovery, email verification and public abuse prevention are outside the
  examples, which teach the Stack integration boundary.

## App platform migrations

`examples/app-platform-migrations/` holds complete destination apps and
commands to transfer protected data that a team can copy. App code and exported data
belong to the application, so migration examples stay outside the skill.
The [migration index](app-platform-migrations/README.md) links export,
rehearsal, cutover and cleanup guides, plus feasibility assessments.
Each destination app carries a versioned test record and checks on a disposable copy.
An independent replay checks that a guide needs no hidden setup knowledge.

Migration guides distinguish source evidence, verified exports, destination
proof and unresolved access boundaries. Code, database rows, object bytes,
secrets, jobs and schedules need separate migration steps because no source
export contains every part. A code archive alone proves neither database nor
private-object nor password-verifier portability. Private exports, credentials,
password hashes and documents stay outside Git.

A standalone rehearsal does not prove production routing, real object-provider
permissions, database failover or full Stack backup recovery. Final cutover
requires paused source writes and exactly one job execution location.

- [Replit](app-platform-migrations/from-replit.md): preserve the PostgreSQL
  schema, stable UUIDs, bcrypt verifiers, sessions, queue and schedule state.
  Keeping the schema avoids unnecessary ownership and identity translation.
  S3 API calls replace App Storage, and the destination uses the unchanged
  Stack Node database helper. Web, ordered migrations and background jobs use
  separate commands. A native read-only database snapshot and separate object
  export preserve the source for rehearsal.
- [Fly.io](app-platform-migrations/from-fly.md): preserve application-owned
  authentication, the PostgreSQL schema, stable owner IDs and object keys to
  reduce translation risks. The copied Node database module uses the unchanged
  Stack helper so new connections find the writable primary.
- [Firebase](app-platform-migrations/from-firebase.md): the
  [destination](../examples/app-platform-migrations/from-firebase/README.md)
  replaces accounts, owned records, private files, reports and a scheduled
  task with PostgreSQL 17 and private S3-compatible storage. No Firebase
  service remains at runtime.

  UIDs and document IDs stay text primary keys because changing identities
  would break ownership. Preserve native issuer
  and subject, and never join accounts by email. Imported email/password users
  keep modified-scrypt verifiers and private project hash settings. New users
  use bcrypt. Browser sessions end at the move. PostgreSQL stores active and
  revoked destination sessions.

  An audit table retains every exported Firestore document beside mapped
  operational tables. Source and PostgreSQL migration ledgers stay separate
  because Firestore releases do not establish SQL schema versions. S3 bytes
  move separately and are checked by SHA-256. Conditional object creation
  prevents an import from overwriting different bytes. Source and destination
  processing never run together, and imports preserve maintenance and
  processing pauses.

  Job locks, output and completion share a transaction.
  Daily task occurrences and the next due time also commit together. A source
  export, independent restore and fresh replay establish phase 1.
- [Heroku](app-platform-migrations/from-heroku.md): the portable portal uses
  application-owned bcrypt accounts, PostgreSQL records and queues, separate
  S3-compatible files and a code-defined clock process. Preserve the schema and
  migration checksums instead of translating rows into another reference
  schema. The Node module copies the unchanged primary-discovery helper.
  The Stack's single jobs command supervises report and clock processes.
  Database transactions prevent duplicate claims and daily occurrences.

  Export checks cover every application table, account verifier, ownership
  link, queued and completed job, schedule receipt and current object.
  Heroku-owned database diagnostics stay outside the application schema and
  never become destination dependencies. A PostgreSQL 18-to-17 claim requires
  an actual restore. The [example README](../examples/app-platform-migrations/from-heroku/README.md)
  holds acceptance contracts. Remove source services and objects only after
  protected export and fresh-agent replay pass.
- [Netlify](app-platform-migrations/from-netlify.md): the
  [example](../examples/app-platform-migrations/from-netlify/README.md)
  preserves native account IDs, emails, ownership, records, private bytes and
  queued work. Native Identity verifier export is not a normal customer route,
  so imported accounts require a password reset. Expiring one-time tokens let
  returning users set a password and log in. Password replacement consumes
  tokens and revokes sessions atomically.

## The person's experience

A coding agent follows the skill, and a person drives the agent: someone
who has chosen the stack, knows basic Linux and what a server and a
database are, and can be new to production servers. The skill's "Talking
with the person", the systems repository template's
`talking_with_the_team.md`, and [the initial setup in chapter 0 (before you start: what we build and how long it takes)](../skills/monkeymaxxing-stack/systems_repository_template/initial_setup/00_before_you_start_what_we_build_and_how_long_it_takes.md)
hold what "The person's experience" decides. A change to any text the
person sees must meet "The person's experience".

**The goal.** A startup founder or developer who is new to running
servers sets up a production system with their coding agent in about a
working day. At the end, the person's site is live, alerts reach the
person's phone, and backups are proven to restore. The person is
confident that the system works and understands how. Setup feels like
steady progress, not an exam. Reason: this is the most secure stack the
person will use, but only if the person uses the Stack. A setup that
feels hard sends people to a system they build themselves, full of holes.

Three rules follow from the goal, and one rule on settings follows them. Every setup chapter, every item of the
checklist, and every operating procedure must meet the rules.

1. **The agent and the APIs do the work. The person decides and watches.**
   The person makes accounts, approves costs, and enters a secret only
   where a service offers no other way. The rest is automated: the coding
   agent works through the services' APIs, or the Stack provides a command
   that does the work, whichever keeps the person's part smallest and
   safest. At each step the person hears what is happening and why, and
   gets a link to see the result for themselves, such as the backup
   bucket's settings at Backblaze. Reason: good systems are largely
   automated, and every manual step is a chance for a wrong setting.
2. **The person proves their own system. The Stack's tests prove the
   Stack.** A setup step checks what is specific to this team: the team's
   accounts, keys, domain, phone, and data. The Stack's own tests prove
   once how the Stack's software behaves. The person can ask for that
   proof as an optional check, "Check my system's protections" in
   [`operating_procedures/assess_a_running_system_and_recommend_changes.md`](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/assess_a_running_system_and_recommend_changes.md#check-my-systems-protections).
   Reason: a person who repeats the Stack's own tests on every system
   spends the working day on an exam, and the Stack's tests already proved
   the software.
3. **Defaults fit a small team.** Each default works for a team of one or
   two people with ordinary tools. A stronger option, such as a hardware
   security key or an alert that wakes someone, is a setting that a team
   can turn on. A stronger option is never a setup requirement. Reason: a
   requirement that a small team cannot meet stops the setup, and the
   team then builds something weaker by hand.

**Settings and fixed values.** A value that a reasonable team would
choose differently is a setting, written out with its default and the
reason for the default. A fixed value records why it is fixed. Server
schedules are in UTC: the agent picks the times from the users' quiet
hours and tells the person the times in the person's local time. Reason: a
team sets its own backup retention, maintenance window, and time limits,
and a hidden constant forces the team to edit a role file to change it.

**The bar.** At every step, the person knows what is happening, why it is
happening, and why it matters. In plain words: "If it's bad or
confusing, or they're not sure what's going on, we have failed. It doesn't
matter how good it is technically if they don't understand what is going
on." Reason: the person owns the system and makes its decisions, at 3 a.m.
too. A system that its owner does not understand is run by guesswork.

**The level.** A smart fifth grader with basic Linux and a basic idea of a
server and a database can follow the text that the person sees. The
correct terms stay, each explained in one plain line before its first use.
The why is said at a high level that still gives the real cause and
purpose. The low-level details wait until the person asks. Reason: the
person needs the purpose of each part to
judge it later, not the flags that implement it.

**Plain English, with no loose words.** `talking_with_the_team.md` holds
the rules: short sentences, one instruction each, the actor named, "must"
for a requirement, no hedge on a known fact, and every number, name,
condition, and reason kept when a sentence is shortened. The Plain English
rules adapt the Plain mode of SimpleEnglish. The MIT notice for
SimpleEnglish is in `talking_with_the_team.md`. Reason:
without rules this tight, a coding agent drifts into vague text that reads
well and says little, and a shortened sentence silently loses the fact the
person needed. A rewrite that turned "stopped after 5 failed starts;
restarted it" into "operates correctly after a restart" is the kind of loss
the rules forbid.

**One portable source.** The rules, the example messages, and the glossary
live in one file of the systems repository template,
`talking_with_the_team.md`. The skill, the team's `AGENTS.md`, and the
triage agent's rules all point to `talking_with_the_team.md`. Reason:
`talking_with_the_team.md` is copied into each team's systems repository.
So a later coding-agent session, or the triage agent on `util01`, finds the
Plain English rules in the team's systems repository, with no outside
skill to install.

**Teach each idea when its step comes.**
[The map in chapter 0 (before you start: what we build and how long it takes)](../skills/monkeymaxxing-stack/systems_repository_template/initial_setup/00_before_you_start_what_we_build_and_how_long_it_takes.md#the-map)
shows the system in brief, in the words of the first page that opens the
team's `README.md`, then the route and the time, in ten chapters with one
line of purpose each.
Each chapter opens with when it comes, what it does, who acts, and a
short opening message. Each step then carries its own messages to the
person, with their reasons, so each idea is explained when its action
comes. The six core ideas in
[`SKILL.md`](../skills/monkeymaxxing-stack/SKILL.md#the-core-ideas) govern
every operation.
Chapter 3 (make your server account and your systems desk) introduces the laptop login, provider account, systems desk, repository, vault, and personal
token file, which holds the person's own API tokens on the systems desk. Chapter 4 (set up your accounts and lock your systems desk)
introduces the accounts at other companies and their APIs. Chapter 7 (install everything on the production servers)
introduces how the coding agent runs MMX on `util01` after pushing. Each chapter introduces
the checklist's results as its checks pass. Each exception stays with its
rule, with its reason. Reason: the person has already chosen the stack.
Showing the whole project, or a whole chapter, before the first action
overwhelmed people before they got to work. A point explained when its
action comes is understood and kept. The reasons themselves stay, because
a step without its why leaves the person guessing.

**The setup's one-off actions leave a record too.** The initial setup
starts the first copy of the uploads and the first restore drill from the
run of `every_server` itself. The optional MMHotline-down alarm outage test stops MMHotline through
`./server_management_scripts/run_mmx_on_util01 run-command`. Reason: core idea 3 says that MMX makes every
change to a server, and that MMX records the change's run. Core idea 3
holds for the first copy, the first drill, and the MMHotline-down alarm's outage test as
well. So every change to a server has a run on record.

**The step shape.** Each chapter has the shape of an operating procedure,
with the coding agent's messages to the person inside each step:

- "When", "What this chapter does", "Who acts", and "Tell the person when
  the chapter starts" open the chapter.
- "Before you start" holds what every step needs, such as the token-file
  rule and the links where the person sees results.
- Numbered steps follow, each with a "Check:". A long chapter, such as
  chapter 7 (install everything on the production servers) or chapter 8
  (check that alerts reach your phone and backups restore), splits its
  steps into parts, and the step numbers run on through the parts, so a
  citation such as "chapter 7, step 10" stays valid.
- Each step gives its messages as labelled quote blocks: "Tell the person
  first", "Ask the person" only when the person acts or approves, "Tell
  the person while waiting" for a step that runs for minutes, with a time
  from the chapter's or the tests' own figures, and "Tell the person
  after", with the result and the link where the person sees it. A step
  with no message says why in one line.
- "If something is different" and "Why the chapter works this way" close
  the chapter.

A message is an instruction said in the agent's own words, with the team's
own names and links, not a script. An "Ask the person" says what the
person will see, that it is expected, and what to tell the agent back. A
message covers only what the person wonders at that moment, in at most
five short lines, and carries no expert caveat. Such facts go in "Why the
chapter works this way".
Reason: the narration stays simple and the technical detail stays exact,
so neither the explanations nor the instructions have to bend to fit each
other. A message beside its step is said when its action comes, and the
person always knows what happens, why, what to do, and where to see the
result.

**The setup order** keeps each dependency before its use. Reason: a person
who knows the route can tell where they are and why a step comes when it
does, and no chapter needs a fact or an account from a later one.

- Chapter 1 (answer two questions) asks for the domain, where most users are, and whether the
  team wants the smallest system or the fuller one, each question
  separately. The server location and Backblaze's region depend on the
  domain and where most users are. The fuller system's two servers come
  in chapter 7 (install everything on the production servers), through the
  operating procedures that add them on any later day.
  Three things are defaults, not questions: the weekly restore drill and full backup run on Sunday
  (`weekly_work_day`); the triage agent uses the same kind of coding agent
  as the person's own (`triage_agent_coding_agent`); and the coding agent proposes
  the break-in response page, which the person corrects (chapter 10).
  Reason: each has an answer that fits nearly every small team, and each
  setting's comment or procedure says how to change it later.
- Chapter 6 (create your three production servers: app, database, and
  tools) shows the prices and has the person set the growth limits once,
  `growth_limits` in `mmx_project_settings.yml`: each pool's largest number
  of servers and its server types, and the app pool's smallest number,
  below which the triage agent never removes an app server for low load
  ([Adding and removing app servers with the load](#adding-and-removing-app-servers-with-the-load)).
  Inside the limits, the coding agent adds
  a server or a bigger type at once when a trigger arrives, and reports
  the server and its monthly cost ("Add a server", step 1, in `operating_procedures/add_a_server.md`). It asks
  first only outside them: more servers, another type, a new kind of
  server, or a new outside account. Reason: a price
  check before each new server would hold up scaling at the worst time; scaling
  must never wait for a person, and the person still decides how far the
  bill can grow. No price is written into the Stack: each one is read
  from the provider's API when it is shown, so none goes stale.
  Chapter 1 (answer two questions) also starts the domain's move to Cloudflare, the slowest wait of
  the day, which needs the password manager and the Cloudflare account
  first.
- Chapter 3 (make your server account and your systems desk) makes the systems repository's private backup at the
  Git host, and the desk's checkout becomes the team's main copy until chapter 7 moves it to `util01`
  ([The main copy of the systems repository](#the-main-copy-of-the-systems-repository)).
- Chapter 2 (get your app ready to deploy) only names the app's R2 bucket. Chapter 4 (set up your accounts and lock your systems desk) creates the app's R2 bucket
  as part of setting up the accounts at other companies. Chapter 4 also makes
  the status page's bucket and R2 key, so every key of the Cloudflare account
  is made in one chapter, and chapter 8 (check that alerts reach your phone and backups restore) only tests the status page.
  When the domain is still "Pending", Cloudflare cannot connect the status page's host
  name to its bucket, so that one step waits for chapter 8.
- Chapter 4 (set up your accounts and lock your systems desk) chooses the server provider and its location before creating the
  Backblaze account. The order matters because Backblaze's region follows
  the servers' location and is set when the Backblaze account is made.
- Chapter 6 (create your three production servers: app, database, and tools) gets the person's approval of the weekly restore drill's server
  together with the servers' own costs, at the provider's current prices.
  The approval comes in chapter 6 (create your three production servers: app, database, and tools) because chapter 7 (install everything on the production servers) starts the first drill.
- Chapter 7 (install everything on the production servers) writes MMHotline's first settings before it configures the
  servers, because MMHotline refuses to start without them. Chapter 8 (check that alerts reach your phone and backups restore) adds
  how MMHotline reaches people.
- Chapter 8 (check that alerts reach your phone and backups restore) and chapter 9 (go live) need the domain active: MMHotline's sign-in, the status
  page, and the deploy's last check all use the domain's host names.

**The initial setup, not "the first hour".** The initial setup includes
waits of hours, the domain's move above all. Reason: promising an hour
would mislead the person.

**The first release follows the same explicit deploy as every release.**
CI or the coding agent tests, builds, and pushes the image. The coding
agent records the selected tag, commits, pushes, runs `deploy` on `util01`,
and verifies the live release. Reason: the first release must prove the
team's repeatable path without requiring a CI service.

**A release to production waits for the person's approval, by default.**
`production_releases_wait_for_a_persons_approval` in
`mmx_project_settings.yml` is `true` in the template: the coding agent
shows the tested version and releases only after the person's yes. With
`false`, the coding agent releases a tested version and reports the
result. The rule lives in one place, step 4 of "A release" in
`operating_procedures/deploy_and_roll_back_an_app_release.md`, and the
release asks once, at production, not also when the app's code changes.
Staging releases and rollbacks never wait. No program reads the setting,
because only the coding agent starts a release. Reasons: a release changes
what customers see, so by default the person decides when it goes live. A
team that releases many times a day turns the approval off, and the
deploy's health check still keeps users on the old version when a new
version fails. A rollback returns to a release that passed, and waiting
for a person keeps users on the broken release.

**The saved handover.** Chapter 10 (write down how to run your system) saves the operating guide in the team's
`README.md` before it presents the result. The README opens with the
first page, what the Monkeymaxxing Stack builds, with the team's servers;
it holds the actual links, common requests, failure behavior,
measured results, and the person's next actions: at most five, in
order, each naming a person and a date or an event, or saying that it is
unassigned. The checklist holds the detailed evidence, the later checks,
and, in their own section, the growth and improvement items with their
triggers. Later operations
update the README when its links, failure behavior, or next actions
change. Reasons: a summary said only in the setup conversation is lost
when the conversation ends, and a person who returns, or a new agent
session, needs the operating summary in the systems repository. A list of
every open item gives the person no first step: in a test run it grew to 36
rows, and a new session had to pick its own first step. Related work, such
as the account protection still to add, is one action, so five actions
hold a new system's first steps.

**The team's README is for the person.** The README holds only what the
person reads, in the person's words. An instruction for a coding agent
lives in the team's `AGENTS.md`, `triage_agent_rules.md`, or an operating
procedure. A design argument or a measurement from the Stack's own tests
lives in this file. Reason: a person who opens the README at 3 a.m. needs
the links, the effects of a failure, and the next step. An agent
instruction or a design argument in the same text makes the person guess
which sentences are for the person.

**The weekly review covers what needs a person's judgment.**
[`operating_procedures/do_the_weekly_system_review.md`](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/do_the_weekly_system_review.md)
has four parts: the week's alerts, the waiting updates, the restore
drill's result, and the checklist items that are due. For the growth and
improvement items, the review checks only whether a trigger arrived. The
coding agent gathers the four parts with exact commands, then shows the
person one report with a ready proposal for each change. A trigger whose
server fits the growth limits is no proposal: the coding agent adds the
server at once and reports it in the review, as the growth limits say.
The per-server update check leaves out the systems desks, which the coding
agent cannot log in to as root; a desk's own MMWatchdog warning reaches
the week's alerts instead. The secret scan is `gitleaks detect`, the form
Debian's gitleaks 8.16 on the desk has (its `git` subcommand came in 8.19). Checks that
already alert when they fail stay out of the review: the daily server
settings comparison, the daily check for a leftover `restore01` or a server
missing from the inventory, the capacity warnings, and the failed-unit
warnings of scheduled jobs. SSH through WireGuard and closed public SSH stay
in "Check my system's protections": broken WireGuard stops the MMX runs
and the alerts, and the daily comparison warns about a changed firewall.
The README stays current because each operation updates the README.
Reasons: a weekly duty that repeats a dozen checks takes an hour, and a
person who finds nothing in it for weeks stops doing it. A check that
alerts by itself needs no person to look for its failure each week.

**Failure claims.** What the agent says about failures uses the current
inventory and test results. One app server or one database server has no
second server to take its work. Automatic database failover needs a
healthy replica. The backup settings aim to limit lost database writes to
about the last minute before a failure. The one-minute target is not a
measured limit on lost data, and a database restore time is not the time to
recover the whole site. The README records each measured result
separately, with its date and limits.
Reason: archiving can lag or fail, and MMWatchdog warns when it does. A
claim that the inventory or a test does not back misleads the person at
the moment they rely on it.

## The systems repository template

```text
README.md                                 the first page with the team's servers, operating links, failure behavior, and the next actions
talking_with_the_team.md                  the Plain English rules, example messages, and technical terms
AGENTS.md                                 the rules every coding agent reads first, including the triage rules
initial_setup/                            the ten chapters of the initial setup, done once, kept as the record of how the system was set up
operating_procedures/                     one file per later job: its steps and its verification
triage_agent_rules.md                     the triage agent's rules
CLAUDE.md                                 one line: @AGENTS.md
monkeymaxxing_stack_checklist.yml         every item of the stack: the Setup part first, in course order, then the Later part
mmx_project_settings.yml                  MMX's project settings, the apps, the people's SSH keys, the software releases
mmhotline_settings.yml                    MMHotline's settings, an MMX template that util01's run renders onto util01, with its secrets from the vault
server_management_scripts/                the helper that runs MMX on util01, the programs of the server replacement, provider scripts written by the coding agent, and first-boot data
inventories/servers.yml                   every server, its pools, the flags that tell roles which pools the server belongs to, private address, WireGuard key, and the deployed image tags
playbooks/                                every_server.yml and the operating procedures that need their own order
roles/                                    every_server, app_server, tunnel_connector_and_caddy, database_server, util_server, uploads_backup, mmwatchdog_joined_node, and the later steps' jobs_server and pgbouncer; each role's templates in roles/<role>/files/
files_used_by_several_roles/              files that more than one role or playbook uses: Cloudflare's apt signing key, pgBackRest's settings, the apps' env files, the job container, the image cleanup's units, MMHotline's backup settings
mmwatchdog_checks/                        MMWatchdog's check groups, the named groups of checks, rendered by MMX
one_time_playbooks/completed/             MMX's one-time playbooks: the triage agent's dated fixes
triage_agent_notes/                       the triage agent's notes, one per triage session, a section for each cause; open_software_findings.md ships saying "No open findings."
software_outside_the_distribution.yml     every program that doesn't come from the distribution
secrets_vault.age                         the MMX vault, created by the coding agent during the initial setup
ssh/known_hosts, ssh/config               the host keys and SSH settings the systems desk and util01 share
.gitignore                                .mmx/
```

Every value is written out in the files. An example value that the team
must replace, such as a domain or an IP address, uses the documentation
ranges (`example.com`, `203.0.113.0/24`), so a forgotten one fails loudly
instead of reaching a real machine.

A file used only by one role lives in that role's `files/`. A file shared
by roles or playbooks lives once in the project's
`files_used_by_several_roles/`, so the roles and playbooks that use the
file can't drift apart. A role reads a shared file as
`../../files_used_by_several_roles/<name>`. Several kinds of server can
run the same thing, such as the tunnel connector and Caddy on the app
servers, the load-balancer servers, and `staging01`. The shared work is
then a role of its own. One fleet stage calls the role for the app servers and the
load-balancer servers together, and a separate stage calls the role for
`staging01`.

## Who runs MMX, and which commits count

The coding agent edits the systems repository, validates and previews the
change, commits, pushes, and runs MMX. A push alone changes no server.
For configuration, the agent runs `every_server`. For a release, the agent
runs `deploy --var environment_name=staging` or `production` after updating
`deployed_image_tags`. Configuration runs before a deploy that needs new
settings. Documentation-only commits need no MMX run.

Reason: the team's coding agent owns each change and verifies the result.
A Git host cannot start a server change merely by accepting a push.

### The main copy of the systems repository

The team's main copy of the systems repository is a bare repository on `util01`,
`systems_repository.main_copy_path_on_util01`, owned by root and closed to every other user. Desks push to it and
pull from it as root over WireGuard, and `util01`'s `mmhotline` user as `root@127.0.0.1`, with the keys in
`root_ssh_public_keys`. So the same list decides who has root on the servers and who can change the repository,
and no desk or server key is registered at the Git host. A separate Git account on `util01` would protect nothing,
because every key that could push already has root there, and it would be shut out with the rest during a lock-out.
The repository refuses a force push and a branch deletion (`receive.denyNonFastForwards`,
`receive.denyDeletes`), and keeps a reflog of every change to `main` (`core.logAllRefUpdates`). With `util01`'s
sshd journal, which names each root login's key, the reflog says which key pushed each change.

Before `util01` exists, the first desk's checkout is the main copy: it has no `origin`, `publish-branch-to-main`
ends at the fast-forward of its `main`, and the vault commands commit there. The `util_server` role makes the empty bare
repository, MMHotline's clone step skips it while it is empty, and the desk pushes `main` to it after the first run
and makes it `origin` (chapter 7). The desk's own readers, the button, the WireGuard peers command, the desk review
and the lock-out button, read pushed `main` from the coding agent's checkout, `origin/main` when it has an origin
and its own `main` before, so they work before `util01` exists and while it is lost; the desk review and the
lock-out button first fetch `origin` into the checkout as the coding agent. The WireGuard peers command must read
the checkout, not `util01`: a rebuilt `util01`'s new WireGuard key is what lets the desk reach it. All four read the
checkout as data, through `fetch-pushed-main-from-the-coding-agents-checkout`: it copies the checkout's objects and
refs into a new bare repository of the reader's own account, fetches the one ref from that copy, and deletes it.
Reason: Git in a repository runs commands that the repository's own settings name, such as `core.fsmonitor`, and
`coding-agent` writes those settings, so root and `servers-mmx` never run Git in the checkout or with it as the
remote. Git also refuses another account's repository as "dubious ownership", and no `safe.directory` value reaches
the `git-upload-pack` that a local fetch starts.

The Git host keeps a private backup, `systems_repository.backup_url_at_the_git_host`, which the laptop's coding
agent pushes with the person's own login. Nothing reads from it, so a break-in at the Git host reaches no server.
A refused backup push shows commits made at the Git host; a restore from it, only when every other copy is gone,
first checks the Git host's push activity.

The one accepted loss: when `util01` is lost, commits that only `util01` had since a desk last pulled, such as the
triage agent's newest notes or a server replacement's inventory commit, are lost with it. The rebuilt `util01`
gets `main` from a desk. Reason: the case is rare, and a failing run or a leftover server makes the gap visible, so
no mechanism copies `util01`'s commits elsewhere.

### Where each command runs

The helper `server_management_scripts/run_mmx_on_util01` accepts
MMX arguments. The helper requires a clean systems desk copy on `main`, fetches
`origin/main`, and requires `HEAD` to equal `origin/main`. Over SSH, as root,
the helper first asks MMHotline to bring its copy to that commit, without the lock
([MMHotline decides which commit is trusted](#mmhotline-decides-which-commit-is-trusted)),
and runs nothing while MMHotline does not answer. Then, as the `mmhotline` user, the helper locks
`/var/lib/mmhotline/systems_repository.lock` and requires
`/var/lib/mmhotline/systems_repository` to be checked out at the systems
desk commit, which MMHotline's check brought it to. The helper never moves
the checkout.
The helper names the current lock holder at once and every minute while waiting.
Every message gives the status and stop commands for an MMX holder.
After the first minute, each message also gives the minutes waited.
The helper streams MMX output and returns MMX's exit status. The helper supplies
`MMX_VAULT_PASSWORD_FILE=/var/lib/mmhotline/mmx_vault_passphrase` and disables
prompts for commands that support `--non-interactive`.

The helper is the one way the coding agent runs MMX on `util01`. Reason:
a hand-typed copy of its steps beside it could drift from the
tested script; the script itself is short Bash that a reader can follow.

Reason: matching commits establishes exactly what runs without a second
commit-permission system. One shared lock serializes agent runs, the daily
server settings comparison, and the weekly restore drill. MMX also has node locks, so a
systems desk preview is refused on a server where an operation runs. The desk's
button does not take `util01`'s lock, so an `every_server` run from the desk can
overlap a deploy between two stages. The `app_server` role asserts that each
app's recorded live port still equals the port its find stage read, before it
changes anything, so an overlap stops the desk's run visibly. Reason for this
in place of a lock: the lock is a file on `util01`, held by another account
across a long MMX run, which the desk's unprivileged button cannot hold; the
assertion catches the harm whatever started the second run.

MMX keeps run history in `.mmx/` on `util01`; the template sets
`run_history_retention: 30d`. Read output with `mmx results` or follow work
with `mmx status` through the helper (`run_mmx_on_util01 results` and
`status`), which take no lock. MMHotline's
request page shows its run output after the run ends. Results never enter Git.

The coding agent validates local structure with `mmx validate` and uses the buttons for vault-backed work.
The coding agent never opens or prints the vault's contents (the template's `AGENTS.md`, "The rules"):
it runs `secrets list-keys` and `secrets usage`, which show key names only, through its button
(`ssh desk01-agent sudo -n -u servers-mmx run-mmx-on-the-servers secrets usage`), on pushed `main`, and the
person adds and replaces keys with `set-up-outside-services secrets` (`ssh desk01-secrets`), which commits and
pushes the vault itself. A key that command does not make, the person sets with `mmx secrets` on a copy of the
vault in the person's own desk login, and installs the copy into the coding agent's checkout ("Change the vault by
hand" in the template's `operating_procedures/rotate_a_secret.md`), so MMX never runs as root on the pulled
checkout. The coding agent's plain `mmx secrets` has no passphrase and stops with exit 4 (proved on real servers). Reason: the coding agent's provider stores
the conversation, so a secret the coding agent reads leaves the team's control. The rule is an
instruction, not a lock: the coding agent is trusted and could read the vault through the buttons.
The coding agent previews the pushed commit with `sudo -n -u servers-mmx run-mmx-on-the-servers dryrun ... --connection ssh_only`.
A systems desk runs MMX directly before `util01` exists, while `util01` is broken
or rebuilt, once after changing the vault passphrase, and for `util01`'s
own reboot. Use `sudo -n -u servers-mmx run-mmx-on-the-servers` with `--connection ssh_only` for direct production runs from the desk. MMX never reboots
the controller machine; the reboot playbook also refuses a held shared lock.

### MMHotline and commit permissions

MMHotline runs `mmx run --non-interactive --vault-password-file
/var/lib/mmhotline/mmx_vault_passphrase NAME --inventory INVENTORY` at the
judged commit. MMHotline, the helper and all timers use
`/var/lib/mmhotline/systems_repository` under
`/var/lib/mmhotline/systems_repository.lock`. MMHotline commits nothing
after a run. The request's page shows MMX output after the run ends.

Before every run, MMHotline fetches the main copy and moves its checkout
to the newest commit
([MMHotline decides which commit is trusted](#mmhotline-decides-which-commit-is-trusted)).

Every process takes `flock` before running MMX in the shared copy, and
never while it asks MMHotline for the commit. After taking the lock, the holder truncates the lock file
and writes one holder line. A waiting process shows the existing line.
MMHotline leaves the file empty during short fetch, explain and push
operations, so a waiting message must allow an unnamed holder.

Reason: MMHotline owns the approval and execution boundary. The triage
agent cannot change server settings through instructions hidden in logs.
A push decides only what the next run applies; a push starts no run.

### What the triage agent may do without a person

The team gives one answer in chapter 6,
`what_the_triage_agent_may_do_without_a_person` in
`mmx_project_settings.yml`: `every_fix_waits_for_a_person`,
`routine_fixes` (the default), or `routine_fixes_and_server_work`.
`mmhotline_settings.yml` renders MMHotline's
`rules_for_running_agent_playbooks.servers` from it: MMHotline's preset
`permission_for_every_fix` for the first answer,
`routine_fixes_without_permission` for the other two, and with the third
the six playbooks of server work listed by name
(`replace_failed_servers`, `every_server`, `destroy_replaced_servers` as
`act_then_report`; `reboot_servers_after_updates` as `warn_wait_then_act`
with `triage_agent_server_work.minutes_between_the_warning_and_a_reboot`;
`add_an_app_server_for_the_load` and `remove_server` as
`warn_wait_then_act` with
`minutes_between_the_warning_and_adding_or_removing_an_app_server`).
The reboot check `no_reboot_waits_that_may_run_now` and `util01`'s two
load checks are rendered from the same answer ([Reboots](#reboots),
[Adding and removing app servers with the load](#adding-and-removing-app-servers-with-the-load)).

- **One setting, not a hand-written block:** three places must agree with
  the answer: MMHotline's rules, the reboot check that exists only with
  the third answer (so that no coding agent starts when there is no work
  for it), and the rules text the triage agent reads. A hand-written block
  in `mmhotline_settings.yml` would hold the same fact twice. Both files
  are in `paths_only_a_person_may_approve`, so the triage agent cannot
  widen its own powers. The cost: a team that wants another MMHotline rule
  edits the template block and records a deviation.
- **The third answer is not MMHotline's `every_fix_without_permission`:**
  that preset lets `unrecognized_task` and `reboot_a_server` act at once on
  the whole inventory, so a one-time `shell` playbook or a reboot of `db01`
  or `util01` would run without a person. MMHotline's rules are per
  inventory, not per pool, so listing playbooks by name is the only way to
  allow server work and nothing else.
- **A value outside the three** stops `every_server` in its stage
  `validate_what_the_triage_agent_may_do_without_a_person`, before any
  server changes, with the three values in the message. The same stage
  checks `triage_agent_server_work`: only `app_servers`, `jobs_servers`
  and `load_balancer_servers` may be listed in
  `pools_whose_failed_servers_the_triage_agent_replaces`,
  `tries_to_replace_a_failed_server` is at least 1, the hours are at least
  0, `minutes_between_the_warning_and_a_reboot` is from 1 to 1440, the
  range MMHotline accepts for `warning_wait_minutes`, and
  `sos_waits_for_a_server_replacement_minutes` is from 0 to 60, the range
  MMHotline accepts, and `warn_waits_for_the_triage_agent_minutes` is from
  0 to 15, MMHotline's cap.
- **One approval for the whole replacement:** with the first two answers,
  the three replacement playbooks are listed as `get_permission_then_act`
  with `approvals_needed: 1`, and `replace_failed_servers` carries
  `its_approval_also_approves_in_the_same_session: [every_server,
  destroy_replaced_servers]` (MMHotline's `docs/running.md`,
  "One approval for a known sequence"). Reason: a person woken by an
  outage approves once, not three times, and MMHotline's approval page says
  before the click that the approval also covers the two later runs, once
  each, in that triage session. With the third answer the three are
  `act_then_report` and the key is left out: MMHotline accepts it only with
  `get_permission_then_act`, and refuses a named playbook that is not
  listed. `approvals_needed` is written although the design's sketch left
  it out: the pinned release's settings check refuses
  `get_permission_then_act` without it ("approvals_needed must be 1 or
  2"), which a check of the rendered file with the release's
  `mmhotline settings check` showed. 1 because the preset asks one person
  for every other fix too.
- **MMHotline judges each request at the newest commit.** It
  fetches before it judges a request. Reason: `replace_failed_servers`
  pushes an inventory commit, and the `every_server` request that follows
  must not be judged stale against an older checkout, or a person would be
  asked again.
- **The SOS waits while the triage agent replaces a server, then wakes:**
  with an outage at night, the
  triage agent replaces the failed server while the person sleeps, and the
  person is woken only if the replacement fails or takes too long.
  MMHotline holds the mechanism: `replace_failed_servers`
  carries `starts_a_server_replacement: true` with all three answers, and
  `triage_agent.sos_waits_for_a_server_replacement_minutes` comes from the
  Stack setting of the same name in `triage_agent_server_work`. When the
  marked run starts, a waiting SOS waits that long from the start instead
  of `sos_waits_for_the_agent_minutes`; MMHotline sends one warn as the
  replacement starts ("Your site is down: ..." / "The triage agent is
  replacing the server. You will be woken only if the replacement fails or
  takes longer than 7 minutes ..."), wakes the person on call at once when
  a run fails, the triage agent reports at sos, a run waits for an approval
  or a person takes over, and otherwise at the limit. The SOS's own
  resolved message, at normal priority after such a start, is the end of
  the night: the triage agent sends no "Resolved" warn of its own, only
  silent progress reports at info, the last one carrying the outcome
  ([the triage agent's rules](../skills/monkeymaxxing-stack/systems_repository_template/triage_agent_rules.md#replacing-a-failed-server)).
  Reasons: a replacement of an app server takes minutes and needs no
  person, so waking a person for it costs sleep and saves nothing; a
  failure or a hand-over still wakes at once, and the limit bounds a stuck
  replacement. Only `replace_failed_servers` is marked: `every_server` and
  `destroy_replaced_servers` run inside the replacement it started, and
  adding or removing an app server for the load is no outage. With the
  first two answers the mark makes no difference at night, because the
  approval request already woke the person; it is written so the three
  answers render one shape. The setting's default, 7 minutes, comes from the
  measurement: a replacement by the triage agent alone served the site
  again 2 m 21 s after it started, measured on test servers at Hetzner; slower
  providers get about 2 minutes more, and half again is added. 0
  turns the longer wait off; 60 is MMHotline's limit, because MMHotline
  stops an MMX run after one hour.
- **Each replacement has its own start warning and its own limit.** A
  `replace_failed_servers` run that starts while none of the session's
  replacements is in progress starts a new replacement, with its own start
  warning and its own limit (`sos_waits_for_a_server_replacement_minutes`).
  A replacement also ends when the urgent alert its warning named
  resolves. Reason: a second replacement in the same session, such as the
  agent's second try after the first one ended, must not run without a
  warning or a limit, or the person on call could wait on the earlier
  replacement's end.
- **A replacement the triage agent finishes makes two sounds,** the start
  warning and "Your site works again", both at once:
  - a warning that joins while an urgent alert waits for the triage agent
    is held with it, and never sent when the agent's report or request
    covers it or its alert resolves first;
  - a resolved message goes only to contact methods MMHotline told about
    the incident, so a resolved message for warnings that were all held
    goes to nobody;
  - after a replacement that woke nobody, the resolved message reads "Your
    site works again";
  - the start warning names the time MMHotline will really wake the
    person, the later of the replacement's limit and the urgent alert's
    own wait;
  - the start warning and "Your site works again" skip MMHotline's
    one-a-minute grouping of warnings, because the start warning says when
    the person will be woken and the end must not come late.

  Reason: without these, the person on call heard five warnings and a
  resolved message for an urgent alert that was never sent, and the start
  warning could name a wake time earlier than the real one (seen on test
  servers).
- **A warn waits for the triage agent first.** MMHotline holds a warn that
  starts a triage session for `triage_agent.warn_waits_for_the_agent_minutes`,
  rendered from the Stack setting
  `triage_agent_server_work.warn_waits_for_the_triage_agent_minutes`
  (3 by default, validated from 0 to 15 in `every_server`). Reason: the
  agent tries first, so a routine change it handles makes one sound,
  MMHotline's own warning or approval request, or the agent's report, and
  not a warning followed by the report. Nothing is dropped: a warn the
  agent does not take sounds at the end of the wait, and at once when the
  agent is not set up, its sandbox or MMHotline's copy of the repository
  is missing, or the session ended, failed or ended with no request or
  report. A warn that joins a running session, and MMHotline's own warns,
  are never held. 15 is MMHotline's cap; 0 turns holding off. The rules
  tell the agent to request the playbook run or report within the first
  minute or two of a session a warn started, well inside 3.
- **The MMHotline-down alarm escalates like an SOS.** The person on call
  is woken at the first wait, then the backup at the backup wait, where
  the backup is the named backup or, under the default
  `backup_option: everyone_available`, everyone else available. Reason:
  while MMHotline is down, no other alert reaches the team. The alarm
  does not read `escalate_if_unclaimed_after_minutes`. The alarm cannot
  see whether the person on call answered, because the answer goes to
  Pushover while MMHotline is down, so the others are woken even when that
  person is already at work; a team that wants fewer people woken names
  one backup or raises the backup's wait, as the comment on
  `wake_the_backup_after_minutes_without_a_check_in` says.
- **A notes commit keeps a request valid.** A warning or an approval of a
  playbook in `playbooks/` stays valid when the triage agent commits only
  to `triage_agent_notes/` between the request and the run, even with
  shell tasks whose values `mmx explain` cannot show (that exception
  applies only to `one_time_playbooks/`). Reason: on test servers, the
  agent's notes commit 20 seconds after its request would make the warned
  reboot stale, MMHotline would warn again, and every reboot the agent
  asked for would wait 20 minutes, not 10. MMHotline's answer for a
  warned, approval-waiting or covered request also says "Commit nothing
  more until MMHotline resumes you". The rules say it plainly too, in the
  Stack's own words.
- **A scheduled software review that finds nothing new sends no report.**
  MMHotline's review prompt says "Send the reports the team's task asks
  for. When you find nothing new, send no report", so MMHotline's frame
  and `scheduled_software_review_task.md`'s one report per review agree.
- **A new pin keeps MMHotline's state.** `mmhotline install`, which the
  `mmhotline` stage of `every_server` runs whenever the installed program
  differs from the pin, replaces the program, rewrites the unit and
  restarts MMHotline, keeping its database and settings file (MMHotline's
  `docs/how-to/upgrade.md`). It upgrades the database in place, with every
  row kept.
- **A new database never replaces the team's backup.** On a new server
  whose backup settings are in place, `mmhotline install` never backs up
  a new, empty database over the team's existing backup: when install
  itself created the database and the bucket holds a backup (or cannot be
  listed), install leaves the backup stopped and exits 1 with the steps
  to restore or to start empty in a new folder. The rebuild of `util01` is
  not affected: `every_server` restores `mmhotline.db` before
  `install_the_mmhotline_release`, and install backs up a database it did
  not create at once, without listing the bucket.
- **MMHotline's unit leaves `/proc/sys` visible, read-only.** An
  `every_server` run that MMHotline starts must read
  `/proc/sys/kernel/random/boot_id` on `util01`: MMX reads the controller's
  boot ID when a task leaves a restore owed, such as a change of a
  WireGuard peer list. With `ProcSubset=pid`, which hides `/proc/sys`
  inside the service, the triage agent's `every_server` after a
  replacement fails with "reading the boot ID of the controller machine:
  open /proc/sys/kernel/random/boot_id: no such file or directory".

### Replacing a failed server

Three playbooks replace a server of a listed pool that stopped reporting,
in three MMHotline runs in one triage session:
`replace_failed_servers`, `every_server`, `destroy_replaced_servers`. Their
programs are files in `server_management_scripts/`
(`replace_failed_servers`, `destroy_replaced_servers`,
`read_the_fleet_hub_for_server_replacement`, and the shared
`steps_for_replacing_failed_servers.bash`), so `tests/replace_failed_servers_test.py`
and `tests/destroy_replaced_servers_test.py` run them with stand-in
commands, real Git, and real `mmx validate`.

- **Which pools:** app servers, jobs servers and load-balancer servers,
  listed in `triage_agent_server_work.pools_whose_failed_servers_the_triage_agent_replaces`,
  all three by default, and the list is a setting. Reason for the default:
  their servers hold no data, and a new one starts from the repository and
  the vault alone. `every_server` and the program both
  refuse `database_servers` (a replacement copies data and changes the
  failover formation), `util_server` (`util01` runs MMX itself) and
  `staging_server` (`staging01` holds staging's database). The program
  refuses too, because a pushed setting runs in `replace_failed_servers`
  before any `every_server` has checked it.
- **One code path for the three pools:** what differs between them is
  data the program already has. The new name follows the failed server's
  own name, its letters and as many digits (`app002`, `jobs002`, `lb03`);
  the address is the pool's block from `private_ip_ranges` with the
  number; the inventory block has the same fields in every pool; and what
  "does its work" means comes from the server's own flags, in
  `check-that-this-server-does-its-work`. No table of pool facts exists,
  because each fact it would hold is in the inventory or the name already.
- **A jobs server:** the replacement never removes a server, it puts the
  new one in the failed one's place in one commit. So `remove_server`'s
  refusal of the last jobs server never applies, a production deploy (which
  stops while the inventory names a jobs server it cannot reach) runs again
  once `every_server` has installed the new server, and
  `job_containers_run_only_on_the_jobs_servers` stays as it is. A job that
  ran on the failed server rolls back with its lost database connection
  and waits in the queue for another worker. With the only jobs server
  and that setting on, no job runs until the new server runs, and the site
  keeps answering: the triage agent still requests the three runs at once
  and reports at warn.
- **A load-balancer server needs no call to Cloudflare.** Every connector
  of the apps' tunnel, on the app servers and the load-balancer servers,
  starts with the one tunnel token in the vault
  (`apps_cloudflare_tunnel_token`, written to
  `/etc/cloudflared/tunnel_token.env`), and the tunnel is locally managed:
  its routes are in `/etc/cloudflared/config.yml` from the repository. A
  new load-balancer server is one more replica of the tunnel, as `lb03`
  was in a test run on real servers, so `util01` needs no Cloudflare token for it.
  Cloudflare's documentation says the replicas of one tunnel share it, a
  request goes to the geographically nearest replica, and when that
  connection fails Cloudflare tries another replica; one tunnel takes at
  most 25 replicas. It also says Cloudflare keeps tracking a disconnected
  connection for several minutes, and offers
  `DELETE /accounts/{account_id}/cfd_tunnel/{tunnel_id}/connections` to
  remove a connector record; the replacement does not call it, because a
  record of a powered-off connector receives no request that Cloudflare
  does not retry elsewhere, and two load-balancer servers are far below
  the 25.
- **Powering off matters most for a load-balancer server:** the nearest
  replica can take most requests, so a load-balancer server that only
  looks dead, still connected to Cloudflare while its Caddy no longer
  reaches the app servers, could answer most users with errors. After a
  failed power-off of an app server or a load-balancer server the
  replacement goes on, and the triage agent's final report is an SOS, so a
  person stops the server from the provider's console. `check-that-this-server-does-its-work`
  on a load-balancer server fails when its tunnel connector's unit is
  missing, so a new one whose install stopped before the connector is never
  taken for working.
- **Three runs, not one playbook:** an MMX run on `util01` holds `util01`'s
  node job, and `every_server` has tasks on `util01`, so a nested
  `every_server` would be refused as busy, as the restore drill's nested
  run would.
- **A new app, jobs or load-balancer server serves first and installs its
  waiting security updates last.** The last fleet stage of
  `every_server`, `install_the_waiting_security_updates_on_new_servers`,
  runs `unattended-upgrade --no-minimal-upgrade-steps` on those pools with
  the marker file the role's task used, so an existing server skips it. The
  role's task `install_the_waiting_security_updates_on_a_new_server` skips
  the pools. Why: on a team's only app server, a replacement's site stayed
  down while the new server installed 63 updates (227 to 426 seconds in
  the measured replacements), and the longest replacement (9 minutes 51
  seconds) woke the person on call at the limit 8 seconds after the site
  answered. What it costs: the new server serves for 2.7 to 6.6 minutes
  (measured stage length on Hetzner's `debian-13` image, 74 days old in the
  test; about 1.5 to 2.5 minutes with the flag, an estimate) on the image's
  packages. Only WireGuard's UDP port (443 outside, redirected to 51820) is public, requests reach the
  server only through the Cloudflare tunnel to Caddy on loopback, and none
  of the 63 waiting packages is on the request path. The kernel's fix
  waits for a reboot in either order. A needed reboot follows the existing
  paths (`reboots_that_may_run_now`, the maintenance window, step 7 of
  `add_a_server.md`); nothing changed there. Database servers, `util01`
  and `staging01` keep the old order: needrestart only lists the services
  of a database server, so a Postgres started before the update would keep
  the old libraries until the weekly window, and no replacement of a
  failed server waits for them. `--no-minimal-upgrade-steps` installs in
  one dpkg run instead of 32 (minimal steps let a shutdown interrupt the
  upgrade; a first run under MMX is not shut down), in both places. No
  setting: the cost is a few minutes of serving on fixes that are off the
  request path, with no public port added. The load check ignores a
  server's readings until its marker exists, so
  `record_when_each_app_server_installed_its_waiting_security_updates`
  runs after the new stage (still a `for_each_node` loop, so a run limited
  to `util01` works). The triage agent's last report takes its minutes
  from the site's answer, not from the end of `every_server`, which now
  ends 3 to 7 minutes later. The measurements below show the gain.
- **Where the minutes go** (a run on test servers that replaced a
  server that never came back from its reboot, the agent alone; the app
  pool held one app server, so the site was down meanwhile):

  | Part | From to | Time |
  | --- | --- | --- |
  | The failed reboot run ends; the agent diagnoses and requests the replacement | 18:03:05.8 to 18:04:10 | 65 s (a plain failure adds the trigger instead: `node_reports` 78 to 89 s after the power-off) |
  | `replace_failed_servers`: the provider's create and boot, the wait for first boot and for `util01` to reach the new server over WireGuard (its runtime peer), the commit | 18:04:10 to 18:05:44 | 94 s (70 s on the person's run of the same day) |
  | MMHotline starts the next run | 18:05:44 to 18:05:52 | 8 s |
  | `every_server` until the site serves | 18:05:52 to 18:10:36.6 | 284 s; the whole run took 397 s on the person's run |
  | `destroy_replaced_servers`, after the site serves | 18:10:48 to 18:10:52 | 4 to 6 s, no downtime |

  From the start of the replacement to a serving site: 6 minutes 27
  seconds in that run. A later round of three replacements (the agent alone,
  from `mmx results --json` on `util01`) measured every stage; the
  replacement's start to a serving site took 9 minutes 51 seconds, 5
  minutes 40 seconds, and 9 minutes 16 seconds with one approval (three
  replacements, in that order). Seconds after the run's start; a stage
  ends when its slowest server ends:

  | Stage of `every_server` (or run) | Plain failure, 9 m 51 s | Agent alone again, 5 m 40 s | One approval, 9 m 16 s |
  | --- | --- | --- | --- |
  | `replace_failed_servers` (create, boot, first boot, WireGuard, commit) | 66 s | 49 s | 65 s |
  | `every_server`: the checks on `util01` and `install_jq_and_python3` | not saved | 18 s | 21 s |
  | `every_server`: the common role (the new server's first configuration, with `install_the_waiting_security_updates_on_a_new_server`) | not saved | 228 s | 372 s |
  | `every_server`: `util01`, MMHotline, the fleet hub join, the database servers | not saved | 8 s | 9 s |
  | `every_server`: the app server's stage | not saved | 15 s | 25 s |
  | `every_server`: the tunnel connector and Caddy | not saved | 10 s | 15 s |
  | `destroy_replaced_servers`, after the site serves | 4 s | 4 s | 4 s |

  The variable part is the common role's stage: the new server installs
  its waiting security updates there (227 to 426 seconds across the
  measured runs, depending on how many updates its image lags behind). The
  rest of `every_server` takes about 60 to 80 seconds, and the replacement
  itself about a minute. With serve-first (the entry above) the stage
  moved after the site answers, and the rules say "about 3 minutes", as
  measured below. (The
  first replacement's `every_server` took 508 seconds in all; the reading
  program failed on it, so its per-stage split is not saved. A
  fourth replacement, 4 minutes 2 seconds of `every_server`, spent 190
  seconds in the common role.)

  Measured after serve-first (three replacements on test servers at
  Hetzner, the agent alone, the only app server powered off): the replacement's start to a
  serving site 2 m 21.5 s, 2 m 14.8 s and 2 m 11.4 s; the failure to a
  serving site 4 m 15.8 s, 4 m 1.9 s and 4 m 34.0 s. The update stage then
  runs after the site serves, so `every_server` ends later, and the rules'
  first report says "about 3 minutes".

  After serve-first, per stage (run seconds from the run's creation, the first
  replacement; the other two are within 15 seconds, except the new stage):

  | Stage | Time |
  | --- | --- |
  | `replace_failed_servers` | 48 s (49 and 52 s in the other two) |
  | The gap before the next run starts | 20 s |
  | `every_server` stages until the first 200 answer | at +73 s (refuse and validate 1.3 s, `install_jq_and_python3` 17.6 s, the common role 39.9 s, `util_server` 42.4 s, `mmhotline` 43.0 s, `database_server` 46.7 s, `app_server` 64.0 s, the tunnel connector and Caddy 72.1 s) |
  | `install_the_waiting_security_updates_on_new_servers`, after the site serves, one dpkg transaction | 80 to 96 s (92.6, 96.1, 80.1) |
  | `destroy_replaced_servers` | 5 s |

  Cuts considered, with their saving and the protection each touches:

  | Cut | Saves | Protection it touches | Done |
  | --- | --- | --- | --- |
  | `every_server` on the new server and the servers that must learn of it only | at most about 70 s (the stages where another server is slower than the new one) | A run that touches every server keeps all of them equal to the repository: peers, firewalls, the database servers' `pg_hba.conf` (the new address), every Caddy's list, MMWatchdog's settings. The servers that must learn of a new app server are the database servers, `util01`, the load-balancer servers and the other app servers, which is nearly all of them | No: the saving is unmeasured, and which servers must learn differs by pool (a jobs server needs the database and `util01`; a load-balancer server needs every app server). Needs the per-stage times from the rerun, then one rule for what each pool's new server forces |
  | Run the app server's and the tunnel connector's stages before the database servers' and `util01`'s | unmeasured | The app server needs the database servers to admit its address first | No: the order is a dependency |
  | A shorter poll in the waits | 0 s | None | Nothing to cut: `wait_for` polls every second and the host-key wait every 2 seconds (at most 4 s with its connection timeout) |
  | More installs in first boot (podman, Caddy, `cloudflared`) | at most 10 to 20 s | First boot's list of packages would repeat the roles' lists | No: WireGuard comes up last in first boot, so `replace_failed_servers` already waits for it, and the roles' installs would still wait for apt's lock |
  | One run for the three playbooks | 8 s | `every_server` has tasks on `util01`, which a nested run holds | No: see "Three runs, not one playbook" above |
  | The 65 seconds and the 8 seconds | | The agent's diagnosis and MMHotline's start | Not the Stack's to cut |

  The default of `sos_waits_for_a_server_replacement_minutes` is 7: Hetzner measured
  2 minutes 21 seconds at most from the replacement's start to a serving
  site; slower providers take longer, up to about 2 minutes more; with half
  again added that gives about 7. A failed replacement, a hand-over or an
  SOS report wakes the person at once regardless, so the limit only
  matters for a slow replacement that is still working. A team at a fast
  provider may lower it.
- **`destroy_replaced_servers` tells MMX each destroyed server is gone.**
  After the provider confirms a destroy, or no longer lists the server, it
  runs `mmx mark-node-work-failed --node NAME --json` in `util01`'s
  project. A failed reboot run, for example, leaves the unconfirmed work of
  the server in `mmx status` until MMX is told the server is gone. Exit 0:
  recorded or nothing unconfirmed. Exit 2: MMX reached the server although
  the provider says it is destroyed, which is wrong, so the run stops,
  commits nothing more and exits 1 (a rerun asks MMX again). Exit 3 or 4:
  the output says so and the destroy does not fail, because the server is
  gone and only MMX's history is untidy.
- **The replacement's commit subject** is "Replace app001 with app002": the
  failed server may be a bad new server that never reported, so the subject
  names no cause.
- **The playbook's refusals decide, not the agent's judgment.** For a
  failed server of a listed pool the triage agent requests
  `replace_failed_servers` each time. The playbook refuses by its own
  rules (tries, a failure within
  `hours_after_a_replacement_in_which_another_failure_of_the_pool_needs_a_person`,
  the bound, the limits). The rules' fixed 24-hour returning-fault rule does
  not apply: in a test on real servers the agent twice refused to replace and quoted
  it against the replacement's own setting.
- **The trigger is the fleet hub's check `node_reports/NODE`,** at warn,
  which joins the site's SOS session; a failing site alone is not the
  trigger. A reboot that never came back is the same case, requested at
  once ([Reboots](#reboots)).
- **State lives in Git trailers, the provider's list and the fleet hub,**
  never in a file on `util01`: the replacement commit carries
  `Server-pool`, `Replaced-server`, `Replaced-server-provider-id`,
  `Replacement-server`, `Replacement-server-provider-id` and
  `Replacement-try`; the cleanup commit carries `Server-pool` and, for
  each destroyed server, `Destroyed-server` and
  `Destroyed-server-provider-id`. A replacement whose failed server no
  cleanup commit names is unfinished. Reason: a triage session that dies
  half way, or a rebuilt `util01`, loses nothing, and every playbook can
  be requested again safely. A server name is never used twice, so a name
  identifies a server across the whole history.
- **A target** is a server of a listed pool that the hub calls `silent`
  outside a whole-server maintenance window whose `until` is later than
  now, or silent after a failed reboot; or the newest new server of an
  unfinished replacement that the hub does not list or that fails
  `check-that-this-server-does-its-work` over SSH from `util01` (a bad new
  server, replaced as the next try). `waiting_for_first_report` is never a
  target: right after a `util01` restart a dead server shows it before it
  turns silent. A server a desk adds by hand, which the hub does not list
  yet, is never a target.
- **Every refusal comes before anything is created or powered off,** with
  exit 1 and a line naming the reason: the lock-out; more than half of the
  servers silent at once; a silent server outside the listed pools; a pool
  above its `growth_limits` largest number, or a server type outside its
  `server_types`; a try above `tries_to_replace_a_failed_server`; a
  replacement in the pool finished within
  `hours_after_a_replacement_in_which_another_failure_of_the_pool_needs_a_person`;
  the provider's list or the Git host not answering; a pool that used
  every number up to 254, its block's last address; and an inventory on
  `main` whose node block or one-line nodes list the edit cannot find.
- **"More than half of the servers silent at once" is a bound,** as the
  pools' growth limits are: it stops a run from powering off and
  replacing most of a healthy fleet when `util01` itself is cut off from
  the servers. It counts every server but `util01`, the systems desks and
  the restore servers: with `app001` and `db01`, `app001` silent is 1 of 2
  and is replaced; both silent is 2 of 2 and is refused.
- **The failed server is powered off first, never destroyed then,** by
  `power_off_a_server_at_the_provider` with its ID: the trailer's ID for a
  new server of an earlier replacement, otherwise the provider's entry
  that matches both the name and the public address. Reason: a server
  that only looks dead can keep its tunnel connection and, once
  `every_server` drops it from the database's peers, serve errors to a
  share of users with no alert. A failed power-off is reported and does
  not stop the replacement. The disk stays for evidence until the new
  server does its work.
- **The new name is one above every number the pool ever used:** in the
  inventory's Git history, in the provider's list (a desk's server
  created and not yet committed), and in the trailers.
- **The create is the restore drill's:** the drill and
  `replace_failed_servers` share
  `server_management_scripts/steps_for_a_server_this_run_creates.bash`
  (first-boot data, the create with a receipt, the destroy by the
  receipt's ID, the runtime WireGuard peer on `util01`, the host key over
  WireGuard). The new server peers with `util01` and every systems desk
  from its first boot, so a desk reaches it after
  `update-this-desks-wireguard-peers`.
- **The commit comes from the playbook's own clone,** a `git clone --local`
  of `util01`'s copy with `origin` set to the main copy on `util01`, at `origin/main`,
  never in `/var/lib/mmhotline/systems_repository`, which MMHotline keeps
  at the judged commit. The inventory edit replaces the failed node's
  block with the new one, with `server_type` and `location`, and the name
  in the pool's nodes list; it adds the host key, moves each unfinished
  one-time playbook that names the failed server to
  `one_time_playbooks/completed/`, and runs `mmx validate`. The commit is
  pushed by `util01`'s `mmhotline` user, whose key is in `root_ssh_public_keys`, so
  the `every_server` request that follows runs at the new commit. A refused push, such as after a desk's
  push, is redone on the new `main`, up to 3 pushes; the run stops when
  the failed server left the inventory or the new name is taken there.
- **The exit trap destroys only the server the run created,** by the
  receipt's ID, when its commit was not pushed, and removes its runtime
  peer. Nothing else is ever destroyed by `replace_failed_servers`. When
  that destroy fails, the attempt directory keeps the receipt and the
  output names the ID; the daily leftover check warns about a server at
  the provider that is not in the inventory.
- **`destroy_replaced_servers` destroys by trailer ID only, after the new
  server works:** the newest new server must report to the hub and pass
  `check-that-this-server-does-its-work`; otherwise nothing of the chain
  is destroyed. An ID the provider lists under the name of a server in the
  inventory is refused, so a damaged trailer never destroys a server in
  use. An ID the provider no longer lists counts as destroyed, so a rerun
  after a destroy that worked but whose commit was lost finishes cleanly.
- **The last lines of each run's output** say what exists at the
  provider and in the inventory: MMHotline gives the triage agent the last
  16 KiB of a run's output (`playbook_run_output`), which the agent copies
  into an SOS.
- **Two time limits, fixed:** each program stops after 30 minutes (a
  standard `timeout` sends TERM, so the exit trap runs); a replacement
  takes about 3 minutes for one server (measured on test servers), and the limit keeps a stuck run
  well inside MMHotline's one-hour limit for a run.

### Adding and removing app servers with the load

With `routine_fixes_and_server_work`, the triage agent adds one app server
when the app servers stay busy and removes the newest when a week's load no
longer needs it, inside `growth_limits.app_servers`: from
`smallest_number_of_servers` (1 by default; the growth item
`second_app_server` sets 2) to `largest_number_of_servers`. Built after the
replacement, with its pattern: playbooks that find their own server and
refuse what they may not do, programs in `server_management_scripts/`
tested with stand-ins (`tests/add_an_app_server_for_the_load_test.py`,
`tests/remove_an_app_server_for_the_load_test.py`), commits from the
playbook's own clone pushed by `util01`, state read from Git trailers, the
fleet hub and the provider's list, never from a file of its own on
`util01`.

- **One rule, in one program, for the checks and the playbooks:**
  `check-whether-the-load-changes-the-app-pool` (in
  `roles/util_server/files/`, installed on `util01`, Python 3) reads the
  fleet hub's readings of every app server's
  `cpu_is_below_the_app_pool_headroom_limit` with `mmwatchdog fleet
  readings --node-group app_servers` and answers add, remove, none, or
  stopped by a bound. `util01`'s checks `app_servers_to_add_for_the_load`
  and `app_servers_to_remove_for_the_load` run it, and so do
  `add_an_app_server_for_the_load` and `remove_server` without
  `server_name` (through `read_the_app_pool_load`, as root), so the check
  that starts the triage agent and the playbook that acts cannot disagree,
  as with the reboot's `check-whether-a-reboot-may-run-now`.
- **Add:** the average of each app server's lowest reading over
  `minutes_of_high_load_before_an_app_server_is_added` (15) is above the
  limit the readings record, 70 × (n − 1) / n percent, the headroom rule of
  `mmwatchdog_checks/app_servers.yml`: the pool's CPU, spread over one
  server fewer, stayed above 70%. The limit comes from the readings, so
  `app_servers.yml` stays its one home. The lowest reading means "stayed
  above", as MMWatchdog's own 15-minute warning does.
- **Remove:** each app server's busiest reading over
  `days_of_low_load_before_an_app_server_is_removed` (7), added up and
  spread over two servers fewer than the pool (at least one), stays below
  `cpu_percent_below_which_the_app_pool_can_spare_a_server` (50): the
  smaller pool would still carry the week's peak with a server to spare.
  Adding up each server's busiest reading counts more than the pool ever
  used at once, so the rule errs toward keeping the server. Reasons for
  the defaults: 20 points under the add's 70%, so the load must grow by
  40% over the week's peak before the smaller pool asks again; and a week,
  because a server costs cents a day while each change costs a triage
  session and the team's attention, so daily and weekend lows never
  remove a server. 7 is the most: the hub keeps 8 days of readings.
- **No pause setting: the windows count only the readings of the present
  pool size.** Each reading records its check's limit, which differs for
  every number of app servers (70, 35, 47, 53, 56, ...), and
  `every_server` writes the new limit when the pool changes. A window with
  a reading of another limit, or one that an app server's readings do not
  cover (a new server, a silent one), calls for no change; so does a hub
  whose `app_servers` differ from the inventory's (`every_server` has not
  run since the change). So after an add the next add waits until the new
  server has reported for 15 minutes, and after any change the next
  removal waits a whole week. Two candidates were weighed: a pause setting
  read from the commits' times, or the readings' own limits. The second
  needs no setting, measures from when the pool really changed size, and
  guards what a pause from the commit misses: after a removal, the other
  servers' older readings come from the bigger pool and understate their
  load, so a second removal on them would be a silent wrong result.
- **Which server is removed: the newest, the highest number.** Names are
  never used twice, so it is the last one added; the rule is deterministic
  and needs no record of why a server was added. The smallest number,
  not a record, keeps the servers the team wants for failures. A pool of
  mixed server types is a bound: the rule counts every server alike, so a
  removal there waits for a person.
- **Which server is added: one more like the pool's newest,** its type and
  location. The newest holds the team's latest choice, such as a bigger
  type that replaced the first servers; the type must be in the pool's
  `server_types`.
- **The add refuses before anything is created:** the lock-out; the
  largest number; an app server that does not report, or an unfinished
  replacement (the replacement comes first, and the pool's load is not
  known meanwhile); a type outside `server_types`; the provider's list or
  the Git host not answering; and the Postgres connection budget of
  `operating_procedures/add_an_app_server.md`, computed with each app
  server's CPU count read over SSH: `WEB_CONCURRENCY` times connections
  per worker process (the app's optional
  `database_connections_per_worker_process`, else `RAILS_MAX_THREADS`, else
  3: a non-Rails app's pool, such as node-postgres's 10, would otherwise be
  counted at Rails' 3), twice for a deploy, one
  worker process per job container, 15 for the system, or 54 shared
  through PgBouncer; above 70 the add refuses with the numbers. A server
  added past the database's connections would be a silent wrong result
  until the next deploy fails, so it is guarded in code.
- **The removal takes the server out of service first,** by `remove_server`'s
  own stages, the same ones a person's removal uses; then its last stage,
  only without `server_name`, checks over SSH that the server's tunnel
  connector is stopped and every other app server passes
  `check-that-this-server-does-its-work`, commits the removal (inventory,
  `ssh/known_hosts`, one-time playbooks), and destroys the server by the ID
  of the provider's entry that matches both its name and its public
  address, never by name. Destroying before `every_server` is safe: the
  server is out of the tunnel and every Caddy list, and its peers and
  firewall lines name a server that no longer exists. `remove_server`
  reads the server's name from one stage's output for every later stage,
  and its stages select by name with `when`; a new stage refuses the only
  app server, which MMX's "except_nodes leaves no node" refused before.
- **One playbook for removal, not two:** `remove_server` without
  `server_name` is the load's removal, because MMHotline's requests take
  no variables and taking an app server out of service must stay one
  sequence; a separate playbook would copy its stages.
- **Under which rule:** both run under `warn_wait_then_act` with
  `triage_agent_server_work.minutes_between_the_warning_and_adding_or_removing_an_app_server`
  (10), because a change that is not urgent waits a set time in which a
  person can stop it: slow pages are no outage. The `every_server` after
  each runs at once, as for the replacement. With the other two answers no
  check exists on `util01` and the two playbooks are not listed: the
  app servers' CPU warning sounds once, and the triage agent's report with
  the commands follows at info, because an approval request is an SOS and
  slowness wakes no one; the weekly review proposes a removal.
- **The triggers wake no one and start one session per change:** warn,
  because info never starts a session; one check for the pool on `util01`,
  not one per app server; `alert_after_failing_for: 0s` and
  `recovered_after_healthy_for: 0s`, because the program already looked
  over the whole window, and right after a change the window starts again,
  so the alert closes and the next change brings a new one. The removal's
  check runs hourly, the add's every minute. After Stop, the check stays
  failing, so no new session starts; the weekly review shows the waiting
  change.
- **One sound at the start of a change; the end is silent:** a scale-up or scale-down is routine work, not an
  outage, so the person hears MMHotline's warning with Stop and nothing
  more, unless the change fails or is refused. With
  `routine_fixes_and_server_work`, each app server's own
  `cpu_is_below_the_app_pool_headroom_limit` is info, because `util01`'s
  add check reads the same readings for the whole pool and starts the
  session; a warn on each busy app server too would ring once more for
  each. So that the info costs no notice, the add check also fails when
  the pool holds its largest number (the rule's `stopped_by_a_bound`), and
  the triage agent then reports the person's choices at info. A removal
  that a pool of mixed server types stops raises nothing, as before: no
  one waits for it. The triage agent's progress reports and its outcome
  report, with the server, its monthly price (for a removal, the price that
  stops) and the number of app servers now, are all info; MMHotline's
  warning before the run is the only sound. The triage agent reports at
  warn only when the add or the removal fails or is refused, and says which
  refusal needs a person. With the other two answers the busy warning
  sounds once and the agent's report is info. The resolved messages of `util01`'s check after the change are
  low priority in Pushover, without a sound.
  The start is one sound: `util01`'s
  check is warn, which starts a triage session, but MMHotline holds that
  warn for `triage_agent.warn_waits_for_the_agent_minutes` (3). The
  triage agent requests the playbook within the first minute or two,
  MMHotline's own warning with Stop is the one start sound, and the held
  warn is never sent. So the person's timeline for a load change is: the
  held warn, the request, MMHotline's warning with Stop, silent progress,
  a silent end.
- **The price** comes from a fifth provider script,
  `read_the_monthly_price_at_the_provider`, which wraps the price request
  each provider guide names; the add's last lines give the new server's
  monthly price, the removal's the price that stops. A price that cannot
  be read is left out, never a reason to stop.

### MMHotline decides which commit is trusted

MMHotline is the one place that says which commit of `main` runs, for its
own MMX runs and triage agent runs, for the helper, and for `util01`'s
scheduled jobs. The template sets
`triage_agent.trusted_commits: every_commit_on_origin`: MMHotline trusts
every commit on `origin`, the main copy on `util01`. Nothing is signed, and
no commit waits for review.

Reason: only a key in `root_ssh_public_keys` can push to the main copy
([The main copy of the systems repository](#the-main-copy-of-the-systems-repository)),
and each of those keys, every desk's production key and `util01`'s
`mmhotline` key, is already root on every server. A signature by the same
keys proved nothing that the push itself does not. The Git host holds only
a backup that nothing reads, so a break-in there reaches no server.

What protects the main copy without signatures:

- **Who can push:** only the keys in `root_ssh_public_keys`, as root over
  WireGuard. A person's leaving takes the desk's key out, and the run on
  `util01` ends its push rights with its root login.
- **The triage agent cannot push.** It runs in MMHotline's sandbox, with no
  Git credential. MMHotline takes its commits as a bundle and pushes them
  as the `mmhotline` user only when they change nothing but regular files
  in `one_time_playbooks/` and `triage_agent_notes/`; anything else waits
  for a person. `every_server` refuses `triage_ssh_public_key` among
  `root_ssh_public_keys`, compared by the key without its comment, so the
  triage key never gets push rights.
- **History only grows.** The main copy refuses a force push and a branch
  deletion. Every desk, the laptop and the Git host's backup hold copies,
  so a rewrite shows as a refused pull or a refused backup push.
- **Who pushed is on record.** The main copy's reflog and `util01`'s sshd
  journal name the key and the time of each change to `main`
  ([Respond to a break-in](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/respond_to_a_break_in.md#an-unknown-commit-in-the-systems-repository)).
- **A lock-out trusts nothing.** During a lock-out MMHotline's settings have
  no `triage_agent` section, so MMHotline answers no commit, and the jobs
  run nothing new.

**The lock order.** MMHotline's copy lock is
`/var/lib/mmhotline/systems_repository.lock`, the same file the jobs and the
helper hold, and MMHotline's commit check waits for it with no time limit,
while an MMX run can hold it for up to an hour. So every caller asks
MMHotline first, without the lock, and takes the lock only after the
answer: MMHotline takes and releases the lock inside the check. No caller
calls `mmhotline` while it holds the lock, and no MMHotline-started MMX run
waits for anything a caller holds besides the lock itself, so no cycle
exists. `tests/run_mmx_on_util01_test.py` fails when `mmhotline` is called
while the lock is held.

The Stack has no commit check of its own beside MMHotline's. Reason: one
place that decides serves every runner, and two checks could disagree.

CI is optional. When a team has CI, CI tests, builds, and pushes an image.
Without CI, the coding agent tests, builds, and pushes the image on the
laptop, in a container, with the person's registry login. In either
case, the coding agent updates the image tag, commits, pushes, and deploys.
CI needs registry access, never server SSH keys or the vault passphrase.

### Scheduled server settings comparison

`compare_every_server_with_the_repository.service` runs only the trusted commit ([MMHotline decides which commit is trusted](#mmhotline-decides-which-commit-is-trusted)) under the shared lock and runs
`mmx dryrun every_server` daily, three and a half hours after `nightly_work_starts_at` (04:30 UTC in the template). Only exit 0 passes. Exit 1
means failed work, 2 means proposed changes, 3 means an incomplete check,
and 4 means a command error. Every nonzero result fails the systemd unit,
so MMWatchdog's existing systemd check warns. Read the cause in
`journalctl -u compare_every_server_with_the_repository`, correct the cause, and rerun
the check. No automatic apply or timed retry follows a failure.

Reason: a preview that could not inspect every required task does not
prove that the servers match the repository. The agent decides and verifies the correction.

A shell task whose dryrun runs a program that the same run installs, such
as `find_the_live_and_new_web_ports`, is a check (`changed_when: false`):
on a new server the program is not there yet, and MMX reports such a check
`not_checked` after an earlier task would change the server, so the preview
before a new server's first run ends with exit 3, as "Add a server"
says, not exit 1. A separate task, `report_the_apps_not_on_the_deployed_image_tags`,
reports the change when a server runs another release than
`deployed_image_tags` names. Reason (proved on real servers): with
the change report on the check itself, the dryruns before `app002`'s and
`staging01`'s first runs failed reading the missing program's empty
output as JSON. `tests/invariants_test.py` keeps such tasks checks.

A shell task whose program only reads, and so runs in a dryrun too, writes
the program once, in its `env` as `PROGRAM`, with `script: bash -c
"$PROGRAM"` and the same `dryrun` (`python3 -I -c "$PROGRAM"` for Python).
A task whose dryrun must do less passes the program an argument, such as
`end_the_clients` or `only_count_the_clients`. Reason: MMX's
YAML has no anchors and its `shell` no read-only shorthand, so a program
pasted into both `script` and `dryrun` could drift between the two.

## One inventory for staging and production

All servers are in `inventories/servers.yml`, and `default_inventory` is
`servers`. `staging01`, when the team has it, is in its own group,
`staging_server`.

Reason: `util01` serves both staging and production. `util01` peers with
`staging01` over WireGuard. The MMWatchdog hub on `util01` watches
`staging01`, and `util01`'s SSH key reaches `staging01`.
With two inventories, a run with the staging inventory
would rewrite `util01`'s WireGuard peers and hub settings from a view that
lacks the production servers. One inventory gives every server one view of
the whole system. A deploy names its environment
(`--var environment_name=staging`), and its fleet stages select the group
that `app_server_group_of_environment` names for it: `app_servers` or
`staging_server`.

## Servers, groups, and private addresses

"Production servers" means the app servers, database servers, and utility server, `util01`.
Systems desks, staging servers, and temporary restore servers are separate.

| Server | Inventory group | Group flag | Private address | Notes |
| --- | --- | --- | --- | --- |
| `util01` | `util_server` | `is_util_server` | `10.20.0.1` | |
| `staging01` | `staging_server` | `is_staging_server` | `10.20.0.2` | The app server and database server roles, for staging, on one server |
| `app001`, `app002`, ... | `app_servers` | `is_app_server` | `10.20.1.N` | N is the server's number |
| `db01`, `db02`, ... | `database_servers` | `is_database_server` | `10.20.2.N` | |
| `jobs001`, ... (later step) | `jobs_servers` | `is_jobs_server` | `10.20.3.N` | Only the apps' job containers: no Caddy, no tunnel connector ([Jobs servers](#jobs-servers)) |
| `lb01`, `lb02` (later step) | `load_balancer_servers` | `is_load_balancer_server` | `10.20.4.N` | The tunnel connector and Caddy, in place of the app servers' ([Load-balancer servers](#load-balancer-servers-a-later-step)); the group is empty until then |
| `restore01` (only during a drill or an inspection of data from before a bad database change) | `database_restore_servers` | | `10.20.8.1` | SSH over WireGuard, peered only with `util01`. During a recovery after losing every database server, the group holds the new database server instead. |

The private address is the node variable `private_ip`; names resolve
through `/etc/hosts`, rendered from the inventory. The stack is designed
for dozens of servers, so 254 addresses per pool is far beyond the intended
system size.

MMWatchdog's node groups equal the server's inventory groups, so
MMHotline's dashboard draws one box per pool.

### The group flags

A role can't ask which groups its server is in, so the inventory carries
one flag per group: false in the inventory's `vars`, true in that group's
`vars`. The fleet stages pass the flags to the roles as inputs, and the
roles' node tasks and templates test them to choose a server's software and
settings. The firewall and the WireGuard peers don't use the flags: they
come from one table ([Which pool talks to which](#which-pool-talks-to-which)).

```yaml
# inventories/servers.yml
vars:
  is_app_server: false
  is_database_server: false
  is_util_server: false
  is_staging_server: false
  is_jobs_server: false
groups:
  app_servers:
    nodes: [app001]
    vars:
      is_app_server: true
      mmwatchdog_check_file: app_servers.yml
```

```yaml
# playbooks/every_server.yml
- id: every_server
  nodes: all
  except_nodes: database_restore_servers
  node_tasks:
    - role: every_server
      inputs:
        is_app_server: "{{ .vars.is_app_server }}"
        # is_database_server, is_util_server, is_staging_server, is_jobs_server the same way
```

```yaml
# roles/every_server/main.yml
- id: confine_app_containers_with_apparmor
  when:
    any:
      - "{{ .inputs.is_app_server }}"
      - "{{ .inputs.is_jobs_server }}"
      - "{{ .inputs.is_staging_server }}"
```

Each group flag has a distinct name, because MMX refuses two groups that
set the same variable for a node.

### Each pool's MMWatchdog checks

Each pool's group also names its own MMWatchdog check file, with the
same name in every group: `mmwatchdog_check_file: app_servers.yml`, a file
in `mmwatchdog_checks/`. Each server is in one pool, so no node gets two
values. The four MMWatchdog stages of `every_server.yml` pass
`{{ .vars.mmwatchdog_check_file }}` to `mmwatchdog_joined_node`, which
writes, checks, and installs `every_server.yml` and that one file, and
deletes any other file in `/etc/mmwatchdog/check_groups`. `staging01`
names `database_servers.yml`, because it runs Postgres. `util01`'s own
role installs `util_server.yml`, and `playbooks/systems_desk.yml` passes
`systems_desks.yml`, because the desk is named on the command line, which
`mmx validate` cannot read.

So a new pool adds its check file and one line in its group, and no role
or playbook changes ([Add a new kind of server pool](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/add_a_new_kind_of_server_pool.md),
decision 5). Without this setting, each pool would need an input, two file
tasks, a list entry, and a flag in five stages.

- **Choosing the file from the pool's name alone was rejected:** MMX's
  references have no "is this node in that group" test, and a node record
  carries no list of its groups. A loop over every group with a condition
  per member still resolves each group's `template` path during
  validation, so every group, `database_restore_servers` included, would
  need a check file, and the loop would split the files from the block
  whose change restarts MMWatchdog.
- **The template path reads a role input under `path_exists`:** the stage
  `mmwatchdog_joins_the_fleet_hub_before_the_roles` runs the role only on
  a server MMWatchdog already watches. The MMX release that
  `stack_software.mmx` pins resolves role inputs in such a path; an
  earlier MMX refuses the template in `mmx validate`.

### Which pool talks to which

A **server pool** is an inventory group with an address block in
`vars.private_ip_ranges`. Every server is in exactly one pool, and its
`private_ip` lies inside the pool's block, because the address plan's
third number names the pool. `database_restore_servers` has no block, so it is
not a pool ([The weekly drill](#the-weekly-drill) wires
`restore01` itself).

Which pool connects to which is one table in the inventory's `vars`,
`connections_between_server_pools`:

```yaml
connections_between_server_pools:
  - from_pool: app_servers
    to_pool: database_servers
    tcp_ports: [5432, 6432]
    why: The apps' web and job containers use Postgres, directly on 5432 or through PgBouncer on 6432. Nothing listens on 6432 until PgBouncer runs.
  - from_pool: app_servers
    to_pool: app_servers
    tcp_ports: ["8001:8099"]
    only_while_this_setting_is_false: tunnel_connector_and_caddy_run_only_on_the_load_balancer_servers
    why: While the app servers run the tunnel connector and Caddy, Caddy on each app server sends requests to every app server's web containers.
```

Each line makes every server of `from_pool` and every server of `to_pool`
WireGuard peers in both directions, because WireGuard drops packets from a
key it doesn't know. Each line also opens the firewall of every `to_pool`
server to every `from_pool` server on `tcp_ports`, on `wg0`; the
connecting side needs no rule, because outgoing connections are allowed.
`why` is required. A line with `only_while_this_setting_is_false` counts
only while that setting is false: once the load-balancer servers carry the
requests, the app servers stop peering with each other and close their web
ports to each other, as one line's change.

The rules that hold for every pool stay code, listed in the comment above
the table and in the role: every server peers with `util01` and every
systems desk and admits SSH from both; every server but `util01` admits
MMX's 7443 from `util01`; `util01` peers with every server and admits
MMWatchdog's fleet hub on `util01` (8445) and MMHotline's alerts (8484) from every other pool. They
are code because they have no exception. As lines, each new pool would
repeat four of them, and a forgotten 8484 line would silently cut the
alert path a server uses when the fleet hub did not take an alert.

The role `work_out_who_this_server_talks_to` reads the table for the
server it runs on, with one Python program on the server, and outputs
`wireguard_peer_names`, `incoming_firewall_rules`, and
`peers_with_the_database_moving_in`. The playbooks that write `wg0` run it
first and pass its outputs on: `every_server`, `systems_desk`, and
`lock_everyone_out`, so one program decides the peers on every path.
Reasons for the shape:

- **One table, not each group's own list.** A pool that connects out, such
  as workers reading Postgres, keeps its lines beside its other lines, and
  "who reaches the database servers?" is one scan of `to_pool`. A group's
  own list would be invisible to the other servers while the group is
  empty.
- **A program, not template logic.** MMX task values take data references
  but no function calls, and one ufw task holds a server's whole rule set,
  so something must turn lines into rules. One reader for both the peers
  and the firewall means they can't disagree.
- **On the server itself, in run and dryrun alike.** The dryrun runs the
  same program, so a mistake in the table fails the dryrun too. The dryrun
  still shows only *that* a server's firewall or `wg0` would change, as
  below. During a lock-out `util01` loses authority, so the program
  can't live there. `python3` is on every Debian server from the first
  boot, because cloud-init needs it.
- **Its rule order.** The rules every server gets come first, in a fixed
  order, and the table's rules follow sorted by port and then address, so
  reordering lines in the table changes no server.

The stage `validate_the_connections_between_server_pools` runs the same
role on `util01` before any server changes, with `on_node_failure:
stop_run`. It refuses, naming the line or server, the fix, and "Nothing
changed.": a server in no pool or in two; a `private_ip` outside its pool's
block; a line whose `from_pool` or `to_pool` is not a pool; a line into
`systems_desks`, whose own firewall admits only its laptops; a line without
`why`; a port that is not a number or a `first:last` range; an unknown key;
and an `only_while_this_setting_is_false` setting the playbooks don't pass
in `settings_named_in_the_connections`. A server in no pool would otherwise
get no firewall and no peers, with every port open, MMX's own included.

`mmx explain` does not list each server's firewall rules, because they
are a runtime output; `tests/server_connections_test.py` runs the program
on any inventory in seconds. The `every_server` role takes a secret input, so MMX shows only
*that* a server's firewall or `wg0` would change, not the rules, in a
dryrun; read the rules on the server with
`ufw show added` and `wg show wg0 allowed-ips`.

## The WireGuard network

The private network is WireGuard, set up by MMX's `wireguard_interface`
module in the `every_server` role: interface `wg0`, each server at `<private_ip>/16`.
WireGuard listens on UDP 51820 (`vars.wireguard_listen_port`, written once in `inventories/servers.yml`),
and the outside world reaches it on UDP 443. The two ports have two reasons.
Reason for 51820: it is WireGuard's usual port and lies above 1024, so WireGuard needs no capability and no AppArmor
rule to bind it. On Ubuntu 26.04, and on the Debian releases that ship AppArmor 5, AppArmor confines `wg-quick`, and
its profile refuses a port below 1024, a rule a local override cannot loosen (`wg0` fails with
`Could not create IPv4 socket`).
Reason for 443 outside: hotel and office networks let UDP 443 out, so every laptop's `Endpoint`, every provider
firewall and the old database server's peers keep 443. Servers and desks use `Endpoint = <public_ipv4_address>:51820` for each other.
Reason: a NAT table, the redirect's included, gives every new flow a null NAT binding; when two peers send first packets at the
same moment (a `wg0` reload), or a peer that learned 51820 meets a flow redirected from 443, the tracking tuples clash and NAT
rewrites a source port. WireGuard roams to it, and when that entry expires the peer sits on a dead port: between servers, which
send no keepalive, for 12+ minutes on test servers. Port 51820 alone did not cure it (0 of 10 pairs); with
`files_used_by_several_roles/wireguard_notrack_between_servers_and_desks.nft`, which skips tracking for UDP 51820 to and from the
public address of every inventory node, 12 of 12 directed pairs answered after 150 s of silence, through a reload on every node.
A laptop keeps `Endpoint` 443 and adds `PersistentKeepalive = 25`, which keeps its flow alive through the redirect's tracking.
`files_used_by_several_roles/wireguard_udp_443_redirect.nft`, loaded by `wireguard-udp-443-redirect.service` before
`wg-quick@wg0.service`, redirects 443 to 51820. It is an nftables table of its own and not a line in ufw's
`before.rules`, so it touches none of ufw's files and MMX's ufw module keeps owning ufw. The firewalls admit 51820, because the redirect
happens before the filter sees the packet. On an existing system, `every_server` and the desk review apply the
redirect and the 51820 rule before they change `ListenPort`, so a peer that keeps sending to 443 never meets a closed port.
The first boot writes the same redirect before `wg-quick` starts, so a new server answers on UDP 443 from its first minute.
The inventory's `vars.wireguard_network` selects a private /16 inside
`10.0.0.0/8`, `172.16.0.0/12`, or `192.168.0.0/16`, with `10.20.0.0/16` as the default.
The third number identifies the server group, so the address plan needs a /16.

`vars.private_ip_ranges` holds each server pool's block, and the blocks of the
systems desks' laptops and the database moving in.
`vars.restore01_private_ip` holds the temporary restore server's address.
MMX task values reference data and cannot call functions to derive ranges.

The WireGuard network must not overlap an existing server network, such as a provider's private network on another network card.
Otherwise `wg0` would take the existing network's traffic, including traffic to the existing network's gateway. Another Stack system on a team systems desk must use a different network.
The laptop's home and office networks do not matter because doubleshell adds no laptop route.

**No file names the provider's network card.** A card's name can change
after an update or a reboot (`enp1s0` one boot, `eth0` the next), so the
stack names only its own `wg0`: nothing matches `eth0`, `enp*`, or `ens*`,
and MMWatchdog's network check watches the card of the server's default
route, which MMX reads from the server at each run. The
server's own network settings, which the provider's image writes at the
first boot, such as netplan's `/etc/netplan/50-cloud-init.yaml`, find the
card by its MAC address. After the first boot, `every_server` turns
cloud-init off (`/etc/cloud/cloud-init.disabled`) so later boots cannot
look for the network card under an old name. A test run on Ubuntu 26.04
with kernel 7.0.0-42 left three units failed after the card's name changed.
The provider's network settings stay after cloud-init is disabled.

**Peers by pool, not everyone with everyone.** Each server peers only with
the servers its pool talks to, so every peer list stays short and a
machine reaches only what it needs. The peers follow from
`connections_between_server_pools`
([Which pool talks to which](#which-pool-talks-to-which)); the Stack's
table gives:

| Server | Peers with |
| --- | --- |
| An app server | the app servers while they run the tunnel connector and Caddy (each Caddy reaches every web container), the database servers, `util01`, the load-balancer servers |
| A database server | the database servers (replication), the app servers, the jobs servers, `util01` |
| A jobs server | the database servers, `util01` |
| `util01` | every server on the WireGuard network, `staging01` included |
| `staging01` | `util01` only: staging serves no customers and gets less care, so it has no line and reaches no production server |
| A load-balancer server | the app servers (the load-balancer server's Caddy reaches every web container), `util01` |

The template `roles/every_server/files/wireguard_wg0.conf` writes a
`[Peer]` section for each name in `wireguard_peer_names`: `PublicKey` from
the peer's `wireguard_public_key`, `Endpoint` its
`vars.public_ipv4_address:51820`, `AllowedIPs` its `private_ip/32`.

**Every systems desk is a production peer.** `groups.systems_desks.nodes`
names numbered desk nodes. Each node holds `vars.person_unix_username`, `vars.private_ip`,
`vars.public_ipv4_address`, and `vars.wireguard_public_key`.
The desk's private address comes from `vars.private_ip_ranges.systems_desks`.
Production peers include the desk's public endpoint on UDP 51820.
Only the desk's `vars.allowed_laptops` lists laptop keys and addresses.
`restore01` remains the exception: the temporary server peers only with `util01`.

**A desk's peers for the servers follow pushed `main` without the person.** A desk peers with every
inventory node outside `systems_desks` that has a `wireguard_public_key`, except a node of
`database_restore_servers` whose `private_ip` lies outside `private_ip_ranges.database_servers`, and with its
own laptops. A new database server that `restore_database` restores after every database server is lost keeps a
database server's address and admits SSH from the desks, which run its restore; `restore01` has
`restore01_private_ip`, outside every pool, and peers only with `util01`. Reason: a command that left out
every node of `database_restore_servers` would leave a desk unable to reach a recovery's new server ("No route to host"). The servers' peers change with every added, replaced or removed server, and a
desk review asks the person, so the desk review does not write them. The coding agent runs
`sudo -n update-this-desks-wireguard-peers`, with no arguments, after such a push, at the start of each
session, and when SSH to a server times out. The command is root-owned and installed by the desk review.
It fetches pushed `main` as `servers-mmx`, with the desk's agent relay and with Git hooks off, reads only
`inventories/servers.yml` as data, writes `/etc/systems-desk/wireguard-server-peers.conf`, and sets the same
peers on the running `wg0` with `wg set`, so open sessions to other peers keep working. It refuses, naming the
server and the value, a key that is not WireGuard's 44-character form, a private address outside
`wireguard_network` or inside the desks' or the laptops' block, a public address that is not IPv4, a node
name that is not a plain server name, two servers with one key or one address, and a key that is this desk's
or one of its laptops'. Reason: the command runs as root and takes the inventory from pushed `main`, so an
intruder who can push there must not be able to cut the person off from their desk, take a laptop's
or a desk's address, or write anything into `wg0` but a server peer. A server on the desk's peer list reaches
only the desk's WireGuard port: the desk's firewall admits SSH on `wg0` only from its laptops.

One writer for each part of the desk's `wg0`: the desk review writes the interface and the laptop peers, from
`roles/systems_desk/files/wireguard_wg0.conf`; the command writes the server peers. MMX's `wireguard_interface`
makes the running interface match its file, and its reload removes peers that are not in the file, so the
desk's template reads the command's file with `read_file` and copies the server peers below a fixed line;
a desk review therefore keeps them. Its `PostUp` line loads the command's newest file when `wg0` starts,
such as after a reboot.

The desk playbook also writes the command's file itself, just before it reads it, with the command's root-only
form `--only-write-the-server-peers-file`: the same fetch and checks, the laptops of the reviewed run in place
of `wg0`'s file, and no change to the running `wg0`. Reason: on a desk from an earlier Stack version, or a
rebuilt desk, the file is empty, and the desk is MMX's controller in a desk review. A `wg0` without the server
peers would cut the controller off; MMX would restore the old `wg0` after two minutes and fail the run, and the
command refuses to run before the desk has the new template, a loop seen on a real desk. With the
file written first, a move to the new template is one desk review, and SSH to the servers loses one packet. A refused server
value stops the run at that task, before `wg0` changes. Before the coding agent's checkout holds a commit, as
at the start of the bootstrap, the fetch fails and the file stays as it is: a new desk has no server peers to keep. The coding
agent's sudo rule allows only the empty argument list, so the form is root's only.

The desk review shows that template's text, not its rendered result, because the
rendered result depends on the command's file. So adding, replacing or removing a server changes nothing in
the desk review: the desk playbook does not read the inventory's other nodes, the desk's MMWatchdog
settings take a fixed group list, and the review leaves `ssh/known_hosts` out, which only says which host
key to trust for a server. `tests/review_and_apply_the_systems_desk_settings_test.py` checks this.
`tests/desk_wireguard_peers_test.py` checks that a desk gets the same server peers it had when the desk
review wrote them, in every state, and each refusal.

**Keys before first boot.** The setup machine creates the server key pair.
On `util01`, setup runs `wg genkey` and `wg pubkey`. A systems desk uses the installed `wg genkey` and `wg pubkey` too. Initial setup creates every server from the systems desk because
`util01` does not yet have the provider tool or its copy of the systems repository. The public
key goes in the inventory; the private key goes once in first-boot data.
The setup machine retains no private key. MMX reuses
`/etc/wireguard/wg0.private_key`, root-owned with mode 0600.

The first-boot renderer reads JSON on stdin: `private_key`, `private_ip`,
and `peers`, a nonempty list of objects. `private_ip` must be IPv4 inside
`10.0.0.0/8`, `172.16.0.0/12`, or `192.168.0.0/16`, with every number at most 255. Each peer has `public_key`, a
canonical base64 WireGuard key, and `allowed_ips`, a nonempty list of IPv4
or IPv6 prefixes. An optional `endpoint` is `IPv4:port` or `[IPv6]:port`,
with a port from 1 to 65535. An optional `persistent_keepalive` is a whole
number of seconds from 0 to 65535, WireGuard's protocol range; the
`util01` peer uses 25 seconds. The renderer refuses unknown fields and
invalid values, naming the field without printing secret values. The
renderer creates every wg-quick directive from validated fields, so no
caller can supply a hook such as `PreUp`. Base64 encoding protects the
cloud-config shell boundary; structured peers also protect the wg-quick
boundary. The renderer uses jq instead of Python to keep the existing
Bash/jq-only setup requirements. The provider script reads the rendered data
once. Rendered data uses a pipe or a temporary mode-0600 file outside Git;
setup removes the temporary file after submission, including on failure.

The first boot blocks public TCP 22 on IPv4 and IPv6 before package
installation. The early IPv4 and IPv6 INPUT guards stay while ufw enables
its own chains (`MANAGE_BUILTINS=no`); first boot never resets the firewall.
Once ufw is enabled with SSH only on `wg0`, first boot removes the guards.
The guards also drop SSH over loopback, and `util01` runs MMX against its
own private address over loopback. ufw admits loopback.
Cloud-init writes the key and interface file directly with mode 0600, so
no private key enters a shell command argument. The configuration stage
installs WireGuard and ufw, then starts `wg0` with `util01`
and the systems desk peers. A new `util01` has only systems desk peers.
The first-boot firewall admits TCP 22 only on `wg0`, whose peers admit only the enrolled keys and addresses.
A restore server peers only with util01. The first MMX run replaces the first-boot rules with the inventory's rules. The provider
image must order cloud-init's network stage before `ssh.service` and
`ssh.socket`; a disposable-server check proves the ordering before use.
No provider firewall is used. After first boot, ufw blocks outbound HTTP
to `169.254.169.254:80` and `[fd00:ec2::254]:80`, and cloud-init is
disabled. The metadata block prevents apps from reading the provider's saved first-boot private key.
Only HTTP is blocked because some providers also serve DNS at the IPv4
metadata address.

**First SSH trust.** Setup records the SSH host key seen through the new
WireGuard peer in `ssh/known_hosts`, under the WireGuard address. Only the
new server holds the private WireGuard key passed at creation. An initial
SSH connection with `StrictHostKeyChecking=accept-new` records the key;
all later SSH connections use strict checking. Pre-generated SSH host
keys add no protection and are omitted.

**Production SSH from the desk.** The desk and `util01` use kernel `wg0`.
MMX and agents use `ssh/config` from the repository root, with the committed
host keys and each production server's private inventory address.
The laptop keeps a private desk-only wg-quick file read by doubleshell's
`--wireguard-config` option. No laptop inventory, runtime, VPN interface,
or generated fleet SSH file is needed after bootstrap.
The laptop's SSH entry names the desk user, laptop-only key, and verified desk host key.
Reason: the laptop must not keep the production repository or peer with production servers.
The desks and `util01` reach the servers over their own `wg0`, so `ssh/config` has no doubleshell line.

**Reachability protection.** `wireguard_interface` uses
`restore_unless_controller_confirms_within: 2m`; the task has no `retry`,
`time_limit`, or `time_limit_per_try`. MMX restores the previous interface
settings when a fresh controller connection cannot confirm the change.
SSH fallback helps when MMX HTTPS is down; SSH fallback still needs
WireGuard. A broken WireGuard interface needs the provider console.

## The inventory

```yaml
# inventories/servers.yml
vars:
  deployed_image_tags:            # requested image tags: the app's full 40-character Git commit
    production:
      shop: "3f2a1c97d4e85b60a1c2d3e4f5061728394a5b6c"
    staging: {}                   # Add staging01 fills in staging01's tags and host names
  public_host_names:
    production:
      shop: shop.example.com
    staging: {}
  is_app_server: false            # the group flags: true in each group's vars
  is_database_server: false
  is_util_server: false
  is_staging_server: false
  is_jobs_server: false
  is_load_balancer_server: false
nodes:
  app001:
    address: 10.20.1.1                          # SSH over WireGuard
    https_address: https://10.20.1.1:7443       # MMX's HTTPS, over WireGuard only
    ssh_user: root
    ssh_known_hosts: ssh/known_hosts
    ssh_config: ssh/config
    vars:
      private_ip: 10.20.1.1
      public_ipv4_address: 203.0.113.11
      server_type: cx33                         # the provider's type and location, from the create receipt
      location: fsn1
      wireguard_public_key: "PFHMlKh61wvN0/mEnwE2mCdTk3PCQmr/u0lh3F8JkT0=" # generated before creation
groups:
  app_servers:
    nodes: [app001]
    vars:
      is_app_server: true
      mmwatchdog_check_file: app_servers.yml
  database_servers:
    nodes: [db01]
    vars:
      is_database_server: true
      mmwatchdog_check_file: database_servers.yml
  jobs_servers:                   # a later step: jobs001 and up
    nodes: []
    vars:
      is_jobs_server: true
      mmwatchdog_check_file: jobs_servers.yml
  util_server:
    nodes: [util01]
    vars:
      is_util_server: true
  staging_server:                     # staging01, once Add staging01 adds it
    nodes: []
    vars:
      is_staging_server: true
      mmwatchdog_check_file: database_servers.yml
  database_restore_servers:           # restore01 during a drill or a recovery of lost rows; a recovery's new database server
    nodes: []
  load_balancer_servers:          # lb01 and lb02, a later step
    nodes: []
    vars:
      is_load_balancer_server: true
      mmwatchdog_check_file: load_balancer_servers.yml
```

- **`ssh_user: root`,** because server providers create a server with the
  team's SSH key on `root`, and MMX needs unrestricted root on every node
  anyway. A separate administrator account would add a bootstrap step and
  no protection. `every_server` sets `PermitRootLogin prohibit-password`
  and manages `root`'s `authorized_keys` from the project settings.
- **`address` is the WireGuard address,** equal to `vars.private_ip`.
  SSH uses `address`; WireGuard endpoints and provider scripts use
  `vars.public_ipv4_address`.
- **`https_address` points at the private address,** and the firewall opens
  7443 only on `wg0`.
- **`server_type` and `location` on every server,** except the systems desks
  and the servers of `database_restore_servers`, from the create script's
  receipt. `replace_failed_servers` creates the replacement with the failed
  server's type in its location. The other way, reading both from the
  provider's list, was rejected: the list contract returns only `id`,
  `name`, `public_ipv4_address` and `power_state`, and a failed server may
  be gone from the provider, so the list would need a fallback that the
  inventory makes unnecessary. `every_server` refuses a server without
  them, before anything changes, and names what to add. The two values
  are facts about the server, not settings, so they live on the server's
  own entry.
- **`power_off_a_server_at_the_provider --server-id ID`,** a fourth
  provider script. `replace_failed_servers` powers a failed server off
  before it creates the replacement, so a server that only looks dead
  cannot keep serving errors through its tunnel connector, and the failed
  disk stays for evidence until the replacement serves. The second app
  server's power test calls the same script. It takes the ID only, never a
  name: a name can repeat at a provider, and a power cut by the wrong
  match takes down a healthy server. It waits until the list's
  `power_state` is `stopped`, at most 5 minutes (a stop took up to 40
  seconds at OVHcloud; the room covers slower providers), and a server
  already stopped needs no action, so a rerun after a lost answer is
  harmless. A server the provider does not list is an error the caller
  reads: the caller knows whether "gone" is fine. Where the provider has
  only a stop that shuts the operating system down (OVHcloud, and Vultr's
  halt until an abrupt cut is confirmed), the script uses that stop; the
  guide says so. The DigitalOcean, Vultr, Scaleway and OVHcloud guides
  give the five scripts whole, and `tests/*_provider_scripts_test.py` run
  them against a stand-in of each provider's API; the other guides name the
  command and the permission `util01` needs.

## The project settings

```yaml
# mmx_project_settings.yml
project_name: example_systems
default_inventory: servers
vault_file: secrets_vault.age
run_history_retention: 30d
vars:
  apps:
    shop:
      image: ghcr.io/example/shop
      web_ports: [8001, 8002]               # used in turn: a deploy starts the new version on the free port
      health_url_path: /up
      migration_command: bin/rails db:migrate
      jobs_command: bin/jobs                    # "" for an app with no background jobs: no job container anywhere
      jobs_connect_directly_to_postgres: false  # true when the jobs need a whole Postgres session, such as for LISTEN/NOTIFY
      asset_directory: /rails/public/assets
      database_name: shop
      env:                          # plain settings; secrets come from the vault
        RAILS_ENV: production
      secrets_from_vault:                   # each name, and where its value comes from
        SECRET_KEY_BASE: {where_the_value_comes_from: generated_by_the_setup}
        STRIPE_API_KEY:
          where_the_value_comes_from: an_outside_service
          what_it_is_for: Stripe takes your customers' card payments with it.
          steps_to_get_it: ["Open  https://dashboard.stripe.com/apikeys", "Press  Reveal live key,  then copy it."]
          checked_with: stripe
      production_uploads_r2_bucket: example-shop-uploads   # util01 copies the bucket to backups.uploads_bucket every night; "" for no uploads
      staging_uploads_r2_bucket: ""   # staging01's own bucket, such as example-shop-staging-uploads, set by Add staging01 for an app with uploads; staging01's R2_BUCKET; never copied
      staging_env: {}                 # staging01's own plain settings in place of env's, such as its own APP_ORIGIN; every_server refuses staging01 without them
  app_server_group_of_environment:          # the group whose servers run each environment's apps
    production: app_servers
    staging: staging_server
  groups_that_run_caddy_of_environment:     # the groups whose servers may run each environment's Caddy: a deploy switches every Caddy there
    production: [app_servers, load_balancer_servers]
    staging: [staging_server]
  job_containers_run_only_on_the_jobs_servers: false   # the later steps' settings: true once the step is in effect (Later steps)
  tunnel_connector_and_caddy_run_only_on_the_load_balancer_servers: false
  container_registry_read_only_username: example-registry-reader
  postgresql_major_version: 17              # Debian 13's, on the database servers, staging01, and util01's failover monitor
  pgbouncer_runs_in_front_of_postgres: false   # PgBouncer, a later step: on, then each environment's apps through PgBouncer
  apps_connect_through_pgbouncer:
    staging: false
    production: false
  backups:                                  # pgBackRest's B2 bucket for production, through B2's S3-compatible API
    b2_s3_endpoint: s3.eu-central-003.backblazeb2.com
    b2_region: eu-central-003
    production_bucket: example-systems-backups
    uploads_bucket: example-systems-uploads-backups   # the apps' uploads, copied from R2 every night (Uploaded files)
    uploads_r2_s3_endpoint: https://example-cloudflare-account-id.r2.cloudflarestorage.com
    uploads_backup_runs_on: [util_server]       # [] while no app keeps uploads: then no copy, and no uploads keys needed
    mmhotline_backup_replica_url: "s3://example-mmhotline-backup/mmhotline?endpoint=...&region=..."   # Litestream's copy of MMHotline's database, in the same B2 account as the buckets above
  root_ssh_public_keys:                     # who may log in to every server; the comment says whose key
    - ssh-ed25519 AAAA... Ana Silva's systems desk
    - ssh-ed25519 AAAA... util01, the mmhotline user
  triage_ssh_public_key: ssh-ed25519 AAAA... util01, the triage agent
  util01_private_page_host_names:           # each behind Cloudflare Access, through util01's own tunnel
    mmhotline: ops.example.com
  systems_repository:                       # the main copy on util01, and the backup at the Git host
    main_copy_path_on_util01: /var/lib/systems_repository.git   # the team's main copy, root-owned, on util01
    backup_url_at_the_git_host: https://github.com/example/example_systems.git   # pushed from the laptop, never read
  stack_software:                           # releases from outside the distribution, each pinned
    mmx: {version: "0.1.0", download_url: "...", sha256: "..."}
    mmwatchdog: {version: "0.1.0", download_url: "...", sha256: "..."}
    mmhotline: {version: "0.1.0", download_url: "...", sha256: "..."}
    litestream: {version: "0.5.17", download_url: "...", sha256: "..."}
```

The apps live in `mmx_project_settings.yml`, under `vars.apps`, for two
reasons. MMX does not load variables from a file of each app's own, and
most teams have one to three apps. Each app also has
`restore_drill_check_queries`, which the restore drill runs on the restored
copy ([Restore drill and recovery](#restore-drill-and-recovery)):

```yaml
      restore_drill_check_queries:          # each answers true or false, on the restored copy
        - name: the_migrations_came_back
          sql: select count(*) > 0 from schema_migrations
        - name: an_order_from_the_last_two_days_came_back
          sql: select max(created_at) > now() - interval '2 days' from orders
```

## The app contract

**AppArmor confines app containers.** The `every_server` role installs and
loads `monkeymaxxing-app-containers` on app, jobs, and staging servers.
Web and job Quadlets and the migration helper select this profile explicitly.
The profile keeps Podman's container restrictions and allows signals between
processes carrying the plain profile or the profile stacked with `crun`.
Debian 13's named crun profile and `NoNewPrivileges=true` cause crun to stack
profiles. Podman's default exact peer rule does not match the stacked label,
so even a Node process stopping its own child receives `kill EACCES`.
The Stack owns this policy because the Stack owns container confinement and
must support apps that stop child processes. AppArmor stays enabled, the
distribution's crun profile stays unchanged, and web and jobs containers
keep `NoNewPrivileges=true` and `DropCapability=all`.

**A user namespace makes a break-out less harmful.** Two layers protect the
server from an app container. AppArmor makes a break-out harder: the profile
denies mounts, the server's `/proc` and `/sys` controls, and signals to
processes outside the container. A user namespace makes a break-out less
harmful: every web, job, and migration container runs with `UserNS=auto`, so
Podman maps root inside the container to an unused, unprivileged user ID on the
server, a different range for each container. An app that escapes is then a
user that owns no file and no process on the server, and it cannot read files
that only root may read.

Rootless Podman, which runs the containers as a normal user, would give the
same benefit, but the Stack does not use it: on Debian, rootless Podman
refuses every AppArmor profile ("Apparmor is not enabled on this system"), so
it would give up the first layer to gain the second. The containers stay under
root's Podman as Quadlet system units, with both layers. `UserNS=auto` needs a
range of user IDs that no server user has. Debian ships none, so the
`every_server` role writes `containers:2147483647:2147483648` to `/etc/subuid`
and `/etc/subgid`; without it a container fails to start with "Cannot find
mappings for user containers". The role leaves every other line of the files.

The server's files count as "other" to a container's user. A file that the app
reads from the server must therefore be readable by anyone. The environment
files are read by systemd and Podman as root, before the container starts, so
they stay private to root. The asset directory is the only directory mounted
into a container. The `fill_web_asset_directory` program makes its files
readable, and its directories enterable, by anyone, whatever the image's modes.

What an app provides to run on the stack, checked by the coding agent
before the first server exists (the checklist's `apps` items):

- **The web container listens on the port in `PORT`,** and binds no other
  fixed port. The containers run with `Network=host`, so each container
  uses the server's own network. Container traffic uses the server's
  firewall rules on `wg0`, so no routed firewall rules are needed.
  Each web container listens at `<private_ip>:<web port>` on the app
  server, so each Caddy can reach every app server's web containers.
  And on `staging01`, the apps reach `staging01`'s own Postgres on the
  server's network.

  A container port is a server port, so a fixed port would collide between
  the old and new web containers during a deploy. A fixed port could also
  collide with Caddy's port 80.
- **The web server sets the number of worker processes from
  `WEB_CONCURRENCY`.** Each server sets `WEB_CONCURRENCY` in the app's web
  containers to the server's CPU count, MMX's fact `.node.cpu.count`.
  An app can override the CPU count with `WEB_CONCURRENCY` in
  `apps.<app>.env`.

  A Quadlet file describes a container that Podman runs as a systemd
  service. The web container's Quadlet file uses `Environment=` to set
  `WEB_CONCURRENCY`. `Environment=` would override
  `/etc/<app>/<app>_settings.env`, which holds `apps.<app>.env`.
  If `apps.<app>.env` sets `WEB_CONCURRENCY`, MMX leaves the
  `WEB_CONCURRENCY` line out of the Quadlet file.

  Puma, Gunicorn, and Uvicorn read `WEB_CONCURRENCY` automatically. A Node
  app uses the cluster module to fork the number of workers in
  `WEB_CONCURRENCY`. No common job runner reads `WEB_CONCURRENCY`, so the
  job containers get no `WEB_CONCURRENCY` setting.

  Each Caddy sends a request to the web container with the fewest
  requests in flight (`lb_policy least_conn`), so a server that is slower,
  or busy with other work, gets fewer requests. In routing tests on real
  servers, with two equal app servers, `least_conn` and `round_robin`
  carried the same load; with one server doing double the work for each
  request, `least_conn` carried about 1.5 times as much load before failing,
  because `round_robin` kept sending the slow server half the requests.
  In the same tests, passing a request to another app server added a delay
  too small to measure.
  Each worker process keeps its own Postgres connections, so a much
  bigger app server also opens many more of them (the template's
  [add_an_app_server.md](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/add_an_app_server.md)).
- **Two `web_ports` per app,** used in turn: a deploy starts the new
  release on the free one. Every app's `web_ports` lie in 8001 to 8099,
  because the firewall's rule for them is one port range (a rule can't
  loop over the apps), and no two apps share a port.
- Each app supplies the following values under `apps.<app>` in
  `mmx_project_settings.yml`:
  - a health URL (`health_url_path`), one migration command, and one command
    for background jobs,
  - whether the app's background jobs need a whole Postgres session
    (`jobs_connect_directly_to_postgres`),
  - the directory of the app's asset files and the app's database,
  - the app's plain settings (`environment`) and the names of the app's
    secrets (`secrets_from_vault`),
  - the R2 bucket for the app's uploaded files in production
    (`production_uploads_r2_bucket`, `""` for none).
- **A seed command fills a developer's laptop database and staging's
  database with invented test data after migrations.** The seed command
  runs only when `APP_ENV` is `development` or `staging`. The seed command
  never reads production data. A size option named after the app's main
  record, such as `--orders 200000`, creates enough invented records to
  show slow queries. The app's tests run the seed command on an empty
  database before every image build, in CI when the team uses CI.
  Reason: a seed command nobody runs breaks at the next migration, and
  developers go back to copying production. The skill's
  `files_for_your_app/write_the_seed_command.md` gives the principles, a
  worked example, and each framework's usual seed tool. The guide names
  long-lived framework tools without versions. Tools that copy and mask
  production appear only as a category. These choices keep the guide's
  upkeep small. The reference
  app's `reference_app seed-test-data` creates one test page view and one
  test job, and running it again does not duplicate them.
- **Production data stays on the production servers.** No copy of
  production goes to a laptop, staging, or CI, even with the personal data
  removed. The Stack's own copies stay: uploaded files in R2, backups in
  B2, and the temporary `restore01`. A bug that needs particular records
  gets invented records like them in the seed command or a test, and a
  test that checks the bug stays fixed.
  Reason: any program that runs as the developer, such as a poisoned package, can copy what a laptop holds, and
  a laptop's backups go to a backup company. A
  coding agent on a laptop can send what it reads to the company that runs
  the agent's AI model. Staging gets less care than production. The usual
  alternative is a sanitized copy: production's data with the personal
  data removed by a script. The Stack does not offer one. The script must
  be updated for every new column that holds personal data, and a missed
  column leaks without anyone noticing. Invented data has no such gap.
- **The app's Postgres driver finds the primary automatically after a
  failover.** The driver uses `DATABASE_URL` and `DATABASE_READ_URL`, which
  list every database server ([Secrets](#secrets)), with TCP keepalive on.
  Each language's method is in the skill's
  `files_for_your_app/database_driver_finds_the_primary.md`.

  One URL form serves every app, so adding a framework needs no change to
  the stack. If a driver or framework takes another form, a few lines of
  the app build that form. Rails is an example: Active Record stops at
  boot on the stack's URL with the list of database servers
  ([Ruby and Rails](../skills/monkeymaxxing-stack/files_for_your_app/database_driver_finds_the_primary.md#ruby-and-rails)).

  Node.js gets the file
  `files_for_your_app/node/pg_with_multiple_database_servers.mjs`, because
  one Node.js driver, pg, cannot read the server list, and the other
  driver, postgres.js, can choose the wrong server. An ORM (object-relational mapper) is a
  library that maps app objects to database records. The Node.js file
  uses only pg's public API, so every common ORM can use the file for
  database connections.
  `check_database_failover.mjs` checks that database connections find the
  new primary during a switchover.

  A database server that loses power sends nothing. So `every_server`
  sets TCP keepalive and retransmission limits on app servers, jobs
  servers, and `staging01`, which run the apps' containers.
  App containers share the host server's network, so the host's limits
  apply to connections from app containers. The app containers'
  connections to the dead database server end within about a minute.

## Secrets

All secrets are in the MMX vault, `secrets_vault.age`. Each server gets only
its role's secrets: a fleet stage passes exactly the vault keys its role
needs.

The keys from Backblaze and Cloudflare reach the vault through
`set-up-outside-services`, which makes each one with only the access its
table in [Account and secret setup from the systems desk](#account-and-secret-setup-from-the-systems-desk)
gives it.

| Vault key | Who gets the vault key |
| --- | --- |
| `container_registry_read_only_token` | the app servers, the jobs servers, and `staging01`: they pull the same images |
| `apps_cloudflare_tunnel_token` | the servers that run production's tunnel connector: the app servers until the load-balancer servers carry the requests, and the load-balancer servers |
| `<database_name>_database_password`, such as `shop_database_password` | the app servers and the jobs servers |
| `<app>_<VARIABLE>` for each name in `secrets_from_vault`, such as `shop_SECRET_KEY_BASE` | the app servers and the jobs servers |
| `staging_apps_cloudflare_tunnel_token`, `staging_<database_name>_database_password`, `staging_<app>_<VARIABLE>` | `staging01`: the production key with `staging_` in front, so `staging01` holds no production secret |
| `pg_auto_failover_autoctl_node_password` | `util01` and the database servers: the failover monitor's login, with which every node reaches it |
| `pg_auto_failover_replication_password` | the database servers: the login with which a replica copies from the primary |
| `pgbackrest_b2_write_key_id`, `pgbackrest_b2_write_application_key` | the database servers: a B2 key that can reach only the production backup bucket |
| `pgbackrest_repository_cipher_passphrase` | the database servers: pgBackRest encrypts every file of the production repository with the passphrase |
| `util01_cloudflare_tunnel_token` | `util01`: its own tunnel, for its private pages |
| `mmhotline_backup_access_key_id`, `mmhotline_backup_secret_access_key` | `util01`: Litestream's copy of MMHotline's database |
| `pushover_application_token`, `mmwatchdog_pushover_user_or_group_key` | `util01`: the push app. The fleet hub on `util01` names the push app as the destination for the alert that `util01` went silent, and passes the push app's settings, with `pushover_application_token` and `mmwatchdog_pushover_user_or_group_key`, to the hub-outage alerters in its fleet settings. The hub-outage alerters send that alert to the group of everyone who may be on call, because the fleet hub is silent with `util01`; MMHotline sends everyone's alerts with the same application token (`sending_services.pushover` in `mmhotline_settings.yml`), so the token's name belongs to neither program |
| `mmhotline_triage_agent_credential`, `mmhotline_down_alarm_cloudflare_api_token`, `mmhotline_status_page_r2_access_key_id`, `mmhotline_status_page_r2_secret_access_key`, `mmhotline_signing_secret_of_the_fleet_hub` | `util01`: MMX renders the systems repository's `mmhotline_settings.yml` into `/etc/mmhotline/mmhotline_settings.yml`, which MMHotline reads. `mmhotline_triage_agent_credential` supplies the triage agent's API key or subscription token. `mmhotline_down_alarm_cloudflare_api_token` supplies the MMHotline-down alarm's Cloudflare token. `mmhotline_status_page_r2_access_key_id` and `mmhotline_status_page_r2_secret_access_key` supply the status page's R2 credentials. The fleet hub signs alerts and check-ins with `mmhotline_signing_secret_of_the_fleet_hub`, which MMHotline also reads |
| `shared_root_console_password_hash` | every normal server: the shared console root password hash |
| `mmx_vault_passphrase` | `util01`: the vault's own passphrase, for MMX's runs there |
| `util01_provider_api_token` | `util01`: its own token at the server provider, for the restore drill's `restore01` |
| `pgbackrest_b2_read_only_key_id`, `pgbackrest_b2_read_only_application_key`, with `pgbackrest_repository_cipher_passphrase` | the server in `database_restore_servers`: a key that can only read the production bucket |
| `uploads_r2_read_only_access_key_id`, `uploads_r2_read_only_secret_access_key` | `util01`: an R2 token that can only read the apps' upload buckets, for their nightly copy ([Uploaded files](#uploaded-files)) |
| `uploads_backup_b2_write_key_id`, `uploads_backup_b2_write_application_key` | `util01`: a B2 key that can reach only the uploads' bucket, and can't delete a file version. The uploads' copy needs four keys, the two R2 keys above and the two B2 keys, only while `backups.uploads_backup_runs_on` names `util01` |

The roles that arrive later bring their own keys. MMHotline's settings
file reads its keys itself, as `.secrets.KEY`, because the fleet stage
`mmhotline` renders it from the playbook ([The main playbook](#the-main-playbook)),
so a key is needed only while the file has the section that reads it.

- **An app's settings reach its containers through env files,** read by
  the Quadlet units' `EnvironmentFile=` and by the app's migrations:
  - `/etc/<app>/<app>_settings.env`, mode 0644: the plain settings from
    `apps.<app>.env`;
  - `/etc/<app>/<app>.env`, mode 0600, owned by root: the secrets, with
    `DATABASE_URL` listing every database server
    (`target_session_attrs=read-write`, so the driver finds the primary
    after a failover, and `connect_timeout=3`, so a switched-off server
    costs seconds instead of the minutes a driver otherwise waits), at
    Postgres's port or, once the environment connects through it,
    PgBouncer's;
  - `/etc/<app>/<app>_database_direct_to_postgres.env`, mode 0600: the
    app's `DATABASE_URL` and `DATABASE_READ_URL` at Postgres's port.
    The migrations load the direct-to-Postgres file after
    `/etc/<app>/<app>.env` because migrations need a whole Postgres session.
    When `jobs_connect_directly_to_postgres` is `true`, the job container
    also loads the direct-to-Postgres file after `/etc/<app>/<app>.env`
    ([PgBouncer, a later step](#pgbouncer-a-later-step)).

  Env files were chosen for three reasons. Env files are MMX's documented
  way. systemd reads the files with no extra store. And MMX hides secret
  content in file differences and results.
- **No schedule, name or path reads a hidden output.** MMX hides the
  output of a node task that reads a secret, or a value made from one,
  such as a `set_vars` value or a hidden output. Inside a role, MMX also
  hides the output of every node task that starts after a node task that
  read a secret and ran something on the server, such as a `file` task
  whose template reads a secret: that task may have left the secret on
  the server. A secret read by `set_vars`, `show` or `assert` hides no
  later node task, because these run nothing on the server (the MMX
  release that `stack_software.mmx` pins). MMX refuses a hidden value in a schedule, a name or a path
  ("resource identifier must not contain a secret"), and the error names
  the node task that read the secret. A login that MMX hands only to its
  tool, such as a Postgres password, hides nothing. So a role works out
  such a value before its first such node task, as `uploads_backup` does
  with the uploads copy's time before it writes the rclone settings, or
  takes it from a var, as `database_server` takes the days of the
  differential backups, whose job comes after
  `write_the_pgbackrest_settings`, from `days_other_than`. Without this
  rule, the first real run of a new system fails on `db01`.
  `tests/task_outputs_after_a_secret_test.py` walks every playbook's node
  tasks with `mmx explain` and fails on the pattern.
- **The vault holds its own passphrase** as `mmx_vault_passphrase`, so a
  systems desk that rebuilds `util01` brings it back with the rest; reading it
  needs the passphrase already, so it exposes nothing. After
  `mmx secrets passwd`, the vault key `mmx_vault_passphrase` is set to the
  new passphrase too. Then a systems desk runs
  `every_server` from the systems desk after the push
  (`mmx run every_server --connection ssh_only --limit util_server`).

## Emergency console access

Every server shares one root password so a person can type the password
in a provider console without paste: `set-up-outside-services secrets`
makes it as six groups of five lowercase letters, chosen from letters
that sit in the same place on QWERTY, QWERTZ and AZERTY keyboards (about
129 bits). It shows the password once for the password manager item
`Shared root console password`, clears the screen, and has the person type
it back from the password manager, so a password that was never saved
cannot reach the servers. The password lives in the team's password
manager; its SHA-512 crypt hash, from the desk's `openssl passwd -6`,
lives in the vault as `shared_root_console_password_hash`. MMX's `user` module sets `password_hash` with
`apply_password_hash: on_every_run` and `password_locked: false`. SSH
keeps `PasswordAuthentication no`, `KbdInteractiveAuthentication no`, and
`PermitRootLogin prohibit-password`, so the password works only at the
console. Rotation changes the vault hash and applies `every_server` to
every normal server. Before rotation, finish and remove a running
`restore01` through the recovery procedure that created the restore
server, or apply the new hash through an MMX one-time playbook on the
restore server. `every_server` excludes `database_restore_servers`, so an
unhandled restore server would keep the old password. Verify a console
login before replacing the recorded password.

[Repair SSH or WireGuard from the provider console](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/repair_ssh_or_wireguard_from_the_provider_console.md)
holds the one list of commands, the same for every provider: the provider
guides say only where each console is. The list covers what the Stack can
break: `wg-quick@wg0` and its peers (one desk peer added with `wg set`),
the ufw rules that admit SSH on `wg0`, and sshd (`sshd -t`, the lock-out
file `00-incident-lockout.conf`, root's `authorized_keys`). Every hand
change is temporary: the next `every_server` run for the server replaces
it with the repository's settings, because MMX removes rules and peers
that the repository does not list.

The checklist's `provider_console_and_backup_mmhotline_logins` tests a console root login and keeps
the MMHotline port-forward and one-time sign-in test. Provider guides say
whether console access needs enabling first. A rescue system remains the
way to repair a server unable to boot; replacement is the normal recovery.
"Check my system's protections" tests public TCP 22 closure on every
public IPv4 and IPv6 address from outside. No extra MMWatchdog check is
needed: failed application traffic and MMX connections already expose a
broken WireGuard interface, and the daily server settings comparison warns
about a firewall rule that differs from the repository.

## Database servers

Postgres 17 comes from Debian 13's own packages, including
`postgresql-17-auto-failover`. Debian 13 has no
`postgresql-18-auto-failover` package. Keeping Postgres within the
distribution keeps MMWatchdog's `apt_security_updates` and vulnerability
checks covering Postgres. Packages from PGDG, PostgreSQL's separate apt
repository, would sit outside the distribution and silently escape those
checks. A major upgrade comes only with a new Debian release.
[Replace a server](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/replace_a_server.md)
alone cannot do one, because a replica must run the primary's Postgres
major version. The Stack version that adds the new Debian release brings
tested steps for moving the database servers ([Testing](testing.md)).
Postgres 17 receives upstream minor releases, including security fixes,
until November 2029. Debian security supplies the minor releases:
Debian 13 carries `17.11-0+deb13u1`.
See [Debian's package](https://packages.debian.org/trixie/postgresql-17)
and [PostgreSQL's support policy](https://www.postgresql.org/support/versioning/).

Postgres runs under pg_auto_failover on the database servers
(`roles/database_server`), and pg_auto_failover's failover monitor, which
decides which server is the primary, runs on `util01`
(`roles/util_server`). `staging01` runs the cluster `main`, created by
Debian's Postgres packaging tools. The
`database_server` role sets up `main` outside pg_auto_failover when
`is_staging_server` is true.

| What | Name |
| --- | --- |
| Postgres | major version 17, Debian 13's (`vars.postgresql_major_version`) |
| The formation | `production`: the group of database servers managed together by `util01`'s failover monitor. Each database server is a node, named after the server. |
| A node | data directory `/var/lib/postgresql/17/pg_auto_failover_node`, port 5432, service `pgautofailover.service` |
| `staging01`'s cluster | Debian's `main`: data directory `/var/lib/postgresql/17/main`, settings in `/etc/postgresql/17/main/`, port 5432, service `postgresql@17-main.service` |
| The monitor | data directory `/var/lib/postgresql/17/pg_auto_failover_monitor` on `util01`, port 5432 on `10.20.0.1` |
| The apps' databases | one database and one login role for each `apps.<app>.database_name`, named alike, collation `C.UTF-8`; the role's password is the vault key `<database_name>_database_password` |
| The triage user | the role `triage`, a member of `pg_monitor`, through the local socket |
| Postgres's settings | `shared_buffers` and the archive settings, in `pg_auto_failover_node`'s input `postgresql_settings`. The `pg_auto_failover_node` module writes `/etc/postgresql/pg_auto_failover_node_settings.conf`, included by the last line of `postgresql.conf`. For settings requiring a restart, `pg_auto_failover_node` restarts Postgres only on a node created by the current run, or in `update_database_servers` (below). |
| Postgres's buffers | `shared_buffers` is a quarter of the server's memory (`{percent_of_memory: 25, rounded_down_to_mib: 128, at_least_mib: 128}`). The value is rounded down to a step of 128 MB and is at least 128 MB. The rounding exists because a new kernel can move `MemTotal` by a few MB, and each changed `shared_buffers` value requires a Postgres restart. `staging01` keeps Postgres's default, 128 MB, because a quarter of its memory would take memory from the apps' two releases during a deploy. MMWatchdog records the share of reads that the buffers served (`cache_hit_percent`) with every `postgresql` check of the `postgres` group, each minute, and no check alerts on the share. Reason: a block missing from the buffers is often in the operating system's page cache, so a low share alone proved nothing, and the earlier hourly warning, `postgres_cache/cache_hit_ratio_is_above_99_percent`, cost a long review each time. The group `postgres_cache` is gone: MMWatchdog allows `only_record_readings` only for modules that measure without failing, and a `postgresql` check fails when Postgres does not answer, while every `postgresql` run already records every one of its measurements. The disk reads and memory pressure in `database_server_capacity` stay recorded. |
| pgBackRest | on the database servers only: stanza `main`, pgBackRest's name for production's cluster, backups, and archived database changes; `/etc/pgbackrest/pgbackrest.conf` from the project's `files_used_by_several_roles/pgbackrest.conf`, `root:postgres` 0640; repository 1 is production's B2 bucket (`vars.backups`), path `/pgbackrest`, host-style S3 addresses, encrypted with `aes-256-cbc` |
| Backups | `pgbackrest_full_backup.timer` on `weekly_work_day` and `pgbackrest_differential_backup.timer` on the other days, at `nightly_work_starts_at` (Sunday and 01:00 UTC in the template), on every database server. `back_up_the_database_on_the_primary` skips replicas, so backups run on production's primary. pgBackRest keeps full backups for `backups.keep_database_backups_for_days` (21 in the template, `repo1-retention-full-type=time`), so a restore reaches any moment of that period; `archive_timeout = 60` |

- **`staging01` runs plain Postgres, outside pg_auto_failover.** MMX runs
  one pg_autoctl instance on a server, so `util01` cannot run a separate
  staging monitor beside production's monitor. A staging formation would
  then live on production's monitor, which has one login, `autoctl_node`,
  for every formation. So a staging node would hold a password with which
  root on `staging01` could fail over and remove nodes in production's
  formation. Staging tests the apps and their migrations, not failover.

  So `staging01` gets the cluster `main` from Debian's packaging tools,
  with the apps' databases and roles. The `database_server` role writes
  the apps' `pg_hba.conf` lines on `staging01` as on production, with
  `staging01`'s own address as the source. Its listen address lives in
  the cluster's `conf.d`. The apps on `staging01` use a `DATABASE_URL` with production's shape
  (`postgresql://staging01:5432/shop?target_session_attrs=read-write`),
  and `staging01` holds no production secret.
- **`staging01` keeps no backups.** No pgBackRest, no archiving, no
  backup bucket, key, or passphrase, and no backup checks. A new
  `staging01` gets its data from each app's seed command
  ([Replace staging01](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/replace_staging01.md)).
  Reason: staging holds only the
  seed command's invented data, which the seed command makes again at any
  time, so a backup would protect nothing. A backup would cost a bucket, a
  key, a passphrase in the password manager, two check groups, and a
  restore mode of `restore_database` that deletes a database on purpose.
  The weekly drill proves production's backups.
- **Synchronous replication, equal priorities.** Every node has
  `replication_quorum: true` and `candidate_priority: 50`: the primary
  confirms a write only once a replica holds it, and the monitor promotes
  whichever replica is healthy. While the only replica is down or in
  maintenance, the primary stops waiting for it.
- **Who may log in (`pg_hba.conf`).** pg_autoctl creates each cluster with
  `initdb --auth=trust`, whose six lines let every account of the server,
  the triage user's too, log in as the superuser `postgres` through the
  local socket and the loopback address. MMX's `pg_auto_failover_node` and
  `pg_auto_failover_monitor` replace `trust` in initdb's six lines on every
  run. The replacement methods match Debian's packaging defaults, which
  `staging01`'s cluster already uses: `peer` through the local socket, a
  password through the loopback address. The monitor's socket line is
  `peer map=pg_autoctl`, because pg_autoctl logs in to the monitor as
  `autoctl_node`.

  The `database_server` role writes the apps' lines into
  `/etc/postgresql/pg_hba_logins_of_the_apps.conf`, which `pg_hba.conf`
  includes with `include_if_exists` (Postgres 16 and later). Each app's
  role gets one line, to log in with its password from the app servers'
  range, `vars.private_ip_ranges.app_servers`. On `staging01`, the line's source is `staging01`'s
  own address, because `staging01`'s containers use the server's network.
  Each production database server also permits an app-role password login
  from the database server's own private address. Secret rotation uses
  the local TCP login to prove the current vault password works.
  While `jobs_servers` holds a server, each app's role also gets a line
  from the jobs servers' range, `vars.private_ip_ranges.jobs_servers`.
  The `database_server` role removes the jobs servers' lines when the last
  jobs server leaves the inventory.

  PgBouncer's lines for the apps' Postgres roles, from the database
  servers' range, are in the `pgbouncer` role's own file,
  `/etc/postgresql/pg_hba_logins_through_pgbouncer.conf`. The
  `pg_auto_failover_node` and `pg_auto_failover_monitor` modules change
  only lines whose method is `trust`, which the apps' lines never have.
  pg_autoctl adds its own lines to `pg_hba.conf`, for the monitor and
  for replication: when it creates the node, and on every node each time
  another node joins the formation. A joining replica, and an old primary
  that pg_rewind brings back, copy `pg_hba.conf` from the current primary,
  including the include lines. The included files, outside the data
  directory, contain each database server's own address for the rotation
  check; the remaining app rules agree across database servers.
  - **Why separate files:** the `postgres_logins` block writes the apps'
    lines. The block reloads Postgres only when the block's tracked inputs
    differ from MMX's record of the block's last reload
    (`only_when_tracked_inputs_changed`). MMX's record holds whole files.

    With the apps' lines in `pg_hba.conf` itself, `pg_hba.conf` also
    changed after the run. pg_autoctl's keeper adds two lines for a new
    node on every other node, after their stage of the run has ended, and
    reloads Postgres itself. pg_rewind and a replica's copy also bring the
    current primary's `pg_hba.conf`. So the daily server settings comparison's dryrun
    reported a reload that nothing needed, until the next `every_server`
    run. A run on test servers showed the reload after a database server
    joined.

    A reload on every run, without the record, was rejected. The block's
    dryrun would then have to report nothing, whatever changed, and
    Postgres would reload at every run.

    `include_if_exists`, not `include`, because a cluster that a replica
    copied or a restore brought back already holds the include lines. The
    roles write the included files on the cluster's server later. With
    `include_if_exists`, Postgres skips a missing file, but with `include`,
    Postgres would refuse to load `pg_hba.conf`. The lines that an earlier
    version wrote into `pg_hba.conf` itself stay on the systems that the
    earlier version built. The old lines admit the same logins as
    `/etc/postgresql/pg_hba_logins_of_the_apps.conf` and
    `/etc/postgresql/pg_hba_logins_through_pgbouncer.conf`, so the old
    lines admit no one new.

    MMX's `pg_auto_failover_node` keeps Postgres's settings outside the
    data directory too, in
    `/etc/postgresql/pg_auto_failover_node_settings.conf`, for a similar
    reason. pg_rewind and a replica's copy bring another server's
    `postgresql.conf`, but each server keeps values sized from the
    server's own memory.
- **Postgres listens only on its WireGuard address:** a node on its
  `private_ip`, the monitor on `10.20.0.1`, `staging01`'s cluster on
  `10.20.0.2`. No other address of the server reaches Postgres, whatever the
  firewall says; ufw also admits port 5432 only on `wg0`, from the servers
  listed in [Firewall](#firewall), and `pg_hba.conf` only their addresses.
  pg_autoctl, MMX's modules, pgBackRest, MMWatchdog's checks, and the
  triage user log in through the local socket, so nothing needs the
  loopback address. Postgres binds its address when it starts,
  so a drop-in starts its service, `pgautofailover.service` or
  `postgresql@17-main.service`, after `wg-quick@wg0.service` at boot.
- **On existing production nodes, only `update_database_servers` restarts
  Postgres for changed settings.** While the formation has a replica,
  `update_database_servers` never restarts the server that is the primary.

  `archive_mode` and `shared_buffers` take effect only when Postgres
  restarts, and a restart drops every connection of the apps; with
  synchronous replication, even a replica's restart makes the primary's
  writes wait. An agent can run configuration changes at any hour.
  So an `every_server` run restarts Postgres only where a restart
  interrupts nobody. A restart interrupts nobody on a server whose node
  the same `every_server` run created, and on `staging01`, which serves no
  customers. The `database_server` role
  passes `pg_auto_failover_node` its input
  `restart_postgresql_for_new_settings`, which decides each call's
  restart:
  - **`every_server` passes `never`:** the module writes the file and
    reloads Postgres, so what a reload loads takes effect at once, and a
    setting that takes a restart waits, named in the task's reason and its
    output `postgresql_settings_waiting_for_a_restart`. The reason's hint
    names the module's input. The template's [update_and_restart_the_database_servers.md](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/update_and_restart_the_database_servers.md)
    tells the coding agent to run `update_database_servers` instead of a
    task with `restart_postgresql_for_new_settings`. A node that the run
    creates restarts with its settings at once, whatever the input.
  - **`update_database_servers` passes `on_a_replica`** to each server in
    maintenance, so the primary doesn't wait for it, and to the old primary
    only once a switchover made it a replica: writes fail only for the
    seconds of the switch.
  - **With `db01` alone, `update_database_servers` passes
    `on_a_replica_or_a_node_alone`:** `db01` restarts in place, in the
    team's weekly window, with a few seconds of failed requests.
  - **The `pg_auto_failover_node` module** restarts a replica only through
    maintenance, once the formation has settled. The module never restarts
    the primary of a formation with a replica. The module refuses the
    primary's restart and puts back the earlier
    `/etc/postgresql/pg_auto_failover_node_settings.conf`, so the earlier
    settings stay in effect. The module decides on a restart from the
    settings that Postgres marks `pending_restart`. So a later run that may
    restart Postgres applies the settings that an earlier `never` run left
    waiting.
  - **Why `pg_auto_failover_node` manages settings instead of the
    `database_server` role's own tasks:** the `database_server` role kept
    the settings in two files of the role's own, with an include line, an
    assert, and a restart for each file. The `pg_auto_failover_node`
    module does the same work: writing, including, checking, and
    activating the settings. The module also does three things that the
    role's tasks did not:
    - Postgres checks each value before the reload.
    - Another file that sets a setting again, such as
      `postgresql.auto.conf`, fails the task.
    - If a value keeps Postgres from starting, a run with the corrected
      value repairs Postgres. The repair works because the module writes
      `/etc/postgresql/pg_auto_failover_node_settings.conf` before the
      module waits for Postgres.

    Postgres's settings have one way in: `pg_auto_failover_node`.
  - **Why existing nodes restart through `update_database_servers` instead
    of `every_server`:** with a person's approval, an `every_server` run
    restarted one server at a time, in name order. The run checked only
    "Postgres answers" between servers. On test servers the primary's
    restart was a failover at once, because the primary's keeper reported
    Postgres as not running. The replica's restart came while the monitor
    promoted the replica. Both servers then went on from the same point
    with different histories, and every write hung for 7.6 minutes.

    Letting `every_server` restart `db01` alone
    (`on_a_replica_or_a_node_alone`) was rejected. One way for every
    restart is simpler. And a refusal by the inventory's count of database
    servers left two cases stuck, such as `db01` with a restart waiting
    when `db02` is added. A safe order inside `every_server` was rejected
    too. The safe order would copy `update_database_servers`' order into
    the playbook that `util01` runs at every commit. Then `every_server`
    would switch the primary over for any change that waits for a restart.
  - **The cost of `never`:** the waiting value is already in
    `/etc/postgresql/pg_auto_failover_node_settings.conf` on every database
    server, including the primary. So a restart for another reason, such as
    a crash, starts Postgres with the waiting value.

    Previously, `every_server` refused a change that needed a restart,
    before the new value reached the `database_server` role's settings
    files. The refusal kept the new value off the server until the planned
    restart, but failed every `util01` run until the restart. And
    `pg_auto_failover_node` has Postgres check each value first.

  A change that needs no restart, such as a change to `pg_hba.conf`, takes
  effect at once with a reload.
- **Security updates.** On the database servers, `every_server` holds back
  the updates of Postgres, pg_auto_failover, and the kernel with
  `Unattended-Upgrade::Package-Blacklist`, written from
  `roles/every_server/files/unattended_upgrades.conf`.
  `update_database_servers` installs the held-back updates in the team's
  weekly window, together with any setting that waits for a restart of
  Postgres.

  `update_database_servers` updates each replica in maintenance, then
  switches the primary over, then updates the old primary. Until `db02`
  exists, the playbook updates `db01` alone, with a short outage. A server
  reboots when an update asks for a reboot. Otherwise, `needrestart`
  restarts each service that still uses a replaced file.

  `staging01` and `util01` aren't database servers,
  so their Postgres updates itself with the daily security updates: staging
  serves no customers, and a restart of the monitor interrupts no app.
- **The operating procedures.** `switch_database_primary --var server_name=db02` makes a
  healthy replica the primary, waits until the old primary is a replica
  again, and checks each app through its public host name. Every database
  server's alerts are held while `switch_database_primary` runs, as
  `update_database_servers` holds them. Without the hold, each switchover
  sent warnings that wake nobody, such as the old primary's archive check
  while it restarted as a replica, and the triage agent answered each one.
  `update_database_servers` is the update that "Security updates" above
  describes.

  `remove_server` takes a
  replica into maintenance, so writes go on, and out of the formation;
  `pg_auto_failover_node` refuses maintenance on the primary, before
  anything changes. A server that is gone needs no playbook: deleting the
  server from the inventory makes `util01`'s next run remove the server
  from the formation. And the monitor never drops a healthy primary.
- **The primary is what the monitor assigned,** as MMX's modules report it:
  `pg_auto_failover_node`'s `is_primary`, with which the `database_server`
  role runs the primary's own tasks, such as the apps' databases;
  `pg_auto_failover_monitor`'s `primary_node_name`, which
  `update_database_servers` reads on `util01` with a copy of the
  `util_server` role's task `failover_monitor_with_the_production_formation`,
  with the same inputs; and `pg_auto_failover_primary` for a
  switchover.
  A server's own report cannot decide: after a failover, the old primary
  can still report `primary`.

  The `pg_auto_failover_node` and `pg_auto_failover_primary` modules wait
  for a settled formation at the start of a task and after the task's
  change. Each wait lasts at most five minutes. A settled formation has
  every node healthy in the state assigned by the monitor. So a stage of
  one server at a time starts each server on a settled formation. And a
  switchover ends with the old primary caught up as a replica.

  Tasks that call `pg_auto_failover_node` or `pg_auto_failover_primary`
  get `time_limit: 20m` for the waits before and after the task's change.
  MMX's modules do not report which healthy replica a switchover goes to.
  `update_database_servers` reads the replica from
  `show_the_database_servers_and_their_health`
  (`roles/database_server/files/`), which `update_database_servers`
  installs on `util01`.
- **A run of `update_database_servers` that stopped partway runs again
  from the start.** On each replica's turn, `update_database_servers` ends
  pg_auto_failover maintenance left by the stopped run. The wait of
  `pg_auto_failover_node` and `pg_auto_failover_primary` at the start of
  each task holds the run until the formation has settled. The program
  that names the replica to switch to reads the formation only after the
  replicas' turns. The late read is needed because the program fails on
  any formation that hasn't settled, a replica in maintenance included.
  With the read before the replicas' turns, every run after a run stopped
  with a replica in maintenance would stop at the read.

  An earlier version of `update_database_servers` refused an unsettled
  formation at once, so a run that stopped with a replica in maintenance
  could not run again. A later version read the primary by running the
  `database_server` role on every database server first. The role run
  ended the maintenance of a replica whose Postgres could not start, and
  then failed minutes later. The monitor names the primary instead. While
  the monitor names no primary, as for some seconds of a failover, the run
  stops on `util01`, before any server's alerts are held.

  If a value keeps Postgres from starting after a restart, an
  `every_server` run with the corrected value repairs a replica or `db01`
  alone. The repair works because the `pg_auto_failover_node` module
  writes `/etc/postgresql/pg_auto_failover_node_settings.conf` before the
  module waits for Postgres. pg_autoctl then starts Postgres with the
  corrected value
  (the template's [update_and_restart_the_database_servers.md](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/update_and_restart_the_database_servers.md)).
  At a task's start, `pg_auto_failover_node` counts the task's own node as
  stopped while the node's Postgres does not answer. So on a node alone, a
  value that keeps Postgres from starting does not hold the task waiting
  for a settled formation. With `db01` alone, the apps stay down until the
  `every_server` run with the corrected value repairs Postgres.
- **A rebuilt failover monitor knows no node.** After `util01` is
  rebuilt, MMX's `pg_auto_failover_node` registers each node with the new
  monitor, the primary first, while a replica waits up to five minutes for
  a primary. The `database_server` stage runs one server at a time, in the
  order of server names, and stops at the first that fails, so a replica
  whose name comes first, as after a failover, would keep the primary from
  registering, run after run. The rebuild therefore runs the primary's
  `every_server` and `database_server` stages alone first (the template's
  [rebuild_the_utility_server_util01.md](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/rebuild_the_utility_server_util01.md)).
  Running the `database_server` stage on every database server at once was
  rejected. At once, a replica's wait for the primary would keep the order
  of registration. But one server at a time is what stops a failing change
  at the first server, such as a change that keeps Postgres from starting.
- **Backups.** The timers run on every database server, so the backups
  follow the primary after a failover. A new stanza gets its first full
  backup at once, so the backup check passes from the first day.
  pgBackRest encrypts every file before it leaves the server, because the
  bucket's lock protects the backups from deletion, not from reading by
  whoever takes over the B2 account. The pgBackRest backup repository's
  passphrase cannot change without a new pgBackRest backup repository.
- **One template for pgBackRest's settings,** the project's
  `files_used_by_several_roles/pgbackrest.conf`, which the `database_server` role and
  `restore_database` both render, so a restore reads the repository exactly
  where and as the backups wrote it: the same path, address style, and
  cipher. A role reads only its inputs and a playbook its variables, so the
  template reads one mapping, `pgbackrest_settings`. Each caller sets
  `pgbackrest_settings` with `set_vars` immediately before rendering
  `files_used_by_several_roles/pgbackrest.conf`: the bucket, the bucket's
  key, the passphrase, and the cluster's data directory. The restore's key
  can only read.

### PgBouncer, a later step

When Postgres connections in use pass about 70% of `max_connections`
(MMWatchdog's `postgres/connections_are_below_70_percent`), PgBouncer goes
on each database server and on `staging01`, in front of the server's own
Postgres: the operating procedure "Adding PgBouncer" in the template's [add_pgbouncer.md](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/add_pgbouncer.md#adding-pgbouncer).
PgBouncer lets many app connections share a smaller pool of Postgres
connections, lending a Postgres connection for each transaction.

PgBouncer's role, `roles/pgbouncer`, is in the template from the start.
Three settings in `mmx_project_settings.yml` enable PgBouncer, one commit
each:
`pgbouncer_runs_in_front_of_postgres`, which runs the role in every
`every_server` run, then `apps_connect_through_pgbouncer.staging`, then
`.production`. Enabling `pgbouncer_runs_in_front_of_postgres` first puts
PgBouncer on every database server before an app's settings point at
PgBouncer. Enabling staging's `apps_connect_through_pgbouncer` before
production's sends staging's apps through PgBouncer first. Until
`pgbouncer_runs_in_front_of_postgres` is `true`, no part of PgBouncer
runs.

| What | Name |
| --- | --- |
| PgBouncer | Debian 13's package `pgbouncer`, 1.24.1, because Postgres comes from Debian too; 1.21 is the first release that keeps prepared statements in transaction mode |
| Where PgBouncer listens | the server's WireGuard address, port 6432; PgBouncer's admin console on the socket in `/var/run/postgresql` |
| PgBouncer's settings | `/etc/pgbouncer/pgbouncer.ini` from `roles/pgbouncer/files/pgbouncer.ini`; a drop-in for `pgbouncer.service` |
| The pool | transaction mode, `max_prepared_statements = 200`, at most 20 Postgres connections per app's database on each server (`default_pool_size`), fewer when more than two apps share 54 connections, room for 10,000 clients |
| The apps' settings | `DATABASE_URL` and `DATABASE_READ_URL` name `db01:6432,db02:6432` in each environment whose `apps_connect_through_pgbouncer` is `true`; `db01:5432,db02:5432` before. `target_session_attrs` remains `read-write` for `DATABASE_URL` and `prefer-standby` for `DATABASE_READ_URL`. |
| Direct to Postgres | `/etc/<app>/<app>_database_direct_to_postgres.env`: `DATABASE_URL` and `DATABASE_READ_URL` at port 5432, on every server that runs the apps' containers |

- **What connects directly.** Transaction mode lends a Postgres connection
  to a client for one transaction, so what lives in a session between
  transactions is lost. The apps' migrations connect directly to Postgres,
  for two reasons. PgBouncer refuses the migrations' `PGOPTIONS` at login
  ("unsupported startup parameter in options: lock_timeout", on test
  servers with PgBouncer 1.25.1 and Postgres 18). And a migration can hold
  a session-level advisory lock, as Rails' migrations do.

  An app's job container connects directly to Postgres when
  `jobs_connect_directly_to_postgres` is `true`. Direct connections support
  workers that wait with `LISTEN`/`NOTIFY` or hold a session-level lock,
  such as good_job.
  Replication, the failover monitor, pgBackRest, the restore drill, and
  MMWatchdog's checks keep the connections they had. The direct file comes
  after the secrets file in `run_app_migrations` and in such a job
  container's Quadlet file, because Podman lets a later env file's setting
  win.
- **The jobs are decided per app,** not for every job container at once: a
  job container holds about as many connections as a web container, so
  sending them all directly would keep about half of the connections that
  PgBouncer is there to save. `jobs_connect_directly_to_postgres` is
  required on every app from the initial setup onward. So the coding agent
  inspects each app once during initial setup, alongside the rest of the
  app contract, to choose `jobs_connect_directly_to_postgres`. The job
  container's template names `jobs_connect_directly_to_postgres` when the
  setting is missing.
- **No second copy of a password.** PgBouncer reads each client's password
  from Postgres at each login (`auth_query`), as `postgres`, through the
  local socket: it runs as the account `postgres`, which reaches Postgres as
  its administrator already, so it gains nothing, and no new secret exists.
  The query admits only the apps' roles. PgBouncer logs in to Postgres as
  the client's role, with the keys of the client's own login (SCRAM), over
  TCP to the server's WireGuard address, so its role's file of `pg_hba.conf`
  lines, `/etc/postgresql/pg_hba_logins_through_pgbouncer.conf`, holds one
  line per app from `vars.private_ip_ranges.database_servers`, and
  `inet_server_addr()` still names the server, as the reference app's page
  shows it. PgBouncer keeps what it read only in memory, never on disk,
  and asks Postgres again at the next login, so a new password works at
  once.
- **Rotating a database password.** PgBouncer keeps a client logged in
  after its password changed and lends it new Postgres connections with the
  keys of later logins, so `end_connections_that_use_an_old_database_password` first ends PgBouncer's client
  connections of the role older than the cutoff (`KILL_CLIENT`, from
  PgBouncer 1.24), then the Postgres connections, as before. The cutoff is
  the start time of the oldest container, across the environment's
  servers, among the apps whose database password changes.
  The task `end_the_pgbouncer_clients_older_than_the_oldest_container` runs
  only where `/etc/pgbouncer/pgbouncer.ini` exists. So the client-termination
  task follows PgBouncer's installation, even after
  `pgbouncer_runs_in_front_of_postgres` is back to `false`. The Postgres
  connections ended by `end_the_connections_older_than_the_oldest_container`
  include PgBouncer's connections opened before the rotation. A transaction
  that runs on one of PgBouncer's old connections when the connection ends
  fails, once.
- **The stack restarts PgBouncer whenever the local Postgres starts,
  becomes a standby, or is promoted.** The restart is needed because
  PgBouncer keeps client connections across Postgres restarts and changes
  between primary and standby. Until PgBouncer restarts, PgBouncer keeps
  passing each new client what Postgres reported at PgBouncer's first
  connection, such as `in_hot_standby`.

  The following results come from test servers with PgBouncer 1.25.1 and
  Postgres 18. After a failover without a PgBouncer restart, the app's pgx
  pool kept its connections to the old primary's PgBouncer, now in front
  of a standby. Every write failed with "cannot execute INSERT in a
  read-only transaction". A new libpq connection (Rails, Django) with
  `target_session_attrs=read-write` reached the standby. Without a
  PgBouncer restart at the promotion, libpq found no server for writes at
  all.
  - **What the refresh program does:** the refresh program,
    `refresh_pgbouncer_when_postgres_starts_or_changes_role`
    (`roles/pgbouncer/files/`), first waits, at most 60 seconds, until
    `pg_is_in_recovery()` agrees with `standby.signal`. The wait exists
    because Postgres deletes `standby.signal` before Postgres leaves
    recovery. A connection between the deletion and the end of recovery
    still reports a standby. A PgBouncer refreshed between the deletion and
    the end of recovery would tell libpq clients that Postgres is a standby
    until the next change.

    On a primary, the refresh program also waits until
    `default_transaction_read_only` is off. pg_autoctl turns
    `default_transaction_read_only` on before a switchover and off about a
    second after the promotion. A PgBouncer restarted in the second before
    `default_transaction_read_only` turns off tells every libpq client that
    the server is read-only. On test servers, every write through such a
    PgBouncer then failed until PgBouncer's next restart.

    Then the refresh program restarts PgBouncer, on a standby and on a
    primary alike. PgBouncer's clients connect again, so a driver that
    wants writes finds the primary. A restart waits for the transactions in
    flight, and a long query once held a restart up for 90 seconds. So the
    drop-in's `TimeoutStopSec=10s` limits the wait to ten seconds.
  - **Why a restart on the primary too:** a `RECONNECT` on the admin
    console, which keeps PgBouncer's clients and listener and replaces each
    Postgres connection once its transaction ends, was the first choice for
    a promotion. On test servers with PgBouncer 1.25.1, a `RECONNECT` didn't
    refresh the `in_hot_standby` that new clients get at login. After a
    switchover, libpq (Rails, Django, PHP) found no primary through PgBouncer
    until PgBouncer on the promoted server restarted. The restart fixed the
    failure at once, in 0.34 seconds and with 3 failed requests.
  - **When the refresh program runs:** a systemd path unit,
    `refresh_pgbouncer_when_postgres_starts_or_changes_role.path`, watches
    two files of the data directory and starts the refresh service on a
    change. Postgres writes `postmaster.opts` at each start, before
    Postgres accepts a connection, and pg_rewind leaves `postmaster.opts`
    alone. pg_autoctl writes `standby.signal` when pg_autoctl sets the node
    up as a standby, and at each pg_autoctl reload. pg_autoctl deletes
    `standby.signal` while pg_autoctl follows a new primary, and Postgres
    deletes `standby.signal` at a promotion. `postmaster.pid` can't serve:
    the postmaster opens it for writing every minute.

    An old primary that comes back makes about five changes in a few
    seconds, and the refresh program's wait takes the changes together.
    The service's `StartLimitIntervalSec=0` keeps systemd from refusing a
    start after five in ten seconds, which would switch the watch off
    without a word.
  - **PgBouncer's checks** (`mmwatchdog_checks/database_servers.yml`, group
    `pgbouncer`): `pgbouncer.service` runs, the admin console answers
    `SHOW VERSION` (a PgBouncer that runs but hangs doesn't), and the path
    unit runs. A failed run of
    `refresh_pgbouncer_when_postgres_starts_or_changes_role.service`
    shows in every server's check for failed units.
- **PgBouncer's updates wait for the team's weekly window** on the
  database servers, as Postgres's do. An update restarts PgBouncer, which
  drops the apps' connections on the updated server. `staging01` updates
  PgBouncer every day.
- **`staging01` runs PgBouncer too,** so staging's apps run through
  PgBouncer's transaction mode before production's apps do.
  `apps_connect_through_pgbouncer` is set per environment, and `false`
  sends an environment's apps directly to Postgres again.
- **The connections PgBouncer serves are unencrypted:** it offers clients
  no TLS, and the drivers fall back to a plain connection, over WireGuard,
  which encrypts it.

### Moving an existing database into the Stack

`vars.database_moving_in` in `inventories/servers.yml` describes one old,
unmanaged PostgreSQL server. An empty mapping disables the move. The mapping
holds `wireguard_address`, `wireguard_public_key`, `public_ipv4_address`,
`postgres_port`, `copy_onto`, `apps`, and `through_relay`: `true` for a
managed source behind a relay, `false` for a self-hosted source.
`through_relay` is required, because the switch playbook's `when` reads it
and MMX fails on a missing key.
The address belongs to
`vars.private_ip_ranges.database_moving_in`. `copy_onto` names the first
database server in name order, which a new formation makes primary.
The move refuses unknown apps and invalid addresses before changing servers.
The empty project default lets the person remove the inventory block after
the switch. The old address lies outside every other role range, so the
old peer cannot inherit a desk range's incoming SSH permission.
The old server never joins an inventory group, because the Stack must not
configure or replace the running old PostgreSQL cluster.

App, jobs, and database servers peer with the old server on UDP 443 (the old server redirects it to 51820 as
[the WireGuard network](#the-wireguard-network) describes; the procedure gives it by hand).
Their existing firewalls admit replies, but add no incoming service rule
for the old server. Staging, desks, and load balancers need no old-server peer.

The listed apps put the old address first in their database URLs.
During the move, their read URL also uses `target_session_attrs=read-write`.
Reason: `prefer-standby` would select the unfinished copy on a Stack replica.
Both URLs retain `connect_timeout=3`. The old server always uses its own
PostgreSQL port, including when Stack connections use PgBouncer.
Each listed app's Stack role has `default_transaction_read_only=on`.
The subscription belongs to `postgres`, so replication can still write.
The copy and switch playbooks put the source password file on every database
server, so a promoted replica can reconnect to the source.
Drivers must test transaction writability, not only recovery state.

`copy_the_database_moving_in` loads each app's schema and creates its logical
subscription. Logical replication works across PostgreSQL major versions.
The ordinary `every_server` path creates the formation and its backups first.
No restored-cluster adoption, registration restart, or physical source copy occurs.
The app passwords match on the old server and in the Stack vault.

A managed source requires a temporary
Debian 13 relay inside the provider network at the existing `database_moving_in`
WireGuard address. The relay uses PgBouncer from PostgreSQL's apt repository,
with session pooling and verified TLS
to the provider hostname, with the provider's CA bundle. Replication uses the
same relay. Stack clients use ordinary PostgreSQL without TLS inside WireGuard.
TLS ends on the relay. Reason: a multi-host URL applies its TLS settings to
every host, while the Stack database servers use WireGuard without PostgreSQL
TLS. The relay preserves the existing URLs and driver discovery.
The relay requires PgBouncer 1.26.1 or newer and
`track_extra_parameters = lock_timeout`. The relay's guide checks the PGDG
signing-key fingerprint published by PostgreSQL before adding the
`trixie-pgdg` apt source. Reason: Debian 13's PgBouncer 1.24.1 cannot carry
the migration's `PGOPTIONS=-c lock_timeout=5s` to PostgreSQL 15.
PgBouncer 1.26 fixes tracked startup parameters that the server does not report.
With 1.26.1, the backend reads five seconds for that client, then zero when
the same backend serves a client without the option. Ignoring the option
would remove the migration guard. The Stack's own optional PgBouncer
continues to use Debian's package; the temporary relay needs the newer
version because app migrations must pass through it.
The relay switch first sends `DISABLE` for every moving app database entry,
then `KILL` for every entry, through PgBouncer's admin console.
`DISABLE` refuses new clients. `KILL` drops existing client and server connections.
Reason: PgBouncer restores cached session settings, including a writable
`default_transaction_read_only`, on new backends. A database default alone cannot
fence a warm relay. Successful switches leave the app entries disabled.
The console listens only on `wireguard_address`, at `postgres_port`, alongside
the database listener. The fixed `admin_users` login is
`database_moving_in_relay_admin`. The vault key is
`database_moving_in_relay_admin_password`. The relay switch writes the password
to `/var/lib/postgresql/database_moving_in_relay_admin.pgpass`, owned by postgres with mode 0600.
One playbook, `switch_to_the_database_moving_in`, switches both kinds of
source. Its fleet stage `switch_to_the_database_moving_in` runs when
`through_relay` is false, and `switch_to_the_database_moving_in_through_relay`,
the only reader of the relay password, when it is true. Both are top-level
fleet stages whose `when` reads only vars, so MMX decides before the run
which one runs, and a self-hosted move needs no relay password. Reason:
one switch playbook for both kinds of move. The MMX release that
`stack_software.mmx` pins needs no secret of a top-level fleet stage whose
`when` is false on every server; an earlier MMX needs every secret of a
fleet stage that selects servers, and asks a self-hosted move for the
relay's password.
The copy playbook stays the same for every source.
Each moving database has a separate unfenced entry named after the database's
derived replication slot. Replication and source administrator reads use that entry.
The ordinary app URL keeps the database name and cannot select the copy entry.
Reason: replication, sequences and large-object export must remain reachable
while the app entry is disabled. Derived names avoid a second inventory mapping.
The inventory validator refuses a collision between copy entries and moving database names.
The copy probes the replication protocol instead of requiring a native role flag,
because providers can grant replication through a provider-specific role.
A source with row security still requires `BYPASSRLS` or a superuser replication
login, so policies cannot silently omit rows from the initial copy.

`switch_to_the_database_moving_in` fences each moving old database with
`ALTER DATABASE ... SET default_transaction_read_only = on`, then ends
the listed app sessions. Managed services refuse `ALTER SYSTEM`, so the
per-database fence provides one method for every source. Unlisted databases
remain writable. Undo uses `ALTER DATABASE ... RESET default_transaction_read_only`.
The switch waits for durable replay feedback, copies sequences and large objects, removes subscriptions
and their source slots, then opens the Stack app roles for writes.
The publisher's `pg_stat_replication` feedback supplies received, flushed,
and applied positions for each subscription. A replication-origin position
can remain behind a checkpoint after all published changes arrived.
The catch-up deadline is 15 seconds. Before any subscription is removed,
a failed switch restores the old fence setting and keeps Stack roles read-only.
After removal begins, an error leaves the old server fenced for explicit recovery.
Reason: reopening the old server after partial cleanup could split app writes.
Relay switches instead disable subscriptions before opening the Stack roles,
then drop subscriptions after the Stack opens. Every failure before opening
can re-enable subscriptions, reset database defaults, and `ENABLE` the app entries.
Rollback also runs `RESUME` for a paused app entry.
Reason: removing subscriptions before opening would make safe rollback impossible
after a partial cleanup. An error after opening keeps the relay fenced for inspection.
If the opening transaction loses a reply, rollback checks that every Stack app
role remains read-only before reopening the source. An unknown result keeps the source fenced.
The switch prints each part of the pause separately from the bulk copy.
The helper has no inherited task deadline or automatic retry. A fixed
deadline could interrupt fence recovery or a valid large-object transfer.
The program bounds its connection checks and catch-up wait itself.
Session termination signals and polls captured backend processes before
sampling the fence LSN. The barrier uses `pg_current_wal_insert_lsn()`,
which also covers asynchronous commits still in the source WAL buffers.
Stack backend sessions also end after role changes,
so PgBouncer cannot retain a backend with the previous defaults.
The source slot uses a database-name digest, because PostgreSQL permits
database names that do not fit a prefixed replication-slot name.
Subscription lookups include the current database's identity. PostgreSQL
shares the subscription catalog across the cluster, and each app database
uses the same subscription name. Worker checks use the resulting unique
subscription identity so several databases can move together.

The operating procedure is
[`move_a_database_into_the_stack.md`](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md).


## The checklist

`monkeymaxxing_stack_checklist.yml` holds the detailed evidence that a
person reads, and MMHotline's dashboard reads the checklist too. The
systems repository's `README.md` is the person's operating guide. The
template's copy of the checklist holds the items of the stack, all `open`,
as the checklist catalog. The checklist has two parts, and each item names
its part in `part`:

- **Setup** (`part: setup`) holds the items that the initial setup
  finishes, in the order the system is built. When the setup ends, every
  Setup item is `done`, or `deviated` with its reason.
- **Later, when it happens** (`part: later_when_it_happens`) holds the items
  that wait for a routine or an event that every team meets after the
  setup: a routine's first run, the first rollback, a team member joining,
  or a rotation. A Later item that stays open is no gap in the setup.

Reason: a person who hears "36 open items" at the end of the setup has no
first step, and the setup ends with items nobody can finish that day. The
two parts let the setup end with nothing open.

**The growth and improvement items have their own section,**
`growth_and_improvement_items`, a second list beside `items`. Growth is a
step such as a second app server or PgBouncer. Improvement is optional
practice, an extra check, or a recovery proof, such as the break-in drill
or "Check my system's protections". Each item names its `trigger`, a
measured warning or an event, and has `state: waits_for_its_trigger` until
the trigger comes, which never counts as open. After the step, the item
becomes `done` or `deviated` like any item. The weekly review checks only
whether a trigger arrived. Reasons: the growth and improvement items are
critical on the day their trigger comes, so the checklist keeps each item,
its trigger, and its verification. But most of them wait for years or
forever, and twenty open items that nobody can act on make a working system
look unfinished and turn the weekly review into a reading of the whole
file.

`staging_server`, `second_app_server`, and each app's
`<app>_seed_command_fills_test_data` are Later items for every team. A
team that chooses the fuller system in chapter 1 (answer two
questions) gets their `waits_for` set to
chapter 7's step that adds the two servers, and the operating procedures
that add the servers finish the items. Reason: the items move nowhere in
the file, and the same procedures finish them on a later day.

MMHotline's dashboard reads only the top-level `items` list and each
app's `items`, in the order of the file, so the dashboard does not show
`growth_and_improvement_items`. Reason: the dashboard is for what needs a
person now. The growth and improvement items are a separate list, not a
third `part` inside `items`, because the dashboard lists every open item of
`items`, and would list twenty waiting items beside the work that needs a
person.

The checklist holds each protection's evidence only to the point that the
setup proves. The detailed checks of the Stack's own behavior, such as the
exact firewall rules, are in the optional "Check my system's protections"
of `operating_procedures/assess_a_running_system_and_recommend_changes.md`.
The item `optional_protection_checks` records that the team asked for the
checks. Reason: the Stack's own tests prove how the Stack's software
behaves, and a person who repeats the tests on every system spends the
working day on an exam.

The checklist has no item for a provider the coding agent cannot reach without reading the credential.
The setup offers only the providers the coding agent can reach that way, and says "not
ready yet in this Stack version" for any other. Reason: an item that no
team can finish stays open forever and teaches the team to ignore open items.

```yaml
stack_version: 0.1.0
stack_commit: "3f2a1c9..."          # the stack's commit the template files came from, written in by the coding agent
apps:
  shop:
    items: [...]                    # the app contract's items, one copy per app, first: the app is checked before any server exists
items:
  - id: backups_restore_every_week
    title: Backups restore, every week
    state: open                     # open, done, or deviated
    part: later_when_it_happens     # setup, or later_when_it_happens
    protects_against: losing data to a mistake, an attacker on a database server, or an account takeover
    verification: the weekly restore drill restored the end of production's archive on restore01, and each app's check queries passed
    verify_again_every: 7d          # optional: d for days, months for months
    waits_for: the initial setup              # on open items: what must happen first
    # done items add verified_at (UTC) and last_result; deviated items add deviation
growth_and_improvement_items:
  - id: second_app_server
    title: A second app server, app002
    state: waits_for_its_trigger    # waits_for_its_trigger, done, or deviated
    protects_against: the site going down with app001
    verification: with app001's power cut, each app's public host name kept answering, served by app002
    trigger: the first paying customers, or when the business cannot stay down while an app server is replaced
what_this_system_does_not_survive: >
  ...
```

- `verification` states what must pass, so `verification` stays the same
  before and after a check. `last_result` records what the latest check
  measured.
- `done` is set only after the verification passed, with `verified_at`.
  When `verified_at` is older than `verify_again_every`, the item counts as
  open again.
- `deviated` carries `deviation`: what differs and why.
- The items are in two parts, "Setup" and "Later, when it happens", and
  the growth and improvement items follow in their own list.

## Firewall

Every production and staging server uses ufw. The desk uses nftables as described in [The systems desk](#the-systems-desk). ufw's rules come from the rules every server gets and
the lines of `connections_between_server_pools` whose `to_pool` is the
server's pool, with the inventory addresses of the allowed source servers
([Which pool talks to which](#which-pool-talks-to-which)); the table below
is what the Stack's own table gives. The firewall
blocks incoming internet traffic except for the traffic allowed below.
Servers in `database_restore_servers`, such as `restore01`, admit only SSH
on `wg0` from `util01` and the systems desks' block, plus public WireGuard UDP 51820
([Restore drill and recovery](#restore-drill-and-recovery)). `restore01`
peers only with `util01`, so in practice only `util01` reaches `restore01`.

| Port | Where ufw allows the port | Open to |
| --- | --- | --- |
| TCP 22 (SSH) | `wg0` on production and staging | the inventory's systems-desk range and `util01`, on restore servers too |
| UDP 51820 (WireGuard; servers and desks send to 51820, laptops to UDP 443, which the redirect turns into 51820 before the firewall) | every server | every source, including roaming laptops connecting to desks |
| TCP 7443 (MMX's HTTPS) | `wg0` on production and staging outside `database_restore_servers` | `util01` |
| TCP 8001 to 8099 (the apps' `web_ports`) | `wg0` on app servers | the app servers while they run the tunnel connector and Caddy; the load-balancer servers |
| TCP 5432 (Postgres) | `wg0` on database servers | the app servers, the jobs servers, the database servers, `util01` |
| TCP 6432 (PgBouncer) | `wg0` on database servers | the app servers and the jobs servers, which run the apps' containers. Open from the start; nothing listens until PgBouncer runs |
| TCP 5432 (the failover monitor) | `wg0` on `util01` | the database servers |
| TCP 8445 (MMWatchdog's fleet hub) | `wg0` on `util01` | every server |
| TCP 8484 (MMHotline's signed alert routes) | `wg0` on `util01` | every server |

`staging01` opens SSH on `wg0` to desks and `util01`, UDP 51820 to every
source, and TCP 7443 on `wg0` to `util01` only. The apps on
`staging01` reach Postgres on `staging01` through local connections, which
need no firewall rule. No other server uses `staging01`'s Postgres.
A load-balancer server opens SSH on `wg0`, UDP 51820 to every source,
and 7443 to `util01`, and no web port: its tunnel
connector dials out to Cloudflare, and its Caddy dials out to the app
servers.

A jobs server opens SSH on `wg0`, UDP 51820 to every source,
and 7443 to `util01`: its job containers only connect out.

MMX's HTTPS process listens on every interface, so its rule names the
interface (`incoming_interface: wg0`).

## Software sources

**Debian only.** The Stack runs only on Debian, including restore drills.
Use Debian 13, with `server_image: debian-13` at Hetzner, the one setting
for the image of every server `util01` creates.
Chapter 6 (create your three production servers: app, database, and tools) gives the team's
[server image rule](../skills/monkeymaxxing-stack/systems_repository_template/initial_setup/06_create_your_three_production_servers.md#the-server-image).

The Stack supports each Debian release while Debian's security team
provides regular security support. As of 2026-11-03, Debian 13 is the only
supported release. Debian 12's regular support ended in 2026, so Debian 12
is now in Debian LTS. Debian LTS is run by a separate team and covers fewer
packages, so LTS does not qualify a release for the Stack.

A new Debian release, such as Debian 14, joins the Stack only after the
test runs that [Testing](testing.md) requires pass. From the Stack version
that adds the new Debian release, new servers start on the new release.
Running servers can stay on their release while its regular security
support lasts, which Debian ends about one year after the next release.
MMWatchdog's `security_support_lasts_another_half_year` check, with
`security_support: regular`, warns 180 days before regular support ends.
It does not count Debian LTS, because LTS does not qualify a release for
the Stack.
Before then, the servers move to the new release. Most servers move with
[Replace a server](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/replace_a_server.md).
The database servers also change their Postgres major version, which
Replace a server alone does not cover, so the Stack version that adds the
release brings tested steps for them.
Never upgrade a server's Debian release in place.

Reason: on Ubuntu, the Stack's Podman and container tools, pgBackRest,
and pg_auto_failover come from Universe. Without Ubuntu Pro, Universe gets
security fixes only when community volunteers provide them. Canonical's own
security fixes for Universe arrive through Ubuntu Pro's ESM Apps, which
requires an Ubuntu Pro subscription. A test system on Ubuntu 26.04
found a buildah security fix, available only through ESM Apps, waiting on
an app server. Neither apt nor MMWatchdog's
`apt_security_updates` check could see the waiting fix. Ubuntu has also
left critical security fixes open for weeks after Debian fixed the flaws.

Stack users always create new servers, so choosing Debian costs the team
nothing. MMX and MMWatchdog keep supporting Ubuntu. Only the Stack is
Debian only.

| Program | Source | Reason |
| --- | --- | --- |
| Postgres, pg_auto_failover, pgBackRest, Podman, WireGuard tools | Debian 13 | Security fixes come with the distribution |
| jq, on every server | Debian 13 | The Stack's bash scripts read and write JSON with jq |
| PgBouncer | Debian 13, 1.24.1 | Postgres comes from Debian too. Debian supplies security fixes within the distribution's package version. Debian's security tracker still lists flaws, including CVE-2026-19888 and CVE-2026-6668. The stack keeps the distribution's package because only servers running app containers reach PgBouncer, over WireGuard. App containers already hold database passwords and can load Postgres through their own logins. MMWatchdog's admin-console check alerts on a stall, MMWatchdog's `known_exploited_flaws` check warns about a PgBouncer flaw that attackers exploit, and the scheduled software review, when the team turns it on, reports PgBouncer's other flaws. `update_database_servers` installs PgBouncer fixes in the database servers' weekly window. unattended-upgrades holds PgBouncer back on database servers, but updates `staging01` daily. The Stack database servers keep Debian's package because another package source adds complexity and behavior changes. The temporary managed-source relay uses PGDG to preserve migration startup options. The restricted access limits the gain from replacing Debian's package |
| Caddy | the Caddy project's apt repository | Debian 13 ships Caddy 2.6.2 from 2022 |
| `cloudflared` | Cloudflare's apt repository | Not in Debian |
| MMX, MMWatchdog, MMHotline, Litestream (MMHotline's backup), rclone (the uploads' copy), and the systems desk's `set-up-outside-services` | the programs' release downloads, pinned by version and SHA-256 in `stack_software` | Not in Debian 13; Debian 13's rclone is 1.60, which can't sign in with today's bucket-restricted B2 keys ([Uploaded files](#uploaded-files)) |
| Claude Code, the triage agent's coding agent | Anthropic's apt repository, its stable channel | Not in Debian. Not pinned, for two reasons. Claude Code releases several times a week, so a pin would always be out of date. And Claude Code is only the triage agent's harness, the program that runs the agent's sessions and tools, unlike the programs that run the system. The stable channel serves a version about a week old and skips releases with major regressions |
| Codex, the triage agent's coding agent when the team chooses it | Codex's release package from GitHub, pinned by version and SHA-256 in `stack_software.codex` | Not in Debian, and Codex has no apt repository, so a pin is the only way to know what `util01` runs. The pin is the Codex version the pinned MMHotline release was built against |

[Debian's security tracker](https://security-tracker.debian.org/tracker/source-package/pgbouncer)
records which PgBouncer fixes Debian has supplied, rather than relying on
the upstream version number alone.

Every program that doesn't come from the distribution has an entry in
`software_outside_the_distribution.yml`.

**The scheduled software review is off by default.** The template sets
`triage_agent.software_review_interval_hours: off` in
`mmhotline_settings.yml`, so the triage agent starts only for an alert.
Reason: each review is one run of the coding agent,
measured at $1.12 on a quiet day and $1.97 for a first review, so a team
on the default would pay about $34 a month without having chosen it, and a
team must not be surprised by token costs. Turning the review on is one
setting: the review's task ships as `scheduled_software_review_task.md` at
the top of the systems repository, which MMHotline reads at each review's
starting commit, and
[Turn on the scheduled software review](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/turn_on_the_scheduled_software_review.md)
has the coding agent fit the task to the team's software, run one review
by hand, tell the person its cost and time and what a month costs at each
interval, and set the interval the person chooses. The task file holds the
task, which software and how; `triage_agent_rules.md` holds only the rules
for every software finding, such as reporting a finding once. Reason: one
home for each instruction, so a team that rewrites its task cannot leave a
contradicting copy in the rules.

**A review sends at most one report, and none when nothing changed.**
The task file has the agent put every new or
changed finding into one summary: first what a person must do, each item
with the exact playbook or procedure by its name, then what changed since
the last review. The summary is warn only when a person must act, such as
for a fix the nightly security updates did not install a day after Debian
published the fix, or a security release of a downloaded program. Every
other summary is info, and an SOS finding still makes the summary SOS.
A flaw with no fix is never reported: the agent records the flaw in
`triage_agent_notes/open_software_findings.md` only, and leaves out the
flaws Debian rates `unimportant`. The flaw enters a report when a fix
appears. The agent tells new or changed from unchanged by comparing each
finding, keyed by package or program and flaw ID, with the notes the last
review committed. Reason: in a test with a real agent, a first review
without these rules sent 9 alerts, 7 at warn, one for each group of findings. One of
the warnings said that 384 flaws had no fix and nothing was to be done,
and 107 of those flaws Debian rated unimportant. Other reports said "run
the ready playbook from the brotli report" instead of naming the
playbook. A phone that rings 7 times for one review, partly for warnings
nobody can act on, teaches the team to ignore warnings. MMHotline sends
nothing for a quiet review, because the
review's record already shows that the review ran and what the review
cost.

**mmx, MMHotline, MMWatchdog and `set-up-outside-services` have empty
pages in `software_outside_the_distribution.yml`.** The entries say that
the team gets each release from the archive pinned in `stack_software`,
and the task file has the agent compare the installed version with the
pin and fetch no page. MMHotline lists no host for an empty page. Reason:
the check group `pinned_program_releases` already warns about each new
release of these programs, and the triage agent reads its release notes
then ([New releases of the pinned programs](#new-releases-of-the-pinned-programs)).
When a product publishes an advisory page, the product's entry gets the
address.

While the review is off, plain checks watch the software and the coding
agent starts only when a check finds something: MMWatchdog's
`apt_security_updates` and `known_exploited_flaws` for the Debian
packages, unattended-upgrades for the programs from vendors' apt
repositories, and `pinned_program_releases` for the downloaded programs
([New releases of the pinned programs](#new-releases-of-the-pinned-programs)).

- **The triage agent is Claude Code or Codex, by default the same kind as
  the person's own coding agent.** `triage_agent_coding_agent` in
  `mmx_project_settings.yml` holds the choice, `claude_code` or `codex`; the
  coding agent that runs the setup sets it to its own kind without a
  question (one question fewer, and the team already has
  that vendor's account). `mmhotline_settings.yml` reads it for
  `triage_agent.coding_agent`, `util_server` installs Codex only when it is
  `codex`, and `set-up-outside-services secrets` reads it to ask for the
  matching credential. Reason: the team uses the coding agent it already
  trusts, and one setting decides both what MMHotline runs and what
  `util01` installs, so the two cannot disagree. Codex goes where
  MMHotline looks for it: the release package unpacks to
  `/usr/local/lib/codex/releases/<version>`, with `codex`,
  `codex-code-mode-host`, and `rg` linked in `/usr/local/bin`; an earlier
  version is deleted once the links move, because an unpacked package
  takes about 520 MB. Claude Code stays installed with either choice: its
  package updates itself with the security updates and costs nothing while
  unused, and removing it would bring no protection, because the triage
  agent runs only the program MMHotline's settings name. A Codex review
  agent beside a Claude Code triage agent comes in a later version
  (SKILL.md, "Not in this version's template yet").

- **The apt refresh stamp is managed on every server.** Before the first
  role package operation, `every_server` writes
  `/etc/apt/apt.conf.d/15update-stamp` on Debian. The hook runs
  `touch /var/lib/apt/periodic/update-success-stamp 2>/dev/null || true`
  after a successful refresh. MMWatchdog's `apt_security_updates` reads
  that exact path. Debian does not write the stamp by default.
  The existing `20auto-upgrades` keeps the daily refresh enabled.
- **A program from a vendor's apt repository updates itself** with the
  security updates, on the servers outside the database pool, which run
  the vendors' programs. The reason: a patch must not wait for a person
  where a restart costs nothing. unattended-upgrades allows the vendors'
  origins, as the vendors' Release files name them:
  `origin=cloudsmith/caddy/stable,codename=any-version`,
  `origin=cloudflared,codename=any`, and `origin=Anthropic,codename=stable`.
  MMX installs each vendor apt package with `newest_when_first_installed`.
- **The vendors' signing keys are committed** as the vendors publish them:
  Caddy's in `roles/tunnel_connector_and_caddy/files/`, Cloudflare's in
  the project's `files_used_by_several_roles/`, because `roles/tunnel_connector_and_caddy` and
  `util01`'s role both install `cloudflared`, and Anthropic's in
  `roles/util_server/files/`.
- **A downloaded program is pinned** in `stack_software`, so every server
  runs the same version and a replacement server gets the version the
  others run. An update is a commit that changes the pin.
- MMHotline pushes the triage agent's commits only when the commits change
  nothing outside `one_time_playbooks/` and `triage_agent_notes/`.

### A Stack release pins its own programs

A released Stack version, the tag named by `stack_version` in the
template's checklist, holds a real release of every program in
`stack_software`: the version, the download address, and the SHA-256 from
that release's own checksum file. A team copies the pins with the template
and never fills one by hand. Between releases, `mmx`, `mmwatchdog` and
`set_up_outside_services` hold a SHA-256 of zeros. A run with such a pin
changes nothing. MMX checks every download of a run before the run starts,
so a zero pin of a program the playbook downloads stops the run with MMX's
"size or SHA-256 mismatch" (seen on real servers). For a pin
the playbook does not download, the first stage of `every_server`,
`refuse_programs_pinned_without_a_release`, and the first tasks of the desk
playbook refuse with a message that says the copy came from an unreleased
checkout. Reason: a pin filled by hand from a release page could name any
build, not the one the Stack was tested with.

The release step, in one commit that the tag then names:

1. Set `stack_version` in the template's checklist to the new version, such
   as `0.2.0`, whose tag is `v0.2.0`.
2. Pin the MMX, MMWatchdog and MMHotline releases the Stack was tested
   with, each from its release's `SHA256SUMS`. The MMX release must have:
   - `mmx mark-node-work-failed`, which the restore drill and
     `destroy_replaced_servers` call, recording the work of an older run
     whose saved ssh_config path no longer exists (otherwise such a run
     makes the drill's cleanup fail with exit 3);
   - durations that may be one whole reference to a var, which the reboot
     playbooks' come-back wait needs;
   - the rule of which node task results MMX hides, which the template's
     comments and `tests/task_outputs_after_a_secret_test.py` follow
     ("No schedule, name or path reads a hidden output" in
     [Secrets](#secrets));
   - the rule that a top-level fleet stage whose `when` is false on every
     server needs none of its secrets, which the one switch playbook of
     [moving a database in](#moving-an-existing-database-into-the-stack)
     needs. An earlier MMX asks a self-hosted move for the relay's
     password.
3. Run `set_up_outside_services/build_release_archive.sh VERSION
   OUTPUT_DIRECTORY` on Linux. It refuses a version other than
   `stack_version`, builds the archive, and writes the archive's version,
   address and SHA-256 into `stack_software.set_up_outside_services`.
4. Check that each pinned program's release is published at its own
   address, then tag the commit with the version and push the tag. A
   workflow in the Stack's repository builds the
   `set-up-outside-services` archive when a version tag is pushed, and
   attaches the archive to that tag's GitHub release, at the address
   step 3 wrote.

`tests/release_build_test.py` checks step 3 with stand-ins for the build
tools; `tests/pinned_program_releases_test.py` checks that every pin is
refused while it holds zeros. Each release is published on GitHub, under
`github.com/monkeymaxxing`, the addresses the template's pins follow.
`gitlab.com/monkeymaxxing` holds a public mirror of each repository, for
when GitHub is down.

### New releases of the pinned programs

MMWatchdog's check group `pinned_program_releases` on `util01` has one
shell check per program pinned in `stack_software` that the settings
install, `PROGRAM_pin_is_the_newest_release`, and one check
`release_sources_answer`. Each program's check asks GitHub's
`releases/latest` for the newest release and fails at warn when it is newer
than the pin, with a message that names the program, both versions, the
release's page, and the update procedure. The warning starts the triage
agent like any warning; `triage_agent_rules.md`, "A newer release of a
pinned program", has the agent read the release notes, judge the security
fixes, and hand over to a person with the new pin's values. The agent
never changes a pin: the pin is in `mmx_project_settings.yml`, outside the
folders the triage key may change. Reason (no agent without work): with the scheduled software review off, nothing else
would notice a new release of the Stack's own programs, and a plain
comparison needs no coding agent; the agent starts only when there is a
release to read.

- **The checks come from `stack_software`, not from
  `software_outside_the_distribution.yml`.** MMX templates cannot read
  another file of the project, and `stack_software` holds every downloaded
  program's pin and download address under the entry's name. The template
  repeats two install conditions of the roles: `codex` only while
  `triage_agent_coding_agent` is `codex`, and
  `rclone` only while `backups.uploads_backup_runs_on` is not empty, so a
  program the system does not install raises no warning. Programs from
  vendors' apt repositories update themselves and get no check. A pin whose
  `download_url` is not a GitHub release, such as Google's gcloud, gets a
  comment and no check; the scheduled software review covers it when the
  team turns it on. `tests/pinned_program_releases_test.py` checks that the
  real playbook gives one check per installed downloaded program.
- **Pre-releases never warn.** `releases/latest` leaves out pre-releases
  and drafts, and answers 404 for a project with only pre-releases, which
  counts as an answer with no release. A pin at a pre-release of
  MMHotline `0.1.0` warns once `0.1.0`, or any later release, is out. No list of skipped releases exists, so none was added.
- **A source that does not answer is not a new release.** A check tries 3
  times, 5 seconds apart, then passes. `release_sources_answer` asks every
  source again and fails when one still does not answer: a refused,
  rate-limited, or malformed answer, or no connection. It warns after 24
  hours. Reason: a source down for a day means the team no longer learns of
  that program's releases; a shorter outage changes nothing.
- **Once an hour.** GitHub allows 60 requests an hour from one address
  without a sign-in. Each program costs 2 requests an hour, so the
  template's 6 checked programs make 12 requests an hour, 48 under the
  limit; with Codex, 7 programs make 14. When every request fails and is
  tried 3 times, 7 programs make 42, still 18 under the limit. Each further
  pinned program adds 2, or 6 when every request fails. A release an hour
  late changes nothing.
- **One alert per release, until the pin moves.** MMWatchdog sends one
  alert for an incident, and the MMHotline destination takes no reminders,
  so a failing check stays one open warning. A later release while it is
  open sends no new alert. MMWatchdog has no way to quiet one release of
  one check (maintenance quiets the whole group, including the other
  programs), so a team that will not take a release leaves the warning
  open, and the weekly system review reads the newest release from the
  checks' output.

## Reboots

On Debian, unattended-upgrades' kernel hook writes
`/var/run/reboot-required` and `/var/run/reboot-required.pkgs` when a
kernel package is installed. The marker means a new kernel needs a
reboot. needrestart handles library and service restarts, which the
reboot marker does not cover. The playbooks keep reading the distribution's
marker.

The `every_server` role installs needrestart explicitly and writes the
existing restart policy. Services restart after library updates outside
the database pool. On database servers, needrestart lists services until
`update_database_servers` restarts the services in the weekly window.

needrestart never restarts a web container's unit (`APP-web-PORT.service`,
such as `shop-web-8001.service`), `caddy.service` or `cloudflared.service`
(`$nrconf{override_rc}` patterns in `roles/every_server/files/needrestart.conf`).
Reason: in a test on real servers, needrestart restarted
`shop-web-8001.service` in `install_the_waiting_security_updates_on_new_servers`
while that server was the only app server and serving: one failed request
and about 4 seconds down (Caddy marked the upstream down 02:00:28 to
02:00:33). What picks up the new libraries: the reboot the update asks for,
which follows the reboot paths, and the next deploy, which restarts the
containers. This is safe because a container's app uses the libraries of its
image; the restart would only refresh the host side, such as conmon. The jobs
containers still restart, since no request waits on them. The daily
unattended upgrades on running servers skip these restarts too. That is
right: with two or more app servers a restart is harmless, and the deploy and
the reboot pick the libraries up anyway.

No server reboots by itself: unattended-upgrades has
`Automatic-Reboot "false"`, and a person reboots each server whose updates
wait for a reboot (`/var/run/reboot-required`), one at a time, in the
team's weekly window:

1. `./server_management_scripts/run_mmx_on_util01 run update_database_servers`, which updates and reboots the
   database servers in its own order ([Database servers](#database-servers));
2. `./server_management_scripts/run_mmx_on_util01 run reboot_servers_after_updates`, on `util01` like every
   run, for every server but `util01` and the database servers:
   `staging01`, the app servers, the jobs servers, and the load-balancer
   servers;
3. `mmx run reboot_util01_after_updates`, from a
   systems desk.

Each playbook first reads which of its servers wait for a reboot, and
changes nothing on the others.

- **Why no server reboots by itself:** a reboot at an hour nobody chose
  surprises the team. Most fixes that wait for a reboot are the kernel's,
  and the flaws that such fixes close rarely reach the stack's servers.
  The internet reaches the stack's servers only through authenticated
  WireGuard and the Cloudflare tunnel. Cloudflare terminates the public HTTPS, so even a flaw in a
  server's TLS code, such as Heartbleed in OpenSSL, stops at Cloudflare.

  A rare fix that cannot wait a week is the triage agent's to raise as an
  SOS, with the reboot ready to approve. The triage agent raises the SOS
  only when attackers exploit the flaw now and the flaw reaches the
  stack's servers. The flaw can reach the servers from the internet or
  from inside an app's container (the template's [triage_agent_rules.md](../skills/monkeymaxxing-stack/systems_repository_template/triage_agent_rules.md#a-fix-that-waits-for-a-reboot), "A fix that waits for a
  reboot"). The triage agent never asks permission for an ordinary reboot,
  because MMHotline sends every request for permission as an SOS, which
  wakes the person on call.
- **One server at a time, and each server does its work again before the
  next server reboots,** so the other servers of the pool carry the
  rebooting server's work. The playbook waits, at most 5 minutes, for
  `check-that-this-server-does-its-work`, a root command that the
  `every_server` role installs on every server, with what it checks in
  `/etc/monkeymaxxing-stack/the_work_of_this_server.json`. What counts as
  doing the work again depends on the server:
  - On an app server, the live web containers answer the containers'
    health URLs, with the requests Caddy uses.
  - On a server running the tunnel connector, `cloudflared` is connected
    to Cloudflare (`http://127.0.0.1:20241/ready`), and each app answers
    through the rebooted server's Caddy. The checks match
    `tunnel_connector_and_caddy`'s checks before a new connector joins the
    tunnel.
  - On a jobs server, each app's job container runs.

  Reason for one command: the replacement playbooks need the same answer
  for a new server, so the checks live in one place instead of in inline
  waits of each playbook. Its 5 seconds per request follow the public site
  checks. The earlier inline waits waited up to 5 minutes for each kind of
  check in turn (2 minutes for the connector); one wait of 5 minutes for
  all of them bounds the reboot path, and the alert pause, by one number.
  A server whose install failed before the command was written has no
  command, which counts as not doing its work.

  A server that does not come back, or does not resume work, stops the run.
  With `app001` alone, the apps are down while it reboots: about 20
  seconds on a cloud VPS (16.6 seconds of errors on a test server), a few
  minutes on a dedicated server whose firmware checks run first.
- **Alert pauses: one server's planned work, no longer than the run waits
  for it.** Before each reboot, a whole-node MMWatchdog maintenance window,
  the alert pause, holds the server's own alerts, its reboot notice, and
  the fleet hub's alert that it stopped reporting. The run ends the pause
  the moment the server's work is confirmed. Each pause's `--for` is the
  longest time the run waits for that server, plus a small margin, never a
  round 30 minutes or an hour, so a run that fails or dies never leaves
  alerts paused longer than it would have waited, and no failure path is
  needed for that. `tests/alert_pauses_test.py` adds up each playbook's
  own waits and checks each pause against the sum.

  | Pause | Before | Now | The arithmetic |
  | --- | --- | --- | --- |
  | `reboot_servers_after_updates`, the rebooting server | 30m | 10m | the come-back wait 3m + `check-that-this-server-does-its-work` 5m + 2m |
  | `reboot_util01_after_updates`, `util01` but its public site checks | 30m | 10m | the come-back wait 3m + MMHotline and MMWatchdog 5m + 2m |
  | `switch_database_primary`, every database server | 15m | 22m + 1m for each app | the switchover's `time_limit` 20m + 60s for each app's answer + 2m |
  | `update_database_servers`, one database server's turn | 1h, until the end of the run | 75m, until the end of its own turn | pg_auto_failover node task 20m + 30s, twice, 41m + the updates about 15m + the restarts about 5m + the reboot 10m + 4m |
  | `update_database_servers`, every database server during the switchover | (inside the hour above) | 22m + 1m for each app | as `switch_database_primary` |
  | MMWatchdog's restart for a new release or settings (`mmwatchdog_joined_node`, `util_server`), not announced | 15m | 3m | the hub's acceptance 25s + systemd's start timeout 90s + the socket's 10s + margin |
  | `remove_server`, the server being removed | 1h | 1h, unchanged | the person's time to destroy the server after the run; the server is leaving, so nothing replaces its silence alert. Without `server_name` (the load's removal), the run's last stage destroys the server itself within its 30m limit; when that stage refuses, the server is put back in service by `every_server` and its own alerts wait at most the rest of the hour, while the other app servers' checks and the public site check still alert |
  | The one-time playbook of `fix_failed_database_write_ahead_log_archiving.md`, one database server at a time | 1h | 2m | the hub's acceptance 25s + a marking of seconds + margin |
  | The second app server's test in `add_an_app_server.md`, run by hand | 30m | 15m | the test takes about 5m; the rest is room for a dedicated server's boot |
  | A person's own pause while a harmful service is stopped by hand (`AGENTS.md`, "Never change a server by hand") | 24h | unchanged | a person's decision during an incident, not a run's |

  - **What MMX offers on failure, used where it is cheap:** a node task
    block's `on_failure` runs on the same node when an earlier phase of the
    block failed, and `cleanup` runs after it either way (MMX's usage
    guide, "Put things back when a node task block fails"). So the wait
    for the server's work, and the updates of a database server, sit in a
    block whose `cleanup` or `on_failure` ends the pause, and a `maintenance
    on` that the hub did not take (exit 1, the window on the server alone)
    ends again at once. What MMX does not offer: a `reboot` must be the
    last task of its fleet stage and never inside a block, a role cannot
    stand inside a block's phase, and a failed node starts none of its
    later fleet stages. MMWatchdog cannot end a node's window from the hub
    ("Maintenance affects only the node where the command runs. There is
    no fleet-wide maintenance command."). So a failed reboot, or a failed
    role on a database server, ends its pause through the short cap.
  - **A server that never comes back from its reboot:** MMX's reboot task
    fails after the come-back wait, 3 minutes, and the run stops. With
    `routine_fixes_and_server_work`, the triage agent requests
    `replace_failed_servers` as soon as the reboot run answers that it
    failed, without waiting for the pause to end. The playbook takes no
    variables and never replaces a silent server inside a whole-server
    window, so it tells this case from planned work by data `util01` has:
    the reboot playbook's window carries the reason
    `reboot_servers_after_updates: waits 3m for the server to come back`,
    which the fleet hub keeps from the node's last report as
    `report.maintenance.every_check_group.reason`. A server silent inside
    such a window counts as failed once its `last_report_received_at` is
    older than the wait named in the reason plus 2 minutes, so the reboot
    run's own wait has certainly ended; any other window still means
    "planned, never a target", so a server a person powers off for planned
    work, with a reason of their own, is never replaced. When the request
    comes a little earlier, `read_the_fleet_hub_for_server_replacement`
    waits out the rest, at most those 2 minutes, and reads the hub again.
    The wait is read from the reason, not a setting, so a window opened
    before a change of the wait is judged by the wait its run used. The
    reboot run and the replacement never overlap: the reboot run holds
    `util01`'s lock until its wait fails, and the triage agent's request
    comes after its answer. The pause ends 10 minutes after it began, and
    the fleet hub then sends the alert that the server stopped reporting
    (`node_reports/NODE`), the same trigger, which stays as the second
    path: a replacement already pushed makes the alert's server leave the
    inventory, and the hub closes it ("alert closed, maybe not fixed").
    Expected gain with a pool's only server, not yet measured: the
    replacement starts about 5 minutes earlier than at the pause's end
    (10 minutes against 3 plus 2).
  - **The come-back wait is one setting,
    `come_back_wait_after_a_reboot` in `mmx_project_settings.yml`,** which
    a server or a group overrides in the inventory, such as a dedicated
    server's `15m`. Both reboot playbooks read it: the `reboot` task's
    `wait_at_most` is one whole reference to the var (MMX resolves each server's value before the run and refuses a value
    that is no duration, naming the setting and where it is set), and the
    pause's `--for` and the window's reason come from the same value
    through the pause command's env, `$(( ${COME_BACK_WAIT%m} + 7 ))m`,
    because MMX takes no template function in a task's argument. So the
    setting is whole minutes, from 1m to 45m (MMHotline stops a run after
    one hour, and one server's turn takes the wait plus 5 minutes), which
    each reboot playbook checks on the server before its pause: MMX
    checks the value of `util01`'s reboot when the project
    loads, but not that of a reboot inside a `for_each_node` stage, such as
    an app server's. `tests/alert_pauses_test.py` computes the pause and
    the reason from the setting, for the default and for a server's own
    value, and checks they agree. The default is 3 minutes, measured: three reboots
    of a cloud app server at a real provider took 34, 54 and
    56 seconds from the reboot to the server answering and doing its work,
    and `util01` answered about 28 seconds after it stopped answering, three
    times; 3 minutes is the longest, 56 seconds, plus a clear margin. A
    dedicated server, which runs its firmware checks before it boots, needs
    more: its own value in the inventory, as the setting's comment shows.
    The database
    servers' reboot in `update_database_servers` keeps its own 10 minutes,
    inside that playbook's pause of a whole turn.
  - **The public site checks on `util01` are never paused**, by an app
    server's reboot, by `util01`'s own reboot, or by MMWatchdog's restart on
    `util01`. An app server's pause is on the rebooting server only. When a
    pool's only app server reboots for longer than the check's 30 seconds,
    the SOS waits `sos_waits_for_the_agent_minutes` (3 by default) for the
    triage agent and resolves without waking anyone when the site answers
    again; only a real failure wakes a person. On `util01`, the program
    `util01-alert-pause` (`roles/util_server/files/`) opens the pause on
    every check group the running MMWatchdog has, and on `node_reports`, by
    name, but never on `public_sites`. MMWatchdog offers a window on every
    check group (`--every-check-group`) or on named check groups, and no
    window on every check group but some; on the hub, the whole-node window
    includes `node_reports`, so naming it keeps the hub's stopped-reporting
    alerts held as before. The names come from `mmwatchdog status --json`,
    because `maintenance on` refuses a name the running MMWatchdog does not
    know. The cost, accepted: only a whole-node window holds back a node's
    reboot notice, so `util01`'s reboot sends its notice (warn), and the
    triage agent reads it as planned when the window's reason names
    `reboot_util01_after_updates`. The gain: a site that stops answering
    during `util01`'s reboot, or while a run that died leaves `util01`'s
    pause open for up to 10 minutes, still raises its SOS.
  - **Releases do not pause alerts:** `deploy` opens no maintenance window.
    A deploy keeps the old release serving until the new one answers its
    health check, so its alerts mean a real fault.
  - **The hub has the window before the reboot:** MMWatchdog's
    `maintenance on` returns only once the hub has taken the maintenance
    window, and exits with 1 when the hub doesn't within 25 seconds,
    which stops the run before the reboot. If only the server knew about
    the window, the server would send the window settings to the hub with
    the next report, after the reboot. So the hub would count the
    rebooting server as silent.
  - **The join goes on without the hub:** `mmwatchdog_joined_node`
    accepts exit status 1 of `maintenance on` before MMWatchdog's own
    restart, which takes seconds. The reason: the join must also work
    while the hub is down. The join must also work after `util01` was
    rebuilt, when only the join gives a server the new hub's join code. The join code holds the
    hub's address, certificate fingerprint, and join secret.
  - **`util01` is the hub,** so its window holds only its own alerts; its
    hub-outage alerters alert when it isn't back within 2 minutes
    (`alert_after_hub_unreachable_for`; three real `util01` reboots left the
    hub unreachable for 27, 22 and 21 seconds).
- **`util01`'s reboot is a playbook of its own, run from a systems desk,**
  because MMX never reboots the machine running MMX. A fleet stage that
  ends with a reboot of MMX's own machine fails before the stage's first
  task. So adding `util01`'s reboot to `reboot_servers_after_updates`,
  which runs on `util01`, would make every run of
  `reboot_servers_after_updates` fail.

  While a run holds `util01`'s lock, the desk's
  `reboot_util01_after_updates` run stops before changing anything.
  So the reboot cuts no deploy, fix, or restore drill short. The person
  runs `reboot_util01_after_updates` again later.

  `reboot_util01_after_updates` does not wait for `util01`'s lock because
  MMX runs one job at a time on a server. A desk's job waiting on
  `util01` would make `util01`'s own runs fail on `util01` as busy.
  Reboots of servers other than `util01` stay in the playbook running on
  `util01`, so the runs take `util01`'s lock like every run. Taking
  `util01`'s lock prevents a reboot run from racing a deploy, which a
  desk's run could do.
- **When a reboot may run, one rule in one program:**
  `check-whether-a-reboot-may-run-now`, a Python 3 program that the
  `every_server` role installs on every server, decides it, and both
  `reboot_servers_after_updates` and MMWatchdog's check
  `no_reboot_waits_that_may_run_now` run it, so the check that starts the
  triage agent and the playbook that reboots cannot disagree. A reboot may
  run now when another server of the pool carries the work (two servers or
  more), on a jobs server (jobs wait in the queue about 20 seconds), on
  `staging01`, before go-live (`public_site_checks_run: false`), when a
  person passes `reboot_the_only_server_of_a_pool_outside_the_maintenance_window=true`
  on the command line, or inside the weekly maintenance window. The
  server's pool is the inventory group that holds it, so a pool the team
  added follows the same rule. The window's arithmetic counts minutes since
  monday 00:00 UTC, modulo one week, so a window across midnight or from
  sunday into monday needs no special case; `tests/reboots_that_may_run_now_test.py`
  runs the program for those edges.
  - **Enforced in the playbook, not the rules text:** the triage agent's
    rules are advice, and MMHotline judges a playbook by its tasks. The run
    also starts only after MMHotline's warning has waited, when the clock
    may have left the window. A server that waits is skipped, not failed,
    and a `show` task prints "app001 waits for the maintenance window:
    tuesday 2026-11-17 21:00 UTC, for 60 minutes; ...", which the triage
    agent copies into its report.
  - **Decided once, when the run starts,** on each server's own clock.
    Only a pool's only server needs the window, and the servers reboot one
    at a time, each in under 15 minutes, so such a server starts at most
    one reboot's time after the decision.
  - **`maintenance_window.length_minutes` from 30 to 1440,** 60 by default,
    checked by `every_server` before anything changes. 30 minutes hold the
    check's 10 minutes, about a minute for the triage agent, MMHotline's
    warning (10 minutes by default) and the reboot. One day is the most:
    a longer window is no longer a quiet time the team chose.
  - **The trigger exists only with `routine_fixes_and_server_work`:** the
    check group `reboots_that_may_run_now` in `mmwatchdog_checks/every_server.yml`
    is rendered only then, and only on the servers the playbook reboots:
    never on a database server, `util01` or a systems desk. Without it no
    alert, so no coding agent starts for a reboot only a person may run.
    It alerts at warn, because MMHotline starts a triage session for warn
    and SOS alerts and never for info; a warn wakes nobody. It runs every
    minute, because a 60-minute window must be seen at once, and alerts
    after 10 minutes, so unattended-upgrades finishes its batch first. Its
    own check group: `security_updates` runs every hour. After a person's
    Stop the check stays failing, so no new alert comes, and the weekly
    review lists the reboot that waits.
  - **`util01` is unchanged:** MMX never reboots the machine it runs on,
    so `reboot_util01_after_updates` stays a person's run from a desk.
- **The warning waits a week:** `no_reboot_waits` states its own
  `alert_after_failing_for: 8d` on every server, so a reboot that waits for
  the next window never warns, and one that a window missed does.
  MMWatchdog counts the 8 days again when its daemon starts and when a
  maintenance window starts or ends, so a missed window can warn later;
  the weekly review still catches it, because the window's checklist item
  is open again every 7 days. `known_exploited_flaws` reports a flaw that
  attackers exploit in the running kernel without waiting for the
  eight-day reboot warning. The check fails for the running kernel until
  the server boots the fixed kernel. CISA, the US cybersecurity agency,
  keeps a list of known exploited vulnerabilities. `known_exploited_flaws`
  finds a new entry in CISA's list of known exploited vulnerabilities
  within about 12 hours.

## Memory for both releases

A deploy starts the new release's web containers beside the live release's
web containers. For a minute or two, each app server runs the live and new
releases' web containers together. The app servers' memory warning at 75%
does not ensure enough memory for the additional web containers. For
example, on an 8 GB server, web containers using 4.5 GB and everything else
using 1 GB never trigger the memory warning. But the server has about 2 GB
available for another 4.5 GB of web containers.

So `deploy` checks each server of the environment before changing anything,
in the stage `check_that_each_app_server_has_memory_for_the_new_release`.
The memory check follows finding the live web containers and comes before
the pull and the migrations:

- **The memory check measures available memory and the live web
  containers' memory use, then calculates a reserve.** The stage installs
  `roles/app_server/files/check_memory_for_the_new_release`, just as the
  deploy's first stage installs `find_live_web_ports`, so servers never
  run an older copy of either helper.
  - Available memory is `MemAvailable` from `/proc/meminfo`.
  - Each live web container's memory use comes from the container's
    systemd unit's cgroup: `memory.current` less `inactive_file`.
    `inactive_file` is the file cache the kernel takes back first, already
    counted as available by `MemAvailable`.
  - The reserve is a tenth of the server's `MemTotal`. The reserve leaves
    room for new containers warming up, job containers, and Postgres on
    `staging01`. The reserve also leaves room for the page cache of
    programs' own code. Without memory for the code cache, a server slows
    to a crawl before the kernel kills anything.

  Available memory must cover the live web containers' combined memory
  use once more, plus the reserve of a tenth of `MemTotal`.
- **A server without memory for the additional web containers and the
  reserve stops the run**
  (`on_node_failure: stop_run`), before any pull or migration. The failure
  names the operating procedure: a bigger server, or a smaller
  `WEB_CONCURRENCY` for the app; another app server does not fix the check
  ([Memory for both releases](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/deploy_and_roll_back_an_app_release.md#memory-for-both-releases)).
  The stage's outputs give each server's numbers for the deploy's
  verification.
- **`deploy`'s command-line variable `skip_the_memory_check` disables the
  memory check,** for one case: rollback of a release that leaks memory.
  The leaking release's live containers use more memory than the previous
  release will need, so the memory check would refuse the rollback.
  A person passes `skip_the_memory_check`. The automatic runs on `util01`
  never pass `skip_the_memory_check`.

## The main playbook

`playbooks/every_server.yml` runs, in order:

0. Two fleet stages for the load-balancer servers' setting,
   `tunnel_connector_and_caddy_run_only_on_the_load_balancer_servers`,
   which do nothing while the setting is `false`
   ([Load-balancer servers](#load-balancer-servers-a-later-step)).
1. `every_server` on production and staging at once (excluding `database_restore_servers` and `systems_desks`):
   its name, SSH, the firewall, the WireGuard network, updates, the
   triage user, and the MMWatchdog release.
2. `util_server`, because the failover monitor and MMWatchdog's fleet hub must
   exist before the servers other than `util01` register with the monitor
   and the hub.
   The monitor and hub listen on `util01`'s WireGuard address, which
   `every_server` set up. Then
   `read_the_mmwatchdog_fleet_hub_join_code` reads the hub's join code.
3. `mmhotline` on `util01`: Litestream and the backup's settings, the
   database's restore on a new `util01`, the settings file, and
   MMHotline's install. MMHotline starts before the database and app
   stages, so MMHotline receives alerts while the rest of the system is
   being built.
4. `mmwatchdog_joins_the_fleet_hub_before_the_roles`: each server that
   has joined the hub before joins it again, at once, with the join code
   read from `util01` during the run.
5. `database_server`, one server at a time, then on `staging01`, with
   staging's secrets and no backups. Once
   `pgbouncer_runs_in_front_of_postgres` is true, `pgbouncer` runs on one
   database server at a time, then on `staging01`.
6. `mmwatchdog_joins_the_fleet_hub_after_the_roles_on_the_database_servers`,
   for the database servers. Then
   `mmwatchdog_joins_the_fleet_hub_after_the_roles` runs on the app servers,
   jobs servers, and `staging01`. Each join stage runs on all selected
   servers at once. New servers join the hub in the join stages after the
   roles. Servers already joined in
   `mmwatchdog_joins_the_fleet_hub_before_the_roles` change nothing.

   A database server joins only after `database_server` passed on the
   database server. The load-balancer servers join after step 9. Across
   the join stages, every server except `util01` and `restore01` joins the
   hub.
7. `jobs_server` on the jobs servers, a later step, one server at a time,
   before the app servers' stage. So the run that takes the job containers
   off the app servers runs the jobs servers' stage first
   ([Jobs servers](#jobs-servers)).
8. `app_server`, one server at a time, after the databases that each app's
   health URL needs.
9. `tunnel_connector_and_caddy`, one server at a time, on the app servers
   until `tunnel_connector_and_caddy_run_only_on_the_load_balancer_servers`
   is true, and on the load-balancer servers. After the app servers'
   stage, so a connector
   that joins the tunnel for the first time, as on a new system, finds
   the apps answering through its Caddy. Then
   `mmwatchdog_joins_the_fleet_hub_after_the_roles_on_the_load_balancer_servers`,
   with `requires.same_node: [tunnel_connector_and_caddy]`.
10. `app_server` and `tunnel_connector_and_caddy` on `staging01`, with
    staging's tags, host names, tunnel, and secrets.
11. The uploads' copy on `util01`, while an app keeps uploads
    ([Uploaded files](#uploaded-files)).
12. `apply_the_mmhotline_settings` on `util01`: `mmhotline settings
    apply`, after `/etc/mmhotline/mmhotline_settings.yml` changed.
13. The restore drill's start, until one has passed on `util01`
    ([The weekly drill](#the-weekly-drill)).

**MMHotline is a stage of its own, just after `util01`'s stages, with its
node tasks in the playbook,** for two reasons:

- **MMHotline's settings template reads each vault key named in the
  template.** A role's template can read only the role's inputs.
  Every secret input requires a vault key on every run, even without a
  template section that uses the secret input.
  But chapter 7 (install everything on the production servers) configures the servers before chapter 8 (check that alerts reach your phone and backups restore) creates the status
  page's key.

  Rendering `mmhotline_settings.yml` from the playbook avoids requiring
  the status page's key before chapter 8 (check that alerts reach your phone and backups restore). A playbook's template reads
  `.secrets` directly, and `mmx secrets usage` lists each key at the
  template's line. A team can also add a sending service, such as Twilio,
  with the service's keys and settings section in one commit.
  Adding the service needs no new role input or corresponding line in the
  playbook.
- **A part that MMHotline refuses fails only the final settings stage.**
  `settings apply` refuses some changes for a while, by design: a new Pushover token
  while an emergency message is open, a person left out of `people` who
  owns a claimed incident, a new triage agent setup while a triage run is
  active. A refusal inside the `util_server` stage would keep `util01` out
  of every later stage, among them the one that reads the hub's join code,
  which every other server's MMWatchdog stages need. The separate
  `apply_the_mmhotline_settings` stage stays at the end: the other
  servers' work has run, `util01`'s run fails with MMHotline's reason, and
  the coding agent corrects the cause and reruns the settings apply. Only the restore
  drill's first start waits, until the settings stage passes.

The early install has everything it needs: `every_server` set up the
WireGuard address; `util_server` made the `mmhotline` user, group, and
home, installed the triage agent, and attempted the systems repository's
clone. The clone happens once a desk pushed `main` to the main copy on
`util01`, and root there accepts the SSH key of the `mmhotline` Linux
account. The alert listener needs no systems
repository clone, but the restore drill waits for the clone.
The `mmhotline` stage writes Litestream's backup settings and restores
MMHotline's own SQLite database before the install can start it, then
checks and writes `mmhotline_settings.yml` before the install, which
requires it. Neither the app databases nor the app containers are needed.

**The `apply_the_mmhotline_settings` stage runs separately and reads no
secret,** so MMHotline's failure reason reaches the MMX result, which the
person reads from the systems desk. MMX hides the result of every node task
that reads a secret.
Inside a role call or node task block, MMX also hides results of node
tasks that start after a secret-reading task that ran something on the
server, such as the `file` task `write_the_mmhotline_settings`; a read by
`set_vars`, `show` or `assert` hides no later node task. Each node task
records secret reads under the enclosing role call or block as a parent.
Such a read marks the parent, so later node tasks inside the marked parent
start marked.

A node task at a stage's top level has no role call or block as a parent.
So a top-level node task shows results even after a secret-reading task.
MMX's usage guide says ("Which node tasks have a hidden result"):
"A node task after the outermost role call or node task block is not hidden".
The `write_the_mmhotline_settings` task reads the vault to write
`/etc/mmhotline/mmhotline_settings.yml`. So in a block with the write, the
apply's reason went only to the file of hidden details on `util01`, which
only root reads.

MMHotline keeps every secret's value out of what `settings apply` prints,
so nothing needs hiding there. The check of the new file stays with the
write, and so does the check's reason. The reason: the check runs before
the new file replaces the installed `/etc/mmhotline/mmhotline_settings.yml`.

The `mmhotline settings apply` command tracks only
`/etc/mmhotline/mmhotline_settings.yml`, through
`only_when_tracked_inputs_changed`. The command is inside the
`mmhotline_settings_file` block, whose only additional node task is a
`file` task with no content. The `file` task writes nothing and reads no
secret. The `file` task makes `/etc/mmhotline/mmhotline_settings.yml` a
tracked input, hashed from the file's content on disk.
So `mmhotline settings apply` runs after
`/etc/mmhotline/mmhotline_settings.yml` changed, and again at each run
after a failed apply, and never otherwise.

The block's first run takes `/etc/mmhotline/mmhotline_settings.yml` as the
file is and applies nothing, as every new record does. On a new `util01`,
MMHotline applies `/etc/mmhotline/mmhotline_settings.yml` during startup,
with outside tests running in the background. No MMX run would see the
background tests' results.

So a task before `mmhotline_settings_file` runs `mmhotline settings apply`
once (`run_only_once_marker_file`). MMHotline runs one apply at a time, so the
explicit apply waits for the startup apply and retests each part that
failed. If a settings part still fails to apply, the run that builds
`util01` fails with MMHotline's reason, and the next attempt tries again.

MMHotline restarts itself for changes to settings that need a restart:
`web_url`, the listen addresses, and `cloudflare_access`. So the
`mmhotline` stage starts MMHotline outside any block's `activate` phase,
where a changed file restarts nothing. A block's `activate` phase runs the
tasks that make the block's changes take effect, such as a service
restart.

The hub sends alerts to MMHotline through a configured alert destination.
The hub's alert destination names the alert source
`mmwatchdog_fleet_hub` and reads the signing secret from the vault key
`mmhotline_signing_secret_of_the_fleet_hub`.
MMHotline's `mmhotline_settings.yml` lists
`mmhotline_signing_secret_of_the_fleet_hub` for the alert source.
The hub keeps and retries an alert while MMHotline starts. The hub no
longer waits through the database and app stages for the alert
destination to exist.

The triage agent's `listed_hosts` is empty, because MMHotline lists the
hosts of the programs' release and advisory pages itself, from
`software_outside_the_distribution.yml` in MMHotline's copy of the systems
repository. Adding a program to `software_outside_the_distribution.yml`
therefore adds access to the program's page hosts, without updating a
second host list.

Between steps 6 and 7, every Caddy that runs in production points at the
live web containers that the app servers recorded. Production's Caddy runs
on the app servers or the load-balancer servers. The pointing comes
before the app servers' stage removes any other web container
([Load-balancer servers](#load-balancer-servers-a-later-step)). On
`staging01`, which serves no customers, `tunnel_connector_and_caddy`
simply follows `app_server`.

Joining the hub has a separate role, `mmwatchdog_joined_node`, because the
hub is set up after `every_server`. MMX excludes a server that failed a
fleet stage from later stages. So previously joined servers rejoin before
role stages that can fail, and remain watched after a role failure.
Examples include an app whose new image fails to start, or a database
server whose database stage fails after `util01` was rebuilt.
Without the early join, the failed database server kept the old hub's
join code. The new hub never knew the database server, so the new hub
sent no alert when the database server was silent.

- **Two places, one role.** A server that has joined before (its
  `/etc/mmwatchdog/mmwatchdog_node_settings.yml` exists) joins before the
  roles. A new server joins after the database stages, because the new
  server's checks name what the server's roles set up. MMWatchdog's check
  of the settings on the server looks up each check's account, such as
  `postgres` for PgBouncer's check. The check refuses an account that does
  not exist yet. And a new database server's Postgres checks would warn while
  the server's database stage still copies the primary.

  A new load-balancer server joins after `tunnel_connector_and_caddy`
  because the `tunnel_connector_and_caddy` check group needs the connector
  and Caddy running. On test servers, a new pair that joined with the
  other servers in `mmwatchdog_joins_the_fleet_hub_after_the_roles` warned
  while the pair is being configured and verified.

  The join stages after the roles change nothing on servers already
  joined by `mmwatchdog_joins_the_fleet_hub_before_the_roles`.
  Together, the later join stages cover every server that joins the hub,
  without a `when`, so `mmx explain` renders MMWatchdog files in the later
  stages. The early join's `when` checks whether
  `/etc/mmwatchdog/mmwatchdog_node_settings.yml` exists on the server.
  But `mmx explain` cannot read a server.

  Two check group templates also need facts reported by servers during
  the run. `mmwatchdog_checks/app_servers.yml` reads each app server's
  network interfaces. `mmwatchdog_checks/database_servers.yml` reads each
  database server's disks, except on `staging01`.
  So `mmx explain` renders the app servers' and the database servers'
  check groups from no server, and renders the other check groups.
- **One rule for the join after the roles:** each server must finish
  every preceding role stage on the server before joining in a later
  join stage. MMX already excludes servers that failed a stage from later
  stages. But `on_node_failure: stop_fleet_stage` also prevents servers
  from starting a stage after another server fails the stage.
  A server prevented from starting did not fail the stage, so MMX allows
  the unstarted server into later stages.

  On test servers, a database server failed `database_server` before a
  new database server could start the stage. The new database server then
  joined before Postgres existed, and MMWatchdog warned about the missing
  `postgres` account. So database servers have a separate join stage with
  `requires.same_node: [database_server]`.
  The database-server join stage blocks servers prevented from starting
  `database_server`. The blocked servers join during the run that sets up
  the blocked servers.

  The database-server join stage cannot require the `pgbouncer` stages,
  because each PgBouncer stage's `when` skips every server until the
  PgBouncer setup step. A server skipped by `when` does not meet a stage
  requirement. So if an earlier failure prevents a new database server
  from starting `pgbouncer`, the new database server can still join.
  The server's PgBouncer checks then warn until the next run, as in the
  run that turns PgBouncer on. Each `staging01` stage selects only
  `staging01`, so only a failure on `staging01` holds back `staging01`.

  Using a `when` condition on a single join stage was rejected.
  The condition would read each database server's `database_server`
  outcome from `.fleet_stages`. Because `mmx explain` cannot know run
  outcomes, `mmx explain` would no longer render any database server's
  MMWatchdog files.
  MMX also requires a stage named in `requires.same_node` to select every
  server selected by the dependent stage. So a join stage for every server
  cannot require `database_server`, which selects only database servers.
- **A check group can come before its program** on a server that has
  joined before: the run that turns `pgbouncer_runs_in_front_of_postgres`
  on gives the database servers and `staging01` PgBouncer's checks before
  the `pgbouncer` stages install it, one server at a time. A server that
  gets PgBouncer more than about 3 minutes after the join can receive
  warnings before PgBouncer runs. The `pgbouncer/pgbouncer_answers` check
  fails, and MMWatchdog cannot check `pgbouncer/pgbouncer_runs` or
  `pgbouncer/pgbouncer_follows_postgres`. The checks recover once
  PgBouncer runs.

  The PgBouncer group warns after 2 minutes of failing, checked every
  minute and confirmed. A hung PgBouncer on test servers took 3 minutes 28
  seconds to reach the warning. On the test servers, PgBouncer came up in
  time everywhere, and nothing warned.

  PgBouncer installation warnings wake nobody and occur only in the run
  that turns `pgbouncer_runs_in_front_of_postgres` on. The template's
  [add_pgbouncer.md](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/add_pgbouncer.md#adding-pgbouncer)
  says installation warnings can occur (step 2).
  The apps' check groups always came before the apps' stages.
- **A server whose join failed** misses the `every_server` run's later
  role stages. A deploy, a playbook of its own, still reaches the server. `restore01` is in no stage: the
  restore drill sets it up by itself.

**The Stack starts without `staging01`.** The template's group
`staging_server` has `nodes: []`, and the inventory has no staging tags or
host names (`staging: {}`): each fleet stage of `every_server` that selects only
`staging_server` has `skip_when_no_nodes_are_selected: true`, and the
coding agent omits staging deploys. A run loads only the secrets of the
stages that select a server, so a system without `staging01` needs no
`staging_` key in the vault, although `mmx secrets usage` lists them as
not defined. Setup asks one question: the smallest system, or the fuller
one, which adds `staging01` and `app002` in chapter 7 (install everything
on the production servers) with
[Add staging01](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/add_staging01.md)
and [Add an app server](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/add_an_app_server.md),
the same procedures a team follows on a later day.
Reason: every staging part made the
setup longer for every team, while a team that wants staging gets it
from one procedure with no hand edits.
`deploy`'s stages select the environment's group, not `staging_server`
alone, and keep MMX's error for an empty selection: a production deploy
that selects no server is a mistake that must stop.

## Load-balancer servers, a later step

At about 20 app servers, or when the CPU or network that cloudflared and
Caddy use on the app servers becomes the limit, `lb01` and `lb02` take over
production's tunnel connector and Caddy from the app servers. The pair uses
the same tunnel as the app servers, with the same token: the connectors move, and Cloudflare and DNS
stay as they are. Cloudflare decides by itself how to split the requests
between the two connectors, and may send every request to one connector, so
each load-balancer server is sized to carry every request alone, and the
pair grows by getting bigger.

Load-balancer servers are a later step, not the default, because most
systems never need load-balancer servers. About 20 app servers, each scaled
up, with jobs servers and Cloudflare's cache taking work off the app
servers, is more than most companies ever need. Nor does the pair make a
small system more robust.

In routing tests on real servers, losing a
server that runs a tunnel connector cost a few seconds of errors for the
requests that Cloudflare was sending to the lost server's connector, until
Cloudflare noticed the lost connector. Without the pair, losing any app
server costs the few seconds of errors. With the pair, losing an app server costs
nothing, but losing either load-balancer server costs the few seconds of errors. So the
pair helps only with more than two app servers.

Cloudflare's own load
balancer isn't used either. In the routing tests, Cloudflare's load balancer
split requests in blocks of about 5 seconds, carried less load than Caddy,
and kept sending to a lost server until the load balancer's next health
check. On the Cloudflare plan tested, the health checks run a minute apart.
The operating procedure's steps are in the template's
[add_load_balancer_servers.md](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/add_load_balancer_servers.md#adding-load-balancer-servers),
"Adding load-balancer servers".

- **One role for the tunnel connector and Caddy,**
  `tunnel_connector_and_caddy`: the tunnel connector and Caddy, with their
  packages, Caddy's list of web containers, the tunnel's routes, and the
  connector's unit. The role runs on the app servers before the step, on
  the load-balancer servers, and on `staging01`. One Caddyfile and one
  `cloudflared_config.yml` serve the app servers, the load-balancer
  servers, and `staging01`, with the load-balancing policy `least_conn`,
  the health checks, `fail_duration`, and `lb_try_duration`. The two
  files' comments give the reasons for the policy and the settings. Every
  server's connector gives the connector's readiness at
  `127.0.0.1:20241/ready`.
- **One setting:** `tunnel_connector_and_caddy_run_only_on_the_load_balancer_servers`,
  production's only, because `staging01` runs every role on one server.
  The load-balancer servers run the connector and Caddy from the
  load-balancer servers' first configuration run on. The setting says whether the app
  servers still run the connector and Caddy.

  The group's servers alone cannot be the signal. `lb01` and `lb02` are in
  the inventory before the pair is configured and verified. And a deploy in
  between must still switch the app servers' Caddy.
- **Three commits, so users see nothing.** The server-creation and host-key commits, as
  "Add a server" describes, bring the pair up beside the app servers.
  Then the pair and the app servers both carry requests, and every deploy
  switches every Caddy. The third commit turns the setting on.

  The third commit's run takes the app servers' connectors out, in two
  fleet stages at the start of `every_server.yml`. Only then does the
  `every_server` stage stop the app servers' peering with each other. An
  app server whose connector still brings requests in sends some of the
  requests to the other app servers' web containers. Without the peering,
  the app server would serve all the requests from the app server's own
  web containers, and one connector could carry every request alone for
  the minutes of the run.

  A single commit for the pair's keys and the setting was rejected,
  because MMX runs the `every_server` stage first in every run. So the
  setting in the commit of the pair's keys would cut the app servers'
  peering minutes before the pair's connectors exist.
- **The guard.** An app server's connector leaves only once every
  load-balancer server passed `mmwatchdog check-now tunnel_connector_and_caddy`
  in the same run. The check passes when the load-balancer server's
  connector holds a connection to Cloudflare, and each app answers through
  the load-balancer server's Caddy. One definition of "carries the
  requests", the MMWatchdog check group `tunnel_connector_and_caddy`,
  serves the continuous check, the guard before an app server's connector
  leaves, and `remove_server`'s guard.

  The answer is the output of the fleet stage
  `check_that_the_load_balancer_servers_carry_the_requests`
  (`carries_the_requests`), not the stage's failure. MMX keeps a server
  that failed a fleet stage out of the rest of the run. But a load-balancer
  server must still get the server's updates while an app's health URL
  fails, as during a database failover. And a new load-balancer server,
  which has no MMWatchdog before configuration, must get set up.
  The check answers "doesn't carry the requests" when MMWatchdog isn't
  installed.

  An app server that fails the guard fails the guard's fleet stage. MMX
  then keeps the app server out of the later stages, so the app server
  keeps its peering too. The run fails and names the
  load-balancer server. The guard runs only while the app server's own
  `/etc/cloudflared/config.yml` exists. So once the setting is on, a
  load-balancer server that is down blocks nothing. An assert refuses the
  setting while `load_balancer_servers` is empty.
- **A server joins the tunnel only once each app answers through the
  server's Caddy** (the role waits before the server's connector's first
  start). The moment the server joins, Cloudflare may send the server every
  request. So `every_server`'s stage that sets the role up comes after the
  app servers' stage. On a new system, the app servers' stage starts the
  first web containers.
- **Every running Caddy follows the recorded ports first.** A stage of the
  role without the role's setup, `point_every_caddy_at_the_live_web_containers`,
  points every Caddy that runs at the live ports that the app servers
  recorded. The stage runs before the app servers' stage, which removes
  the web containers on the ports that aren't live. A deploy's switch of
  the Caddies can stop halfway, as when a load-balancer server reboots in
  the middle of the switch. A Caddy can then still send the Caddy's
  requests to the old ports. Without the stage, the old ports' containers
  would go first.
- **One server at a time** in `every_server`, so a change that restarts the
  connector, such as a new tunnel token, leaves the other servers bringing
  the requests in. A failure stops the stage before the stage reaches the
  next server. A dead server stops the stage too, so a dead load-balancer
  server leaves the inventory first ([replace_a_server.md](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/replace_a_server.md) in the template).
- **Deploys.** Step 5 of `playbooks/deploy.yml` is two fleet stages. The
  app servers record the new ports as the live ports, then every Caddy of
  the environment switches at once, through the role. The role changes
  Caddy only where Caddy runs (`path_exists: /etc/caddy/Caddyfile`). So an
  app server that kept the app server's connector after a failed guard
  still switches, and an app server behind the pair changes nothing.

  The recording comes first. When a Caddy fails to switch, the run stops
  at the switch (`on_node_failure: stop_run`) with the old and the new
  release running.
  The next `every_server` run then brings every Caddy to the recorded ports
  before the run's app servers' stage removes the web containers on the
  old ports. The switch selects `groups_that_run_caddy_of_environment`, so
  a staging deploy selects `staging01` alone and reaches no production
  server. `stop_the_old_release` requires the recording stage, not the
  switch, because a failed switch already stops the run.
- **`remove_server`:** an app server leaves every Caddy list, through the
  role, before the app server's containers stop. While only the
  load-balancer servers bring the requests in, a load-balancer server
  leaves the tunnel only once every other load-balancer server passes
  `mmwatchdog check-now tunnel_connector_and_caddy`. And `remove_server`
  refuses the last load-balancer server. Before the setting is on, the app
  servers bring the requests in too. On the way back, the first
  load-balancer server taken out stays in the inventory while the second
  load-balancer server leaves.
- **Checks** (`mmwatchdog_checks/load_balancer_servers.yml`): CPU above 70%
  and the network above 60% of the port warn, because each server may
  carry every request alone. So the limits keep the headroom that one
  server needs to carry every request. The limits' operating procedure is
  bigger load-balancer servers, each replaced in turn.

  The tunnel connector and Caddy checks warn, because the other
  load-balancer server carries the requests. And `util01`'s check of the
  public sites wakes a person when both load-balancer servers fail. A
  silent load-balancer server warns. Once only the pair brings the
  requests in, the hub raises the load-balancer servers' silence alerts to
  SOS while every load-balancer server is silent
  (`raise_to_sos_when_every_node_of_these_node_groups_is_silent`). The SOS
  comes beside the check of the public sites, so the alert names the
  servers that stopped. Before the setting is on, the app servers'
  connectors carry the requests too.

  A silent app server stays a warning, with no such raise: when the apps
  stop answering, the check of the public sites wakes a person. And a
  silent database server is an SOS already. The app servers' network check
  names two operating procedures: adding load-balancer servers, and, once
  the load-balancer servers bring the requests in, adding another app
  server. A new load-balancer server's check group arrives in the run
  before the server's connector does, so the new server may send one
  warning.
- **Back to the app servers,** when the move is undone or both
  load-balancer servers are lost. Setting
  `tunnel_connector_and_caddy_run_only_on_the_load_balancer_servers` back
  to `false` gives the app servers their peering again. Then,
  one server at a time after the app servers' stage, each app server gets
  Caddy and a connector on the same tunnel as the load-balancer servers.

## Two nearby locations, not a step yet

The stack covers one location. The database primary and `util01` stay in
the stack's one location, so losing the location stops the site. In routing
tests on real servers, one pool of app servers split between two data centers
about 150 km apart, with a 3 ms round trip between them, worked without
changes. Each server ran its own tunnel connector, and every Caddy listed
every app server. Cloudflare split visitors between the two locations
differently for each Cloudflare data center. Losing one location cost a few
seconds of errors, only for the requests at the lost location's connectors.
So app servers in a second nearby location protect against losing the
second location, but not against losing the first location. The test had no
database: a second location protects the whole site only once the database
and `util01` can also keep running in the second location.

## Restore drill and recovery

`playbooks/restore_database.yml` restores production's whole Postgres
cluster, including every app's database, from the B2 bucket onto one
server with MMX's `pgbackrest_restore`. Then the playbook runs each app's
`restore_drill_check_queries` on the restored copy, read-only. Each query
must answer true. The server is in `database_restore_servers`, which
`every_server` and every other playbook skip, so no run touches the server
while the server receives the restore.

`staging01` keeps no backups, so its replacement gets its data from the
seed command, not from a restore
([Database servers](#database-servers), "`staging01` keeps no backups"). The restore
playbook's variables:

| Variable | Value |
| --- | --- |
| `restore_mode` | `copy_on_restore01`: a copy outside pg_auto_failover's `production` formation, for the weekly drill and for recovering rows lost to a bad change. `recovery`: the first new database server after every database server is lost. |
| `server_name` | `restore01` for a copy; for a recovery, the new database server's name, such as `db03`, which it keeps when it joins |
| `recover_to` | `latest`, or a time with its time zone, such as `"2026-11-03 14:01:00+00"` |
| `read_backup_bucket_as_of` | the moment whose bucket contents pgBackRest reads: the start of the restore, or a time before anything could have changed the bucket |

- **The restore playbook refuses a server that does not fit `restore_mode`.**
  `copy_on_restore01` requires `restore01` in `database_restore_servers`.
  `recovery` requires the new database server in `database_restore_servers`,
  with a name other than `restore01`.

  The playbook also refuses a recovery while the failover monitor reports
  a node of `production` healthy, or while any server still in
  `database_servers` answers as a running Postgres: `util01` asks each one
  with `pg_isready` on its WireGuard address, port 5432, with a five-second
  limit. Production may still run then, and a second primary from the
  backups would split the data. A server that does not answer counts as
  lost. Reason for asking the servers too: after a rebuild of `util01` the
  monitor knows no database server, so the monitor alone would pass beside
  an old primary that still runs. A server unreachable from the new
  `util01`, such as at a lost location whose WireGuard still names the old
  `util01`, counts as lost; powering such a server off stays the
  procedure's step.
  `pgbackrest_restore` refuses a data directory that holds anything, so a
  restore never writes over a database,
  and a rerun finds its completed restore and changes nothing. A copy and a
  recovery delete nothing themselves, so their reruns need no guard.
- **A copy or recovery server gets only what a restore needs.** The
  playbook installs Postgres and pgBackRest from Debian, without creating
  a cluster. The firewall admits only SSH on `wg0`, from `util01` and the
  systems desks' block, and public UDP 51820,
  because the restored copy holds every customer's data. The desks' rule
  lets the desk that keeps access run a recovery during a lock-out, when
  `util01` has lost admission; without the rule, MMX's ufw module refuses
  the change from a desk because the rules would block the desk's own SSH. The playbook writes pgBackRest's
  settings from the shared template, with the key that can only read the
  production bucket. The copy or recovery server uses SSH over WireGuard
  (`connection: ssh_only`) and peers only with `util01` during the restore.
- **A copy or recovery uses the database servers' data directory,**
  `/var/lib/postgresql/17/pg_auto_failover_node`, because pg_autoctl's
  settings in the restored files name their paths.
- **`read_backup_bucket_as_of` is always given.** The bucket keeps every
  version of its files under Object Lock, so pgBackRest reading it as it
  stood at a time ignores whatever an attacker deleted or overwrote later.
  The weekly drill gives `read_backup_bucket_as_of` too, so the drill tests
  the way a recovery after an attack reads the bucket.

### The weekly drill

`weekly_database_restore_drill.service` starts an MMX playbook on `weekly_work_day`, two hours after
`nightly_work_starts_at` (Sunday 03:00 UTC in the template). The timer runs only the trusted commit ([MMHotline decides which commit is trusted](#mmhotline-decides-which-commit-is-trusted)) under the same lock as the systems desk helper and
runs `mmx run weekly_database_restore_drill`. The playbook uses the team's
provider scripts and a temporary project copy outside Git. A standard
six-hour timeout sends SIGTERM to the Bash drill, whose traps clean up.
MMX task time limits are disabled for the drill because MMX uses SIGKILL,
which cannot run cleanup.

1. Refuse an existing `restore01` at the provider, an inventory node named
   `restore01`, or a member of `database_restore_servers`.
2. Record the drill start time. Generate `restore01`'s WireGuard key pair,
   render first-boot data with only the `util01` peer, and add the temporary
   runtime peer on `util01` through root SSH in the MMX drill. Create
   `restore01` with the database servers' size, location, image, and
   registered utility-server SSH key. The provider create script records
   the created server's immutable ID in an ownership file before waiting
   for provisioning. Remove the rendered private data after submission.
3. Accept the SSH host key only through the authenticated WireGuard peer.
   No SSH host key is read from a provider response.
4. Clone the pushed project into a temporary directory. Add `restore01`
   and the verified host key only in the temporary copy. Run
   `restore_database` with `restore_mode=copy_on_restore01`, `recover_to=latest`, and
   `read_backup_bucket_as_of` set to the drill start. Every app's check query
   must answer true.
5. Read the restore outputs: elapsed seconds until the queries answered,
   the newest replayed transaction, and the maximum seconds of missing
   writes. No replayed transaction means the write-age measurement is
   unavailable; the result says so. Compare one eligible uploaded file per
   app byte for byte with the frozen B2 backup, using `rclone check
   --download`; use files unchanged since the last passed uploads copy.
6. After success, failure, or a handled stop, remove the runtime peer
   through root SSH and destroy only the server ID in
   the ownership file. Remove the temporary project and host keys only
   after destruction succeeds. A destruction failure preserves the receipt
   and temporary inventory for recovery. Write `latest_result.json`; write
   `latest_passed_drill` only after every check and cleanup passes.

Reason: a permanent `restore01` inventory entry would expose a placeholder
address to ordinary runs and conflict with manual recovery. MMX selects
inventories by name inside a project, so a temporary project copy provides
an isolated inventory without extending MMX. The production inventory
stays unchanged. The provider receipt prevents deletion of a server the
drill did not create. WireGuard authenticates the SSH host key before production backup data
moves. The drill uses the inventory's `vars.restore01_private_ip` for `restore01`, stores the public key in
the attempt directory, and removes the runtime peer on failure as well as
success. Root SSH avoids a nested MMX job targeting `util01`, because the
outer drill holds the node lock. A temporary `every_server` run on `util01` was rejected because
rewriting the utility role would change unrelated settings for one peer.

The marker files live in `/var/lib/restore_drill/`. MMWatchdog reads
`latest_passed_drill` and warns after eight days without a passed drill.
The failed service also warns through the existing systemd check. The
journal holds progress and failures. The coding agent records measured
results in the checklist after reading the marker and journal; no scheduled
job edits or commits the checklist.

The first or rebuilt-system `every_server` run starts the drill in the
background until a drill passes. The drill waits for an active uploads copy
and for the shared MMX lock. A stop requests MMX to finish the current task
and cleanup; an abrupt server loss can leave a server, so the daily
`check_for_a_leftover_restore01` job compares the provider listing and the
inventory and fails while a restore server remains. The next drill refuses
the leftover.

The duration measures database recovery, including server creation and
check queries, rather than recovery of the whole site. The write-age
measurement is an upper bound on a quiet database. Restoring `latest` from
the archive frozen at drill start measures exposure to lost writes; a
point-in-time target cannot measure writes beyond the available archive.

#### The drill gives way to MMHotline

An outage's fix must not wait for a drill. MMHotline keeps
`/var/lib/mmhotline/systems_repository.lock.waiting` while it waits for
the lock, rewritten every second, removed when the wait ends, and its wait
counts toward its MMX run's one-hour limit. The drill checks for the
marker once before it creates anything and then, from a background
watcher, every 5 seconds. When MMHotline rewrote the marker since the
previous check, the drill records the marker's line, ends itself with
TERM, destroys `restore01` by its receipt's ID first, stops its inner
`restore_database` run with `mmx stop` (exit 3 is expected, see below),
ends the inner `mmx run` process at once (TERM, then KILL after 10 seconds
if it remains: on test servers it took 80 seconds from the waiting marker to a free
lock with a 30 second wait before, and KILL was always needed), records `restore01`'s work as failed with
`mmx mark-node-work-failed --node restore01 --json`, removes the runtime
peer, writes `latest_result.json` with `"passed": false` and `gave_way_to`,
and exits 75. The scheduled service
reads that result, exits 75 too, and the drop-in
`RestartForceExitStatus=75`, `RestartSec=2h` runs the drill again.

- **Ending, not releasing the lock.** The drill's outer MMX job holds
  `util01`'s node job for the whole drill, so a waiting `every_server`
  would be refused as busy, and `every_server` sets `util01`'s WireGuard
  peers from the inventory and would remove the drill's runtime peer.
- **Destroying first.** The lock must be free as soon as MMHotline's wait
  no longer needs to wait for the drill, so the drill keeps its order:
  destroy, then stop, wait, mark. Stopping first and waiting for
  `restore01`'s acknowledgement before the destroy would keep the lock
  longer and leave a clean history; the drill takes the faster lock and
  records the destroyed server's work after the fact. (Without the end of
  the inner `mmx run`, MMX's `mmx run` stays `stopping` with 1 unconfirmed
  work, and the lock took 95.4 seconds on test servers, 60 of them in a
  wait the destroy never ended.)
- **What `mmx stop` and `mmx mark-node-work-failed` do** (the MMX release
  that `stack_software.mmx` pins).
  `mmx stop` writes a stop marker that the running `mmx run` picks up,
  contacts each node with unconfirmed work once (SSH `ConnectTimeout` 10
  seconds) and returns; it does not wait for the `mmx run` process. It
  exits 3 when work is still unconfirmed, 0 when nothing is, 4 for a command
  error. A destroyed server never answers, so after the destroy exit 3 is
  the expected answer, and the run stays `stopping` with 1 unconfirmed until
  `mmx mark-node-work-failed --node restore01 --json` records the work as
  failed ("the team says this server is gone; MMX could not reach it").
  That command tries every run of the node, always prints `runs` and
  `runs_not_recorded` with `--json`, and exits with the most serious outcome:
  0 when it recorded the work or none was unconfirmed;
  2 when MMX reached the server; 3 when it could not tell; 4 for a command
  error, including a run whose own `mmx run` process still holds it, which
  is why the drill ends that process (TERM at once, then KILL after 10 seconds)
  first. The drill treats 2, 3 and 4 as a failed cleanup, never 75.
- **Every MMHotline waiter counts, short holds included.** While the drill
  holds the lock, a short hold, such as the fetch that starts a triage
  agent run, waits as long as an MMX run, so waiting some seconds before
  giving way would tell nothing apart. To keep busy nights from ending
  every drill, `util01`'s scheduled jobs never make MMHotline wait:
  `check_new_commits_on_main` asks nothing while the lock is held, and the
  comparison and the leftover check wait for a free lock before they ask
  MMHotline. A person's `run_mmx_on_util01` asks MMHotline first, so it
  ends a drill too, which is what the person wants.
- **A marker MMHotline stopped rewriting is ignored.** A marker left by an
  MMHotline that stopped during a wait would otherwise end every drill.
- **Time to a free lock.** The provider's destroy plus about 30 to 40
  seconds (`mmx stop` at most 10 seconds, the inner process about 5,
  `mmx mark-node-work-failed` at most 10), an estimate until the next run
  on real servers measures it, and at most about 60 seconds more when the
  inner process ignores the stop; when the drill was in the create script's
  wait for boot, about a minute more, because Bash runs a trap after the
  running command.
- **systemd.** `RestartForceExitStatus=` restarts whatever `Restart=`
  says, and a `Type=oneshot` unit may use it; the unit keeps `Restart=no`,
  so a failed drill is not repeated. During `RestartSec` the unit is
  `activating (auto-restart)`, never `failed`, so the failed-unit check is
  quiet. A start during the wait, by the weekly timer or a person, starts
  the drill at once in place of the waiting restart (systemd v257
  `service_start()`), so the drill never runs twice; `systemctl stop`
  cancels the waiting restart. 2 hours, fixed: a replacement and its
  follow-up runs end within an hour. `restore_drill`'s 8 days hold one
  delayed drill; a drill that gives way every time still warns.
- **A failed cleanup is a failure.** When the destroy fails, or
  `mmx mark-node-work-failed` exits 2, 3 or 4, or `mmx stop` exits other
  than 0 or 3, the result keeps `gave_way_to` and `attempt_dir` (and
  `cleanup_failure_reason`), the service fails, and nothing runs again: the
  next drill would refuse the leftover anyway. The unit turns a result into
  exit 75 only when it has `gave_way_to` and no `attempt_dir`. Reason: a
  unit that turned every result with `gave_way_to` into 75 would start a
  drill whose cleanup failed again two hours later.

### Rows lost to a bad change

`playbooks/recover_rows_from_a_restored_copy.yml` copies rows that a bad
change deleted back to the primary from a copy restored to the minute
before the change, and keeps every later change
([recover_rows_lost_to_a_bad_change.md](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/recover_rows_lost_to_a_bad_change.md)).
When much of the database is wrong, the whole database goes back instead
([Every database server is lost](#every-database-server-is-lost), with a
chosen `recover_to`).

- **Each run is whole, like the drill.** One task on `util01` creates
  `restore01`, adds it only to a throwaway clone of `util01`'s copy with
  its host key, runs `restore_database` with `copy_on_restore01` there,
  copies the rows, and destroys `restore01`, also after a failure. The
  shared steps are in `steps_for_a_server_this_run_creates.bash`. Reason:
  `restore01` in `util01`'s own copy made the helper refuse every later
  run, and desks cannot reach `restore01`. Keeping `restore01` between runs
  would need saved state on `util01`, and any `every_server` run in between
  removes its runtime peer. The cost is a restore in each run: 3 to 5
  minutes in drills on test servers.
- **A preview, then the real run.** The values are command-line variables:
  the database, the table, an SQL condition for the lost rows, and what
  happens to a row whose primary key the primary holds (`skip_the_row`, an
  `ON CONFLICT ON CONSTRAINT` on the primary key, or `change_nothing`, a
  plain insert that ends the transaction). The preview runs the same
  transaction and rolls it back, so its counts are what the real run does;
  the same `recover_to` and `read_backup_bucket_as_of` restore the same copy.
- **The rows pass `util01` only in a pipe.** `COPY ... TO STDOUT` in a
  read-only transaction on `restore01`, through `util01`'s shell, into one
  transaction on the primary that the failover monitor names. A failed copy
  ends the pipe before `COMMIT`. psql runs with `VERBOSITY terse`, and the
  run prints only counts, so no row reaches a file, Git, a desk or MMX's
  history.
- **Not proved on real servers yet:** a test run must show the preview and
  the real run against a real backup, util01's copy clean, and no
  `restore01` or runtime peer left.

### Every database server is lost

The first new database server goes through the weekly drill's restore,
`restore_database`, so the way a recovery restores is tested every week.
Then the new server joins the formation through `util01`'s normal
`every_server` runs:

1. Create the new database server, such as `db03`, and put the new server
   in `database_restore_servers`, with `connection: ssh_only`. Remove nothing
   from the inventory yet. Commit and push. Keeping `db03` in
   `database_restore_servers` prevents `every_server`'s `database_server` stage
   from making `db03` an empty primary before the restore.
2. `./server_management_scripts/run_mmx_on_util01 run restore_database --var restore_mode=recovery --var server_name=db03 --var recover_to=latest --var read_backup_bucket_as_of=NOW`.
   The restored cluster stays as pgBackRest left the cluster, with
   `archive_mode` off in `postgresql.auto.conf`, which wins over
   `postgresql.conf`. The run resets the `archive_mode` setting, so the
   database servers' `archive_mode = on` takes effect at the cluster's next
   start.
3. Move `db03` to `database_servers`, with its `https_address`,
   `private_ip`, and the first-boot WireGuard key, and delete the lost servers
   from the inventory and `ssh/known_hosts`. Commit, push, and run `every_server` on `util01`: the
   run drops the lost nodes from the formation and adds the role peers.
   MMX registers the restored cluster as the formation's primary through
   `pg_auto_failover_node`, using
   `/var/lib/postgresql/17/pg_auto_failover_node`, where the restore placed
   the data. The module makes the restored cluster the primary when the
   formation has no node. Starting the restored cluster turns archiving
   on into production's stanza `main`, and the app servers'
   `DATABASE_URL` names `db03`.
4. Verify the restored primary, app queries, and backup archiving before
   creating replicas. No later WireGuard-key commit is needed.
5. New database servers besides `db03` join as replicas, each as
   [add_a_second_database_server.md](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/add_a_second_database_server.md)
   describes.

The bucket gets only one database history, for two reasons. The restored
cluster archives nothing until the restored cluster is the formation's
primary. And the restore playbook refuses a recovery while any production
node is healthy.

After a break-in that changed the database, the same steps restore the
database to a chosen time, `recover_to` a minute before the first known
access, from the desk that keeps access
([recover_when_every_database_server_is_lost.md](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/recover_when_every_database_server_is_lost.md),
"Bring the whole database back to a chosen minute"). The order follows
from the refusals: the person decides before `util01` is rebuilt, because
the rebuild's steps 5 and 6 would register the old database servers with
the new monitor; the old database servers are snapshotted for evidence and
powered off, because the restore refuses while one answers on port 5432.
"Replace a server" is not used for the database, because it copies the
running database with the intruder's changes. `read_backup_bucket_as_of`
is the restore's start time unless the intruder may have reached a
database server or a B2 key; then it is the time of that access, and
`recover_to` lies at least 3 minutes before it, because `archive_timeout`
sends the newest changes to the bucket about once a minute.

## Account and secret setup from the systems desk

The person makes the accounts, approves the costs, and enters a secret only
where a service offers no other way. One Stack command does the rest of the
account and secret work: `set-up-outside-services`, a Go program in the
Stack repository's `set_up_outside_services/`. The desk role installs it on
every systems desk from its pin, `stack_software.set_up_outside_services`.
The person runs it in their own desk login, each command through one short
entry on the laptop, such as `ssh desk01-setup` for `go-live` and
`ssh desk01-secrets` for `secrets`, or `ssh -t desk01 set-up-outside-services
COMMAND`. The person keeps no checkout on the desk. `go-live` works in the desk's one working copy,
the coding agent's checkout `/home/coding-agent/systems_repository`, which
the person's account reaches only through `sudo -n`. It runs MMX as root,
which opens the vault with the desk's `/etc/systems-desk/vault-passphrase`
and gives each vault file it writes back to `coding-agent`, and it runs Git
as `coding-agent` with the production key's relay socket, so each push
reaches the main copy and every file stays the coding agent's own. The recovery bundle
gets the vault passphrase through `sudo -n cat`, on MMX's standard input.
Reason: the passphrase never passes through a process of `coding-agent`'s,
which the coding agent could read, and never through a file in the
person's home.

| Command | What it does |
| --- | --- |
| `set-up-outside-services go-live` | The first part of the setup, on the desk, one screen at a time in the four-part form: Cloudflare (the link token; it finds the account, adds the domain, has Cloudflare copy the DNS records from the current nameservers, gives the account its workers.dev address, then does `cloudflare`'s work; with an app that keeps uploads, one more step turns R2 on, with its price, and the run waits until R2 is on), the domain's registrar (the two nameservers; the registrar's name and DNSSEC state from the registry's RDAP service; it waits for Enter), Backblaze (the master key; then `backblaze`'s work), the registry's read-only token at ghcr.io (checked to never end, to hold only `read:packages`, and to read the app's image), each app secret from `an_outside_service` on its own screen (checked at Stripe with `checked_with: stripe`), every other vault secret without a question, then the lock: the recovery passphrase, shown once and typed back, and the phone code through `sudo -n set-up-the-phone-code --emergency-codes-to PATH`. Each value is checked with its service at once; a refused value is asked again with the service's reason. It commits and pushes the vault, then the recovery bundle, and copies the bundle into the locked backup bucket. Its last screen says the desk is locked only when `/etc/systems-desk/locked` exists and the before-the-lock root login file is gone; otherwise it says the coding agent locks the desk next, because the lock stage runs after it. `/var/lib/monkeymaxxing-stack/setup_results.json` (0644) names each step's state and the values the coding agent needs that are not secrets; a rerun continues where a run stopped |
| `set-up-outside-services backblaze`, with `--replace-key VAULT_KEY` for a rotation and `--delete-the-old-keys-at-once` after a break-in, as for `cloudflare` | Takes the B2 account's master key at two hidden prompts. Creates every bucket the system uses, sets each bucket's Object Lock and lifecycle rule, checks each lock with a test file, makes each server's key with exactly the capabilities below, and saves each key into the vault |
| `set-up-outside-services cloudflare` | Takes the link token, the one token the person makes by hand from a prepared link, at a hidden prompt. With it, makes the person's desk token and writes it into the API proxy and the token file; with the desk token, creates the tunnels, the apps' R2 buckets (with `staging01`, each app's staging bucket too), and, through `mmhotline status-page set-up`, the status page's bucket, host name, and rule; with the link token, makes the servers' account-owned tokens and R2 keys below and saves them into the vault, and makes the person's own posting key for the status page and writes it into the token file; with a short-lived token it deletes at once, adds the One-time PIN login method when missing and, with `staging01`, makes staging's Access service token, whose two values go into the token file. Before it makes anything, it sets the link token to end by itself after 24 hours, and it deletes the link token when it ends, after a failure too. While the status page's domain is not Active at Cloudflare, it skips the status page and its two keys, says so, and finishes the rest; a rerun adds them |
| `set-up-outside-services cloudflare --replace-key NAME` (repeatable) or `--replace-every-key`, with `--delete-the-old-keys-at-once` after a break-in | Makes a new key for each named one and saves it where the old one was (the vault, the API proxy, or the token file). A key the servers use keeps its old key until the servers' run passed and the person presses Enter; the at-once flag deletes it without waiting. A tunnel gets a new secret; staging's service token gets a new secret with the same ID |
| `set-up-outside-services cloudflare --delete-tokens-of-person NAME` | Deletes, by their names, the desk token, the posting key, and any link token of a person who leaves, NAME being their `vars.person_unix_username`; it refuses the person's own name |
| `set-up-outside-services secrets`, with `--replace KEY` to enter one again | Saves every vault key the playbooks read (`mmx secrets usage`) that the vault lacks and no other command makes: the keys only a website gives, each with its page, at hidden prompts; each app's `secrets_from_vault`, making each one `generated_by_the_setup` and asking for each one from `an_outside_service`; the servers' shared root console password, shown once for the password manager and typed back, saved only as its hash `shared_root_console_password_hash`; and the random keys, made inside MMX or, for the fleet hub's signing secret, as 64 hexadecimal characters handed to `mmx secrets set` on standard input. It skips saved keys, refuses a repository with uncommitted changes other than the vault or with commits not pushed yet, pulls `main`, and ends by committing the vault and pushing it |
| `set-up-outside-services personal-token staging-access` | Takes staging's Access service token from the password manager at two hidden prompts, on a desk whose token file lacks it, and writes it into the token file |
| `set-up-outside-services personal-token server-provider --server-listing-path PATH` | Takes the person's server provider token at a hidden prompt, checks it at the provider, only at a provider guide's own API address, named before the prompt, then writes it into the API proxy's file, its only place on the desk, restarts the proxy, and checks a request through it. For a provider whose API signs each request (`systems_desk_provider_api_authentication: ovhcloud_signed_requests`), it takes each of the credential's values at its own prompt, checks them with a signed listing, writes the API proxy's credential file, restarts that proxy, and checks the listing through it |

**Why go-live works the way it does.** The screens are the product: the
person reads only what to do, so each provider's step-by-step lines run
quietly and an error stops the run with its reason. The recovery bundle,
`recovery_bundle.age`, is an MMX vault file of its own, made with
`mmx secrets set --vault`, encrypted with six words from the BIP39 list (66
bits; age's scrypt makes guessing a copy at the Git host or Backblaze too
costly). It holds the vault passphrase, the production private key, the
desk's WireGuard private key, the console password, the phone code's
emergency codes, the server provider credential, the desk's Cloudflare
token, the restore drill's read-only Backblaze key, the backups' passphrase
(no backup can be read without it), and staging's Access service token with
`staging01`. The Backblaze master key is never stored, the bundle included.
The passphrase is made at the run's start and kept in a 0600 file in the
person's home until the bundle is pushed, so a secret that exists nowhere
else, such as the console password, goes into the bundle when it is made and
a rerun loses nothing. util01 gets the desk's own provider credential,
because providers such as Hetzner make tokens only on their website. Turning
R2 on asks for a card at Cloudflare's checkout, so the Cloudflare screen
states R2's price from Cloudflare's pricing page before the person approves
it. `secrets_from_vault` names where each value comes from, so no screen asks
"random or pasted?": the coding agent reads that from the app's code. A
key from an outside service is checked only at an address fixed in the
command, never one from the settings, which the coding agent can push.

**Why one Stack command.** Two designs were weighed. Playbooks in the template would need new MMX
features: a hidden prompt inside a run, and a task that writes the
controller's vault. That changes another product's execution engine for
one Stack workflow. A Stack command keeps the provider work where it
belongs and uses MMX's vault as it is, through `mmx secrets set`. The cost
is one more pinned program on the desk, built from the Stack repository.
The command ships in Go, as one static program, because users install no
runtimes. It needs no dependency besides a YAML reader: the hidden prompt
uses the standard library's terminal calls.

**Why every command that saves keys commits and pushes the vault
itself.** `secrets`, `backblaze` (with `--replace-key` too) and
`cloudflare` share one path, `beginVaultChange` and `finishVaultChange`.
A vault that changed but was not pushed leaves the servers' runs without
the new keys, and a person new to Git meets a commit and a push as two more
commands to get right. The command owns the whole change: it starts only on a
repository whose other files are committed, so its commit holds the vault
alone; and it pulls first, so the push lands on the team's `main`. Keys
whose value only the person knows are typed; every key nobody needs to see
is made, because a typed random value is a chance for a weak or reused
one. An unknown key the playbooks read is listed, not made: the step
cannot know whether it is random.

**What the command never does.** It never runs as `coding-agent`,
`servers-mmx`, or root (it refuses), so the coding agent never sees a key.
It keeps each master credential in memory for the run only and never saves
it. It never puts a secret in a process argument, a file of the
repository, or its output: values go to `mmx secrets set` on standard
input, and an error message holds only the provider's status, code, and
message, never a request or a response body. It never edits a file in Git
other than the vault; the settings it reads, such as bucket names, stay
the coding agent's to change, and the command prints the values the agent
needs, such as `r2_bucket_url`. It never reads a value back out of the
vault: MMX has no command for that, and the command does not decrypt the
vault itself.

**One source of truth for what exists.** The command reads the bucket
names, the apps, and whether `staging01` exists from `mmx_project_settings.yml`
and `inventories/servers.yml`, so its plan always matches the team's own
settings. It reads which keys are already saved from `mmx secrets list-keys`.
A bucket or key the system does not use is not made: no staging tunnel,
staging keys, or staging uploads bucket without `staging01`, no staging
backup bucket ever (`staging01` keeps no backups), and no uploads bucket or uploads keys while no
app keeps uploads. The command refuses a setting that still holds the
template's example, such as `example-systems-backups`.

**A key issued but not saved** is its own outcome.
The command saves a new key's two values one after the other. When a save
fails, it revokes the new key, and only that key, and says what the vault
got. When the revocation fails too, the message names the key and the
provider page where the person deletes it by hand. One sequence in
`vault.go`, `issueAndSave`, holds these rules for Backblaze and Cloudflare
alike; each provider supplies only its own list, create, and delete calls. A key whose two values are both in the vault is never touched, so a
failed save never revokes a working key. A rerun finds a half-saved pair,
makes a new key, and replaces the half. Before making a key whose pair the
vault lacks entirely, the command deletes any key of the same name at the
provider: such a key is left over from a run whose answer was lost, and
nothing uses it. So a rerun never leaves two keys behind, and a rerun of a
finished setup creates nothing.

That rule holds only while this checkout's vault is the team's vault. A
person who saved keys without committing them, then runs the command in
another checkout or after a rebase that took the other side of the binary
vault, has a vault that lacks keys the servers' vault holds. So when a run
starts, before it asks for a master credential, the command makes this
checkout's vault the team's: it refuses other uncommitted files and
unpushed commits, commits a vault change an earlier run left, and pulls
`origin/main`; only then does it list the vault's keys. A rebase that
conflicts on the binary vault stops the run with nothing changed. After
that, a key this vault lacks, the team's vault lacks too. A key whose vault pair is only half
there is never deleted either, since the saved half may name it: a
`--replace-key` rotation leaves two keys with one name until the person
presses Enter, and the command keeps both, says so, and deletes only the
old key it recorded. The same rules hold for Cloudflare's tokens. Ctrl-C between issuing a key and saving it waits
until the key is saved or revoked.

**Backblaze.** [B2's native API v4](https://www.backblaze.com/apidocs/introduction-to-the-b2-native-api):
`b2_create_bucket` creates a private bucket with `fileLockEnabled` and the
lifecycle rule. Default retention is not part of the create request, so
`b2_update_bucket` sets it next, before any key exists
([create bucket](https://www.backblaze.com/apidocs/b2-create-bucket),
[Object Lock with the native API](https://www.backblaze.com/docs/cloud-storage-enable-object-lock-with-the-native-api)).
An existing bucket gets whatever differs; Object Lock can be turned on
later, but never off, so MMHotline's bucket with a lock on is refused.
The settings count only as `b2_list_buckets` reports them back.
The lock check then proves the lock by its behavior: it uploads a test
file, requires compliance-mode retention of at least the lock length minus one day on it in
`b2_get_file_info`, and requires `b2_delete_file_version` to answer HTTP 401
with `access_denied`. Any other answer fails the check. The master key must
have `deleteFiles`, among the other capabilities the command uses, so a
refusal proves the lock, not a missing permission. The test file is then
hidden, so the lifecycle rule deletes it once its lock ends. A rerun with
every key saved checks the settings only and uploads no test file.
Keys come from `b2_create_key` with a one-element `bucketIds`; the command
checks the answer's capabilities and bucket before saving
([create key](https://www.backblaze.com/apidocs/b2-create-key)). B2 key
names hold letters, digits, and hyphens, so they are made from the project's
name, such as `example-systems-pgbackrest-write`.

| Bucket | Object Lock | Lifecycle rule | Key name | Capabilities, on that bucket only | Vault keys |
| --- | --- | --- | --- | --- | --- |
| `backups.production_bucket` | Compliance, `backups.lock_backups_against_deletion_for_days` | Hidden versions deleted after `backups.keep_prior_file_versions_in_buckets_for_days` | `PROJECT-pgbackrest-write` | `listBuckets`, `listFiles`, `readFiles`, `writeFiles`, `deleteFiles` | `pgbackrest_b2_write_key_id`, `pgbackrest_b2_write_application_key` |
| same | | | `PROJECT-restore-drill-read-only` | `listBuckets`, `listFiles`, `readFiles` | `pgbackrest_b2_read_only_key_id`, `pgbackrest_b2_read_only_application_key` |
| `backups.uploads_bucket`, while an app keeps uploads | Compliance, `backups.lock_backups_against_deletion_for_days` | Same | `PROJECT-util01-uploads-copy` | `listBuckets`, `listFiles`, `readFiles`, `writeFiles` | `uploads_backup_b2_write_key_id`, `uploads_backup_b2_write_application_key` |
| The bucket in `backups.mmhotline_backup_replica_url` | None | Same | `PROJECT-mmhotline-backup` | `listBuckets`, `listFiles`, `readFiles`, `writeFiles`, `deleteFiles` | `mmhotline_backup_access_key_id`, `mmhotline_backup_secret_access_key` |

Reasons for each list:

- **pgBackRest's write keys** list, read, and write the repository, and
  `deleteFiles` lets pgBackRest expire old backups. A deletion inside the
  lock is refused; after the lock, the lifecycle rule removes what was
  hidden. These are the capabilities of the website's "Read and Write" key
  that pgBackRest uses, without the ones it never uses, such as
  `shareFiles` or the bucket-setting capabilities.
- **The restore drill's key** only reads, so a drill can never change a
  backup.
- **The uploads key** has no `deleteFiles` ([Uploaded files](#uploaded-files)).
- **MMHotline's key** needs `deleteFiles`, because Litestream removes the
  database copies it no longer needs. The bucket stays unlocked, because
  Litestream sends no upload checksum (checked with 0.5.18: B2 answers "Content-MD5 OR x-amz-checksum- HTTP header required"), which B2 requires in a locked
  bucket. It gets the same lifecycle rule (`backups.keep_prior_file_versions_in_buckets_for_days`),
  so the copies Litestream removes leave the bucket after that period instead
  of costing storage forever.
- **No key reads lock settings** (`readBucketRetentions`): the servers never
  need them, and the command checks the locks with the master key.

**Cloudflare.** The person makes one token by hand, the link token, from a
link that fills in its one permission, Account API Tokens Edit, and its
name ([token template URLs](https://developers.cloudflare.com/fundamentals/api/how-to/account-owned-token-template/)),
and enters it at the command's hidden prompt. Only a hand-made token can
make tokens: Cloudflare refuses a token made through the API that holds
Account API Tokens Write ("sub-token is not allowed to have permissions to
manage other tokens", tested at Cloudflare). The command
checks the link token with `GET /accounts/ID/tokens/verify`, reads each
permission group's ID by its name and its scope
([permission groups](https://developers.cloudflare.com/api/resources/accounts/subresources/tokens/subresources/permission_groups/methods/list/)),
because two groups can share a name across scopes, and makes each token
with `POST /accounts/ID/tokens`
([create](https://developers.cloudflare.com/api/resources/accounts/subresources/tokens/methods/create/)).

**The link token is deleted when the run ends, after a failure too, and
never saved.** Two decisions were weighed. Keeping it on the desk would
spare a later run, a key replacement, or a deletion for a leaving person
one click on the link; but a token that can make tokens can make one with
any permission of the account, so a copy of the desk's files would let an
outside attacker take over the Cloudflare account. Deleting it costs the
person one click on the same link at each run, which is rare: setup, a
joining person, a key replacement, a leaving person. The link token stays
out of the API proxy for the same reason: the proxy returns every
response, a new token's value included, to the coding agent.

**A run cut off half way leaves the link token for at most 24 hours.**
Cloudflare's form makes the link token with "No expiration", and a run
stopped by Ctrl-C or a dropped connection cannot delete it. So right after
the command checks the link token, and before it makes anything, it sets
the link token's own end to 24 hours from then, unless the token already
ends sooner: `GET /accounts/ID/tokens/ID` reads its name, status, and
policies, and `PUT /accounts/ID/tokens/ID` sends them back unchanged with
`expires_on`. If Cloudflare refuses the update, the run stops before it
makes anything and tells the person to make a new link token, or to give
it an end date on Cloudflare's form. The next run also deletes any earlier
link token of the same name. 24 hours is long enough for a setup session
and a rerun the same day, which takes a new link token anyway, and short
enough that a forgotten token ends by itself. It is fixed, not a setting:
each link token lives for one run only, so a team has nothing to tune.
Proved at Cloudflare with a real link token made on the
website: with only the link token, verify returned its ID; the GET
returned its one allow policy, Account API Tokens Write; the PUT answered
200 and the token then showed the new `expires_on`; verify still answered;
and the link token deleted itself. A token made through the API cannot
stand in for this test, because Cloudflare refuses to give it Account API
Tokens Write ("sub-token is not allowed to have permissions to manage
other tokens").

**The person's desk token** is account-owned and named after the person,
`PROJECT: PERSON's systems desk sets up Cloudflare`, where PERSON is the
person's account name on the desk, `vars.person_unix_username`. It holds,
on the account, Cloudflare Tunnel Write, Access: Apps and Policies Write,
Access: Organizations, Identity Providers, and Groups Read, Access: Service
Tokens Read, and Workers R2 Storage Write; and on every zone of the
account, written as `{"com.cloudflare.api.account.ACCOUNT":
{"com.cloudflare.api.account.zone.*": "*"}}`, DNS Write, Cache Settings
Write, Zone Read, and Zone Transform Rules Write (one token with these
nine, tested at Cloudflare). These cover what the coding
agent does through the proxy (tunnels, DNS, Access applications and
policies, the cache rule, R2 buckets, the lock-out's revocation of Access
sessions) and MMHotline's status-page set-up. The desk token only reads
login methods and service tokens: a login method decides whose address
Access believes, so a token in the proxy that could add one would let a
mistake admit anyone. An account-owned token keeps working whatever
happens to the person's own Cloudflare login, so a leaving person's tokens
are deleted by name (`--delete-tokens-of-person`), never by removing the
person from the account alone. Cloudflare's `/user/tokens/verify` answers
401 for an account-owned token, so every check of it uses
`/accounts/ID/tokens/verify`.

**A short-lived token for Access.** When the account lacks the One-time
PIN login method, or `staging01` needs its Access service token made or
renewed, the command makes `PROJECT: set-up-outside-services sets up Access,
deleted after the run`, with Access: Organizations, Identity Providers,
and Groups Write and Access: Service Tokens Write, uses it, and deletes it
at once. Adding One-time PIN answers 409 "already exists" on an account
that has it (a test account answered so, although its list
of login methods showed none), so the command takes 409 as success.
Renewing staging's service token uses its rotate call, which keeps the
token's ID, so the staging pages' Service Auth policies stay as they are.

**One rerun rule for the person's own tokens**, the desk token and the
posting key: the command keeps one while it is the only token of its name
at Cloudflare and the token file holds it; otherwise it makes a new one,
saves it, and then deletes every other token of that name. So a run
stopped halfway continues, a rebuilt desk's run deletes the lost desk's
tokens, and nothing is left with two tokens of one name. The servers'
tokens keep the vault's rule below. A failure to write the desk token into
the proxy deletes the new token, so the proxy keeps the old one working.

**Replacing a key truly replaces it, after the servers have the new one**
(`--replace-key`, `--replace-every-key`, the same for `cloudflare` and
`backblaze`). The command makes a new key with the old one's permissions,
saves it where the old one was, and pushes the vault. Then it waits in the
person's terminal: it lists the old keys, prints the run the coding agent
starts now (`./server_management_scripts/run_mmx_on_util01 run every_server`,
or the desk button's form during a lock-out), and deletes the old keys when
the person presses Enter after the run and the new keys' checks passed.
Two designs were weighed. Deleting the old key at once leaves the servers,
for the minutes until the run ends, with a key that no longer works: an
app cannot reach its uploads and MMHotline cannot post to the status page,
on a routine replacement on a quiet day. Waiting keeps the hand
procedure's order: new key, run, then delete. The link token, or B2's
master key, stays in the command's memory only while it waits, never on
disk. Ctrl-C or no answer leaves the old keys working; their IDs, never a
secret, stay in the person's
`~/.config/monkeymaxxing-stack/PROJECT_old_keys_to_delete`, so the next
run of the same command lists exactly those keys again and deletes them at
Enter. The file names the keys by ID because the command cannot read
which key of a name the vault holds, and a guess by age would delete the
saved key after a run whose answer was lost.

After a break-in, `--delete-the-old-keys-at-once` deletes the old keys
before the vault is pushed, without waiting. Reason: an outside attacker
may hold the old keys, and a few minutes of failed uploads and status posts
are the smaller harm. `respond_to_a_break_in.md` uses it.

A tunnel has one secret. `PATCH .../cfd_tunnel/ID` with `tunnel_secret`
([update a tunnel](https://developers.cloudflare.com/api/resources/zero_trust/subresources/tunnels/subresources/cloudflared/methods/edit/))
gives it a new one, so the old token opens no new connection at once, in
both forms; no API keeps two tunnel secrets valid. Whether the running
connectors stay connected until the run restarts them is not yet proved.
So `rotate_a_secret.md` runs `every_server` right after the command.
The person's desk token and posting key need no wait: no server holds
them, and the command writes each new one before it deletes the old one.
Staging's service token gets a new secret through Cloudflare's rotate call
in one step; only CI and the other desks hold it, and the procedure tells
each to take the new secret.

An R2 key is an account token scoped to a bucket: its access key ID is the
token's `id`, and its secret access key the SHA-256 of the token's `value`,
in hexadecimal ([R2 API tokens](https://developers.cloudflare.com/r2/api/tokens/)).

| Token name at Cloudflare | Owned by | Permission group | Resource | Vault keys |
| --- | --- | --- | --- | --- |
| `PROJECT: APP reads and writes its uploads`, for each app that keeps uploads | The account | Workers R2 Storage Bucket Item Write | `com.cloudflare.edge.r2.bucket.ACCOUNT_default_BUCKET`, the app's `production_uploads_r2_bucket` | `APP_` and each name in the app's `production_uploads_r2_key_variables`, such as `shop_R2_ACCESS_KEY_ID` and `shop_R2_SECRET_ACCESS_KEY` |
| `PROJECT: APP on staging reads and writes its uploads`, for each app that keeps uploads, only with `staging01` | The account | Workers R2 Storage Bucket Item Write | The app's `staging_uploads_r2_bucket` | `staging_APP_` and each name in `production_uploads_r2_key_variables`, such as `staging_shop_R2_ACCESS_KEY_ID`, which `staging01` reads as the app's own names |
| `PROJECT: util01 reads the apps' uploads`, while an app keeps uploads | The account | Workers R2 Storage Bucket Item Read | Every app's uploads bucket | `uploads_r2_read_only_access_key_id`, `uploads_r2_read_only_secret_access_key` |
| `PROJECT: MMHotline uploads the MMHotline-down alarm` | The account | Workers Scripts Write | `com.cloudflare.api.account.ACCOUNT` | `mmhotline_down_alarm_cloudflare_api_token`, the token itself |
| `PROJECT: MMHotline posts to the status page` | The account | Workers R2 Storage Bucket Item Write | The bucket `mmhotline status-page set-up` made | `mmhotline_status_page_r2_access_key_id`, `mmhotline_status_page_r2_secret_access_key` |
| `PROJECT: PERSON posts to the status page`, each person's own posting key | The account, named after the person | Workers R2 Storage Bucket Item Write | The status page's bucket | None: the person's token file, as `MMHOTLINE_STATUS_PAGE_R2_ACCESS_KEY_ID` and `MMHOTLINE_STATUS_PAGE_R2_SECRET_ACCESS_KEY`, where `mmhotline status-page` on the desk reads it |
| `PROJECT: PERSON's systems desk sets up Cloudflare`, each person's desk token | The account, named after the person | The nine groups above | The account and every zone of the account | None: the API proxy's `/etc/systems-desk/cloudflare-api-token.conf` and the token file's `CLOUDFLARE_API_TOKEN` |

An app that keeps uploads names its R2 key's two variables in
`production_uploads_r2_key_variables`, so the command knows where the app
reads its key; both names must be in its `secrets_from_vault`.
With `staging01`, each such app also names its own staging bucket in
`staging_uploads_r2_bucket`, a plain setting beside production's, not one
derived from it: the Stack's settings are written out, never inherited. The
command refuses an empty value or production's own bucket before it changes
anything, so `staging01`'s key can never reach production's uploads. The
staging bucket gets no copy to B2, since staging holds seed data only, and
util01's reader key does not reach it. `staging01` gets it as the app's
`R2_BUCKET`, and `every_server` refuses `staging01` while an app that keeps
uploads has no staging bucket of its own, or while `staging_env` leaves
production's `APP_ORIGIN` in place.
When a later app adds a bucket, a rerun adds the bucket to util01's reader
token with `PUT /accounts/ID/tokens/TOKEN_ID`, which keeps the token's value,
so the vault needs no change. A reader key made by hand under another name
cannot be found this way; the command then says to add the bucket on the
website.

Each person's posting key lets the person post to the status page from
their own desk while `util01` is down, without a key the servers share.
It was a user token made on the website; an account token named after
the person needs no website step and is deleted by name when the person
leaves.

Each tunnel's name carries the project, such as `example_systems-apps`,
`example_systems-util01`, and `example_systems-staging_apps`, so two systems
in one Cloudflare account never share a tunnel. Unlike a token name, a
tunnel name has no space or colon, so it goes into an API query or a
`cloudflared` command as it is.
The tunnels are created through the API with `config_src: local`, because
a tunnel's routes live in the systems repository
([create a tunnel](https://developers.cloudflare.com/api/resources/zero_trust/subresources/tunnels/subresources/cloudflared/methods/create/)).
An existing tunnel of the same name is reused, and its token is read with
`GET .../cfd_tunnel/ID/token`
([tunnel token](https://developers.cloudflare.com/api/resources/zero_trust/subresources/tunnels/subresources/cloudflared/subresources/token/methods/get/)).
A tunnel token belongs to its tunnel, so a failed save leaves nothing to
revoke.

**The person's own tokens on the desk.** The provider token lives only in
the API proxy's file; the desk token goes into the API proxy's file and the
person's token file. The person types the provider token, which
must pass a check at the provider guide's server listing first; a token
that fails changes nothing, so the old token keeps working.
`set-up-outside-services cloudflare` makes the desk token and hands it to
the same step, which checks it at `/accounts/ID/tokens/verify` through the
proxy. Only the
proxy file needs root, so the command runs one narrow step of its own
through `sudo`, with the token on standard input: the step writes the file,
restarts the API proxy, and checks a request through it. On
any failure the step puts the old file back. The token file keeps every
other line and each line's comment, and its mode stays 0600. The command
writes a value only when it holds nothing but letters, digits, and
`._~+/=:-`, so no value can break the token file's quotes. A token file
holds one line the proxy reads, `proxy_set_header NAME "VALUE";`, the line
nginx once included; the format stayed so that a desk review needs to
rewrite no token file. For a provider whose API signs each request, the
same step writes the proxy's credential file instead, restarts the proxy,
and checks the listing through it, again putting the old file back on any
failure ("The API proxy" below). The proxy starts once every file
its unit hands it exists: Cloudflare's, and the provider's token file or
credential file. While one is missing, the step writes its file, says which
file the proxy waits for, and skips the check through the proxy.

**Recovery items.** `go-live` puts every recovery item into the recovery
bundle at the lock, so no command shows recovery items one by one. The procedures send one item of
the bundle straight to a program with `mmx secrets pipe-to`, or print it to
the person's own terminal with `mmx secrets show`, which refuses to print
anywhere but a terminal ("Read an item from the recovery bundle" in the
template's `operating_procedures/rebuild_a_systems_desk.md`). The person
never edits a file.

**What stays a website step, and why:**

- Making each account, choosing B2's region, approving a cost, and the
  two-step sign-in: the person's identity and money.
- The B2 master key and the Cloudflare link token: something must
  authorize the command, and neither company offers another way. A
  Cloudflare token made through the API cannot make tokens.
- Turning on R2 and opening Workers & Pages once: Cloudflare's own
  activation steps, which no token can do.
- Pushover, the email service, the triage agent's key, and the registry
  token: no API this command could use to issue them was verified.
  `mmx secrets set` takes each one at its hidden prompt.
- Rotating a Cloudflare or B2 key has no website step:
  `set-up-outside-services cloudflare --replace-key NAME` or
  `set-up-outside-services backblaze --replace-key VAULT_KEY`, which make a
  new key, save it, and delete the old key when the person presses Enter
  after the servers' run, as above. `personal-token
  server-provider` rotates the person's provider token, keeping the old
  token until the new one passes its check.

**Release.** The program's version is the Stack version, and its archive is
built by `set_up_outside_services/build_release_archive.sh` with Go's
toolchain from `go.mod`, `-trimpath`, no build ID, and a tar with fixed
order, owners, and times. The same source gives the same archive, byte for
byte, so a published archive can be checked by building it again. The
build writes the archive's address and SHA-256 into the pin itself
([A Stack release pins its own programs](#a-stack-release-pins-its-own-programs)).

**Tests.** Go unit tests run the commands against stand-ins for B2 and
Cloudflare (`set_up_outside_services/internal/standins/`) that refuse what
the real APIs refuse: unknown request fields, a key without a capability,
a deletion inside a lock, a token scope that does not fit its permission
group, and a token-making permission on a token made through the API. A desk test on a
disposable server applies the real desk role through MMX, which installs
the real release, and runs every command as the person through a terminal
against the same stand-ins over TLS, with real MMX, the API proxy, `sudo`, and
MMHotline's own status-page set-up. Stand-ins cannot prove what only the
real companies do: Cloudflare's permission checks, B2's enforcement of the
lock, the permission groups' exact names, and the dashboard links. A short
live run at the real companies checks those before a release.

## Uploaded files

The apps' uploaded files live in R2, at Cloudflare, so losing the servers'
location or provider loses no uploads. A mistake, an attacker with an
app's R2 key, or a Cloudflare account takeover can lose uploads. Every app
server holds each app's R2 key.

So `util01` copies each app's `production_uploads_r2_bucket` every
`backups.uploads_copy_every_hours` hours, starting one hour after
`nightly_work_starts_at` (every night at 02:00 UTC in the template), into one B2 bucket, `backups.uploads_bucket`, in a folder
named after the app. The script `copy_uploads_to_the_backup_bucket`
(`roles/uploads_backup/files/`) runs from a timer of its own. The app reads
the same setting as `R2_BUCKET`, which the Stack writes, never the app's
`env`, so the app and the copy cannot name different buckets. On `staging01`
the app's `R2_BUCKET` is `staging_uploads_r2_bucket`, and its other own
settings, such as `APP_ORIGIN`, come from `staging_env`.

**What comes back:** a file deleted or overwritten in R2
comes back, as the last copy before the change held it, for
`backups.keep_prior_file_versions_in_buckets_for_days` (14 in the template)
after the change; a file uploaded since the last copy isn't in it yet.

- **How often: a setting, nightly by default.** `uploads_copy_every_hours`
  is one of 1, 2, 3, 4, 6, 8, 12 and 24 (`validate_the_schedule_settings`
  refuses other values), so the copies fall at the same hours every day:
  the timer is `*-*-* 02:00:00 UTC` for 24, as before the setting, and
  `*-*-* H/N:MM:00 UTC` otherwise, where `H` is the start hour's remainder
  after dividing by `N`, because systemd's hour step stops at 23. Reason for
  24: one night of uploads is what a small team loses at most, and every
  copy lists every file of every app's bucket, which costs storage requests.
  The age warning follows the setting (the interval plus 2 hours); the weekly
  full copy follows the age of its own marker, and the restore drill's
  ordering after a running copy and its sample by the last passed copy's
  start need no change.
- **A warning when one copy hides an unusual share of an app's files.**
  Before each app's copy, a dry run of the same `rclone sync` with
  `--combined -` lists what the copy will hide: files gone from R2 (`-`)
  and changed in R2 (`*`), out of the files in the app's folder before the
  copy (`-`, `*`, `=`). A real run's report would not do on full-copy
  nights, when `--ignore-times` marks every file changed. The copy prints
  the two numbers, never a path, and writes a line per app above
  `warn_when_one_uploads_copy_hides_more_than_percent_of_an_apps_files`
  (10) into `/var/lib/uploads_backup/apps_whose_latest_copy_hid_an_unusual_share`,
  once the folder held `warn_about_hidden_uploads_only_when_an_app_has_at_least_files`
  (100). MMWatchdog's `uploads_backup/the_latest_copy_hid_no_unusual_share_of_an_apps_files`
  fails at once while the file holds a line; the next copy rewrites the
  file, so the warning closes by itself. The group checks every 10 minutes,
  so each copy's result is read even with hourly copies. Reasons: an app
  that deletes or replaces a tenth of its files in one night is unusual,
  while an intruder or a mistake that deletes everything is far above it;
  a new app with ten files deletes two on a normal day; warn, not SOS,
  because the files stay restorable for
  `keep_prior_file_versions_in_buckets_for_days` and a customer's own bulk
  delete would otherwise wake a person for nothing. The cost: one extra
  listing of both buckets per copy. A system without uploads has no copy,
  no file and no check.

- **Only where uploads exist.** The role `uploads_backup` sets up the copy
  in an `every_server` stage after the server setup stages.
  `backups.uploads_backup_runs_on` names the servers: `[util_server]`, or
  `[]` while no app keeps uploads. With `[]` the stage selects no nodes,
  so MMX needs none of the uploads copy's four keys. A system without
  uploads needs neither the bucket nor the keys (`mmx secrets usage` marks
  the keys "not needed with this inventory").
  The stage just before `uploads_backup` refuses an app with
  a bucket while `backups.uploads_backup_runs_on` is `[]`.

  The uploads refusal and copy stages follow the server setup stages. So
  the refusal, or a key the copy cannot use, holds back no earlier server
  work. A key missing from the vault stops the whole run before the run
  starts, because MMX loads every secret a run needs first. MMX cannot
  select a stage from the apps' settings themselves, because a fleet
  stage's `nodes` is a group, a list, or one whole template reference.
- **The uploads' B2 bucket is locked like production's database backup
  bucket:** versioning on, and Object Lock in compliance
  mode for `backups.lock_backups_against_deletion_for_days`. No one can delete a version sooner, the account's
  owner included. The uploads bucket's lifecycle setting keeps each prior
  version of an overwritten or hidden file for `backups.keep_prior_file_versions_in_buckets_for_days` (14 days in the template, as
  long as the lock). Then the lifecycle rule deletes the prior version, so a file a
  customer deleted leaves the backups too.
- **`util01`'s B2 key can't delete:** `listBuckets`, `listFiles`,
  `readFiles`, and `writeFiles`, made with B2's native API, because
  the website's "Read and Write" key includes `deleteFiles`. rclone's
  `sync` and `copy` never need `deleteFiles`. rclone 1.75.2's B2 backend
  deletes a version only for `--b2-versions`, `hard_delete`, `purge`, and
  `cleanup`, and the stack uses none of these four. A hide, an upload, and
  the cancel of a failed large upload need only `writeFiles`. So only the
  lifecycle rule deletes, after the lock, even for an attacker on `util01`.
- **`rclone sync`, with B2's own API.** When a file is gone from R2, rclone
  hides the file in B2 and never deletes the file (`hard_delete = false`).
  So the file's versions stay for `backups.keep_prior_file_versions_in_buckets_for_days`.
  rclone is the vendor's release, pinned in `stack_software`, at
  1.75.2: Debian 13 ships 1.60, which can't sign in with a key
  restricted to one bucket as B2 makes them today (rclone added that in
  1.73.0), and lacks the fix of 1.70.3 for finding files with
  `--b2-version-at`, which the drill and a restore use.
- **R2's own time decides what changed** (`--use-server-modtime`): the
  apps' uploads carry no time of rclone's, and without the flag rclone
  asks R2 for each file's metadata, one request per file, every night.
  The flag acts on the S3 side only. B2 keeps the time rclone gives each
  file, R2's file timestamp, so an unchanged file compares equal without
  `--update`.
- **A full copy once a week** (`--ignore-times`), when the last one is
  more than 6 days old, by its marker file's age, so a copy missed on a
  Sunday doesn't push the next one a week further. Each file's newest copy
  is then at most about a week old, and so under its lock, as the newest
  full backup of the database is: no one, the B2 account's owner included,
  can delete the copy of a file the apps still have. Copying only the
  changes was rejected because of someone who gets into the B2 account
  itself, through the account's login or master key: every file that
  hasn't changed for the lock's length would have only an unlocked copy, which that
  person could delete at once. Against an attacker on `util01`, the full
  copy adds nothing. `util01`'s key can't delete, and a file that the
  attacker hides or overwrites keeps the file's last good version in B2
  for `backups.keep_prior_file_versions_in_buckets_for_days` after the hide or overwrite, with full copies or with copies
  of only the changes: B2's lifecycle rule counts those days from when a
  version is hidden, not from the version's upload. The cost of the full
  copy: the bucket holds about three copies of the uploads, the newest and
  the prior versions, and once a week the whole of the uploads
  passes through `util01`'s network.
- **The R2 key can only read,** one account API token for every app's
  bucket, so the copy can't change an upload, whatever a mistake tells it.
  Each new app's bucket is added to the read-only R2 account API token's
  allowed buckets. Copying a file back is a one-time
  playbook with the app's own R2 key from the vault (the template's
  [restore_an_uploaded_file.md](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/restore_an_uploaded_file.md#restore-listed-files), "Restore listed files").
  `restore_an_uploaded_file.md` holds every restore; turning the copy on
  holds none, so a person in trouble finds one page.
- **All of an app's files at a chosen time,** after a break-in or a large
  mistake: a one-time playbook on `util01` runs `rclone copy` (or `sync`)
  from the app's folder with `--b2-version-at` into the app's R2 bucket,
  with the app's own R2 key from the vault. No new key: the app's key is
  the only key that can write the app's bucket, and the vault already
  holds it. Its first task compares first with `--dry-run --combined -`
  and `util01`'s read-only R2 key, and prints four counts, never a path,
  so a dryrun shows the person what the restore writes, keeps and
  deletes before the approval. It refuses when the backup held no file of
  the app at the time, because a `sync` from an empty folder would empty
  the bucket. Files uploaded after the chosen time stay (`keep`, rclone
  `copy`) unless the person chooses `delete` (rclone `sync`): a later
  customer upload may have no other copy, and an unwanted file can still
  be deleted later. The time is written `2026-11-03T14:00:00Z`, because
  rclone 1.75.2's `--b2-version-at` refuses pgBackRest's
  `2026-11-03 14:00:00+00` form (checked with the pinned release).
  After a break-in the restore runs after the app's own R2 key is
  replaced, so the intruder's copy of the key cannot delete the restored
  files again.
  The paths of files to restore come from the vault key
  `uploaded_file_paths_to_restore`, not from a run variable. MMX's
  command-line variables are public, in `explain`, the process list, and
  the run's history, and a path can name a customer. A task that
  reads a secret has its whole result hidden, so neither the paths nor
  rclone's lines stay in MMX's controller history.
- **`util01` keeps no customer file on its disk:** the copy streams each
  file from R2 to B2 through memory, and the drill's check compares with
  `rclone check --download`, which reads both copies into memory.
- **The drill reads one file of each app** from the uploads' B2 bucket as
  the bucket stood at the drill's start (`--b2-version-at`). A restore
  after an attack also reads the bucket as of a past time. The drill
  compares the file with the file in R2. The drill picks the file at random
  among files whose R2 time is before the last passed copy's start. So a
  file changed after the copy's start does not fail the drill.

  R2 is the comparison's source, so a file that the backup lacks fails the
  comparison. With B2 as the source, rclone would skip the missing file.
  The drill script's log names the sampled file. The checklist omits the
  sampled file's path because a path can name a customer.
- **The uploads copy's checks:** the copy writes
  `/var/lib/uploads_backup/latest_passed_copy` once every app's copy passed,
  and `latest_passed_full_copy` after a full copy. MMWatchdog's group
  `uploads_backup` on `util01` exists while
  `backups.uploads_backup_runs_on` names `util01`'s group, also between
  copies. The group warns when `/var/lib/uploads_backup/latest_passed_copy`
  is older than `uploads_copy_every_hours` plus 2 hours (26 in the
  template) or `latest_passed_full_copy` is older than 8 days. A failed copy fails the copy's unit, which every server's check
  for failed units sees.
- **The first copy starts by itself,** in the background, whenever the
  `uploads_backup` role runs while no copy has passed on `util01`.
  `start_the_copy_until_one_has_passed` is skipped once `latest_passed_copy`
  exists. The role starts the first copy during the initial setup and in
  the run that turns the copy on. So the copy's checks pass instead of
  warning 2 hours later, with no `systemctl start` by a person.

  A first copy that failed starts again with the run of the fix. The copy
  starts in the background because a first copy of a big bucket can take
  hours. Meanwhile, the run, which holds `util01`'s lock, would hold back
  every deploy. Starting the copy while a copy already runs changes
  nothing.

## Rotating a secret

Every kind of secret follows the steps of the template's
[Rotating a secret](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/rotate_a_secret.md#rotating-a-secret).
The steps are: issue the new secret, update the vault, run MMX, restart
what reads the secret, verify, and revoke the old secret. For every kind of secret but an
app's database password, a commit does the middle steps. The vault change
makes `util01` run `every_server`. The `every_server` roles rewrite the
files that hold the secret and restart what reads the files, one app
server at a time. An
app's database password also needs `playbooks/end_connections_that_use_an_old_database_password.yml`, for what
the `every_server` run cannot do:

- **An app's database password.** A Postgres role has one password, which
  Postgres checks only when a connection opens. `every_server` sets the new
  password on the primary first and restarts the app's containers after.
  So the connections opened before keep working meanwhile: the old and the
  new password overlap in the connections. `end_connections_that_use_an_old_database_password`
  (`--var environment_name=production --var database_name=shop`) then ends
  the overlap:

  1. `end_connections_that_use_an_old_database_password` logs in as the app's Postgres role with the current
     vault password, using Bash, jq and psql. Each database server's app
     login rules admit password authentication from the server's own
     private address. Staging already admits staging01's private address.
     The private listener and firewall stay unchanged.
     The playbook also checks each app's
     secrets file contains the current password before reading container
     start times. A live check establishes the rotation's prerequisite
     without a private deployment-state file.
  2. `end_connections_that_use_an_old_database_password` checks that each container of the app started after
     the container's secrets file changed: on the app servers and on
     production's jobs servers, or on `staging01`.
  3. On each database server of the environment, replicas too,
     `end_connections_that_use_an_old_database_password` ends the role's connections that are older than the
     app's oldest container. The ended connections are the old password's
     connections, such as a connection held by whoever leaked the old
     password. Where PgBouncer runs, the role's older PgBouncer client
     connections end first
     ([PgBouncer, a later step](#pgbouncer-a-later-step)).

The kinds of secret in the table need only "issue, vault, commit, push, run MMX, verify, revoke", with the
order and the check in the template's [rotate_a_secret.md](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/rotate_a_secret.md#rotating-a-secret), "Rotating a secret":

| Kind | What restarts with the new secret | Verified by |
| --- | --- | --- |
| The shared root console password | nothing: MMX updates root's hash on production and staging | a provider-console root login with the new shared root console password |
| An app secret | the app's containers | the app's own use of the new secret |
| A tunnel token | `cloudflared` on each server of the tunnel | the public host names answering; Cloudflare's "Refresh token" keeps the running connectors up and stops new connections with the old token, so the refresh is issue and revoke in one |
| The registry token | nothing: each pull logs in | the next deploy pulls with the new token |
| A B2 key | nothing for pgBackRest, which reads `/etc/pgbackrest/pgbackrest.conf` at each command, or for the uploads' copy, which reads the copy's settings file each night; Litestream's backup unit for MMHotline's key | the next daily backup, the next drill for the read-only key, the backup unit's log for Litestream's key, and the next nightly copy for the uploads' key |
| The uploads' R2 key | nothing: the uploads' copy reads the copy's settings file each night | the next nightly copy |
| The Pushover keys | the fleet hub. When `util01`'s run applies `mmhotline_settings.yml`, MMHotline's sending service takes the new application token from the vault key `pushover_application_token`. MMHotline keeps every Pushover contact method, because a user key works with any Pushover application. While an emergency message is open, MMHotline keeps the old token, because MMHotline checks and cancels the emergency message with the old token. Then applying `mmhotline_settings.yml` fails `util01`'s run until the run's retry | `mmwatchdog send-notice` to the push app, a contact method's test, and the MMHotline-down alarm's test |
| The pg_auto_failover monitor password | nothing: `every_server` sets the monitor's login on `util01`, then writes each database server's password file, one server at a time. A keeper is a database server's pg_autoctl process, which reports to the failover monitor. Until the keeper's turn, the keeper cannot report to the monitor. The monitor still fails nothing over, because the monitor's own checks reach each Postgres (pg_auto_failover's `IsUnhealthy` needs a failed report and a failed check). A primary whose replica copies from the primary does not take itself for cut off (`is_network_healthy`) | the keepers' report times on the monitor |
| The pg_auto_failover replication password | nothing: `every_server` sets the primary's replication login, then writes each database server's password file, one server at a time | a replica's login to the primary |
| `util01_provider_api_token` | nothing: the restore drill's two jobs, `weekly_database_restore_drill` and `check_for_a_leftover_restore01`, read the token at each job's next start | the next `check_for_a_leftover_restore01` |
| MMHotline's: the triage agent's credential, the MMHotline-down alarm's token, the status page's R2 key | nothing: `util01`'s run writes `mmhotline_settings.yml` and runs `mmhotline settings apply`, which tests each changed part first. MMHotline tests the agent with a prompt, the MMHotline-down alarm with an upload and a check-in, and the page with a post. When a test fails, MMHotline keeps the old value, and `util01`'s run fails until the run's retry | `mmhotline settings show`, and each changed part's own test |
| The fleet hub's signing secret | the fleet hub, in the run's `util_server` stage, before `apply_the_mmhotline_settings` drops the old secret. The rotation takes two commits, because the alert source first lists the new secret beside the old secret, so no alert is refused while the hub moves to the new secret | `mmhotline alert-sources list` names one secret, and a test alert from the hub arrives |

Two secrets are not rotated by the issue, vault, commit, push, verify,
revoke steps. `pgbackrest_repository_cipher_passphrase`
encrypts every backup and archived WAL file in the bucket, so a new
passphrase would read none of the bucket's files. When the passphrase may
have leaked, the B2 keys are rotated, because the passphrase alone reads
nothing. The vault passphrase changes with `mmx secrets passwd`, in the
template's [Adding or removing a person](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/add_or_remove_a_team_member.md#adding-or-removing-a-person).

## Later steps

PgBouncer, jobs servers, and load-balancer servers each wait for a measured
trigger, and most systems take few of these steps, or none for years. Each
step's role and fleet stages are in every systems repository from the
initial setup, and do nothing until the step. The step's settings, in
`mmx_project_settings.yml`, are `false`, and the jobs and load-balancer
servers' groups are empty. So each later step is commits, like any other
operating procedure, and the team sees the whole path from the initial
setup, with nothing hidden.

A kind of pool the Stack doesn't ship, such as cache servers, follows the
same pattern but is not in the template:
[Add a new kind of server pool](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/add_a_new_kind_of_server_pool.md)
lists the six decisions a team makes (name and addresses, peers and
firewall, software, data and backups, checks, and the reading that says to
add another), with the jobs servers as the worked example. The Stack ships
no such pool, because each one is a step beyond the Stack that a business
requirement decides, and the team records it in the checklist as a
deviation.

- **Each step's settings are named for what they turn on,** and `true`
  means the step is in effect: `job_containers_run_only_on_the_jobs_servers`,
  `tunnel_connector_and_caddy_run_only_on_the_load_balancer_servers`, and
  PgBouncer's two, `pgbouncer_runs_in_front_of_postgres` and, per
  environment, `apps_connect_through_pgbouncer`. A group's servers alone
  cannot be the signal. A new server is in the inventory before
  configuration and verification prove the server can carry work. And a server in the inventory may have failed the
  server's stage.

  The operating procedure brings up what the step needs beside what the
  step relieves, such as new servers beside the app servers. A person
  checks the new servers or services. Then a setting's commit moves the
  work. Turning the setting back to `false` is the way back, again with
  the work's old and new places overlapping.
- **A setting that would leave the work with no server is refused,** at
  the first app server, before anything changes. The run refuses the jobs
  and load-balancer settings while the step's group is empty. The run also
  refuses an environment's `apps_connect_through_pgbouncer` while
  `pgbouncer_runs_in_front_of_postgres` is `false`.

  PgBouncer's refusal sits in the stage that finds the live web ports,
  before the jobs servers' stage. A job container has no health URL, so
  every worker would otherwise restart against a port that nothing serves.
- **What each step needs from other roles is there from the initial setup
  too:** the group and the group's flag, the firewall rules, peers, and
  `pg_hba.conf` lines for the group's servers, and the step's check groups.
  A firewall rule for an empty group expands to no rule, and a list of
  peers or hosts gains no line.
- **Copying a step's role in at the step's trigger was rejected:** MMX
  refuses a playbook that names a role MMX can't find, even in a fleet
  stage that selects no server. So a copy-in meant editing the playbooks by
  hand during the operating procedure, and most of each step's wiring lives
  in shared files anyway.

## Jobs servers

`jobs001` and up, in `jobs_servers`, at `10.20.3.N`, run each app's job
container from the app's own image and `jobs_command`, as the app servers
do, and nothing that takes requests: no web container, no Caddy, no tunnel
connector (`roles/jobs_server`). Jobs servers peer over WireGuard with the
database servers and `util01` for workload traffic, and every systems desk for administration.
Jobs servers run production's job
containers. `staging01` runs staging's job containers.

- **Where the job containers run:** `staging01` always runs staging's job
  containers. Each jobs server starts job containers in the jobs server's
  first configuration run, after MMX adds the database peers. The
  first-boot key already lives in the inventory. The app servers run job containers until
  `job_containers_run_only_on_the_jobs_servers` is `true`.

  A WireGuard key alone did not decide the move. Otherwise, a jobs server
  whose stage failed, or whose workers cannot start, would have taken the
  jobs off the app servers all the same. The person checks the jobs
  server's journal before the setting's commit
  ([Adding jobs servers](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/add_jobs_servers.md#adding-jobs-servers)),
  and the run refuses the setting while `jobs_servers` is empty and an app
  has a `jobs_command`. The refusal tells the person to set the setting back
  to `false` or to add a jobs server first.

  An app with no background jobs sets `jobs_command: ""`. Every app states
  the key, so a forgotten `jobs_command` is refused and `""` is a visible
  choice (as `production_uploads_r2_bucket: ""` is for an app with no
  uploads). That app gets no job container on staging01, the app servers, or
  the jobs servers; its job-container MMWatchdog checks, the image pulls on
  the jobs servers, and the waits in `remove_server` and
  `reboot_servers_after_updates` skip it. When an app changes from having
  jobs to having none, the next `every_server` run removes its old job
  container (service and Quadlet file) from every server it set up. The
  jobs-only switch never refuses for such an app. Its checklist item
  `<app>_background_jobs_run_from_one_command` is marked `deviated`, with no
  background jobs as the reason, as the email item is for an app with no
  email.

  `every_server`'s call of `app_server` passes
  `job_containers_run_only_on_the_jobs_servers`.
  `deploy`'s and `remove_server`'s calls change a job container only where
  one runs (`path_exists`), so the calls do not need
  `job_containers_run_only_on_the_jobs_servers`. The app servers' check
  group `job_containers` follows `job_containers_run_only_on_the_jobs_servers`.
- **A job while jobs move to the jobs servers.** The queue is in Postgres.
  An app server's job container gets the stop signal and up to 30 seconds
  (`StopTimeout`) to finish the current job. The reference app's worker
  finishes the job the worker runs, then exits. A worker that is still in a
  job when the 30 seconds end is killed and never commits the job's
  transaction. So Postgres releases the job's row lock, and another worker
  runs the job again.

  Between the commit of the jobs server's WireGuard key and the setting's
  commit, app servers and jobs servers both run workers.
  A queue that locks each job's row (`FOR UPDATE SKIP LOCKED`) allows the
  overlap. Moving the jobs back also overlaps app servers and jobs servers.
- **The release on jobs servers** is the app servers' live release.
  `every_server` passes the first app server's `live_web_containers`, so
  a new jobs server starts on the live release, never on a tag whose
  migrations have not run. A jobs server that missed a deploy's last step
  catches up at the next run.

  A deploy pulls the new images on the jobs servers in the deploy's step 2
  ([playbooks/deploy.yml](../skills/monkeymaxxing-stack/systems_repository_template/playbooks/deploy.yml)).
  So a jobs server that cannot pull stops the deploy before anything
  changes. The deploy changes the jobs servers' job containers in step 6,
  after every app server stopped the app server's old web containers. The
  app servers' own job containers change in step 6 too.
- **The secrets on jobs servers** are the apps' production secrets, with
  the same `app_secrets` lines in `every_server.yml` as the app servers'
  call. `end_connections_that_use_an_old_database_password` checks the jobs servers' job containers too.

  The fleet stage `find_when_the_containers_of_the_app_started` selects
  `[app_servers, jobs_servers, staging_server]`, and the stage's `when`
  keeps the environment's servers, with no connection to the others. The
  next fleet stage, `end_the_connections_of_the_old_password`, reads the
  whole output of `find_when_the_containers_of_the_app_started`. The
  output leaves out the servers that the `when` skipped, and a server that
  failed stops the run first. `end_the_connections_of_the_old_password`
  has no `requires.all_nodes`, because MMX counts a skipped server as unmet
  in `requires.all_nodes`.
- **`remove_server`** stops a jobs server's job containers. While only the
  jobs servers run the jobs, `remove_server` refuses the last jobs server.
  `remove_server` also checks first that every other jobs server runs each
  app's job container (`systemctl is-active`). The check also catches a
  jobs server whose WireGuard key is not in the inventory yet.

  Before the setting is `true`, `remove_server` checks nothing, because the
  app servers run the jobs. On the way back, each jobs server that
  `remove_server` already took out stays in the inventory until the commit
  that deletes all the jobs servers.

  A dead jobs server needs no `remove_server`: the dead server leaves the
  inventory. When the dead server was the only jobs server, the commit that
  removes the dead server also sets the setting back to `false`. Until
  then, every
  production deploy stops at the jobs servers' pull, before it changes
  anything, as a dead app server stops it.
- **MMWatchdog:** each jobs server joins the fleet hub, in its own node
  group, so the dashboard draws a box for the pool. Each jobs server's
  check group `jobs_servers` warns at 70% CPU or 75% memory for 15 minutes
  (the operating procedure: add a jobs server). The check group also
  records each job container's CPU. A silent jobs server warns, because
  the other jobs servers take the silent server's jobs.

  Once only the jobs servers run the jobs, each jobs server also names the
  jobs servers' group in MMWatchdog's
  `raise_to_sos_when_every_node_of_these_node_groups_is_silent`. So the hub
  raises the jobs servers' silence alerts to SOS while every jobs server
  is silent, also when there is only one jobs server. While every jobs
  server is silent and only the jobs servers run the jobs, no job runs, and
  no other check sees the stop. A jobs server in a maintenance window, as
  during the jobs server's reboot, does not count as silent
  ([Reboots](#reboots)).
- **Scheduled tasks:** the template runs no app task on a server timer.
  The app contract has no setting for an app task on a server timer. The
  one timer on the app servers, the weekly cleanup of unused images, is
  the server's own, which the jobs servers run too, because each deploy
  pulls an image there. An app's
  recurring jobs that its queue schedules, such as Solid Queue's recurring
  tasks or good_job's cron, run in its job container, so they move with it.

## One coding agent, on the laptop

The team's coding agent is the one the person already uses, on their own
laptop. There is no coding agent on the desk, nothing to sign in there, and
no handoff between two agents. Reason: two agents meant two sign-ins, two
conversations and the person carrying messages between them; one agent on
the laptop already has the app's code, the person's Git login and the
conversation.

**One door to the desk.** The laptop's SSH settings hold `desk01-agent`, as
the desk's `coding-agent` user, with `ControlMaster auto`,
`ControlPersist 1h` and `ServerAliveInterval 30`. The person types one
phone code in the chat; the agent passes it to the systems repository's
`ssh/open-the-desk-login CODE`, which hands it to SSH through `SSH_ASKPASS`
with `SSH_ASKPASS_REQUIRE=force`, so no terminal is needed, and every later
command reuses the one shared connection. The script is its own askpass
program and reads the code from its environment, so no file ever holds the
code; it asks once (`NumberOfPasswordPrompts=1`), because each wrong try
counts toward the lockout. It takes the desk from the repository: the
`ssh/DESK` file whose laptop key, `~/.ssh/DESK.pub`, the desk's
`allowed_laptops` lists. Reason for a script: a command that starts with a
variable assignment matches no Claude Code allow rule, so the earlier
`mktemp` snippet asked the person each time. sshd gives `coding-agent`
`DisableForwarding yes` and sets `SSH_AUTH_SOCK` and `GIT_CONFIG_SYSTEM` for
its commands, so it uses the production key's relay socket and never holds
the key. Both the person and `coding-agent` use one root-owned phone-code
file, `/etc/systems-desk/phone-code`; a code used by one is refused for the
other, so the agent's screens say WAIT FOR A NEW CODE where one code
follows another.

**The desk decides how long a login lasts.** sshd's `UnusedConnectionTimeout`
closes a login unused for `coding_agent_login_idle_minutes` (60 in the
template), and a timer ends a login older than
`coding_agent_login_longest_hours` (10). Both are settings with their
reasons. Reason for the desk and not the laptop: a changed laptop setting
cannot lengthen them. A laptop that sleeps less than the idle hour needs
nothing; after a longer sleep the agent asks for one new code.

**Long runs are desk jobs.** A run longer than a few minutes starts with
`systemd-run --user` as `coding-agent`, with a log file and an exit file
named after the run. It keeps running when the connection closes, and the
agent reads the two files later. Reason: nothing on the desk needs
resuming, so no terminal-session program runs there; the agent's
conversation lives on the laptop, where the agent already keeps it.

**The agent waits with one command.** `wait-for-a-desk-job NAME` and
`wait-for-the-setup` run in the agent's own login, with no sudo. Each
prints a line at least once a minute, so the person sees progress, and
ends after 9 minutes by default with its own exit code (124), before Claude
Code's 10-minute command limit. The job's exit code passes through; 125
means the exit file holds no number. The wait reads only `~/runs/NAME.log`
and `NAME.exit`. `wait-for-the-setup` reads `go-live`'s results file, and a
stop counts only when the file was written after the wait started, because
an earlier run's `stopped_with` stays until the next run's first write.
Reason: in a newcomer test the agent wrote 25 polling loops, and one
blocked `sleep 240` turned a wait into a turn that ended with a promise.
`wait_for_the_app_image`, in `server_management_scripts/`, runs on the
laptop, because the desk's registry login is in the vault: it asks the
registry's manifest address, with a login only when the laptop already
saved one, and says "cannot tell" (exit 3), never "missing", when the
registry refuses the laptop.

**Edits on the laptop, publishing on the desk.** The agent clones the
desk's checkout, `git clone desk01-agent:systems_repository`, edits with
its own tools, pushes a branch to the desk, and runs
`ssh desk01-agent publish-branch-to-main BRANCH`. That rebases the branch
onto `main`, fast-forwards `main`, pushes it to the main copy on `util01`,
and deletes the branch; on a conflict it names the files and changes
nothing. The laptop pushes the Git host's backup with the person's own login.

**What the desk protects, and what it leaves.** The production key, the
vault passphrase and the person's tokens stay on the desk, and the agent
uses them without copying them. The idle hour and the ten-hour limit exist
so a login does not stay open on a laptop that is lost, stolen or left
unattended. The guide's rule to run the app's install and test commands in a
container on the laptop keeps the app's own commands away from the open login
by mistake. A live attacker on the laptop during an open login is the rare
case these limits bound; nothing more is built for it ("The systems desk",
below).

## Naming

- Files and directories are named for what they hold, with whole words.
- Task IDs say what the task does, such as `install_caddy_from_its_repository`.
- Roles take their values as declared inputs, including the inventory
  (`inventory_nodes`, `inventory_groups`) and the group flags, because a
  role can't read `.inventory` itself.

## The systems desk

### Use only a coding agent you trust

The Stack requires a coding agent the person trusts, and it is built only
for trusted agents. Trust means three things: the person trusts the agent
to do the work well, trusts its intentions, and trusts the company that
runs it, because the person's work passes through that company. Using an
agent the person does not trust on production servers is at the person's
own risk; an agent or a model the person would not trust with root on
every server must never be used here.

### What the desk protects against, and what it does not

The agent works on the servers with root, because that is its job. Every
protection on the desk exists for one of five things:

- **A stolen or lost laptop.** Every login to the desk needs a code from
  the person's phone.
- **Malware or a thief copying the laptop's files.** The production key,
  the vault passphrase and the person's tokens are never on the laptop.
  They live on the desk, so the laptop holds nothing worth stealing.
- **A secret reaching the agent's conversation.** What the agent reads goes
  to the company that runs it. So the agent uses the keys through the desk
  and never sees them. The person types each secret at a hidden prompt, and
  no command the agent runs prints one.
- **Clumsy mistakes.** For example, a cleanup that deletes the desk itself,
  a typo that cuts the person's laptop off, or a screen that says "locked"
  when the desk is not.
- **Attackers from outside.** Only the person's laptop reaches the desk.
  Wrong phone codes get banned, and the person gets an alert.

What it does not protect against:

- **An agent the person does not trust.** The agent has root on every
  server, through the button; that is how it runs them. A fence on the desk
  against it would add parts and steps, and still not stop it.
- **Someone in control of the laptop while the desk login is open.** Until
  the login closes, they can do what the agent can do, including reaching
  outside hosts through the servers, like any administrator. The login
  closes after `coding_agent_login_idle_minutes` without a command (60) and
  after `coding_agent_login_longest_hours` (10) at most. That is the rare
  case these limits bound, and nothing more is built for it.

**Judge every review finding and every design question by these lists.** A
finding that needs the trusted agent to act against the person is not a
finding. A finding about a live attacker using an open desk login is
answered by the login limits; no further desk part is built for it. A
finding that lets a key or a secret reach the laptop, the agent's
conversation, or an outside attacker is a real finding. A security
review's brief quotes this section first.

Each person has a numbered systems desk, `desk01`, `desk02`, and upward.
The desk holds systems work; the laptop keeps app development and desk-only login keys.
The desk runs in a location different from production.
Reason: a production location outage must leave the person's tools available.
Numbered names permit a replacement to exist beside the old desk during preparation.
The person's name belongs in `vars.person_unix_username`, rather than in the node name.

### One inventory and separate management

`inventories/servers.yml` is the source of truth for production, staging, and desks.
The `systems_desks` group uses `vars.private_ip_ranges.systems_desks`, normally `10.20.9.0/24`.
Laptop peers appear only under each desk's `vars.allowed_laptops` and use `10.20.10.0/24`.
Reason: a separate desk inventory would duplicate production peer data and drift after server changes.
The desk takes its server peers from this inventory too, through `update-this-desks-wireguard-peers`.
The desk uses kernel `wg0`, because MMWatchdog needs a network connection to the fleet hub.
Doubleshell carries the laptop's SSH connection without giving the laptop a production network interface.

`playbooks/systems_desk.yml` owns desk configuration.
Production playbooks exclude `systems_desks`; `util01` never manages a person's desk.
Reason: production's base role would replace the phone-code door with production root-key access.
The desk manages `127.0.0.1` with `/root/.ssh/systems_desk_self_management_key`.
The separate root-owned key never enters the production SSH socket.
`ssh/desk01` pins the host key under `HostKeyAlias desk01`, preventing a desk from applying another desk's identity to loopback.
The person runs, on the laptop, with a phone code:

```sh
ssh desk01-review
```

The entry runs `review-and-apply-the-systems-desk-settings` on the desk, as the person.

The command runs `mmx run systems_desk --var desk_name=<this desk> --connection ssh_only` as root,
with the person-owned private agent socket, which reaches `util01` to read the monitoring join code.
First bootstrap runs only `--only-fleet-stages systems_desk`, because `util01` does not exist yet;
the laptop's bootstrap run uses `mmx` directly, and every later run uses the command.
The command first fetches `origin` into the coding agent's checkout, as the coding agent, reads pushed `main`
from it as data, and stops with nothing run when the fetch fails, so the person reviews what is pushed. Reason: nothing about a desk review is urgent;
the lock-out button shares the pull but goes on without it.

### The desk bootstrap: the agent does the whole desk setup before the lock

The laptop's coding agent writes every final value of the systems repository before the copy to the
desk: the project, the schedule, the backup address at the Git host, the provider address, and
`desk01`'s keys and addresses. Only the bootstrap connection differs, and only in the laptop's own copy,
which chapter 4 moves aside: MMX reads how it connects from the inventory and `ssh/desk01`, not from
`--var`, so the laptop's copy points `desk01` at its WireGuard address and laptop key while the desk's
copy keeps `127.0.0.1` and the self-management key.

The bootstrap, `mmx run systems_desk` from the laptop as root, does the whole desk setup before the lock:
the person's production key, the vault passphrase `/etc/systems-desk/vault-passphrase` (root:servers-mmx,
0640), the vault, which holds its own passphrase, the systems repository in the coding agent's checkout
`/home/coding-agent/systems_repository` with its first commit (`start-the-systems-repository`), the first
desk review recorded without a question, and the coding agent's door. Its normal end prints "The desk is
ready." and the production public key. Reason: before the lock, root SSH from the laptop works, so the
agent does every desk step itself, and the person's part is the accounts and the lock in
`ssh desk01-setup`. The first desk review is recorded without a question because the person has nothing
to compare it with, and the bootstrap ran this very desk playbook from the same repository.

**A desk that joins a team's repository,** a new member's or a rebuilt one, gets a copy of the laptop's clone
with its history. `start-the-systems-repository` sees the commits, starts nothing, and stops the bootstrap
until the team's vault passphrase is in `/etc/systems-desk/vault-passphrase`; the person writes it there from the
recovery bundle at a hidden prompt. So only an empty copy ever gets a new vault passphrase. A rebuilt desk also gets
the lost desk's production key from the bundle. Then the desk's checkout takes `origin`, the main copy on `util01`,
and resets to its `main`. The anchor is `util01` itself: its host key is in the repository's `ssh/known_hosts`, and
it lets in only a desk whose key a teammate's run, or the restored key, put in `root_ssh_public_keys`. A new member
starts from the Git host's backup only after the person checked its push activity, because the bootstrap runs the
desk playbook from that copy as root.

After inventory changes, the coding agent's `sudo -n update-this-desks-wireguard-peers` refreshes the desk's
server peers in `wg0`.

### The person reviews each change to the desk playbook

The coding agent pushes `main`, and the desk playbook applies `main` as root on the desk that holds the
person's production key, phone-code secret and tokens. A pushed role change could copy any of them.
So `review-and-apply-the-systems-desk-settings` compares what the desk playbook would do with what the person last reviewed.
Unchanged, it runs at once. Changed, it shows a diff and runs only after the person types `yes`.
Reason: the design accepts that the agent misuses production authority, never that it takes the person's
own key, phone secret or tokens. A review only on change keeps the friction to the rare desk-role change
and the server changes that need a desk review anyway.

What is compared comes from MMX: `mmx explain systems_desk --json` lists each node task of the run with
its resolved arguments and each template's rendered text. The command adds the content of files that
tasks copy unrendered (`file.source`, `apt_repository.signing_key_source` and similar), the inventory's
connection settings of the nodes the run connects to, and the SSH settings and known-hosts files they
name, because OpenSSH runs `ProxyCommand` and `Match exec` commands as root.
An `Include` line in those SSH settings stops the command, with the file and line, and asks for the
included settings in the file itself. Reason: an included file is outside the review, so once the person
approved an `Include`, a later change to the included file alone would run as root unseen. Following
each `Include` into the review was built first and dropped after the real desk playbook run: OpenSSH reads an
included file only when root or the user running `ssh` owns it, so for root's run of the desk playbook an included file
in the coding agent's checkout never works, and a root-owned file elsewhere could change after the review.
The lock-out button refuses an `Include` the same way. Line numbers and value
origins are left out. Reason: a fixed list of paths either misses an input, such as `ssh/config`, which
the run uses for `util01`, or asks on every unrelated settings change, such as a deploy's image tags.
Control and invisible characters are shown as escapes, so a pushed file cannot hide a line.
A file reached through a link that leaves the repository stops the command, because the target could
change after the review. The record is the reviewed view and its commit, in
`/var/lib/systems-desk/reviewed-desk-refresh/`, root-only, outside the coding agent's reach.
The view ends with the keys that the lock-out button's undo lets in, described below with the lock-out button.
The comparison uses the stored view rather than an old commit, so a rebase cannot lose it.

The check lives in a command the desk role installs, not in the playbook's first stage.
Reason: the playbook is pushed content, so a pushed commit could remove a stage that guards it;
a pushed change to the installed command shows in the review before it applies.
The command reads the answer from `/dev/tty` of the person's `sudo` session. The coding agent cannot
answer: it has no sudo rule for the command, its own processes run in a separate terminal
(`sudo -u coding-agent -i` gets its own pseudo-terminal), the person's terminal device is the person's
own, and the coding agent's login has no terminal of the person's.
A new or rebuilt desk's bootstrap records its first desk review, as above.
The lock-out button, `sudo lock-everyone-out`, runs as root on the desk too, so it follows the same rule.
The desk review installs root-owned copies of every file the lock-out loads except data, in
`/usr/local/lib/systems-desk/lock-everyone-out/`: `playbooks/lock_everyone_out.yml`, the
`everyone_locked_out`, `systems_desk_lockout` and `work_out_who_this_server_talks_to` roles, `server_management_scripts/start_break_in_lockout.py`,
`ssh/`, and the files the roles install on the servers from outside themselves: the WireGuard peer
template `roles/every_server/files/wireguard_wg0.conf`, the triage user's sudo rules
`roles/every_server/files/sudoers_triage` and `roles/util_server/files/sudoers_triage_mmwatchdog_fleet_readings`,
which the undo restores, and `mmhotline_settings.yml`, which the lock-out applies on `util01` without
the triage agent. The lock-out button builds a root-only run directory from the person's pulled repository with
each of those paths replaced by its reviewed copy, so only data comes from the pull: the inventory, which
names the desk that keeps access, today's servers and `connections_between_server_pools`, so a server added since the last desk review is still locked out,
`ssh/known_hosts`, the project settings and the vault. MMX runs no command from any of these. It refuses
a node whose `ssh_config` is not a reviewed SSH settings file, an `Include` in them, and a pulled link
that leaves the repository, because root would read or write through it in a directory the coding agent
can change. It opens the vault with the root-owned `/etc/systems-desk/vault-passphrase`, so it
needs no token file. Reason: an intruder who can push to the main copy must not get root on the desk,
or on every server, through the lock-out, and the lock-out must still work when a push is the way in.
Server-side content counts too: a pushed WireGuard peer, a wider triage sudo rule or a changed MMHotline
setting, such as `fleet_view_command`, which MMHotline runs as root, would otherwise reach the servers
through the lock-out itself. The cost: the lock-out button applies the MMHotline settings of the last desk
review, so the coding agent tells the person when a change touches a reviewed path, and the lock-out button
names each reviewed path whose pulled version differs, for the person to review after the incident.
`tests/desk_repository_and_lock_out_button_test.py` lists every file `mmx explain lock_everyone_out --json`
says the lock-out loads, in both states, and fails when one is neither reviewed nor data, so the list cannot drift.

The person's part is one command, `ssh -t desk01 sudo lock-everyone-out`. The coding agent prepares and
publishes the one-line inventory commit, and the lock-out button first fetches `origin` into the coding
agent's checkout, as the coding agent, and reads pushed `main` from it as data. When the fetch fails, because
`util01` does not answer within `PULL_TIME_LIMIT_SECONDS` (30), the lock-out button says so in
one sentence and goes on with the checkout as it is. Reason: a break-in must not wait for `util01`,
and the person checks the result in the list that follows. The desk review shares the same pull, but stops
when the pull fails, because nothing about a desk review is urgent.

The inventory is data, but the lock-out peers every server with the servers it names, so a server that an
intruder pushed with their own WireGuard key would join the private network through the lock-out
itself. So the lock-out button shows, at every press, every inventory node that is not a systems desk, one
line each, with its pools, its private address and its public address; then the desk that keeps access
and the desks that lose access; and asks for `yes` at the person's own terminal, in the same way and for
the same reasons as the desk review. Enter stops it with nothing changed. Control characters are shown as
escapes. Reason for a plain list rather than a difference from the inventory recorded at the last desk
review: desk reviews are rare, because a desk's WireGuard peers follow the inventory without one, so the
record would always be old, and the difference would grow with every ordinary server change; a short list
that the person reads each time shows a server they do not know just as well. The press shows no host keys:
`ssh/known_hosts` only says which host key to trust for a server that the list shows.
The keys the lock-out button lets in are checked against a record. The lock-out press admits only the key of
the desk that keeps access, from that desk's address; it reads `root_ssh_public_keys` from the project settings only
to check that the key of the desk that keeps access is in it, and installs no triage key. The undo, the press after
`everyone_locked_out_except_desk` is removed, installs every key in `root_ssh_public_keys` as root's
authorized keys and `triage_ssh_public_key` as the triage user's key on every server. So a key pushed before or during the incident
would be let in as root on every server by the undo itself. The desk review shows and records
those two settings in `lock_out_button_keys_view`, one line per key, sorted, and the lock-out button compares the
pulled settings with that record whenever its press lets them in on some server, by the switch's value
as MMX resolves it for each node. Unchanged, it goes on. Changed, it shows each added or removed key
with its comment and its fingerprint as `ssh-keygen -l` shows it, plus any options before the key, and
asks a second time at the person's own terminal; Enter stops it with nothing changed. The lock-out press asks
nothing about these keys, because it installs none of them. The other project settings the lock-out reads
let nobody in: the switch itself, whether app servers peer with each other, and where Cloudflare Access
sessions are revoked. `tests/desk_repository_and_lock_out_button_test.py`
lists the project settings `mmx explain lock_everyone_out --json` says the lock-out reads, in both
states, and fails on one that is neither compared nor listed as letting nobody in.
The lock-out button runs MMX as a child process, not in its place, so its last lines come after MMX's
result: a failed MMX run, and after a lock-out, how to undo it. Reason: the person reads the end of the
output first, and the undo after a false alarm is the next question. After a failed run it reads the run's
results: when the only failure is the desk's Cloudflare Access session revocation, it says that every server
was locked out and that the person revokes the sessions at Cloudflare; any other failure, or results it
cannot read, keeps the sentence that a failed server is a way in until isolated at the provider. That sentence
belongs to a lock-out only: a failed undo says that the server where it failed is still locked out, and a failed
press with no lock-out says that the server did not get normal access again; both say to fix the cause and press
again. A press
with no lock-out set and none recorded on this desk says it only applies normal access again, which matters
only after a lock-out press that stopped before its last stage, the one that writes the record, so it still
asks. Reason: such a press may leave servers locked out without the record, and stopping there would leave
the person no undo.
Its run history stays in the run directory's `.mmx`.
The other MMX runs during an incident, such as the `every_server` run that shows the status page and
the rebuild procedures' runs, are the coding agent's, with its button on the desk that keeps access,
`sudo -n -u servers-mmx run-mmx-on-the-servers ... --connection ssh_only`.
Reason: the lock-out cuts off the other desks and `util01` at the servers; it does not need to stop the
person's own coding agent, which the Stack trusts, and which reaches the servers only through that desk. An earlier version stopped the coding agent, its
buttons and the API proxy on the desk that keeps access and gave the person a separate MMX
command for the incident; that left the person alone with the incident's MMX work, in the hour when
the coding agent helps most. The evidence copy, `save_break_in_evidence.py`, needs root to read the desk's own logs,
so the desk review installs it beside the button's copies, and it connects with the reviewed SSH
settings beside it; the pulled repository supplies only the inventory and `ssh/known_hosts`.

### Bootstrap, phone code, and recovery

Chapter 3 (make your server account and your systems desk) creates the provider account and personal token before creating the first desk.
Reason: the first desk cannot create the provider account or supply the laptop's temporary bootstrap tools.
The laptop briefly holds the template, MMX, doubleshell, and provider credentials.
First-boot data enrolls only the laptop peer and selected bootstrap root SSH key.
Public SSH stays closed from first boot.
The bootstrap run closes root's remote access and can end with a warning, or with "node busy with job …"
while the desk carries on with the job; chapter 3 lists each end the person can see and says to rerun until the
laptop's root login is refused, and then to go on, because the first desk review finishes the playbook on the desk.
The "node busy" end was seen on the first run of every test desk. Cause: the test ran the
controller as a systemd service on the desk itself; the run's own `install_the_waiting_security_updates_on_a_new_server`
ran needrestart, which restarted every service with an old library, the controller's included. The job carried on
alone, and the rerun met it. A restart of `ssh.service` does not end an open SSH session, so a controller on the
laptop keeps its connection. A rerun that reaches the desk after the orphaned job finished stops with "The
phone code is missing …", which names the enrollment command; chapter 3 says so. The marker below stays the
signal: a desk where nobody enrolled must not pass a desk review.
The person immediately runs `set-up-the-phone-code`, saves the secret, scans the QR code, and confirms a real phone code.
Before enrollment, the permitted laptop key admits the person without a code.
Until a run of the desk playbook has finished once, recorded by its last task in
`/etc/systems-desk/first-desk-playbook-run-finished`, a missing phone code only prints how to enroll; after it,
a missing phone code fails the run. Reason: a rerun of an unfinished bootstrap run is still setup, and an earlier
version failed it before the person had the chance to enroll; after setup, PAM's `nullok` would otherwise let the
laptop key alone in without anyone noticing in the run.
MMX preserves the enrollment file's content and live rate/reuse state.
Reason: regenerating the secret during an apply would invalidate the person's phone and reuse tracking.

The desk accepts an SSH key plus a phone code on the WireGuard address.
Loopback root accepts only the separate self-management key.
The desk allows only laptop SSH, public WireGuard, loopback, established traffic, and essential host traffic.
LLMNR and multicast DNS are off.
Reason: a copied laptop WireGuard key must not reach unrelated network services.
sshd starts after `wg0`, so a reboot preserves the private phone-code door.

Rate limiting permits three attempts per 30 seconds; codes cannot be reused.
Reason: 30 seconds is one code's lifetime, so a guesser gets three tries per code shown and the person, who types one code, never meets the limit.
The ban counts wrong codes over a fixed ten minutes (`findtime = 600`): long enough that a guesser who paces tries under the rate limit is still counted,
short enough that a person's typos on separate occasions never add up; `phone_code_lockout` already lets a team make the lockout stricter or looser.
The desk installs GnuPG, so the coding agent prints a vendor's apt signing key's fingerprint before the key enters a role.
`phone_code_lockout` in `mmx_project_settings.yml` sets the lockout: by default, 5 failed attempts within ten minutes ban the laptop address for 5 minutes.
Reason: five tries keep a typist from locking themselves out, and five minutes lets a lockout end quickly while a thief still gets few guesses an hour.
One wrong code is an `info` alert; the lockout sends one alert with `alert_severity_when_a_laptop_is_locked_out` (`info`, `warn`, or `sos`; `sos` wakes the person on call).
The ban and the alert count wrong codes for the person and for `coding-agent` alike.
Reason: both log in with the laptop key and the one phone code, so a thief with the laptop can guess as either.
Debian's ordinary sshd jail and OpenSSH source penalties are disabled.
Reason: the documented ban rule must own the refusal timing.
A typo, reused code, and rate limit show the same authentication refusal; a ban shows connection refused.
One code opens one connection per 30-second step; the coding agent's shared login carries all its commands.

MMWatchdog joins from the desk's full playbook after `util01` is configured.
The first rejected-code reading opens one incident per burst; the opening reading's count is not a running total.
Reason: a brute-force burst must not overwhelm the person with repeated alerts.
A missing enrollment file also warns.

Recovery rests on one recovery passphrase in the password manager. It opens the recovery bundle,
`recovery_bundle.age`, in the systems repository, with a copy in the locked backup bucket: the vault
passphrase, the first desk's production and WireGuard private keys, the console password, the phone code's
emergency codes, the server provider credential, the desk's Cloudflare token (and staging's access token), the backups' passphrase, and the read-only Backblaze key that restores them, never the master key. The phone code's secret itself stays
only on the desk. The desk's SSH host keys are not kept. A rebuilt desk makes new ones under a new desk name, and
the laptop enrolls them over the WireGuard route as for a first desk. Reason: only the machine holding the
restored WireGuard key answers at that address on that route, so the check needs no saved host key.
The root-only self-management key can be generated again.
The rebuild runs in this order: the host key is enrolled before the bootstrap, because the bootstrap's
`ssh/<desk>` pins it; it is read with `ssh-keygen -F`, because Debian's laptop SSH settings hash host names;
the laptop's rename commit travels to the desk inside the copy's history; the bootstrap stops for the vault
passphrase; the person restores the production key and the vault passphrase from the bundle; the bootstrap
finishes; the checkout takes `origin` and publishes the rename. Reason: a solo person has no other desk to push
the rename from, and the restored key is already in `root_ssh_public_keys`.
A teammate's desk is not in the bundle, so a lost teammate desk is replaced as a new member's desk, and the old
one leaves as a leaving member's does.
A new phone gets the alerts by signing in to the person's Pushover account, so nothing in the vault changes;
a stolen phone is deleted from the account's devices. The person then logs in with one emergency code and
makes a new phone code with `set-up-the-phone-code`; the new emergency codes replace the old ones in the bundle.
A lost laptop gets fresh laptop keys and a replacement desk; deleting the old desk revokes the stolen laptop's door.
The person also replaces the personal provider token, because the laptop held it during setup.
Changes to the bundle and the vault by hand run as the person, with MMX on a copy in the person's own folder,
which root then installs into the checkout. Reason: MMX never runs as root on the pulled checkout on a desk.

### The coding agent and personal credentials

The coding agent runs on the person's laptop and reaches the desk as `coding-agent`
([One coding agent, on the laptop](#one-coding-agent-on-the-laptop)). No coding agent is installed on the
desk. Reason: protection uses Unix file ownership on the desk, independent of a particular agent's sandbox
settings, and the person's own agent already holds the app's code and the conversation.
The persistent production SSH socket permits production login and pushes to the main copy without exporting the private key.
The relay passes the whole agent protocol on, so `ssh-agent` starts with `-P /nonexistent/*`, a pattern
that matches no file: the agent refuses to load any PKCS#11 or security-key library a relay client names.
Reason: a library loaded in the person's agent runs as the person, who has sudo. The desk key is a plain key file.
The production private key stays in the person's protected home.
The desk's login profile, `/etc/profile.d/desk-buttons.sh`, gives each account its agent: the coding agent the
relay socket, and the person the private socket. Reason: the person's SSH login from the laptop brings no
agent, and the person's own SSH from the desk, such as to a server during an incident, needs the production
key.

`sudo -n -u servers-mmx run-mmx-on-the-servers` runs MMX as the separate `servers-mmx` account.
The button fetches pushed `main` into a private execution checkout and keeps MMX history there.
The button uses the actual committed production inventory and settings, with desks excluded.
Reason: running MMX as the person would let a committed absolute `file.source` read personal keys from the controller.
The button's vault passphrase is `/etc/systems-desk/vault-passphrase`, root:servers-mmx, mode `0640`.
The button runs only an allow-list of MMX commands and options. Of the `secrets` commands it runs `set`, `add-random`,
`list-keys`, `diff-keys` and `usage`, and refuses `--vault`, `--vault-password-file` and `--new-vault-password-file`.
Reason: `secrets edit` opens an editor on the decrypted vault, `secrets show` prints a secret, `secrets pipe-to` runs any program with a secret on its input, and `describe-module` opens a pager, which put vault secrets on the
coding agent's screen, and a run must not point at another vault by mistake.
No account on the desk accepts the production key that the button's runs offer: sshd admits only root from
loopback, with the root-owned self-management key alone, and the person and `coding-agent` from elsewhere, with a
laptop key and the phone code. Reason: a pushed inventory or `ssh_config` can name the desk under any address or `HostName`,
and a run of the button must not log in to the desk by mistake.

The API proxy supplies provider and Cloudflare authentication through loopback ports 8081 and 8082, from root-only token files. It is the desk's one program for this job. Reason: nginx, the alternative for the providers that take a token in a header, needs `proxy_http_version 1.1` and a deep enough `proxy_ssl_verify_depth` to reach Hetzner, Scaleway or Vultr, and one program already signs requests for the others. Go's HTTP client speaks HTTP/1.1 or later and verifies with the system's certificate store, and one program means one set of behavior for every provider.
`systems_desk_provider_api_url` selects the provider's HTTPS base URL, including a trailing slash.
The provider proxy on 8081 refuses, with the plain message "this would change your desk itself; the desk is managed by its own guide", any request other than GET whose path has the desk's own server ID or provider-side name as a segment, or whose query or body names either (a JSON value, or a form value such as AWS's `InstanceId.1`). The ID is `provider_server_id` in the desk's entry of `inventories/servers.yml`, from the create receipt; the desk playbook writes it, root-owned, to `/etc/systems-desk/desk-server-id`, and systemd hands it to the proxy. Reason: a cleanup must never delete or rebuild the desk by mistake. The name is `provider_server_name` beside the ID, written to `/etc/systems-desk/desk-server-name`, for providers that put a name in the path (an OVHcloud VPS service name, a Google Cloud instance name); it is checked only when recorded.
`systems_desk_provider_api_authentication` says how the credential reaches each request: `token_in_a_header`
(Hetzner, DigitalOcean, Vultr, Scaleway; Scaleway's token file sets `X-Auth-Token`, the others set
Authorization), where the proxy adds the token on 8081, or one where it signs the requests on 8081; 8082 is always Cloudflare:
`ovhcloud_signed_requests` (OVHcloud), `aws_signed_requests` (AWS EC2) or `google_cloud_service_account_tokens`
(Google Compute Engine). The desk role refuses any other value before it changes anything.
`set-up-outside-services personal-token server-provider` sends the typed credential only to one of the
provider guides' API addresses for that setting, and names the address before the prompt.
Reason: anyone who can push to the main copy can change the setting, and the person's token must reach only the provider.
The desk review shows a change to either setting before a proxy uses it.

**The API proxy.** Three providers' APIs need more than a fixed header. OVHcloud's signs each request
with the application's secret: SHA-1 over the secret, the consumer key, the method, the whole URL, the body and
OVHcloud's own time, in `X-Ovh-*` headers (OVHcloud's "First steps with the OVHcloud API"). AWS signs each
request with Signature Version 4, an HMAC-SHA256 chain from the secret access key over the date, the region and
the service, over a canonical form of the request and its body. Google Cloud takes an access token that lasts an
hour, which a JWT signed with the service account's RSA key buys at Google's token address. A proxy that only
adds a header can do none of these. The API proxy is a small part of `set-up-outside-services`,
`set-up-outside-services run-the-provider-api-proxy`, which `provider-api-proxy.service` runs.
It listens on `127.0.0.1:8081`, the address the coding agent uses for the provider at every provider, reads
the whole request, signs it with the credential, and forwards it to the one API address in its credential file;
the answer, its status and its headers, such as a pagination cursor, go back unchanged.

- The credential file, `/etc/systems-desk/provider-api-signing-credential.json`, is root:root, mode `0600`, and
  holds the setting's value, the API address and the joined token. systemd runs the proxy under an account
  of its own (`DynamicUser`) and hands it a copy through `LoadCredential`, which only that account reads.
  Reason: the coding agent uses the credential without reading it, so a mistake or a leak of its conversation
  never carries the credential, and the proxy itself needs no file permissions of its own to keep right.
- The proxy refuses a credential file whose API address is not one of the provider guide's (the same list
  `set-up-outside-services` checks before it writes the file), a request target that is a whole address
  rather than a path, and a path with a `..` segment. It drops any `Authorization`, `Cookie` and `X-Ovh-*`
  header the caller sent and the headers that belong to one connection, and passes a redirect back without
  following it. Reason: the signed request must reach only OVHcloud's API, and OVHcloud checks its access
  rules against the path as signed; a redirect followed would send the signed headers to another host.
- It reads OVHcloud's clock once from `/auth/time` and keeps the difference, as OVHcloud's own client
  libraries do. Reason: the desk keeps its clock with the network time service, so the difference stays put.
- It sets no time limit of its own: the caller's time limit ends a request, and a closed connection cancels it.
- Every provider the proxy serves is one entry of one table, `requestSigningMethods` in
  `set_up_outside_services/provider_api_proxy.go`, keyed by the setting's value, and one code path reads
  it: the proxy, `personal-token` and `secrets` never branch on the provider. Reason: a branch per provider
  spread through three commands is how one of them gets missed. Each entry holds:

  | Entry | How the person enters it | API addresses the credential may reach | What the proxy adds |
  | --- | --- | --- | --- |
  | `ovhcloud_signed_requests` | Application Key, Application Secret, Consumer Key, each at its own prompt, joined with colons | `https://api.us.ovhcloud.com/1.0/`, `https://eu.api.ovh.com/1.0/`, `https://ca.api.ovh.com/1.0/` | `X-Ovh-*` headers with the SHA-1 signature, at OVHcloud's time |
  | `aws_signed_requests` | Access key ID and Secret access key, each at its own prompt, joined with a colon | `https://ec2.REGION.amazonaws.com/`, any region | `Authorization` with Signature Version 4 for the service and region of the address's host, and `X-Amz-Date` and `X-Amz-Content-Sha256` |
  | `google_cloud_service_account_tokens` | The service account's whole key file at one prompt, read until its JSON closes, kept in base64 on one line | `https://compute.googleapis.com/compute/v1/`; paths under `/cloudbilling/` go to `https://cloudbilling.googleapis.com/` | `Authorization: Bearer` with an access token for the scopes `compute` and `cloud-billing.readonly`, made at `https://oauth2.googleapis.com/token` and kept until a minute before it expires |

  The AWS entry takes its region and service from the address's host, so one credential file serves one region,
  the system's, and an address of another form is refused before anything is sent. Reason: the same check as
  the guides' addresses above; EC2's address names the region, so a list of every region would only go stale.
  Google's key file is pasted whole because Google gives only the file; base64 keeps it within the characters
  the token file and the vault take. The proxy refuses a key file whose `token_uri` is not Google's, because the
  signed JWT is itself a credential for an hour. Google's scopes are the narrowest that let the scripts create
  servers (Compute Engine has no narrower scope that writes) and read prices; the service account's role decides
  the rest. The price catalog is a second address of the same provider, reached under its own first path
  segment, so the coding agent's address stays `http://127.0.0.1:8081/`. Errors name the provider's refusal and
  never print a secret: a token address's refusal gives Google's error and description, never the JWT.
- The proxy drops the caller's `X-Ovh-*`, `X-Amz-*` and `X-Goog-*` headers as well as `Authorization`, so only
  the signer sets them. The Stack's tests check AWS's signature against AWS's published example (the GET Object
  example of Amazon S3's "Signature Calculations for the Authorization Header"), and Google's token request with
  a stand-in token address that verifies the JWT with the key's public key; a test against the real providers had EC2
  in `eu-north-1` and Compute Engine accept the proxy's requests.
- At AWS and Google Cloud, as at OVHcloud, `util01` needs no proxy: the guides' request functions sign in the
  shell, AWS's with `curl --aws-sigv4`, and make Google's token with `openssl` and `curl`, once per script.
  Reason for `curl` over AWS's and Google's own command-line tools: each tool is a large separate download with
  its own version to pin and review on `util01`, the desk and the laptop, while `curl`, `awk` and `openssl`
  are on every machine. EC2 answers in XML, which a short `awk` reader in the AWS guide turns into JSON.
- The unit names the release's own path and, for a provider that takes a token in a header, the provider's
  API address (`--provider-api-url`), so a new release or a new address restarts the proxy. The proxy checks
  that address against the provider guides' list, because the unit's address comes from
  `mmx_project_settings.yml`, which the coding agent can push. The unit hands the proxy the Cloudflare token
  file and the provider's token file or credential file (`LoadCredential`), and the proxy runs only while all
  of them exist, so neither port answers without its token. The proxy listens on both ports before it serves
  either, so a port in use stops the service at once. The desk role removes nginx (`apt_package` absent,
  with its settings) before the proxy starts, so an earlier desk's nginx lets go of 8081 and 8082 first.
  `check_which_program_serves_the_api_ports` fails the run unless the proxy listens on both ports, or nothing
  does while a file is missing. Reason: a program that holds a port keeps running without the proxy, while
  systemd and MMX report the start as a success.
- The desk keeps only the provider credential its setting uses: with `token_in_a_header` the desk role
  removes the proxy's credential file, and otherwise the proxy's
  `provider-api-token.conf`. The proxy gets the new provider's token when the person runs
  `personal-token server-provider` for it. Reason: after a move to another provider, a working credential for
  the account the team left would otherwise stay on the desk, unused and forgotten. The credentials
  themselves are deleted at the old provider when the move ends ("Move the servers to another provider").
- `SERVER_PROVIDER_API_TOKEN` keeps one name at every provider: at AWS it holds the two values joined with a colon,
  and at Google Cloud the key file in base64; at OVHcloud it holds the Application Key,
  Application Secret and Consumer Key joined with colons, and the commands that take it ask for each value
  at its own prompt under OVHcloud's own names. `util01`'s `util01_provider_api_token` has the same form, so
  the restore drill, the leftover check and the triage agent's server replacements pass it to the same three
  provider scripts as at every provider. Where it is set, the scripts sign in the shell with `curl` and
  `sha1sum`; on a desk, where it is not, they send the request unsigned to the proxy
  (`provider_guides/ovhcloud_public_cloud.md`, "The provider scripts' request function"). `util01` therefore
  needs no proxy and no program beyond Debian's.
- Each person makes their own OVHcloud credential from a link that fills in the access rules for the one
  Public Cloud project, with validity Unlimited, named after the person, and `util01` gets its own with
  narrower rules. A leaving person's credential is deleted by its name, as for Cloudflare's tokens.

Candidates weighed: OVHcloud's newer service accounts give an OAuth2 bearer token that a proxy
adding a fixed header could carry, but the token lasts an hour (`expires_in: 3599`), so a root job would have to fetch
a new one every hour with the service account's secret and rewrite the proxy's file, and the person would set up
an IAM policy by hand; that is more moving parts than signing, and it would not serve AWS, whose Signature
Version 4 signs each request. A sudo button that signs one request in Bash was the other candidate; it would
give the coding agent a different shape (a command, not the address it uses at every provider). AWS (Signature
Version 4) and Google Cloud (a service account key traded for short-lived tokens) became entries in the proxy's
table, each with its credential entry, its addresses and its signer, with no change to the proxy's shape.
Candidates weighed for them: one table read by one code path (chosen), or a proxy program per
provider, each with its own unit; the second would repeat the listener, the unit, the desk role's order on
8081 and the credential checks three times.
The Stack's own to-do list is "Not in this version's template yet" in `skills/monkeymaxxing-stack/SKILL.md`.
Production servers retain account-owned tokens; the desk alone holds the person's tokens.

The coding agent can still misuse granted production authority and read production vault secrets,
including the passphrase needed by the MMX execution account.
Committed playbooks leave a Git record; ad hoc MMX commands leave MMX history.
Direct SSH commands are not automatically recorded in Git or MMX history.
Malware controlling the laptop while the coding agent's shared login is open can act through that login.
Reason: the desk reduces lasting personal-key theft; the desk does not remove authority required for production work.

### Several people

Every desk uses `main`. The order is edit on the laptop, commit on a branch, push the branch to the desk,
publish it with `publish-branch-to-main`, which shows incoming commits, then run.
On a conflict, `publish-branch-to-main` changes nothing and names the files; the coding agent tells the person,
and never resolves the conflict.
Before a big change, the person announces the work in the team's chat.
The same synchronization rules apply to a solo person.
Reason: every run applies the full pushed branch, including colleagues' changes.
The existing lock on `util01` keeps the helper's, the timers' and MMHotline's production runs sequential; the desk's button is covered by the live-port assertion in the `app_server` role.

## Responding to a break-in

`operating_procedures/respond_to_a_break_in.md` is a guide by case: the coding agent and the person first find
out how the intruder got in, then follow that case's section. The break-in through the app comes first and is the
fullest, because it is the most common, and it keeps every desk, `util01` and the triage agent working.
The lock-out is only for the narrow cases the page names: `util01` or the triage agent is suspect, an unknown root
login, process or MMX run is on the servers, or a desk or a kept credential is suspect and nobody knows which.
Reason: in every other case the lock-out cuts off the people and agents the team needs and closes none of the ways
in, so it harms more than it helps. Steps 0 through 7 remain the lock-out route and the shared steps.
A person starts containment from a trusted desk. The triage agent cannot press the lock-out button.
The password manager holds the prepared contact and notification questions.
Reason: an incident needs a practiced order, without decisions about tools during the incident.

Inventory `vars.everyone_locked_out_except_desk` names the only desk retaining production access.
The project default is an empty string. Removing the inventory setting undoes containment.
Each desk's `vars.production_ssh_public_key` identifies the production key to retain.
The normal `root_ssh_public_keys` list remains the unlocked list, including util01's controller key.
Reason: key comments cannot reliably identify a desk. A Boolean cannot identify the surviving desk.
The explicit mapping avoids replacing all existing key ownership with a new registry.

The `everyone_locked_out` role owns server containment. `lock_everyone_out` applies containment
without rebuilding the application. The normal base role consumes the same state on every run.
Role calls within roles are enabled so the button and ordinary base runs share admission tasks.
The button first uses ordinary SSH from the desk that keeps access, before MMX requests a server job.
Reason: an active MMX task owns node admission and survives its original SSH transport.
The initial SSH step restricts admission and peers, closes untrusted sessions, and ends the active
MMX worker and its descendants by the job ID and the inode of the worker's held lock.
The normal role then reapplies the declared state. No process-name pattern selects a process.
Independent servers start containment concurrently. A 45-second per-server deadline prevents
an unresponsive server from delaying every server, and names the server requiring provider isolation.
The initial SSH step keeps the production key of the desk that keeps access, `/etc/systems-desk/production_key.pub`,
and its own WireGuard address, from `/etc/wireguard/wg0.conf`, not values from the pulled repository.
It also derives the desk's own WireGuard public key with `wg pubkey` from `/etc/wireguard/wg0.private_key`.
When the inventory's `production_ssh_public_key`, `private_ip` or `wireguard_public_key` for the desk that keeps access differs, the step fails
and the run stops before MMX changes a server. Only exit code 3, some servers failed and are named, lets
the run go on, to the final report. Reason: the later MMX stage writes the inventory's values on every
server, and a pushed key there would keep root for whoever holds it.
Every press, the undo included, first runs the same script with `--check-only` in the playbook's first fleet stage,
on the desk that presses, before any stage that changes a server: the desk must be in the inventory and in
`systems_desks`, the inventory's address and keys for it must be its own, and `root_ssh_public_keys` must hold its
production key line. Otherwise the run stops with nothing changed and names what to correct.
Reason: an undo from a desk whose key a commit had already removed from
`root_ssh_public_keys` writes the new keys on the servers, loses its own SSH partway, and leaves every server
locked, with only the provider's rescue system to recover them (seen in a test on real servers). The press's own desk is the only desk the servers
admit during a lock-out, so a press that cuts it off can never be finished from a desk.
So a desk that was the way in, working alone, keeps its key until the undo has run and the fresh desk has joined;
the fresh desk then removes the old key, and its `every_server` run makes `util01` stop trusting it. With a
teammate, the teammate's desk runs the undo, and one commit adds the fresh key and removes the old one.
`operating_procedures/respond_to_a_break_in.md` gives both orders and the rescue-system recovery for a press that
stopped partway for another cause.
Reviewed SSH host keys are copied to root-owned files on the desk that keeps access. The helper uses the private
person-owned agent socket. Reason: a node task runs outside the repository directory.
Production keeps only the named desk's root key, restricted to that desk's WireGuard address.
SSH admission also restricts login to root from that address. Every other desk peer disappears
from both the saved WireGuard configuration and the running interface.
Established SSH transports and their login sessions end unless they came from the desk that keeps access.
The triage account loses keys, sudoers and running processes. MMHotline's settings omit the triage agent.
A root-owned marker and systemd conditions stop triage socket activation across service restarts and reboot.
Reason: killing one run must not let the socket immediately create its replacement.
Reason: deleting keys alone leaves authenticated sessions alive. util01's root key must also lose admission,
because an old automation request must not provide a second route into production.
MMHotline's alerts, the fleet hub, backups, tunnels, apps, replication and database logins keep running.
Containment is applied from the desk that keeps access over SSH, rather than from the controller being cut off.

On the desk that keeps access, the lock-out changes nothing for the person, the coding agent's login, its
buttons or the API proxy. The button leaves one root-owned file there,
`/etc/systems-desk/everyone-locked-out`, which says that the person pressed the lock-out button on this
desk; the undo removes it. Only `playbooks/lock_everyone_out.yml` writes or removes the file.
Its first line holds the desk that keeps access, that desk's `private_ip`, `wireguard_public_key` and
`production_ssh_public_key`, separated by spaces, from the inventory at the press. The press writes
it only after the initial SSH step has checked the address and both keys against the desk's own files, as above.
`run-mmx-on-the-servers` passes that first line to `every_server` as `lock_out_button_record_on_this_desk`,
empty when the file does not exist, and refuses the variable from its caller. The first three tasks of
`every_server`'s `every_server` fleet stage refuse the run, with nothing changed:
when `everyone_locked_out_except_desk` is set and the variable is empty;
when `everyone_locked_out_except_desk` is set and the variable differs from the same four values that
the pushed inventory gives now, so a different desk, address or key;
and when the setting is empty and the variable is not.
Reason: only the person starts, changes or undoes a lock-out. `every_server` applies the lock-out
state on every run, because a server added during the incident must get it too, so a pushed inventory
line alone would otherwise lock everyone out through an ordinary run, from any desk or from `util01`,
with no person involved; a pushed change to the named desk or to its address or keys would hand the
servers' admission to another desk or key without the button's comparison with the desk's own files;
and a pushed removal would apply the undo, whose keys the button compares, without the button.
A desk without the record passes the undo check, but during a lock-out no desk but the desk that keeps
access reaches the servers: SSH admits only that desk's key, from that desk's address. To change the
desk or keys that keep access, the person presses the button again on that desk, which checks the
new values and rewrites the record. The checks sit in the playbook because every way it runs passes there: the desks'
button, `util01`'s helper and timers, and MMHotline's runs. They are the first tasks of the fleet stage
that applies the lock-out, not a fleet stage of their own, so `--only-fleet-stages` and `--limit` keep
them. A variable that the button command sets is the one fact a playbook cannot read otherwise: which
desk runs MMX. The other fleet stages that read the setting, `util_server` and the two that write
MMHotline's settings, change only the triage agent's access, and a full run leaves a server that failed
the checks out of them. `util01`'s daily server settings comparison reads from `mmx explain` whether the
first check runs, and during a lock-out ends with a message instead of a failed unit that would warn.
Undo also starts an existing MMX HTTPS service. Reason: restoring SSH keys alone
does not restart the management listener stopped during containment.
No desk connects to another desk. Other desks retain their local sessions and their coding agents' logins.
Every desk runs its own desk playbook during a lock-out too. Reason: a new desk joins during a lock-out with a
teammate, and a desk playbook manages only its own desk, over loopback, while a cut-off
desk reaches no server. The lock-out button itself runs only on the desk that keeps access.
Reason: production revokes admission; personal desks have a loopback-only management boundary.
Provider snapshots preserve suspect desk disks before provider power-off. Company-side revocation
ends copied personal tokens and company sessions, which removing a WireGuard peer cannot revoke.
The button cannot make an already compromised root host trustworthy. Rebuilding remains required.

`send_app_requests_to_the_status_page` is independent of the lock. Caddy redirects public app requests
to the configured public status-page URL with a temporary redirect and `Cache-Control: no-store`.
The redirect applies to every path and method. Setting the switch false restores app routing.
`status_page_host_name` supplies both MMHotline's status page and Caddy's redirect.
`cloudflare_account_id` supplies both the MMHotline-down alarm and the desk's Access session revocation.
Reason: each company address or account has one configured value.
The desk's existing Cloudflare token has Access Apps and Policies Edit permission.
The button uses that token to revoke sessions only for the configured private Stack applications,
including staging when staging exists. Other account applications are left alone.
Company memberships, personal tokens, other account sessions and copied credentials still require the checklist.
Cloudflare's [revocation API](https://developers.cloudflare.com/api/resources/zero_trust/subresources/access/subresources/applications/methods/revoke_tokens/)
accepts that existing permission. Failed API calls are reported after local containment completes.
Reason: a redirect uses the independent status page even when the app is unsafe to run.
A proxy would keep the request on an app host name and can break the status page's relative links.
Every caller of the Caddy role passes the switch, including deploy and server removal.

Evidence collection streams the retained journal, authentication and web logs and MMX run records
from each reachable server to a protected directory on the desk that keeps access. The logs of the desk that keeps access are included.
The archive records missing paths. Every archive gets a SHA-256 checksum and a second copy
in the production backup bucket before investigation or replacement.
The desk reads the bucket-scoped identity from a database server's pgBackRest settings into memory.
The desk encrypts each archive with the existing backup passphrase, using OpenSSL AES-256-CBC,
PBKDF2 with 200000 iterations, and SHA-256, then signs S3 PUT and GET requests.
The downloaded encrypted bytes must match the local checksum. A manifest records both archive
and encrypted checksums, object keys and failed servers. The upload credential values stay in memory,
without command arguments or new credential files.
Reason: the native pgBackRest command set has no documented general file upload command.
Using the current bucket identity avoids a new account or secret, while encrypted archives protect log contents. An unavailable server is
reported as a failure, never silently omitted. Other desks' evidence comes from provider disk snapshots.
Reason: streaming avoids a new evidence directory on a suspect server and preserves the logs already kept.
Evidence has sensitive contents, so archives stay private and never enter Git.
