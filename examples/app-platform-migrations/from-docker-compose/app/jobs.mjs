import { pool, transaction } from './database.mjs';
import { pathToFileURL } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';
export async function runJob() {
 return transaction(async client=>{
  const controls=await client.query('SELECT jobs_paused FROM controls WHERE id=1');
  if(controls.rows[0].jobs_paused) return null;
  const result=await client.query("SELECT id,owner_id FROM report_jobs WHERE state='PENDING' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1");
  if(!result.rowCount) return null;
  const job=result.rows[0];
  const count=await client.query('SELECT count(*)::integer AS count FROM records WHERE owner_id=$1',[job.owner_id]);
  await client.query("UPDATE report_jobs SET state='COMPLETED',output=$2,completed_at=now() WHERE id=$1",[job.id,`record_count=${count.rows[0].count}\n`]);
  return job.id;
 });
}
if(process.argv[1] && import.meta.url===pathToFileURL(process.argv[1]).href){
 let stopping=false; for(const signal of ['SIGINT','SIGTERM']) process.on(signal,()=>{stopping=true;});
 const once=process.argv.includes('--once');
 try {
  do {
   try {const id=await runJob();if(id)console.log('Completed report '+id);}
   catch(error){
    if(once)throw error;
    // A database switch can leave no writable server briefly. The next poll
    // reads durable queue state; report output and completion share a transaction.
    console.error('Report attempt failed:',error.code||error.name);
   }
   if(once)break;
   if(!stopping)await delay(1000);
  } while(!stopping);
 }
 finally {await pool.end();}
}
