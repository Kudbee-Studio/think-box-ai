import assert from 'node:assert/strict';
import { test } from 'node:test';
import { auditVerdict, parseAudit } from '../dep-audit.ts';

const sample = JSON.stringify({ metadata: { vulnerabilities: { info: 0, low: 2, moderate: 1, high: 1, critical: 0, total: 4 } } });

test('parseAudit reads the severity counts', () => {
  assert.deepEqual(parseAudit(sample), { low: 2, moderate: 1, high: 1, critical: 0 });
});

test('parseAudit returns null for anything that is not an audit report (offline, error, garbage)', () => {
  assert.equal(parseAudit('not json'), null);
  assert.equal(parseAudit(JSON.stringify({ error: { code: 'ENOTFOUND' } })), null);
  assert.equal(parseAudit(''), null);
});

test('auditVerdict fails on high or critical, passes otherwise, and says not_run when there is no report', () => {
  assert.equal(auditVerdict({ low: 2, moderate: 1, high: 1, critical: 0 }).status, 'fail');
  assert.equal(auditVerdict({ low: 0, moderate: 0, high: 0, critical: 1 }).status, 'fail');
  assert.equal(auditVerdict({ low: 3, moderate: 2, high: 0, critical: 0 }).status, 'pass');
  assert.equal(auditVerdict(null).status, 'not_run');
});
