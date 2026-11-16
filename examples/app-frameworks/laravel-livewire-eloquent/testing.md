# Variances and guidance needs

- Laravel's URL parser does not preserve the Stack's multi-host database URL. Keep `DB_URL` unset and use the included connector.
- Laravel normally retries some lost-connection queries. The included connection disables replay because a write can commit before the reply disappears.
- Every web container needs the identical, stable `APP_KEY`. PostgreSQL stores sessions, but encrypted cookies still depend on `APP_KEY`.
- Laravel's normal database queue reserves and acknowledges work separately. `portal:jobs` uses a transactional `SKIP LOCKED` job table instead.
- FrankenPHP uses PHP threads for `WEB_CONCURRENCY`. `PORT` controls the sole app listener. No separate PHP-FPM service is needed.
- Staging needs an environment-specific `APP_ENV=staging`, database, bucket, origin and restricted credentials. Production defaults would refuse seeding.
- PHP needs local writable compiled-view directories. Customer state remains in PostgreSQL and S3.
- Laravel uses the `migrations` table and Artisan commands, so restore queries and deploy commands differ from the Go fixture.
- Forms and JSON clients use Laravel CSRF tokens and cookies. The Go fixture's origin-header rule does not replace Laravel CSRF handling.
- Livewire JavaScript is served by PHP. `/app/assets` remains empty for the Stack's asset-copy path. No Node build is needed.
- The health statement deadline is two seconds, with additional connection time per listed host. Allow that distinction when interpreting outage measurements.
- The isolated test uses loopback HTTP with secure cookies disabled. Production keeps HTTPS-only cookies.
- The isolated S3-compatible test service does not establish real R2 authorization. Database restart does not establish a real primary promotion.
- PgBouncer role refresh, real `switch_database_primary`, shared Stack deployment and Stack backup recovery require live checks.
- The local replay needs Linux, Podman, PHP extensions, Composer and Python `boto3`. S3 test ports 9090 and 9191 must be free.

## Test method

From the copied example directory, install locked development dependencies, build the image, and run:

```sh
COMPOSER_CACHE_DIR="${TMPDIR:-/tmp}/laravel-composer-cache" composer install --no-interaction --no-progress
podman build --build-arg RELEASE=local-check --tag localhost/laravel-portal:check .
python3 tests/check_local.py localhost/laravel-portal:check
```

The runner creates a fresh PostgreSQL 17 database and private S3 test bucket.
The runner starts two web containers with shared PostgreSQL sessions and a shared encryption key.
The database URL lists an unreachable address before the live database address.
Passwords are random, temporary and never printed. Test containers are removed after each run.
The private temporary evidence directory contains the check results and container logs.

The runner checks migration idempotence, the additive description default, exact fixture rows and unsafe-seed refusal.
PHPUnit checks URL conversion, uncertain-query refusal and Livewire CRUD and ownership.
HTTP checks cover registration, login, cookie reuse across containers, logout revocation, CSRF, ownership, CRUD and S3 byte equality.
Two workers complete fixture reports and concurrent report requests.
A killed worker holds an open transaction before the check kills the worker and verifies another worker completes the report.
SIGTERM checks drain active web and jobs transactions.
The database restarts while web and jobs containers retain their IDs and configuration.
The runner checks a retained login, a fresh write and a newly completed report after reconnection.
A logical dump and restore compares all six application tables exactly and checks referenced object bytes separately.

## Recorded run

- 2026-11-05: The process `APP_ENV` guard refused production and unset values despite Artisan `--env=development`. The full isolated PostgreSQL 17/S3 suite passed, including complete fixed rows and unchanged password hashes after reruns and a different `FIXTURE_PASSWORD`. Earlier image IDs predate the guard change.

- 2026-11-05 post-fix rerun: the pinned image build and full `tests/check_local.py` suite passed. Records, sessions and authentication locks returned 503 in 5.016, 5.010 and 5.011 seconds. The statement deadline passed at 12.762 seconds, and health passed at 2.009 seconds. PHPUnit, HTTP/storage, worker recovery, reconnect, logical restore and graceful web shutdown also passed. The deadline assertions were not relaxed.

- 2026-11-05 regression fix: web-group middleware restores the ordinary request deadlines lost during PgBouncer support, including session and authentication reads, using transaction-local limits.

- 2026-11-05: `seed-test-data` allows development/staging and adds `--accounts`. PHP syntax, locked Composer installation, image build, and the seed checks passed. `python3 tests/check_local.py localhost/laravel-portal:check` also passed PHPUnit, HTTP/storage, worker interruption, graceful jobs, and database reconnect. The full suite failed at the existing locked-record `/portal` deadline check with a 20-second HTTP timeout. Later deadline, restore, and web shutdown checks did not run. Earlier recorded image IDs predate this seed change.

