import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

test('local uploads preserve exact bytes, refuse overwrite and path escape, and delete by key', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'portal-uploads-'));
  process.env.UPLOADS_DIR = directory;
  try {
    const { putObject, getObject, deleteObject } = await import('../storage.mjs');
    const bytes = Buffer.from([0, 1, 255, 10]);
    await putObject('private/customer/document', bytes);
    assert.deepEqual(await getObject('private/customer/document'), bytes);
    await assert.rejects(putObject('private/customer/document', Buffer.from('replacement')), { code: 'EEXIST' });
    assert.deepEqual(await getObject('private/customer/document'), bytes);
    await assert.rejects(putObject('../outside', bytes), /escapes UPLOADS_DIR/);
    await deleteObject('private/customer/document');
    await assert.rejects(getObject('private/customer/document'), { code: 'ENOENT' });
  } finally { await rm(directory, { recursive: true, force: true }); }
});
