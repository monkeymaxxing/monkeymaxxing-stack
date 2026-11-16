import {S3Client,PutObjectCommand,GetObjectCommand,DeleteObjectCommand} from '@aws-sdk/client-s3';
const client=new S3Client({endpoint:process.env.S3_ENDPOINT,region:process.env.S3_REGION||'auto',forcePathStyle:process.env.S3_FORCE_PATH_STYLE==='true',credentials:{accessKeyId:process.env.S3_ACCESS_KEY_ID,secretAccessKey:process.env.S3_SECRET_ACCESS_KEY},requestHandler:{requestTimeout:15000,connectionTimeout:10000},maxAttempts:1});
export const putDocument=(key,bytes)=>client.send(new PutObjectCommand({Bucket:process.env.S3_BUCKET,Key:key,Body:bytes,ContentType:'application/octet-stream'}));
export const deleteDocument=key=>client.send(new DeleteObjectCommand({Bucket:process.env.S3_BUCKET,Key:key}));
export async function getDocument(key){const r=await client.send(new GetObjectCommand({Bucket:process.env.S3_BUCKET,Key:key}));return Buffer.from(await r.Body.transformToByteArray());}
