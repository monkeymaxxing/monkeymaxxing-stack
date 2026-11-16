import {pool,transaction} from './database.mjs';
import {fileURLToPath} from 'node:url';
export async function runSchedule(at=new Date()){
 return transaction(async c=>{
  const control=await c.query('SELECT worker_paused FROM controls WHERE id=1 FOR SHARE');
  if(control.rows[0].worker_paused)return {paused:true};
  const occurrence=new Date(Math.floor(at.getTime()/300000)*300000).toISOString();
  const row=await c.query('INSERT INTO scheduled_runs(occurrence_at,archived_reports) VALUES($1,0) ON CONFLICT DO NOTHING RETURNING occurrence_at',[occurrence]);
  if(!row.rowCount)return {duplicate:true,occurrence_at:occurrence};
  const archived=await c.query("UPDATE jobs SET archived_at=now() WHERE state='COMPLETED' AND completed_at<now()-interval '30 days' AND archived_at IS NULL");
  await c.query('UPDATE scheduled_runs SET archived_reports=$2,completed_at=now() WHERE occurrence_at=$1',[occurrence,archived.rowCount]);
  return {occurrence_at:occurrence,archived_reports:archived.rowCount};
 });
}
if(process.argv[1]===fileURLToPath(import.meta.url)){
 try{console.log('scheduled archive completed',JSON.stringify(await runSchedule()));}
 finally{await pool.end();}
}
