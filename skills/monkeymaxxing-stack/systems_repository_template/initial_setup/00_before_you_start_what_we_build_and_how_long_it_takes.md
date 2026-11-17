# Chapter 0: Before you start: what we build and how long it takes

**When:** whenever the person asks what the setup builds, or how long it
takes. The setup itself starts at chapter 1 with its first question, not
with this map.

**What this chapter does:** the person sees what the setup builds, from a
web app and no servers to the system the initial setup builds: `app001`, `db01`, and
`util01`, a systems desk per person, plus `staging01` and `app002` if the team chooses the fuller
system. The person also sees the chapters, the sittings, and how long they take.
The first page of the [team's `README.md`](../README.md#what-the-monkeymaxxing-stack-builds)
describes that system; this chapter's map follows the first page's words.

**Who acts:** you, the coding agent, show the map and the time estimate when asked.
The person reads them and asks questions. Nothing changes on a server or an
account, so this chapter has no numbered steps.

## Before you start

- **The order of the chapters.** Follow the numbered setup steps in order.
  Each setup step needs only the earlier steps.
- **Only what the steps say.** Do what each step says, and nothing more, because work
  nobody asked for costs the person time: no checks,
  scans, or experiments of your own. When something seems to need more,
  say so to the person in one line, as a suggestion; it joins the steps
  only once they agree.
- **The messages to the person.** Each chapter's steps say what to tell or
  ask the person, in quote blocks: "Tell the person first" before a step,
  "Ask the person" when the person must act or approve, and "Tell the
  person after" with the result and the link where the person sees it.
  Say each message when its step comes, in your own words, with the
  team's own names and links.
- **Commits.** Commit each chapter's changes to the systems repository as you go, signed,
  with a message that says what changed and why (the systems repository's [`AGENTS.md`, "Making a
  change"](../AGENTS.md#making-a-change)). The coding agent builds images or uses existing CI,
  then records each selected image tag and runs MMX explicitly.
- **Command blocks.** Every command block in the initial setup files starts
  with a comment that says where it runs.

## The map

Show this map and the time estimate only when the person asks. The person
has already chosen the stack, so the map gives the system in brief and
the route. When the person asks for the whole
picture, show the first page of the team's `README.md`. Explain each tool
further when the person first needs it.

**Show the person the map,** as the chapter's opening message:

> This setup builds a production system for your app. I build and run the
> system, and your team owns every account, every server, and all the data.
>
> - Your users' requests reach Cloudflare first. Cloudflare passes the
>   requests to your app servers through Cloudflare tunnels, so no server
>   has an open web port.
> - The smallest system has three production servers: the app server
>   `app001`, the database server `db01`, and the utility server `util01`,
>   which runs MMX, MMWatchdog, and MMHotline. The setup starts with the
>   smallest system. You can choose the fuller system, which adds a second app server,
>   `app002`, and a test server, `staging01`.
> - Every change to the servers is a commit to your systems repository.
>   I push the commit and start an MMX run on `util01`.
> - I work on your laptop. I reach production only through your systems desk, a small server of your own that keeps the production key, the secrets, and your tokens locked away.
> - MMWatchdog checks every server. MMHotline runs the triage agent, which
>   investigates each problem and proposes a fix. Then MMHotline alerts the
>   phone of the person on call. We test that alerts reach your phone.
> - Your database backups go to Backblaze, a separate company, and are
>   locked against deletion for a number of days that a setting names,
>   14 days by default. Every week, the
>   restore drill restores the backups onto a temporary server and checks
>   the data.
> - The system grows through operating procedures: tested steps that I
>   follow when a trigger arrives, such as MMWatchdog's warning that the app
>   server is busy. When your team lets the triage agent do server work, the
>   triage agent also adds an app server when the app servers stay busy, and
>   removes one when the load drops, within your limits and after a warning
>   that anyone can stop.
> - The first growth step for most teams is a second app server, which keeps
>   the site up while one app server fails. After that, with server work on,
>   the triage agent adds and removes app servers with the load. Without
>   server work, the triage agent tells you when the app servers are busy,
>   and I add one.
>
> You decide about money once, in chapter 1: I show you the prices of the
> servers, and you approve the limits for growth, such as the smallest and the
> largest number of app servers. Inside your limits, servers are added and
> removed without asking you, and you get a report of what each one costs.
> I ask you only for something outside your limits.
> You approve each change to your app.
>
> The setup comes in sittings. The first sitting puts your app live, protected and backed up:
>
> 1. Chapter 1: Answer two questions: your domain and your server provider.
> 2. Chapter 2: Get your app ready to deploy. You approve my changes to your app once.
> 3. Chapter 3: Make your server account and your systems desk.
> 4. Chapter 4: Set up your accounts and lock your systems desk: Cloudflare, your domain's registrar, Backblaze, one GitHub token, one recovery passphrase, and one phone code.
> 5. Chapter 5: Put your site behind Cloudflare and lock your private pages.
> 6. Chapter 6: Create your three production servers.
> 7. Chapter 7: Install everything on the production servers.
> 8. Chapter 8: Check that your backups restore.
> 9. Chapter 9: Go live, and approve your app's first release.
>
> The second sitting adds phone alerts, the same day, in about 15 minutes.
> Later short sittings add the triage agent, the status page for your customers, and chapter 10, your written operating guide.
>
> The smallest system has one app server and one database server. If
> `app001` or `db01` fails, your site stops until the failed server is
> replaced. When your site stops answering, MMWatchdog sends an SOS, the
> urgent alert. The SOS first gives the triage agent time to investigate,
> three minutes by default, and then
> wakes the person on call. While the triage agent replaces a failed server,
> the SOS waits longer and wakes the person only if the replacement fails or
> takes too long. A warn alert that the triage agent takes up waits the
> same way, three minutes by default: you hear the triage agent's own
> message instead, or nothing when the agent fixes the problem and reports
> it quietly. When your team lets the triage agent do server
> work, the triage agent replaces a failed app server by itself and tells
> you, and the same goes for jobs servers and load-balancer servers once
> your system has them. Otherwise, the person on call approves the
> replacement once, and the triage agent does the rest. A failed database server or a failed `util01`
> always needs a person: the person on call tells me, and I replace the
> server by an operating procedure. A second app server and a second database server let the site
> keep running through such a failure. The checklist says when to add
> them, such as when your first paying customers arrive.

## How long it takes

Give this estimate with the map. At each wait, say its cause and the next
check.

**Tell the person, with the map:**

> The first sitting takes a few hours. You are busy for about an hour of it:
> answering two questions, approving changes to your app, signing up at four websites, and saving one passphrase.
> If your app needs bigger changes first, such as moving from SQLite to
> PostgreSQL or its uploads to R2, chapter 2 can take days, and the day's
> plan moves with it.
>
> Two waits are long, and you have nothing to do during them:
>
> - Your domain's move to Cloudflare takes from minutes to about a day,
>   and nothing speeds it up. The move starts in chapter 4, and I keep
>   working meanwhile. Chapter 9 needs the move to be finished.
> - The first server setup, in chapter 7, takes most of an hour, mostly
>   for the servers' security updates. Your laptop may sleep: the work
>   continues on your desk.
>
> After the first two sittings, your site is live, alerts reach your phone, and your
> backups are proven to restore. After the setup, your team has one
> regular duty. Each week, one person and I do the weekly system review:
> the week's alerts, the waiting updates, the restore drill's result, and
> the checklist items that are due. If you want extra confidence afterward,
> you can ask me to check your system's protections. Those checks are
> optional, and some of them wake whoever is on call, so they wait for a
> quiet time that you choose.

Next: [Chapter 1: Answer two questions](01_answer_two_questions.md).
