import { closeDatabase } from '../../lib/database.mjs'
export default defineNitroPlugin(app => { app.hooks.hook('close', closeDatabase) })
