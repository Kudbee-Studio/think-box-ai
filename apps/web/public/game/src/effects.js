// What makes hits feel like hits: a short screen shake, floating scores, flashes, call-out banners and the stars drifting past. Visual only; nothing here touches the rules.
// Every list is capped and everything fades on its own. With "reduced motion" the shake is off.
const SHAKE = { hit: 9, 'shield-break': 5, boss: 4, 'boss-down': 12, over: 12, bomb: 9, 'boss-enrage': 6 };
const MAX_SHAKE = 14;

export function createEffects({ reducedMotion = false } = {}) {
  const fx = {
    popups: [], banner: null, shake: 0, flash: 0, white: 0,
    handle(e) {
      const bump = SHAKE[e.type] ?? (e.type === 'kill' && e.big ? 3 : 0);
      if (bump && !reducedMotion) fx.shake = Math.min(MAX_SHAKE, fx.shake + bump);
      if (e.type === 'kill' || e.type === 'boss-down') { fx.popups.push({ x: e.x, y: e.y - 10, text: `+${e.pts}`, life: 0.8, size: Math.min(30, 13 + Math.floor(e.pts / 20)) }); if (fx.popups.length > 14) fx.popups.shift(); }
      if (e.type === 'hit') fx.flash = 0.35;
      if (e.type === 'bomb') fx.white = 0.45;
      if (e.type === 'boss-enrage') fx.banner = { text: 'ENRAGED!', sub: '', life: 1.4 };
      if (e.type === 'perfect') { fx.popups.push({ x: 240, y: 330, text: `PERFECT WAVE +${e.pts}`, life: 1.8, size: 22 }); if (fx.popups.length > 14) fx.popups.shift(); }
      if (e.type === 'summon') fx.popups.push({ x: e.x, y: e.y + 60, text: 'REINFORCEMENTS', life: 1, size: 13 });
      if (e.type === 'wave') fx.banner = { text: `WAVE ${e.wave}`, sub: e.wave > 1 && e.wave % 5 === 0 ? 'BOSS INCOMING' : '', life: 2 };
      if (e.type === 'boss') fx.banner = { text: 'BOSS', sub: '', life: 1.6 };
      if (e.type === 'boss-down') fx.banner = { text: 'BOSS DOWN', sub: '', life: 2 };
      if (e.type === 'pickup' && e.kind !== 'token') fx.popups.push({ x: e.x, y: e.y - 12, text: e.kind === 'life' ? '+1 LIFE' : e.kind === 'weapon' ? (e.weapon ?? 'WEAPON').toUpperCase() : e.kind === 'rapid' ? 'OVERCLOCK' : e.kind.toUpperCase(), life: 0.9, size: 14 });
      if (e.type === 'weapon') fx.banner = { text: String(e.weapon).toUpperCase(), sub: `LEVEL ${e.level}`, life: 1.1 };
      if (e.type === 'weapon-up') fx.banner = { text: e.max ? 'MAX LEVEL +500' : 'WEAPON UP!', sub: e.max ? '' : `${String(e.weapon).toUpperCase()} LEVEL ${e.level}`, life: 1.3 };
      if (e.type === 'combo' && e.combo % 5 === 0) fx.popups.push({ x: 240, y: 560, text: `COMBO x${e.multiplier}`, life: 0.9, size: 18 });
    },
    update(dt) {
      for (const p of fx.popups) { p.life -= dt; p.y -= 34 * dt; } fx.popups = fx.popups.filter((p) => p.life > 0);
      if (fx.banner) { fx.banner.life -= dt; if (fx.banner.life <= 0) fx.banner = null; }
      fx.shake = Math.max(0, fx.shake - 36 * dt); fx.flash = Math.max(0, fx.flash - dt); fx.white = Math.max(0, fx.white - dt);
    },
    /** How far to move the picture this frame: zero when calm. */
    offset() { return fx.shake > 0 ? { x: (Math.random() * 2 - 1) * fx.shake, y: (Math.random() * 2 - 1) * fx.shake } : { x: 0, y: 0 }; },
  };
  return fx;
}
