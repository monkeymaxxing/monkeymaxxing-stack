import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { setTimeout as delay } from 'node:timers/promises';
import { pool } from '/app/database.mjs';
const run=(name,args=[])=>spawn(process.execPath,['/app/'+name,...args],{env:process.env,stdio:['ignore','pipe','pipe']});
async function exited(child){const [code]=await once(child,'exit');assert.equal(code,0,'Execution command completed');}
try {
 const before=(await pool.query('SELECT id,owner_id,state,output FROM report_jobs ORDER BY id')).rows;
 assert.equal(before.filter(j=>j.state==='PENDING').length,2);
 // Hold the actual worker after UPDATE, so killing that process tests transaction rollback.
 await pool.query("CREATE FUNCTION hold_report_test() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_advisory_xact_lock(20261105); PERFORM pg_sleep(30); RETURN NEW; END $$");
 await pool.query('CREATE TRIGGER hold_report_test AFTER UPDATE ON report_jobs FOR EACH ROW EXECUTE FUNCTION hold_report_test()');
 await pool.query('UPDATE controls SET jobs_paused=false WHERE id=1');
 const interrupted=run('jobs.mjs',['--once']);let locked=false;
 for(let n=0;n<200;n++){
  locked=(await pool.query("SELECT EXISTS(SELECT 1 FROM pg_locks WHERE locktype='advisory' AND objid=20261105 AND granted) AS locked")).rows[0].locked;
  if(locked)break;await delay(50);
 }
 assert.ok(locked,'Actual worker reached the uncommitted completion');
 const interruptedExit=once(interrupted,'exit');interrupted.kill('SIGKILL');await interruptedExit;
 await pool.query('DROP TRIGGER hold_report_test ON report_jobs');await pool.query('DROP FUNCTION hold_report_test()');
 assert.equal((await pool.query("SELECT count(*)::integer AS n FROM report_jobs WHERE state='PENDING'")).rows[0].n,2);
 const a=run('jobs.mjs',['--once']),b=run('jobs.mjs',['--once']);await Promise.all([exited(a),exited(b)]);
 const after=(await pool.query('SELECT id,owner_id,state,output FROM report_jobs ORDER BY id')).rows;
 assert.deepEqual(after.map(j=>[j.id,j.owner_id]),before.map(j=>[j.id,j.owner_id]));
 for(const job of after){
  assert.equal(job.state,'COMPLETED');
  const count=(await pool.query('SELECT count(*)::integer AS n FROM records WHERE owner_id=$1',[job.owner_id])).rows[0].n;
  assert.equal(job.output,'record_count='+count+'\n');
 }
 const first=run('schedule.mjs'),second=run('schedule.mjs');await Promise.all([exited(first),exited(second)]);
 const prior=(await pool.query('SELECT count(*)::integer AS n FROM scheduled_runs')).rows[0].n;
 await exited(run('schedule.mjs'));
 assert.equal((await pool.query('SELECT count(*)::integer AS n FROM scheduled_runs')).rows[0].n,prior);
 await exited(run('database.mjs'));await exited(run('database.mjs'));
 assert.equal((await pool.query('SELECT count(*)::integer AS n FROM schema_migrations')).rows[0].n,2);
 const sequence=(await pool.query("INSERT INTO migration_load(payload,payload_md5) VALUES('after switch',md5('after switch')) RETURNING id")).rows[0].id;
 assert.equal(sequence,'49156','Skipped identity values survived the switch');
 assert.equal((await pool.query("SELECT last_value,is_called FROM migration_unused")).rows[0].is_called,false);
 assert.equal((await pool.query("SELECT nextval('migration_descending') AS n")).rows[0].n,'-20');
 console.log(JSON.stringify({interrupted_worker_rolled_back:true,concurrent_reports_completed_once:after.length,schedule_idempotent:true,migration_ledger_preserved:true,sequence_default_after_switch:sequence,unused_sequence_preserved:true,descending_sequence_preserved:true}));
} finally {await pool.end();}
