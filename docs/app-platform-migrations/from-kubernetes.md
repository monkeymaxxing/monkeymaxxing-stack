# Move from Kubernetes to your own system

## Variances and guidance needs

Move a coherent application out of Kubernetes, with PostgreSQL moved last.
Use the [shared container migration procedure](from-any-container-platform.md) for the common app contract, file transfer, routing, and operational acceptance.
The Kubernetes steps below add resource ownership, reconciliation shutdown, persistent volumes, and private access to an in-cluster database.

| Source behavior | Guidance and tested boundary |
| --- | --- |
| Deployments recreate Pods | Set desired replicas to zero. Deleting individual Pods does not stop execution. |
| CronJobs start independent Jobs | Suspend CronJobs, then drain active Jobs separately. Suspension leaves existing Jobs running. |
| GitOps, HPA, operators, and external deploy hooks | Find and pause the actual owner before changing desired state. The fixture has none of these owners. |
| PostgreSQL lives inside k3s | Keep the database StatefulSet running during the app move. A transition Service exposes PostgreSQL through WireGuard only. |
| Secret files and ConfigMaps | Export live values through an authorized, protected route. Git and image archives do not contain runtime values. |
| Private uploads live on a PVC | Export the owning node's files separately. Preserve object keys and owner links when importing into object storage. |
| PostgreSQL inside a dedicated source cluster | The Stack copies through logical replication. Schema changes stay frozen. Its switch copies sequences and large objects separately. |
| Managed Kubernetes storage and identity | EKS, GKE, and DigitalOcean Kubernetes variations are documented, not live-tested. |
| Stack-generated database URLs | `database_moving_in` puts the old address first and keeps destination app logins read-only until the switch. |

## What the example proves

The [example](../../examples/app-platform-migrations/from-kubernetes/README.md) uses a handwritten Node customer portal and one k3s node.
The source contains web and worker Deployments, a Service, Ingress, CronJob, ConfigMap, mounted Secret, PostgreSQL StatefulSet, and persistent uploads.
Accounts use application-owned bcrypt verifiers and UUIDs.

The targeted handoff first moves web, file storage, workers, and schedule ownership onto separate Linux containers.
The destination initially connects to PostgreSQL still inside k3s over WireGuard.
The Stack copy and switch playbooks move PostgreSQL through logical replication before source-cluster shutdown.
The [test record](../../examples/app-platform-migrations/from-kubernetes/test_record.md) states the measured results and limitations.

The [Stack database-move procedure][database-move] owns the database configuration, copy, switch, and failure recovery.
The targeted fixture uses the real copy and switch playbooks against a Stack-shaped destination.
The recorded Stack copy and switch passed from PostgreSQL 15.19 inside k3s to PostgreSQL 17.11.
The playbook reported a 1.14-second pause, and all 76 acknowledged load-test writes survived on the primary and replica.
The destination kept serving customer actions after the entire source machine powered off.
The [test record](../../examples/app-platform-migrations/from-kubernetes/test_record.md) gives timing definitions, checks, and limits.
Full initial setup, formation failover, backups, real R2 authorization, public TLS, and tunnel cutover need separate acceptance.

## Inventory the source facts

Record the source commit, dependency lockfile, image digests, Kubernetes distribution/version, PostgreSQL version, extensions, and required external services.
List accounts, password-verifier formats, sessions, record owners, document keys, hashes, queued work, schedules, and migration ledgers independently.

Start with the example's [inventory command](../../examples/app-platform-migrations/from-kubernetes/scripts/inventory-source.sh).
Use your selected kubeconfig and record the current context before collecting live objects.
Keep inventories outside Git because Secrets, annotations, and Pod specifications can contain credentials.

```sh
umask 077
kubectl config current-context
bash scripts/inventory-source.sh /secure/portal-source-inventory
```

Inspect `ownerReferences`, deployment managers, Helm releases, admission behavior, and custom resource instances discovered through `kubectl api-resources`.
Find Argo CD, Flux, operators, HPA/KEDA, CI deploy hooks, external schedules, and direct database writers where present.
A namespace's `kubectl get all` output is not a complete inventory.

Record each PVC's bound PV, storage class, reclaim policy, owning node, CSI driver, snapshots, and actual filesystem path.
A Kubernetes manifest or volume snapshot does not independently export application rows or private file bytes.
Inventory service DNS names used by the app and replace cluster-only addresses at the destination.

For each dependency, record **move**, **replace**, **retain**, or **retire**, with a reason.
Retaining RDS, Cloud SQL, an identity provider, or a bucket is a retained dependency, even after the cluster disappears.

## Freeze source execution and export

Rehearse on a disposable copy before the final production freeze.
For the final app handoff, pause external reconciliation and new writes, suspend schedules, and drain active work.
Keep PostgreSQL running throughout the app handoff.

