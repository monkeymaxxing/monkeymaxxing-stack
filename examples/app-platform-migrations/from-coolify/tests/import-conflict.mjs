// The deliberate corruption stays inside an explicitly disposable rehearsal.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import {S3Client,PutObjectCommand} from '@aws-sdk/client-s3';
import {getObject} from '../storage.mjs';
if(process.env.REHEARSAL_CONFIRM!=='disposable-destination')throw Error('Use a disposable destination');
const manifest=JSON.parse(await readFile(process.env.EXPORT_DIR+'/manifest.json','utf8'));
const file=manifest.files[0],original=await readFile(process.env.EXPORT_DIR+'/'+file.export_path);
const storage=new S3Client({region:process.env.AWS_REGION,endpoint:process.env.AWS_ENDPOINT_URL_S3,forcePathStyle:true});
const corrupt=Buffer.from('A different, newer destination object\n');
const write=bytes=>storage.send(new PutObjectCommand({Bucket:process.env.BUCKET_NAME,Key:file.object_key,Body:bytes}));
try{
 await write(corrupt);
 const result=spawnSync(process.execPath,['scripts/import-objects.mjs'],{cwd:new URL('../',import.meta.url),env:process.env,encoding:'utf8'});
 assert.notEqual(result.status,0,'Import refuses an existing key with different bytes');
 assert.deepEqual(await getObject(file.object_key),corrupt,'Importer did not overwrite different destination bytes');
}finally{await write(original);}
console.log('Conflicting destination object refused without overwriting; original test bytes restored');
