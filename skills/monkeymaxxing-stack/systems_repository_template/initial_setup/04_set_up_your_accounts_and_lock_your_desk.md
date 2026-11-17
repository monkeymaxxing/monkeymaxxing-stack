# Chapter 4: Set up your accounts and lock your desk

**When:** right after chapter 3 (make your server account and your
systems desk), once the desk's key is at the Git host.

**What this chapter does:** the person types one command on the laptop,
`ssh desk01-setup`. The command shows the next three accounts, one at a
time: Cloudflare, the domain's registrar, and Backblaze. Then one token at
the Git host, so the servers can download the app. Each value is checked
with its service at once. Then the lock: one recovery passphrase, and one
QR code for the phone. After the lock, the desk needs the laptop and a
code from the phone.

**Who acts:** the person signs up on three websites, makes one key at
each, changes the nameservers at the registrar, saves the recovery
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
  Read the file through your login, every 30 seconds while the command
  runs:

  ```sh
  # On the laptop:
  ssh desk01-agent cat /var/lib/monkeymaxxing-stack/setup_results.json
  ```

- **One message at a time.** When a screen is done, say in one line what
  you do next, such as "Cloudflare accepted your token. I am adding your
  domain at Cloudflare."

## Steps

1. **Open your shared login before the lock.** Before the phone code
   exists, your login needs only the laptop key. Open the shared
   connection now, and keep it in use: the reads of the results file use
   it every 30 seconds, so the desk's one-hour idle limit never closes it
   during this chapter.

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

   **Check:** `ssh -O check desk01-agent` says the master connection is
   running, and `~/code/example_systems` is a clone of the desk's
   repository.

2. **The desk's setup command.**

   **Ask the person:**

   ```text
   Your desk is ready.

   Type this in your terminal:

     ssh desk01-setup

   It shows the next 3 accounts, one at a time.  I watch from here.
   ```

   **Check:** the results file shows that `go-live` started.

3. **Cloudflare.** The command shows:

   ```text
   Account 2 of 4: Cloudflare (your web address and protection)

   What this is for:
     Cloudflare puts your site on the internet and keeps your private pages private.

   Do this now:
     1. Open  https://dash.cloudflare.com/sign-up  and make an account.
     2. Save the login in 1Password.
     3. Turn on two-step sign-in:  https://dash.cloudflare.com/profile/authentication
     4. Open this link.  It fills in the key for you:
          https://dash.cloudflare.com/?to=/:account/api-tokens&permissionGroupKeys=...&name=...
        Press  Continue to summary,  then  Create Token.

   Then paste the token here.

     Cloudflare token (hidden):
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
   it deletes the link token. The status page waits for its own sitting.

   When the results file shows the step `cloudflare` done:

   - Write `cloudflare_account_id` from `for_the_coding_agent` into
     `vars.cloudflare_account_id` in `mmx_project_settings.yml`, and
     commit it in your clone. Publish it once `go-live` has finished
     (step 7's check), as "Making a change" in
     [`AGENTS.md`](../AGENTS.md#making-a-change) says. Reason: `go-live`
     saves keys in the vault of the desk's checkout and commits them only
     later, and `sign-and-publish` refuses a checkout with changes that
     are not committed.
   - Check the scan's records through the proxy at
     `http://127.0.0.1:8082/` on the desk. Read the current records with
     `dig` against the old nameservers, for the domain itself, `www`, the
     MX records, and TXT records such as SPF and `_dmarc`, and add each
     record that the scan missed. The MX records come first, because
     without them the company's email stops arriving.

   **Tell the person,** after the command accepted the token: one line
   about each piece of work, as it happens, such as "Cloudflare accepted
   your token. I am checking your domain's DNS records at Cloudflare."

   **Check:** the step `cloudflare` is `done`, and
   `vars.cloudflare_account_id` is committed in your clone.

