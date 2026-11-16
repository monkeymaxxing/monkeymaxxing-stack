import { randomBytes } from 'node:crypto'
import { hashPassword, verifyPassword } from '@better-auth/utils/password'
import { database } from './database.mjs'
import { sha256 } from './storage.mjs'

export function validPassword(password) {
  return typeof password === 'string' && Buffer.byteLength(password) >= 12 && Buffer.byteLength(password) <= 72
}
export function validEmail(email) {
  return typeof email === 'string' && email.length <= 254 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}
export const passwordHash = password => hashPassword(password)
export const passwordMatches = (password, hash) => verifyPassword(hash, password)
export function sessionToken(request) {
  return /(?:^|;\s*)portal_session=([a-f0-9]{64})(?:;|$)/.exec(request.headers.get('cookie') || '')?.[1]
}
export async function accountFor(request) {
  const token = sessionToken(request)
  if (!token) return null
  const { rows } = await database().query('SELECT a.id, a.email FROM accounts a JOIN sessions s ON a.id=s.account_id WHERE s.token_hash=$1 AND s.expires_at>now()', [sha256(token)])
  return rows[0] || null
}
export async function newSession(accountId) {
  const token = randomBytes(32).toString('hex')
  await database().query("INSERT INTO sessions(token_hash,account_id,expires_at) VALUES($1,$2,now()+interval '7 days')", [sha256(token), accountId])
  return `portal_session=${token}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=604800`
}
export const expiredCookie = 'portal_session=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0'
