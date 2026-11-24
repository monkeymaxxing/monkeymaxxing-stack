# Chapter 4: Set up your accounts and lock your systems desk

**When:** right after chapter 3 (make your server account and your
systems desk).

**What this chapter does:** you lead the person through three more
accounts in the chat: Cloudflare, Backblaze and GitHub. First you ask
which of the accounts the person has already. Then you take each account
from where the person stands: a new account, an account with a saved key,
an account without a key, or an account set up differently than the plan.
Each key goes from the person's clipboard, or from a laptop file the
person names, straight to a small command on the desk. The key never
appears in the chat, and you never see it. Then the person opens one
window, `ssh desk01-lock`, for the lock: a console password, one recovery
passphrase, and one QR code for the phone. After the lock, the desk needs
the laptop and a code from the phone.

**Who acts:** the person signs up where an account is missing, copies
each key when you ask, changes the domain's nameservers at the registrar
when needed, and does the lock window. You do everything else: you send
each key to the desk, add the domain at Cloudflare, check its DNS records,
make the buckets and keys through the desk's commands, and lock the desk.

**Tell the person when the chapter starts:** step 2's question.

## Before you start

- **Why you lead, not a program.** Each person's accounts are different.
  A person may have every account, with the keys saved on the laptop,
  or have none. A fixed program that treats every account as new tells a
  person with a Backblaze account to sign up again, and a new Backblaze
  master key stops the old one working. So you ask first, and take each
  account from where the person stands.
- **A key never goes into the chat.** Everything in the chat goes to the
  company that runs you. When the person pastes a key into the chat by
  mistake, say so in one line, and ask the person to make a new key at
  that company, because the old key is no longer private. Then delete the
  old key at that company, or ask the person to.
- **The desk's account commands.** `set-up-outside-services
  from-the-coding-agent COMMAND` runs on the desk as root, through one
  sudo rule for your login, with the key on standard input:

  | COMMAND | Standard input | What the command does |
  | --- | --- | --- |
  | `cloudflare` | Line 1: the link token | Finds the account, adds the domain, has Cloudflare copy its DNS records, makes the tunnels and every Cloudflare key, then deletes the link token |
  | `backblaze` | Line 1: the keyID. Line 2: the applicationKey | Makes the buckets with their locks, checks each lock, and makes one narrow key for each server. Never stores the master key |
  | `save-a-key KEY` | Line 1: the key | Checks and saves one key a person must give: `container_registry_read_only_token`, or an app key from `an_outside_service`, such as `shop_STRIPE_API_KEY` |
  | `random-secrets` | Nothing | Makes every random secret of the vault |

  Each command prints plain lines that never hold a secret, commits and
  pushes the vault, and writes its step into the results file. Exit 0
  means done, and exit 1 means stopped, with the reason on the last line.
  The command takes no path or setting from you, and prints no key, so
  you can put a key in and never get one out.
- **The results file.** `/var/lib/monkeymaxxing-stack/setup_results.json`
  holds each step's name and state, `stopped_with`, the reason a command
  stopped, and `for_the_coding_agent`, the values that are not secrets,
  which you write into the settings. The file never holds a secret. It
  appears with the first account command. Read it after each command, and
  each time the person comes back to you:

  ```sh
  # On the laptop:
  ssh desk01-agent cat /var/lib/monkeymaxxing-stack/setup_results.json
  ```

- **Publish each setting at once.** Each account command commits and
  pushes the vault when it ends, so `publish-branch-to-main` works between
  commands. Publish the settings you write after each command, as "Making
  a change" in [`AGENTS.md`](../AGENTS.md#making-a-change) says. A later
  command reads them from pushed `main`.
- **One message at a time.** When an account is done, say in one line
  what you did, such as "Cloudflare accepted your token. I added your
  domain at Cloudflare."

## How a key reaches the desk

Three ways, chosen per key. The person never chooses among them: you ask
where the key is, and use the first way that fits.

**From a file on the laptop,** only when the person names the file, such
as `~/.config/backblaze/env`. Never search the laptop for keys. First list
the variable names in the file, never the values:

```sh
# On the laptop. Lists the names of the variables in the file the person named, never a value.
sed -n 's/^[[:space:]]*\(export[[:space:]]\{1,\}\)\{0,1\}\([A-Za-z_][A-Za-z0-9_]*\)=.*/\2/p' ~/.config/backblaze/env
```

Pick the names that hold the key, such as `B2_APPLICATION_KEY_ID` and
`B2_APPLICATION_KEY`. When the names leave a doubt, ask the person which
name holds which value. Then pass only those values, one per line, with
shell tracing off. Read each value as data, never by running the file
with `.` or `source`: a shell that cannot read a line prints the whole
line, key included, into your conversation, even with tracing off.
`value_of` prints the value of one named variable, its quotes removed,
and a missing value stops the pipe with the name alone:

```sh
# On the laptop. Passes two named values from the file to the desk's command, without printing them.
(
  set +x
  file=~/.config/backblaze/env
  value_of() {
    sed -n "s/^[[:space:]]*\(export[[:space:]]\{1,\}\)\{0,1\}$1=//p" "$file" | tail -n 1 |
      sed -e 's/[[:space:]]*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'\$/\1/"
  }
  for name in B2_APPLICATION_KEY_ID B2_APPLICATION_KEY; do
    [ -n "$(value_of "$name")" ] || { echo "The file has no value for $name." >&2; exit 1; }
  done
  printf '%s\n%s\n' "$(value_of B2_APPLICATION_KEY_ID)" "$(value_of B2_APPLICATION_KEY)"
) | ssh -T desk01-agent sudo -n /usr/local/bin/set-up-outside-services from-the-coding-agent backblaze
```

When the pipe stops with "The file has no value for NAME", ask the person
which name holds the value, or use the clipboard. A file that is not in
the `NAME=value` form, such as a JSON file, gets the same pipe with a
reader for its form in place of `value_of`, such as
`jq -r .applicationKey FILE`. Never print, `cat`, or `grep` the values.

**Way A, the clipboard,** when you run on the person's laptop and the
laptop has a clipboard tool. Check only that the tool exists, with
`command -v`:

| Laptop | Read the clipboard (READ) | Empty the clipboard (EMPTY) |
| --- | --- | --- |
| macOS | `pbpaste` | `printf '' \| pbcopy` |
| Windows, with the Stack in WSL | `powershell.exe -NoProfile -Command Get-Clipboard` | `printf '' \| clip.exe` |
| Linux with Wayland | `wl-paste --no-newline` | `wl-copy --clear` |
| Linux with X11 | `xclip -o -selection clipboard` | `printf '' \| xclip -selection clipboard` |

Never run a clipboard command on its own: its output, the person's key,
would appear in your conversation. Always pipe the clipboard straight
into the desk's command, with no terminal on the desk's side (`ssh -T`),
and empty the clipboard when the pipe ends, also when it fails. The
`tr` removes line endings, Windows' carriage return included, and
`printf` ends the value with one line break:

```sh
# On the laptop (macOS). Sends the clipboard to the desk's command, then empties the clipboard.
(
  set +x
  trap "printf '' | pbcopy" EXIT
  { pbpaste | tr -d '\r\n'; printf '\n'; } |
    ssh -T desk01-agent sudo -n /usr/local/bin/set-up-outside-services from-the-coding-agent save-a-key container_registry_read_only_token
)
```

On another laptop, replace `pbpaste` with READ and `printf '' | pbcopy`
with EMPTY from the table.

**Ask the person,** the first time, as the last text of your reply:

```text
Copy your GitHub token, then type  copied  here.

