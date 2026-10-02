// Pool objective_ok from two A/B JSON outputs and report a two-proportion z-test (related goals only).
// Usage: node scripts/think-token-ab-pooled-significance.mjs <ab31.json> <ab33.json> [out.json]
import fs from 'node:fs';

const [a, b, out] = process.argv.slice(2);
if (!a || !b) throw new Error('usage: think-token-ab-pooled-significance.mjs <ab31.json> <ab33.json>');

function load(p) {
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

function armStats(rows, arm) {
  const r = rows.filter((x) => x.arm === arm && x.related);
  const ok = r.filter((x) => x.objective_ok).length;
  return { n: r.length, ok };
}

function zTest(p1, n1, p2, n2) {
  if (!n1 || !n2) return { z: null, p_value: null };
  const pooled = (p1 * n1 + p2 * n2) / (n1 + n2);
  const se = Math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2));
  if (!se) return { z: 0, p_value: 1 };
  const z = (p1 - p2) / se;
  const p = 2 * (1 - normalCdf(Math.abs(z)));
  return { z, p_value: p };
}

function normalCdf(x) {
  // Abramowitz & Stegun approximation
  const t = 1 / (1 + 0.2316419 * x);
  const d = 0.3989423 * Math.exp((-x * x) / 2);
  const prob = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
  return 1 - prob;
}

const j1 = load(a);
const j2 = load(b);
const rows = [...(j1.rows ?? []), ...(j2.rows ?? [])];
const off = armStats(rows, 'off');
const on = armStats(rows, 'on');
const pOff = off.ok / off.n;
const pOn = on.ok / on.n;
const { z, p_value } = zTest(pOn, on.n, pOff, off.n);

const report = {
  sources: [a, b].map((p) => ({ file: p, spent_usd: load(p).spent_usd ?? null })),
  pooled_related_runs: rows.filter((r) => r.related).length,
  off: { ...off, rate: pOff },
  on: { ...on, rate: pOn },
  delta_on_minus_off: pOn - pOff,
  two_sided_z: z,
  p_value,
  interpretation: p_value === null ? 'insufficient data' : p_value < 0.05 ? 'significant at 0.05' : 'not significant at 0.05',
};
const text = `${JSON.stringify(report, null, 2)}\n`;
if (out) fs.writeFileSync(out, text);
else process.stdout.write(text);
console.error(report.interpretation, `p=${p_value?.toFixed(4) ?? 'n/a'}`, `on-off=${(pOn - pOff).toFixed(3)}`);
