# Verify a disposable destination

Use Linux, Node.js 24, PostgreSQL 17 client tools, the locked Node dependencies, and a private S3-compatible test bucket.
Run from the example directory on the disposable Linux machine as root.
The settings helper uses the local PostgreSQL administrator to create a new role and database.
Provide the protected export, native inventory, and fixture password file copied from the source.

```sh
npm ci --ignore-scripts --no-audit --no-fund
export EXPORT_DIR=/secure/state-export
export COOLIFY_NATIVE_INVENTORY_FILE=/secure/native-after-freeze/coolify.json
export FIXTURE_PASSWORD_FILE=/secure/fixture-password
export REHEARSAL_NAME=coolify_first
export REHEARSAL_SETTINGS_DIR=/secure/coolify-first-settings
export REHEARSAL_FIRST_PORT=18001
export REHEARSAL_S3_ENDPOINT=http://127.0.0.1:9090
python3 scripts/prepare-rehearsal.py
. "$REHEARSAL_SETTINGS_DIR/settings.env"
node scripts/create-bucket.mjs
```

The helper creates new resources and refuses an existing settings directory.
`settings.env` uses shell quoting and is loaded by the shell. It is not a Docker environment file.
The configured S3 endpoint must already answer locally before `create-bucket.mjs`.
For a standalone synthetic service, start the following container first:

```sh
docker run -d --name coolify-rehearsal-storage \
  --publish 127.0.0.1:9090:9090 --env debug=false \
  docker.io/adobe/s3mock@sha256:cf5b4f0b6200c4b636b779b93db1847419f6bd082c0b6cd88ee409dcaa350f9b
```

Wait for the service before running `create-bucket.mjs`.
Create the PostgreSQL restore connection from the protected URL without putting a password on the command line:

```sh
node --input-type=module -e '
import {spawnSync} from "node:child_process";
const u=new URL(process.env.DATABASE_URL);
const result=spawnSync("pg_restore",["--no-owner","--no-acl","--exit-on-error","--dbname="+u.pathname.slice(1),process.env.EXPORT_DIR+"/database.dump"],
 {stdio:"inherit",env:{...process.env,PGHOST:u.hostname,PGPORT:u.port,PGUSER:u.username,PGPASSWORD:u.password}});
process.exit(result.status??1);'
node scripts/verify-export.mjs
node scripts/compare-database.mjs
node scripts/import-objects.mjs
```

The comparison runs before any destination request changes session state.
Clear the restored HTTP maintenance gate, keep report work paused, then start two web processes:

```sh
node --input-type=module -e 'const {pool}=await import("./database.mjs");await pool.query("UPDATE controls SET maintenance=false WHERE id=1");await pool.end();'
PORT=18001 node server.mjs > /secure/portal-web-1.log 2>&1 &
portal_web_pid_1=$!
PORT=18002 node server.mjs > /secure/portal-web-2.log 2>&1 &
portal_web_pid_2=$!
```

Use the two ports selected in `REHEARSAL_FIRST_PORT` if different.
After both health URLs return HTTP 200, run:

```sh
node --test tests/portal.test.mjs
REHEARSAL_CONFIRM=disposable-destination node tests/import-conflict.mjs
kill "$portal_web_pid_1" "$portal_web_pid_2"
wait "$portal_web_pid_1" "$portal_web_pid_2"
```

The object conflict check deliberately changes a file in the disposable bucket, verifies refusal, and restores the original bytes.
The suite checks existing passwords and IDs, owned records, wrong-owner refusals, exact private bytes, shared sessions, CRUD, and logout revocation.
A killed report transaction must leave pending work available.
Concurrent report workers must commit distinct claims and correct output.
The hourly cleanup command must commit only once during overlap.
Migration checksums, database reconnection, malformed requests, and production-seed refusal are checked too.

For the seed check, use another empty disposable database and bucket.
Set `REHEARSAL_CONFIRM=disposable-destination` and run:

```sh
node --test tests/seed-test-data.test.mjs
```

The seed check exercises both allowed environments, repeat runs, bulk accounts, smaller-count preservation, and production/unset refusals.

Native migration proof also needs the following checks outside this restored-copy suite:

- Compare a normal `read` token with `read:sensitive`; verify exact recovered values privately against the running production container.
- Export shared scopes, runtime/build flags, storage mounts, tasks, and task execution history.
- Disable Scheduled Tasks, automatic/preview deployment and manual webhook paths, then verify fresh native state.
- Copy files to the destination, retain PostgreSQL on the old host, and exercise login, ownership, private downloads, new writes, and a source-issued session over WireGuard.
- Follow the Stack [database-move procedure](../../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md) and its copy/switch playbooks; record the HTTP writer and switch measurements.
- Stop the source guest and repeat customer actions at the destination.

Independent replay uses a new app copy, database, bucket, settings directory, and ports.
S3Mock proves byte/API behavior but does not prove production R2 access control.
A same-host connection reset does not prove primary switching. Keep the actual replication result separate in the test record.

## Source session and database transition

Before freezing the source, load its fixture password and set `SOURCE_APP_URL` and a new protected `SOURCE_SESSION_FILE`.
Run `node tests/save-source-session.mjs` to retain a source-issued session.
After moving the app/files and clearing maintenance on the old database, set `APP_URL` to the destination and `TRANSITION_CHECKPOINT_FILE` to a new protected filename.
Run `node tests/check-transition.mjs --old-database` while the destination still uses the old database over WireGuard.
After the Stack logical-replication switch and source shutdown, run `node tests/check-transition.mjs` again.
The second check verifies that the pre-replication destination record and uploaded bytes survived the database move.
