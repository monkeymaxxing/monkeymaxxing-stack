import {poolForDatabaseUrl} from './pg_with_multiple_database_servers.mjs';
import {readFile, readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
export const pool=poolForDatabaseUrl(process.env.DATABASE_URL,{max:5,idleTimeoutMillis:10000,query_timeout:12000});
pool.on('error',e=>console.error('database connection error',e.code||e.name));
export const query=(text,values=[])=>pool.query(text,values);
export async function transaction(fn){
 const c=await pool.connect();let failure;
 try{await c.query('BEGIN');await c.query("SET LOCAL idle_in_transaction_session_timeout='15s'");await c.query("SET LOCAL statement_timeout='10s'");const result=await fn(c);await c.query('COMMIT');return result;}
 catch(e){failure=e;await c.query('ROLLBACK').catch(()=>{});throw e;}finally{c.release(failure);}
}
export async function migrate(){
 const c=await pool.connect();
 try{
  await c.query('SELECT pg_advisory_lock(431504)');
  await c.query('CREATE TABLE IF NOT EXISTS schema_migrations(version text PRIMARY KEY,sha256 text NOT NULL,applied_at timestamptz NOT NULL DEFAULT now())');
  for(const name of (await readdir(new URL('./migrations/',import.meta.url))).filter(n=>/^\d+_.*\.sql$/.test(n)).sort()){
   const sql=await readFile(new URL('./migrations/'+name,import.meta.url),'utf8');const sha=createHash('sha256').update(sql).digest('hex');
   const old=await c.query('SELECT sha256 FROM schema_migrations WHERE version=$1',[name]);
   if(old.rowCount){if(old.rows[0].sha256!==sha)throw Error('Applied migration checksum changed: '+name);continue;}
   await c.query('BEGIN');try{await c.query("SET LOCAL lock_timeout='5s'");await c.query(sql);await c.query('INSERT INTO schema_migrations(version,sha256) VALUES($1,$2)',[name,sha]);await c.query('COMMIT');console.log('migration applied',name);}catch(e){await c.query('ROLLBACK');throw e;}
  }
 }finally{await c.query('SELECT pg_advisory_unlock(431504)').catch(()=>{});c.release();}
}
if(process.argv[1]===fileURLToPath(import.meta.url)){try{await migrate();}finally{await pool.end();}}
