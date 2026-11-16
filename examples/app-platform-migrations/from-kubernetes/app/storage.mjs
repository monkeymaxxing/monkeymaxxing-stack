import { mkdir, readFile, writeFile, unlink } from 'node:fs/promises';
import { resolve, dirname, sep } from 'node:path';
import * as s3 from './s3-storage.mjs';

// The source mounts private files. The destination uses the existing S3 interface.
const uploadsDir = process.env.UPLOADS_DIR && resolve(process.env.UPLOADS_DIR);
function filePath(key) {
  const path = resolve(uploadsDir, key);
  if (!path.startsWith(uploadsDir + sep)) throw Error('Document key escapes UPLOADS_DIR');
  return path;
}
export async function putObject(key, bytes) {
  if (!uploadsDir) return s3.putObject(key, bytes);
  const path = filePath(key);
  await mkdir(dirname(path), { recursive: true, mode: 0o700 });
  await writeFile(path, bytes, { flag: 'wx', mode: 0o600 });
}
export async function getObject(key) {
  return uploadsDir ? readFile(filePath(key)) : s3.getObject(key);
}
export async function deleteObject(key) {
  return uploadsDir ? unlink(filePath(key)) : s3.deleteObject(key);
}
