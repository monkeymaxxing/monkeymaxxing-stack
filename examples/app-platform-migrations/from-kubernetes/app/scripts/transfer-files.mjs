import { readdir, readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve, relative, sep } from 'node:path';
import { createHash } from 'node:crypto';
import { PutObjectCommand, GetObjectCommand, HeadObjectCommand } from '@aws-sdk/client-s3';
import { storage } from '../s3-storage.mjs';

const directory = process.env.EXPORT_DIR || '/export';
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const mode = process.argv[2];
async function walk(directory) {
  const files = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) files.push(...await walk(path));
    else if (entry.isFile()) files.push(path);
    else throw Error('Upload export requires ordinary files and directories');
  }
  return files;
}
if (mode === 'export') {
  const root = resolve(process.env.UPLOADS_DIR);
  const audit = JSON.parse(await readFile(directory + '/table-audit.json', 'utf8'));
  const files = [];
  await mkdir(directory + '/objects', { mode: 0o700 });
  for (const path of await walk(root)) {
    const bytes = await readFile(path), sha256 = digest(bytes);
    const key = relative(root, path).split(sep).join('/');
    await writeFile(directory + '/objects/' + sha256, bytes, { mode: 0o600 });
    files.push({ key, sha256, byte_length: bytes.length });
  }
  for (const document of audit.documents) {
    const file = files.find(file => file.key === document.object_key);
    if (!file || file.sha256 !== document.sha256 || String(file.byte_length) !== String(document.byte_length)) {
      throw Error('Private bytes differ from document metadata');
    }
  }
  await writeFile(directory + '/files.json', JSON.stringify(files), { flag: 'wx', mode: 0o600 });
  console.log(JSON.stringify({ file_export: 'PASS', files: files.length, bytes: files.reduce((n, f) => n + f.byte_length, 0) }));
} else if (mode === 'import') {
  const files = JSON.parse(await readFile(directory + '/files.json', 'utf8'));
  for (const file of files) {
    if (!/^[a-f0-9]{64}$/.test(file.sha256)) throw Error('Invalid export object checksum');
    const bytes = await readFile(directory + '/objects/' + file.sha256);
    if (digest(bytes) !== file.sha256 || bytes.length !== file.byte_length) throw Error('Export file checksum mismatch');
    const location = { Bucket: process.env.BUCKET_NAME, Key: file.key };
    try {
      await storage.send(new HeadObjectCommand(location));
      throw Error('Destination object already exists: ' + file.key);
    } catch (error) { if (error.$metadata?.httpStatusCode !== 404) throw error; }
    await storage.send(new PutObjectCommand({ ...location, Body: bytes, IfNoneMatch: '*' }));
    const response = await storage.send(new GetObjectCommand(location));
    const restored = Buffer.from(await response.Body.transformToByteArray());
    if (digest(restored) !== file.sha256 || restored.length !== file.byte_length) throw Error('Imported file checksum mismatch');
  }
  console.log(JSON.stringify({ file_import: 'PASS', files: files.length }));
} else throw Error('Usage: transfer-files.mjs export|import');
