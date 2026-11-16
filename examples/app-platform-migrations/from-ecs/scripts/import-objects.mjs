import { verifyExport } from './verify-export.mjs';
import { readFile } from 'node:fs/promises';
import { storage, getObject } from '../storage.mjs';
import { PutObjectCommand } from '@aws-sdk/client-s3';
import { createHash } from 'node:crypto';
const root=process.env.EXPORT_DIR||'/export';const {manifest}=await verifyExport(root);
for(const file of manifest.files){const bytes=await readFile(root+'/'+file.export_path);await storage.send(new PutObjectCommand({Bucket:process.env.BUCKET_NAME,Key:file.object_key,Body:bytes,IfNoneMatch:'*'}));const downloaded=await getObject(file.object_key);if(createHash('sha256').update(downloaded).digest('hex')!==file.sha256)throw Error('Destination object differs');}
console.log('Imported and downloaded '+manifest.files.length+' verified private objects');
