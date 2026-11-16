# Chapter 2: Set up your laptop and your systems desk

**When:** after chapter 1 (pick your web address and start the team's
password manager). The domain's move to Cloudflare can still be "Pending".

**What this chapter does:** the laptop gets a key that reaches only the
person's systems desk, `desk01`, a small server at the server provider. The
desk gets the systems repository, the vault, the person's tokens, and the
coding agent's own account. At the end, the laptop holds none of the
temporary systems files.

**Who acts:** you, the coding agent, prepare the laptop and the desk: at
first as the laptop's agent, then on the desk as `coding-agent`. The person
approves each tool and the desk's price, makes the provider account and
the empty systems repository on websites, enrolls the phone code, and runs
the person-only commands in the person's own desk terminal.

**Tell the person when the chapter starts:**

> The systems desk is a small server of its own, separate from your laptop and from your production servers.
> Your systems desk is where you manage your system and run your systems coding agent.
> Your laptop keeps app development and a key
> that reaches only your desk. A phone code protects the desk login.
> Nothing copied off the laptop opens production.
> The desk runs outside production's location, so a production outage leaves
> your tools available.
>
> I will prepare the desk, then remove the temporary systems files from your laptop.

## Before you start

- **The messages to the person.** Each step says what to tell or ask the
  person, in quote blocks: "Tell the person first" before the step, "Ask
  the person" when the person must act or approve, and "Tell the person
  after" with the result and its link. Say each message when its step
  comes, in your own words, with the team's own names and links.
- **The laptop.** We say "laptop" throughout because most people use one. Any computer you develop on works the same way, such as a desktop or a Mac mini.
- **The temporary laptop setup.** The laptop briefly holds the template, MMX, doubleshell, and the person's provider token.
  No Python or additional language runtime is required on the laptop.
  "Recovery items and laptop cleanup" clears them at the end of the chapter.
- **Secrets.** The person enters secrets in the person's own terminal on the desk, never in the chat.
- **The chapter's parts.** Each part below numbers its own steps from 1,
  because the operating procedures cite them, such as "chapter 2's step 4"
  for step 4 of "Create desk01 through WireGuard".

## Prepare the laptop and provider account

1. **The company's name.** Name the separate systems repository `example_systems`: lowercase words with underscores, without the legal suffix, followed by `_systems`.
   The app repository stays where it is. The desk gets a read-only clone of it in
   chapter 3 (get your app ready to deploy), only to read the code.

   **Ask the person:**

   > What is your company's name, as your team writes the name, such as `Example Inc.`?

   **Tell the person after:**

   > Your systems repository will be called `example_systems`. It holds your servers' settings and the encrypted secrets, not your app's code.

   **Check:** you recorded the company's name and the repository's name.

