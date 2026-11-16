import { cp } from 'node:fs/promises'

// Route tracing omits CLI-only files. Copy these explicit runtime inputs.
for (const directory of ['lib', 'scripts', 'migrations', 'public']) {
  await cp(directory, `.next/standalone/${directory}`, { recursive: true })
}
await cp('.next/static', '.next/standalone/.next/static', { recursive: true })
