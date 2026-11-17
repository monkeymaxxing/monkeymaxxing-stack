# Remove a server

**When:** a person removes a server, including during a replacement; or
the app pool's load no longer needs one of its app servers.

**What this page does:** the server leaves service, then leaves the
inventory, the peers and the firewall rules, and then the provider
destroys it.

**Who acts:** you, the coding agent, run the commands from the systems
desk. A person chooses which server to remove and agrees to the destroy
in step 3. Database servers always need a person
([The rules](../AGENTS.md#the-rules)). For an app server that the load no
longer needs, the triage agent may run the playbook itself, as
[An app server the load no longer needs](#an-app-server-the-load-no-longer-needs)
says.

## Find your situation

| Situation | Follow |
| --- | --- |
| An app server that the load no longer needs | [An app server the load no longer needs](#an-app-server-the-load-no-longer-needs): the playbook comes first |
| Any other server, or an app server the person chooses, that MMX can reach over HTTPS or SSH | [Removing a server](#removing-a-server), from step 1, with `server_name` |
| A database server that is gone for good, such as a failed primary, or another server that no longer answers | [Removing a server](#removing-a-server), from step 2 |
| A server that the provider has already destroyed | [Removing a server](#removing-a-server), steps 2 and 4 |
| `util01` or `staging01` | `remove_server` refuses both: each is the only server of its kind, so it is replaced, never removed. Follow [Rebuild util01](rebuild_the_utility_server_util01.md) or [Replace staging01](replace_staging01.md) |

## Before you start

- **Check the limits on removing a server.** `remove_server` refuses
  each of these, so prepare first:
  - The only app server cannot be removed. Add the replacement app server
    first.
  - The database primary cannot be removed. Switch the primary first.
  - While only jobs servers run jobs, the last jobs server cannot be removed
    ([Adding jobs servers](add_jobs_servers.md#adding-jobs-servers)).
  - While only load-balancer servers bring requests in, the only
    load-balancer server cannot be removed. Add the replacement load-balancer
    server first.
- **Use `remove_server` to take a server out of service** before deleting
  its settings or destroying it.
- **A push alone changes no server.** Apply each configuration change as
  [Making a change](../AGENTS.md#making-a-change)
  says: a push alone changes no server, so run `every_server` or the playbook the step names.
- **After a push that adds, replaces or removes a server in the inventory,**
  also run `sudo -n update-this-desks-wireguard-peers`, so this
  desk's WireGuard peers match the servers
  ([Update the desk's production peers](../initial_setup/03_make_your_server_account_and_your_systems_desk.md#update-the-desks-production-peers)).
- **Without the provider scripts,** use the provider's own command-line tool, as
  [Without the provider scripts](../server_management_scripts/README.md#without-the-provider-scripts)
  says.

## An app server the load no longer needs

**An app server the load no longer needs: the playbook comes first,**
`remove_server` without `server_name`:

```sh
./server_management_scripts/run_mmx_on_util01 run remove_server
./server_management_scripts/run_mmx_on_util01 run every_server
```

**Check:** the playbook's last lines give the monthly price that stops,
or it says "nothing to remove" and why.

**What the playbook does.** Without `server_name`, `remove_server` removes
the newest app server when the smaller pool would have carried the
busiest readings of the last
`triage_agent_server_work.days_of_low_load_before_an_app_server_is_removed`
(7 by default) with a server to spare below
`cpu_percent_below_which_the_app_pool_can_spare_a_server` (50), by the same
rule as `util01`'s check `app_servers_to_remove_for_the_load`, and never
below `growth_limits.app_servers.smallest_number_of_servers`. It takes the
server out of service as step 1 below does. Then it does steps 2 and 3
itself, once every other app server does its work: one commit to `main`,
made by `util01` (pull before your next change), and the destroy by the
provider's ID, never by name. Its last lines give the monthly price that
stops. `every_server` then takes the server out of the peers and the
firewall.

**When it refuses:** it refuses while an app server does not report,
during an unfinished replacement, and for a pool of mixed server types;
otherwise it says "nothing to remove" and why.

**Who runs it:** with `what_the_triage_agent_may_do_without_a_person:
routine_fixes_and_server_work`, the triage agent runs both after
MMHotline's warning; with the other answers, the weekly review proposes
it.

## Removing a server

For any other server, or an app server the person chooses, follow the
steps below with `server_name`. For a server that MMX can reach over
HTTPS or SSH, start at step 1.

1. **Take the server out of service:**
   `./server_management_scripts/run_mmx_on_util01 run remove_server --var server_name=db02`.
   The playbook acts according to the server's role:

   - The playbook stops `cloudflared` on the app server, so the app server
     leaves the Cloudflare tunnel.
     The playbook also removes the app server from every list of web
     containers that Caddy sends requests to.
     Caddy uses the lists on the remaining app servers that run Caddy and
     on the load-balancer servers.
   - A database replica enters the failover monitor's maintenance state
     and leaves the formation.
   - A jobs server's job containers stop.
   - A load-balancer server leaves the tunnel once every remaining
     load-balancer server passes MMWatchdog's `tunnel_connector_and_caddy`
     checks.
     The checks confirm a connection to Cloudflare and an answer from
     each app through Caddy.

   **Check:** the run ends without failed work. A refusal names the limit
   from [Before you start](#before-you-start).
2. **Remove the server's saved settings.** Delete the server from the
   inventory and the server's line from `ssh/known_hosts`.
   Handle the server's one-time playbooks as
   [One-time playbooks that name the removed server](#one-time-playbooks-that-name-the-removed-server)
   says.
   Include the playbook moves, the inventory deletion, and the
   `ssh/known_hosts` deletion in one commit. Commit and push.
   `util01` applies the change with `every_server`.
   Peer lists and firewall rules no longer name the server.
   MMWatchdog's fleet hub on `util01` forgets the removed server and will not alert
   about the removed server's silence.
   **Check:** `mmx validate` passes before the push, and
   `grep -lw db02 one_time_playbooks/*.yml`, with the server's name, lists
   no playbook.
3. **Destroy the server** with `./server_management_scripts/destroy_a_server_at_the_provider`.
   Use `--server-name` with the server's inventory name, such as `db02`.
   No check here: step 4 checks the destroy.
4. **Verify:** `util01`'s `every_server` run for the commit passed.
   `./server_management_scripts/list_the_servers_at_the_provider` no longer lists the server.
   The dashboard's box for the removed server's pool shows the new count.

## If something is different

- **A database server that is gone for good, such as a failed primary:**
  skip `remove_server` in step 1.
  Start at step 2 to remove the database server's saved settings.
  After you push the step 2 commit, `util01` runs `every_server`.
  `every_server` removes the database server from the formation, the group
  managed by the failover monitor.
- **Another server that no longer answers:** also skip step 1:
  `remove_server` needs the server to answer.
- **The provider has already destroyed the server:** skip step 3 too.

## One-time playbooks that name the removed server

**Move one-time playbooks that name the removed server to
`one_time_playbooks/completed/`.**
Include the playbook moves in the commit that deletes the server from the
inventory.
`mmx validate`, and therefore every run, refuses unfinished playbooks that name a server missing from the inventory.
The requirement to name servers still in the inventory applies to playbooks
outside `one_time_playbooks/completed/`.

`grep -lw db02 one_time_playbooks/*.yml` lists the affected playbooks.
While the server still answers, `mmx complete-one-time-playbook NAME`
moves each affected playbook to `completed/`.
For a server that is gone, move each affected playbook to
`one_time_playbooks/completed/` with `git mv`.
When the playbook's remaining fix was only for the removed server, move
the playbook with `git mv`. A fix that a surviving server still needs goes
into a new one-time playbook.
Use `one_time_playbooks/completed/` as the destination.