I send it from your clipboard straight to your systems desk, and empty your clipboard right after.
I never see it, and it never appears in this chat.
```

After the first time, the first line is enough.

**Way B, the paste window,** when you cannot read the clipboard: a Linux
laptop without `wl-paste` or `xclip`, or a coding agent that does not run
on the person's laptop. Also use way B for one key when way A's pipe
failed before the desk's command read a key, such as when the clipboard
tool gave an error or the command said the value was empty.

**Ask the person,** as the last text of your reply, with the command for
the account:

```text
This key goes in through a window of its own, because I cannot read this laptop's clipboard.
Open a new terminal window and type:

  ssh -t desk01 set-up-outside-services backblaze

It logs in to your systems desk and asks for your Backblaze keys.  Paste each one there.  The applicationKey stays hidden.
When the window says what it made and ends, tell me "done" here.
```

The window shows the prompts, then a few lines about what the command
made, such as the buckets and keys, and ends:

```text
Paste your Backblaze keyID (hidden):
Paste your Backblaze applicationKey (hidden):
```

The window's command for each key: `cloudflare` for the Cloudflare
token, `backblaze` for the Backblaze keys, and `save-a-key KEY` for the
GitHub token and each app key, such as
`save-a-key container_registry_read_only_token` or
`save-a-key shop_STRIPE_API_KEY`. It asks for that one key only.
Then read the results file, and carry on as after way A.

## Steps

1. **Open your shared login before the lock.** You did this step at the
   end of chapter 3, before the three servers were created
   ([Create the three production servers now](03_make_your_server_account_and_your_systems_desk.md#create-the-three-production-servers-now));
   check it, and do it now only when it was not done. Before the phone code
   exists, your login needs only the laptop key. Open the shared
   connection now. When the person takes longer than the desk's one-hour
   idle limit, the login closes, and step 10 says how to open it again.

   ```sh
   # On the laptop:
   ssh desk01-agent true
   ```

   Then move the laptop's bootstrap copy aside, and clone the desk's
   systems repository in its place. From now on you edit in the clone, as
   "Making a change" in [`AGENTS.md`](../AGENTS.md#making-a-change) says.
   The bootstrap copy is needed once more, for step 10.

   ```sh
   # On the laptop:
   mv ~/code/example_systems ~/example-setup/desk_bootstrap_copy
   git clone desk01-agent:systems_repository ~/code/example_systems
   ```

   Check which way a key reaches the desk on this laptop
   ([How a key reaches the desk](#how-a-key-reaches-the-desk)), such as
   with `command -v pbpaste`.

   **Tell the person:** no message.

   **Check:** `~/code/example_systems/ssh/open-the-desk-login --check`
   says the login is open, and `~/code/example_systems` is a clone of the desk's
   repository.

2. **Ask which accounts the person has.** **Ask the person,** as the last
   text of your reply:

   ```text
   Your systems desk is ready.

   Next come three accounts:
     Cloudflare, for your web address,
     Backblaze, for your backups,
     GitHub, so your servers can download your app.

   Which of them do you have already?
   ```

   GitHub holds the app already, so the GitHub part needs only a token.
   For each account the person has, ask where its key is when the
   account's step comes, never all at once:

   ```text
   Where is your Backblaze key saved?
     In a password manager or a note:  say "password manager".  You copy it from there when I ask.
     In a file on this laptop:  tell me the file's path, such as  ~/.config/backblaze/env.
       I pass the key from the file to your systems desk without reading it.
     Nowhere:  say "no key".  I help you make one.
   ```

   **Check:** you know, for each of the three accounts, whether the
   person has it.

3. **Cloudflare.** Cloudflare lets only a token made on its own website
   make other tokens (tested at Cloudflare). So the person makes one
   token, the link token, from a link that fills in its one permission
   and its name, even with an existing account. Build the link with the
   repository's `project_name` and the desk's `vars.person_unix_username`,
   such as `example_systems` and `alex`, because the command finds and
   deletes the link token by that name:

   ```text
   https://dash.cloudflare.com/?to=/:account/api-tokens&permissionGroupKeys=%5B%7B%22key%22%3A%22account_api_tokens%22%2C%22type%22%3A%22edit%22%7D%5D&name=example_systems%3A+alex+makes+tokens+with+set-up-outside-services%2C+deleted+after+the+run
   ```

   **Ask the person,** with no Cloudflare account yet:

   ```text
   Your accounts: Cloudflare (your web address and protection)

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
     5. Copy the token, then type  copied  here.  Cloudflare calls the key an API token.
   ```

   With a Cloudflare account, the screen keeps only steps 4 and 5, and
   starts with "Sign in at Cloudflare." When the account has no two-step
   sign-in, step 3 stays: the account controls the domain and the private
   pages. When an app keeps uploaded files, the screen has one more step
   before the link, from R2's pricing page: turn on R2, where the app
   keeps its uploads. Cloudflare asks for a card on its website before R2
   turns on, and no token can do that step.

   ```text
     4. Turn on R2, where your app keeps its uploaded files:
          https://dash.cloudflare.com/?to=/:account/r2/overview
        If the page shows your R2 buckets, R2 is on already.  Go to the next step.
        Otherwise finish the checkout there.  It asks for a card.
        It costs nothing up to 10 GB of files a month.
        Above that:  $0.015 for each GB a month,
                     $4.50 for each million file writes after the first million,
                     $0.36 for each million file reads after the first 10 million.
        Downloads to your users cost nothing.
   ```

   Then send the token to the desk's `cloudflare` command, by way A or
   way B. The command checks the token, sets it to end by itself after 24
   hours, finds the account, adds the domain to the account, has
   Cloudflare copy the domain's DNS records, gives the account its
   workers.dev address, makes the person's desk token and starts the
   desk's Cloudflare proxy, makes the tunnels `example_systems-apps` and
   `example_systems-util01` with their tokens in the vault, makes the
   servers' Cloudflare keys (the table in
   [chapter 5](05_put_your_site_behind_cloudflare_and_lock_your_private_pages.md#steps)),
   adds One-time PIN, Access's login method that emails a code, and makes
   the app's uploads bucket and its key when an app keeps uploads. Then it
   deletes the link token. The status page waits for its own part of the
   setup.

   Two stops need the person, and each needs a new link token, because
   the command deletes the link token when it stops:

   - **The token reaches several accounts.** The command lists each
     account's name and ID. **Ask the person:**

     ```text
     Your Cloudflare login reaches 2 accounts:
       Acme Inc
       Alex's own account
     Which one should hold your company's domain?
     ```

     Then ask for a new token from the same link, and run the command
     again with `cloudflare --account-id ID`. When the stop says that
     deleting the link token failed, also ask the person to delete it at
     the account's API Tokens page, `https://dash.cloudflare.com/ID/api-tokens`.
   - **R2 is off,** while an app keeps uploads. The command prints R2's
     price lines and page. Show the R2 step above, then ask for a new
     token from the same link.

   When the command is done:

   - Write `cloudflare_account_id` from `for_the_coding_agent` into
     `vars.cloudflare_account_id` in `mmx_project_settings.yml`, and
     `vars.backups.uploads_r2_s3_endpoint` beside it:
     `https://ACCOUNT_ID.r2.cloudflarestorage.com` with that ID when an app
     keeps uploads, or `""` when none does. Publish both.

   **Tell the person,** one line, such as "Cloudflare accepted your token.
   I added your domain at Cloudflare and made your tunnels and keys."

   **Check:** the step `cloudflare` is `done`, and
   `vars.cloudflare_account_id` is on `main`.

