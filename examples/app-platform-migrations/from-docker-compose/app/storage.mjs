import { S3Client, PutObjectCommand, GetObjectCommand, DeleteObjectCommand } from '@aws-sdk/client-s3';
import { readFile, writeFile, mkdir, unlink } from 'node:fs/promises';
import { resolve, dirname, sep } from 'node:path';
const uploadsDir = process.env.UPLOADS_DIR && resolve(process.env.UPLOADS_DIR);
function localPath(key) {
  const path = resolve(uploadsDir, key);
  if (!path.startsWith(uploadsDir + sep)) throw new Error('Upload key leaves UPLOADS_DIR');
  return path;
}
export const storage = uploadsDir ? null : new S3Client({region:process.env.AWS_REGION || 'auto', endpoint:process.env.AWS_ENDPOINT_URL_S3, forcePathStyle:process.env.S3_FORCE_PATH_STYLE === 'true'});
export async function putObject(key, bytes) {
  if (uploadsDir) { const path=localPath(key); await mkdir(dirname(path), {recursive:true}); await writeFile(path,bytes); return; }
  await storage.send(new PutObjectCommand({Bucket:process.env.BUCKET_NAME,Key:key,Body:bytes,ContentType:'application/octet-stream'}));
}
export async function getObject(key) {
  if (uploadsDir) return readFile(localPath(key));
  const response=await storage.send(new GetObjectCommand({Bucket:process.env.BUCKET_NAME,Key:key}));
  return Buffer.from(await response.Body.transformToByteArray());
}
export async function deleteObject(key) {
  if (uploadsDir) return unlink(localPath(key));
  await storage.send(new DeleteObjectCommand({Bucket:process.env.BUCKET_NAME,Key:key}));
}
