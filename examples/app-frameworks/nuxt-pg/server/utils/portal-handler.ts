import { defineEventHandler, toWebRequest } from 'h3'
import { handlePortal } from '../../lib/portal.mjs'
export default defineEventHandler(event => handlePortal(toWebRequest(event)))
