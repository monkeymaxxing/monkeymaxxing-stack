# The example.com systems

This repository holds the server settings for `shop.example.com`.
Your coding agent uses the server settings in this repository to operate
the system.
The system follows Monkeymaxxing Stack version 0.1.0.

**Setup status: incomplete.** The links below contain example values.
At the end of the setup, your coding agent replaces the example values with
your actual links, results, and outstanding work.

The first part of this README, up to "Start or resume work", describes
the system with this system's own servers. The rest holds this system's
links, results, and next actions.

## What the Monkeymaxxing Stack builds

The Monkeymaxxing Stack is a production system for a web app. Your coding
agent builds and runs the system, and your team owns every account, every
server, and all the data. A coding agent is an AI assistant, such as Claude
Code or Codex, that writes files and runs commands for you.

## The system in seven points

1. **Requests.** Your users' requests reach Cloudflare first. Cloudflare
   passes the requests to your app servers through Cloudflare tunnels. A
   Cloudflare tunnel is a connection that a server opens out to Cloudflare.
   So no server has an open web port.
2. **Production servers.** The smallest system has three production
   servers, one of each kind. The app server, `app001`, runs your app. The
   database server, `db01`, runs the Postgres database. The utility server,
   `util01`, runs the three tools that operate the servers: MMX, MMWatchdog,
   and MMHotline. More servers join later, as point 7 says. At setup, your
   team chooses the smallest system or the fuller system. The fuller system
   adds a second app server, `app002`, and a test server, `staging01`, where
   every release runs first.
3. **Changes.** Every change to the servers is a commit to your systems
   repository. The systems repository holds the server settings and the
   encrypted secrets, and your Git host keeps a copy. Your coding agent
   pushes the commit and starts an MMX run on `util01`. MMX is the program
   that makes each server match the systems repository. A push alone changes
   no server.
4. **Systems desks.** Each person has a systems desk. A systems desk is a
   small server of the person's own, where the person's coding agent does
   the systems work. Your laptop reaches only your desk, and the desks reach
   the production servers.
5. **Alerts.** MMWatchdog checks every server and sends each problem that
   needs a person to MMHotline. MMHotline runs the triage agent, which
   investigates the problem and proposes a fix. Then MMHotline alerts the
   phone of the person on call.
6. **Backups.** A program called pgBackRest sends every change of the
   database to Backblaze B2. Backblaze is a company separate from your
   server provider and from Cloudflare. Backblaze's Object Lock stops anyone
   from deleting or changing a stored backup for a number of days that a
   setting names, 14 days by default. Every week, the restore drill restores
   the backups onto a temporary server and checks the data.
7. **Growth.** The system grows through operating procedures. An operating
   procedure is a file of tested steps that your coding agent follows. Each
   operating procedure waits for a trigger, such as MMWatchdog's warning
   that the app server is busy. Most growth is one of two steps: adding
   a server to a pool, as in the operating procedure "Add an app server", or
   replacing a server with a bigger server, as in the operating procedure
   "Replace a server". A pool is the servers that share one job, such as the app
   servers. When your team lets the triage agent do server work, the triage
   agent also adds an app server when the app servers stay busy, and removes
   one when the load drops, within your limits and after a warning that
   anyone can stop.

## Three plain answers

**What happens when a server fails at night?** The smallest system has one
app server and one database server. If `app001` or `db01` fails, your site
stops until the failed server is replaced. MMWatchdog on `util01` checks
your site. When your site stops answering, MMWatchdog sends an SOS, the
urgent alert, to MMHotline. MMHotline first gives the triage agent time to
investigate. Then the SOS wakes the person on call; while the triage agent
replaces a failed server, the SOS waits longer and wakes the person only if
the replacement fails or takes too long.

Two settings decide how soon the phone rings: how long your site must fail
before MMWatchdog sends the SOS, and how long the SOS waits for the triage
agent. By default, MMWatchdog sends the SOS after your site fails for 30
seconds, and the SOS waits three minutes for the triage agent. Your team
can change both settings.

When your team lets the triage agent do server work, the triage agent
replaces a failed app server by itself and tells you, and the same goes for
jobs servers and load-balancer servers once your system has them. Otherwise,
the person on call approves the replacement once, and the triage agent does
the rest.
A failed database server or a failed `util01` always needs a person: the
person on call tells the coding agent, and the coding agent replaces the
server by an operating procedure.

