import { S3Client, PutObjectCommand, GetObjectCommand, DeleteObjectCommand } from '@aws-sdk/client-s3';
export const storage = new S3Client({region:process.env.AWS_REGION || 'auto', endpoint:process.env.AWS_ENDPOINT_URL_S3, forcePathStyle:process.env.S3_FORCE_PATH_STYLE === 'true'});
export async function putObject(key, bytes) { await storage.send(new PutObjectCommand({Bucket:process.env.BUCKET_NAME,Key:key,Body:bytes,ContentType:'application/octet-stream'})); }
export async function getObject(key) { const response=await storage.send(new GetObjectCommand({Bucket:process.env.BUCKET_NAME,Key:key}));return Buffer.from(await response.Body.transformToByteArray()); }
export async function deleteObject(key) { await storage.send(new DeleteObjectCommand({Bucket:process.env.BUCKET_NAME,Key:key})); }
