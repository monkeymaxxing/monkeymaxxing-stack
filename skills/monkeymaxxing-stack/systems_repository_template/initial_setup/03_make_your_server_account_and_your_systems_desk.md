# Chapter 3: Make your server account and your systems desk

**When:** after chapter 2 (get your app ready to deploy). The first CI run
can still be running.

**What this chapter does:** the person makes the account at the server
provider and one key there. You build the person's systems desk,
`desk01`, with that key: a small server of the person's own, in another
location than production. The desk is a locked key box. It holds the
production key, the vault and the person's tokens. You use them through
the desk, and you can never copy them. At the end, the desk's checkout
is the team's main copy of the systems repository, until `util01` holds
it from chapter 7 on.

**Who acts:** the person makes the provider account, types the key
into one short command on the laptop, and says yes to the real monthly
price. You do everything else: the
laptop's keys and SSH settings, the private backup repository at the Git
host, the desk, and its whole setup.

**Tell the person when the chapter starts:** no separate message. The
account screen of step 1 is the opening.

## Before you start

- **Secrets never go into the chat.** The chat is stored at your
  provider. The person types each secret at a hidden prompt: on the
  laptop for the provider key, because the desk does not exist yet, and
  on the desk for every other secret.
- **The laptop.** We say "laptop" throughout because most people use one.
  Any computer the person develops on works the same way, such as a
  desktop or a Mac mini.
- **The provider guide.** Every provider value in this chapter comes from
  the selected [provider guide](../provider_guides/README.md): the account
  pages, the key and its shape, the API address, the listing request, the
  scripts and the prices.
- **The chapter's parts.** Each part below numbers its own steps from 1,
  because the operating procedures cite them, such as "chapter 3's step 4"
  for step 4 of "Create desk01 through WireGuard".

## The provider account

