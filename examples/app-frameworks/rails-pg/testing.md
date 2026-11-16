# Variances and guidance needs

Rails needs a connection configuration boundary because Active Record rejects the
Stack's multi-host URL. libpq parses the original URL into host and port lists.
The app consumes `DATABASE_URL` before Rails' automatic URL parsing.
New connections retain `target_session_attrs=read-write` and `connect_timeout=3`.
All reads use the primary. `DATABASE_READ_URL` is unused.

Puma uses `WEB_CONCURRENCY` processes with four threads and four connections each.
Puma explicitly uses the production Rails environment, including staging.
Puma disables its default SIGTERM exception so successful draining exits 0.
Bundler loads before the launcher consumes arguments because Bundler can restart Ruby.
Rails assumes HTTPS termination at the ingress so Secure cookies are emitted.
Every mutation requires the exact configured Origin instead of Rails form tokens.

Propshaft's actual fingerprinted assets live at `/app/public/assets`.
The Stack must bridge that directory between releases.
Migration runners need direct PostgreSQL for Rails' session advisory lock.
The report queue uses transaction row locks and needs no session affinity.

This record covers isolated app services. A complete shared Stack proof remains separate.
No image was published and no live Stack configuration was changed.

## Versions and artifact identity

Checked 2026-11-04 on Debian 13 x86_64 with PostgreSQL 17.11.
Native Ruby was 3.3.8 with Bundler 2.6.7. The image uses Ruby 3.4.7.
The lockfile records Rails 8.1.4, Puma 7.2.1, pg 1.7.0, Propshaft 1.3.2,
and aws-sdk-s3 1.237.0. Python 3.13.5 with psycopg 3 ran the service checks.
Podman 5.4.2 ran app containers and S3Mock.

The Rails version was checked against [Rails releases](https://rubyonrails.org/releases).
The relevant platform guidance is [Rails configuration](https://guides.rubyonrails.org/configuring.html)
and [the pg connection interface](https://deveiate.org/code/pg/PG/Connection.html).

[source-sha256.json](source-sha256.json) identifies
executable, configuration, build, and test inputs.
The Containerfile pins the Ruby base by digest.
S3Mock used `docker.io/adobe/s3mock@sha256:ab01a6946750f451ca215a47e91030695b260e4003b8a5a6201d25029b8fca92`.

## Executed proof

- 2026-11-05: The full isolated PostgreSQL 17/S3 suite passed with complete first-run fixture snapshots. Every fixed row and password hash survived reruns, two 1,000-account runs, and a different `FIXTURE_PASSWORD`. Previously recorded image IDs predate the test changes.

- 2026-11-05: `seed-test-data` now supports development and staging plus `--accounts`. The full real-service suite passed on Debian 13 with PostgreSQL 17.11 and S3Mock. Checks covered refused environments and counts, exact fixtures, 1,000 accounts twice, unchanged documents/jobs, HTTP ownership and storage, workers, and shutdown. Previously recorded image IDs predate this change.


- Fresh dependency install and asset compilation passed.
- Migration 1, title-only insert, additive migration 2, repeated migration, and old-shape insert passed.
- Production seeding refused. Staging seed twice preserved the exact fixture and saved passwords.
- Two web instances, with two Puma workers each, shared database sessions.
- Registration, password login, logout revocation, owner-scoped CRUD, and foreign-Origin refusal passed.
- Private upload/download byte equality and SHA-256 passed. Guessed document and report IDs were refused for another account.
- Two workers completed 22 initial reports. A killed worker's open transaction left the job available for another worker.
- SIGTERM drained an in-flight report transaction and an in-flight HTTP write. Processes exited 0.
- A real PostgreSQL standby was listed before the primary in the unchanged URL.
  The app wrote through the primary while the first host was read-only.
- The old primary stopped and the standby promoted. Existing sessions, fresh writes, documents, and jobs worked afterward.
  Surviving web and job process IDs stayed unchanged. Recovery checks took 1.473 seconds from the promotion command.
- A fresh independent reader installed a clean copy into a separate bundle directory and replayed the complete guide's service checks.
  The replay also checked the final HTML document, fingerprinted CSS, and launcher fix. No unresolved guide gap remained.

The native suite's primary-change measurement includes command execution and subsequent checks.
The observed duration is not a recovery ceiling.
The standby was a real streaming replica, promoted directly through PostgreSQL tools.
The run did not exercise Stack failover orchestration.

## Image and logical recovery proof

The tested image ID is `f46491066eebe35421e4413787723383c901c04ea17f54b460a33b26877c0e01`.
The actual image ran as UID 1000 with two web and two job containers.
The image served the HTML document and fingerprinted CSS and passed the shared HTTP checks.

A logical dump/create/restore comparison took 1.271 seconds.
Every saved row matched across 13 accounts, 14 sessions, seven records,
seven documents, 30 report jobs, and two migration versions.
The restored app accepted a saved session and password login.
An isolated copied bucket supplied matching bytes for restored document references.
Those counts include synthetic accounts retained by earlier image checks.
No production data was used.

A five-second lock wait returned HTTP 503 in 5.020 seconds and inserted no row.
A PostgreSQL relay withheld the reply after a committed mutation, then closed the connection.
The app returned 503 while exactly one row existed. No automatic replay occurred.
A later distinct write succeeded.

## Reproduce

Follow the complete [Rails guide](https://github.com/monkeymaxxing/monkeymaxxing-stack/blob/main/docs/app-frameworks/rails-pg.md).
Supply an empty PostgreSQL 17 database, separate private S3-compatible bucket,
protected runtime environment, and two unused ports. Install psycopg 3 for the test runner.

```sh
bundle install
RAILS_ENV=production bundle exec rake assets:precompile
python3 tests/services.py
```

The service runner intentionally retains synthetic rows for restore inspection.
The runner stops its own processes on success or failure.
Only an isolated, owned primary/replica environment may supply `TEST_PROMOTE_ARGV`.
Never restart or promote a service shared with another app.

## Remaining shared-system checks

The later deployment must prove real R2 authorization and TLS, public browser flows,
Stack `switch_database_primary` in both directions, silent network loss, PgBouncer,
previous-release asset delivery, image rollback, and the Stack backup chain.
The old SQL shape was checked after migration 2. A separately built previous Rails
image still needs the real deploy/rollback check.

A first restore drill checks migration versions only. Later drills must compare
accounts, password/session hashes, ownership, records, document metadata, pending jobs,
completed output, and migration versions against a saved manifest.
Object bytes need a separate backup and byte comparison.
A logical database restore is not a whole-system recovery measurement.
