import { createHash, randomUUID } from 'node:crypto'
import { S3Client, PutObjectCommand, GetObjectCommand } from '@aws-sdk/client-s3'

let client
function storage() {
  client ??= new S3Client({
    endpoint: process.env.R2_ENDPOINT, region: 'auto', forcePathStyle: true,
    credentials: { accessKeyId: process.env.R2_ACCESS_KEY_ID, secretAccessKey: process.env.R2_SECRET_ACCESS_KEY },
    requestHandler: { connectionTimeout: 3000, requestTimeout: 12000 }, maxAttempts: 1,
  })
  return client
}
export const sha256 = bytes => createHash('sha256').update(bytes).digest('hex')
export async function putDocument(accountId, fileName, bytes, fixtureKey) {
  const objectKey = fixtureKey || `${accountId}/${randomUUID()}`
  await storage().send(new PutObjectCommand({
    Bucket: process.env.R2_BUCKET, Key: objectKey, Body: bytes, ContentType: 'application/octet-stream',
  }))
  return { objectKey, fileName, sha256: sha256(bytes), byteCount: bytes.length }
}
export async function getDocument(row) {
  const result = await storage().send(new GetObjectCommand({ Bucket: process.env.R2_BUCKET, Key: row.object_key }))
  const bytes = Buffer.from(await result.Body.transformToByteArray())
  if (bytes.length !== Number(row.byte_count) || sha256(bytes) !== row.sha256) throw new Error('Document integrity check failed')
  return bytes
}

// Conditional writes protect an existing destination object. A failed database
// import may leave identical bytes, so a safe rerun verifies those bytes.
export async function importDocument(row, bytes) {
  try {
    await storage().send(new PutObjectCommand({
      Bucket: process.env.R2_BUCKET, Key: row.object_key, Body: bytes,
      ContentType: 'application/octet-stream', IfNoneMatch: '*',
    }))
  } catch (error) {
    if (error.$metadata?.httpStatusCode !== 412) throw error
  }
  await getDocument({object_key:row.object_key,sha256:row.sha256,byte_count:row.byte_size})
}
