import {transaction} from './database.mjs';
export async function runReport(){return transaction(async c=>{
 const control=(await c.query('SELECT worker_paused FROM controls WHERE id=1 FOR SHARE')).rows[0];if(control.worker_paused)return null;
 const job=(await c.query("SELECT id,owner_id FROM jobs WHERE state='PENDING' ORDER BY created_at,id FOR UPDATE SKIP LOCKED LIMIT 1")).rows[0];if(!job)return null;
 const count=(await c.query('SELECT count(*)::integer AS count FROM records WHERE owner_id=$1',[job.owner_id])).rows[0].count;
 await c.query("UPDATE jobs SET state='COMPLETED',output=$2,completed_at=now() WHERE id=$1",[job.id,'record_count='+count+'\n']);return job.id;
});}
export async function runSchedule(){return transaction(async c=>{
 if((await c.query('SELECT scheduler_paused FROM controls WHERE id=1 FOR SHARE')).rows[0].scheduler_paused)return false;
 await c.query("SELECT id FROM schedules WHERE id='archive_old_reports' FOR UPDATE");
 const claim=await c.query("INSERT INTO scheduled_runs(schedule_id,occurrence_date) VALUES('archive_old_reports',(now() AT TIME ZONE 'UTC')::date) ON CONFLICT DO NOTHING RETURNING schedule_id");
 if(!claim.rowCount)return false;
 await c.query("UPDATE jobs SET archived=true WHERE state='COMPLETED' AND completed_at<now()-interval '30 days'");
 await c.query("UPDATE schedules SET last_run_at=now() WHERE id='archive_old_reports'");return true;
});}
