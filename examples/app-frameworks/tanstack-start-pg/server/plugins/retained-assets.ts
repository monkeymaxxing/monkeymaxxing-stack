import { definePlugin } from 'nitro'
import { retainedAsset } from '../../lib/retained-assets.mjs'

export default definePlugin(app => {
  const frameworkFetch = app.fetch
  app.fetch = async request => {
    const response = await retainedAsset(new URL(request.url).pathname, request.method, '.output/public', ['/assets/'])
    return response ?? frameworkFetch(request)
  }
})
