# Chapter 4: Set up your accounts and lock your systems desk

**When:** right after chapter 3 (make your server account and your
systems desk).

**What this chapter does:** the person types one command on the laptop,
`ssh desk01-setup`. The command shows the next two accounts, one at a
time: Cloudflare and Backblaze, with the domain's registrar between them
when the domain does not point at Cloudflare yet. Then one token at
the Git host, so the servers can download the app. Each value is checked
with its service at once. Then the lock: one recovery passphrase, and one
QR code for the phone. After the lock, the desk needs the laptop and a
code from the phone.

**Who acts:** the person signs up at Cloudflare and Backblaze, makes one
key at each and one at the Git host, changes the nameservers at the
registrar when needed, saves the recovery
passphrase, and scans the QR code. You watch the command's progress from
your own login, and do everything the person's keys let you do: the
domain at Cloudflare, its DNS records, and the lock.

**Tell the person when the chapter starts:** step 2's screen.

## Before you start

- **`set-up-outside-services go-live`** is the Stack's command for the
  accounts and the lock, installed on the desk. `ssh desk01-setup` starts
  it as the person, in the person's own terminal. Every screen below is
  the command's own text. The chapter shows each screen so that you know
  what the person sees, and can answer questions about it.
- **You never ask the person what the command printed.** The command
  writes its progress to `/var/lib/monkeymaxxing-stack/setup_results.json`:
  each step's name and state, `done`, `not_needed`, `in_progress` or
  `not_started`, and `stopped_with`, the reason a run stopped. Its
  `for_the_coding_agent` block holds values that are not secrets, which
  you write into the settings or check. The file never holds a secret.
  Wait for the file with `ssh desk01-agent wait-for-the-setup`, as step 2
  says, and read it again each time the person writes to you:

  ```sh
  # On the laptop:
  ssh desk01-agent cat /var/lib/monkeymaxxing-stack/setup_results.json
  ```

- **One message at a time.** When a screen is done, say in one line what
  you do next, such as "Cloudflare accepted your token. I am adding your
  domain at Cloudflare."

## Steps