A complete isolated run and an independent clean guide replay passed on 2026-11-04, on Linux amd64.
The replay installed locked dependencies, built a separate image and ran the copied integration runner.
Four PHPUnit tests passed with 20 assertions and no notices.
Composer strict validation, PHP syntax, Python syntax and guide-link checks passed.

| Component | Tested version or source revision |
| --- | --- |
| Laravel | 13.40.0, `1449bf241017087fbd38c118ecaabef3f6797fdc` |
| Livewire | 4.4.8, `8d7f8fc6138274a2f3384c9db354ca012215a259` |
| Flysystem S3 driver | 3.35.3, `b03780cb97585ee7e48977f40ed599b33b751634` |
| AWS PHP SDK | 3.402.5, `ffff4dbeda1c386f66e7e819afbd55406aa9799b` |
| PHPUnit | 12.5.43 |
| Container PHP | 8.4.27, ZTS |
| FrankenPHP / Caddy | 1.13.4 / 2.11.7 |
| PostgreSQL | 17.11, Debian PGDG package `17.11-1.pgdg12+2` |
| Podman | 5.4.2 |

`composer.lock` records every dependency revision. `Containerfile` pins the FrankenPHP and Composer image digests.
`tests/check_local.py` pins the PostgreSQL and S3Mock image digests.
The test database uses the official PostgreSQL container, rather than the Stack's native Debian 13 database package.

| Behavior | Clean replay result |
| --- | --- |
| Empty-database health refusal; migrated health success | Pass |
| Ordered migrations, rerun, title-only HTTP before and after additive migration | Pass |
| Exact fixture, repeatable seed, production-seed refusal | Pass |
| Livewire CRUD and guessed-ID ownership refusals | Pass |
| Registration, login, two-container sessions, logout revocation, CSRF | Pass |
| Private S3 uploads, downloads, exact bytes and cross-owner refusals | Pass |
| Two workers complete 22 owner-count reports | Pass |
| SIGKILL rolls back an active job; a later worker completes the job | Pass |
| SIGTERM finishes an active report and exits zero | Pass |
| Database restart; retained cookie, fresh write and newly completed report; unchanged web/job container IDs | Pass, 3.013 seconds after restart began |
| Locked ordinary query | 5.056 seconds |
| Twelve-second running-statement deadline | Pass, 13.193-second command wall time including container startup |
| Two-second health statement deadline | 2.012 seconds |
| Exact logical restore of six tables; retained session and referenced S3 bytes | Pass |
| SIGTERM drains an in-flight authenticated HTTP request and exits zero | Pass |

The restart measurement starts when the stopped database is started again.
The controlled stop interval is excluded.
The restart measurement ends after the fresh HTTP write and the new report have completed.
Health returned 503 while the database was stopped.
The image ran without root privileges. Caddy configuration also validated with `WEB_CONCURRENCY=1`.

The replay image ID was `9111ea7a7ae2e9cc17cfee955b78a5510880cf48cd624af37960293855e8ca34`.
Build a deployment image from your reviewed app commit, then publish the deployment image to your registry.

The executable-source manifest digest is `3f99d45e46bad3dbb91106f795582e4874618419692b39ab15ba6885903390ce`.
The digest covers PHP, Python and INI files, the Artisan executable, Composer files, PHPUnit configuration, Containerfile and Caddyfile.
The digest hashes sorted `SHA256  relative/path` lines ending in LF. Documentation and ignored caches are excluded.
After the clean replay, only prose and Python-cache ignore rules changed.

## Boundaries of the proof

The database restart check proves reconnection and unchanged multi-host settings.
The restart check does not prove standby-first primary selection, promotion, silent TCP failure or PgBouncer behavior.
The no-replay test injects a lost reply at PDO execution and requires one execution and no reconnect.
A real proxy dropping a committed write's reply remains a separate stronger check.

The additive-migration check preserves a title-only database row while web containers remain running.
A separately built previous release during the second migration remains a live rollout check.
The logical restore uses PostgreSQL tools and the existing isolated S3 bucket.
The logical restore does not prove the Stack's physical backup, point-in-time recovery, separate-bucket restore or uploads backup.

The [guide](../../../docs/app-frameworks/laravel-livewire-eloquent.md#prove-the-live-release) gives the remaining live checks.
Do not infer a live Stack, real R2 or PgBouncer result from the isolated checks.
