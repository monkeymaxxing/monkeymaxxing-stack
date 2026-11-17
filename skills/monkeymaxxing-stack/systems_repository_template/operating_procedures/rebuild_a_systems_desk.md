# Rebuild a systems desk

**When to use this page:** a person's systems desk is lost or cannot be
recovered.

**What this page does:** a replacement desk, under a new name and with the
lost desk's WireGuard identity and production key, takes the lost desk's
place, and then the lost desk is deleted at the provider.

**Who acts:**

- **The person** signs in at the provider's and Cloudflare's websites, copies keys from the password manager, and runs
  the desk steps that this page marks "in the person's own terminal".
  The person runs
  [Create the replacement desk from the laptop](#create-the-replacement-desk-from-the-laptop)'s
  step 8, because the person pastes a key there.
- **The laptop's coding agent** names the replacement in the laptop's
  clone of the systems repository (steps 4 to 6), then writes the laptop's
  connection and enrolls the replacement's host key (steps 11 and 12).
- **The replacement desk's coding agent** records the replacement in `main`
  and runs MMX (steps 17 to 19, and step 26). It also deletes the old desk
  (step 28).
- **Each other person** runs a desk review on their own desk (step 27).

**Terms:** this page uses the Stack's terms, such as systems desk, desk
review, phone code, token file, and link token.
[Technical terms](../talking_with_the_team.md#technical-terms) explains
each term.

**The examples** rebuild the lost desk `desk02`, at `10.20.9.2`, of the
person `blair`, whose laptop is at `10.20.10.2`, as `desk03`. Use the
inventory's real names and addresses.

## Before you start

- **The provider account, `util01`, and the password manager must remain
  reachable without the lost desk.** `util01` holds the team's main copy of
  the systems repository, and the replacement fetches `main` from it.
- **App and database servers keep running while the desk is
  unavailable.**
- **If `util01` also failed,** [post to the status page](post_to_the_status_page.md#when-the-desk-is-also-lost)
  before rebuilding production services.

**The order, in short:** the laptop prepares a replacement under a new name
with the lost desk's WireGuard identity, the bootstrap builds it, the
person restores the production key, the replacement's coding agent records
the replacement in `main`, and `set-up-the-systems-repository` makes the
person's repository that `main`.

## Tell the person before you start

Tell the person what they will do on websites and in the password manager:

- In the password manager, they copy the lost desk's WireGuard private key
  (step 8) and the production private key (step 15), and save the new
  phone-code secret (step 14). They paste the vault passphrase in step 21.
- At the provider's website or console, they may power off the old desk
  (step 7), and they confirm the old desk's ID before the coding agent
  deletes it (step 28).
- At Cloudflare's website, in step 24, they make one Cloudflare link
  token, in about a minute. `set-up-outside-services cloudflare` prints a
  link to Cloudflare's token form with everything filled in. The person
  selects Continue to summary, then Create Token, and pastes the token at
  the command's hidden prompt. The link token can only make tokens. With
  it, the command makes the rebuilt desk's own Cloudflare token and
  status-page posting key, and deletes the lost desk's tokens, which have
  the same names. The command deletes the link token when it ends.

## Create the replacement desk from the laptop

1. **Use the laptop's clone** of the lost desk's repository,
   `~/code/example_systems`. It is a starting copy only: the replacement
   fetches the team's `main` from `util01` in step 17.
   **Check:** the clone holds the systems repository's files, such as
   `inventories/servers.yml`.
2. **Only when the laptop has no clone, clone the backup at the Git host**
   into `~/code/example_systems`, with the person's own Git login, from
   `systems_repository.backup_url_at_the_git_host`. First show the person
   the Git host's push activity, as "The main copy and the backup at the
   Git host" in [`AGENTS.md`](../AGENTS.md#the-main-copy-and-the-backup-at-the-git-host) says.
   **Check:** every push in the activity came from the person's own
   laptop login, and the clone holds `inventories/servers.yml`.
3. **Prepare the temporary tools and provider access:** follow
   [chapter 3 (make your server account and your systems desk)](../initial_setup/03_make_your_server_account_and_your_systems_desk.md)'s
   "Prepare the laptop and provider account".
   In chapter 3's commands from here on, use `desk03` in place of
   `desk01`, `10.20.9.2` in place of `10.20.9.1`, and the laptop's own
   address, `10.20.10.2`, in place of `10.20.10.1`.
   **Check:** the checks in chapter 3's "Prepare the laptop and provider
   account".
4. **The laptop's coding agent renames the lost desk's entry** in
   `inventories/servers.yml` from `desk02` to `desk03`, in `nodes` and in
   `groups.systems_desks.nodes`. The coding agent:
   - keeps `private_ip`, `wireguard_public_key`, `person_unix_username`,
     `production_ssh_public_key` and the connection lines (`address: 127.0.0.1`,
     `ssh_user`, `connection`, `ssh_identity_file`, `ssh_known_hosts`);
   - sets `ssh_config: ssh/desk03`;
   - puts the laptop's current login SSH and WireGuard public keys under
     `allowed_laptops`.

   Never add the replacement beside the lost desk's entry.
   Reason: production servers already trust that WireGuard key at that
   address, so the replacement reaches production with no production
   change. Two entries with one key would break every server's WireGuard
   settings.
   The replacement's address does not match the name's number, `desk03`
   at `10.20.9.2`. That is expected.
   Preserve the existing production configuration and every other
   person's desk.
   **Check:** step 18's diff, which lists the files this page changes.
5. **The laptop's coding agent changes the key comment** `blair on desk02`
   to `blair on desk03`, in that `production_ssh_public_key` and in
   `root_ssh_public_keys` in `mmx_project_settings.yml`. The key itself
   stays.
   **Check:** step 18's diff.
6. **The laptop's coding agent renames the lost desk's SSH settings and
   drops its host-key lines:**

   ```sh
   # On the laptop, in the clone:
   git mv ssh/desk02 ssh/desk03
   sed -i.old 's/HostKeyAlias desk02/HostKeyAlias desk03/; s/belongs to desk02/belongs to desk03/' ssh/desk03 && rm ssh/desk03.old
   grep -v -e '^desk02 ' -e '^10\.20\.9\.2 ' ssh/known_hosts > ssh/known_hosts.new && mv ssh/known_hosts.new ssh/known_hosts
   ```

   Reason for a new name: the replacement makes new SSH host keys, and
   the laptop's `~/.ssh/desk02_known_hosts` and the repository's
   `ssh/known_hosts` held the lost desk's keys under `desk02`. Under a new
   name the new keys get their own entries, and a host-key warning for
   `desk02` keeps meaning what it should: a machine that is not that desk.
   **Check:** step 18's diff shows `ssh/desk02` renamed to `ssh/desk03`.
7. **Power off an accessible old desk** at the provider's website or
   console.
   Reason: two desks with one WireGuard identity must never run at the
   same time.
   Skip this step when a fresh provider listing no longer shows the old
   desk. [Find the old desk at the provider](#find-the-old-desk-at-the-provider)
   says how to tell the old desk in the listing.
   **Check:** the provider shows the old desk powered off: in the provider
   listing, the old desk's `power_state` is `stopped`.
8. **Render the first-boot data with the lost desk's WireGuard identity.**
   The person runs this block once, as one command, on the laptop, in the
   clone. The block takes the lost desk's WireGuard private key from the
   password manager, which the person pastes at the hidden prompt, and
   renders the first-boot data with the laptop as the only peer:

   ```sh
   set +x
   umask 077
   # Paste desk02's WireGuard private key from the password manager, then press Enter. It does not show.
   read -rs desk_private_key
   # LAPTOP_WIREGUARD_PUBLIC_KEY: the laptop's wireguard_public_key under the desk's allowed_laptops.
   laptop_public_key='LAPTOP_WIREGUARD_PUBLIC_KEY'
   jq -n --arg private_key "$desk_private_key" --arg laptop_public_key "$laptop_public_key" \
     '{private_key:$private_key, private_ip:"10.20.9.2", peers:[{public_key:$laptop_public_key, allowed_ips:["10.20.10.2/32"]}]}' |
     ./server_management_scripts/render_server_first_boot > /tmp/desk03-first-boot.yml
   unset desk_private_key
   ```

   **Check:** the block prints no error, and `/tmp/desk03-first-boot.yml`
   holds the first-boot data for step 9.
9. **Create the replacement desk:** create Debian 13 with chapter 3's step 2, from
   `/tmp/desk03-first-boot.yml`, in a location different from production.
   Record the returned public address as `desk03.vars.public_ipv4_address`.
   **Check:** the provider returns the new desk's public address.
10. **Clear the first-boot file at once:**
    `: > /tmp/desk03-first-boot.yml`. As chapter 3 says, clear the file
    after a failed create request too.
    **Check:** none, because the command only empties the file.
11. **The laptop's coding agent writes the laptop's connection to the
    replacement:**
    `~/.config/doubleshell/desk03.conf` and the laptop's `Host desk03`
    entry, as chapter 3's step 3 does, with the lost desk's
    `wireguard_public_key`, the new public address, and
    `UserKnownHostsFile ~/.ssh/desk03_known_hosts`.
    **Check:** step 12's first command connects.
12. **The laptop's coding agent enrolls the replacement's host key over
    WireGuard, before the bootstrap.** On the laptop, in the clone:

    ```sh
    ssh -o StrictHostKeyChecking=accept-new root@desk03 true
    ssh-keygen -F 10.20.9.2 -f ~/.ssh/desk03_known_hosts |
      awk '!/^#/ { print "desk03", $2, $3; print "10.20.9.2", $2, $3 }' >> ssh/known_hosts
    ```

    `ssh-keygen -F` finds the line also when the laptop's SSH settings
    hash host names, as Debian's do.
    Reason: only the machine that holds the restored WireGuard private key
    answers at that address on that route, so the key seen there is the
    replacement's. The bootstrap's `ssh/desk03` then pins the key. Keep
    strict host checking on.
    **Check:** the `ssh` command ends without an error, and
    `ssh/known_hosts` ends with two new lines, one for `desk03` and one for
    `10.20.9.2`.

## Set up the replacement desk

13. **Bootstrap:** run chapter 3's step 4 with `desk_name=desk03`.
    **Check:** chapter 3's step 4 lists how the bootstrap run can end and
    what to do for each ending.
14. **Set up the phone code,** as chapter 3's step 5 says: the person logs
    in with `ssh desk03`, runs `set-up-the-phone-code`, and saves the
    confirmed secret in the password manager.
    **Check:** `set-up-the-phone-code` says "Your phone code is ready.",
    and a second `ssh desk03` with a fresh code works.
15. **The person restores the production key**, in their own desk
    terminal on `desk03`:

    ```sh
    install -m 0600 /dev/null ~/.ssh/production_key
    # Paste the production private key from the password manager, save, and close the editor.
    nano ~/.ssh/production_key
    ssh-keygen -y -f ~/.ssh/production_key > ~/.ssh/production_key.pub
    sudo install -o root -g root -m 0644 ~/.ssh/production_key.pub /etc/systems-desk/production_key.pub
    sudo systemctl restart desk-ssh-agent desk-ssh-agent-relay
    sudo set-up-coding-agent-repository
    start-the-coding-agent
    ```

    Reason: the bootstrap made a temporary production key. The agent must
    hold the restored key, which the servers and `util01`'s main copy
    already let in as the lost desk's. `/etc/systems-desk/production_key.pub` names that
    key for Git, signing and the coding agent's buttons. The next desk
    review writes the same file from the restored key.
    The person performs these restorations in the person's own terminal.
    The coding agent never reads the key.
    **Check:** `SSH_AUTH_SOCK=/run/desk-ssh-agent/private.sock ssh-add -l`,
    run as the person, lists one key, with the fingerprint that
    `ssh-keygen -l -f /etc/systems-desk/production_key.pub` prints. The
    restarted `desk-ssh-agent` loads `~/.ssh/production_key`.
16. **The person writes the bootstrap copy's changes to a file** the coding
    agent can read, in their own desk terminal. The bootstrap copy in the
    person's repository holds the changes of steps 4 to 6 and step 12,
    which hold only public keys and addresses:

    ```sh
    git -C ~/example_systems diff HEAD > /tmp/desk03-rebuild.patch && chmod 0644 /tmp/desk03-rebuild.patch
    ```

    **Check:** step 18's `git apply` reads the file.
17. **The replacement's coding agent updates the desk's peers, then
    fetches `main` from `util01`:** in its checkout, it runs
    `sudo -n update-this-desks-wireguard-peers`, which gives the desk its
    server peers, `util01` included, from the checkout. Then it makes the
    main copy on `util01` the checkout's `origin` and brings `main` to it:

    ```sh
    # coding-agent, in /home/coding-agent/systems_repository:
    git remote add origin root@10.20.0.1:/var/lib/systems_repository.git
    git fetch origin && git reset --hard origin/main && git branch --set-upstream-to=origin/main main
    sudo -n update-this-desks-wireguard-peers
    ```

    `util01` lets the desk in because the restored production key is in
    `root_ssh_public_keys`, and the desk trusts `util01`'s host key from
    `ssh/known_hosts`. The reset drops the laptop copy's files; step 18
    applies the rebuild's changes again from the patch.
    **Check:** each peers command prints the commit it used and each peer
    it added, changed or removed, or "No change", and `git status` says
    `main` is up to date with `origin/main`.
18. **The coding agent sets its Git author to the person's name and email,
    applies the changes, and checks them:**

    ```sh
    # coding-agent, in /home/coding-agent/systems_repository:
    git config user.name "Blair Example" && git config user.email blair@example.com
    git apply --3way /tmp/desk03-rebuild.patch
    mmx validate
    git diff --stat HEAD
    ```

    **Check:** the diff shows `inventories/servers.yml`,
    `mmx_project_settings.yml`, `ssh/known_hosts`, and `ssh/desk02`
    renamed to `ssh/desk03`. The coding agent tells the person anything
    else before committing. When `git apply` reports a conflict, `main`
    changed the same lines since the laptop's clone: the coding agent
    makes the change of steps 4 to 6 in that file by hand.
19. **The coding agent commits, synchronizes and pushes the changes** to
    the main copy on `util01`, as
    [Making a change](../AGENTS.md#making-a-change) says. The coding agent
    tells the person the pushed commit's full ID.
    Reason: `set-up-the-systems-repository` takes the team's `main` only
    when it lists this desk with this desk's production key, and the
    commit, signed by the restored key, is the one the person then
    compares.
    **Check:** the push succeeds, as step 4 of Making a change says.
20. **The person makes their repository the team's `main`**, in their own
    desk terminal:

    ```sh
    cd ~/example_systems
    set-up-the-systems-repository --author-name "Blair Example" --author-email blair@example.com
    ```

    The command sees that the main copy on `util01` has commits, so it
    joins it, as
    [chapter 3's "Finish the systems repository on the desk"](../initial_setup/03_make_your_server_account_and_your_systems_desk.md#create-desk01-through-wireguard)
    describes. It keeps the laptop copy's edits in `git stash`.
    **Check:** the command names `main`'s newest commit and its signer,
    `blair on desk03`. The person compares the commit with step 19's ID.
    If the two differ, the person presses Enter at the desk review's
    question, which applies nothing, and asks why.
21. **The person pastes the vault passphrase** from the password manager
    at the command's hidden prompt.
    **Check:** the command says the passphrase opens the vault. If the
    command says "That passphrase does not open the vault", copy the
    passphrase again from the password manager and run
    `set-up-the-systems-repository` again.
22. **The person approves the first desk review,** which the command runs.
    A rebuilt desk has no desk review yet, so the desk review asks once
    without changes to show. The record of the lost desk's last desk review was only on
    the lost desk. Before typing `yes`, run `git log` on `main` since a date
    the person remembers, and read each commit that the desk playbook would
    apply.
    **Check:** the command goes on to the coding agent's checkout and ends
    without "Stopped:".
23. **The person brings the provider token to the desk,** as chapter 3's
    "Bring the provider token to the desk" says.
    **Check:** `set-up-outside-services` checks the token with the
    provider's server listing, and saves only a token that passed.
24. **The person makes the desk's Cloudflare token and posting key:**
    `. ~/.config/monkeymaxxing-stack/example_systems.env && set-up-outside-services cloudflare`,
    in their own terminal, in the systems repository, with a link token
    made from the link it prints. The run makes the rebuilt desk's
    Cloudflare token and status-page posting key, writes the proxy's
    Cloudflare file and the token file, starts the proxy, and deletes the
    lost desk's tokens, which have the same names.
    **Check:** the run says "Deleted the earlier token" for each of the
    lost desk's tokens, and "Deleted the link token at Cloudflare." at its
    end. A deletion that failed says "Delete it by hand" with the link to
    Cloudflare's token page: delete the token there.
25. **Join the desk to monitoring:** once `util01` is available, the person
    runs `review-and-apply-the-systems-desk-settings`. While `util01` is
    down, go on with step 26, which has its own command for that case,
    and come back to step 25 once `util01` runs again. When `util01` is
    lost, rebuild `util01` from this desk with
    [Rebuild the utility server util01](rebuild_the_utility_server_util01.md).
    **Check:** the desk appears in the MMWatchdog fleet.
26. **The coding agent saves the replacement's endpoint on every server:**
    it runs `./server_management_scripts/run_mmx_on_util01 run every_server`,
    or `sudo -n -u servers-mmx run-mmx-on-the-servers run every_server --connection ssh_only`
    while `util01` is down, which saves the replacement's endpoint in
    every server's persistent peers.
    **Check:** the run ends without failed work, and the checks below pass.

    Verify:
    - a fresh phone-code login;
    - production SSH from `coding-agent`;
    - a signed commit and push from the person's repository;
    - the API proxy;
    - that `ssh-keygen -y -f ~/.ssh/production_key`, run as the person,
      prints the key in `/etc/systems-desk/production_key.pub`;
    - that the desk appears in the MMWatchdog fleet.

    The production key in `root_ssh_public_keys` stays the same; only its
    comment changed. A restored desk initiates WireGuard connections using
    the restored identity, so production needs no new login key.

## Update every other desk

27. **Every other desk runs a desk review.** Each other person runs, in
    their own desk terminal, in their systems repository:
    `review-and-apply-the-systems-desk-settings`.
    Reason: each desk's lock-out button uses the SSH settings files of
    that desk's last desk review. Until that desk's next desk review, the
    lock-out button refuses with "nodes.desk03.ssh_config in the inventory
    is ssh/desk03, which is not one of the SSH settings files of your last
    desk review … Nothing changed.". The same desk review also gives that
    desk's Git the rebuilt desk's signing key under its new name.
    **Check:** their coding agent tells them the change the desk review
    shows: the rebuilt desk's SSH settings file, `ssh/desk03`, and its
    comment in `root_ssh_public_keys`.

## Clean up and record

28. **Delete the old desk.** Verify the old desk's provider ID, as
    [Find the old desk at the provider](#find-the-old-desk-at-the-provider)
    says, and the person confirms the ID. Then the coding agent runs
    `./server_management_scripts/destroy_a_server_at_the_provider --server-id ID`
    with that ID, through the API proxy. Skip this step when a fresh provider listing no longer
    shows the old desk.
    **Check:** the ID is absent from a fresh provider listing.
29. **Remove the patch file and the kept edits on the desk,** in the
    person's own terminal: `/tmp/desk03-rebuild.patch` and the bootstrap
    copy's edits that step 20 kept, with `rm /tmp/desk03-rebuild.patch`
    and `git -C ~/example_systems stash drop`.
    **Check:** `git -C ~/example_systems stash list` no longer shows the
    entry "Changes before joining main at …" that step 20 made.
30. **Complete chapter 3's laptop cleanup,** including temporary
    provider-tool credential stores.
    **Check:** the checks in chapter 3's "Recovery items and laptop
    cleanup".
31. **Record the recovery in `systems_desk_recovery`,** in the checklist,
    `monkeymaxxing_stack_checklist.yml`.
    **Check:** none, because the record is the last step.

## If something is different

- **If the old desk cannot be powered off** in step 7, stop until the old
  desk is off. Reason: two desks with one WireGuard identity must never run
  at the same time.
- **If `set-up-the-systems-repository` says that `main` "does not list this
  desk, desk03, with this desk's production key yet",** step 19's commit
  is not pushed yet. Push the commit, then run the command again. Nothing
  from `main` was used.

## Find the old desk at the provider

The inventory records no provider ID for a systems desk, so read the ID
from the provider listing. The listing gives each server's `id`, `name`,
`public_ipv4_address` and `power_state`. The old desk is the server with
the lost desk's `public_ipv4_address`, which `inventories/servers.yml`
held under `desk02` before this rebuild.

## How the rebuild restores the desk

The password manager restores production identities. MMX restores desk
software and settings. The root-only self-management key is generated
again on the replacement desk and never enters the coding agent's socket.
