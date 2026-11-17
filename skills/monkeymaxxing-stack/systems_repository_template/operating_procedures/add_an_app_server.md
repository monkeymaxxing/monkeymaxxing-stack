# Add an app server

Read [the systems repository rules](../AGENTS.md#the-rules) first.

**When to use this page:** the app servers warn about CPU or memory use, a
deploy lacks memory, or the team wants the second app server that keeps the
site up while one app server fails.

**What this page does:** this page adds one server to `app_servers`, and
every production Caddy then lists the new server's web containers as
destinations for requests.

**Who acts:** you, the coding agent, do every step from the systems desk,
or the triage agent runs the playbook route on its own when the team's answer
is `routine_fixes_and_server_work` (see "Who runs the playbook route" below).
The person approves the monthly price only when the new server is outside the
growth limits, and hears afterwards which server was added.

**Terms:** this page uses the Stack's terms, such as pool, growth limits,
playbook, and triage agent. [Technical terms](../talking_with_the_team.md#technical-terms)
explains each term.

## Choose the route

- **The app servers' CPU warns:** the playbook comes first. Follow
  [Add an app server for the CPU load](#add-an-app-server-for-the-cpu-load).
- **Every other app server:** follow
  [Add an app server by hand](#add-an-app-server-by-hand), which uses
  [Add a server](add_a_server.md). The other cases are memory, a bigger
  type, a deploy that lacks memory, the second app server that keeps the
  site up while one app server fails, and a person who wants a server
  anyway after the playbook says "nothing to add".

**A deploy lacks memory:** another app server does not fix it. The deploy's
memory check runs on each app server alone. It compares that server's
available memory with a second copy of that server's own live web
containers, plus a tenth of its memory. An app server added beside it
changes none of these numbers. The app servers' growth limits are
`growth_limits.app_servers` in `mmx_project_settings.yml`:

- Replace the server without room with a bigger type from the pool's
  `server_types` ([Replace a server](replace_a_server.md)). Inside the
  growth limits, you, the coding agent, choose this without asking.
- Or set a smaller `WEB_CONCURRENCY` in the app's own env
  (`vars.apps.<app>.env` in `mmx_project_settings.yml`). Without that
  setting, each server uses its own CPU count, so a smaller value means
  fewer worker processes and less memory, and also fewer requests served at
  once. Tell the person this before choosing it.
- When no bigger type in `server_types` fits, or the pool is at its
  `largest_number_of_servers`, ask the person first, with the monthly
  price, as step 1 of [Add a server](add_a_server.md) says.

Reason to also consider a second app server: another server keeps the apps
answering while one app server reboots or fails. A bigger server does not.
That reason is not a fix for the deploy.

Each app server must still fit the live and new releases, jobs, the system,
and the free-memory reserve. Follow
[Memory for both releases](deploy_and_roll_back_an_app_release.md#memory-for-both-releases)
before retrying the deploy.

## Before you start

- **A push alone changes no server.** Apply each configuration change as
  [Making a change](../AGENTS.md#making-a-change) says: run `every_server`
  or the playbook the step names.
- **A much bigger app server opens many more Postgres connections.** Before
  adding the bigger server by hand, calculate the total with the new server
  included, as [Postgres connections with the new server](#postgres-connections-with-the-new-server)
  says. If the total would exceed 70, [add PgBouncer](add_pgbouncer.md)
  first. The playbook `add_an_app_server_for_the_load` does this sum itself.

## Add an app server for the CPU load

`add_an_app_server_for_the_load` adds one app server only when the CPU load
needs one, by the rule in
[When the playbook adds an app server](#when-the-playbook-adds-an-app-server).

1. **Run the playbook:**

   ```sh
   ./server_management_scripts/run_mmx_on_util01 run add_an_app_server_for_the_load
   ```

   **Check:** the playbook's last lines give the new server's monthly
   price. Tell the person which server was added, why, and its type and
   monthly price from that last line. When the line says the price could
   not be read, leave the price out. The price is never a reason to stop.
   If the playbook says "nothing to add" or refuses, see
   [If something is different](#if-something-is-different).

2. **Pull the playbook's commit,** in the desk's checkout and in your
   clone: `ssh desk01-agent 'cd systems_repository && git pull --ff-only'`,
   then `git pull --ff-only` on the laptop.
   Reason: the playbook commits the new server to `main` itself, as
   `util01`, so pull before your next change. After a commit that a
   playbook pushed, the helper refuses the next run with "HEAD must equal
   pushed main" until you pull
   ([The rules](../AGENTS.md#the-rules)).

3. **Install the new server:**

   ```sh
   ./server_management_scripts/run_mmx_on_util01 run every_server
   ```

   `every_server` installs the new server.
   **Check:** verify the new server as step 8 of [Add a server](add_a_server.md)
   says.

4. **Update this desk's WireGuard peers:**
   `sudo -n update-this-desks-wireguard-peers`.
   Reason: the playbook's push added a server to the inventory, and this
   desk's WireGuard peers must match the servers
   ([Update the desk's production peers](../initial_setup/03_make_your_server_account_and_your_systems_desk.md#update-the-desks-production-peers)).

## Add an app server by hand

1. **[Add a server](add_a_server.md) to `app_servers`.** Step 1 of Add a
   server checks the growth limits, and step 8 of Add a server verifies the
   new server. [What the new app server joins](#what-the-new-app-server-joins)
   says where the new server takes requests from.
2. **After a deploy that stopped at the memory check, fix the server
   without room, then rerun the deploy.** The new app server does not fix the
   memory check ([A deploy lacks memory](#choose-the-route)). Reason: a new
   app server runs the release the pool runs now, not the tag in
   `deployed_image_tags`. After a deploy that stopped at the memory check,
   the pool still runs the old release, so the new server starts the old
   release too. Rerun the deploy, after the server without room is bigger or
   the app's `WEB_CONCURRENCY` is smaller, to move every server to the new
   release.
3. **For the second app server, run
   [the second app server's test](#the-second-app-servers-test).**

## The second app server's test

The checklist item `second_app_server` is done once the apps keep answering
while `app001` is gone. The second app server's test cuts `app001`'s power,
as when a server dies, while `app002` serves alone:

1. **Put `app001` in MMWatchdog maintenance,** so MMWatchdog sends no alerts
   about `app001` during the power-off:

   ```sh
   ssh -F ssh/config root@10.20.1.1 'mmwatchdog maintenance on --every-check-group --for 15m --reason "second_app_server test: app001 powered off"'
   ```

   Reason for 15 minutes: the test takes about 5, with the power-off, the
   requests and the boot. The rest is room for a dedicated server's boot.
   A pause that ends while `app001` is still off brings the fleet hub's
   alert that `app001` stopped reporting, which is the right alert then.

2. **Cut `app001`'s power:**
   `./server_management_scripts/power_off_a_server_at_the_provider --server-id ID`,
   with `app001`'s ID from `list_the_servers_at_the_provider`.
   **Check:** the script returns once the provider shows `app001` stopped.
3. **Wait 30 seconds, then send an HTTP request to each app's health URL**
   through the app's public host name. Send five requests to each app's
   health URL, a few seconds apart. Find the production host name under
   `vars.public_host_names.production` in `inventories/servers.yml`. Append
   the app's `health_url_path` from `vars.apps.<app>` in
   `mmx_project_settings.yml`:

   ```sh
   curl --silent --output /dev/null --write-out '%{http_code} %{time_total}\n' https://shop.example.com/up
   ```

   **Check:** each request must answer `200`, from `app002`.

   The wait matters: for a few seconds after a power-off, Cloudflare still
   sends some requests down `app001`'s tunnel, and those requests fail. In
   the stack's tests, the failures lasted about 5 seconds.

   If a request still fails after the wait, the apps are down while
   `app001` is off. Turn `app001`'s power back on at once (step 4). Leave
   `second_app_server` at `waits_for_its_trigger` until the reason `app002`
   did not answer is fixed and the test passes.

4. **Turn `app001`'s power back on:**
   the provider's power-on action for `app001`, as the provider guide gives
   it. The containers and tunnel connector on `app001` start as at any
   boot. Once `ssh -F ssh/config root@10.20.1.1 true` connects, turn off
   MMWatchdog maintenance for every check group on `app001`:
   `ssh -F ssh/config root@10.20.1.1 'mmwatchdog maintenance off --every-check-group'`.
   **Check:** `mmwatchdog status` on `app001` exits 0, as in step 8 of
   [Add a server](add_a_server.md).
5. **Mark the item done.** Record the five HTTP response codes and response
   durations in seconds in `last_result`. In the same commit, set
   `growth_limits.app_servers.smallest_number_of_servers` to 2 in
   `mmx_project_settings.yml`, and run `every_server`. Reason: the second
   app server is there for failures, so the triage agent never removes the
   second app server for low load.

## If something is different

- **If `add_an_app_server_for_the_load` says "nothing to add":** the
  playbook also says why. If the person wants a server anyway, follow
  [Add an app server by hand](#add-an-app-server-by-hand).
- **If `add_an_app_server_for_the_load` refuses:** the playbook refuses at
  the pool's `largest_number_of_servers`, while an app server does not
  report, during an unfinished replacement, for a type outside the pool's
  `server_types`, and when the Postgres connections would pass 70. For the
  connections, the playbook refuses with the numbers: [add
  PgBouncer](add_pgbouncer.md) first.
- **Who runs the playbook route:** with
  `what_the_triage_agent_may_do_without_a_person:
  routine_fixes_and_server_work` in `mmx_project_settings.yml`, the triage
  agent runs `add_an_app_server_for_the_load`, then `every_server`, after
  MMHotline's warning, with no person. The triage agent also removes the
  server again when a week's load no longer needs the server
  (`remove_server` without `server_name`, [Remove a server](remove_a_server.md)).
  With the other two answers, a person adds and removes app servers, so
  you, the coding agent, run the steps above with the person
  ([The rules](../AGENTS.md#the-rules)).
- **If no app server runs yet:** the first app server starts the tag in
  `deployed_image_tags`.
- **If the pool mixes server sizes:** MMWatchdog's CPU warning assumes equal
  app servers, so the [weekly system review](do_the_weekly_system_review.md)
  checks that the other servers can carry the load when the biggest server
  fails. [A pool of mixed server sizes](#a-pool-of-mixed-server-sizes) says
  how the servers share the requests.

## How it decides

This part explains the rules behind the steps, for the reader who wants
them.

### When the playbook adds an app server

`add_an_app_server_for_the_load` adds one app server when the pool's CPU,
spread over one server fewer, stayed above 70% for
`triage_agent_server_work.minutes_of_high_load_before_an_app_server_is_added`
(15 by default). The playbook uses the same rule as `util01`'s check
`app_servers_to_add_for_the_load`. The new server copies the type and
location of the pool's newest server.

### What the new app server joins

Until load-balancer servers take over incoming requests, the new app server
opens a connection to production's shared Cloudflare tunnel. Every
production Caddy lists the new server's web containers as destinations for
requests. Production Caddy runs on the app servers until the load-balancer
servers take over, then on the load-balancer servers.

### A pool of mixed server sizes

A pool may mix server sizes, such as a dedicated server beside small VPS
instances. Each server gives its CPU count to the apps' web containers as
`WEB_CONCURRENCY`. Each app's web server uses the CPU count in
`WEB_CONCURRENCY` to set the number of worker processes. Caddy sends each
request to the web container with the fewest unfinished requests, so a
bigger server takes a bigger share.

An app can set `WEB_CONCURRENCY` under `vars.apps.<app>.env` in
`mmx_project_settings.yml`. The app then uses the configured worker count on
every server, regardless of CPU count. Setting a fixed worker count suits an
app whose workers need more memory than one CPU's share.

### Postgres connections with the new server

Each worker process keeps its own pool of Postgres connections. A much
bigger app server therefore opens many more connections. Before adding the
bigger server, calculate the total with the new server included:

- For each app on each app server, multiply that server's `WEB_CONCURRENCY`
  by the app's connections per worker process: the app's
  `database_connections_per_worker_process` in `mmx_project_settings.yml`
  when the app sets it. Without that setting, the Rails rule counts:
  `RAILS_MAX_THREADS` under the app's `env`, or 3, Rails' own default.
- Add the web connection counts for every app on every app server, then
  double the result. The live and new releases' web containers run together
  during a deploy, for about a minute.
- Add the job containers' connections: each job container counts as one
  worker process of its app, on every server that runs job containers.
- Add 15 for the system's own connections, a fixed count of what the
  Stack itself opens at once: MMWatchdog's checks (5), pg_auto_failover
  (2), the nightly backup (2), a person or the triage agent reading the
  database (3), a deploy's migration (1), and PgBouncer's password
  lookups (2).

`add_an_app_server_for_the_load` does this sum with each app server's CPU
count, read over SSH, and refuses with the numbers when the total would
pass 70. The playbook's connections per worker process are the ones above.
For an app on another framework, set `database_connections_per_worker_process`
to the size of the app's database pool in one process, such as 10 for
node-postgres's default pool. Reason: without the setting, the Rails rule's
3 makes the sum too low.

If the total would exceed 70 of Postgres's 100 connections
(`max_connections`, Postgres's own default, which the Stack keeps),
[add PgBouncer](add_pgbouncer.md) first. 70 connections is the level at
which MMWatchdog's check `connections_are_below_70_percent`, in
`mmwatchdog_checks/database_servers.yml`, warns. The reason beside the
check: the other 30 leave room for a burst. PgBouncer lets many app
connections share fewer Postgres connections.

With PgBouncer, the apps' databases share 54 Postgres connections: 20 for
each of one or two apps, fewer for more apps, such as 18 each for three
apps and 4 each for twelve. These numbers are fixed in
`roles/pgbouncer/files/pgbouncer.ini`, whose comment gives the reasons:
about 20 is as many transactions as a database server runs well at once,
and 54 keeps the apps and the system's own 15 under the warning's 70. Only
job containers that connect directly to Postgres
(`jobs_connect_directly_to_postgres: true`) still count on top.

### PgBouncer, jobs servers, and load-balancer servers

The repository already holds the roles and fleet stages for PgBouncer, jobs
servers, and load-balancer servers. A role defines the tasks for a server's
function, such as running apps. An MMX fleet stage selects servers and
applies a role or runs tasks on the selected servers.

These roles and fleet stages do nothing until their settings in
`mmx_project_settings.yml` change from `false`, so the jobs and
load-balancer server groups start empty. Each later step has its own
operating procedure and its own settings:

- [Add PgBouncer](add_pgbouncer.md): `pgbouncer_runs_in_front_of_postgres`
  and each environment's `apps_connect_through_pgbouncer`.
- [Add jobs servers](add_jobs_servers.md):
  `job_containers_run_only_on_the_jobs_servers`.
- [Add load-balancer servers](add_load_balancer_servers.md):
  `tunnel_connector_and_caddy_run_only_on_the_load_balancer_servers`.

Each of these operating procedures adds the servers or software beside the
existing servers, checks each part, and turns on the procedure's settings
in the order the procedure gives. To go back, follow the same operating
procedure, because setting a value back to `false` alone removes neither
the added servers nor PgBouncer.
