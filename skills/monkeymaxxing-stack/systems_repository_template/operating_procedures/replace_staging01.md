# Replace staging01

**When to use this page:** `staging01` is lost or broken, or `staging01`
needs another server type, such as a bigger type after a staging deploy
that lacked memory.

**What this page does:** the old `staging01` is destroyed. A new server
takes the name `staging01` and the inventory's private address,
`10.20.0.2`. The seed command fills staging's database again. Nothing is
restored from a backup.

**Who acts:** the coding agent does every step from the systems desk. The
person decides only about a bigger or dearer server type (see Before you
start).

## Before you start

- **Read [the systems repository rules](../AGENTS.md#the-rules) first.**
- **A bigger `staging01` waits for the person's yes.** Before step 1, when
  the new `staging01` is a bigger or dearer type than the old one, such as
  after a staging deploy that lacked memory, ask the person, with the new
  type's monthly price from the provider. The same type at the same price
  needs no question.
  Reason: `staging01` is outside the growth limits, as step 1 of
  [Add a server](add_a_server.md) says, and this procedure follows only
  that procedure's steps 2 to 7.
- **A push alone changes no server.** Apply each configuration change as
  [Making a change](../AGENTS.md#making-a-change) says: run `every_server`
  or the playbook the step names.

## Steps

1. **Destroy the old server** with
   `destroy_a_server_at_the_provider --server-id` and `staging01`'s
   provider ID from a fresh listing. Delete the old server's line from
   `ssh/known_hosts`.
   **Check:** the script returns `"deleted": true`
   ([the provider-script contract](../server_management_scripts/README.md#write-the-teams-provider-scripts)),
   and `ssh/known_hosts` has no line for `10.20.0.2`.
2. **Create and set up the new server.** Follow steps 2 to 7 of
   [Add a server](add_a_server.md).
   The shared steps cover server creation, inventory, the SSH host key,
   first-boot WireGuard enrollment, configuration, and rebooting.
   Use `staging01` and `staging_server` instead of the example's app-server
   name and group, and keep the inventory's existing private address.
   `util01`'s `every_server` run sets up the new `staging01` with an
   empty database and starts each app's release from
   `deployed_image_tags.staging`.
   **Check:** the checks of those steps, such as step 6's enrollment check.
3. **Fill staging's database** with each app's seed command, as in step 7
   of [Add staging01](add_staging01.md#adding-staging01).
   **Check:** step 4 below checks the result.
4. **Check the result:** each app's health URL answers 200 through Caddy
   on `staging01`, as in step 8 of [Add staging01](add_staging01.md#adding-staging01),
   and `ssh -F ssh/config root@10.20.0.2 mmwatchdog status` exits 0.
   **Check:** both hold.

## If something is different

- **A check fails:** stop, and tell the person which check failed and
  what it printed.
- **`mmwatchdog status` exits 3 and lists a check as `unknown`:** step 8
  of [Add a server](add_a_server.md) explains why, and when the check
  runs again.

## Why staging gets no backup

There is only one staging server. Staging holds only the seed command's
invented test data, so the new `staging01` gets its data from the seed
command again.

Reason: staging keeps no backups. The seed command makes the same
invented data at any time, so a backup of it would protect nothing, and
would cost a bucket, a key, a passphrase in the password manager, and
checks.
