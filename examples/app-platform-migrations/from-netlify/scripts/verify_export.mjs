import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
export const sha256=bytes=>createHash('sha256').update(bytes).digest('hex');
export function verifyExport(directory) {
 const root=fs.realpathSync(directory);
 const read=name=>JSON.parse(fs.readFileSync(path.join(root,name),'utf8'));
 const manifest=read('manifest.json');const audit=read('table_audit.json');
 if(sha256(fs.readFileSync(path.join(root,'table_audit.json')))!==manifest.table_audit_sha256)throw Error('The row audit checksum differs.');
 if(sha256(fs.readFileSync(path.join(root,'database.dump')))!==manifest.database_dump_sha256)throw Error('The database dump checksum differs.');
 for(const [table,count] of Object.entries(manifest.table_counts))if(!Array.isArray(audit[table])||audit[table].length!==count)throw Error(`The table count differs: ${table}`);
 const ids=new Set(audit.application_users.map(x=>x.id));
 const native=read('identity_users.json');
 if(new Set(native.map(x=>x.id)).size!==ids.size||native.some(x=>audit.application_users.find(u=>u.id===x.id)?.email!==x.email))throw Error('Native account emails or unique IDs differ.');
 if(native.length!==ids.size||native.some(x=>!ids.has(x.id)))throw Error('Native Identity IDs differ from application ownership IDs.');
 for(const collection of ['records','documents','report_jobs'])for(const row of audit[collection])if(!ids.has(row.owner_id))throw Error(`Unknown owner in ${collection}.`);
 const keys=new Set();
 if(manifest.objects.length!==audit.documents.length)throw Error('Document and object counts differ.');
 for(const object of manifest.objects){
  const document=audit.documents.find(x=>x.id===object.document_id);
  if(!document||document.owner_id!==object.owner_id||document.object_key!==object.key||document.sha256!==object.sha256||document.byte_length!==object.byte_length||keys.has(object.key))throw Error('Document metadata or object ownership differs.');
  keys.add(object.key);
  const file=fs.realpathSync(path.join(root,object.file));if(!file.startsWith(root+path.sep))throw Error('An object path leaves the export directory.');
  const bytes=fs.readFileSync(file);if(bytes.length!==object.byte_length||sha256(bytes)!==object.sha256)throw Error('Exported object bytes differ.');
 }
 if(!audit.task_controls.every(x=>x.maintenance&&x.worker_paused&&x.scheduler_paused))throw Error('The source execution controls were not paused.');

 return {manifest,audit};
}
if(process.argv[1]===new URL(import.meta.url).pathname){
 try{
  const directory=process.env.NETLIFY_EXPORT_DIR;if(!directory)throw Error('Set NETLIFY_EXPORT_DIR to the private export directory.');
  if(process.argv.length>2)throw Error('This verifier uses the reset-required migration. No additional flags are needed.');
  const {manifest}=verifyExport(directory);
  console.log(JSON.stringify({data_export_verified:true,existing_password_login_proved:false,objects:manifest.objects.length,password_reset_required:true,identity_verifiers_exported:false}));
 }catch(error){console.error(error.message);process.exitCode=1;}
}