4. **The domain's registrar.** The command reads the domain's registrar
   and its DNSSEC state from the registry's RDAP service, and shows the
   zone's two Cloudflare nameservers. A domain that already points at
   Cloudflare skips the screen, and the step shows `not_needed`.

   ```text
   Account 3 of 4: your domain's registrar (Namecheap)

   What this is for:
     Your domain must point at Cloudflare.

   Do this now:
     1. Sign in at Namecheap.
     2. Open your domain's nameservers.  Choose custom nameservers.
     3. Put in these two, and remove the others:

          ada.ns.cloudflare.com
          bob.ns.cloudflare.com

     4. Press save.

   Press Enter here when you saved.  I check it from here.
   ```

   When DNSSEC is on, the screen has a loud line above "Do this now:", and
   a first step that turns DNSSEC off:

   ```text
   TURN OFF DNSSEC FIRST.  YOUR SITE WILL NOT WORK WITH IT ON.
   ```

   After the person presses Enter, check the change with
   `dig NS example.com +short` until the answer names the two nameservers
   in `cloudflare_nameservers` of `for_the_coding_agent`. Cloudflare's own
   "Active" can take hours. Nothing in chapters 4 to 7 waits for
   "Active".

   **Tell the person after:**

   > Your registrar now points your domain at Cloudflare. Cloudflare can take a few hours to confirm. I keep working meanwhile.

   **Check:** `dig NS example.com +short` names the two Cloudflare
   nameservers.

5. **Backblaze.** Backblaze's region follows the servers' location, such
   as `EU Central` for servers in Europe. The command shows:

   ```text
   Account 4 of 4: Backblaze (your backups)

   What this is for:
     Your database backups are stored at Backblaze, away from your servers.

   Do this now:
     1. Open  https://www.backblaze.com/sign-up/cloud-storage
     2. Choose the region  EU Central.

     THE REGION CANNOT BE CHANGED LATER.

     3. Save the login in 1Password.
     4. Open  App Keys  and press  Generate New Master Application Key.

   Then paste the two values here.

     keyID:
     applicationKey (hidden):
   ```

   The command checks the key and prints `Backblaze accepted the key.`
   When the account's region differs from `vars.backups`, the results
   file's `b2_s3_endpoint` names the account's own endpoint: write it into
   `vars.backups`, because the region cannot change.
   Then it makes the buckets and keys as the settings in `vars.backups`
   name them, with Object Lock on the database backups' bucket and the
   uploads' copy, checks each lock with a test file, saves each server's
   own narrow key in the vault, and forgets the master key. The master key
   is never stored, so nothing needs deleting.

   **Check:** the results file shows Backblaze done, with each lock
   checked.

6. **The Git host token.** The servers download the app's images with a
   read-only token. The command shows:

   ```text
   One more key: so your servers can download your app.

   Do this now:
     1. Open this link.  It fills in the key for you:
          https://github.com/settings/tokens/new?scopes=read:packages&description=example-servers
     2. Set  Expiration  to  No expiration.

     SET EXPIRATION TO "NO EXPIRATION".  OTHERWISE YOUR DEPLOYS STOP IN 30 DAYS.

     3. Press  Generate token.

   Then paste the token here.

     GitHub token (hidden):
   ```

   The command reads the app's image at the registry with the token, and
   prints `GitHub accepted the token.` Write
   `container_registry_read_only_username` from `for_the_coding_agent`
   into `mmx_project_settings.yml`, and commit it in your clone, to
   publish once `go-live` has finished, as in step 3.
   `container_image_found` says whether CI has built the first image yet.
   With `no, not built yet`, check CI before chapter 7, with `gh run watch`
   when `gh` is signed in.

   Then the command makes every other vault secret without a question,
   because each is random: the database passwords, the failover monitor's
   logins, the backup passphrase, the fleet hub's signing secret, each
   app's random secrets, and the shared root console password and its
   hash.

   **Check:** the results file shows the Git host token done, and
   `ssh desk01-agent sudo -n -u servers-mmx run-mmx-on-the-servers secrets usage`
   lists no key `not defined` that chapters 5 to 9 need. The keys of the
   later sittings, such as Pushover's and the triage agent's, stay
   `not defined` until their sitting.

