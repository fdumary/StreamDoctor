import test from 'node:test';
import assert from 'node:assert/strict';
import { errorMessage, observationPayload, request, setToken, hasSession } from '../src/services/api.js';

globalThis.sessionStorage = { setItem() {}, removeItem() {} };

test('observation payload preserves unknowns and converts measured pH', () => {
  assert.deepEqual(observationPayload({ observed_at: '2026-01-01T12:00:00Z', ph: '', clarity: 'unknown' }), { observed_at: '2026-01-01T12:00:00.000Z', ph: null, clarity: 'unknown' });
  assert.equal(observationPayload({ observed_at: '2026-01-01', ph: '7.2' }).ph, 7.2);
});

test('API uses bearer auth and preserves browser multipart boundary', async () => {
  setToken('test-session');
  const body = new FormData(); body.append('source', 'synthetic');
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/v1/reports/photo');
    assert.equal(options.headers.Authorization, 'Bearer test-session');
    assert.equal(options.headers['Content-Type'], undefined);
    assert.equal(options.body, body);
    return new Response(null, { status: 204 });
  };
  assert.equal(await request('/reports/photo', { method: 'POST', body }), null);
});

test('expired API session is removed and validation errors remain useful', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Session expired' }), { status: 401 });
  await assert.rejects(request('/users/me'), /Session expired/);
  assert.equal(hasSession(), false);
  assert.equal(errorMessage([{ loc: ['body', 'email'], msg: 'Invalid email' }]), 'email: Invalid email');
});
