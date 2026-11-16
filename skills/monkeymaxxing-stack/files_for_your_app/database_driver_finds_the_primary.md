# How an app's Postgres driver finds the primary

After a database failover, another database server is the primary, the
one that takes writes. The app must find the new primary by itself, with
no restart and no change of settings. The requirement is checklist item
`<app>_database_driver_finds_the_primary`. This page says how, for each
common language, and what to build where a driver can't. The checklist
item, the skill's SKILL.md, and the design document link here, so this
page is the one place that holds these instructions.

## What the stack gives each app

Each app's secrets file, `/etc/<app>/<app>.env`, holds two settings that
list every database server:

```text
DATABASE_URL=postgresql://shop:PASSWORD@db01:5432,db02:5432/shop?target_session_attrs=read-write&connect_timeout=3
DATABASE_READ_URL=postgresql://shop:PASSWORD@db01:5432,db02:5432/shop?target_session_attrs=prefer-standby&connect_timeout=3
```

- **`target_session_attrs=read-write`:** a new connection goes to the
  first server in the list that accepts writes, the primary. Writes, and
  reads that must see the app's own latest write, use `DATABASE_URL`.
- **`target_session_attrs=prefer-standby`:** a new connection goes to a
  standby, as Postgres calls a replica, when one answers, and otherwise to
  the primary. Reads that may be a moment behind can use
  `DATABASE_READ_URL`; with one database server, it reaches that server.
- **`connect_timeout=3`:** each server gets 3 seconds to answer, so a
  server that is switched off costs 3 seconds before the next one is
  tried, not the minutes a driver otherwise waits.
