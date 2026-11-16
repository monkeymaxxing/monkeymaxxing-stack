# A running Stack system, day to day

This page says how a Monkeymaxxing Stack system behaves after the setup:
what happens when a server fails, what an intruder can reach, how your team
works on the servers, how you hear about a problem, how a release goes live,
and how the system grows. The [README](../README.md) gives the overview.

The waiting times and limits on this page are the defaults of settings.
Your team can change each one, and your own system's README, which the
setup writes, shows your values.

## What happens when a server fails at night

The smallest system has one
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

## What an intruder can reach who breaks into your app

The intruder can
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
default.

The operating procedure "Respond to a break-in" starts with finding out
how the intruder got in. The most common way in is your app. For a
break-in through your app, the operating procedure stops the harm,
replaces the app's keys, and puts the data back. Every desk and the triage
agent keep working, because you need their help. The operating procedure
covers every other way in too, such as a stolen login at an outside
company, and says how to replace the keys that the intruder reached.

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
   `sudo lock-everyone-out`. The lock-out button is for a few narrow
   cases, where a way to administer the servers is in the wrong hands,
   such as a suspect utility server. For a break-in through your app, do
   not use the lock-out button: the lock-out button would cut off the
   helpers you need. You run the lock-out button on your desk. After the
   lock-out, your desk is the only way into the
   servers. You and your coding agent keep working from your desk. Every
   other desk loses access to the servers, and the triage agent stops. Your
   coding agent can give you the command, but only you run the lock-out
   button.

The servers and the desks talk over [WireGuard](https://www.wireguard.com/), an encrypted private
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
   MMHotline's dashboard shows every open incident. [Cloudflare Access](https://www.cloudflare.com/zero-trust/products/access/), a
   sign-in for your team, protects the dashboard.
3. **The triage agent works first, within your settings.** One setting
   says how long an SOS waits for the
   triage agent before the phone rings, three minutes by default. If the
   problem ends during the wait, nobody is woken. A warn alert that the
   triage agent takes up waits the same way, three minutes by default: you
   hear the triage agent's own message instead, or nothing when the triage
   agent fixes the problem and reports it quietly. If the triage agent
   cannot run, or the triage agent reports an SOS, the phone rings at once.
   Another setting says which fixes run without your approval. In the default settings, a routine fix
   that cannot lose data runs at once and is reported, such as a restart of
   a failed service. Every other fix waits for your approval. The triage
   agent's fix is a commit too.
4. **Two alarms cover a silent `util01`.** MMHotline runs on `util01`, so a
   failed `util01` cannot alert you about `util01`. First, `app001` and
   `db01` watch `util01`. If `util01` goes silent, `app001` and `db01` alert
   the phones directly through Pushover. Second, the MMHotline-down alarm is
   a small program that runs in your Cloudflare account, not on your
   servers. MMHotline checks in with the
   MMHotline-down alarm every minute. If the check-ins stop, the
   MMHotline-down alarm wakes the person on call. The MMHotline-down alarm
   works even while every server is down. A setting names each waiting
   time. By default, `app001` and `db01` alert after three minutes. The
   MMHotline-down alarm wakes the person on call after five minutes, and
   the backup person after ten minutes.
5. **The status page tells your customers.** The status page is a public
   page that Cloudflare serves from your Cloudflare account, and a person on your team posts each
   notice. The status page works while every server is down.

## How a release of your app goes live

A release works like every other change. Your app is packaged as a
container image, and a registry stores the image, such as your Git host's
registry. Each image version has an image tag.

The Stack recommends CI, a build service such as GitHub Actions, to test
your app, build the image, and push the image to the registry. The Stack
gives you a ready GitHub Actions file for that. With CI, no password that
can publish an image is on your laptop or on your systems desk. Without
CI, your coding agent tests your app and builds the image on your systems
desk, only inside a container.

Your coding agent writes the
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
work, the triage agent tells you when the app servers' CPU use stays too
high, and your
coding agent adds one, by the operating procedure "Add an app server". The
web server [Caddy](https://caddyserver.com/) on each app server spreads the requests over all app
servers. If one app server fails, the remaining app server keeps serving
requests, and some users see errors for a few seconds.

Besides the two common operating procedures, "Add an app server" and
"Replace a server", five operating procedures each add a part when the part's trigger arrives. A trigger is a
measured warning or an event:

- **A second database server,** when your first paying customers arrive.
  The second database server is a replica: a database server that keeps a
  live copy of the data. If the first database server fails, the replica
  takes over automatically, and database writes fail for about a minute.
- **[PgBouncer](https://www.pgbouncer.org/),** when Postgres warns about the number of connections.
- **Jobs servers,** when background jobs compete with requests for the app
  servers' CPU.
- **Reads from replicas,** when a database server's CPU warning arrives and
  most of the database work is reads.
- **Load-balancer servers,** when the app pool reaches about 20 servers.
