import { after, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { repoSpec } from '../local-tools.ts';
import { accepted, attemptRepo, repoEscalationReason, type RepoAttempt } from '../escalation.ts';
import type { LocalChat, LocalToolResult } from '../local-tools.ts';
import type { OllamaChatTurn } from '../ollama-client.ts';
import type { RepoEvidence } from '../repo-tools.ts';
import { lookupHooks } from './helpers/lookup-hooks.ts';

const UNTESTED = 'Find an exported function in src/alpha.ts that has no test.';
const CONSTANT = 'Which file defines MAX_ITEMS and what is its value?';
const NAMED = 'Find a function named nothingHere.';

const result = (o: Partial<LocalToolResult<RepoEvidence>>): LocalToolResult<RepoEvidence> => ({ success: true, model: 'm', mode: 'native', evidence: [], steps: [], tool_calls: 0, prompt_tokens: 0, completion_tokens: 0, latency_ms: 0, cold_load_ms: 0, grounding: { status: 'GROUNDED', classification: 'ok', unsupported: [], checked: CHECKED }, ...o });
const attempt = (o: Partial<LocalToolResult<RepoEvidence>>, disk?: RepoAttempt['disk']): RepoAttempt => ({ model: 'm', result: result(o), ...(disk ? { disk } : {}) });
const CHECKED = { numbers: 0, urls: 0, ids: 0, branches: 0, states: 0 };
const found = { found: true, file: 'src/alpha.ts', line: 4, quote: 'q', claim: 'c' };

describe('repoEscalationReason', () => {
  it('accepts a grounded, disk-verified finding', () => {
    const a = attempt({ finding: found }, { disk_verified: true });
    assert.equal(repoEscalationReason(UNTESTED, a), null);
    assert.equal(accepted(a), true);
  });
  it('escalates a failed run, an ungrounded one, and a finding that is not on disk', () => {
    assert.match(repoEscalationReason(UNTESTED, attempt({ success: false, failure: { kind: 'no_tool_call', message: 'looked at nothing' } }))!, /^no_tool_call: looked at nothing/);
    assert.match(repoEscalationReason(UNTESTED, attempt({ success: false }))!, /^failed: no result/);
    assert.match(repoEscalationReason(UNTESTED, attempt({ finding: found, grounding: { status: 'GROUNDING FAILED', classification: 'unsupported_claim', unsupported: [], checked: CHECKED } }, undefined))!, /grounding failed \(unsupported_claim\)/);
    assert.match(repoEscalationReason(UNTESTED, attempt({ finding: found, grounding: null }))!, /grounding failed \(none\)/);
    assert.match(repoEscalationReason(UNTESTED, attempt({ finding: found }, { disk_verified: false, reason: 'the quote is not at src/alpha.ts:4 on disk' }))!, /re-read from disk \(the quote is not at/);
    assert.match(repoEscalationReason(UNTESTED, attempt({ finding: found }))!, /not checked/);
    assert.equal(accepted(attempt({ finding: found }, { disk_verified: false })), false);
    assert.equal(accepted(attempt({ success: false })), false);
  });
  it('never escalates after a denial or a stop', () => {
    assert.equal(repoEscalationReason(UNTESTED, attempt({ success: false, failure: { kind: 'tool_denied', message: 'no' } })), null);
    assert.equal(repoEscalationReason(UNTESTED, attempt({ success: false, failure: { kind: 'no_tool_call', message: 'x' } }), true), null);
  });
  it('"no finding" is retried for goals that expect a finding and kept for "function named X" and unknown shapes', () => {
    const none = attempt({ finding: { found: false, reason: 'all tested' } });
    assert.match(repoEscalationReason(UNTESTED, none)!, /untested-function/);
    assert.match(repoEscalationReason(CONSTANT, none)!, /defines-constant/);
    assert.equal(repoEscalationReason(NAMED, none), null);
    assert.equal(repoEscalationReason('Inspect the code for unused exports', none), null);
    assert.equal(accepted(none), true);
  });
});

describe('attemptRepo', () => {
  let root = '';
  before(() => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), 'escalation-'));
    fs.mkdirSync(path.join(root, 'src'), { recursive: true }); fs.mkdirSync(path.join(root, 'tests'), { recursive: true });
    fs.writeFileSync(path.join(root, 'src/alpha.ts'), 'export function alpha() {\n  return 1;\n}\nexport function orphan() {\n  return 7;\n}\n');
    fs.writeFileSync(path.join(root, 'tests/alpha.test.ts'), 'alpha();\n');
    process.env.KUDBEE_REPO_ROOT = root;
  });
  after(() => { delete process.env.KUDBEE_REPO_ROOT; fs.rmSync(root, { recursive: true, force: true }); });
  const turn = (o: Partial<OllamaChatTurn>): OllamaChatTurn => ({ content: '', tool_calls: [], prompt_tokens: 10, completion_tokens: 5, latency_ms: 1, ...o });
  const call = (name: string, args: object): OllamaChatTurn => turn({ tool_calls: [{ function: { name, arguments: args } }] });
  const chatOf = (turns: OllamaChatTurn[]): LocalChat => ({ modelCapabilities: async () => ['tools'], chatOnce: async () => turns.shift() ?? turn({ error: 'exhausted' }) });
  const good = { found: true, file: 'src/alpha.ts', line: 4, quote: 'export function orphan()', claim: 'The function `orphan` has no tests.', absence_search: { query: 'orphan', path: 'tests' } };
  const hooks = () => lookupHooks({ allowedTools: ['repo_search', 'repo_read'] }).hooks;

  it('runs the governed loop and re-reads a grounded finding from disk', async () => {
    const a = await attemptRepo({ model: 'm', goal: UNTESTED, chat: chatOf([call('repo_read', { path: 'src/alpha.ts', start: 1, end: 6 }), call('repo_search', { query: 'orphan', path: 'tests' }), call('report_finding', good)]), hooks: hooks() });
    assert.equal(a.result.success, true);
    assert.deepEqual(a.disk, { disk_verified: true });
    assert.equal(accepted(a), true);
    assert.equal(repoEscalationReason(UNTESTED, a), null);
  });
  it('a quote that is not on disk is reported as such (root override), and a "found nothing" report has no disk check', async () => {
    const other = fs.mkdtempSync(path.join(os.tmpdir(), 'escalation-other-'));
    fs.mkdirSync(path.join(other, 'src'), { recursive: true }); fs.writeFileSync(path.join(other, 'src/alpha.ts'), 'export function different() {}\n');
    const a = await attemptRepo({ model: 'm', goal: UNTESTED, root: other, chat: chatOf([call('repo_read', { path: 'src/alpha.ts', start: 1, end: 6 }), call('repo_search', { query: 'orphan', path: 'tests' }), call('report_finding', good)]), hooks: hooks() });
    fs.rmSync(other, { recursive: true, force: true });
    assert.equal(a.disk?.disk_verified, false); assert.equal(accepted(a), false);
    assert.match(repoEscalationReason(UNTESTED, a)!, /re-read from disk/);
    const none = await attemptRepo({ model: 'm', goal: UNTESTED, maxSteps: 4, chat: chatOf([call('repo_read', { path: 'src/alpha.ts', start: 1, end: 6 }), call('report_finding', { found: false, reason: 'nothing' })]), hooks: hooks() });
    assert.equal(none.disk, undefined);
  });
  it('a custom spec is what the model sees (the token block reaches the system prompt)', async () => {
    const seen: string[] = [];
    const chat: LocalChat = { modelCapabilities: async () => ['tools'], chatOnce: async (_m, messages) => { seen.push(String((messages[0] as { content: string }).content)); return turn({ error: 'stop' }); } };
    const base = repoSpec();
    await attemptRepo({ model: 'm', goal: UNTESTED, chat, hooks: hooks(), spec: { ...base, system: `${base.system}\n\nTHINK TOKENS: marker` } });
    assert.match(seen[0]!, /THINK TOKENS: marker/);
  });
});
