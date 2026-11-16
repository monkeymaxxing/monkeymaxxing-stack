import { pool, databaseUrl } from '../database.mjs';
import { storage } from '../storage.mjs';
import { ListObjectsV2Command, GetObjectCommand } from '@aws-sdk/client-s3';
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
const root=process.env.EXPORT_DIR||'/tmp/ecs-export';process.umask(0o077);await mkdir(root,{mode:0o700});await mkdir(root+'/objects',{mode:0o700});
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const client=await pool.connect();
try{
 await client.query('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY');
 const controls=(await client.query('SELECT * FROM controls WHERE id=1')).rows[0];
 if(!controls.maintenance||!controls.jobs_paused)throw Error('Pause source writes and jobs before export');
 // pg_dump runs while this transaction keeps its exported snapshot alive.
 await client.query('SET LOCAL idle_in_transaction_session_timeout=120000');
 const snapshot=(await client.query('SELECT pg_export_snapshot() AS id')).rows[0].id;
 const url=new URL(databaseUrl);
 const dumpEnv={...process.env,PGHOST:url.hostname,PGPORT:url.port||'5432',PGUSER:decodeURIComponent(url.username),PGPASSWORD:decodeURIComponent(url.password),PGDATABASE:decodeURIComponent(url.pathname.slice(1))};
 const dump=spawnSync('pg_dump',['--format=custom','--no-owner','--no-acl','--no-publications','--no-subscriptions','--snapshot='+snapshot,'--file='+root+'/database.dump'],{encoding:'utf8',env:dumpEnv});
 if(dump.status!==0)throw Error('pg_dump failed: '+dump.stderr.replaceAll(databaseUrl,'[DATABASE_URL]'));
 const tables=(await client.query("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")).rows.map(r=>r.tablename);
 const audit={};for(const table of tables){if(!/^[a-z_]+$/.test(table))throw Error('Unexpected table name');audit[table]=(await client.query('SELECT * FROM "'+table+'" ORDER BY 1')).rows;}
 await client.query('COMMIT');await writeFile(root+'/table-audit.json',JSON.stringify(audit,null,2)+'\n');
 const files=[];let continuation;
 do{
  const listed=await storage.send(new ListObjectsV2Command({Bucket:process.env.BUCKET_NAME,ContinuationToken:continuation}));
  for(const item of listed.Contents||[]){const response=await storage.send(new GetObjectCommand({Bucket:process.env.BUCKET_NAME,Key:item.Key}));const bytes=Buffer.from(await response.Body.transformToByteArray());const digest=sha(bytes);await writeFile(root+'/objects/'+digest,bytes);files.push({object_key:item.Key,sha256:digest,byte_length:bytes.length,export_path:'objects/'+digest});}
  continuation=listed.IsTruncated?listed.NextContinuationToken:undefined;
 }while(continuation);
 const code=spawnSync('tar',['czf',root+'/code.tar.gz','--exclude=node_modules','--exclude=.git','-C',process.env.APP_DIR||'/app','.']);if(code.status!==0)throw Error('Code archive creation failed');
 await writeFile(root+'/source-inventory.json',await readFile(process.env.SOURCE_INVENTORY_FILE));
 const checksums={};for(const name of ['code.tar.gz','database.dump','table-audit.json','source-inventory.json',...files.map(f=>f.export_path)])checksums[name]=sha(await readFile(root+'/'+name));
 const runtimeSettings=new Set(['DATABASE_URL','PGHOST','PGPORT','PGUSER','PGPASSWORD','PGDATABASE','PGSSLMODE','PGSSLROOTCERT','QUEUE_BACKEND','SQS_QUEUE_URL','BUCKET_NAME','PORT','WEB_CONCURRENCY','NODE_ENV','COOKIE_SECURE','APP_ENV']);
 const manifest={format_version:1,exported_at:new Date().toISOString(),database_version:(await pool.query('SELECT version() AS v')).rows[0].v,source_bucket:process.env.BUCKET_NAME,files,checksums,env_var_names:Object.keys(process.env).filter(k=>runtimeSettings.has(k)||k.startsWith('AWS_')).sort()};
 await writeFile(root+'/manifest.json',JSON.stringify(manifest,null,2)+'\n');
 const tar=spawnSync('tar',['czf',root+'.tar.gz','-C',root,'.']);if(tar.status!==0)throw Error('Archive creation failed');
 console.log(JSON.stringify({export_archive:root+'.tar.gz',sha256:sha(await readFile(root+'.tar.gz')),tables:tables.length,files:files.length}));
}finally{client.release();await pool.end();}
