import { createServerFn } from '@tanstack/react-start'
import { getRequest } from '@tanstack/react-start/server'
import { handle } from '../lib/http.mjs'

// Both transport adapters use the same validation, ownership checks and SQL.
// The call stays in this process; no HTTP request is sent back to the server.
export const listRecords = createServerFn({ method: 'GET' }).handler(async () => {
  const request = getRequest()
  return handle(new Request(new URL('/records', request.url), { headers: request.headers }))
})
export const createRecord = createServerFn({ method: 'POST' })
  .validator((data: unknown) => {
    if (!(data instanceof FormData)) throw new Error('Send a record form')
    return data
  })
  .handler(async ({ data }) => {
    const request = getRequest()
    const headers = new Headers(request.headers)
    headers.delete('content-type')
    headers.delete('content-length')
    return handle(new Request(new URL('/records', request.url), { method: 'POST', headers, body: data }))
  })
