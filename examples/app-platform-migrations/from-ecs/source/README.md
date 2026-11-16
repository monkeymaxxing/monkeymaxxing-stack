# Native Fargate source fixture

The native Fargate fixture and managed Stack relay migration passed on the Stack; the [test record](../test_record.md) separates that proof from the earlier standalone handoff.
The [private RDS procedure](database-last.md) describes the managed PgBouncer relay, logical copy and relay-specific switch.
Use a dedicated synthetic research environment. Keep source inventories and exports in a protected directory outside the repository.

## Prerequisites and resources

Use AWS CLI v2, Python 3, Linux Podman, a PostgreSQL-17-compatible client and the example's pinned Node dependencies.
The operator needs CloudFormation, ECS/Fargate, RDS, S3, Secrets Manager, SQS, EventBridge Scheduler, Logs, ECR and VPC lifecycle permissions.
The template creates three IAM roles. The operator needs role creation, inline policies, managed-policy attachment, tagging and scoped `iam:PassRole`.
Provider service-linked roles must already exist or be creatable by the authorized provisioning identity.
ECS and RDS use fixed account roles named `AWSServiceRoleForECS` and `AWSServiceRoleForRDS`.
AWS creates those roles automatically when needed. The fixed roles are separate from the three template-managed roles.
See [ECS service roles](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/using-service-linked-roles-for-clusters.html) and [RDS service roles](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAM.ServiceLinkedRoles.html).

`cloudformation.json` creates a VPC, two subnets, public task networking, private RDS, separate administrator/app secrets, a private bucket, two queues and one cluster.
The second queue holds failed notifications. The template creates web, worker and schedule task definitions.
Both services start at zero tasks. The hourly UTC schedule starts disabled.
RDS uses `db.t4g.micro`, PostgreSQL 17, 20 GiB gp3 storage and logical replication enabled before initial boot, with wal_sender_timeout=4000 milliseconds.
Fargate tasks request 0.25 vCPU and 512 MiB each. Logs retain one day.
The fixture has no load balancer, NAT gateway, customer traffic or production backup policy.

Every taggable template resource uses `project=ecs-migration-example`.
The scheduler's group carries the project tag because Scheduler schedules do not expose a Tags property.
Scheduled tasks carry the project tag too. One-off tasks launched with `run-task.py` are tagged.

Record a current region-specific estimate before creation.
Include Fargate, RDS, storage, public IPv4, Secrets Manager, ECR, logs, S3 and SQS.

## Publish the source image

Run on the Linux build machine using the authorized operator identity. If building remotely, pass only a short-lived ECR login token over the protected administrative channel; keep long-lived operator keys on the operator machine.
Set the chosen AWS profile, region and dedicated names explicitly:

```sh
export AWS_PROFILE=YOUR_AUTHORIZED_PROFILE
export AWS_REGION=eu-north-1
export SOURCE_STACK_NAME=portal-ecs-example
export SOURCE_REPOSITORY_NAME=portal-ecs-example
umask 077
mkdir -p /secure/ecs
aws ecr create-repository --repository-name "$SOURCE_REPOSITORY_NAME" \
  --tags Key=project,Value=ecs-migration-example > /secure/ecs/repository.json
SOURCE_IMAGE_REPOSITORY=$(python3 -c 'import json; print(json.load(open("/secure/ecs/repository.json"))["repository"]["repositoryUri"])')
SOURCE_REGISTRY=${SOURCE_IMAGE_REPOSITORY%%/*}
aws ecr get-login-password | podman login --authfile /secure/ecs/registry-auth.json \
  --username AWS --password-stdin "$SOURCE_REGISTRY"
podman build --format docker --platform linux/amd64 -f Containerfile -t "$SOURCE_IMAGE_REPOSITORY:source" .
podman push --authfile /secure/ecs/registry-auth.json --digestfile /secure/ecs/image-digest \
  "$SOURCE_IMAGE_REPOSITORY:source"
export SOURCE_IMAGE_URI="$SOURCE_IMAGE_REPOSITORY@$(cat /secure/ecs/image-digest)"
```