4. **The domain moves to Cloudflare.** The domain's registrar answers the
   domain's address questions until its nameservers point at Cloudflare.
   A switch before Cloudflare holds every record stops the site and the
   company's email. So the switch goes in this order. A domain whose
   nameservers already are `cloudflare_nameservers` in
   `for_the_coding_agent` skips this step.

   1. **Check that Cloudflare copied every record,** through the proxy at
      `http://127.0.0.1:8082/` on the desk. Read the current records with
      `dig` against the old nameservers: the MX records first, because
      without them the company's email stops arriving; then the domain
      itself, `www`, and TXT records such as SPF and `_dmarc`. Cloudflare's
      copy can miss the email service's DKIM records, whose names depend
      on the service, such as `google._domainkey`. Ask the person which
      email service the company uses, and check its DKIM names. Add each
      record that is missing at Cloudflare.

      `dig` finds only the names you ask for, so a host name such as
      `billing.example.com` can be missing without any check failing.
      List every record Cloudflare now holds for the domain
      (`GET http://127.0.0.1:8082/zones/ZONE_ID/dns_records`, every
      page), name and type only, never a TXT record's value, and **ask the
      person:**

      ```text
      Before your domain moves, Cloudflare must hold every name your domain uses.
      Cloudflare holds these now:

        example.com          A, MX, TXT
        www.example.com      CNAME
        google._domainkey    TXT

      Does your company use any other name, such as  billing.example.com  or  shop.example.com ?
      Your old DNS provider's page lists them all.  Say "complete", or name the missing ones.
      ```

      Add each name the person names, with its record from the old
      nameservers, before the switch.
   2. **Turn DNSSEC off,** when `domain_dnssec_on` says `yes`. When
      `for_the_coding_agent` has no `domain_dnssec_on`, the registrar's
      record did not say: ask the registry yourself, with the `dig` below.
      A DS record means DNSSEC is on; an empty answer means off. When
      `dig` fails or times out, the state is unknown: keep the switch
      pending and ask again later, because a switch with DNSSEC on stops
      the site and the email. Read the domain's DNSSEC record (DS) at the
      domain's registry first, and note its time to live, the second
      column:

      ```sh
      # On the laptop. Asks the registry of the domain's ending, here .com, with no cache between.
      registry_server=$(dig +short NS com. | head -1)
      dig +noall +answer DS example.com @"$registry_server"
      ```

      **Ask the person,** with the registrar's name from `domain_registrar`:

      ```text
      Your domain moves to Cloudflare next.  Cloudflare now holds every record your domain uses, your email's first.

      One change at Namecheap first:
        1. Sign in at Namecheap.
        2. Open your domain's settings, and turn off DNSSEC.

      I see the change by myself.
      ```

      Before the screen, start a background wait until the registry lists
      no DS record:

      ```sh
      # On the laptop, as a background command. Waits up to 30 minutes.
      registry_server=$(dig +short NS com. | head -1)
      timeout 30m sh -c "until [ -z \"\$(dig +short DS example.com @$registry_server)\" ]; do sleep 20; done"
      ```

      Then wait the DS record's time to live before step 3, as
      Cloudflare's own guide for moving a domain with DNSSEC says. Reason:
      a resolver that still holds the old DS record refuses the domain's
      answers from Cloudflare, so the site and the email stop for the
      people behind that resolver. For a `.com` domain the time to live
      is one day. Chapters 5 to 8 need no nameserver change, so carry on,
      and tell the person when step 3 comes:

      > DNSSEC is off. One more change at Namecheap tomorrow at about 15:00 your time, because the internet forgets the old DNSSEC setting only after a day. I keep working meanwhile.

   3. **Change the nameservers.** **Ask the person:**

      ```text
      One change at Namecheap:
        1. Sign in at Namecheap.
        2. Open your domain's nameservers.  Choose custom nameservers.
        3. Put in these two, and remove the others:

             ada.ns.cloudflare.com
             bob.ns.cloudflare.com

        4. Press save.

      I see the change by myself.
      ```

      Before the screen, start a background wait:

      ```sh
      # On the laptop, as a background command. Waits up to 30 minutes for the registry to name Cloudflare.
      registry_server=$(dig +short NS com. | head -1)
      timeout 30m sh -c "until dig +short NS example.com @$registry_server | grep -qi 'ada.ns.cloudflare.com'; do sleep 20; done"
      ```

   4. **Check the change** with `dig NS example.com +short` until the
      answer names the two nameservers. Cloudflare's own "Active" can take
      hours. Nothing in chapters 5 to 8 waits for "Active". When the
      answer still names other nameservers at chapter 9, say so plainly,
      and say what the person changes at the registrar.

   **Tell the person after:**

   > Your registrar now points your domain at Cloudflare. Cloudflare can take a few hours to confirm. I keep working meanwhile.

   **Check:** the records check found nothing missing, the registry lists
   no DS record, and `dig NS example.com +short` names the two Cloudflare
   nameservers.