1. **The provider account and its key.** First write the laptop key
   command, `~/example-setup/enter-the-hetzner-key`, as
   [The laptop key command](../provider_guides/README.md#the-laptop-key-command)
   says, with the values of the provider guide's own "The laptop key
   command" section. `example` is the company's name in lowercase with
   hyphens, and `hetzner` is the provider's short name.

   Set `systems_desk_provider_api_url` and, at a provider that signs
   requests, `systems_desk_provider_api_authentication` in
   `mmx_project_settings.yml`, as the guide says, including the trailing
   slash.

   **Ask the person:** the screen below, whole, as the last text of your
   reply, with the guide's own website steps. At OVHcloud, steps 4 and 5
   become the guide's project step and its key page, with the page's own
   field names; the command asks for the project's ID first, then shows
   the filled-in key link, then asks for the three values. After the key
   comes the one price screen of
   [the real price, approved once](#the-real-price-approved-once).

   ```text
   Your accounts: account 1 of 3, Hetzner (your servers)

   What this is for:
     Hetzner runs your servers.  I build them with a key you make there.

   Do this now:
     1. Open  https://accounts.hetzner.com/signUp  and make an account.
     2. Save the login in 1Password.
     3. Turn on two-step sign-in, which Hetzner calls  Two-factor authentication (2FA):
          https://accounts.hetzner.com/tfa
     4. Open  https://console.hetzner.com  and press  New project.  Name it  Example.
     5. In the project, open  Security,  then  API tokens.  Hetzner calls the key an API token.
        Press  Generate API token.  Name it  example-desk.  Choose  Read & Write.

   Then open a terminal on this laptop and type:

     ~/example-setup/enter-the-hetzner-key

   It asks for the key, checks it with Hetzner, and keeps it for me.
   Then leave that window open.  It goes on to your next accounts by itself later.

   After the key, I check what Hetzner has in stock and show you the real monthly price here.
   Nothing is ordered before your yes.  I wait here until the key is in.
   ```

   First start the wait for the key file as a background command, as
   [`AGENTS.md`, "The two windows agree"](../AGENTS.md#the-two-windows-agree)
   says, then end your reply with the screen, whole, as its last text:
   your turn ends there, with no tool call after it.

   ```sh
   # On the laptop, as a background command. Waits up to an hour for the key file.
   for i in $(seq 720); do [ -f ~/example-setup/provider-key ] && break; sleep 5; done
   ls -l ~/example-setup/provider-key
   ```

   When the wait ends with the file there, carry on without being told.
   When the hour passed, start the same wait again, and end your reply
   with one line that you still wait for the key. Never print the file.
   An agent with no background commands ends its reply with the screen
   and "When it says  Hetzner accepted the key,  tell me "done" here."
   The key command stays open after that on purpose: chapter 4 step 2
   tells it when the desk is ready.

   **Check:** `~/example-setup/provider-key` exists, mode `0600`.

2. **The backup repository at the Git host.** The team's main copy of
   the systems repository lives on the team's own machines: the desk's
   checkout first, then `util01` from chapter 7. The Git host keeps a
   private backup copy, which you push from the laptop with the person's
   own login ("The main copy and the backup at the Git host" in
   [`AGENTS.md`](../AGENTS.md#the-main-copy-and-the-backup-at-the-git-host)). When the
   person gave the backup repository's address on chapter 2's screen, use
   that address exactly as given, and skip `gh repo create` and the
   screen below; still set the address, as the end of this step says. Never ask for the address again. Otherwise make an empty
   private repository, `example_systems`, at the app's Git host and owner
   from chapter 2. With `gh` signed in:

   ```sh
   # On the laptop:
   gh repo create OWNER/example_systems --private
   ```

   Without `gh`, show one screen with the Git host's new-repository link,
   already filled in:

   ```text
   Your accounts: one more page, a private backup of your systems repository at GitHub.

   Do this now:
     1. Open  https://github.com/new?owner=OWNER&name=example_systems&visibility=private
        It names the repository  OWNER/example_systems.
     2. Press  Create repository.
     3. If you gave it another name or owner, tell me the name.  Otherwise you need not tell me anything.
   ```

   Set `systems_repository.backup_url_at_the_git_host` in
   `mmx_project_settings.yml` only to an address that `gh` made or the
   person saw on this screen, such as
   `https://github.com/OWNER/example_systems.git`, with the name the
   person gave instead when the person changed it. Never write an
   address the person did not see or confirm. Reason: a backup address
   that names a repository nobody made fails at the first backup push, in
   chapter 4, far from its cause. No key of the desk or
   of a server goes to the Git host.

   **Tell the person:** no message with `gh`. You made the repository.

   **Check:** `gh repo view OWNER/example_systems --json visibility` says
   `PRIVATE`. Without `gh`, the first backup push in chapter 4 checks the
   repository.

3. **The provider scripts and the locations.** Write the provider scripts
   into `server_management_scripts/` of the laptop's copy, from the guide
   and the
   [provider script contract](../server_management_scripts/README.md#write-the-teams-provider-scripts).
   The scripts call the provider's API with `curl` and `jq`, so install
   no provider program on the laptop. Check the key with the list script,
   which reads it from the environment only:

   ```sh
   # On the laptop:
   SERVER_PROVIDER_API_TOKEN="$(cat ~/example-setup/provider-key)" ~/code/example_systems/server_management_scripts/list_the_servers_at_the_provider
   ```

   A new account answers `{"servers": []}`.
   Choose `desk01`'s location: the provider location chapter 1 picked for
   the desk, different from production's. Use Debian 13 on x86-64, by
   default with 2 vCPUs and 4 GB of memory. Check the provider's attached
   private networks before keeping `vars.wireguard_network: 10.20.0.0/16`.
   Keep `desk01.address: 127.0.0.1` for the desk's own runs after the
   bootstrap.

   Before you write the scripts, say in one line what they are: "I am
   writing the small scripts that talk to Hetzner for me; nothing in
   them needs reading."

   **Tell the person:** only that one line. The price comes next, in
   [the real price, approved once](#the-real-price-approved-once).

   **Check:** the list script answers, and `vars.wireguard_network`
   overlaps no provider network.

4. **The settings that chapter 4 reads.** `set-up-outside-services go-live`
   in chapter 4 reads these settings from the systems repository, so write
   them now, in `mmx_project_settings.yml`:

   - `vars.backups`: Backblaze's S3 endpoint and region for the region
     nearest the servers, such as `s3.eu-central-003.backblazeb2.com` and
     `eu-central-003` for servers in Europe, and the buckets' names,
     `production_bucket`, `uploads_bucket` (`""` when no app keeps
     uploads), and MMHotline's bucket in `mmhotline_backup_replica_url`,
     such as
     `s3://acme-mmhotline-backup/mmhotline?endpoint=https://s3.eu-central-003.backblazeb2.com&region=eu-central-003`.
     Bucket names are unique across all of Backblaze, so use the company's
     name in them. The three backup lengths keep the template's values,
     each written out there with its reason.
   - For each app that keeps uploads, `production_uploads_r2_bucket` and
     `production_uploads_r2_key_variables`, and
     `backups.uploads_backup_runs_on: [util_server]`. With no app that
     keeps uploads, `backups.uploads_backup_runs_on: []`.

   **Tell the person:** no message.

   **Check:** the `grep` for `the setup fills it` lists no value of
   chapters 1 to 3 other than the desk's and its laptop's, which the desk's
   steps below fill, and `mmx validate every_server` stops, if at all, only
   on such a value or one whose comment names a later chapter. Reason: in
   three newcomer test runs `go-live` stopped in the person's terminal on a
   bucket name left as the template's example.

## The real price, approved once

1. **Check the stock and show the real price.** Right after the key
   works, before anything is ordered, check the stock and read the price
   of every server of the plan, in one go: `desk01`'s size in the desk's
   location, and each production server's size in production's location
   (`app001`, `db01`, `util01`, and with the fuller system `staging01`
   and `app002`), with the sizes of
   [chapter 6's table](06_create_your_three_production_servers.md#steps).
   Use the route this chapter already uses to read the provider before
   the desk exists: the provider scripts and the guide's read-only
   requests, with `SERVER_PROVIDER_API_TOKEN` read from
   `~/example-setup/provider-key` in the same command, or the guide's
   public stock route when its "Stock" line names one. These are `curl`
   calls that only read, so no provider program is installed. The
   guide's "Stock" line names the request, such as Hetzner's
   `GET /server_types`, and `read_the_monthly_price_at_the_provider` gives
   each size's monthly price with its public address. At OVHcloud, the
   desk's line is the total of the guide's order cart, which orders
   nothing.

   When a size is sold out where the plan put it:

   - First try the same size at the provider's other locations in the
     same region (the same continent), and recommend the one that has it
     in one line: "Nuremberg is sold out of this size; Helsinki has it,
     at the same price." The production servers stay together in one
     location.
   - Only when no nearby location has the size, recommend the next
     bigger size, with the old total, the new total and the reason, one
     line each.
   - **Always also offer "wait and try again"** when a cheap size is sold
     out, with the honest line: "Cheap sizes often come back within the
     hour. I check again every few minutes and tell you when one is
     back." On that answer, re-check in the background with a 5-minute
     bound, such as `timeout 5m bash -c 'until CHECK; do sleep 60; done'`,
     and start it again while the size stays sold out, up to about an
     hour. At each end, say one line, such as "Still sold out at 10:40;
     I check again. I'll tell you when a size is back (I look every few
     minutes)." Reason: in a newcomer test run, Hetzner's smallest size
     was sold out in every location at 04:54 and back in Nuremberg at
     04:57; in another, the person heard nothing during a 15-minute stock
     wait unless they asked.
   - **At Hetzner, also offer "use OVHcloud instead"** beside waiting
     and the bigger size, while the person has made no account other than
     Hetzner's for the setup: "Or I set up your servers at OVHcloud
     instead, which has this size now." Check OVHcloud's stock first, as
     its guide says, and give its total in the same line. On that
     answer, read OVHcloud's guide and start this chapter again with it.
     Reason: a sold-out cheap size at Hetzner otherwise leaves only a
     wait or a higher price, and the person has nothing yet to undo.

   Re-check the stock right before you show any price dearer than the
   plan's, and again at the moment of each order: the desk's, and the
   three servers' in chapter 6's step 4. Reason: stock changes within
   minutes, both ways.

   **The desk's place.** By default the desk is in a different location
   from production. Reason: an outage of the production location then
   leaves the desk working, so you can still reach the provider and
   rebuild from it. The separate place is a good default, not a must:
   when the desk's size costs more there than in production's location,
   or is sold out there, show both on the price screen with the
   difference in money, and recommend the cheaper place unless the person
   asked for the separate one:

   ```text
     Systems desk, same place as your servers:   about €6 a month   (I recommend this)
     Systems desk, a separate place:             about €20 a month, €14 more
       A separate place keeps your systems desk working if your servers' location has an outage.
   ```

   **The app server's size.** `app001` starts at the smallest size, as
   [chapter 6's table](06_create_your_three_production_servers.md#steps)
   says. Offer the next size on the price screen, in one line, for a
   heavier app, such as an app that runs many worker processes or holds
   big files in memory:

   ```text
     A bigger app001 (4 CPUs, 8 GB), for a heavier app:  about €3 a month more.  Say "bigger app server".
   ```

   Never offer a kind of product the person did not ask about, such as
   a provider's hourly cloud servers in place of its monthly ones,
   without saying plainly why and what it costs a month against the
   plan.

   **Ask the person,** as the last text of your reply, with no tool call
   after it:

   ```text
   Your real price, checked with Hetzner just now:

     Systems desk  desk01, Nuremberg       about €6 a month
     app001        Falkenstein             about €6 a month
     db01          Falkenstein             about €6 a month
     util01        Falkenstein             about €6 a month
     Backups       Backblaze               a few cents a month at first

     In all:  about €24 a month, before VAT

     A bigger app001 (4 CPUs, 8 GB), for a heavier app:  about €3 a month more.  Say "bigger app server".

   Say "yes", and I order your systems desk now, and your three servers as soon as it is ready.
   Or tell me what to change.
   ```

   The screen leads with the real numbers: each server's line shows the
   size and place you will order, and "In all" the real total. A change
   from chapter 1's plan gets one line under "In all", such as:

   ```text
     Falkenstein is sold out of app001's size today.  Helsinki has it, at the same price.  I recommend Helsinki.
   ```

   or, only when no nearby location has the size:

   ```text
     More than the plan's "from about €24": Hetzner has app001's size nowhere in Europe today,
     so app001 is the next bigger size.
   ```

   Never word it as a correction of yourself, such as "this is not the
   price I quoted". Reason: chapter 1's plan said "from about", and the
   real numbers are what the person approves.

   Each price includes the server's public address, so the screen does
   not say so. Name sizes in the person's words, such as "2 CPUs, 4 GB",
   never the provider's type code, such as `cx23`. When the person must
   choose between plans, such as after a sell-out, give each option at
   most three lines: its total a month, what differs from the plan, and
   its one drawback. Reason: in a newcomer test run, the options carried
   type codes and four lines each, and the person had to think.

   The person's yes approves the desk's order now and the three servers,
   which you create as soon as the desk is ready
   ([Create the three production servers now](#create-the-three-production-servers-now)),
   at these sizes, locations and prices. Write the
   approved sizes and locations into the settings that chapter 6 and
   "Create desk01 through WireGuard" read, and the monthly total into the
   commit message. Order only after the yes in the chat.

   **Check:** the person said yes to a screen that showed the real
   monthly total, read from the provider after the key worked.

## Create desk01 through WireGuard

In every command from here on, replace `alex` with
`desk01.vars.person_unix_username` and `example_systems` with the
repository's name, including paths inside quoted SSH commands.

1. **The laptop's keys.** Create a separate laptop SSH key with
   `ssh-keygen -t ed25519 -N '' -f ~/.ssh/desk01`. Leave the key's
   passphrase empty: the phone code supplies the second factor. Never
   reuse the app's Git key or a production key for desk login.
   Run `~/.local/bin/doubleshell create-wireguard-key`. The command saves
   `~/.config/doubleshell/wireguard_private_key` and prints the public key.
   Replace `desk01.vars.allowed_laptops` in `inventories/servers.yml` with
   the laptop's `laptop_name`, the printed `wireguard_public_key`,
   `private_ip: 10.20.10.1`, and `ssh_public_key` from
   `~/.ssh/desk01.pub`. The same laptop key opens the person's login and
   the coding agent's login. Further laptops take unused addresses from
   `vars.private_ip_ranges.systems_desk_laptops`.

   **Tell the person:** no message, because the person does nothing.

   **Check:** `~/.ssh/desk01.pub` and
   `~/.config/doubleshell/wireguard_private_key` exist, and
   `desk01.vars.allowed_laptops` holds the laptop.

2. **Create the desk.** First register `~/.ssh/desk01.pub` with the
   provider, as the provider guide says, with `SERVER_PROVIDER_API_TOKEN`
   read from `~/example-setup/provider-key` in the same command. Then run
   the block below once, as one command, because the desk's private key
   lives only in shell memory and your shell keeps no variables from one
   command to the next. The block creates the desk's WireGuard pair with
   `doubleshell create-server-wireguard-key`, renders the first-boot data
   through `server_management_scripts/render_server_first_boot`, prints
   the desk's public key and never the private key, creates the desk with
   the provider guide's create command, and clears the private first-boot
   file whether the provider accepts or refuses the request. Only after
   the provider accepted the request does it make
   `~/example-setup/desk-ordered`, which tells the waiting key command
   that the desk is ordered.

   ```sh
   # On the laptop. Creates desk01 at the provider, once.
   set -euo pipefail
   set +x
   umask 077
   cd ~/code/example_systems
   first_boot=~/example-setup/desk01-first-boot.yml
   trap ': > "$first_boot"' EXIT
   desk_keys=$(~/.local/bin/doubleshell create-server-wireguard-key)
   # LAPTOP_WIREGUARD_PUBLIC_KEY: the public key that create-wireguard-key printed in step 1.
   laptop_public_key='LAPTOP_WIREGUARD_PUBLIC_KEY'
   printf '%s' "$desk_keys" | jq --arg laptop_public_key "$laptop_public_key" \
     '{private_key, private_ip:"10.20.9.1", peers:[{public_key:$laptop_public_key, allowed_ips:["10.20.10.1/32"]}]}' |
     ./server_management_scripts/render_server_first_boot > "$first_boot"
   desk_public_key=$(printf '%s' "$desk_keys" | jq -r .public_key)
   unset desk_keys
   printf 'desk01 WireGuard public key: %s\n' "$desk_public_key"
   # The provider guide's create command for desk01: desk01's size and location, the guide's Debian 13 image,
   # and the name under which ~/.ssh/desk01.pub is registered.
   SERVER_PROVIDER_API_TOKEN="$(cat ~/example-setup/provider-key)" ./server_management_scripts/create_a_server_at_the_provider \
     --server-name desk01 --server-type SERVER_TYPE --location LOCATION --image IMAGE --ssh-key-name SSH_KEY_NAME \
     --first-boot-data "$first_boot" --wireguard-public-key "$desk_public_key" --wireguard-private-ip 10.20.9.1
   : > ~/example-setup/desk-ordered
   ```

   The desk's only first-boot peer is the laptop, without an endpoint.
   Public SSH stays closed from first boot. Save the printed public key in
   `desk01.vars.wireguard_public_key`. Record the returned public address as
   `desk01.vars.public_ipv4_address` and the returned `id` as
   `desk01.vars.provider_server_id`; at OVHcloud (a VPS) and Google Cloud,
   also the order or create receipt's service or instance name as
   `desk01.vars.provider_server_name`. When the provider refuses the
   request, such as for no stock, the block stops before
   `desk-ordered`: tell the person in one line, and show the price screen
   of [the real price, approved once](#the-real-price-approved-once) again,
   with the stock as it is now.

   **Tell the person,** as the last text of the reply that ends your turn
   once step 4's bootstrap runs in the background:

   ```text
   I am building your systems desk now, a small server of your own that holds your keys.
   It takes about 10 minutes.

   In about 10 minutes, the window where you typed the Hetzner key goes on by itself
   and shows your next account, Cloudflare.  I'll say when.
   Until then, you have nothing to do.
   ```

   **Check:** the provider lists `desk01`, `desk01.vars.public_ipv4_address`
   holds its address, `desk01.vars.provider_server_id` holds its ID,
   `~/example-setup/desk01-first-boot.yml` is empty, and
   `~/example-setup/desk-ordered` exists.

3. **The laptop's way in.** Write `~/.config/doubleshell/desk01.conf`
   with your write tool, as the following block. The file holds no secret:
   it has no `PrivateKey` line, so doubleshell reads the laptop's private
   key from `~/.config/doubleshell/wireguard_private_key`. Replace the
   desk's public key and the documentation public address with the actual
   values:

   ```ini
   [Interface]
   Address = 10.20.10.1/32

   [Peer]
   PublicKey = DESK_WIREGUARD_PUBLIC_KEY
   Endpoint = 203.0.113.91:443
   AllowedIPs = 10.20.9.1/32
   ```

   doubleshell reads the wg-quick format. No laptop VPN interface or
   service starts. Add the desk's entries to `~/.ssh/config`. Each entry
   is one short name the person or you type:

   ```sshconfig
   Host desk01 desk01-agent desk01-setup desk01-secrets desk01-review
     HostName 10.20.9.1
     IdentityFile ~/.ssh/desk01
     IdentitiesOnly yes
     ForwardAgent no
     UserKnownHostsFile ~/.ssh/desk01_known_hosts
     StrictHostKeyChecking yes
     ProxyCommand /Users/alex/.local/bin/doubleshell --wireguard-config ~/.config/doubleshell/desk01.conf proxy-ssh %h %p

   Host desk01 desk01-setup desk01-secrets desk01-review
     User alex

   Host desk01-agent
     User coding-agent
     ControlMaster auto
     ControlPath ~/.ssh/cm-%C
     ControlPersist 1h
     ServerAliveInterval 30

   Host desk01-setup
     RequestTTY yes
     RemoteCommand set-up-outside-services go-live

   Host desk01-secrets
     RequestTTY yes
     RemoteCommand set-up-outside-services secrets

   Host desk01-review
     RequestTTY yes
     RemoteCommand review-and-apply-the-systems-desk-settings
   ```

   Write `ProxyCommand`'s doubleshell with the laptop's home folder written
   out (`$HOME`), such as `/Users/alex/.local/bin/doubleshell`. Reason:
   `~/.local/bin` is not on a Mac's path, and a full path runs the same
   doubleshell in every shell.
   `desk01` is the person's own login. `desk01-agent` is your login, as
   `coding-agent`: one shared connection that later commands reuse. The
   other three each start one command for the person: `desk01-setup` in
   chapter 4, `desk01-secrets` for a key the vault still lacks, such as
   Pushover's in the alerts part of the setup, and `desk01-review` for a desk
   review.
   Enroll the first SSH host key through the authenticated WireGuard
   route:

   ```sh
   # On the laptop:
   ssh -o StrictHostKeyChecking=accept-new root@desk01 true
   ```

   Copy the observed host key into the repository's `ssh/known_hosts`
   under `desk01` and `10.20.9.1`. The laptop's file may hold the line
   hashed, as Debian's SSH settings write it, so read it with
   `ssh-keygen -F`:

   ```sh
   # On the laptop:
   ssh-keygen -F 10.20.9.1 -f ~/.ssh/desk01_known_hosts
   ```

   The answer's line that does not start with `#` holds the host name,
   the key type and the key. Add two lines to `ssh/known_hosts` with your
   edit tool, each with the key type and the key: one starting `desk01`,
   one starting `10.20.9.1`.

   **Tell the person:** no message, because the person does nothing.

   **Check:** `ssh -o StrictHostKeyChecking=accept-new root@desk01 true`
   exits 0, and `ssh/known_hosts` holds `desk01`'s lines.

4. **Copy the repository and run the bootstrap.** Commit every setting of
   chapters 1 to 3 in the laptop's copy first, and check that
   `~/.local/bin/mmx validate systems_desk --var desk_name=desk01` passes:
   it names a value of the desk or its laptop that is still empty. Leave
   `production_ssh_public_key` and `root_ssh_public_keys` as the template
   has them: the bootstrap writes the desk's production key into both, in
   the desk's checkout. After the bootstrap, never copy the laptop's copy
   over the desk's checkout again: it would empty both settings, and
   `every_server` would refuse to run. Reason: in a newcomer test run,
   the template's example key replaced the desk's own, and the first
   install locked the desk out of the servers.

   The bootstrap is the
   desk's whole setup, run as root from the laptop, before the lock. It
   makes the production key, the vault passphrase and the vault, starts
   the systems repository in your checkout on the desk,
   `/home/coding-agent/systems_repository`, with its first commit,
   records the first desk review, and opens your login,
   `coding-agent`. The desk's own commits name `coding-agent on desk01` as
   their author. Your later commits keep the author from the laptop's
   `git config user.name` and `git config user.email`:
   `publish-branch-to-main` keeps them as they are.

   The provider image does not have the `coding-agent` account yet, so root
   writes the copy, and the bootstrap makes it the coding agent's own.
   Copy the files without the laptop's `.git`: the bootstrap starts the
   desk's history with its own first commit, and stops on a copy that has
   commits already.

   ```sh
   # On the laptop. Copies the laptop's systems repository to desk01, without Git's history.
   set -euo pipefail
   cd ~/code/example_systems
   # COPYFILE_DISABLE=1 stops a Mac's tar from adding ._ metadata files; Linux ignores it.
   # --warning=no-unknown-keyword keeps the desk's tar quiet about a Mac's file labels, which it skips anyway.
   COPYFILE_DISABLE=1 tar --exclude=./.git --exclude=./.mmx -cf - . |
     ssh root@desk01 'mkdir -p /home/coding-agent/systems_repository && tar --warning=no-unknown-keyword -C /home/coding-agent/systems_repository -xf -'
   ```

   Then point only the laptop's own copy at the bootstrap connection. MMX
   reads how it connects from the inventory and `ssh/desk01`, not from
   `--var`: set `desk01.address` to `10.20.9.1` and
   `desk01.ssh_identity_file` to the laptop key's absolute path; in
   `ssh/desk01`, keep `HostKeyAlias desk01`, replace `IdentityFile` with
   that absolute path, and add the desk-only `ProxyCommand` from the
   laptop's SSH entry. Then run:

   ```sh
   # On the laptop, in ~/code/example_systems:
   ~/.local/bin/mmx run systems_desk --var desk_name=desk01 --only-fleet-stages systems_desk --connection ssh_only
   ```

   Start the run as a background command, then end your reply with step
   2's message, as the skill's "Long work" rule says; the run's end wakes
   you. The `systems_desk` stage runs alone because `util01` does not exist
   yet. The run installs the waiting security updates, which take several
   minutes. Root SSH from the laptop stays open until the lock in
   chapter 4.

   Right after the run, move the provider key to the desk's API proxy,
   over the same root login, on standard input, and delete the laptop
   file. MMX keeps every laptop file a run reads in the run's history, so
   the bootstrap cannot do this itself. The person does nothing. Use the
   provider guide's server listing path, here Hetzner Cloud's `servers`.
   
   ```sh
   # On the laptop. Moves the provider key to desk01's API proxy, then deletes the laptop's copy.
   set -euo pipefail
   cd ~/code/example_systems
   ssh -F ssh/desk01 root@10.20.9.1 set-up-outside-services write-api-token-proxy-file \
     --api server-provider --server-listing-path servers < ~/example-setup/provider-key
   rm ~/example-setup/provider-key
   ```

   At Scaleway, add `--token-header X-Auth-Token`. At a provider whose
   requests the proxy signs (OVHcloud, AWS, Google Cloud), add
   `--provider-api-authentication` with
   `systems_desk_provider_api_authentication` and
   `--provider-api-address` with `systems_desk_provider_api_url`. The key
   file's line is already in the form the proxy reads, as
   [The laptop key command](../provider_guides/README.md#the-laptop-key-command)
   says. The command checks a listing through the proxy, and keeps the
   laptop file when the check fails, so run it again after the cause is
   fixed.

   **Tell the person while waiting:** nothing more. The message of step 2
   said how long the build takes. When the person writes meanwhile,
   answer, and say in one line what the run is doing now.

   **Tell the person after:** nothing yet. First create the three
   production servers, as
   [Create the three production servers now](#create-the-three-production-servers-now)
   says; then chapter 4's first screen follows.

   The run's normal end prints `The desk is ready.` and the production
   public key. When the run ends with an error such as
   "node busy with job …" or a lost connection, the desk carries on with
   the job by itself. Wait two minutes and run the same command again.
   "node busy" again means the desk is still at work, so wait once more.

   **Check:** the run printed `The desk is ready.`, the key's move
   succeeded and the laptop file `~/example-setup/provider-key` is gone,
   and `ssh desk01-agent true` logs in as `coding-agent` with no code.

## Create the three production servers now

As soon as the desk is ready, and before chapter 4's step 2 opens the
person's next accounts, create `app001`, `db01` and `util01`. They stay
idle until chapter 7 installs everything on them. Reason: stock changes by
the hour; in a newcomer test run, the approved sizes sold out in the 35
minutes between the person's yes and the creation. The servers need only
the desk: the Cloudflare tunnels' tokens and every other secret are read
later, when chapter 7 installs everything.

1. **Your login and your clone.** Do chapter 4's
   [step 1](04_set_up_your_accounts_and_lock_your_desk.md#steps) now: open
   your shared login on the desk, and clone the desk's repository on the
   laptop. Every change from here on is made in that clone.

   **Check:** chapter 4's step 1 check passes.

2. **Create the servers.** Follow chapter 6's
   [Before you start](06_create_your_three_production_servers.md#before-you-start),
   with its check that no private network overlaps the WireGuard network,
   then its steps 1 to 5. Chapter 6 later does only its steps 6 and 7.

   **Tell the person first,** one line, between your work:

   > Your systems desk is ready. I am creating your three servers now, so the prices you approved hold: `app001` for your app, `db01` for its data, and `util01` for the system tools. About 5 minutes. Nothing for you.

   **Check:** chapter 6's step 5 check passes.

## Update the desk's production peers

1. **Update the peers.** After a commit that adds, replaces, or removes a
   server, you push it and then run, on the desk:

   ```sh
   # On the laptop:
   ssh desk01-agent sudo -n update-this-desks-wireguard-peers
   ```

   The command fetches pushed `main`, reads the servers in
   `inventories/servers.yml`, and sets this desk's WireGuard peers to
   exactly those servers: it adds the new ones, changes the replaced
   ones, and removes the gone ones. It prints the commit it used and each
   peer it added, changed or removed, or "No change". The desk's laptops
   keep their peers, and open sessions keep working.

   The coding agent of each other systems desk, on that person's laptop,
   runs the same command on that systems desk at the start of its
   session, and whenever SSH to a server times out. A server without a
   `wireguard_public_key` yet is left out. When the inventory gives a
   server a value a server must not have, such as a laptop's key or an
   address in the desks' or the laptops' block, the command names the
   server and the value and changes nothing. You then correct the
   inventory and push.

   **Tell the person:** no message, because the person does nothing.

   **Check:** `ssh desk01-agent 'cd systems_repository && ssh -F ssh/config root@10.20.1.1 true'`
   reaches `app001`.

Reason: `util01` never manages a person's desk, and a server change must
not need the person. The command runs as root, so it is the copy that the
last desk review installed, and it takes only the inventory from the Git
host, checking each value. The desk review writes the same peers from
pushed `main` before it rewrites `/etc/wireguard/wg0.conf` and copies them
into that file, so a desk review keeps them, and `wg0` loads them again
after a reboot.

## Check remaining example values

1. **Replace the example values.** Before chapter 7 (install everything
   on the production servers), the `grep` for `the setup fills it` in
   `mmx_project_settings.yml` and `inventories/servers.yml` lists
   nothing, and `mmx validate` passes. Then replace every remaining example value,
   including zero software checksums, with the verified release
   values. Keep documentation examples and script usage examples. Run the
   search in the laptop's clone of the systems repository:

   ```sh
   # On the laptop:
   grep -rnE 'example|203\.0\.113\.|0{40}' --exclude-dir=.git --exclude-dir=.mmx --exclude=AGENTS.md --exclude=triage_agent_rules.md --exclude=talking_with_the_team.md --exclude-dir=initial_setup --exclude-dir=operating_procedures ~/code/example_systems
   ```

   Or search with your search tool, with the same pattern and exclusions.

   Replace `example_systems`, the app name `shop`, and `example.com` in
   the copied guide with the team's names. Keep documentation-only public
   addresses in `203.0.113.0/24` and private examples in `10.20.0.0/16`.
   Rewrite README links and verification text for the actual system.
   Keep untested claims marked as not checked.

   **Tell the person:** no message, because the values change only in the
   systems repository, and chapter 7 shows the result.

   **Check:** the search finds only documentation examples and script
   usage examples.

## Secrets

Every secret has one home, and gets there one way. The person types each
secret once, at a hidden prompt, and you never see one.

| Secret | Where the secret is stored | How it gets there |
| --- | --- | --- |
| Every secret the servers use, listed below | The vault, `secrets_vault.age`, in the systems repository. Playbook key names come from `mmx secrets usage`. MMHotline's key names come from the `.secrets` references in `mmhotline_settings.yml` | In the first part of the setup, `set-up-outside-services go-live` (`ssh desk01-setup`): it asks for each key a website gives, makes every random one without a question, and commits and pushes the vault. Later, `set-up-outside-services secrets` (`ssh desk01-secrets`) asks for each key the vault still lacks. `--replace KEY` enters one key again, such as for a rotation: `ssh -t desk01 set-up-outside-services secrets --replace KEY` |
| The person's own tokens: the provider credential, the desk's Cloudflare token, and the R2 key for posting to the status page while `util01` is down | The provider credential: only the API proxy's root-only file. The Cloudflare token: the API proxy's root-only file and the person's own token file on the desk. The R2 key: the person's own token file | The provider credential: the laptop key command of chapter 3, which you move to the desk right after the bootstrap. The Cloudflare tokens: `go-live` makes them |
| The recovery bundle: the vault passphrase, the production private key, the desk's WireGuard private key, the shared root console password, the phone code's emergency codes, the server provider credential, the systems desk's Cloudflare token (and staging's access token when `staging01` exists), the backups' passphrase, and the read-only Backblaze key for restoring them (never the Backblaze master key) | `recovery_bundle.age` in the systems repository, and a copy in the locked backup bucket at Backblaze, encrypted with the recovery passphrase | `go-live` makes it at the lock in chapter 4 |
| The recovery passphrase, and every account's login and recovery codes | The team's password manager | The person saves each one when it is made |

The secrets that servers use are:

- The shared root console password's hash, `shared_root_console_password_hash`.
- The tunnel tokens and the registry token.
- The apps' secrets and database passwords, and the failover monitor's
  logins.
- The backups' B2 keys and passphrases, and MMHotline's backup keys.
- `util01`'s R2 key that reads the apps' uploads, and `util01`'s B2 key
  that copies the uploads, which can write but never delete.
- The Pushover application's token and the Pushover group's key.
- `util01`'s own provider token and the triage agent's credential.
- The MMHotline-down alarm's Cloudflare token and the status page's R2 key.
- The signing secret of MMWatchdog's fleet hub on `util01`, for MMHotline,
  and the vault's own passphrase.

`mmx secrets list-keys` lists the keys and prints no value.
`mmx secrets usage` lists every key that the playbooks read, and says
`not defined` for each one the vault lacks. You run both through your
button on the desk, on pushed `main`:

```sh
# On the laptop:
ssh desk01-agent sudo -n -u servers-mmx run-mmx-on-the-servers secrets usage
```

**Why the vault holds its own passphrase,** as `mmx_vault_passphrase`:
`util01` needs the passphrase to open the vault for MMX runs on `util01`.
When setting up or rebuilding `util01`, MMX runs on the systems desk and
opens the vault with the desk's passphrase file. MMX gives each server
only the secrets the server needs from the vault, so MMX gives `util01`
the value of `mmx_vault_passphrase`, along with `util01`'s remaining
secrets. Reading `mmx_vault_passphrase` needs the vault passphrase
already, so storing the passphrase inside the vault exposes nothing.

## If something is different

- **A brand-new server does not answer within its time limit**: the
  server is new and empty, so delete it at the provider and create it
  again, once, by yourself, with one line to the person, such as "Your
  systems desk did not start properly. I am creating it again; this costs
  a few cents and takes about 5 minutes. Nothing for you." (with the
  server's name, such as `db01`, for a production server). Only a second
  failure goes to the person. Never ask the person to read the provider's
  console to decide. Reason: a new server that hangs at its first boot is
  rare and costs nothing to replace, and the person cannot judge a boot
  console.
- **A provider whose guide gives the scripts whole** ("The provider
  account", step 3): every guide except Hetzner Cloud's. There is no tool
  to install: the scripts send each request, sign it, or make its token,
  in the shell with `curl`, `jq` and the tools the guide names.
- **A provider that needs a project first,** such as OVHcloud or Google
  Cloud: the guide's steps go into the account screen, and the project's
  ID is not a secret. Read the ID with the provider's API once the key
  works, or from the page the guide names, and never ask the person to
  copy it when the key can read it. At OVHcloud the key's own link needs
  the ID, so the key command asks for it first: never write a separate
  command for the ID.
- **A provider network overlaps `vars.wireguard_network`** ("The provider
  account", step 3): choose a free private /16 and update every inventory
  address together.
- **The person makes a new provider key,** such as when the first key
  expires: give the same key command again. It stops the older copy that
  still waits, and once the desk is ordered it only saves the key, as
  [The laptop key command](../provider_guides/README.md#the-laptop-key-command)
  says. Never ask the person to press Ctrl+C or to close a window.
- **The team's systems repository already exists on `util01`** ("Create
  desk01 through WireGuard", step 4), as for a new team member's desk
  ([Add or remove a team member](../operating_procedures/add_or_remove_a_team_member.md))
  or a rebuilt desk
  ([Rebuild a systems desk](../operating_procedures/rebuild_a_systems_desk.md)):
  follow that operating procedure.
- **No stock at the desk's location** ("The real price, approved
  once"): follow the provider guide. At OVHcloud, the guide makes a
  Public Cloud desk until stock returns, and the price screen says so.

## Why the chapter works this way

**The provider key is typed on the laptop, once.** The desk does not exist
yet, and the desk is built with the key. The key sits in a `0600` laptop
file for about ten minutes, then moves to the desk and is deleted.

**One price approval, after the key.** Most providers show their stock
only with the key, and stock changes by the hour. So the person sees the
real total once, checked just before the first order, and that one yes
covers the desk and the production servers.

**One provider key for the desk and `util01`.** Hetzner makes tokens only
on its website, so the desk and `util01` share the one key the person made.
A team can make a narrower second key for `util01` later.

**The whole desk setup runs before the lock.** Root SSH from the laptop
still works, so you do every desk step yourself. The lock in chapter 4
closes root SSH and adds the phone code.

**No key at the Git host for the desk or the servers.** The team's main
copy of the systems repository is on the team's own machines, and the
desk and `util01` reach it with the root SSH they already have. So the
person registers no deploy key, and a break-in at the Git host reaches no
server. The Git host keeps a backup that the laptop pushes with the
person's own login, and nothing reads from it.

**A console independent of SSH.** Recovery must work when SSH or
WireGuard fails.

**The default WireGuard network.** The desk's `wg0` must not replace a
provider network's routes.

**The first host key over WireGuard.** Only the new desk holds the
WireGuard private key matching the public key supplied before creation.

**One API proxy for both ports.** One program serves the provider's port
and Cloudflare's port, and never answers on a port without that port's
token.

**What the desk protects, and what it leaves.** The production key, the
vault and the person's tokens stay on the desk, and you use them without
copying them. While your shared login is open, any program on the laptop
could use the login too, as
[chapter 2's container rule](02_get_your_app_ready_to_deploy.md#before-you-start)
says. The login closes after one idle hour, and after ten hours at most.

Next, in the same reply, as the skill's "Now and next" rule says: [Chapter 4: Set up your accounts and lock your systems desk](04_set_up_your_accounts_and_lock_your_desk.md).
