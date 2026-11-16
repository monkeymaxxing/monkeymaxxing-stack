if (!['development', 'staging'].includes(process.env.APP_ENV)) {
  throw new Error('seed-test-data refuses to run: APP_ENV must be development or staging, so production never gets test data');
}
const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== '--accounts' || !/^\d+$/.test(args[1]) || BigInt(args[1]) < 2n)) {
  throw new Error('Usage: seed-test-data [--accounts N]; --accounts must be a whole number of at least 2');
}
const accounts = args[1] || '2';
if (!process.env.FIXTURE_PASSWORD) throw new Error('FIXTURE_PASSWORD must be supplied at runtime.');
const base = process.env.APP_URL;
if (!base) throw new Error('APP_URL must name the running laptop or staging portal.');
for (const [person, title, description, bytes] of [
  ['barbara', 'Barbara invoice', 'First synthetic record', 'Barbara synthetic document\n'],
  ['michael', 'Michael invoice', 'Second synthetic record', 'Michael synthetic document\n'],
]) {
  let cookie = '';
  async function request(path, options = {}) {
    const response = await fetch(new URL(path, base), { ...options, headers: { Cookie: cookie, ...options.headers } });
    const setCookie = response.headers.get('set-cookie');
    if (setCookie) cookie = setCookie.split(';')[0];
    const value = await response.json();
    return { response, value };
  }
  const auth = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: `${person}@example.com`, password: process.env.FIXTURE_PASSWORD }) };
  let result = await request('/api/register', auth);
  if (result.response.status === 409) result = await request('/api/login', auth);
  if (!result.response.ok) throw new Error('Fixture account authentication failed.');
  const records = await request('/api/records');
  if (!records.response.ok) throw new Error('Fixture records could not be read.');
  if (!records.value.some(record => record.title === title)) {
    result = await request('/api/records', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title, description }) });
    if (!result.response.ok) throw new Error('Fixture record creation failed.');
  }
  const documents = await request('/api/documents');
  if (!documents.response.ok) throw new Error('Fixture documents could not be read.');
  if (!documents.value.some(document => document.file_name === `${person}-note.txt`)) {
    result = await request('/api/documents', { method: 'POST', headers: { 'Content-Type': 'application/octet-stream', 'X-File-Name': `${person}-note.txt` }, body: Buffer.from(bytes) });
    if (!result.response.ok) throw new Error('Fixture document upload failed.');
  }
  const reports = await request('/api/reports');
  if (!reports.response.ok) throw new Error('Fixture reports could not be read.');
  if (!reports.value.length) {
    result = await request('/api/reports', { method: 'POST' });
    if (!result.response.ok) throw new Error('Fixture report enqueue failed.');
  }
  result = await request('/api/logout', { method: 'POST' });
  if (!result.response.ok) throw new Error('Fixture logout failed.');
}
console.log('Test fixture checked.');

if (BigInt(accounts) > 2n) {
  const {pool,transaction} = await import('./database.mjs');
  const {default:bcrypt} = await import('bcryptjs');
  try {
    const passwordHash = await bcrypt.hash(process.env.FIXTURE_PASSWORD, 12);
    await transaction(async client => {
      await client.query('SELECT pg_advisory_xact_lock(7341206)');
      await client.query(`INSERT INTO users(id,email,password_hash)
        SELECT gen_random_uuid(), 'test-account-' || lpad(n::text, greatest(6,length(n::text)), '0') || '@example.com', $2
        FROM generate_series(3,$1::bigint) AS n ON CONFLICT (email) DO NOTHING`, [accounts,passwordHash]);
      await client.query(`INSERT INTO records(id,owner_id,title,description)
        SELECT gen_random_uuid(), u.id, 'Test record ' || n, 'Generated test record' FROM users u
        JOIN generate_series(3,$1::bigint) n ON u.email='test-account-' || lpad(n::text,greatest(6,length(n::text)),'0') || '@example.com'
        WHERE NOT EXISTS (SELECT 1 FROM records r WHERE r.owner_id=u.id)`, [accounts]);
    });
  } finally { await pool.end(); }
}
