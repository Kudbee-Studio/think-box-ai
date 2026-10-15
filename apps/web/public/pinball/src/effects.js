// Things that make hits feel like hits: a flash and floating score on a bumper, sparks, a ball trail and a short screen shake. Visual only; nothing here touches the rules.
// Every list is capped and everything fades on its own. With "reduced motion" the shake is off.
const SHAKE = { bumper: 2, 'flipper-hit': 3, drain: 8, over: 12 };
const MAX_SHAKE = 12; const TRAIL = 12;

/** The score shown on screen counts up to the real score (never past it) and drops straight down when the score resets. */
export function easeScore(shown, target, dt) {
  if (target <= shown) return target;
  return Math.min(target, shown + Math.max(3, Math.ceil((target - shown) * 8 * dt)));
}

export function createEffects({ reducedMotion = false } = {}) {
  const fx = {
    flashes: [], popups: [], sparks: [], trailPoints: [], shake: 0, banner: null, callout: null, multiplierFlash: 0, shown: 0, pendingBonus: null,
    handle(e) {
      if (e.type === 'combo') fx.callout = { text: `COMBO x${e.combo}`, life: 1 };
      else if (e.type === 'multiplier') fx.multiplierFlash = 0.8;
      else if (e.type === 'bonus') fx.pendingBonus = e;
      else if (e.type === 'launch') fx.banner = null;
      else if (e.type === 'drain') {
        const b = fx.pendingBonus; fx.pendingBonus = null;
        fx.banner = { title: 'Ball lost', lines: b ? [`Bonus ${b.pts}  (${b.hits} hits x${b.multiplier})`] : [], life: 2.2 };
      } else if (e.type === 'over') fx.banner = null;
      const bump = SHAKE[e.type] ?? 0;
      if (bump && !reducedMotion) fx.shake = Math.min(MAX_SHAKE, fx.shake + bump);
      if (e.type === 'bumper') {
        fx.flashes.push({ x: e.x, y: e.y, life: 0.25 }); if (fx.flashes.length > 12) fx.flashes.shift();
        fx.popups.push({ x: e.x, y: e.y - 30, text: `+${e.pts}`, life: 0.8, size: Math.min(34, 16 + Math.floor(e.pts / 50)) }); if (fx.popups.length > 12) fx.popups.shift();
        for (let i = 0; i < 8; i++) { const a = (i / 8) * Math.PI * 2; fx.sparks.push({ x: e.x, y: e.y, vx: Math.cos(a) * 140, vy: Math.sin(a) * 140, life: 0.5 }); }
        if (fx.sparks.length > 120) fx.sparks.splice(0, fx.sparks.length - 120);
      }
    },
    trail(x, y) { fx.trailPoints.push({ x, y }); if (fx.trailPoints.length > TRAIL) fx.trailPoints.shift(); },
    clearTrail() { fx.trailPoints.length = 0; },
    update(dt) {
      for (const f of fx.flashes) f.life -= dt; fx.flashes = fx.flashes.filter((f) => f.life > 0);
      for (const p of fx.popups) { p.life -= dt; p.y -= 30 * dt; } fx.popups = fx.popups.filter((p) => p.life > 0);
      for (const s of fx.sparks) { s.life -= dt; s.x += s.vx * dt; s.y += s.vy * dt; } fx.sparks = fx.sparks.filter((s) => s.life > 0);
      fx.shake = Math.max(0, fx.shake - 30 * dt);
      fx.multiplierFlash = Math.max(0, fx.multiplierFlash - dt);
      if (fx.callout) { fx.callout.life -= dt; if (fx.callout.life <= 0) fx.callout = null; }
      if (fx.banner) { fx.banner.life -= dt; if (fx.banner.life <= 0) fx.banner = null; }
    },
    /** How far to move the picture this frame: zero when calm. */
    offset() { return fx.shake > 0 ? { x: (Math.random() * 2 - 1) * fx.shake, y: (Math.random() * 2 - 1) * fx.shake } : { x: 0, y: 0 }; },
  };
  return fx;
}
