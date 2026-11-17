# Rebuild a systems desk

**When to use this page:** the person's systems desk is lost or cannot be
recovered.

**What this page does:** a new desk takes the lost desk's place. It gets
the lost desk's WireGuard identity and production key back from the
recovery bundle, so every server lets it in with no change. Then the lost
desk is deleted at the provider.

**Which desk this page rebuilds:** the desk whose keys are in the recovery
bundle, `recovery_bundle.age`. That is the desk that ran chapter 4 (set up
your accounts and lock your systems desk), usually `desk01`, and any desk this page
rebuilt from it. A desk added later for a teammate has its own keys, which
the bundle does not hold. A teammate's lost desk is replaced with
[Add or remove a team member](add_or_remove_a_team_member.md): remove the
lost desk ("Leaving", steps 2 and 3), then add a new desk ("Joining").

**Who acts:**

- **The person** runs the commands that send three items from the recovery
  bundle straight to the new desk, unseen, makes one Cloudflare key, scans a new QR code, and
  confirms the old desk's ID at the provider.
- **The coding agent,** on the person's laptop, does everything else.

**Terms:** this page uses the Stack's terms, such as systems desk,
recovery bundle, phone code, desk review and link token.
[Technical terms](../talking_with_the_team.md#technical-terms) explains
each term.

**The examples** rebuild the lost desk `desk01`, at `10.20.9.1`, of the
person `alex`, whose laptop is at `10.20.10.1`, as `desk02`. Use the
inventory's real names and addresses, and the next unused desk name.

## Before you start

- **`util01` holds the team's main copy** of the systems repository. The
  new desk fetches `main` from it. When `util01` is lost too, rebuild the
  desk first, then follow
  [Rebuild the utility server util01](rebuild_the_utility_server_util01.md),
  and [post to the status page](post_to_the_status_page.md#when-the-desk-is-also-lost)
  first.
- **The servers keep running** while the desk is missing.
- **The person needs the recovery passphrase,** in the team's password
  manager, and a login to the provider's and Cloudflare's websites.

## Tell the person before you start

> Your desk is lost, so I build a new one, `desk02`, and give it your old desk's keys back. Your servers keep running.
> You do five small things: open your recovery bundle with your recovery passphrase, paste three items from it,
> make one Cloudflare key, scan a new QR code with your phone, and confirm the old desk's number at Hetzner.
> I tell you each one when it comes.

## Prepare on the laptop

1. **Use the laptop's clone,** `~/code/example_systems`. It is a starting
   copy only. The new desk fetches `main` from `util01` later, in step 15.
   **Check:** the clone holds `inventories/servers.yml`.
2. **Only when the laptop has no clone,** clone the backup at the Git host
   into `~/code/example_systems`, with the person's own Git login. First
   show the person the Git host's push activity, as
   ["The main copy and the backup at the Git host"](../AGENTS.md#the-main-copy-and-the-backup-at-the-git-host)
   says.
   **Check:** every push came from the person's own laptop login.

   EVERY PUSH MUST BE THE PERSON'S OWN. ANY OTHER PUSH IS A BREAK-IN.

3. **Get the provider key and the laptop tools ready,** as
   [chapter 3's "The provider account"](../initial_setup/03_make_your_server_account_and_your_systems_desk.md#the-provider-account)
   step 1 and step 3 say, with the provider's existing account and project.
   The person makes a new key there and types it into
   `~/example-setup/enter-the-hetzner-key`.
   **Check:** `~/example-setup/provider-key` exists, mode `0600`, and the
   list script answers.
4. **Rename the lost desk's entry** in `inventories/servers.yml`, from
   `desk01` to `desk02`, in `nodes` and in `groups.systems_desks.nodes`.
   - Keep `private_ip`, `wireguard_public_key`, `person_unix_username`,
     `production_ssh_public_key` and the connection lines
     (`address: 127.0.0.1`, `ssh_user`, `connection`, `ssh_identity_file`,
     `ssh_known_hosts`).
   - Set `ssh_config: ssh/desk02`.
   - Keep the laptop under `allowed_laptops`.

   NEVER ADD THE NEW DESK BESIDE THE LOST DESK'S ENTRY.

   Reason: the servers already trust that WireGuard key at that address,
   so the new desk reaches them with no server change. Two entries with
   one key would break every server's WireGuard settings.
   **Check:** step 7's diff.
5. **Change the key's comment** from `alex on desk01` to `alex on desk02`,
   in `production_ssh_public_key` and in `root_ssh_public_keys` in
   `mmx_project_settings.yml`. The key itself stays.
   **Check:** step 7's diff.
6. **Rename the SSH settings and drop the old host-key lines:**

   ```sh
   # On the laptop, in ~/code/example_systems:
   git mv ssh/desk01 ssh/desk02
   sed -i.old 's/HostKeyAlias desk01/HostKeyAlias desk02/; s/belongs to desk01/belongs to desk02/' ssh/desk02 && rm ssh/desk02.old
   grep -v -e '^desk01 ' -e '^10\.20\.9\.1 ' ssh/known_hosts > ssh/known_hosts.new && mv ssh/known_hosts.new ssh/known_hosts
   ```

   Reason for a new name: the new desk makes new SSH host keys. Under a
   new name they get their own entries, and a host-key warning for
   `desk01` keeps meaning what it should: a machine that is not that desk.
   **Check:** `git status` shows `ssh/desk01` renamed to `ssh/desk02`.
7. **Commit the rename on a branch,** `rebuild-desk02`:

   ```sh
   # On the laptop, in ~/code/example_systems:
   git switch -c rebuild-desk02
   git add inventories/servers.yml mmx_project_settings.yml ssh/desk01 ssh/desk02 ssh/known_hosts
   git commit -m "Rebuild desk01 as desk02 with the same keys"
   git show --stat HEAD
   ```

   **Check:** the commit changes only `inventories/servers.yml`,
   `mmx_project_settings.yml`, `ssh/known_hosts`, and the rename of
   `ssh/desk01` to `ssh/desk02`.

## Create the new desk

8. **Power off the old desk,** when the provider still lists it. The
   person does this at the provider's website, or you do it through the
   provider script with the person's yes.
   [Find the old desk at the provider](#find-the-old-desk-at-the-provider)
   says how to tell which server it is.

   TWO DESKS WITH ONE WIREGUARD KEY MUST NEVER RUN AT THE SAME TIME.

   **Check:** the listing shows the old desk's `power_state` as `stopped`,
   or no longer lists it.
9. **The person gives the new desk the lost desk's WireGuard key.** First the person
   loads `bundle_item`, as
   [Read an item from the recovery bundle](#read-an-item-from-the-recovery-bundle)
   says. Then the person runs this block in the same laptop terminal, as one
   command. It asks for the recovery passphrase, and shows no key:

   ```sh
   set +x
   umask 077
   desk_private_key=$(bundle_item desk_wireguard_private_key)
   # LAPTOP_WIREGUARD_PUBLIC_KEY: the laptop's wireguard_public_key under the desk's allowed_laptops.
   laptop_public_key='LAPTOP_WIREGUARD_PUBLIC_KEY'
   jq -n --arg private_key "$desk_private_key" --arg laptop_public_key "$laptop_public_key" \
     '{private_key:$private_key, private_ip:"10.20.9.1", peers:[{public_key:$laptop_public_key, allowed_ips:["10.20.10.1/32"]}]}' |
     ./server_management_scripts/render_server_first_boot > /tmp/desk02-first-boot.yml
   unset desk_private_key
   ```

   **Check:** the block prints no error, and `/tmp/desk02-first-boot.yml`
   is not empty.
10. **Create the new desk,** as
    [chapter 3's "Create desk01 through WireGuard"](../initial_setup/03_make_your_server_account_and_your_systems_desk.md#create-desk01-through-wireguard)
    step 2 says, from `/tmp/desk02-first-boot.yml`, in a location
    different from production. Skip that step's key block: the first-boot
    file is ready. Clear the file at once, also after a refused request:
    `: > /tmp/desk02-first-boot.yml`.
    Record the new public address as `desk02.vars.public_ipv4_address`
    and the returned `id` as `desk02.vars.provider_server_id` (at OVHcloud
    and Google Cloud, also the receipt's service or instance name as
    `desk02.vars.provider_server_name`), and commit them on the branch.
    **Check:** the provider lists `desk02`, `desk02.vars.provider_server_id`
    holds its ID, and the first-boot file is empty.
11. **Write the laptop's way in,** as chapter 3's step 3 says, with
    `desk02` in place of `desk01` in every name: `desk02.conf`, the SSH
    entries `desk02`, `desk02-agent`, `desk02-setup`,
    `desk02-secrets` and `desk02-review`, and
    `~/.ssh/desk02_known_hosts`. Use the lost desk's
    `wireguard_public_key` and the new public address. Delete the
    `desk01` entries and `~/.ssh/desk01_known_hosts`. Then enroll the new
    host key, and add its lines to `ssh/known_hosts`, as step 3 does, and
    commit them on the branch.
    **Check:** `ssh -o StrictHostKeyChecking=accept-new root@desk02 true`
    exits 0.

## Set up the new desk

12. **Copy the clone to the desk, with its history.** Unlike chapter 3,
    keep `.git`: the copy's commits tell the bootstrap that this desk
    joins the team's repository, so it starts no new one.

    ```sh
    # On the laptop, in ~/code/example_systems:
    COPYFILE_DISABLE=1 tar --exclude=./.mmx -cf - . |
      ssh root@desk02 'mkdir -p /home/coding-agent/systems_repository && tar --warning=no-unknown-keyword -C /home/coding-agent/systems_repository -xf -'
    ```

    Then point the laptop's copy at the bootstrap connection, as chapter
    3's step 4 says, without committing it, and run the bootstrap:

    ```sh
    # On the laptop, in ~/code/example_systems:
    ~/.local/bin/mmx run systems_desk --var desk_name=desk02 --only-fleet-stages systems_desk --connection ssh_only
    ```

    **Check:** the run stops at `start_the_systems_repository`, saying
    that a desk that joins a team's repository gets the vault passphrase
    from the recovery bundle. That stop is expected: step 13 gives it.
13. **The person gives the desk its production key and the vault
    passphrase,** from the recovery bundle. Tell the person:

    > I'll give you a few commands for your laptop terminal, then a few for the desk.
    > Each laptop command asks for your recovery passphrase. Nothing secret shows on screen.

    The person runs every line of
    [Give a desk its keys from the recovery bundle](#give-a-desk-its-keys-from-the-recovery-bundle).
    **Check:** the checks of that section.
14. **Run the bootstrap again,** the same command as step 12. Then move
    the provider key to the desk's API proxy, and delete the laptop file,
    as chapter 3's step 4 says.
    **Check:** the run prints `The desk is ready.` and a production public
    key equal to `production_ssh_public_key` in the inventory, apart from
    the comment. `ssh desk02-agent true` logs in as `coding-agent`.
15. **Join the team's `main`, on the desk.** Run these as the coding
    agent, through `ssh desk02-agent`:

    ```sh
    # This systems desk, as the coding agent, in ~/systems_repository:
    sudo -n update-this-desks-wireguard-peers
    git switch main
    git remote remove origin 2>/dev/null  # the laptop clone's origin, copied in step 12
    git remote add origin root@10.20.0.1:/var/lib/systems_repository.git
    git fetch origin && git reset --hard origin/main && git branch --set-upstream-to=origin/main main
    sudo -n update-this-desks-wireguard-peers
    ```

    The first peers command gives the desk its server peers, `util01`
    included, from the copy. `util01` lets the desk in because the
    restored production key is in `root_ssh_public_keys`.
    **Check:** each peers command prints the commit it used and its
    peers, or "No change", and `git status` says `main` is up to date
    with `origin/main`.
16. **Publish the branch `rebuild-desk02`,** as
    [Making a change](../AGENTS.md#making-a-change) says. The branch is on
    the desk already, so skip the push to the desk:
    `ssh desk02-agent publish-branch-to-main rebuild-desk02`. On a conflict, `main`
    changed the same lines since the laptop's clone: tell the person, and
    make the change of steps 4 to 6 again on a new branch from `main`.
    **Check:** the publishing step names the commits it published.
17. **The person makes the desk's Cloudflare key.** Tell the person:

    > Please type `ssh -t desk02 set-up-outside-services cloudflare` in your terminal.
    > It prints a link. Open it, press  Review token,  then  Create token,  and paste the token.

    The command makes the new desk's Cloudflare token and status-page
    posting key, and deletes the lost desk's tokens, which have the same
    names. It deletes the link token when it ends.
    **Check:** the command says "Deleted the earlier token" for each of the
    lost desk's tokens, and "Deleted the link token at Cloudflare." at its
    end. A deletion that failed says "Delete it by hand", with the link:
    the person deletes the token there.
18. **Lock the desk.** First the person makes the new phone code. Tell the
    person:

    > Please type this in your terminal, and scan the QR code with your phone:
    >
    > `ssh -t desk02 'sudo -n set-up-the-phone-code --emergency-codes-to ~/phone-code-emergency-codes'`

    Then the person saves the new emergency codes in the recovery bundle,
    as [Change an item in the recovery bundle](#change-an-item-in-the-recovery-bundle)
    says, with `phone_code_emergency_codes` and the file
    `~/phone-code-emergency-codes`. Then you run the lock stage from the
    laptop, and clean up as chapter 4's step 8 says:

    ```sh
    # On the laptop, in ~/code/example_systems:
    ~/.local/bin/mmx run systems_desk --var desk_name=desk02 --only-fleet-stages lock --connection ssh_only
    ```

    Then move the laptop's copy aside, and clone the desk's checkout in its
    place, as chapter 4's step 1 says:
    `mv ~/code/example_systems ~/example-setup/desk_bootstrap_copy` and
    `git clone desk02-agent:systems_repository ~/code/example_systems`.
    **Check:** `set-up-the-phone-code` said "Your phone code is ready.",
    `ssh root@desk02 true` is refused, and `ssh desk02-agent true` still
    works.
19. **Save the new desk's place on every server:** run `every_server` on
    `util01`, as step 6 of
    [Making a change](../AGENTS.md#making-a-change) says. It saves the new
    desk's public address in every server's WireGuard peers. While
    `util01` is down, use the desk's own button:
    `sudo -n -u servers-mmx run-mmx-on-the-servers run every_server --connection ssh_only`.
    **Check:** the run ends without failed work.
20. **Join monitoring.** Once `util01` runs, the person types
    `ssh desk02-review` and a phone code. The desk review shows no change
    and applies the desk playbook, which adds the desk to MMWatchdog.
    **Check:** the desk appears in the MMWatchdog fleet.

**Verify the new desk:**

- A new `ssh desk02` login asks for a phone code, and a fresh code works.
- `ssh desk02-agent 'cd systems_repository && ssh -F ssh/config root@10.20.1.1 true'`
  reaches `app001`.
- The API proxy answers: the provider's list script through
  `http://127.0.0.1:8081/` lists the servers.
- `ssh-keygen -y -f ~/.ssh/production_key`, run by the person on the desk,
  prints the key in `/etc/systems-desk/production_key.pub`.
- The desk appears in the MMWatchdog fleet.

## Update every other desk

21. **Each teammate runs a desk review:** `ssh desk03-review` on their
    laptop, with their own desk name, and a phone code.
    Reason: each desk's lock-out button uses the SSH settings files of
    that desk's last desk review. Until then, that button refuses with
    "nodes.desk02.ssh_config in the inventory is ssh/desk02, which is not
    one of the SSH settings files of your last desk review … Nothing
    changed.".
    **Check:** each teammate's coding agent names the change the review
    shows: the new desk's SSH settings file, `ssh/desk02`, and its comment
    in `root_ssh_public_keys`.

## Clean up and record

22. **Delete the old desk.** Find its provider ID, as
    [Find the old desk at the provider](#find-the-old-desk-at-the-provider)
    says, and the person confirms the ID. Then run
    `./server_management_scripts/destroy_a_server_at_the_provider --server-id ID`
    on the desk, through the API proxy. Skip this step when the listing no
    longer shows the old desk.
    **Check:** a new listing no longer shows the ID.
23. **Clean the laptop,** as chapter 4's step 8 says:
    `rm -rf ~/example-setup`, and any saved login of the provider's tool.
    **Check:** `~/example-setup` is gone.
24. **Push the backup** at the Git host, as
    ["The main copy and the backup at the Git host"](../AGENTS.md#the-main-copy-and-the-backup-at-the-git-host)
    says.
    **Check:** `git ls-remote backup main` shows the same commit as
    `main` in the clone.
25. **Record the rebuild** in `systems_desk_recovery`, in
    `monkeymaxxing_stack_checklist.yml`, and publish it.
    **Check:** none, because the record is the last step.

## If something is different

- **The old desk cannot be powered off** in step 8: stop until it is off.
  Reason: two desks with one WireGuard key must never run at the same time.
- **The bootstrap does not stop in step 12, but starts a new repository:**
  the copy had no `.git`. Stop. Delete the new desk at the provider and
  start again at step 9.
- **The bootstrap's key in step 14 differs from the inventory's key:**
  step 13's first part did not take. Do that part again, then run the
  bootstrap again.

## Read an item from the recovery bundle

The recovery bundle, `recovery_bundle.age`, is in the systems repository.
The recovery passphrase opens it. The person uses it in their own laptop
terminal; you never see it.

First the person loads `bundle_item`, a small shell command, in their
laptop terminal:

```sh
# On the laptop, in your own terminal:
cd ~/code/example_systems
# MMX has no command that prints one value: this editor setting prints the one item and changes nothing.
# When MMX has a one-value command, such as `mmx secrets show`, use it here instead.
bundle_item() {
  EDITOR="awk -v key=$1 '\$0 ~ \"^\" key \":\" {on=1; v=substr(\$0, length(key)+3); if (v !~ /^[|]/) {gsub(/^\"|\"\$/, \"\", v); print v; on=0}; next} on && /^[^ ]/ {on=0} on {sub(/^  /, \"\"); print}'" \
    ~/.local/bin/mmx secrets edit --vault recovery_bundle.age | grep -v '^Saved encrypted vault: '
  git restore recovery_bundle.age
}
```

Then `bundle_item KEY` asks for the recovery passphrase and prints only
that item, such as `bundle_item phone_code_emergency_codes`. The steps
pipe most items straight where they go, so nothing secret shows.
`git restore` puts the bundle back: `mmx secrets edit` saves the file
again, even with no change. The person never sees the rest of the bundle
and never edits a file.

**Check:** the command printed one item, and `git status` shows no change
to `recovery_bundle.age`.

The bundle holds the vault passphrase (`mmx_vault_passphrase`), the
production private key (`production_ssh_private_key`), the desk's
WireGuard private key (`desk_wireguard_private_key`), the servers' shared
root console password, the phone code's emergency codes
(`phone_code_emergency_codes`), and the provider, Cloudflare and Backblaze
credentials. A copy is in the locked backup bucket at Backblaze. Use that
copy only when no clone of the systems repository is left.

## Give a desk its keys from the recovery bundle

The person sends each key from the bundle on the laptop straight into a
file on the desk. Nobody sees a key, and nobody edits a file.
Before the lock, `ssh desk02` needs no phone code.

**On the laptop,** in the person's own terminal, after loading
`bundle_item` as [Read an item from the recovery bundle](#read-an-item-from-the-recovery-bundle)
says. Each command asks for the recovery passphrase.

```sh
# On the laptop, in your own terminal:
# The production key: only for a rebuilt desk. A new teammate's desk keeps the key its bootstrap made.
bundle_item production_ssh_private_key | ssh desk02 'umask 077 && cat > ~/.ssh/production_key'
# The vault passphrase: for every desk.
bundle_item mmx_vault_passphrase | ssh desk02 'umask 077 && cat > ~/vault-passphrase'
```

**On the desk,** in the person's own terminal (`ssh desk02`):

```sh
# On the desk, as the person. The first three lines only for a rebuilt desk:
ssh-keygen -y -f ~/.ssh/production_key > ~/.ssh/production_key.pub
sudo install -o root -g root -m 0644 ~/.ssh/production_key.pub /etc/systems-desk/production_key.pub
sudo systemctl restart desk-ssh-agent desk-ssh-agent-relay
# For every desk:
cat ~/vault-passphrase | sudo install -o root -g servers-mmx -m 0640 /dev/stdin /etc/systems-desk/vault-passphrase
rm ~/vault-passphrase
```

**Check:** for a rebuilt desk, `ssh-keygen -l -f /etc/systems-desk/production_key.pub`
prints the fingerprint of the inventory's `production_ssh_public_key`.
For every desk, `sudo -n -u servers-mmx run-mmx-on-the-servers secrets list-keys`,
run by the coding agent after the bootstrap, lists key names and no error.

## Change an item in the recovery bundle

The person changes the bundle in their own desk login, `ssh desk02` and a
phone code, on a copy in a folder of their own. Then you publish the
changed file.

```sh
# On the desk, as the person. KEY: the item's name, such as phone_code_emergency_codes.
# FILE: the file that holds the new value, such as ~/phone-code-emergency-codes.
work=$(mktemp -d) && cd "$work"
cp /home/coding-agent/systems_repository/recovery_bundle.age .
# Type the recovery passphrase, then press Enter. It does not show.
read -rs MMX_VAULT_PASSWORD && export MMX_VAULT_PASSWORD
mmx secrets set --vault recovery_bundle.age --replace KEY < FILE
sudo install -o coding-agent -g coding-agent -m 0644 recovery_bundle.age /home/coding-agent/systems_repository/recovery_bundle.age
cd && rm -r "$work" FILE && unset MMX_VAULT_PASSWORD
```

Then commit `recovery_bundle.age` in the desk's checkout and publish it,
as [Making a change](../AGENTS.md#making-a-change) says.
The copy in the locked backup bucket keeps the older items. That is
fine: the copy in the systems repository is the current one.

**Check:** the publishing step names the commit, and
[Read an item from the recovery bundle](#read-an-item-from-the-recovery-bundle)
shows the new value.

## Find the old desk at the provider

The old desk's ID is the `provider_server_id` that `inventories/servers.yml`
held under `desk01` before this rebuild. Check it against the provider
listing, which gives each server's `id`, `name`, `public_ipv4_address` and
`power_state`: the old desk is the server with the lost desk's
`public_ipv4_address`. The new desk's API proxy refuses a request other than
GET that names the new desk's own ID, never the old desk's.

## How the rebuild restores the desk

The recovery bundle restores the desk's identities: its WireGuard key and
its production key. So the servers and `util01` let the new desk in as
before, and need no change. MMX restores the desk's software and settings.
The desk's root-only key for its own runs is made new on the new desk, and
never enters the coding agent's socket.
