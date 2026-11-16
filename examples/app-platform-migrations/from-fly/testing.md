# Verify a disposable restore

Use an isolated Linux environment with PostgreSQL 17, Podman, and an S3-compatible test server.
Restore the protected source export using the migration guide before running these tests.
Run `verify-export.mjs`, `compare-database.mjs`, and `import-objects.mjs` before allowing any app writes.

Start two web containers from the same image and protected environment file.
Set `PORT=18001` on the first container and `PORT=18002` on the second container.
Use `WEB_CONCURRENCY=2`, `COOKIE_SECURE=false`, and `NODE_ENV=production` for the isolated HTTP test.
Set `DATABASE_URL` to the dedicated restored database. Set the destination S3 variables and `BUCKET_NAME`.
Set `FIXTURE_PASSWORD` from the protected source fixture password.

After both health URLs return 200, run:

```sh
podman run --rm --user 0 --network host \
  --env-file /secure/rehearsal.env \
  -v /secure/exports:/export:ro -v "$PWD/tests:/tests:ro" \
  customer-portal node --test /tests/portal.test.mjs
```

The test image defaults to `/app`. Tests load the application database module from that directory.
The tests require exactly the two original pending fixture reports and one record per fixture user.
The database role needs permission to create the test-only trigger and terminate its own database sessions.
The test trigger is removed after the interrupted-worker check.

The tests mutate the destination. Use a fresh database and bucket for an independent replay or final restore.
The suite checks password continuity, stable IDs, cross-process sessions, ownership refusals, CRUD, exact bytes, worker rollback, concurrent claims, schedule idempotence, migrations, and reconnection.
The suite also checks malformed inputs, unauthenticated private access, and production seed refusal.

S3Mock does not enforce production bucket authorization. Verify private R2 access separately before production acceptance.
Terminating database sessions proves reconnection. A real primary/replica switch remains a separate acceptance check.

2026-11-05: Renamed the seed to `seed-test-data` for laptops and staging and added bulk `--accounts` generation. JavaScript syntax checks passed. On isolated Debian 13, Node 24.22.1, PostgreSQL 17 and pinned S3Mock, `node --test tests/seed-test-data.test.mjs` passed 1 test and `node --test tests/portal.test.mjs` passed all 4 existing tests against fresh synthetic data. Seed checks covered both allowed environments, production/unset refusals, exact fixture preservation, 1,000 accounts twice, shared generated hash and smaller-count preservation. No source platform was accessed. The recorded images predate this change.
