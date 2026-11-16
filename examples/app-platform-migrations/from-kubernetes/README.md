# Customer portal moved from Kubernetes

Move a Node customer portal from k3s to Linux containers, PostgreSQL, and S3-compatible storage.
The [guide](../../../docs/app-platform-migrations/from-kubernetes.md) follows the shared container procedure and adds Kubernetes-specific ownership and shutdown steps.
The [test record](test_record.md) separates the targeted handoff from full Stack deployment.

## Acceptance contracts

- The real source runs web and worker Deployments, Service, Ingress, CronJob, ConfigMap, mounted Secret, and persistent PostgreSQL and upload volumes.
- Synthetic users register, create records, upload private files, and queue reports through the source HTTP app.
- Migration retains bcrypt verifiers, stable UUIDs, sessions, record ownership, private bytes, report state/output, and migration checksums.
- Suspending schedules and scaling controllers to zero stops source execution across k3s reconciliation.
- A source worker inside a completion transaction can drain without losing or duplicating a report.
- The destination serves customer actions against the old database through WireGuard before the database moves.
- The Stack logical copy and switch playbooks preserve acknowledged writes, sequence state, large objects, and application rows across PostgreSQL majors.
- Returning users, ownership checks, writes, private downloads, uploads, reports, and scheduled work function after source-cluster shutdown.
- A fresh disposable restore independently checks the protected export, file hashes, and application behavior.
- EKS, GKE, and DOKS remain documented, not live-tested. Full initial setup, backups, real R2 privacy, and public routing require separate evidence.

## Contents and data

`app/` is a complete build context copied from the existing portable Node portal.
No sibling example is needed at build or runtime.
PostgreSQL owns eight tables, including accounts, session hashes, records, document metadata, queue state, controls, schedules, and migration history.
Source file bytes live on a PVC. Destination file bytes live in a private S3-compatible bucket.

`UPLOADS_DIR` selects the source filesystem adapter.
Without `UPLOADS_DIR`, the storage adapter uses S3 settings.
`DATABASE_URL_FILE` reads the source's mounted Secret before opening database connections.
The destination uses the Stack's unchanged multi-host PostgreSQL helper through `DATABASE_URL`.

`source.json` creates the native source objects.
Worker replicas start at zero and the CronJob starts suspended so schema initialization cannot race background work.
`database-transition-service.json` creates the temporary private database NodePort.
`scripts/inventory-source.sh` collects protected native configuration.
The transfer tools inside the app image export exact rows and every local file, then verify imports.

The upload interface buffers at most 1 MiB per request because the teaching app transfers document bodies in memory.
The synthetic PostgreSQL image creates an administrative `portal` role so disposable tests can install interruption triggers.
Before logical copying, create the procedure's `postgres` administrator and make the app role non-superuser.
Use the [Stack database procedure](../../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md) for protected passwords and replication grants.
For the bundled source image, the initial administrative SQL connection is `kubectl -n portal exec -it postgres-0 -- psql -U portal -d portal`.
The Kubernetes image's `POSTGRES_USER` selects the initial administrator, so a `postgres` SQL role is not created automatically.
If metadata insertion fails, uploaded bytes remain for reconciliation because a failed reply can follow a committed INSERT.
The file exporter includes unreferenced files so the migration does not silently discard possible uploads.

## Reproduce the synthetic k3s source

Use an isolated Debian 13 Linux source with Podman, k3s, curl, and Python 3.
The source uses pinned PostgreSQL 15.19 with logical replication enabled.
The recorded k3s version is `v1.37.2+k3s1`.
The fixture uses k3s's local-path provisioner and bundled Traefik.
Configure the private NodePort listener range before creating the transition Service, as the guide explains.

From this example directory:

