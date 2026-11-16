import bcrypt from 'bcryptjs';
import { scrypt, createCipheriv, timingSafeEqual } from 'node:crypto';
import { promisify } from 'node:util';

const derive = promisify(scrypt);
export function validateFirebaseHashConfig(config) {
  if (!config || config.algorithm !== 'SCRYPT' || !Number.isInteger(config.rounds) || config.rounds < 1 || config.rounds > 2 ** 32 - 1 ||
      !Number.isInteger(config.memoryCost) || config.memoryCost < 1 || config.memoryCost > 31) {
    throw new Error('A supported Firebase SCRYPT hash configuration is required.');
  }
  const signerKey = decodeBase64(config.signerKey);
  decodeBase64(config.saltSeparator);
  if (!signerKey.length) throw new Error('Firebase signer key must not be empty.');
  // Node's N and r options are unsigned 32-bit values; maxmem must be a safe integer.
  const maxmem = 128 * (2 ** config.memoryCost) * config.rounds + 128 * config.rounds + 1024 * 1024;
  if (!Number.isSafeInteger(maxmem)) throw new Error('Firebase hash parameters exceed Node scrypt memory support.');
  return { N: 2 ** config.memoryCost, r: config.rounds, p: 1, maxmem };
}
function decodeBase64(value) {
  if (typeof value !== 'string' || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value)) {
    throw new Error('A Firebase hash field is not canonical base64.');
  }
  const bytes=Buffer.from(value, 'base64');
  if(bytes.toString('base64')!==value)throw new Error('A Firebase hash field is not canonical base64.');
  return bytes;
}
export async function verifyFirebasePassword(password, passwordHash, passwordSalt, config) {
  const options = validateFirebaseHashConfig(config);
  const expected = decodeBase64(passwordHash);
  const salt = Buffer.concat([decodeBase64(passwordSalt), decodeBase64(config.saltSeparator)]);
  const signerKey = decodeBase64(config.signerKey);
  if (!expected.length || expected.length !== signerKey.length) return false;
  // Firebase's modified scrypt encrypts the project signer key with AES-256-CTR.
  // The derived key is scrypt(password, user salt || project separator, N, r, p=1, 64).
  // Official algorithm and independent known-answer vector: github.com/firebase/scrypt.
  const key = await derive(password, salt, 64, options);
  try {
    const cipher = createCipheriv('aes-256-ctr', key.subarray(0, 32), Buffer.alloc(16));
    const actual = Buffer.concat([cipher.update(signerKey), cipher.final()]);
    return actual.length === expected.length && timingSafeEqual(actual, expected);
  } finally { key.fill(0); }
}
export async function verifyUserPassword(password, user, config) {
  if (user.disabled) return false;
  if (user.password_algorithm === 'bcrypt') return bcrypt.compare(password, user.password_hash);
  if (user.password_algorithm === 'firebase_scrypt') return verifyFirebasePassword(password, user.firebase_password_hash, user.firebase_password_salt, config);
  return false;
}
