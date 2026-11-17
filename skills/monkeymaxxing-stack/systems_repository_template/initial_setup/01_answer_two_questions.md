# Chapter 1: Answer two questions

**When:** first, when the person says "Set up the Monkeymaxxing Stack for
my app." in the app's folder, and the team has no systems repository yet.

**What this chapter does:** the person names the domain and the server
provider. You show every other choice as a default, on one screen, with
the monthly cost. The person's "go" approves the whole screen. Then you
install two tools and start the systems repository on the laptop.

**Who acts:** the person answers two questions and says "go". You work
out every other value from the laptop and the domain, and do the rest.

**Tell the person when the chapter starts:** no separate message. The
first question is the opening.

Chapters 1 to 9 are the first sitting, "go live". The first sitting ends
with the app live, protected and backed up. Phone alerts are the second
sitting. The triage agent, the status page and the break-in page are later
sittings, each a short one.
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
- **Short messages.** Between screens, say what you do in one line at a
  time, such as "I am adding your domain at Cloudflare." Explain more
  only when the person asks.
- **Command blocks.** Every command block in the initial setup files
  starts with a comment that says where it runs.
- **Commits.** Commit each chapter's changes to the systems repository as
  you go, with a message that says what changed and why. Before the desk
  exists, the commits stay in the laptop's copy. From chapter 4 on, follow
  the systems repository's [`AGENTS.md`, "Making a change"](../AGENTS.md#making-a-change).

## Steps

1. **The domain.**

   **Ask the person,** as the first message:

   ```text
   Two questions, then I start.

   1. Which domain is your app on?  (for example  example.com)
   ```

   **Check:** you recorded the domain.

2. **The server provider.** Read the [provider guides](../provider_guides/README.md).

   **Ask the person:**

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
   - **Company name:** from the domain, such as `Example` for
     `example.com`.
   - **Password manager:** the one the laptop has, such as 1Password,
     Bitwarden, or KeePassXC. On a Mac, look in `/Applications`.
   - **Your name on the desk:** the laptop's user name, `$USER`.
   - **Cost:** the desk and the three servers, each with its public
     address, from the provider's prices, as the provider guide says. Before
     the provider credential exists, read the provider's public price page
     or public catalog. Chapter 6 reads the prices again with the API.

   **Ask the person:**

   ```text
   Here is what I will set up.

     Servers near:       Frankfurt          (from your laptop's time zone: change this if your users are somewhere else)
     Size:               the smallest system (3 servers and 1 desk)
     Company name:       Example            (from your domain)
     Password manager:   1Password          (the one this laptop has)
     Your name on the desk:  alex           (your laptop's user name)

     Cost:               about €27 a month at Hetzner

   I will also install two small tools in your home folder: mmx and doubleshell.

   "go" also approves a weekly test that your backups restore, and limits on how far your servers grow by themselves.

   Tell me what to change, or say "go".
   ```

   "go" approves everything on the screen and what comes with it: the
   prices of the desk and the three servers, the weekly restore drill,
   the default growth limits in `growth_limits` of
   `mmx_project_settings.yml`, and the two installs. When the person asks
   what one line means, answer in one or two sentences, then show the
   screen again.

   **Check:** the person said "go", or you changed what the person asked
   and the person then said "go".

4. **The tools.** Install the release of MMX that `stack_software.mmx`
   in the installed skill's `systems_repository_template/mmx_project_settings.yml`
   pins. Follow [MMX installation](https://github.com/monkeymaxxing/mmx#install).
   Verify the archive against `SHA256SUMS`, keep the complete archive
   layout in `~/.cache/monkeymaxxing-stack/desk-bootstrap-tools/`, and
   link `mmx` into `~/.local/bin`. Never fill a pin by hand.
   Install doubleshell's newest release as
   [doubleshell installation](https://github.com/monkeymaxxing/doubleshell#install)
   says: download the archive, check it against `SHA256SUMS`, and copy
   the binary to `~/.local/bin`. The laptop also needs Git 2.34 or later,
   OpenSSH, Bash, jq, curl, and OpenSSL. On Windows, every command runs
   inside WSL.

   **Tell the person:** one line, "I am installing mmx and doubleshell."

   **Check:** `mmx version`, `doubleshell version`, `git --version`,
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
   cd ~/code/example_systems && git init -b main
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
   - `stack_commit` in `monkeymaxxing_stack_checklist.yml`, from
     `git -C TEMPLATE_DIRECTORY rev-parse HEAD` when the template belongs
     to a clone. Without a source clone, remove `stack_commit`.
   - With the fuller system, set `trigger` of `staging_server` and
     `second_app_server` in `monkeymaxxing_stack_checklist.yml` to
     `chapter 7 (install everything on the production servers), step 10: the team chose the fuller system`.
   - What the triage agent may do,
     `what_the_triage_agent_may_do_without_a_person`, keeps the template's
     `routine_fixes`. The triage agent's own sitting asks the person.

   The servers' production location and the desk's location go into the
   settings that chapter 3 and chapter 6 name.

   **Tell the person:** no message, because chapter 2 starts at once.

   **Check:** `~/code/example_systems` holds the template with the values
   above, and `mmx validate` passes there.

## If something is different

- **The team has no domain yet** (step 1): the person registers one at
  Cloudflare in chapter 4, right after the Cloudflare account exists, at
  the price Cloudflare shows. The new domain needs no nameserver change,
  so chapter 4's registrar screen is skipped.
- **The laptop has no password manager** (step 3): show
  `Password manager:  none found. I recommend Bitwarden.` on the screen.
  The person installs it before chapter 3, where the first login is saved.
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
