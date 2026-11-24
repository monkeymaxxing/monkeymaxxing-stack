# Chapter 0: Before you start: the five parts of the setup, and how long they take

**When:** right after the person's "go" in chapter 1, for the full map; at
the end of each part, for the compact map; and whenever the person asks
where the setup stands, or comes back to it, such as in a new session, after
the laptop slept, or the next day.

**What this chapter does:** the person always knows four things: what is
going to happen, where the setup is now, what has happened, and what is
left. The person also knows, for each part, what you do and what the person
does. The person sees the setup as five parts, with the same names in the
chat, in the terminal window and in the team's `README.md`. The chapters
are your own structure, and the person never sees them: the Monkeymaxxing
Stack skill's `SKILL.md`, "Where the person is: the five parts", maps each chapter to its part, and holds the rules for when each screen
below comes.

When the person asks what the setup builds, show the first page of the
team's [`README.md`](../README.md#what-the-monkeymaxxing-stack-builds) in a
few lines, and explain each tool further when the person first needs it.

**Who acts:** you, the coding agent, show the map. The person reads it and
asks questions. Nothing changes on a server or an account, so this chapter
has no numbered steps.

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
- **Commits.** Commit each chapter's changes to the systems repository as you go,
  with a message that says what changed and why (the systems repository's [`AGENTS.md`, "Making a
  change"](../AGENTS.md#making-a-change)). The coding agent builds images or uses existing CI,
  then records each selected image tag and runs MMX explicitly.
- **Command blocks.** Every command block in the initial setup files starts
  with a comment that says where it runs.

## The map

Show the full map once, right after the person's "go" in chapter 1, as its
own screen. Fill in the team's own facts, as the list below the screen
says. The time figures come from full newcomer test runs, which went live
in 55 to 70 minutes; say "about", never an exact time. The parts' times
add up to the total: 5, 25, 3, 40 and 15 minutes make about an hour and a
half.

**Show the person,** after "go", for a Hetzner setup:

```text
Here is the whole setup, in five parts.  About an hour and a half in all.

  1. Your app                  about 5 minutes
     I get your app ready to deploy.  You approve my changes.
  2. Your accounts             about 25 minutes
     You use the accounts you have, or make the missing ones, and copy a key from each,
     approve the real price, and change one setting at your domain's registrar.
     I build your systems desk: a small server of your own that holds your keys
     and secrets, so neither your laptop nor I ever hold them.  I work through it.
     I order your servers right after your yes, and do the rest.
  3. Your keys locked away     about 5 minutes
     You save a password and one passphrase, and scan one code with your phone.
  4. Your servers              about 40 minutes
     I install everything on your servers, back up your data, and prove a restore.
     Nothing for you.
  5. Live                      about 15 minutes
     I tell you the moment your site is up, then put your app's newest version live.
     If your domain is new to Cloudflare, going live waits for its move, minutes to about a day.

  Later, about 15 minutes:     phone alerts.
  Then, when you want them:    an agent that answers alerts before they reach you,
                               a status page for your customers,
                               and a written guide to running your system.

By default, I'll go fast and only stop when I need you. Say "guide me" any time
and I'll slow down and explain each part before I do it. Say "go fast" to speed
up again. Ask "why?" about anything.

Now: I am installing two small tools and reading your app, about 5 minutes.
Next for you: approve my changes to your app, in about 5 minutes.  I show them here.
```

The facts on the screen:

- **The accounts** are the server provider, Cloudflare and Backblaze, and
  the GitHub account the app is at already. The person keeps each account
  that exists, and makes only the missing ones.
- **The keys** are a key from each of the 3 accounts and one from
  GitHub: the server provider's key, Cloudflare's token, Backblaze's key
  (two values, the key's ID and the key) and the GitHub token that lets
  the servers download the app. The map says "a key from each" and never
  a count, because the person counts copies, and Backblaze's key is two
  copies. Add each outside service that an app needs a key from, such as
  Stripe: "and copy a key from each, and one from Stripe". The person
  sees each extra key as its own message in "Your accounts".
- **The registrar's setting** is the domain's nameservers. Leave the words
  "and change one setting at your domain's registrar" out when
  `dig NS example.com +short` already names Cloudflare's nameservers, or
  when the person registers a new domain at Cloudflare. When the clause is
  in, keep the line under part 5: "If your domain is new to Cloudflare,
  going live waits for its move, minutes to about a day." Otherwise leave
  that line out too.
- **The pace paragraph** ("By default, I'll go fast ...") stays as it
  stands. It is the second time the person sees it, after chapter 1's
  first screen. The skill's "The person's pace" holds the rules for
  "guide me", "go fast" and "why?".
- **The private backup repository at GitHub:** when `gh` is not signed in
  on the laptop, the person makes it on one screen in "Your accounts", so
  add "and make one empty repository at GitHub" before "and do the rest".
- **An app that needs bigger changes first,** such as a move from SQLite
  to PostgreSQL: part 1's time reads "longer: your app needs bigger
  changes, which I show you first", and the "about an hour and a half" line says that
  part 1 can take days.
- **The Now and Next lines** follow the skill's "Now and next" rule. Before
  you end your reply with the map, start the two tools' install as a
  background command, as the skill's "Screen last" rule says, so the
  install's end wakes you.

## The compact map

At the end of each part, show the compact map: the parts that are done
ticked, the current part marked with an arrow, and the rest listed, with
the line "Later: phone alerts.  Your site has none yet." until the alerts
part of the setup is done. That line, the map and the live screen are where
the person hears that the site has no phone alerts yet; not every reply.
Its first line is the finished part's result, in one line. The next screen or
the Now and Next lines follow it. For example, at the end of "Your app":

```text
Your app is ready: my changes are on main, and GitHub is building your app.

  ✓ 1. Your app
  → 2. Your accounts            now, about 25 minutes
    3. Your keys locked away
    4. Your servers
    5. Live
    Later: phone alerts.  Your site has none yet.
```

Then the account screen of chapter 3 follows in the same reply, as its last
text.

At the end of "Your accounts", your reply shows the compact map, before
the window for "Your keys locked away", as chapter 4's step 9 gives it:

```text
Your accounts are done.

  ✓ 1. Your app
  ✓ 2. Your accounts
  → 3. Your keys locked away    now: 3 steps, about 5 minutes
    4. Your servers
    5. Live
    Later: phone alerts.  Your site has none yet.
```

At the end of "Your keys locked away", your reply shows the compact map
with three parts ticked, as chapter 4's last step gives it.

Between the ends of parts, give only the Now and Next lines, with no map.

## Where are we

When the person asks where the setup stands, or comes back to it, such as
in a new session, after the laptop slept, or the next day, your first
reply is the compact map, with the current part's next step in the Now and
Next lines. Work out where the setup is from the files, never from the
person:

| What you find | Where the setup is |
| --- | --- |
| No systems repository on the laptop, such as `~/code/example_systems` | Before part 1: start chapter 1 |
| `deployed_image_tags` in `inventories/servers.yml` still holds the template's example | In part 1, "Your app" |
| The app's pushed commit in `deployed_image_tags`, and no `setup_results.json` on the systems desk, or one with an account step that is not `done` or `not_needed` | In part 2, "Your accounts" |
| Every account step in `/var/lib/monkeymaxxing-stack/setup_results.json` on the systems desk is `done` or `not_needed`, and `finished` is not `true`, or `ssh root@desk01 true` still works | In part 3, "Your keys locked away" |
| `finished: true`, and `backups_restore_every_week` in `monkeymaxxing_stack_checklist.yml` is not `done` | In part 4, "Your servers" |
| `backups_restore_every_week` is `done`, and `tunnel_and_the_public_host_name` is not | In part 5, "Live" |
| `tunnel_and_the_public_host_name` is `done` | The five parts are done. Name what is left of the later parts: phone alerts until `mmhotline_reaches_the_person_on_call` is `done`, then `triage_agent_investigates_alerts`, `status_page_for_customers` and `operating_handover_saved` |

The account steps of `setup_results.json` are every step before
`recovery_passphrase`.

## How long it takes

The map gives the times. When the person asks for more, say:

> The setup takes about an hour and a half in all, and I need you for about 20 minutes of it, mostly at the start.
>
> Two waits can be long, and you have nothing to do during them:
>
> - Your domain's move to Cloudflare takes from minutes to about a day,
>   and nothing speeds it up. The move starts in "Your accounts", and I
>   keep working meanwhile. Your site goes live only once the move is
>   finished.
> - "Your servers" takes about 40 minutes: installing everything, mostly
>   the servers' security updates, then the restore test, a check that
>   your backups really restore. Your laptop may sleep: the work
>   continues on your systems desk. I give you a line about every 10
>   minutes.
>
> If your app needs bigger changes first, such as moving from SQLite to
> PostgreSQL or its uploads to R2, "Your app" can take days.
>
> After the five parts and the phone alerts, your site is live, alerts
> reach your phone, and your backups are proven to restore. After that,
> your team has no regular duty: updates and reboots run by themselves
> each week in a quiet night hour, without taking your site down, and your
> phone rings only when a person must act. Whenever you like, such as once
> a month, ask me "Review my system".

Next: [Chapter 1: Answer two questions](01_answer_two_questions.md).