5. **Backblaze.** `vars.backups` names the region near the servers, such
   as `EU Central` (`eu-central-003`) for servers in Europe.

   **No Backblaze account yet. Ask the person:**

   ```text
   Your accounts: Backblaze (your backups)

   What this is for:
     Your database backups are stored at Backblaze, away from your servers.

   Do this now:
     1. Open  https://www.backblaze.com/sign-up/cloud-storage
        Type your email and press  Get Started Free.  Then finish making the account.
     2. When Backblaze asks for a region, choose  EU Central.  It is near your servers.

     THE REGION CANNOT BE CHANGED LATER.

     3. Save the login in 1Password.
     4. Open  App Keys  and press  Generate New Master Application Key.
     5. Copy the  keyID,  then type  copied  here.

   Backblaze calls it the master key.  I use it once, to make a narrow key
   for each server, and never store it.
   ```

   **A Backblaze account with the key saved:** with a file, pass both
   values from the file. With a password manager, ask for the keyID first,
   then the applicationKey:

   ```text
   Copy your Backblaze keyID, then type  copied  here.
   ```

   **A Backblaze account without a saved key.** **Ask the person** first,
   and wait for the answer:

   ```text
   A new master key stops your old master key working.  Other keys keep working.
   Does anything else of yours use the old master key?
   ```

   When something uses it, the person updates that program with the new
   master key afterwards, or makes the new key only after checking. Then
   the screen's steps 4 and 5, with "Sign in at Backblaze." first.

   By way A, the two values come in two copies. Save the keyID first, in
   a laptop file of its own, and empty the clipboard. The keyID is not a
   secret, but it stays out of the chat all the same, so that a person
   who mixes up the two values never pastes the applicationKey there.
   The pipe saves the copy only when it looks like a keyID: hexadecimal,
   12 characters for a master key or 25 for another key. Reason: a person
   who copied the applicationKey first would otherwise leave that secret
   in a laptop file. The pipe never prints the copy:

   ```sh
   # On the laptop (macOS). Saves the copied keyID in a private laptop file, only when it looks like a keyID, then empties the clipboard.
   (
     set +x
     umask 077
     trap "printf '' | pbcopy" EXIT
     key_id=$(pbpaste | tr -d '\r\n')
     case "$key_id" in
       *[!0-9a-fA-F]*) looks_like_a_key_id=no ;;
       *) case ${#key_id} in 12|25) looks_like_a_key_id=yes ;; *) looks_like_a_key_id=no ;; esac ;;
     esac
     if [ "$looks_like_a_key_id" = yes ]; then
       printf '%s\n' "$key_id" > ~/example-setup/backblaze-key-id && echo "Saved the keyID."
     else
       echo "The copy is not a keyID. Nothing was saved, and the clipboard is empty." >&2
       exit 1
     fi
   )
   ```

   When the pipe says the copy is not a keyID, **ask the person:**

   ```text
   That copy was not the keyID, so I saved nothing and emptied your clipboard.
   Copy the keyID, the shorter of the two values, then type  copied  here.
   ```

   Then ask for the applicationKey, and send both:

   ```sh
   # On the laptop (macOS). Sends the keyID file and the copied applicationKey to the desk, then empties the clipboard.
   (
     set +x
     trap "printf '' | pbcopy" EXIT
     { cat ~/example-setup/backblaze-key-id; pbpaste | tr -d '\r\n'; printf '\n'; } |
       ssh -T desk01-agent sudo -n /usr/local/bin/set-up-outside-services from-the-coding-agent backblaze
   )
   ```

   The command checks the key. Then it makes the buckets and keys as
   `vars.backups` names them, with Object Lock on the database backups'
   bucket and the uploads' copy, checks each lock with a test file, and
   saves each server's own narrow key in the vault. The master key is
   never stored, not in the vault and not in the recovery bundle. When
   the command is done, leave `~/example-setup/backblaze-key-id` in place:
   step 10 removes it with the rest of `~/example-setup`.

   **The account is in another region than the plan.** The command saves
   nothing, writes `b2_account_s3_endpoint` and `b2_account_region` into
   `for_the_coding_agent`, and stops. **Ask the person:**

   ```text
   Your Backblaze account keeps its files in  US East.  Your servers are in Europe.
   An account's region cannot be changed.

   You can:
     Keep this account.  Your backups work the same, a bit farther from your servers.   I recommend this.
     Make a second Backblaze account in  EU Central.  It needs another email address.
       Choose this only when your company must keep its data in Europe.

   Say "keep" or "second account".
   ```

   With "keep", write the account's endpoint and region into
   `vars.backups.b2_s3_endpoint`, `vars.backups.b2_region`, and the
   endpoint and region in `vars.backups.mmhotline_backup_replica_url`,
   publish them, and send the key again: from the file with no question,
   or with one more copy of the applicationKey. With "second account",
   show the screen for no account yet.

   **Tell the person,** one line, such as "Backblaze accepted your key. I
   made your 4 backup buckets, each with its own narrow key."

   **Check:** the step `backblaze` is `done`, with each lock checked.

