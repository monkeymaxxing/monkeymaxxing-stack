// Run on the source host with the app environment and upload mount accessible.
import { pool } from '../database.mjs';
import { mkdir, readFile, writeFile, readdir } from 'node:fs/promises';
import { resolve, relative, sep } from 'node:path';
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';
process.umask(0o077);
const root=resolve(process.env.EXPORT_DIR);
const uploads=resolve(process.env.UPLOADS_DIR);
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
await mkdir(root,{mode:0o700});await mkdir(root+'/objects',{mode:0o700});
const client=await pool.connect();
try {
 await client.query('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY');
 await client.query('SET LOCAL idle_in_transaction_session_timeout=120000');
 const controls=(await client.query('SELECT * FROM controls WHERE id=1')).rows[0];
 if(!controls.maintenance||!controls.jobs_paused)throw Error('Pause source mutations and report workers before export');
 const snapshot=(await client.query('SELECT pg_export_snapshot() AS id')).rows[0].id;
 const url=new URL(process.env.DATABASE_URL);
 const child=spawn('pg_dump',['--format=custom','--no-owner','--no-acl','--snapshot='+snapshot,'--file='+root+'/database.dump'],{env:{...process.env,PGHOST:url.hostname,PGPORT:url.port||'5432',PGUSER:decodeURIComponent(url.username),PGPASSWORD:decodeURIComponent(url.password),PGDATABASE:decodeURIComponent(url.pathname.slice(1))},stdio:['ignore','ignore','pipe']});
 child.stderr.resume();
 await new Promise((ok,bad)=>{child.once('error',bad);child.once('exit',code=>code===0?ok():bad(Error('pg_dump failed; check the private connection settings and client version')));});
 const tables=(await client.query("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")).rows.map(r=>r.tablename);
 const audit={};
 for(const table of tables){if(!/^[a-z_]+$/.test(table))throw Error('Unexpected fixture table name');audit[table]=(await client.query('SELECT * FROM "'+table+'" ORDER BY 1')).rows;}
 await writeFile(root+'/table-audit.json',JSON.stringify(audit,null,2)+'\n');
 const files=[];
 async function visit(directory){
  for(const entry of await readdir(directory,{withFileTypes:true})){
   const path=resolve(directory,entry.name);
   if(entry.isDirectory()){await visit(path);continue;}
   if(!entry.isFile())throw Error('Upload mount contains a non-regular file; inventory it separately');
   const key=relative(uploads,path).split(sep).join('/');
   const bytes=await readFile(path),digest=sha(bytes);
   await writeFile(root+'/objects/'+digest,bytes);
   files.push({object_key:key,byte_length:bytes.length,sha256:digest,export_path:'objects/'+digest});
  }
 }
 await visit(uploads);
 for(const document of audit.documents){const file=files.find(f=>f.object_key===document.object_key);if(!file||file.sha256!==document.sha256||String(file.byte_length)!==String(document.byte_length))throw Error('Source upload bytes differ from database metadata');}
 await client.query('COMMIT');
 const checksums={};for(const name of ['database.dump','table-audit.json',...files.map(f=>f.export_path)])checksums[name]=sha(await readFile(root+'/'+name));
 await writeFile(root+'/manifest.json',JSON.stringify({format_version:1,exported_at:new Date().toISOString(),database_version:(await pool.query('SELECT version() AS v')).rows[0].v,files,checksums},null,2)+'\n');
 console.log('Exported every public table and '+files.length+' mounted files, including unreferenced files');
} finally {await client.query('ROLLBACK').catch(()=>{});client.release();await pool.end();}