- **The list** follows the inventory, so a database server added later is
  in it at the next run. PgBouncer reuses Postgres connections for the
  apps, and runs on each database server after the
  [Adding PgBouncer](../systems_repository_template/operating_procedures/add_pgbouncer.md#adding-pgbouncer)
  procedure. When `apps_connect_through_pgbouncer` is true for the app's
  environment, each URL uses PgBouncer's port, 6432. The password is letters
  and digits, so it needs no escaping. `staging01` runs every role on one
  server, for testing the apps, so on `staging01` the list holds
  `staging01` alone.

## What the app does

1. **Every database connection pool uses `DATABASE_URL` or
   `DATABASE_READ_URL`** in the format the driver accepts
   ([each language](#each-language)). No app setting names one database
   server alone.
2. **The app's driver has TCP keepalive on, with the app host's timing.**
   libpq is Postgres's client library. Ruby's pg, Python's psycopg and
   psycopg2, PHP's pdo_pgsql, and Rust's diesel use libpq, which enables
   keepalive without an app setting. Other drivers need a setting, and
   each language's entry says which. TCP keepalive ends connections to a
   dead database server
   ([When a database server dies](#when-a-database-server-dies)).
   sqlx is a Rust database library that cannot enable TCP keepalive.
   An app using sqlx gives queries a time limit instead.

Each driver below checks which server a connection reached when it opens
the connection, never for a query: an open connection stays where it is
until it ends. The pool drops an ended connection, and the new ones find
the new primary. Writes fail while no server is the primary. A read
connection to the standby that became the primary stays open until the
pool replaces the read connection. Reads on the existing connection
return correct data, but add load to the new primary. Once the old primary
is back as a standby, new read connections go to the old primary.

Each request's queries also get a time limit in the app itself, such as
the 2 to 5 seconds in the stack's
[Go reference app](../../../reference_app/README.md). A query time limit
makes a request fail fast instead of waiting for TCP. The limit is good
practice, but the limit is not what makes a failover work.

## When a database server dies

- **A switchover is a planned change of primary.** A failover happens
  automatically when the primary fails. During a switchover, or a failover
  whose old primary still runs, pg_auto_failover stops Postgres on the old
  primary.
  The old primary's kernel then closes the database connections at once.
- **A database server that loses power or drops off the network** sends
  nothing, not even an end to the database connections. Connections to
  the dead database server end only when TCP gives up. With the kernel's
  defaults, a query sent after the server died waits 15 minutes. A query
  received before the server died waits over 2 hours with keepalive on,
  and forever without keepalive. While TCP waits, the pool keeps handing
  out connections to the dead server, so the app stops answering.

  The stack shortens the TCP waits on app servers, jobs servers, and
  `staging01`, because those servers run app containers. The systems
  repository's `roles/every_server` sets `tcp_keepalive_time` 30,
  `tcp_keepalive_intvl` 10, `tcp_keepalive_probes` 3, and `tcp_retries2` 7.
  App containers share the host server's network, so the host's settings
  also apply inside the app containers. With TCP keepalive enabled and
  using the host's timing, a connection ends 60 seconds after the dead
  database server's last packet. The 60-second limit excludes sqlx and
  drivers that override the host's timing. A connection whose sent query
  gets no acknowledgement ends after about 51 seconds.
- **The failover test measured failed writes and reconnection times** with
  [`node/pg_with_multiple_database_servers.mjs`](node/pg_with_multiple_database_servers.mjs).
  The test used a Linux network namespace with `tcp_keepalive_time` 30,
  `tcp_keepalive_intvl` 10, `tcp_keepalive_probes` 3, and `tcp_retries2` 7.
  A firewall rule dropped every packet to silence the primary.
  The standby was promoted 5 seconds later, with a write every half second.

  Writes sent into the dead connections failed at 52.9 seconds.
  The next writes reached the new primary at 55.9 seconds.
  A query the primary had received ended at 60.6 seconds.
  In all, 3 writes failed. Without keepalive, the query received before the
  primary died still waited at 150 seconds. With the kernel's defaults,
  no write reached the new primary in 150 seconds.

## Each language

Most languages' standard drivers find the primary after a failover by
themselves. Ruby's, Python's, and PHP's drivers and Rust's diesel use
libpq, Postgres's own client library. Go's pgx, Java's pgjdbc, and .NET's
Npgsql also choose the server automatically. Elixir's Postgrex and Rust's
tokio-postgres choose the primary for writes.

Rails, Laravel, pgjdbc, Npgsql, and Ecto can't read a URL that lists
several servers. For these drivers and frameworks, a few lines of app code
build the driver's or the framework's own form from the stack's URL, as
each language's entry shows. Node.js gets the stack's own file. Each
entry below was checked against the driver's docs or source at the
version it names, and run against a Postgres 18 primary and standby on
one machine, on 2026-10-28, unless it says otherwise.

| Language and framework | Driver, version checked | What the app sets |
| --- | --- | --- |
| [Ruby, Rails](#ruby-and-rails) | pg 1.7.0 (libpq), Rails 8.1.4 | A few lines in `config/boot.rb` that rewrite `DATABASE_URL` and `DATABASE_READ_URL` into libpq's other URL form, because Rails can't parse the stack's and stops at boot |
| [Python, Django](#python-and-django) | psycopg 3.3.6 or psycopg2 2.9.13 (libpq), Django 6.1.2 | `DATABASES` from django-environ's `env.db_url()`; never dj-database-url |
| [PHP, Laravel](#php-and-laravel) | pdo_pgsql (libpq), Laravel 13.39 | The URL's parts in `config/database.php`, a connector that adds `target_session_attrs`, and `PDO::ATTR_TIMEOUT` |
| [Go](#go) | pgx 5.11.0 | `DATABASE_URL` and `DATABASE_READ_URL` unchanged, and a dialer that leaves keepalive's timing to the server; never lib/pq |
| [Java](#java) | pgjdbc 42.7.14 | A JDBC URL that a few lines build from each setting, with `loadBalanceHosts=true` and `tcpKeepAlive=true` |
| [.NET](#net) | Npgsql 10.0.3 | A connection string that a few lines build from `DATABASE_URL`, with `TcpKeepAlive`, and one multi-host data source for writes and reads |
| [Elixir, Phoenix](#elixir-and-phoenix) | Postgrex 0.22.4, Ecto 3.14.2 | The URL's parts in the Ecto database interface's settings, with `endpoints`, `target_server_type: :primary`, and `socket_options: [keepalive: true]`; reads that prefer a standby need a small helper |
| [Rust](#rust) | tokio-postgres 0.7.18, diesel 2.3.14 (libpq), sqlx 0.9.0 | tokio-postgres takes `DATABASE_URL` unchanged, with `keepalives_idle` 30. tokio-postgres refuses `DATABASE_READ_URL` because `prefer-standby` is unsupported. diesel takes `DATABASE_URL` and `DATABASE_READ_URL`; sqlx takes one server only, and no keepalive |
| [Node.js](#nodejs-the-stacks-file) | pg 8.23.1 with the stack's file | The stack's `pg_with_multiple_database_servers.mjs` |

**TCP keepalive:** libpq enables TCP keepalive (`keepalives=1`) and uses the
timing settings of the host running the app, so a libpq app sets nothing
([fe-connect.c](https://github.com/postgres/postgres/blob/REL_18_6/src/interfaces/libpq/fe-connect.c#L2481-L2596)).
Never set `keepalives_idle`, `keepalives_interval`, or `keepalives_count`
to 0: on Linux, 0 makes the connection fail (`setsockopt(TCP_KEEPIDLE)
failed: Invalid argument`), whatever libpq's docs say. The other drivers'
entries say what to set.

A pool keeps a connection that still works. After promotion, read
connections on the former standby keep reading from the new primary until
the pool replaces the connections. Each pool replaces connections at a
different time:

- HikariCP, the Java connection pool used by Spring Boot, replaces a
  connection at 30 minutes old by default.
- pgxpool and psycopg_pool replace a connection at an hour old by default.
- Rails and Node's pg.Pool replace connections after an idle period,
  rather than because of age.
- Go's `database/sql` does not replace connections by itself.
- Npgsql replaces connections within seconds, by itself.
- Every pool replaces connections at the next deploy, because the deploy
  restarts the app's containers.

Reading from the promoted standby returns correct data, but adds load to
the new primary. An app that sends reads to a standby to reduce work on
the primary gives the read pool a connection lifetime. The operating
procedure is
[Send reads to replicas](../systems_repository_template/operating_procedures/send_reads_to_replicas.md).
Lifetime settings include pgxpool's `MaxConnLifetime`, Rails' `max_age`, and
pg.Pool's `maxLifetimeSeconds`. The lifetime makes reads return to the
standby soon after a failover.

### Ruby and Rails

- **The pg gem 1.7.0** ([connection.rb](https://github.com/ged/ruby-pg/blob/v1.7.0/lib/pg/connection.rb))
  takes `DATABASE_URL` and `DATABASE_READ_URL` unchanged. libpq chooses the
  server, and the gem tries the servers in turn, each for
  `connect_timeout`. The pg gem's Linux and macOS builds bundle libpq.
  The tested pg 1.7.0 build used libpq 18.
- **Rails 8.1.4 cannot parse `DATABASE_URL` or `DATABASE_READ_URL`.**
  Active Record is Rails' database interface, which uses the pg driver.
  Active Record reads `DATABASE_URL` automatically while loading, with
  Ruby's older URL parser. Because Ruby's older parser refuses a server
  list, the app stops at boot regardless of `config/database.yml`.
  The error is
  `URI::InvalidURIError: the scheme postgresql does not accept registry part`
  ([connection_url_resolver.rb](https://github.com/rails/rails/blob/v8.1.4/activerecord/lib/active_record/database_configurations/connection_url_resolver.rb)).

  Active Record does read libpq's other URL form, which holds every part
  as a setting after the `?`. Active Record passes `host: "db01,db02"`,
  `port`, `target_session_attrs`, and `connect_timeout` to libpq unchanged.
  So the app rewrites `DATABASE_URL` and `DATABASE_READ_URL` with every
  part after the `?` before Rails loads.
  Put the conversion in `config/boot.rb`, after `require "bundler/setup"`:

  ```ruby
  require "pg"
  require "uri"
  # Rails' URL parser refuses a URL that lists several database servers, and
  # Active Record reads DATABASE_URL by itself when it loads. libpq, inside
  # the pg gem, reads the stack's URL; this rewrites it into libpq's other URL
  # form, with every part after the ?, which Rails reads.
  %w[DATABASE_URL DATABASE_READ_URL].each do |env_var|
    next unless ENV[env_var]&.include?(",")
    rails_names = { "dbname" => "database", "user" => "username" }
    settings = PG::Connection.conninfo_parse(ENV[env_var]).filter_map do |option|
      [rails_names.fetch(option[:keyword], option[:keyword]), option[:val]] if option[:val]
    end
    ENV[env_var] = "postgresql:///?#{URI.encode_www_form(settings)}"
  end
  ```

  `config/database.yml`, where `primary` takes `DATABASE_URL` from Rails
  itself:

  ```yaml
  production:
    primary:
      adapter: postgresql
    primary_replica:
      url: <%= ENV["DATABASE_READ_URL"] %>
      replica: true
  ```

  and `connects_to database: { writing: :primary, reading: :primary_replica }`
  in `ApplicationRecord`. Rails reads from the replica inside
  `connected_to(role: :reading)`, or with its automatic role switching,
  which reads from the primary for a moment after the app's own write
  ([Rails' guide](https://guides.rubyonrails.org/active_record_multiple_databases.html)).
- **After a failover:** one write raised `ActiveRecord::ConnectionFailed`,
  then Rails reconnected and wrote to the new primary, with no restart.
- **TCP keepalive:** libpq enables keepalive with the app host's timing.
  The pg gem keeps TCP keepalive enabled for each server the gem tries.
  Rails passes libpq's keywords through. The app sets nothing.

### Python and Django

- **psycopg 3.3.6 and psycopg2 2.9.13** take `DATABASE_URL` and
  `DATABASE_READ_URL` unchanged.
  libpq chooses the server, each for `connect_timeout` (psycopg 3 tries the
  servers in turn itself, with at least 2 seconds each:
  [connection.py](https://github.com/psycopg/psycopg/blob/3.3.6/psycopg/psycopg/connection.py)).
- **Django 6.1.2 doesn't read `DATABASE_URL` itself.**
  [django-environ](https://github.com/joke2k/django-environ) 0.14.0 reads
  the stack's URL right: `HOST` `"db01,db02"`, `PORT` `"5432,5432"`, and
  `target_session_attrs` and `connect_timeout` in `OPTIONS`, which Django
  hands to the driver unchanged
  ([base.py](https://github.com/django/django/blob/6.1.2/django/db/backends/postgresql/base.py)).
  dj-database-url 3.1.2 refuses the stack's multi-server URL with
  `ParseError`, from Python's own URL parser. So an app using
  dj-database-url moves to django-environ:

  ```python
  import environ
  env = environ.Env()
  DATABASES = {
      "default": env.db_url("DATABASE_URL"),
      "replica": env.db_url("DATABASE_READ_URL"),
  }
  DATABASE_ROUTERS = ["shop.db_router.ReadReplicaRouter"]

  # shop/db_router.py: reads that may be a moment behind go to the replica
  class ReadReplicaRouter:
      def db_for_read(self, model, **hints): return "replica"
      def db_for_write(self, model, **hints): return "default"
      def allow_relation(self, obj1, obj2, **hints): return True
      def allow_migrate(self, db, app_label, model_name=None, **hints): return db == "default"
  ```

  A read that must see the app's own latest write names the primary:
  `Model.objects.using("default")`.
- **After a failover:** a few requests failed while no server was the
  primary, then Django wrote to the new primary, with no restart, with
  `CONN_MAX_AGE` 600 and with Django's own pool (`OPTIONS["pool"] = True`).
- **TCP keepalive:** on, with the server's timing, from libpq, in psycopg 3
  for each server it tries and in psycopg2. The app sets nothing.

### PHP and Laravel

- **pdo_pgsql** hands a data source name (DSN) to libpq. A DSN is a
  connection string describing the database connection. pdo_pgsql uses
  libpq's keyword form, including `target_session_attrs`, rather than a URL:
  `pgsql:host=db01,db02;port=5432,5432;dbname=shop;target_session_attrs=read-write`.
  pdo_pgsql ignores `connect_timeout` in the DSN, because pdo_pgsql adds a
  timeout from `PDO::ATTR_TIMEOUT`. The default is 30 seconds.
  The app sets `PDO::ATTR_TIMEOUT => 3`, which applies to each server
  ([pgsql_driver.c](https://github.com/php/php-src/blob/PHP-8.4/ext/pdo_pgsql/pgsql_driver.c)).
  A persistent connection (`PDO::ATTR_PERSISTENT`) that broke connects
  again through the list by itself.
- **Laravel 12 and 13 can't take the URL.** Laravel's URL parser reads the
  stack's URL wrong without an error. Laravel connects only to the last
  server listed, whether the last server is a primary or a standby.
  Laravel's Postgres connector leaves
  `target_session_attrs` out of the DSN
  ([PostgresConnector.php](https://github.com/laravel/framework/blob/13.x/src/Illuminate/Database/Connectors/PostgresConnector.php)).
  So `DB_URL` stays unset. App code in `config/database.php` converts
  `DATABASE_URL` and `DATABASE_READ_URL` into Laravel's connection settings.
  A connector of the app's adds `target_session_attrs`. In
  `config/database.php`:

  ```php
  // The parts of one of the stack's database URLs, which list every
  // database server: Laravel's own URL parser reads them wrong.
  function stack_database_settings(string $databaseUrl): array
  {
      if (!preg_match('#^postgres(?:ql)?://([^:@/]+):([^@/]*)@([^/?]+)/([^/?]+)\?(.*)$#', $databaseUrl, $parts)) {
          throw new RuntimeException('The database URL must look like postgresql://USER:PASSWORD@db01:5432,db02:5432/DATABASE?target_session_attrs=read-write&connect_timeout=3');
      }
      [, $user, $password, $serverList, $database, $query] = $parts;
      parse_str($query, $settings);
      $servers = array_map(fn ($server) => explode(':', $server), explode(',', $serverList));
      return [
          'host' => implode(',', array_column($servers, 0)),
          'port' => implode(',', array_column($servers, 1)),
          'database' => urldecode($database),
          'username' => urldecode($user),
          'password' => urldecode($password),
          'target_session_attrs' => $settings['target_session_attrs'],
      ];
  }

  // in 'connections':
  'pgsql' => [
      'driver' => 'pgsql',
      'write' => stack_database_settings(env('DATABASE_URL')),
      'read' => stack_database_settings(env('DATABASE_READ_URL')),
      'options' => [PDO::ATTR_TIMEOUT => 3],
  ],
  ```

  and the connector, bound in `AppServiceProvider::register()` with
  `$this->app->bind('db.connector.pgsql', StackPostgresConnector::class);`:

  ```php
  // Adds target_session_attrs to the DSN, which Laravel's own Postgres
  // connector leaves out.
  class StackPostgresConnector extends \Illuminate\Database\Connectors\PostgresConnector
  {
      protected function getDsn(array $config)
      {
          $dsn = parent::getDsn($config);
          if (isset($config['target_session_attrs'])) {
              $dsn .= ";target_session_attrs={$config['target_session_attrs']}";
          }
          return $dsn;
      }
  }
  ```

  With `stack_database_settings`, the `pgsql` connection settings, and
  `StackPostgresConnector`, writes reached the primary and reads reached
  the standby. The test also passed with a refused server listed first,
  using Laravel's database package, illuminate/database 13.39.0.
  The URL-conversion function was tested separately, rather than through
  Laravel's configuration loading.
- **TCP keepalive:** on, with the server's timing, from libpq, with and
  without Laravel. The app sets nothing.

### Go

- **pgx 5.11.0** takes `DATABASE_URL` and `DATABASE_READ_URL` unchanged,
  through `pgxpool.New`
  and through `database/sql` with its driver
  (`sql.Open("pgx", os.Getenv("DATABASE_URL"))`, with
  `_ "github.com/jackc/pgx/v5/stdlib"`). pgx asks each new connection with
  a query: `show transaction_read_only` for `read-write`,
  `select pg_is_in_recovery()` for `prefer-standby`
  ([pgconn's ParseConfig](https://pkg.go.dev/github.com/jackc/pgx/v5@v5.11.0/pgconn#ParseConfig)).
  `connect_timeout` applies to each server. pgx 5.11.0 needs Go 1.25.
  The stack's reference app uses pgxpool with the unchanged database URLs.
- **lib/pq** 1.12.3 cannot take `DATABASE_URL` or `DATABASE_READ_URL`:
  lib/pq reads `db01:5432,db02:5432` as wrong host names.
  lib/pq wants TLS unless told otherwise. With `prefer-standby`, lib/pq
  never returns when no server answers. An app on lib/pq
  moves to pgx's `database/sql` driver, a change of its import and its
  driver's name.
- **After a failover:** a few errors while no server was the primary, then
  writes reached the new primary, with no restart.
- **TCP keepalive:** pgx enables keepalive with Go's timing. Go waits
  15 seconds before the first probe, then 15 seconds between probes.
  Go sends 9 probes, about 150 seconds in all, whatever the app host's
  settings
  ([config.go](https://github.com/jackc/pgx/blob/v5.11.0/pgconn/config.go#L1085-L1088)).
  So the app gives pgx a dialer that leaves the timing to the server:

  ```go
  config, err := pgxpool.ParseConfig(os.Getenv("DATABASE_URL"))
  if err != nil {
  	return err
  }
  dialer := &net.Dialer{
  	Timeout: config.ConnConfig.ConnectTimeout, // connect_timeout, as pgx's own dialer has it
  	// -1: the server's own keepalive timing (net.ipv4.tcp_keepalive_*)
  	KeepAliveConfig: net.KeepAliveConfig{Enable: true, Idle: -1, Interval: -1, Count: -1},
  }
  config.ConnConfig.DialFunc = dialer.DialContext
  pool, err := pgxpool.NewWithConfig(ctx, config)
  ```

  For a single connection, use the `net.Dialer` shown above as `DialFunc`
  on `pgx.ParseConfig`'s result, with `Timeout: config.ConnectTimeout`.
  With the database server silenced, a query waiting for an answer ended
  after 153.6 seconds with pgx's default dialer. The query ended after
  60.9 seconds with the `net.Dialer` configured above.
  Never put libpq's keepalive keywords in a URL for pgx: it sends them to
  Postgres, which refuses the connection (`unrecognized configuration
  parameter "keepalives_idle"`). The reference app keeps pgx's default
  dialer, because the reference app's 2 to 5 seconds' limit on each
  request's queries already ends a wait for a silent database server.

### Java

- **pgjdbc 42.7.14** ([ConnectionFactoryImpl.java](https://github.com/pgjdbc/pgjdbc/blob/REL42.7.14/pgjdbc/src/main/java/org/postgresql/core/v3/ConnectionFactoryImpl.java),
  [its docs](https://jdbc.postgresql.org/documentation/use/)) takes
  several servers and chooses among them, but only in a JDBC URL.
  JDBC is Java's database interface. A JDBC URL starts with
  `jdbc:postgresql://`. pgjdbc uses different setting names from the
  stack's URL. pgjdbc uses `targetServerType=primary` for writes and
  `targetServerType=preferSecondary` for reads that may be a moment behind.
  The timeout setting is `connectTimeout`. The stack's URL fails as it is (`No
  suitable driver`), and with only `jdbc:` added it's read wrong, without
  an error, and connects to the first server listed. Spring Boot's
  `spring.datasource.url` is a JDBC URL that HikariCP hands to pgjdbc
  unchanged. So the app builds the JDBC URL from each setting, with a few
  lines:

  ```java
  record JdbcSettings(String url, String username, String password) {}

  // The stack's DATABASE_URL or DATABASE_READ_URL, which lists every database
  // server, as pgjdbc's JDBC URL, user name, and password.
  static JdbcSettings jdbcSettingsFromStackUrl(String stackUrl) {
    String rest = stackUrl.substring(stackUrl.indexOf("://") + 3);
    int at = rest.lastIndexOf('@');
    String[] userAndPassword = rest.substring(0, at).split(":", 2);
    String[] serversDatabaseAndSettings = rest.substring(at + 1).split("\\?", 2);   // "db01:5432,db02:5432/shop", the settings
    Map<String, String> settings = new HashMap<>();
    for (String setting : serversDatabaseAndSettings[1].split("&")) {
      String[] nameAndValue = setting.split("=", 2);
      settings.put(nameAndValue[0], nameAndValue[1]);
    }
    String targetServerType = switch (settings.get("target_session_attrs")) {
      case "read-write" -> "primary";
      case "prefer-standby" -> "preferSecondary";
      default -> throw new IllegalArgumentException("unexpected target_session_attrs: " + settings.get("target_session_attrs"));
    };
    return new JdbcSettings(
        "jdbc:postgresql://" + serversDatabaseAndSettings[0] + "?targetServerType=" + targetServerType
            + "&connectTimeout=" + settings.get("connect_timeout") + "&loadBalanceHosts=true&tcpKeepAlive=true",
        URLDecoder.decode(userAndPassword[0], StandardCharsets.UTF_8),
        URLDecoder.decode(userAndPassword[1], StandardCharsets.UTF_8));
  }
  ```

  `jdbcSettingsFromStackUrl` converts the example `DATABASE_URL` to
  `jdbc:postgresql://db01:5432,db02:5432/shop?targetServerType=primary&connectTimeout=3&loadBalanceHosts=true&tcpKeepAlive=true`.
  For writes, a Spring Boot app sets the system properties
  `spring.datasource.url`,
  `spring.datasource.username`, and `spring.datasource.password` from
  `jdbcSettingsFromStackUrl(System.getenv("DATABASE_URL"))` in `main()`,
  before `SpringApplication.run`. For reads, an app with a separate read
  pool makes a `HikariDataSource` bean from `DATABASE_READ_URL`.
  The Spring Boot setup was not run.
- **Why `loadBalanceHosts=true`:** since 42.7.11, `connectTimeout` is one
  limit for all the servers of an attempt together, not for each, and a
  server after the limit gets 1 ms. A switched-off server answers nothing.
  When listed first, a switched-off server takes the whole 3 seconds.
  The next server's 1 ms can be too short over a network.
  pgjdbc then tries the URL's server order again.

  With `loadBalanceHosts=true`, pgjdbc tries
  the servers in a random order on each attempt. pgjdbc still chooses the
  primary for writes and prefers a standby for reads. pgjdbc skips a server
  that failed for the next 10 seconds (`hostRecheckSeconds`). With a silent
  server listed first, one connection took 3 seconds and the next
  connections took a few milliseconds, on one machine.
  The 1 ms on a network was not measured.
- **TCP keepalive:** off by default. `tcpKeepAlive=true` in the URL above
  enables TCP keepalive with the app host's timing.
  HikariCP takes the JDBC URL unchanged
  ([PGProperty.java](https://github.com/pgjdbc/pgjdbc/blob/REL42.7.14/pgjdbc/src/main/java/org/postgresql/PGProperty.java#L908-L914)).
  HikariCP's own `keepaliveTime` is a check of idle connections, not TCP
  keepalive.
- **How pgjdbc decides:** pgjdbc treats a server that reported
  `in_hot_standby=on` at login as a standby. For servers that did not
  report `in_hot_standby=on`, pgjdbc asks `show transaction_read_only`.
- **After a failover,** with HikariCP 7.1.0: one write failed, and the
  next, 265 ms later, went to the new primary, with no restart. pgjdbc
  remembers each server's state for 10 seconds, in the whole program, which
  cost one more failed attempt.

### .NET

- **Npgsql 10.0.3** ([failover and load balancing](https://www.npgsql.org/doc/failover-and-load-balancing.html),
  [NpgsqlMultiHostDataSource.cs](https://github.com/npgsql/npgsql/blob/v10.0.3/src/Npgsql/NpgsqlMultiHostDataSource.cs))
  takes several servers and libpq's names for the choice, `read-write` and
  `prefer-standby`, but only in its connection string, never a URL: the
  stack's URL throws an error that repeats the password. So the app builds
  the connection string from `DATABASE_URL`:

  ```csharp
  // The stack's DATABASE_URL, which lists every database server, as an Npgsql
  // connection string: Host=db01:5432,db02:5432;Database=shop;...;Target Session Attributes=read-write;Timeout=3
  static string NpgsqlConnectionStringFromStackUrl(string stackUrl)
  {
      var rest = stackUrl[(stackUrl.IndexOf("://") + 3)..];
      var at = rest.LastIndexOf('@');
      var userAndPassword = rest[..at].Split(':', 2);
      var serversDatabaseAndSettings = rest[(at + 1)..].Split('?', 2);
      var serversAndDatabase = serversDatabaseAndSettings[0].Split('/', 2);
      var settings = serversDatabaseAndSettings[1].Split('&').Select(s => s.Split('=', 2)).ToDictionary(s => s[0], s => s[1]);
      return new NpgsqlConnectionStringBuilder {
          Host = serversAndDatabase[0], Database = serversAndDatabase[1],
          Username = Uri.UnescapeDataString(userAndPassword[0]), Password = Uri.UnescapeDataString(userAndPassword[1]),
          TargetSessionAttributes = settings["target_session_attrs"], Timeout = int.Parse(settings["connect_timeout"]),
          TcpKeepAlive = true,   // TCP keepalive, off by default, with the server's timing
      }.ConnectionString;
  }
  ```

  The app makes one multi-host data source, then a view of the data source
  for writes and a view for reads, so the two views share what Npgsql
  knows of each server:

  ```csharp
  var databaseServers = new NpgsqlDataSourceBuilder(NpgsqlConnectionStringFromStackUrl(Environment.GetEnvironmentVariable("DATABASE_URL")!)).BuildMultiHost();
  var forWrites = databaseServers.WithTargetSession(TargetSessionAttributes.ReadWrite);
  var forReads = databaseServers.WithTargetSession(TargetSessionAttributes.PreferStandby);
  ```

  Entity Framework Core's provider takes such a data source:
  `options.UseNpgsql(forWrites)`. The Entity Framework Core provider setup
  was not run because the provider needs .NET 10.
- **Why one data source:** Npgsql remembers each server's state for
  `Host Recheck Seconds`, 10 by default. With separate data sources from
  `DATABASE_URL` and `DATABASE_READ_URL`, the write data source still
  treated the new primary as a standby after a switchover.
  Writes failed for 5.4 seconds. With one shared multi-host data source,
  a single write failed. Reads returned to the new standby automatically
  about 10 seconds later.
- **How Npgsql decides:** from what the server reports at login
  (`in_hot_standby`, `default_transaction_read_only`), and with a query
  only when they're missing. `Timeout` applies to each server, login
  included.
- **TCP keepalive:** off by default. `TcpKeepAlive = true` above enables
  TCP keepalive with the app host's timing
  ([NpgsqlConnectionStringBuilder.cs](https://github.com/npgsql/npgsql/blob/v10.0.3/src/Npgsql/NpgsqlConnectionStringBuilder.cs#L1086-L1166)).
  Npgsql's `Keepalive` setting is a query it sends, not TCP keepalive.

### Elixir and Phoenix

- **Ecto 3.14.2 can't take the URL**
  ([supervisor.ex](https://github.com/elixir-ecto/ecto/blob/v3.14.2/lib/ecto/repo/supervisor.ex)).
  Ecto keeps only the first server, and hands `connect_timeout` on as text.
  So a repo started with `url:` set to the stack's URL never connects
  (`ArgumentError`). Without `connect_timeout` in the URL, Ecto connects to
  the first server listed, whether the server is a primary or a standby.
- **Postgrex 0.22.4** tries several servers in turn (`endpoints`) and
  chooses the primary (`target_server_type: :primary`), asking each
  `show transaction_read_only`
  ([protocol.ex](https://github.com/elixir-ecto/postgrex/blob/v0.22.4/lib/postgrex/protocol.ex)).
  So `config/runtime.exs` takes the URL's parts in place of Phoenix's
  `url: database_url`. The `url: database_url` configuration would override
  the connection settings built from the URL's parts:

  ```elixir
  # The repo's settings from one of the stack's database URLs, which list
  # every database server: Ecto's own URL parser keeps only the first.
  stack_database_options = fn env_var ->
    "postgresql://" <> rest = System.fetch_env!(env_var)
    [authority, path_and_query] = String.split(rest, "/", parts: 2)
    [userinfo, servers] = String.split(authority, "@", parts: 2)
    [username, password] = String.split(userinfo, ":", parts: 2)
    [database, query] = String.split(path_and_query, "?", parts: 2)
    settings = URI.decode_query(query)
    timeout_ms = String.to_integer(settings["connect_timeout"]) * 1000
    [
      username: URI.decode(username),
      password: URI.decode(password),
      database: database,
      endpoints:
        for server <- String.split(servers, ",") do
          [host, port] = String.split(server, ":")
          {host, String.to_integer(port)}
        end,
      connect_timeout: timeout_ms,
      handshake_timeout: timeout_ms,
      # TCP keepalive, off by default, with the server's timing
      socket_options: [keepalive: true]
    ]
  end

  config :shop, Shop.Repo, stack_database_options.("DATABASE_URL") ++ [target_server_type: :primary, pool_size: 10]
  ```
- **Postgrex has no setting to prefer a standby with fallback to the
  primary.** Postgrex's `:secondary` refuses to connect when no standby
  answers, as with one database server. Postgrex's `:any` takes the first
  server listed.
  DBConnection manages Postgrex connections for the Ecto repo.
  An app reads through the write repo, or builds the
  [small helper](#a-driver-that-cant-a-small-helper-of-the-apps-own) for a
  read repo. Put the helper in the `:configure` function that DBConnection
  runs before each connect
  ([DBConnection.start_link](https://hexdocs.pm/db_connection/DBConnection.html#start_link/2)).
- **After a failover:** one write failed, and the next, half a second
  later, was on the new primary, with no restart.
- **TCP keepalive:** off by default. `socket_options: [keepalive: true]`
  above enables TCP keepalive with the app host's timing
  ([protocol.ex](https://github.com/elixir-ecto/postgrex/blob/v0.22.4/lib/postgrex/protocol.ex#L85)).

### Rust

- **tokio-postgres 0.7.18** ([Config](https://docs.rs/tokio-postgres/0.7.18/tokio_postgres/config/struct.Config.html)),
  and deadpool-postgres and bb8-postgres, which read the URL with it, take
  `DATABASE_URL` as it is, asking each new connection
  `SHOW transaction_read_only`. tokio-postgres, deadpool-postgres, and
  bb8-postgres refuse `DATABASE_READ_URL`. tokio-postgres accepts only
  `any`, `read-write`, and `read-only`, with no
  `prefer-standby`. An app reads through its write pool, or builds the
  [small helper](#a-driver-that-cant-a-small-helper-of-the-apps-own) in a
  pool manager of its own (deadpool's `Manager`, bb8's
  `ManageConnection`). tokio-postgres's `connect_timeout` limits only each
  server's TCP connection, not login. A server that accepts connections
  and never answers holds a new connection until the pool's own timeout.
  **TCP keepalive** is on in tokio-postgres, including through
  deadpool-postgres and bb8-postgres. tokio-postgres waits 2 hours before
  the first probe by default. Setting `keepalives_idle` to 0 leaves the
  2-hour wait unchanged. So the app sets `keepalives_idle` to 30 seconds.
  The app leaves the probe interval and count to the app host's operating
  system. After
  `let mut config: tokio_postgres::Config = std::env::var("DATABASE_URL")?.parse()?;`,
  `config.keepalives_idle(std::time::Duration::from_secs(30));`, or
  deadpool's `keepalives_idle: Some(Duration::from_secs(30))`
  ([config.rs](https://github.com/rust-postgres/rust-postgres/blob/tokio-postgres-v0.7.18/tokio-postgres/src/config.rs#L262-L268)).
  tokio-postgres's setting names differ from libpq's: the probe count is
  `keepalives_retries`, and `tcp_user_timeout` is in seconds.
- **diesel 2.3.14** ([PgConnection](https://docs.rs/diesel/2.3.14/diesel/pg/struct.PgConnection.html))
  hands the URL to libpq, so diesel takes `DATABASE_URL` and
  `DATABASE_READ_URL` unchanged, as Ruby's and Python's drivers do.
  TCP keepalive is on at the app host's timing, so the app sets nothing.
  diesel-async provides asynchronous database access for diesel apps, but
  uses tokio-postgres instead of libpq. Follow the tokio-postgres URL and
  keepalive instructions for diesel-async.
- **sqlx 0.9.0 can't:** it takes one server only, refuses the stack's URL
  (`invalid port number`), and ignores `target_session_attrs`
  ([PgConnectOptions](https://docs.rs/sqlx/0.9.0/sqlx/postgres/struct.PgConnectOptions.html)).
  To follow a failover, an app using sqlx moves database access to
  tokio-postgres or diesel, or implements a helper in the app.
  If the app keeps sqlx, the helper finds the primary as the
  [small helper](#a-driver-that-cant-a-small-helper-of-the-apps-own) does.
  When the sqlx pool's connections fail, the helper makes a new pool
  connected to the primary the helper found.
  sqlx cannot turn TCP keepalive on at all
  ([socket/mod.rs](https://github.com/transact-rs/sqlx/blob/v0.9.0/sqlx-core/src/net/socket/mod.rs#L184-L203)).
  So a sqlx app gives queries a time limit. Without a query time limit,
  a query that a dead server had received waits forever.
  A query sent after the database server
  died still ends after about 51 seconds, through the app host's
  `tcp_retries2`.
- **After a failover:** the next connection of deadpool, bb8, and diesel's
  r2d2 pool reached the new primary, with no restart. r2d2 is a connection
  pool that a diesel app can use to reuse database connections.

## Node.js: the stack's file

Node's common driver, node-postgres (`pg` 8), can't read a URL that lists
several servers (pg 8.23.1 throws `Invalid URL`), and it has no
`target_session_attrs`. So the stack gives a Node app a small file that
adds support for multi-server URLs and `target_session_attrs` to pg, in
[`node/`](node):

| File | Purpose | Copied into the app |
| --- | --- | --- |
| [`pg_with_multiple_database_servers.mjs`](node/pg_with_multiple_database_servers.mjs) | Makes the app's pools from `DATABASE_URL` and `DATABASE_READ_URL`. Each new connection asks servers in order whether the servers are standbys. For writes, connects to the first primary that answers. For reads, tries servers for a standby before falling back to the first server that answered. | Always, unchanged |
| [`run_with_the_primary_database_url.mjs`](node/run_with_the_primary_database_url.mjs) | Runs a migration tool that reads `DATABASE_URL` itself, such as Prisma's CLI or drizzle-kit, with `DATABASE_URL` narrowed to the primary alone | When the app has such a tool, unchanged |
| [`check_database_failover.mjs`](node/check_database_failover.mjs) | Checks that a switchover moves the app's writes and reads. Runs during `switch_database_primary` (the systems repository's [test_a_nodejs_app_during_a_database_switchover.md](../systems_repository_template/operating_procedures/test_a_nodejs_app_during_a_database_switchover.md#a-node-app-through-a-switchover), "A Node app through a switchover") | Never |

`pg_with_multiple_database_servers.mjs` and
`run_with_the_primary_database_url.mjs` are ES modules, the JavaScript
module format that uses `import` and `export`. CommonJS is the module
format that uses `require()` and `module.exports`.

A CommonJS app on Node 22.12 or later loads
`pg_with_multiple_database_servers.mjs` unchanged with `require()`.
The app runs `run_with_the_primary_database_url.mjs` with `node`.
A TypeScript app keeps `pg_with_multiple_database_servers.mjs` and
`run_with_the_primary_database_url.mjs` as `.mjs` files.
The TypeScript app adds a declaration file when types are wanted.
Keep the code in `pg_with_multiple_database_servers.mjs` and
`run_with_the_primary_database_url.mjs` unchanged, so a new stack version
can replace the copied files.

### The app's pools

The app makes every pool with functions from
`pg_with_multiple_database_servers.mjs`. Use `process.env.DATABASE_URL`
for writes, or `process.env.DATABASE_READ_URL` for a second pool for reads.
An ORM maps app objects to database queries and uses a driver and
connection pool to send the queries. Never give `DATABASE_URL` or
`DATABASE_READ_URL` directly to pg, an ORM, or a tool as a connection
string. The parsers in pg, the ORMs, and the tools refuse multi-server URLs
or read the URLs incorrectly.

- `poolForDatabaseUrl(url, poolSettings)`: a `pg.Pool`. `poolSettings` are
  pg.Pool's own, such as `max`.
- `clientClassForDatabaseUrl(url)`: a `pg.Client` class, for an ORM that
  takes one.
- `pgModuleForDatabaseUrl(url)`: the pg module with the `Client` class from
  `clientClassForDatabaseUrl(url)` and a `Pool` that uses the client class.
  Use the module for an ORM that takes the pg module itself.
- `databaseNameInDatabaseUrl(url)`: the database's name, for an ORM that
  wants the database name beside the client class or pg module.

`pg_with_multiple_database_servers.mjs` rejects a URL with an unsupported
setting, such as `sslmode`, rather than silently ignoring the setting.
`pg_with_multiple_database_servers.mjs` applies
`target_session_attrs` (`read-write`, `prefer-standby`, or `any`, which a
URL without the setting gets) and `connect_timeout`.
`pg_with_multiple_database_servers.mjs` needs no additional settings.
Errors from `pg_with_multiple_database_servers.mjs` never contain the
password. `connect_timeout`
limits each connection, for the question to each server and for the app's
connection; the question itself, `select pg_is_in_recovery()`, has no
timeout of its own. pg.Pool's own
`connectionTimeoutMillis` limits only how long a request waits for a
connection. `pg_with_multiple_database_servers.mjs` enables TCP keepalive
with the app host's timing.

Each common ORM runs on pg and uses
`pg_with_multiple_database_servers.mjs` as shown below. Each line below
reached the primary with the standby listed first, and Prisma's second
client reached the standby, with the versions in the table, on Node
24.22.1, with one copy of pg 8.23.1:

```js
import { poolForDatabaseUrl, clientClassForDatabaseUrl, pgModuleForDatabaseUrl, databaseNameInDatabaseUrl } from './pg_with_multiple_database_servers.mjs'
const writeUrl = process.env.DATABASE_URL
const readUrl = process.env.DATABASE_READ_URL
const databaseName = databaseNameInDatabaseUrl(writeUrl)

// Prisma 7, through its driver adapter for pg. prisma.config.ts keeps
// datasource: { url: env('DATABASE_URL') } for the CLI, which runs through
// run_with_the_primary_database_url.mjs.
import { PrismaClient } from './generated/prisma/client.js'
import { PrismaPg } from '@prisma/adapter-pg'
export const prisma = new PrismaClient({ adapter: new PrismaPg(poolForDatabaseUrl(writeUrl, { max: 10 })) })
export const prismaForReads = new PrismaClient({ adapter: new PrismaPg(poolForDatabaseUrl(readUrl, { max: 10 })) })

// Drizzle: drizzle-orm/node-postgres, never drizzle-orm/postgres-js
import { drizzle } from 'drizzle-orm/node-postgres'
export const db = drizzle({ client: poolForDatabaseUrl(writeUrl) })

// Kysely
import { Kysely, PostgresDialect } from 'kysely'
export const kysely = new Kysely({ dialect: new PostgresDialect({ pool: poolForDatabaseUrl(writeUrl) }) })

// Knex: its pg dialect, with the file's pg module; never a connection string
import knex from 'knex'
import PostgresDialect from 'knex/lib/dialects/postgres/index.js'
const pgForWrites = pgModuleForDatabaseUrl(writeUrl)
class PostgresDialectForWrites extends PostgresDialect { _driver() { return pgForWrites } }
export const knexDb = knex({ client: PostgresDialectForWrites, connection: {} })

// Sequelize 6: never the URL
import { Sequelize } from 'sequelize'
export const sequelize = new Sequelize({ dialect: 'postgres', dialectModule: pgModuleForDatabaseUrl(writeUrl), database: databaseName })

// TypeORM: no url
import { DataSource } from 'typeorm'
export const dataSource = new DataSource({ type: 'postgres', database: databaseName, extra: { Client: clientClassForDatabaseUrl(writeUrl) } /* entities, ... */ })

// MikroORM 7: no clientUrl
import { MikroORM } from '@mikro-orm/postgresql'
export const orm = await MikroORM.init({ dbName: databaseName, driverOptions: { Client: clientClassForDatabaseUrl(writeUrl) } /* entities, ... */ })
```

| ORM, version checked | What to watch |
| --- | --- |
| Prisma 7.10.1, `@prisma/adapter-pg` 7.10.1 | Prisma 7 connects only through a driver adapter ([upgrading to Prisma 7](https://www.prisma.io/docs/orm/more/upgrade-guides/upgrading-versions/upgrading-to-prisma-7)); Prisma 6's own engine can't take the stack's URL, so a Prisma 6 app moves to 7 first. Prisma's own URL parser refuses a list of servers (`P1013 ... invalid port number`, [issue 13493](https://github.com/prisma/orm/issues/13493)), so its CLI runs through `run_with_the_primary_database_url.mjs`. The Prisma adapter takes a pool only from the adapter's own copy of pg: `npm ls pg` must show one copy. |
| Drizzle 0.45.4 | An app on `drizzle-orm/postgres-js` moves to `drizzle-orm/node-postgres`, which has the same query API. drizzle-kit runs through `run_with_the_primary_database_url.mjs` with `dbCredentials: { url: process.env.DATABASE_URL }`, not host settings, which drop `target_session_attrs` ([issue 6229](https://github.com/drizzle-team/drizzle-orm/issues/6229)). |
| Kysely 0.29.7 | Kysely's `PostgresDialect` takes a pool from `pg_with_multiple_database_servers.mjs`. |
| Knex 3.3.0 | Never give it the URL string: its parser fails on it, and Knex then takes it for a SQLite file's name. |
| Sequelize 6.37.8 | Never give Sequelize the stack's URL: Sequelize's parser reads the database's name as `:5432,db02/shop`. Sequelize builds a pool from the pg module returned by `pgModuleForDatabaseUrl(url)`. |
| TypeORM 1.1.2 | Leave out `url`, which TypeORM hands to pg, which throws. Never install `pg-native`: TypeORM switches to it by itself when it's there. |
| MikroORM 7.2.5 | Leave out `clientUrl`, which MikroORM parses with `new URL()`. MikroORM 6 runs on Knex and takes the Knex way. |

A second pool, client class, or module made from `DATABASE_READ_URL`
serves reads, as Prisma's second client shows; the ORMs' own features for
read replicas, such as Prisma's `@prisma/extension-read-replicas`,
Drizzle's `withReplicas`, and TypeORM's `replication`, take such a second
client or database. Every ORM passes a read-only error (`25006`, "cannot
execute INSERT in a read-only transaction") to the app and retries
nothing: it shows when a connection stayed on a server that became a
standby, or when the app sends a write through `DATABASE_READ_URL`. The
stack's `pgbouncer` role ends a connection left on a new standby within
seconds by
restarting PgBouncer
([Through PgBouncer](#through-pgbouncer)).

### `pg_with_multiple_database_servers.mjs`: two `'error'` listeners

An `'error'` event that nothing listens to ends a Node process. Every
connection to the old primary ends in a failover, at once or once TCP
gives up ([When a database server dies](#when-a-database-server-dies)).
pg then emits `'error'` on the pool or on a connection held by the app.
`pg_with_multiple_database_servers.mjs` registers listeners on the pool
and on each connection:

- **On the pool, for idle connections:** the listener in
  `pg_with_multiple_database_servers.mjs` writes a
  warning, such as `An idle database connection to db01:5432 closed:
  terminating connection due to administrator command`.
  The pool drops the connection.
- **On each connection held by the app or an ORM,** such as in a
  transaction, the pool does not listen for errors.
  `pg_with_multiple_database_servers.mjs` supplies a connection listener
  that handles the error event without ending the process.
  The connection remains broken, so the next statement fails.
  The pool drops the broken connection after the app releases the
  connection. Without the connection listener, Drizzle 0.45 and Kysely
  0.29 ended the process in a transaction, as tested on 2026-10-28.

### Migrations

- **A tool that connects through the app's own settings,** such as Knex's,
  Sequelize's, TypeORM's, and MikroORM's, uses
  `pg_with_multiple_database_servers.mjs` through the app's settings, as
  the app does, and needs nothing more.
- **A tool that reads `DATABASE_URL` itself,** Prisma's CLI and
  drizzle-kit, runs through `run_with_the_primary_database_url.mjs`.
  `run_with_the_primary_database_url.mjs` finds the current primary and
  runs the migration tool with `DATABASE_URL` naming the primary alone.
  The stack's migration runner,
  `roles/app_server/files/run_app_migrations` in the systems repository,
  supplies `PGOPTIONS` (`-c lock_timeout=5s`) to the migration container.
  `run_with_the_primary_database_url.mjs` copies `PGOPTIONS` into the URL's
  `options`, because Prisma's CLI ignores `PGOPTIONS`.
  The app's `migration_command`, under `vars.apps.<app>` in the systems
  repository's `mmx_project_settings.yml`, then is, for example,
  `node run_with_the_primary_database_url.mjs npx prisma migrate deploy`.

### What the coding agent checks during the initial setup

1. `npm ls pg` lists one copy of `pg`, version 8.
2. Nothing else connects to the app's database: `npm ls pg-native` lists
   nothing, and the code uses no `postgres` (postgres.js),
   `drizzle-orm/postgres-js`, `kysely-postgres-js`, or Bun's `sql`.
3. The code reads `DATABASE_URL` and `DATABASE_READ_URL` only through the
   functions in `pg_with_multiple_database_servers.mjs`.
   Search the app's code for `DATABASE_URL`, `DATABASE_READ_URL`, and
   `connectionString`, `url:`, `clientUrl`, `new Sequelize(` with a
   string, and `knex({ connection: '`.
4. The ORM uses the pool, client class, or pg module shown for the app's
   ORM in [The app's pools](#the-apps-pools). Prisma is at version 7 with
   `@prisma/adapter-pg`.
5. A migration tool that reads `DATABASE_URL` itself runs through
   `run_with_the_primary_database_url.mjs` in the app's `migration_command`.
6. Node is 22.12 or later; Prisma 7 needs 20.19, 22.12, 24, or later.
7. On the servers, the app answers its health URL, and its logs show no
   "doesn't apply" or "No database server fits" error. The switchover
   itself is checked once `db02` exists (the systems repository's
   [test_a_nodejs_app_during_a_database_switchover.md](../systems_repository_template/operating_procedures/test_a_nodejs_app_during_a_database_switchover.md#a-node-app-through-a-switchover), "A Node app through a switchover").

### Why a file, and not another driver

Tested on 2026-10-28 with Postgres 18.6, a primary, a standby, and a
switchover in each direction, directly and through PgBouncer:

- **postgres.js** 3.4.9 reads the URL, but with `read-write` it connects
  writes to a standby: it checks only `default_transaction_read_only`,
  which a hot standby reports as `off`
  ([src/connection.js](https://github.com/porsager/postgres/blob/v3.4.9/src/connection.js#L790-L798)).
  With `prefer-standby` and no standby answering, a query remains pending
  forever ([issue 1174](https://github.com/porsager/postgres/issues/1174)).
  A server whose connect times out fails the query instead of moving on
  ([issue 988](https://github.com/porsager/postgres/issues/988)). Of the
  ORMs above, only Drizzle and Kysely can use postgres.js.
- **pg-native** 3.9.1, pg's binding to libpq, chooses right in every case,
  but ignores the per-query type parsers that Prisma's adapter and Drizzle
  rely on. pg-native needs a native build and connects with a blocking
  call in Node's thread pool. So a dead database server also stalls the app's
  file reads and DNS lookups during the database outage.
- **Bun's SQL** (Bun 1.4.4) leaves out `target_session_attrs` on purpose
  ([its docs](https://github.com/oven-sh/bun/blob/bun-v1.4.4/docs/runtime/sql.mdx))
  and can't parse a list of servers. A Bun app can run pg with
  `pg_with_multiple_database_servers.mjs`.
- **pg itself** may take several hosts one day
  ([pull request 3643](https://github.com/brianc/node-postgres/pull/3643),
  open since 2026-03); then the file can go, once pg also picks the
  primary for `read-write` and prefers a standby, falling back to the
  primary, for `prefer-standby`.

`pg_with_multiple_database_servers.mjs` uses only pg's public API: a
`Client` class that picks a server before connecting, and pg.Pool's
`Client` setting. A pg client connects once and cannot try a second
server. So `pg_with_multiple_database_servers.mjs` asks each server over a
separate short connection before opening the app's connection.

**Tests of `pg_with_multiple_database_servers.mjs`,** run only when
changing `pg_with_multiple_database_servers.mjs`: `npm ci`, then `npm test` in
`node/`, as the top of `node/database_failover.test.mjs` says.

## A driver that can't: a small helper of the app's own

When a driver cannot choose from a list of servers, the app needs a helper
like [`node/pg_with_multiple_database_servers.mjs`](node/pg_with_multiple_database_servers.mjs).
The helper runs in the app, where the driver or pool lets app code choose
the server for a new connection. For example, use a connection factory or
a hook that runs before each connect. The helper selects the server the
new connection will use.

Postgrex and tokio-postgres need a helper for reads that prefer a standby.
sqlx needs a helper for writes and reads.

The developer or coding agent implements the following behavior in the
app's helper:

1. **Read `DATABASE_URL` or `DATABASE_READ_URL` directly.** The servers are
   the part between `@` and `/`, separated by commas, each `host:port`.
   The settings follow the `?`.
   Many URL parsers refuse the list. Support `target_session_attrs` with
   `read-write` for `DATABASE_URL` and `prefer-standby` for
   `DATABASE_READ_URL`, and `connect_timeout` in seconds.
   Reject a URL with an unsupported setting and return an error, rather
   than silently ignoring the setting.
2. **Each time the pool opens a connection, never for a query,** try the
   servers in the URL's order, each for at most `connect_timeout` seconds,
   and ask each `select pg_is_in_recovery()`, which answers `true` on a
   standby.
3. **For `read-write`,** take the first server that answers `false`. **For
   `prefer-standby`,** remember the first server that answers, but continue
   looking for a standby. Take the first server that answers `true`.
   Only if no standby answers, use the first server that answered at all.
4. **When no server fits,** fail that connection with each server's reason
   (refused, timed out, a standby); the pool's next connection tries
   again.
5. **Leave open connections alone, with TCP keepalive on,** at the
   app host's timing. After a failover, the old primary's connections end,
   at once or once TCP gives up
   ([When a database server dies](#when-a-database-server-dies)), and the
   pool replaces them. Handle connection errors while a connection is
   idle in the pool and while the app holds the connection.
   Never let an unhandled connection error end the app's process.

Ask Postgres with the query, never trust what a server reported at login:
through PgBouncer, that report can be what its Postgres was before the
failover. The helper's tests start a primary and a standby on one machine,
as the tests of `node/pg_with_multiple_database_servers.mjs` do in
`node/database_failover.test.mjs`.

## What finding the server costs

A driver finds the server once each time a pool opens a connection, never
for a query, as libpq and pgx do when they connect. A query on an open
connection costs the same with `pg_with_multiple_database_servers.mjs`
as with plain pg.

On Postgres 14 and later, libpq decides from the database server's role
report at login. pgx asks the database server's role with a query on the
new connection. `pg_with_multiple_database_servers.mjs` asks each
database server over a separate short connection, because a pg client
connects only once. So each server asked by
`pg_with_multiple_database_servers.mjs` costs about one extra login.

SCRAM is the password-authentication method used by the stack's Postgres
servers. The measurements
include password authentication, as on the stack's servers.

Measured on one machine (Apple M1 Max, Postgres 18.6, Node 23.11,
pg 8.23.1, password logins with SCRAM as on the stack's servers), each a
new connection that logs in and runs one query, the median of 300:

| New connection | Time |
| --- | --- |
| Plain pg, to the primary | 4.5 ms |
| `pg_with_multiple_database_servers.mjs`, `read-write`, the primary listed first: asks one server | 8.9 ms |
| `pg_with_multiple_database_servers.mjs`, `read-write`, the primary listed second, as after a failover: asks two servers | 14.0 ms |
| `pg_with_multiple_database_servers.mjs`, `prefer-standby`, the primary listed first: asks two servers | 13.4 ms |
| **A query on an open pooled connection,** plain pg and `pg_with_multiple_database_servers.mjs`, 20,000 queries | 65 µs and 61 µs |

Through a proxy that added a 10 ms round trip, a new connection took
51 ms with plain pg. Asking one server took 99 ms, and asking two took
148 to 150 ms. Each server asked added about one login, or 5 round trips.
Between servers in one location, a round trip takes well under a
millisecond. So asking each server is estimated to add a few milliseconds
to a new connection, but the estimate was not measured on servers.

pg.Pool opens connections when database requests need more connections
than the pool has available. New connections are needed at the app's
start, after a failover, and when traffic grows beyond the open connections.
The pool also closes connections after 10 idle seconds, so later requests
need new connections. A higher `idleTimeoutMillis` delays closing idle
connections. A `min` preserves a minimum number of connections from idle
closure. So a busy pool opens no new connections.

## Through PgBouncer

- **A driver that decides from what the server reports at login** hears
  PgBouncer's report of Postgres's role when PgBouncer first connected.
  libpq's drivers (Ruby's, Python's, PHP's, and diesel) and Npgsql decide
  from the role report at login. pgjdbc treats a standby reported by
  PgBouncer at login as a standby without querying Postgres's current role.
  The stack's `pgbouncer` role restarts PgBouncer whenever the local
  Postgres starts or changes role, so the login report is right again
  within seconds. Drivers that ask with a query reach Postgres itself
  through PgBouncer: pgx, Postgrex, tokio-postgres, and
  `pg_with_multiple_database_servers.mjs`.
- **Connections that were open** stay on a PgBouncer whose Postgres became
  a standby until PgBouncer restarts. The restart triggered by the
  Postgres start or role change closes existing client connections, and
  every driver's pool replaces the closed connections.

  Tests on 2026-10-28 omitted the PgBouncer restart after Postgres changed
  role. Writes through existing connections to PgBouncer in front of the
  new standby failed with the read-only error. A pool that discards a
  connection after an error opened a replacement connection to the new
  primary after one failed write. A pool kept failing when the app returned
  failed connections without reporting the error to the pool.
