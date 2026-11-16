# Variances and guidance needs

The native Fargate-to-Stack migration passed on 2026-11-06 using the Stack's managed old-database relay path.
The app first ran on the Stack against private RDS through PgBouncer and WireGuard. RDS then moved by logical replication into db01, with db02 receiving physical replication.
The measured repeat run retained every acknowledged write on both servers, kept the web and jobs containers running, and continued after RDS and the relay were powered off.

This was a targeted migration through normal Stack roles and playbooks. The destination used independent Moto storage with fake credentials. Public routing, HTTPS and real destination storage authorization were outside the run.
The earlier standalone handoff remains separate historical evidence below.

## Versions

| Item | Managed run |
| --- | --- |
| Stack | copied Node helper SHA-256 `cbcfc4fd275dc797acd017a516a61ec4f970ca011817f18b5ba7cc0727f01e42` |
| Native source | Fargate Linux `1.4.0`, x86_64; web and worker each 0.25 vCPU, 512 MiB |
| RDS | PostgreSQL 17.11, ARM64, private Single-AZ `db.t4g.micro`, encrypted 20 GiB gp3 |
| Source image digest | `sha256:26f3fc37e6c38fc1afbe914676ccbf8334ff0a1e6458caa838354aee683e6399` |
| Measured destination image ID | `b03d200600c584c9b567c32a1b1ef26cc9d110ebe134307b1ca356aa838daf7f` |
| Later socket-recovery image ID | `eff651c20af827c9841238cf1eaa18cac1df1e42236088ab75296502b2c7d4e9` |
| Relay | Debian 13, `t3.micro`, 8 GiB auto-delete disk; PgBouncer `1.26.1-1.pgdg13+1` from PGDG |
| Runtime and database tools | Node.js 24.11.0, Debian 13, PostgreSQL 17.11, Podman 5.4.2, Python 3.13.5 |
| App dependencies | pg 8.23.1, express 5.3.0, bcryptjs 3.0.3, S3/SQS SDK 3.1161.0; exact graph in `package-lock.json` |
| Operator tools | AWS CLI 2.10.0, boto3 1.43.125; cfn-lint 1.59.0 |

The running Fargate digest matched the published digest. Destination images reused the archived source image and changed only `execution.mjs` for database reconnection.
The helper stayed byte-for-byte identical to the Stack copy.
The relay package version was also recovered from retained EC2 boot output after teardown.

## Native source and platform handoff

CloudFormation created real Fargate services, private RDS, S3, separate Secrets Manager administrator/app secrets, SQS with a dead-letter queue, EventBridge Scheduler, logs and scoped roles.
A real migration task exited zero. RDS used ordinary app owner `portal` and administrator `postgres`, which is not a native PostgreSQL superuser.
The source replication role used `rds_replication`; actual replication-protocol access through the relay passed.
`rds.logical_replication=1`, `wal_level=logical` and `wal_sender_timeout=4s` were active.

Two customers registered through HTTP and retained stable UUIDs, bcrypt verifiers, owned records and two private S3 documents totaling 54 bytes.
The staging command grew the source to 10,000 synthetic accounts in 6.837 seconds. This bulk SQL fixture is not a 10,000-user browser load test.
Separate load accounts were added for the successive proof runs.

Real SQS processing completed two original reports. A duplicate notification left every completed-row field unchanged; an independent long poll then found no message.
Further immediate and 300-second reports were submitted through HTTP and dispatched by Fargate. One message was claimed with a 900-second visibility lease.
At the final source inventory, approximate counts were one visible, one in-flight and zero delayed. The original delay had elapsed during setup.
The durable SQL rows supplied destination work. Queue counts and receipt handles did not establish transfer completeness.

A temporary one-time EventBridge expression launched a real task and committed its schedule receipt. The original hourly UTC expression was restored disabled.
Both services reached desired/running/pending counts of zero, every active task disappeared, and the schedule remained disabled before Stack execution began.

Compatible PostgreSQL tools captured a protected recovery dump, code, table audit and private S3 bytes. That dump was never restored into the managed formation.
Both original objects were imported into independent destination storage and read back for SHA-256 checks.
The Stack app, with two web processes, then passed existing passwords/UUIDs, ownership refusal, original private downloads, new CRUD/uploads and logout against old RDS.
The new run recorded platform freeze/resume timestamps but did not run a continuous native HTTP writer across that platform handoff. Its measurement below concerns the later database switch.

## Relay and managed copy

PgBouncer listened only on WireGuard and connected directly to the private RDS hostname using verified TLS. No forwarding, SNAT or disabled EC2 source/destination check was needed.
Its app entry and derived copy entry pointed to the same actual PostgreSQL database. The administrator entry pointed to RDS `postgres`.

