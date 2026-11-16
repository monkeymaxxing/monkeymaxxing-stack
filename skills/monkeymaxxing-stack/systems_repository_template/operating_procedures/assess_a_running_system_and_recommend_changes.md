# Assess a running system and recommend changes

**When:** you start work on a systems repository that has
`monkeymaxxing_stack_checklist.yml`, with every server in its
`inventories/servers.yml` built by the Stack; or the person asks for
extra confidence, such as "Check my system's protections".

**What this page does:** you compare the running system with its systems
repository, its limits and its checklist, recommend the operating
procedures that the readings call for, and run one only when the person
asks. [Check my system's protections](#check-my-systems-protections) is
an optional deeper check that the protections hold on the team's own
servers.

**Who acts:** you, the coding agent, assess, recommend, and run the
harmless checks. The person decides which recommendation to execute, and
agrees each disruptive check and its time. The person does the checks
that need the person's own laptop or terminal: harmless check 6 and
check 12, and the logins of disruptive check 1.

## Before you start

- **With a systems repository, read its `AGENTS.md` first.** It holds the
  rules and the operating procedure table that the steps below use.

## Assess, recommend, execute

Follow the three steps in order.

1. **Assess.** The assessment has three parts:

   - Compare `inventories/servers.yml` with the live server list from
     `./server_management_scripts/list_the_servers_at_the_provider`.
     Then use `sudo -n -u servers-mmx run-mmx-on-the-servers dryrun every_server --connection ssh_only` to compare the inventoried
     servers' settings with the systems repository.
     The dryrun exits 0 when MMX finds no changes to make and 2 when
     something would change.
   - Compare each pool's resource use with the limits in
     `mmwatchdog_checks/`.
     Resource use includes CPU, memory, disk, and network use, as measured
     by the pool's checks.
     Also compare the readings with the "When this happens" column of
     [the operating procedure table](../AGENTS.md#when-this-happens-follow-this-operating-procedure).
     Use the past week's readings on MMWatchdog's fleet hub on `util01`
     (`mmwatchdog fleet readings`).
     MMWatchdog's docs, "Looking at the readings", explain how to read the
     measurements.
   - Review `monkeymaxxing_stack_checklist.yml`'s open items and done items
     whose `verified_at` is older than `verify_again_every`.

   [Do the weekly system review](do_the_weekly_system_review.md#what-the-coding-agent-gathers)
   gives the commands for the week's alerts, updates, and restore drill.

   **Check:** you can name, for each of the three parts, what differs or
   that nothing differs, such as the dryrun's exit code.

2. **Recommend** an operating procedure only when the table's "When this
   happens" condition is met. For a measured condition, give the numbers:
   "The app pool's peak CPU passed 47% on 3 of the last 7 days.
   Add `app004`."

   Never propose a step beyond the stack based on a measurement alone.
   Examples are a second location, a second provider, or surviving a
   Cloudflare outage.
   A step beyond the stack requires a business requirement.
   The team decides whether to take the step beyond the stack.
   The checklist's `what_this_system_does_not_survive` section lists the
   outages that require changes beyond the stack to avoid downtime.

   **Check:** each recommendation names the table's condition and the
   numbers that meet it.

3. **Execute only when the person asks.** Follow the tested operating
   procedure from
   [the operating procedure table](../AGENTS.md#when-this-happens-follow-this-operating-procedure),
   step by step. Then run the operating procedure's verification.
   After verification passes, update the operating procedure's checklist
   item as [The checklist](../AGENTS.md#the-checklist) requires.
   **Check:** the operating procedure's verification passes.

## If something is different

**If the recorded stack version lacks a required program or operating
procedure:** the stack version is recorded by `stack_version` in
`monkeymaxxing_stack_checklist.yml`.
If the recorded stack version lacks a required program or operating
procedure, do not improvise the operation.
The operation's checklist item names the unavailable program or
operating procedure in `waits_for`, or in `trigger` for a growth or
improvement item.
Tell the person which program or operating procedure is missing, then
stop that operation. The rest of the assessment goes on.

## Check my system's protections

This section is optional. Run it only when the person asks, for example
"Check my system's protections", or accepts the offer at the end of the
setup: "Want extra confidence? Ask me to check your system's protections."
[Why these checks are optional](#why-these-checks-are-optional) gives the
reason.

The checks come in two kinds. Say which kind each check is before the
check starts.

- **Harmless checks** only read. They change nothing on a server, so the
  coding agent can run them at any time without asking again.
- **Disruptive checks** change something while they run: they stop a
  service, reboot a server, lock a laptop out, or send an alert that
  reaches a phone. Ask the person before each disruptive check. Name what
  stops or rings, and how long the check takes. Agree on a quiet time,
  with no open incident and no team mute. Run one disruptive check at a
  time, and put back what the check changed before the next check.
  Reason: a disruptive check run at a busy hour costs customers or wakes
  someone for a test.

Record each result, with its date, in `last_result` of the checklist item
`optional_protection_checks`. When a check fails, report the failure and a
proposed fix. Execute the fix only when the person asks, as step 3 of
[Assess, recommend, execute](#assess-recommend-execute) says.

Each numbered item below is itself a check: the item says what must show
for the check to pass.

### Harmless checks

Run the server-side commands from the coding agent's checkout on the
systems desk, with `ssh -F ssh/config root@ADDRESS`. `ADDRESS` is the
server's private address from `inventories/servers.yml`. Run each
server-side check on every production and staging server, unless the check
names one server.

1. **SSH settings and the exact authorized keys.** `sudo sshd -T` shows
   `passwordauthentication no` and root login by key only. Root's
   `authorized_keys` lists exactly the keys in `root_ssh_public_keys` in
   `mmx_project_settings.yml`. Compare the keys' fingerprints from
   `ssh-keygen -lf`, so that a key nobody listed stands out.
2. **The firewall.** `ufw status verbose` shows incoming traffic denied by
   default. TCP 22 is open only on `wg0`, from the systems desks' range and
   from `util01`'s private address. UDP 51820 is open to every source (laptops send to 443, servers and desks to 51820, and the redirect `wireguard-udp-443-redirect.service` turns it into 51820).
   `ss -tulpn` lists only the server's own programs.
3. **The WireGuard peers.** `sudo wg show wg0` lists exactly the peers that
   the server's role needs, plus the systems desks, as
   [Server names and private addresses](../AGENTS.md#server-names-and-private-addresses)
   lists them. Every active peer has a recent handshake. Server names such
   as `db01` resolve to private addresses from `/etc/hosts`.
4. **The log size limit.** `journalctl --disk-usage` shows a journal within
   the limit that the `every_server` role writes: `SystemMaxUse=2G` and
   `SystemKeepFree=4G`.
5. **The automatic updates.** `sudo apt-config dump` shows
   `Unattended-Upgrade::Automatic-Reboot "false"`. On the database servers,
   the `Package-Blacklist` names Postgres, pg_auto_failover, PgBouncer, and
   the kernel. MMWatchdog's check
   `security_updates/no_security_update_waits` passes.
6. **Public SSH is closed.** From a machine outside the system, such as the
   person's laptop, connect to TCP 22 of every public IPv4 and IPv6 address
   of the servers, for example `nc -vz -w 5 ADDRESS 22`. Every connection
   must fail. The public IPv4 addresses are `vars.public_ipv4_address` in
   `inventories/servers.yml`. The IPv6 addresses come from
   `./server_management_scripts/list_the_servers_at_the_provider`.
7. **Postgres and MMX refuse the desk.** From the systems desk, a direct
   connection to Postgres on a database server (TCP 5432) and to MMX's
   HTTPS port (TCP 7443) on every ordinary server must fail. SSH
   forwarding still works when a person needs access.
8. **The metadata block.** On a server, `curl --max-time 5 http://169.254.169.254/`
   and `curl --max-time 5 'http://[fd00:ec2::254]/'` must fail, and
   `/etc/cloud/cloud-init.disabled` must exist. Use the addresses that the
   provider guide names when the provider guide names others. Reason: a
   program on the server must not read the first-boot key from the
   provider's metadata service. A failure can also come from a missing
   metadata service, so check the firewall rule too: `ufw status` lists
   the deny rule for each address.
9. **The helper refuses unpushed commits.** In the coding agent's checkout,
   make a local commit and do not push the commit:
   `git commit --allow-empty -m "Test of the helper: do not push"`. Run
   `./server_management_scripts/run_mmx_on_util01 validate`. The helper
   must refuse and say that the commit is not pushed, before the helper
   contacts `util01`. Then remove the test commit with
   `git reset --soft HEAD~1`.
10. **Each server holds only its role's secrets.** The server's secret files
    are root-only, such as `/etc/shop/shop.env` with mode 0600. Two files
    have another owner on purpose: `/etc/mmhotline/mmhotline_settings.yml`
    on `util01`, `root:mmhotline` with mode 0640, which MMHotline's own user
    reads too; and `/etc/pgbackrest/pgbackrest.conf` on the database
    servers and `restore01`, `root:postgres` with mode 0640,
    which pgBackRest reads as `postgres`. Read the modes with `stat` over
    SSH. A server holds no secret file of another role.
11. **Postgres accepts connections only over WireGuard.** On `db01`,
    `sudo ss -tlnp` shows Postgres listening on the server's WireGuard
    address only, and `ufw status` admits TCP 5432 only from the app
    servers, the database servers, and `util01`.
12. **The second way into MMHotline.** In the person's own desk terminal,
    forward `util01`'s MMHotline port with
    `ssh -L 8480:127.0.0.1:8480 util01`, make a one-time link on `util01` with
    `sudo mmhotline people create-sign-in-link --sign-in-email-address ADDRESS`,
    and open the link in the browser at `http://localhost:8480`. It signs the
    person in without Cloudflare, for the day Cloudflare is down. Record the
    result for `provider_console_and_backup_mmhotline_logins`.
13. **The cache behaves.** A public page that an app marks with
    `Cache-Control: public, max-age=60` answers `cf-cache-status: HIT` on its
    second request, and a response marked `Cache-Control: private` never
    answers HIT.
14. **Staging's alerts go no higher than warn.** On `staging01`, the
    check groups that MMX rendered for MMWatchdog, in
    `/usr/local/lib/mmwatchdog/candidate_config/check_groups/`, name no
    severity above `warn`, so a staging failure never wakes the person on call.
15. **The uploads copy's keys.** When an app keeps uploads, run
    [The uploads key check](turn_on_nightly_backups_of_uploaded_files.md#the-uploads-key-check):
    `util01`'s B2 key allows only the uploads' bucket, with exactly
    `listBuckets`, `listFiles`, `readFiles`, and `writeFiles` and no
    `deleteFiles`. On `util01`, a test upload to an app's R2 bucket with
    `util01`'s R2 key, through the copy's own rclone settings
    (`/var/lib/mmhotline/uploads_backup_rclone.conf`), is refused.
16. **Each app container's locks.** On each server that runs app
    containers (app servers, jobs servers, and `staging01`), check every
    web container (`APP-web-PORT`) and every jobs container (`APP-jobs`).
    List them with `sudo podman ps --format '{{.Names}}'`. For one container,
    read its process ID, then the process's own record on the server:

    ```sh
    NAME=APP-web-PORT
    PID=$(sudo podman inspect --format '{{.State.Pid}}' "$NAME")
    sudo podman inspect --format 'security_options={{.HostConfig.SecurityOpt}} capabilities_dropped={{.HostConfig.CapDrop}} read_only_root={{.HostConfig.ReadonlyRootfs}} user_namespace={{.HostConfig.UsernsMode}}' "$NAME"
    sudo cat /proc/$PID/attr/current
    sudo grep -E '^(Uid|NoNewPrivs|CapPrm|CapEff|CapBnd):' /proc/$PID/status
    sudo cat /proc/$PID/uid_map /proc/$PID/gid_map
    ```

    Each lock must show:
    - **The AppArmor profile.** `/proc/$PID/attr/current` prints
      `crun//&monkeymaxxing-app-containers (mixed)`. The `crun//&` part is
      expected: Debian 13's `crun` profile stacks with ours. `unconfined`
      or a line without `monkeymaxxing-app-containers` is a failure.
      `security_options` also lists `apparmor=monkeymaxxing-app-containers`.
    - **No capabilities.** `CapEff`, `CapPrm`, and `CapBnd` are all
      `0000000000000000`, and `capabilities_dropped` lists `all`.
    - **No new privileges.** `NoNewPrivs:` is `1`, and `security_options`
      lists `no-new-privileges`.
    - **A read-only root file system.** `read_only_root` is `true`. Only
      `/tmp`, `/run`, `/dev`, and the app's
      `writable_temporary_directories` are writable, and those are memory
      only.
    - **The user, with the mapped range.** `user_namespace` is not `host`.
      `/proc/$PID/uid_map` and `gid_map` each have one line: `0`, then a
      high server user ID (about 2 billion, from the `containers` range in
      `/etc/subuid`), then `1024`. So root in the container is a user with
      a high ID on the server. The `Uid:` line in `/proc/$PID/status`
      shows that same high ID, never `0`. The container's user ID `0` maps
      to a different range for each container; two containers sharing a
      first range is a failure.

    Record which containers were checked. A container that fails any line
    is a finding: its Quadlet file in `/etc/containers/systemd/` differs
    from the template, so run `every_server` and check again.

### Disruptive checks

Ask first, as the introduction of this section says.

1. **The desk's login protections.** Each test below is a failed login, and
   each failed login counts toward the lockout of the laptop. The lockout
   settings are `phone_code_lockout` in `mmx_project_settings.yml`. Keep
   the number of failed logins below `wrong_codes_before_lockout`, except
   in the lockout test.
   - A login with the laptop key alone and no phone code is refused after
     the phone code is enrolled.
   - A login with a phone code that was already used is refused. Each code
     works for one login only.
   - A login with a phone code and no laptop key is refused.
   - **The lockout test.** Enter `wrong_codes_before_lockout` wrong codes in
     a row. The laptop is locked out and sees "connection refused", even
     with a correct code, for `lockout_minutes` minutes. After the lockout
     ends by itself, a fresh code logs in. Run the lockout test when the
     person does not need the desk during the lockout.
2. **The wrong-code alert.** Enter fewer wrong codes than
   `wrong_codes_before_lockout`. MMHotline opens one incident, not one per
   attempt. The incident records the count of the first reading and does
   not change with later attempts. One wrong code is an `info` alert. A
   lockout sends an alert with the severity that
   `alert_severity_when_a_laptop_is_locked_out` sets. Tell the person
   before the test which severity rings the phone.
3. **A reboot keeps the private door.** Reboot the systems desk. After the
   reboot, `wg0` is up before the SSH service accepts logins, and a login
   with the laptop key and a fresh phone code succeeds. The desk is
   unavailable for a few minutes and its coding agent sessions end, so
   agree on a time first.
4. **Stopping Caddy takes the connector out of the tunnel.** On one app
   server, stop Caddy:
   `./server_management_scripts/run_mmx_on_util01 run-command --nodes app001 -- systemctl stop caddy`.
   Cloudflare's API stops listing a connector of the `apps` tunnel on that
   server
   (`GET http://127.0.0.1:8082/accounts/ACCOUNT_ID/cfd_tunnel/TUNNEL_ID/connections`
   through the API proxy, with `ACCOUNT_ID` from `vars.cloudflare_account_id`),
   so Cloudflare stops sending requests to a server that cannot answer.
   Start Caddy again with `systemctl start caddy`, and the connector comes
   back. With one app server, the site is down while Caddy is stopped, so
   run this check at the quiet time the person chose.
5. **A hand change raises a server settings comparison alert.** Change one harmless managed file
   on one server by hand, such as a comment line in a file that MMX writes.
   [The rules](../AGENTS.md#the-rules) allow this test change. Start the
   server settings comparison on `util01`: `sudo systemctl start compare_every_server_with_the_repository`.
   The check must report the change, and the alert must reach MMHotline.
   Then run `every_server` to put the file back, and check that the alert
   closes.
6. **A capacity warning reaches the triage agent.** From `util01`, send a
   test warning that names a pool's capacity trigger, such as "The app
   servers' CPU is above the limit (test)", with
   `mmwatchdog send-notice --alert-severity warn`. The triage agent must
   read the recorded readings of the past week and propose the operating
   procedure that the trigger names, such as
   [Add an app server](add_an_app_server.md), ready for approval. Close the
   test incident afterward.
7. **The hub-outage alerters alert when `util01` goes silent.** MMWatchdog's fleet
   hub stops for about 200 seconds: by default a hub-outage alerter alerts
   once its reports to the hub fail for 2 minutes
   (`alert_after_hub_unreachable_for` in
   `roles/util_server/files/mmwatchdog_node_settings.yml`), plus a report
   interval of 30 seconds. The alert goes to the whole
   Pushover group, so everyone who can be on call hears the alert. Before
   the stop, read the two hub-outage alerters' names with `sudo mmwatchdog fleet`
   on `util01`. Stop the hub with
   `./server_management_scripts/run_mmx_on_util01 run-command --nodes util01 -- systemctl stop mmwatchdog`.
   Both hub-outage alerters, an app server and a database server, must send the
   alert that the hub is unreachable straight to the push app. Start the
   hub again, and check that the hub's alerts recover and that no hub-outage
   alerter has a delivery waiting.
8. **The MMHotline-down alarm alerts when MMHotline goes silent.** The outage test
   stops MMHotline and wakes the person on call. Follow the steps of
   [Test the alarm for a silent MMHotline](test_the_alarm_for_a_silent_mmhotline.md#steps).
   The setup keeps the short test, `mmhotline down-alarm send-test`, which
   proves that the MMHotline-down alarm's notification reaches the phone.

When every check that the person asked for has run, tell the person which
checks passed, which failed, and which the person skipped. Record each
skipped check, with the reason, in `last_result` of `optional_protection_checks`.

### Why these checks are optional

The Stack's own tests prove how the Stack's software behaves. The setup
therefore checks only what is specific to the team: the team's accounts,
keys, domain, phone, and data. This section shows that the protections
also hold on the team's own servers. A team that skips this section still
has a system that the Stack's tests already proved.
