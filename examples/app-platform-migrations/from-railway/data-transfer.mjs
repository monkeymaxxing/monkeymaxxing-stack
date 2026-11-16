import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
import pg from './app/node_modules/pg/lib/index.js';
import sdk from './app/node_modules/@aws-sdk/client-s3/dist-cjs/index.js';
import {poolForDatabaseUrl,singleServerDatabaseUrl} from './app/pg_with_multiple_database_servers.mjs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const failure=message=>Object.assign(new Error(message),{safeToPrint:true});
const {S3Client,ListObjectsV2Command,GetObjectCommand,PutObjectCommand,HeadObjectCommand}=sdk;
export const tables=['users','sessions','records','documents','jobs','controls','scheduled_runs','schema_migrations'];
const canonical=value=>JSON.stringify(value,(_,item)=>item&&typeof item==='object'&&!Array.isArray(item)?Object.fromEntries(Object.entries(item).sort(([a],[b])=>a.localeCompare(b))):item);
export const sha256=bytes=>createHash('sha256').update(bytes).digest('hex');
export async function snapshotDatabase(client){
 const snapshot={};
 for(const table of tables){
  const result=await client.query(`SELECT to_jsonb(t) AS row FROM ${table} t`);
  snapshot[table]=result.rows.map(r=>r.row).sort((a,b)=>canonical(a).localeCompare(canonical(b)));
 }
 return snapshot;
}
export function databaseChecks(snapshot){return Object.fromEntries(tables.map(table=>[table,{rows:snapshot[table].length,sha256:sha256(canonical(snapshot[table]))}]));}
const load=async file=>JSON.parse(await readFile(file,'utf8'));
const save=async(file,value)=>writeFile(file,JSON.stringify(value,null,2)+'\n',{mode:0o600});
function s3(config){return new S3Client({endpoint:config.endpoint,region:config.region||'auto',forcePathStyle:config.forcePathStyle===true,credentials:{accessKeyId:config.accessKeyId,secretAccessKey:config.secretAccessKey},maxAttempts:1,requestHandler:{connectionTimeout:10000,requestTimeout:15000}});}
function destinationStorage(){return {endpoint:process.env.S3_ENDPOINT,region:process.env.S3_REGION,bucketName:process.env.S3_BUCKET,forcePathStyle:process.env.S3_FORCE_PATH_STYLE==='true',accessKeyId:process.env.S3_ACCESS_KEY_ID,secretAccessKey:process.env.S3_SECRET_ACCESS_KEY};}
async function command(executable,args,options={}){
 // Child stderr may contain private data or connection values. Keep stderr off stdout.
 return new Promise((resolve,reject)=>{
  const child=spawn(executable,args,{env:options.env||process.env,stdio:['pipe','pipe','pipe']});
  const chunks=[];child.stdout.on('data',b=>chunks.push(b));child.stderr.resume();
  child.on('error',()=>reject(failure(`${executable} could not start`)));
  child.on('close',code=>code===0?resolve(Buffer.concat(chunks)):reject(failure(`${executable} failed with exit code ${code}; inspect settings without printing credentials`)));
  child.stdin.on('error',()=>{});child.stdin.end(options.input);
 });
}
function postgresEnv(config){return {...process.env,PGHOST:config.host,PGPORT:String(config.port),PGUSER:config.user,PGPASSWORD:config.password,PGDATABASE:config.database,PGSSLMODE:config.ssl?'require':'disable',PGCONNECT_TIMEOUT:'10'};}

async function exportData(dir){
 await mkdir(dir,{mode:0o700}); // Refuse overwriting an earlier export.
 const config=await load(process.env.SOURCE_DATABASE_CONFIG_FILE);
 const storage=await load(process.env.SOURCE_STORAGE_CONFIG_FILE);
 const client=new pg.Client({...config,connectionTimeoutMillis:10000,statement_timeout:10000});
 try{
  await client.connect();await client.query('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY');
  const snapshot=await snapshotDatabase(client);
  if(!snapshot.controls[0]?.worker_paused)throw failure('Source worker must already be paused before exporting a consistent queue');
  const exported=(await client.query('SELECT pg_export_snapshot() AS id')).rows[0].id;
  const dump=await command(process.env.PG_DUMP||'pg_dump',['--format=custom','--no-owner','--no-privileges','--snapshot',exported],{env:postgresEnv(config)});
  await writeFile(path.join(dir,'postgres.dump'),dump,{mode:0o600});
  await save(path.join(dir,'snapshot.json'),snapshot);
  const bucket=s3(storage);const objects=[];let continuation;
  await mkdir(path.join(dir,'objects'),{mode:0o700});
  do{
   const page=await bucket.send(new ListObjectsV2Command({Bucket:storage.bucketName,ContinuationToken:continuation}));
   for(const entry of page.Contents||[]){
    const response=await bucket.send(new GetObjectCommand({Bucket:storage.bucketName,Key:entry.Key}));
    const bytes=Buffer.from(await response.Body.transformToByteArray());
    const file=`objects/${sha256(entry.Key)}.bin`;
    await writeFile(path.join(dir,file),bytes,{mode:0o600});
    objects.push({key:entry.Key,file,byte_length:bytes.length,sha256:sha256(bytes)});
   }
   continuation=page.IsTruncated?page.NextContinuationToken:undefined;
   if(page.IsTruncated&&!continuation)throw failure('Bucket listing is truncated without a continuation token');
  }while(continuation);
  for(const document of snapshot.documents){
   const object=objects.find(o=>o.key===document.object_key);
   if(!object||object.sha256!==document.sha256||object.byte_length!==document.byte_length)throw failure('Source document bytes differ from database metadata; freeze uploads and repeat export');
  }
  const variableNames=await load(process.env.SOURCE_VARIABLE_NAMES_FILE);
  const manifest={exported_at:new Date().toISOString(),source_postgres_version:(await client.query('SHOW server_version')).rows[0].server_version,dump_sha256:sha256(dump),snapshot_sha256:sha256(await readFile(path.join(dir,'snapshot.json'))),database:databaseChecks(snapshot),objects,variable_names:variableNames,schedule:{expression:'*/5 * * * *',timezone:'UTC',command:'npm run cron'},source_worker_paused:true};
  await save(path.join(dir,'manifest.json'),manifest);
  await client.query('COMMIT');console.log('EXPORT_PASS database, accounts, jobs, schedule and object bytes saved privately');
 }finally{await client.end();}
}

