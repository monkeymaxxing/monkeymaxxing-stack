import { defineConfig } from 'vite'
import { tanstackStart } from '@tanstack/react-start/plugin/vite'
import { nitro } from 'nitro/vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [tanstackStart(), nitro({ preset: 'node_server', serverEntry: './server.ts', plugins: ['./server/plugins/retained-assets.ts', './server/plugins/shutdown.ts'] }), react()],
})