6. **The GitHub token.** The servers download the app's images with a
   read-only token. **Ask the person:**

   ```text
   Your accounts: one key at GitHub, so your servers can download your app.

   Do this now:
     1. Open this link.  It fills in the key for you:
          https://github.com/settings/tokens/new?scopes=read:packages&description=example-servers
        GitHub may first show  Confirm access  and ask for an authentication code or password.
        Enter it.  The link is not broken.
     2. Set  Expiration  to  No expiration.

     SET EXPIRATION TO "NO EXPIRATION".  OTHERWISE YOUR DEPLOYS STOP IN 30 DAYS.

     3. Press  Generate token.
     4. Copy the token, then type  copied  here.  GitHub calls the key a token.
   ```

   A token the person has saved already works only when it holds
   `read:packages` alone; the command refuses a token with more. Send it
   to `save-a-key container_registry_read_only_token`. The command reads
   the app's image at the registry with the token. Write
   `container_registry_read_only_username` from `for_the_coding_agent`
   into `mmx_project_settings.yml`, and publish it.
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
   token that ends 30 or more days from now, and refuses one that ends
   sooner. Before you send such a token, tell the person that on the end
   date the servers can no longer download the app, so deploys and new
   servers stop, and wait for "yes". The results file's
   `for_the_coding_agent` then holds
   `container_registry_read_only_token_expires_at`, the end date in UTC,
   such as `2027-02-15T09:00:00Z`. The weekly review reads it
   ([Do the weekly system review](../operating_procedures/do_the_weekly_system_review.md)).
   A token with no end date leaves the field out.

   **Check:** the step for the GitHub token is `done`.

