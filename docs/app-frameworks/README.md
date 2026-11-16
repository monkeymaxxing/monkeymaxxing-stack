# Application framework examples

Each example uses a customer portal to exercise accounts, owned records, private uploads,
and a PostgreSQL report queue. Each guide links to the working app and test record.
The guides explain database reconnection and adding an app to a running Stack system.
Copy the whole example into your app repository. Keep app code outside your systems repository.
The [reference app](../../reference_app/) remains the infrastructure proof app.

- [Go with net/http and pgx](go-net-http-pgx.md): a compiled HTTP server with native multi-host database connections.
- [Rust with Axum, Tokio and tokio-postgres](rust-axum-tokio-postgres.md): a compiled async server with native writable-server selection.
- [Next.js with pg](nextjs-prisma-pg.md): standalone Node output, shared database sessions and separately packaged command-line tools.
- [Laravel, Livewire and Eloquent](laravel-livewire-eloquent.md): a copyable interactive portal served by FrankenPHP, with isolated integration checks.
- [Rails with PostgreSQL](rails-pg.md): Active Record, Puma, Propshaft assets and transactional report jobs.
- [Django with PostgreSQL](django-pg.md): native accounts and sessions, psycopg, Gunicorn and WhiteNoise assets.
- [FastAPI with PostgreSQL](fastapi-pg.md): psycopg pools, Argon2 accounts and Gunicorn/Uvicorn workers.
- [Express with PostgreSQL](express-pg.md): explicit account and queue tables, the Stack database helper and Node cluster.
- [TanStack Start with PostgreSQL](tanstack-start-pg.md): server functions and HTTP routes in a persistent Nitro Node server.
- [SvelteKit with PostgreSQL](sveltekit-pg.md): an independent customer portal using adapter-node and retained frontend assets.
- [Nuxt with PostgreSQL](nuxt-pg.md): an independent customer portal using Nitro's Node server and retained frontend assets.

## Recorded integration results

Each row links to the guide containing the settings and measured results.
Built-in selection means the database driver finds a writable server when opening a connection.
Rails, Django and Laravel adapt the Stack URL to the native driver's settings.
Node examples use the Stack's unchanged multi-host helper because plain `pg` cannot select the primary from that URL.
HTTP reads stay on the primary for current sessions and records. Replica reads below are administrative aggregate reports.
PgBouncer pools database connections. The table describes the tested transaction mode.

| Guide | Writable-server handling | Replica reads | PgBouncer settings needed | Old-asset handling | Peak web RSS, MiB |
| --- | --- | --- | --- | --- | ---: |
| [Go](go-net-http-pgx.md) | Built-in pgx | Built-in `prefer-standby` | `max_prepared_statements = 200`; no app statement change | No external JS or CSS; old form passed | 35.7 |
| [Rust](rust-axum-tokio-postgres.md) | Built-in tokio-postgres | Report helper probes hosts, then falls back to primary | `max_prepared_statements = 200`; no app statement change | No external JS or CSS; old form passed | 22.7 |
| [Next.js](nextjs-prisma-pg.md) | Stack Node helper | Helper implements `prefer-standby` | Transaction-local timeouts; keep client `query_timeout` | Retain `/app/.next/static`; old JS/CSS checks passed | 256.3 |
| [Laravel](laravel-livewire-eloquent.md) | Built-in libpq through PDO settings | Named connection with `prefer-standby` | Disable named prepares; persistent PDO; URL timeout; transaction-local job timeouts | Empty `/app/assets`; Livewire URL unchanged; old component passed | 165.1 |
| [Rails](rails-pg.md) | Built-in libpq through parsed settings | Separate Active Record connection | `prepared_statements: false`; transaction-local timeouts | Retain `/app/public/assets`; old JS/CSS checks passed | 297.2 |
| [Django](django-pg.md) | Built-in psycopg/libpq through parsed settings | Named connection with `.using("replica")` | `DISABLE_SERVER_SIDE_CURSORS: True`; transaction-local timeouts | Retain `/app/staticfiles`; old JS/CSS checks passed | 133.7 |
| [FastAPI](fastapi-pg.md) | Built-in psycopg/libpq | Built-in `prefer-standby` | Remove startup statement timeout; set timeout inside transactions | Retain `/app/assets`; old JS/CSS checks passed | 170.6 |
| [Express](express-pg.md) | Stack Node helper | Helper implements `prefer-standby` | Transaction-local timeouts; keep client `query_timeout` | Retain `/app/assets`; old JS/CSS checks passed | 187.3 |
| [TanStack Start](tanstack-start-pg.md) | Stack Node helper | Helper implements `prefer-standby` | Transaction-local timeouts; keep client `query_timeout` | Serve retained `/app/.output/public`; all 3 old URLs passed | 245.6 |
| [SvelteKit](sveltekit-pg.md) | Stack Node helper | Helper implements `prefer-standby` | Transaction-local timeouts; keep client `query_timeout` | Serve retained `/app/build/client`; all 36 old URLs passed | 219.5 |
| [Nuxt](nuxt-pg.md) | Stack Node helper | Helper implements `prefer-standby` | Transaction-local timeouts; keep client `query_timeout` | Serve retained `/app/.output/public`; all 7 old URLs passed | 242.0 |

