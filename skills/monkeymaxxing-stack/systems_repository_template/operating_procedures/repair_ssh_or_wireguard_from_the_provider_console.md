# Repair SSH or WireGuard from the provider console

**When to use this page:** SSH to a server fails from every desk and from
`util01`, or MMX cannot reach a server, while the server still runs at the
provider. A server that cannot boot at all uses
[Replace a server](replace_a_server.md).

**What this page does:** the person repairs the server's WireGuard,
firewall or sshd settings by hand at the provider's console, and then MMX
puts back the settings from the systems repository.

**Who acts:** the person types the commands at the provider's console, and
runs `sudo wg show wg0 latest-handshakes` in the person's own desk terminal.
The coding agent gives the commands one at a time, reads what the person
reports, and chooses the next one. The coding agent runs the desk check in
step 0, the [rescue system](#rescue-system-instead-of-a-console-login) without
a person, and the `every_server` run in step 5. The examples use `app001`
at `10.20.1.1`: use the server's own `private_ip` from
`inventories/servers.yml` in its place.

**This page is an exception to "Never change a server by hand"** in
[The rules](../AGENTS.md#the-rules). Reason: MMX cannot reach the server,
so only a hand repair at the console can, and step 5 then puts the
repository's settings back.

**Tell the person before work:**

> SSH to app001 fails, so I cannot reach it the usual way. You log in at the server provider's console,
> which works without the network, and type a few commands I give you. Each hand repair is temporary:
> once MMX reaches app001 again, MMX puts back the settings from the systems repository.

**Terms:** this page uses the Stack's terms, such as provider console,
WireGuard, inventory and desk that keeps access.
[Technical terms](../talking_with_the_team.md#technical-terms) explains each
term. sshd is the SSH server's program. A peer is another machine in
WireGuard's list, with its public key and its private address. The
**rescue system** is a small system that boots from the provider's network,
with the server's disk attached and nothing of the server's own running.

## Choose the route

Start with [step 0](#0-check-the-desk-first). Its result chooses the route:

| Step 0 shows | The fault is | Follow |
| --- | --- | --- |
| SSH works after the desk's peers are updated | the desk's peers | Nothing more: the server needs no repair |
| The server's key shows a handshake in the last two minutes, but SSH fails | the server's firewall or sshd | [Step 1](#1-log-in-at-the-providers-console), [step 3](#3-the-firewall), [step 4](#4-sshd), then [step 5](#5-put-the-repositorys-settings-back). For sshd's files only, the [rescue system](#rescue-system-instead-of-a-console-login) can replace steps 1 to 4. The firewall needs a console that shows the running system, with a person at it where the provider's console needs one: the rescue system cannot repair the firewall |
| The server's key shows no recent handshake | WireGuard, on either side | [Step 1](#1-log-in-at-the-providers-console), [step 2](#2-wireguard), [step 3](#3-the-firewall) when step 2 sends you there, then [step 5](#5-put-the-repositorys-settings-back). WireGuard, too, needs a console that shows the running system |
| The server cannot boot at all | the server | [Replace a server](replace_a_server.md) |

## Before you start

- **If a commit of the repository caused the failure, the coding agent
  first commits the correction and pushes,** as
  [Making a change](../AGENTS.md#making-a-change) says.
  Reason: step 5's `every_server` run applies pushed `main`, so without
  the correction it would put the bad setting back.
  **Check:** Git accepts the push, as step 4 of Making a change says.
- **The server still runs at the provider.** The provider's website shows
  the server running.
- **The person can read the shared root console password.** It is the
  recovery bundle's item `shared_root_console_password`, which the person
  reads in their own terminal as
  [Read an item from the recovery bundle](rebuild_a_systems_desk.md#read-an-item-from-the-recovery-bundle)
  says, never in the chat. After
  [a rotation](rotate_a_secret.md#the-shared-root-console-password), the
  password manager item `Shared root console password` holds the current
  password instead. The password works only at the
  console, never over SSH.
- **Know which way in the provider gives.** Some consoles show the running
  system and take a login (step 1; steps 2 to 4 work there as written).
  Others, such as Hetzner Cloud's, need a person at the browser console, and
  the coding agent can use the rescue system instead. The provider guide's
  section "Console and rescue access" says which:
  [Hetzner Cloud](../provider_guides/hetzner_cloud.md#console-and-rescue-access),
  [DigitalOcean](../provider_guides/digitalocean.md#console-and-rescue-access),
  [Vultr](../provider_guides/vultr.md#console-and-rescue-access),
  [Scaleway](../provider_guides/scaleway.md#console-and-rescue-access),
  [OVHcloud](../provider_guides/ovhcloud_public_cloud.md#console-and-rescue-access),
  [AWS EC2](../provider_guides/aws_ec2.md#console-and-rescue-access),
  [Google Compute Engine](../provider_guides/google_compute_engine.md#console-and-rescue-access).

## 0. Check the desk first

1. **The coding agent, on the desk, in its checkout, makes the desk's peers
   match the inventory and tries SSH again:**

   ```sh
   sudo -n update-this-desks-wireguard-peers
   ssh -F ssh/config -o ConnectTimeout=5 root@10.20.1.1 true
   ```

   **Check:** when `ssh` prints nothing and ends without an error, SSH works
   again and the server needs no repair. When SSH still fails, go on with
   step 0.2.

2. **The person reads WireGuard's handshakes,** in the person's own desk
   terminal, which can read WireGuard's state:

   ```sh
   sudo wg show wg0 latest-handshakes
   ```

   Each line is a peer's public key and the time of its last handshake, in
   seconds since 1970; `0` means never. `date +%s` prints the time now in
   the same unit, so a handshake in the last two minutes is a time less
   than 120 below it. The server's key is the server's
   `wireguard_public_key` in `inventories/servers.yml`.
   **Check:**
   - The server's key shows a handshake in the last two minutes, but SSH
     fails: the fault is the server's firewall or sshd. Go to step 1, then
     steps 3 and 4.
   - The server's key shows no recent handshake: the fault is WireGuard on
     either side. If a run of MMX changed the server's WireGuard settings
     just before, wait two minutes and run step 0 again: MMX puts the
     earlier WireGuard settings back by itself when its run does not confirm
     the change in time. Otherwise go to step 1, then step 2.

## 1. Log in at the provider's console

1. **The person opens the server in the provider's website and logs in as
   `root`** with the shared root console password (the recovery bundle's
   item, or the password manager item after a rotation).
   The console's place in the website is in the provider guide's section
   "Console and rescue access" ([Before you start](#before-you-start) links
   each guide).
   **Check:** the console shows a root shell prompt. When the provider's
   way in is the rescue system, follow
   [Rescue system instead of a console login](#rescue-system-instead-of-a-console-login)
   instead.

2. **Type each command carefully.** A console often cannot paste: compare
   long values, such as keys, with `wg show` before going on.
   **Check:** none, because this is how to type the later steps' commands.

## 2. WireGuard

Steps 2 and 3 run on the running system, at a console that shows it; the
rescue system cannot run them.

1. **See the interface:**

   ```sh
   systemctl status wg-quick@wg0 --no-pager
   wg show wg0
   ```

   **Check:** the status says active, and `wg show wg0` lists the desk's
   peer with a recent handshake. Otherwise:
   - **`wg0` is down** (`inactive` or `failed`): steps 2.2 and 2.3.
   - **The desk's peer is missing** from `wg show wg0`, or has wrong
     allowed IPs: step 2.4.
   - **The peer is there but shows no handshake:** step 2.5.
   - **`wg show wg0` shows a listening port other than the inventory's
     `vars.wireguard_listen_port`** after a run that changed the port:
     step 2.6.

2. **When `wg0` is down, read why, then start it:**

   ```sh
   journalctl -u wg-quick@wg0 -n 30 --no-pager
   systemctl restart wg-quick@wg0
   ```

   **Check:** `systemctl status wg-quick@wg0 --no-pager` says active. Then
   do step 2.3.

3. **Compare the server's WireGuard key with the inventory:**

   ```sh
   wg pubkey < /etc/wireguard/wg0.private_key
   ```

   **Check:** the printed key equals the server's `wireguard_public_key` in
   `inventories/servers.yml`. A different key means the server or the
   inventory changed; stop and tell the person.
   Reason: the desks and the other servers trust only the inventory's key.
   MMX writes `/etc/wireguard/wg0.conf`, with the server's private key as
   the `PrivateKey` line, from the key in `/etc/wireguard/wg0.private_key`,
   which the first boot wrote.

4. **When the desk's peer is missing or has wrong allowed IPs, add the desk
   that keeps working as a peer by hand,** with the desk's
   `wireguard_public_key`, `private_ip` and `public_ipv4_address` from
   `inventories/servers.yml`:

   ```sh
   wg set wg0 peer 'DESK_WIREGUARD_PUBLIC_KEY' allowed-ips 10.20.9.1/32 endpoint 203.0.113.9:51820 persistent-keepalive 25
   wg show wg0
   ```

   **Check:** `wg show wg0` lists the desk's peer with the desk's allowed
   IPs. The peer lasts until `wg0` restarts. The route to the desk already
   exists, because `wg0`'s address covers the whole private network
   (`Address = 10.20.1.1/16` in `wg0.conf`).

5. **When the peer is there but shows no handshake, check WireGuard's
   port.** The firewall must admit WireGuard's port, UDP 51820, from
   anywhere ([step 3](#3-the-firewall)). Peers send to UDP 443, and
   `wireguard-udp-443-redirect.service` redirects it to 51820.
   **Check:** `systemctl status wireguard-udp-443-redirect.service` must say
   active, and `nft list table inet stack_wireguard_port` must show the
   redirect. When the service is not active, start it with
   `systemctl start wireguard-udp-443-redirect.service` and check again.
   When the firewall lacks the 51820 rule, go to step 3.

6. **When `wg0` still listens on its earlier port after a run that changed
   the port, set the target port.** A run that changes WireGuard's port
   reloads `wg0` under MMX's restore-unless-confirmed protection. When the
   machine does not confirm within two minutes, MMX restores the earlier
   `wg0.conf`, which listens on the earlier port while the redirect already
   sends UDP 443 to the new one, so the tunnel stays down. In
   `/etc/wireguard/wg0.conf`, set `ListenPort` to the inventory's
   `vars.wireguard_listen_port`, 51820 unless the inventory says otherwise,
   then run `systemctl restart wg-quick@wg0`.
   The firewall already admits the new port, because the run changes the
   firewall before `wg0`. The restart also forgets the old UDP 443 flows:
   the drop-in `forget_udp_443_flows_after_a_port_change.conf` runs
   `conntrack -D` after `wg-quick@wg0` starts.
   **Check:** `wg show wg0 listen-port` prints the inventory's port, and the
   desk's `sudo wg show wg0 latest-handshakes` shows a recent handshake with
   the server. Step 5's run then puts the repository's settings back.

## 3. The firewall

1. **See the firewall's rules:**

   ```sh
   ufw status verbose
   ```

   **Check:** the rules include `22/tcp on wg0 ALLOW IN 10.20.9.0/24`, the
   systems desks' block (`private_ip_ranges.systems_desks`), the same from
   `util01`'s address, and `51820/udp ALLOW IN Anywhere` for WireGuard.
   When a rule is missing, do step 3.2.

2. **Add a missing rule by hand:**

   ```sh
   ufw allow in on wg0 from 10.20.9.0/24 to any port 22 proto tcp
   ufw allow 51820/udp
   ```

   When the rule from `util01` is missing, add it the same way, with
   `util01`'s private address (`10.20.0.1` in the examples):
   `ufw allow in on wg0 from 10.20.0.1 to any port 22 proto tcp`.
   **Check:** `ufw status verbose` shows the rule.

## 4. sshd

In the rescue system, run these as file edits under `/mnt/root` with
`chroot /mnt/root`, as [the rescue system](#rescue-system-instead-of-a-console-login)
shows.

1. **See sshd's state, its settings and root's keys:**

   ```sh
   sshd -t
   systemctl status ssh --no-pager
   sshd -T | grep -i -E '^(allowusers|permitrootlogin|passwordauthentication) '
   cat /etc/ssh/sshd_config.d/00-incident-lockout.conf
   cat /root/.ssh/authorized_keys
   ```

   **Check:** `sshd -t` prints nothing, `/etc/ssh/sshd_config.d/00-incident-lockout.conf`
   holds only its comment line (or, during a lock-out, the `AllowUsers` line
   of step 4.3), and `/root/.ssh/authorized_keys` holds the desk's key.
   Otherwise do the step below that matches.

2. **When `sshd -t` prints the file and line of a setting sshd refuses,
   correct that line.**
   **Check:** run `sshd -t` again until it prints nothing, then
   `systemctl restart ssh`.

3. **Remove a leftover `AllowUsers` line outside a lock-out.**
   `/etc/ssh/sshd_config.d/00-incident-lockout.conf` holds an
   `AllowUsers root@10.20.9.1` line only during a lock-out, while
   `everyone_locked_out_except_desk` is set in `inventories/servers.yml`
   ([Respond to a break-in](respond_to_a_break_in.md)): then only the desk
   that keeps access, from its own address, gets in, which is correct, so
   leave the line. Without a lock-out the file holds only its comment line,
   and a leftover `AllowUsers` line is removed with:

   ```sh
   printf '# Managed by MMX. Empty while normal access is restored.\n' > /etc/ssh/sshd_config.d/00-incident-lockout.conf
   sshd -t && systemctl reload ssh
   ```

   **Check:** `sshd -t` prints nothing, and
   `cat /etc/ssh/sshd_config.d/00-incident-lockout.conf` shows only the
   comment line.

4. **When the desk's key is missing from `/root/.ssh/authorized_keys`, add
   the desk's line from `mmx_project_settings.yml` at the end of the file,
   typed exactly.** The file holds each key of `root_ssh_public_keys` in
   `mmx_project_settings.yml`, or, during a lock-out, only the desk's
   `production_ssh_public_key` behind `from="10.20.9.1"`.
   **Check:** `cat /root/.ssh/authorized_keys` shows the desk's line, equal
   to the line in `mmx_project_settings.yml`.

## 5. Put the repository's settings back

Every hand change above is temporary. Once SSH from the desk works, MMX
replaces the hand repair with the repository's settings: a hand peer, a hand
firewall rule and a hand key line go, and the repository's own come back.

1. **When a commit caused the failure, check that the correction is
   pushed** ([Before you start](#before-you-start)).
   **Check:** `git log origin/main` shows the correction.

2. **The coding agent runs `every_server`:**

   ```sh
   ./server_management_scripts/run_mmx_on_util01 run every_server
   ```

   During a lock-out, or while `util01` cannot reach the server, the coding
   agent runs from the desk instead:
   `sudo -n -u servers-mmx run-mmx-on-the-servers run every_server --connection ssh_only`.
   Run the whole of `every_server`, without `--limit`.
   Reason: MMX refuses `--limit app001`, because the server's MMWatchdog
   stage reads the join code that a stage on `util01` reads first.
   **Check:** the run ends without a failed server.

3. **Verify** with a fresh `ssh -F ssh/config root@10.20.1.1 true` from the
   desk, and on the server `wg show wg0 allowed-ips` and `ufw show added`.
   **Check:** the SSH command works, and the two server commands list the
   inventory's peers and rules again.

4. **Check that the server does its pool's work again:**
   `ssh -F ssh/config root@10.20.1.1 check-that-this-server-does-its-work`.
   **Check:** the command exits 0. Otherwise it prints one line for each
   part that fails. For a database server, which this command does not
   check, run on `util01`
   `sudo -u postgres pg_autoctl show state --pgdata /var/lib/postgresql/17/pg_auto_failover_monitor --formation production`:
   the server's line shows `primary` or `secondary` in both state columns.

## Rescue system instead of a console login

Use this when the provider's rescue system is the way in (see the provider
guide's "Console and rescue access"), for sshd's files only. The coding
agent can do it over SSH, without a person at a console.
Do not use a rescue system for `wg0` or the firewall.
Reason: the server's WireGuard and firewall are not running there, so only
file repairs work, and step 4's file repairs are the ones that fit.

1. **Enable the rescue system and reset the server** through the provider's
   API.
   **Check:** the server's public address answers SSH as `root` (Hetzner
   Cloud's answered about 37 seconds after the reset). Connect there.

2. **Find the server's root disk** with `lsblk -f`.
   **Check:** `lsblk -f` shows which partition is the server's root disk.
   The commands below use `/dev/sda1`; use the partition that `lsblk -f`
   shows.

3. **Mount the server's disk and test sshd's settings:**

   ```sh
   mkdir -p /mnt/root
   mount /dev/sda1 /mnt/root
   for d in dev proc sys; do mount --bind /$d /mnt/root/$d; done
   mkdir -p /mnt/root/run/sshd
   chroot /mnt/root sshd -t
   ```

   The server's own commands, such as `sshd`, exist only inside
   `chroot /mnt/root`, and `sshd -t` needs the `/run/sshd` directory that
   `mkdir -p` makes above.
   **Check:** `sshd -t` prints nothing, or the file and line to repair.
   "Missing privilege separation directory: /run/sshd" means the
   `mkdir -p /mnt/root/run/sshd` line did not run.

4. **Make the file repairs of [step 4](#4-sshd) under `/mnt/root`,** for
   example remove the bad line or file in `/mnt/root/etc/ssh/sshd_config.d/`,
   or fix `/mnt/root/root/.ssh/authorized_keys`.
   **Check:** run `chroot /mnt/root sshd -t` until it prints nothing.

5. **Unmount the disk and reboot:**

   ```sh
   for d in sys proc dev; do umount /mnt/root/$d; done
   umount /mnt/root
   sync
   reboot
   ```

   The server boots from its own disk. The whole repair took 72 seconds on
   Hetzner Cloud, from the break to a working SSH from the desk.
   **Check:** SSH from the desk works. When it does not, see
   [If something is different](#if-something-is-different).

6. **Go on with [step 5](#5-put-the-repositorys-settings-back).**

## If something is different

- **If a run of MMX changed the server's WireGuard settings just before,**
  wait two minutes before the console: MMX puts the earlier WireGuard
  settings back by itself when its run does not confirm the change in time.
- **If the server's public key differs from the inventory's,** stop and
  tell the person (step 2.3).
- **If the fault was in WireGuard or the firewall, not in a file you can
  read, after the rescue system,** boot the server, then use steps 2 and 3
  from a console that shows the running system, or
  [Replace a server](replace_a_server.md).
- **If the server cannot boot at all,** follow
  [Replace a server](replace_a_server.md).
- **During a lock-out,** the `AllowUsers` line and the single desk key are
  correct; leave them (steps 4.3 and 4.4).

## Why one server can lock everyone out

SSH works only inside WireGuard, so a broken WireGuard interface, a
firewall rule, or sshd's settings can each lock everyone out of one server.
The provider console works without the network, so the person can log in
there as root and repair them.

MMX's firewall rules admit SSH only on `wg0`, from the systems desks' block
and from `util01`'s address. The redirect turns the peers' UDP 443 into
51820 before the firewall sees it, so the firewall admits 51820, not 443.
