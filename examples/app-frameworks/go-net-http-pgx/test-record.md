# Go example test record

## Variances and guidance needs

The baseline is the Stack's Hetzner architecture and Go infrastructure reference app.
No provider setting or Stack architecture changes for this framework example.
The framework still needs its own database, upload buckets, registry image, and host names.
The recorded service proof used isolated containers, so the shared Hetzner deployment remains a separate check.

| Difference or help needed | Guidance |
| --- | --- |
| Go HTTP server | `net/http` serves concurrent goroutines. `WEB_CONCURRENCY` sets `GOMAXPROCS`, rather than child processes. |
| Multi-host database URL | pgx 5.11.0 accepts the Stack URL unchanged. Keep `read-write` selection, three-second connection timeout, and host TCP keepalive. |
| Read routing | The portal reads the primary for fresh sessions and CRUD. `DATABASE_READ_URL` is unused despite pgx supporting preferred standby selection. |
| Packaging | The independent app changes only the Go module path. Keep migrations inside the copied build context. |
| Build/runtime | The Go recipe retains the reference app's pinned static-binary builder and non-root distroless runtime. |
| Silent database loss | The isolated first acknowledged write recovered 9.744 seconds after promotion. This observation is not a recovery ceiling. |
| Sessions and private state | The reference app has no accounts or files. The portal stores sessions in Postgres and documents in private object storage. |
| Health and assets | Use `/healthz` instead of the reference app's `/up`. All responses are uncached and `/app/assets` is empty. |
| Deadlines and connection capacity | Requests use twelve-second database deadlines. Budget up to eight database connections per web or job process. |
| Upload and account scope | Uploads are limited to 5 MiB per request to bound memory. Email verification, password recovery, and account administration are omitted. |
| Test-data seed | `seed-test-data` requires `APP_ENV=development` or `APP_ENV=staging` and a runtime fixture password; `--accounts N` adds generated accounts. Run twice before starting workers, using isolated database and object storage. |
| Browser requests | Use HTTPS for Secure cookies and the exact `APP_ORIGIN` for write requests. Use distinct origins and buckets for staging and production. |
| Additional-app configuration | Extend app settings, inventory tags/hosts, database-password mappings, app secret mappings, and rotation mappings. Preserve existing apps. |
| Initial app start | `every_server` can start the new app in every configured environment. Review the production scope before running configuration. |
| Cloudflare routing | Inventory renders locally managed tunnel routes. Add proxied DNS CNAMEs, staging Access, and cache coverage for new hosts. |
| Upload backups | Include the production bucket in the backup reader's scope. Recover object bytes separately from database references. |
| First restore drill | Check only migrations until data exists. Add fixture queries after seeding and completed reports. |
| Uncertain mutation result | Do not replay automatically after a lost reply. Check the database result before submitting a replacement. |
| Guide replay | Local commands pass in the packaged layout. Canonical Stack links remain usable when the app directory is copied alone. |
| Remaining live help | Rebuild the image, then prove real R2, public HTTPS, two-server sessions, Stack switches, PgBouncer, and Stack backup recovery. |

## Revisions and scope

Packaging checked on 2026-11-04 on macOS arm64.
The accompanying [source hashes](test-source-sha256.json) identify the packaged executable and build inputs exactly.

The executable sources match the isolated 2026-11-03 primary/replica run,
with only the Go module path changed.
The Go container recipe is unchanged.
SQL content, HTTP behavior, dependency versions, and connection settings are unchanged.
The Linux images below belong to the pre-packaging layout and are not newly published images.

## Fresh local checks

| Check | Result |
| --- | --- |
| Compiler | Go 1.27.3, darwin/arm64 |
| Unit tests | Pass, 5 tests |
| go vet ./... | Pass |
| gofmt | Pass |
| go build | Pass |
| Executable/SQL equivalence against isolated proof inputs | Pass after the documented path normalization |