ECR is separate from the CloudFormation stack. Record the repository identity for separate teardown.
An independent destination image registry replaces ECR before claiming a complete AWS exit.

## Create the native source

List available PostgreSQL 17 versions in the selected region:

```sh
aws rds describe-db-engine-versions --engine postgres \
  --query 'DBEngineVersions[?starts_with(EngineVersion, `17.`)].EngineVersion'
```

Set `DATABASE_ENGINE_VERSION` to the selected returned version.
Set `OPERATOR_CIDR` to the test caller's public IPv4 `/32`.
HTTP ingress is limited to that address. RDS has no public endpoint and admits PostgreSQL only from the task security group.

```sh
aws cloudformation validate-template --template-body file://source/cloudformation.json
aws cloudformation create-stack --stack-name "$SOURCE_STACK_NAME" \
  --template-body file://source/cloudformation.json --capabilities CAPABILITY_NAMED_IAM \
  --tags Key=project,Value=ecs-migration-example \
  --parameters ParameterKey=ImageUri,ParameterValue="$SOURCE_IMAGE_URI" \
    ParameterKey=DatabaseEngineVersion,ParameterValue="$DATABASE_ENGINE_VERSION" \
    ParameterKey=OperatorCidr,ParameterValue="$OPERATOR_CIDR" \
  > /secure/ecs/created-stack.json
aws cloudformation wait stack-create-complete --stack-name "$SOURCE_STACK_NAME"
aws cloudformation describe-stacks --stack-name "$SOURCE_STACK_NAME" > /secure/ecs/stacks.json
aws cloudformation list-stack-resources --stack-name "$SOURCE_STACK_NAME" > /secure/ecs/resources.json
```

## Prepare the managed source logins

Before starting any Fargate task, prepare the private relay/tool host using the [managed relay procedure](database-last.md).
Retrieve the `DatabaseSecret` output into protected operator settings: it contains the RDS administrator `postgres`.
Retrieve `AppDatabaseSecret` separately: it contains the ordinary `portal` app password, which must also become `portal_database_password` in the Stack vault.
The task execution role reads only the app secret; endpoint, port and database name are ordinary task environment values.
Generate a separate replication password and relay-console password. Keep values out of arguments and logs.

Create a mode-600 bootstrap settings file on the private-network tool host with this shape, replacing values from the protected sources:

```json
{
  "administrator_env": {
    "PGHOST": "REPLACE_WITH_DIRECT_RDS_HOSTNAME",
    "PGPORT": "5432",
    "PGDATABASE": "portal",
    "PGUSER": "postgres",
    "PGPASSWORD": "REPLACE_FROM_ADMINISTRATOR_SECRET",
    "PGSSLMODE": "verify-full",
    "PGSSLROOTCERT": "/etc/pgbouncer/provider-ca.pem"
  },
  "app_password": "REPLACE_FROM_APP_SECRET",
  "replication_password": "REPLACE_WITH_GENERATED_REPLICATION_PASSWORD"
}
```

Run the fresh-fixture bootstrap before applying application migrations:

```sh
python3 source/bootstrap-managed-source.py roles /secure/ecs/bootstrap.json
python3 source/run-task.py node database.mjs
python3 source/bootstrap-managed-source.py publication /secure/ecs/bootstrap.json
```

The SQL tools run on the database-connected tool host; `run-task.py` runs on the authorized AWS operator machine.
The roles phase refuses existing fixture roles or app tables. It creates ordinary owner `portal`, grants its membership to the permitted administrator, and creates `database_moving_in_replication` with `rds_replication`.
The publication phase runs after the app schema exists and prepares `database_moving_in FOR ALL TABLES` plus copy grants.
RDS's `postgres` administrator has `rds_superuser` privileges without being a PostgreSQL superuser; verify its statistics/session-control permissions during the native preflight.
The bootstrap is for this fresh synthetic fixture; use the Stack procedure to prepare an existing production source.

