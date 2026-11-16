import { createFileRoute } from '@tanstack/react-router'
import { handle } from '../../lib/http.mjs'

export const Route = createFileRoute('/$')({
  server: { handlers: { GET: ({ request }) => handle(request), POST: ({ request }) => handle(request) } },
})
