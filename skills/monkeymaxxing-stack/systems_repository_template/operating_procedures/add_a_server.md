# Add a server

Read [the systems repository rules](../AGENTS.md#the-rules) first.

**When to use this page:** another operating procedure sends you here to
create a server. Every operating procedure that creates a server follows
these steps and says which of them it uses, such as
[Add an app server](add_an_app_server.md),
[Add a second database server](add_a_second_database_server.md),
[Add jobs servers](add_jobs_servers.md),
[Add load-balancer servers](add_load_balancer_servers.md),
[Add staging01](add_staging01.md), and [Replace a server](replace_a_server.md).

**What this page does:** these are the shared steps that create a server
and bring it into its pool: pick its name, create it with its WireGuard
key, record it in the inventory, trust its SSH host key, apply its
configuration, reboot it, and verify it.

**Who acts:** you, the coding agent, do every step from the systems desk.
The person only approves the monthly price when the new server is outside
the growth limits (step 1), and hears afterwards which server you added.

**Terms:** this page uses the Stack's terms, such as pool, growth limits,
inventory, playbook, and fleet stage.
[Technical terms](../talking_with_the_team.md#technical-terms) explains
each term.

## Before you start

- **Use your server's own name and addresses.** The examples below add
  `app002`; use the name and addresses of the server you add.
- **A push alone changes no server.** Apply each configuration change as
  [Making a change](../AGENTS.md#making-a-change) says: a push alone
  changes no server, so run `every_server` or the playbook the step names.
- **Without the provider scripts,** use the provider's own command-line
  tool, as
  [Without the provider scripts](../server_management_scripts/README.md#without-the-provider-scripts)
  says.

## Steps

1. **Pick the new server's name and WireGuard address.** Use the next
   number in the new server's pool
   ([Server names and private addresses](../AGENTS.md#server-names-and-private-addresses)).
   Use the Debian release from
   [The server image in chapter 6 (create your three production servers: app, database, and tools)](../initial_setup/06_create_your_three_production_servers.md#the-server-image).
   Use an x86 server and the pool's location and size,
   unless the change calls for a bigger server.

   **Check the growth limits,** `growth_limits` in
   `mmx_project_settings.yml`: with the new server, the pool holds at most
   its `largest_number_of_servers`, and the server's type is in the pool's
   `server_types`. Inside the limits, go on at once; no approval and no
   price check. Outside them, or for a pool without limits, such as
   `staging01`, ask the person first, with the monthly price. After step 8,
   tell the person which server you added, why, and its monthly cost from
   the provider's current price.

   **Check:** the name, address and type are chosen, and the server is
   inside the growth limits or the person approved its price.

2. **Prepare the first-boot data and create the server.** Follow the
   [provider-script contract](../server_management_scripts/README.md#write-the-teams-provider-scripts).
   The setup machine is normally `util01`.
   1. Generate the server's WireGuard private key in memory with
      `wg genkey`; pipe the private key to `wg pubkey` for the public key.
      When creating `util01`, use `wg genkey` and `wg pubkey` on the
      systems desk instead. Keep the public key for step 3. Never put the
      private key in Git, a command argument, a receipt, a log, or a
      persistent setup-machine file.
   2. Run `server_management_scripts/render_server_first_boot`, with the
      `peers` list for `util01` and every entry in `systems_desks`, as
      steps 2 and 3 of
      [Enroll a server before the first MMX run](../server_management_scripts/README.md#enroll-a-server-before-the-first-mmx-run)
      say. For `util01`, omit the server's own peer and include every
      systems desk. The renderer writes cloud-config on stdout.
   3. Pass the rendered data once to `create_a_server_at_the_provider`
      with `--first-boot-data`, using the provider's supported stream or a
      private temporary file removed after submission. Supply
      `--wireguard-public-key` and `--wireguard-private-ip` with the new
      server's public key and chosen private address. Register the
      person's SSH key and `util01`'s `mmhotline` SSH key on `root`. Use
      the provider guide for the remaining create arguments.
   4. Clear the setup machine's private-key variables after submission.

   **Check:** the create script returns the new server, with its public
   IPv4 address, `server_type` and `location`, which step 3 records. A
   capacity refusal or an unclear answer: see
   [If something is different](#if-something-is-different).

3. **Add the new server to the inventory and the server's group.** Set
   `address` to `private_ip`. Record the provider's public IPv4 address as
   `public_ipv4_address`, the public key from step 2 as
   `wireguard_public_key`, and the create script's `server_type` and
   `location` as `server_type` and `location`: a replacement of a failed
   server is created with the same type in the same location, and
   `every_server` refuses a server without them. The following key is an
   example public key; replace the example key with the key generated for
   `app002`:

   ```yaml
   # inventories/servers.yml
   nodes:
     app002:
       address: 10.20.1.2
       https_address: https://10.20.1.2:7443
       ssh_user: root
       ssh_known_hosts: ssh/known_hosts
       ssh_config: ssh/config
       vars:
         private_ip: 10.20.1.2
         public_ipv4_address: 203.0.113.12
         server_type: cx33
         location: fsn1
         wireguard_public_key: PFHMlKh61wvN0/mEnwE2mCdTk3PCQmr/u0lh3F8JkT0=
   groups:
     app_servers:
       nodes: [app001, app002]
       vars:
         is_app_server: true
         mmwatchdog_check_files: [every_server.yml, app_servers.yml]
   ```

   Commit and push the inventory, then run `every_server` on `util01`
   limited to `util_server` and the `every_server` fleet stage:

   ```sh
   ./server_management_scripts/run_mmx_on_util01 run every_server --only-fleet-stages every_server --limit util_server
   ```

   Reason: `util01` must accept the new server's WireGuard key before MMX
   can connect to the new server. Skipping this run makes step 5 fail with no
   hint ([If something is different](#if-something-is-different)).

   Before connecting to the new server, run `sudo -n update-this-desks-wireguard-peers`, as
   [update the desk's production peers in chapter 3 (make your server account and your systems desk)](../initial_setup/03_make_your_server_account_and_your_systems_desk.md#update-the-desks-production-peers)
   describes. Each teammate's coding agent runs it on that teammate's desk at the start of its next session.
   Use the new server's inventory address, such as `10.20.1.2`.

   **Check:** the limited run on `util01` passes.

4. **Trust the SSH host key seen over WireGuard.** Remove any old line for
   the chosen WireGuard address from `ssh/known_hosts`. From a systems desk in
   the systems repository, accept the host key over wg0:

   ```sh
   ssh -F ssh/config -o StrictHostKeyChecking=accept-new root@10.20.1.2 true
   ```

   Retry while the server boots. Save the resulting `ssh/known_hosts` line
   in Git. Every later connection requires the recorded host key.

   **Check:** the command exits 0, and `ssh/known_hosts` holds one new
   line for the new server's address.

5. **Preview and apply the new server's configuration.** Commit the host
   key, synchronize, and push. Preview the pushed commit with
   `sudo -n -u servers-mmx run-mmx-on-the-servers dryrun every_server --connection ssh_only`.
   Tell the person in one line first that this first preview copies MMX's
   program, `mmx-runner`, to the new server and starts no service. The
   run that follows also sets up MMX's HTTPS service there, on TCP port 7443.
   Exit 3 is expected: the new server lacks the packages, accounts and
   programs that earlier tasks of the run install, so the preview reports
   the tasks that need them `not_checked`, such as
   `find_the_live_and_new_web_ports` on the new server, and the tasks on
   the other servers that read its answer. Inspect every unchecked task's
   reason; go on when each names an earlier task of the run, as step 5 of
   [Making a change](../AGENTS.md#making-a-change) says. Exit 1 is failed
   work: stop and read the failed task.
   Then run `./server_management_scripts/run_mmx_on_util01 run every_server`.

   **Check:** the run passes. Private-network stages must pass in the run.
   When it fails at `install_jq_and_python3` with "No route to host" for the
   new server, step 3's limited run on `util01` did not happen: run it, then run
   `every_server` again.

6. **Verify enrollment.** MMX's result shows the WireGuard public key as
   `[redacted]`, so read the key on the server instead, with the new
   server's WireGuard address (`10.20.1.2` is `app002` in the example):
   `ssh -F ssh/config root@10.20.1.2 wg show wg0 public-key`. No second
   key-generation run or key-copy commit is needed.

   **Check:** the command prints the public key recorded in step 3, and a
   fresh SSH connection from a systems desk and a fresh connection from
   `util01` succeed.

7. **Reboot the new server to use the installed updates.** A new kernel
   needs a reboot even after the configuration run passes. Reboot the new
   server now, while adding the new server, rather than waiting for the
   weekly window:

   - An app, jobs, or load-balancer server, or `staging01`:
     `./server_management_scripts/run_mmx_on_util01 run reboot_servers_after_updates`. The playbook reboots
     every app, jobs, load-balancer, and staging server whose updates wait
     for a reboot, including existing servers. Servers reboot one at a time.
     The remaining servers in each pool handle web requests or background
     jobs while a server reboots. A server that is the only one of its app
     or load-balancer pool, such as a replacement of `app001` alone, waits
     for the weekly window, and the run says so; when the site is not
     serving users yet, or the person accepts the short outage now, add
     `--var reboot_the_only_server_of_a_pool_outside_the_maintenance_window=true`.
   - A database server: `./server_management_scripts/run_mmx_on_util01 run update_database_servers` ([Update and
     restart the database
     servers](update_and_restart_the_database_servers.md)). Daily database
     server updates leave out the kernel.
   - `util01`: from a systems desk,
     `sudo -n -u servers-mmx run-mmx-on-the-servers run reboot_util01_after_updates --connection ssh_only`, because
     MMX never reboots the machine it runs on.

   No check of its own: step 8 verifies the server after the reboot.

8. **Verify:** `ssh -F ssh/config root@10.20.1.2 mmwatchdog status` exits
   0 when no check needs attention. A check listed as `confirming_failure`
   is failing but has not failed long enough to alert. A check listed as
   `unknown` makes `status` exit 3: see
   [If something is different](#if-something-is-different).

   Check that the dashboard's **Servers** list shows the new server with
   its groups, such as `app002` with App servers. Then
   verify the checklist item of the operating procedure that sent you to
   these steps, if that procedure has an item. For a second app server,
   verify `second_app_server` in `monkeymaxxing_stack_checklist.yml` with
   [the second app server's test](add_an_app_server.md#the-second-app-servers-test).

   **Check:** `mmwatchdog status` exits 0, and the dashboard lists the new
   server. Then tell the person which server you added, as step 1 says.

## If something is different

- **The provider refuses for lack of capacity (step 2):** a capacity
  refusal that created no server retries every 20 seconds for five
  minutes, times fixed in the
  [provider-script contract](../server_management_scripts/README.md#write-the-teams-provider-scripts).
  After five minutes, choose a server at least as large or a nearby
  location, and record the choice in the commit.
- **The provider's answer is unclear (step 2):** before retrying an
  ambiguous provider response, establish whether creation succeeded.
- **The full run stops at `install_jq_and_python3` (step 5):** with "SSH 10.20.3.1: ...
  No route to host" on the new server, because `util01` has no WireGuard
  peer for it yet. Step 3's limited run on `util01` did not happen: run it,
  then run `every_server` again. WireGuard handshakes succeed once the
  first boot and the utility peer update have completed, in either order.
- **`mmwatchdog status` exits 3 with a check listed as `unknown` (step 8):**
  a check that last ran before setup finished shows `unknown`, and
  `status` exits 3 until the check runs again. For example, the job
  container's check may have run before its container started. Run the
  check group of each check listed as `unknown` once the server has had a
  few minutes, or wait for its `check_every` in `mmwatchdog_checks/`, which
  is up to 6 hours. Do not run `check-now` on a server that serves
  requests unless its MMWatchdog maintenance is on
  (`mmwatchdog maintenance on --every-check-group --for 15m
  --reason "checking the new server"`, and `maintenance off --every-check-group`
  after). Reason: a check such as `installed_packages` takes 100 to 160 seconds and
  pushes an app server's CPU to 75 to 100%, which the pool's check for adding a
  server counts as load, so one early `check-now` can add an app server that
  nobody needed. Then run `status` again.

## How the steps work

This part explains the steps, for the reader who wants the reasons.

### The first boot and WireGuard

The first boot blocks public SSH before sshd starts, writes
`/etc/wireguard/wg0.private_key` as root with mode `0600`, and starts
`wg0` on UDP 51820, which the redirect from UDP 443 reaches. The server allows SSH only over `wg0`. The first-boot
script blocks outgoing TCP 80 to the provider's metadata addresses,
`169.254.169.254` and `fd00:ec2::254` unless the provider guide names
others, then disables cloud-init after setup.
No provider firewall is needed.

Reason: first-boot WireGuard makes the server reachable without ever
opening public SSH. The private key goes once to the new server; the
setup machine keeps only the public key.

### The host key

Reason for trusting the host key seen over WireGuard: only the new server
holds the private key generated in step 2. WireGuard therefore
authenticates the server before SSH records the host key. Pre-generated
SSH host keys and public-address scans are unnecessary.

### The configuration run

The run reuses `/etc/wireguard/wg0.private_key`, adds the server's normal
peers. An app, jobs or load-balancer server serves first and installs its
waiting security updates last in the run, 3 to 7 minutes on Debian 13
after the server serves. A database server installs them before its
services start.

### The reboot

Until the new server reboots, MMWatchdog warns about known exploited
flaws in the running kernel. MMWatchdog warns within about 12 hours
after a flaw enters
CISA's list of known exploited vulnerabilities: by default the check
group `installed_packages` runs every 6 hours (`check_every` in
`mmwatchdog_checks/every_server.yml`, because one check takes about
100 seconds), and its second failed run warns. The warning reports a
known vulnerability, not an attack detected on the new server.

No server reboots by itself, so someone always chooses the time ([A fix
that waits for a
reboot](../triage_agent_rules.md#a-fix-that-waits-for-a-reboot)).

The `update_database_servers` playbook installs kernel
updates on each database server in turn. The playbook reboots the new
database server while the new server is a replica. The playbook
switches the primary so the old primary can be updated as a replica
too. Writes fail for a few seconds during the switch.
