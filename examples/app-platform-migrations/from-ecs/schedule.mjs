import { pool, transaction } from './database.mjs';
import { pathToFileURL } from 'node:url';
export async function runSchedule() {
 return transaction(async client=>{
  if((await client.query('SELECT jobs_paused FROM controls WHERE id=1')).rows[0].jobs_paused)return 'paused';
  const stamp=await client.query("SELECT date_trunc('hour',now()) AS occurrence_at");
  const inserted=await client.query('INSERT INTO scheduled_runs(occurrence_at,expired_sessions_removed) VALUES($1,0) ON CONFLICT DO NOTHING RETURNING occurrence_at',[stamp.rows[0].occurrence_at]);
  if(!inserted.rowCount)return 'already completed';
  // Remove expired sessions hourly. Reports and outputs remain available for migration.
  const removed=await client.query('DELETE FROM sessions WHERE expires_at < now()');
  await client.query('UPDATE scheduled_runs SET expired_sessions_removed=$2 WHERE occurrence_at=$1',[stamp.rows[0].occurrence_at,removed.rowCount]);
  return `expired_sessions_removed=${removed.rowCount}`;
 });
}
if(process.argv[1] && import.meta.url===pathToFileURL(process.argv[1]).href){
 try {console.log('Hourly session cleanup: '+await runSchedule());} finally {await pool.end();}
}
