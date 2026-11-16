import { pathToFileURL } from 'node:url';
import { pool, transaction } from './database.mjs';

export async function completeReport() {
  return transaction(async client => {
    const { rows } = await client.query("SELECT id,owner_id FROM report_jobs WHERE state='PENDING' ORDER BY created_at,id FOR UPDATE SKIP LOCKED LIMIT 1");
    if (!rows.length) return false;
    const job = rows[0];
    const count = await client.query('SELECT count(*)::integer AS total FROM records WHERE owner_id=$1', [job.owner_id]);
    await client.query("UPDATE report_jobs SET state='COMPLETED',output=$2,completed_at=now() WHERE id=$1", [job.id, `record_count=${count.rows[0].total}\n`]);
    return true;
  });
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  let stopping = false;
  process.on('SIGTERM', () => { stopping = true; });
  process.on('SIGINT', () => { stopping = true; });
  try {
    while (!stopping) {
      if (process.env.JOBS_PAUSED !== 'true') await completeReport();
      if (!stopping) await new Promise(resolve => setTimeout(resolve, 1000));
    }
  } catch { console.error('Report worker failed.'); process.exitCode = 1; }
  finally { await pool.end(); }
}
