import { test } from 'node:test';
import assert from 'node:assert/strict';
import { verifyFirebasePassword, validateFirebaseHashConfig } from '../firebase_password.mjs';

// Public synthetic known-answer vector, published by Firebase; no account secret.
// https://github.com/firebase/scrypt/blob/master/README.md
const config = {
  algorithm: 'SCRYPT',
  signerKey: 'jxspr8Ki0RYycVU8zykbdLGjFQ3McFUH0uiiTvC8pVMXAn210wjLNmdZJzxUECKbm0QsEmYUSDzZvpjeJ9WmXA==',
  saltSeparator: 'Bw==', rounds: 8, memoryCost: 14,
};
const salt = '42xEC+ixf3L2lw==';
const expected = 'lSrfV15cpx95/sZS2W9c9Kp6i/LVgQNDNC/qzrCnh1SAyZvqmZqAjTdn3aoItz+VHjoZilo78198JAdRuid5lQ==';
test('Firebase official verifier vector accepts its password and rejects a changed password', async () => {
  assert.ok(await verifyFirebasePassword('user1password', expected, salt, config));
  assert.equal(await verifyFirebasePassword('user1password-wrong', expected, salt, config), false);
});
test('missing password hash, wrong algorithm and malformed base64 cannot authenticate', async () => {
  assert.equal(await verifyFirebasePassword('user1password', '', salt, config), false);
  assert.throws(() => validateFirebaseHashConfig({ ...config, algorithm: 'STANDARD_SCRYPT' }));
  await assert.rejects(verifyFirebasePassword('user1password', expected, 'not base64!', config));
});
