import { poolForDatabaseUrl } from './pg_with_multiple_database_servers.mjs';
import { readdir, readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';

export const pool = poolForDatabaseUrl(process.env.DATABASE_URL, {
  ssl: process.env.DATABASE_SSL === 'true' ? { rejectUnauthorized: false } : false,
  max: 3,
  connectionTimeoutMillis: 5000,
  statement_timeout: 10000,
  query_timeout: 12000,
  idle_in_transaction_session_timeout: 15000,
  keepAlive: true,
});
pool.on('error', () => console.error('A database connection was lost.'));

export async function transaction(action) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const result = await action(client);
    await client.query('COMMIT');
    return result;
  } catch (error) {
    try { await client.query('ROLLBACK'); } catch { /* Preserve the original error. */ }
    throw error;
  } finally { client.release(); }
}

export async function migrate() {
  // A transaction lock serializes the full migration pass, including ledger creation.
  return transaction(async client => {
    await client.query('SELECT pg_advisory_xact_lock(77341024)');
    await client.query(`CREATE TABLE IF NOT EXISTS schema_migrations (
      version text PRIMARY KEY, sha256 text NOT NULL,
      applied_at timestamptz NOT NULL DEFAULT now())`);
    const directory = new URL('./migrations/', import.meta.url);
    for (const version of (await readdir(directory)).filter(name => /^\d+_.*\.sql$/.test(name)).sort()) {
      const sql = await readFile(new URL(version, directory), 'utf8');
      const sha256 = createHash('sha256').update(sql).digest('hex');
      const old = await client.query('SELECT sha256 FROM schema_migrations WHERE version=$1', [version]);
      if (old.rowCount) {
        if (old.rows[0].sha256 !== sha256) throw new Error(`Applied migration changed: ${version}`);
        continue;
      }
      await client.query(sql);
      await client.query('INSERT INTO schema_migrations(version,sha256) VALUES($1,$2)', [version, sha256]);
    }
  });
}
