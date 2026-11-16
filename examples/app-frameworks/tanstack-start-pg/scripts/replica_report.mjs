// Administrative aggregate. Counts can lag. Session and read-after-write paths stay on DATABASE_URL.
import { poolForDatabaseUrl } from '../lib/pg_with_multiple_database_servers.mjs'
for (const [purpose, variable] of [['read', 'DATABASE_READ_URL'], ['write', 'DATABASE_URL']]) {
  const pool = poolForDatabaseUrl(process.env[variable], {max: 1, connectionTimeoutMillis: 3000, query_timeout: 10000})
  try {
    const {rows} = await pool.query("select inet_server_addr()::text as database_server_address, pg_is_in_recovery() as is_replica, (select count(*)::int from records) as record_count")
    console.log(JSON.stringify({connection_purpose: purpose, ...rows[0]}))
  } finally { await pool.end() }
}
