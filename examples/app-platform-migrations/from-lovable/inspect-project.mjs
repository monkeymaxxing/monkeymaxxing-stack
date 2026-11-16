#!/usr/bin/env node
// Read-only static inventory. Never executes project code or prints config values.
import { lstatSync, readFileSync, readdirSync } from 'node:fs';
import { join, relative } from 'node:path';
import { pathToFileURL } from 'node:url';

export function inspectProject(root) {
  if (lstatSync(root).isSymbolicLink() || lstatSync(join(root, 'package.json')).isSymbolicLink()) {
    throw new Error('Use a real project directory and package.json, without symlinks');
  }
  const pkg = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'));
  const dependencies = { ...pkg.dependencies, ...pkg.devDependencies };
  const current = Object.hasOwn(dependencies, '@tanstack/react-start');
  const runtime = current ? 'tanstack-start-server' : Object.hasOwn(dependencies, 'vite') && Object.hasOwn(dependencies, 'react') ? 'react-vite-static' : 'unknown-inspect-manually';
  const matches = { auth: [], storage: [], realtime: [], functions: [], jobs: [], connectors: [], worker_runtime: [] };
  const patterns = { auth: /supabase\.auth|auth\.uid\(|@clerk|oidc|signInWith/, storage: /\.storage\.from|storage\.objects|storage\.buckets/,
    realtime: /\.channel\(|postgres_changes|realtime/, functions: /functions\.invoke|Deno\.serve|serve\(/,
    jobs: /cron\.(schedule|unschedule)|pg_cron|SKIP LOCKED|scheduled\s*\(/i,
    connectors: /connector|lovable\.dev\/ai|ai\.gateway|lovable\.dev\/integrations/i,
    worker_runtime: /cloudflare:|@cloudflare|wrangler|ExecutionContext|\.env\.(get|[A-Z])/ };
  const envNames = new Set();
  function walk(dir) {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (entry.isSymbolicLink() || ['.git', 'node_modules', '.output', 'dist', '.env'].includes(entry.name) || entry.name.startsWith('.env.')) continue;
      const path = join(dir, entry.name);
      if (entry.isDirectory()) { walk(path); continue; }
      if (!/\.(ts|tsx|js|jsx|mjs|json|sql|toml)$/.test(entry.name) || entry.name.endsWith('lock.json')) continue;
      const source = readFileSync(path, 'utf8');
      const name = relative(root, path);
      for (const [kind, pattern] of Object.entries(patterns)) if (pattern.test(source)) matches[kind].push(name);
      for (const match of source.matchAll(/(?:import\.meta\.env|process\.env)(?:\.([A-Z][A-Z0-9_]*)|\[['"]([A-Z][A-Z0-9_]*)['"]\])/g)) envNames.add(match[1] || match[2]);
    }
  }
  walk(root);
  return { runtime, supabase_sdk: Object.hasOwn(dependencies, '@supabase/supabase-js'),
    lovable_build_config: Object.hasOwn(dependencies, '@lovable.dev/vite-tanstack-config'),
    build_script_present: typeof pkg.scripts?.build === 'string',
    env_var_names: [...envNames].sort(), dependency_evidence: matches,
    verification: 'Static inventory only. Build, services, auth, and complete dependency discovery are unverified.' };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    if (process.argv.length !== 3) throw new Error('Usage');
    console.log(JSON.stringify(inspectProject(process.argv[2]), null, 2));
  } catch { console.error('Project inventory failed. Pass an accessible project directory containing package.json.'); process.exitCode = 1; }
}
