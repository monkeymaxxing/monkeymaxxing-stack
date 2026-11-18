# Chapter 6: Create your three production servers: app, database, and tools

**When:** steps 1 to 5, which create the servers, run as soon as the
systems desk is ready, at the end of chapter 3
([Create the three production servers now](03_make_your_server_account_and_your_systems_desk.md#create-the-three-production-servers-now)),
so the approved sizes cannot sell out meanwhile. Steps 6 and 7 run after
chapter 5 (put your site behind Cloudflare and lock your private pages).

**What this chapter does:** the three production servers start at the
provider: `app001` runs the app, `db01` stores the app's data, and `util01`
runs the system tools. Each server's WireGuard key and SSH host key are
recorded in the systems repository before any connection. The person
approved the weekly restore drill and the default growth limits with
"go" in chapter 1, and the servers' real monthly price with a yes on
[chapter 3's price screen](03_make_your_server_account_and_your_systems_desk.md#the-real-price-approved-once).

**Who acts:** you, the coding agent, do every step through the desk: the
team's scripts reach the provider through the API proxy. The person does
nothing, unless the stock or the prices changed since chapter 3's price
screen (step 2).

**Tell the person when the chapter starts,** at the end of chapter 3,
before step 1, the one line that
[Create the three production servers now](03_make_your_server_account_and_your_systems_desk.md#create-the-three-production-servers-now)
gives, which names each server's job the first time: `app001` for your
app, `db01` for its data, and `util01` for the system tools. After chapter
5, no message: the servers already exist.

## Before you start

- **The messages to the person.** You work alone in chapters 5 to 9, and
  the person may be away. Give each step's message as one short line, and
  give the full text only when the person asks. Use each step's links and
  names.
- **No private network may overlap the WireGuard network.** Before creating
  the first server, check that no private network the provider attaches to
  the new servers overlaps `vars.wireguard_network`: a private network the
  team made at the provider, or one the provider adds to every new server.
  If one overlaps, choose another network as
  [chapter 3 (make your server account and your systems desk)](03_make_your_server_account_and_your_systems_desk.md) describes,
  then [update the desk's production peers](03_make_your_server_account_and_your_systems_desk.md#update-the-desks-production-peers) before connecting.
- **The link.** The person sees the new servers in the provider's web console.
  The team's [provider guide](../provider_guides/README.md) gives its address, in the section
  "The provider's web console", such as [Hetzner Cloud's](../provider_guides/hetzner_cloud.md#the-providers-web-console).

## Steps

1. **The location and the sizes.** Use the production location and the sizes the person approved on
   [chapter 3's price screen](03_make_your_server_account_and_your_systems_desk.md#the-real-price-approved-once),
   and the desk's location from the same screen.
   The table gives the initial setup sizes, with Hetzner Cloud as an
   example. With another provider, use x86 types with at least each
   server's vCPUs, memory, and disk in the table:

   | Server | Hetzner Cloud type | Size |
   | --- | --- | --- |
   | `app001` | `cx23` | 2 vCPU, 4 GB RAM, 40 GB disk |
   | `db01` | `cx23` | 2 vCPU, 4 GB RAM, 40 GB disk |
   | `util01` | `cx23` | 2 vCPU, 4 GB RAM, 40 GB disk |
   | `staging01`, with the fuller system, created in chapter 7 | `cx23` | 2 vCPU, 4 GB RAM, 40 GB disk |
   | `app002`, with the fuller system, created in chapter 7 | `app001`'s type | `app001`'s size |

   Use x86 servers for the template's x86 software releases and example
   image build. In Hetzner's US locations, use the CPX line instead:
   `cpx21` for `app001`, `db01`, `util01`, `staging01` and `app002`
   (3 vCPU, 4 GB RAM). Each meets the
   table's minimums.

   `app001` starts at the smallest size, like `db01` and `util01`. The
   price screen offers the next size, such as `cx33` (4 vCPU, 8 GB RAM,
   80 GB disk), as an option for a heavier app. Reason: a small app's two
   releases fit in 4 GB during a deploy, and the deploy's memory check
   stops a deploy that lacks memory, visibly, before it changes anything;
   [Memory for both releases](../operating_procedures/deploy_and_roll_back_an_app_release.md#memory-for-both-releases)
   then moves `app001` to the bigger size in `growth_limits.app_servers.server_types`.

   The weekly drill's `restore01` takes `db01`'s server type, location,
   and operating-system image. Record `db01`'s values in
   `mmx_project_settings.yml` as `restore_drill_server_type`,
   `restore_drill_location`, and `server_image`, respectively.
   `server_image` names the image of every server `util01` creates, the
   same image as the three servers. [The server image](#the-server-image)
   says why the image is Debian 13.

   **Tell the person:** no message, because step 2 shows each server's
   size with its price.

   **Check:** each chosen type meets the table's minimums, and
   `restore_drill_server_type`, `restore_drill_location`, and
   `server_image` hold `db01`'s values.

2. **The prices, checked against chapter 3's price screen.** Read each selected server
   type's current hourly and monthly prices in the chosen location from
   the provider, through `http://127.0.0.1:8081/`. With the fuller system, the
   servers include `staging01` and `app002`. The
   [provider guide](../provider_guides/README.md) names the request that gives its prices, such as
   OVHcloud's flavor plan codes and public catalog. At OVHcloud these servers stay, so they are VPS
   servers: follow [VPS or Public Cloud](../provider_guides/ovhcloud_public_cloud.md#vps-or-public-cloud-by-how-long-the-server-stays).
   At Hetzner Cloud, request
   `GET http://127.0.0.1:8081/server_types`.
   From each selected type's `prices`, read the hourly and monthly prices
   for the chosen location. The server-type prices exclude the public
   IPv4 address that each server needs. Read the public IPv4 address's
   charge too, from `pricing.primary_ips` (type `ipv4`, at the chosen
   location) in `GET http://127.0.0.1:8081/pricing`.

   Check the stock again with the guide's stock request, through the
   same proxy. Compare with the sizes, locations and monthly total that
   the person approved on chapter 3's price screen. When they still hold,
   ask nothing: that yes approved these servers. When the stock or the
   price changed since, by more than the rounding of "about", show one
   screen by the same rule as chapter 3's, as the last text of your
   reply: each server's size, location and monthly price with its public
   address, the currency and whether tax is included; a sold-out size
   first moves to the same size at a nearby location of the same region;
   only when none has it, a bigger size, with the old total, the new
   total and the reason, one line each. Then "Say yes to create them, or
   tell me what to change." Never promise a separate approval otherwise.
   The person's "go" in chapter 1 approved the weekly restore drill. The drill runs each
   `weekly_work_day`, Sunday in the template, on a temporary server of
   the database server's size, usually within the hour. The first drill
   starts during chapter 7 (install everything on the production
   servers), and chapter 8 reads its result.

   Then write the growth limits, `growth_limits` in
   `mmx_project_settings.yml`, with the template's defaults, which the
   person's "go" approved. Write each pool's `server_types` for the chosen
   provider: the type in the table above, and the next bigger type of the
   same line. A pool is servers with the same job. Jobs servers and
   load-balancer servers keep the template's types, the bigger app size
   and the one above it, because a jobs server and a load-balancer server
   start when the load has grown. The
   defaults and their reasons are beside the setting. Chapter 10's
   operating guide shows each limit with its monthly cost, so the person
   can change a limit any day.

   Inside the limits, you add a server when a trigger arrives, and, with
   server work, the triage agent adds or removes one. Two operating
   procedures add capacity to the system: add a server to a pool, or
   replace a server with a bigger server. Commit the limits.

   `what_the_triage_agent_may_do_without_a_person` keeps
   `routine_fixes` from chapter 1. The triage agent's part of the setup asks the
   person, with the three answers and a recommendation.

   **Tell the person after:** no message, because step 4 starts with the
   servers' creation.

   **Check:** `growth_limits` holds the defaults in a commit, and the
   sizes and monthly total are those of chapter 3's price screen, or the
   person said yes to a new screen.

3. **Prepare each server's WireGuard identity on the systems desk.** Create
   `util01` first. For every initial server, generate the private key in memory with `wg genkey`.
   Pipe the private key to `wg pubkey` for the public key. Keep the pair in shell memory without logging.
   Keep only the public key as the node's `vars.wireguard_public_key` in
   `inventories/servers.yml`. The node's `address` equals the node's
   `vars.private_ip`. Use addresses inside the chosen `vars.wireguard_network`.

   Render [server_first_boot.cloud-config.yml](../server_management_scripts/server_first_boot.cloud-config.yml)
   with `server_management_scripts/render_server_first_boot`, building its
   `peers` list as steps 2 and 3 of
   [Enroll a server before the first MMX run](../server_management_scripts/README.md#enroll-a-server-before-the-first-mmx-run)
   say: every systems desk in `groups.systems_desks.nodes`, plus `util01`
   for every server other than `util01`. `util01`'s first-boot peers
   contain only the systems desks.
   Pass the rendered data to the provider once through a private temporary
   file outside Git, with mode `0600`. Remove the rendered file immediately
   after the provider accepts the data. Keep no setup-machine copy.

   Your shell keeps no variables from one command to the next, so make the
   key, render the first-boot data, and create the server (step 4) in one
   command per server, on the desk. The private key never leaves that
   command's memory and the temporary file; the command prints the public
   key, which you then save in the inventory. For `util01`, with the desk peers from the
   inventory written into `peers`:

   ```sh
   # The systems desk, in the coding agent's checkout. One command per server.
   cd ~/systems_repository
   set -euo pipefail
   umask 077
   private_key=$(wg genkey)
   public_key=$(printf '%s' "$private_key" | wg pubkey)
   first_boot=$(mktemp)
   trap ': > "$first_boot"; rm -f -- "$first_boot"' EXIT
   jq -n --arg private_key "$private_key" \
     '{private_key: $private_key, private_ip: "10.20.0.1",
       peers: [{public_key: "DESK01_WIREGUARD_PUBLIC_KEY", allowed_ips: ["10.20.9.1/32"],
                endpoint: "203.0.113.91:51820", persistent_keepalive: 25}]}' |
     ./server_management_scripts/render_server_first_boot > "$first_boot"
   unset private_key
   printf 'util01 WireGuard public key: %s\n' "$public_key"
   ./server_management_scripts/create_a_server_at_the_provider --server-name util01 \
     --server-type SERVER_TYPE --location LOCATION --image debian-13 --ssh-key-name SSH_KEY_NAME \
     --first-boot-data "$first_boot" --wireguard-public-key "$public_key" --wireguard-private-ip 10.20.0.1
   ```

   **Tell the person:** no message, because step 4 runs in the same
   command and tells the person about the servers' creation.

   **Check:** each node in `inventories/servers.yml` has its
   `vars.wireguard_public_key`, an `address` equal to its `vars.private_ip`
   inside `vars.wireguard_network`, and no private key is in Git or in a
   file on the systems desk.

4. **Create each server with the approved type and location.** You run
   the team's scripts on the desk, which reach the provider through the API
   proxy and never read the person's token. First register the desk's
   production public key, `/etc/systems-desk/production_key.pub`, at the
   provider through the proxy, and check that the registered key equals
   the file. Complete the provider guide's console activation, when the
   guide names one. Then run
   `create_a_server_at_the_provider` with
   `--server-name` (the server's name at the provider must be exactly its
   inventory name, such as `util01`: the weekly restore drill and the checks
   for leftover servers find a server by that name in the provider's list),
   `--server-type`, `--location`, the provider's Debian 13
   image as `--image` (`debian-13` at Hetzner, `"Debian 13"` at OVHcloud), and the registered systems desk key's name as
   `--ssh-key-name`. Supply the rendered private file as
   `--first-boot-data`, the new public key as `--wireguard-public-key`,
   and the node's WireGuard address as `--wireguard-private-ip`.
   Follow the [provider script contract](../server_management_scripts/README.md#write-the-teams-provider-scripts).

   Without the provider scripts (for a provider outside the guides), use the provider's own command-line tool, as
   [Without the provider scripts](../server_management_scripts/README.md#without-the-provider-scripts)
   says.

   Record the result's `public_ipv4_address` as the node's
   `vars.public_ipv4_address`, separate from the private `address`, and
   the result's `server_type` and `location` as the node's
   `vars.server_type` and `vars.location`: a replacement of a failed
   server is created with the same type in the same location, and
   `every_server` refuses a server without them.
   The first-boot script blocks public TCP 22 on IPv4 and IPv6 before
   sshd starts, opens UDP 51820 (servers and desks send to 51820; laptops send to 443, which a redirect written at first boot turns into 51820), writes the private key at
   `/etc/wireguard/wg0.private_key`, and starts `wg0`.
   After setup, the script blocks outgoing TCP 80 to the provider's
   metadata addresses, `169.254.169.254` and `fd00:ec2::254` unless the
   provider guide names others, then turns cloud-init off.

   **Tell the person first:**

   > Next, I create `util01`, then `app001` and `db01`, with the sizes and prices you approved: about [the total] a month.
   > Each server starts with no open SSH port to the internet. Only your systems desk reaches it, through a private network.
   > As you approved, your servers may later grow by themselves to at most 4 app servers and 2 database servers, up to about [X] a month more, without asking you.

   The growth line gives chapter 1's numbers: the person may have
   approved them without saying "details".

   **Tell the person while waiting:** each server takes about a minute or
   two to create and boot. The Stack's tests measured 49 to 94 seconds at
   Hetzner for the create, the boot, and the first boot's WireGuard.

   > Each server takes about a minute or two to start. I create them one at a time.

   **Tell the person after:** no message, because step 5 shows the
   servers once each one answers over SSH.

   **Check:** the provider's list shows each server under its inventory
   name, and each node has `vars.public_ipv4_address`, `vars.server_type`,
   and `vars.location`.

5. **Update the desk, then trust each SSH host key over WireGuard.**
   Before connecting, commit and push the new inventory, then run `sudo -n update-this-desks-wireguard-peers`.
   It prints each new server's peer it added. The desk now has every new server's WireGuard peer.
   [Update the desk's production peers](03_make_your_server_account_and_your_systems_desk.md#update-the-desks-production-peers) says more.
   Save each new public key and
   address in the inventory before connecting. From the repository root,
   accept the new server's host key once over wg0:

   ```sh
   # The systems desk, for util01's WireGuard address:
   ssh -F ssh/config -o StrictHostKeyChecking=accept-new root@10.20.0.1 true
   ```

   Use each server's private `address` for the remaining connections.
   Retry a refused connection while the new server boots. The shared
   `ssh/config` writes the observed host key to `ssh/known_hosts`.
   Every later connection requires the recorded host key. Generate no
   SSH host key on the setup machine.

   **Tell the person first,** before the first SSH connection:

   > Next, I connect to each new server once and save the server's identity in your systems repository.
   > Every later connection checks that identity, so an impostor server is rejected.

   **Tell the person after,** once each new server answers over SSH:

   > Your three servers are running: `app001` at [address], `db01` at [address], and `util01` at [address].
   > You can see the servers in [the provider's web console, at the address in your provider guide's "The provider's web console"].

   **Check:** `ssh/known_hosts` holds each new server's host key, and
   `ssh -F ssh/config root@ADDRESS true` succeeds over each server's
   private `address`.

6. **The shared root console password is ready.** `set-up-outside-services go-live`
   in [chapter 4 (set up your accounts and lock your systems desk)](04_set_up_your_accounts_and_lock_your_desk.md#steps)
   made the servers' shared root console password, saved only its hash in
   the vault as `shared_root_console_password_hash`, and put the password
   itself into the recovery bundle. Every server shares the one password.
   Check with
   `sudo -n -u servers-mmx run-mmx-on-the-servers secrets usage shared_root_console_password_hash`
   that the hash is defined.

   MMX sets root's password from `shared_root_console_password_hash` during
   chapter 7 (install everything on the production servers), using `password_hash` and `apply_password_hash: on_every_run`.
   SSH keeps refusing passwords. The password opens a server's console at
   the provider when SSH fails, as each [provider guide](../provider_guides/README.md)
   says. The person reads the password from the recovery bundle on the day
   the person needs it.

   When the hash is not defined, `go-live` did not finish: read
   `stopped_with` in `/var/lib/monkeymaxxing-stack/setup_results.json` on
   the desk, and give the person `ssh desk01-setup` again, which continues
   where it stopped.

   **Tell the person:** no message.

   **Check:** `secrets usage shared_root_console_password_hash` shows the
   hash as defined.

7. **Commit and push the inventory and host keys.** Keep
   `app001_db01_and_util01_created` open until
   [chapter 7 (install everything on the production servers)](07_install_everything_on_the_production_servers.md) proves MMX
   reaches every server over private SSH. The check from an outside machine
   that public TCP 22 is closed is optional:
   [Check my system's protections](../operating_procedures/assess_a_running_system_and_recommend_changes.md#check-my-systems-protections).

   **Tell the person after,** which also ends the chapter:

   > Your three servers and their keys are saved in your systems repository.
   > Next, MMX, the program that sets up your servers from your systems repository, installs everything on them.

   **Check:** `git status` shows nothing to commit, and `publish-branch-to-main`
   published the commit on the desk's `main`.

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
- **A private network overlaps `vars.wireguard_network`** (before step 3):
  choose another network and update the desk's production peers, as
  [Before you start](#before-you-start) says.
- **The location has no server of the requested type free** (step 4): the
  create script retries for five minutes. After the retries, show the one
  price screen of step 2 again, with a nearby location first, before
  choosing another location or a bigger type.
  Record a changed type or location in the commit message. Previously
  created servers keep the previous location.
- **The provider is outside the guides** (step 4): use the provider's own
  command-line tool, as
  [Without the provider scripts](../server_management_scripts/README.md#without-the-provider-scripts)
  says.
- **An ARM system:** an ARM system needs matching software releases and
  images. The pinned downloads of MMX, MMWatchdog, MMHotline, Litestream, and
  rclone in `mmx_project_settings.yml` are also x86-64 archives.

## Why the chapter works this way

**`app001` is bigger.** `app001` is bigger than `db01`, `util01`, and `staging01`
because `app001` needs memory for web and job containers. During a
deploy, the previous and new releases' web containers run together for
a minute. The deploy checks first, before changing anything, that
`app001` has enough memory ([deploy_and_roll_back_an_app_release.md](../operating_procedures/deploy_and_roll_back_an_app_release.md#memory-for-both-releases), "Memory for both
releases").
For how many apps of each framework fit on one app server, by
measured memory, see "How many apps fit on an app server" in the stack
repository's `docs/app-frameworks/README.md`.

**The drill's cost has a ceiling, with exceptions.** A drill stops after
`restore_drill_time_limit_hours`, six in the template. Provider cleanup
can take longer, and a refused destruction leaves the server billable
until removal. The team pays for the hours when the temporary server
exists.

**The desk makes the first keys.** Reason: the initial servers do not yet have a configured controller,
so the systems desk creates every initial key with the installed WireGuard tools. Later server
creation normally runs on `util01` with `wg genkey` and `wg pubkey`.
First-boot WireGuard gives MMX a private SSH route from the start.

**No public SSH, and no metadata after setup.** Reason: public SSH never provides a bootstrap route. The metadata
block prevents programs on the server from reading the first-boot key
through the provider's IPv4 or IPv6 metadata service after setup.

**The desk updates its peers before connecting.** Reason: recording a server in Git does not add the server to the desk's live `wg0`.

**The host key is trusted over WireGuard.** Reason: only the newly created server holds the WireGuard private key
matching the committed public key. The first SSH connection therefore
authenticates the server through WireGuard before trusting the SSH
host key. A public host-key scan would provide no such proof.

**The root console password is letters only.** Reason: the password is letters only, in groups, so a person can type it
into a console that cannot paste. Only the hash belongs in the vault.

## The server image

Use Debian 13 on every server. Hetzner names the image `debian-13`.

The Stack supports only Debian releases that have regular security
support from Debian's security team. Today, only Debian 13 qualifies.
Debian 12 is now in Debian LTS, which a separate team runs and which
covers fewer packages.

A new Debian release, such as Debian 14, joins the Stack in a later Stack
version, once the Stack's own tests on the new release pass. From that
Stack version on, new servers start on the
new release. Running servers can stay on their release while its regular
security support lasts. Debian ends that support about one year after the
next release. MMWatchdog's check `security_support_lasts_another_half_year`
warns 180 days before the support ends. Before then, move the running
servers to the new release,
as the Stack version that adds the release describes in
[Upgrade to a new stack version](../operating_procedures/upgrade_to_a_new_stack_version.md#what-each-version-changes).
Most servers move with [Replace a server](../operating_procedures/replace_a_server.md).
The database servers also change their Postgres major version, which
Replace a server alone does not cover, so that Stack version brings
tested steps for the database servers.
Never upgrade a server's Debian release in place.

Reason: Debian supplies security fixes for the Stack's distribution
packages without an extra subscription. The Stack always creates new
servers, so choosing Debian costs the team nothing.

Next, in the same reply, as the skill's "Now and next" rule says: [Chapter 7: Install everything on the production servers](07_install_everything_on_the_production_servers.md).
