# Add a new kind of server pool

**When:** a business requirement needs servers of a kind the Stack doesn't
ship, and the team decides to add them. A new kind of pool is a step beyond
the Stack, so a measurement alone is not enough
([Assess, recommend, execute](assess_a_running_system_and_recommend_changes.md#assess-recommend-execute),
step 2).

**What this page does:** the Stack ships a few kinds of server pool: app servers, database servers,
jobs servers, and load-balancer servers. A team can add a pool of another
kind the Stack doesn't ship, such as cache servers. This procedure lists
the decisions to make and the files each decision changes.
[Add jobs servers](add_jobs_servers.md) is the full worked example of the
pattern: read it first, and copy its shape.

**Who acts:** you, the coding agent, write the decisions, change the files,
and add the servers. The person agrees the six decisions before any
change, and agrees each new server as [Add a server](add_a_server.md)
says.

## Before you start

- **First check that a step the Stack already has doesn't solve the
  problem,** such as a bigger server, another server in an existing pool, or
  Cloudflare's cache.
- **Before any change, write down the six decisions below,** with the reason for
  each, and agree them with the person. Then record the pool in the checklist
  as its own item, with `deviation` saying what it adds to the Stack and why.
  Reason: every later coding agent, and every stack upgrade, must know that the
  pool exists and why.
- **A push alone changes no server.** Apply each configuration change as
  [Making a change](../AGENTS.md#making-a-change)
  says: a push alone changes no server, so run `every_server` or the playbook the step names.

## The six decisions

The decisions are written down and agreed, not run, so a decision has no
check of its own: `mmx validate` and step 3 of
[Adding the first server](#adding-the-first-server) check the files that
the decisions change.

1. **The group's name, flag and private address block.** Name the pool for
   its servers' job, in the plural, such as `cache_servers`, with servers
   `cache001`, `cache002`, and up. Choose the flag the roles read, such as
   `is_cache_server`: `true` in the group's `vars`, and `false` among the
   flags in the inventory's top-level `vars`. Take the next unused third
   number of the WireGuard network for the address block, such as
   `10.20.5.0/24`, and add it to `vars.private_ip_ranges` in
   `inventories/servers.yml`: a group with an address block there is a
   server pool. Check
   [Server names and private addresses](../AGENTS.md#server-names-and-private-addresses)
   for the numbers already in use, and add the new pool's row there.
2. **Which pools it talks to, and which talk to it.** Add a line to
   `connections_between_server_pools` in `inventories/servers.yml` for each
   connection, in the direction it is opened, with its TCP ports and why.
   For example, the app servers use the cache servers' memcached:

   ```yaml
   - from_pool: app_servers
     to_pool: cache_servers
     tcp_ports: [11211]
     why: The apps keep cached pages in memcached on the cache servers.
   ```

   Each line makes the two pools WireGuard peers in both directions, and
   opens the firewall of every `to_pool` server to every `from_pool` server
   on those ports. Every server already peers with `util01` and the systems
   desks without a line. The dryrun of `every_server` shows only that a
   server's firewall or `wg0` would change, not the rules: the role takes a
   secret input, so MMX hides its values. After the run, read each changed
   server's peers and rules with `wg show wg0 allowed-ips` and
   `ufw show added` on the server.
   Also check the playbooks that read a flag such as `is_jobs_server`, such
   as `reboot_servers_after_updates.yml`, for whether the new pool needs the
   same step.
3. **What software it runs.** Prefer a package from the Debian release the
   servers run: Debian's security updates then cover it. A program from
   outside the distribution follows
   [Add or update a program from outside the distribution](add_or_update_a_program_from_outside_the_distribution.md).
   Write the pool's own role, such as `roles/cache_server/main.yml`, and
   one fleet stage for it in `playbooks/every_server.yml`, named for the
   tool, with `nodes: cache_servers` and `skip_when_no_nodes_are_selected:
   true`. Put the stage before `mmwatchdog_joins_the_fleet_hub_after_the_roles`,
   so the pool's checks find its service running. Each setting a team
   would choose differently, such as a memory limit, goes in
   `mmx_project_settings.yml` with its default and its reason. Secrets go
   in the vault. If the pool's servers log in to the apps' databases, they
   also need a line in
   `roles/database_server/files/pg_hba_logins_of_the_apps.conf`, as the
   jobs servers have; the firewall line alone lets them reach Postgres, not
   log in.
4. **Whether it holds data that needs a backup.** Prefer a pool that holds
   no data of its own: a cache can be emptied, and a worker can restart.
   The Stack keeps one home for each kind of thing (data in Postgres,
   uploaded files in R2), so a new pool must never hold the only copy of
   the team's data. If the pool must keep data, write how the data is
   backed up to the locked backup bucket, how the restore drill proves
   the backup, and how
   [Replace a server](replace_a_server.md) brings the data back, before
   any server holds real data. The triage agent's replacement playbooks
   replace only app servers, jobs servers and load-balancer servers: a
   failed server of the new pool is replaced by a person, with
   [Replace a server](replace_a_server.md).
5. **What MMWatchdog checks on it.** Add the pool's check group, such as
   `mmwatchdog_checks/cache_servers.yml`. Copy the capacity checks of
   `mmwatchdog_checks/jobs_servers.yml` (CPU, memory, disk), and add a
   check that the pool's own service runs and answers. Give each severity
   its reason, as the other check files do. A severity of `sos` wakes a
   person, so use it only when customers are affected.
   Then list the files in the pool's group in `inventories/servers.yml`,
   beside the flag:
   `mmwatchdog_check_files: [every_server.yml, cache_servers.yml]`. Every
   server of the pool then gets exactly those files, and no role or
   playbook changes. A pool's group without `mmwatchdog_check_files`
   fails `mmx validate`, naming `.vars.mmwatchdog_check_files`.
   Reason for the setting: a role cannot ask which pool its server is in,
   so the pool's group lists its files once, as it sets its flag.
6. **The measurement that says to add another.** Name the reading that
   says the pool is full, such as "memory above 75% for 15 minutes" or
   "the cache evicts keys every minute", and the check that reports it.
   Add a row to the
   [operating procedure table](../AGENTS.md#when-this-happens-follow-this-operating-procedure)
   that names the reading. Also write down what adding a server changes
   for the pool's users: for example, whether the apps spread their keys
   over the new server by themselves, or need a new setting first.

## Adding the first server

When the six decisions are agreed and the files are changed:

1. Run `mmx validate`, commit, and push.
   **Check:** `mmx validate` passes. A pool's group without
   `mmwatchdog_check_files` fails it, naming `.vars.mmwatchdog_check_files`.
2. Add the first server, such as `cache001`, with
   [Add a server](add_a_server.md), as step 1 of
   [Adding jobs servers](add_jobs_servers.md#adding-jobs-servers) does,
   with the pool's group and an address inside its block. The run refuses
   a server whose `private_ip` lies outside its pool's block, or that is
   in no pool or in two.
   **Check:** the checks of [Add a server](add_a_server.md).
3. Verify over SSH, which only reads: the pool's service runs, the
   firewall opens only the agreed ports to the agreed pools
   (`ufw show added`), and `wg show wg0 allowed-ips` lists only the agreed
   peers. Check from one server that uses the pool that it reaches the
   service.
   No separate check: this step is the check.
4. Then let the apps or servers that use the pool start using it, with
   the setting the pool needs, and verify that they work.
   **Check:** the apps or servers that use the pool work with it.
5. Record the checklist item `done`, with what the verification measured,
   and update the README's list of servers.
   No check here: the record is the result of steps 3 and 4.

## Adding a pool from a recipe

**When:** the pool, its role, and its checks come from a recipe, such as
a Redis or Meilisearch recipe from
[monkeymaxxing-recipes](https://github.com/monkeymaxxing/monkeymaxxing-recipes).
First follow [Using a recipe](../AGENTS.md#using-a-recipe): fetch it at a
pinned commit, check it, and get the person's approval. Then follow the
six decisions above, with the recipe as the draft of each one. A recipe
changes no file by itself, and adds no pool the person did not approve.

The Stack leaves a place for each part of a recipe, so no Stack file
changes beyond these places:

- **The recipe's fleet stage** goes between the two `# --- Custom
  extensions ---` comment lines in `playbooks/every_server.yml`, before
  MMWatchdog joins. It names its own role, such as
  `roles/custom_redis_server/main.yml`.
- **The recipe's settings** go under `custom:` in `mmx_project_settings.yml`,
  such as `custom.redis.maxmemory_megabytes`, with a default and a reason.
  The roles and the check files read them as `{{ .inputs.custom.<key> }}`,
  such as `{{ .inputs.custom.redis.maxmemory_megabytes }}`: the playbook
  passes `custom` as the role input of the same name.
- **The recipe's checks** go in `mmwatchdog_checks/custom_NAME.yml`. A
  check file the team adds always starts with `custom_`, so a later Stack
  file can never take the same name. List it at the end of
  `mmwatchdog_check_files` in the pool's group, such as
  `[every_server.yml, cache_servers.yml, custom_redis.yml]`. The triage
  user can confirm a fix of a custom check group with no sudo change: one
  line of `roles/every_server/files/sudoers_triage` covers every group.
  That line matches only group names of lower-case letters, digits, and
  underscores (`[a-z0-9_]+`, no hyphens), so name each check group under
  `check_groups:` that way, such as `custom_redis`, or triage's
  `sudo mmwatchdog check-now` cannot run it.
- **The record** is a copy of the recipe in `custom_recipes/ID.md`, with
  `source_url`, `source_commit`, and `applied_on`, and an entry in
  `custom_extensions:` in `monkeymaxxing_stack_checklist.yml`.

**Check:** `mmx validate` passes, `mmx dryrun every_server` proposes only
the pool's changes, and the recipe's own verification step passes after
the run. `mmx validate` refuses a check file name with a path part (`..` or
a `/`) and a name of a file that does not exist in `mmwatchdog_checks/`,
naming `mmwatchdog_check_files`. The role's own first task, which runs on
the server before any change, refuses a name outside
`^[a-z0-9][a-z0-9_-]*\.yml$`: lower case, and a `.yml` ending.

## If something is different

- **More servers:** add `cache002` and up with
  [Add a server](add_a_server.md), when the reading
  from decision 6 says so.
- **Removing the pool:** stop its users from using it first, then remove each
  server with [Remove a server](remove_a_server.md). Then, in one commit,
  remove the pool's lines in `connections_between_server_pools`, its address
  block, its group with its flag and `mmwatchdog_check_files`, the role, the
  stage, and the check file. The run refuses a line that names a pool which
  no longer exists, so a leftover line can't slip through.
