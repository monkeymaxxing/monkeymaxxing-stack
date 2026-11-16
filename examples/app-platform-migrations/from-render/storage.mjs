import {readFile,writeFile,mkdir,unlink} from 'node:fs/promises';
import {resolve,dirname,sep} from 'node:path';
import {S3Client,PutObjectCommand,GetObjectCommand,DeleteObjectCommand} from '@aws-sdk/client-s3';
const mode=process.env.FILE_STORAGE||'disk';
if(!['disk','s3'].includes(mode))throw new Error('FILE_STORAGE must be disk or s3');
const root=resolve(process.env.UPLOADS_DIR||'/var/data/uploads');
const client=mode==='s3'?new S3Client({endpoint:process.env.S3_ENDPOINT,region:process.env.S3_REGION||'us-east-1',forcePathStyle:true,credentials:{accessKeyId:process.env.S3_ACCESS_KEY_ID,secretAccessKey:process.env.S3_SECRET_ACCESS_KEY}}):null;
function location(key){const p=resolve(root,key);if(!p.startsWith(root+sep))throw new Error('Invalid object key');return p;}
export async function putObject(key,bytes){if(client)return client.send(new PutObjectCommand({Bucket:process.env.S3_BUCKET,Key:key,Body:bytes}));const p=location(key);await mkdir(dirname(p),{recursive:true});await writeFile(p,bytes,{flag:'wx',mode:0o600});}
export async function getObject(key){if(client){const r=await client.send(new GetObjectCommand({Bucket:process.env.S3_BUCKET,Key:key}));return Buffer.from(await r.Body.transformToByteArray());}return readFile(location(key));}
export async function deleteObject(key){if(client)return client.send(new DeleteObjectCommand({Bucket:process.env.S3_BUCKET,Key:key}));return unlink(location(key));}
