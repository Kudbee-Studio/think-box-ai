import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import type { AddressInfo } from 'node:net';
import { medicationQuery, validateMedicationInput, OPENFDA_DISCLAIMER } from '../medication.ts';

let baseUrl: string;
let server: http.Server;
const hits: string[] = [];

// Keyed by the drug name the mock query targets (matches the openfda.generic_name/brand_name
// clause built by medication.ts) so each test can script exactly what "openFDA" returns.
const routes: Record<string, { total: number; result?: Record<string, unknown> }> = {
  warfarin: {
    total: 74,
    result: {
      openfda: { brand_name: ['Warfarin Sodium'], generic_name: ['WARFARIN SODIUM'], rxcui: ['855332'] },
      drug_interactions: ['Concomitant use of drugs that increase bleeding risk...'],
      boxed_warning: ['Bleeding risk is increased...'],
    },
  },
  aspirin: {
    total: 1,
    result: {
      openfda: { brand_name: ['Aspirin'], generic_name: ['ASPIRIN'], rxcui: ['1191'] },
      drug_interactions: ['May increase bleeding risk when combined with anticoagulants.'],
    },
  },
};

before(async () => {
  server = http.createServer((req, res) => {
    hits.push(req.url ?? '');
    const url = new URL(req.url ?? '', 'http://x');
    const search = url.searchParams.get('search') ?? '';
    const match = Object.keys(routes).find((drug) => search.includes(`"${drug}"`));
    res.setHeader('Content-Type', 'application/json');
    if (!match) {
      res.statusCode = 404;
      return res.end(JSON.stringify({ error: { code: 'NOT_FOUND', message: 'No matches found!' } }));
    }
    const route = routes[match];
    res.end(JSON.stringify({ meta: { results: { total: route.total } }, results: [route.result] }));
  });
  await new Promise<void>((r) => server.listen(0, '127.0.0.1', r));
  baseUrl = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});

after(() => new Promise<void>((r) => server.close(() => r())));

test('lookup returns the requested label section for a known drug', async () => {
  const r = await medicationQuery({ action: 'lookup', drug: 'warfarin' }, { openfdaBaseUrl: baseUrl });
  assert.equal(r.found, true);
  assert.equal(r.brand_name, 'Warfarin Sodium');
  assert.match(String(r.text), /bleeding risk/);
  assert.equal(r.section, 'drug_interactions');
});

test('lookup defaults to drug_interactions but honours an explicit section', async () => {
  const r = await medicationQuery({ action: 'lookup', drug: 'warfarin', section: 'boxed_warning' }, { openfdaBaseUrl: baseUrl });
  assert.equal(r.section, 'boxed_warning');
  assert.match(String(r.text), /Bleeding risk is increased/);
});

test('unknown drug returns found:false, not a thrown error', async () => {
  const r = await medicationQuery({ action: 'lookup', drug: 'notarealdrugxyz' }, { openfdaBaseUrl: baseUrl });
  assert.equal(r.found, false);
  assert.equal(r.total_matching_labels, 0);
});

test('every response carries the openFDA disclaimer verbatim', async () => {
  const r = await medicationQuery({ action: 'lookup', drug: 'warfarin' }, { openfdaBaseUrl: baseUrl });
  assert.equal(r.disclaimer, OPENFDA_DISCLAIMER);
  assert.match(String(r.disclaimer), /unvalidated/);
  assert.match(String(r.disclaimer), /licensed pharmacist or physician/);
});

test('compare fetches each drug independently and never computes a verdict', async () => {
  const before = hits.length;
  const r = await medicationQuery({ action: 'compare', drugs: ['warfarin', 'aspirin'] }, { openfdaBaseUrl: baseUrl, interDrugDelayMs: 0 });
  assert.equal(hits.length, before + 2, 'one openFDA request per drug');
  const drugs = r.drugs as Array<{ drug: string; found: boolean }>;
  assert.deepEqual(drugs.map((d) => [d.drug, d.found]), [['warfarin', true], ['aspirin', true]]);
  // The whole point: this module never asserts "safe" / "unsafe" together.
  assert.doesNotMatch(JSON.stringify(r).toLowerCase(), /"verdict"|"is_safe"|"safe_together"/);
  assert.match(String(r.note), /does not cross-reference/);
  assert.match(String(r.note), /pharmacist or physician/);
});

test('compare rejects fewer than 2 or more than 5 drugs before any network call', async () => {
  const before = hits.length;
  await assert.rejects(medicationQuery({ action: 'compare', drugs: ['warfarin'] }, { openfdaBaseUrl: baseUrl }), /2 or more/);
  await assert.rejects(medicationQuery({ action: 'compare', drugs: ['a', 'b', 'c', 'd', 'e', 'f'] }, { openfdaBaseUrl: baseUrl }), /at most 5/);
  assert.equal(hits.length, before);
});

test('invalid input is rejected without any request', () => {
  assert.throws(() => validateMedicationInput({ action: 'lookup' }), /drug is required/);
  assert.throws(() => validateMedicationInput({ action: 'lookup', drug: 'x'.repeat(101) }), /too long/);
  assert.throws(() => validateMedicationInput({ action: 'lookup', drug: 'warfarin"; DROP TABLE' }), /unsupported characters/);
  assert.throws(() => validateMedicationInput({ action: 'poison' }), /action must be one of/);
  assert.throws(() => validateMedicationInput({ action: 'lookup', drug: 'x', section: 'made_up_section' }), /section must be one of/);
});

test('ambiguous flags when more than one label matched', async () => {
  const r = await medicationQuery({ action: 'lookup', drug: 'warfarin' }, { openfdaBaseUrl: baseUrl });
  assert.equal(r.ambiguous, true); // route has total: 74
  const r2 = await medicationQuery({ action: 'lookup', drug: 'aspirin' }, { openfdaBaseUrl: baseUrl });
  assert.equal(r2.ambiguous, false); // route has total: 1
});
