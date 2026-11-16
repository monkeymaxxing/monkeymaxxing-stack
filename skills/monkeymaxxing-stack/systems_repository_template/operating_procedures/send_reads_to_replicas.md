# Send reads to replicas

**When:** the database servers warn about CPU use, and most of their work is reads.

**What this page does:** the app sends some of its reads to the database
replicas, so the primary has less work. Change the app to use
`DATABASE_READ_URL` only for reads that can return older data.
`DATABASE_READ_URL` lists every database server. The app's database driver
prefers a replica and uses the primary when no replica answers, as with
one database server.

**Who acts:** you, the coding agent, do every step. The change is in the
app's repository only. The person chooses which reads may return older
data, from the list in step 1.

## Before you start

- **No setting in this systems repository changes.** Every app's secrets
  file, `/etc/<app>/<app>.env` on the app servers, already holds
  `DATABASE_READ_URL`, so the change is in the app's repository only.
- **Reads through `DATABASE_READ_URL` can return older data.** A replica
  can be behind the primary while the replica catches up. Keep reads that
  need the latest data on the primary. For example, a read that must see
  the app's own latest write needs the primary.

## Steps

1. **Check that a replica exists and that reads cause the load.** The
   system needs at least two database servers. With one, follow
   [Add a second database server](add_a_second_database_server.md) first,
   because `DATABASE_READ_URL` then reaches only the primary. Read the
   primary's CPU check, with the primary's WireGuard address (`10.20.2.1`
   is `db01`; a row with `f` in step 5's command is the primary):
   `ssh -F ssh/config root@10.20.2.1 'mmwatchdog check-now database_server_capacity'`.
   Then name the busiest queries for the person from the app's own
   records, such as its slow-query log or its performance dashboard, and
   say which of them are reads that may be a moment behind.
   **Check:** the system has two or more database servers, and the
   busiest queries are mostly reads.
2. **Give the app a second connection pool for reads, in the app's
   repository.** Follow the app's language in "Each language" of
   `files_for_your_app/database_driver_finds_the_primary.md`, in the
   installed `monkeymaxxing-stack` skill's directory, beside `SKILL.md`. Each
   language's entry shows the read pool built from `DATABASE_READ_URL`,
   such as Rails' `primary_replica` with `connects_to`, or Django's
   database router. Give the read pool a connection lifetime, such as
   Rails' `max_age`, pgxpool's `MaxConnLifetime`, or pg.Pool's
   `maxLifetimeSeconds`. Reason: after a failover, a read connection to the
   replica that became the primary stays there until the pool replaces
   it, so without a lifetime the reads keep loading the new primary.
   No check here: step 3's test and step 5 check the read pool.
3. **Send only the chosen reads to the read pool.** Everything else, and
   every read inside a request that wrote, stays on `DATABASE_URL`. Add a
   test that a write followed by its read uses the primary.
   **Check:** that test passes.
4. **Release the new app version,** with
   [Deploy and roll back an app release](deploy_and_roll_back_an_app_release.md).
   **Check:** the checks of that page.
5. **Verify** the checklist item `read_replicas`. Each replica answers the
   apps' reads, which this command shows as rows starting with `t`, a
   replica, with the app's login and its count of connections:

   ```sh
   # This systems desk, in the systems repository; the command runs on every database server:
   ./server_management_scripts/run_mmx_on_util01 run-command --nodes database_servers --run-as-node-user-account postgres -- "psql -X -At -c \"select pg_is_in_recovery(), usename, count(*) from pg_stat_activity where backend_type = 'client backend' group by 1, 2\""
   ```

   A day later, the primary's `cpu_is_below_50_percent` check, from step 1,
   passes at the busiest hour. Record both readings in the item's
   `last_result`.
   **Check:** a row starting with `t` shows the app's login, and the CPU
   check passes.

## If something is different

- **If the system has one database server:** follow
  [Add a second database server](add_a_second_database_server.md) first,
  as step 1 says.
- **If the CPU check still fails a day later:** the reads may not be the
  load. Return to step 1's list of the busiest queries with the person.
