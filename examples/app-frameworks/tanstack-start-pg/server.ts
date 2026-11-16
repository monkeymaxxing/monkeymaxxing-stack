import { defineServerEntry } from 'nitro'

// srvx defaults to an exclusive socket. Let Node cluster share its listener
// so all WEB_CONCURRENCY workers can use the assigned PORT.
export default defineServerEntry({ node: { exclusive: false }, gracefulShutdown: { gracefulTimeout: 25 } })
