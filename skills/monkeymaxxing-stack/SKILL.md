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
with [its trust line and auto mode line](systems_repository_template/initial_setup/01_answer_two_questions.md#first-the-trust-line-and-auto-mode),
so the person runs you in auto mode instead of approving every step,
then its first question. The person has already chosen the stack, so do
not explain the whole project first: the first screen gives one line of
time, and the map of the setup's five parts comes right after "go" ("Where
the person is: the five parts" below).

The person sees the setup as five parts. After the fifth part, the app is
live, protected and backed up, in about an hour and a half. In this guide, "the first
part of the setup" means chapters 1 to 9, all five parts; never say "first
part" to the person, because the person's part 1 is "Your app". The alerts
part of the setup adds phone alerts. Later short parts add the triage
agent, the status page, and the written operating guide (chapter 10).
Until the alerts part of the setup is done, say plainly that the site has
no phone alerts.

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

- **Screen last.** Anything the person must read or act on is the last
  thing in your reply, and your turn ends there: never a tool call after
  it. Text between tool calls is collapsed on the person's screen: Claude
  Code draws it as one short line, and the person never sees the whole
  text. Only the text that ends your turn is shown in full. So a screen,
  a question, an approval such as a price, or a result the person must
  read always ends the turn. When you must wait for the person's result,
  such as the key file, `desk-ready`, `wait-for-the-setup` or an order's
  progress, start the wait first as a background command (in Claude
  Code, the Bash tool's run-in-background option), then write the screen
  and end your turn. The background command's end wakes you, and you
  carry on. An agent with no background commands ends its turn with the
  screen and asks the person to say "done" when the person's window
  says so.
- **Every background wait has a time limit, and its end gets a reply.**
  Give each wait its bound: `--at-most-minutes N` on the Stack's wait
  commands, or `timeout` around a loop of your own, such as
  `timeout 5m bash -c 'until CHECK; do sleep 10; done'`. Never start an
  `until` loop with no bound. The command's end wakes you whatever the
  result: success, failure or the bound. Then say the result in a reply
  that ends your turn, also when it is "still not done". Reason: in a
  full newcomer test run, an unbounded background loop never ended, and
  the person waited 8 minutes for a site that was already live.
- **Long work.** Before any stretch of work longer than about a minute,
  end a reply with one line: what happens now, about how long, and that
  the person need do nothing, such as "Now: I am setting up your servers,
  about 15 to 20 minutes. Next for you: nothing. I tell you when it is done."
  Run long work as background commands, with your turn ended, where you
  can. Notes between tool calls are collapsed, so never rely on them to
  tell the person anything. While a background job runs, your reply's
  last line says when you next speak: "I'll tell you how it goes in
  5 minutes at most, and when it's done, in about 10 to 15 minutes." Reason: the person then never has to ask whether
  you are still working.
- **No wait longer than 5 minutes; each end gets one line.** Bound each
  background wait at 5 minutes at most, `--at-most-minutes 5` on the
  Stack's wait commands or `timeout 5m` around a loop of your own, and
  start the next one when it ends unfinished. When a wait ends, say one
  line, as the text that ends your turn, before you start the next
  wait: what finished, what runs now, and how long is left, such as
  "Your desk's security updates are done. Now I set up the desk itself,
  about 10 to 15 more minutes." The wait commands' last line starts with
  "Tell the person:" and gives that line's content; say it in your own
  words. Say what is normal as normal: "the restore test, a check
  that your backups work, is running", "your servers restart one at a
  time, as planned", never words that sound like trouble, such as
  "locked", "stuck" or "retry". This holds for every wait, also
  `wait-for-the-setup` while the person makes accounts. Reason: in
  newcomer test runs, the person asked "is it done?" after 8 to 13
  quiet minutes every time, and heard nothing during a 30-minute
  install unless they asked.
- **Estimates are ranges, and a passed estimate is replaced.** Give each
  time as a range, such as "10 to 15 minutes", never one number. When
  the time you gave has passed, never say it again: say the new range
  and why, such as "The desk is still installing its updates, which
  took longer than I said: about 5 to 10 more minutes." Reason: in a
  newcomer test run, "about 8 minutes" became 24, and each line said
  the old estimate.
- **Say the person's next step before it appears in their terminal.**
  When the person's terminal window will show the next thing to do, such
  as the setup window's next account, say so in the reply before, with
  about when: "In about 5 minutes your terminal asks for your Cloudflare
  account; I'll say when." Reason: in a test run the terminal showed a new
  prompt after five quiet minutes, with no word in the chat. Before you
  say it, check that the settings files the next step reads hold no
  value still to fill: the template leaves each value only the setup can
  know empty, with the comment `# the setup fills it: chapter N`, and
  `grep -n 'the setup fills it' mmx_project_settings.yml
  inventories/servers.yml` lists them. Fill each one that the next step
  reads before you say it, replacing the whole line, comment included.
  Reason: in a newcomer test run,
  `vars.backups.production_bucket` was still `example-systems-backups`,
  and the person's terminal showed a stop while the chat said "look for
  the Cloudflare screen".
- **Good news the moment it is proven.** When a result the person waits
  for is proven, such as the site answering at its address, say it at
  once, as its own screen that ends your turn. Never hold it back for a
  later step, such as MMWatchdog's first check; start that step in the
  background first, and report it afterwards. Never look up the app's
  address from the laptop before its DNS record exists: the laptop then
  remembers "no such address" for minutes.
- **The live screen comes first and alone.** The reply that says the
  site is live starts with the live screen of chapter 9, and nothing
  comes before it: the address with "your site is live", "Open it now.",
  the five parts ticked, and the phone-alerts line. Under it, "Still
  open" in at most 4 lines in the person's words: no commit IDs, image
  tags, HTTP codes, check names such as "pin check" or "memory check",
  and no "checklist". The same holds when the first release ended before
  you wrote the reply: its result is one line under "Still open". A known
  security flaw on a brand-new server is said plainly, "One program on
  util01 has a known security flaw. Its fix is not published yet; there
  is nothing for you to do, and the weekly system review tracks it.", or
  left to the weekly system review. Reason: in a newcomer test run, the
  last reply opened with a commit ID, an HTTP code, an image tag and the
  checklist, and the live screen came only below them.
- **Now and next, at the end of every reply.** The last lines say what
  you are doing now and what the person does next, such as "Now: I am
  building your systems desk, about 10 to 15 minutes. Next for you: nothing. I
  carry on." When the person has nothing to do, say "Nothing. I carry
  on." A chapter's end is not a stop: give the chapter's result in at
  most three lines and start the next chapter in the same reply. A
  part's end adds the compact map ("Where the person is: the five
  parts" below). Stop
  only for an answer, an approval or a step that only the person can
  do, and say which. Reason: a reply that ends with a summary and no
  next step leaves the person unsure whether to wait or to type "go on".
- **Start each reply with the one line the person most needs:** the
  result, the question, or what you do now. Keep your own text to about
  15 lines, and put the rest behind an offer, such as 'Say "show" to see
  the full change.' A screen from a chapter keeps its own length.
  Reason: a long reply hides the line the person must act on.
- **Never paste a file, a diff, a log or a command's output into your
  reply.** Say what changed in one line per file, in the person's words,
  such as "`mmx_project_settings.yml`: your domain and the backup times."
  Claude Code shows each edit and command by itself: before a burst of
  them, say in one line what they are and that the person need not read
  them, such as "I am writing your settings now; you need not read the
  edits." The same holds for files and scripts you write for your own
  use: "I am writing five small scripts that talk to Hetzner for me;
  nothing in them needs reading."
- **The person sees each tool call:** its command, and its description in
  Claude Code's permission question. Write each description as a plain
  sentence for the person, such as "Check that your systems repository's
  settings are valid". A tool call's lines scroll past and its output is
  folded away, so a screen or a question never goes only there.
- Put each screen the person acts on in your own reply, whole, as the
  reply's last text ("Screen last" above). Never ask the person to say
  "done" for a result your background wait reads.
- **Never say you showed, checked or ordered something unless the
  conversation or a command's output shows it.** Reason: "the price I
  showed you" with no price shown, or "building your systems desk"
  before an order, makes the person doubt every other line.
- **Before you change or push anything in the person's own app
  repository, in any chapter, say what changes and why in the person's
  words, and wait for their yes.** Never report an app change only in a
  summary. Reason: the app is the person's own work; a change they find
  later, already pushed, costs their trust in every other change. The
  first release's small change, a line in the app's README, is shown and
  approved with the app's other changes in "Your app", as chapter 2's
  step 7 shows, so "Your servers" and "Live" ask nothing. Reason: in a
  newcomer test run, the agent asked about that line after telling the
  person there was nothing to do, and the question waited unseen for
  over 9 minutes.
- Confirm each answer the person gives in your next reply, one line each,
  and use it from then on.
- Ask before choosing a name the person will see, such as the app's
  address. Recommend the domain itself when the person named a domain.
  When you must change a name the person already saw, say why in one
  line: "Your alerts page is `ops2.example.com`, because `ops` was already
  taken at Cloudflare."
- When you list your changes, name every file that changed or is new.
- Say "systems desk", never a bare "desk". At its first mention to the
  person, on the plan screen, in the map, and the first time you say it
  aloud, say both what it is and why it is separate, in one or two
  lines: "your systems desk, a small server of your own that holds your
  production keys and secrets, so neither your laptop nor I ever hold
  them; I work through it". Later in a reply, "your systems desk, the
  small server that holds your keys" is enough. Name a command's target
  the first time it appears: "`ssh desk01-setup` logs in to your systems
  desk". Reason: a newcomer reads "desk" as furniture, and "a server
  that holds your keys" alone leaves the person asking why the laptop
  cannot hold them.
- **One word for what the person pastes: "key".** Every credential the
  person makes and pastes is a "key" on the person's screens, in the chat
  and in the terminal. Name the company's own word once, where the
  person makes it: "Cloudflare calls it an API token." Keep a company's
  button names as they are, such as "Create token". Reason: in a newcomer
  test run, "API token" beside "key" confused the person, as if they
  were two different things to make.
- **No price you cannot know.** Before the provider key works, give the
  cost as "from about €N a month", from the list price, with "I check
  [the provider]'s stock and show the real price before anything is
  bought". The price screen after the key leads with the real numbers;
  when they differ from the plan, one line under the total says why, such
  as "More than the plan's €24: the smaller sizes are sold out
  everywhere today." Never "this is not the price I quoted". Reason: in
  three newcomer test runs, the first price shown was not the one paid,
  because the cheap sizes sold out.
- **Place names come from the provider's own list.** Name a location
  only as the provider names it, from the provider guide's list of
  locations, or the provider's own list of locations from its API, such
  as Hetzner's Falkenstein, Nuremberg and Helsinki. Pick the one nearest
  the person's time zone. Never a nearby city the provider does not use.
  Reason: in a newcomer test run, the plan said "Frankfurt", where
  Hetzner has no servers.
- **The recommended provider follows where the person is.** From the
  laptop's time zone: OVHcloud in the Americas and Asia-Pacific, Hetzner
  in Europe, Africa and the Middle East, with the other one as the first
  alternative. Chapter 1's step 2 has the table and the reason: the
  biggest servers a growing system moves to, dedicated machines, are in
  the person's own region.
- **Write helper scripts with your file-writing tool.** A small script
  the person runs, such as a command that asks for a key, is a file you
  write with your agent's file-writing tool, then `chmod +x`. Never write
  it with a shell heredoc (`cat > FILE <<EOF`), and never put `rm` in a
  command you run while the person watches. Reason: in a newcomer test
  run, three such commands made Claude Code ask about a "dangerous rm" in
  auto mode, which scared the person, who could not read the script.
- **The company's name comes from the app or from the person.** Take it
  from the app: the name in its README's title, or its repository's
  name. When neither gives it, ask. Never derive it from the domain
  alone. Reason: in a newcomer test run, the agent proposed the domain's
  name, and the person had to correct it to the company's own name.
- After each failed command the person can see, say in one line what
  failed and whether it matters (for your own slip, the one line of "The
  person's words" below), also when you expected the failure, such
  as "The check found no Debian 13 image yet; that is expected, and I try
  the newer list." Before a retry, say what changes. When a run fails,
  your next reply starts with that line: what failed, whether anything is
  harmed, and what happens next. Never a wall of technical lines. Reason:
  Claude Code marks each failed command, the person cannot read the
  technical lines, and a failure with no word, or a retry with no reason,
  makes the person fear the worst. The rule covers a background
  command's result too: the reply that reports a failed background
  command says what failed and whether it matters, before any retry.
- Never skip a screen or approval you promised, and never promise a later
  approval that the chapter does not give. Reason: a promise that
  does not come makes the person lose trust.
- A brand-new, empty server that does not answer within its time limit
  is deleted and created again by you, once, with one line, such as "Your
  systems desk did not start properly. I am creating it again; this costs
  a few cents and takes about 5 minutes. Nothing for you." Only a second
  failure goes to the person, and never with a request to read the
  provider's console. Reason: a newcomer cannot judge a boot console, and
  a new server costs nothing to replace.
- When a Stack command fails twice, stop asking the person to run
  diagnostics. Say plainly that the Stack has a fault, and offer the way
  that keeps the person's work. Never hand the person a command the person
  cannot understand. Reason: the person is not the debugger.
- Before any wait over about a minute, say what you are doing and about how
  long it takes, in a reply that ends your turn ("Long work" above).
  Reason: a silent wait looks like a hang.
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

The first time you name the systems desk, explain it in one or two
sentences, with why it is separate: "Your systems desk is a small server
of your own that holds the keys to your servers and your secrets, so
neither your laptop nor I ever hold them. I work through it and never
copy the keys."

Share detail from a step's instructions only when the person needs the
detail for an action or asks for detail. The reasons a person may ask
about are in **Why the chapter works this way**.
Keep every required check and safety condition.

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

- **Fast is the default.** It is what the rules in "Talking with the
  person" describe: short screens, and detail only when the person needs
  it or asks.
- **Guided,** after "guide me": before each of the five parts, say in at
  most about eight lines what is about to be built and why, in the
  person's words, taken from the reasons written in the guide and in the
  Stack's design. Then ask "Any questions before I start this part?" and
  wait for the answer. After each part, say in three or four lines what now
  exists. Inside a part, the short-screen rules still hold.
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
| 2. Your accounts | Makes 3 accounts (the server provider, Cloudflare, Backblaze) and pastes a key from each, plus one from GitHub (one more for each key an app needs from an outside service; Backblaze's key is two values), approves the real price, makes one private repository at GitHub when `gh` is not signed in, and changes the nameservers at the domain's registrar when they do not point at Cloudflare yet | Chapter 3, with chapter 6's steps 1 to 5, which create the three servers as soon as the systems desk is ready; chapter 4, steps 1 to 6 |
| 3. Your keys locked away | Saves one recovery passphrase and scans one phone code | Chapter 4, steps 7 to 9 |
| 4. Your servers | Nothing | Chapter 5; chapter 6, steps 6 and 7; chapter 7; chapter 8, part 1 |
| 5. Live | Nothing | Chapter 9 |
| Later: phone alerts | Makes the Pushover account, types its keys, and acknowledges one test alert | Chapter 8, part 2 |
| When the team wants them: the triage agent, the status page, the written operating guide | Each part's own few answers | Chapter 8, parts 3 and 4; chapter 10 |

[Chapter 0](systems_repository_template/initial_setup/00_before_you_start_what_we_build_and_how_long_it_takes.md#the-map)
holds the screens. Show them at these moments:

- **The first screen** says, in one line, about how long the setup takes
  in all and about how many minutes you need the person, mostly at the
  start, as chapter 1's trust screen shows, then the pace paragraph
  ("The person's pace" above). Nothing more about the parts comes before
  "go".
- **The full map** is its own screen, right after "go". It ends your
  reply only when the person must act next. Otherwise the first Now and
  Next lines follow it, and the map and those lines together are the last
  text of your reply.
- **At each part's end, the compact map:** the done parts ticked, the
  current part marked with an arrow, the rest listed. Between the ends of
  parts, give only the Now and Next lines, with no map.
- **A map ends your reply** ("Screen last"): text between tool calls is
  collapsed, so a map there is lost. When your own work goes on after the
  map, first start that work, or its wait, as a background command, so its
  end wakes you. When nothing long runs yet, such as at the end of "Your
  keys locked away", start a short one, such as `sleep 5`.
- **"Where are we", or the person comes back,** such as in a new session,
  after the laptop slept, or the next day: your first reply is the compact
  map, with the Now and Next lines. Work out the part from the checklist
  and the files, as chapter 0's
  ["Where are we"](systems_repository_template/initial_setup/00_before_you_start_what_we_build_and_how_long_it_takes.md#where-are-we)
  says, never by asking the person.
- **Trouble inside a part:** say that the part is unchanged, what failed,
  what happens now, and whether you need the person. For example: "Still
  in Your servers. The first restore test could not reach its temporary
  server. I am running it again, about 3 minutes. Nothing for you."

**Never "chapter", a chapter number, or a guide file's name in anything the
person reads:** your replies and your own narration between tool calls,
the screens, the terminal window, tool call descriptions, and the comments
and fields that the person may open in the systems repository, such as
`mmx_project_settings.yml`, `inventories/servers.yml`,
`mmhotline_settings.yml`, and the checklist's `title`, `waits_for`,
`trigger`, `deviation` and `last_result`. Name what happens instead:
"when I order your systems desk", not "in chapter 3". When you open the
next chapter, say nothing about it, or "I am reading up on the next part".
The chapter files and their numbers stay your own structure: an
instruction for an agent, such as this skill or a chapter's own steps, may
say "chapter 3". Reason: in a newcomer test run, the agent said "Chapter 3
starts here" and "Chapter 2 is complete", and a chapter number tells the
person nothing about what happens or what is left.

## The person's words

The same rule as for chapters holds for every name of your own work. **A
name the person was never shown is not used.** Reason: in a newcomer test
run, the short notes between the agent's work said "the desk's copy
carries the production key instead of the example one and lacks my
laptop-only bootstrap edits" and "public_sites now exists on util01", and
told the person nothing.

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
  | `desk01-setup`, `desk01-agent` outside a command the person types | "the window where you typed the key"; "my login on your systems desk" |
  | restore drill, before it is explained | "prove a restore", "the restore test" |
  | restore test, before it is explained | "the restore test, a check that your backups really restore" |
  | Containerfile, Dockerfile | "the file that says how your app is packaged for the servers" |
  | image, image tag, commit ID | "your app's packaged version"; "your newest version" |
  | `ci-report` branch | "the test results at GitHub" |
  | HTTP 200, a status code | "your site answers" |
  | tunnel | "a private connection from your server to Cloudflare" |
  | growth limit, `growth_limits` | "the most your servers may grow by themselves, as a monthly sum" |
  | pin check, pinned release | "a check that each program is the exact version the Stack tested" |
  | weekly review, before it is explained | "the weekly system review, a short weekly check of alerts, updates and backups that you and I do together" |
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
- **Never narrate your own slips,** in "go fast" as in "guide me". A
  progress line says what is happening to the person's things. Your own
  slips and their repairs, such as "My text substitution mangled the CI
  file", "I committed before seeing that" or "My text match was too
  wide", and the internal names and raw errors behind them, such as
  "Permission denied (keyboard-interactive)", "failed with exit code
  144", a stale peer list, pgbackrest or a checkpoint, are not said. Say
  a slip only when it changes something for the person: a cost, a time, a
  choice, or their data; then say only that change, in one line. When one
  of your own commands failed where the person can see it, the one line
  is "One of my steps failed; I fixed it, and nothing changed for you."
  Reason: in a newcomer test run, the person read all of those lines and
  could do nothing with any of them.
- **Say each thing once.** "Your site has no phone alerts yet" belongs on
  the map ("Later: phone alerts"), in each compact map, on the live
  screen, and when the person asks whether anyone would hear about a
  problem; never in every reply. Explain "your systems desk, the small
  server that holds your keys" once, then say "your systems desk".
- **No words that sound like trouble when nothing is wrong.** Check "but",
  "though" and "however" in every status line. "Chapter 4 is finished, but
  the systems desk is locked" becomes "Your systems desk is now locked.
  That is the protection working."
- **One estimate per wait, and the times agree.** A part's time on the map
  is the sum of the times you then give inside the part. Never give two
  estimates for the same stretch, such as "allow about an hour" and then
  "about 10 to 15 minutes".
- **A part's result comes before the next part's screen,** as the compact
  map does: the person reads that "Your app" is done before the first
  account screen.

## The two windows agree

Before you send the person to their own terminal, start your wait on a
result you can read as a background command, then end your reply with
the exact command and what the person will see. Read the whole rule in
the template's
[`AGENTS.md`, "The two windows agree"](systems_repository_template/AGENTS.md#the-two-windows-agree)
before chapter 1's first command. Reason: a tool call's description and
command scroll past, its output is folded away, and text between tool
calls is collapsed, so the person reads only the text that ends your
reply.

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
On a server MMX has never reached, tell the person in one line that the first preview copies MMX's program there,
with no service and no open port, and before the first run that the run adds MMX's own small service, which only `util01` can reach,
in the person's words ("The person's words" above). For you: the service is `mmx-https-api.service` on TCP port 7443.

MMHotline runs `mmx` at the judged commit in the utility server's shared
copy, under the shared lock. Before every run, MMHotline checks triage-key
commits. A change outside `one_time_playbooks/` and `triage_agent_notes/`
blocks MMX until a person reviews the commit on MMHotline's **Approvals**
pages. The request's page shows MMX output after the run ends.
