import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {getDatabase} from '@netlify/database';
import {getStore} from '@netlify/blobs';
process.umask(0o077);
const required=name=>{const value=process.env[name];if(!value)throw Error(`Set ${name}.`);return value;};
const facts=JSON.parse(fs.readFileSync(required('NETLIFY_SOURCE_FACTS_FILE'),'utf8'));
const output=path.resolve(required('NETLIFY_EXPORT_DIR'));
if(fs.existsSync(output)&&fs.readdirSync(output).length)throw Error('Choose an empty NETLIFY_EXPORT_DIR to preserve earlier exports.');
if(!process.env.NETLIFY_AUTH_TOKEN)throw Error('Set NETLIFY_AUTH_TOKEN.');fs.mkdirSync(path.join(output,'objects'),{recursive:true,mode:0o700});
const auth={Authorization:`Bearer ${process.env.NETLIFY_AUTH_TOKEN}`};
const url=fs.readFileSync(required('NETLIFY_DATABASE_URL_FILE'),'utf8').trim();
const db=getDatabase({connectionString:url});
const client=await db.pool.connect();
const manifest={source_url:facts.site.ssl_url,site_id:facts.site.id,exported_at:new Date().toISOString(),table_counts:{},objects:[],source_repository:facts.source_repository,identity:{password_hashes_exported:false}};
try{
 await client.query('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY');
 const snapshot=(await client.query('SELECT pg_export_snapshot() AS snapshot')).rows[0].snapshot;
 const tables=(await client.query("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")).rows.map(x=>x.tablename);
 const audit={};
 for(const table of tables){if(!/^[a-z_]+$/.test(table))throw Error('Unexpected table name');audit[table]=(await client.query(`SELECT row_to_json(t) AS value FROM (SELECT * FROM "${table}" ORDER BY 1) t`)).rows.map(x=>x.value);manifest.table_counts[table]=audit[table].length;}
 fs.writeFileSync(path.join(output,'table_audit.json'),JSON.stringify(audit,null,2));
 manifest.table_audit_sha256=createHash('sha256').update(fs.readFileSync(path.join(output,'table_audit.json'))).digest('hex');
 const parsed=new URL(url);const env={...process.env,PGHOST:parsed.hostname,PGPORT:parsed.port||'5432',PGDATABASE:decodeURIComponent(parsed.pathname.slice(1)),PGUSER:decodeURIComponent(parsed.username),PGPASSWORD:decodeURIComponent(parsed.password),PGSSLMODE:'verify-full',PGSSLROOTCERT:'system',PGCONNECT_TIMEOUT:'15'};
 const args=['--format=custom','--no-owner','--no-acl','--schema=public','--snapshot='+snapshot,'--file='+path.join(output,'database.dump')];
 const dump=spawnSync(process.env.PG_DUMP_BIN||'pg_dump',args,{env,encoding:'utf8'});
 if(dump.status!==0){fs.writeFileSync(path.join(output,'pg_dump_error.txt'),String(dump.stderr||dump.error));throw Error('pg_dump failed; inspect privately without printing connection details.');}
 manifest.database_dump_sha256=createHash('sha256').update(fs.readFileSync(path.join(output,'database.dump'))).digest('hex');
 await client.query('COMMIT');
 const store=getStore({name:'private-documents',siteID:facts.site.id,token:process.env.NETLIFY_AUTH_TOKEN,consistency:'strong'});
 const listing=await store.list();if(listing.directories?.length)throw Error('Unexpected directory listing');
 const keys=new Set(listing.blobs.map(x=>x.key));
 for(const document of audit.documents){
  if(!keys.delete(document.object_key))throw Error('Document key missing from full native listing.');
  const bytes=Buffer.from(await store.get(document.object_key,{type:'arrayBuffer'}));const digest=createHash('sha256').update(bytes).digest('hex');
  if(digest!==document.sha256||bytes.length!==document.byte_length)throw Error('Object hash/length mismatch.');
  const file='objects/'+document.id+'.bin';fs.writeFileSync(path.join(output,file),bytes);
  manifest.objects.push({document_id:document.id,owner_id:document.owner_id,key:document.object_key,sha256:digest,byte_length:bytes.length,file});
 }
 if(keys.size)throw Error('Native store contains unaccounted objects.');
 for(const [name,suffix] of [['identity_users',`identity/${facts.identity_instance_id}/users?page=1&per_page=100`],['functions','functions']]){
  const r=await fetch(`https://api.netlify.com/api/v1/sites/${facts.site.id}/${suffix}`,{headers:auth});if(!r.ok)throw Error(name+' export failed.');
  const data=await r.json();fs.writeFileSync(path.join(output,name+'.json'),JSON.stringify(data,null,2));
  if(name==='identity_users'){
   if(!Array.isArray(data)||data.length!==audit.application_users.length)throw Error('Identity account count differs.');
   manifest.identity.user_ids=data.map(x=>x.id).sort();
   if(data.some(x=>x.encrypted_password||x.password_hash))throw Error('Unexpected verifier available: review privately before declaring a blocker.');
  }
  if(name==='functions')manifest.functions=data.functions.map(x=>({name:x.n,invocation_mode:x.im,schedule:x.schedule,runtime:x.r,region:x.rg}));
 }
 const envResponse=await fetch(`https://api.netlify.com/api/v1/accounts/${facts.site.account_slug}/env?site_id=${facts.site.id}`,{headers:auth});if(!envResponse.ok)throw Error('Variable-name inventory failed.');
 manifest.env_var_names=(await envResponse.json()).map(x=>x.key).sort();
 manifest.identity.password_reset_required=true;
 manifest.identity.password_verifier_export='No normal customer self-service export; optional Netlify support export only.';
 fs.writeFileSync(path.join(output,'manifest.json'),JSON.stringify(manifest,null,2));

 console.log('Exported relational snapshot, exact Blobs bytes, Identity metadata, functions and variable names. Returning users must set a new password through the one-time reset flow.');
}finally{client.release();await db.pool.end();}
