import { transaction } from './database.mjs'
export async function runOneJob() {
  return transaction(async client => {
    const { rows } = await client.query('SELECT id,account_id FROM report_jobs WHERE completed_at IS NULL ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1')
    if (!rows.length) return false
    const job = rows[0]
    const result = await client.query('SELECT count(*) AS count FROM records WHERE account_id=$1', [job.account_id])
    await client.query('UPDATE report_jobs SET output=$1,completed_at=now() WHERE id=$2', [`record_count=${result.rows[0].count}\n`, job.id])
    return true
  })
}
