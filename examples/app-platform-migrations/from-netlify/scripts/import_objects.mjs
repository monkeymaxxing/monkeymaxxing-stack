import fs from 'node:fs';
import path from 'node:path';
import { S3Client, GetObjectCommand, PutObjectCommand } from '@aws-sdk/client-s3';
import { verifyExport, sha256 } from './verify_export.mjs';
const required=name=>{const value=process.env[name];if(!value)throw Error(`Set ${name}.`);return value;};
try{
 const directory=required('NETLIFY_EXPORT_DIR');
 const {manifest}=verifyExport(directory);
 const bucket=required('S3_BUCKET');
 const client=new S3Client({endpoint:required('S3_ENDPOINT'),region:required('S3_REGION'),forcePathStyle:process.env.S3_FORCE_PATH_STYLE==='true'});
 for(const object of manifest.objects){
  const bytes=fs.readFileSync(path.join(directory,object.file));
  try{
   const result=await client.send(new GetObjectCommand({Bucket:bucket,Key:object.key}));
   const existing=Buffer.from(await result.Body.transformToByteArray());
   if(existing.length!==object.byte_length||sha256(existing)!==object.sha256)throw Error('The destination contains different bytes. The existing object was preserved.');
  }catch(error){
   if(!['NoSuchKey','NotFound'].includes(error.name)&&error.$metadata?.httpStatusCode!==404)throw error;
   await client.send(new PutObjectCommand({Bucket:bucket,Key:object.key,Body:bytes,ContentType:'application/octet-stream',IfNoneMatch:'*'}));
  }
  const download=await client.send(new GetObjectCommand({Bucket:bucket,Key:object.key}));
  const restored=Buffer.from(await download.Body.transformToByteArray());
  if(restored.length!==object.byte_length||sha256(restored)!==object.sha256)throw Error('Downloaded destination bytes differ.');
 }
 console.log(JSON.stringify({objects_verified:manifest.objects.length,identity_verifiers_imported:false}));
 client.destroy();
}catch(error){console.error(error.message);process.exitCode=1;}
