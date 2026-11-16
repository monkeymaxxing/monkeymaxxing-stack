# Managed database migration proof

Run the proof scripts from an isolated Linux controller with Python 3 and `psql`.
The migration operator runs the actual Stack copy and relay switch commands.
The proof scripts never create a publication, subscription, fence, or database switch.

`writer.py` keeps full HTTP acknowledgements in an append-only JSONL file.
`source_fixture.py` creates and captures database evidence.
`verify_rows.py` compares every acknowledged row on db01 and db02.
`proof_common.py` supplies protected settings and PostgreSQL reads.

Keep settings, logs, and captured facts in a protected directory.
Settings files must have mode `600`.
Passwords travel through environment variables or `PGPASSFILE`, never command arguments.
PostgreSQL errors go into `proof-psql-error.log`, with mode `600`, beside the settings file.
HTTP error bodies, cookies, and passwords never enter the writer log.

## Prepare the fixture

Run application migrations before creating the fixture.
The database must already contain `portal`, `database_moving_in_replication`, and `public.records`.
The source administrator must be allowed to `SET ROLE portal`.

Use a protected `source-settings.json`:

```json
{
  "postgres_env": {
    "PGHOST": "source.example.com",
    "PGPORT": "5432",
    "PGDATABASE": "portal",
    "PGUSER": "postgres",
    "PGPASSFILE": "/protected/source.pgpass",
    "PGSSLMODE": "verify-full",
    "PGSSLROOTCERT": "/protected/rds-ca.pem"
  }
}
```

```sh
python3 -B source_fixture.py create /protected/source-settings.json \
  --output /protected/initial-source-facts.json
```

The fixture owns schema `migration_evidence`, table `events`, and sequence `event_id_sequence` as `portal`.
The fixture creates two complete rows with Unicode, binary bytes, non-empty descriptions, and precise timestamps.
The sequence ends at `9041`, with `is_called=true`, beyond the inserted IDs `9001` and `9002`.
The fixture creates a known 96 KiB large object with `lo_from_bytea`, so RDS needs no server file access.
The large object belongs to `portal` and grants `SELECT` to `migration_evidence_reader`.
The extra role cannot log in.
The replication role receives schema `USAGE` and table `SELECT`.

Create the extra role on the Stack primary before copying the schema:

```sh
python3 -B source_fixture.py roles /protected/db01-administrator-settings.json
```

The administrator settings use the `postgres_env` shape above.
Use the actual db01 connection and credentials.
Do not run role creation on db02. Physical replication carries the role to db02.
The Stack copy creates its own destination mapping for `database_moving_in_replication`.

The operator creates the all-table source publication after the fixture exists.
`create` refuses an existing fixture schema instead of replacing evidence.
`roles` accepts an existing NOLOGIN grantee.

## Keep HTTP writes running

Use a protected `writer-settings.json`:

```json
{
  "base_url": "https://portal.example.com",
  "email": "migration-writer@example.com",
  "password": "replace-with-protected-password",
  "run_id": "managed-move-20261106",
  "log_file": "/protected/writer.jsonl",
  "stop_file": "/protected/writer.stop",
  "interval_seconds": 0.25,
  "request_timeout_seconds": 10
}
```

```sh
python3 -B writer.py /protected/writer-settings.json \
  > /protected/writer-process.log 2>&1 &
writer_pid=$!
printf '%s\n' "$writer_pid" > /protected/writer.pid
```

The writer registers the account, accepts an existing account, then logs in.
Each POST uses a new UUID nonce in the title and request description.
The app ignores POST descriptions, so verification requires the returned description to equal `""`.
Every successful POST logs the full returned row, submitted values, request time, response time, and elapsed seconds.
Every log entry is flushed and synced before the next request.
Failed or uncertain POSTs are recorded and never replayed.

An optional `route_file` setting names a text file containing the current base URL.
The writer reads the route before each request.
Use a single trusted app route when possible.
The writer retains its session across a route change because the database move preserves sessions.

Keep the writer running throughout the native Stack copy and relay switch.
After recovery, let several more requests complete.
Stop the exact owned process by creating the configured stop file:

