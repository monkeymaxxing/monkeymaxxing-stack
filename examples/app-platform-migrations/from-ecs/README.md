# Variances and guidance needs

This example moves an ECS Fargate portal for independent PostgreSQL and private S3-compatible storage.
The [migration guide](../../../docs/app-platform-migrations/from-ecs.md) explains AWS inventory, execution ownership and the database-order decision.
The [test record](test_record.md) distinguishes standalone checks from live AWS proof.
The database migration passed. Final web shutdown failed on the tested Stack host because AppArmor refused the Node cluster master's signal to its workers; that shared runtime gap needs a fix before a production release. No host-policy workaround is included here.

The native source definition includes Fargate web and worker services, private RDS PostgreSQL 17, S3, Secrets Manager, SQS and EventBridge Scheduler.
The destination uses the same application tables and replaces SQS notifications with PostgreSQL job selection.
The destination jobs command also runs the hourly application schedule.

## Acceptance contracts

- Returning users retain UUIDs, bcrypt password verifiers, records and ownership links.
- Private document keys, byte lengths and SHA-256 hashes survive separately from the database.
- An uncertain metadata-write reply retains uploaded bytes, including when PostgreSQL committed before the reply was lost.
- Logical-copy rows match the frozen source on both database servers. Independent archive replays compare rows before login or workers change data.
- Each source report has a durable PostgreSQL row before any SQS notification is sent.
- Failed sends leave notifications available for dispatch. Redelivery preserves the original committed report output.
- SQS acknowledgement follows the SQL completion commit. Interrupted SQL transactions leave work pending.
- Delayed reports retain `available_at`. The PostgreSQL destination does not run reports early.
- Source schedules, services, standalone tasks and scaling cannot restart work after the final freeze.
- Only the selected execution location runs reports and scheduled work.
- The RDS source and relay can stop completely while destination writes, account, file and job checks continue.
- An AWS-exit claim requires verified replacement of RDS, S3, SQS, identity, scheduling and the image registry.
- The managed move uses logical replication only and switches through the relay without restarting app/jobs containers. The native managed run and its measured interruption are in the test record.

## Data and commands

PostgreSQL owns users, hashed sessions, records, document metadata, report jobs, execution controls, schedule receipts and migration checksums.
S3 owns document bytes. SQS carries only `{ "job_id": "UUID" }` notifications.
`report_jobs.sqs_notified_at` records successful dispatch. A failed dispatch transaction leaves the timestamp unset.
A crash after sending but before committing can duplicate a notification. The report row lock and completion state make redelivery harmless.

| Command | Purpose |
| --- | --- |
| `node server.mjs` | Serve HTTP on PORT with WEB_CONCURRENCY processes |
| `node database.mjs` | Apply ordered migrations and reject changed migration checksums |
| `node jobs.mjs` | Run source SQS processing or standalone PostgreSQL reports |
| `node jobs.mjs --once` | Attempt one processing cycle |
| `node schedule.mjs` | Complete the current UTC hour's expired-session cleanup once |
| `node execution.mjs` | Run destination PostgreSQL reports and application scheduling |
| `node scripts/control.mjs freeze` | Pause HTTP mutations, reports and schedule execution |
| `node scripts/control.mjs resume-web` | Enable HTTP mutations |
| `node scripts/control.mjs resume-jobs` | Enable report and schedule execution |
| `node seed-test-data.mjs` | Populate a laptop or staging through the app |

`QUEUE_BACKEND=sqs` requires `SQS_QUEUE_URL` and AWS task credentials at the source.
`QUEUE_BACKEND=postgres` uses no SQS API. Remove source task credentials and the queue URL at the destination.
Native Fargate uses verified RDS TLS through `PG*` settings. The managed Stack app keeps its ordinary multi-host `DATABASE_URL`; its first server is the PgBouncer/WireGuard relay during the move.
The copied current helper tests `transaction_read_only` before selecting a writable server. The database moves into the formation by the Stack logical-copy and relay-switch playbooks only.

The synthetic HTTP fixture uses `COOKIE_SECURE=false` and operator-restricted ingress.
Production behind HTTPS uses `COOKIE_SECURE=true`.
Document uploads buffer at most 1 MiB. Report delays are 0–900 seconds because the API mirrors SQS's per-message delay range.

## Source and replay

[Source setup](source/README.md) describes the native CloudFormation fixture and exact ownership boundaries.
[Testing](testing.md) describes the disposable transfer rehearsal and its limits.
Copy this whole directory for an independent app. Build `Containerfile` with this directory as the build context.
No sibling application files are required at build or runtime.

For invented staging data, supply `APP_ENV=staging`, `APP_URL` and `FIXTURE_PASSWORD` through protected settings, then run:

```sh
npm run seed-test-data
npm run seed-test-data -- --accounts 1000
```

Reruns preserve existing passwords and fixtures. Larger counts add synthetic accounts and records without copying production data.
