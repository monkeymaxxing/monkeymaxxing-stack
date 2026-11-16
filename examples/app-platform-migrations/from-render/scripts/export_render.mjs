// Run from the source project with its existing pg dependency and disk attached.
import pg from 'pg';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import {resolve,dirname,sep} from 'node:path';
import {createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
process.umask(0o077);
const directory=resolve(process.env.EXPORT_DIR||'migration-export');
const uploads=resolve(process.env.UPLOADS_DIR||'/var/data/uploads');
const client=new pg.Client({connectionString:process.env.DATABASE_URL,statement_timeout:10000});
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
await mkdir(directory,{mode:0o700});
try{
 await client.connect();await client.query('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY');
 const controls=(await client.query('SELECT * FROM controls WHERE id=1')).rows[0];
 if(!controls?.maintenance||!controls.worker_paused||!controls.scheduler_paused)throw new Error('Pause source mutations, workers and schedules before exporting');
 const snapshot=(await client.query('SELECT pg_export_snapshot() AS snapshot')).rows[0].snapshot;
 const names=(await client.query("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")).rows.map(x=>x.tablename);
 const tables={};for(const name of names)tables[name]=(await client.query('SELECT * FROM "'+name.replaceAll('"','""')+'"')).rows;
 await writeFile(resolve(directory,'tables.json'),JSON.stringify(tables,null,2)+'\n',{mode:0o600});
 const databaseUrl=new URL(process.env.DATABASE_URL);
 const child=spawn('pg_dump',['--format=custom','--no-owner','--no-acl','--snapshot='+snapshot,'--file='+resolve(directory,'database.dump')],{env:{...process.env,PGDATABASE:decodeURIComponent(databaseUrl.pathname.slice(1)),PGHOST:databaseUrl.hostname,PGPORT:databaseUrl.port||'5432',PGUSER:decodeURIComponent(databaseUrl.username),PGPASSWORD:decodeURIComponent(databaseUrl.password),PGSSLMODE:databaseUrl.searchParams.get('sslmode')||'prefer'},stdio:['ignore','ignore','pipe']});
 let diagnostic='';child.stderr.on('data',b=>{diagnostic+=b.toString();});
 await new Promise((ok,bad)=>{child.once('error',bad);child.once('exit',code=>code===0?ok():bad(new Error('pg_dump failed; review private export environment and client version')));});
 const objects=[];
 for(const doc of tables.documents){
  const input=resolve(uploads,doc.object_key);if(!input.startsWith(uploads+sep))throw new Error('Document key escapes uploads directory');
  const bytes=await readFile(input);if(hash(bytes)!==doc.sha256||bytes.length!==doc.byte_length)throw new Error('Source document does not match database hash');
  const output=resolve(directory,'objects',doc.object_key);if(!output.startsWith(resolve(directory,'objects')+sep))throw new Error('Document key escapes export directory');
  await mkdir(dirname(output),{recursive:true,mode:0o700});await writeFile(output,bytes,{mode:0o600});objects.push({...doc});
 }
 await writeFile(resolve(directory,'objects.json'),JSON.stringify(objects,null,2)+'\n',{mode:0o600});
 const artifacts={};for(const name of ['database.dump','tables.json','objects.json'])artifacts[name]=hash(await readFile(resolve(directory,name)));
 await writeFile(resolve(directory,'export_manifest.json'),JSON.stringify({exported_at:new Date().toISOString(),database_snapshot:snapshot,table_counts:Object.fromEntries(Object.entries(tables).map(([name,rows])=>[name,rows.length])),objects,artifacts},null,2)+'\n',{mode:0o600});
 await client.query('COMMIT');console.log('EXPORT_COMPLETE: database snapshot, every application table, and verified disk objects');
}catch(e){await client.query('ROLLBACK').catch(()=>{});throw e;}finally{await client.end();}
