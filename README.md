# The Monkeymaxxing Stack

**Agent-first server systems, maxxed for monkey/human understanding.**

The Monkeymaxxing Stack is a full production system for web services: web
apps, websites, and APIs, from a first product to a company's heavy
production traffic. Your coding agent, such as [Claude Code](https://claude.com/claude-code) or [Codex](https://openai.com/codex/),
builds the system in about a day and then runs it. Everything is in your own
accounts, on plain Linux servers that cost 10 to 30 times less than
hosting at a platform such as Heroku.

## What you get

- Maxxed for monkey/human understanding
- Built and run by your coding agent (Claude/Codex)
- Ruthlessly simple (plain Linux, Postgres, SSH)
- Convention over configuration (no decision fatigue)

**Cost and getting started**

- Hosting 10-30x cheaper than Heroku, Railway, Replit, etc.
- Fully open source (Apache 2.0)
- Set up in about a day
- Migration guides for 19 platforms (Heroku, Railway, Replit, Vercel, etc.)
- Guides for 11 app frameworks (Rails, Django, Laravel, Next.js, etc.)
- Runs on any Linux VPS or bare metal
- No lock-in (switch server providers anytime)

**Deploys and scaling**

- Zero-downtime, health-checked deploys
- Every change is a commit (infra as code, fully auditable)
- Runbooks for the common events (add a server, lost laptop, database restore, etc.)
- Autoscaling app servers (you set the limits)
- Planned scaling path (each step triggered by real load)
- Scales to thousands of servers
- Automatic database failover

**Security**

- No open web ports (everything goes through Cloudflare)
- Encrypted private network between servers (WireGuard)
- Compromised-laptop protection (no production keys on laptops, 2FA login)
- Break-in response guide (with an emergency lock-out button)

**Alerting**

- Monitoring and alerting built in
- Your agent triages alerts first, wakes you only if needed
- On-call scheduling
- Offsite dead man's switch (alerts you even if every server is down)
- Offsite status page that stays up even if every server is down

**Backups**

- Offsite database backups, restore-tested every week
- Deletion-proof backups (even you can't delete them for 14 days)
- Restore the database to any minute
- Offsite backups of user uploads (images, docs), also deletion-proof

You do not need to be a systems engineer to get all of this. Your coding
agent builds it with you in about one working day and explains each step as
it goes, so a startup founder or a developer who is new to running servers
ends the day with the whole system and understands it.

Your team owns every account, every server, and all the data.

To see the Stack at work, the
[app framework examples](docs/app-frameworks/README.md) are working apps
made for the Stack, in Rails, Django, Laravel, Next.js, Go, and other
frameworks. Each example has a guide and a test record.

## The Monkeymaxxing tools

The Stack is built from the free, open-source Monkeymaxxing tools for
running simple server systems.

| Tool | What it does |
|---|---|
| [MMX](https://github.com/monkeymaxxing/mmx) | Sets up your servers, and makes every later change to them |
| [MMWatchdog](https://github.com/monkeymaxxing/mmwatchdog) | Watches your servers, restarts what fails, and alerts you |
| [MMHotline](https://github.com/monkeymaxxing/mmhotline) | Gets each urgent alert to the person on call, and can let your coding agent investigate first |
| **Monkeymaxxing Stack** (this repository) | Instructions for your coding agent that build and run a whole production system with the three tools above |

Each tool also works by itself. The Stack is the three tools put together
with a Postgres database, backups to Backblaze B2, a WireGuard private
network, Cloudflare in front of the servers, and a tested procedure for
each job. You do not need to learn the tools first: your coding agent installs
and runs them.

## Why the Stack

### Why a tested system instead of one that your coding agent invents

A coding agent can put a web app on a server in an hour. You ask, and you
get a server, a database, and a site that answers. The site works, so
nothing shows you what is missing. A system that is made this way can leave
these questions open:

- Do the backups restore? Nobody knows until somebody restores one.
- Who hears about it when the site stops at 3 AM?
- What can an intruder reach who breaks into the app? Can the intruder
  delete the backups?
- What did the agent change on the server last month? Could you build the
  same server again?
- What happens when one server is not enough?

The Stack gives every team the same answers. The Stack's own tests check
the first five answers below on real servers:

- **Alerted.** MMWatchdog checks every server, and MMHotline wakes the person
  on call, by default with an emergency alert on the phone through Pushover.
  During
  the setup, you test that an alert reaches your phone.
- **Recoverable.** The database backups go to a separate storage provider
  (Backblaze B2), where Object Lock stops anyone from deleting a backup
  for 14 days by default. Every week, a restore drill restores the backups
  onto a temporary server and checks the data.
- **Secured.** No server has an open web port. The servers accept SSH logins
  only from your team's systems desks and from the utility server. An
  intruder in your app cannot delete or change the stored backups.
- **Recorded.** Every change to the servers is a commit to your systems
  repository, a Git repository at your own Git host. Your coding agent can
  build the servers again from the systems repository and the backups.
- **Scalable.** The system grows by tested procedures that your coding
  agent follows, such as "Add an app server". Each procedure waits for its
  trigger: a measured warning or an event, such as your first paying
  customers.
- **Understood.** At each step, your coding agent says what it does, why,
  and what it needs from you. The setup ends with an operating guide for
  your own system.

### If you were thinking of Kubernetes

Many people take [Kubernetes](https://kubernetes.io/) for a complete system for running production
servers. Kubernetes covers one part of that work: it runs containers on a
group of servers and adds or removes containers with the load. Kubernetes'
own documentation says what Kubernetes leaves to you, under
["What Kubernetes is not"](https://kubernetes.io/docs/concepts/overview/)
(read on 2026-11-15). Kubernetes:

- "operates at the container level rather than at the hardware level";
- "does not provide application-level services, such as ... databases";
- "does not dictate logging, monitoring, or alerting solutions";
- "does not provide nor adopt any comprehensive machine configuration,
  maintenance, management, or self-healing systems".

So with Kubernetes, your team still decides and builds the database and its
backups, the alerts and who is woken, the servers' own setup and updates,
and how people log in. The Stack covers all of these.

The Stack also does the work that Kubernetes does for a web service. A new
release starts beside the old version, and takes the requests only after it
passes a health check. The requests are spread over all app servers. When
your team lets the triage agent do server work, app servers are added when
the load grows and removed when the load drops. The Stack does this work
without a cluster to operate: the servers are plain [Debian](https://www.debian.org/) servers, and a
coding agent follows a tested procedure for each job.

If your app runs on Kubernetes now, the guide
[Move from Kubernetes](docs/app-platform-migrations/from-kubernetes.md) has
the steps.

### If you use a hosting platform

A hosting platform, such as [Heroku](https://www.heroku.com/), [Render](https://render.com/), or [Fly.io](https://fly.io/), runs your app on the
platform's own system. The Stack gives you a system of your own, and it is
better in three ways:

- **It costs far less.** For the same size of server, a platform charges 10
  to 30 times more than a server provider such as Hetzner or OVHcloud. An
  always-on server with 2 vCPU and 4 GB of memory costs €5.99 a month at
  Hetzner, and $5.35 a month, month to month, as an OVHcloud VPS in the US.
  The same size costs $85 a month at Render and $150 a month at Heroku.
  These prices are from each company's pricing page or catalog, read
  between 2026-11-13 and 2026-11-17.
- **You are not locked in.** The servers are plain Debian servers at a
  server provider that you choose, such as Hetzner or OVHcloud. If the
  provider raises its prices, your coding agent rebuilds the system at
  another provider from your systems repository and your backups. A
  platform's customer can only pay the new price or move the whole app.
- **It is yours.** The database is your own Postgres, which you can log in
  to. The backups are at a separate storage provider (Backblaze B2), and you
  have proof that they restore. The alerting, the on-call schedule, and the
  security in the list above are part of the system, not extra products.

The [app platform migration guides](docs/app-platform-migrations/README.md)
have the steps for a move from Heroku, Railway, Replit, Vercel, Render,
Fly.io, and other platforms.

## One shape, from three servers to thousands

A Stack system has one shape, and the shape never changes. Requests come
in and are spread over the app servers. The app servers use the database
servers. Each kind of server is a **pool**: the servers that share one job.
A system of servers in pools is called a **fleet**.

```text
              your users
                  |
              Cloudflare
                  |
   app servers        app001, app002, ...
                  |
   database servers   db01, db02, ...

   utility server     util01: the tools that operate every server
   systems desks      where your team and your coding agents work
```

The smallest system has one server in each pool. When you need more, you
add servers to a pool, and later a new pool, such as jobs servers. The
shape stays the same at three servers, at thirty, and at thousands.

The Stack has one shape on purpose. You learn one system, and that
knowledge holds from your first customer to a billion-dollar company. A
simpler shape with everything on one server would be easier on the first
day, and then you would have to learn a second system, and move to it,
at the moment when your product takes off. So the Stack starts you on the
shape that you keep.

The shape is not new. Large websites were built in this shape long before
Kubernetes existed.

### The system in seven points, and the reason for each

1. **Requests.** Your users' requests reach [Cloudflare](https://www.cloudflare.com/) first. Cloudflare
   passes the requests to your app servers through Cloudflare tunnels. A
   Cloudflare tunnel is a connection that a server opens out to Cloudflare.
   *Why:* no server has an open web port, so nobody on the internet can
   connect to your servers directly. An attack on your site meets
   Cloudflare first. Cloudflare is a network that stands in front of
   websites: it absorbs floods of traffic that are meant to knock a site
   offline (DDoS attacks), and it can block bots and malicious requests
   before they reach your servers.
2. **Production servers.** The smallest system has three production
   servers, one of each kind. The app server, `app001`, runs your app. The
   database server, `db01`, runs the [Postgres](https://www.postgresql.org/) database. The utility server,
   `util01`, runs the three tools that operate the servers: MMX, MMWatchdog,
   and MMHotline. At setup, your team chooses the smallest system or the
   fuller system. The fuller system adds a second app server, `app002`, and
   a test server, `staging01`, where every release runs first.
   *Why:* each kind of server has one job, so each pool grows by itself: more
   app servers for more requests, a bigger database server for more data.
   The tools that watch the system run on their own server, so they keep
   working when the app server or the database server fails.
3. **Changes.** Every change to the servers is a commit to your systems
   repository. The systems repository holds the server settings and the
   encrypted secrets, and your Git host, such as GitHub, keeps a copy. Your
   coding agent pushes the commit and starts an MMX run on `util01`. MMX is
   the program that makes each server match the systems repository. A push
   alone changes no server.
   *Why:* the repository is the record of what every server is and of who
   changed what. Your coding agent can build any server again from the
   repository, and the data from the backups. No server is changed by hand
   in a way that nobody remembers.
4. **Systems desks.** Each person has a systems desk. A systems desk is a
   small server of the person's own, where the person's coding agent does
   the systems work. You log in from your laptop to your desk. Only the
   desks and the utility server can log in to the production servers. Your
   laptop cannot.
   *Why:* most developers keep their production keys in their home
   directory. Any program that runs as them can copy those keys and send
   them away, and one poisoned package is enough. With the Stack, no
   production key is on your laptop, so there is nothing to copy. And your
   coding agent keeps working on the desk when your laptop is closed.
5. **Alerts.** MMWatchdog checks every server and sends each problem that
   needs a person to MMHotline. MMHotline runs the triage agent, which
   investigates the problem and proposes a fix. Then MMHotline alerts the
   person on call. By default, that is an emergency alert on the phone
   through Pushover. Each person can add other contact methods, such as a
   phone call.
   *Why:* you hear about a problem before your customers tell you, and you
   are woken only when the triage agent has not settled the problem within
   a few minutes.
6. **Backups.** A program called [pgBackRest](https://pgbackrest.org/) sends every change of the
   database to [Backblaze B2](https://www.backblaze.com/cloud-storage). Backblaze is a storage
   provider, separate from your server provider and from Cloudflare.
   Backblaze's Object Lock stops anyone from deleting or changing a stored
   backup for a number of days that a setting names, 14 days by default.
   Every week, the restore drill restores the backups onto a temporary
   server and checks the data.
   *Why:* the backups survive the loss of your server provider's account, an
   intruder, and your own mistake. And a backup that nobody has restored is
   not proven, so the Stack restores yours every week.
7. **Growth.** The system grows through operating procedures. An operating
   procedure is a file of tested steps that your coding agent follows. Each
   operating procedure waits for a trigger, such as MMWatchdog's warning
   that the app server's CPU use stays above 70 percent. Most growth is one
   of two steps: adding a server to a pool, as in the operating procedure
   "Add an app server", or replacing a server with a bigger server, as in
   the operating procedure "Replace a server". When your team lets the
   triage agent do server work, the triage agent also adds an app server
   when the app servers' CPU use stays above that level, and removes one
   when the load drops. The triage agent stays between the smallest and the
   largest number of app servers that you set, and warns first, so that
   anyone can stop it.
   *Why:* you add a part when a measured load, or an event such as your
   first paying customers, asks for it, not before. You do not pay for
   servers that you do not need yet, and you do not have to guess what to
   build next.

## What it costs

You pay the companies whose services you use, at their own prices. This
example is the smallest system, at two server providers. Hetzner's prices
are from its pricing page, read on 2026-11-15; OVHcloud's from its US
catalog, read on 2026-11-17, month to month.

| Machine | Size | Hetzner Cloud (Europe) | OVHcloud VPS (US) |
| --- | --- | --- | --- |
| App server `app001` | 4 vCPU, 8 GB of memory | €8.99 (CX33) | $10.00 (VPS-2) |
| Database server `db01` | 2 vCPU, 4 GB of memory | €5.99 (CX23) | $5.35 (VPS-1) |
| Utility server `util01` | 2 vCPU, 4 GB of memory | €5.99 (CX23) | $5.35 (VPS-1) |
| One systems desk | 2 vCPU, 4 GB of memory | €5.99 (CX23) | $5.35 (VPS-1) |
| **Total each month** | | **€26.96** | **$26.05** |

Hetzner's prices are without VAT and include each server's public address
and 20 TB of traffic. OVHcloud's VPS prices include unlimited traffic. At
OVHcloud, the servers the Stack creates and removes by itself, such as the
weekly restore drill's server, are Public Cloud servers billed by the hour,
so a drill costs a few cents. Your coding agent shows you each server's
price before it creates one.

The other costs:

- **Backups at Backblaze B2:** the first 10 GB are free. After that, each
  gigabyte costs less than one cent a month ($6.95 for 1,000 GB). The
  backups hold about three full copies of your database and the changes
  between them, so a starting app pays nothing or a few cents.
- **Cloudflare:** the Free plan costs $0. The sign-in for your private
  pages is free for up to 50 people. File storage for your app's uploads
  (R2) is free for the first 10 GB, then $0.015 for each gigabyte each
  month. Cloudflare asks for a payment method before R2 turns on.
- **Pushover:** $4.99 once for each person and kind of phone, after a
  30-day free trial.
- **Your coding agent:** your own Claude Code or Codex access. The triage
  agent runs only when an alert arrives, on an API key or on a plan that
  your team already pays for.
- **The weekly restore drill:** a server of the database server's size,
  once a week, for minutes.

For comparison, Heroku lists $300 a month for its "Compute 4CPU-8GB" plan
and $50 a month for its "Standard-0" Postgres plan with 4 GB of memory.
Those two do the work of `app001` and `db01`, which cost €14.98 at
Hetzner above.

You decide about money at setup. Your coding agent shows you the servers'
prices, and you set the largest number of servers in each pool. If you let
the triage agent do server work, it adds and removes app servers with the
load, inside those numbers, and reports what each one costs.

## Why these parts

The Stack makes the choices, so that you do not have to compare tools
before you can start. Each choice is a good default with a reason. The
Stack is open source: you can copy it and change any part to fit your needs.

| Part | Choice | Why |
| --- | --- | --- |
| Server provider | Yours | Plain servers are a commodity. You pick the provider and the price, and you can move later. |
| Operating system | [Debian](https://www.debian.org/) | Widely used and well supported. Debian's own security team fixes security flaws in the programs that the Stack installs from Debian, at no charge. The Stack checks every day for fixes that wait to be installed. |
| Database | [Postgres](https://www.postgresql.org/) | Widely used and well supported. Postgres can also be the job queue and the search index, so you run fewer services, and a second database server can take over automatically. |
| Database backups | [pgBackRest](https://pgbackrest.org/) | It saves every change to the database as the change happens. So you can restore the database to any minute, such as the minute before a mistake, and you lose almost nothing when a server dies. It also checks that its own backups are good. |
| Backup storage | [Backblaze B2](https://www.backblaze.com/cloud-storage) | Your backups are at a different company from your servers, so losing one account does not lose both. Nobody can delete a backup before its lock ends, not even the account's owner. The keys on your servers can add backups but never delete them. |
| Your app | A container image, run by [Podman](https://podman.io/) | A release puts a new image in place of the old one, and a rollback puts the old one back. Podman runs each container as an ordinary systemd service, with no extra background service. Only your app runs in a container. |
| Load balancer | [Caddy](https://caddyserver.com/) | It spreads your users' requests over all the app servers, so each app server that you add takes its share of the load. It switches to a new release of your app without dropping a connection, and its configuration is one short file. |
| In front of the servers | [Cloudflare](https://www.cloudflare.com/) | The servers connect out to Cloudflare, so no server has an open web port, and attack traffic stays off your servers. One account covers the tunnel, the sign-in for private pages, caching, attack filtering, and file storage. |
| Network between servers | [WireGuard](https://www.wireguard.com/) | Every connection between servers is encrypted. The network is a list of keys in your repository, with no outside service that controls it. |
| Monitoring | [MMWatchdog](https://github.com/monkeymaxxing/mmwatchdog) | One program on each server. Each check comes with the next action to take, and its settings are readable files that your coding agent writes and you can read. |
| Alerting and on-call | [MMHotline](https://github.com/monkeymaxxing/mmhotline) | It runs in your own accounts, with no price for each person, and gives each alert to the triage agent first. |
| Alerts to your phone | [Pushover](https://pushover.net/) | Easy to start with, cheap, and its emergency alert sounds through Do Not Disturb and repeats until someone acknowledges it. Each person can add or choose other contact methods, such as a phone call. |
| Where your team works | A systems desk | The desk runs in a different location from production, so your tools stay available when production's location fails. No production key is on your laptop, where a poisoned program could copy it. Your coding agent keeps working when your laptop is closed. |

The [design](docs/design.md#why-these-tools) records each choice in full,
with what it costs and what was considered instead.

## The setup: one working day, in ten chapters

Your coding agent does the work, explains each step, and asks you for facts
and for a few major decisions. Before you start, you need a domain at a
registrar, a password manager for your team, a Git host such as GitHub, and
an account with your coding agent's provider. The setup adds accounts at
Cloudflare, your server provider, Backblaze, and Pushover. Before chapter 1, your coding agent shows you
the route (chapter 0, the map):

| Chapter | What happens |
| --- | --- |
| 1 | Pick your web address and start the team's password manager. Your domain's move to Cloudflare starts here, because the move is the slowest wait. |
| 2 | Set up your laptop and your systems desk. |
| 3 | Get your app ready to deploy. |
| 4 | Sign up for the outside services that the Stack uses: Cloudflare, Backblaze B2, Pushover, and your coding agent's provider. Make a read-only token for your container registry. |
| 5 | Put your site behind Cloudflare, and put a sign-in (Cloudflare Access) in front of your private pages, such as MMHotline's dashboard. |
| 6 | Create your three production servers, after you approve their prices and choose what the triage agent may do by itself. |
| 7 | Install everything on the production servers. |
| 8 | Check that alerts reach your phone and backups restore. |
| 9 | Go live. Your app answers at your domain, and its first release goes out the way every later release will. |
| 10 | Write down how to run your system: your links, test results, and next steps. |

Most of the day needs you: you sign up for the accounts, answer questions,
approve costs, and review changes to your app. Your longest stretch of work
is chapter 4, the accounts, at about one to two hours. Two waits are long.
Your domain's move to Cloudflare takes from minutes to about a day. The
first server setup, in chapter 7, takes most of an hour, and then waits up
to an hour for the first restore drill.

Your app must meet three conditions. Your app uses Postgres, keeps uploaded
files in R2, and runs as a container image. If your app does not meet a
condition yet, your coding agent changes your app with your approval, and
the change can take days.

After the setup, your team has one regular duty. Each week, one person and
the coding agent do the weekly system review: the week's alerts, the
waiting updates, the restore drill's result, and the checklist items that
are due. The checklist is the file that records what is done, what is open,
and when each growth step is due.

## Give it to your coding agent

A skill is a directory of instructions for a coding agent. The stack skill
tells Claude Code or Codex how to build and run your team's production
system. The stack skill lives in
[`skills/monkeymaxxing-stack`](skills/monkeymaxxing-stack).
Clone the Monkeymaxxing Stack repository once, check out the newest
release, then link the skill directory into the place where your agent
looks for your skills:

```sh
git clone https://github.com/monkeymaxxing/monkeymaxxing-stack.git ~/monkeymaxxing-stack
git -C ~/monkeymaxxing-stack checkout "$(git -C ~/monkeymaxxing-stack describe --tags --abbrev=0)"

# Claude Code reads your skills from ~/.claude/skills
mkdir -p ~/.claude/skills
ln -s ~/monkeymaxxing-stack/skills/monkeymaxxing-stack ~/.claude/skills/monkeymaxxing-stack

# Codex reads your skills from ~/.agents/skills
mkdir -p ~/.agents/skills
ln -s ~/monkeymaxxing-stack/skills/monkeymaxxing-stack ~/.agents/skills/monkeymaxxing-stack
```

Each release is a Git tag with a version number, such as `v0.1.0`. Use a
release, not the `main` branch: between releases, `main` names no released
programs, and the setup refuses to install from it.

The repository is on GitHub at
[github.com/monkeymaxxing/monkeymaxxing-stack](https://github.com/monkeymaxxing/monkeymaxxing-stack).
When GitHub is down, clone the same repository from its mirror,
[gitlab.com/monkeymaxxing/monkeymaxxing-stack](https://gitlab.com/monkeymaxxing/monkeymaxxing-stack).

Then start a new session of your agent. To give the skill to everyone who
works in one repository instead, commit a copy in that repository's
`.claude/skills/` (Claude Code) or `.agents/skills/` (Codex), such as
`cp -R ~/monkeymaxxing-stack/skills/monkeymaxxing-stack .claude/skills/`.
A committed link works only on a machine that has the stack's clone at the
same path. For your own skills, a copy works as well as a link.

`git -C ~/monkeymaxxing-stack fetch --tags` brings new releases of the
stack, and changes none of your systems. Your agent applies a new release's
changes to your systems repository only when you ask, following the
[upgrade procedure](skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/upgrade_to_a_new_stack_version.md).

Then tell your agent what you want, in your own words. Your coding agent
loads the skill for requests about production hosting for a web app or work
on an existing stack system. You can also name the skill:
`/monkeymaxxing-stack` in Claude Code, `$monkeymaxxing-stack` in Codex.

- **To start:** "Set up production servers for my app in `~/code/shop` with
  the Monkeymaxxing Stack." Your agent first shows you the
  [ten setup chapters in chapter 0 (before you start: what we build and how long it takes)](skills/monkeymaxxing-stack/systems_repository_template/initial_setup/00_before_you_start_what_we_build_and_how_long_it_takes.md#the-map)
  and how long the waits take: about a working day in all.

  At each chapter, your agent names the setup task, explains why the task
  matters, and says what your agent needs from you. Your agent says where
  the setup task happens and how your agent checks that the task succeeded.

  Your agent asks you for one fact at a time, such as your domain or an
  approval. Your agent never asks you to paste a secret into the chat: you
  type each secret into your own terminal. At the end, your agent saves
  your operating guide in the systems repository. The guide contains your
  links, results, and next actions.
- **Later,** in your systems repository: "Review my system", "Deploy shop
  to production", "We have paying customers now: what should change?", or
  "app001 died. Replace it."

## Documentation

| Read | When you want to know |
| --- | --- |
| [A running Stack system, day to day](docs/day-to-day-operation.md) | What happens when a server fails, what an intruder can reach, how you hear about a problem, how a release goes live, and how the system grows |
| [The ten setup chapters](skills/monkeymaxxing-stack/systems_repository_template/initial_setup) | Exactly what the setup does, chapter by chapter |
| [The operating procedures](skills/monkeymaxxing-stack/systems_repository_template/operating_procedures) | The tested steps for every later job, such as replacing a server |
| [App framework examples](docs/app-frameworks/README.md) | How an app in your framework fits the Stack, with a working example |
| [App platform migration guides](docs/app-platform-migrations/README.md) | How to move from the platform that you use now |
| [The design](docs/design.md) | The reason for each of the Stack's decisions, in full |

## Contributing

Report a bug or propose a change on GitHub, as
[CONTRIBUTING.md](CONTRIBUTING.md) describes. [AGENTS.md](AGENTS.md) is the starting point for changing the Stack itself.
The [acceptance contracts](docs/acceptance.md) state the outcomes that every
change must keep, [the design](docs/design.md) gives the reasons for the
Stack's decisions, and [the testing guide](docs/testing.md) says how changes
are tested.

## License

Apache License 2.0. Included dependencies keep their own licenses.
