# Server management scripts

The Stack ships `run_mmx_on_util01`, the way the coding agent runs MMX on
`util01` from a systems desk. The coding agent writes and reuses the
team's provider scripts in the same directory.

## Run MMX on util01

The helper works once a run has applied the triage agent's settings (chapter 8,
part 1). Before that run, MMHotline has applied no `triage_agent` settings, so
it trusts no commit and the helper refuses (MMHotline's own words: "no commit
signing keys are applied"); use the systems desk's
button, `sudo -n -u servers-mmx run-mmx-on-the-servers`, for those runs.

From the systems repository, after committing and pushing `main`:

```sh
./server_management_scripts/run_mmx_on_util01 run every_server
./server_management_scripts/run_mmx_on_util01 run deploy --var environment_name=production
```

The helper accepts MMX's arguments. The helper fetches `origin/main` and
refuses uncommitted files or a different systems desk `HEAD`. `main` also
moves without the desk: the triage agent pushes its notes, and
`replace_failed_servers` and `destroy_replaced_servers` push commits. The
helper then refuses with "HEAD must equal pushed main: run git pull
--rebase, and push your own commits if any, then run this again"; nothing
ran. On `util01`,
as root, the helper first asks MMHotline to check the commit, without the
lock:
`mmhotline commit-reviews check --commit-id COMMIT --json`. MMHotline
trusts every commit on `origin` (`systems_repository_commits.trusted_commits: every_commit_on_origin`
in `mmhotline_settings.yml`), fetches, and moves its checkout forward to
the commit. When MMHotline does not answer, the helper says so and runs
nothing. Then the helper takes the shared lock as `mmhotline`,
requires the copy's checkout at the systems desk commit, and runs MMX.
The helper never moves the checkout.
Output streams to the systems desk. The exit status comes from MMX. A
refusal names the failed condition. The helper is a short Bash script;
read it to see each step.

The order matters: MMHotline's check takes
`/var/lib/mmhotline/systems_repository.lock` itself and waits for the lock
without a time limit, so a check made while holding the lock would wait
forever. Ask MMHotline first, then take the lock.

Reason: matching commits makes the pushed change the running change. The
shared lock makes ordinary runs, server settings comparisons, and restore drills take turns.

MMX keeps 30 days of run history by default (`run_history_retention` in `mmx_project_settings.yml`) in `.mmx/` of `util01`'s copy of the systems repository. Read
results with `./server_management_scripts/run_mmx_on_util01 results`, which shows the newest saved run, or
`results RUN_ID` for one run. Run one command on servers with
`./server_management_scripts/run_mmx_on_util01 run-command --nodes app001,db01 -- uptime`. `results`, `status`, and `stop` take no
lock and need no clean, pushed systems desk copy: a run in progress holds the
lock, and these commands change no setting.
MMHotline also shows each run's output on the request's page after the
run ends.

MMHotline commits no output after an MMX run.

MMHotline, the helper and all scheduled jobs share
`/var/lib/mmhotline/systems_repository` and
`/var/lib/mmhotline/systems_repository.lock`. Each takes `flock` before
running MMX in the copy, never while asking MMHotline the commit check, and keeps the lock until its operation ends. After taking the
lock, each writes one line naming the holder into the lock file, which
the helper shows while it waits. MMHotline leaves the file empty during
short fetch, explain or push operations, so an empty line means an
unnamed operation holds the lock. A new scheduled job on `util01` follows
the same order.

While MMHotline waits for the lock, it keeps
`/var/lib/mmhotline/systems_repository.lock.waiting`, one line that names
the waiter. The weekly restore drill, which holds the lock for long, ends
when it sees the marker and runs again 2 hours later
([The drill gives way to MMHotline](../operating_procedures/run_the_weekly_database_restore_drill.md#the-drill-gives-way-to-mmhotline)).
So a scheduled job asks MMHotline's commit check only while no one holds
the lock: otherwise MMHotline's wait would end a drill for a check that
runs nothing. The helper's commit check does end a drill: the person gets
`util01` within about two minutes.

Before `util01` exists, while `util01` is broken or rebuilt, after changing
the vault passphrase, and for `util01`'s reboot, use
`sudo -n -u servers-mmx run-mmx-on-the-servers` on the desk with `--connection ssh_only`.
Desk previews use `sudo -n -u servers-mmx run-mmx-on-the-servers dryrun` with `--connection ssh_only`, after pushing. Wait until any utility-server run has finished.
MMHotline runs `mmx` at the judged commit under the shared lock.

## The replacement of a failed server

`replace_failed_servers`, `destroy_replaced_servers` and
`read_the_fleet_hub_for_server_replacement` are the programs of
`playbooks/replace_failed_servers.yml` and
`playbooks/destroy_replaced_servers.yml`, run on `util01` by MMX, never by
hand. Each program's comment lists its steps, its refusals and what a
rerun does after a failure at each step. They use the team's provider
scripts below, and share two files of steps:
`steps_for_replacing_failed_servers.bash` (the fleet hub's view, the Git
trailers, the push to `main`) and `steps_for_a_server_this_run_creates.bash`,
which the weekly restore drill and the row recovery
(`playbooks/recover_rows_from_a_restored_copy.yml`) use too (the first-boot
data, the create with a receipt, the destroy by the receipt's ID, the
runtime WireGuard peer, the host key, and `restore01` in a throwaway clone). [Replace a server](../operating_procedures/replace_a_server.md#a-failed-server-the-three-replacement-playbooks)
gives the commands for a person.

## App servers added and removed with the load

`add_an_app_server_for_the_load`, `remove_an_app_server_for_the_load` and
`read_the_app_pool_load` are the programs of
`playbooks/add_an_app_server_for_the_load.yml` and of
`playbooks/remove_server.yml` run without `server_name`, run on `util01` by
MMX, never by hand. `read_the_app_pool_load`, as root, hands the fleet
hub's readings to `/usr/local/bin/check-whether-the-load-changes-the-app-pool`
(from `roles/util_server/files/`), the one rule that `util01`'s checks
`app_servers_to_add_for_the_load` and `app_servers_to_remove_for_the_load`
run too. The two programs share `steps_for_replacing_failed_servers.bash`
(the next name, the inventory change, the push to `main`, the price line)
and the add shares `steps_for_a_server_this_run_creates.bash`. Their
commits carry `Server-pool` with `Added-server` and
`Added-server-provider-id`, or `Removed-server` and
`Removed-server-provider-id`.
[Add an app server](../operating_procedures/add_an_app_server.md) and
[Remove a server](../operating_procedures/remove_a_server.md) give the
commands for a person.

## Write the team's provider scripts

Read the provider's guide in [provider_guides/](../provider_guides/) first;
each provider that setup offers has one. Without a guide, read the
provider's current API or command-line documentation. Write Bash scripts
the way the guide says. Most guides give the five scripts whole, with
`curl` and `jq` and the guide's request function: copy them, with the
team's own values at the top. The fifth,
`read_the_monthly_price_at_the_provider`, wraps the price request that
each guide names. When the scripts use a provider tool
instead, put the tool's pinned installation on `util01` in the
utility role, so rebuilding `util01` restores the tool. Reuse the scripts
for initial setup, later servers, and the restore drill.

The scripts have the following interfaces. Keep diagnostics on stderr and
JSON on stdout. A provider error returns a nonzero exit status.
`replace_failed_servers` powers a failed server off before it creates the
replacement, so a server that only looks dead cannot keep serving errors
through its tunnel connector; the disk stays for evidence until the new
server serves. The power-failure test of
[Add an app server](../operating_procedures/add_an_app_server.md#the-second-app-servers-test)
uses the same script.

| Script | Arguments and result |
| --- | --- |
| `create_a_server_at_the_provider` | `--server-name`, `--server-type`, `--location`, `--image`, repeated `--ssh-key-name`, `--first-boot-data`, `--wireguard-public-key`, `--wireguard-private-ip`, and optional `--ownership-file`. Return an object with string `id`, `name`, `public_ipv4_address`, `server_type`, `location`, `wireguard_public_key`, and `private_ip`. |
| `destroy_a_server_at_the_provider` | `--server-id` for an immutable provider ID, or `--server-name` for a person-directed removal. Wait for deletion to finish. Never fall back from a missing ID to a matching name. An ID the provider does not list counts as destroyed: say so on stderr and return as for a destroyed server, so a rerun after a lost answer succeeds. Return `{"id": ..., "deleted": true}`. |
| `power_off_a_server_at_the_provider` | `--server-id` only, never a name. Cut the server's power with the provider's power-off action, or, at a provider that has only a stop that shuts the operating system down, that stop, as the provider guide says. A server already stopped needs no action. Wait until the list's `power_state` is `stopped`, at most 5 minutes. Return `{"id": ..., "power_state": "stopped"}`. A server the provider does not list is an error, `no server with ID ...`: the caller decides what that means. |
| `read_the_monthly_price_at_the_provider` | `--server-type` and `--location`. Read the provider's current monthly price of one server of that type in that location, with the public IPv4 address it needs, by the price request its provider guide names (the same request chapter 6 shows the person). Return `{"server_type": ..., "location": ..., "monthly_price": "7.49", "currency": "EUR"}`, the price as a decimal string in the provider's currency. Say on stderr whether tax is included, and what the price leaves out, such as a public IPv4 address that the provider prices apart and whose price the answer does not state per month. A provider whose answer gives only an hourly price, such as Scaleway's catalog, gets the monthly estimate as the hourly price times 730, the hours of an average month (8,760 hours a year divided by 12): a server runs the whole month, and a provider that stops charging at a lower monthly cap bills less, so the estimate never understates the bill. Read a price that needs no credential, such as a public catalog, without one, so `util01`'s narrow token needs no extra right. A type or location the provider does not offer is an error. `add_an_app_server_for_the_load`, `replace_failed_servers` and `remove_server` put the price in their last lines, so the triage agent's report names what a new server costs and what a removed one no longer costs; a failure only leaves the price out, and never stops a run. |
| `list_the_servers_at_the_provider` | No arguments. Return `{"servers": [...]}` with every server's string `id`, `name` (exactly the inventory name the server was created with, such as `util01`: the restore drill finds `util01` and `restore01` by that name), `public_ipv4_address`, and `power_state`: `running` for a server that is powered on, `stopped` for one that is powered off, and the provider's own word for any other state, such as one that is starting. Each provider guide says which of its states are `running` and `stopped`. Include every page of the provider's listing, and every server of this system, util01 included: `replace_failed_servers`, `destroy_replaced_servers`, `add_an_app_server_for_the_load`, `remove_an_app_server_for_the_load`, the restore drill and the check for a leftover `restore01` refuse a list without `util01` at its `public_ipv4_address` (`steps_for_reading_the_providers_list.bash`), because a server missing from a partial list would count as gone. |

`SERVER_PROVIDER_API_TOKEN` holds the utility server's provider token. A
guide's request function sends the token in the provider's header through
standard input, or, at OVHcloud, signs each request with it; a script that
uses a provider tool hands the token to the tool's own token variable. Personal
tokens stay in the person's protected desk files. The coding agent uses `http://127.0.0.1:8081/`,
the API proxy, never the
person's token file. At OVHcloud, `SERVER_PROVIDER_API_TOKEN` holds the credential's three values joined
with colons, and the scripts sign in the shell where it is set
([the request function](../provider_guides/ovhcloud_public_cloud.md#the-provider-scripts-request-function)).
In a person-only terminal, or for account-owned restore jobs, export the provider tool's token variable
from `SERVER_PROVIDER_API_TOKEN`; scripts with a guide's request function read `SERVER_PROVIDER_API_TOKEN` itself. No credential goes in an argument or a repository file.

The create script must:

1. Register and verify the initial SSH public keys with the request or
   command the provider guide gives. Include the person's key and, once available, the utility
   server's key on ordinary servers. A drill server needs the utility key.
   OVHcloud's create takes one key: the key of the machine that runs the
   server's first MMX run, which writes root's whole key list.
2. Read rendered [first-boot data](server_first_boot.cloud-config.yml) once,
   and submit the data when creating the server. The setup machine creates
   the WireGuard key before creation and passes the public key and private
   address as arguments; no private key goes in an argument or receipt.
   Use an image whose cloud-init network stage runs before `ssh.service`
   and `ssh.socket`. No provider firewall is used.

   Reason: the first-boot script closes public SSH before installing
   packages, then starts WireGuard. An image starting SSH before cloud-init
   cannot meet the public-SSH requirement.
3. For a temporary capacity error that created no server, retry every 20
   seconds for up to five minutes. Reason for the times: a provider's
   location usually frees capacity within minutes, and 15 tries in five
   minutes stay far below every guide's provider's rate limits; after five
   minutes the shortage is not a passing one, so a person chooses another
   type or a nearby location ([Add a server](../operating_procedures/add_a_server.md),
   step 2). The times are fixed because a team gains nothing from other
   numbers: a longer wait only delays that choice. Report other errors immediately. Before
   retrying an ambiguous request, check whether the provider created the
   server; an ambiguous response must not create a duplicate.
4. When `--ownership-file` is supplied, write the accepted server's ID and
   name atomically as soon as the provider accepts creation, before waiting
   for boot. Finish the receipt with the public address, WireGuard public key, and private address.
   Leave the receipt on failure so the drill can destroy the owned server.

Reason: only the create script knows whether creation succeeded before a
later wait failed. A receipt protects customer data and prevents cleanup
from deleting another server with the same name.

For a power-failure test, run `power_off_a_server_at_the_provider
--server-id ID`, then power on with the guide's command and wait for
`running`. A power-off that cuts power without shutting down the operating
system tests a sudden power loss; a guide says when its provider has only a
stop that shuts the operating system down, as at OVHcloud. Register keys
and power on with the guide's plain commands or requests.

For a provider without a guide, verify create, list, key-checked SSH,
power-off/on, and destroy with a throwaway server before enabling the
weekly drill. For a provider that setup offers, the Stack's own tests have
proved these steps, except a step its guide names as not yet proved, such
as `util01`'s restore drill at OVHcloud; the person's system needs only its
own first server to answer. The daily
leftover check proves `util01`'s provider token.

### Without the provider scripts

Until the team's provider scripts exist, or for a provider outside the
guides, use the provider's own command-line tool: register the initial SSH
keys, pass the server's first-boot data to create, wait for provisioning,
and verify SSH trust; use the provider's list, power-off/on, or delete
command for the step being performed. Confirm the result with a fresh
listing. The [provider guide](../provider_guides/) and the script contract
above give the provider commands and required checks. Reason: the scripts
repeat commands the coding agent has already verified for the team's
provider, so prefer the scripts once they exist.

## Enroll a server before the first MMX run

The setup machine is normally `util01`. Initial setup and a rebuild of
`util01` use the systems desk instead.

1. Make a fresh WireGuard key pair in memory. On `util01`, use `wg genkey`
   and pass the private key to `wg pubkey` on stdin. Use the installed `wg genkey` and `wg pubkey` on the desk too. Keep only the public key in the inventory.
2. Build a `peers` list for `util01` and every entry of
   `groups.systems_desks.nodes`. Each peer object requires `public_key`
   and `allowed_ips`. Copy the inventory's `wireguard_public_key` into
   `public_key`. Set `allowed_ips` to a list containing the peer's
   `private_ip` with `/32`.
   Each desk peer has `endpoint: "<public_ipv4_address>:51820"` and `persistent_keepalive: 25`. The `util01` peer also has
   `endpoint: "<public_ipv4_address>:51820"` and `persistent_keepalive: 25`. 51820 is `vars.wireguard_listen_port`: servers and desks
   send to each other's WireGuard port directly, not to the redirected UDP 443 (the notrack table of
   `files_used_by_several_roles/wireguard_notrack_between_servers_and_desks.nft` says why).
   A new `util01` needs only systems desk peers. `restore01` needs only the
   `util01` peer.
3. Send JSON on stdin to `server_management_scripts/render_server_first_boot`:
   `private_key` is the new base64 key, `private_ip` is the WireGuard IPv4
   address inside `10.0.0.0/8`, `172.16.0.0/12`, or `192.168.0.0/16`.
   Each number must be at most 255. Use an address inside the inventory's `wireguard_network`.
   `peers` is the nonempty list from step 2. Every peer's `public_key`
   must be a WireGuard base64 key. `allowed_ips` must be a nonempty list of IPv4 or IPv6 prefixes. The optional `endpoint` accepts only `IPv4:port`
   or `[IPv6]:port`, with a port from 1 to 65535. The optional
   `persistent_keepalive` accepts a whole number of seconds from 0 to
   65535, WireGuard's supported range. Unknown fields are refused.

   For example, the `peers` value for `restore01` is:

   ```json
   [
     {
       "public_key": "PFHMlKh61wvN0/mEnwE2mCdTk3PCQmr/u0lh3F8JkT0=",
       "allowed_ips": ["10.20.0.1/32"],
       "endpoint": "203.0.113.1:51820",
       "persistent_keepalive": 25
     }
   ]
   ```

   The renderer writes cloud-config to stdout. Pass the result once
   through `--first-boot-data`, using a pipe where the provider's tool
   or request supports a pipe, or a mode-0600 temporary file outside Git. Remove the
   temporary file immediately after submission, including on failure.
   Keep shell tracing off and omit the rendered data from logs. Clear
   the private key variables after submission.

   Reason: validated peer fields cannot become wg-quick hooks running as root.
   The renderer reads the port WireGuard listens on, `vars.wireguard_listen_port`, from `inventories/servers.yml`
   beside it, and writes the redirect from UDP 443 to that port, for laptops
   (`wireguard_udp_443_redirect.nft`, written before `wg0` starts), and an empty table that skips connection tracking
   between servers and desks, which the first `every_server` run or desk review fills. A peer's `endpoint` is
   `<address>:` and that port.
4. Create the server. Record `address: <private_ip>`, `vars.private_ip`,
   `vars.public_ipv4_address`, `vars.wireguard_public_key`, and the
   receipt's `server_type` and `location` as `vars.server_type` and
   `vars.location` (not for `restore01`). Preserve the
   separate `https_address`. Commit and push. Apply `every_server` to the
   existing servers before waiting for the new server's first connection.
   During initial setup a systems desk already peers directly with every server.
5. Connect over WireGuard once with
   `ssh -F ssh/config -o StrictHostKeyChecking=accept-new root@10.20.1.1 true`,
   using the new server's private address. The command records the host key
   in `ssh/known_hosts`. Commit the host key, then run MMX with normal strict
   host-key checking. Never scan or trust the public address.

   Reason: only the new server has the private WireGuard key passed at
   creation, so the authenticated tunnel establishes trust in the SSH host
   key. Pre-generated SSH host keys add no protection and are omitted.

The temporary restore drill, and the row recovery the same way, adds `restore01` as a runtime peer on `util01`
using the inventory's `restore01_private_ip`, for example:
`ssh -F ssh/config root@10.20.0.1 wg set wg0 peer PUBLIC_KEY
allowed-ips 10.20.8.1/32`. Cleanup uses root SSH to remove the runtime peer
after stopping restore work. The drill holds the shared lock throughout
enrollment and removal. The permanent inventory and systems desk copies never
gain `restore01`.

Reason: a runtime peer changes only the temporary connection. Running the
whole utility role from a temporary inventory would change unrelated settings.
A nested MMX command targeting `util01` would conflict with the outer drill's
node lock. The outer MMX job owns the root SSH peer commands. The drill records
the public key in the attempt directory for cleanup after an abrupt
utility-server loss.

## Desk caller and MMX buttons

All systems work starts on the desk, as `coding-agent`.
`run_mmx_on_util01` still applies the clean pushed `main` commit on `util01` under the shared lock.
Direct production runs from the desk use `sudo -n -u servers-mmx run-mmx-on-the-servers`, including util01 recovery and reboot.
The button reads pushed `main`, so commit, pull with rebase, report incoming changes, and push before using the button.
The person alone manages `systems_desk` from the person's checkout with the preserved SSH agent socket.
Update the desk's `wg0` peers with `sudo -n update-this-desks-wireguard-peers` after a pushed change that adds, replaces or removes a server, before attempting SSH to that server ([Update the desk's production peers](../initial_setup/03_make_your_server_account_and_your_systems_desk.md#update-the-desks-production-peers)).
The laptop has no inventory copy after bootstrap and uses only a desk-specific `--wireguard-config` file.
