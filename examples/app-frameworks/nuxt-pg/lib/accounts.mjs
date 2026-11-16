import { randomBytes } from 'node:crypto'
import bcrypt from 'bcryptjs'
import { sha256 } from './storage.mjs'

export function refuse(httpStatusCode, message) {
  const error = new Error(message); error.httpStatusCode = httpStatusCode; throw error
}
export function credentials(body = {}) {
  const { email, password } = body
  if (typeof email !== 'string' || email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) refuse(400, 'Enter a valid email address')
  if (typeof password !== 'string' || Buffer.byteLength(password) < 12 || Buffer.byteLength(password) > 72) refuse(400, 'Password must be 12 to 72 bytes')
  return { email:email.toLowerCase(), password }
}
export const passwordHash = password => bcrypt.hash(password, 12)
export const passwordMatches = (password, hash) => bcrypt.compare(password, hash)
export function sessionToken(request) {
  return /(?:^|;\s*)portal_session=([a-f0-9]{64})(?:;|$)/.exec(request.headers.get('cookie') || '')?.[1] || ''
}
export async function accountFor(client, request) {
  const { rows } = await client.query('SELECT a.id FROM accounts a JOIN sessions s ON a.id=s.account_id WHERE s.token_hash=$1 AND s.expires_at>now()', [sha256(sessionToken(request))])
  if (!rows.length) refuse(401, 'Log in first')
  return rows[0].id
}
export async function newSession(client, accountId) {
  const token = randomBytes(32).toString('hex')
  await client.query("INSERT INTO sessions(token_hash,account_id,expires_at) VALUES($1,$2,now()+interval '7 days')", [sha256(token), accountId])
  return `portal_session=${token}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=604800`
}
export const expiredCookie = 'portal_session=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0'
