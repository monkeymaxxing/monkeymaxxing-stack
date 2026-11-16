import { readFile, realpath, stat } from 'node:fs/promises'
import { resolve, sep } from 'node:path'
import { contentType, lookup } from 'mime-types'

// Read the mounted filesystem at request time, including retained releases.
// Only the named asset directories are public, even when a URL contains escapes.
export async function retainedAsset(path, method, publicDir, prefixes) {
  const encodedPath = path.split('?')[0]
  let decodedPath
  try { decodedPath = decodeURIComponent(encodedPath) }
  catch { return new Response(null, { status: 400 }) }
  const prefix = prefixes.find(prefix => decodedPath.startsWith(prefix))
  if (!prefix) return
  const segments = decodedPath.slice(prefix.length).split('/')
  if (decodedPath.includes('\\') || decodedPath.includes('\0') || segments.some(part => part.startsWith('.'))) {
    return new Response(null, { status: 403 })
  }
  if (method !== 'GET' && method !== 'HEAD') {
    return new Response(null, { status: 405, headers: { Allow: 'GET, HEAD' } })
  }
  try {
    const directory = await realpath(resolve(publicDir, '.' + prefix))
    const file = await realpath(resolve(directory, ...segments))
    // realpath also refuses a symlink that escapes the selected asset directory.
    if (!file.startsWith(directory + sep)) return new Response(null, { status: 403 })
    const metadata = await stat(file)
    if (!metadata.isFile()) return new Response(null, { status: 404 })
    // Vite fingerprints use eight characters; copied public assets use SHA-256 prefixes.
    // A public directory alone does not make an ordinary filename immutable.
    const fingerprinted = /(?:^[A-Za-z0-9_-]{8}|[.-][A-Za-z0-9_-]{8}|\.[a-f0-9]{12})\.[^.]+(?:\.(?:map|gz|br))*$/.test(segments.at(-1))
    const cacheControl = fingerprinted ? 'public,max-age=31536000,immutable' : prefix === '/assets/' ? null : 'no-store'
    return new Response(method === 'HEAD' ? null : await readFile(file), {
      headers: {
        'Content-Type': contentType(lookup(file) || 'application/octet-stream') || 'application/octet-stream',
        'Content-Length': String(metadata.size),
        ...(cacheControl ? { 'Cache-Control': cacheControl } : {}),
        'X-Content-Type-Options': 'nosniff',
      },
    })
  } catch (error) {
    if (['ENOENT', 'ENOTDIR'].includes(error.code)) return new Response(null, { status: 404 })
    throw error
  }
}
