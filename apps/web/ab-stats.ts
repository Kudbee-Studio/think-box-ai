// Statistics for the Think Token A/B: Fisher's exact test on pass counts and a paired bootstrap interval on the pass-rate difference.
// Pure and deterministic: the bootstrap uses a seeded generator.

const lnFact: number[] = [0];
const lnF = (n: number): number => { for (let i = lnFact.length; i <= n; i += 1) lnFact.push(lnFact[i - 1]! + Math.log(i)); return lnFact[n]!; };
const lnChoose = (n: number, k: number): number => lnF(n) - lnF(k) - lnF(n - k);

/** Two-sided Fisher exact test for [[a, b], [c, d]] (sum of the probabilities of all tables at most as likely as the observed one). */
export function fisherExact(a: number, b: number, c: number, d: number): number {
  const row1 = a + b; const col1 = a + c; const n = a + b + c + d;
  const lp = (x: number): number => lnChoose(row1, x) + lnChoose(n - row1, col1 - x) - lnChoose(n, col1);
  const observed = lp(a);
  let p = 0;
  for (let x = Math.max(0, col1 - (n - row1)); x <= Math.min(row1, col1); x += 1) if (lp(x) <= observed + 1e-9) p += Math.exp(lp(x));
  return Math.min(1, p);
}

/** mulberry32: a small seeded generator, so the same results always give the same interval. */
export function rng(seed: number): () => number {
  let s = seed >>> 0;
  return () => { s = (s + 0x6D2B79F5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

/** Paired bootstrap 95% interval for mean(y) - mean(x), resampling goals (the same goal is run in both arms). */
export function pairedBootstrap(x: number[], y: number[], opts: { resamples?: number; seed?: number } = {}): { diff: number; lo: number; hi: number } {
  if (x.length !== y.length || !x.length) throw new Error('paired samples must be the same non-zero length');
  const n = x.length; const B = opts.resamples ?? 10000; const rand = rng(opts.seed ?? 20261005);
  const diffs: number[] = [];
  for (let i = 0; i < B; i += 1) { let s = 0; for (let j = 0; j < n; j += 1) { const k = Math.floor(rand() * n); s += y[k]! - x[k]!; } diffs.push(s / n); }
  diffs.sort((p, q) => p - q);
  const mean = (v: number[]): number => v.reduce((p, q) => p + q, 0) / v.length;
  return { diff: mean(y) - mean(x), lo: diffs[Math.floor(0.025 * B)]!, hi: diffs[Math.min(B - 1, Math.floor(0.975 * B))]! };
}

/** Wilson 95% interval for a proportion. */
export function wilson(k: number, n: number): { lo: number; hi: number } {
  if (!n) return { lo: 0, hi: 0 };
  const z = 1.96; const p = k / n; const den = 1 + (z * z) / n;
  const centre = (p + (z * z) / (2 * n)) / den; const half = (z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n))) / den;
  return { lo: Math.max(0, centre - half), hi: Math.min(1, centre + half) };
}

export const percentile = (v: number[], q: number): number => { if (!v.length) return 0; const s = [...v].sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.ceil(q * s.length) - 1)]!; };
