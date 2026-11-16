# Add a second database server

**When:** the first paying customers arrive, add `db02`. Later, add replicas
for apps configured to read from replicas
([Send reads to replicas](send_reads_to_replicas.md)).

**What this page does:** a new database server copies the primary's data
and joins the failover formation as a replica, which can take over as
primary.

**Who acts:** database servers always need a person
([The rules](../AGENTS.md#the-rules), "What the triage agent may do
without a person"). You, the coding agent, do the steps with the person.

## Before you start

- **The shared server steps are in [Add a server](add_a_server.md).** In
  its examples, which add `app002`, use the new database server's name and
  addresses.

## Steps

1. **Follow steps 1 to 8 of [Add a server](add_a_server.md)
   for the new database server.** In `inventories/servers.yml`, use the
   `database_servers` group, whose `is_database_server` flag is already `true`.

   **Check:** step 8 of [Add a server](add_a_server.md) verifies the new
   server.

2. **For a Node.js app,** follow
   [A Node app through a switchover](test_a_nodejs_app_during_a_database_switchover.md#a-node-app-through-a-switchover)
   for the app's verification.

   **Check:** the check on that page passes.

3. **Verify `second_database_server`** in
   `monkeymaxxing_stack_checklist.yml`, before reporting that the app follows
   a change of primary.

   **Check:** the item's `verification` passed.

## If something is different

- **A later replica,** after `db02`: add it the same way, for apps
  configured to read from replicas
  ([Send reads to replicas](send_reads_to_replicas.md)).

## How the new server joins

During `every_server`, MMX runs `pg_autoctl create postgres` for the new
server. The new server copies the primary’s data and joins as a replica.
A healthy replica can take over as primary.
