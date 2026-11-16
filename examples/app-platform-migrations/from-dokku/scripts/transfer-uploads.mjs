// Run with the source web, workers and schedule stopped during the final copy.
import { readdir, readFile, writeFile, mkdir, lstat } from 'node:fs/promises';
import { resolve, join, sep } from 'node:path';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
const require = createRequire(new URL('../app/package.json', import.meta.url));
const { Client } = require('pg');
const { S3Client, PutObjectCommand, GetObjectCommand } = require('@aws-sdk/client-s3');
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const directory = resolve(process.env.EXPORT_DIR);
const mode = process.argv[2];
if (mode === 'export') {
  await mkdir(directory, { mode: 0o700 });
  await mkdir(join(directory, 'objects'), { mode: 0o700 });
  const root = resolve(process.env.UPLOAD_DIR);
  const objects = [];
  async function walk(parent = '') {
    for (const name of (await readdir(join(root, parent))).sort()) {
      const key = parent ? `${parent}/${name}` : name;
      const path = join(root, key);
      const stat = await lstat(path);
      if (stat.isDirectory()) await walk(key);
      else if (stat.isFile()) {
        const bytes = await readFile(path);
        const sha256 = hash(bytes);
        await writeFile(join(directory, 'objects', sha256), bytes, { mode: 0o600 });
        objects.push({ key, sha256, byte_length: bytes.length });
      } else throw new Error('Upload mount contains a non-regular file: ' + key);
    }
  }
  await walk();
  const client = new Client({ connectionString: process.env.DATABASE_URL });
  await client.connect();
  try {
    const documents = (await client.query('SELECT object_key,sha256,byte_length FROM documents ORDER BY object_key')).rows;
    for (const document of documents) {
      const object = objects.find(value => value.key === document.object_key);
      if (!object || object.sha256 !== document.sha256 || object.byte_length !== document.byte_length)
        throw new Error('Missing or changed private document bytes.');
    }
    await writeFile(join(directory, 'uploads.json'), JSON.stringify({ objects, document_count: documents.length }, null, 2) + '\n', { mode: 0o600 });
    console.log(JSON.stringify({ exported_objects: objects.length, documents: documents.length }));
  } finally { await client.end(); }
} else if (mode === 'import') {
  const storage = JSON.parse(await readFile(process.env.DESTINATION_STORAGE_CONFIG_FILE, 'utf8'));
  const client = new S3Client({ ...storage, maxAttempts: 1 });
  const manifest = JSON.parse(await readFile(join(directory, 'uploads.json'), 'utf8'));
  for (const object of manifest.objects) {
    if (!/^[a-f0-9]{64}$/.test(object.sha256)) throw new Error('Invalid object checksum.');
    const path = resolve(directory, 'objects', object.sha256);
    if (!path.startsWith(directory + sep)) throw new Error('Invalid export path.');
    const bytes = await readFile(path);
    if (bytes.length !== object.byte_length || hash(bytes) !== object.sha256) throw new Error('Export checksum differs.');
    await client.send(new PutObjectCommand({ Bucket: storage.bucket, Key: object.key, Body: bytes, IfNoneMatch: '*' }));
    const downloaded = await client.send(new GetObjectCommand({ Bucket: storage.bucket, Key: object.key }));
    const result = Buffer.from(await downloaded.Body.transformToByteArray());
    if (!result.equals(bytes)) throw new Error('Destination object bytes differ.');
  }
  console.log(JSON.stringify({ verified_destination_objects: manifest.objects.length }));
} else throw new Error('Usage: node scripts/transfer-uploads.mjs export|import');