7. **The app keys from outside services.** Each app's `secrets_from_vault`
   names each key with `where_the_value_comes_from: an_outside_service`,
   such as Stripe's. For each one, **Ask the person,** from the key's
   `what_it_is_for` and `steps_to_get_it`:

   ```text
   Your app needs one key from Stripe.

   What this is for:
     Stripe takes your customers' card payments with it.

   Do this now:
     1. Open  https://dashboard.stripe.com/apikeys
     2. Press  Reveal live key,  then copy it.
     3. Type  copied  here.
   ```

   Send each key to `save-a-key APP_VARIABLE`, such as
   `save-a-key shop_STRIPE_API_KEY`. A key with `checked_with: stripe` is
   checked at Stripe first. Skip a key the vault holds already, such as
   one copied from Monkeymaxxing Solo: `secrets list-keys` through your
   button lists the saved keys. An app with no such key skips this step.

   **Check:** the step for each app key is `done`.

8. **The random secrets.** Make every other vault secret, each random,
   with no question to the person: the database passwords, the failover
   monitor's logins, the backup passphrase, the fleet hub's signing
   secret, and each app's random secrets.

   ```sh
   # On the laptop:
   ssh -T desk01-agent sudo -n /usr/local/bin/set-up-outside-services from-the-coding-agent random-secrets < /dev/null
   ```

   **Tell the person:** no message.

   **Check:**
   `ssh desk01-agent sudo -n -u servers-mmx run-mmx-on-the-servers secrets usage`
   lists no key `not defined` that chapters 5 to 9 need, other than
   `shared_root_console_password_hash`, which step 9 makes. The keys of
   the later parts of the setup, such as Pushover's and the triage
   agent's, stay `not defined` until their part of the setup.

