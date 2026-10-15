// The "feel" of the table: the numbers that decide whether it plays like pinball. The page lets you change them while playing; the physics reads them every step.
export const DEFAULTS = { gravity: 900, wallBounce: 0.5, flipperBounce: 0.55, flipperSpeed: 22, bumperKick: 450 };
export const RANGES = {
  gravity: { min: 300, max: 1800, step: 25, label: 'Gravity (how heavy the ball feels)' },
  wallBounce: { min: 0.1, max: 0.9, step: 0.05, label: 'Wall bounce' },
  flipperBounce: { min: 0.2, max: 0.9, step: 0.05, label: 'Flipper bounce' },
  flipperSpeed: { min: 10, max: 40, step: 1, label: 'Flipper swing speed' },
  bumperKick: { min: 200, max: 900, step: 10, label: 'Bumper kick' },
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
