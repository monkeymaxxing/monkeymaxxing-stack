import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile, writeFile, unlink } from 'node:fs/promises'

process.env.APP_ORIGIN = 'https://portal.example.com'
const { app } = await import('../lib/app.mjs')

test('public fingerprinted CSS is immutable while ordinary assets and private responses are not', async t => {
  const plain = new URL('../assets/cache-test-ordinary.css', import.meta.url)
  await writeFile(plain, '/* mutable */', { flag: 'wx' })
  t.after(() => unlink(plain))
  const server = app.listen(0, '127.0.0.1')
  await new Promise(resolve => server.once('listening', resolve))
  t.after(() => new Promise(resolve => server.close(resolve)))
  const base = `http://127.0.0.1:${server.address().port}`
  const path = '/assets/portal.d055d47ecf33.css'
  const response = await fetch(base + path)
  assert.equal(response.status, 200)
  assert.equal(response.headers.get('cache-control'), 'public, max-age=31536000, immutable')
  assert.equal(response.headers.get('x-content-type-options'), 'nosniff')
  assert.deepEqual(Buffer.from(await response.arrayBuffer()), await readFile(new URL('..' + path, import.meta.url)))
  const head = await fetch(base + path, { method: 'HEAD' })
  assert.equal(head.headers.get('cache-control'), 'public, max-age=31536000, immutable')
  assert.equal(await head.text(), '')
  assert.equal((await fetch(base + '/assets/cache-test-ordinary.css')).headers.get('cache-control'), 'public, max-age=0')
  for (const path of ['/assets/%2e%2e%2fhome.html', '/assets/missing.123456abcdef.css']) {
    const denied = await fetch(base + path)
    assert.notEqual(denied.status, 200)
    assert.equal(denied.headers.get('cache-control'), 'no-store')
  }
  const privateResponse = await fetch(base + '/records', { method: 'POST', headers: { Origin: 'https://untrusted.example.com' } })
  assert.equal(privateResponse.status, 403)
  assert.equal(privateResponse.headers.get('cache-control'), 'no-store')
})
