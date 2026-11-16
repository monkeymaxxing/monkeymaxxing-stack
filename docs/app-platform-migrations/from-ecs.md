# Move from Amazon ECS to your own system

## Variances and guidance needs

An ECS exit moves the application and replaces the AWS services the application uses.
Start with the [shared container procedure](from-any-container-platform.md), then apply the AWS differences below.

| ECS source behavior | Migration guidance and example coverage |
| --- | --- |
| Fargate owns the container hosts | Deploy the same image on Linux. The native Fargate fixture and targeted handoff passed. |
| Private RDS PostgreSQL | Use the managed PgBouncer/WireGuard relay and the Stack logical-copy/switch procedure. The native managed copy/switch passed with a writer under load. |
| Secrets Manager references in task definitions | Retrieve authorized secret values separately. A task-definition export contains references, not values. |
| Task and execution IAM roles | Replace application AWS API access with destination credentials. Image pulls and secret injection use a different role. |
| S3 private uploads | Transfer bytes and check keys, hashes and ownership separately from SQL. |
| SQS report notifications | Preserve the durable report ledger and delayed due times. The destination selects PostgreSQL jobs without SQS. |
| EventBridge Scheduler launches tasks | Disable the native schedule and inspect already-launched tasks before enabling destination scheduling. |
| ECS services and scaling maintain task counts | Stop services, scaling and independent launchers. Stopping an individual task does not stop its service. |
| Node cluster shutdown on the tested Stack host | Debian 13 AppArmor denied the web master's signal to its workers. This shared runtime gap needs a fix before a production release; the guide supplies no host-policy workaround. |
| EC2-hosted ECS tasks | Inventory host mounts, capacity providers and instance-held state too. This variation is documented, not live-tested. |

## What the example proves

The [portal example](../../examples/app-platform-migrations/from-ecs/README.md) preserves application-owned accounts and schema.
The source definition includes Fargate web and worker services, RDS PostgreSQL 17, private S3, Secrets Manager, SQS and EventBridge Scheduler.
The destination replaces SQS and native scheduling with PostgreSQL reports and an application scheduler.

The [test record](../../examples/app-platform-migrations/from-ecs/test_record.md) states the checks actually run.
The managed run used actual Stack app, utility and two-node database roles of the Stack.
The app first used private RDS through the managed PgBouncer/WireGuard relay. The database then entered the formation by logical replication.
Every acknowledged write is checked by full row contents on db01 and db02, alongside a non-public schema, sequence and large object.
The source RDS instance and relay are powered off for destination checks.
Public DNS/HTTPS and real destination object-provider authorization remain outside this targeted proof.
Final shutdown exposed an unresolved host-policy gap: the tested AppArmor profile refused the Node cluster master's worker signal. The web container exited 1; the jobs container stopped cleanly. Resolve and retest that shared runtime behavior before treating this example as production-ready.

## Collect the source facts

Record source revision, image digest, architecture, PostgreSQL version and extensions.
Save task-definition revisions, service deployments, launch type, platform version, overrides and capacity-provider settings.
Record web, worker, one-off and scheduled tasks separately.
Record the application schema, stable user IDs, password algorithms, sessions, owner links and migration checksums.

Inventory RDS, S3, SQS, dead-letter queues, Secrets Manager or SSM, EventBridge, ECR, logs and external integrations.
Mark each dependency **move**, **replace**, **retain** or **retire**.
Keeping RDS or SQS is a staged platform exit. Keeping an AWS registry or runtime service is an AWS dependency.

Keep the native responses in a protected inventory directory:

```sh
umask 077
mkdir -p /secure/ecs-inventory
aws ecs describe-services --cluster "$SOURCE_CLUSTER" --services "$SOURCE_WEB_SERVICE" "$SOURCE_WORKER_SERVICE" \
  > /secure/ecs-inventory/services-before.json
aws ecs describe-task-definition --task-definition "$SOURCE_TASK_DEFINITION" \
  > /secure/ecs-inventory/task-definition.json
aws rds describe-db-instances --db-instance-identifier "$SOURCE_DATABASE_ID" \
  > /secure/ecs-inventory/database.json
aws scheduler get-schedule --name "$SOURCE_SCHEDULE_NAME" --group-name "$SOURCE_SCHEDULE_GROUP" \
  > /secure/ecs-inventory/schedule-before.json
aws sqs get-queue-attributes --queue-url "$SOURCE_QUEUE_URL" --attribute-names All \
  > /secure/ecs-inventory/queue-before.json
```

Save every task definition, queue and schedule actually used, including failed-work queues and older EventBridge rules.
Inventory Application Auto Scaling targets, policies and scheduled actions.
Inspect service deployment controllers and CI, webhook or external task launchers too.

For S3, record bucket region, endpoint, encryption, versioning, current keys, object lengths, hashes and owner links.
For schedules, record expression, timezone, flexible window, retries, payload, target role and missed-run behavior.
For queues, record visible, in-flight, delayed and failed work plus the application's durable job identifiers.
Approximate queue counts cannot establish that every job transferred.

