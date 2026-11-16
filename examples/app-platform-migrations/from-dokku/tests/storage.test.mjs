import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
process.env.UPLOAD_DIR = await mkdtemp(join(tmpdir(),'dokku-private-uploads-'));
const { putObject, getObject, deleteObject } = await import('../app/storage.mjs');
test('private upload keys survive a byte-preserving local store', async()=>{
  const key = 'private/owner/document';
  const bytes = Buffer.from([0,1,255,10]);
  await putObject(key,bytes,'application/octet-stream');
  assert.deepEqual(await getObject(key),bytes);
  await assert.rejects(putObject(key,Buffer.from('overwrite'),'application/octet-stream'),{code:'EEXIST'});
  await deleteObject(key);
  await assert.rejects(getObject(key),{code:'ENOENT'});
});
test('a local object key cannot read or write outside the mount',async()=>{
  await assert.rejects(putObject('../outside',Buffer.from('escape'),'application/octet-stream'),/escapes/);
  await assert.rejects(getObject('/etc/passwd'),/escapes/);
  await assert.rejects(deleteObject('../outside'),/escapes/);
});
