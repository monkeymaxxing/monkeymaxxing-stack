// Restore to a separate destination bucket. Never point this at the source.
import { readFile } from 'node:fs/promises';
import { resolve, relative, join } from 'node:path';
import { createHash } from 'node:crypto';
import { upload, download } from '../storage.mjs';
const directory = resolve(process.env.EXPORT_DIR || 'migration-export');
const manifest = JSON.parse(await readFile(join(directory, 'manifest.json'), 'utf8'));
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
for (const object of manifest.objects) {
  const file = resolve(directory, object.file);
  if (relative(directory, file).startsWith('..')) throw new Error('Object file must stay inside the export directory.');
  const bytes = await readFile(file);
  if (bytes.length !== object.byte_length || digest(bytes) !== object.sha256) throw new Error('Export object checksum mismatch.');
  await upload(object.key, bytes);
  const restored = await download(object.key);
  if (!bytes.equals(restored)) throw new Error('Destination object differs from the export.');
}
console.log(`Imported and downloaded ${manifest.objects.length} objects with exact byte equality.`);
