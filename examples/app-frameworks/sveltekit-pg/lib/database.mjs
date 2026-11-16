import { poolForDatabaseUrl } from './pg_with_multiple_database_servers.mjs'

let pool
export function database() {
  const maximumConnections = Number(process.env.DATABASE_POOL_MAX_CONNECTIONS ?? 4)
  if (!Number.isSafeInteger(maximumConnections) || maximumConnections < 1) {
    throw new Error('DATABASE_POOL_MAX_CONNECTIONS must be a positive integer')
  }
  pool ??= poolForDatabaseUrl(process.env.DATABASE_URL, {
    max: maximumConnections, connectionTimeoutMillis: 8000, query_timeout: 8000,
    options: process.env.PGOPTIONS || '',
  })
  return pool
}
export async function closeDatabase() { if (pool) await pool.end() }
export async function transaction(work) {
  const client = await database().connect()
  let failed
  try {
    await client.query('BEGIN')
    await client.query("SET LOCAL statement_timeout = '12s'")
    await client.query("SET LOCAL lock_timeout = '5s'")
    const result = await work(client)
    await client.query('COMMIT')
    return result
  } catch (error) {
    failed = error
    // No automatic replay: the COMMIT reply can be lost after a successful write.
    try { await client.query('ROLLBACK') } catch {}
    throw error
  } finally { client.release(failed) }
}
