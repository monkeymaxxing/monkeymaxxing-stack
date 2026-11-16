import test from 'node:test'
import assert from 'node:assert/strict'
import { validPassword, validEmail, passwordHash, passwordMatches, sessionToken } from '../lib/accounts.mjs'

test('password bounds count bytes, and established bcrypt hashes reject a different password', async () => {
  assert.equal(validPassword('x'.repeat(11)), false)
  assert.equal(validPassword('x'.repeat(72)), true)
  assert.equal(validPassword('é'.repeat(37)), false)
  const hash = await passwordHash('synthetic-test-password')
  assert.ok(await passwordMatches('synthetic-test-password', hash))
  assert.equal(await passwordMatches('different-test-password', hash), false)
})
test('email and session inputs reject malformed identities', () => {
  assert.ok(validEmail('barbara@example.com'))
  assert.equal(validEmail('missing-at.example.com'), false)
  assert.equal(sessionToken(new Request('https://portal.example.com', { headers: { cookie: 'portal_session=invalid' } })), undefined)
  assert.equal(sessionToken(new Request('https://portal.example.com', { headers: { cookie: `portal_session=${'a'.repeat(64)}; other=value` } })), 'a'.repeat(64))
})
