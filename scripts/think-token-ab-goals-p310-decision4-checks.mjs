// P3.10 A/B goals: the 12 P3.8 decision-set goals with OBJECTIVE checks on what the run left in its workspace and what it answered. Written and committed
// before any A/B run. The goals are deliberately vague (terse, rambling, typos), so the checks are lenient: they test the outcome the goal asks for,
// not a particular way of doing it. Files are keyed by workspace-relative path.
import { GOALS as SET4 } from './think-token-ab-goals-p38-decision4.mjs';

const entries = (f) => Object.entries(f);
const bytes = (s) => Buffer.byteLength(s ?? '', 'utf8');
const CHECKS = {
  'terse-deep-folders': (f) => entries(f).some(([k]) => k.split('/').length >= 5),
  'rambling-stub': (f, a) => entries(f).some(([, v]) => v === '') && /\b0\b|zero/i.test(a ?? ''),
  'typos-replace-letter': (f) => entries(f).some(([, v]) => v.trim() === 'Y'),
  'terse-rocket-icon': (f, a) => entries(f).some(([, v]) => v.includes('🚀')) && /\b4\b/.test(a ?? ''),
  'rambling-quarter-recap': (_f, a) => /not (exist|found|there|uploaded)|missing|no such|couldn|cannot|can.t|unable|does not|doesn.t|isn.t|wasn.t|no (file|report|document)/i.test(a ?? ''),
  'typos-config-fallback': (f, a) => entries(f).some(([k, v]) => /config/i.test(k) && /dark/i.test(v)) && /dark/i.test(a ?? ''),
  'typos-accented-greeting': (f, a) => entries(f).some(([, v]) => /[^\x00-\x7f]/.test(v) && new RegExp(`\\b${bytes(v)}\\b`).test(a ?? '')),
  'terse-tack-on-line': (f) => entries(f).some(([, v]) => v.split('\n').filter((l) => l.trim()).length >= 2),
  'terse-five-letters': (f, a) => entries(f).some(([, v]) => v.trim() === 'abcde') && /\b5\b/.test(a ?? ''),
  'rambling-machine-config': (f) => entries(f).some(([, v]) => { const t = v.trim(); if (t.includes('\n')) return false; try { return Object.values(JSON.parse(t)).includes(true); } catch { return false; } }),
  'terse-memo-above': (f) => entries(f).length >= 1,
  'rambling-three-labelled': (f) => entries(f).filter(([k]) => /\.md$/i.test(k)).length >= 3,
};
export const GOALS = SET4.map((g) => ({ ...g, check: CHECKS[g.id] }));
