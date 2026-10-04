// Unit tests for net-guard.ts: private-address classification, hostname resolution and redirect-by-redirect fetching.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import type { AddressInfo } from 'node:net';
import { isPrivateAddress, targetsPrivateNetwork, fetchChecked } from '../net-guard.ts';

test('isPrivateAddress covers loopback, RFC1918, link-local, CGNAT and IPv6 local ranges', () => {
  for (const ip of ['127.0.0.1', '10.1.2.3', '172.16.0.1', '172.31.255.255', '192.168.1.1', '169.254.1.1', '100.64.0.1', '100.127.255.255', '0.0.0.0', '::1', '::', 'fc00::1', 'fd12:3456::1', 'fe80::1', '::ffff:10.0.0.1']) {
    assert.equal(isPrivateAddress(ip), true, ip);
  }
  for (const ip of ['8.8.8.8', '1.1.1.1', '172.15.0.1', '172.32.0.1', '100.128.0.1', '11.0.0.1', '2001:db8::1', 'not-an-ip']) {
    assert.equal(isPrivateAddress(ip), false, ip);
  }
});

test('targetsPrivateNetwork handles literal IPs, localhost names and a non-URL', async () => {
  assert.equal(await targetsPrivateNetwork('http://127.0.0.1/x'), true);
  assert.equal(await targetsPrivateNetwork('http://[::1]/x'), true);
  assert.equal(await targetsPrivateNetwork('http://8.8.8.8/x'), false);
  assert.equal(await targetsPrivateNetwork('http://localhost/x'), true);
  assert.equal(await targetsPrivateNetwork('http://api.localhost/x'), true);
  assert.equal(await targetsPrivateNetwork('not a url'), false);
});

let server: http.Server;
let base: string;
before(async () => {
  server = http.createServer((req, res) => {
    if (req.url === '/ok') { res.writeHead(200, { 'Content-Type': 'text/plain' }); res.end('ok'); return; }
    if (req.url === '/a') { res.writeHead(302, { Location: '/b' }); res.end(); return; }
    if (req.url === '/b') { res.writeHead(200); res.end('b'); return; }
    if (req.url === '/no-location') { res.writeHead(302); res.end(); return; }
    res.writeHead(302, { Location: '/loop' });
    res.end();
  });
  await new Promise<void>((r) => server.listen(0, '127.0.0.1', r));
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
after(() => new Promise<void>((r) => server.close(() => r())));

const notPrivate = async () => false;

test('fetchChecked refuses a private target without approval and allows it with approval', async () => {
  await assert.rejects(() => fetchChecked(`${base}/ok`, {}, false, async () => true), /local or private network/);
  const res = await fetchChecked(`${base}/ok`, {}, false, notPrivate);
  assert.equal(await res.text(), 'ok');
  const allowed = await fetchChecked(`${base}/ok`, {}, true, async () => true);
  assert.equal(allowed.status, 200);
});

test('fetchChecked follows a redirect hop by hop', async () => {
  const res = await fetchChecked(`${base}/a`, {}, false, notPrivate);
  assert.equal(res.status, 200);
  assert.equal(await res.text(), 'b');
});

test('fetchChecked returns a redirect that has no location', async () => {
  const res = await fetchChecked(`${base}/no-location`, {}, false, notPrivate);
  assert.equal(res.status, 302);
});

test('fetchChecked gives up after too many redirects', async () => {
  await assert.rejects(() => fetchChecked(`${base}/loop`, {}, false, notPrivate), /Too many redirects/);
});
