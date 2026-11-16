import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, writeFileSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { inspectProject } from './inspect-project.mjs';

// An explicit directory keeps test artifacts under the caller's cleanup policy.
const root = process.env.MIGRATION_INSPECT_TEST_DIR || mkdtempSync(join(tmpdir(), 'lovable-inspect-'));
if (process.env.MIGRATION_INSPECT_TEST_DIR) mkdirSync(root, { recursive: false, mode: 0o700 });

test('current server stack is identified without exposing config values or executing scripts', () => {
  writeFileSync(join(root, 'package.json'), JSON.stringify({ dependencies: { '@tanstack/react-start': '1.0', '@supabase/supabase-js': '2.0' }, scripts: { build: 'echo DO_NOT_EXECUTE' } }));
  writeFileSync(join(root, 'app.ts'), 'const url = import.meta.env.VITE_SUPABASE_URL; const key = import.meta.env["VITE_SUPABASE_PUBLISHABLE_KEY"]; const secret = process.env["SERVER_SECRET"]; supabase.auth.getUser(); supabase.storage.from("private");');
  writeFileSync(join(root, '.env'), 'SECRET=DO_NOT_DISPLAY');
  symlinkSync(join(root, '.env'), join(root, 'linked-secret.ts'));
  const result = inspectProject(root), output = JSON.stringify(result);
  assert.equal(result.runtime, 'tanstack-start-server');
  assert.equal(result.supabase_sdk, true);
  assert.deepEqual(result.env_var_names, ['SERVER_SECRET', 'VITE_SUPABASE_PUBLISHABLE_KEY', 'VITE_SUPABASE_URL']);
  assert.deepEqual(result.dependency_evidence.auth, ['app.ts']);
  assert.ok(!output.includes('DO_NOT_DISPLAY') && !output.includes('DO_NOT_EXECUTE') && !output.includes('linked-secret'));
});

test('older Vite application and unknown runtime are distinct', () => {
  writeFileSync(join(root, 'package.json'), JSON.stringify({ dependencies: { react: '18.0', vite: '5.0' } }));
  assert.equal(inspectProject(root).runtime, 'react-vite-static');
  writeFileSync(join(root, 'package.json'), '{}');
  assert.equal(inspectProject(root).runtime, 'unknown-inspect-manually');
});


test('project roots and package manifests cannot bypass symlink exclusion', () => {
  const linkedRoot = join(root, 'linked-root');
  symlinkSync(root, linkedRoot);
  assert.throws(() => inspectProject(linkedRoot), /without symlinks/);
  const linkedPackage = join(root, 'linked-package');
  mkdirSync(linkedPackage);
  symlinkSync(join(root, 'package.json'), join(linkedPackage, 'package.json'));
  assert.throws(() => inspectProject(linkedPackage), /without symlinks/);
});
