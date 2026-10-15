// The "feel" of the table: the numbers that decide whether it plays like pinball. The page lets you change them while playing; the physics reads them every step.
export const DEFAULTS = { gravity: 900, wallBounce: 0.5, flipperBounce: 0.55, flipperSpeed: 22, bumperKick: 450, saveSeconds: 10, lockSeconds: 3 };
export const RANGES = {
  gravity: { min: 300, max: 1800, step: 25, label: 'Gravity (how heavy the ball feels)' },
  wallBounce: { min: 0.1, max: 0.9, step: 0.05, label: 'Wall bounce' },
  flipperBounce: { min: 0.2, max: 0.9, step: 0.05, label: 'Flipper bounce' },
  flipperSpeed: { min: 10, max: 40, step: 1, label: 'Flipper swing speed' },
  bumperKick: { min: 200, max: 900, step: 10, label: 'Bumper kick' },
  saveSeconds: { min: 0, max: 30, step: 1, label: 'Ball save after launch (seconds, 0 = off)' },
  lockSeconds: { min: 1, max: 6, step: 0.5, label: 'Ball lock time (seconds)' },
};

/** One-click feels: easy is heavier-forgiving (a lighter ball, quicker flippers, a long ball save, a short lock), hard the opposite. */
export const PRESETS = {
  easy: { gravity: 750, wallBounce: 0.5, flipperBounce: 0.6, flipperSpeed: 28, bumperKick: 500, saveSeconds: 20, lockSeconds: 2 },
  normal: { ...DEFAULTS },
  hard: { gravity: 1100, wallBounce: 0.45, flipperBounce: 0.5, flipperSpeed: 20, bumperKick: 400, saveSeconds: 4, lockSeconds: 4 },
};

/** A usable value for a setting, kept inside its range, or null when the name or the value is not valid. */
export function clampTuning(key, value) {
  const r = RANGES[key];
  const n = typeof value === 'string' && value.trim() !== '' ? Number(value) : value;
  if (!r || typeof n !== 'number' || !Number.isFinite(n)) return null;
  return Math.min(r.max, Math.max(r.min, n));
}

export function setTuning(g, key, value) { const v = clampTuning(key, value); if (v !== null) g.tuning[key] = v; }
export function resetTuning(g) { g.tuning = { ...DEFAULTS }; }

export function applyPreset(g, name) {
  if (!Object.prototype.hasOwnProperty.call(PRESETS, name)) return false;
  g.tuning = { ...PRESETS[name] };
  return true;
}

/** 'easy', 'normal' or 'hard' when the settings match one exactly, otherwise 'custom'. */
export function presetOf(tuning) {
  for (const [name, p] of Object.entries(PRESETS)) if (Object.keys(DEFAULTS).every((k) => tuning[k] === p[k])) return name;
  return 'custom';
}
