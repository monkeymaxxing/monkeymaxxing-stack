import {transaction,pool} from './database.mjs';
import {fileURLToPath} from 'node:url';
import {setTimeout as wait} from 'node:timers/promises';
import {runSchedule} from './cron.mjs';
export async function runJob(){return transaction(async c=>{
 // The shared lock lets concurrent workers claim different jobs while pause waits for in-flight jobs.
 const control=await c.query('SELECT worker_paused FROM controls WHERE id=1 FOR SHARE');
 if(control.rows[0].worker_paused)return null;
 const r=await c.query("SELECT id,owner_id FROM jobs WHERE state='PENDING' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1");
 if(!r.rowCount)return null;
 const job=r.rows[0];const count=await c.query('SELECT count(*)::integer AS record_count FROM records WHERE owner_id=$1',[job.owner_id]);
 await c.query("UPDATE jobs SET state='COMPLETED',output=$2,completed_at=now() WHERE id=$1",[job.id,`record_count=${count.rows[0].record_count}\n`]);return job.id;
});}
if(process.argv[1]===fileURLToPath(import.meta.url)){
 let stopped=false;
 for(const signal of ['SIGTERM','SIGINT'])process.on(signal,()=>{stopped=true;});
 while(!stopped){try{await runSchedule();const id=await runJob();if(id)console.log('report completed',id);else await wait(1000);}catch(e){console.error('worker error',e.code||e.name);await wait(1000);}}
 await pool.end();
}
