# Fix database writes that hang

**When to use this page:** the apps' writes get no answer, while reads work.

**What this page does:** the replica that no longer copies from the
primary leaves the inventory and the failover formation, so the primary
stops waiting for that replica, and a new database server takes the
removed replica's place.

**Who acts:** database servers always need a person
([The rules](../AGENTS.md#the-rules), "What the triage agent may do
without a person"). The triage agent hands over to a person and does not
follow this page ([When to hand over](../triage_agent_rules.md#when-to-hand-over)).
The coding agent does every step from the systems desk. The person
approves the removal in step 4 and decides about the removed replica in
step 11. The person runs nothing in the person's own terminal.

**Terms:** this page uses the Stack's terms, such as primary, replica,
failover monitor, failover formation, inventory and one-time playbook.
[Technical terms](../talking_with_the_team.md#technical-terms) explains
each term.

## Before you start

- **Run the investigation from `coding-agent` on the systems desk.**
  Use the desk's production SSH socket and `ssh/config`; the laptop
  connects only to the desk. The socket is `/run/desk-ssh-agent/socket`
  ([What this repository is](../AGENTS.md#what-this-repository-is)).
- **Never start or restart the replica that is not copying from the primary,
  or the replica's Postgres or `pgautofailover`, to make writes continue.**
  Reason: the replica's data history may differ from the primary's after a
  restart during failover. The failover monitor could count the restarted
  replica as healthy and make it the primary at the next failover. Making
  the restarted replica the primary would lose every write since the
  histories split.
- **A push alone changes no server.** Apply each configuration change as
  [Making a change](../AGENTS.md#making-a-change) says: run `every_server`
  or the playbook the step names.

## Confirm the cause

The checks below test whether the primary waits for a replica to confirm
the primary's writes while no replica copies from the primary.

1. **Find the primary and the replicas,** on `util01`:
   `ssh -F ssh/config root@10.20.0.1 'sudo -u postgres pg_autoctl show state --pgdata /var/lib/postgresql/17/pg_auto_failover_monitor --formation production'`.
   **Check:** the output lists each database server of the formation by
   name, with its state. The primary's line shows `primary`. Each database
   server's private address is its `private_ip` in `inventories/servers.yml`,
   such as `10.20.2.1` for `db01`.
2. **Check on the primary for writes that wait for a replica:**
   `ssh -F ssh/config root@10.20.2.1 'sudo -u postgres psql -XAt -h /var/run/postgresql -p 5432 -c "select count(*) from pg_stat_activity where wait_event = \$\$SyncRep\$\$" -c "select application_name, state from pg_stat_replication"'`,
   with the primary's private address from step 1.
   **Check:** the command prints a count above 0 and no replica. The
   replica that is not copying from the primary is the replica from step 1
   that this command does not list. When the result is different, the
   writes hang for another cause, and this page does not fit: stop and tell
   the person what the command printed.
3. **Read the `pgautofailover` log on the primary,** `journalctl -u pgautofailover`:
   `ssh -F ssh/config root@10.20.2.1 'journalctl -u pgautofailover'`.
   Reason: the primary's `pgautofailover` repeated the line below in the
   Stack's tests on real servers, while writes hung.
   **Check:** the log repeats `we don't have a quorum candidate yet`. When
   the log does not repeat that line, stop and tell the person, as in
   step 2.

## Remove the replica that does not copy from the primary

4. **Tell the person which replica you remove and why, and get the
   person's approval.**
   **Check:** the person approves. Reason: database servers always need a
   person.
5. **Delete the replica from the inventory, and delete the replica's lines
   from `ssh/known_hosts`.** `ssh/known_hosts` lists each server by its
   private address, such as `10.20.2.2`.
   **Check:** `git diff` shows only the replica's lines removed.
6. **Move each one-time playbook that names the replica to
   `one_time_playbooks/completed/`,** as [Removing a server](remove_a_server.md)
   requires: `mmx complete-one-time-playbook NAME` while the server still
   answers, or `git mv` for a server that is gone.
   **Check:** `grep -lw db02 one_time_playbooks/*.yml`, with the replica's
   name, lists no playbook
   ([Removing a server](remove_a_server.md) gives the command).
7. **Push the inventory deletion, the `ssh/known_hosts` deletions, and the
   one-time playbook moves together,** in one commit, as steps 1 to 4 of
   [Making a change](../AGENTS.md#making-a-change) say: `git add PATH` for
   each path, `git commit`, the synchronization snippet, then
   `git push origin main`.
   Reason: `mmx validate`, and therefore every run, refuses an unfinished
   playbook that names a server missing from the inventory.
   **Check:** `mmx validate` passes before the push.
8. **Run `every_server` on `util01`:**
   `./server_management_scripts/run_mmx_on_util01 run every_server`.
   `util01`'s run removes the replica from the formation, the database group
   managed by the failover monitor. The primary then stops waiting for the
   removed replica.
   **Check:** the run passes. Then repeat step 2's command: the count is 0,
   and the apps' writes answer again.
9. **Update this desk's WireGuard peers:**
   `sudo -n update-this-desks-wireguard-peers`.
   Reason: the push removed a server from the inventory, and this desk's
   WireGuard peers must match the servers
   ([Removing a server](remove_a_server.md)).
   **Check:** the command ends without an error.
10. **Power off the removed replica at the provider.** Find the replica's
    provider ID in `./server_management_scripts/list_the_servers_at_the_provider`,
    then run
    `./server_management_scripts/power_off_a_server_at_the_provider --server-id ID`.
    Reason: the replica may hold writes that the primary lacks, so it stays
    at the provider, powered off, until the person decides.
    **Check:** the script returns `"power_state": "stopped"`
    ([the provider-script contract](../server_management_scripts/README.md#write-the-teams-provider-scripts)).
11. **Ask the person whether the removed replica's writes matter.** When
    they do not, destroy the replica, as step 3 of
    [Removing a server](remove_a_server.md) says:
    `./server_management_scripts/destroy_a_server_at_the_provider --server-name db02`,
    with the replica's name.
    **Check:** `./server_management_scripts/list_the_servers_at_the_provider`
    no longer lists the replica.
    Until then, the daily `check_for_a_leftover_restore01` job on `util01`
    fails with "servers at the provider that are not in the inventory",
    naming the replica, and MMWatchdog's
    `systemd_units/no_systemd_unit_has_failed` warns on `util01`. This is
    expected while the replica waits for the person's decision.

## Replace the removed replica

12. **Add a new database server** in place of the removed replica
    ([Replacing a server](replace_a_server.md#replacing-a-server)).
    **Check:** the checks of that procedure.
