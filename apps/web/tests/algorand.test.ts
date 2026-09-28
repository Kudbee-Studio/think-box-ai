import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import type { AddressInfo } from 'node:net';
import { algorandQuery, decodeState, validateAlgorandInput, algorandHost, type AlgorandEndpoints } from '../algorand.ts';

const ADDR = 'A'.repeat(58);
const TXID = 'B'.repeat(52);
const b64 = (s: string) => Buffer.from(s).toString('base64');
let endpoints: AlgorandEndpoints;
let server: http.Server;
const hits: string[] = [];

const routes: Record<string, unknown> = {
  '/v2/status': { 'last-round': 123, 'time-since-last-round': 2_000_000_000, 'catchup-time': 0, 'last-version': 'v1' },
  [`/v2/accounts/${ADDR}?exclude=created-apps,created-assets`]: {
    amount: 2_500_000,
    'min-balance': 100_000,
    status: 'Offline',
    'total-assets-opted-in': 1,
    assets: [{ 'asset-id': 31566704, amount: 5_000_000, 'is-frozen': false }],
  },
  '/v2/assets/31566704': { params: { name: 'USDC', 'unit-name': 'USDC', decimals: 6, total: 18446744073709552, creator: ADDR, url: 'https://centre.io' } },
  '/v2/applications/42': {
    params: {
      creator: ADDR,
      'approval-program': Buffer.from([1, 2, 3, 4]).toString('base64'),
      'global-state': [
        { key: b64('owner'), value: { type: 1, bytes: b64('alice') } },
        { key: b64('count'), value: { type: 2, uint: 7 } },
      ],
    },
  },
  [`/v2/transactions/${TXID}`]: {
    transaction: { id: TXID, 'tx-type': 'pay', 'confirmed-round': 99, 'round-time': 1_700_000_000, sender: ADDR, fee: 1000, 'payment-transaction': { receiver: ADDR, amount: 3_000_000 }, note: b64('hello') },
  },
};

before(async () => {
  server = http.createServer((req, res) => {
    hits.push(req.url ?? '');
    const body = routes[req.url ?? ''];
    res.setHeader('Content-Type', 'application/json');
    if (!body) {
      res.statusCode = 404;
      return res.end(JSON.stringify({ message: 'no such thing' }));
    }
    res.end(JSON.stringify(body));
  });
  await new Promise<void>((r) => server.listen(0, '127.0.0.1', r));
  const url = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  endpoints = { algod: { testnet: url, mainnet: url }, indexer: { testnet: url, mainnet: url } };
});

after(() => new Promise<void>((r) => server.close(() => r())));

test('status summarises the node', async () => {
  const r = await algorandQuery({ action: 'status' }, { endpoints });
  assert.deepEqual(r, { network: 'testnet', last_round: 123, seconds_since_last_round: 2, catching_up: false, last_version: 'v1' });
});

test('account converts microAlgos and lists holdings', async () => {
  const r = await algorandQuery({ action: 'account', address: ADDR, network: 'mainnet' }, { endpoints });
  assert.equal(r.balance_algo, 2.5);
  assert.equal(r.min_balance_algo, 0.1);
  assert.deepEqual(r.holdings, [{ asset_id: 31566704, amount_base_units: 5_000_000, frozen: false }]);
});

test('asset applies decimals to the total', async () => {
  const r = await algorandQuery({ action: 'asset', id: '31566704' }, { endpoints });
  assert.equal(r.name, 'USDC');
  assert.equal(r.decimals, 6);
  assert.equal(r.total, 18446744073709552 / 1e6);
});

test('application decodes global state', async () => {
  const r = await algorandQuery({ action: 'application', id: 42 }, { endpoints });
  assert.deepEqual(r.global_state, { owner: 'alice', count: 7 });
  assert.equal(r.approval_program_bytes, 4);
});

test('transaction summary includes payment amount, time and note', async () => {
  const r = await algorandQuery({ action: 'transaction', txid: TXID }, { endpoints });
  assert.equal(r.amount_algo, 3);
  assert.equal(r.note, 'hello');
  assert.equal(r.time, new Date(1_700_000_000_000).toISOString());
});

test('not found is reported clearly', async () => {
  await assert.rejects(algorandQuery({ action: 'asset', id: '999' }, { endpoints }), /Not found on Algorand: no such thing/);
});

test('invalid input is rejected without any request', async () => {
  const before = hits.length;
  assert.throws(() => validateAlgorandInput({ action: 'account', address: 'short' }), /not a valid Algorand address/);
  assert.throws(() => validateAlgorandInput({ action: 'asset', id: '12abc' }), /numeric id/);
  assert.throws(() => validateAlgorandInput({ action: 'transaction', txid: 'x' }), /transaction id/);
  assert.throws(() => validateAlgorandInput({ action: 'send_payment' }), /action must be one of/);
  assert.throws(() => validateAlgorandInput({ action: 'status', network: 'betanet' }), /testnet or mainnet/);
  await assert.rejects(algorandQuery({ action: 'account', address: 'lower'.repeat(12) }, { endpoints }));
  assert.equal(hits.length, before);
});

test('decodeState keeps binary keys and values readable', () => {
  const state = decodeState([{ key: Buffer.from([0xff, 0x01]).toString('base64'), value: { type: 1, bytes: Buffer.from([0x00, 0xfe]).toString('base64') } }]);
  assert.deepEqual(state, { '0xff01': `base64:${Buffer.from([0x00, 0xfe]).toString('base64')}` });
});

test('indexer actions target the indexer host', () => {
  assert.equal(algorandHost('status', 'testnet'), 'testnet-api.algonode.cloud');
  assert.equal(algorandHost('transaction', 'mainnet'), 'mainnet-idx.algonode.cloud');
});
