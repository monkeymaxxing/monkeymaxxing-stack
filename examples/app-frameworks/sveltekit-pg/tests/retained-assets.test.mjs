import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, mkdir, writeFile, symlink } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { retainedAsset } from '../lib/retained-assets.mjs'

test('retained files are read from disk with correct types and cannot escape asset directories', async () => {
  const root = await mkdtemp(join(tmpdir(), 'retained-assets-'))
  await mkdir(join(root, 'assets'))
  await writeFile(join(root, 'private.txt'), 'private')
  await writeFile(join(root, 'assets', 'old.js'), 'export const old = true;')
  await writeFile(join(root, 'assets', 'old.css'), 'body { color: red; }')
  await symlink(join(root, 'private.txt'), join(root, 'assets', 'escape.js'))
  const serve = (path, method = 'GET') => retainedAsset(path, method, root, ['/assets/'])
  for (const [path, type, bytes] of [
    ['/assets/old.js?version=old', /javascript/, 'export const old = true;'],
    ['/assets/old.css', /^text\/css/, 'body { color: red; }'],
  ]) {
    const response = await serve(path)
    assert.equal(response.status, 200)
    assert.match(response.headers.get('content-type'), type)
    assert.equal(await response.text(), bytes)
  }
  const head = await serve('/assets/old.js', 'HEAD')
  assert.equal(head.status, 200)
  assert.equal(head.headers.get('content-length'), '24')
  assert.equal(await head.text(), '')
  assert.equal((await serve('/assets/missing.js')).status, 404)
  assert.equal((await serve('/assets/old.js', 'POST')).status, 405)
  for (const path of ['/assets/../private.txt', '/assets/%2e%2e/private.txt', '/assets/a%2f..%2fprivate.txt', '/assets/%2eprivate', '/assets/%5c..%5cprivate.txt', '/assets/%00.js', '/assets/escape.js']) {
    assert.equal((await serve(path)).status, 403, path)
  }
  assert.equal((await serve('/assets/%zz')).status, 400)
  assert.equal(await serve('/private.txt'), undefined)
  assert.equal(await serve('/assets-other/old.js'), undefined)
  await writeFile(join(root, 'assets', 'retained-later.js'), 'old bytes mounted later')
  assert.equal(await (await serve('/assets/retained-later.js')).text(), 'old bytes mounted later')
})


test('fingerprinted retained files keep immutable caching and mutable files do not', async () => {
  const root = await mkdtemp(join(tmpdir(), 'retained-cache-'))
  const prefix = '/_app/immutable/'
  await mkdir(join(root, '.' + prefix), { recursive: true })
  const bytes = Buffer.from([0, 1, 255, 13, 10])
  for (const name of ['old-Ab12_C34.js', 'old-Ab12_C34.js.br', 'plain.js']) {
    await writeFile(join(root, '.' + prefix, name), bytes)
  }
  const serve = (name, method = 'GET') => retainedAsset(prefix + name, method, root, [prefix])
  const response = await serve('old-Ab12_C34.js')
  assert.equal(response.headers.get('cache-control'), 'public,max-age=31536000,immutable')
  assert.equal(response.headers.get('x-content-type-options'), 'nosniff')
  assert.deepEqual(Buffer.from(await response.arrayBuffer()), bytes)
  assert.equal((await serve('old-Ab12_C34.js.br')).headers.get('cache-control'), 'public,max-age=31536000,immutable')
  const head = await serve('old-Ab12_C34.js', 'HEAD')
  assert.equal(head.headers.get('cache-control'), 'public,max-age=31536000,immutable')
  assert.equal(head.headers.get('content-length'), String(bytes.length))
  assert.equal(await head.text(), '')
  assert.equal((await serve('plain.js')).headers.get('cache-control'), 'no-store')
})


test('copied content-hashed CSS is cached but ordinary public CSS is not', async () => {
  const root = await mkdtemp(join(tmpdir(), 'retained-public-cache-'))
  await mkdir(join(root, 'assets'))
  for (const name of ['portal.d055d47ecf33.css', 'portal.css']) {
    await writeFile(join(root, 'assets', name), 'body {}')
  }
  const serve = name => retainedAsset('/assets/' + name, 'GET', root, ['/assets/'])
  assert.equal((await serve('portal.d055d47ecf33.css')).headers.get('cache-control'), 'public,max-age=31536000,immutable')
  assert.equal((await serve('portal.css')).headers.get('cache-control'), null)
})


test('private API refusals still forbid caching', async t => {
  const previousOrigin = process.env.APP_ORIGIN
  process.env.APP_ORIGIN = 'https://portal.example.com'
  t.after(() => {
    if (previousOrigin === undefined) delete process.env.APP_ORIGIN
    else process.env.APP_ORIGIN = previousOrigin
  })
  const { handlePortal: handle } = await import('../lib/portal.mjs')
  const response = await handle(new Request('https://portal.example.com/records', {
    method: 'POST', headers: { Origin: 'https://untrusted.example.com' },
  }))
  assert.equal(response.status, 403)
  assert.equal(response.headers.get('cache-control'), 'no-store')
})
