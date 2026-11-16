import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { resolve, sep } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
const require=createRequire(new URL('../app/package.json',import.meta.url));
const { S3Client, HeadObjectCommand, PutObjectCommand, GetObjectCommand }=require('@aws-sdk/client-s3');
const {pool}=await import(pathToFileURL(resolve('app/database.mjs')));
const config=JSON.parse(await readFile(process.env.DESTINATION_STORAGE_CONFIG_FILE,'utf8'));
const client=new S3Client(config.client);
const directory=resolve(process.env.SOURCE_UPLOADS_DIR);
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
try {
  const {rows}=await pool.query('SELECT object_key,sha256,byte_length FROM documents ORDER BY object_key');
  for (const row of rows) {
    const path=resolve(directory,row.object_key);
    if(!path.startsWith(directory+sep)) throw new Error('Document path leaves SOURCE_UPLOADS_DIR');
    const bytes=await readFile(path);
    if(bytes.length!==Number(row.byte_length)||hash(bytes)!==row.sha256) throw new Error('Source document bytes differ');
    let exists=false;
    try {await client.send(new HeadObjectCommand({Bucket:config.bucket,Key:row.object_key}));exists=true;}
    catch(error){if(error.$metadata?.httpStatusCode!==404)throw error;}
    if(!exists)await client.send(new PutObjectCommand({Bucket:config.bucket,Key:row.object_key,Body:bytes,IfNoneMatch:'*'}));
    const object=await client.send(new GetObjectCommand({Bucket:config.bucket,Key:row.object_key}));
    const restored=Buffer.from(await object.Body.transformToByteArray());
    if(restored.length!==bytes.length||hash(restored)!==row.sha256)throw new Error('Destination document bytes differ');
  }
  console.log(JSON.stringify({uploads_verified:rows.length}));
} finally {await pool.end();client.destroy();}