For the example, run the following operations through the existing PostgreSQL administrative connection:

```sql
UPDATE controls SET maintenance=true, jobs_paused=true WHERE id=1;
```

The controls block new HTTP mutations and new report claims.
Already-running report transactions must finish or roll back before the export.
Inventory and drain active native Jobs too.

```sh
kubectl -n portal patch cronjob/session-cleanup --type=merge \
  -p '{"spec":{"suspend":true}}'
kubectl -n portal get jobs,pods
kubectl -n portal scale deployment/worker --replicas=0
kubectl -n portal wait --for=delete pod -l app=worker --timeout=60s
```

The source worker handles SIGTERM after finishing the current report transaction.
The database lock, report output, and completion state commit together.
If shutdown interrupts a transaction, PostgreSQL leaves the unfinished report pending.
The fixture's 30-second Pod grace period exceeds the worker's normal bounded transaction time.
A different job needs a measured drain period or an explicit checkpoint.

With source execution paused, export exact rows and upload bytes through the read-only web Pod:

```sh
kubectl -n portal exec deployment/web -- sh -c \
  'umask 077; mkdir /tmp/export; EXPORT_DIR=/tmp/export node scripts/audit-database.mjs export; EXPORT_DIR=/tmp/export node scripts/transfer-files.mjs export'
pod=$(kubectl -n portal get pods -l app=web -o jsonpath='{.items[0].metadata.name}')
kubectl -n portal cp "$pod:/tmp/export/." /secure/portal-export/
kubectl -n portal exec postgres-0 -- pg_dump -U portal -d portal -Fc \
  > /secure/portal-export/database.dump
kubectl -n portal scale deployment/web --replicas=0
kubectl -n portal wait --for=delete pod -l app=web --timeout=60s
kubectl -n portal get deployments,cronjobs,jobs,pods
```

Create `/secure/portal-export/` with mode 700 before copying.
The commands assume the example's in-Pod local PostgreSQL authentication.
Use a protected passfile or service configuration for a different source.

`table-audit.json` contains all eight application tables, including password hashes and active session hashes.
`files.json` preserves every local file key, size, and SHA-256, including files absent from document metadata.
`objects/` holds the separately checksummed bytes.
The helpers refuse missing or mismatched referenced files.
The SQL dump and row audit agree because all application writers stay frozen during collection.

Export live Secrets and ConfigMaps into the protected inventory.
Preserve encryption and signing keys where existing data or cookies depend on those keys.
Archive the selected source revision separately, including the container recipe, lockfile, SQL migrations, and deployment manifests.
A code archive contains no runtime Secrets or PVC data.

After freezing, verify zero web and worker Pods and zero active source Jobs.
Verify the selected external reconciliation owners cannot restore the old replica counts.
The k3s fixture also restarts the control plane and checks that the application stays stopped.

## Keep the in-cluster database reachable

Join the database's node to the destination's private WireGuard network before moving the app.
Keep the old database close enough to the new app servers for acceptable query latency.
Use the shared procedure for peer enrollment and firewall configuration.

The fixture restricts NodePort listeners with the k3s server configuration:

```yaml
kube-proxy-arg:
  - nodeport-addresses=10.203.11.0/24
```

The example assigns the source node `10.203.11.1` and the destination `10.203.2.1` on WireGuard.
Apply [database-transition-service.json](../../examples/app-platform-migrations/from-kubernetes/database-transition-service.json) only after the private interface and listener restriction exist.
The transition Service maps port 30432 to the database Pod's port 5432.

Point `database_moving_in` at the old PostgreSQL server itself, through the transition Service, rather than a PgBouncer or other pooler.
A pooler between the Stack apps and old PostgreSQL defeats the read-only fence and can lose acknowledged writes.
The old Kubernetes platform can keep its pooler until the switch.
If a chart or operator provides a pooler Service, find the primary PostgreSQL Service and inspect its selected Pods and `targetPort`.
Run `SHOW port;` inside the primary PostgreSQL Pod to confirm the server's own listening port.
Add the Stack's PgBouncer after the move, following [Add PgBouncer](../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/add_pgbouncer.md).

The database Pod listens on its Pod address, not the node's WireGuard address.
For the bundled PostgreSQL image, keep `listen_addresses='*'` inside the Pod.
Do not copy the bare-host procedure's WireGuard listener address into Pod PostgreSQL configuration.

