# The reference app

The reference app is a small web app, written in Go, with its data in
Postgres. The Monkeymaxxing Stack's proofs and courses deploy the reference
app. The reference app's home page shows which app server and which
database server answered the request. A person watching a deploy, a
database failover, or a recovery after every database server is lost sees
the event happen on the home page.

A team that uses the stack brings its own app. The stack never needs the
reference app. The reference app exists so the proofs and the course have
an app whose page shows what the system does. The reference app also meets
every point of the stack's [app contract](../docs/design.md#the-app-contract).
So the reference app is an example of an app that the stack's coding agent
finds nothing to fix in.

## What the pages show

- **`/`, the home page,** shows:
  - The host name of the app server whose web container answered.
  - The IP address that the request arrived on, with the server name from
    `/etc/hosts`, such as `10.20.1.1 (app001)`.
  - The release, such as the commit CI built.
  - The database server that stored the new page-view row, such as
    `10.20.2.1 (db01)`, labelled as the primary.
  - The newest jobs, with the server that added each job and the server
    that ran the job, and an **Add a job** button.
  - The newest page views, each with the app server and database server
    that handled the page view.
  - The number of page views so far, counted through `DATABASE_READ_URL`
    on a replica when one answers, or on the primary otherwise, with the
    server that counted the views.
- **`/cached`,** a page that Cloudflare may keep for 60 seconds. The
  `/cached` page shows when and on which app server the page was rendered.
  So a reload that Cloudflare answers from a saved copy of `/cached`
  shows the time of the saved rendering.
- **`/up`,** the health URL. The `/up` endpoint answers 200 only when the
  app can serve requests, and 503 otherwise.

What you see on the home page:

- **During a deploy:** the release changes at the moment the deploy
  switches to the new release, and no reload fails.
- **During a database failover:** the database server changes, such as from
  `db01` to `db02`. For the few seconds until the new primary accepts
  writes, the page says that the database didn't answer.
- **With several app servers:** the app server can change from reload to
  reload. Caddy is the web server in front of the apps on each app server.
  Caddy sends each request to a web container on any app server.

## The settings for your systems repository

The systems repository is the repository that the stack's coding agent
writes for a team's servers. At chapter 3 (get your app ready to deploy), set the following values in the
systems repository's `mmx_project_settings.yml`:

```yaml
# mmx_project_settings.yml, in the systems repository
vars:
  apps:
    reference_app:
      image: ghcr.io/example/reference-app        # where your CI pushes the image
      web_ports: [8001, 8002]                     # the systems repository picks two free ports in 8001 to 8099
      health_url_path: /up
      migration_command: reference_app migrate
      jobs_command: reference_app jobs
      jobs_connect_directly_to_postgres: false    # the reference app's worker
                                                 # polls the queue inside transactions
      asset_directory: /app/assets
      database_name: reference_app
      env: {}                             # no plain settings: the stack sets PORT itself
      secrets_from_vault: []                      # no secrets but DATABASE_URL, which the stack writes
      production_uploads_r2_bucket: ""            # the reference app keeps no uploads
      restore_drill_check_queries:                # each answers true or false, on the restored copy
        - name: the_migrations_came_back
          sql: select count(*) > 0 from schema_migrations
```

The app's only secret is the database password, in the vault as
`reference_app_database_password`. In `playbooks/every_server.yml`, the
`app_server` role's `app_secrets` passes the database password to the app
servers with the following line:
`reference_app_database_password: "{{ .secrets.reference_app_database_password }}"`.
The stack writes the database password into `DATABASE_URL`, with every
database server:

```text
DATABASE_URL=postgresql://reference_app:PASSWORD@db01:5432,db02:5432/reference_app?target_session_attrs=read-write&connect_timeout=3
```

The restore drill restores the production database onto a separate server
every week and runs the check queries read-only. Each query must answer
true. The first drill runs at the end of chapter 7 (install everything on the production servers)'s run 2 (configure every server), before anyone has
opened the app. The first drill uses only `the_migrations_came_back`,
which returns true as soon as the migrations have run.

At [chapter 9 (go live)](../skills/monkeymaxxing-stack/systems_repository_template/initial_setup/09_go_live.md),
once people have opened the app, add the following query to
`restore_drill_check_queries` in a commit:

```yaml
        - name: a_page_view_came_back
          sql: select count(*) > 0 from page_views
```

The `a_page_view_came_back` query returns true once the app has recorded a
page view.

## How the reference app meets the app contract

Each point below is one item of the app contract, in the order of the
checklist's `apps` items
([`monkeymaxxing_stack_checklist.yml`](../skills/monkeymaxxing-stack/systems_repository_template/monkeymaxxing_stack_checklist.yml)).

