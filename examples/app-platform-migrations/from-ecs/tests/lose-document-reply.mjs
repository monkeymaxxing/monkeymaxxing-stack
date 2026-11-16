// Test-only boundary injection: the real INSERT commits, then its caller loses the reply.
import { pathToFileURL } from 'node:url';
const appDir = process.env.APP_DIR || new URL('../', import.meta.url).pathname;
const { pool } = await import(pathToFileURL(appDir + '/database.mjs'));
const query = pool.query.bind(pool);
pool.query = async (...arguments_) => {
  const result = await query(...arguments_);
  if (typeof arguments_[0] === 'string' && arguments_[0].startsWith('INSERT INTO documents(')) {
    const error = new Error('Injected loss of a committed document INSERT reply');
    error.code = 'ECONNRESET';
    throw error;
  }
  return result;
};