The transition Service uses `externalTrafficPolicy: Local` to preserve the caller's address.
Connect to the WireGuard node that actually hosts the ready PostgreSQL Pod.
A different node without a local database endpoint cannot serve the transition connection.
From the destination app and database servers, run `SELECT inet_client_addr()` through the transition Service.
Verify PostgreSQL sees each server's WireGuard address before applying the procedure's narrow `pg_hba.conf` rules.
Preserve the source app's existing Pod-network rules while the source app still runs.
A different networking implementation needs the equivalent observed-address check before changing authentication rules.

Prove successful authenticated database access through `10.203.11.1:30432` from the destination.
Prove the node's non-WireGuard address refuses port 30432.
Do not expose the database through public Ingress or an internet-facing LoadBalancer.
Kube-proxy and networking implementations differ, so managed-cluster variations need their own reachability check.
The [k3s server reference](https://docs.k3s.io/cli/server) describes kube-proxy arguments.

Configure the source node as the unmanaged `database_moving_in` peer, outside the normal Stack database inventory.
The example's source database port is 30432 because the private Service forwards PostgreSQL traffic.
Use the [Stack procedure][database-move] to prepare the old PostgreSQL and configure the inventory and matching app credentials.
For Kubernetes, apply PostgreSQL configuration changes through the StatefulSet or operator that actually owns the database.
The fixture's source manifest sets `wal_level=logical` and the short sender timeout required by the procedure.
Schedule the required PostgreSQL restart before moving live app traffic.

Keep the database's PVC and StatefulSet running while the Stack copies and switches.
Pause any operator, GitOps owner, or deployment hook that could reset the database fence or recreate old app writers.
Record PostgreSQL command-line overrides and mounted configuration alongside the owning controller.
An override that forces writable transactions would defeat the switch's read-only fence.

## Restore on Linux and verify execution

Build the example's portable image using `app/` as the complete build context.
The destination omits `UPLOADS_DIR` and `DATABASE_URL_FILE` and uses PostgreSQL and S3 settings from a protected environment file.
Keep the original SQL migration files unchanged because the migration ledger verifies checksums.

Import the source files into an empty private destination bucket.
Preserve the original object keys so document rows need no rewrite.
Before enabling destination writes, compare the original database through WireGuard and verify imported bytes:

```sh
podman run --rm --network host --user 0 --env-file /secure/portal.env \
  -v /secure/portal-export:/export:ro portal \
  node scripts/audit-database.mjs compare
podman run --rm --network host --user 0 --env-file /secure/portal.env \
  -v /secure/portal-export:/export:ro portal \
  node scripts/transfer-files.mjs import
```

For a separate disposable restore, load `database.dump` into an empty PostgreSQL 17 database before running the comparison.
Use `pg_restore --no-owner --no-acl --exit-on-error`, with protected PostgreSQL connection settings.
Run the example's [testing procedure](../../examples/app-platform-migrations/from-kubernetes/testing.md) before choosing destination execution.

Test returning passwords, stable IDs, original private downloads, guessed-ID refusals, CRUD, new uploads, and shared session revocation.
Keep source web and worker replicas at zero throughout destination testing.
Set `controls.maintenance=false` only after exact row and byte checks pass.
Enable report processing only at the destination.

The hourly command is `node schedule.mjs`.
A destination systemd timer or the team's application scheduler must own the hourly UTC cleanup.
The database receipt prevents duplicate committed cleanup within an hour.
The fixture tests overlapping command invocations and restart behavior.
The Stack has no generic CronJob importer.

## Replicate the database last

Follow [Move a database into the Stack][database-move].
The source-to-Stack move uses logical replication across PostgreSQL major versions, subject to schema, extension, and client compatibility.
The copy goes into the Stack's normally initialized database formation.

For the fixture's address plan, the inventory contains:

```yaml
vars:
  database_moving_in:
    wireguard_address: 10.203.11.1
    wireguard_public_key: "F2qpGm7+0rhvkiDtzK0xwD1vM9t3q0HjOdC2mW1W3XY="
    public_ipv4_address: 203.0.113.50
    postgres_port: 30432
    copy_onto: db01
    apps: [portal]
    through_relay: false
```

Replace the example key and public address with the source node's actual values.
The source address belongs to `private_ip_ranges.database_moving_in`, outside every normal role range.
The old Kubernetes node never joins `nodes` or `database_servers`.
The [Stack procedure][database-move] supplies the required roles, grants, vault entries, publication, and matching app password.

Move app and execution ownership first, then verify customer actions against the old database through WireGuard.
Keep source web/worker Deployments at zero, the CronJob suspended, and active source Jobs drained.
Freeze schema migrations during copying because logical replication does not carry DDL.
Run the Stack commands from the systems desk:

```sh
./server_management_scripts/run_mmx_on_util01 run copy_the_database_moving_in
```

Wait for every subscribed table to become ready, following the shared database procedure.
Keep the PostgreSQL StatefulSet available: the switch still needs the publisher for its final catch-up, sequence values, and large objects.
Monitor the source PVC's free space while replication slots retain WAL.

## Switch and verify

Keep an HTTP writer running through the destination app and record every acknowledged record ID and response time.
Capture destination container start times before switching.
Run:

```sh
./server_management_scripts/run_mmx_on_util01 run switch_to_the_database_moving_in
```

Use the [Stack procedure][database-move] for pause measurements and failure recovery.
The playbook fences each listed source database and ends the listed app sessions.
The playbook catches up the logical copy, transfers sequences and large objects, and opens destination app logins.
The copied Node helper checks transaction writability, so new connections skip the fenced source and the unfinished destination.
The web containers keep running while new database connections select the writable login.

For Kubernetes, preserve the fence through the actual StatefulSet/operator owner.
Keep the original PVC until acceptance, because PostgreSQL stores the `ALTER DATABASE` defaults in the database cluster.
Do not let reconciliation replace the old cluster or reapply a writable default during the switch.
After successful cleanup, verify acknowledged writes, returning accounts, original files, queue state, and unchanged web container start times.
Check the source migration slot and destination subscription are gone.

## Cut over and define rollback

Use the [shared container procedure](from-any-container-platform.md) for public traffic, cookies, object authorization, backup acceptance, and rollback dependencies.
The targeted fixture uses isolated HTTP and an S3-compatible test service.

The [Stack database procedure][database-move] defines which failed switches reopen the source and which leave the source fenced.
Follow the recorded switch state before changing either database's write setting.
After destination writes, rollback requires data and external-effect reconciliation.
Restarting the old StatefulSet is not a rollback procedure.

## Retire the source

Complete the database procedure's backup and temporary-setting cleanup before retiring a real source.
Remove `database_moving_in` before another normal configuration run, as the procedure requires.

Scale the source PostgreSQL StatefulSet to zero only after the switch and subscription cleanup finish:

```sh
kubectl -n portal scale statefulset/postgres --replicas=0
kubectl -n portal wait --for=delete pod/postgres-0 --timeout=60s
kubectl -n portal get deployments,statefulsets,cronjobs,jobs,pods
```

Keep the StatefulSet's GitOps, Helm, or operator owner paused so the owner cannot restore the old primary.
Then stop the source cluster and repeat customer reads, writes, uploads, report completion, and destination scheduling checks.
Record the source retention period and cleanup owner for a real migration.

Delete resources by recorded identity after recovery acceptance.
Re-list the cluster, nodes, volumes, snapshots, load balancers, and retained cloud dependencies separately.
PVC and namespace deletion can delete backing storage according to the reclaim policy.

## Named distribution variations

| Variation | Extra discovery and handoff work | Evidence |
| --- | --- | --- |
| k3s | Inspect local-path PV/node affinity, node storage, bundled Traefik, and the actual kube-proxy configuration. Export local bytes from the owning node. | Targeted live fixture. |
| Amazon EKS | Inventory EBS/EFS, CSI provisioners, Pod Identity or IRSA, external Secrets, load balancers, and managed database dependencies. Replace cluster-bound API identity with destination-authorized access. | Documented, not live-tested. |
| Google GKE | Inventory Persistent Disk/Filestore, CSI drivers, node topology, Workload Identity Federation, external secret owners, and Cloud SQL connectivity. Replace cluster-bound identity and prove private database routing. | Documented, not live-tested. |
| DigitalOcean Kubernetes (DOKS) | Inventory block volumes, snapshots, load balancers, Spaces credentials, and database dependencies. Check retention behavior before deleting PVCs or the cluster. | Documented, not live-tested. |

EKS Pod Identity associates an IAM role with a service account in a particular cluster.
The association does not become a portable credential file. [AWS Pod Identity](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html).
EBS CSI manages EBS-backed Kubernetes volumes. [AWS EBS storage](https://docs.aws.amazon.com/eks/latest/userguide/ebs-csi.html).

GKE storage and Workload Identity Federation require separate inventory and destination access decisions.
See [GKE storage](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/storage-overview) and [GKE identity](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/workload-identity).
DigitalOcean documents volume deletion through PVC and cluster operations. [DOKS volume deletion](https://docs.digitalocean.com/products/kubernetes/how-to/delete-volumes/).

The variations do not cover arbitrary operators, service meshes, network policy replacements, multi-zone requirements, or managed identity export.

## Evidence

The [test record](../../examples/app-platform-migrations/from-kubernetes/test_record.md) records versions, commands, counts, write-pause measurements, failures, replay, and untested branches.
The example's [acceptance contracts](../../examples/app-platform-migrations/from-kubernetes/README.md#acceptance-contracts) define completion for the targeted fixture.

[database-move]: ../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md
