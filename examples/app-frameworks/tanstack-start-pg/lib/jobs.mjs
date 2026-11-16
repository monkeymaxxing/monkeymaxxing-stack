import { transaction } from './database.mjs'

// Hold the row lock through counting and completion. Process death rolls back
// the whole transaction, so another worker sees the unfinished job again.
export async function runOneJob() {
  return transaction(async client => {
    const { rows } = await client.query('SELECT id,account_id FROM report_jobs WHERE finished_at IS NULL ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1')
    if (!rows.length) return false
    const job = rows[0]
    const result = await client.query('SELECT count(*) AS count FROM records WHERE account_id=$1', [job.account_id])
    await client.query('UPDATE report_jobs SET output=$1,finished_at=now() WHERE id=$2', [`record_count=${result.rows[0].count}\n`, job.id])
    return true
  })
}
