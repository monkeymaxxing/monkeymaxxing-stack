import pg from 'pg';
import {spawn} from 'node:child_process';
import {readFile,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
process.umask(0o077);
if(process.env.RESTORE_CONFIRM!=='isolated-destination')throw Error('Confirm an isolated destination with RESTORE_CONFIRM=isolated-destination');
const url=new URL(process.env.RESTORE_DATABASE_URL); // A single primary host for pg_restore, not the Stack server list.
const directory=resolve(process.env.EXPORT_DIR);
await readFile(resolve(directory,'database.dump'));
const client=new pg.Client({connectionString:process.env.RESTORE_DATABASE_URL,connectionTimeoutMillis:5000,statement_timeout:10000});
try{await client.connect();const existing=(await client.query("SELECT count(*)::integer n FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema')")).rows[0].n;if(existing!==0)throw Error('Destination database is not empty; select a new isolated database');}finally{await client.end();}
const env={...process.env,PGHOST:url.hostname,PGPORT:url.port||'5432',PGDATABASE:decodeURIComponent(url.pathname.slice(1)),PGUSER:decodeURIComponent(url.username),PGPASSWORD:decodeURIComponent(url.password),PGSSLMODE:url.searchParams.get('sslmode')||'prefer'};
const child=spawn('pg_restore',['--exit-on-error','--no-owner','--no-acl','--dbname='+env.PGDATABASE,resolve(directory,'database.dump')],{env,stdio:['ignore','ignore','pipe']});
let diagnostic='';child.stderr.on('data',b=>{diagnostic+=b.toString();});
const code=await new Promise((ok,bad)=>{child.once('error',bad);child.once('exit',ok);});
if(code!==0){await writeFile(resolve(directory,'restore_error.log'),diagnostic,{mode:0o600});throw Error('Database restore failed; inspect the protected restore_error.log and discard the partial destination');}
console.log('DATABASE_RESTORE_COMPLETE: isolated database restored without dropping existing objects');