```sh
umask 077
python3 scripts/prepare-source-secrets.py /secure/portal-source
podman build -t localhost/kubernetes-portal:proof -f app/Containerfile app
podman save -o /secure/portal-image.tar localhost/kubernetes-portal:proof
k3s ctr images import /secure/portal-image.tar
kubectl create namespace portal
kubectl -n portal create secret generic portal-runtime \
  --from-file=postgres-password=/secure/portal-source/postgres-password \
  --from-file=database-url=/secure/portal-source/database-url
kubectl apply -f source.json
kubectl -n portal rollout status statefulset/postgres --timeout=180s
kubectl -n portal wait --for=jsonpath='{.status.phase}'=Running \
  pod -l app=web --timeout=180s
kubectl -n portal exec deployment/web -- node database.mjs
kubectl -n portal rollout status deployment/web --timeout=180s
```

The Secret mounts at `/run/portal-secrets` because `/var/run/secrets/kubernetes.io` belongs to Kubernetes service-account projection.
The source's local image policy deliberately avoids a registry dependency.
A multi-node source needs the image on every eligible node or an authorized registry.

Populate synthetic users through the running HTTP app:

```sh
cat /secure/portal-source/fixture-password | \
  kubectl -n portal exec -i deployment/web -- node --input-type=module -e \
  'import {readFileSync} from "node:fs"; process.env.FIXTURE_PASSWORD=readFileSync(0,"utf8"); process.env.APP_ENV="staging"; process.env.APP_URL="http://web:8080"; await import("./seed-test-data.mjs");'
kubectl -n portal scale deployment/worker --replicas=1
kubectl -n portal patch cronjob/session-cleanup --type=merge \
  -p '{"spec":{"suspend":false}}'
kubectl -n portal create job --from=cronjob/session-cleanup source-hourly-proof
kubectl -n portal wait --for=condition=complete job/source-hourly-proof --timeout=90s
```

Reports start paused in the database controls so pending work remains available for migration checks.
The last command executes a native Job from the actual CronJob template.
A natural clock-triggered CronJob occurrence is a separate observation.

Use `portal.example.com` as the Ingress hostname, resolving to the source node.
Check `/healthz` through Ingress before capturing customer actions.
For an HTTP-only fixture on the source node, map `portal.example.com` to loopback in the probe container:

```sh
mkdir -m 700 /secure/portal-export
cat /secure/portal-source/fixture-password | \
  podman run --rm -i --network host --add-host portal.example.com:127.0.0.1 \
  --user 0 -v /secure/portal-export:/export -e APP_URL=http://portal.example.com \
  localhost/kubernetes-portal:proof node --input-type=module -e \
  'import {readFileSync} from "node:fs"; process.env.FIXTURE_PASSWORD=readFileSync(0,"utf8"); process.argv[2]="capture"; await import("./scripts/check-handoff.mjs");'
```

`customer-state.json` holds active synthetic sessions and stable source IDs.
Keep the customer-state file private, alongside the protected export.
The guide explains the final freeze, data export, WireGuard database access, and replication switch.

## Runtime commands

| Command | Purpose |
| --- | --- |
| `node server.mjs` | Web on supplied PORT, honoring WEB_CONCURRENCY |
| `node database.mjs` | Ordered, checksum-verified SQL migrations |
| `node jobs.mjs` | PostgreSQL-backed report worker with SIGTERM draining |
| `node jobs.mjs --once` | Attempt one report |
| `node schedule.mjs` | Idempotent hourly UTC expired-session cleanup |
| `node seed-test-data.mjs` | Synthetic laptop or staging data |
| `node scripts/audit-database.mjs export` | Protected exact eight-table snapshot while writes/jobs are paused |
| `node scripts/audit-database.mjs compare` | Compare current application rows with the frozen snapshot |
| `node scripts/transfer-files.mjs export` | Export every local file and validate document references |
| `node scripts/transfer-files.mjs import` | Create destination S3 objects and verify downloaded bytes |
| `node scripts/check-handoff.mjs verify` | Test original sessions, passwords, ownership, bytes, and CRUD |

For laptop or staging data, set `APP_ENV=development` or `APP_ENV=staging`, `APP_URL`, and a protected `FIXTURE_PASSWORD`.
`npm run seed-test-data -- --accounts 200000` adds synthetic accounts and records for query experiments.
The seed refuses production and preserves existing passwords, edited records, document rows, and jobs on rerun.
