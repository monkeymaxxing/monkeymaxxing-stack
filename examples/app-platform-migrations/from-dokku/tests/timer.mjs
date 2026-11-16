// Changes only synthetic fixture receipts and dates in the disposable rehearsal.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { pool } from '../app/database.mjs';
assert.equal(process.env.ALLOW_DISPOSABLE_REHEARSAL,'true','Use the disposable migration fixture only.');
try {
  const old = (await pool.query("SELECT id FROM report_jobs WHERE state='COMPLETED' ORDER BY created_at,id LIMIT 1")).rows[0];
  assert.ok(old,'Run the HTTP customer check and worker first.');
  await pool.query("DELETE FROM schedule_runs WHERE task_name='archive_completed_reports' AND occurrence_date=(now() AT TIME ZONE 'UTC')::date");
  await pool.query("UPDATE report_jobs SET completed_at=now()-interval '31 days',archived_at=NULL WHERE id=$1",[old.id]);
  const invocations = [0,1].map(()=>spawn('systemctl',['start','portal-archive-completed-reports.service'],{stdio:'ignore'}));
  const exits = invocations.map(child=>once(child,'exit'));
  for (const result of await Promise.all(exits)) assert.equal(result[0],0);
  const receipts = (await pool.query("SELECT archived_job_count FROM schedule_runs WHERE task_name='archive_completed_reports' AND occurrence_date=(now() AT TIME ZONE 'UTC')::date")).rows;
  assert.equal(receipts.length,1); assert.equal(receipts[0].archived_job_count,1);
  assert.ok((await pool.query('SELECT archived_at FROM report_jobs WHERE id=$1',[old.id])).rows[0].archived_at);
  console.log(JSON.stringify({overlapping_timer_starts:true,utc_receipts:1,archived_reports:1,passed:true}));
} finally {await pool.end();}