The warm-pool probe proved that `DISABLE` plus `KILL` closed existing app clients and refused fresh ones while the copy entry stayed available.
A direct fresh source session obeyed the database read-only fence.
Actual upstream connections used provider TLS 1.3.
`lock_timeout=5s`, `statement_timeout=10s` and `idle_in_transaction_session_timeout=15s` survived startup through the relay. A reused backend returned to its observed defaults, including the RDS one-day idle-transaction default.

The destination used normal utility, network, app and two-node database roles. Its app databases were empty and app roles read-only before copy.
The first app setup invoked the already-applied migration command; its three checksums matched and no DDL was pending.
The managed commands were:

```sh
./server_management_scripts/run_mmx_on_util01 run copy_the_database_moving_in
./server_management_scripts/run_mmx_on_util01 run switch_to_the_database_moving_in_through_relay
./server_management_scripts/run_mmx_on_util01 results --node db01 \
  --fleet-stage switch_to_the_database_moving_in --json
```

No separate subscription or manual switch was substituted.
All nine published relations reached ready state and the subscription streamed while the app continued writing old RDS. The ninth relation was the non-public fixture table.
Db02 received the data as the physical standby. Readiness was checked after copy; returning from the copy command alone was not treated as readiness.

## Managed measurement and complete row proof

A continuous HTTP writer submitted a new nonce every 50 milliseconds after each response. It recorded every status, request/response timestamp and complete HTTP 201 row without replaying uncertain requests.
The source was captured through the separate copy entry after fencing. Source app backends and migration slots were zero, and the source database default remained read-only.

| Measurement | Result |
| --- | --- |
| Stack helper write pause | **1.996 seconds** |
| Last source acknowledgement to first Stack acknowledgement | **2.090608 seconds** |
| First request started after relay fencing to its successful response | 1.785262 seconds |
| Full acknowledged writes | **3,497**: 240 on RDS, 3,257 on the Stack |
| Failed or uncertain requests | 15 HTTP 500 responses during the fence |
| Frozen source records retained on each node | **13,416** |
| Final records on each node | **16,673** |
| Acknowledged requests started after confirmed source shutdown | 257; zero failures in that interval |
| Largest acknowledgement gap over the whole run | 3.168288 seconds, after the switch |

Helper pause parts were fence 0.428s, catch-up 0.114s, subscription disable 0.047s, sequence copy 0.222s, large-object copy 1.112s, opening Stack roles 0.074s and subscription cleanup 0.202s.
These parts and the HTTP measurement describe different boundaries. The whole-run maximum is not the switch pause.
No acknowledged request started after the relay fence and landed in frozen source data.
This is a small synthetic workload, not a production throughput benchmark.

The [public proof scripts](tests/managed_move/README.md) checked every acknowledged field on db01 and db02.
A separate source-audit comparison also preserved every field of the original 10,000 user rows (including password hashes), two document rows, three migration rows, two completed reports and the original schedule receipt on both nodes. That comparison normalized the source Node audit's date precision and bigint wire format; the writer/source-record proof retained raw PostgreSQL precision.
They also compared every frozen source record and every raw destination record between the nodes, retaining PostgreSQL timestamp microseconds.
Only comparisons with JavaScript HTTP dates account for millisecond precision.
The non-public fixture preserved schema/table/sequence ownership and grants, both complete Unicode/binary rows, sequence `9041` with `is_called=true`, and the original large-object OID, all 98,304 bytes, owner and reader ACLs.

Web and jobs container start times remained unchanged throughout copy, switch, source shutdown and the source-off customer/job checks.
RDS and the EC2 relay both reported `stopped` before the final source-off interval. Existing passwords, IDs, private bytes, new CRUD/uploads and logout passed again.
A new report created after confirmed shutdown remained pending during 15 early samples, then completed after its 30-second due time with exact output. It used the PostgreSQL queue without SQS.

An actual pgBackRest full backup succeeded after the final writer stopped. Its metadata and all backup/upload object bytes were saved before guest teardown; backup restoration was not exercised.
The normal inventory moving block was then removed before another `every_server` run. Normal destination URLs and network configuration replaced the temporary path.

## Failures, corrections and independent replay

The first managed run exposed a destination app defect: the jobs loop exited while no database was writable. The web container stayed up.
All 6,972 acknowledged writes from that run still matched in full on both database servers, together with the non-public fixture; the final database had 16,972 records.
The full-row facts, dump and backup were saved before retiring that disposable test target and replaying from the synthetic RDS source with the jobs fix.
This test reset is not a production rollback procedure; the guide requires reconciliation after destination writes.