- **The reference app's data is only in Postgres.** The reference app saves
  no uploads and keeps no sessions. The web server and job worker write no
  files while running.
- **The reference app's settings come from the environment, and the app's
  logs go to standard output.** The reference app reads three environment
  variables: `DATABASE_URL`, plus `PORT` and `DATABASE_READ_URL` for `web`.
  If a required variable is missing, the app stops at start with a message
  that names the missing variable.
  For example: `reference_app web: the environment variable PORT
  is not set`.
  The reference app's logs never hold `DATABASE_URL`.
  When the URL cannot be read, pgx, the app's Postgres driver, shows the URL
  with the password replaced by `xxxxx`.
- **The reference app's web container listens on the port in `PORT`, and
  on no other port.** The web container listens on every IP address of the
  app server. So Caddy on every app server reaches the web container at
  the private IP address of the app server running the container.
  The reference app's web container needs no Linux capability.
- **The reference app uses every CPU of the app server.** The reference
  app runs as one Go process. Go tasks called goroutines run on every CPU
  within the reference app's process. So the reference app needs no worker
  processes and ignores `WEB_CONCURRENCY`.
- **The reference app has a Containerfile,** described in
  [Build the image](#build-the-image).
- **The reference app's health URL, `/up`, passes only when the app can
  serve requests.** The database must answer within 2 seconds.
  The newest migration known to the release must also be applied.
  Caddy requests `/up` on each reference app web container every 5 seconds
  and waits 3 seconds for the answer.
  A web container that can't reach its database answers 503, and the
  reason goes to the log, not to the answer: anyone on the internet can ask
  `/up`.
- **The reference app's migrations keep the running release working.**
  `reference_app migrate` applies the SQL files in
  [`migrations/`](migrations) in the order of the file names.
  The SQL files are built into the program. Each migration runs in a
  separate transaction, which also records the migration in
  `schema_migrations`. Running `reference_app migrate` again changes
  nothing.

  Two migration runs at once are safe because each transaction first
  takes a transaction-level advisory lock (`pg_advisory_xact_lock`). The
  second run waits for the lock. After acquiring the lock, the second run
  finds the migrations already applied. The stack runs migrations with
  `PGOPTIONS=-c lock_timeout=5s`, which pgx reads. So a statement, including
  the advisory-lock request, waits at most 5 seconds for a lock and then
  fails. The migrations only add tables, and there are no down migrations.
- **The reference app's background jobs run from one command, with the
  queue in Postgres.**
  `reference_app jobs` takes the oldest waiting job in the table `jobs` with
  `FOR UPDATE SKIP LOCKED`, does a second of pretend work, and records when
  it finished and on which server. The job's row stays locked until then:
  another worker skips it, and if this worker dies first, Postgres releases
  the lock and the job waits for the next worker. When the database doesn't
  answer, as during a failover, the worker logs the error and tries again
  every 5 seconds; it never exits for it. On `SIGTERM` or `SIGINT`, the job
  worker finishes the current job, then exits.
- **The reference app deploys without dropping requests.** On `SIGTERM`
  or `SIGINT`, the web server stops taking new connections and answers the
  requests in flight for up to 25 seconds. Then the web server exits, and
  a request still running is cut off, inside the container's 30-second
  stop timeout.

  The reference app's stylesheet has a file name with a fingerprint of the
  stylesheet's content, such as `stylesheet-aec33caec024613a.css`.
  The home page links the name this release knows.
  The stack mounts a directory over `/app/assets`.
  The mounted directory holds the current release's and the previous
  release's asset files (asset bridging). So a page the old release rendered still finds
  the page's stylesheet after the switch.
- **The reference app's Postgres driver finds the primary by itself.** pgx
  tries the servers in `DATABASE_URL` in turn and keeps only one that
  accepts writes (`target_session_attrs=read-write`), so after a failover
  new connections reach the new primary. The stack's `DATABASE_URL` ends with
  `connect_timeout=3`: a database server that is switched off answers
  nothing, and without a limit pgx would wait minutes for it before trying
  the next one.
- **The reference app works behind PgBouncer in transaction mode.**
  PgBouncer shares Postgres connections among clients. In transaction
  mode, PgBouncer lends a Postgres connection to a client for one
  transaction. The stack's later step "Add PgBouncer" sets up PgBouncer.
  The reference app's tests show the app works with `TEST_DATABASE_URL`
  through PgBouncer.

  pgx's prepared statements need PgBouncer 1.21 or later, which the stack
  has. The migrations' advisory lock ends with the migration's
  transaction. The job worker's row lock ends with the job's transaction.
  The worker asks the queue every second instead of waiting with `LISTEN`,
  so the reference app's `jobs_connect_directly_to_postgres` is `false`.
- **The reference app has check queries for the restore drill,** shown in
  [the settings](#the-settings-for-your-systems-repository).

Every answer also says whether Cloudflare may keep a copy, because the
stack's Cache Rule makes Cloudflare follow the app's `Cache-Control` header,
and Cloudflare may cache an answer that has none:

| Answer | `Cache-Control` |
| --- | --- |
| `/`, the home page | `private, no-store` |
| `/cached` | `public, max-age=60` |
| `/assets/<name>`, a fingerprinted file | `public, max-age=31536000, immutable` |
| everything else, including `/up`, a missing asset, and errors | `no-store` |

The checklist's Cache Rule item checks that Cloudflare caches `/cached`
but never caches `/`. The second request for `/cached` answers
`cf-cache-status: HIT`, and `/` never does.

## Development and staging test data

After migrations, run `reference_app seed-test-data` with `APP_ENV=development` or `APP_ENV=staging` and that environment's `DATABASE_URL`.
The command creates one invented page view and one invented queued job.
Running `reference_app seed-test-data` again does not duplicate the test rows.
Any other `APP_ENV` value, including an unset value, refuses before opening the database.
Production data stays on production servers. Add a needed data shape to a seed or test.

For a local development database after migrations:

```sh
APP_ENV=development reference_app seed-test-data
```

The infrastructure reference app has no `--accounts` option. Framework examples provide scalable account fixtures.

## Build the image

```sh
cd reference_app
podman build --build-arg RELEASE="$(git rev-parse --short HEAD)" --tag reference-app .
```

The [`Containerfile`](Containerfile) has two stages. The first stage uses
Go's official image to build the program as one static file
(`CGO_ENABLED=0`) with the release built in.
Then the first stage runs `reference_app write-assets` to write the
stylesheet under a fingerprinted name into `/app/assets`.
The second stage copies the program to `/usr/local/bin/reference_app` and
the asset files to `/app/assets` onto `gcr.io/distroless/static-debian13`.
The distroless base image has no shell and no package manager, and the
container runs as the distroless image's user `nonroot`.

The Go and distroless base images are pinned by digest: each image is
identified by a fixed hash of the image's content. A build makes an image
for the machine running the build. CI's machines and the stack's servers
use x86-64, so a build on any other machine adds `--platform linux/amd64`.

The image has no `ENTRYPOINT`. The image's default command is
`reference_app web`, so the web container runs the web server.
The stack runs the remaining subcommands by giving the container a
different command:

- `podman run IMAGE reference_app migrate` runs the migrations.
- `Exec=reference_app jobs` runs the job worker from the job container's
  Quadlet file, Podman's container settings file for systemd.

The release is required: a build without `--build-arg RELEASE` stops with a
message.

## Run the reference app on your laptop

You need Go 1.21 or newer, which fetches the Go release that `go.mod`
names by itself, and a Postgres server on your laptop.

```sh
cd reference_app
createdb reference_app
export DATABASE_URL=postgresql://localhost/reference_app
export DATABASE_READ_URL="$DATABASE_URL"

go build                         # builds ./reference_app
./reference_app write-assets     # writes assets/stylesheet-<fingerprint>.css
./reference_app migrate
PORT=8001 ./reference_app web    # then open http://localhost:8001
```

In a second terminal, use the `reference_app` directory and the
`DATABASE_URL` value exported in the first terminal. Start the job worker
with `./reference_app jobs`, then press **Add a job** on the home page and
reload the home page after a second. Run `./reference_app write-assets`
again after a change to `stylesheet.css`.

## Tests

```sh
go test ./...
```

Without a database, `go test ./...` tests the pages' `Cache-Control`
headers, the health URL's 503 when the database does not answer, and the
stylesheet's fingerprint. With `TEST_DATABASE_URL` naming a throwaway
database, `go test ./...` also tests the migrations and the health URL's
200 after migrations. The tests run by `go test ./...` with
`TEST_DATABASE_URL` also check the job queue and the test-data seed's test
rows and lack of duplicates on a second run.
The database tests drop the tables of the database named by
`TEST_DATABASE_URL`:

```sh
createdb reference_app_tests
TEST_DATABASE_URL=postgresql://localhost/reference_app_tests go test ./...
```

## The code

- [`main.go`](main.go): the subcommands, the settings, and the database
  connection.
- [`web.go`](web.go) and [`pages.html`](pages.html): the web server and its
  pages.
- [`migrate.go`](migrate.go) and [`migrations/`](migrations): the
  migrations.
- [`jobs.go`](jobs.go): the job worker.
- [`seed_test_data.go`](seed_test_data.go): invented development and staging test data.
- [`assets.go`](assets.go) and [`stylesheet.css`](stylesheet.css): the
  asset files and their fingerprinted names.
