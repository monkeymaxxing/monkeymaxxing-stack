# Next.js / pg test record

## Variances and guidance needs

- Use the Stack multi-host helper for pg pools. A plain pg connection URL cannot read multiple database hosts.
- Copy static assets and CLI inputs into standalone output. Next.js tracing alone does not package every runtime command.
- Set the Stack asset directory to `/app/.next/static` to retain previous-release browser bundles during deployment.
- Fork Node workers from `WEB_CONCURRENCY`. Normalize Next.js signal exit codes only after the requested shutdown.
- Share database sessions and disable private response caching across app servers.
- Use HTTPS in browsers because login cookies are Secure. Private-port checks explicitly send cookies.
- Replace Vercel-hosted functions, storage, jobs, and service credentials individually when migrating an incoming app.
- Keep staging origins, database passwords, and buckets separate from production.
- Build standalone output on Linux with Node 24 and the target architecture.
- Optional database restarts require service-management permission and exclusive ownership of every dependent test app.
- The Stack environment deploy applies all configured app tags. Review other apps' pending tags before adding this app.
- The example buffers uploads, so the file limit is 8 MiB. Larger uploads need a streaming design.
- Account verification, password recovery, and abuse controls are outside this hosting fixture. Apply ingress login limits before public use.
- A database restart proves reconnection after connection loss, not actual primary promotion.
- S3Mock proves API byte behavior, not R2 credential authorization or TLS.
- The first Stack restore drill checks migrations only. Data and object recovery require later checks.

## Verification status

Isolated Linux checks passed on 2026-11-04. A fresh agent replayed the setup,
build, service checks, and shared HTTP checks without manual intervention.
The guide's service-management permission note was clarified after the replay.
No product code changed after the verified image build.

## Versions and source

| Component | Verified version or identity |
| --- | --- |
| App source | The example files, identified by the SHA-256 table below |
| Linux | Debian 13, x86_64 |
| Node / npm | 24.22.2 / 11.19.1 |
| Next.js | 16.4.5, stable registry tag checked before implementation |
| React / React DOM | 19.3.1 |
| pg | 8.23.1 |
| bcryptjs | 3.0.3 |
| AWS S3 SDK | 3.1161.0 |
| PostgreSQL | 17.11, Debian package 17.11-0+deb13u1 |
| Node base image | `node:24-bookworm-slim@sha256:a43f7fc3e52e87d12a905f46eea0275def84ca8f2981a5b53fed44d7fb398ee0` |
| S3Mock image | `adobe/s3mock@sha256:ab01a6946750f451ca215a47e91030695b260e4003b8a5a6201d25029b8fca92` |
| Verified app image ID | `8389a0322a859a70aa24513172eac7afdc511bfa7550c9604a65d329fe4a692c` |

Dependencies are pinned in `package-lock.json`. The SHA-256 table identifies the source.
Node's base image digest is pinned in the Containerfile. The app image was built
from these files.

