import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
const mode = process.argv[2];
assert.ok(['populate', 'verify'].includes(mode), 'Usage: customer-actions.mjs populate|verify');
const password = (await readFile(process.env.FIXTURE_PASSWORD_FILE, 'utf8')).trim();
const base = process.env.APP_URL;
const baselineFile = process.env.CUSTOMER_BASELINE_FILE;
const baseline = mode === 'verify' ? JSON.parse(await readFile(baselineFile, 'utf8')) : [];
const actors = [];
for (const [index, name] of ['barbara','michael'].entries()) {
  let cookie = '';
  async function request(path, method = 'GET', body, raw) {
    const headers = { Cookie: cookie };
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (raw !== undefined) { headers['Content-Type'] = 'application/octet-stream'; headers['X-File-Name'] = name + '-note.txt'; }
    const response = await fetch(new URL(path, base), { method, headers, body: raw ?? (body === undefined ? undefined : JSON.stringify(body)) });
    const setCookie = response.headers.get('set-cookie');
    if (setCookie) cookie = setCookie.split(';')[0];
    const bytes = Buffer.from(await response.arrayBuffer());
    return { status: response.status, bytes, value: response.headers.get('content-type')?.includes('application/json') ? JSON.parse(bytes) : undefined };
  }
  const login = await request(mode === 'populate' ? '/api/register' : '/api/login', 'POST', { email: name + '@example.com', password });
  assert.equal(login.status, mode === 'populate' ? 201 : 200);
  if (mode === 'populate') {
    const record = await request('/api/records', 'POST', { title: name + ' invoice', description: 'Original synthetic record' });
    const document = await request('/api/documents', 'POST', undefined, Buffer.from(name + ' synthetic document\n'));
    const report = await request('/api/reports', 'POST');
    assert.equal(record.status, 201); assert.equal(document.status, 201); assert.equal(report.status, 202);
    baseline.push({ owner: login.value.id, record: record.value.id, document: document.value.id, job: report.value.id,
      object_key: document.value.object_key, sha256: document.value.sha256 });
  }
  const original = baseline[index];
  assert.equal(login.value.id, original.owner);
  const record = await request('/api/records/' + original.record);
  assert.equal(record.status, 200); assert.equal(record.value.title, name + ' invoice');
  const document = await request('/api/documents/' + original.document);
  assert.equal(document.status, 200);
  assert.equal(document.bytes.toString(), name + ' synthetic document\n');
  assert.equal(createHash('sha256').update(document.bytes).digest('hex'), original.sha256);
  if (mode === 'verify') {
    const created = await request('/api/records','POST',{ title: 'Destination temporary record' });
    assert.equal(created.status,201);
    assert.equal((await request('/api/records/'+created.value.id,'PATCH',{title:'Updated destination record'})).status,200);
    assert.equal((await request('/api/records/'+created.value.id,'DELETE')).status,200);
    const uploaded = await request('/api/documents','POST',undefined,Buffer.from('Destination private bytes\n'));
    assert.equal(uploaded.status,201);
    assert.equal((await request('/api/documents/'+uploaded.value.id)).bytes.toString(),'Destination private bytes\n');
    assert.equal((await request('/api/reports','POST')).status,202);
  }
  actors.push(request);
}
for (const [index, request] of actors.entries()) {
  const other = baseline[1-index];
  for (const path of ['/api/records/'+other.record,'/api/documents/'+other.document,'/api/reports/'+other.job])
    assert.equal((await request(path)).status,404);
  assert.equal((await request('/api/records/'+other.record,'PATCH',{title:'Forbidden'})).status,404);
  assert.equal((await request('/api/records/'+other.record,'DELETE')).status,404);
  if (mode === 'verify') {
    const end = Date.now()+15000;
    let pending;
    do {
      const reports = await request('/api/reports');
      assert.equal(reports.status,200);
      pending = reports.value.filter(report => report.state !== 'COMPLETED');
      if (!pending.length) {
        assert.ok(reports.value.every(report => report.output === 'record_count=1\n'));
        break;
      }
      await new Promise(resolve=>setTimeout(resolve,100));
    } while(Date.now()<end);
    assert.equal(pending.length,0,'Destination worker must finish pending reports.');
  }
  assert.equal((await request('/api/logout','POST')).status,200);
  assert.equal((await request('/api/me')).status,401);
  assert.equal((await request('/api/login','POST',{email:(index ? 'michael' : 'barbara')+'@example.com',password:'definitely-wrong-password'})).status,401);
}
if (mode === 'populate') await writeFile(baselineFile, JSON.stringify(baseline,null,2)+'\n',{mode:0o600});
console.log(JSON.stringify({mode,existing_passwords:2,stable_account_ids:2,private_downloads:2,ownership_refusals:10,
  destination_writes_and_worker:mode==='verify',passed:true}));
