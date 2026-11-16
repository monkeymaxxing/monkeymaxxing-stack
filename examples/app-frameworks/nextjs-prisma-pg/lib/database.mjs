import { poolForDatabaseUrl } from './pg_with_multiple_database_servers.mjs'

let pool
export function database() {
  const maximumConnections = Number(process.env.DATABASE_POOL_MAX_CONNECTIONS ?? 4)
  if (!Number.isSafeInteger(maximumConnections) || maximumConnections < 1) {
    throw new Error('DATABASE_POOL_MAX_CONNECTIONS must be a positive integer')
  }
  pool ??= poolForDatabaseUrl(process.env.DATABASE_URL, {
    max: maximumConnections, connectionTimeoutMillis: 3000,
    query_timeout: 13000,
    application_name: 'nextjs-portal',
  })
  return pool
}

export async function transaction(action) {
  const client = await database().connect()
  let failure
  try {
    await client.query('BEGIN')
    await client.query("SET LOCAL statement_timeout = '12s'")
    await client.query("SET LOCAL lock_timeout = '5s'")
    const value = await action(client)
    await client.query('COMMIT')
    return value
  } catch (error) {
    failure = error
    await client.query('ROLLBACK').catch(() => {})
    throw error
  } finally {
    client.release(failure)
  }
}

export async function closeDatabase() {
  if (pool) await pool.end()
}

export async function health() {
  return transaction(async client => {
    await client.query("SET LOCAL statement_timeout = '1500ms'")
    const { rows } = await client.query("SELECT count(*)::int AS count FROM schema_migrations WHERE version IN ('0001_portal.sql','0002_record_descriptions.sql')")
    if (rows[0].count !== 2) throw new Error('Migrations are missing')
    return { healthy: true }
  })
}
