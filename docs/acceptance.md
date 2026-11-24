# Acceptance contracts of the Monkeymaxxing Stack

This page is for people and coding agents who change the Stack itself.
The contracts below state the required outcomes for changes to the stack.

- **The goal.** A startup founder or developer who is new to running
  servers sets up a production system with their coding agent in a few
  hours: the app is live, protected, and backed up in about an hour and a
  half, and phone alerts follow in about 15 minutes. At the end, the
  person's site is live, alerts reach the person's phone, and backups are
  proven to restore. The person is confident that the system works and
  understands how. Setup feels like steady progress, not an exam. Reason:
  this is the most secure stack the person will use, but only if the person
  uses the Stack. A setup that feels hard sends people to a system they
  build themselves, full of holes.

  Three rules follow from the goal. Every setup chapter, every item of the
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
     spends hours on an exam, and the Stack's tests already proved the
     software.
  3. **Defaults fit a small team.** Each default works for a team of one or
     two people with ordinary tools. A stronger option, such as a hardware
     security key or an alert that wakes someone, is a setting that a team
     can turn on. A stronger option is never a setup requirement. Reason: a
     requirement that a small team cannot meet stops the setup, and the
     team then builds something weaker by hand.

- **The person understands each step:** they can tell its purpose and its
  reason, the next action, who acts, where, and the expected result. The
  agent follows the [Plain English rules](../skills/monkeymaxxing-stack/systems_repository_template/talking_with_the_team.md#plain-english).
  The agent explains an unfamiliar term before the step that needs the
  term, and does not repeat what the person already knows.
- **A return to work:** the team's systems repository holds the guide for
  talking with the team, and the operating handover in its README. A new
  agent session finds the current links, failure behavior, and duties in
  the systems repository's README, without the setup conversation. The
  README holds only what the person reads; agent instructions live in the
  team's `AGENTS.md`, the triage agent's rules, and the operating
  procedures.
- **An alert asks for action:** an SOS means users are hurt now and the
  triage agent could not fix it; a warning means a person must act within
  days, or must know of a change that costs money or carries risk; info is
  everything else, including "checked, does not affect you". Every warning
  waits for the triage agent first, so the person hears its verdict, and
  an alert reaches people whenever the agent cannot look. One finding on
  many servers is one alert and one investigation. A finding the agent
  set aside, with a reason that holds for every server, stays quiet until
  its package, version, fix or advisory changes, and then alerts again;
  setting a finding aside never quiets an SOS, and an SOS always alerts,
  also in the scheduled review. The
  agent's run limit stops only agent runs, never alerts. A Stack release
  that fixes a flaw attackers exploit now warns every older system.
- **A short weekly review:** the weekly system review covers the week's
  alerts with the triage agent's runs and cost, the waiting updates with
  the findings set aside, the restore drill's result, and the
  checklist items that are due, with exact commands. The growth and
  improvement items keep their own section of the checklist with their
  triggers, never count as open, and the weekly review only checks
  whether a trigger arrived.
- **The agent drives changes:** a push starts no server change. The agent
  runs MMX at the pushed commit and verifies the result. Building an app
  image requires no CI. The helper
  reports the current lock holder and minutes waited every minute, with
  commands to inspect or stop an MMX run. A release to production waits
  for the person's yes while `production_releases_wait_for_a_persons_approval`
  is `true`, the template's value. Staging releases and rollbacks never
  wait.
- **Debian only:** server creation and restore drills use Debian
  13. Postgres 17 comes from Debian's packages, keeping distribution
  security-update and vulnerability checks covering Postgres.
  Supported releases must have Debian's regular security support and pass
  the lab runs that [docs/testing.md](testing.md) requires for a new
  Debian release, as [The server image in chapter 6 (create your three production servers: app, database, and tools)](../skills/monkeymaxxing-stack/systems_repository_template/initial_setup/06_create_your_three_production_servers.md#the-server-image) explains.
- **App containers stay confined:** web, jobs, and migration containers use
  the Stack's AppArmor profile. Apps can signal their own workers and stop
  cleanly during a service stop or a deploy. Web and jobs containers keep
  all Linux capabilities dropped and cannot gain new privileges.
- **An existing database moves last:** apps first reach the old PostgreSQL server over a temporary WireGuard peer.
  A managed move requires a session-mode PgBouncer relay with verified provider TLS and preserved migration startup options.
  Stack URLs keep their usual WireGuard-only connection settings.
  Logical replication populates the normal Stack formation while Stack app roles remain read-only.
  The switch verifies ready tables and durable replay, preserves sequences and large objects, and removes the old slots.
  The fence changes only moving database defaults and ends the listed app sessions, without requiring a source superuser.
  For relay moves, the switch disables and kills the app entries while a separate copy entry keeps replication reachable.
  Every failure before the Stack opens resets the database fence and reopens the relay app entries.
  Drivers reconnect without an app restart. A catch-up timeout resets the old database defaults.
  The proof records the HTTP write pause, every acknowledged write, replica state, backups, and old-system power-off.
- **Private administration:** each person's laptop reaches only the person's systems desk through doubleshell and a phone-code SSH login.
  The desk runs outside production's location, uses kernel `wg0`, and peers directly with production and staging servers.
  The desk is a locked key box: it holds the production key, the vault passphrase and the person's tokens, and no coding agent runs there.
  The person manages the desk through a separate root-owned loopback key, with `review-and-apply-the-systems-desk-settings`:
  an unchanged desk playbook runs at once; a changed one shows each change since the person's last
  desk review and runs only after the person types yes in the person's own terminal, which the coding agent cannot answer.
  The coding agent's relay to the person's SSH agent cannot load a library into it.
  Public TCP 22 stays closed on IPv4 and IPv6 from first boot.
  The laptop clears temporary bootstrap files and retains app work and desk-only login configuration.
  Phone, laptop, desk, and status-posting recovery procedures name the required independent account access.
  A lost laptop's recovery replaces the personal provider token the laptop held during setup. A person's leaving
  removes the departing desk's key from `root_ssh_public_keys`, which also ends its push rights to the main copy of
  the systems repository on `util01`. No desk or server key is registered at the Git host, which keeps only a backup
  that the laptop pushes and nothing reads.
  The person's provider token goes only to a provider guide's API address. The recovery passphrase is shown once,
  exactly as it opens the bundle, and cleared from the desk terminal after the person types back that exact text.
  Production servers retain account-owned tokens; only a person's desk holds personal tokens.
  At Cloudflare the person makes one token by hand, from the link the coding agent gives;
  the command makes every other token, the person's desk token and posting key named after the person, and
  deletes the link token when it ends. Replacing a Cloudflare or B2 key deletes the old one once the servers'
  run brought the new one and the person pressed Enter, so a routine replacement stops no upload; after a
  break-in, `--delete-the-old-keys-at-once` deletes it at once. A person's leaving
  deletes that person's Cloudflare tokens by name. No secret appears in the coding agent's conversation.
  The team uses one branch, `main`. Publishing a branch reports incoming changes, and stops on a rebase conflict
  with nothing changed.
  The setup offers only providers the coding agent can reach at `http://127.0.0.1:8081/` without reading the person's credential: Hetzner Cloud, DigitalOcean, Vultr, and Scaleway, where the API proxy adds the token, and OVHcloud, AWS EC2 and Google Compute Engine, whose APIs need each request signed or a token made from a key, where the same proxy signs the request.
- **One coding agent, on the laptop:** the person works with one coding agent, the one they already use, on their
  own laptop. It edits the systems repository in its clone on the laptop, and reaches the desk only through one SSH
  entry, `desk01-agent`, as the desk's `coding-agent` user. One phone code, typed in the chat, opens one shared
  login; the desk closes it after `coding_agent_login_idle_minutes` unused (60 in the template) and after
  `coding_agent_login_longest_hours` (10), so a changed laptop setting cannot lengthen it. Through that login the
  agent uses the production key's socket, `run-mmx-on-the-servers` (run as the `servers-mmx` account) and the API
  proxy, and never reads a key or a token. A run longer than a few minutes is a desk job that keeps running while
  the laptop sleeps; the agent reads its log and exit file later. Nothing on the desk needs resuming, and nothing
  is signed in there. The coding agent passes each key the person copies, or keeps in a laptop file the person
  names, straight to the desk's account command, which prints no key and reads none back. The person logs in to
  the desk only for the lock, a hidden prompt or a desk review, each one short command plus one phone code.
- **The team's main copy is on `util01`:** a root-owned bare repository that refuses force pushes and branch
  deletions. Only keys in `root_ssh_public_keys` can push to it. MMHotline and `util01` trust every commit on it
  (`systems_repository_commits.trusted_commits: every_commit_on_origin`); nothing is signed. MMHotline pushes the triage agent's
  commits only when they change nothing but its notes and one-time playbooks. The Git host keeps a backup that the
  laptop pushes with the person's own login; nothing reads from it, and a refused backup push is shown to the
  person.
- **One recovery passphrase:** the recovery bundle, `recovery_bundle.age`, holds every item a lost desk needs,
  for the desk that made it, which the bundle names, encrypted with one six-word passphrase that the person saves in the password manager. A copy sits in the locked
  backup bucket. Rebuilding a lost desk, a lost phone and a new team member's desk each start from it.
- **A practiced break-in response:** only a person starts or undoes a lock-out. The coding agent prepares and
  publishes the one-line inventory commit, `everyone_locked_out_except_desk`, and the person runs one command,
  the lock-out button, `ssh -t desk01 sudo lock-everyone-out`, for the desk that keeps access. The lock-out
  button pulls `main`, and goes on without the pull when `util01` does not answer; it shows every server
  and the desk that keeps access, and runs only after the person types `yes`. It runs only the lock-out copies
  that the person's last desk review installed, so a change that an intruder pushes to the main copy
  reaches it only through that review. It keeps the production key and WireGuard address of the desk that keeps
  access, and stops before changing any server when the inventory names others. Other desks keep local
  sessions but lose server keys, peers and established server access; server triage stops; customer-serving
  credentials stay, and no path between desks appears. The person and the coding agent keep working through the
  desk that keeps access. Ordinary runs keep containment, and refuse to start or undo a lock-out that the lock-out
  button did not make. Undo restores managed access. A separate
  status-page switch diverts public app requests. Retained logs reach the desk
  that keeps access and verified encrypted copies reach the backup bucket before rebuilding.
  The procedure covers company revocations, replacement, notices and extortion.
  The optional drills, in the checklist's growth and improvement items, use two actual desks and continuous customer requests.
  The setup runs no break-in drill, and prepares the response page.
- **Accurate protection claims:** what the agent says agrees with the
  current inventory and test results. Backup targets state the intended
  limit on lost database writes. Restore drills measure database restore
  time and how many seconds of writes could be missing at most. The time to
  recover the whole site includes getting the app and supporting services
  working again. A database restore time measures only database recovery.
  One database server has no automatic failover.

- **Copyable framework examples:** each app supplies accounts, shared revocable sessions, owned records, private documents and PostgreSQL report jobs.
  Separate web, migration, jobs and test-data seed commands meet the Stack's app contract.
  The seed runs only when `APP_ENV` is `development` or `staging`. Running the seed again leaves the fixed test records unchanged.
  `--accounts N` sets the number of invented accounts.
  Tests prove ownership refusals, object bytes, concurrent workers, interrupted jobs, additive migrations and graceful shutdown.
  Database primary selection preserves the Stack URL. Failed mutations never replay automatically.
  Each guide supplies additional-app settings and separates isolated evidence from required live Stack deployment proof.
  A fresh agent replays each guide before the local deliverable is complete.

The [design](design.md#the-persons-experience) gives the reasons. The
person never needs to read scripts, logs, or the whole checklist to find
the next action.