Use the [guide](https://github.com/monkeymaxxing/monkeymaxxing-stack/blob/main/docs/app-frameworks/go-net-http-pgx.md) for the commands.
Local checks start no Postgres, object store, VM, or server.
No new Linux container build or live integration run is claimed for packaging.
The existing isolated tests pin behavior, while fresh local checks verify the moved build inputs.

## Recorded isolated service proof

- 2026-11-05: The full isolated PostgreSQL 17/S3 suite passed with complete first-run fixture snapshots. Every fixed row and password hash survived reruns, two 1,000-account runs, and a different `FIXTURE_PASSWORD`. Previously recorded image IDs predate the test changes.

- 2026-11-05: renamed the command to `seed-test-data`, allowed development/staging, and added `--accounts`. Go unit tests, the image build, and the full `tests/services.py` suite passed with PostgreSQL 17.11 and S3Mock, including 1,000 accounts twice and recovery. Previously recorded image IDs predate this change.

The 2026-11-03 run used Debian 13 amd64, PostgreSQL 17.11,
Podman 5.4.2, Go 1.27.3, and pinned Adobe S3Mock.
pgx was 5.11.0.
See the committed lockfiles and pinned Containerfile for all dependencies and base images.
Each framework had a separate database and bucket, two web containers, and two job workers.

Passed checks included:

- Health refusal before migration and success after ordered migrations.
- Migration and staging-seed idempotence, plus unsafe seed refusal.
- Registration, login, cross-process sessions, logout revocation, ownership, and CRUD.
- Private document upload/download with matching bytes and SHA-256.
- Concurrent workers completing 20 reports and recovery of an interrupted job.
- Query deadlines and graceful web/job shutdown with active work.
- A title-only previous release continuing through additive migration 0002.
- Logical dump/restore equality across all six tables.
- Restored login and document download from an isolated copied bucket.

A separate real PostgreSQL primary/streaming-standby test passed with the standby listed first.
Web and job process identities stayed unchanged through forward/reverse promotions and a silent TCP fault.
Existing sessions, new logins, fresh writes, and reports worked after switching.
The actual Go configuration helper also selected the preferred standby in each role orientation. The HTTP portal still reads the primary.

| Measurement | Result |
| --- | --- |
| Planned forward / reverse recovery | 0.439 / 0.489 seconds |
| Silent TCP loss plus promotion recovery | 9.744 seconds |
| Failed HTTP requests, forward / reverse / silent | 27 / 27 / 1 |
| Locked health query | 2.006 seconds, HTTP 503 |
| Locked ordinary request | 12.010 seconds, HTTP 503 |

Recovery starts at PostgreSQL's logged promotion request and ends at the first acknowledged new write.
The tests included about two seconds without a writer before promotion.
Counts describe a sequential writer and do not promise zero delay or a recovery ceiling.
Silent faults dropped the database and relay peer traffic.
Host TCP settings were keepalive idle 30 seconds, interval 10 seconds, three probes, and `tcp_retries2=7`.
The longest silent-fault request took 12.012 seconds.

A lost-reply test dropped the reply after a database commit.
The app returned HTTP 503, but an independent query found exactly one committed row.
The row stayed unique and a new distinct write worked. No automatic mutation replay occurred.

Recorded isolated app manifest digest:
`sha256:f5a468f679db3f873ab87a2b7de4c541d45e4f6cb6debde3ac5d8da0fb3560f4`.
S3Mock digest:
`sha256:ab01a6946750f451ca215a47e91030695b260e4003b8a5a6201d25029b8fca92`.

## Limits and next proof

S3Mock proves S3 API behavior, not R2 authorization or TLS.
The primary switches used direct PostgreSQL promotion, not Stack `switch_database_primary` orchestration.
Logical restore and object copying do not prove the Stack's backup chain.
Sessions crossed processes within an isolated host, not two public Stack app servers.

The shared-system deployment must still prove:

- Rebuilt images from the packaged directories and registry pull access.
- Migrations at deployment, public HTTPS/browser behavior, and real R2 access.
- Sessions and ownership across two app servers.
- Native reconnection during Stack switches in each direction without process restart.
- Transaction-mode PgBouncer compatibility.
- Stack database backup recovery and independent uploaded-file recovery.

Fresh-reader local replay passes. Deployment preparation was read and checked without running server commands.
The replay fixed copied documentation links and a Rust build instruction that named Go.
The independent replay does not prove any live Stack check.
No live deployment occurred during packaging.
