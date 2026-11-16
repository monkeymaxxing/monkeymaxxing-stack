import { sendWebResponse } from 'h3'
import { retainedAsset } from '../../lib/retained-assets.mjs'

export default defineNitroPlugin(app => {
  app.hooks.hook('request', async event => {
    const response = await retainedAsset(event.node.req.url || '/', event.method, '.output/public', ['/_nuxt/', '/assets/'])
    if (response) await sendWebResponse(event, response)
  })
})