`run-task.py` reads stack outputs and launches a tagged one-off Fargate task.
The helper waits for task completion and rejects a nonzero container exit code.
The application image omits PostgreSQL client tools. Export runs on a separate private-network tool host with a source-compatible client.
The execution role retrieves Secrets Manager values. The task role permits only the fixture bucket and report queue operations.
The app username and password arrive as separate secret environment variables. No credential value appears in task command arguments.

Save the outputs as shell variables `SOURCE_CLUSTER`, `SOURCE_WEB_SERVICE` and `SOURCE_WORKER_SERVICE` from `/secure/ecs/stacks.json`.
Use output keys `Cluster`, `Web` and `Worker` respectively.

```sh
aws ecs update-service --cluster "$SOURCE_CLUSTER" --service "$SOURCE_WEB_SERVICE" --desired-count 1 > /secure/ecs/web-start.json
aws ecs wait services-stable --cluster "$SOURCE_CLUSTER" --services "$SOURCE_WEB_SERVICE"
```

Find the running web task through `list-tasks` and `describe-tasks`.
Resolve the task's network-interface ID through `ec2 describe-network-interfaces` to obtain the temporary public HTTP address.
Populate the app through `seed-test-data.mjs` with the protected fixture password and `APP_ENV=staging`.
The two default reports stay pending until `resume-jobs` runs and a worker starts.

Exercise source SQS delivery, delayed work, redelivery and a completed report before migration.
Keep additional pending work for the final move.
Enable the schedule only for the source scheduling test.
Save the complete `get-schedule` response, then prepare the update request:

```sh
aws scheduler get-schedule --name "$SOURCE_SCHEDULE_NAME" --group-name "$SOURCE_SCHEDULE_GROUP" \
  > /secure/ecs/schedule-before.json
python3 source/set-schedule-state.py /secure/ecs/schedule-before.json /secure/ecs/schedule-enable.json ENABLED
aws scheduler update-schedule --cli-input-json file:///secure/ecs/schedule-enable.json
aws scheduler get-schedule --name "$SOURCE_SCHEDULE_NAME" --group-name "$SOURCE_SCHEDULE_GROUP" \
  > /secure/ecs/schedule-enabled.json
```

The helper removes response-only ARN and timestamp fields, preserving the schedule target, timezone, retries and optional settings.
For the final freeze, save a fresh response and prepare a new request with `DISABLED`.
Verify the saved native response reports the selected state after every update.
The [GetSchedule response](https://docs.aws.amazon.com/cli/latest/reference/scheduler/get-schedule.html) differs from the [UpdateSchedule input](https://docs.aws.amazon.com/cli/latest/reference/scheduler/update-schedule.html).

## Cleanup by recorded identity

Preserve proof before removing synthetic state.
Disable the recorded schedule and scale the recorded services to zero.
List every running task in the recorded cluster and stop only the recorded fixture tasks by ARN.
Drain active one-off tasks before stack deletion.
Empty the recorded bucket, including versions and delete markers if versioning was enabled.

Delete the CloudFormation stack by the StackId saved in `created-stack.json` and wait for deletion.
Delete the separately recorded ECR repository by name after removing its image.
Read fresh ECS, RDS, S3, SQS, Secrets Manager, Scheduler, IAM, Logs, ECR and VPC listings.
Check recorded IDs as well as the project tag. A successful delete request alone does not prove cleanup.
RDS snapshots, retained resources and replication slots require their own recorded disposition.

After stack removal, permanently delete its recorded inactive task-definition revisions with ECS `DeleteTaskDefinitions` using a current AWS CLI or SDK.
The tested older CLI lacked that operation; the current official Python SDK provided it.
Remove separately created relay resources and the scoped export role too.
AWS service-linked roles are account prerequisites: delete only roles introduced solely for this disposable run, after their service dependencies are gone.
Keep any pre-existing or shared roles. Do not delete the operator identity as part of fixture cleanup.

ECS may retain stopped/inactive historical records and task revisions in `DELETE_IN_PROGRESS` after workload removal.
Record those states separately from active resources; direct task-definition description can still return deletion state after revision lists become empty.
See [ECS deletion states and timing](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-definition-state.html).
