# Chapter 1: Answer two questions

**When:** first, when the person says "Set up the Monkeymaxxing Stack for
my app." in the app's folder, and the team has no systems repository yet.

**What this chapter does:** the person names the domain and the server
provider. You show every other choice as a default, on one screen, with
the monthly cost. The person's "go" approves the whole screen. Then you
install two tools and start the systems repository on the laptop.

**Who acts:** the person answers two questions and says "go". You work
out every other value from the laptop and the domain, and do the rest.

**Tell the person when the chapter starts:** the trust line and the auto
mode line below, then the first question.

Chapters 1 to 9 are the first part of the setup: the person's five parts,
from "Your app" to "Live". They end with the app live, protected and backed
up. Phone alerts are the alerts part of the setup. The triage agent, the
status page and the written operating guide are later parts, each a short
one. The person sees the five parts on
[chapter 0's map](00_before_you_start_what_we_build_and_how_long_it_takes.md#the-map),
right after "go" (step 4).

## Before you start

- **You do every step you can.** The person's part is only what a step's
  screen asks for. Use the person's signed-in tools when they show no
  secret, such as `gh`. Never ask the person for a value that you can read
  from the laptop, the domain, or a service's API.
- **The screens.** Each chapter gives the exact text of each screen you
  show the person, in a `text` block. Show the screen's lines as they
  stand, with the team's own names and values in place of the example's.
  Show a line in capital letters on its own line, in bold. Keep each
  blank line: the blank lines make the screen easy to read.
- **Each screen goes in your own reply, whole,** as the skill's
  "Talking with the person" says, with the other rules for every reply.
- **Short messages.** Between screens, say what you do in one line at a
  time, such as "I am adding your domain at Cloudflare." Explain more
  only when the person asks.
- **Command blocks.** Every command block in the initial setup files
  starts with a comment that says where it runs.
- **Commits.** Commit each chapter's changes to the systems repository as
  you go, with a message that says what changed and why. Before the desk
  exists, the commits stay in the laptop's copy. From chapter 4 on, follow
  the systems repository's [`AGENTS.md`, "Making a change"](../AGENTS.md#making-a-change).

## First: the trust line and auto mode

Your coding agent's program may ask the person before each new command,
file change, or web page, such as Claude Code's "Do you want to proceed?".
The setup runs about a hundred commands, so ask the person at the very
start to run you in the agent's auto mode.

**Tell the person first,** in your first reply, before the first question:

```text
USE ONLY A CODING AGENT YOU TRUST.  It will have full control of your servers.

Trust means three things: it does the work well, it means you well, and you trust
the company that runs it, because your work passes through that company.
An agent you would not trust with your servers should never be used here.

Run me in auto mode for this setup, so I don't stop to ask before each step.
In Claude Code: press Shift+Tab until it shows "auto mode on".
Reason: the Stack needs a coding agent you trust, and anything that changes your live servers still goes through your systems desk and a `yes` you type.

The setup takes about an hour and a half.  I need you for about 20 minutes of it, mostly at the start.

By default, I'll go fast and only stop when I need you. Say "guide me" any time
and I'll slow down and explain each part before I do it. Say "go fast" to speed
up again. Ask "why?" about anything.
```

The time line is the only word about time and parts before "go": the
map of the five parts comes right after "go". The pace paragraph comes
again under the map; the skill's "The person's pace" says what "guide
me", "go fast" and "why?" change. Reason: the person has
already chosen the Stack and wants to start; newcomer test runs showed
55 to 70 minutes from the first question to the live site.

Then ask question 1 in the same reply. When the person's agent is not
Claude Code, say in one line how to use that agent's own auto mode, or
that it has none. Never write a permission list into the app's folder.

**Check:** you showed the screen, and recorded the domain once the person
answers.

## Steps

1. **The domain.**

   **Ask the person,** in your first reply, with no command before it:

   ```text
   First question:  which domain is your app on?  (for example  example.com)
   ```

   **Check:** you recorded the domain.

2. **The server provider.** Read the [provider guides](../provider_guides/README.md).

   **Recommend by where the person is,** from the laptop's time zone
   (`readlink /etc/localtime`, as step 3 reads it; the person can change
   it):

   | The laptop's time zone | Recommend | First other choice |
   | --- | --- | --- |
   | The Americas (`America/...`) | OVHcloud | Hetzner |
   | Europe (`Europe/...`) | Hetzner | OVHcloud |
   | Africa and the Middle East (`Africa/...`, and the Middle East's `Asia/...` zones, such as `Asia/Dubai`, `Asia/Riyadh`, `Asia/Tehran` and `Asia/Jerusalem`) | Hetzner | OVHcloud |
   | Asia-Pacific (the other `Asia/...` zones, `Australia/...`, `Pacific/...`) | OVHcloud | Hetzner |

   Reason, which is also the answer to "why?": a system grows first by
   moving to bigger servers, and the biggest are dedicated machines.
   Hetzner's dedicated machines are only in Europe (Nuremberg and
   Falkenstein in Germany, Helsinki in Finland). OVHcloud also has them
   in North America (Hillsboro and Vint Hill in the USA, Montreal in
   Canada) and in Asia-Pacific (Singapore, Mumbai and Sydney). So each
   recommendation keeps the way to bigger servers in the person's own
   region; Africa and the Middle East are nearer Europe. Both are also
   cheap and simple. Checked on 2026-11-18 at
   `docs.hetzner.com/general/others/data-centers-and-connection/` and
   `us.ovhcloud.com/bare-metal/regions-availability/`. Say nothing about
   the other providers' offers or prices.

   **Ask the person,** in your second reply, such as for a laptop in
   `America/New_York`:

   ```text
   Second question:  which company should run your servers?

      I recommend OVHcloud.  It is cheap and simple, and it has bigger servers
      in North America for when your app grows.
      Other choices:  Hetzner, DigitalOcean, Vultr, Scaleway, AWS, Google Cloud.
   ```

   For a laptop in Europe, the first lines are "I recommend Hetzner.  It
   is cheap and simple, and it has bigger servers in Europe for when your
   app grows." and "Other choices:  OVHcloud, DigitalOcean, ...".

   **Check:** you recorded the provider, and read its guide.

3. **The defaults, on one screen.** Work out each value, then show the
   screen.

   - **Servers near:** the provider location nearest the laptop's time
     zone, such as Falkenstein for `Europe/Berlin` at Hetzner. Name only
     a location from the provider's own list: the provider guide's list
     of locations, or the provider's own list of locations from its API.
     Never a nearby city the provider does not use. Reason: in a newcomer
     test run, the plan said "Frankfurt", where Hetzner has no servers.
     Read the time zone with
     `readlink /etc/localtime` on a Mac or Linux, or
     `timedatectl show -p Timezone --value` on Linux. Pick the desk's
     location too: by default a different location of the same provider,
     so a production outage leaves the desk working. The separate place is
     a good default, not a must: when it costs more, chapter 3's price
     screen compares both places.
   - **Size:** the smallest system, three production servers and one
     desk. The fuller system adds `staging01`, a test server, and
     `app002`, a second app server.
   - **Your app's address:** the domain the person named, as named, such
     as `example.com`. The domain itself is the default. Never choose a
     name such as `shop.example.com` yourself: offer it only when the
     person asks, or when the domain already runs another site.
   - **Company name:** from the app: the name in its README's title, or
     its repository's name, such as `Example` for a repository named
     `example`. When neither gives a name, write "What is your company or
     project called?" on the screen. Never derive the name from the domain
     alone. Reason: in a newcomer test run, the agent proposed the
     domain's name, and the person had to correct it to the company's own
     name.
   - **Password manager:** the one the laptop has, such as 1Password,
     Bitwarden, or KeePassXC. On a Mac, look in `/Applications`. On Linux,
     look for `1password`, `bitwarden`, or `keepassxc` on `PATH` or in
     `~/.local/share/applications`. When you find none, or the person
     already named one, do not recommend one: write "Which password
     manager do you use?" on the screen. Reason: a recommendation to a
     person who has a manager reads as not listening.
   - **Your name on the desk:** the laptop's user name, `$USER`.
   - **Status page and alerts page names:** `status.` and `ops.` before
     the domain, such as `status.example.com` and `ops.example.com`.
     Reason: `go-live` refuses a name that is still the template's
     example, so chapter 1 fills both for the person's yes. Chapters 5
     and 8 check that the domain has no DNS record for each name, and
     pick another when it has.
   - **Sign-in email:** read `git config user.email`. Use it as the
     default when it looks real: it has a domain that is not
     `example.invalid`, `example.com` or `localhost`, and no `noreply` in
     it. When it is empty or such a placeholder, say so on the screen and
     ask for an address the person reads today. Never offer an address on
     the new domain, unless the person says mail already works there.
     Reason: the sign-in link for the private alerts page, and the
     setup's notices, go to this address, and the new domain has no
     mailbox yet.
   - **Cost, an estimate:** the desk and each of the three servers, each
     with its public address, from the provider's public price list or
     public catalog, as the provider guide says, plus backups. Round to
     one sum, "from about €N a month". Name every paid thing across the parts
     of the setup: the servers, backup storage, and the one-time fee for
     phone alerts. When you leave a paid thing out, say plainly that it
     comes later and has a fee. Reason: a paid service that appears in
     the middle of a part feels like a trick. When the guide names a
     public stock route, plan with sizes it lists as sellable now. The
     real price, checked against the provider's stock, comes once, right
     after the provider key works, in chapter 3's
     [the real price, approved once](03_make_your_server_account_and_your_systems_desk.md#the-real-price-approved-once),
     before anything is bought. Reason: stock changes by the hour, and
     most providers show it only with the key; in a newcomer test run the
     cheap sizes sold out between this screen and the order, and €27
     became €68.
   - **Growth, as money:** from `growth_limits` in the template's
     `mmx_project_settings.yml` and the same prices, work out the most
     the servers may add by themselves without asking the person: for
     each pool, the servers above the first system's count, up to
     `largest_number_of_servers`, each at the price of the pool's
     largest type in `server_types`. With the template's limits, that is
     3 more app servers and 1 more database server, so N is 4 and M is 2.
     Add the jobs and load-balancer servers that the limits allow on a
     second line, "Later pools, only when their operating procedure adds
     them", with their cost. Round X up. Reason: "limits on growth" means
     nothing to a newcomer, and a monthly sum the person approved is no
     surprise on the bill.

   **Ask the person,** as the last text of your reply, with no tool call
   after it:

   ```text
   Here is what I will set up.

     Servers near:       Falkenstein         (from your laptop's time zone; change it if your users are elsewhere)
     Size:               the smallest system: 3 servers, and 1 systems desk
                         (your systems desk is a small server of your own that holds your keys and secrets,
                          so neither your laptop nor I ever hold them; I work through it)
     Your app's address: example.com
     Company name:       Example             (from your app; change it if it is wrong)
     Password manager:   1Password
     Sign-in email:      alex@gmail.com      (a mailbox you read today)

     Cost:               from about €24 a month.  I check Hetzner's stock and show you
                         the real price before anything is bought.

   Say "details" to see everything this includes.
   Tell me what to change, or say "go".
   ```

   Keep the screen to these lines. Reason: a newcomer reads a short
   screen; a long one hides the lines that matter. Write nothing below
   the screen: no second sign-in email line, and no alerts sentence.
   The cost line is one sum: the systems desk and the three servers, each
   with its public address, plus backups. It always reads "from about €N
   a month" and ends with "I check Hetzner's stock and show you the real
   price before anything is bought", with the provider's name. Reason:
   the price depends on what the provider has in stock at the moment of
   the order, which nobody can know before the key works. When no name
   for the company is found, the company line reads:

   ```text
     Company name:       what is your company or project called?
   ```

   **"details"** shows the rest, as one reply that ends your turn, then
   the same question:

   ```text
   Everything "go" approves:

     Servers:            from about €24 a month at Hetzner, from Hetzner's price list
                         (one line per server with its list price: the systems desk, app001, db01, util01)
     Backups:            Backblaze, a few cents a month at first
     Later, phone alerts: Pushover, a one-time fee of about $5 for each phone
     Growth:             your servers may grow by themselves to at most 4 app servers and 2 database servers,
                         up to about €36 a month more, without asking you
     Restore test:       a weekly test that your backups restore
     Your name on the systems desk:  alex  (your laptop's user name)
     Status page:        status.example.com  (the public page where your customers see if your site is up)
     Alerts page:        ops.example.com     (your private page for alerts: only your team signs in)
     Sign-in email:      from your Git settings; it signs you in to the alerts page and gets the setup's notices
     Tools:              mmx and doubleshell, two small tools in your home folder

   Nothing is bought yet.  Right after you make your Hetzner key, I check what Hetzner has in stock
   and show you the real monthly price.  Your yes there approves it.

   Tell me what to change, or say "go".
   ```

   "go" approves everything on both screens, whether or not the person
   said "details": the plan (the desk and the three servers), the weekly
   restore drill, the default growth limits in `growth_limits` of
   `mmx_project_settings.yml`, and the two installs. It does not approve
   a price: the person approves the real monthly total once, on chapter
   3's price screen, and that yes covers the desk and the servers that
   chapter 6 creates. Promise only that one price screen. Reason: a
   promise the agent invents is a promise that breaks. Chapter 6 states
   the growth limit's money line again before it creates the servers.
   When Git's address is empty or a placeholder, the sign-in line reads:

   ```text
     Sign-in email:      which address do you read today?  (not one on your new domain, which has no mail yet)
   ```

   When the person asks what one line means, answer in one or two
   sentences, then show the screen again.

   When the person changes a line, confirm each change in your next reply,
   in one line each, such as "Password manager: 1Password, as you said.
   Your name on the desk: sam." A name the person gives for the desk
   becomes a user name in lowercase letters, such as `sam` for "Sam".

   **Check:** the person said "go", or you changed what the person asked
   and the person then said "go". Your next reply confirms each change.

4. **The tools.** Install the release of MMX that `stack_software.mmx`
   in the installed skill's `systems_repository_template/mmx_project_settings.yml`
   pins. Follow [MMX installation](https://github.com/monkeymaxxing/mmx#install).
   Verify the archive against `SHA256SUMS`, keep the complete archive
   layout in `~/.cache/monkeymaxxing-stack/desk-bootstrap-tools/`, and
   link `mmx` into `~/.local/bin`. Never fill a pin by hand.
   Install the release of doubleshell that `stack_software.doubleshell`
   pins, never a newer one: download
   `doubleshell-VERSION-PLATFORM.tar.gz` for the laptop's platform from
   the folder of the pin's `download_url`, such as
   `doubleshell-0.1.2-macos-arm64.tar.gz`, check its SHA-256 against
   `laptop_archive_sha256` for that platform, and copy the binary to
   `~/.local/bin`, as
   [doubleshell installation](https://github.com/monkeymaxxing/doubleshell#install)
   says. A SHA-256 that differs stops the install. The laptop also needs Git,
   OpenSSH, Bash, jq, curl, and OpenSSL. On Windows, every command runs
   inside WSL.

   **Tell the person,** right after "go": first confirm each change the
   person made, one line each, then show
   [chapter 0's full map](00_before_you_start_what_we_build_and_how_long_it_takes.md#the-map),
   with its Now and Next lines, as the last text of your reply. Start
   this step's install as a background command before you write the
   reply, so the install's end wakes you, as the skill's "Screen last"
   rule says. This is part 1, "Your app", of the person's five parts.

   Run both tools by their full paths on the laptop, `~/.local/bin/mmx`
   and `~/.local/bin/doubleshell`, as the laptop's command blocks do, also
   where a step names a command in the text, such as `mmx validate`. On the desk and the servers, `mmx` is on the path.

   **Check:** `~/.local/bin/mmx version`, `~/.local/bin/doubleshell version`, `git --version`,
   `bash --version`, and `jq --version`.

5. **Start the systems repository on the laptop.** `TEMPLATE_DIRECTORY`
   is `systems_repository_template/` beside the installed skill's
   `SKILL.md`. The repository's name is the company's name in lowercase
   words with underscores, followed by `_systems`, such as
   `example_systems`.

   ```sh
   # On the laptop. Replace TEMPLATE_DIRECTORY with the directory's path:
   mkdir -p ~/code
   cp -R TEMPLATE_DIRECTORY ~/code/example_systems
   git init -b main ~/code/example_systems
   ```

   Write the answers into the copy:

   - `project_name: example_systems` in `mmx_project_settings.yml`.
   - `nightly_work_starts_at` (UTC), a time when most users are away,
     and `maintenance_window`, a weekday evening, both in the servers'
     region's time. `weekly_work_day` keeps `sunday`.
   - `password_manager` under `vars` in `mmx_project_settings.yml`, such
     as `1Password`, from the screen. The account screens of chapters 3
     and 4 name it.
   - `desk01.vars.person_unix_username` in `inventories/servers.yml`.
   - The example person's name in the example keys: in place of `alex`,
     write the person's desk name in the key comment `alex on desk01`,
     in `desk01.vars.production_ssh_public_key` of
     `inventories/servers.yml` and in `root_ssh_public_keys` of
     `mmx_project_settings.yml`, such as `sam on desk01`. In
     `desk01.vars.allowed_laptops`, write the laptop's short host name as
     `laptop_name` in place of `work-laptop`, and `USER@HOST` in place of
     the key comment `alex@work-laptop`. The keys themselves stay the
     template's until chapter 3 writes the real ones: chapter 3 replaces
     `allowed_laptops`, and the systems desk's start replaces every key
     that ends in ` on desk01`. Reason: a stranger's name in the person's
     files reads as someone else's access.
   - `status_page_host_name` under `vars` in `mmx_project_settings.yml`,
     and `util01_private_page_host_names.mmhotline` beside it, from the
     screen's two names. The person's sign-in email goes into
     `mmhotline_settings.yml` in chapter 7.
   - `stack_commit` in `monkeymaxxing_stack_checklist.yml`, from
     `git -C TEMPLATE_DIRECTORY rev-parse HEAD` when the template belongs
     to a clone. Without a source clone, remove `stack_commit`.
   - With the fuller system, set `trigger` of `staging_server` and
     `second_app_server` in `monkeymaxxing_stack_checklist.yml` to
     `when your coding agent installs everything on your servers: the team chose the fuller system`.
     The person may read the checklist, so the value names no chapter.
   - What the triage agent may do,
     `what_the_triage_agent_may_do_without_a_person`, keeps the template's
     `routine_fixes`. The triage agent's part of the setup asks the person.

   The servers' production location and the desk's location go into the
   settings that chapter 3 and chapter 6 name.

   **Tell the person:** one short line as you go on to chapter 2, with
   no map, because "Your app" goes on: the map's Now and Next lines
   already said what comes. Never end the reply after this result, as
   the skill's "Now and next" rule says. For example:

   > Your systems repository is on this laptop at `~/code/example_systems`. Now I am reading your app's code, to see what it needs to run on your servers.

   **Check:** `~/code/example_systems` holds the template with the values
   above, and `mmx validate` passes there. `mmx validate` does not catch a
   value that is still the template's example, and `go-live` refuses one.
   Search the systems repository with your search tool for `example.com`,
   `example.invalid` and `example-`, and search `inventories/servers.yml`
   and `mmx_project_settings.yml` for `alex` and `work-laptop`. Replace
   each one that this chapter owns now: the status page and alerts page
   names, and the example person in the key comments `alex on desk01`
   and `alex@work-laptop`. The guides' example commands keep `alex`. The others belong to
   later chapters, which fill each before a step needs it: the app's
   address in chapter 2, the bucket names in chapter 3, the Cloudflare
   account and the registry account in chapter 4, and the example person
   in chapter 7.

## If something is different

- **The team has no domain yet** (step 1): the person registers one at
  Cloudflare in chapter 4, right after the Cloudflare account exists, at
  the price Cloudflare shows. The new domain needs no nameserver change,
  so chapter 4's registrar screen is skipped.
- **The laptop shows no password manager** (step 3): show
  `Password manager:  which one do you use?` on the screen, and take the
  answer. Only when the person has none, recommend Bitwarden: the person
  installs it before chapter 3, where the first login is saved.
- **The laptop lacks Git, jq, curl, or OpenSSL** (step 4): name each
  missing tool in the screen's install line.
- **A pin whose SHA-256 is all zeros** (step 4): the skill came from a
  Stack checkout that is not a release. Stop, and tell the person to
  install a released Stack version.
- **The person changes the size later:** follow
  [Add staging01](../operating_procedures/add_staging01.md) and
  [Add an app server](../operating_procedures/add_an_app_server.md), or
  "Removing staging01" in
  [Add staging01](../operating_procedures/add_staging01.md#removing-staging01)
  and [Remove a server](../operating_procedures/remove_a_server.md).

## Why the chapter works this way

**Two questions.** Only the domain and the provider need the person. Every
other value has a default that fits a small team, and the person sees each
default once, with the cost.

**The smallest system first.** The smallest system costs least and has the
fewest parts to learn. Either extra server can be added on a later day with
one operating procedure.

**The time zone stands for the users.** Most teams start near their users.
The region line says how to change the place, because a team with users far
away gets slower pages from servers near the laptop.

Next, in the same reply, as the skill's "Now and next" rule says: [Chapter 2: Get your app ready to deploy](02_get_your_app_ready_to_deploy.md).
