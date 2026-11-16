# Render migration example

## Variances and guidance needs

This example restores a handwritten Render customer portal into PostgreSQL 17 and S3-compatible storage.
The source used Render Postgres, a disk-backed web service, a native background worker, and a native cron service.
Existing application accounts use bcrypt. No managed identity-provider exit is claimed.
The [migration guide](../../../docs/app-platform-migrations/from-render.md) explains the customer workflow and completion limits.

## Commands and files

Use Node.js 24 and the pinned `package-lock.json`.
Copy `environment.example` to a protected location outside Git, replace the example values, and load the env file.
`DATABASE_URL` accepts the Stack's server list. `RESTORE_DATABASE_URL` names one primary for PostgreSQL tools.
The database helper is copied unchanged from the Stack's Node guidance.

```sh
npm ci --ignore-scripts
node scripts/verify_export.mjs
node scripts/restore_database.mjs
node scripts/import_objects.mjs
node app.mjs migrate
node app.mjs web
```

Run web and jobs as separate processes. The jobs process also checks the daily archive schedule after 03:00 UTC.

```sh
node app.mjs jobs
```

The restored controls start paused because the source was frozen for export.
Only an administrator can change maintenance, worker, and scheduler controls through `/api/operations`.
Enable destination work only after source execution is stopped and the data comparison passes.

`node app.mjs schedule` runs one archive occurrence and exits.
The date ledger makes concurrent calls process an occurrence once. The fixture records use UTC dates.
The automatic destination schedule catches up the current day's task after 03:00 UTC. Older missed days do not run separately.

`npm run seed-test-data` creates its fixed invented fixture through an already running app.
The command requires `APP_ENV=development` or `APP_ENV=staging`, `APP_URL`, and `FIXTURE_PASSWORD`.
The test-data command does not read a source export, reset existing passwords, or duplicate an existing fixture.

## Fixture rehearsal

Use a new isolated database and S3 bucket. Never point the rehearsal at a production app.
The rehearsal creates and deletes records, registers a synthetic account, completes jobs, and changes schedule state.
Set the confirmation values in the example env file after checking the targets.
Load `FIXTURE_PASSWORD` from the original protected fixture password file without printing the value.
Run after the export verification, database restore, and object import above:

```sh
node --test tests/rehearsal.test.mjs
```

The tests compare every restored row before making changes.
Then the tests check existing passwords, stable ownership, shared sessions, private bytes, CRUD, jobs, schedules, and logout.
See [test_record.md](test_record.md) for measured evidence and exclusions.

## Fill a laptop or staging with test data

The command fills a developer's laptop database or staging with invented test data.
After the guide's local database and bucket setup, run migrations and start the app.
Set `APP_URL` to that app and supply `FIXTURE_PASSWORD`, then run:

```sh
APP_ENV=development npm run seed-test-data
```

For staging, use `APP_ENV=staging` with its own database and bucket.
`npm run seed-test-data -- --accounts 200000` makes enough rows to show slow queries.
The count includes the two fixed accounts. Extra accounts use bulk SQL through
`DATABASE_URL`; they get one record each and no files or report jobs.
Reruns add missing rows, and a smaller count removes nothing.
