// Opt-in (npm run test:live-local-simulate): the pre-registered experiment in docs/evidence/p3.48-local-simulate/PLAN.md.
// Real models (local Ollama models and Mercury-2), the real governed tools, the real sandbox, the real Mayor and runner; fifteen frozen fixture repositories. The sandbox-run approval is
// granted by this script on the founder's instruction to run the experiment, not by a person. The Mercury key comes from the repo .env and is never printed or written.
// Exit codes: 0 = ran and the validity criteria hold, 1 = ran and a validity criterion failed, 2 = NOT RUN (a precondition failed before any model ran).
import { execFileSync, spawnSync } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { readTextIfPresent, writeEvidence } from '../helpers/evidence-file.ts';
import { PACKAGE_JSON, TASKS, type Task } from '../helpers/local-sim-tasks.ts';
import { lookupHooks } from '../helpers/lookup-hooks.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const repoRoot = path.resolve(appDir, '../..');
const OUT = path.join(repoRoot, process.env.P348_OUT || 'docs/evidence/p3.48-local-simulate');
const LABEL = process.env.P348_RUN_LABEL || 'run';
const MODELS = (process.env.P348_MODELS || 'smollm2:360m,qwen2.5:1.5b,qwen2.5:3b,gemma3:4b,mercury-2').split(',');
const ONLY = process.env.P348_TASKS ? new Set(process.env.P348_TASKS.split(',')) : null;
const TIMEOUT_MS = Number(process.env.P348_TIMEOUT_MS) || 400_000; const MERCURY_CAP_USD = 0.20;
// trials per model, e.g. P348_TRIALS=smollm2:360m=2,qwen2.5:3b=2 (default 1 each)
const TRIALS = new Map((process.env.P348_TRIALS || '').split(',').filter(Boolean).map((x) => [x.slice(0, x.lastIndexOf('=')), Number(x.slice(x.lastIndexOf('=') + 1))] as const));
const trialsFor = (m: string): number => Math.max(1, TRIALS.get(m) ?? 1);
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const log = (s: string) => console.log(`[p3.48 ${new Date().toISOString().slice(11, 19)}] ${s}`);
function notRun(why: string): never { console.error(`NOT RUN: ${why}`); process.exit(2); }