7. **The lock.** The command shows two last steps. First the recovery
   passphrase:

   ```text
   Last two steps.

   Step 1 of 2: your recovery passphrase

   What this is for:
     If you lose your desk, this one passphrase brings everything back.

     SAVE IT NOW.  IT IS SHOWN ONLY ONCE.

       maple  orbit  candle  river  stone  pilot

   Do this now:
     1. Save it in 1Password as  "Example recovery passphrase".
     2. Type it here to prove you saved it.

     Recovery passphrase:
   ```

   Then the phone code:

   ```text
   Step 2 of 2: your phone code

   What this is for:
     From now on, your desk needs your laptop AND a code from your phone.

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
   Your phone code is ready. From now on each new login to this desk needs your laptop AND a code from your phone.
   Each code works once. 5 wrong codes within ten minutes lock that laptop out of the desk for 5 minutes.
   ```

   The command ends:

   ```text
   Done.  Your desk is locked.

   Go back to your coding agent.
   ```

   The command puts the recovery bundle, `recovery_bundle.age`, into the
   systems repository, and a copy into the locked backup bucket. It holds
   the vault passphrase, the production private key, the desk's WireGuard
   private key, the shared root console password, the phone code's
   emergency codes, and the provider, Cloudflare and Backblaze
   credentials. The phone code's secret itself stays only on the desk.

   **Tell the person:** no message while the person is in the command.
   The person needs no help unless the person asks.

   **Check:** the results file shows the recovery passphrase and the phone
   code done and `finished: true`, and the Git host shows
   `recovery_bundle.age` on `main`. Then publish the settings you
   committed in steps 3 to 6 with `sign-and-publish`.

8. **Close root SSH from the laptop.** Run the bootstrap's `lock` stage.
   It closes root SSH from the laptop, so from now on the desk admits only
   the person and you, each with the laptop key and a phone code. Your
   shared login, opened in step 1, stays open.

   ```sh
   # On the laptop, in ~/example-setup/desk_bootstrap_copy:
   mmx run systems_desk --var desk_name=desk01 --only-fleet-stages lock --connection ssh_only
   ```

   Then remove the laptop's setup folder, which holds the bootstrap copy
   and the key command, and no secret any more:

   ```sh
   # On the laptop:
   rm -rf ~/example-setup
   ```

   The laptop keeps mmx, doubleshell, `~/.ssh/desk01`, `~/.ssh/desk01.pub`,
   `~/.ssh/desk01_known_hosts`, the desk's SSH entries, and
   `~/.config/doubleshell/desk01.conf`. Remove any provider tool's saved
   login that the provider guide names, such as `~/.config/hcloud/cli.toml`.

   **Tell the person:** no message.

   **Check:** `ssh root@desk01 true` is refused, and
   `ssh desk01-agent true` still works with no code.

   When your shared login closed anyway, such as after a long pause, ask
   the person for one code:

   ```text
   Your desk is locked.  I need one code to start the work.

   WAIT FOR A NEW CODE.  The code you just typed works only once.

   Type the 6 digits here.
   ```

   Then open the login with the code, as "Your login on the desk" in
   [`AGENTS.md`](../AGENTS.md#your-login-on-the-desk) says.

9. **Then you work alone.** Chapters 5 to 9 need nothing from the person
   until the first release. Run each long run as a desk job, as
   [`AGENTS.md`](../AGENTS.md#making-a-change) says, so the laptop may
   sleep.

   **Tell the person:**

   > Thank you. Now I create your servers, install everything, set up your backups, prove a restore, and put your app live.
   > That takes about an hour. Your laptop may sleep: the work continues on your desk.
   > I tell you what I am doing, one line at a time.

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
  at the first screen that is not done.
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
and nothing needs the master key again.

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

Next: [Chapter 5: Put your site behind Cloudflare and lock your private pages](05_put_your_site_behind_cloudflare_and_lock_your_private_pages.md).