```sh
touch /protected/writer.stop
wait "$writer_pid"
```

`SIGTERM` also ends the owned writer after the in-flight request completes or times out.
Use a fresh log and stop-file path for each run.

## Capture the fenced source

After the native relay switch disables the app entry, capture source rows through the relay's separate copy entry.
The separate copy entry must remain enabled.
Do not reconnect through the app entry or manually reopen the source.

Use `fenced-copy-settings.json` with the `postgres_env` shape.
Set `PGHOST` to the relay and `PGDATABASE` to the separate copy entry. Derive its exact `database_moving_in_` name with the Stack procedure; it is not an arbitrary alias.
Use the administrator login and the relay connection's actual TLS settings.

```sh
python3 -B source_fixture.py capture /protected/fenced-copy-settings.json \
  --output /protected/source-frozen-facts.json
```

Capture runs in a single read-only repeatable-read transaction.
The resulting JSON contains `records` and `fixture`.
`records` contains every full `public.records` row, including source rows outside the load account.
`fixture` contains schema owner and ACL, relation owners and ACLs, sequence state, full event rows, and extra-role attributes.
`large_objects` contains the original OID, full hexadecimal bytes, owner, and ACL for each referenced large object.
ACLs name grantees and grantors because role OIDs can differ across clusters.
PostgreSQL generates row JSON directly, retaining microseconds and exact bytea values.

Save evidence that the app entry was disabled during capture.
The operator may now power off the source after its required acceptance checks.
The verifier only needs captured source facts and the two destination servers.

## Verify destination rows and objects

Stop the writer and allow db02 to receive the final acknowledged commit before reading destination facts.
Use a protected `verify-settings.json`:

```json
{
  "writer_log_file": "/protected/writer.jsonl",
  "source_frozen_facts_file": "/protected/source-frozen-facts.json",
  "relay_fence_completed_unix_seconds": 1793926802.123,
  "observed_facts_file": "/protected/destination-observed-facts.json",
  "verification_file": "/protected/verification.json",
  "servers": {
    "db01": {
      "PGHOST": "203.0.113.11",
      "PGPORT": "5432",
      "PGDATABASE": "portal",
      "PGUSER": "postgres",
      "PGPASSFILE": "/protected/destination.pgpass",
      "PGSSLMODE": "verify-full",
      "PGSSLROOTCERT": "/protected/stack-ca.pem"
    },
    "db02": {
      "PGHOST": "203.0.113.12",
      "PGPORT": "5432",
      "PGDATABASE": "portal",
      "PGUSER": "postgres",
      "PGPASSFILE": "/protected/destination.pgpass",
      "PGSSLMODE": "verify-full",
      "PGSSLROOTCERT": "/protected/stack-ca.pem"
    }
  }
}
```

Use the actual Stack connection settings, including the installed TLS configuration.
Read `relay_fence_completed_unix_seconds` from the native switch result, never from the example value.

```sh
python3 -B verify_rows.py /protected/verify-settings.json
```

The verifier checks all returned fields against every HTTP acknowledgement on each database server.
Only the HTTP `created_at` comparison accounts for JavaScript's millisecond precision.
The verifier compares raw PostgreSQL timestamps exactly between db01, db02, and frozen source rows.
Repeated acknowledgement IDs, wrong row contents, missing rows, changed bytes, changed OIDs, changed owners, and lost ACLs fail verification.
Fixture facts must equal frozen source facts on each destination server.

The summary reports acknowledgement counts, failed or uncertain requests, and the longest gap between acknowledgements.
With the native fence timestamp, the summary also measures the first successful request started after fencing.
The recovery measurement includes driver reconnection and HTTP request time.

For fixture-only preliminary checks, replace `source_frozen_facts_file` with `fixture_facts_file` pointing to initial source facts.
Preliminary checks do not prove preservation of the full frozen source prefix.
Final proof uses `source_frozen_facts_file`.

## Local checks

```sh
python3 -B -m unittest -v test_proof.py
```

Pure checks prove that full-row mismatches, duplicate IDs, timestamp truncation, missing old rows, ACL loss, and sequence changes fail.
The operator must run the scripts on the actual managed source and Stack destination before claiming migration proof.
