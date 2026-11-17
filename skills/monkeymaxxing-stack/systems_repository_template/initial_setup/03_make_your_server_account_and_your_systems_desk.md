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

**Who acts:** the person makes the provider account and types the key
into one short command on the laptop. You do everything else: the
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

   **Ask the person:** the screen below, first and whole in your reply's
   text, with the guide's own website steps. At OVHcloud, steps 4 and 5
   become the guide's prefilled createToken link, and the command asks
   for the three values.

   ```text
   Account 1 of 4: Hetzner (your servers)

   What this is for:
     Hetzner runs your servers.  I build them with a key you make there.

   Do this now:
     1. Open  https://accounts.hetzner.com/signUp  and make an account.
     2. Save the login in 1Password.
     3. Turn on two-step sign-in, which Hetzner calls  Two-factor authentication (2FA):
          https://accounts.hetzner.com/tfa
     4. Open  https://console.hetzner.com  and press  New project.  Name it  Example.
     5. In the project, open  Security,  then  API tokens.
        Press  Generate API token.  Name it  example-desk.  Choose  Read & Write.

   Then open a terminal on this laptop and type:

     ~/example-setup/enter-the-hetzner-key

   It asks for the key, checks it with Hetzner, and keeps it for me.
   Then leave that window open. It shows when your desk is ready, about
   10 minutes later, and goes on to the next questions by itself.
   I carry on by myself meanwhile.
   ```

   Then, in the same turn, wait for the key file. Give the command the
   longest time your agent allows a command, 10 minutes in Claude Code:

   ```sh
   # On the laptop. Waits up to 9 minutes for the key file.
   for i in $(seq 108); do [ -f ~/example-setup/provider-key ] && break; sleep 5; done
   ls -l ~/example-setup/provider-key
   ```

   Reason for 9 minutes: the loop ends by itself before Claude Code's
   10-minute limit stops the command, so you get a clear answer, and a
   question the person types meanwhile waits 9 minutes at most.
   When the file is there, carry on without being told. When the limit
   passed, say in one line that you are still waiting and that the person
   can type anything here when the key command is done, and end the
   reply. At the person's next message, look for the file, and wait again
   when it is not there yet. Never print the file. An agent that does
   not show its text before a command ends its reply with the screen and
   "When it says  Hetzner accepted the key,  tell me "done" here."
   The key command stays open after that on purpose: chapter 4 step 2
   tells it when the desk is ready.

   **Check:** `~/example-setup/provider-key` exists, mode `0600`.