async function restoreData(dir){
 const manifest=await load(path.join(dir,'manifest.json'));
 const dump=await readFile(path.join(dir,'postgres.dump'));
 if(sha256(dump)!==manifest.dump_sha256)throw failure('Database archive checksum mismatch');
 const snapshotBytes=await readFile(path.join(dir,'snapshot.json'));
 if(sha256(snapshotBytes)!==manifest.snapshot_sha256)throw failure('Snapshot checksum mismatch');
 const pool=poolForDatabaseUrl(process.env.DATABASE_URL,{statement_timeout:10000});
 try{
  const existing=await pool.query("SELECT tablename FROM pg_tables WHERE schemaname='public'");
  if(existing.rowCount)throw failure('Restore requires an empty destination database; use a new database');
  const sourceMajor=Number(manifest.source_postgres_version.split('.')[0]);
  const destinationMajor=Number((await pool.query('SHOW server_version')).rows[0].server_version.split('.')[0]);
  let sql=(await command(process.env.PG_RESTORE||'pg_restore',['--no-owner','--no-privileges','--file=-',path.join(dir,'postgres.dump')])).toString();
  let removedTransactionTimeout=false;
  if(sourceMajor===18&&destinationMajor===17){
   // PostgreSQL 17 has no transaction_timeout. Never rewrite data or migration SQL.
   const line='SET transaction_timeout = 0;';
   if(sql.split('\n').filter(row=>row===line).length!==1)throw failure('Expected one PostgreSQL 18 transaction_timeout setting');
   sql=sql.replace(line+'\n','');removedTransactionTimeout=true;
  }
  const url=new URL(await singleServerDatabaseUrl(process.env.DATABASE_URL));
  await command(process.env.PSQL||'psql',['-X','--set=ON_ERROR_STOP=1','--single-transaction'],{env:postgresEnv({host:url.hostname,port:url.port||5432,user:decodeURIComponent(url.username),password:decodeURIComponent(url.password),database:decodeURIComponent(url.pathname.slice(1))}),input:sql});
  const actual=databaseChecks(await snapshotDatabase(pool));
  if(canonical(actual)!==canonical(manifest.database))throw failure('Restored database rows differ from source snapshot');
  const config=destinationStorage();const bucket=s3(config);
  for(const object of manifest.objects){
   const objectPath=path.resolve(dir,object.file);
   if(!objectPath.startsWith(path.resolve(dir,'objects')+path.sep))throw failure('Object manifest path must stay inside export objects directory');
   const bytes=await readFile(objectPath);
   if(bytes.length!==object.byte_length||sha256(bytes)!==object.sha256)throw failure('Exported object checksum mismatch');
   let exists=false;
   try{await bucket.send(new HeadObjectCommand({Bucket:config.bucketName,Key:object.key}));exists=true;}catch(e){if(e.$metadata?.httpStatusCode!==404)throw e;}
   if(exists)throw failure('Destination object key already exists; restore into an empty bucket');
   await bucket.send(new PutObjectCommand({Bucket:config.bucketName,Key:object.key,Body:bytes}));
   const response=await bucket.send(new GetObjectCommand({Bucket:config.bucketName,Key:object.key}));
   if(sha256(Buffer.from(await response.Body.transformToByteArray()))!==object.sha256)throw failure('Destination object checksum mismatch');
  }
  await save(path.join(dir,'restore-result.json'),{checked_at:new Date().toISOString(),destination_postgres_major:destinationMajor,removed_transaction_timeout:removedTransactionTimeout,database:actual,object_count:manifest.objects.length,source_credentials_used:false});
  console.log('RESTORE_PASS exact database rows and object SHA-256 verified');
 }finally{await pool.end();}
}
if(process.argv[1]===fileURLToPath(import.meta.url)){
 process.umask(0o077);
 const mode=process.argv[2];const dir=process.env.EXPORT_DIR;
 try{
  if(!dir||!['export','restore'].includes(mode))throw failure('Use EXPORT_DIR with node data-transfer.mjs export or restore');
  const required=mode==='export'?['SOURCE_DATABASE_CONFIG_FILE','SOURCE_STORAGE_CONFIG_FILE','SOURCE_VARIABLE_NAMES_FILE']:['DATABASE_URL','S3_ENDPOINT','S3_REGION','S3_BUCKET','S3_ACCESS_KEY_ID','S3_SECRET_ACCESS_KEY'];
  for(const name of required)if(!process.env[name])throw failure(`${name} is required`);
  if(mode==='export')await exportData(dir);else await restoreData(dir);
 }catch(error){console.error('TRANSFER_FAILED',error.safeToPrint?error.message:error.code||error.name);process.exitCode=1;}
}
