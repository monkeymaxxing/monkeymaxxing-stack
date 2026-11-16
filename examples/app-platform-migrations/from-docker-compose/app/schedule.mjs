import { pool, transaction } from './database.mjs';
try {
 const result=await transaction(async client=>{
  const stamp=await client.query("SELECT date_trunc('hour',now()) AS occurrence_at");
  const inserted=await client.query('INSERT INTO scheduled_runs(occurrence_at,expired_sessions_removed) VALUES($1,0) ON CONFLICT DO NOTHING RETURNING occurrence_at',[stamp.rows[0].occurrence_at]);
  if(!inserted.rowCount)return 'already completed';
  // Remove expired sessions hourly. Reports and outputs remain available for migration.
  const removed=await client.query('DELETE FROM sessions WHERE expires_at < now()');
  await client.query('UPDATE scheduled_runs SET expired_sessions_removed=$2 WHERE occurrence_at=$1',[stamp.rows[0].occurrence_at,removed.rowCount]);
  return `expired_sessions_removed=${removed.rowCount}`;
 });
 console.log('Hourly session cleanup: '+result);
} finally {await pool.end();}
