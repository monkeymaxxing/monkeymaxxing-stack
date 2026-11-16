import { poolForDatabaseUrl } from './pg_with_multiple_database_servers.mjs'

let pool
export function database() {
  pool ??= poolForDatabaseUrl(process.env.DATABASE_URL, {
    max: 4, connectionTimeoutMillis: 3000, statement_timeout: 12000,
    query_timeout: 13000, idle_in_transaction_session_timeout: 15000,
    application_name: 'vercel-exit-portal',
  })
  return pool
}

export async function transaction(action) {
  const client = await database().connect()
  let failure
  try {
    await client.query('BEGIN')
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