1. **Open your shared login before the lock.** You did this step at the
   end of chapter 3, before the three servers were created
   ([Create the three production servers now](03_make_your_server_account_and_your_systems_desk.md#create-the-three-production-servers-now));
   check it, and do it now only when it was not done. Before the phone code
   exists, your login needs only the laptop key. Open the shared
   connection now. When the person takes longer than the desk's one-hour
   idle limit, the login closes, and step 8 says how to open it again.

   ```sh
   # On the laptop:
   ssh desk01-agent true
   ```

   Then move the laptop's bootstrap copy aside, and clone the desk's
   systems repository in its place. From now on you edit in the clone, as
   "Making a change" in [`AGENTS.md`](../AGENTS.md#making-a-change) says.
   The bootstrap copy is needed once more, for step 8.

   ```sh
   # On the laptop:
   mv ~/code/example_systems ~/example-setup/desk_bootstrap_copy
   git clone desk01-agent:systems_repository ~/code/example_systems
   ```

   **Tell the person:** no message.

   **Check:** `~/code/example_systems/ssh/open-the-desk-login --check`
   says the login is open, and `~/code/example_systems` is a clone of the desk's
   repository.

2. **The desk's setup command.** The laptop key command from chapter 3
   is still open in the person's terminal, waiting for
   `~/example-setup/desk-ready`. Make that file now, empty, with your
   write tool, and the key command runs `ssh desk01-setup` by itself in
   the same window, so the person types nothing.

   **Ask the person:**

   ```text
   Your systems desk, the small server that holds your keys, is ready.

   The window where you typed the Hetzner key goes on by itself now.
   It shows the rest of "Your accounts", one screen at a time: 2 more accounts, one more key,
   and a change at your domain's registrar if one is needed.
   Then it goes on to "Your keys locked away": one passphrase and one code for your phone.
   I carry on by myself when it is done.
   Ask me here at any time if a step is unclear.

   If you closed that window, type this in a terminal instead.
   It logs in to your systems desk:

     ssh desk01-setup
   ```

   First start the wait for `go-live` as a background command, as
   [`AGENTS.md`, "The two windows agree"](../AGENTS.md#the-two-windows-agree)
   says. Then end your reply with the screen, whole, as its last text:
   your turn ends there, with no tool call after it.

   ```sh
   # On the laptop, as a background command. Waits up to 5 minutes for go-live to finish or stop;
   # start it again while go-live runs.
   ssh desk01-agent wait-for-the-setup --at-most-minutes 5
   ```

   It prints the steps as they change, and a line at least once a minute.
   It ends with the results file's summary: the steps, `finished`,
   `stopped_with` and `for_the_coding_agent`. Exit 0 means `go-live`
   finished, 1 that it stopped, and 124 that it still runs at the bound.
   When it ends with a stop, say at once, in one plain sentence, what
   `stopped_with` says and what happens next: a refusal before the first
   screen, such as a setting that is still the template's example, is in
   `stopped_with` too. Fix the setting, publish it, and ask the person to
   type `ssh desk01-setup` again.
   A stop counts only when the run wrote the file after the wait started,
   so an earlier run's `stopped_with` never ends the wait for the next run.
   The wait is one more session on your shared login, and the person's
   `ssh desk01-setup` is a separate login, so neither blocks the other.
   Both go through the same doubleshell tunnel, which serves several
   connections at once.

   When the person writes to you meanwhile, answer, read the results
   file, and do the work of each step that is done, such as step 3's; the
   background wait keeps running. When `finished` is true, carry on with
   the steps below without being told. With `stopped_with`, tell the
   person the reason in plain words and what to do. At exit 124, start
   the same wait again in the background, and end your reply with one
   line that you still wait for the setup window. An agent with no
   background commands ends its reply with the screen and "When it says
   Go back to your coding agent,  tell me "done" here.", and then runs
   the same wait in the foreground: it ends at once when `go-live`
   finished.

   **Check:** the results file shows that `go-live` started.

3. **Cloudflare.** The command shows:

   ```text
   Your accounts: account 2 of 3, Cloudflare (your web address and protection)

   What this is for:
     Cloudflare puts your site on the internet and keeps your private pages private.

   Do this now:
     1. Open  https://dash.cloudflare.com/sign-up  and make an account.
     2. Save the login in 1Password.
     3. Turn on two-step sign-in, which Cloudflare calls  Two-Factor Authentication:
          https://dash.cloudflare.com/profile/authentication
     4. Open this link.  It fills in the key for you:
          https://dash.cloudflare.com/?to=/:account/api-tokens&permissionGroupKeys=...&name=...
        The page is long.  Scroll to the bottom, below the list of permissions.
        Press  Review token,  then  Create token.

   Then paste the key here.  Cloudflare calls it an API token.

     Cloudflare key (hidden):
   ```

   When an app keeps uploaded files, the screen has one more step before
   the link: turn on R2, where the app keeps its uploads, with R2's price,
   from the command's own lines:

   ```text
     4. Turn on R2, where your app keeps its uploaded files:
          https://dash.cloudflare.com/?to=/:account/r2/overview
        Finish the checkout there.  It asks for a card.
        It costs nothing up to 10 GB of files a month.
        Above that:  $0.015 for each GB a month,
                     $4.50 for each million file writes after the first million,
                     $0.36 for each million file reads after the first 10 million.
        Downloads to your users cost nothing.
   ```

   The link is the one the command prints, with the team's own token
   name. The command checks the token and prints `Cloudflare accepted the
   token.` The link token can only make tokens. With it, the command makes
   the person's desk token and starts the desk's API proxy, adds the
   domain to the account, copies the domain's DNS records with
   Cloudflare's scan, gives the account its workers.dev address, makes the
   tunnels `example_systems-apps` and `example_systems-util01` with their
   tokens in the vault, makes the servers' Cloudflare keys (the table in
   [chapter 5](05_put_your_site_behind_cloudflare_and_lock_your_private_pages.md#steps)),
   and adds One-time PIN, Access's login method that emails a code. When
   an app keeps uploaded files, it waits until R2 is on, saying so, and
   then makes the app's uploads bucket and its key in the same run. Then
   it deletes the link token. The status page waits for its own part of the setup.

   When the results file shows the step `cloudflare` done:

   - Write `cloudflare_account_id` from `for_the_coding_agent` into
     `vars.cloudflare_account_id` in `mmx_project_settings.yml`, and
     commit it in your clone. Publish it once `go-live` has finished
     (step 7's check), as "Making a change" in
     [`AGENTS.md`](../AGENTS.md#making-a-change) says. Reason: `go-live`
     saves keys in the vault of the desk's checkout and commits them only
     later, and `publish-branch-to-main` refuses a checkout with changes that
     are not committed.
   - Check the scan's records through the proxy at
     `http://127.0.0.1:8082/` on the desk. Read the current records with
     `dig` against the old nameservers, for the domain itself, `www`, the
     MX records, and TXT records such as SPF and `_dmarc`, and add each
     record that the scan missed. The MX records come first, because
     without them the company's email stops arriving.

   **Tell the person,** when your wait ends: one line about each
   piece of work, such as "Cloudflare accepted your token. I checked your
   domain's DNS records at Cloudflare."

   **Check:** the step `cloudflare` is `done`, and
   `vars.cloudflare_account_id` is committed in your clone.

4. **The domain's registrar.** The command reads the domain's registrar
   and its DNSSEC state from the registry's RDAP service, and shows the
   zone's two Cloudflare nameservers. A domain that already points at
   Cloudflare skips the screen, and the step shows `not_needed`. The
   screen has no account number: the account screens count only the
   accounts the person makes in this setup (Hetzner 1 of 3, Cloudflare 2
   of 3, Backblaze 3 of 3), so a skipped registrar screen never leaves a
   gap in the count. Every screen's title starts with "Your accounts:",
   the person's part.

   ```text
   Your accounts: one change at your domain's registrar (Namecheap)

   What this is for:
     Your domain must point at Cloudflare.

   Do this now:
     1. Sign in at Namecheap.
     2. Open your domain's nameservers.  Choose custom nameservers.
     3. Put in these two, and remove the others:

          ada.ns.cloudflare.com
          bob.ns.cloudflare.com

     4. Press save.

   Nothing to press here.  The next account comes next, and I check the nameservers myself later.
   ```

   When DNSSEC is on, the screen has a loud line above "Do this now:", and
   a first step that turns DNSSEC off:

   ```text
   TURN OFF DNSSEC FIRST.  YOUR SITE WILL NOT WORK WITH IT ON.
   ```

   The command asks for no keypress and goes on to Backblaze by itself.
   Once `go-live` has finished, check the change with
   `dig NS example.com +short` until the answer names the two nameservers
   in `cloudflare_nameservers` of `for_the_coding_agent`. Cloudflare's own
   "Active" can take hours. Nothing in chapters 4 to 7 waits for
   "Active". When the answer still names other nameservers at chapter 9,
   say so plainly and say what the person changes at the registrar.

   **Tell the person after:**

   > Your registrar now points your domain at Cloudflare. Cloudflare can take a few hours to confirm. I keep working meanwhile.

   **Check:** `dig NS example.com +short` names the two Cloudflare
   nameservers.

5. **Backblaze.** Backblaze's region follows the servers' location, such
   as `EU Central` for servers in Europe. The command shows:

   ```text
   Your accounts: account 3 of 3, Backblaze (your backups)

   What this is for:
     Your database backups are stored at Backblaze, away from your servers.

   Do this now:
     1. Open  https://www.backblaze.com/sign-up/cloud-storage
        Type your email and press  Get Started Free.  Then finish making the account.
     2. When Backblaze asks for a region, choose  EU Central.

     THE REGION CANNOT BE CHANGED LATER.

     3. Save the login in 1Password.
     4. Open  App Keys  and press  Generate New Master Application Key.

   Backblaze calls it the master key.  I use it once, to make a narrow key
   for each server, and never store it.

   Then paste the two values here.

     keyID:
     applicationKey (hidden):
   ```

   The command checks the key and prints `Backblaze accepted the key.`
   When the account's region differs from `vars.backups`, the command
   says so on the person's screen and waits for the person's choice:

   ```text
   Your Backblaze account is in  US West.  The plan was  EU Central,  near your servers.
   An account's region cannot be changed.

   Choose one:
     1. Carry on with  US West.  Your backups work the same, farther from your servers.
     2. Make a new Backblaze account in  EU Central.  It needs another email address.

     Type 1 or 2:
   ```

   With 1, the results file's `b2_s3_endpoint` names the account's own
   endpoint: write it, and its region, into `vars.backups`. With 2, the
   command shows the new account's steps and asks for its key.
   Then it makes the buckets and keys as the settings in `vars.backups`
   name them, with Object Lock on the database backups' bucket and the
   uploads' copy, checks each lock with a test file, saves each server's
   own narrow key in the vault, and forgets the master key. The master key
   is never stored, not in the vault and not in the recovery bundle, so
   nothing needs deleting.

   **Check:** the results file shows Backblaze done, with each lock
   checked.

6. **The Git host token.** The servers download the app's images with a
   read-only token. The command shows:

   ```text
   Your accounts: one more key, so your servers can download your app.

   Do this now:
     1. Open this link.  It fills in the key for you:
          https://github.com/settings/tokens/new?scopes=read:packages&description=example-servers
        GitHub may first show  Confirm access  and ask for an authentication code or password.
        Enter it.  The link is not broken.
     2. Set  Expiration  to  No expiration.

     SET EXPIRATION TO "NO EXPIRATION".  OTHERWISE YOUR DEPLOYS STOP IN 30 DAYS.

     3. Press  Generate token.

   Then paste the key here.  GitHub calls it a token.

     GitHub key (hidden):
   ```

   The command reads the app's image at the registry with the token, and
   prints `GitHub accepted the key.` Write
   `container_registry_read_only_username` from `for_the_coding_agent`
   into `mmx_project_settings.yml`, and commit it in your clone, to
   publish once `go-live` has finished, as in step 3.
   `container_image_found` says whether CI has built the first image yet.
   With `no, not built yet`, read CI's result yourself, before chapter 6,
   as chapter 2's step 7 says: the `ci-report` branch in the app's
   repository, which also shows a failure's reason, and the image at the
   registry, as a background command, with the tag chapter 2 recorded in
   `deployed_image_tags`:

   ```sh
   # On the laptop, in ~/code/example_systems, as a background command.
   ./server_management_scripts/wait_for_the_app_image ghcr.io/example/shop:FULL_APP_COMMIT_ID
   ```

   Exit 0: the image is at the registry; carry on. Exit 1: it is still
   missing after 9 minutes, so the build failed or still runs. Exit 3:
   the registry does not let the laptop read a private image without a
   registry login, so the command cannot tell. In both cases, read the
   `ci-report` branch, or use `gh run watch` when `gh` is signed in.
   Never ask the person to sign in to the Git host or to look at a CI
   page. Never tell the person the app's tests passed from the image
   alone: say only what CI's report or the command showed.

   When CI's report says the tests failed, read `test.log` on the
   branch, fix the app, show the fix as chapter 2's step 7 does, and push
   it after the person's "yes". When no report exists for the pushed
   commit after about 15 minutes, CI did not run: check that the workflow
   file is on `main`, and say plainly what you found.

   An organization may require a token that ends. The command accepts a
   token that ends 30 or more days from now, after the person types `yes`,
   and refuses one that ends sooner. The screen says that the servers can
   no longer download the app on the end date, and that deploys and new
   servers stop. The results file's `for_the_coding_agent` then holds
   `container_registry_read_only_token_expires_at`, the end date in UTC,
   such as `2027-02-15T09:00:00Z`. The weekly review reads it
   ([Do the weekly system review](../operating_procedures/do_the_weekly_system_review.md)).
   A token with no end date leaves the field out.

   Then the command makes every other vault secret without a question,
   because each is random: the database passwords, the failover monitor's
   logins, the backup passphrase, the fleet hub's signing secret, each
   app's random secrets, and the shared root console password and its
   hash.

   **Check:** the results file shows the Git host token done, and
   `ssh desk01-agent sudo -n -u servers-mmx run-mmx-on-the-servers secrets usage`
   lists no key `not defined` that chapters 5 to 9 need. The keys of the
   later parts of the setup, such as Pushover's and the triage agent's, stay
   `not defined` until their part of the setup.

7. **The lock.** The command ends "Your accounts" with
   [chapter 0's compact map](00_before_you_start_what_we_build_and_how_long_it_takes.md#the-compact-map),
   and shows the two steps of "Your keys locked away". First the recovery
   passphrase:

   ```text
   Your accounts are done.

     ✓ 1. Your app
     ✓ 2. Your accounts
     → 3. Your keys locked away    now: 2 steps, about 3 minutes
       4. Your servers
       5. Live
       Later: phone alerts.  Your site has none yet.

   Your keys locked away: step 1 of 2, your recovery passphrase

   What this is for:
     If you lose your systems desk (the small server that holds your keys), this one passphrase brings everything back.

     SAVE IT NOW.  IT IS SHOWN ONLY ONCE.

       maple  orbit  candle  river  stone  pilot

   Do this now:
     1. Save it in 1Password as  "Example recovery passphrase".
     2. Type it here to prove you saved it.

     Recovery passphrase:
   ```

   Then the phone code:

   ```text
   Your keys locked away: step 2 of 2, your phone code

   What this is for:
     From now on, your systems desk (the small server that holds your keys) needs your laptop AND a code from your phone.

   Do this now:
     1. Open the authenticator app on your phone.
     2. Scan this code.

     [QR code]

     Or type this key into the app instead:  [the key]

     3. Type the 6 digits your phone shows.

     Code:
   ```

   After a wrong code, the command says so and asks again:

   ```text
     That code did not match.  Type the 6 digits your phone shows now.
     If every code fails, check that your phone sets its clock automatically.
   ```

   Once a code matches, it clears the screen and says:

   ```text
   Your phone code is ready. From now on each new login to this systems desk needs your laptop AND a code from your phone.
   Each code works once. 5 wrong codes within ten minutes lock that laptop out of the systems desk for 5 minutes.
   ```

   The command ends:

   ```text
   Done.  Your phone code is ready.  Your coding agent locks your systems desk next, then builds your servers.

   Go back to your coding agent.
   ```

   It says "Done.  Your desk is locked." instead only when the lock has
   run: `/etc/systems-desk/locked` exists, and
   `/etc/ssh/sshd_config.d/00-systems-desk-root-login-before-the-lock.conf`,
   which lets root in from the laptop with the laptop key alone, is gone.
   In this first setup that happens in step 8.

   The command puts the recovery bundle, `recovery_bundle.age`, into the
   systems repository, and a copy into the locked backup bucket. It holds
   the vault passphrase, the production private key, the desk's WireGuard
   private key, the shared root console password, the phone code's
   emergency codes, and the provider, Cloudflare and Backblaze
   credentials. The phone code's secret itself stays only on the desk.

   **Tell the person:** no message while the person is in the command.
   The person needs no help unless the person asks.

   **Check:** the results file shows the recovery passphrase and the phone
   code done and `finished: true`, and `main` in the desk's checkout holds
   `recovery_bundle.age`. Then publish the settings you committed in
   steps 3 to 6 with `publish-branch-to-main`.

   **Push the first backup to the Git host,** from the laptop, with the
   person's own Git login, as "The main copy and the backup at the Git host" in
   [`AGENTS.md`](../AGENTS.md#the-main-copy-and-the-backup-at-the-git-host) says:

   ```sh
   # On the laptop, in ~/code/example_systems. BACKUP_URL:
   # systems_repository.backup_url_at_the_git_host in mmx_project_settings.yml.
   git pull --ff-only
   git remote add backup BACKUP_URL
   git push backup main
   ```

   The Git host's copy is a backup only. Push it; never pull from it,
   and never force-push to it. When the Git host refuses a push, it holds
   commits the main copy lacks: show the person those commits. Before a
   restore from it, read its push activity. Push it again at the end of
   each working session.

   When the Git host answers "Repository not found", first try the
   address in the form the laptop's own Git login reaches it: the form of
   the app repository's `origin`, or a `Host` entry in `~/.ssh/config`
   that names the Git host, such as `github-backup:OWNER/NAME.git`. Never
   ask the person for the address again, and never list it among the
   open items at the end of the setup: say it once, here, with what you
   tried. Reason: in a newcomer test run, the person had given the name
   in part 2, the push used the wrong address form, and the end of the
   setup asked again, which looked like the setup forgot the answer.

   **Check:** `git ls-remote backup main` on the laptop shows the same
   commit as `main` in your clone.

8. **Close root SSH from the laptop.** Run the bootstrap's `lock` stage.
   It closes root SSH from the laptop, so from now on the desk admits only
   the person and you, each with the laptop key and a phone code. Your
   shared login, opened in step 1, stays open.

   Run it after `cd ~/example-setup/desk_bootstrap_copy` as a call of its
   own:

   ```sh
   # On the laptop, in ~/example-setup/desk_bootstrap_copy:
   ~/.local/bin/mmx run systems_desk --var desk_name=desk01 --only-fleet-stages lock --connection ssh_only
   ```

   Then run `cd ~/code/example_systems` as a call of its own, and remove
   the laptop's setup folder, which holds the bootstrap copy and the key
   command, and no secret any more:

   ```sh
   # On the laptop:
   rm -rf ~/example-setup
   ```

   The laptop keeps mmx, doubleshell, `~/.ssh/desk01`, `~/.ssh/desk01.pub`,
   `~/.ssh/desk01_known_hosts`, the desk's SSH entries, and
   `~/.config/doubleshell/desk01.conf`. Remove any provider tool's saved
   login that the provider guide names; most guides name none, because the
   scripts use `curl`.

   **Tell the person:** no message.

   **Check:** `ssh root@desk01 true` is refused, and
   `ssh desk01-agent true` still works with no code.

   When your shared login closed anyway, such as after a long pause, ask
   the person for one code:

   ```text
   Your systems desk, the small server that holds your keys, is locked.  I need one code to start the work.

   WAIT FOR A NEW CODE.  The code you just typed works only once.

   Type the 6 digits here.
   ```

   Then open the login with the code, as "Your login on the desk" in
   [`AGENTS.md`](../AGENTS.md#your-login-on-the-desk) says.

9. **Then you work alone.** Chapters 5 to 9 need nothing from the person
   until the first release. Run each long run as a desk job, as
   [`AGENTS.md`](../AGENTS.md#making-a-change) says, so the laptop may
   sleep.

   **Tell the person:** the end of part 3, "Your keys locked away", with
   the compact map, as the last text of your reply. Before you write it,
   start a short background command, such as `sleep 5`, so its end wakes
   you to start chapter 5, as the skill's "Where the person is: the five
   parts" says:

   ```text
   Your keys are locked away.  Your systems desk now needs your laptop and a code from your phone.

     ✓ 1. Your app
     ✓ 2. Your accounts
     ✓ 3. Your keys locked away
     → 4. Your servers             now, about 40 minutes
       5. Live
       Later: phone alerts.  Your site has none yet.

   Now: I am setting up Cloudflare for your site and installing everything on your servers, about 40 minutes.
   Your laptop may sleep: the work continues on your systems desk.
   Next for you: nothing.  I tell you the moment your site is up.
   ```

   **Check:** you started chapter 5.

## If something is different

- **The team has no domain yet** (step 3): after the Cloudflare screen,
  the person registers the domain at Cloudflare, at the price Cloudflare
  shows. The registrar screen is skipped.
- **An app keeps uploaded files** (step 3): R2 stores them. The
  Cloudflare screen's extra step turns R2 on, with its price, because
  Cloudflare asks for a card on its website before R2 turns on. When the
  person pasted the token before R2 was on, the command shows R2's page
  again and waits for Enter, then makes the uploads bucket and its key.
- **Cloudflare, Backblaze or GitHub refuses a value** (steps 3, 5 and 6):
  the command shows the service's reason and asks again. Nothing else is
  needed.
- **The person stops in the middle:** `ssh desk01-setup` again continues
  at the first screen that is not done. When Backblaze was done in the
  earlier run, a short screen asks for the master key once more, because
  the key is never kept and the recovery bundle's copy goes into the
  locked backup bucket. The same key works; a new master key works too.
- **The domain shows "Pending" for longer than the setup takes:** chapters
  5 to 8 continue. Chapter 9's check through the public address waits for
  "Active".

## Why the chapter works this way

**The provider account came first.** The desk is built with its key, and
every other secret is typed into the desk.

**One screen per account, with the check at once.** The person makes a key
and pastes it in the same minute, and the service says yes or no at once.
So no key waits in an open browser tab.

**Separate accounts.** The backups are at Backblaze, away from the server
provider and Cloudflare, so a lost server account leaves the backups safe.

**The master key is never stored.** Every server gets its own narrow key,
and nothing needs the master key again. The recovery bundle holds only the
read-only Backblaze key that restores the backups, never the master key.

**MMHotline's backup bucket stays unlocked.** Litestream (checked with
0.5.18 on 2026-11-12) sends no checksum with its uploads, and B2 refuses
uploads into a locked bucket without one.

**One recovery passphrase.** The recovery bundle holds every item a lost
desk needs, encrypted. The person saves one passphrase instead of six
secrets, and types it back once, so a bad copy shows at once.

**The phone code comes last.** The phone code is the lock. Before it, the
laptop key alone opens the desk, so you do the whole desk setup yourself.

**WAIT FOR A NEW CODE.** Each code works once, for the person and for you
alike, because both logins share one phone-code secret.

Next, in the same reply, as the skill's "Now and next" rule says: [Chapter 5: Put your site behind Cloudflare and lock your private pages](05_put_your_site_behind_cloudflare_and_lock_your_private_pages.md).
