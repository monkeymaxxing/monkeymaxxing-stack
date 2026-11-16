import { defineEventHandler, setHeader } from 'h3'
export default defineEventHandler(event => {
 setHeader(event,'Cache-Control','no-store')
 setHeader(event,'X-Content-Type-Options','nosniff')
})
