import {readFile} from 'node:fs/promises';
import {resolve,sep} from 'node:path';
import {createHash} from 'node:crypto';
import {S3Client,PutObjectCommand,GetObjectCommand} from '@aws-sdk/client-s3';
if(process.env.FILE_STORAGE!=='s3')throw new Error('FILE_STORAGE=s3 is required');
if(process.env.RESTORE_CONFIRM!=='isolated-destination')throw new Error('Set RESTORE_CONFIRM=isolated-destination after checking the destination bucket');
const dir=resolve(process.env.EXPORT_DIR),root=resolve(dir,'objects');
const docs=JSON.parse(await readFile(resolve(dir,'objects.json'),'utf8'));
const client=new S3Client({endpoint:process.env.S3_ENDPOINT,region:process.env.S3_REGION||'us-east-1',forcePathStyle:true,credentials:{accessKeyId:process.env.S3_ACCESS_KEY_ID,secretAccessKey:process.env.S3_SECRET_ACCESS_KEY}});
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
for(const doc of docs){const p=resolve(root,doc.object_key);if(!p.startsWith(root+sep))throw new Error('Object key escapes export directory');
 const bytes=await readFile(p);if(hash(bytes)!==doc.sha256||bytes.length!==doc.byte_length)throw new Error('Export object checksum differs');
 // An existing object may be the same bytes from a prior import; never overwrite different bytes.
 try{const old=await client.send(new GetObjectCommand({Bucket:process.env.S3_BUCKET,Key:doc.object_key}));const existing=Buffer.from(await old.Body.transformToByteArray());if(hash(existing)!==doc.sha256)throw new Error('Destination object exists with different bytes');}
 catch(e){if(e.name!=='NoSuchKey'&&e.$metadata?.httpStatusCode!==404)throw e;await client.send(new PutObjectCommand({Bucket:process.env.S3_BUCKET,Key:doc.object_key,Body:bytes}));}
 const output=await client.send(new GetObjectCommand({Bucket:process.env.S3_BUCKET,Key:doc.object_key}));const actual=Buffer.from(await output.Body.transformToByteArray());
 if(hash(actual)!==doc.sha256||actual.length!==doc.byte_length)throw new Error('Imported object checksum differs');}
console.log('OBJECT_IMPORT_COMPLETE:',docs.length,'objects match exported SHA-256 values');
