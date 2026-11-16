import { S3Client, PutObjectCommand, GetObjectCommand, DeleteObjectCommand } from '@aws-sdk/client-s3';
const client = new S3Client({
  endpoint: process.env.S3_ENDPOINT,
  region: process.env.S3_REGION || 'auto',
  forcePathStyle: true,
  credentials: { accessKeyId: process.env.S3_ACCESS_KEY_ID, secretAccessKey: process.env.S3_SECRET_ACCESS_KEY },
});
const bucket = process.env.S3_BUCKET;
export async function upload(key, bytes) {
  await client.send(new PutObjectCommand({ Bucket: bucket, Key: key, Body: bytes, ContentType: 'application/octet-stream' }));
}
export async function download(key) {
  const result = await client.send(new GetObjectCommand({ Bucket: bucket, Key: key }));
  return Buffer.from(await result.Body.transformToByteArray());
}
export async function remove(key) {
  await client.send(new DeleteObjectCommand({ Bucket: bucket, Key: key }));
}
