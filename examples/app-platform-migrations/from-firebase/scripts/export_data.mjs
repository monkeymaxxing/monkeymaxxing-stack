import { readFile, realpath } from 'node:fs/promises';
import { resolve, relative, join, isAbsolute } from 'node:path';
import { createHash } from 'node:crypto';
import { validateFirebaseHashConfig } from '../firebase_password.mjs';

export const digest = bytes => createHash('sha256').update(bytes).digest('hex');
export async function readExport(directory = process.env.EXPORT_DIR) {
  if (!directory) throw new Error('Set EXPORT_DIR to the protected Firebase export directory.');
  const root = await realpath(resolve(directory));
  async function file(name) {
    if (typeof name !== 'string' || isAbsolute(name)) throw new Error('Export filenames must be relative.');
    const path = await realpath(resolve(root, name));
    const inside = relative(root, path);
    if (inside === '..' || inside.startsWith('../') || isAbsolute(inside)) throw new Error('Export file must remain inside EXPORT_DIR.');
    return readFile(path);
  }
  const manifest = JSON.parse(await file('manifest.json'));
  if (!manifest.project_id || !manifest.checksums || !manifest.exported_at) throw new Error('Export manifest must identify the source project, time and checksums.');
  for (const required of ['users.json','auth-config.json','firestore.json','objects.json']) {
    if (!manifest.checksums[required]) throw new Error('Export checksum missing for '+required);
  }
  for (const [name, expected] of Object.entries(manifest.checksums)) {
    if (!/^[a-f0-9]{64}$/.test(expected) || digest(await file(name)) !== expected) throw new Error('Export checksum mismatch: '+name);
  }
  const users = JSON.parse(await file('users.json')).users;
  const config = JSON.parse(await file('auth-config.json')).signIn?.hashConfig;
  const firestore = JSON.parse(await file('firestore.json'));
  const objects = JSON.parse(await file('objects.json'));
  validateFirebaseHashConfig(config);
  if (!Array.isArray(users) || !Array.isArray(objects) || !firestore.collections) throw new Error('Unsupported Firebase export shape.');
  const ids = new Set();
  for (const user of users) {
    if (!user.localId || !user.email || !user.passwordHash || !user.salt || ids.has(user.localId)) throw new Error('Export users need unique stable IDs, email and Firebase password verifiers. A missing verifier needs a separate password-reset plan.');
    ids.add(user.localId);
  }
  const collections=firestore.collections;
  for (const name of ['records','documents','jobs','controls','schedules','schema_migrations']) {
    if (!Array.isArray(collections[name])) throw new Error('Export collection missing: '+name);
  }
  for (const [name, rows] of Object.entries(collections)) {
    if (!Array.isArray(rows)) throw new Error('Export collection must be an array.');
    const seen=new Set();
    for (const row of rows) {
      if (!row.id || !row.data || seen.has(row.id)) throw new Error('Export collection has missing or duplicate document IDs: '+name);
      seen.add(row.id);
      if (['records','documents','jobs'].includes(name) && !ids.has(row.data.owner_id)) throw new Error('Export ownership does not match an exported Firebase UID.');
    }
  }
  const objectKeys=new Set();
  for (const object of objects) {
    if (!object.object_key || objectKeys.has(object.object_key) || !Number.isInteger(object.byte_length) || object.byte_length<0 || !/^[a-f0-9]{64}$/.test(object.sha256)) throw new Error('Export objects need unique keys, byte lengths and SHA-256 hashes.');
    objectKeys.add(object.object_key);
    const bytes=await file(object.file);
    if (bytes.length!==object.byte_length || digest(bytes)!==object.sha256) throw new Error('Export object checksum mismatch.');
  }
  for (const {data} of collections.documents) {
    const object=objects.find(object=>object.object_key===data.object_key);
    if (!object || object.sha256!==data.sha256 || object.byte_length!==data.byte_length) throw new Error('Firestore file metadata and exported object bytes disagree.');
  }
  return {manifest, users, config, collections, objects, file};
}