The successful repeat used the measured `b03d…` image above. A fresh reviewer independently ran the public verifier against both live database servers and confirmed the same rows, pause boundaries, source-off writes and unchanged container metadata.
Twelve pure proof tests checked that duplicate IDs, altered fields, lost rows, truncated timestamps, changed sequence state and lost grants fail verification.

Review found one further reconnect case: node-postgres can deliver an un-coded `Connection terminated unexpectedly` when a socket ends during a query.
The later `eff651…` image adds that exact error and Node connection error codes to the jobs retry classification.
A separate live TCP fault closed a real jobs query in flight. The same process and container stayed up with zero restarts, completed the queued report after reconnecting, and left its completed row unchanged on another processing cycle. The test container then stopped with exit zero.
The updated image was also deployed through normal app release stages and passed customer checks after source deletion.
Its socket-loss proof is separate from the earlier native relay-switch measurement.
Execution-loop tests cover nine transient error cases, plus visible failure for one-shot jobs and unexpected errors.

An unresolved shared runtime gap appeared during final teardown. Debian 13 AppArmor denied `signal=term` from profile `containers-default-0.62.2` to the worker label `containers-default-0.62.2//&crun`. The Node cluster master received `kill EACCES`; the web service stopped with exit 1. Jobs and the isolated socket-test container stopped with exit zero. The kernel audit and service status are retained. No Stack file or host-policy workaround was added. This needs the shared runtime owner's fix and a clean shutdown retest before a production release. It does not change the recorded no-restart database-switch result.

Other corrections were confined to the app or private run tooling:

- The relay initially rejected the Portal's statement/idle timeout startup settings. Tracking those alongside `lock_timeout` fixed the application-specific contract without ignoring guards.
- An SSH copy had left the relay with no destination peers. Comparing the installed peer list to the three expected peers found and fixed it.
- A private image build needed nftables. Installing that prerequisite resolved Podman networking.
- A private fault-injection URL incorrectly supplied `sslmode` to the Stack helper. The helper refused it before connecting; the corrected test used the helper's supported settings.
- The earlier uncertain-upload correction retains committed bytes after a lost SQL reply. Its focused real-database check remains part of the example.

The earlier independent native-export replay restored a recovery archive into a separate disposable database and bucket and passed customer, worker, schedule and migration checks. That archive replay is separate from the managed logical-copy proof.

## Not live-tested

- Real destination object-provider authorization, public DNS/HTTPS and browser assets through a public rolling release. The targeted app deployment omitted Caddy/public-routing stages.
- Backup restoration, independent recovery and database-primary failover. Creating the managed full backup passed.
- Production-scale data, latency or concurrency; arbitrary schemas, extensions, row security or application side effects.
- Actual SQS acknowledgement loss, poison-message retries and DLQ transfer. Duplicate delivery was native; failure injection used isolated tests.
- A full elapsed hourly EventBridge cycle. The native launch used a one-time expression; the app processes only the current UTC hour.
- EC2-hosted ECS tasks, host mounts, EFS and alternate databases. The temporary EC2 relay did not host ECS tasks.

## Historical standalone result

The 2026-11-05/06 standalone run used an earlier Stack helper and hand-controlled replication. It measured a 10.157-second database pause and a separate 58.318-second platform handoff gap, retaining 5,276 acknowledged IDs.
Those numbers do not describe the managed path. The managed measurements above replace that run as evidence for the current guide.

## Cleanup

CloudFormation reached `DELETE_COMPLETE`. Fresh lists passed 27 cleanup checks: no source RDS instance, snapshots, automated backups, parameter/subnet groups, S3 bucket, queues, secrets, schedules, logs, registry, VPC or live network resources remained.
The relay was terminated and its volume, interface, dedicated security group and imported key pair were absent.
All four custom roles and the two service-linked roles introduced by this fixture were absent.
The temporary operator IAM user was left for the account administrator.

All three task-definition revisions were deregistered and submitted for permanent deletion with the current SDK. Fresh revision lists were empty across all supported states.
Direct description/tag inventory still retained asynchronous `DELETE_IN_PROGRESS` metadata, plus stopped tasks and inactive service/cluster records. No live workload remained; the run did not remove tags to conceal historical records.
AWS can retain this metadata after deletion; see [ECS deletion states](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-definition-state.html).

Protected exports, complete dumps, full-row proof, backup bytes and independent-review output were saved before the five destination guests and the earlier separate builder were removed. The final run-prefix guest list was empty.
