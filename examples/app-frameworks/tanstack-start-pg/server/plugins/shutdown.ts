import { definePlugin } from 'nitro'
import { closeDatabase } from '../../lib/database.mjs'

export default definePlugin(app => {
  app.hooks.hook('close', async () => {
    // The HTTP listener has drained. Close the pool, then release cluster IPC.
    // Disconnecting on SIGTERM itself can kill a request before its reply.
    await closeDatabase()
    if (process.connected) process.disconnect()
  })
})