// Cloud (API) models talk through the SAME worker-agent path (an OpenAI-compatible endpoint); only the base URL and key differ. Each key is looked up by its own NAME only, never printed.
const DEEPSEEK_MODEL = process.env.P348_DEEPSEEK_MODEL || 'deepseek-chat';
const readKey = (name: string): string => process.env[name] || readTextIfPresent(path.join(repoRoot, '.env')).match(new RegExp(`^${name}=(.+)$`, 'm'))?.[1]?.trim().replace(/^["']|["']$/g, '') || '';
const CLOUD: Record<string, { baseUrl: string; keyEnv: string; key: string }> = {
  'mercury-2': { baseUrl: process.env.INCEPTION_BASE_URL || 'https://api.inceptionlabs.ai/v1', keyEnv: 'INCEPTION_API_KEY', key: '' },
  [DEEPSEEK_MODEL]: { baseUrl: process.env.DEEPSEEK_BASE_URL || 'https://api.deepseek.com/v1', keyEnv: 'DEEPSEEK_API_KEY', key: '' },
};
const isCloud = (m: string): boolean => Object.prototype.hasOwnProperty.call(CLOUD, m);
for (const m of MODELS) if (isCloud(m)) { CLOUD[m]!.key = readKey(CLOUD[m]!.keyEnv); if (!CLOUD[m]!.key) notRun(`No ${CLOUD[m]!.keyEnv} in the environment or the repo .env (needed for ${m})`); }
const allKeys = Object.values(CLOUD).map((c) => c.key).filter(Boolean);
process.env.INCEPTION_API_KEY_2 = '';
const savedTmp = process.env.TMPDIR;
const privateTmp = fs.mkdtempSync(path.join(os.tmpdir(), 'p348-')); process.env.TMPDIR = privateTmp;

const { runToolAgent } = await import('../../agent.ts');
const { executeConvoy } = await import('../../convoy-runner.ts');
const { ConvoyStore } = await import('../../convoy.ts');
const { evaluatePolicy, planConvoy } = await import('../../mayor.ts');
const { createModelClients } = await import('../../ollama-client.ts');
const { RunStore } = await import('../../runs.ts');
const { probeSandbox } = await import('../../scratch-runner.ts');

const probe = await probeSandbox(); if (!probe.ok) notRun(`sandbox not proven: ${(probe as { reason: string }).reason}`);
const chat = createModelClients({ ollamaBaseUrl: process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434', janusBaseUrl: 'http://127.0.0.1:9', janusEnabled: () => false });
const installed = new Set((await chat.listOllamaModels()).map((m) => m.name));
for (const m of MODELS) if (!isCloud(m) && !installed.has(m)) notRun(`${m} is not installed (nothing is pulled)`);

const git = (cwd: string, ...a: string[]): string => execFileSync('git', ['-c', 'user.email=t@t', '-c', 'user.name=t', ...a], { cwd, encoding: 'utf8' }).trim();
const realGit = (...a: string[]): string => git(repoRoot, ...a);
const EXCLUDE = [`:(exclude)${path.relative(repoRoot, OUT)}`];
const realState = (): string => createHash('sha256').update(realGit('status', '--porcelain', '--', '.', ...EXCLUDE) + realGit('diff', '--', '.', ...EXCLUDE) + realGit('rev-parse', 'HEAD')).digest('hex');
const scratchDirs = (): number => fs.readdirSync(privateTmp).filter((n) => n.startsWith('kudbee-scratch-')).length;
const tasksHash = createHash('sha256').update(fs.readFileSync(path.join(appDir, 'tests/helpers/local-sim-tasks.ts'))).digest('hex');
const tasks: Task[] = TASKS.filter((t) => !ONLY || ONLY.has(t.id));

function makeRepo(task: Task): { dir: string; sha: string } {
  const dir = fs.mkdtempSync(path.join(privateTmp, `task-${task.id}-`));
  const put = (rel: string, text: string): void => { fs.mkdirSync(path.dirname(path.join(dir, rel)), { recursive: true }); fs.writeFileSync(path.join(dir, rel), text); };
  put('apps/web/package.json', PACKAGE_JSON); put('apps/web/.gitignore', 'node_modules\n'); fs.mkdirSync(path.join(dir, 'apps/web/node_modules'), { recursive: true });
  for (const [f, c] of Object.entries(task.files)) put(f, c);
  git(dir, 'init', '-q', '-b', 'main'); git(dir, 'add', '-A'); git(dir, 'commit', '-qm', `fixture ${task.id}`);
  return { dir, sha: git(dir, 'rev-parse', 'HEAD') };
}
/** Unsandboxed, trusted-fixture check: a fresh export of the commit, the patch applied, the fixture's own test run. Returns the exit status. */
function independentTest(dir: string, sha: string, patch: string | null): number {
  const x = fs.mkdtempSync(path.join(privateTmp, 'verify-')); const tar = path.join(x, 't.tar'); const work = path.join(x, 'w'); fs.mkdirSync(work);
  execFileSync('git', ['archive', '--format=tar', '-o', tar, sha], { cwd: dir }); execFileSync('tar', ['-x', '-f', tar, '-C', work]);
  if (patch) execFileSync('git', ['apply', '--whitespace=nowarn', '-'], { cwd: work, input: patch });
  const r = spawnSync('sh', ['-c', 'node --test tests/*.test.js'], { cwd: path.join(work, 'apps/web'), encoding: 'utf8', env: { PATH: process.env.PATH ?? '', HOME: x } });
  fs.rmSync(x, { recursive: true, force: true }); return r.status ?? 1;
}

// ---- V0 pre-flight: every task fails as written and passes with its reference fix ----
const preflight: Array<{ id: string; before: number; after: number; ok: boolean }> = [];
for (const task of tasks) {
  const { dir, sha } = makeRepo(task);
  const before = independentTest(dir, sha, null);
  const x = fs.mkdtempSync(path.join(privateTmp, 'ref-')); const work = path.join(x, 'w'); fs.mkdirSync(work);
  execFileSync('git', ['archive', '--format=tar', '-o', path.join(x, 'ref.tar'), sha], { cwd: dir }); execFileSync('tar', ['-x', '-f', path.join(x, 'ref.tar'), '-C', work]);
  for (const e of task.ref) { const p = path.join(work, e.path); const s = fs.readFileSync(p, 'utf8'); if (s.split(e.find!).length !== 2) notRun(`${task.id}: the reference find text is not unique`); fs.writeFileSync(p, s.replace(e.find!, () => e.replace!)); }
  const after = spawnSync('sh', ['-c', 'node --test tests/*.test.js'], { cwd: path.join(work, 'apps/web'), encoding: 'utf8', env: { PATH: process.env.PATH ?? '', HOME: x } }).status ?? 1;
  preflight.push({ id: task.id, before, after, ok: before !== 0 && after === 0 }); fs.rmSync(x, { recursive: true, force: true });
}
if (!preflight.every((p) => p.ok)) { console.error(JSON.stringify(preflight)); notRun('V0 failed: a task does not fail as written or does not pass with its reference fix'); }
log(`V0 ok: ${tasks.length} tasks fail as written and pass with the reference fix`);

interface Row { model: string; task: string; trial: number; kind: string; state: string; outcome: string | null; category: string; reason: string | null; verified: boolean | null; flags: string[]; files: string[]; patch: string | null; independent: number | null; agrees: boolean | null; wall_ms: number; tokens: number; tool_calls: number; cost_usd: number; approvals: number; repo_clean: boolean; summary: string | null; error: string | null }
const rows: Row[] = [];
const before = { real: realState(), scratch: scratchDirs() };
let cloudSpend = 0;
const lookup = (m: string | null) => (m && isCloud(m) ? { usd: 0.01, basis: 'estimate' } : { usd: 0, basis: 'local model, no API cost' });

for (const model of MODELS) {
  for (let trial = 1; trial <= trialsFor(model); trial += 1) {
  for (const task of tasks) {
    if (isCloud(model) && cloudSpend >= MERCURY_CAP_USD) { log(`cloud spend cap reached: skipping ${task.id}`); continue; }
    const { dir, sha } = makeRepo(task); const headBefore = git(dir, 'rev-parse', 'HEAD');
    process.env.KUDBEE_REPO_ROOT = dir;
    // a cloud model goes through the worker-agent path with ITS endpoint and key; a local model gets neither
    if (isCloud(model)) { process.env.INCEPTION_BASE_URL = CLOUD[model]!.baseUrl; process.env.INCEPTION_API_KEY = CLOUD[model]!.key; } else { process.env.INCEPTION_API_KEY = ''; }
    const local = !isCloud(model);
    const planned = planConvoy({ goal: task.goal, mode: 'simulate', lookupModel: local ? model : 'gemma3:4b', ...(local ? { routing: { source: 'operator' as const, model, reason: 'chosen by the operator' } } : {}), agentModel: local ? 'mercury-2' : model, isLocalModel: (m) => !isCloud(m), availableTools: ['list_files', 'read_file', 'repo_search', 'repo_read', 'propose_change', 'run_checks', 'live_lookup'], costOf: lookup, now: Date.now() });
    if (!planned.ok) notRun(`the Mayor did not plan ${task.id} for ${model}: ${planned.error}`);
    const plan = planned.plan; plan.simulation!.checks = ['test']; plan.simulation!.max_rounds = 1;
    if ((plan.simulation!.patch_local) !== local) notRun(`plan for ${model} has patch_local=${plan.simulation!.patch_local}`);
    const cdir = fs.mkdtempSync(path.join(privateTmp, 'c-')); const store = new ConvoyStore(path.join(cdir, 'c.json')); const runStore = new RunStore(path.join(cdir, 'r.json'));
    const c0 = store.create(plan.goal, plan, evaluatePolicy(plan)); store.submit(c0.id); store.decide(c0.id, 'approve', 'human');
    const ac = new AbortController(); let approvals = 0; const timer = setTimeout(() => ac.abort(), TIMEOUT_MS);
    const t0 = Date.now(); let timedOut = false;
    const deps = {
      store, runStore, repo: null, isLocalModel: (m: string) => !isCloud(m), chat: { chatOnce: chat.chatOnce, modelCapabilities: chat.modelCapabilities },
      newChildRun: (g: string, runId: string, mdl: string, convoyId: string, workerId: string) => runStore.create({ id: runId, session_id: 's', goal: g, model: mdl, provider: mdl === 'sandbox' ? 'sandbox' : local ? 'ollama' : 'inception', status: 'running', started_at: Date.now(), steps: [], current_step: 0, tool_calls: 0, prompt_tokens: 0, completion_tokens: 0, cost_usd: 0, approvals: { approved: 0, denied: 0 }, files: [], jobId: convoyId, specialistId: workerId } as never),
      hooksFor: (_r: unknown, signal: AbortSignal, allowedTools: string[]) => ({ ...lookupHooks({ signal, requestApproval: async () => { approvals += 1; return true; } }).hooks, allowedTools }),
      runAgent: (g: string, m: string, h: never) => runToolAgent(g, m, 20, 0.7, [], h, ''),
      runSpecialists: async () => ({}), broadcast: () => {}, signal: ac.signal,
    };
    let c; let error: string | null = null;
    try { c = await executeConvoy(deps as never, c0.id); } catch (e) { error = String((e as Error).message ?? e).slice(0, 300); c = store.get(c0.id)!; }
    clearTimeout(timer); timedOut = ac.signal.aborted;
    const wall = Date.now() - t0; await sleep(300);
    const sim = c.simulation ?? null; const patchW = c.workers.find((w) => w.id === 'patch-1');
    const independent = sim?.patch ? independentTest(dir, sha, sim.patch) : null;
    const reportVerified = sim?.report ? (sim.report as { verified?: boolean }).verified === true : null;
    const agrees = independent === null || reportVerified === null ? null : (independent === 0) === reportVerified;
    const flags = sim?.flags ?? [];
    let category: string; let reason: string | null = null;
    if (sim?.verified === true) category = flags.length ? 'verified_flagged' : 'success';
    else if (sim?.checks_ran === true) category = 'proposal_wrong';
    else { category = 'no_proposal'; reason = timedOut ? 'timeout' : (patchW?.failure?.message ?? error ?? c.error ?? 'unknown').split(':')[0]!.trim().slice(0, 40); if (!timedOut && patchW?.failure?.kind === 'no_patch') reason = 'no_valid_proposal'; }
    const cost = Number(c.cost_usd) || 0; if (isCloud(model)) cloudSpend += cost;
    const row: Row = { model, task: task.id, trial, kind: task.kind, state: c.state, outcome: c.outcome ?? null, category, reason, verified: sim?.verified ?? null, flags, files: sim?.files ?? [], patch: sim?.patch ?? null, independent, agrees, wall_ms: wall, tokens: c.tokens, tool_calls: c.tool_calls, cost_usd: cost, approvals, repo_clean: git(dir, 'status', '--porcelain') === '' && git(dir, 'rev-parse', 'HEAD') === headBefore, summary: sim?.summary ?? null, error: c.error ?? error };
    rows.push(row);
    log(`${model.padEnd(13)} ${task.id}${trialsFor(model) > 1 ? ` t${trial}` : ''} ${category.padEnd(15)} ${reason ?? ''} ${(wall / 1000).toFixed(1)}s ${row.tool_calls} calls $${cost.toFixed(4)}${agrees === false ? '  !! DISAGREES with the independent test' : ''}`);
    process.env.KUDBEE_REPO_ROOT = ''; process.env.INCEPTION_API_KEY = ''; fs.rmSync(dir, { recursive: true, force: true });
  }
  }
}

// ---- summary and validity ----
const wilson = (k: number, n: number): [number, number] => { if (!n) return [0, 0]; const z = 1.96; const p = k / n; const d = 1 + z * z / n; const c = p + z * z / (2 * n); const m = z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return [Math.max(0, (c - m) / d), Math.min(1, (c + m) / d)]; };
const median = (xs: number[]): number => { const s = [...xs].sort((a, b) => a - b); return s.length ? s[Math.floor(s.length / 2)]! : 0; };
const byModel = MODELS.map((model) => {
  const r = rows.filter((x) => x.model === model); const n = r.length; const cnt = (cat: string) => r.filter((x) => x.category === cat).length;
  const reasons: Record<string, number> = {}; for (const x of r.filter((y) => y.category === 'no_proposal')) reasons[x.reason ?? 'unknown'] = (reasons[x.reason ?? 'unknown'] ?? 0) + 1;
  const ci = wilson(cnt('success'), n);
  return { model, provider: isCloud(model) ? 'cloud API (OpenAI-compatible)' : 'local (Ollama)', ...(isCloud(model) && model !== 'mercury-2' ? { cost_note: 'cost_usd is tokens priced with Mercury\'s rates, not this provider\'s: use the token counts' } : {}), trials: trialsFor(model), n, success: cnt('success'), success_ci95: [Number(ci[0].toFixed(2)), Number(ci[1].toFixed(2))], verified_flagged: cnt('verified_flagged'), proposal_wrong: cnt('proposal_wrong'), no_proposal: cnt('no_proposal'), no_proposal_reasons: reasons, median_wall_s: Number((median(r.map((x) => x.wall_ms)) / 1000).toFixed(1)), tokens: r.reduce((t, x) => t + x.tokens, 0), tool_calls: r.reduce((t, x) => t + x.tool_calls, 0), cost_usd: Number(r.reduce((t, x) => t + x.cost_usd, 0).toFixed(5)), success_tasks: r.filter((x) => x.category === 'success').map((x) => x.task) };
});
const validity = {
  v0_preflight: preflight.every((p) => p.ok),
  v1_independent_agreement: rows.every((r) => r.agrees !== false), v1_checked: rows.filter((r) => r.agrees !== null).length,
  v2_integrity: rows.every((r) => r.repo_clean) && realState() === before.real,
  v3_all_terminal: rows.every((r) => ['COMPLETED', 'PARTIAL', 'FAILED'].includes(r.state)),
  v4_same_input: !process.env.P348_EXPECT_TASKS_SHA || process.env.P348_EXPECT_TASKS_SHA === tasksHash,
  v5_hygiene: cloudSpend <= MERCURY_CAP_USD && !allKeys.some((k) => JSON.stringify(rows).includes(k)) && scratchDirs() === before.scratch,
};
const bestLocal = byModel.filter((m) => !isCloud(m.model)).reduce((a, b) => (b.n && b.success / b.n > (a.n ? a.success / a.n : -1) ? b : a), byModel[0]!);
const mercury = byModel.find((m) => m.model === 'mercury-2');
const rate = bestLocal.n ? bestLocal.success / bestLocal.n : 0;
const decision = rate >= 0.6 ? 'build the local-first + Mercury fallback lane (needs go-ahead)' : rate >= 0.33 ? 'offer local as an opt-in privacy mode; no fallback without a repeat run' : 'do not pursue local patching now';
const sanity = mercury ? (mercury.success >= 13 ? 'ok' : `SUSPECT: mercury-2 reached only ${mercury.success}/${mercury.n}`) : 'not run';
console.table(byModel.map((m) => ({ model: m.model, success: `${m.success}/${m.n}`, flagged: m.verified_flagged, wrong: m.proposal_wrong, none: m.no_proposal, reasons: JSON.stringify(m.no_proposal_reasons), p50_s: m.median_wall_s, cost: m.cost_usd })));
await writeEvidence(OUT, path.join(OUT, `${LABEL}-results.json`), { generated_at: new Date().toISOString(), plan: `${path.relative(repoRoot, OUT)}/PLAN.md`, tasks_sha256: tasksHash, models: MODELS, tasks: tasks.map((t) => t.id), note: 'real models, real governed tools, real sandbox, throwaway fixture repositories; approvals granted by the script on the founder\'s instruction; one trial per cell, default sampling', preflight, validity, cloud_spend_usd_at_mercury_rates: Number(cloudSpend.toFixed(5)), by_model: byModel, best_local: bestLocal.model, decision_by_pre_registered_rule: decision, mercury_sanity: sanity, rows });
process.env.TMPDIR = savedTmp ?? ''; fs.rmSync(privateTmp, { recursive: true, force: true });
log(`validity ${JSON.stringify(validity)}; best local ${bestLocal.model} ${bestLocal.success}/${bestLocal.n}; rule says: ${decision}; mercury sanity: ${sanity}`);
void randomUUID;
process.exit(Object.values(validity).every(Boolean) ? 0 : 1);
