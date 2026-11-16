import { pathToFileURL } from 'node:url';
import { pool, transaction } from './database.mjs';

export async function archiveReports() {
  return transaction(async client => {
    await client.query("SET LOCAL TIME ZONE 'UTC'");
    const occurrence = await client.query(`INSERT INTO schedule_runs(task_name,occurrence_date,archived_job_count)
      VALUES('archive_completed_reports',CURRENT_DATE,0) ON CONFLICT DO NOTHING RETURNING occurrence_date`);
    if (!occurrence.rowCount) return false;
    const archived = await client.query(`UPDATE report_jobs SET archived_at=now()
      WHERE state='COMPLETED' AND completed_at<now()-interval '30 days' AND archived_at IS NULL`);
    await client.query(`UPDATE schedule_runs SET archived_job_count=$1
      WHERE task_name='archive_completed_reports' AND occurrence_date=CURRENT_DATE`, [archived.rowCount]);
    return true;
  });
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try { await archiveReports(); console.log('Daily report archive checked.'); }
  catch { console.error('Daily report archive failed.'); process.exitCode = 1; }
  finally { await pool.end(); }
}
