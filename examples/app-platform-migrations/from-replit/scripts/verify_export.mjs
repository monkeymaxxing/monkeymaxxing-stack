import { readFile } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { createHash } from 'node:crypto';
const directory = resolve(process.env.EXPORT_DIR || 'migration-export');
const manifest = JSON.parse(await readFile(join(directory, 'manifest.json'), 'utf8'));
for (const [name, expected] of Object.entries(manifest.checksums)) {
  if (!['source.zip','database.dump','tables.json'].includes(name)) throw new Error('Unexpected export checksum filename.');
  const bytes = await readFile(join(directory,name));
  if (createHash('sha256').update(bytes).digest('hex') !== expected) throw new Error('Export checksum mismatch: ' + name);
}
for (const object of manifest.objects) {
  if (!/^objects\/[a-f0-9]{64}$/.test(object.file)) throw new Error('Unexpected export object filename.');
  const bytes = await readFile(join(directory,object.file));
  if (bytes.length !== object.byte_length || createHash('sha256').update(bytes).digest('hex') !== object.sha256) throw new Error('Export object checksum mismatch.');
}
console.log('Export archive files and all object checksums verified.');
