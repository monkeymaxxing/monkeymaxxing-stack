# Disposable verification

Run server checks on Linux with PostgreSQL 17, Node.js 24, Python 3 and a separate S3-compatible test server.
Use fresh databases and buckets. The tests create accounts, mutate rows, stop workers and terminate their own database connections.

## Queue adaptation

Create an empty dedicated PostgreSQL database and role.
Load the role's connection URL into `DATABASE_URL` through a protected environment file.
Install the example dependencies with `npm ci --ignore-scripts --no-audit --no-fund`.
Then run:

```sh
REHEARSAL_CONFIRM=disposable-destination npm test
```

`tests/queue.test.mjs` uses real PostgreSQL transactions and an injected SQS transport.
The checks cover failed dispatch, duplicate delivery after a lost acknowledgement, committed output before acknowledgement, delayed work and schedule ownership.
The injected transport does not prove AWS identity, SDK wire behavior, native queue timing or IAM permissions.
Actual source SQS checks belong in the native Fargate run.

## Transfer rehearsal

Prepare two empty PostgreSQL databases, distinct roles and two separate private test buckets.
For API compatibility only, a disposable S3Mock service can provide the buckets:

```sh
podman run -d --name ecs-rehearsal-storage --publish 127.0.0.1:9090:9090 \
  --env debug=false \
  docker.io/adobe/s3mock@sha256:cf5b4f0b6200c4b636b779b93db1847419f6bd082c0b6cd88ee409dcaa350f9b
```

Wait for the service and create the buckets before running the rehearsal.
S3Mock does not establish real bucket authorization.

Create mode-600 `source-settings.json` and `destination-settings.json` outside the repository.
Each file is a JSON object mapping environment-variable names to string values:

```json
{
  "DATABASE_URL": "postgresql://portal:REPLACE_WITH_URL_ENCODED_PASSWORD@127.0.0.1:5432/portal_source",
  "AWS_ENDPOINT_URL_S3": "http://127.0.0.1:9090",
  "AWS_REGION": "us-east-1",
  "AWS_ACCESS_KEY_ID": "synthetic-test-key",
  "AWS_SECRET_ACCESS_KEY": "synthetic-test-secret",
  "BUCKET_NAME": "portal-source-test",
  "S3_FORCE_PATH_STYLE": "true",
  "QUEUE_BACKEND": "sqs"
}
```

The destination file uses another database, role and bucket, with `QUEUE_BACKEND=postgres`.
The synthetic key values above are only for the isolated test server.
For a real bucket, load fresh scoped credentials from the authorized protected source.

Store a generated fixture password separately in a mode-600 file.
Choose an unused export path outside the app directory:

```sh
export SOURCE_SETTINGS_FILE=/secure/ecs/source-settings.json
export DESTINATION_SETTINGS_FILE=/secure/ecs/destination-settings.json
export FIXTURE_PASSWORD_FILE=/secure/ecs/fixture-password
export EXPORT_DIR=/secure/ecs/rehearsal-export
python3 tests/rehearsal.py
```

The runner migrates the synthetic source, populates two accounts through HTTP, freezes writes and stops the source web process.
The runner exports SQL, exact rows, code and private object bytes.
The runner restores into the empty destination and compares every row before account tests.
The runner imports bytes with conditional creation, then starts two destination web processes.

The destination checks cover existing passwords, stable IDs, ownership, exact downloads, CRUD, new uploads and cross-process logout.
Worker checks kill an actual completion transaction, then run concurrent workers against pending rows.
Schedule checks overlap two commands and verify one committed occurrence.
The tests also rerun migrations, terminate database connections, and check reconnection and production-seed refusal.

The source settings select SQS, but this local source runs no SQS worker.
The rehearsal's inventory explicitly records `fixture_kind=standalone-synthetic`.
A transfer-tool rehearsal cannot establish a native ECS execution freeze or queue replacement from real SQS.

The seed test uses a third empty database and bucket:

```sh
REHEARSAL_CONFIRM=disposable-destination node --test tests/seed-test-data.test.mjs
```

Supply `FIXTURE_PASSWORD`, database and storage settings through protected runtime configuration.
The seed test checks reruns, bulk synthetic accounts and rejection of production use.

## Verify the built destination image

Build the production image on Linux:

```sh
podman build -f Containerfile -t localhost/ecs-portal:rehearsal .
```

Use a fresh empty destination database and bucket for this additional run.
Restore the trusted `database.dump` with PostgreSQL 17 client tools before starting web or jobs containers:

```sh
pg_restore --no-owner --no-acl --no-publications --no-subscriptions --exit-on-error \
  --dbname="$PGDATABASE" "$EXPORT_DIR/database.dump"
```

Load destination `PG*` settings from the protected environment. Exclude operational publication and subscription metadata; replication is configured separately.
Do not restore over the destination database changed by the earlier rehearsal.