When `db01` is replaced, the new database server gets the data from the
backups. With the Stack's default backup settings, the aim is to lose no
more than about one minute of database changes. The weekly restore drill
measures the real figure for your system.

If `util01` fails, your site keeps running. The checks that run on `util01`
stop, and the two alarms under
["How you hear about a problem"](#how-you-hear-about-a-problem) reach your
phone.

**What can an intruder reach who breaks into your app?** The intruder can
read and change what your app can read and change. So the intruder reaches
the app's database, the app's uploaded files, and the app's keys for
outside services, such as a payment service. The intruder cannot delete or
change your stored database backups. The app servers hold no backup key,
and Object Lock protects each stored backup, even from the account's owner.
The intruder cannot log in to another server, because every server accepts
SSH logins only from the systems desks and from `util01`.

After a break-in, pgBackRest can restore the database to a minute before
the break-in. The intruder can delete or overwrite uploaded files. When your
app keeps uploaded files, `util01` copies the uploaded files to Backblaze
every night by default. Backblaze keeps the earlier versions of the
uploaded files for a number of days that a setting names, 14 days by
default. The operating procedure "Respond to a
break-in" starts with finding out how the intruder got in. For a break-in
through the app, the procedure replaces the app's keys and puts the data
back, while every desk and the triage agent keep working. The procedure covers every
other way in too, such as replacing the keys that the intruder reached.

**What costs money?** Five companies charge for the system:

- **Your server provider** charges for each server, for each server's
  public IP address, and for each systems desk. The temporary server of the
  weekly restore drill costs about an hour of server time each week.
- **Backblaze** charges for the storage that your backups use.
- **Cloudflare** asks for a payment method before Cloudflare's file storage,
  R2, turns on. R2 holds your app's uploaded files, and a small app stays
  inside R2's free allowance.
- **Pushover,** the app that sounds the alerts on your phone, charges a
  one-time licence fee after a free trial.
- **Your coding agent's provider** bills the work of your coding agent and
  of the triage agent.

Your team keeps paying for the accounts that your team already has, such as
the domain's registrar and the Git host.

You decide about money once, at setup. Your coding agent shows you the
prices of the servers, and you set the limits for growth, such as the
smallest and the largest number of app servers. Inside your limits, servers
are added and removed without asking you, and you get a report of what each
one costs. Your coding agent asks you only for something outside your
limits.

## Your systems desk

1. **A server of your own.** Your systems desk is a small server at your
   server provider, in a different location from production. A location is
   one of the server provider's data centers. So an outage of production's
   location leaves your tools available.
2. **Your laptop holds no production key.** Most developers keep their
   production keys in their home directory, where any program that runs as
   them can copy the keys and send them away. One poisoned package is
   enough. With the Stack, the production key stays on your desk, so your
   laptop has nothing to copy. From your laptop, you log in to your desk
   with an SSH key and a phone code. A phone code is a six-digit code from
   an authenticator app on your phone, so a copied login key alone opens
   nothing. And only the desks and the utility server can log in to the
   production servers.
3. **Two Unix accounts.** The desk has your account and the coding agent's
   account. Your production SSH key and your API tokens stay in your
   account. When the coding agent connects to a server, the desk signs with
   your key for the coding agent. So your coding agent can use the key and
   the tokens, but your coding agent cannot read the key or the tokens. A
   mistake then cannot copy your own secrets into the coding agent's
   conversation, which the coding agent's provider stores.
4. **The lock-out button.** The lock-out button is the command
   `sudo lock-everyone-out`, for a few narrow break-in cases, such as a
   suspect utility server. For a break-in through the app, the lock-out
   button would cut off the helpers you need, so you do not use the button
   there. You run the lock-out button on your desk. After the lock-out,
   your desk is the only way into the servers. You and your coding agent keep working from your desk. Every
   other desk loses access to the servers, and the triage agent stops. Your
   coding agent can give you the command, but only you run the lock-out
   button.

The servers and the desks talk over WireGuard, an encrypted private
network. WireGuard's port is the only port that a server opens to the
internet. A lost laptop, a lost phone, and a lost desk each have an
operating procedure.

Three coding agents have three jobs. The coding agent on your laptop, if you
use a coding agent there, works on your app's code. The coding agent on your
desk does the systems work. The triage agent is a separate coding agent that
MMHotline runs on `util01` for each alert.

## How you hear about a problem

1. **MMWatchdog checks every server.** MMWatchdog runs on every server, and
   most checks run every minute. Every server reports to MMWatchdog's fleet
   hub on `util01`, so the fleet hub notices a server that goes silent.
2. **MMHotline alerts the person on call.** MMHotline's on-call schedule
   says who is on call. An SOS wakes the person on call, even at night, and
   repeats until someone claims the SOS. Claiming an SOS means "I am
   handling the problem". A warn alert shows on the phone with a sound,
   once. An info alert shows on the phone without a sound. Each person can
   turn warn alerts and info alerts off for the person's own phone.
   MMHotline's dashboard shows every open incident. Cloudflare Access, a
   sign-in for your team, protects the dashboard.
3. **The triage agent works first, within your settings.** One setting
   says how long an SOS waits for the
   triage agent before the phone rings, three minutes by default. If the
   problem ends during the wait, nobody is woken. A warn alert that the triage agent takes up waits the same way, three minutes by default: you hear the triage agent's own message instead, or nothing when the agent fixes the problem and reports it quietly. If the triage agent cannot run, or the triage
   agent reports an SOS, the phone rings at once. Another setting says which
   fixes run without your approval. In the default settings, a routine fix
   that cannot lose data runs at once and is reported, such as a restart of
   a failed service. Every other fix waits for your approval. The triage
   agent's fix is a commit too.
4. **Two alarms cover a silent `util01`.** MMHotline runs on `util01`, so a
   failed `util01` cannot alert you about `util01`. First, `app001` and
   `db01` watch `util01`. If `util01` goes silent, `app001` and `db01` alert
   the phones directly through Pushover. Second, the MMHotline-down alarm is
   a small program in your Cloudflare account. MMHotline checks in with the
   MMHotline-down alarm every minute. If the check-ins stop, the
   MMHotline-down alarm wakes the person on call. The MMHotline-down alarm
   works even while every server is down. A setting names each waiting
   time. By default, `app001` and `db01` alert after two minutes. The
   MMHotline-down alarm wakes the person on call after five minutes, and
   the backup person after ten minutes.
5. **The status page tells your customers.** The status page is a public
   page in your Cloudflare account, and a person on your team posts each
   notice. The status page works while every server is down.

## How a release of your app goes live

A release works like every other change. Your app is packaged as a
container image, and a registry stores the image, such as your Git host's
registry. Each image version has an image tag. Your coding agent writes the
new image tag into the systems repository, commits, pushes, and starts an
MMX run. MMX starts the new version beside the old version on the app
servers. MMX switches the requests to the new version only after the new
version passes a health check on every app server. If the new version
fails the health check, your users stay on the old version. A setting says
whether your coding agent asks for your approval before a release to
production. By default, your coding agent asks.

## How the system grows

The first growth step for most teams is a second app server, which keeps
the site up while one app server fails. After that, with server work on, the
triage agent adds and removes app servers with the load. Without server
work, the triage agent tells you when the app servers are busy, and your
coding agent adds one, by the operating procedure "Add an app server". The
web server Caddy on each app server spreads the requests over all app
servers. If one app server fails, the remaining app server keeps serving
requests, and some users see errors for a few seconds.

Besides the two common operating procedures from point 7, five operating
procedures each add a part when the part's trigger arrives. A trigger is a
measured warning or an event:

- **A second database server,** when your first paying customers arrive.
  The second database server is a replica: a database server that keeps a
  live copy of the data. If the first database server fails, the replica
  takes over automatically, and database writes fail for about a minute.
- **PgBouncer,** when Postgres warns about the number of connections.
- **Jobs servers,** when background jobs compete with requests for the app
  servers' CPU.
- **Reads from replicas,** when a database server's CPU warning arrives and
  most of the database work is reads.
- **Load-balancer servers,** when the app pool reaches about 20 servers.

## What the setup asks of you and of your app

The initial setup takes about one working day, in ten chapters. Your coding
agent does the work, explains each step, and asks you for facts and for a
few major decisions.

Your app must meet three conditions. Your app uses Postgres, keeps uploaded
files in R2, and runs as a container image. If your app does not meet a
condition yet, your coding agent changes your app with your approval, and
the change can take days.

After the setup, your team has one regular duty. Each week, one person and
the coding agent do the weekly system review: the week's alerts, the
waiting updates, the restore drill's result, and the checklist items that
are due. The checklist is the file that records
what is done, what is open, and when each growth step is due.

## The accounts at outside companies

Your team uses eight accounts at outside companies. A typical team makes
four new accounts and already has four accounts.

- **Four new accounts:** Cloudflare, the server provider, Backblaze, and
  Pushover.
- **Four accounts your team already has:** your domain's registrar, your
  team's password manager, your Git host, and your coding agent's provider.
  The password manager holds the logins and the recovery items for every
  account and for your desk.
- **Two more accounts only when needed:** email addresses at your company's
  domain, for the sign-in to MMHotline's dashboard, and an email sending
  service when your app sends email.

Separate companies hold the servers and the backups. So the backups stay
reachable when your team loses access to the server provider's account or
to Cloudflare's account.

## What the system does not survive

All production servers run in one location of one server provider, with
Cloudflare in front. A failure of the whole location, of the server
provider, or of Cloudflare stops your site. After a location or provider
failure, your coding agent rebuilds the servers from the systems repository
and the backups. The new servers run in another location or at another
server provider.

## Start or resume work

Log in to your systems desk and run `start-the-coding-agent`. Then give
your coding agent your request, for example:

> What is the next necessary step?

Your coding agent explains each action, checks the current state, and
follows the operating procedure for the job. Never paste a secret into the
conversation. Your coding agent tells you where to type each secret, such
as your own terminal or the password manager.

[`AGENTS.md`](AGENTS.md) holds your coding agent's rules and lists the
files of this repository. `git log` is the system's history, because every
setting, release, triage fix, and added server is a commit. `util01` keeps
the history of MMX's runs for 30 days by default (`run_history_retention`
in `mmx_project_settings.yml`). Ask your coding agent to read the run
history.