9. **The lock window.** The console password, the recovery passphrase and
   the phone code are for the person's eyes only, so they come in a
   window of the person's own, `ssh desk01-lock`. Say first what the
   window shows. **Ask the person,** as the last text of your reply:

   ```text
   Your accounts are done.

     ✓ 1. Your app
     ✓ 2. Your accounts
     → 3. Your keys locked away    now: 3 steps, about 5 minutes
       4. Your servers
       5. Live
       Later: phone alerts.  Your site has none yet.

   Your keys locked away happens in a window of its own, because only you may see what it shows.
   Open a terminal on this laptop and type:

     ssh desk01-lock

   It logs in to your systems desk and shows three things, one at a time:
     1. A password for your servers' consoles.  Save it in 1Password, then type it back.
     2. Your recovery passphrase, six words.  Save it in 1Password, then type it back.
     3. A QR code.  Scan it with the authenticator app on your phone, then type the 6 digits it shows.

   I see by myself when it is done.  Ask me here at any time if a step is unclear.
   ```

   First start the wait as a background command, as
   [`AGENTS.md`, "The two windows agree"](../AGENTS.md#the-two-windows-agree)
   says. Then end your reply with the screen, whole, as its last text.

   ```sh
   # On the laptop, as a background command. Waits up to an hour for the lock window to finish or stop.
   ssh desk01-agent wait-for-the-setup --at-most-minutes 60
   ```

   Exit 0 means the lock window finished, 1 that it stopped, and 124 that
   it still runs at the bound: start the same wait again, and end your
   reply with one line that you still wait for the lock window. With a
   stop, say in one plain sentence what `stopped_with` says and what
   happens next. An agent with no background commands ends its reply
   with the screen and "When it says  Go back to your coding agent,  tell
   me "done" here.", and then runs the same wait in the foreground.

   The window shows, first:

   ```text
   Your keys locked away: step 1 of 3, your servers' console password

   What this is for:
     Your server provider's web console lets root log in with it, the way in when everything else fails.

   The servers' shared root console password, saved as its hash in shared_root_console_password_hash.
     Why: Every server lets root log in with it at your server provider's web console, the way in when SSH and the private network fail. SSH never accepts it. The vault keeps only its hash.
     Save it in your team's password manager as the item named "Shared root console password", in place of any older one. It shows here once:
     ----
     [the password]
     ----
     Press Enter once it is saved. The screen is cleared then:
     Type the password from the item "Shared root console password" (hidden), to check the saved copy:
   ```

   The desk saves only the password's hash in the vault, as
   `shared_root_console_password_hash`, and the password itself in the
   recovery bundle. Then the recovery passphrase:

   ```text
   Your keys locked away: step 2 of 3, your recovery passphrase

   What this is for:
     If you lose your systems desk (the small server that holds your keys), this one passphrase brings everything back.

     SAVE IT NOW.  IT IS SHOWN ONLY ONCE.

       maple  orbit  candle  river  stone  pilot

   Do this now:
     1. Save it in 1Password as  "Example recovery passphrase".
     2. Type it here to prove you saved it.

     Recovery passphrase:
   ```

   A passphrase that is lost later, while the desk still works, gets
   replaced with
   [Make a new recovery passphrase](../operating_procedures/make_a_new_recovery_passphrase.md).

   Then the phone code:

   ```text
   Your keys locked away: step 3 of 3, your phone code

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

   After a wrong code, the window says so and asks again:

   ```text
     That code did not match.  Type the 6 digits your phone shows now.
     If every code fails, check that your phone sets its clock automatically.
   ```

   Once a code matches, it clears the screen and says:

   ```text
   Your phone code is ready. From now on each new login to this systems desk needs your laptop AND a code from your phone.
   Each code works once. 5 wrong codes within ten minutes lock that laptop out of the systems desk for 5 minutes.
   ```

   Then the recovery bundle, `recovery_bundle.age`, with no question. The
   bundle took each item when its account command made the item. Now the
   window checks that the bundle holds every item, commits and pushes it
   into the systems repository, and puts a copy into the locked backup
   bucket. The bundle holds the vault passphrase, the production private
   key, the desk's WireGuard private key, the shared root console
   password, the phone code's emergency codes, and the provider,
   Cloudflare and Backblaze credentials. The phone code's secret itself
   stays only on the desk. When an item is missing, the window stops and
   names the item: run the account command that makes the item, then ask
   the person to type `ssh desk01-lock` again, which continues where it
   stopped.

   The window ends:

   ```text
   Done.  Your phone code is ready.  Your coding agent locks your systems desk next, then builds your servers.

   Go back to your coding agent.
   ```

   It says "Done.  Your systems desk is locked." instead only when the
   lock has run: `/etc/systems-desk/locked` exists, and
   `/etc/ssh/sshd_config.d/00-systems-desk-root-login-before-the-lock.conf`,
   which lets root in from the laptop with the laptop key alone, is gone.
   In this first setup that happens in step 10.

   **Tell the person:** no message while the person is in the window.

   **Check:** the results file shows the console password, the recovery
   passphrase, the phone code and the recovery bundle done and
   `finished: true`, and `main` in the desk's checkout holds
   `recovery_bundle.age`.

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
   tried. Reason: the person gave the address once already, in "Your
   app", and a second question reads as if the setup forgot the answer.

   **Check:** `git ls-remote backup main` on the laptop shows the same
   commit as `main` in your clone.

10. **Close root SSH from the laptop.** Run the bootstrap's `lock` stage.
    It closes root SSH from the laptop, so from now on the desk admits
    only the person and you, each with the laptop key and a phone code.
    Your shared login, opened in step 1, stays open.

    Run it after `cd ~/example-setup/desk_bootstrap_copy` as a call of its
    own:

    ```sh
    # On the laptop, in ~/example-setup/desk_bootstrap_copy:
    ~/.local/bin/mmx run systems_desk --var desk_name=desk01 --only-fleet-stages lock --connection ssh_only
    ```

    Then run `cd ~/code/example_systems` as a call of its own, and remove
    the laptop's setup folder, which holds the bootstrap copy, the key
    command and the Backblaze keyID, and no secret:

    ```sh
    # On the laptop:
    rm -rf ~/example-setup
    ```

    The laptop keeps mmx, doubleshell, `~/.ssh/desk01`, `~/.ssh/desk01.pub`,
    `~/.ssh/desk01_known_hosts`, the desk's SSH entries, and
    `~/.config/doubleshell/desk01.conf`. Remove any provider tool's saved
    login that the provider guide names; most guides name none, because the
    scripts use `curl`. The person's own key files, such as
    `~/.config/backblaze/env`, stay: they are the person's.

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

11. **Then you work alone.** Chapters 5 to 9 need nothing from the person
    until the first release, except the nameserver change of step 4 when
    it waits for DNSSEC. Run each long run as a desk job, as
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

- **The team has no domain yet** (step 3): after the Cloudflare account,
  the person registers the domain at Cloudflare, at the price Cloudflare
  shows. Step 4 is skipped.
- **Cloudflare, Backblaze, GitHub or Stripe refuses a key** (steps 3 and
  5 to 7): the command stops with the service's reason. Say the reason in
  one line, and ask for the key again: one more copy, or a check of the
  file the person named. A refused Cloudflare token needs a new token
  from the same link.
- **The person pastes a key into the chat:** say in one line that the key
  is no longer private, and ask the person to make a new key at that
  company. Use the new key, and delete the old one at the company.
- **The person stops in the middle:** read the results file, and carry on
  at the first account that is not `done`. The account commands keep
  what they made, and a rerun makes nothing twice. The lock window
  continues at its first step that is not done. Backblaze's key is not
  needed again for the recovery bundle's copy: the Backblaze command kept
  the backup bucket's write key on the desk for that copy, and the lock
  window deletes it after the copy.
- **The coding agent does not run on the person's laptop:** use way B for
  every key, and ask the person for each file's values by way B too.
- **The domain shows "Pending" for longer than the setup takes:** chapters
  5 to 8 continue. Chapter 9's check through the public address waits for
  "Active".

## Why the chapter works this way

**You lead, and small commands do the fixed work.** People come with
their own accounts, keys and history. A fixed program that walks the same
screens for everyone failed the first real setup with existing accounts:
it told a person who had every account to sign up again, and to make a
Backblaze master key that would have stopped the old one. The whole
point of a coding agent is that it works with the person's current
setup. So you ask, and adapt to each account. A small
command per account does the part that must be exact, once it has a key.

**A key goes from the clipboard or a file straight to the desk.** The
chat goes to the company that runs you, so a key never enters it. You
start the pipe, but the key passes from the laptop's clipboard or file to
the desk's command without your conversation seeing it. The desk's
command prints no key and reads none back, so the sudo rule lets you put
a key in and never get one out.

**The clipboard first, the paste window second.** Copying and typing
`copied` keeps the person in the chat. The paste window works everywhere,
so it stays as the backup for a laptop whose clipboard you cannot read.

**The domain switch has a fixed order.** Every record at Cloudflare
first, the mail records before all, then DNSSEC off, then the
nameservers. A switch out of order stops the site and the email.

**Separate accounts.** The backups are at Backblaze, away from the server
provider and Cloudflare, so a lost server account leaves the backups safe.

**The master key is never stored.** Every server gets its own narrow key,
and nothing needs the master key again. The recovery bundle holds only the
read-only Backblaze key that restores the backups, never the master key.

**MMHotline's backup bucket stays unlocked.** Litestream (checked with
0.5.18 on 2026-11-12) sends no checksum with its uploads, and B2 refuses
uploads into a locked bucket without one.

**One recovery passphrase.** The recovery bundle holds every item a lost
desk needs, encrypted. The person saves one passphrase instead of seven
secrets, and types it back once, so a bad copy shows at once.

**Only the lock is a window.** The console password, the recovery
passphrase and the phone code are for the person's eyes only, so they
appear in the person's own terminal, never in the chat.

**The phone code comes last.** The phone code is the lock. Before it, the
laptop key alone opens the desk, so you do the whole desk setup yourself.

**WAIT FOR A NEW CODE.** Each code works once, for the person and for you
alike, because both logins share one phone-code secret.

Next, in the same reply, as the skill's "Now and next" rule says: [Chapter 5: Put your site behind Cloudflare and lock your private pages](05_put_your_site_behind_cloudflare_and_lock_your_private_pages.md).