The [Next.js standalone output](https://nextjs.org/docs/app/api-reference/config/next-config-js/output)
and [self-hosting documentation](https://nextjs.org/docs/app/guides/self-hosting)
were checked when preparing the example. The registry's stable Next.js tag was
16.4.5. The example's lockfile remains the reproducible dependency input.

## Source SHA-256

| File | SHA-256 |
| --- | --- |
| `.dockerignore` | `c7160244ba6acdf06f8705cd82e8bfce810942efb4181f2628817fd54808e5f5` |
| `.gitignore` | `0674c5b4bf5621cae135ceaccc35dac4657459771dda9fa863b5d8501fec3761` |
| `Containerfile` | `1897b590a41603acae3a03a62201d5f300b105656614df0a6a6b7bbca85c5027` |
| `app/[...path]/route.js` | `2b6ed01b9376e040b1d1d2d4990868cc9494f2891d897641bdfbd5253dfc9644` |
| `app/layout.jsx` | `44592188ead7c1c7eefafee765bfecc1943e22aebace34e875fcb410dc7c9d76` |
| `app/page.jsx` | `c1fb1e321e2ede486eaa546642b1192e2e071455fabf31d8fb255693e92c35d3` |
| `lib/accounts.mjs` | `066ed5e4e86dc2c5ec89bcdba6e8eb80b2577a4cd8b080aba987bc862db0afac` |
| `lib/database.mjs` | `34943e0305ea60f753ca34e7027d4b868a0e068ba5eca75258466ec1fcfded85` |
| `lib/http.mjs` | `7334b723f0a98254df349bca000aa112499ccf4ede60f72accdc6e6177e4868e` |
| `lib/jobs.mjs` | `dc13801afaff87896d54bca5687d925f0340211bd17338256578708e527b3840` |
| `lib/pg_with_multiple_database_servers.mjs` | `1c4bd9fda5c588efa20d87d0866fa0cd63e27309953a86164c597e49b7d0364c` |
| `lib/storage.mjs` | `802b9c2f48457692ad6d589c030a6642f293cdac000c4197603e6495d1a81ef5` |
| `migrations/0001_portal.sql` | `b601c80248e069c08123a92651f29562fe3400abbac3b2a2317125c9d2fe3711` |
| `migrations/0002_record_descriptions.sql` | `14056a6549689409d05b1638d8a4adb0ea12975362f1b2d356950cfeff2f37e0` |
| `next.config.mjs` | `7817e2e5b9b858da79e2ff40d04fe7092806ae68e90aa91800aba7e71eb96069` |
| `package-lock.json` | `3fd9667310feb596a67301c0137e05f51197811550adc59417e8b03c8e725d90` |
| `package.json` | `dc40b42466768a90f266c355662eff25c24bca3c2f0d9a42392ffb1dc6044ce1` |
| `public/robots.txt` | `331ea9090db0c9f6f597bd9840fd5b171830f6e0b3ba1cb24dfa91f0c95aedc1` |
| `scripts/manage.mjs` | `9fc0e92284bb108ce2620031bdf89d0dbd5418aa5002985d3f03e57fb37409fa` |
| `scripts/package-runtime.mjs` | `183dcebc9daaca47f01172878dcf5d9a20b0d72d3caddd33a9fdfe5d60b95f23` |
| `scripts/web.mjs` | `88a3f4396d58ade453eec7022326363f8351fdb50c766445b4f72fe9172cc08b` |
| `tests/accounts.test.mjs` | `c401b9abbbbe0769f7031068c767d91a61620b693696be1a171427e45299868d` |
| `tests/check_portal.py` | `0db584d5d3941750a925ca8c60871ad65d52726156abd3b255dfc5b9c8561015` |
| `tests/services.mjs` | `b0b3ecd753070904920b35cbcf5f7be01c8254173057334a13f39c29ed75b3c1` |

## Executed checks

- 2026-11-05: The full isolated PostgreSQL 17/S3 suite passed with complete first-run fixture snapshots. Every fixed row and password hash survived reruns, two 1,000-account runs, and a different `FIXTURE_PASSWORD`. Previously recorded image IDs predate the test changes.

- 2026-11-05: `seed-test-data` now supports development and staging plus `--accounts`. The full real-service suite passed on Debian 13 with PostgreSQL 17.11 and S3Mock. Checks covered refused environments and counts, exact fixtures, 1,000 accounts twice, unchanged documents/jobs, HTTP ownership and storage, workers, and shutdown. Previously recorded image IDs predate this change.


| Check | Result |
| --- | --- |
| `npm ci`, `npm test`, `npm run build` on Node 24 | Pass, two unit tests |
| Containerfile build including tests and standalone output | Pass |
| Empty database health refusal, then migrated health | Pass |
| Ordered migrations twice, exactly two migration rows | Pass |
| Additive migration, old title-only reads/inserts, preserved empty descriptions | Pass |
| Staging seed twice, password hashes preserved, no duplicated fixture documents/jobs | Pass |
| Production seed refusal | Pass |
| Two clustered web instances, two workers per web instance | Pass |
| Login, registration, wrong password, ownership, CRUD, origin refusal | Pass |
| Private upload and cross-process download, exact binary bytes | Pass |
| Cross-process sessions, logout revocation, fresh login | Pass |
| Two job workers finish 22 reports, fixture output `record_count=1` plus LF | Pass |
| Kill a worker holding a job transaction, then recover the waiting job | Pass |
| Job SIGTERM during a blocked count, then completion and exit 0 | Pass |
| Health SQL deadline while migrations table is locked | 1.505 seconds |
| Ordinary mutation deadline while records table is locked | 12.007 seconds, HTTP 503, no inserted row |
| Web SIGTERM during a blocked HTTP mutation | Pass, mutation completes and launcher exits 0 |
| Native standalone web processes reconnect after database restart | 3.454 seconds including restart |
| Two web and two job containers reconnect after database restart | 4.205 seconds including restart |
| All four container identities and every child PID unchanged across restart | Pass |
| Session, fresh write, and report completion after restart | Pass |
| Lost reply after committed mutation, no automatic replay | HTTP 503, exactly one saved row, next distinct write succeeds |
| Non-root container runtime and generated static JavaScript | UID 1000, HTTP 200 |
| Shared HTTP checker against two web containers and two job containers | Pass |
| All four proof containers stop cleanly | Exit 0 |
| Logical database dump/restore, exact saved-row comparison | Pass, 1.537 seconds including dump and database creation |
| Restored pre-backup session and password login | Pass |
| Four document objects copied into isolated bucket | Pass, all bytes equal the pre-backup manifest |
| Fresh independent setup/build/service/HTTP guide replay | Pass, no product edits or undocumented intervention |
| Systems repository template `mmx validate` | Pass with compatible current MMX build |
| New files' public-content check | Pass, zero findings |

The additive test runs old title-only SQL before and after migration 0002.
The test does not build and run a separate old Next.js application image.
The previous SQL insert shape remains usable after the new column exists.

The first database URL listed an unreachable address before the reachable
primary. The restart ended existing connections. Subsequent connections used
the unchanged multi-host URL and discovered the writable database again.
The restart does not prove selecting between a real primary and standby.

A transparent test relay buffered a mutation's PostgreSQL replies until an idle
ReadyForQuery message. The relay then closed the connection without delivering
those replies. An independent database query found one committed row, even
though HTTP returned 503. The app did not replay that mutation.
This check proves the ambiguous-result behavior for the injected fault.

## Repeat the checks

Follow the [guide](../../../docs/app-frameworks/nextjs-prisma-pg.md) to provide
an empty assigned database, private bucket, protected settings, and two free ports.
Run `npm ci`, `npm test`, and `npm run build` before `node tests/services.mjs`.
Use `TEST_DATABASE_RESTART_ARGV` only when you own every user of that database service.
The service script retains synthetic data and stops its own child processes.

Build the image with the guide's Containerfile command. Run two instances on
different assigned ports against the same database and bucket. Run two job
containers. Supply `FIXTURE_PASSWORD` privately and run `tests/check_portal.py`
with each instance's private address. Inspect the container user and stop results.

For a logical restore, stop test workers before taking the saved-row manifest.
Keep one pending job and completed output. Save ordered row values for accounts,
sessions, records, documents, report_jobs, and schema_migrations before the dump.
Never publish password hashes, session tokens, or protected environment files.

Run `pg_dump -Fc` against the assigned source database. Restore with `pg_restore`
into a separate empty database. Compare every saved row value, including owner
IDs, password hashes, session expiry, object keys/hashes, job states/output, and
migration versions. Use protected connection settings for both commands.

Copy recovered objects to a separate bucket. Compare recovered bytes with the
pre-backup manifest before starting an isolated restored web process. Reuse an
unexpired pre-backup session. Also verify a fresh password login and download
owned documents from the restored app. Start no worker against the source queue
as a side effect of the restore check.

The recorded snapshot held six accounts, six sessions, six records, four
private-document rows, 26 jobs, and two migration rows. All row values matched
after restore. Four recovered objects matched their saved bytes.

## Remaining live checks

- Deploy as another app through the Stack's normal configuration and deploy path.
- Verify public HTTPS browser behavior, keyboard use, Access-protected staging, and ingress limits.
- Keep an old browser page open across two image releases and verify asset bridging.
- Run a separate previous-release image through the additive migration and rollback.
- Switch a real primary and standby in both directions with app and job processes running.
- Measure silent TCP failure recovery under the Stack's kernel settings.
- Repeat HTTP, worker, and switch checks through transaction-mode PgBouncer.
- Verify actual R2 TLS, bucket-scoped credentials, denied access, and byte recovery.
- Restore through the Stack's database backup chain and separate uploads backup.

S3Mock is an API test service, not an R2 authorization proof. The object recovery
check used S3 CopyObject, not the Stack's backup chain. A short logical restore
time is not a whole-site recovery time. No provider compatibility conclusion or
completed Vercel migration is implied by these isolated framework checks.
