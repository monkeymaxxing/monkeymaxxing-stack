import { transaction } from './database.mjs';

export async function runReport() {
  return transaction(async client=>{
    const controls=(await client.query('SELECT worker_paused FROM controls WHERE id=1 FOR SHARE')).rows[0];
    if(controls.worker_paused) return null;
    const job=(await client.query("SELECT id,owner_id FROM jobs WHERE state='PENDING' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1")).rows[0];
    if(!job) return null;
    await client.query("UPDATE jobs SET state='RUNNING' WHERE id=$1",[job.id]);
    const count=(await client.query('SELECT count(*)::text AS n FROM records WHERE owner_id=$1',[job.owner_id])).rows[0].n;
    const output='record_count='+count+'\n';
    await client.query("UPDATE jobs SET state='COMPLETED',output=$2,completed_at=now() WHERE id=$1",[job.id,output]);
    return job.id;
  });
}
export async function runSchedule(manual=false) {
  return transaction(async client=>{
    const controls=(await client.query('SELECT scheduler_paused FROM controls WHERE id=1 FOR SHARE')).rows[0];
    if(controls.scheduler_paused) return null;
    const schedule=(await client.query("SELECT * FROM schedules WHERE id='archive_old_reports' FOR UPDATE SKIP LOCKED")).rows[0];
    if(!schedule || (!manual && new Date(schedule.next_run_at)>new Date())) return null;
    const result=await client.query("UPDATE jobs SET archived=true WHERE state='COMPLETED' AND archived=false AND completed_at<now()-interval '30 days'");
    if(!manual) {
      await client.query('INSERT INTO scheduled_runs(schedule_id,occurrence_at,archived_count) VALUES($1,$2,$3)',[schedule.id,schedule.next_run_at,result.rowCount]);
      await client.query("UPDATE schedules SET next_run_at=next_run_at+interval '1 day',last_run_at=now() WHERE id=$1",[schedule.id]);
    } else await client.query('UPDATE schedules SET last_run_at=now() WHERE id=$1',[schedule.id]);
    return {archived_count:result.rowCount,manual};
  });
}
export function startBackgroundWork() {
  let reportRunning=false, scheduleRunning=false;
  const reportTick=async()=>{if(reportRunning)return;reportRunning=true;try {await runReport();} catch {console.error('Report worker failed. Pending transactions remain available.');}finally{reportRunning=false;}};
  const scheduleTick=async()=>{if(scheduleRunning)return;scheduleRunning=true;try {await runSchedule();} catch {console.error('Daily task failed. Next run remains in PostgreSQL.');}finally{scheduleRunning=false;}};
  void reportTick(); void scheduleTick();
  const timers=[setInterval(reportTick,1000),setInterval(scheduleTick,30000)];
  return ()=>timers.forEach(clearInterval);
}
