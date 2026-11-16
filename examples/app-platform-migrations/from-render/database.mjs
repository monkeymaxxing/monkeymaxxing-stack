import {poolForDatabaseUrl} from './pg_with_multiple_database_servers.mjs';
import {readFile,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const url=process.env.DATABASE_URL;
if(!url)throw new Error('DATABASE_URL is required');
export const pool=poolForDatabaseUrl(url,{max:5,statement_timeout:10000,query_timeout:12000,idle_in_transaction_session_timeout:15000});
pool.on('error',()=>console.error('Idle database connection failed'));
export async function transaction(work){const c=await pool.connect();try{await c.query('BEGIN');const result=await work(c);await c.query('COMMIT');return result;}catch(e){await c.query('ROLLBACK').catch(()=>{});throw e;}finally{c.release();}}
export async function migrate(){const c=await pool.connect();try{
 await c.query('SELECT pg_advisory_lock(4918302)');
 await c.query('CREATE TABLE IF NOT EXISTS schema_migrations(version text PRIMARY KEY,sha256 text NOT NULL,applied_at timestamptz NOT NULL DEFAULT now())');
 for(const file of (await readdir(new URL('./migrations/',import.meta.url))).filter(x=>x.endsWith('.sql')).sort()){
  if(Number(file.slice(0,3))>Number(process.env.MIGRATION_LIMIT||2))continue;
  const sql=await readFile(new URL('./migrations/'+file,import.meta.url),'utf8'),hash=createHash('sha256').update(sql).digest('hex');
  const old=await c.query('SELECT sha256 FROM schema_migrations WHERE version=$1',[file]);
  if(old.rowCount){if(old.rows[0].sha256!==hash)throw new Error('Applied migration checksum differs: '+file);continue;}
  try{await c.query('BEGIN');await c.query(sql);await c.query('INSERT INTO schema_migrations(version,sha256) VALUES($1,$2)',[file,hash]);await c.query('COMMIT');}catch(e){await c.query('ROLLBACK');throw e;}
 }
 }finally{await c.query('SELECT pg_advisory_unlock(4918302)').catch(()=>{});c.release();}}
