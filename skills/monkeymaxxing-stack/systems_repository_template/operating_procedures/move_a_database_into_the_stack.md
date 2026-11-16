# Move a database into the Stack

**When:** an existing app and its database move into the Stack.

**What this page does:** move the app first, while the app still uses the old Postgres server over WireGuard.
Then logical replication copies table changes into the Stack's normal failover formation.
One switch command pauses writes, finishes the copy, and lets the apps reconnect without restarting containers.

This example moves `shop` from Postgres 15 into Postgres 17 on `db01`, with `db02` as its replica.

**Who acts:** you, the coding agent, prepare the Stack, change the
inventory, and run the copy and the switch from the systems desk. The
commands marked for the old server or the relay run as root on that
machine, through the team's own access to it: the Stack's inventory never
lists the old server. Only a person:

- announces the work in the team's chat, and agrees the maintenance window;
- saves the passwords in the Stack vault, in the person's own terminal;
- does the old provider's console work, such as a managed database's
  settings, its firewall rule, and destroying the relay, because no step
  calls the old provider's API from the desk.

## Find your situation

| The old database | Follow, in order |
| --- | --- |
| The team has not done this move before | [Rehearse the move first](#rehearse-the-move-first), then the row below that fits |
| Postgres that the team runs on its own server, or in a container | [Prepare the old server](#prepare-the-old-server), [Prepare the Stack and move the app](#prepare-the-stack-and-move-the-app), [Copy the database](#copy-the-database), [Switch and verify](#switch-and-verify) |
| A managed database without WireGuard access: RDS, Cloud SQL, or Azure | Steps 1, 2 and 9 of [Prepare the old server](#prepare-the-old-server) for the backup, the object inventory, the publication, the passwords and the grants; then [An old database behind a provider network](#an-old-database-behind-a-provider-network) in place of the old server's operating-system setup; then [Prepare the Stack and move the app](#prepare-the-stack-and-move-the-app), [Copy the database](#copy-the-database), and [Switch and verify](#switch-and-verify), with `through_relay: true` |

Read [An old database behind a provider network](#an-old-database-behind-a-provider-network) before preparing a managed move.
To practice first, read [Rehearse the move first](#rehearse-the-move-first).

## Before you start

- **Repeat the per-database commands for each distinct database** used by the apps under `database_moving_in.apps`.
  The switch makes only the moving databases read-only. Unlisted databases keep their existing defaults.
- **Choose a maintenance window** for enabling logical replication on the old cluster, which needs a restart.
- **Expect a short write pause.** The final write pause depends on replication lag and the amount of large-object data.
- **No schema migrations run during the copy,** because logical replication does not copy schema changes.
- **A table without a primary key** needs `REPLICA IDENTITY FULL` or a key before updates or deletes can replicate.
- **Large objects are copied at the switch,** because logical replication does not copy large objects.

## Rehearse the move first

A team that has not done this move before should rehearse it once, so the
real move holds no first-time steps. The rehearsal uses the same playbooks,
the same `database_moving_in` settings, and the same commands as the real move.
Only the servers and the data are different.

**What the rehearsal can target.** It cannot target `staging01`. Three things
in the playbooks stop it:

- `copy_onto` must be the first name in the `database_servers` group, the
  primary of a new failover formation. `staging01` is in `staging_server` only, and
  its Postgres stays outside the failover formation (the validation role refuses any
  other `copy_onto`).
- The copy and switch playbooks run their move steps on `database_servers`
  only. `staging01` never runs them.
- Only app, jobs, and database servers get the temporary WireGuard peer for
  the old server. `staging01` gets none, by design, so it could not reach
  the old server.

Changing any of these is a code change, not a setting, so the rehearsal
below is written against what works: a second, complete test Stack.

1. **Build a test Stack of its own.** Follow the setup chapters again with a
   new systems repository (for example `rehearsal_systems`), its own
   systems desk, `util01`, `db01`, `db02`, and one app server. Use a separate
   project or account at the provider if the provider has one. Reason: the
   production desk's server list check and `util01`'s daily check
   `check_for_a_leftover_restore01` compare the provider's list with the
   production inventory, and would report the test servers as strangers. Deploy a small test app (or the real app's image) under
   `vars.apps`, with a database name of its own. Use the same Debian release
   and the same Postgres major version the production Stack uses.
   **Check:** the checks of the setup chapters pass on the test Stack.
2. **Build a test old server.** Make a Debian server with the Postgres
   version the real old database uses. Fill it with made-up data. Never copy
   customer data into the rehearsal. Make the data include what the real
   database has, in miniature: a table without a primary key, a large
   object, a sequence, an unlogged table (to see the refusal), and any
   extension the real database uses. Run the app against it if the app can
   run in the test Stack, so a writer exists during the switch.
   No check here: step 3 uses every part of the test data.
3. **Do every step of this procedure** against the test Stack: [Prepare the old server](#prepare-the-old-server),
   [Prepare the Stack and move the app](#prepare-the-stack-and-move-the-app),
   [Copy the database](#copy-the-database), and
   [Switch and verify](#switch-and-verify). Use the test servers' own
   addresses and keys wherever the steps name an address or key. For a managed
   old database, rehearse with a relay and a test managed database the same way.
   **Check:** the checks of each of those sections.
4. **Keep an HTTP writer running through the switch** as the Switch section
   says, and write down the measured pause the results show. Run the
   rehearsal a second time from a restored test old server if the first run
   found a problem.
   **Check:** you wrote down the measured pause.
5. **Destroy the test Stack and the test old server** when done. Verify each
   provider ID, destroy the server, and check a fresh provider listing. The
   test Stack's own servers need no [Remove a server](remove_a_server.md)
   steps, because the whole test repository is thrown away.
   **Check:** a fresh provider listing shows none of the test servers.

**What the rehearsal proves:** the old server's changes (the restart for
`wal_level = logical`, `pg_hba.conf`, the firewall, WireGuard) work on this
Postgres version and at this provider; the commands, settings and vault
keys are right; the team has seen the copy, the switch, the pause, and the
cleanup once; and the app's driver reconnects without a restart.

**What it does not prove:** how long the first copy takes and how much WAL the
old server keeps for the real data size; replication lag under the real write
load; that the real database's tables, extensions, ownership and grants all
copy (the inventory step in [Prepare the old server](#prepare-the-old-server)
still decides this); how the real app behaves; and anything about
`staging01`, which the real move never touches.

## Prepare the old server

1. **Announce the work and back up the old system.**
   Ask the person to announce the work in the team's chat.
   Take and verify an old-system backup before changing the old system.
   Keep the old system until the final customer checks and a Stack backup pass.
   **Check:** the backup's verification passed.
2. **Inventory the old databases.**
   Inventory every app database, extension, table owner, extra role, grant, sequence, and large object.
   Create required extra owner and grantee roles on the Stack before loading the schema.
   Do not import old cluster administrators as app roles.
   Resolve unsupported extensions and non-table data before starting the move.
   The copy refuses unlogged tables, materialized views, and foreign tables, because logical replication cannot copy their stored rows.
   Convert an unlogged table with `ALTER TABLE public.legacy_cache SET LOGGED`, or plan a separate rebuild or retained dependency first.
   The copy command refuses a Stack database that already contains app tables, views, or sequences.
   **Check:** each unsupported extension, unlogged table, materialized
   view and foreign table has a resolution before the move starts.
3. **Make the old server's WireGuard key.**
   Run these commands on the old server as root, with `wireguard-tools` installed:

   ```sh
   install -d -m 700 /etc/wireguard
   umask 077
   wg genkey > /etc/wireguard/database_moving_in.private_key
   wg pubkey < /etc/wireguard/database_moving_in.private_key
   ```

   Save the printed public key in the inventory block, in step 3 of
   [Prepare the Stack and move the app](#prepare-the-stack-and-move-the-app).
   Keep the private key on the old server.
   No check here: step 5 checks WireGuard.
4. **Write the old server's WireGuard settings.**
   If `wg0` already exists, merge the following address and peers into its configuration instead of replacing the existing configuration.
   In the example file, replace each `..._WIREGUARD_PUBLIC_KEY` with that server's `wireguard_public_key` in `inventories/servers.yml`, and each address with the server's `public_ipv4_address`.
   Add a peer for every additional app, jobs, and database server that needs the old database.
   Each peer's `AllowedIPs` is that Stack server's private address followed by `/32`.

   Create `/etc/wireguard/wg0.conf`:

   ```sh
   umask 077
   {
     printf '[Interface]\nAddress = 10.20.11.1/16\nListenPort = 51820\nPrivateKey = '
     cat /etc/wireguard/database_moving_in.private_key
     cat <<'WIREGUARD'

   [Peer]
   # app001
   PublicKey = APP001_WIREGUARD_PUBLIC_KEY
   Endpoint = 203.0.113.11:443
   AllowedIPs = 10.20.1.1/32

   [Peer]
   # db01
   PublicKey = DB01_WIREGUARD_PUBLIC_KEY
   Endpoint = 203.0.113.21:443
   AllowedIPs = 10.20.2.1/32

   [Peer]
   # db02
   PublicKey = DB02_WIREGUARD_PUBLIC_KEY
   Endpoint = 203.0.113.22:443
   AllowedIPs = 10.20.2.2/32
   WIREGUARD
   } > /etc/wireguard/wg0.conf
   ```

   No check here: step 5 checks the peers.
5. **Redirect UDP 443 and start WireGuard.**
   The Stack servers send to this server's UDP 443, as the `Endpoint` lines of their peers say.
   This server's `wg0` listens on UDP 51820, above 1024, because on Ubuntu 26.04 and later Debian releases AppArmor confines `wg-quick` and refuses a port below 1024.
   A small redirect turns UDP 443 into 51820 before WireGuard starts.
   It is a table of its own, so it touches none of the old server's firewall files.
   Make the nft file and the unit that loads it, then start WireGuard:

   ```sh
   apt-get install -y nftables
   cat > /etc/wireguard/wireguard_udp_443_redirect.nft <<'NFT'
   table inet stack_wireguard_port {}
   flush table inet stack_wireguard_port
   table inet stack_wireguard_port {
       chain prerouting {
           type nat hook prerouting priority dstnat; policy accept;
           udp dport 443 redirect to :51820
       }
   }
   NFT
   cat > /etc/systemd/system/wireguard-udp-443-redirect.service <<'UNIT'
   [Unit]
   Description=Redirect UDP 443 to the port WireGuard listens on
   Before=wg-quick@wg0.service

   [Service]
   Type=oneshot
   RemainAfterExit=yes
   ExecStart=/usr/sbin/nft -f /etc/wireguard/wireguard_udp_443_redirect.nft

   [Install]
   WantedBy=multi-user.target
   UNIT
   systemctl daemon-reload
   systemctl enable --now wireguard-udp-443-redirect.service
   systemctl enable --now wg-quick@wg0
   ```

   **Check:** `wg0` has one peer for each Stack server you added, and no other:

   ```sh
   wg show wg0 allowed-ips
   ```

   Each line is a peer's public key and its `AllowedIPs`. A missing line means a copied file lost a peer: fix `wg0.conf` and run `systemctl restart wg-quick@wg0`.
6. **Open the old server's firewall to the Stack.**
   On the old server, allow WireGuard's port, UDP 51820, which the redirect above makes of the public UDP 443.
   Allow Postgres only over `wg0` from the app, jobs, and database ranges below.
   Preserve the old server's existing administration and app rules.
   For a server using UFW, add:

   ```sh
   ufw allow 51820/udp
   ufw allow in on wg0 from 10.20.1.0/24 to 10.20.11.1 port 5432 proto tcp
   ufw allow in on wg0 from 10.20.3.0/24 to 10.20.11.1 port 5432 proto tcp
   ufw allow in on wg0 from 10.20.2.0/24 to 10.20.11.1 port 5432 proto tcp
   ```

   Use the actual `private_ip_ranges` when the team's address plan differs.
   For a container database, publish Postgres on the WireGuard address and apply equivalent source restrictions.
   Keep public Postgres closed.
   No check here: step 7 of [Prepare the Stack and move the app](#prepare-the-stack-and-move-the-app)
   checks that the Stack app's connections arrive.
7. **Change the old Postgres settings.**
   Add these exact settings to the old Postgres configuration:
   Keep any existing listener addresses needed by the old app until the app moves.

   ```conf
   wal_level = logical
   listen_addresses = '127.0.0.1,10.20.11.1'
   # Prompt keepalives make the switch's replay-feedback check finish quickly.
   wal_sender_timeout = '4s'
   ```

   Add these lines before broader matching rules in the old `pg_hba.conf`:

   ```conf
   host shop shop 10.20.1.0/24 scram-sha-256
   host shop shop 10.20.3.0/24 scram-sha-256
   host shop database_moving_in_replication 10.20.2.0/24 scram-sha-256
   host all postgres 10.20.2.0/24 scram-sha-256
   ```

   Logical replication connects to the app database, so the replication line names `shop`, not the special physical-replication database.
   Ensure `max_replication_slots` and `max_wal_senders` have room for the apps and their initial table copies.
   Postgres's defaults provide ten of each. Existing replicas and subscriptions also consume slots and senders.
   No check here: the settings take effect at step 8's restart.
8. **Restart the old Postgres** during the agreed maintenance window.
   For Debian's Postgres 15 cluster named `main`:

   ```sh
   systemctl restart postgresql@15-main
   ```

   For a container or another cluster name, restart that old database through its existing service manager.
   **Check:** the old app still works after the restart.
9. **Create the replication role, the grants and the publication.**
   Open an administrator `psql` session on the old server:

   ```sh
   sudo -u postgres psql -X -d shop
   ```

   Run:

   ```sql
   CREATE ROLE database_moving_in_replication LOGIN REPLICATION BYPASSRLS;
   \password database_moving_in_replication
   GRANT CONNECT ON DATABASE shop TO database_moving_in_replication;
   GRANT USAGE ON SCHEMA public TO database_moving_in_replication;
   GRANT SELECT ON ALL TABLES IN SCHEMA public TO database_moving_in_replication;
   CREATE PUBLICATION database_moving_in FOR ALL TABLES;
   \password shop
   \password postgres
   ```

   Create the replication role and set its password once per old cluster.
   For each additional app database, repeat the database/schema/table grants
   and `CREATE PUBLICATION`, using that database's actual names and schemas.
   Set each app role's password to its matching Stack vault value.
   Set `shop`'s password to the Stack vault's `shop_database_password`, so the unchanged URL can reach either system.
   The replication and postgres passwords belong in the vault keys below.
   If postgres already has a password, keep that password and save the existing value instead of changing postgres's password.
   Grant `USAGE` and `SELECT` in each additional app schema too.
   `BYPASSRLS` ensures the initial copy includes every row instead of a policy-filtered subset.
   For a table without a key, run the following with the actual table name before starting replication:

   ```sql
   ALTER TABLE public.legacy_notes REPLICA IDENTITY FULL;
   ```

   No check here: the copy in [Copy the database](#copy-the-database) uses
   the role, the grants and the publication.

## An old database behind a provider network

For a database without WireGuard access, use a temporary Debian 13 relay VM inside the provider network.
The transport setup below is for RDS, Cloud SQL, and Azure databases.
A relay accepts Stack connections and opens connections to the managed database.
Follow the backup, object inventory, publication, password, and grant requirements above.
Replace the old server's operating-system setup with the following relay setup.

Reason for two fences: PgBouncer restores cached session settings on new server connections, so a database read-only default alone cannot fence a warm relay.
The relay switch disables app entries and drops app connections before fencing the source database.
Separate copy entries keep replication and administrator reads reachable during the fence.

1. **Enable the provider's logical replication setting before copying.**
   For RDS, set `rds.logical_replication = 1` in the instance's parameter group, then reboot during the maintenance window.
   For [Cloud SQL](https://docs.cloud.google.com/sql/docs/postgres/replication/configure-logical-replication), set `cloudsql.logical_decoding = on` and restart.
   For [Azure Flexible Server](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-logical), set `wal_level = logical` and restart.
   Allow enough replication slots and WAL senders for the app databases and initial table copies.
   Set `wal_sender_timeout = 4000` milliseconds through the provider settings, so replay feedback arrives promptly during the switch.
   See [RDS logical replication](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.Concepts.General.FeatureSupport.LogicalReplication.html).
   No check here: the copy's subscription in [Copy the database](#copy-the-database) needs the setting.
2. **Create the replication login.**
   On RDS, create `database_moving_in_replication` with `LOGIN`.
   Grant `rds_replication` instead of requesting Postgres's native `REPLICATION` attribute.
   Grant the database, schema, and table access shown above.
   If any source table uses row security, the replication login also needs `BYPASSRLS` before copying.
   The copy checks actual replication access and refuses row security without that protection.
   No check here: the copy checks the login's access, as the sentence before says.
3. **Give `postgres` the source administrator's permissions.**
   The helper's source administrator login is `postgres`, even when `postgres` is not a Postgres superuser.
   Give `postgres` the database owner's permissions, plus access to schema, sequences, and large objects.
   Give `postgres` access to replication statistics and permission to end app sessions.
   On ordinary Postgres, database ownership, membership of the app owner roles, `pg_read_all_stats`, and `pg_signal_backend` provide those permissions.
   Use the provider's permitted administrator to prepare roles and the all-table publication.
   Save `postgres`'s password under the existing `database_moving_in_superuser_password` vault key.
   No check here: the copy and the switch use these permissions.
4. **Install PgBouncer on the relay.**
   On the relay, install PgBouncer from [Postgres's apt repository](https://www.postgresql.org/download/linux/debian/).
   Use PgBouncer 1.26.1 or newer, with `track_extra_parameters` as shown below.
   The Stack sends `PGOPTIONS=-c lock_timeout=5s` when running app migrations.
   Debian 13's PgBouncer 1.24.1 cannot preserve that guard on Postgres 15.
   PgBouncer 1.26 fixes tracked startup parameters that Postgres does not report to clients.
   The relay setup below was checked with PgBouncer 1.26.1.

   Run these commands as root on the Debian 13 relay.
   Check the downloaded signing key against the fingerprint [Postgres publishes](https://www.postgresql.org/download/linux/debian/#postgresql-apt-repository) before adding the apt source:

   ```sh
   set -eu
   apt-get update
   apt-get install -y curl ca-certificates gpg wireguard-tools
   install -d /usr/share/postgresql-common/pgdg
   curl --fail --output /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
     https://www.postgresql.org/media/keys/ACCC4CF8.asc
   pgdg_key_fingerprint=$(gpg --show-keys --with-colons \
     /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
     | awk -F: '$1 == "fpr" { print $10; exit }')
   test "$pgdg_key_fingerprint" = B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8
   cat > /etc/apt/sources.list.d/pgdg.sources <<'EOF'
   Types: deb
   URIs: https://apt.postgresql.org/pub/repos/apt
   Suites: trixie-pgdg
   Components: main
   Signed-By: /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc
   EOF
   chmod 644 /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc /etc/apt/sources.list.d/pgdg.sources
   apt-get update
   apt-get install -y pgbouncer postgresql-client-17
   dpkg --compare-versions "$(dpkg-query -W -f='${Version}' pgbouncer)" ge 1.26.1
   pgbouncer --version
   ```

   **Check:** the commands run to the end, and `pgbouncer --version`
   prints 1.26.1 or newer. With `set -eu`, a wrong key fingerprint or an
   older PgBouncer stops the commands.
5. **Connect the relay to the Stack and to the managed database.**
   Give the relay the inventory's `database_moving_in` public endpoint and WireGuard key.
   On the relay, create `/etc/wireguard/database_moving_in.private_key` and `/etc/wireguard/wg0.conf` with the exact commands and peers above.
   Apply the WireGuard and `wg0` Postgres firewall rules above to the relay.
   The provider firewall must allow TCP 5432 from the relay's private address or security group to the managed database only.
   For example, allow `10.0.1.10/32` to the database's private listener on TCP 5432.
   Do not expose the managed database publicly or add IP forwarding: PgBouncer makes the outgoing connections.
   No check here: step 9 checks the relay's peers, and step 10 its connections to the managed database.
6. **Save the provider's CA bundle** as `/etc/pgbouncer/provider-ca.pem`.
   For RDS, use the [AWS certificate bundle](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.SSL.html).
   Use the provider's database hostname for certificate verification, never the database's numeric address.
   Replace `managed-db.example.com` below with that hostname.
   No check here: step 10 checks that every relay connection uses TLS.
7. **Write `/etc/pgbouncer/pgbouncer.ini`:**

   ```ini
   [databases]
   shop = host=managed-db.example.com port=5432 dbname=shop
   database_moving_in_8d9001d32c6a703d95921a77115050f3 = host=managed-db.example.com port=5432 dbname=shop
   postgres = host=managed-db.example.com port=5432 dbname=postgres

   [pgbouncer]
   listen_addr = 10.20.11.1
   listen_port = 5432
   unix_socket_dir =
   auth_type = scram-sha-256
   auth_file = /etc/pgbouncer/userlist.txt
   admin_users = database_moving_in_relay_admin
   pool_mode = session
   track_extra_parameters = lock_timeout, statement_timeout, idle_in_transaction_session_timeout
   client_tls_sslmode = disable
   server_tls_sslmode = verify-full
   server_tls_ca_file = /etc/pgbouncer/provider-ca.pem
   logfile = /var/log/postgresql/pgbouncer.log
   pidfile = /var/run/postgresql/pgbouncer.pid
   ```

   Each moving database needs an app entry and a separate copy entry.
   The app entry keeps the database name, such as `shop`.
   The copy entry uses the migration slot name and points to the actual source database.
   The example copy entry above is the derived name for `shop`.
   Print the copy entry name for each additional database, replacing `shop` with the actual database name:

   ```sh
   python3 - <<'PYTHON'
   import hashlib
   print('database_moving_in_' + hashlib.sha256('shop'.encode()).hexdigest()[:32])
   PYTHON
   ```

   Replication and source administrator reads use the copy entry during the fence.
   Keep the `postgres` entry for cluster-level administrator queries.
   Do not add a wildcard entry, because a wildcard could reopen a disabled app entry.
   The console uses database `pgbouncer` on the existing listener, bound only to the relay's WireGuard address.
   The relay administrator is a PgBouncer login, not a managed Postgres role.
   Do not grant the app login PgBouncer administrator access.
   No check here: step 12's fence test uses each entry.
8. **Write the relay's passwords.**
   Write `/etc/pgbouncer/userlist.txt` with each login's actual password, matching the managed database and Stack vault:

   ```text
   "shop" "replace-with-shop-database-password"
   "postgres" "replace-with-source-administrator-password"
   "database_moving_in_replication" "replace-with-replication-password"
   "database_moving_in_relay_admin" "replace-with-relay-admin-password"
   ```

   PgBouncer needs these passwords to authenticate its outgoing verified-TLS connections.
   The relay administrator's password authenticates only to PgBouncer's console.
   The person saves the relay administrator password in the Stack vault, on the systems desk, then commits and pushes `secrets_vault.age`:

   ```sh
   # This systems desk, in the systems repository, in the person's own terminal:
   . ~/.config/monkeymaxxing-stack/example_systems.env && mmx secrets set database_moving_in_relay_admin_password
   ```

   No check here: step 12 logs in with each password.
9. **Protect the relay's files, then start PgBouncer:**

   ```sh
   chown postgres:postgres /etc/pgbouncer/pgbouncer.ini /etc/pgbouncer/userlist.txt /etc/pgbouncer/provider-ca.pem
   chmod 640 /etc/pgbouncer/pgbouncer.ini /etc/pgbouncer/userlist.txt /etc/pgbouncer/provider-ca.pem
   systemctl enable --now wg-quick@wg0
   systemctl restart pgbouncer
   ```

   **Check:** the relay's peers with `wg show wg0 allowed-ips`, as for a self-hosted old server above.
10. **Check the relay's TLS connections.**
    On the managed database, check the relay's app and replication connections:

    ```sql
    SELECT a.usename, a.application_name, a.client_addr, s.ssl, s.version
    FROM pg_stat_activity a JOIN pg_stat_ssl s USING (pid)
    WHERE a.client_addr = '10.0.1.10'::inet;
    ```

    Use the relay's actual private address. **Check:** every relay connection must show `ssl = t`.
    [How the relay connects](#how-the-relay-connects) explains the TLS and the tracked settings.
11. **Set `through_relay: true`** in the `database_moving_in` inventory block, in step 3 of
    [Prepare the Stack and move the app](#prepare-the-stack-and-move-the-app).
    The copy command uses the copy entry. The relay switch also uses the relay administrator password.
    The app URLs keep the ordinary app entry.
    No check here: the run in that section checks the block.
12. **Before copying, prove the fence with a warm app pool.**
    Use `psql` on the relay to open the admin console, entering the relay administrator password when prompted:

    ```sh
    psql -X -h 10.20.11.1 -p 5432 -U database_moving_in_relay_admin -d pgbouncer -W
    ```

    Open an app connection through the relay and confirm the source is writable.
    Using the relay administrator, send `DISABLE shop`, then `KILL shop` to database `pgbouncer`.
    The existing app connection must close, and a fresh app connection must fail.
    The copy entry must still accept the replication login.
    Set the source database read-only, end captured app backends, and verify a direct fresh source session is read-only.
    The relay app entry must remain unreachable despite the cached writable default.
    Reset the source database default, then send `ENABLE shop`.
    Run `SHOW DATABASES` on the console. If `shop` reports `paused = 1`, send `RESUME shop`.
    Repeat the probe for each moving database.
    **Check:** verify a fresh app connection can write again before copying.
13. **After the switch, retire the relay.**
    After the switch, verify customer checks and a Stack backup before stopping the relay.
    Remove `database_moving_in`, apply `every_server`, and confirm the old URL and WireGuard peer disappeared.
    Remove the provider's relay-to-database firewall rule, destroy the relay and its disk, and retire the accepted old database through the provider.
    Destroying the relay removes the relay's passwords, CA bundle, and WireGuard private key.
    **Check:** the old URL and WireGuard peer are gone, and the provider lists no relay.

## Prepare the Stack and move the app

1. **Create the Stack's servers.**
   Create `util01`, `db01`, `db02`, and the app servers through the normal setup.
   Put db01 and db02 in `database_servers`. The first server in name order becomes the new failover formation's primary.
   Do not put the old server in `nodes` or any inventory group.
   The Stack must never configure the old cluster as a managed database server.
   Keep `systems_desk_provider_api_url` as it is for the whole move, even when the old server is at another provider: no step calls the old provider's API from the desk, so the old server, a relay, and a managed database are handled with the old provider's own console and tools.
   When the old server is in the same provider account as the Stack, the desk's server list and `util01`'s daily check `check_for_a_leftover_restore01` show it as a
   server that isn't in the inventory, until the move ends and the old server is retired: that is expected, so say so when you
   report it.
   **Check:** the checks of the setup chapters pass, and the old server is in no inventory group.
2. **The person saves the old Postgres passwords,** then commits and pushes `secrets_vault.age`:

   ```sh
   # This systems desk, in the systems repository, in the person's own terminal:
   . ~/.config/monkeymaxxing-stack/example_systems.env &&
     mmx secrets set database_moving_in_replication_password &&
     mmx secrets set database_moving_in_superuser_password
   ```

   **Check:** after the person's push, `sudo -n -u servers-mmx run-mmx-on-the-servers secrets usage`
   no longer shows either key as `not defined`.
3. **Add this block under `vars` in `inventories/servers.yml`:**

   ```yaml
   database_moving_in:
     wireguard_address: 10.20.11.1
     wireguard_public_key: "F2qpGm7+0rhvkiDtzK0xwD1vM9t3q0HjOdC2mW1W3XY="
     public_ipv4_address: 203.0.113.50
     postgres_port: 5432
     copy_onto: db01
     apps: [shop]
     through_relay: false
   ```

   The example public key must be replaced with the old server's printed key.
   For a managed source, use the relay's public key and set `through_relay: true`.
   For a self-hosted source, keep `through_relay: false`.
   `through_relay` is required: the switch playbook chooses its fleet stage from it before the run starts.
   For a self-hosted source, `postgres_port` must be the old Postgres itself, never a PgBouncer or other pooler in front of it.
   A pooler restores each client's cached `default_transaction_read_only` on new server connections, so the switch's fence would not stop app writes through it.
   The old platform's apps can keep their pooler until the switch; only the Stack's connections skip it.
   Keep `apps_connect_through_pgbouncer.production` false in `mmx_project_settings.yml` during the move. The commands refuse a move while it is true. Add the Stack's PgBouncer after the move, by [add_pgbouncer.md](add_pgbouncer.md).
   The address must lie in `vars.private_ip_ranges.database_moving_in`, whose example range is `10.20.11.0/24`.
   The old address must be outside every other role range, so the old peer gains no incoming service permission.
   Include every app that shares a listed database, because the apps share one login and must move together.
   Keep `copy_onto` as the failover formation's primary while preparing and switching.
   The commands refuse a destination that is a live replica.
   No check here: the run in step 6 checks the block.
4. **For a Node.js app, update its database driver.**
   For a Node.js app, copy the Stack skill's current `pg_with_multiple_database_servers.mjs` into the app and rebuild its image first.
   The connection check must test `transaction_read_only`, because recovery state alone does not identify a writable login.
   No check here: step 7 checks the app's connections.
5. **Commit and stop the old app's work.**
   Commit, synchronize, and push the settings using the normal systems-repository procedure.
   Stop old web processes, workers, schedules, and deployment triggers before
   the following run starts the Stack app's workers and schedules.
   Keep the old Postgres running. This avoids two worker fleets using the same job queue.
   No check here: step 6 runs the pushed settings.
6. **Run `every_server`:**

   ```sh
   ./server_management_scripts/run_mmx_on_util01 run every_server
   ```

   The normal run creates the failover formation, its replica, and its backups.
   The app, jobs, and database servers gain an old-server WireGuard peer.
   The Stack adds no incoming service permission for the old server.
   The listed apps' write and read URLs put the old server first and require a writable login.
   Their Stack database roles stay read-only until the switch.
   Reads temporarily use the primary, so reads cannot select the unfinished Stack replica.
   **Check:** the run ends without failed work, and its validation says
   `database_moving_in settings are valid.`
7. **Check the app on the Stack against the old database.**
   Check existing logins, customer writes, ownership, uploaded files, and pending jobs through the Stack app using the old database.
   Verify that the app's database connections arrive on the old server from the Stack app addresses.
   Run no schema migration until the move finishes.
   **Check:** each of those checks passes.

## Copy the database

1. **Start the copy,** from the systems desk:

   ```sh
   ./server_management_scripts/run_mmx_on_util01 run copy_the_database_moving_in
   ```

   The command loads `pg_dump --schema-only` into each listed app database and starts a postgres-owned subscription on db01.
   [What the copy sets up](#what-the-copy-sets-up) explains the names and the password files.
   Read the exact source slot on the destination app database:

   ```sql
   SELECT subslotname FROM pg_subscription
   WHERE subdbid = (SELECT oid FROM pg_database WHERE datname = current_database());
   ```

   The catalog is shared across the cluster, so the database filter matters when several apps move together.
   No check here: step 2 checks the copy.
2. **On db01, check each app database:**

   ```sh
   sudo -u postgres psql -X -d shop
   ```

   ```sql
   SELECT s.subname, s.pid, s.received_lsn
   FROM pg_stat_subscription s JOIN pg_subscription p ON p.oid = s.subid
   WHERE p.subdbid = (SELECT oid FROM pg_database WHERE datname = current_database());
   SELECT srrelid::regclass, srsubstate FROM pg_subscription_rel;
   ```

   **Check:** every table must reach state `r`, meaning ready.
3. **Check the replica and the old server while the copy runs.**
   Check db02 receives the copied tables through normal physical replication from db01.
   Monitor the old server's free disk space and retained WAL while the copy runs.
   A stopped subscription can retain old WAL until the subscription resumes or its slot is removed.
   **Check:** db02 holds the copied tables, and the old server keeps free disk space.

**If a failover happens during the copy:** physical replication carries the subscription catalog and apply progress to db02.
The subscription requests synchronous commits, so applied commits also wait for the failover formation's replica.
After a failover, verify the subscription is streaming on the new primary with every table ready.
Before running the copy or switch command, use the normal `switch_database_primary` playbook to return primary service to `copy_onto`.
Never create a second subscription against the same slot while an existing primary still uses the slot.
If initial table synchronization cannot resume after failover, keep the apps on the old database and inspect the worker error before rebuilding the unfinished copy.

## Switch and verify

1. **Reset the read-only overrides on the old server.**
   The database fence requires the old app roles and databases to have no override of `default_transaction_read_only`.
   The switch refuses an override before fencing. Save any existing values before resetting the overrides.
   For shop, reset role and database overrides on the old server:

   ```sql
   ALTER ROLE shop RESET default_transaction_read_only;
   ALTER ROLE shop IN DATABASE shop RESET default_transaction_read_only;
   ALTER DATABASE shop RESET default_transaction_read_only;
   ```

   Ensure no app or outside writer explicitly requests a writable transaction after connecting to the old server.
   The fence is a connection default, not a permission that prevents an administrator from changing transaction mode.
   The app must also respect read-only defaults on the unfinished Stack copy.
   No check here: the switch refuses an override before fencing.
2. **Start an HTTP writer and save the containers' start times.**
   Keep an HTTP writer running through the Stack app throughout the switch.
   Record each acknowledged write's identifier, time, and row contents.
   Capture the app containers' start times before switching:

   ```sh
   podman inspect --format '{{.Name}} {{.State.StartedAt}}' shop-web-8001 shop-jobs
   ```

   No check here: step 4 compares the writes and the start times.
3. **Switch,** from the systems desk, for either kind of source:

   ```sh
   ./server_management_scripts/run_mmx_on_util01 run switch_to_the_database_moving_in
   ```

   `through_relay` chooses the fleet stage that runs on the database servers:
   `switch_to_the_database_moving_in` for a self-hosted source, or
   `switch_to_the_database_moving_in_through_relay`, which also passes the relay administrator password from the vault to the switch helper.
   MMX decides the choice before the run starts, so a self-hosted move needs no relay administrator password in the vault.
   The copy command is the same for every source.

   **Check:** show the measured pause parts saved in MMX's results:

   ```sh
   ./server_management_scripts/run_mmx_on_util01 results --node db01 --json | jq -r '.. | objects | .stdout? // empty'
   ```

   The output reports fence, catch-up, sequence, large-object, subscription-cleanup, and opening times, plus subscription-disable time for relay moves.
   [What the switch does](#what-the-switch-does) explains each part.
4. **Verify the data and the app.**
   Compare every acknowledged write's full row on db01 and db02, including timestamps and values. An identifier alone can match a different write.
   Record the old database's last write time and the Stack's first write time. No old write may follow the relay fence.
   Verify db02 holds the copied data, sequence values match, and large-object OIDs, bytes, owners, and permissions match.
   Repeat customer checks through the app.
   Compare the container start times with the saved times.
   Check there are no destination subscriptions or source migration slots left.
   Run a full backup on the Stack primary:

   ```sh
   sudo -u postgres /usr/local/sbin/back_up_the_database_on_the_primary full
   ```

   **Check:** each comparison matches, and the full backup passes.
5. **Remove the temporary settings.**
   Before another `every_server` run, remove the `database_moving_in` block or set the block to `{}`.
   After the switch, `every_server` leaves the app logins as they are, since the database holds data and no longer subscribes to the old one. Removing the block still removes the temporary peer and old URL address.
   Commit, synchronize, push, and run `every_server` to remove the temporary peer and old URL address.
   **Check:** read URLs return to preferring Stack replicas.
6. **Clean up the old move's files and roles.**
   Remove the old password file on each database server after confirming no subscription uses the file.
   After an accepted relay move, also remove `/var/lib/postgresql/database_moving_in_relay_admin.pgpass` from each database server.
   Remove the old publication and temporary replication role when the move is accepted.
   No check here: step 7's customer checks run without them.
7. **Retire the old system.**
   Power off the old system and repeat customer writes and reads.
   Only then record the migration checklist item as done and retire the old system through its existing platform procedure.
   **Check:** customer writes and reads work with the old system powered off.

## If something is different

- **A failover during the copy:** follow
  [If a failover happens during the copy](#copy-the-database), under Copy the database.
- **A relay switch fails before the Stack opens:**
  If a relay switch fails before the Stack opens, subscriptions are enabled, old database defaults reset, and relay app entries reopened.
- **A self-hosted switch fails before subscription cleanup:**
  If a self-hosted switch fails before subscription cleanup, the old database becomes writable again.
  Inspect any partially copied large objects before retrying, because a retry refuses unexpected destination large objects.
- **A switch fails after the Stack opens:**
  After the Stack opens, or self-hosted subscription cleanup begins, the old database stays fenced. Do not reopen the old database automatically.
  Inspect the remaining subscriptions and Stack role settings, finish cleanup, and open the Stack only after confirming every app copy.
  Keep any app already writing on the Stack there. Reopening the old database could split customer writes.

## Background

### What the copy sets up

The publication and subscription are named `database_moving_in` in each app database.
The copy creates a target NOLOGIN mapping for `database_moving_in_replication`, so the source's grants restore without creating a target replication login.
Each source slot uses `database_moving_in_` followed by 32 hexadecimal characters derived from the database name.
The derived name fits Postgres's slot-name rules even when the database name is long or uses different characters.

Passwords stay in `/var/lib/postgresql/database_moving_in.pgpass` on every Stack database server, owned by postgres with mode 0600.
Each replica needs `/var/lib/postgresql/database_moving_in.pgpass` so a promoted replica can resume the subscription.
The subscription connection contains the password-file path, rather than a password.
The relay switch writes `/var/lib/postgresql/database_moving_in_relay_admin.pgpass` on every database server, owned by postgres with mode 0600.
The separate file holds the `database_moving_in_relay_admin` password for database `pgbouncer`.

### What the switch does

The command first refuses any subscription that is not streaming or has an unfinished table.
For a relay move, the command first sends `DISABLE` for every moving app entry, then `KILL` for every app entry.
The relay fence refuses new clients and drops existing clients and backends before the database fence starts.
The relay leaves the separate copy entries enabled, so subscriptions and administrator reads can continue.
For each moving database, the command runs `ALTER DATABASE ... SET default_transaction_read_only = on`.
The command then ends the listed app roles' sessions.
The database fence covers direct source sessions. The relay fence blocks cached writable session settings.
The command then waits for each subscription to receive, apply, and flush the fenced cluster's current WAL insertion position.
The insertion position includes acknowledged asynchronous commits that have not yet reached the source WAL file.
WAL is Postgres's record of database changes. An LSN identifies a position in WAL.
The check uses subscriber replay feedback on the old publisher, because receiving WAL alone does not prove durable application.
If catch-up exceeds 15 seconds, the command resets the old database defaults and keeps Stack app roles read-only.
For a relay move, rollback also enables app entries and resumes paused app entries.

After catch-up, the command copies sequence values and large objects.
For a self-hosted source, the command removes subscriptions and old slots, then opens Stack app roles in one transaction.
For a relay source, the command disables subscriptions, opens Stack app roles in one transaction, then removes subscriptions and old slots.
Keeping disabled subscriptions until the Stack opens allows rollback of every earlier failure.
After a successful relay switch, the app entries remain disabled.
If the opening transaction loses a reply, the helper checks the Stack role defaults before deciding whether rollback is safe.
If the Stack role defaults cannot be checked, the source stays fenced for inspection.
Drivers reconnect through the existing URLs. No app restart occurs inside the switch.
`relay_fence_completed_unix_seconds` records when every relay app entry finished disconnecting, as seconds since the Unix epoch in UTC.
MMX also keeps the measurements in the switch task's public stdout in `results --json`.
Raw Postgres errors stay in `/var/lib/postgresql/database_moving_in_error.txt` on `copy_onto`, readable only by postgres and root.
The HTTP writer measures actual customer recovery, which can take longer than the command's pause.

### How the relay connects

The Stack-to-relay Postgres connection is unencrypted inside WireGuard.
WireGuard already encrypts that network traffic, which is the Stack's usual choice for database connections.
The managed database's TLS connection ends on the relay, where PgBouncer verifies the provider certificate and hostname.
Keep `DATABASE_URL`'s TLS settings unchanged: URL settings apply to every listed host, including the Stack's own database servers.
PgBouncer passes logical replication connections through the separate copy entry on the same relay address and port.
`track_extra_parameters` preserves each setting a client sends when it connects, and resets it for a later client without that setting.
`lock_timeout` carries the migration's five-second guard. `statement_timeout` and `idle_in_transaction_session_timeout` are common app settings.
Add any other setting your apps send when they connect: PgBouncer refuses a login whose setting it does not track.
Do not add `lock_timeout` or `options` to `ignore_startup_parameters`: ignoring the startup option removes the migration guard.
