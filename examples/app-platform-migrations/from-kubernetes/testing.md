# Verify a disposable export and handoff

Run integration checks on isolated Linux resources.
Keep the original protected export and fixture password separate from the application checkout.
The checks mutate data. Each replay needs an empty database, a new bucket, and separate web ports.

## Independent restore

The source export must contain `database.dump`, `table-audit.json`, `files.json`, and `objects/`.
Keep the source code revision and native inventory separately.
`customer-state.json` additionally checks active source sessions during the live handoff.

Build a fresh image from `app/`:

```sh
podman build -t portal-replay -f app/Containerfile app
python3 scripts/prepare-rehearsal.py \
  --settings-dir /secure/portal-replay \
  --fixture-password-file /secure/portal-source/fixture-password \
  --database-port 5544 --first-http-port 8801 \
  --storage-url http://127.0.0.1:9090 --bucket-name portal-replay
podman run -d --name portal-replay-database \
  --publish 127.0.0.1:5544:5432 \
  -e POSTGRES_DB=portal -e POSTGRES_USER=portal \
  -e POSTGRES_PASSWORD_FILE=/run/postgres-password \
  -v /secure/portal-replay/postgres-password:/run/postgres-password:ro \
  docker.io/library/postgres:17.11-bookworm
podman exec portal-replay-database pg_isready -U portal -d portal
```

Wait for PostgreSQL readiness before restoring.
Use a separate S3-compatible service for a standalone rehearsal, or an isolated bucket in an existing test service:

```sh
podman run -d --name portal-replay-storage --publish 127.0.0.1:9090:9090 \
  -e debug=false \
  docker.io/adobe/s3mock@sha256:cf5b4f0b6200c4b636b779b93db1847419f6bd082c0b6cd88ee409dcaa350f9b
```

Wait for port 9090 to answer before creating the bucket.
The generated environment file uses synthetic credentials because S3Mock does not enforce real bucket authorization.
Do not use the generated mock credentials for a production object service.

```sh
podman run --rm --network host --env-file /secure/portal-replay/portal.env \
  portal-replay node --input-type=module -e \
  'import {storage} from "./s3-storage.mjs"; import {CreateBucketCommand} from "@aws-sdk/client-s3"; await storage.send(new CreateBucketCommand({Bucket:process.env.BUCKET_NAME}));'
cat /secure/portal-export/database.dump | \
  podman exec -i portal-replay-database pg_restore -U portal -d portal \
  --no-owner --no-acl --exit-on-error
podman run --rm --network host --user 0 --env-file /secure/portal-replay/portal.env \
  -v /secure/portal-export:/export:ro portal-replay \
  node scripts/audit-database.mjs compare
podman run --rm --network host --user 0 --env-file /secure/portal-replay/portal.env \
  -v /secure/portal-export:/export:ro portal-replay \
  node scripts/transfer-files.mjs import
```

Every row must match before any login, worker, or scheduled command changes the restored database.
The importer checks source bytes, refuses existing destination keys, and downloads each new object to verify the checksum.

```sh
podman run -d --name portal-replay-web-1 --network host \
  --env-file /secure/portal-replay/portal.env portal-replay
podman run -d --name portal-replay-web-2 --network host \
  --env-file /secure/portal-replay/portal.env -e PORT=8802 portal-replay
```

Wait for `/healthz` on ports 8801 and 8802 to return 200.
From the example directory, run:

```sh
podman run --rm --network host --user 0 --env-file /secure/portal-replay/portal.env \
  -v /secure/portal-export:/export:ro -v "$PWD/app/tests:/tests:ro" \
  portal-replay node --test /tests/portal.test.mjs
podman run --rm --network host --user 0 --env-file /secure/portal-replay/portal.env \
  -v "$PWD/app/tests:/app/tests:ro" portal-replay \
  node --test tests/upload-rejection.test.mjs
podman run --rm --user 0 -v "$PWD/app/tests:/app/tests:ro" \
  portal-replay node --test tests/local-uploads.test.mjs
```

The portal suite checks returning passwords, UUIDs, private bytes, ownership, new uploads, CRUD, cross-process revocation, and registration.
The worker test interrupts a real transaction and then runs overlapping workers.
Schedule checks overlap the real command and verify exactly one hourly receipt.
Migration and connection-recovery checks preserve sessions without replaying an uncertain HTTP write.
The fixture export needs two users, one record/file per user, and at least one pending report.
Completed source reports are retained and verified too.

Run the seed suite against another empty database and empty bucket using separate settings:

```sh
podman run --rm --network host --user 0 --env-file /secure/portal-seed-test/portal.env \
  -e REHEARSAL_CONFIRM=disposable-destination \
  -v "$PWD/app/tests:/app/tests:ro" portal-replay \
  node --test tests/seed-test-data.test.mjs
```

Prepare `/secure/portal-seed-test/portal.env` with the settings helper and a different database port and bucket.
The seed suite starts its own web process on port 18021.
The seed test proves allowed environments, production refusal, idempotence, 1,000 accounts, and smaller-count preservation.

## Targeted live handoff

Use the guide's ordering: stop source app execution, keep the database in k3s, move files and execution, verify, then replicate PostgreSQL.
The first destination environment lists the private source database and future destination primary, using writable-primary selection.
Run the portal checks against the old database through WireGuard before copying PostgreSQL.

Capture original customer sessions with `check-handoff.mjs capture` before freezing the source.
After the app move, run `check-handoff.mjs verify` with the protected customer-state file and original fixture password.
The probe checks existing session continuity, returning passwords, original bytes, ownership refusals, and fresh CRUD.
Use the actual destination URL in `APP_URL`.

Use the [Stack database-move procedure](../../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md) for the database stage.
Run its actual `copy_the_database_moving_in` and `switch_to_the_database_moving_in` playbooks.
Keep DDL frozen and PostgreSQL available inside k3s until the switch finishes.
The source node belongs only to `database_moving_in`, never the normal database inventory.
The copied Node helper must match the current Stack file and check transaction writability.

Keep an HTTP writer running throughout copying and switching, recording acknowledged IDs and timestamps.
Compare every acknowledged ID with the destination and inspect the playbook's pause parts.
Verify sequence values, large-object bytes and permissions, removed subscriptions/slots, and unchanged web start times.
Pause the StatefulSet's owning reconciler before the switch, then scale PostgreSQL to zero after successful cleanup.
Stop the whole source cluster and repeat customer actions, new uploads, report completion, and hourly cleanup at the destination.
An S3 stand-in does not prove R2 policy, and the targeted playbook test does not prove a complete Stack setup or backup recovery.

## Cleanup

Save secret-free evidence and protect the original export before removing disposable resources.
Stop and remove only the containers, guests, buckets, and peers created by this run.
Re-list resources to verify absence.
A retained PostgreSQL source also needs replication-slot and temporary-role cleanup.
