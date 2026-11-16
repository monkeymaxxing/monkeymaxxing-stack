# Move a Rails/PostgreSQL portal from Kamal

This example preserves a Rails portal while replacing Kamal deployment with the Stack's release procedure.
The source uses PostgreSQL, private S3-compatible files, and separate web, worker, and clock roles.
SQLite conversion is outside this example.

Start with [the Kamal guide](../../../docs/app-platform-migrations/from-kamal.md).
Use [the common container migration procedure](../../../docs/app-platform-migrations/from-any-container-platform.md) for the shared move.
The [test record](test_record.md) separates the earlier standalone proof from the supported Stack procedure.

## Acceptance contracts

- The source runs through Kamal 2.12.0, with a PostgreSQL accessory and the production destination selected.
- Production secrets override common values. `.kamal/secrets` is absent from a destination-specific secret resolution.
- Two users register through HTTP, create records, upload private documents, and request reports before migration.
- Returning passwords, account IDs, owner links, record IDs, file keys and bytes, report state, and migration versions survive.
- Moving the app leaves PostgreSQL on the source host. The destination reaches the old database over WireGuard.
- Only the destination owns workers and scheduling after the app move. Source deployment automation cannot restart execution.
- PostgreSQL replication carries writes made after the initial copy. Final comparison includes every public table.
- The Stack copy and switch playbooks own database movement. App containers stay running while the Stack fences writes and switches writable logins.
- Stopping the source database and source host leaves destination accounts, private downloads, reports, and scheduling operational.
- Previous-release CSS remains available through a release. This portal has no lazy client routes.
- Public text claims only the checks in `test_record.md`. Protected dumps, passwords, cookies, and private bytes remain outside Git.

## Contents and data

`app/` is a complete copy of the Rails portal. Builds and runtime require no sibling example.
`source/` holds the Kamal base configuration, production override, and secret-file patterns.
`tests/` holds customer-action checks. The Stack owns the database-move implementation.

PostgreSQL owns accounts, hashed sessions, owned records, document metadata, transactional reports, and Rails migration versions.
`schedule_runs` adds one committed session-cleanup occurrence per UTC date.
The daily task removes expired sessions. Starting after a missed day runs today's occurrence once, without replaying every missed day.
The occurrence receipt and session removal share one transaction.

The source runs `bin/portal jobs` and `bin/portal clock` in separate Kamal roles.
The destination uses `bin/migration-jobs`, which starts both commands and stops both children on termination or child failure.
The queue uses PostgreSQL row locks. No Redis or SQLite queue is involved.

## Reproduce the source

The source fixture needs Debian 13, Docker, Git, Ruby 3.3 or newer, Bundler, SSH, and Kamal.
Run the source controller on the source host for this fixture.
Use a running Stack system for the destination and follow [Move a database into the Stack][database-move].
Python runs the customer-action checks. The separate Rails service suite also needs psycopg 3.

Install the pinned deployment tool on the source host:

```sh
gem install kamal -v 2.12.0 --no-document
```

Copy `app/` into a protected source working directory.
Copy `source/deploy.yml` and `source/deploy.production.yml` into that app's `config/` directory.
Copy the secret patterns into `.kamal/secrets-common` and `.kamal/secrets.production`.
Do not put the generated `.kamal/` directory in a build or Git archive.
The supplied `.dockerignore` excludes secrets from Docker's build context.

Supply these variables through a protected controller environment:

| Variable | Purpose |
| --- | --- |
| `KAMAL_SOURCE_HOST` | Source host reachable by SSH from the controller |
| `SOURCE_DATABASE_BIND` | Source database's private address, reachable by app containers and the destination over WireGuard |
| `SOURCE_STORAGE_ENDPOINT` | Source private S3-compatible endpoint, reachable from the source app containers |
| `SOURCE_APP_ORIGIN` | Exact browser HTTPS origin, without a trailing slash |
| `COMMON_SECRET_KEY_BASE` | Common Rails signing key used to exercise destination override |
| `PRODUCTION_SECRET_KEY_BASE` | Production Rails signing key, retained by the destination |
| `SOURCE_DATABASE_URL` | Source accessory connection, with libpq parameters and the private database address |
| `SOURCE_POSTGRES_PASSWORD` | Accessory bootstrap password; use a generated synthetic value for rehearsal |
| `SOURCE_R2_ACCESS_KEY_ID`, `SOURCE_R2_SECRET_ACCESS_KEY` | Source bucket-scoped credentials |
| `FIXTURE_PASSWORD` | Synthetic HTTP fixture password, 12 to 72 bytes |

