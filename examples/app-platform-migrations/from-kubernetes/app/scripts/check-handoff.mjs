import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';

const base = process.env.APP_URL;
const path = process.env.CUSTOMER_STATE_FILE || '/export/customer-state.json';
const mode = process.argv[2];
async function request(route, { cookie, method = 'GET', body, raw, status = 200 } = {}) {
  const headers = {};
  if (cookie) headers.cookie = cookie;
  if (body !== undefined) { headers['content-type'] = 'application/json'; raw = JSON.stringify(body); }
  else if (raw !== undefined) headers['content-type'] = 'application/octet-stream';
  const response = await fetch(base + '/api/' + route, { method, headers, body: raw });
  assert.equal(response.status, status, method + ' ' + route);
  const bytes = Buffer.from(await response.arrayBuffer());
  let value;
  try { value = JSON.parse(bytes); } catch { value = bytes; }
  return { value, bytes, cookie: response.headers.get('set-cookie')?.split(';')[0] };
}
let customers;
if (mode === 'capture') {
  customers = [];
  for (const person of ['barbara', 'michael']) {
    const email = person + '@example.com';
    const login = await request('login', { method: 'POST', body: { email, password: process.env.FIXTURE_PASSWORD } });
    const cookie = login.cookie;
    const records = (await request('records', { cookie })).value;
    const documents = (await request('documents', { cookie })).value;
    const reports = (await request('reports', { cookie })).value;
    customers.push({ id: login.value.id, email, cookie, record: records[0], document: documents[0], report: reports[0] });
  }
  await writeFile(path, JSON.stringify(customers), { mode: 0o600, flag: 'wx' });
} else if (mode === 'verify') customers = JSON.parse(await readFile(path, 'utf8'));
else throw Error('Usage: check-handoff.mjs capture|verify');

for (const customer of customers) {
  const { cookie, id, document, record } = customer;
  assert.equal((await request('me', { cookie })).value.id, id, 'Existing session and stable identity');
  assert.equal((await request('records/' + record.id, { cookie })).value.description, record.description);
  const bytes = (await request('documents/' + document.id, { cookie })).bytes;
  assert.equal(createHash('sha256').update(bytes).digest('hex'), document.sha256);
  assert.equal(String(bytes.length), String(document.byte_length));
  const other = customers.find(person => person.id !== id);
  for (const route of ['records/' + other.record.id, 'documents/' + other.document.id, 'reports/' + other.report.id]) {
    await request(route, { cookie, status: 404 });
  }
  const temporary = (await request('records', { cookie, method: 'POST', body: { title: 'Handoff check' }, status: 201 })).value;
  await request('records/' + temporary.id, { cookie, method: 'PATCH', body: { title: 'Handoff checked', description: 'Synthetic mutation' } });
  await request('records/' + temporary.id, { cookie, method: 'DELETE', status: 204 });
  if (mode === 'verify') {
    const login = await request('login', { method: 'POST', body: { email: customer.email, password: process.env.FIXTURE_PASSWORD } });
    assert.equal(login.value.id, id, 'Returning password still authenticates');
    await request('logout', { method: 'POST', cookie: login.cookie });
  }
}
console.log(JSON.stringify({ customer_handoff: 'PASS', mode, customers: customers.length,
  checks: ['existing_sessions', 'stable_ids', 'original_private_bytes', 'ownership_refusals', 'create_update_delete'] }));