For Node, remove startup `statement_timeout` and `idle_in_transaction_session_timeout`.
Set statement and lock timeouts with `SET LOCAL` after `BEGIN`. Keep client `query_timeout`.
Rails removes timeout `variables:`. Django removes timeout connection options. FastAPI removes the appended startup timeout.
The guides give the complete settings, including direct migration connections and Laravel's keepalive settings.
Laravel's persistent connections prevent repeated dead-host probes from exceeding the proxy health timeout.
Disabling PDO named prepares also prevents report transactions from failing through PgBouncer.

RSS is resident process memory. The recorded peaks include each web process group, including master and worker processes.
The measurements used one web worker and one jobs process per app, on Debian 13 x86-64, through transaction-mode PgBouncer.
Rails and Django used two web threads. The guides sampled every 100 ms for about 18 seconds.
The load used four read clients, twelve queued reports and two uploads at each app's transfer limit.
The table excludes jobs memory and release overlap; the next section adds both.
The measurements are short observed peaks, not throughput rankings or tested app counts per server.

## How many apps fit on an app server

| Framework | Peak web RSS, MiB | Peak jobs RSS, MiB | Apps on a 4 GiB app server | Apps on a 16 GiB app server |
| --- | ---: | ---: | ---: | ---: |
| Go | 35.7 | 19.1 | 23 | 121 |
| Rust | 22.7 | 5.7 | 41 | 215 |
| Next.js | 256.3 | 85.1 | 3 | 18 |
| Laravel | 165.1 | 60.7 | 5 | 28 |
| Rails | 297.2 | 104.9 | 3 | 15 |
| Django | 133.7 | 62.7 | 6 | 33 |
| FastAPI | 170.6 | 72.7 | 5 | 26 |
| Express | 187.3 | 86.8 | 4 | 23 |
| TanStack Start | 245.6 | 86.7 | 3 | 18 |
| SvelteKit | 219.5 | 86.6 | 4 | 20 |
| Nuxt | 242.0 | 86.4 | 3 | 19 |

The counts are apps of one framework on one app server, by memory alone.
Each app's budget is two peak web releases, because a deploy runs the old and new web containers together, plus one jobs process, plus a quarter for growth.
The estimate keeps 1 GiB for the system and a tenth of the server's memory free; the deploy's memory check also requires the tenth to stay free:
`floor((0.9 × server_MiB − 1024) / (1.25 × (2 × web_peak_MiB + jobs_peak_MiB)))`,
with the unrounded measurements.
The measurements ran on app001 of the 2026-11-04 lab system, with the worker settings above.
More web workers multiply an app's memory. CPU and database connections can allow fewer apps than memory does.
Compare the guides' complete memory budgets before sizing a server.

The guides record live database switching, replica reports, R2 transfers, PgBouncer and browser release checks.
Read each guide's proof limits before relying on a protection claim. Full Stack recovery remains a separate check.
The browser fixtures cover a single page. Additional lazy-loaded routes need separate checks.
Laravel's overlap result does not cover a Livewire upgrade or Vite asset changes.