Create a mode-600 Podman environment file from the destination settings outside the build context.
Use `KEY=value` lines, `QUEUE_BACKEND=postgres`, `COOKIE_SECURE=false` for loopback HTTP, and the fresh destination database and bucket.
For the one-off test tools, also set `APP_DIR=/app`, `EXPORT_DIR=/export`, `APP_URL=http://127.0.0.1:18001`, and `SECOND_APP_URL=http://127.0.0.1:18002`.
Load `FIXTURE_PASSWORD` from the protected password file into the tool environment file without printing the value.

Verify the export, exact rows and imported object bytes through the built image:

```sh
for command in verify-export compare-database import-objects; do
  podman run --rm --user 0 --network host \
    --env-file /secure/ecs/destination-tools.env \
    -v /secure/ecs/rehearsal-export:/export:ro \
    localhost/ecs-portal:rehearsal node scripts/$command.mjs
done
```

The one-off tools use user 0 to read protected exports. Normal web and jobs containers use the image's `node` user.
Create a separate runtime environment file containing only app settings and destination credentials.

```sh
podman run -d --name ecs-destination-first --network host \
  --env-file /secure/ecs/destination-runtime.env --env PORT=18001 --env WEB_CONCURRENCY=2 \
  localhost/ecs-portal:rehearsal
podman run -d --name ecs-destination-second --network host \
  --env-file /secure/ecs/destination-runtime.env --env PORT=18002 --env WEB_CONCURRENCY=2 \
  localhost/ecs-portal:rehearsal
```

Before the contract suite, wait until every preserved pending report is due. Check `max(available_at)` for pending rows using destination SQL, then wait for that time without changing stored timestamps.
The suite checks killed/concurrent completion of due work; its isolated queue tests separately check that future work stays pending.
Keep background jobs stopped during these checks.

Wait for each `/healthz` URL, then run the contract checks inside the image:

```sh
podman run --rm --user 0 --network host \
  --env-file /secure/ecs/destination-tools.env \
  -v /secure/ecs/rehearsal-export:/export:ro -v "$PWD/tests:/checks:ro" \
  localhost/ecs-portal:rehearsal node --test /checks/portal.test.mjs
podman run --rm --network host --env-file /secure/ecs/destination-runtime.env \
  localhost/ecs-portal:rehearsal node execution.mjs --once
podman stop --time 15 ecs-destination-first ecs-destination-second
podman inspect ecs-destination-first ecs-destination-second --format '{{.State.ExitCode}}'
```

Both exit codes should be 0. Remove only the recorded rehearsal containers, databases, roles and buckets when results are saved.
The contract checks also accept preserved source-completed reports and verify the completed rows remain unchanged.
Keep one pending report per fixture user for the interrupted-worker check.

## Uncertain upload replies

Use another empty disposable database and bucket, with the protected fixture password and `REHEARSAL_CONFIRM=disposable-destination`.
Run:

```sh
node --test tests/upload-uncertain-commit.test.mjs
```

The test commits a real document INSERT, then injects a lost reply at the database boundary.
The test requires the failed HTTP upload to leave a committed document downloadable with exact bytes.
The injection exists only in the test preload module.

## Native handoff and independent replay

Follow [source setup](source/README.md) to deploy the actual AWS fixture.
Populate through the running Fargate app and record actual task/image/database versions.
Exercise real SQS, source scheduling, secret retrieval and private RDS connectivity before export.
Follow source/database-last.md and the Stack managed-relay procedure. Use logical replication only; archive restoration below is a separate disposable replay.
Verify the warm app-entry fence, separate copy entry, provider TLS, ready/streaming subscription, both formation members and full-row HTTP acknowledgements.
Use switch_to_the_database_moving_in, which runs its fleet stage switch_to_the_database_moving_in_through_relay for through_relay: true, and save its result pause parts alongside actual HTTP recovery.
Compare app/jobs container start times and run a Stack full backup before retiring the relay.
Stop source execution and remove AWS runtime access before checking destination independence.

A fresh reader can replay a preserved native export into separate destination state using the image procedure above.
This independently checks export portability and customer behavior; it does not repeat native provisioning, source shutdown, networking or logical replication.
A complete second native run needs separate source resources and its own recorded cutover.
Record manual interventions, failures, measurements and cleanup listings in `test_record.md`.
Keep account IDs, credentials, private inventories and protected exports outside public artifacts.

## Managed relay load proof

Use the [managed proof scripts](tests/managed_move/README.md) with the Stack relay procedure. They add a non-public schema, sequence and 96 KiB large object with owner/reader permissions. The writer saves every complete HTTP acknowledgement; the verifier compares source-fenced rows and both formation members without discarding PostgreSQL microseconds.

Run the pure comparison checks before a native run:

```sh
cd tests/managed_move
python3 -B -m unittest -v test_proof.py
```

These pure checks do not establish native copy/switch behavior. Source preparation, managed copy and relay switch, continuous writes, source shutdown, both-node verification and a full backup require the actual native run recorded in test_record.md.

## Jobs reconnect check

Run `node --test tests/execution.test.mjs` with Node 24. It starts the actual destination loop with controlled job/database dependencies. It checks that continuous jobs reconnect after database selection, connection and read-only errors, while one-shot jobs and unexpected errors still fail. The live managed fence and real socket-loss checks are recorded separately in [test_record.md](test_record.md).
