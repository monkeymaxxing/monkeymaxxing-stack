# Test a Node.js app during a database switchover

**When:** a checklist item's `verification` in
[`monkeymaxxing_stack_checklist.yml`](../monkeymaxxing_stack_checklist.yml)
requires a switchover, and the system runs a Node.js app. For example, for
the checklist item `second_database_server`, test the switch to `db02` and back.

**What this page does:** use `check_database_failover.mjs` to test whether a Node.js app follows the
primary during a database switchover. Apps in other languages skip
`check_database_failover.mjs`.

**Who acts:** you, the coding agent, run every step from the systems desk.
The person runs nothing.

## Before you start

- **The skill must be installed on this systems desk** because the check uses the skill's copy of the Node files.
  The stack's repository gives the
  [skill installation instructions](https://github.com/monkeymaxxing/monkeymaxxing-stack#give-it-to-your-coding-agent).
  This systems repository holds no copy: the Node files belong to the apps.
  `SKILL_DIRECTORY` below is the directory that holds the skill's `SKILL.md`.
- **Run the systems desk commands from the systems repository's
  directory,** where `ssh/config` and `server_management_scripts/` are.
- **Run the check during each switchover.** For each Node app, run the check during each switchover required by the
  checklist item's `verification`.
- **When adding PgBouncer, repeat the check through PgBouncer**
  ([Adding PgBouncer](add_pgbouncer.md#adding-pgbouncer), step 5).
  PgBouncer lets many app connections share fewer Postgres connections.
  The app's env file then names PgBouncer's port, 6432, on each database
  server, so the check connects through PgBouncer.

## A Node app through a switchover

The check runs in a Node container on an app server while
`switch_database_primary` changes the primary.

1. **Start the check** in the background on an app server, for example for
   app `shop`.
   Replace `SKILL_DIRECTORY` with the installed skill's directory.
   Use the app server's WireGuard `address` from `inventories/servers.yml`
   instead of the example `10.20.1.1`.
   For another app, replace `shop` in the env file path and systems desk log path.
   Save the check command's output in a log on this systems desk.
   The log's last line gives the exit status of the whole command.
   The whole command's exit status includes failures before the check
   starts: the SSH connection, image pull, env file, or install may fail:

   ```sh
   { COPYFILE_DISABLE=1 tar -C SKILL_DIRECTORY/files_for_your_app/node -cf - check_database_failover.mjs pg_with_multiple_database_servers.mjs |
       ssh -F ssh/config root@10.20.1.1 \
         "podman run --rm -i --network host --env-file /etc/shop/shop.env docker.io/library/node:24-alpine sh -c 'mkdir /check && cd /check && tar -xf - && npm install --no-save --no-audit --no-fund --loglevel=error pg@8.23.1 && node check_database_failover.mjs'"
     echo "ENDED with exit status $?"; } > /tmp/shop_database_failover_check.log 2>&1 &
   ```

   No check here: step 2 checks that the check started.

2. **Wait for the check's first write,** such as `0.1 s write db01:5432 (primary)`,
   which usually comes within a minute. The wait below has no time limit:

   ```sh
   until grep -qE ' write |^ENDED' /tmp/shop_database_failover_check.log; do sleep 2; done
   cat /tmp/shop_database_failover_check.log
   ```

   **Check:** the log shows a ` write ` line.
   If the log ends with `ENDED` instead, the check ended before the switchover. Read the earlier lines for the cause.
   Fix the cause shown in the log, then start again at step 1.
3. **Switch:** `./server_management_scripts/run_mmx_on_util01 run switch_database_primary --var server_name=db02`.
   No check here: step 4 reads how the switch went for the app.
4. **Read how the check ended:**

   ```sh
   until grep -q '^ENDED' /tmp/shop_database_failover_check.log; do sleep 5; done
   cat /tmp/shop_database_failover_check.log
   ```

   The check prints each change in which server receives reads and writes.
   The check also reports how long writes failed.
   **Check:** the check passes only when the log says `PASSED` and ends with
   `ENDED with exit status 0`.

   A pass means writes moved to `db02` and succeeded for 10 rounds in a row.
   A new read connection also reached `db01`, now a replica.

   Otherwise, after 10 minutes from the check's start, the check prints
   `FAILED` and the check's last observation.
   The switchover playbook waits for up to 10 minutes.
5. **Back:** steps 1 to 4 again, with `--var server_name=db01`.
   For the return switch, step 4's pass means writes moved to `db01`
   and a new read connection reached `db02`, now a replica. Then
   remove the Node image from the app server, which nothing else uses:
   `ssh -F ssh/config root@10.20.1.1 podman rmi docker.io/library/node:24-alpine`.
   **Check:** step 4's check passes for the return switch.

## If something is different

**If the check fails through PgBouncer but passed directly,** a likely cause is a connection that stayed on the PgBouncer of the new replica.
The refresh is the automatic PgBouncer restart after Postgres starts or
changes between primary and replica. The restart closes PgBouncer's
client connections, so the clients reconnect.
Check that the refresh ran on the new replica, `db01` after the switch to
`db02`:

```sh
./server_management_scripts/run_mmx_on_util01 run-command --nodes db01 -- "journalctl -u refresh_pgbouncer_when_postgres_starts_or_changes_role.service --since '-15min'"
```

After the return switch to `db01`, the new replica is `db02`.
For the return switch, use `db02` instead of `db01` in the journal command.

The journal should show `Postgres is a standby: restarting PgBouncer, so its clients
connect again` once after the switch (step 2 of
[Adding PgBouncer](add_pgbouncer.md#adding-pgbouncer)).
The line shows that the restart was asked for, not that PgBouncer restarted.

## How the check works

The app already uses `pg_with_multiple_database_servers.mjs` to find the
primary after failover. The app's copy comes from the `monkeymaxxing-stack`
skill, in `skills/monkeymaxxing-stack` in the stack's repository.
The skill's `files_for_your_app/database_driver_finds_the_primary.md`
explains `pg_with_multiple_database_servers.mjs`.
The check, `check_database_failover.mjs`, is in the skill's
`files_for_your_app/node/` directory.

The check connects through `pg_with_multiple_database_servers.mjs`, using
the app's env file. The check takes `DATABASE_URL` for writes and
`DATABASE_READ_URL` for reads from the app's env file.
The skill's `files_for_your_app/database_driver_finds_the_primary.md`
describes the required URL settings under "What the stack gives each app".

In step 1's command, `tar` sends the check and its required file to the container.
`COPYFILE_DISABLE=1` keeps macOS's `tar` from adding `._` files.
The container installs `pg`, the Node.js Postgres driver, from the npm
registry. The check uses `pg` through
`pg_with_multiple_database_servers.mjs` to connect to Postgres.