2. **The backup repository at the Git host.** The team's main copy of
   the systems repository lives on the team's own machines: the desk's
   checkout first, then `util01` from chapter 7. The Git host keeps a
   private backup copy, which you push from the laptop with the person's
   own login ("The main copy and the backup at the Git host" in
   [`AGENTS.md`](../AGENTS.md#the-main-copy-and-the-backup-at-the-git-host)). Make an empty
   private repository, `example_systems`, at the app's Git host and owner
   from chapter 2. With `gh` signed in:

   ```sh
   # On the laptop:
   gh repo create OWNER/example_systems --private
   ```

   Without `gh`, show one screen with the Git host's new-repository link,
   already filled in:

   ```text
   One more page: a private backup of your systems repository at GitHub.

   Do this now:
     1. Open  https://github.com/new?owner=OWNER&name=example_systems&visibility=private
     2. Press  Create repository.
   ```

   Set `systems_repository.backup_url_at_the_git_host` in
   `mmx_project_settings.yml`, such as
   `https://github.com/OWNER/example_systems.git`. No key of the desk or
   of a server goes to the Git host. Remove the example `util01` key from
   `root_ssh_public_keys` until chapter 7 registers the real key.

   **Tell the person:** no message with `gh`. You made the repository.

   **Check:** `gh repo view OWNER/example_systems --json visibility` says
   `PRIVATE`. Without `gh`, the first backup push in chapter 4 checks the
   repository.

3. **The provider scripts and the locations.** Write the provider scripts
   into `server_management_scripts/` of the laptop's copy, from the guide
   and the
   [provider script contract](../server_management_scripts/README.md#write-the-teams-provider-scripts).
   At Hetzner Cloud, install `hcloud` on the laptop for now, as the
   guide says, with the key only in the environment, so no saved
   `hcloud` context remains. Check the key with the list script:

   ```sh
   # On the laptop, in ~/code/example_systems:
   SERVER_PROVIDER_API_TOKEN="$(cat ~/example-setup/provider-key)" ./server_management_scripts/list_the_servers_at_the_provider
   ```

   A new account answers `{"servers": []}`.
   Choose `desk01`'s location: the provider location chapter 1 picked for
   the desk, different from production's. Use Debian 13 on x86-64, by
   default with 2 vCPUs and 4 GB of memory. Check the provider's attached
   private networks before keeping `vars.wireguard_network: 10.20.0.0/16`.
   Keep `desk01.address: 127.0.0.1` for the desk's own runs after the
   bootstrap.

   **Tell the person:** no message. The person approved the desk's price
   with "go" in chapter 1.

   **Check:** the list script answers, and `vars.wireguard_network`
   overlaps no provider network.

4. **The settings that chapter 4 reads.** `set-up-outside-services go-live`
   in chapter 4 reads these settings from the systems repository, so write
   them now, in `mmx_project_settings.yml`:

   - `vars.backups`: Backblaze's S3 endpoint and region for the region
     nearest the servers, such as `s3.eu-central-003.backblazeb2.com` and
     `eu-central-003` for servers in Europe, and the buckets' names,
     `production_bucket`, `uploads_bucket` when an app keeps uploads, and
     MMHotline's bucket in `mmhotline_backup_replica_url`, such as
     `s3://example-mmhotline-backup/mmhotline?endpoint=https://s3.eu-central-003.backblazeb2.com&region=eu-central-003`.
     Bucket names are unique across all of Backblaze, so use the company's
     name in them. The three backup lengths keep the template's values,
     each written out there with its reason.
   - For each app that keeps uploads, `production_uploads_r2_bucket` and
     `production_uploads_r2_key_variables`, and
     `backups.uploads_backup_runs_on: [util_server]`. With no app that
     keeps uploads, `backups.uploads_backup_runs_on: []`.

   **Tell the person:** no message.

   **Check:** `mmx validate` passes.

## Create desk01 through WireGuard

In every command from here on, replace `alex` with
`desk01.vars.person_unix_username` and `example_systems` with the
repository's name, including paths inside quoted SSH commands.

1. **The laptop's keys.** Create a separate laptop SSH key with
   `ssh-keygen -t ed25519 -N '' -f ~/.ssh/desk01`. Leave the key's
   passphrase empty: the phone code supplies the second factor. Never
   reuse the app's Git key or a production key for desk login.
   Run `doubleshell create-wireguard-key`. The command saves
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

2. **Create the desk.** Run the following block once, as one command:
   your shell keeps no variables from one command to the next. The block
   creates the desk's WireGuard pair in shell memory with
   `doubleshell create-server-wireguard-key`, renders the first-boot data
   through `server_management_scripts/render_server_first_boot`, prints
   the desk's public key, and never prints the private key.
   Save the printed public key in `desk01.vars.wireguard_public_key`:

   ```sh
   set +x
   umask 077
   desk_keys=$(doubleshell create-server-wireguard-key)
   # On the laptop, in ~/code/example_systems.
   # LAPTOP_WIREGUARD_PUBLIC_KEY: the public key that create-wireguard-key printed in step 1.
   laptop_public_key='LAPTOP_WIREGUARD_PUBLIC_KEY'
   printf '%s' "$desk_keys" | jq --arg laptop_public_key "$laptop_public_key" \
     '{private_key, private_ip:"10.20.9.1", peers:[{public_key:$laptop_public_key, allowed_ips:["10.20.10.1/32"]}]}' |
     ./server_management_scripts/render_server_first_boot > /tmp/desk01-first-boot.yml
   printf 'desk01 WireGuard public key: %s\n' "$(printf '%s' "$desk_keys" | jq -r .public_key)"
   ```

   The desk's only first-boot peer is the laptop, without an endpoint.
   Register `~/.ssh/desk01.pub` with the provider and include the
   registered key on the create request. Use the provider guide's create
   command, with `SERVER_PROVIDER_API_TOKEN` read from
   `~/example-setup/provider-key` in the same command, and
   `/tmp/desk01-first-boot.yml` as first-boot data. Public SSH stays
   closed from first boot. Record the returned public address as
   `desk01.vars.public_ipv4_address`. Clear the private first-boot file at
   once after the provider accepts or refuses the request:

   ```sh
   : > /tmp/desk01-first-boot.yml
   ```

   **Tell the person,** once the provider accepted the request:

   ```text
   I am building your desk now.  It takes about 10 minutes.

   You have nothing to do until then.  I tell you when it is ready.
   ```

   **Check:** the provider lists `desk01`, `desk01.vars.public_ipv4_address`
   holds its address, and `/tmp/desk01-first-boot.yml` is empty.

3. **The laptop's way in.** Write `~/.config/doubleshell/desk01.conf`
   with the following block. The file holds no secret: it has no
   `PrivateKey` line, so doubleshell reads the laptop's private key from
   `~/.config/doubleshell/wireguard_private_key`. Replace the desk's
   public key and the documentation public address with the actual
   values:

   ```sh
   # On the laptop:
   desk_public_key='DESK_WIREGUARD_PUBLIC_KEY'
   desk_public_address='203.0.113.91'
   printf '[Interface]\nAddress = 10.20.10.1/32\n\n[Peer]\nPublicKey = %s\nEndpoint = %s:443\nAllowedIPs = 10.20.9.1/32\n' \
     "$desk_public_key" "$desk_public_address" > ~/.config/doubleshell/desk01.conf
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
     ProxyCommand doubleshell --wireguard-config ~/.config/doubleshell/desk01.conf proxy-ssh %h %p

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

   `desk01` is the person's own login. `desk01-agent` is your login, as
   `coding-agent`: one shared connection that later commands reuse. The
   other three each start one command for the person: `desk01-setup` in
   chapter 4, `desk01-secrets` for a key the vault still lacks, such as
   Pushover's in the alerts sitting, and `desk01-review` for a desk
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
   # On the laptop, in ~/code/example_systems:
   ssh-keygen -F 10.20.9.1 -f ~/.ssh/desk01_known_hosts |
     awk '!/^#/ { print "desk01", $2, $3; print "10.20.9.1", $2, $3 }' >> ssh/known_hosts
   ```

   **Tell the person:** no message, because the person does nothing.

   **Check:** `ssh -o StrictHostKeyChecking=accept-new root@desk01 true`
   exits 0, and `ssh/known_hosts` holds `desk01`'s lines.

4. **Copy the repository and run the bootstrap.** Commit every setting of
   chapters 1 to 3 in the laptop's copy first. The bootstrap is the
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
   # On the laptop, in ~/code/example_systems:
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
   mmx run systems_desk --var desk_name=desk01 --only-fleet-stages systems_desk --connection ssh_only
   ```

   The `systems_desk` stage runs alone because `util01` does not exist
   yet. The run installs the waiting security updates, which take several
   minutes. Root SSH from the laptop stays open until the lock in
   chapter 4.

   Right after the run, move the provider key to the desk's API proxy,
   over the same root login, on standard input, and delete the laptop
   file. MMX keeps every laptop file a run reads in the run's history, so
   the bootstrap cannot do this itself. The person does nothing. Use the
   provider guide's server listing path, here Hetzner Cloud's `servers`:

   ```sh
   # On the laptop, in ~/code/example_systems:
   ssh -F ssh/desk01 root@10.20.9.1 set-up-outside-services write-api-token-proxy-file \
     --api server-provider --server-listing-path servers < ~/example-setup/provider-key \
     && rm ~/example-setup/provider-key
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

   **Tell the person while waiting:** nothing more. The screen of step 2
   said how long the build takes. When the build runs past 15 minutes,
   say in one line what the run is doing now and that the person still
   has nothing to do.

   **Tell the person after:** chapter 4's first screen.

   The run's normal end prints `The desk is ready.` and the production
   public key. When the run ends with an error such as
   "node busy with job …" or a lost connection, the desk carries on with
   the job by itself. Wait two minutes and run the same command again.
   "node busy" again means the desk is still at work, so wait once more.

   **Check:** the run printed `The desk is ready.`, the key's move
   succeeded and the laptop file `~/example-setup/provider-key` is gone,
   and `ssh desk01-agent true` logs in as `coding-agent` with no code.

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

   Each other desk's coding agent runs the same command at the start of
   its session, and whenever SSH to a server times out. A server without a
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
   on the production servers), replace every actual setting's example
   value, including zero software checksums, with the verified release
   values. Keep documentation examples and script usage examples. Run the
   search in the laptop's clone of the systems repository:

   ```sh
   grep -rnE 'example|203\.0\.113\.|0{40}' --exclude-dir=.git --exclude-dir=.mmx --exclude=AGENTS.md --exclude=triage_agent_rules.md --exclude=talking_with_the_team.md --exclude-dir=initial_setup --exclude-dir=operating_procedures .
   ```

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
| Every secret the servers use, listed below | The vault, `secrets_vault.age`, in the systems repository. Playbook key names come from `mmx secrets usage`. MMHotline's key names come from the `.secrets` references in `mmhotline_settings.yml` | In the first sitting, `set-up-outside-services go-live` (`ssh desk01-setup`): it asks for each key a website gives, makes every random one without a question, and commits and pushes the vault. Later, `set-up-outside-services secrets` (`ssh desk01-secrets`) asks for each key the vault still lacks. `--replace KEY` enters one key again, such as for a rotation: `ssh -t desk01 set-up-outside-services secrets --replace KEY` |
| The person's own tokens: the provider credential, the desk's Cloudflare token, and the R2 key for posting to the status page while `util01` is down | The provider credential: only the API proxy's root-only file. The Cloudflare token: the API proxy's root-only file and the person's own token file on the desk. The R2 key: the person's own token file | The provider credential: the laptop key command of chapter 3, which you move to the desk right after the bootstrap. The Cloudflare tokens: `go-live` makes them |
| The recovery bundle: the vault passphrase, the production private key, the desk's WireGuard private key, the shared root console password, the phone code's emergency codes, the provider, Cloudflare and Backblaze credentials, and a copy of the backups' passphrase and read-only Backblaze key | `recovery_bundle.age` in the systems repository, and a copy in the locked backup bucket at Backblaze, encrypted with the recovery passphrase | `go-live` makes it at the lock in chapter 4 |
| The recovery passphrase, and every account's login and recovery codes | The team's password manager | The person saves each one when it is made |

The secrets that servers use are:

- The shared root console password's hash, `shared_root_console_password_hash`.
- The tunnel tokens and the registry token.
- The apps' secrets and database passwords, and the failover monitor's
  logins.
- The backups' B2 keys and passphrases, and MMHotline's backup keys.
- `util01`'s R2 key that reads the apps' uploads, and `util01`'s B2 key
  that copies the uploads.
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

- **A provider whose guide gives the scripts whole** ("The provider
  account", step 3): every guide except Hetzner Cloud's. There is no tool
  to install: the scripts send each request, sign it, or make its token,
  in the shell with `curl`, `jq` and the tools the guide names.
- **A provider that needs a project first,** such as OVHcloud or Google
  Cloud: the guide's steps go into the account screen, and the project's
  ID is not a secret. Read the ID with the provider's API once the key
  works, or from the page the guide names, and never ask the person to
  copy it when the key can read it.
- **A provider network overlaps `vars.wireguard_network`** ("The provider
  account", step 3): choose a free private /16 and update every inventory
  address together.
- **The team's systems repository already exists on `util01`** ("Create
  desk01 through WireGuard", step 4), as for a new team member's desk
  ([Add or remove a team member](../operating_procedures/add_or_remove_a_team_member.md))
  or a rebuilt desk
  ([Rebuild a systems desk](../operating_procedures/rebuild_a_systems_desk.md)):
  follow that operating procedure.
- **No stock at the desk's location:** follow the provider guide. At
  OVHcloud, the guide makes a Public Cloud desk until stock returns.

## Why the chapter works this way

**The provider key is typed on the laptop, once.** The desk does not exist
yet, and the desk is built with the key. The key sits in a `0600` laptop
file for about ten minutes, then moves to the desk and is deleted.

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

**Git 2.34 or later.** Git 2.34 is fixed: it is the first Git release that
makes and checks commits signed with an SSH key, which the systems
repository's history uses.

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

Next: [Chapter 4: Set up your accounts and lock your desk](04_set_up_your_accounts_and_lock_your_desk.md).
