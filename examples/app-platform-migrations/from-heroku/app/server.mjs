import express from 'express';
import { randomUUID, createHash } from 'node:crypto';
import { pool } from './database.mjs';
import { hashPassword, verifyPassword, createSession, requireUser, hashToken, sessionToken, cookieSettings } from './auth.mjs';
import { putObject, getObject, deleteObject } from './storage.mjs';

export const app = express();
app.disable('x-powered-by');
app.set('trust proxy', 1);
app.use((request, response, next) => {
  response.set('X-Content-Type-Options', 'nosniff');
  response.set('Cache-Control', 'no-store');
  response.set('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'");
  if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method) && request.headers.origin &&
      request.headers.origin !== `${request.protocol}://${request.get('host')}`) {
    return response.status(403).json({ error: 'Use the portal website to submit this request.' });
  }
  next();
});
app.use(express.json({ limit: '16kb' }));
app.use(express.static(new URL('./web/', import.meta.url).pathname));
app.get('/healthz', async (_request, response) => {
  await pool.query('SELECT 1');
  response.json({ status: 'ok' });
});
function credentials(body) {
  const email = typeof body?.email === 'string' ? body.email.trim().toLowerCase() : '';
  const password = typeof body?.password === 'string' ? body.password : '';
  // bcrypt considers at most 72 bytes, so refuse passwords it would silently truncate.
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 254 ||
      password.length < 12 || Buffer.byteLength(password) > 72) return null;
  return { email, password };
}
app.post('/api/register', async (request, response) => {
  const input = credentials(request.body);
  if (!input) return response.status(400).json({ error: 'Enter an email and a password of at least 12 characters, at most 72 UTF-8 bytes.' });
  const user = { id: randomUUID(), email: input.email };
  const passwordHash = await hashPassword(input.password);
  const result = await pool.query(`INSERT INTO users(id,email,password_hash) VALUES($1,$2,$3)
    ON CONFLICT(email) DO NOTHING RETURNING id`, [user.id, user.email, passwordHash]);
  if (!result.rowCount) return response.status(409).json({ error: 'An account already uses this email.' });
  await createSession(user.id, response);
  response.status(201).json(user);
});
app.post('/api/login', async (request, response) => {
  const input = credentials(request.body);
  if (!input) return response.status(401).json({ error: 'Email or password is incorrect.' });
  const result = await pool.query('SELECT id,email,password_hash FROM users WHERE email=$1', [input.email]);
  if (!result.rowCount || !(await verifyPassword(input.password, result.rows[0].password_hash))) {
    return response.status(401).json({ error: 'Email or password is incorrect.' });
  }
  await createSession(result.rows[0].id, response);
  response.json({ id: result.rows[0].id, email: result.rows[0].email });
});
app.use('/api', requireUser);
app.get('/api/me', (request, response) => response.json(request.user));
app.post('/api/logout', async (request, response) => {
  await pool.query('UPDATE sessions SET revoked_at=now() WHERE token_hash=$1', [hashToken(sessionToken(request))]);
  response.clearCookie('portal_session', { ...cookieSettings, maxAge: undefined });
  response.json({ signed_out: true });
});
app.param('id', (request, response, next, id) => {
  if (!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(id)) {
    return response.status(404).json({ error: 'Item not found.' });
  }
  next();
});
app.get('/api/records', async (request, response) => {
  const result = await pool.query('SELECT * FROM records WHERE owner_id=$1 ORDER BY created_at,id', [request.user.id]);
  response.json(result.rows);
});
app.get('/api/records/:id', async (request, response) => {
  const result = await pool.query('SELECT * FROM records WHERE owner_id=$1 AND id=$2', [request.user.id, request.params.id]);
  response.status(result.rowCount ? 200 : 404).json(result.rows[0] || { error: 'Record not found.' });
});
function recordInput(body) {
  if (typeof body?.title !== 'string' || !body.title.trim() || body.title.length > 500) return null;
  if (body.description !== undefined && (typeof body.description !== 'string' || body.description.length > 10000)) return null;
  return { title: body.title.trim(), description: body.description };
}
app.post('/api/records', async (request, response) => {
  const input = recordInput(request.body);
  if (!input) return response.status(400).json({ error: 'Enter a title of 1 to 500 characters and an optional description of at most 10000 characters.' });
  const values = [randomUUID(), request.user.id, input.title];
  // Title-only requests work before and after migration 002.
  const result = input.description === undefined
    ? await pool.query('INSERT INTO records(id,owner_id,title) VALUES($1,$2,$3) RETURNING *', values)
    : await pool.query('INSERT INTO records(id,owner_id,title,description) VALUES($1,$2,$3,$4) RETURNING *', [...values, input.description]);
  response.status(201).json(result.rows[0]);
});
app.patch('/api/records/:id', async (request, response) => {
  const input = recordInput(request.body);
  if (!input) return response.status(400).json({ error: 'Enter a valid record title and description.' });
  const values = [request.user.id, request.params.id, input.title];
  const result = input.description === undefined
    ? await pool.query('UPDATE records SET title=$3 WHERE owner_id=$1 AND id=$2 RETURNING *', values)
    : await pool.query('UPDATE records SET title=$3,description=$4 WHERE owner_id=$1 AND id=$2 RETURNING *', [...values, input.description]);
  response.status(result.rowCount ? 200 : 404).json(result.rows[0] || { error: 'Record not found.' });
});
app.delete('/api/records/:id', async (request, response) => {
  const result = await pool.query('DELETE FROM records WHERE owner_id=$1 AND id=$2 RETURNING id', [request.user.id, request.params.id]);
  response.status(result.rowCount ? 200 : 404).json(result.rows[0] || { error: 'Record not found.' });
});
app.get('/api/documents', async (request, response) => {
  const result = await pool.query('SELECT * FROM documents WHERE owner_id=$1 ORDER BY created_at,id', [request.user.id]);
  response.json(result.rows);
});
app.post('/api/documents', express.raw({ type: 'application/octet-stream', limit: '1mb' }), async (request, response) => {
  const name = request.get('X-File-Name');
  if (!Buffer.isBuffer(request.body) || typeof name !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9._ -]{0,254}$/.test(name)) {
    return response.status(400).json({ error: 'Upload raw file bytes with Content-Type application/octet-stream and a simple X-File-Name.' });
  }
  const id = randomUUID();
  const key = `private/${request.user.id}/${id}`;
  const sha256 = createHash('sha256').update(request.body).digest('hex');
  await putObject(key, request.body, 'application/octet-stream');
  let result;
  try {
    result = await pool.query(`INSERT INTO documents(id,owner_id,file_name,object_key,sha256,byte_length,content_type)
      VALUES($1,$2,$3,$4,$5,$6,'application/octet-stream') RETURNING *`, [id, request.user.id, name, key, sha256, request.body.length]);
  } catch (error) {
    // A failed insert can have committed before its reply was lost. Keep any object whose metadata might exist.
    // Uncertain metadata failures are reconciled during export, never by automatically deleting object bytes.
    if (error.code?.startsWith('23')) await deleteObject(key);
    throw error;
  }
  response.status(201).json(result.rows[0]);
});
app.get('/api/documents/:id', async (request, response) => {
  const result = await pool.query('SELECT * FROM documents WHERE owner_id=$1 AND id=$2', [request.user.id, request.params.id]);
  if (!result.rowCount) return response.status(404).json({ error: 'Document not found.' });
  const document = result.rows[0];
  const body = await getObject(document.object_key);
  if (body.length !== document.byte_length || createHash('sha256').update(body).digest('hex') !== document.sha256) {
    throw new Error('Stored document checksum differs.');
  }
  response.attachment(document.file_name).type('application/octet-stream').send(body);
});
app.get('/api/reports', async (request, response) => {
  const result = await pool.query('SELECT * FROM report_jobs WHERE owner_id=$1 ORDER BY created_at,id', [request.user.id]);
  response.json(result.rows);
});
app.post('/api/reports', async (request, response) => {
  const result = await pool.query('INSERT INTO report_jobs(id,owner_id) VALUES($1,$2) RETURNING *', [randomUUID(), request.user.id]);
  response.status(202).json(result.rows[0]);
});
app.get('/api/reports/:id', async (request, response) => {
  const result = await pool.query('SELECT * FROM report_jobs WHERE owner_id=$1 AND id=$2', [request.user.id, request.params.id]);
  response.status(result.rowCount ? 200 : 404).json(result.rows[0] || { error: 'Report not found.' });
});
app.use((error, _request, response, _next) => {
  const status = error.type === 'entity.too.large' ? 413 : error.type === 'entity.parse.failed' ? 400 : 500;
  if (status === 500) console.error('A portal request failed.');
  response.status(status).json({ error: status === 413 ? 'The upload is too large.' : status === 400 ? 'The request body is invalid.' : 'The request failed. Check the service and try again after checking the previous result.' });
});