2. **The laptop's tools.** Install the release of MMX pinned by `stack_software.mmx` in the installed skill's `systems_repository_template/mmx_project_settings.yml`.
   Follow [MMX installation](https://github.com/monkeymaxxing/mmx#install).
   `stack_software` in a released Stack version holds each program's release and SHA-256:
   `mmx`, `mmwatchdog`, `mmhotline`, and `set_up_outside_services`, which the desk's first run downloads.
   Never fill a pin by hand.
   Verify the archive against `SHA256SUMS` and keep the complete archive layout in `~/.cache/monkeymaxxing-stack/desk-bootstrap-tools/` and add that directory to the bootstrap shell's `PATH`.
   Install doubleshell following [doubleshell installation](https://github.com/monkeymaxxing/doubleshell/blob/main/README.md).
   The laptop also needs Git 2.34 or later, OpenSSH, Bash, jq, curl, and OpenSSL.
   Windows commands run inside WSL, with temporary files in the Linux home directory.

   **Tell the person first:**

   > Next, I install the tools that set up your systems desk from this laptop.
   > MMX applies your systems repository to a server. doubleshell carries your login to the desk through WireGuard, without a VPN on the laptop.
   > Git keeps your systems repository's history. The laptop holds MMX, doubleshell, and the template only until the desk is ready.

   **Ask the person:**

   > May I install MMX, doubleshell, and any of Git, OpenSSH, Bash, jq, curl, and OpenSSL that your laptop lacks?

   **Tell the person after:** no message, because step 3 starts the
   systems repository with the tools.

   **Check:** `mmx version`, `git --version`, `bash --version`, and `jq --version`.

3. **Copy the template.** `TEMPLATE_DIRECTORY` is `systems_repository_template/` beside the installed skill's `SKILL.md`.

   Replace `TEMPLATE_DIRECTORY` with that directory's path:

   ```sh
   mkdir -p ~/code
   cp -R TEMPLATE_DIRECTORY ~/code/example_systems
   cd ~/code/example_systems
   ```

   Set `project_name` in `mmx_project_settings.yml` to `example_systems`.
   Set `nightly_work_starts_at` and `maintenance_window` there to the answers recorded in chapter 1 (pick your web address and start the team's password manager); `weekly_work_day` keeps its default, `sunday`.
   Record the source commit as `stack_commit` in `monkeymaxxing_stack_checklist.yml` with
   `git -C TEMPLATE_DIRECTORY rev-parse HEAD` when the template belongs to a clone.
   When no source clone can be identified, remove `stack_commit` rather than recording a guessed commit.
   When chapter 1 (pick your web address and start the team's password manager) recorded the fuller system, set `trigger` of
   `staging_server` and `second_app_server` in `monkeymaxxing_stack_checklist.yml` to
   `chapter 7 (install everything on the production servers), step 10: the team chose the fuller system`.

   **Tell the person:** no message, because step 2 told the person that
   the laptop holds the template for a while.

   **Check:** `~/code/example_systems` holds the template, with
   `project_name` and the two times set.

4. **The server provider.** Read the selected [provider guide](../provider_guides/README.md).
   Offer Hetzner Cloud, DigitalOcean, OVHcloud, Vultr, Scaleway, AWS EC2, and Google Compute Engine.
   The coding agent reaches these providers at `http://127.0.0.1:8081/` on the desk without reading the
   person's credential: through the API proxy, which adds the person's token or, for a provider whose API
   needs each request signed or a token made from a key (OVHcloud, AWS EC2, Google Compute Engine), signs the request.
   The provider must offer first-boot data, hourly billing, and a console independent of SSH.
   The person creates the provider account and saves the login and recovery codes in the password manager.
   The person creates a personal provider token with permission to create, list, delete, and register SSH keys.
   At a provider the API proxy serves, the credential is the one the guide's "The person's credential"
   names: OVHcloud's three values from the guide's link, after the Public Cloud project; AWS's access key of an
   IAM user; Google Cloud's service account key file, after the project.
   Install the provider's tool temporarily on the laptop and verify the tool's list command.
   Keep the token outside Git, mode `0600`, in `~/.config/monkeymaxxing-stack/desk-bootstrap.env`.
   The person edits the token file in the person's own terminal:

   ```sh
   export SERVER_PROVIDER_API_TOKEN=''
   ```

   Record every temporary credential path for cleanup before continuing.

   **Ask the person:**

   > Which server provider do you want: Hetzner Cloud, DigitalOcean, OVHcloud, Vultr, Scaleway, AWS EC2, or Google Compute Engine?

   **Ask the person,** once the provider is chosen:

   > Please make your account at [the provider], and save the login and recovery codes in your password manager.
   > Then make a personal API token that can create, list, and delete servers and register SSH keys: [the guide's page].
   > Paste the token between the quotes in `~/.config/monkeymaxxing-stack/desk-bootstrap.env`, in your own terminal, never in this chat.
   > Tell me when the file is saved.

   **Tell the person after:**

   > Your token works: the provider lists the servers in your account, none yet.

   **Check:** the provider tool's list command, or
   `./server_management_scripts/list_the_servers_at_the_provider`,
   answers `{"servers": []}` for a new account.

5. **The locations and the desk.** Choose production's location now. Choose a different location for `desk01`.
   Use Debian 13 on x86-64, by default with 2 vCPUs and 4 GB of memory, the size of `db01` in
   [chapter 6 (create your three production servers: app, database, and tools)](06_create_your_three_production_servers.md): enough for the coding agent, MMX, and Rex.
   Check the provider's attached private networks before keeping `vars.wireguard_network: 10.20.0.0/16`.
   Preserve `desk01.address: 127.0.0.1` for self-management after bootstrap.

   **Ask the person:**

   > Your production servers go in [production's location], near most of your users. Your desk, `desk01`, goes in [the desk's location], so a production outage leaves your tools available.
   > `desk01` is Debian 13 with 2 vCPUs and 4 GB of memory. It costs [the hourly price] an hour, about [the monthly price] a month, plus [the public-address charge] for its public address.
   > Do you approve creating `desk01`?

   **Tell the person after:** no message, because "Create desk01 through
   WireGuard" creates the desk and tells the person.

   **Check:** the person approved the desk's price, and
   `vars.wireguard_network` overlaps no provider network.

6. **The systems repository at a Git host.** The systems repository needs a Git host: a website that stores the repository's history and accepts
   pushes. Use the Git host that the app already uses. A team with none can use any Git host that offers private
   repositories and deploy keys, which are keys that open one repository only.
   The person creates the empty private systems repository at the Git host, such as
   [GitHub's new repository page](https://github.com/new), with no README, and saves the Git-host login and
   recovery codes in the password manager.
   Set `systems_repository.ssh_url` in `mmx_project_settings.yml` to the new repository, and
   `git_host_ssh_known_hosts_lines` to the Git host's published SSH host keys, such as GitHub's page
   [GitHub's SSH key fingerprints](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints);
   never take them from `ssh-keyscan` alone.
   Set `systems_desk_provider_api_url` using the selected provider guide, including the trailing slash,
   and `systems_desk_provider_api_authentication` to the guide's value: `token_in_a_header`, or
   `ovhcloud_signed_requests`, `aws_signed_requests` or `google_cloud_service_account_tokens`.
   Remove the example `util01` key from `root_ssh_public_keys` until chapter 7 (install everything on the production servers) registers the real key.

   **Tell the person first:**

   > Git records every change to your systems repository. A commit is a saved change in Git history, and a push uploads commits to the Git host.
   > Your Git host keeps a copy of the systems repository, such as at GitHub.

   **Ask the person:**

   > Please create an empty private repository called `example_systems` at your Git host, with no README: [GitHub's new repository page](https://github.com/new).
   > Save the Git host's login and recovery codes in your password manager.
   > Tell me the repository's SSH address, such as `git@github.com:OWNER/example_systems.git`.

   **Tell the person after:** no message, because step 1 of "Finish the
   systems repository on the desk" pushes the first commit there.

   **Check:** `systems_repository.ssh_url`, `git_host_ssh_known_hosts_lines`,
   `systems_desk_provider_api_url`, and
   `systems_desk_provider_api_authentication` hold the team's values.

## Create desk01 through WireGuard

In every command from here on, replace `alex` with `desk01.vars.person_unix_username` and `example_systems`
with the repository's name, including paths inside quoted SSH commands.

1. **The laptop's keys.** Create a separate laptop SSH key with `ssh-keygen -t ed25519 -f ~/.ssh/desk01`.
   Leave the laptop key's passphrase empty. The phone code supplies the second factor.
   Never reuse the app's Git key or a production key for desk login.
   Run `doubleshell create-wireguard-key`. The command saves
   `~/.config/doubleshell/wireguard_private_key` and prints the public key.
   In `inventories/servers.yml`, set `desk01.vars.person_unix_username` to the person's Unix login, such as `alex`.
   Replace `desk01.vars.allowed_laptops` with the laptop's `laptop_name`,
   printed `wireguard_public_key`, `private_ip: 10.20.10.1`, and `ssh_public_key` from `~/.ssh/desk01.pub`.
   Additional laptops take unused addresses from `vars.private_ip_ranges.systems_desk_laptops`.

   **Ask the person:**

   > Your desk login needs your Unix username on the desk. What username do you want, such as `alex`?

   **Tell the person after:** no message, because step 2 creates the desk
   with the keys.

   **Check:** `~/.ssh/desk01.pub` and `~/.config/doubleshell/wireguard_private_key`
   exist, and `desk01.vars.allowed_laptops` holds the laptop.

2. **Create the desk.** Run the following block once, as one command: your shell keeps no variables from one command to the next.
   The block creates the desk's WireGuard pair in shell memory with `doubleshell create-server-wireguard-key`,
   renders the first-boot data through `server_management_scripts/render_server_first_boot`, prints the
   desk's public key, and never prints the private key.
   Save the printed public key in `desk01.vars.wireguard_public_key`:

   ```sh
   set +x
   umask 077
   desk_keys=$(doubleshell create-server-wireguard-key)
   # On the laptop, in the temporary systems repository.
   # LAPTOP_WIREGUARD_PUBLIC_KEY: the public key that create-wireguard-key printed in step 1.
   laptop_public_key='LAPTOP_WIREGUARD_PUBLIC_KEY'
   printf '%s' "$desk_keys" | jq --arg laptop_public_key "$laptop_public_key" \
     '{private_key, private_ip:"10.20.9.1", peers:[{public_key:$laptop_public_key, allowed_ips:["10.20.10.1/32"]}]}' |
     ./server_management_scripts/render_server_first_boot > /tmp/desk01-first-boot.yml
   printf 'desk01 WireGuard public key: %s\n' "$(printf '%s' "$desk_keys" | jq -r .public_key)"
   ```

   The desk's only first-boot peer is the laptop, without an endpoint.
   Register `~/.ssh/desk01.pub` with the provider and include the registered key on the create request.
   Use the provider guide's create command with `/tmp/desk01-first-boot.yml` as first-boot data.
   Public SSH stays closed from first boot. Record the returned public address as `desk01.vars.public_ipv4_address`.
   Clear the private first-boot file immediately after provider acceptance, including failed requests:

   ```sh
   : > /tmp/desk01-first-boot.yml
   ```

   **Tell the person after:**

   > Your desk, `desk01`, now runs at your provider: [the provider's server page].
   > Public SSH is closed from its first boot. Your laptop reaches the desk only through WireGuard.

   **Check:** the provider lists `desk01`, `desk01.vars.public_ipv4_address`
   holds its address, and `/tmp/desk01-first-boot.yml` is empty.

3. **The laptop's way in.** Write `~/.config/doubleshell/desk01.conf` with the following block. The file holds no secret: it has no
   `PrivateKey` line, so doubleshell reads the laptop's private key from `~/.config/doubleshell/wireguard_private_key`.
   Replace the desk's public key and the documentation public address with the actual values:

   ```sh
   # On the laptop:
   desk_public_key='DESK_WIREGUARD_PUBLIC_KEY'
   desk_public_address='203.0.113.91'
   printf '[Interface]\nAddress = 10.20.10.1/32\n\n[Peer]\nPublicKey = %s\nEndpoint = %s:443\nAllowedIPs = 10.20.9.1/32\n' \
     "$desk_public_key" "$desk_public_address" > ~/.config/doubleshell/desk01.conf
   ```

   The wg-quick format is read by doubleshell. No laptop VPN interface or service starts.
   Add the desk-only SSH entry to `~/.ssh/config`:

   ```sshconfig
   Host desk01
     HostName 10.20.9.1
     User alex
     IdentityFile ~/.ssh/desk01
     IdentitiesOnly yes
     ForwardAgent no
     UserKnownHostsFile ~/.ssh/desk01_known_hosts
     StrictHostKeyChecking yes
     ProxyCommand doubleshell --wireguard-config ~/.config/doubleshell/desk01.conf proxy-ssh %h %p
   ```

   Replace `alex` with `desk01.vars.person_unix_username`.
   Enroll the first SSH host key through the authenticated WireGuard route:

   ```sh
   ssh -o StrictHostKeyChecking=accept-new root@desk01 true
   ```

   Copy the observed host key into the repository's `ssh/known_hosts` under `desk01` and `10.20.9.1`.
   The laptop's file may hold the line hashed, as Debian's SSH settings write it, so read it with `ssh-keygen -F`:

   ```sh
   # On the laptop, in the temporary systems repository:
   ssh-keygen -F 10.20.9.1 -f ~/.ssh/desk01_known_hosts |
     awk '!/^#/ { print "desk01", $2, $3; print "10.20.9.1", $2, $3 }' >> ssh/known_hosts
   ```

   **Tell the person:** no message, because the person does nothing in
   this step and step 4 says what comes next.

   **Check:** `ssh -o StrictHostKeyChecking=accept-new root@desk01 true`
   exits 0, and `ssh/known_hosts` holds `desk01`'s lines.

4. **Copy the repository and bootstrap the desk.** Copy the finished repository to the desk, then run the bootstrap. Everything the desk keeps is written
   before the copy: the settings of step 3 and step 6 of "Prepare the laptop and provider account", and
   `desk01.vars` (`person`, `allowed_laptops`, `wireguard_public_key`, `public_ipv4_address`, `private_ip`),
   `desk01`'s lines in `ssh/known_hosts`, with `desk01.address: 127.0.0.1` and the template's `ssh/desk01`
   unchanged. The desk's production key is the only value the desk adds later, because the bootstrap run makes it there.
   The provider image does not yet have the `alex` account, so root writes the copy, and the bootstrap run
   makes it the person's own:

   ```sh
   # On the laptop, in the temporary systems repository:
   # COPYFILE_DISABLE=1 stops a Mac's tar from adding ._ metadata files; Linux ignores it.
   # --warning=no-unknown-keyword keeps the desk's tar quiet about a Mac's file labels, which it skips anyway.
   COPYFILE_DISABLE=1 tar -C ~/code -cf - example_systems |
     ssh root@desk01 'mkdir -p /home/alex; tar --warning=no-unknown-keyword -C /home/alex -xf -'
   ```

   Then point only the laptop's own copy at the bootstrap connection. MMX reads how it connects from the
   inventory and `ssh/desk01`, not from `--var`, and the laptop's copy is cleared at the end of this chapter:
   set `desk01.address` to `10.20.9.1` and `desk01.ssh_identity_file` to the laptop key's absolute path; in
   `ssh/desk01`, keep `HostKeyAlias desk01`, replace `IdentityFile` with that absolute path, and add the
   desk-only `ProxyCommand` from the laptop's SSH entry. Then run:

   ```sh
   # On the laptop, in the temporary systems repository:
   mmx run systems_desk --var desk_name=desk01 --only-fleet-stages systems_desk --connection ssh_only
   ```

   Use the `systems_desk` stage alone because `util01` does not exist yet.
   The run installs the waiting security updates, which can take several minutes, and near its end it closes
   root SSH from the laptop: from then on only the person logs in.

   **Tell the person while waiting:**

   > The desk now installs its software and its waiting security updates. That takes several minutes.
   > You do not need to do anything. Near the end, the desk closes root SSH from the laptop, so from then on only you log in.

   **Tell the person after,** which of these the person sees, and what comes next:

   - The run finishes with the line "Log in as alex and run /usr/local/bin/set-up-the-phone-code to add your
     phone code. Until then, login needs only your allowed laptop key." Go on to step 5.
   - The run ends with an error, such as "node busy with job …" or a lost connection, while the desk carries
     on with the job by itself. Wait two minutes and run the same command again. "node busy" again means the
     desk is still at work, so wait once more.
   - The run ends with "unconfirmed; work may still be running" and "Permission denied (publickey)": the desk
     closed root SSH from the laptop before the run could read its last result, and the desk finishes the job
     by itself. Wait two minutes, then go on to step 5.
   - The command is refused at login ("Permission denied"), or the run stops with "The phone code is missing.
     Log in as alex and run /usr/local/bin/set-up-the-phone-code …": an earlier run finished on the desk by
     itself and got past everything the next steps need. Go on to step 5.

   For example:

   > Your desk is set up. Next, you add your phone code, so the desk login needs your laptop key and a code from your phone.

   **Check:** one of the four endings above. The first desk review, in "Finish the systems repository on the desk", runs the desk playbook again on the
   desk and finishes it. Verify the new person's login before treating the run as complete.

5. **The phone code.** The person runs `ssh desk01`, then `/usr/local/bin/set-up-the-phone-code` in the person's own desk terminal.
   Scan the QR code, save the printed secret in the password manager, and confirm a code from the phone.
   A wrong confirmation saves no enrollment. Until enrollment succeeds, the allowed laptop key alone admits the person.
   Finish enrollment immediately before continuing setup.
   Open a second `ssh desk01` connection and keep the first session open until login succeeds.

   **Ask the person:**

   > Please run `ssh desk01` in a laptop terminal, then `/usr/local/bin/set-up-the-phone-code` on the desk.
   > Scan the QR code with your authenticator app, save the printed secret in your password manager, and type a code from your phone.
   > Then open a second `ssh desk01` and log in with a fresh code. Keep the first session open until the second login works.
   > Tell me when the second login works.

   **Tell the person after,** in one sentence:

   > Each code works once, so after a failed login wait for your phone's next code, because five wrong codes within ten minutes lock your laptop out for five minutes.

   The numbers are the defaults (`wrong_codes_before_lockout` and `lockout_minutes` under `phone_code_lockout` in `mmx_project_settings.yml`,
   with the reasons beside them; the ten-minute window is fixed in the desk role).

   **Check:** the second `ssh desk01` login with a fresh phone code works.

   **Rex, on a Mac laptop.** The desk runs Rex, so terminal sessions keep
   running when the laptop sleeps or the connection drops. Scrolling works
   as on the laptop, with no special keys. Rex for Mac connects through the
   same SSH login: open the login with a forward of the desk's Rex socket,
   type one phone code, and keep that terminal open:

   ```sh
   # On the laptop:
   ssh -tt -o ExitOnForwardFailure=yes -o StreamLocalBindUnlink=yes \
     -L "$HOME/.rex-desk.sock:/run/rex-desk/server.sock" desk01
   ```

   Install Rex for Mac from [Rex installation](https://www.superlogical.com/rex/docs/installation).
   With that SSH login open, in Rex for Mac choose **Add a remote host**, choose the socket option,
   and enter the socket's full path, such as `/Users/alex/.rex-desk.sock`
   (Rex for Mac does not expand `$HOME`; `echo "$HOME/.rex-desk.sock"` in a Mac terminal prints the full path).
   The Rex command-line tool takes the same socket as `-S "unix://$HOME/.rex-desk.sock"`. Closing the
   SSH login ends Rex's connection, not the sessions on the desk: the next
   login, with a fresh code, finds them again. An update of Rex on the desk
   restarts Rex and ends its sessions.

   **Plain SSH on a Windows or Linux laptop.** Superlogical's Rex clients
   for Windows and Linux are not yet public
   ([Rex installation](https://www.superlogical.com/rex/docs/installation)),
   so those laptops use `ssh desk01` in a terminal; on Windows, the WSL
   terminal. Plain SSH is also the way in whenever Rex does not work.

## Finish the systems repository on the desk

The desk role installs MMX, Claude Code, Rex, and the MMHotline program, each at its pinned version.
The MMHotline program posts to the status page when `util01` is down; no MMHotline server runs on the desk.

All remaining systems commands run on the desk.
The desk holds a read-only clone of the app, so the coding agent can read what each release changes.
CI, not the desk, tests the app, builds the image, and pushes it. A team without CI tests and builds on the desk,
only inside a container, and the person signs the desk in to the registry to push.
The desk role installs Podman for that, and curl and jq for account setup.
Chapter 3 (get your app ready to deploy) prepares the clone, and the CI or no-CI path.
The laptop can keep app development and local app tests.

The bootstrap left a finished repository in the person's home, owned by the person. Three steps remain,
each the person's own, in the person's desk terminal.

1. **Finish the repository with one command.** Give the person the command with the person's name and
   email filled in, for the commit history:

   ```sh
   # On the desk, in the person's own terminal:
   cd ~/example_systems
   set-up-the-systems-repository --author-name "Alex Example" --author-email alex@example.com
   ```

   **Ask the person:**

   > Please run this command in your own desk terminal. It finishes your systems repository: it makes your vault, `secrets_vault.age`, the encrypted file for your production secrets, and pushes the first commit.
   > Only your account can do this, because only your account reaches your vault passphrase and production key.
   > The command stops twice: once for you to register a key at your Git host, and once for you to type `yes` to approve the desk review.
   > Tell me when the command ends.

   The command does, in order, and a rerun skips each part that is done:

   - writes this desk's production public key, `/etc/systems-desk/production_key.pub`, which the bootstrap run made,
     into `root_ssh_public_keys` in `mmx_project_settings.yml` and into `nodes.desk01.vars.production_ssh_public_key`,
     so the servers will let this desk in;
   - runs `git init`, signs every commit with the production key through the person's own agent socket,
     `/run/desk-ssh-agent/private.sock`, trusts only the Git host's verified keys, sets the author, and
     adds `origin` from `systems_repository.ssh_url`;
   - makes the vault passphrase, `~/.config/monkeymaxxing-stack/example_systems_mmx_vault_passphrase`, and the
     token file, `~/.config/monkeymaxxing-stack/example_systems.env`, both readable only by the person. Its first
     `mmx secrets set` creates the vault, `secrets_vault.age`, and saves the vault's own passphrase in it as
     `mmx_vault_passphrase` ([Why the vault holds its own passphrase](#secrets));
   - prints the production public key and the Git host's deploy-key page, and waits. The person registers
     the key there as a deploy key with write access (at GitHub: the repository's Settings, "Deploy keys",
     `https://github.com/OWNER/REPOSITORY/settings/keys`, Add deploy key, tick "Allow write access"), then
     presses Enter. Typing `stop` ends the command; a rerun continues there;
   - makes the first commit, checks that it is signed, and pushes `main`;
   - runs `review-and-apply-the-systems-desk-settings --only-fleet-stages systems_desk`. This first desk review has nothing to compare
     with, so it asks once; the person types `yes`. It installs the vault passphrase for the coding agent's
     button, root-owned, as `/etc/systems-desk/vault-passphrase`, and the lock-out button's reviewed copies;
   - runs `sudo set-up-coding-agent-repository`, which clones `main` into `/home/coding-agent/systems_repository`
     with signing, and gives that checkout the same author.

   `review-and-apply-the-systems-desk-settings` is how the person runs the desk playbook on the desk from now on.
   It runs the playbook as root, so it first compares what the run would do with the last run the person reviewed.
   When nothing changed, it runs at once. When something changed, it shows each change and runs only after the person types `yes`.
   The coding agent cannot answer for the person.

   **Tell the person after:**

   > Your systems repository is on your Git host, with its first signed commit: [the repository's page].
   > Your vault exists, and your coding agent has its own copy of the repository.

   **Check:** the Git host shows the first commit on `main`, signed, and
   `/home/coding-agent/systems_repository` exists.

2. **Bring the provider token to the desk.** The person runs, in the person's own desk terminal, in the
   systems repository, the selected provider guide's "Credentials on the systems desk" command, with the
   guide's server listing, such as `servers` for Hetzner Cloud:

   ```sh
   # On the desk, in the person's own terminal:
   . ~/.config/monkeymaxxing-stack/example_systems.env && set-up-outside-services personal-token server-provider --server-listing-path servers
   ```

   The command asks for the token at a hidden prompt. The person copies it from the laptop's temporary
   token file, `~/.config/monkeymaxxing-stack/desk-bootstrap.env`, opened in the person's own laptop
   terminal, and pastes it. At a provider the API proxy serves it asks for the values the guide
   names: OVHcloud's three and AWS's two, each at its own prompt, copied from its own line of that file, or
   Google Cloud's whole key file at one prompt.
   `set-up-outside-services` is the Stack's command for the account and secret work, installed by the desk role.
   It checks the token with the provider's server listing.
   Only a token that passed goes into the token file, as `SERVER_PROVIDER_API_TOKEN`, and into the
   API proxy's file, `/etc/systems-desk/provider-api-token.conf`, owned by root, mode `0600`.
   At a provider whose requests the proxy signs it goes into the proxy's credential file, `/etc/systems-desk/provider-api-signing-credential.json`,
   owned by root, mode `0600`, instead.
   The API proxy stays stopped until the Cloudflare token's file exists too, and then answers on `http://127.0.0.1:8081/` for the provider and `http://127.0.0.1:8082/` for Cloudflare:
   `set-up-outside-services cloudflare`, first in chapter 4 (sign up for the outside services the Stack uses), makes the person's desk token for Cloudflare, saves it the same way, and then starts the proxy.

   **Ask the person:**

   > Please run this command in your own desk terminal. It asks for your provider token at a hidden prompt.
   > Copy the token from `~/.config/monkeymaxxing-stack/desk-bootstrap.env` in your own laptop terminal, and paste it there.
   > The token is yours, so only your terminal shows it. Tell me what the command prints at the end.

   **Tell the person after:**

   > Your provider token is on the desk, checked with your provider. I use it through the desk's API proxy from chapter 4 on, without reading it.

   **Check:** the command reports the token as checked with the provider's
   server listing.

3. **Start the coding agent.** The person starts it, because the coding agent signs in with the person's
   own subscription or key: `start-the-coding-agent`. The command starts the coding agent that
   `systems_desk_coding_agent` in `mmx_project_settings.yml` names, `claude_code` or `codex`, as the
   `coding-agent` account in its checkout. To change it, the coding agent changes the setting and pushes,
   and the person runs a desk review.
   The coding agent always works as `coding-agent`. Another trusted coding agent may run in the same Unix account.
   Never start the systems coding agent in the person's account.

   **Tell the person first:**

   > Your systems coding agent works in its own account on the desk, `coding-agent`.
   > The coding agent can use production authority, but cannot copy your SSH key, your API tokens, or your phone secret.

   **Ask the person:**

   > Please run `start-the-coding-agent` in your desk terminal, and sign the coding agent in with your own subscription or key.
   > Tell me when it shows its prompt. We continue there.

   **Tell the person after:** no message, because the conversation
   continues in the coding agent on the desk.

   **Check:** the coding agent runs as `coding-agent` in
   `/home/coding-agent/systems_repository`.

From here on, the coding agent runs production MMX with its button and reaches the provider and
Cloudflare APIs through the desk's proxies, without reading tokens, as
[What this repository is](../AGENTS.md#what-this-repository-is) and
[Making a change](../AGENTS.md#making-a-change) say.
After chapter 7 (install everything on the production servers) configures `util01`, the person runs the full desk playbook:

```sh
review-and-apply-the-systems-desk-settings
```

The full playbook joins the desk to monitoring. One wrong code shows as an info alert.

## Update the desk's production peers

1. **Update the peers.** After a commit that adds, replaces, or removes a server, the coding agent pushes it and then runs, on its own desk:

   ```sh
   sudo -n update-this-desks-wireguard-peers
   ```

   The command fetches pushed `main`, reads the servers in `inventories/servers.yml`, and sets this desk's
   WireGuard peers to exactly those servers: it adds the new ones, changes the replaced ones, and removes the
   gone ones. It prints the commit it used and each peer it added, changed or removed, or "No change".
   The desk's laptops keep their peers, and open sessions keep working.

   Each other desk's coding agent runs the same command at the start of its session, and whenever SSH to a server times out.
   A server without a `wireguard_public_key` yet is left out. When the inventory gives a server a value a server must not have,
   such as a laptop's key or an address in the desks' or the laptops' block, the command names the server and the
   value and changes nothing; the coding agent corrects the inventory and pushes.

   **Tell the person:** no message, because the person does nothing.

   **Check:** use `ssh -F ssh/config root@10.20.1.1` from the coding checkout for `app001`.

Reason: `util01` never manages a person's desk, and a server change must not need the person. The command
runs as root, so it is the copy that the person's last desk review installed, and it takes only the inventory
from the Git host, checking each value. The desk review writes the same peers from pushed `main` before it
rewrites `/etc/wireguard/wg0.conf` and copies them into that file, so a desk review keeps them, and `wg0` loads
them again after a reboot.

## Check remaining example values

1. **Replace the example values.** Before chapter 7 (install everything on the production servers), replace every actual setting's example value, including zero software checksums,
   with the verified release values. Keep documentation examples and script usage examples.
   Run the search on the desk from the coding agent's checkout:

   ```sh
   grep -rnE 'example|203\.0\.113\.|0{40}' --exclude-dir=.git --exclude-dir=.mmx --exclude=AGENTS.md --exclude=triage_agent_rules.md --exclude=talking_with_the_team.md --exclude-dir=initial_setup --exclude-dir=operating_procedures .
   ```

   Replace `example_systems`, the app name `shop`, and `example.com` in the copied guide with the team's names.
   Keep documentation-only public addresses in `203.0.113.0/24` and private examples in `10.20.0.0/16`.
   Rewrite README links and verification text for the actual system. Keep untested claims marked as not checked.

   **Tell the person:** no message, because the values change only in the
   systems repository, and chapter 7 shows the result.

   **Check:** the search finds only documentation examples and script
   usage examples.

## Recovery items and laptop cleanup

The password manager must keep the phone-code secret, vault passphrase,
and the desk's Git-host login, plus two private files: the production SSH
key `/home/alex/.ssh/production_key` and the desk's WireGuard key
`/etc/wireguard/wg0.private_key`. The desk's SSH host keys are not kept:
a rebuilt desk makes new ones, and the laptop checks them over WireGuard,
whose key the password manager does keep.
The root-owned self-management key is local to the desk and can be generated again.
Also keep account logins, recovery codes, the shared root console password,
and `pgbackrest_repository_cipher_passphrase`.

1. **Save the recovery items.** The person runs, in the person's own desk terminal, in the systems repository:

   ```sh
   . ~/.config/monkeymaxxing-stack/example_systems.env && set-up-outside-services show-recovery-items
   ```

   The command walks through each item, one at a time: its entry's name in the
   password manager, why the team needs it, then its value, shown only in the
   person's terminal. After the person saves the entry, the command clears the
   screen before the next item. An item that does not exist yet, such as a
   backup passphrase before chapter 4 (sign up for the outside services the
   Stack uses), is listed as not made yet; the person runs the command again
   then. The command ends with three lines: the items saved now, the items
   skipped or left for later, and the items not made yet. The lines hold item
   names only, no values, so the person can paste them to you, and you record
   the result in `systems_desk_recovery_items_saved`. The coding agent never
   reads recovery keys.

   **Ask the person:**

   > Please run this command in your own desk terminal. It shows each key your team needs to recover the desk, one at a time.
   > Save each one in your password manager under the name it gives, then press Enter.
   > At the end it prints three lines of names, no values. Paste those three lines to me.

   **Tell the person after:**

   > The password manager holds the keys to production, so protect it with its own strong password and its two-step login.

   **Check:** the three lines, recorded in `systems_desk_recovery_items_saved`.

2. **Check before clearing the laptop.** Verify a fresh phone-code login, a signed push
   from `coding-agent`, and the person's successful loopback MMX run.
   Check that the recovery items are saved, and mark `systems_desk_recovery_items_saved` done only after the person has seen each item saved. Keep incomplete checks open in the checklist.

   **Tell the person:** no message, because step 3 tells the person the
   result.

   **Check:** each of the four checks above passed.

3. **Clear every temporary laptop copy** after those checks:

   - `/tmp/desk01-first-boot.yml`: `: > /tmp/desk01-first-boot.yml`.
   - `~/.config/monkeymaxxing-stack/desk-bootstrap.env`: `: > ~/.config/monkeymaxxing-stack/desk-bootstrap.env`.
   - Temporary provider CLI credential stores: follow the selected provider guide and clear every recorded path.
   - `~/code/example_systems`: remove the temporary template copy after checking the desk's pushed repository.
   - The temporary MMX directory: remove `mmx`, the node programs, `official_extra_modules/`, the downloaded archive, and `SHA256SUMS`.
   - Temporary shell values: `unset SERVER_PROVIDER_API_TOKEN desk_keys laptop_public_key desk_public_key desk_public_address` and close the bootstrap shell.

   The same cleanup as commands:

   ```sh
   # On the laptop, after all desk access and recovery checks have passed:
   unset SERVER_PROVIDER_API_TOKEN desk_keys laptop_public_key desk_public_key desk_public_address
   rm -rf -- "$HOME/code/example_systems" "$HOME/.cache/monkeymaxxing-stack/desk-bootstrap-tools"
   rm -f -- /tmp/desk01-first-boot.yml "$HOME/.config/monkeymaxxing-stack/desk-bootstrap.env"
   ```

   Keep `~/.config/doubleshell/wireguard_private_key`: it is the laptop's WireGuard key, which doubleshell reads for every
   desk login.

   The tools directory holds the temporary MMX executable, node programs,
   extra modules, archive, and checksum file.
   Remove the selected provider tool's recorded temporary credential files too; the scripts of OVHcloud's, AWS EC2's
   and Google Compute Engine's guides keep none, and a downloaded Google key file is deleted once pasted.
   The provider guides name the credential stores; never remove an app's unrelated credentials.
   If an archive was saved in Downloads instead, remove that archive and its checksum file separately.
   Check backups, synchronized folders, downloads, and trash for extra bootstrap copies.

   **Tell the person after,** the only cleanup confirmation of the setup:

   > Your laptop holds none of the temporary systems files any more: [the cleared files].
   > It keeps doubleshell, your desk key, and your desk login settings, and your app development tools.

   The laptop keeps doubleshell, `~/.ssh/desk01`, `~/.ssh/desk01.pub`,
   `~/.ssh/desk01_known_hosts`, the desk-only SSH entry, and `~/.config/doubleshell/desk01.conf`.
   The laptop can keep app development tools and credentials.
   The desk keeps the read-only app clone and its read-only deploy key from chapter 3 (get your app ready to deploy).
   A team with CI keeps no registry push credential on the desk. A team without CI keeps the registry publishing login that chapter 4 makes.
   Runtime files hold no secret and may stay: `~/.rex-desk.sock`, Rex's `~/.local/state/rex/`, and doubleshell's socket in `/tmp`.

   **Check:** confirm that the laptop holds none of the cleared files.

## Secrets

| Secret | Where the secret is stored | How to store the secret |
| --- | --- | --- |
| Every secret the servers use, listed below | The vault, `secrets_vault.age`, in the systems repository. Playbook key names come from `mmx secrets usage`, described below. MMHotline's key names come from the `.secrets` references in `mmhotline_settings.yml`. | `set-up-outside-services backblaze` and `cloudflare` for the keys they make at those companies, and `set-up-outside-services secrets` for every other one: it asks at hidden prompts for the keys only a website gives, makes the random ones, and commits and pushes the vault. One key at a time later, such as for a rotation, with `mmx secrets` (below) |
| The person's own tokens, which only the person uses on the desk: the server provider's API token, the desk's Cloudflare token, and their own R2 key for posting to the status page while `util01` is down | This desk's token file (below), and for the provider and Cloudflare tokens the API proxy's files | The provider's: `set-up-outside-services personal-token server-provider`, one hidden entry, checked with the provider, then written to every place that needs it. The two Cloudflare ones: `set-up-outside-services cloudflare` makes them, named after the person, and writes them to the same places |
| With `staging01`, staging's Access service token, used for staging checks and local app tests | The desk's token file, the laptop's app-test token file, and the team's password manager | `set-up-outside-services cloudflare` makes it and writes both values into the token file; `show-recovery-items` shows them for the password manager. Another person's desk enters them from the password manager with `set-up-outside-services personal-token staging-access` |
| Account logins and recovery codes, the shared root console password, a copy of the vault passphrase, and a copy of each backup passphrase | The team's password manager | The person saves each login, recovery code, or passphrase when the login, code, or passphrase is created |

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
- The signing secret of MMWatchdog's fleet hub on `util01`, for MMHotline, and the vault's own
  passphrase.

**The person's two files on the desk** live outside the systems repository, readable
only by the person's own user account, and are named after `project_name`
(here `example_systems`): the vault passphrase,
`~/.config/monkeymaxxing-stack/example_systems_mmx_vault_passphrase`, and the token file,
`~/.config/monkeymaxxing-stack/example_systems.env`. `set-up-the-systems-repository` makes both.
Nobody edits the token file by hand: `set-up-outside-services` writes each token into it
as the token's chapter makes the token.
The person copies the passphrase into the password manager with
`set-up-outside-services show-recovery-items`
([Recovery items and laptop cleanup](#recovery-items-and-laptop-cleanup)).
Never run a command that shows the passphrase yourself.

In the person's desk terminal, every command that needs the vault, provider, or
Cloudflare starts with `. ~/.config/monkeymaxxing-stack/example_systems.env &&`.
The coding agent uses the buttons instead of sourcing the person's token file.
Run person-only commands from the person's repository on the desk.
Another person copies the saved passphrase from the password manager into
the passphrase file on the person's systems desk.
Another person's systems desk uses that person's own tokens, and, with
`staging01`, staging's Access service token from the password manager.

**Into the vault during setup:** `set-up-outside-services secrets`, in the
person's own terminal, in the systems repository, saves every key the
servers read that the vault lacks and that no other command makes. For a
key that only a website gives, it says what the key is for, gives the page
where the person makes it, and asks at a hidden prompt; Enter alone leaves
it for a later run. For an app's secret from `secrets_from_vault`, it asks
whether the value comes from an outside service, such as an API key, or is
random, such as a secret key base. It makes the random keys itself, such as
the database passwords, the backup passphrases and the fleet hub's signing
secret, without showing them. It skips each key the vault has already;
`--replace KEY` enters one again. It refuses a repository with uncommitted
changes other than the vault or commits not pushed yet, pulls the team's `main`, and ends by
committing and pushing the vault, signed through the person's own socket.

```sh
# This systems desk, in the systems repository, in the person's own terminal:
. ~/.config/monkeymaxxing-stack/example_systems.env && set-up-outside-services secrets
```

**One key at a time later, such as for a rotation, by where the secret comes from.**
The person runs each command below in the person's own terminal, because
only the person's token file gives MMX the vault passphrase, then commits
and pushes `secrets_vault.age`:

- **MMX makes it,** such as an app's database password:

  ```sh
  # This systems desk, in the systems repository, in the person's own terminal:
  . ~/.config/monkeymaxxing-stack/example_systems.env && mmx secrets add-random shop_database_password
  ```

  `mmx secrets add-random` never replaces a value that exists.
- **The person holds the secret,** such as a token from a website.
  The person runs the following `mmx secrets set` command in the person's
  own terminal, in the systems repository.
  The person pastes the token at the hidden prompt from `mmx secrets set`.

  ```sh
  # This systems desk, in the systems repository, in the person's own terminal:
  . ~/.config/monkeymaxxing-stack/example_systems.env && mmx secrets set container_registry_read_only_token
  ```

- **A command supplies the secret,** such as a tunnel token from
  Cloudflare's API, or the vault's own passphrase from the passphrase file.
  First, load the token file, which sets `MMX_VAULT_PASSWORD_FILE`.
  A pipe cannot answer MMX's passphrase prompt, so MMX needs the passphrase
  file's path before receiving the secret.
  Then pipe the command's output into `mmx secrets set`.
  The secret never shows on the screen, on a command line, or to you.
  In the example below, `cat` reads the passphrase file and
  `mmx secrets set mmx_vault_passphrase` receives the passphrase:

  ```sh
  # This systems desk, in the systems repository, in the person's own terminal:
  . ~/.config/monkeymaxxing-stack/example_systems.env &&
    cat "$MMX_VAULT_PASSWORD_FILE" | mmx secrets set mmx_vault_passphrase
  ```

A key the vault has already is set again with `--replace`, such as after
`mmx secrets passwd`: `... | mmx secrets set mmx_vault_passphrase --replace`.
[Adding or removing a person](../operating_procedures/add_or_remove_a_team_member.md#adding-or-removing-a-person)
has the whole passphrase change.
An empty value is refused, so a command that failed and printed nothing
changes nothing. `mmx secrets list-keys` lists the keys and prints no
value; `mmx secrets usage` lists every key that the playbooks read, and
says `not defined` for each one the vault lacks; `mmx secrets diff-keys`
shows which keys an edit added or changed, before the person commits
`secrets_vault.age`. The coding agent runs `list-keys` and `usage`
through its button, on pushed `main`:

```sh
# This systems desk, in the systems repository, as the coding agent:
sudo -n -u servers-mmx run-mmx-on-the-servers secrets usage
```

**Why the vault holds its own passphrase,** as `mmx_vault_passphrase`:
`util01` needs the passphrase to open the vault for MMX runs on `util01`.
When setting up or rebuilding `util01`, MMX runs on the systems desk and opens
the vault with the desk's passphrase file.
MMX gives each server only the secrets the server needs from the vault.
So MMX gives `util01` the value of `mmx_vault_passphrase`, along with
`util01`'s remaining secrets.
Reading `mmx_vault_passphrase` needs the vault passphrase already, so
storing the passphrase inside the vault exposes nothing.

**A value comes out of the vault once:** the backup passphrase, which the
password manager must hold too, because without the backup passphrase the
backups cannot be read.
`set-up-outside-services show-recovery-items` opens `mmx secrets edit` at that
item, in the person's own terminal; the person copies
`pgbackrest_repository_cipher_passphrase`, then closes the editor without saving.
Never open the vault yourself.

## If something is different

- **A pin whose SHA-256 is all zeros** ("Prepare the laptop and provider
  account", step 2) means the skill was installed from a
  Stack checkout that is not a release: stop and tell the person to install a released Stack version.
  The desk's first run and every `every_server` run refuse such a pin before changing anything.
- **A provider whose guide gives the scripts whole** ("Prepare the laptop
  and provider account", step 4): every guide except Hetzner Cloud's. There is no tool to install: the coding
  agent writes the guide's five provider scripts into `server_management_scripts/` now, and the person runs
  `./server_management_scripts/list_the_servers_at_the_provider` in the person's own laptop terminal after
  loading the token file. The script sends its request, signs it, or makes its token, in the shell with
  `curl`, `jq` and the tools the guide names, and answers `{"servers": []}` for a new account.
- **A provider network overlaps `vars.wireguard_network`** ("Prepare the
  laptop and provider account", step 5): choose a free private /16 and update every inventory address together.
- **The systems repository at the Git host has commits** ("Finish the
  systems repository on the desk", step 1).
  `set-up-the-systems-repository` sees which kind of desk this is at the Git host. The steps above are for an empty repository
  there, the team's first desk. When the repository there has commits, as for a new team member's desk
  ([Add or remove a team member](../operating_procedures/add_or_remove_a_team_member.md)) or a rebuilt desk
  ([Rebuild a systems desk](../operating_procedures/rebuild_a_systems_desk.md)), the same command joins it:
  after the deploy key, it fetches `main` and, before anything from it is used, checks that it is this team's
  repository, that it lists this desk with this desk's production key, and that its newest commit is signed by
  a key in its `root_ssh_public_keys`. It names that commit and its signer, which the person compares with the
  commit the team member says they pushed. Then it makes the person's repository that commit, keeping any change
  of the bootstrap copy in `git stash`, asks for the team's vault passphrase from the password manager at a hidden
  prompt, keeps it only when it opens the vault, and goes on with the desk review and the coding agent's checkout.
- **A team that needs more protection, such as a bank** ("Recovery items
  and laptop cleanup", step 1), can add more to the password manager's
  protection.

## Why the chapter works this way

**Git 2.34 or later.** Git 2.34 is fixed: it is the first Git release that makes and checks commits signed with an SSH key,
which the systems repository's history uses.

**A console independent of SSH.** Reason: recovery must work when SSH or WireGuard fails.

**The default WireGuard network.** Reason: the desk's `wg0` must not replace a provider network's routes.

**The person makes the empty repository.** Reason: making a repository through the Git host's API needs a further personal token with more power than this one click.

**The first host key over WireGuard.** Reason: only the new desk holds the WireGuard private key matching the public key supplied before creation.

**The person reviews the desk playbook.** Reason: the coding agent pushes to `main`, and the desk playbook applies a pushed change as root,
beside the person's production key and phone-code secret.

**The person runs `set-up-the-systems-repository`.** Why the person runs this command: it makes the vault passphrase and the vault, and signs with the
production key, which only the person's account reaches; the coding agent's account never sees them.
The deploy key is a website step because the Git host's API would need a further personal token with
administration rights on the repository, which is more for the person to make than one paste.

**The person brings the provider token.** Why the person: the token is the person's own, and only the person's terminal
may show it.

**One API proxy for both ports.** Reason: one program serves both ports, and it never answers on a port without that port's token.

**What the desk protects, and what it leaves.** Malware controlling an open desk session can act through the session.
The desk protects stored personal keys from copying, but production authority remains available during authorized work.

Next: [Chapter 3: Get your app ready to deploy](03_get_your_app_ready_to_deploy.md).