Two kinds of settings live outside this repository: the outside
companies' settings, such as your DNS records at Cloudflare, and each
person's own contact methods on MMHotline's page.

## Operating links

| Purpose | Location |
| --- | --- |
| Live app | https://shop.example.com |
| Alerts and correction approvals | https://ops.example.com |
| MMX run history | Ask the agent to read `mmx results` on `util01` |
| Public status page | Not recorded yet |
| App repository and image build, with CI | Not recorded yet |
| This systems repository at the Git host | Not recorded yet |
| Detailed results and outstanding checks | [System checklist](monkeymaxxing_stack_checklist.yml) |

## Common requests

| You need to | Tell your coding agent | Procedure |
| --- | --- | --- |
| Release an app version | "Release the next shop version." | [Release or roll back](operating_procedures/deploy_and_roll_back_an_app_release.md) |
| Respond to an alert | "Give the cause of this alert and the proposed correction." | [Procedure table](AGENTS.md#when-this-happens-follow-this-operating-procedure) |
| Publish a service notice | "Post a status notice for this incident." | [Post to the status page](operating_procedures/post_to_the_status_page.md) |
| Replace a failed server | "app001 stopped. Examine the effect on the site and prepare a replacement." | [Replace a server](operating_procedures/replace_a_server.md) |
| Recover missing data | "A change removed database rows. Give the recovery procedure." | [Recover missing rows](operating_procedures/recover_rows_lost_to_a_bad_change.md) |
| Review the system | "Do the weekly system review." | [Weekly review](operating_procedures/do_the_weekly_system_review.md) |
| Respond to a break-in | "Someone broke in. Find out how, and give me the response." Run `sudo lock-everyone-out` in your own terminal on your desk only when your coding agent shows that the case is one the page names. | [Respond to a break-in](operating_procedures/respond_to_a_break_in.md) |

To release to production without the question for your approval, set
`production_releases_wait_for_a_persons_approval` to `false` in
`mmx_project_settings.yml`, or ask your coding agent to change the setting.

For an urgent alert, open the incident in MMHotline and select
"Claim: I'm handling the incident", or acknowledge the alert in Pushover.
Claiming the alert tells your team that you handle the problem and stops
the repeated notifications, but the claim does not fix the fault. Then read
the incident and any request for approval.

## If a server fails

The table below gives the effect of each server's failure with the servers
you have now.

| Server | Effect of failure with the current servers |
| --- | --- |
| app001 | The site stops until a replacement app server is installed. When your team lets the triage agent do server work, the triage agent replaces app001 at once; otherwise, after a person's one approval. |
| db01 | The site stops until a replacement database is ready. There is no replica for automatic failover. |
| util01 | The site keeps running. The scheduled checks, MMHotline, and MMHotline's dashboard stop until `util01` is rebuilt. Two alarms reach your phone: the hub-outage alerters, `app001` and `db01`, alert everyone who can be on call directly through Pushover, and the MMHotline-down alarm in your Cloudflare account wakes the person on call. Your coding agent can still change the servers from your systems desk. |

[How the system grows](#how-the-system-grows) says what a second app
server and a database replica change.

After a location or provider failure, your coding agent rebuilds the
servers elsewhere as
[Recover when every database server is lost](operating_procedures/recover_when_every_database_server_is_lost.md#the-location-or-provider-is-lost)
describes. The database backups restore Postgres. The uploaded files come
from Cloudflare's R2 file storage, or from the uploads' backups in B2.

The rebuild needs your team's access to the server provider, Cloudflare,
Backblaze B2, the Git host, and the container registry that holds the app
images. The vault passphrase opens `secrets_vault.age`, which holds the B2
access keys and the backup passphrases. Keep the account logins, the
recovery codes, the vault passphrase, and copies of the backup passphrases
in the team's password manager.

A Cloudflare outage also stops the public status page.

## Recovery test results

The database restore time is how long the weekly restore drill takes, from
the drill's start to a checked, restored database. The drill creates the
temporary server `restore01`, restores the backups onto `restore01`, and
runs each app's data checks, such as a check that the database holds an
order from the last two days. The restore time does not include recovering
the whole site.

The one-minute backup target is not a measured upper bound on lost data.

| Measurement | Latest result and date |
| --- | --- |
| Database restore time | Not checked yet |
| Age of the newest restored transaction at the recorded drill start, before creating restore01 | Not checked yet |
| Restored app data meets the queries' requirements for records and their age | Not checked yet |
| Time to recover the whole site | Not measured |
| Phone alert test | Not checked yet |
| Hub-outage alerters' test | Not checked yet |
| MMHotline-down alarm test | Not checked yet |

The [checklist](monkeymaxxing_stack_checklist.yml) holds the detailed evidence.

## Next actions

| Action | Responsible person | Date or starting event |
| --- | --- | --- |
| Complete setup and record its results | Not assigned | Before setup handover |
| Do the weekly system review: the week's alerts, the waiting updates, the restore drill's result, and the checklist items that are due | Not assigned | Weekly, at a time still to be agreed |

The [checklist](monkeymaxxing_stack_checklist.yml) holds the later checks,
and, in their own section, the growth and improvement items, such as a
second database server, each with the trigger it waits for. The
[weekly review](operating_procedures/do_the_weekly_system_review.md) checks
whether a trigger arrived.

## Looking after your systems desk

You manage your desk with `review-and-apply-the-systems-desk-settings`, in
your own terminal on the desk. When the desk's settings changed since your
last review, the command shows each change and runs only after you type
`yes`. Your coding agent explains each change first.

Keep the recovery items that
[chapter 2 (set up your laptop and your systems desk)](initial_setup/02_set_up_the_laptop_and_the_systems_desk.md#recovery-items-and-laptop-cleanup)
lists in the team's password manager. If you lose your phone, your laptop,
or your desk, tell your coding agent. The operating procedures are
[Recover from a lost phone](operating_procedures/recover_from_a_lost_phone.md),
[Recover from a lost or stolen laptop](operating_procedures/recover_from_a_lost_or_stolen_laptop.md),
and [Rebuild a systems desk](operating_procedures/rebuild_a_systems_desk.md).

Your laptop still holds the credentials for your app's code, such as your
Git login. If a program you do not trust ran on your laptop, follow the
laptop procedure above: it replaces those credentials and your desk. The
credential that publishes your app's image is not on the laptop: it is
GitHub's own short-lived token inside your CI, or, for a team without CI, a
login on your systems desk.
