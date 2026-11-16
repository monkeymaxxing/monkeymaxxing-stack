# Replace a server

**When to use this page:** a server needs a bigger size, a move from VPS to dedicated hardware, a new Debian release, or replacement after hardware failure.

**What this page does:** a new server takes the old or failed server's
place in the server's pool, and then the old or failed server leaves the
inventory and the provider.

**Terms:** this page uses the Stack's terms, such as pool, playbook,
primary, replica, and triage agent. [Technical terms](../talking_with_the_team.md#technical-terms)
explains each term.

## Find your situation

| Situation | Follow |
| --- | --- |
| An app server, a jobs server, or a load-balancer server stopped reporting | [A failed server: the three replacement playbooks](#a-failed-server-the-three-replacement-playbooks), then the section for the failed server's pool: [An app server dies](#an-app-server-dies), [A jobs server dies](#a-jobs-server-dies), or [A load-balancer server dies](#a-load-balancer-server-dies) |
| Both load-balancer servers are lost | [Both load-balancer servers are lost](#both-load-balancer-servers-are-lost) |
| The database primary dies | [The database primary dies](#the-database-primary-dies) |
| A database server that was cut off comes back after a replica took over | [When the old primary comes back](#when-the-old-primary-comes-back) |
| A planned replacement: a bigger size, a move from VPS to dedicated hardware, or a new Debian release | [Replacing a server](#replacing-a-server) |
| The utility server, `util01` | [Rebuild util01](rebuild_the_utility_server_util01.md) |
| The test server, `staging01` | [Replace staging01](replace_staging01.md) |

For a failed server, first follow the failed server's section. Follow
[Add a server](add_a_server.md) and [Removing a server](remove_a_server.md)
for the shared server steps.

## Before you start

- **A push alone changes no server.** Apply each configuration change as
  [Making a change](../AGENTS.md#making-a-change) says: run `every_server`
  or the playbook the step names.
- **After a push that adds, replaces or removes a server in the inventory,**
  also run `sudo -n update-this-desks-wireguard-peers`, so this desk's
  WireGuard peers match the servers
  ([Update the desk's production peers](../initial_setup/02_set_up_the_laptop_and_the_systems_desk.md#update-the-desks-production-peers)).

## A failed server: the three replacement playbooks

**When:** an app server, a jobs server or a load-balancer server stops
reporting, and the server's pool is in
`triage_agent_server_work.pools_whose_failed_servers_the_triage_agent_replaces`
in `mmx_project_settings.yml` (all three pools in the template).

**What happens:** three playbooks replace the failed server. The triage
agent runs the three playbooks, at once with
`what_the_triage_agent_may_do_without_a_person: routine_fixes_and_server_work`,
and after one approval otherwise
([Replacing a failed server](../triage_agent_rules.md#replacing-a-failed-server)).

**Before you start:** first read the triage agent's report and MMHotline's
incident: the replacement may be done or under way. To tell which, run
`git pull --rebase`, then `git log --grep '^Server-pool: ' -3`. A commit with
`Replaced-server: app001` means the replacement is under way. A later commit
with `Destroyed-server: app001` means it is done. The incident in MMHotline
shows the triage agent's reports, and
`./server_management_scripts/run_mmx_on_util01 status` names a run in progress. A person who wants to
do the replacement by hand runs the same three playbooks from the desk, in
the order below, each only after the one before succeeded.

1. **Replace the failed server in the inventory:**

   ```sh
   ./server_management_scripts/run_mmx_on_util01 run replace_failed_servers
   ```

   `replace_failed_servers` powers the failed server off at the provider,
   creates the new server with the failed server's type and location, and
   pushes the commit that puts the new server in the inventory in place of
   the failed server. The new server gets the next unused name of the
   pool, such as `app002`, `jobs002` or `lb03`.
   **Check:** the last lines say "What exists now:". They show the failed
   server still at the provider and powered off until
   `destroy_replaced_servers`, and the new server in the inventory in place
   of the failed server. Then comes "replaced app001 with app002". A failed
   power-off shows "the power-off FAILED: app001 may still run". The last
   lines also give the new server's type and monthly price. Tell the person
   which server was added, why, and its type and monthly price from that
   line. When the line says the price could not be read, leave the price
   out. The price is never a reason to stop.

2. **Pull the playbook's commit:**

   ```sh
   git pull --rebase
   ```

   Reason: after the playbook's commit, the helper refuses the next run
   with "HEAD must equal pushed main" until the desk runs `git pull --rebase`.

3. **Install the new server:**

   ```sh
   ./server_management_scripts/run_mmx_on_util01 run every_server
   ```

   `every_server` installs the new server.

4. **Destroy the failed server:**

   ```sh
   ./server_management_scripts/run_mmx_on_util01 run destroy_replaced_servers
   ```

   `destroy_replaced_servers` destroys the failed server, by the provider
   ID in the commit, only when the new server reports to the fleet hub and
   passes `check-that-this-server-does-its-work`. Otherwise it destroys
   nothing and says which server does not do its work yet ("app002 does not
   do its work yet: nothing destroyed", exit 1). When it destroys, it pushes
   a second commit. **Check:** the lines "destroyed app001 (ID …) at the
   provider: app002 does its work" and "committed SHA: destroyed app001".

5. **Pull the second commit:**

   ```sh
   git pull --rebase
   ```

   Reason: `destroy_replaced_servers` pushed a second commit, so the helper
   refuses the next run with "HEAD must equal pushed main" until the desk
   runs `git pull --rebase`, as step 2 says.

6. **Update this desk's WireGuard peers:**

   ```sh
   sudo -n update-this-desks-wireguard-peers
   ```

7. **Verify:**
   - the public app answers: send a request to each app's health URL, with
     the production host name under `vars.public_host_names.production` in
     `inventories/servers.yml` and the app's `health_url_path` from
     `vars.apps.<app>` in `mmx_project_settings.yml`, as step 3 of
     [the second app server's test](add_an_app_server.md#the-second-app-servers-test)
     shows;
   - `git log -2` shows the two commits by "util01, the mmhotline user";
   - MMWatchdog's fleet hub lists the new server as reporting;
   - `./server_management_scripts/list_the_servers_at_the_provider` no
     longer lists the failed server.

   For a jobs server, also check that each app's job container runs on the
   new jobs server, as step 3 of
   [Adding jobs servers](add_jobs_servers.md#adding-jobs-servers) says. For
   a load-balancer server, also check that Cloudflare lists the new
   server's address as a connector of the tunnel, as step 3 of
   [Adding load-balancer servers](add_load_balancer_servers.md#adding-load-balancer-servers)
   says.

**If something is different:**

- **If a triage session is already running:** to tell a
  triage session that is already running something, claim the incident in
  MMHotline with a note, or give a reason when you refuse an approval or
  press Stop. The agent reads it at its next step. To stop the session,
  use **Take over from the agent** on the incident's page. A file you
  commit to `triage_agent_notes/` meanwhile is read only from the
  session's next run, and the agent is not told the file is new, so put
  the fact in a note on the incident.
- **If a run refuses with "HEAD must equal pushed main":** the same refusal
  follows any commit that the triage agent or a playbook pushed, such as a
  triage note. Run `git pull --rebase`, then the run again.
- **If a playbook fails:** each playbook can be run again safely after a
  failure. Each playbook's comments say what a rerun does at each step.
- **If a playbook refuses:** a refusal names its reason, such as more than
  half of the servers being silent at once, and changes nothing. Follow the
  route by hand in the section for the failed server's pool.
- **If the failed server's pool is not listed** in
  `pools_whose_failed_servers_the_triage_agent_replaces`: follow the route
  by hand in the section for the failed server's pool.

**Why nothing waits for the failed server to leave the inventory:** the
new server takes the failed server's place in one commit. So a production
deploy, which stops while the inventory names a jobs server or a
load-balancer server it cannot reach, runs again once the new server is
installed. And `remove_server`, which refuses the last jobs server, is
never needed.

The sections below say what users see meanwhile, and the route by hand
when the pool is not listed or the playbooks refuse.

## An app server dies

**What users see:**

- **With another healthy app server:** the remaining healthy app servers
  carry the failed app server's requests within seconds. Check the public
  app before you report that service continues.
- **With only one app server:** the site is down until its replacement is
  installed.

1. **Tell the person which case applies.** State the next replacement step
   and its cost.
2. **Replace the failed app server** with
   [the three replacement playbooks](#a-failed-server-the-three-replacement-playbooks).
   The three replacement playbooks are the first route.

**By hand, for a pool the playbooks do not replace, or when the playbooks
refuse:**

1. Add a replacement app server, as
   [Replacing a server](#replacing-a-server) describes.
2. Remove the failed app server, starting at step 2 of
   [Removing a server](remove_a_server.md). Skip `remove_server`, because
   `remove_server` needs the failed app server to answer.

## A jobs server dies

**What happens by itself:** the remaining jobs servers take waiting jobs
from the Postgres queue. With the row-locking queue described in
[Adding jobs servers](add_jobs_servers.md#adding-jobs-servers), an
interrupted job waits for another worker after Postgres releases the lock.
App servers can also take the jobs while their job containers still run.

**What users see:** the site keeps answering. Only the jobs wait in the
queue until a jobs server runs them again. Once only jobs servers run jobs,
losing all of them wakes the person on call. Once only jobs servers run
jobs, the person on call also wakes when the only jobs server stops
reporting.

**The first route:** [the three replacement playbooks](#a-failed-server-the-three-replacement-playbooks).
The new jobs server starts each app's job container on the release the app
servers serve, in the `every_server` run, and takes the waiting jobs.
`job_containers_run_only_on_the_jobs_servers` stays as it is, also for
the only jobs server.

**By hand, for a pool the playbooks do not replace, or when the playbooks
refuse:**

1. **Delete the failed server from the inventory, and delete its lines from
   `ssh/known_hosts`.** Skip `remove_server` because `remove_server` cannot
   reach the failed server.
   Reason: until the failed server leaves the inventory, every production
   deploy stops at the jobs servers' image pull, before changing anything.
   `end_connections_that_use_an_old_database_password` for production also
   stops at its second step, which reads the app's container start times.
   The playbook cannot reach the failed jobs server to check that the
   containers started after the secrets file changed.
2. **If the failed server was the only jobs server,** set
   `job_containers_run_only_on_the_jobs_servers` back to `false` in
   `mmx_project_settings.yml`. Include the setting change in the commit
   that deletes the failed server from the inventory and `ssh/known_hosts`.
3. **Push the commit.** Then run `sudo -n update-this-desks-wireguard-peers`, because the push removed a server from the inventory ([Before you start](#before-you-start)). With `job_containers_run_only_on_the_jobs_servers`
   set to `false`, `util01`'s `every_server` run starts the app servers' job
   containers again.
   **Check:** one app server's job containers, as **The way back** in
   [Adding jobs servers](add_jobs_servers.md#adding-jobs-servers) describes.
4. **Add a replacement** ([Adding jobs servers](add_jobs_servers.md#adding-jobs-servers)).

## A load-balancer server dies

**What happens by itself:** once the failed server's connections drop,
Cloudflare sends every request to the surviving load-balancer server's
tunnel connector, `cloudflared`.

**The first route:** [the three replacement playbooks](#a-failed-server-the-three-replacement-playbooks).
The new load-balancer server joins the apps' existing tunnel with the
tunnel token from the vault, as every connector of the tunnel does, so
Cloudflare and DNS need no change.

**If the output says the power-off failed,** stop the failed server from
the provider's console at once. Reason: powering the failed server off
first matters most here. Cloudflare sends each request to the nearest
connector of the tunnel, so a load-balancer server that only looks dead,
and whose Caddy no longer reaches the app servers, could take most of the
requests and answer them with errors.

**By hand, for a pool the playbooks do not replace, or when the playbooks
refuse:**

1. **Delete the failed server from the inventory, and delete its lines from
   `ssh/known_hosts`.** Skip `remove_server` because `remove_server` cannot
   reach the failed server. Push the commit.
   Then run `sudo -n update-this-desks-wireguard-peers`, because the push removed a server from the inventory ([Before you start](#before-you-start)).
   Reason: until the failed server leaves the inventory, every production
   deploy stops when switching Caddy to the new release. The old release
   and the new release keep running. An app server's `remove_server` also
   stops before stopping that app server's containers.
2. **Add a new load-balancer server,** such as `lb03`. Use the addition and
   verification instructions under [Replacing a server](#replacing-a-server).
   The failed server has already left the inventory, so skip
   `remove_server`.
3. **Destroy the failed server at the provider, and check that the failed
   server is gone,** as steps 3 and 4 of [Removing a server](remove_a_server.md)
   describe.

## Both load-balancer servers are lost

**When:** `util01`'s check of the public sites wakes a person, and so does
MMWatchdog's fleet hub on `util01`, once the two lost load-balancer servers are silent.

**The first route:** [the three replacement playbooks](#a-failed-server-the-three-replacement-playbooks)
replace both in one run. The site is down until the `every_server` run
has installed the new pair.

**By hand, when the playbooks refuse,** such as when more than half of the
servers are silent at once, or when `load_balancer_servers` is not listed:

1. **In one commit,** set `tunnel_connector_and_caddy_run_only_on_the_load_balancer_servers`
   back to `false` in `mmx_project_settings.yml`, and delete the lost
   servers from the inventory and `ssh/known_hosts`. Push the commit.
   Then run `sudo -n update-this-desks-wireguard-peers`, because the push removed servers from the inventory ([Before you start](#before-you-start)).
   The run restores the app servers' network peering. Then, one app server
   at a time, `util01`'s `every_server` run restores Caddy and the tunnel
   connector. Each app server's connector joins the existing
   `example_systems-apps` tunnel that the lost load-balancer servers used.
2. **Check that the app servers carry the requests again,** as **The way
   back** in
   [Adding load-balancer servers](add_load_balancer_servers.md#adding-load-balancer-servers)
   describes.
3. **Add new load-balancer servers,** such as `lb03` and `lb04` ([Adding load-balancer servers](add_load_balancer_servers.md#adding-load-balancer-servers)).

## The database primary dies

**Who acts:** database servers always need a person
([The rules](../AGENTS.md#the-rules), "What the triage agent may do
without a person").

**What happens, by case:**

- **With a healthy replica that can take control:** the failover system can
  select the replica as the primary. Writes fail for about a minute (52-64 s
  measured): the promotion takes 24-30 s, then each app's database driver
  gives up on the lost server and finds the new primary.
- **If the only database server is lost:** there is no automatic failover.
  The site is down until recovery. Follow
  [Recover when every database server is lost](recover_when_every_database_server_is_lost.md),
  which also applies when all database servers are lost.
- **If replicas exist but failover did not complete:** investigate the
  replicas' state before a replacement or restore. Do not assume that a
  replica is ready.

After successful failover:

1. **Check the new primary and the public app** before you report
   successful failover. Check the new primary on `util01` with the
   `pg_autoctl show state` command in
   [When the old primary comes back](#when-the-old-primary-comes-back).
2. **Tell the person the current service state and the next action.**
3. **Add a replacement server,** as
   [Replace a database server](#replace-a-database-server) says.
4. **Remove the failed server's saved settings,** only if the old primary
   has not come back. If it has, first follow
   [When the old primary comes back](#when-the-old-primary-comes-back).
   Start at step 2 of
   [Removing a server](remove_a_server.md). Delete the failed server from
   the inventory and `ssh/known_hosts`, and skip `remove_server` because the
   failed server is gone. The next `util01` run removes the failed server
   from the failover formation, the database group managed by the failover
   monitor. The inventory lists the intended servers. The failover monitor
   keeps the failover formation's membership on `util01`.
   After the push, run `sudo -n update-this-desks-wireguard-peers`, because the push removed a server from the inventory ([Before you start](#before-you-start)).

### When the old primary comes back

**What happens by itself:** a primary that was cut off, such as by a
network fault, can come back after a replica took over. pg_auto_failover
then makes the returning server a replica, and the returning server copies
what it missed from the new primary by itself. In the Stack's tests on real servers,
`db01` was cut off silently, `db02` became the primary in 24-30 s, and once
`db01`'s traffic returned, `db01` became a replica and caught up with
nobody touching it.

**Do nothing to the returning server.** Never start, stop, or restart
Postgres or `pgautofailover` on the returning server to get writes back.
Reason: writes already go to the new primary, and a restart can give the
returning server a history different from the primary's, which can lose
every write since the histories split
([The rules](../AGENTS.md#the-rules)).

Watch instead, on `util01`:

1. **Show the formation's state:**
   `sudo -u postgres pg_autoctl show state --pgdata /var/lib/postgresql/17/pg_auto_failover_monitor --formation production`.
   **Check:** wait until the returning server's line shows `secondary` in
   both state columns. In the Stack's test this took 37 seconds after the
   server was powered on (`docs/testing.md` in the Stack's repository). After 5 minutes without `secondary`, follow "If MMWatchdog
   keeps warning about the returning server" below.
2. **Show the fleet's health:** `sudo mmwatchdog fleet` on `util01`.
   **Check:** wait until the output shows the returning server healthy,
   `postgres/replica_is_less_than_30_seconds_behind` included.
3. **Tell the person which server is the primary now.**
4. **Decide whether to keep the returning server or replace it,** when it
   came back before it was removed from the inventory. Reason: a network
   fault leaves a healthy server that rejoins by itself, and a hardware
   fault can recur. The server provider's guide gives no way to ask for a
   hardware fault, so look for one in two places:

   1. **The provider's public status page for the server's location.**
      An incident there about the network or connectivity at the time of
      the failure explains the silence: it does not count as a hardware
      fault. An incident about the host, hardware, storage or power at
      that location counts as a hardware fault.
   2. **The returning server's kernel log, over SSH:**
      `journalctl -k --since "TIME"`, with the time of the failure.
      Look for machine-check, memory or disk I/O errors. Any of them
      counts as a hardware fault.

   **Check:** you have looked at both places. Then:

   - **Neither shows a hardware fault:** it was a network fault. Keep the
     returning server. It is already a replica, so do nothing more to it.
   - **Either shows a hardware fault:** replace the returning server, as
     [Replace a database server](#replace-a-database-server) says.
   - **You can't tell,** for example the status page does not name the
     cause or the server cannot be reached over SSH: replace it. Unknown
     counts as a hardware fault, because a replacement costs money but no
     data.
   - **The replacement has already joined when the old server returns:**
     remove the old server with `remove_server`, which works because the
     server answers now (step 1 of [Removing a server](remove_a_server.md)).
     Then follow the rest of that page.

**An old primary that returns after it left the inventory:** the server is
outside the formation, and no other server reaches it. Destroy it, as the
destroy step of [Removing a server](remove_a_server.md) says.

**If MMWatchdog keeps warning about the returning server, or the returning
server's state stops changing before `secondary`:** leave the returning
server as it is. Tell the person, with the `pg_autoctl show state` output.
The triage agent hands over instead.

**If the person wants the returning server as the primary again:** keeping
the new primary is fine, because a server's name says nothing about the
server's role. To make the returning server the primary again, run
`./server_management_scripts/run_mmx_on_util01 run switch_database_primary --var server_name=db01`
with the returning server's name. Writes pause for a few seconds (2-6 s
measured).

## Replacing a server

**Before you start, tell the person how long the replacement takes:**

- A new server's first configuration, the `every_server` run that sets the
  server up, takes about 3.5 minutes (measured on test servers).
- A new database server also copies the primary's data before the new
  server joins as a replica, so add the copy time for the database's size.
- Making the new database server the primary pauses writes for a few
  seconds (2-6 s measured).

Then follow the part for the server's pool.

### Replace an app server

1. Add the new server ([Add a server](add_a_server.md)).
2. Remove the old server ([Remove a server](remove_a_server.md)).

### Replace a jobs server

1. Add the new server ([Add a server](add_a_server.md)).
2. Check that the new server runs the jobs (step 3 of
   [Adding jobs servers](add_jobs_servers.md#adding-jobs-servers)).
3. Remove the old server ([Remove a server](remove_a_server.md)).

### Replace a database server

**Before you start:** a provider move can also require an app server
replacement. If you also replace an app server, add the new app server
before changing database servers. Use a separate commit for the new app
server. Let the new app server serve before changing database servers.
Follow step 8 of [Add a server](add_a_server.md).

**What users see:** adding and removing database servers each change every
app's `DATABASE_URL` server list. Each run therefore restarts each app's
live web container on every app server, one server at a time. Other app
servers keep serving during each restart. With one app server, the only
web container restarts: requests fail for a second or two.

1. **Add the new server,** such as `db03`, to `database_servers`, as
   [Add a second database server](add_a_second_database_server.md)
   describes. The new database server copies the primary and joins as a
   replica.
2. **If the old server is the primary, make the new server primary:**
   `./server_management_scripts/run_mmx_on_util01 run switch_database_primary --var server_name=db03`.
   Synchronous replication means the replica confirms writes before the
   writes complete. So switching the primary from the old server to the
   new server loses no data.
   **Check:** the command waits until the old primary is a replica, then
   checks each app through its public host name.
3. **Remove the old server** ([Remove a server](remove_a_server.md)).
4. **If the replacement is bigger,** also set `restore_drill_server_type` in
   `mmx_project_settings.yml` to that server type. Reason: matching
   `restore_drill_server_type` to the bigger replacement keeps the weekly
   drill's measurement relevant to a real recovery.

### Replace a load-balancer server

The new servers get the next numbers, `lb03` and `lb04`. Nothing needs the
names `lb01` and `lb02`. A third load-balancer server goes past the pool's
`largest_number_of_servers` of 2, so ask the person first, with the monthly
price. The bigger type must be in the pool's `server_types`. While three
load-balancer servers exist, `replace_failed_servers` refuses to replace a
failed load-balancer server.

1. **Add the new server with the next number,** such as `lb03`. Use steps 1
   and 2 of [Adding load-balancer servers](add_load_balancer_servers.md#adding-load-balancer-servers)
   for the new load-balancer server.
   The new server joins WireGuard at first boot with the setup-generated
   key. The first `every_server` run adds the server's normal peers and
   configures Caddy. Once each app answers through Caddy, the new
   load-balancer server's connector joins the tunnel.
2. **Check that the new load-balancer server carries requests.** Follow
   step 3 of
   [Adding load-balancer servers](add_load_balancer_servers.md#adding-load-balancer-servers).
3. **Remove the old server** ([Remove a server](remove_a_server.md)).

**To replace the pair with bigger servers,** replace each load-balancer
server in turn. Add and check each new load-balancer server before removing
the old server.
