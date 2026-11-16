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

// PostgreSQL serializes daily scheduling across every job process.
// A stopped process leaves the uncommitted day available to another process.
export async function runDueSchedule() {
  return transaction(async client => {
    await client.query('SELECT pg_advisory_xact_lock(61409330)')
    const due = await client.query(`INSERT INTO scheduled_task_runs(task_name,affected_reports,scheduled_for)
      SELECT 'archive_old_reports',0,(now() AT TIME ZONE 'UTC')::date
      WHERE (now() AT TIME ZONE 'UTC')::time >= time '03:00'
      ON CONFLICT(scheduled_for) DO NOTHING RETURNING id`)
    if (!due.rowCount) return false
    const archived = await client.query(`UPDATE report_jobs SET archived_at=now()
      WHERE finished_at < now()-interval '30 days' AND archived_at IS NULL`)
    await client.query('UPDATE scheduled_task_runs SET affected_reports=$1 WHERE id=$2', [archived.rowCount,due.rows[0].id])
    return true
  })
}

export async function archiveReports() {
  return transaction(async client => {
    const result = await client.query(`UPDATE report_jobs SET archived_at=now()
      WHERE finished_at < now()-interval '30 days' AND archived_at IS NULL`)
    await client.query(`INSERT INTO scheduled_task_runs(task_name,affected_reports)
      VALUES('archive_old_reports',$1)`,[result.rowCount])
    return result.rowCount
  })
}