Retrieve referenced secrets through the authorized source identity into protected files or the destination vault.
For example, `secretsmanager get-secret-value --secret-id "$SOURCE_SECRET_ARN"` must redirect output to a protected file.
SSM uses `get-parameter --with-decryption`. Customer-managed encryption keys can require separate decryption permission.
Preserve signing and encryption keys required for existing data. Issue new destination storage credentials.

ECS injects referenced secrets when a task starts. Rotating a secret requires fresh tasks to receive the new value.
See [AWS secret injection](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/secrets-envvar-secrets-manager.html).
Temporary task credentials are not portable application secrets.

## Freeze and export

Rehearse read-only collection first. Use a final freeze only for the agreed cutover.
For this fixture, `node scripts/control.mjs freeze` blocks HTTP mutations, report work and schedule execution.
Run the control command from an authorized database-connected task.
The [source helper](../../examples/app-platform-migrations/from-ecs/source/run-task.py) launches the fixture's tagged one-off tasks without credential-bearing arguments.

Disable each native schedule through `update-schedule`, preserving the original complete schedule input.
Re-read each schedule and verify `State=DISABLED`.
Suspend service scaling and external deployment/task launchers.
Scale source worker and web services to zero, then wait for stopped tasks.
List all tasks in the cluster, including one-off tasks already launched by EventBridge.
Wait for active database transactions and upload requests to finish.

SQS notifications can remain in-flight or delayed after source consumers stop.
In this fixture, every notification refers to a PostgreSQL `report_jobs` row.
Failed dispatch leaves `sqs_notified_at` unset. Successful SQL completion precedes SQS acknowledgement.
SQS can redeliver messages, so completion is idempotent by report ID. See [AWS delivery semantics](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/standard-queues-at-least-once-delivery.html).

Preserve every report row, including `state`, `output`, `completed_at` and `available_at`.
The destination ignores notification receipts and uses the preserved SQL rows.
Do not copy arbitrary SQS payloads into this fixture's report table.
An application whose only job state exists in SQS needs its own verified transfer or source-drain procedure.
The fixture's reports commit output inside PostgreSQL. External payments, emails and other side effects need their own idempotency boundary.

The protected exporter requires frozen controls and a source execution inventory.
Supply `EXPORT_DIR`, `SOURCE_INVENTORY_FILE`, database settings and storage settings through protected runtime configuration.
Run the exporter on a machine with private RDS reachability and a compatible `pg_dump`.
The exporter captures one shared SQL snapshot, exact rows, source code and separate object bytes.
The source inventory must identify disabled schedules and stopped execution. Saved boolean fields alone do not stop AWS resources.

Set `APP_DIR` to the source checkout on that tool host, and choose a new protected export directory:

```sh
export APP_DIR=/srv/portal-source
export EXPORT_DIR=/secure/ecs-export
export SOURCE_INVENTORY_FILE=/secure/ecs-inventory/execution.json
```

`execution.json` records three required execution fields and pointers to the supporting native responses:

```json
{
  "source_execution_stopped": true,
  "schedule_state": "DISABLED",
  "queue_backend": "sqs",
  "services_file": "services-paused.json",
  "tasks_file": "tasks-stopped.json",
  "schedule_file": "schedule-disabled.json"
}
```

Set the execution fields only after fresh native responses confirm zero service counts, stopped tasks and disabled schedules.
The file names identify the supporting protected responses in the source inventory directory.
Keep the complete native inventory beside the export for review.
The verifier checks required execution fields and the inventory checksum; the verifier does not query AWS or validate supporting response files.

For RDS, load `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD` and `PGDATABASE` from the protected source settings.
Set `PGSSLMODE=verify-full` and `PGSSLROOTCERT` to the trusted RDS certificate bundle on the tool host.
Do not set the destination's multi-host `DATABASE_URL` during this native source export.
Load `BUCKET_NAME`, `AWS_REGION` and the authorized export identity's AWS profile or credentials without printing values.
Then run from the source checkout:

```sh
cd "$APP_DIR"
node scripts/export-source.mjs
node scripts/verify-export.mjs
```

## Move onto the Stack

Use the shared procedure for app settings, private object storage, releases and traffic routing.
Build the example's `Containerfile`. Keep exports and runtime secrets outside the build context.
Set `QUEUE_BACKEND=postgres`, remove `SQS_QUEUE_URL` and replace task identity with scoped destination object credentials.
Replace source `PG*` settings with the Stack destination database configuration.
Use `node execution.mjs` as `jobs_command` and `node database.mjs` as `migration_command`.
The asset directory is `/app/web`, and the health path is `/healthz`.

The app copies the current Stack Node helper unchanged for the destination multi-host `DATABASE_URL`.
Native single-address RDS connections use node-postgres with certificate verification instead.

