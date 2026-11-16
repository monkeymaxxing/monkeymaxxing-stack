import { S3Client, PutObjectCommand, GetObjectCommand, DeleteObjectCommand } from '@aws-sdk/client-s3';
import { readFile, writeFile, mkdir, unlink } from 'node:fs/promises';
import { resolve, dirname, sep } from 'node:path';
const uploadDirectory = process.env.UPLOAD_DIR;
function localPath(key) {
  const root = resolve(uploadDirectory);
  const path = resolve(root, key);
  if (!path.startsWith(root + sep)) throw new Error('Object key escapes the private upload directory.');
  return path;
}
const client = uploadDirectory ? null : new S3Client({
  endpoint: process.env.S3_ENDPOINT,
  region: process.env.S3_REGION,
  forcePathStyle: process.env.S3_FORCE_PATH_STYLE === 'true',
  credentials: { accessKeyId: process.env.S3_ACCESS_KEY_ID, secretAccessKey: process.env.S3_SECRET_ACCESS_KEY },
  maxAttempts: 1,
});
export async function putObject(key, body, contentType) {
  if (uploadDirectory) {
    const path = localPath(key);
    await mkdir(dirname(path), { recursive: true, mode: 0o700 });
    await writeFile(path, body, { flag: 'wx', mode: 0o600 });
    return;
  }
  await client.send(new PutObjectCommand({ Bucket: process.env.S3_BUCKET, Key: key, Body: body, ContentType: contentType }));
}
export async function getObject(key) {
  if (uploadDirectory) return readFile(localPath(key));
  const result = await client.send(new GetObjectCommand({ Bucket: process.env.S3_BUCKET, Key: key }));
  return Buffer.from(await result.Body.transformToByteArray());
}
export async function deleteObject(key) {
  if (uploadDirectory) return unlink(localPath(key));
  await client.send(new DeleteObjectCommand({ Bucket: process.env.S3_BUCKET, Key: key }));
}
