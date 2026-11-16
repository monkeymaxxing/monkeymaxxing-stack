# Docker Compose migration example

## Variances and guidance needs

This example moves a real Compose portal's local uploads to object storage, then moves PostgreSQL through logical replication.
The [Compose guide](../../../docs/app-platform-migrations/from-docker-compose.md) adds source-specific steps to the [shared procedure](../../../docs/app-platform-migrations/from-any-container-platform.md).

The source uses production overrides, secret files, a PostgreSQL volume, a worker and a host timer.
The destination uses the Stack's app services and PostgreSQL 17 primary/replica formation.
The lab uses an S3-compatible emulator and a TLS ingress fixture; provider authorization and Cloudflare routing need their own checks.
See [test_record.md](test_record.md) for the measured boundary.

## Acceptance contracts

- Returning users keep bcrypt passwords, stable user IDs, owned records, document IDs and report IDs.
- Guessed record, document and report IDs cannot cross the ownership boundary.
- Local-file conversion preserves keys, owner links, byte lengths and hashes. New destination uploads use object storage.
- Production configuration includes the real override, mounted secret paths and restart behavior.
- Source workers and the host timer stop before destination execution starts.
- Table replication continues while HTTP writes create, edit and delete records.
- Final small-table comparison preserves every row, including verifier hashes, session hashes, job output and schema history.
- Bulk payload bytes and hashes are checked separately from the final write pause.
- Finalization preserves sequence values and `is_called`, large-object OIDs/bytes/owners/ACLs, table ownership, grants and default privileges.
- The source application login remains fenced after the database switch. Subscription and source slots are removed.
- An interrupted worker leaves pending work available. Concurrent workers complete distinct jobs once.
- Repeated scheduled execution has one receipt per UTC hour. Applied migrations retain checksums.
- Destination customer actions survive source power-off, with no web/jobs restart during the native database switch.
- Every acknowledged HTTP UUID and submitted title exists on both Stack database servers after the switch.
- Public Cloudflare routing, real bucket permissions and external alert delivery remain separate proof boundaries.

## Files and commands

`app/` is an independent copy of the portable portal. The PostgreSQL helper and locked dependency graph are preserved.
`UPLOADS_DIR` selects source disk storage. Omitting `UPLOADS_DIR` selects S3-compatible storage.
`DATABASE_URL_FILE` loads the source file secret. At the Stack destination, supply `DATABASE_URL` directly.
`FIXTURE_PASSWORD_FILE` is a test credential file, never a public fixture password.

| Command in the app image | Job |
| --- | --- |
| `node --import ./file-secrets.mjs server.mjs` | Serve web requests on `PORT` |
| `node --import ./file-secrets.mjs database.mjs` | Apply ordered migrations and verify checksums |
| `node --import ./file-secrets.mjs jobs.mjs` | Process reports until SIGTERM |
| `node --import ./file-secrets.mjs jobs.mjs --once` | Attempt one report |
| `node --import ./file-secrets.mjs schedule.mjs` | Run hourly expired-session cleanup |
| `node --import ./file-secrets.mjs seed-test-data.mjs` | Populate two users through the running app in development or staging |

The Containerfile already supplies `node --import ./file-secrets.mjs` as its entrypoint.
For example, `docker run ... compose-portal:rehearsal jobs.mjs` selects the worker command.
For this image, set Stack `migration_command: database.mjs` and `jobs_command: jobs.mjs`.
The entrypoint already supplies Node.js and the secret loader. The health path is `/healthz` and assets live in `/app/web`.
The image runs as user 1000. Source file-backed secrets retain host ownership, so the fixture creates readable files for that user.
The upload limit is 1 MiB because this small app buffers uploads in memory.

PostgreSQL owns accounts, sessions, records, document metadata, reports, pause controls, schema versions and schedule receipts.
S3 owns destination file bytes. Neither a PostgreSQL dump nor logical replication copies file bytes.
Reports hold their row lock through output and completion. This example has no external side effect to reconcile.

## Start a disposable source

Use a Linux test server with Docker Engine, Compose v2, Python 3, curl and a prepared WireGuard interface.
Run as root because preparation assigns file ownership to the container user.
Copy the whole example to `/srv/compose-portal`.
Select unused protected directories and the source host's real WireGuard address:

```sh
cd /srv/compose-portal
export COMPOSE_PROJECT_NAME=container-migration-rehearsal
export SOURCE_SECRETS_DIR=/root/compose-source-private
export SOURCE_UPLOADS_DIR=/srv/compose-source-uploads
export SOURCE_DATABASE_WIREGUARD_IP=10.20.11.1
python3 scripts/prepare-source.py
```

Preparation refuses existing credential and upload directories. The command builds the app, creates a database login and seeds through HTTP.
The fixture intentionally uses HTTP on loopback. Use secure cookies and HTTPS for a real app.
The database is published on loopback and the selected WireGuard address, never a wildcard host address.

Save those four environment variables, plus `SOURCE_POSTGRES_IMAGE` when selecting another image, in `/etc/compose-portal/source.env`, with mode 600, before installing the host timer.
The timer runs from `/srv/compose-portal/source`:

```sh
install -d -m 700 /etc/compose-portal
install -m 644 source/portal-session-cleanup.service source/portal-session-cleanup.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now portal-session-cleanup.timer
systemctl start portal-session-cleanup.service
```

Resolve and save production configuration privately using the guide's exact `-f` order.
Verify `DEPLOYMENT_LABEL=production-override`, mounted credential paths, database volume and host timer state.

## Replay

Follow [testing.md](testing.md) on disposable Linux source/destination servers.
The instructions cover the old-database stage, bulk replication, final state transfer and post-switch checks.
The customer and execution checks mutate the fixture.

The measured run used 3 GiB of table payload plus a 1.1 MB large object.
Reserve enough disk for database data, WAL, container images and a second copy. The Stack proof uses six guests with 40 GiB disks.
The synthetic bulk table uses external, uncompressed storage so a compressible string does not masquerade as a sized copy.

Keep database archives, exact row audits, password files, fixture credentials and upload bytes outside Git.
Publish versions, aggregate checks and measurements from the test record.