The managed path now uses `database_moving_in.through_relay: true` and the normal Stack URLs.
PgBouncer on the source relay terminates verified RDS TLS; Stack connections reach the relay over WireGuard.
The [managed RDS procedure](../../examples/app-platform-migrations/from-ecs/source/database-last.md) replaces the earlier standalone middle phase.
Its managed native measurement is separate from the earlier standalone timings.
The database archive and source schema retain the original bcrypt verifiers, UUIDs, ownership and migration ledger.
Returning users can use existing passwords. Host-bound cookies may require signing in again at the destination hostname.

The [disposable replay](../../examples/app-platform-migrations/from-ecs/testing.md) checks exact rows before login changes sessions.
Object import uses conditional creation and reads every imported object back for SHA-256 verification.
A private destination bucket and actual destination authorization require a real provider check.

### Database order and replication

The default move leaves the database until the application and other services work at the destination.
A managed RDS instance cannot itself become a WireGuard host.
A database-last RDS move therefore needs an approved private VPC network path, potentially through a temporary WireGuard relay.
Measure latency and prove RDS remains private before choosing that path.

Move the database into the Stack by logical replication only, after the app and other services move.
Point `database_moving_in` at the source relay connected directly to RDS PostgreSQL, never at another pooler.
Use `copy_the_database_moving_in` and `switch_to_the_database_moving_in`, which runs its relay fleet stage for `through_relay: true`, from the
[Stack procedure](../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md).
Keep exports for recovery and independent replay; do not restore the archive into the managed destination or use a database-first alternative.

RDS logical replication requires the relevant roles and `rds.logical_replication=1`.
The static setting needs a reboot when changed on an existing instance.
The fixture sets the parameter before its initial boot. See [RDS logical replication](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.Concepts.General.FeatureSupport.LogicalReplication.html).

The managed rehearsal exercised the warm relay fence, ready/streaming subscription, unchanged app/jobs containers, durable replay and full-row preservation on both formation members.
Save command pause parts and actual HTTP recovery separately.
Follow the Stack procedure for source defaults, sequence/large-object transfer, rollback and slot cleanup rather than adding a parallel manual switch.

Logical replication does not copy DDL, sequence state or large objects.
See [PostgreSQL restrictions](https://www.postgresql.org/docs/17/logical-replication-restrictions.html).
The live managed fixture adds a non-public schema with a sequence and a large object, including owner and grants. Inventory another app's schema independently; this fixture does not establish universal compatibility.

## Verify accounts and execution

Before destination writes, compare every application row and private-object hash against the protected export.
Log in as both returning users and check stable IDs, owned records, private downloads and guessed-ID refusal.
Create and edit a record, upload another private document and revoke a session across two web processes.

Keep destination workers paused until source launchers and workers are stopped.
Run the destination worker without AWS queue credentials or access to the source queue.
Check pending, completed and delayed reports separately.
Interrupt an actual worker transaction and verify the unfinished report remains available.
Redeliver a source notification and verify the original completed output remains unchanged.

Continuous web and jobs processes must reconnect through the brief interval with no writable database. The destination jobs command retries database availability errors on its next cycle; one-shot jobs and unexpected errors still fail visibly.

The destination jobs command checks the current UTC hour every minute.
The schedule receipt, expired-session deletion and completion commit together.
Restarting or overlapping destination jobs processes produces one receipt per hour.
Historical missed hours are not replayed. The next run removes all currently expired sessions.

## Cut over and define rollback

Prepare destination routing, HTTPS, cookies, callbacks and external webhook settings before the final freeze.
Record the last accepted source write and first accepted destination write.
Record failed write requests and execution ownership throughout the switch.
Keep the source endpoint unable to accept writes while cached traffic drains.

Before destination writes, traffic can return to the preserved source after source execution deliberately resumes.
After destination writes, freeze again and reconcile rows, objects, report output and schedule receipts before returning.
RDS receiving new source writes after the destination switch invalidates a simple traffic-only rollback.
Keep the source and protected exports for the migration's agreed recovery window.

## Retire the source

Remove only recorded resources after acceptance.
Delete source services, tasks, schedules, scaling, unused task revisions, IAM roles and temporary network access.
Handle RDS instances, snapshots, replication slots, secrets, S3 versions, queues, dead-letter queues, logs and ECR separately.
Deleting an ECS service does not remove the application's AWS backends.

Verify fresh service lists against the recorded IDs and tags.
The [fixture cleanup](../../examples/app-platform-migrations/from-ecs/source/README.md#cleanup-by-recorded-identity) describes the source resource boundaries.
Retained AWS services must remain listed as dependencies.

## EC2-hosted ECS tasks: documented, not live-tested

Inventory container instances, Auto Scaling groups, capacity providers, launch templates and instance roles.
Export bind mounts, attached volumes and host-held configuration before terminating instances.
EFS needs a separate byte export and storage-interface assessment for either Fargate or EC2 tasks.
Confirm no unrelated service shares a host or volume before retiring capacity.
Host state, EFS behavior and EC2 capacity shutdown are outside this example's proof.

## Evidence

The [versioned test record](../../examples/app-platform-migrations/from-ecs/test_record.md) names versions, checks, failures and untested branches.
The native AWS handoff and database measurement are recorded separately from standalone regression checks and independent export replay.
