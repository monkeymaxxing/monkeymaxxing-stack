# Add jobs servers

Read [the systems repository rules](../AGENTS.md#the-rules) first.

**When:** jobs compete with web requests for CPU.
The app servers warn about CPU use, and job containers account for a large
part of the recorded CPU use. MMWatchdog records each job container's CPU
use in the `job_containers` check group.

**What this page does:** this page moves the apps' job containers from app servers to jobs servers, `jobs001` and up.
Jobs servers run only job containers: no Caddy, tunnel connector, or web container.
The app servers then run only web containers.
Moving job containers to jobs servers affects production only.
`staging01` keeps running its own containers.

**Who acts:** you, the coding agent, do the steps from the systems desk.
A person takes an action in an app that queues a job, when an app queues
few jobs (step 3). A failed jobs server can be replaced by the triage
agent ([If something is different](#if-something-is-different)).

**Terms:** this page uses the Stack's terms, such as pool, inventory,
fleet stage and tunnel connector.
[Technical terms](../talking_with_the_team.md#technical-terms) explains
each term.

## Choose the route

| Situation | Follow |
| --- | --- |
| No jobs server yet | [Adding jobs servers](#adding-jobs-servers): add `jobs001`, then turn on `job_containers_run_only_on_the_jobs_servers` |
| The jobs servers warn about CPU or memory | [More jobs servers](#more-jobs-servers) |
| The team wants the job containers back on the app servers | [The way back](#the-way-back) |
| A jobs server stops reporting | [If something is different](#if-something-is-different) |

## Before you start

- **The shared server steps are in [Add a server](add_a_server.md):**
  create the server, record the inventory and SSH host key, and apply the
  configuration. The shared procedure also covers recording the WireGuard
  key, rebooting, and verification.
- **A push alone changes no server.** Apply each configuration change as
  [Making a change](../AGENTS.md#making-a-change)
  says: a push alone changes no server, so run `every_server` or the playbook the step names.

## Adding jobs servers

1. **Add `jobs001`** with steps 1 to 5 of
   [Add a server](add_a_server.md).
   In shared step 1, use `jobs001` and an address from `private_ip_ranges.jobs_servers`, such as `10.20.3.1`.
   In shared step 2, use a type from `growth_limits.jobs_servers.server_types` in `mmx_project_settings.yml` (`cx33` in the template), even when the app servers are smaller.
   In shared step 3, add `jobs001` to `jobs_servers`, as follows:

   ```yaml
   # inventories/servers.yml
   nodes:
     jobs001:
       address: 10.20.3.1
       https_address: https://10.20.3.1:7443
       ssh_user: root
       ssh_known_hosts: ssh/known_hosts
       ssh_config: ssh/config
       vars:
         private_ip: 10.20.3.1
         public_ipv4_address: 203.0.113.31
         server_type: cx33
         location: fsn1
         wireguard_public_key: PFHMlKh61wvN0/mEnwE2mCdTk3PCQmr/u0lh3F8JkT0=
   groups:
     jobs_servers:
       nodes: [jobs001]
       vars:
         is_jobs_server: true
         mmwatchdog_check_file: jobs_servers.yml
   ```

   Replace the example public key with `jobs001`'s setup-generated key,
   and the server type and location with the create script's.
   The first configuration run adds `jobs001`'s database peers, opens
   Postgres's firewall and `pg_hba.conf` to `jobs001`, and starts each app's
   job container on the release the app servers serve.
   The app servers keep running each app's job container.

   **Check:** the checks of steps 1 to 5 of [Add a server](add_a_server.md).

2. **Verify enrollment and reboot** with steps 6 and 7 of
   [Add a server](add_a_server.md).
   The first boot already supplied the WireGuard key; no key-copy commit
   or expected private-network failure is needed.

   **Check:** the check of step 6 of [Add a server](add_a_server.md).

3. **Check that `jobs001` runs the jobs,** over SSH, which only reads:

   ```sh
   ssh -F ssh/config root@10.20.3.1 'podman ps --all; systemctl list-units --all "caddy*" "cloudflared*"; wg show wg0 allowed-ips; journalctl -u shop-jobs --since "1 hour ago"'
   ```

   **Check:** the results of the SSH command show:

   - Each app's `-jobs` container runs, with no other containers.
   - No Caddy or `cloudflared` unit exists.
   - WireGuard lists the database servers' addresses (`10.20.2.N`), `util01`'s address (`10.20.0.1`), and every systems desk. Systems desk addresses from `private_ip_ranges.systems_desks` reach only SSH on `wg0`.
   - For each app, the journal of the app's `-jobs` unit shows a database
     connection and a completed job. Read each app's `-jobs` unit with
     `journalctl`. The example reads `shop-jobs` for `shop`.

   If an app queues few jobs, have a person take an action in the app that queues one.

4. **Turn the setting on:** set `job_containers_run_only_on_the_jobs_servers` to
   `true` in `mmx_project_settings.yml`, commit, and push.
   The `every_server` run for step 4's commit stops the job containers on
   app servers, one server at a time.
   Each worker gets up to the app's `seconds_a_job_gets_to_finish_when_stopped` (30 in the template) to finish its current job.
   A worker still running after that time is killed, and with a queue such
   as the reference app's, the killed worker's job runs again on another
   worker, because the job's transaction never committed.
   Waiting jobs stay in their queue, where `jobs001`'s workers take them.
   The run refuses to turn on `job_containers_run_only_on_the_jobs_servers`
   while `jobs_servers` holds no server, unless every app has
   `jobs_command: ""` (no background jobs, so no job container to move).

   **Check:** the run passes; step 5 verifies the result.

5. **Verify** the checklist item `jobs_servers`: on each app server,
   `ssh -F ssh/config root@10.20.1.1 'podman ps --all'` lists no `-jobs`
   container, and step 3's check of `jobs001` still passes, with a job
   from after the `every_server` run for step 4's commit.
   For each app server, use the server's `address` from
   `inventories/servers.yml` in the SSH command.
   Then record the item `done`.

   **Check:** both points above passed.

## More jobs servers

1. **Add `jobs002` and up** to `jobs_servers` with [Add a server](add_a_server.md).
   Each server's job containers take jobs after the first configuration run.

   **Check:** step 8 of [Add a server](add_a_server.md), and step 3's
   check of [Adding jobs servers](#adding-jobs-servers) on the new server.

By default, each jobs server warns when CPU stays above 70% or memory above 75% for 15 minutes
(`cpu_is_below_70_percent`, `memory_is_below_75_percent` and `alert_after_failing_for` of
`jobs_server_capacity` in `mmwatchdog_checks/jobs_servers.yml`). The reasons beside them: 30% of CPU
stays free as headroom, and 25% of memory leaves room for a restart of the job containers.
The fix is another jobs server.

## The way back

1. **Turn the setting off:** set `job_containers_run_only_on_the_jobs_servers` back to
   `false`, commit, and push. Each app server starts its job containers again, alongside the jobs servers' containers.

   **Check:** the run passes. `util01`'s run stops at the first app server that fails, so a passed run
   started the job containers on every app server.

2. **Check one app server.** On one app server, check that each app's job container runs.
   Check the job containers' journals for a database connection and a
   completed job, as in step 3 of [Adding jobs servers](#adding-jobs-servers). Use the app server's address for SSH.

   **Check:** each app's job container runs, and its journal shows a
   database connection and a completed job.

3. **Remove the jobs servers.** Run `remove_server` for each jobs server, as
   [Remove a server](remove_a_server.md) describes.

   **Check:** each `remove_server` run passes.

4. **Delete the jobs servers** from the inventory and the jobs servers' lines
   from `ssh/known_hosts`, push, and destroy the jobs servers.

   **Check:** as step 4 of [Remove a server](remove_a_server.md) says:
   `util01`'s `every_server` run for the commit passed, and
   `./server_management_scripts/list_the_servers_at_the_provider` no
   longer lists the jobs servers.

## If something is different

- **A jobs server that stops reporting** is replaced, the only one too, by
  the three replacement playbooks, which the triage agent runs while
  `jobs_servers` is in
  `triage_agent_server_work.pools_whose_failed_servers_the_triage_agent_replaces`
  ([A failed server: the three replacement playbooks](replace_a_server.md#a-failed-server-the-three-replacement-playbooks)).
  The new server, such as `jobs003` for `jobs002`, takes the failed server's
  place in the inventory in one commit, so `remove_server`'s refusal of the
  last jobs server never applies, and
  `job_containers_run_only_on_the_jobs_servers` stays on.
- **`remove_server` refuses a jobs server:** while only jobs servers run jobs, `remove_server` refuses to remove the last one.
  `remove_server` removes another jobs server only after every remaining
  jobs server runs each app's job container.
  Before `job_containers_run_only_on_the_jobs_servers` is on, the app servers
  also run job containers, and removal does not check the jobs servers.
- **The run refuses step 4's setting:** the run refuses
  `job_containers_run_only_on_the_jobs_servers` while `jobs_servers`
  holds no server, unless every app has `jobs_command: ""`.

## How the move works

This part explains the steps, for the reader who wants the reasons.

The role, `roles/jobs_server`, and its fleet stages are present from the initial setup.
A jobs server starts job containers in its first run.
The new server joins WireGuard at first boot. After the first configuration
run, the jobs servers and app servers run jobs together,
so the move loses no job.
The setting `job_containers_run_only_on_the_jobs_servers` in `mmx_project_settings.yml` then removes job containers from the app servers.

A Postgres job queue that locks each job's row while a worker runs the job
lets app servers and jobs servers take jobs together.
The row lock keeps workers from taking the same job.
Solid Queue and good_job are programs for running background jobs with a
queue in Postgres. Solid Queue uses `FOR UPDATE SKIP LOCKED`, and good_job
uses advisory locks, to keep workers from taking the same job.