Use different generated common and production Rails keys.
If changing `SOURCE_APP_ORIGIN`, set `proxy.host` in `deploy.yml` to the origin's hostname.
The source database URL must use the password and database configured for the accessory.
Create a private source bucket named `source-uploads` before starting web.
The `127.0.0.1:5555` registry is an unauthenticated loopback fixture on the combined source/controller host.
The public `fixture` login strings are placeholders and provide no authorization.
A separate controller needs a registry reachable from every Docker daemon; that arrangement is not exercised by this fixture.

From the copied app directory on the source host, build and publish the image, then deploy with Kamal.
The registry is disposable, bound to loopback, and runs only for this rehearsal.

```sh
docker run -d --name migration-registry \
  --publish 127.0.0.1:5555:5000 registry:2.8.3
docker build --label service=migration-portal --tag 127.0.0.1:5555/example/migration-portal:r1 -f Containerfile .
docker push 127.0.0.1:5555/example/migration-portal:r1
export VERSION=r1
kamal accessory boot postgres -d production
kamal deploy --skip-push --version r1 -d production
```

Use a recorded release version when the source directory has no Git revision.
The prebuilt image needs `--label service=migration-portal` because Kamal verifies the service label before boot.
Each source role runs `bin/portal migrate` before its web, worker, or clock command.
Rails serializes concurrent source migrations with its advisory lock.
The Stack destination uses its normal deploy-time migration command after the database move.
Run no schema migration during logical copying.
The live test record gives the exact commands used for the source installation.

Run fixture commands from the `from-kamal/` example directory, outside `app/`.
On the test runner, resolve `portal.example.com` to the source's private address.
The hostname must match Kamal's proxy route and Rails' allowed host.
Populate through HTTP using the example's test script:

```sh
python3 tests/check_migrated.py populate \
  --url http://portal.example.com \
  --origin https://portal.example.com \
  --manifest /secure/kamal/source-users.json
```

The mode-600 manifest stores synthetic identities, IDs, temporary session cookies, and expected bytes.
Use the source address and configured origin for the actual rehearsal.
Run `app/tests/check_portal.py` against the source to exercise CRUD, shared sessions, guessed-ID refusal, reports, and logout.

## Move PostgreSQL through the Stack

