import { verifyExport } from './verify-export.mjs';
import { readFile } from 'node:fs/promises';
import { putObject, getObject } from '../storage.mjs';
import { createHash } from 'node:crypto';
const root=process.env.EXPORT_DIR||'/export';const {manifest}=await verifyExport(root);
for(const file of manifest.files){
 const bytes=await readFile(root+'/'+file.export_path);
 const matches=value=>value.length===file.byte_length&&createHash('sha256').update(value).digest('hex')===file.sha256;
 let existing;
 try{existing=await getObject(file.object_key);}catch(error){if(error.$metadata?.httpStatusCode!==404)throw error;}
 if(existing){if(!matches(existing))throw Error('Existing destination object differs; no overwrite performed');continue;}
 try{await putObject(file.object_key,bytes);}catch(error){if(error.$metadata?.httpStatusCode!==412)throw error;}
 if(!matches(await getObject(file.object_key)))throw Error('Destination object differs');
}
console.log('Imported and downloaded '+manifest.files.length+' verified private objects');
