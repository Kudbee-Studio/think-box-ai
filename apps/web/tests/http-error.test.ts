import { test } from 'node:test';
import assert from 'node:assert/strict';
import { httpError } from '../http-error.ts';

const json = (body: unknown, status: number): Response => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

test('httpError keeps the server\'s message and adds the status', async () => {
  assert.equal((await httpError(json({ error: 'path required' }, 400))).message, 'path required (HTTP 400)');
  assert.equal((await httpError(json({ message: 'Not found' }, 404))).message, 'Not found (HTTP 404)');
});

test('httpError falls back to the bare status for a non-JSON body or a JSON body without a message', async () => {
  assert.equal((await httpError(new Response('<html>bad gateway</html>', { status: 502 }))).message, 'HTTP 502');
  assert.equal((await httpError(json({ ok: false }, 500))).message, 'HTTP 500');
  assert.equal((await httpError(new Response('', { status: 503 }))).message, 'HTTP 503');
});
