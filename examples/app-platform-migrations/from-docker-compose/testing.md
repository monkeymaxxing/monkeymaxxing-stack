# Replay the Compose migration onto the Stack

Use a disposable Compose source and a real Stack with `util01`, `app001`, `db01` and `db02`.
The Stack database move follows [Move a database into the Stack](../../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md).
That procedure owns all database copy, fencing, switch, failure recovery and cleanup commands.
These instructions supply the Compose fixture and customer/data checks.

Keep exports, credentials, exact row audits and writer logs outside Git, with `umask 077`.
The tests mutate data. Use the synthetic source from this example.

## Prepare the native source

Run the [README source preparation](README.md#start-a-disposable-source), including the production override and host timer.
Use `SOURCE_POSTGRES_IMAGE` to select the recorded source image when replaying a different PostgreSQL major.
The image must use PostgreSQL's normal `/var/lib/postgresql/data` volume layout from the supplied Compose file.
Record the actual image digest, PostgreSQL/runtime versions and source revision.

Inspect the resolved config and running containers before export.
Verify the production marker, `unless-stopped` policies, file secret, named database volume, upload bind mount and timer.
The host schedule exists outside Compose.

Run `tests/customer-check.mjs` inside a one-shot app container, mounted as `/tests`:

```sh
docker run --rm --network host --user 0 --entrypoint node \
  -e APP_URL=http://127.0.0.1:18001 \
  -e FIXTURE_PASSWORD_FILE=/private/fixture_password \
  -e SAVE_BASELINE_FILE=/private/customer-baseline.json \
  -v "$SOURCE_SECRETS_DIR:/private" -v /srv/compose-portal/tests:/tests:ro \
  compose-portal:rehearsal --import ./file-secrets.mjs /tests/customer-check.mjs
```

Expected output includes `customer_checks_passed:true` for two users.
The saved baseline records stable user, record, document, object and report identities.
The check adds a private test upload. Include that upload in the final transfer.

Load the sized fixture through a protected source administrator connection:

```sh
psql -X -v ON_ERROR_STOP=1 -f tests/replication-fixture.sql
```

The fixture contains 49,152 rows with 65,536 bytes each: exactly 3 GiB of payload.
`STORAGE EXTERNAL` prevents TOAST compression. The payload repeats per-row MD5 blocks.
The fixture adds a non-public `migration_history` schema, sequences, a large object, read grants and default privileges.
Grant the source replication login access to `migration_history` as well as `public`, following the Stack procedure.
Before the copy, advance the load identity three times and the descending sequence once to test their final states:

```sql
SELECT nextval('migration_load_id_seq') FROM generate_series(1,3);
SELECT nextval('migration_descending');
```

Take and restore-check the source backup before changing the old system.
Keep upload bytes in a separate protected backup because PostgreSQL backups contain only document metadata.

## Prepare the real Stack

Build the destination through the Stack setup. Copy the current Stack Node database helper into `app/` before building the image.
Publish the image through the normal registry route and record its selected tag/digest in the systems repository.
The example's Stack app key is `shop`; the database and database login are `portal`.

Use these app settings under `vars.apps.shop`, replacing the image and bucket with the real resources:

```yaml
image: ghcr.io/example/compose-portal
web_ports: [8001, 8002]
health_url_path: /healthz
migration_command: database.mjs
jobs_command: jobs.mjs
jobs_connect_directly_to_postgres: false
asset_directory: /app/web
database_name: portal
env:
  NODE_ENV: production
  COOKIE_SECURE: "true"
  AWS_ENDPOINT_URL_S3: https://s3.example.com
  AWS_REGION: us-east-1
  BUCKET_NAME: example-portal-uploads
  S3_FORCE_PATH_STYLE: "true"
secrets_from_vault: [AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY]
production_uploads_r2_bucket: example-portal-uploads
restore_drill_check_queries:
  - name: the_migrations_came_back
    sql: select count(*) = 2 from schema_migrations
```

Match the production role inputs to the database name and the app key.
In the `database_server` call in `playbooks/every_server.yml`, use:

```yaml
database_passwords:
  portal: "{{ .secrets.portal_database_password }}"
```

In the production `app_server` and `jobs_server` calls, supply:

```yaml
app_secrets:
  portal_database_password: "{{ .secrets.portal_database_password }}"
  shop_AWS_ACCESS_KEY_ID: "{{ .secrets.shop_AWS_ACCESS_KEY_ID }}"
  shop_AWS_SECRET_ACCESS_KEY: "{{ .secrets.shop_AWS_SECRET_ACCESS_KEY }}"
```

Save those three vault keys through the normal app setup.
`portal_database_password` follows the database name; storage secret names follow the Stack app key `shop`.
Keep staging's database and credentials separate.

Use the existing upload-backup setup for the selected bucket. S3-compatible test storage needs its own recorded backup deviation.
Use `COOKIE_SECURE=false` only for an isolated HTTP rehearsal.
Omit `UPLOADS_DIR` and `DATABASE_URL_FILE` in Stack app settings. The Stack supplies `DATABASE_URL` from its vault and server list.
The image entrypoint already supplies Node.js, so migration/jobs settings name the `.mjs` command directly.
Do not run a deployment migration during copying.

Follow the Stack database-move procedure to prepare source access, matching passwords, extra grantee `portal_reader`, and `database_moving_in`.
Leave the old server outside all managed inventory groups.
Stop source execution before starting the Stack app, as the Stack procedure requires.

## Convert files and hand off execution

Disable the source host timer and stop source web/worker services, while preserving PostgreSQL.
Check fresh timer and Compose listings. Disable any external deployment trigger too.
Copy the source upload tree to a protected transfer directory, preserving relative object keys.

Create a private destination bucket and a protected `DESTINATION_STORAGE_CONFIG_FILE`:

```json
{
  "client": {
    "endpoint": "https://s3.example.com",
    "region": "us-east-1",
    "forcePathStyle": true,
    "credentials": {
      "accessKeyId": "REPLACE_FROM_PROTECTED_DESTINATION_CREDENTIAL",
      "secretAccessKey": "REPLACE_FROM_PROTECTED_DESTINATION_CREDENTIAL"
    }
  },
  "bucket": "example-portal-uploads"
}
```

Set the copier's database credential to the old database over WireGuard, without printing the URL.
The Compose hostname `postgres` is local to the source project; replace that hostname in the protected copy of the URL.
Run `scripts/copy-uploads.mjs` from the example root, with app dependencies installed:

```sh
npm ci --prefix app --ignore-scripts --no-audit --no-fund
node --import ./app/file-secrets.mjs scripts/copy-uploads.mjs
```

Required inputs are `DATABASE_URL_FILE`, `SOURCE_UPLOADS_DIR` and `DESTINATION_STORAGE_CONFIG_FILE`.
The copier preserves storage keys and compares source and downloaded destination bytes against database lengths and hashes.
Existing destination bytes must match; the copier never replaces different bytes silently.
Inventory orphaned local files separately because this copier follows the document table.

Run the Stack's normal setup with `database_moving_in`, then check customer actions against the old database.
Verify source database connections arrive from the Stack app's WireGuard address.
Use the same baseline file and `customer-check.mjs` against the Stack app.
Set `APP_URL` to the app's configured hostname, with its normal TLS trust.
Node's `fetch` does not support overriding the hostname with a `Host` header; a loopback URL can reach Caddy's fallback route.

Copy `stack_session_cleanup.yml` to `playbooks/portal_session_cleanup.yml` in the systems repository.
Adjust the app key/image selection when the app is not `shop`.
Commit/push and apply that playbook through the normal utility helper.
For the supplied `shop` playbook, run from the systems desk:

```sh
./server_management_scripts/run_mmx_on_util01 run portal_session_cleanup
./server_management_scripts/run_mmx_on_util01 run-command --nodes app001 -- \
  "systemctl start portal_session_cleanup.service"
```

Start it again and verify there is still one receipt for the UTC hour.
Only the destination timer may own scheduling after the handoff.

## Run load through the native copy and switch

Start `tests/acknowledged-writes.mjs` against the Stack app **before** running the copy playbook.
Supply `APP_URL`, protected `FIXTURE_PASSWORD_FILE`, `WRITER_STOP_FILE` and `WRITER_RESULT_FILE`.
Mount a writable private directory for the log and stop file.
Confirm that successful new records are being acknowledged before beginning the copy.

The writer submits distinct record creations every 100 ms by default and logs returned UUIDs and response times.
Set `WRITE_INTERVAL_MS` to a measured rate the destination can sustain; the recorded Stack switch uses 1000 ms.
Let the subscriber catch up before switching. A growing backlog is a capacity result, not a safe switch condition.
The writer never retries a mutation with an uncertain result.
Keep the writer active throughout the Stack procedure's `copy_the_database_moving_in` and `switch_to_the_database_moving_in` commands.
Run customer checks during copying to exercise ownership, CRUD and new private uploads while table data moves.

Use the Stack procedure to check streaming and ready table states.
Verify the new formation's replica receives the copied data.
The immutable load table must return the same audit on source, db01 and db02:

```sql
SELECT count(*),sum(octet_length(payload)),
       count(*) FILTER (WHERE md5(payload)<>payload_md5),
       md5(string_agg(id::text||':'||payload_md5,',' ORDER BY id))
FROM migration_load;
```

Expected result:

```text
49152|3221225472|0|757703b0aacbe81c8f1b65e809ef5737
```

Change the fixture's large object on the source while the app still writes there:

```sql
SELECT lo_put(44101,0,convert_to('Changed during the live Stack move','UTF8'));
SELECT oid,octet_length(lo_get(oid)),md5(lo_get(oid)) FROM pg_largeobject_metadata;
```

Keep schema changes paused. After the bulk audit, repeat the Stack procedure's streaming/catch-up checks before switching.
Let the Stack switch command transfer final sequence and large-object state.
Record its pause parts from MMX results, separately from the writer's customer-visible gap.
Compare web/jobs container start times before and after the switch; the switch must not restart either container.

## Verify acknowledged writes and customer state

Touch the writer's stop file after recording successful requests with the old system powered off.
Load the JSONL log privately and collect every UUID from an HTTP 201 response.
Check every UUID on db01 and db02. A row count or maximum ID does not prove zero lost acknowledged writes.
Report the number of acknowledgements and missing IDs, with failed requests counted separately.

For the write pause, calculate the gap between the last success before recovery and the first success after the switch.
Include the actual probe interval and the exact measurement window in the record.

Compare source account/ownership/schema rows with their preserved destination rows.
Allow the intentional new rows from acknowledged destination writes; verify their IDs and submitted titles individually.
`scripts/audit-small-tables.sql` and `scripts/audit-catalog.sql` support protected row and ownership/permission audits for this fixture.
Do not publish password/session hashes or exact customer row exports.
Compare ACL privileges by meaning across PostgreSQL majors. PostgreSQL 17 adds the owner's `MAINTAIN` table privilege; preserve every source privilege and refuse unexpected grants to other roles.

Verify the unused sequence is still uncalled at value 700.
An insertion using the load identity must receive 49156, after the three deliberate skipped values.
The descending sequence's next value must be -20.
`execution-check.mjs` performs these consuming probes. Run them once, through that check, so a preliminary `nextval` or insertion does not invalidate the expected values.
Verify large object OID 44101, byte length, final hash, owner and read ACL on both database servers.
Check that `portal_reader` can read the migrated data but cannot insert.

Run `tests/execution-check.mjs` in the built image against the destination database.
The check kills an actual worker before commit, then uses concurrent workers to finish the two pending reports once.
It requires exclusive control of the fixture's workers. From the systems desk:

```sh
./server_management_scripts/run_mmx_on_util01 run-command --nodes app001 -- \
  "systemctl stop shop-jobs.service"
```

On app001, with the example tests copied to `/secure/compose-checks`, run the selected image:

```sh
export COMPOSE_PORTAL_IMAGE=ghcr.io/example/compose-portal:RECORDED_IMAGE_TAG
podman run --rm --network host --user 0 --entrypoint node \
  --env-file /etc/shop/shop.env -v /secure/compose-checks:/tests:ro \
  "$COMPOSE_PORTAL_IMAGE" --import /app/file-secrets.mjs /tests/execution-check.mjs
```

Then resume the normal worker from the systems desk:

```sh
./server_management_scripts/run_mmx_on_util01 run-command --nodes app001 -- \
  "systemctl start shop-jobs.service"
```

Queue another report through HTTP and verify completion through the normal Stack worker.

Finish the Stack procedure's backup, peer/URL/credential cleanup and source power-off checks.
Repeat returning-user, ownership, private-byte and new-write checks with the old system stopped.
Leave real storage permissions, public routing and external alert delivery unproved unless those checks actually ran.

## Independent replay and cleanup

A fresh reader follows this guide and the linked Stack procedure on a prepared disposable source/Stack checkpoint.
Record any hidden input or guessed step and correct the guide before accepting the replay.
The replay must run the real copy/switch playbooks and repeat the acknowledged-write audit.

Save secret-free evidence, then remove only inventoried test resources.
Verify fresh guest/server, volume, schedule, subscription and slot listings.
Remove protected test exports and generated credentials after saving the accepted results.