Follow [Move a database into the Stack][database-move].
The [Kamal guide's accessory preparation](../../../docs/app-platform-migrations/from-kamal.md#restore-on-linux) covers source access, role initialization, published ports, and fencing limits.
Set the inventory's `database_moving_in.apps` to the actual Stack app key and use `database_name: portal` for this fixture.
Keep the old accessory host outside inventory nodes and groups.

The procedure's app-first `every_server` run connects web and jobs to the old accessory over WireGuard.
Verify the saved users and files through the destination app before copying.
Use the Stack's two playbooks from the systems desk:

```sh
./server_management_scripts/run_mmx_on_util01 run copy_the_database_moving_in
./server_management_scripts/run_mmx_on_util01 run switch_to_the_database_moving_in
```

Read the complete procedure before either command.
The [copy playbook][database-copy] owns schema loading and continuous logical replication.
The [switch playbook][database-switch] owns the fence, final catch-up, sequences, large objects, subscription cleanup, and writable-role switch.
Leave Stack app containers running and measure acknowledged HTTP writes during the switch.
Follow the procedure's failure recovery and post-switch cleanup before another `every_server` run.
No database dump/restore route or custom copy/switch helper is supplied for moving into the Stack.

## Move private objects

Create a mode-700 parent directory on the source host. Leave its `objects` child absent.
Create a mode-600 `/secure/kamal/source.env` with the resolved source Rails environment from the table and Rails guide.
The file must contain actual runtime names, including `DATABASE_URL`, `SECRET_KEY_BASE`, `APP_ORIGIN`, `R2_ENDPOINT`, `R2_BUCKET`, `R2_ACCESS_KEY_ID`, and `R2_SECRET_ACCESS_KEY`.
Run the selected source image with that protected parent mounted persistently:

```sh
install -d -m 700 /secure/kamal
docker run --rm --user 0 --network host \
  --env-file /secure/kamal/source.env \
  --env EXPORT_DIR=/export/objects -v /secure/kamal:/export \
  127.0.0.1:5555/example/migration-portal:r1 \
  bundle exec ruby scripts/transfer_objects.rb export
```

The one-off transfer container uses UID 0 to read and write root-owned protected exports.
The web and jobs image keeps its normal UID 1000.
The tool inventories all current bucket keys, writes private bytes, and verifies every document reference.
Freeze uploads before the final export. Preserve the source manifest and object keys.
Copy the entire `/secure/kamal/objects` tree to the destination through an authenticated encrypted connection.
Use the destination image tag and mode-600 destination runtime file for import:

```sh
podman run --rm --user 0 --network host \
  --env-file /secure/kamal/destination.env \
  --env EXPORT_DIR=/export/objects -v /secure/kamal:/export:ro \
  ghcr.io/example/rails-portal:REVIEWED_COMMIT \
  bundle exec ruby scripts/transfer_objects.rb import
```

Choose a new empty destination bucket and its separate credentials.

The importer checks saved lengths and hashes, creates each object conditionally, and downloads each object to verify exact bytes.
The app's source and destination storage environments remain separate.
An interrupted import needs another empty disposable bucket for this rehearsal.

## Verify the destination

Use [the Rails integration guide](../../../docs/app-frameworks/rails-pg.md) for the app's settings, native driver behavior, and existing destination checks.
Set `jobs_command: bin/migration-jobs` and `asset_directory: /app/public/assets`.
The source PostgreSQL data and migration ledger remain unchanged in shape.
The three migration versions include the added schedule receipt table.
Replace the Rails guide's first restore-drill query with this app's three-version check:

```yaml
restore_drill_check_queries:
  - name: the_migrations_came_back
    sql: SELECT count(*) = 3 FROM schema_migrations WHERE version IN ('20261104000100', '20261104000200', '20261106000100')
```

Run the returning-user check against each destination stage, first against the old database and again after the database switch:

```sh
python3 tests/check_migrated.py verify \
  --url http://127.0.0.1:8007 \
  --origin https://portal.example.com \
  --manifest /secure/kamal/source-users.json
python3 app/tests/check_portal.py \
  --server-a http://127.0.0.1:8007 \
  --server-b http://127.0.0.1:8008 \
  --origin https://portal.example.com
```

Run the destination commands on the destination host.
For a remote runner, map `portal.example.com` to the destination private address and use that hostname with the assigned ports.
Use the protected fixture password environment for both commands.
`--expect-pending` checks saved pending reports while all workers remain stopped.
Use a separate empty database and bucket for the copied Rails `app/tests/services.py` suite.
That suite deliberately populates and mutates its database.

Use a separate disposable scheduling database before any clock has run.
Insert an expired synthetic session, then start two overlapping `bin/portal schedule-once` processes.
Verify deletion, one receipt for the current UTC date, and the receipt's `removed_sessions` count.
Stop source roles and source automation, restart destination jobs, and verify source execution stays stopped.
Finally stop the source database and repeat returning users, new writes, downloads, and reports.

## Evidence

Save tool versions, source and destination image digests, source commands, protected row comparisons, object checksums, schedule receipts, and timing.
Record the Stack switch playbook's pause parts and HTTP acknowledgements throughout the switch.
Keep container start times unchanged; customer recovery ends at the first confirmed destination write.
Record exactly which endpoint serves the test. A private-IP rehearsal does not prove public DNS or TLS cutover.

## Backups and independent replay

Use the database procedure's verified source backup and final Stack backup requirements.
Keep backups, `source-users.json`, and the object export protected outside Git.
A recovery backup is separate from the logical-replication migration route.

For a fresh migration replay, follow the Stack database procedure with isolated app/database names, bucket, and ports.
Repeat the saved-user and shared Rails HTTP checks before and after the switch, then with the source accessory stopped.
Keep source workers and schedules stopped throughout the destination checks.
The test record's earlier independent dump-restore check proves application recovery from that saved backup, not the current Stack switch playbook.

[database-move]: ../../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md
[database-copy]: ../../../skills/monkeymaxxing-stack/systems_repository_template/playbooks/copy_the_database_moving_in.yml
[database-switch]: ../../../skills/monkeymaxxing-stack/systems_repository_template/playbooks/switch_to_the_database_moving_in.yml
