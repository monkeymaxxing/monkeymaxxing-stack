# Add load-balancer servers

Read [the systems repository rules](../AGENTS.md#the-rules) first.

**When:** the pool reaches about 20 app servers, or the app servers warn about network use.
About 20 is a fixed guide, not a setting: one Cloudflare tunnel takes at most 25 connectors, and each
app server runs one until the load-balancer servers take over.

**What this page does:** `lb01` and `lb02` take over the tunnel connector (`cloudflared`) and Caddy from the app servers.
These load-balancer servers receive requests from Cloudflare and send them to app servers.
`lb01` and `lb02` use the app servers' existing `example_systems-apps` tunnel.
DNS does not change.

**Who acts:** you, the coding agent, do every step from the systems desk.
The person on call hears about the shutdown test in step 6. A failed
load-balancer server can be replaced by the triage agent
([If something is different](#if-something-is-different)).

**Terms:** this page uses the Stack's terms, such as pool, tunnel
connector, Caddy and fleet hub.
[Technical terms](../talking_with_the_team.md#technical-terms) explains
each term.

## Choose the route

| Situation | Follow |
| --- | --- |
| No load-balancer server yet | [Adding load-balancer servers](#adding-load-balancer-servers): add `lb01` and `lb02`, then turn on `tunnel_connector_and_caddy_run_only_on_the_load_balancer_servers` |
| The team wants the app servers to bring the requests in again | [The way back](#the-way-back) |
| A load-balancer server stops reporting | [If something is different](#if-something-is-different) |

## Before you start

- **The shared server steps are in [Add a server](add_a_server.md).**
- **Size:** create `lb01` and `lb02` at least the size of an app server.
  Give each load-balancer server a network port at least as fast as an app
  server's. [Why the size matters](#why-the-size-matters) says why.
- **Read each MMX run's output** with `./server_management_scripts/run_mmx_on_util01 results` from the desk.
- **A push alone changes no server.** Apply each configuration change as
  [Making a change](../AGENTS.md#making-a-change)
  says: a push alone changes no server, so run `every_server` or the playbook the step names.

## Adding load-balancer servers

Users see no change during the move in steps 1 to 4: app servers keep
receiving requests until MMX applies the setting in step 4.

1. **Create `lb01` and `lb02`** and add the load-balancer servers to
   `inventories/servers.yml`, following steps 1 to 5 of
   [Add a server](add_a_server.md).
   Use the chosen network's server group 4 addresses. The examples use 10.20.
   For `lb01`, use `private_ip` `10.20.4.1` and `https_address` on
   `10.20.4.1`. For `lb02`, use `private_ip` `10.20.4.2` and
   `https_address` on `10.20.4.2`.
   In the inventory group `load_balancer_servers`, set
   `nodes: [lb01, lb02]`. The group's flag `is_load_balancer_server` is
   already in the group's `vars`.
   Each server joins WireGuard at first boot with a setup-generated key.
   The first configuration run adds the app-server peers and configures
   Caddy and the connectors. Private-network stages must pass.
   Nothing changes for users while the new connectors are being prepared.

   **Check:** the checks of steps 1 to 5 of [Add a server](add_a_server.md).

2. **Verify enrollment and reboot `lb01` and `lb02`** with steps 6 and 7
   of [Add a server](add_a_server.md).
   After the app servers' stage, the run configures one load-balancer server at a time.
   On each load-balancer server, Caddy lists every app server's live web
   container.
   A load-balancer server's tunnel connector joins the tunnel once each
   app answers through Caddy on the load-balancer server.

   Only after the tunnel connector joins does the load-balancer server
   being configured join MMWatchdog's fleet hub on `util01`.
   The new load-balancer server's connector and Caddy checks pass from
   the start, without sending a warning.
   App servers and both load-balancer servers now receive requests.
   Every deploy also changes Caddy's destination list on `lb01` and
   `lb02` to the new release's web containers.

   **Check:** the check of step 6 of [Add a server](add_a_server.md). Step 3
   checks the connectors and Caddy.

3. **Check that the pair is ready to carry the requests,** before anything
   leaves the app servers.

   **Check:**
   - On `lb01` and `lb02`,
     `ssh -F ssh/config root@10.20.4.1 'mmwatchdog check-now tunnel_connector_and_caddy'`
     exits 0: the checked load-balancer server's tunnel connector holds a
     connection to Cloudflare, and each app answers through Caddy on the
     checked load-balancer server.
     For each load-balancer server, replace the example SSH address with
     the server's `address` in `inventories/servers.yml`.
   - On `lb01` and `lb02`, `/etc/caddy/Caddyfile` lists every app server's
     private address
     (`ssh -F ssh/config root@10.20.4.1 cat /etc/caddy/Caddyfile`).
   - Cloudflare lists `lb01` and `lb02` as connectors of the `example_systems-apps` tunnel,
     alongside the app servers.
     Check the tunnel's page in Cloudflare's dashboard, or use the API with this desk's token.
     In the code block below, the first command prints the tunnel's ID.
     Put the tunnel ID printed by the first command in place of
     `TUNNEL_ID` in the second command.
     The second command prints the address each connector uses to reach Cloudflare.
     If a load-balancer server has IPv6, Cloudflare can report the
     connector's address as the load-balancer server's IPv6 address rather
     than `vars.public_ipv4_address` in the inventory.
     For the connector on `lb01`, the following command prints `lb01`'s
     IPv6 addresses:
     `ssh -F ssh/config root@10.20.4.1 'ip -brief -6 address show scope global'`.

     ```sh
     # The coding agent, on the systems desk; ACCOUNT_ID is vars.cloudflare_account_id.
     curl -fsS "http://127.0.0.1:8082/accounts/ACCOUNT_ID/cfd_tunnel?name=example_systems-apps&is_deleted=false" |
       jq -r '.result[0].id'
     curl -fsS "http://127.0.0.1:8082/accounts/ACCOUNT_ID/cfd_tunnel/TUNNEL_ID/connections" |
       jq -r '[.result[].conns[].origin_ip] | unique[]'
     ```

     The API proxy adds the person's token, so the coding agent never
     reads the token.

4. **Turn the setting on:** set `tunnel_connector_and_caddy_run_only_on_the_load_balancer_servers`
   to `true` in `mmx_project_settings.yml`. Commit and push.
   The run first repeats step 3's MMWatchdog checks on each load-balancer
   server.
   Then, on every app server at once, `cloudflared` lets unfinished requests finish and leaves the tunnel.
   Cloudflare sends every new request to the pair.
   The run removes Caddy, the Caddy and `cloudflared` packages, and the
   Caddy and `cloudflared` apt repositories from the app servers.
   Only after removing Caddy and `cloudflared` does the MMX run stop app
   servers peering with each other.
   The app servers' firewalls now allow traffic to web ports only from
   the load-balancer servers.

   **Check:** the run passes; step 5 verifies the result. When a
   load-balancer server fails its checks, or the run refuses the setting,
   see [If something is different](#if-something-is-different).

5. **Verify.**

   **Check:**
   - Cloudflare lists only `lb01`'s and `lb02`'s addresses for the tunnel
     (step 3's second command), and no app server's.
   - On each app server, `systemctl is-active cloudflared caddy` reports
     neither as active, and `grep -A1 '^\[Peer\]' /etc/wireguard/wg0.conf`
     names its WireGuard peers: the database servers, `util01`, `lb01`, and
     `lb02`, and every systems desk, with no app-server peer.
   - Each app answers at its public host name.

6. **Each load-balancer server carries every request alone.** Test `lb01`
   and `lb02`, in a quiet hour after step 5:
   shut down each load-balancer server in turn, and check that the other load-balancer server carries every request.
   Shutting down each load-balancer server in turn tests a planned
   handover, as during a reboot.
   A server shutting down lets its connector finish unfinished requests and leave the tunnel.
   A server that dies loses its unfinished requests.

   1. On `lb01` and `lb02`,
      `mmwatchdog check-now tunnel_connector_and_caddy` exits 0.
      Tell the person on call: `util01`'s fleet hub warns when a
      load-balancer server goes silent.
   2. On the systems desk, ask each app's health URL at its public host name
      1,200 times, once a second, which takes 20 minutes or a little more,
      long enough to cover both shut-downs and restarts below,
      counting the answers by status, such as
      `for i in $(seq 1200); do curl -s -o /dev/null -w '%{http_code}\n' --max-time 5 https://shop.example.com/up; sleep 1; done | sort | uniq -c`.
   3. While the loop runs, read how many requests the connectors on
      `lb01` and `lb02` received.
      Read each count twice, a minute apart.
      Above a million, the count prints in exponent form, such as a number multiplied by a power of ten.
      `awk` reads the connector's request count as a number:
      `ssh -F ssh/config root@10.20.4.1 "curl -s http://127.0.0.1:20241/metrics | awk '\$1 == \"cloudflared_tunnel_total_requests\" {printf \"%.0f\\n\", \$2}'"`,
      and the same on `10.20.4.2`. Cloudflare decides by itself how to
      split the requests, so one count or both counts may rise.
   4. Shut down `lb01`: `ssh -F ssh/config root@10.20.4.1 systemctl poweroff`.
      Read `lb02`'s count twice again, a minute apart: `lb02`'s count rises
      by about the loop's requests.
   5. Start the shut-down server again at the server provider, from its
      console or its API. On the restarted load-balancer server, the
      connector starts with Caddy and joins the tunnel.
      Wait until `mmwatchdog check-now tunnel_connector_and_caddy`
      exits 0 on the restarted load-balancer server.
   6. Shut down `lb02`, check that `lb01`'s count rises by
      about the loop's requests, and start `lb02` again as in test substep 5
      above.
   7. The loop counts only 200s. When the loop counts another status, start
      any shut-down load-balancer server again as in test substep 5, and
      find the cause before step 7. Each load-balancer server's CPU stayed
      under 70%, and network use stayed under 600 Mbit/s in each direction:
      the limits of the `load_balancer_server_capacity` checks, whose reasons
      are beside them in `mmwatchdog_checks/load_balancer_servers.yml`.
      Read the capacity measurements on `util01`:
      `mmwatchdog fleet readings lb01 load_balancer_server_capacity --last 30m`,
      and the same for `lb02`.

   **Check:** test substep 7: the loop counted only 200s, and the CPU and
   network readings stayed under their limits.

7. **The checklist item `load_balancer_servers`:** `done`, with
   `verified_at` and the counts of step 6 in `last_result`: each app's
   status counts, and each connector's counts before the shutdowns and
   while each load-balancer server served alone.

   No check of its own: the item records step 6's results.

## The way back

1. **Turn the setting off:** set `tunnel_connector_and_caddy_run_only_on_the_load_balancer_servers`
   back to `false`. Commit and push.
   The run restores app servers' peering.
   After the app servers' stage, the MMX run restores Caddy and the app
   servers' tunnel connectors, one app server at a time.
   Each app server's connector joins the tunnel once each app answers through
   Caddy on the app server joining the tunnel.

   **Check:** the run passes. `util01`'s run stops at the first app server whose connector fails, so a
   passed run restored every app server.

2. **Check one app server.**

   **Check:**
   `ssh -F ssh/config root@10.20.1.1 'systemctl is-active cloudflared caddy; cat /etc/caddy/Caddyfile'`
   prints `active` twice and a Caddyfile listing every app server's private address.
   Cloudflare lists the app server's address for the tunnel again (step 3's second command).
   The check group `tunnel_connector_and_caddy` in step 3 belongs only to load-balancer servers.
   On an app server, `mmwatchdog check-now` refuses the
   `tunnel_connector_and_caddy` check group.

3. **Remove the load-balancer servers.** Run `remove_server` for each load-balancer server
   ([Remove a server](remove_a_server.md)).

   **Check:** each `remove_server` run passes.

4. **Delete and destroy `lb01` and `lb02`.**
   Delete `lb01` and `lb02` from the inventory.
   Delete `lb01`'s and `lb02`'s lines from `ssh/known_hosts`.
   Push, then destroy `lb01` and `lb02`.

   **Check:** verify as
   [Remove a server](remove_a_server.md) says.

5. **The checklist:** set the checklist item `load_balancer_servers` back to
   `waits_for_its_trigger`, with its `trigger` from the template.

   **Check:** `mmx validate` passes.

## If something is different

- **A load-balancer server fails its checks in step 4:** if a load-balancer server fails its checks, every app server keeps its connector, Caddy, and peering.
  The run fails and names the load-balancer server whose checks failed.
  Fix the fault reported by the load-balancer server's checks.
  Then push a commit or run `./server_management_scripts/run_mmx_on_util01 run every_server`.
  Verify the new run's result and confirm the affected MMWatchdog check.
  A push alone does not rerun the failed operation.
- **The run refuses step 4's setting:** the run refuses the setting while `load_balancer_servers` holds no server.
- **A load-balancer server that stops reporting** is replaced by the three
  replacement playbooks, which the triage agent runs while
  `load_balancer_servers` is in
  `triage_agent_server_work.pools_whose_failed_servers_the_triage_agent_replaces`
  ([A failed server: the three replacement playbooks](replace_a_server.md#a-failed-server-the-three-replacement-playbooks)).
  The new server, such as `lb03` for `lb01`, joins the `example_systems-apps`
  tunnel with the same tunnel token from the vault, as `lb01` and `lb02` did,
  so it needs no change at Cloudflare. The failed server is powered off
  first, so its connector leaves the tunnel; Cloudflare tries another
  connector of the tunnel for a request whose connector fails.

## How the move works

This part explains the steps, for the reader who wants the reasons.

### What changes

`lb01` and `lb02` use the app servers' existing `example_systems-apps` tunnel and tunnel
token. Cloudflare and DNS need no change.
Each Caddy sends requests to every app server's web containers over WireGuard.

After the move, app servers run neither `cloudflared` nor Caddy and no
longer peer with each other.
The app servers' firewalls allow traffic to web ports only from the
load-balancer servers.

The pair uses `roles/tunnel_connector_and_caddy`, the role app servers and `staging01` have run since initial setup.
The new connectors join the tunnel alongside the app servers' connectors.
Each deploy changes every Caddy's destination list in the deployed
environment to the new release's web containers.

When the setting is turned on, the run first removes the app servers' connectors after letting their unfinished requests finish.
Only after removing the app servers' connectors does the MMX run stop app
servers peering with each other.
While an app server's connector receives requests, its Caddy must still reach every app server.

### Why the size matters

Cloudflare decides by itself how to split requests between the two
load-balancer connectors. Cloudflare may send every request to a single
connector. The load-balancer server running the chosen connector must
then be able to handle every request alone.
Every request Cloudflare cannot answer from its cache passes through the
receiving load-balancer server's network port.
