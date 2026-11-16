import test from 'node:test';
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';
import { ListObjectsV2Command, GetObjectCommand } from '@aws-sdk/client-s3';

const appDir = process.env.APP_DIR || '/app';
const { pool } = await import(pathToFileURL(appDir + '/database.mjs'));
const { storage } = await import(pathToFileURL(appDir + '/s3-storage.mjs'));
async function keys() {
  const result = new Set();
  let ContinuationToken;
  do {
    const page = await storage.send(new ListObjectsV2Command({ Bucket: process.env.BUCKET_NAME, ContinuationToken }));
    for (const object of page.Contents || []) result.add(object.Key);
    ContinuationToken = page.IsTruncated ? page.NextContinuationToken : undefined;
  } while (ContinuationToken);
  return result;
}
test('metadata rejection retains uploaded bytes for reconciliation', async () => {
  const base = process.env.APP_URL;
  const login = await fetch(base + '/api/login', { method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ email: 'barbara@example.com', password: process.env.FIXTURE_PASSWORD }) });
  assert.equal(login.status, 200);
  const cookie = login.headers.get('set-cookie').split(';')[0];
  const before = await keys();
  const count = (await pool.query('SELECT count(*) FROM documents')).rows[0].count;
  const bytes = Buffer.from('Synthetic upload retained after rejected metadata\n');
  try {
    await pool.query("CREATE FUNCTION reject_upload_test() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Synthetic rejected document'; END $$");
    await pool.query('CREATE TRIGGER reject_upload_test BEFORE INSERT ON documents FOR EACH ROW EXECUTE FUNCTION reject_upload_test()');
    const response = await fetch(base + '/api/documents?file_name=rejected.txt', {
      method: 'POST', headers: { cookie, 'content-type': 'application/octet-stream' }, body: bytes });
    assert.equal(response.status, 500);
    assert.equal((await pool.query('SELECT count(*) FROM documents')).rows[0].count, count);
    const added = [...await keys()].filter(key => !before.has(key));
    assert.equal(added.length, 1);
    const responseObject = await storage.send(new GetObjectCommand({ Bucket: process.env.BUCKET_NAME, Key: added[0] }));
    assert.deepEqual(Buffer.from(await responseObject.Body.transformToByteArray()), bytes);
  } finally {
    await pool.query('DROP TRIGGER IF EXISTS reject_upload_test ON documents');
    await pool.query('DROP FUNCTION IF EXISTS reject_upload_test()');
    await pool.end();
  }
});
