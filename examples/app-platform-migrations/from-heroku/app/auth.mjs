import bcrypt from 'bcryptjs';
import { createHash, randomBytes } from 'node:crypto';
import { pool } from './database.mjs';

export const hashToken = token => createHash('sha256').update(token).digest('hex');
export const hashPassword = password => bcrypt.hash(password, 12);
export const verifyPassword = (password, hash) => bcrypt.compare(password, hash);
export const cookieSettings = {
  httpOnly: true, sameSite: 'strict', secure: process.env.COOKIE_SECURE === 'true',
  path: '/', maxAge: 7 * 86400 * 1000,
};
export function sessionToken(request) {
  return (request.headers.cookie || '').split(';').map(s => s.trim()).find(s => s.startsWith('portal_session='))?.slice(15) || '';
}
export async function createSession(ownerId, response) {
  const token = randomBytes(32).toString('hex');
  await pool.query("INSERT INTO sessions(token_hash,owner_id,expires_at) VALUES($1,$2,now()+interval '7 days')", [hashToken(token), ownerId]);
  response.cookie('portal_session', token, cookieSettings);
}
export async function requireUser(request, response, next) {
  const token = sessionToken(request);
  if (!/^[a-f0-9]{64}$/.test(token)) return response.status(401).json({ error: 'Sign in to continue.' });
  const result = await pool.query(`SELECT users.id,users.email FROM sessions JOIN users ON users.id=sessions.owner_id
    WHERE sessions.token_hash=$1 AND sessions.revoked_at IS NULL AND sessions.expires_at>now()`, [hashToken(token)]);
  if (!result.rowCount) return response.status(401).json({ error: 'Sign in to continue.' });
  request.user = result.rows[0];
  next();
}
