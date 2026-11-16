import { readFile } from 'node:fs/promises';
// Compose mounts credentials as files. Stack supplies DATABASE_URL directly.
for (const name of ['DATABASE_URL', 'FIXTURE_PASSWORD']) {
  if (process.env[name + '_FILE']) {
    if (process.env[name]) throw new Error('Supply either ' + name + ' or ' + name + '_FILE');
    process.env[name] = (await readFile(process.env[name + '_FILE'], 'utf8')).trimEnd();
  }
}
