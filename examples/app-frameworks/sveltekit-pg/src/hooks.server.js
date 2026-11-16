import { closeDatabase } from '../lib/database.mjs'
process.on('sveltekit:shutdown', async () => {
  try { await closeDatabase() }
  finally { if (process.connected) process.disconnect() }
})
export async function handle({event, resolve}) {
  const response = await resolve(event)
  response.headers.set('Cache-Control','no-store')
  response.headers.set('X-Content-Type-Options','nosniff')
  return response
}
