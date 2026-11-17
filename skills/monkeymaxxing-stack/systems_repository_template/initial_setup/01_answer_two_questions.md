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

Chapters 1 to 9 are the first part of the setup, "go live". The first part ends
with the app live, protected and backed up. Phone alerts are the alerts part of
the setup. The triage agent, the status page and the break-in page are later
parts, each a short one.
[Chapter 0](00_before_you_start_what_we_build_and_how_long_it_takes.md)
holds the map of the whole system, for when the person asks.

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
```

Then ask question 1 in the same reply. When the person's agent is not
Claude Code, say in one line how to use that agent's own auto mode, or
that it has none. Never write a permission list into the app's folder.

**Check:** you showed the screen, and recorded the domain once the person
answers.

## Steps

1. **The domain.**

   **Ask the person,** in your first reply, with no command before it:

   ```text
   Two questions, then I start.

   1. Which domain is your app on?  (for example  example.com)
   ```

   **Check:** you recorded the domain.

2. **The server provider.** Read the [provider guides](../provider_guides/README.md).

   **Ask the person,** in your second reply:

   ```text
   2. Which company should run your servers?

      I recommend Hetzner.  It is cheap, fast, and simple.
      Other choices:  OVHcloud, DigitalOcean, Vultr, Scaleway, AWS, Google Cloud.
   ```

   **Check:** you recorded the provider, and read its guide.

3. **The defaults, on one screen.** Work out each value, then show the
   screen.

   - **Servers near:** the provider location nearest the laptop's time
     zone, such as Frankfurt for `Europe/Berlin`. Read the time zone with
     `readlink /etc/localtime` on a Mac or Linux, or
     `timedatectl show -p Timezone --value` on Linux. Pick the desk's
     location too: a different location of the same provider, so a
     production outage leaves the desk working.
   - **Size:** the smallest system, three production servers and one
     desk. The fuller system adds `staging01`, a test server, and
     `app002`, a second app server.
   - **Your app's address:** the domain the person named, as named, such
     as `example.com`. The domain itself is the default. Never choose a
     name such as `shop.example.com` yourself: offer it only when the
     person asks, or when the domain already runs another site.
   - **Company name:** from the domain, such as `Example` for
     `example.com`.
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
   - **Stock, before the cost:** check that the provider sells each
     recommended size in the chosen location now: the desk's size in the
     desk's location, and the servers' sizes in production's. Use the
     public route that the provider guide's "Stock" line names; it needs
     no key. Show only what can be ordered now, at its real price. When a
     recommended size is sold out there, offer the nearest location that
     has it before any dearer size or product. Never offer a kind of
     product the person did not ask about, such as a provider's hourly
     cloud servers in place of its monthly ones, without saying plainly
     why and what it costs a month against the plan on this screen. When
     the guide names no public route, the check happens with the key,
     before any order, in
     [chapter 3](03_make_your_server_account_and_your_systems_desk.md#the-provider-account)
     step 3, and the screen's cost line ends with
     `(price from Hetzner's list; stock checked before ordering)`.
     Reason: a price for a server that cannot be ordered is a promise that
     breaks after the person has made the account.
   - **Cost:** the real price of the desk and each of the three servers,
     each with its public address, from the provider's prices, as the
     provider guide says. Before the provider credential exists, read the
     provider's public price page or public catalog. Name every paid thing
     across the parts of the setup: the servers, backup storage, and the one-time
     fee for phone alerts. When you leave a paid thing out, say plainly
     that it comes later and has a fee. Reason: a paid service that
     appears in the middle of a part feels like a trick. Chapter 6 reads the prices
     again with the API.

   **Ask the person:**

   ```text
   Here is what I will set up.

     Servers near:       Frankfurt          (from your laptop's time zone: change this if your users are somewhere else)
     Size:               the smallest system (3 servers and 1 systems desk, the small server that holds your keys)
     Your app's address: example.com        (your domain itself: say if you want another, such as notes.example.com)
     Company name:       Example            (from your domain)
     Password manager:   1Password          (the one this laptop has)
     Your name on the systems desk:  alex           (your laptop's user name)
     Status page:        status.example.com (the public page where your customers see if your site is up)
     Alerts page:        ops.example.com    (your private page for alerts: only your team signs in)
     Sign-in email:      alex@gmail.com     (from your Git settings; it signs you in to the alerts page and gets the setup's notices. It must be a mailbox you read today)

     Cost:               about €27 a month for the servers at Hetzner  (price from Hetzner's list; stock checked before ordering)
                         (one line per server with its real price: the systems desk, app001, db01, util01)
                         Backups at Backblaze: a few cents a month at first
                         Later, phone alerts: Pushover, a one-time fee of about $5 for each phone

   I will also install two small tools in your home folder: mmx and doubleshell.

   "go" also approves a weekly test that your backups restore, and limits on how far your servers grow by themselves.

   Tell me what to change, or say "go".
   ```

   "go" approves everything on the screen and what comes with it: the
   prices of the desk and the three servers, the weekly restore drill,
   the default growth limits in `growth_limits` of
   `mmx_project_settings.yml`, and the two installs. Chapter 6 creates the
   servers at these prices without asking again. Never promise the person
   a later price approval. Reason: the chapters make none, and a promise
   the agent invents is a promise that breaks. When the price or the
   server type at creation differs from this screen (no stock, a changed
   price, a different size), stop and ask again with the new number,
   with the choices that the stock line above names.
   When Git's address is empty or a placeholder, the sign-in line reads:

   ```text
     Sign-in email:      which address do you read today?  (Git has no real address for you, only a placeholder. This address signs you in to the alerts page and gets the setup's notices. Not one on your new domain, which has no mail yet)
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

   **Tell the person:** one line, "I am installing mmx and doubleshell."

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
   - `status_page_host_name` under `vars` in `mmx_project_settings.yml`,
     and `util01_private_page_host_names.mmhotline` beside it, from the
     screen's two names. The person's sign-in email goes into
     `mmhotline_settings.yml` in chapter 7.
   - `stack_commit` in `monkeymaxxing_stack_checklist.yml`, from
     `git -C TEMPLATE_DIRECTORY rev-parse HEAD` when the template belongs
     to a clone. Without a source clone, remove `stack_commit`.
   - With the fuller system, set `trigger` of `staging_server` and
     `second_app_server` in `monkeymaxxing_stack_checklist.yml` to
     `chapter 7 (install everything on the production servers), step 10: the team chose the fuller system`.
   - What the triage agent may do,
     `what_the_triage_agent_may_do_without_a_person`, keeps the template's
     `routine_fixes`. The triage agent's part of the setup asks the person.

   The servers' production location and the desk's location go into the
   settings that chapter 3 and chapter 6 name.

   **Tell the person:** no message, because chapter 2 starts at once.

   **Check:** `~/code/example_systems` holds the template with the values
   above, and `mmx validate` passes there. `mmx validate` does not catch a
   value that is still the template's example, and `go-live` refuses one.
   Search the systems repository with your search tool for `example.com`,
   `example.invalid` and `example-`. Replace each one that this chapter
   owns, the status page and alerts page names, now. The others belong to
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

Next: [Chapter 2: Get your app ready to deploy](02_get_your_app_ready_to_deploy.md).
