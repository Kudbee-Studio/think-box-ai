// Draws a game onto a canvas. All the rules live in game.js; this only reads the state.
import { WIDTH, HEIGHT, sectorOf, ENEMY_TYPES, BOSS_STYLE, WEAPONS, MAX_WEAPON_LEVEL, TOKENS_PER_LEVEL } from './game.js';

const STARS = Array.from({ length: 70 }, (_, i) => ({ x: (i * 97) % WIDTH, y: (i * 211) % HEIGHT, layer: i % 3 }));
const POWER = { rapid: ['#f0e68c', 'O'], shield: ['#3fb950', '\u25c7'], life: ['#f85149', '+'], bomb: ['#ffa657', 'B'], token: ['#facc15', 'T'], weapon: ['#7ee787', 'W'] };
export const WEAPON_STYLE = { laser: { color: '#7ee787', letter: 'L' }, spread: { color: '#58a6ff', letter: 'S' }, missile: { color: '#ffa657', letter: 'M' }, rail: { color: '#d2a8ff', letter: 'R' } };

function text(ctx, s, x, y, size = 16, color = '#e6edf3', align = 'center', weight = '') { ctx.fillStyle = color; ctx.font = `${weight} ${size}px system-ui, sans-serif`; ctx.textAlign = align; ctx.fillText(s, x, y); }
function poly(ctx, pts, fill) { ctx.fillStyle = fill; ctx.beginPath(); pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y))); ctx.closePath(); ctx.fill(); }
function circle(ctx, x, y, r, fill) { ctx.fillStyle = fill; ctx.beginPath(); ctx.arc(x, y, r, 0, 6.283); ctx.fill(); }

/** '#rrggbb' made lighter (f > 1) or darker (f < 1). */
export function shade(hex, f) { const n = parseInt(hex.slice(1), 16); const c = (v) => Math.max(0, Math.min(255, Math.round(v * f))); return `rgb(${c((n >> 16) & 255)},${c((n >> 8) & 255)},${c(n & 255)})`; }
/** A Think Box: a cube seen from above and the right, with a glyph on its front face. s is half the width of the front face. */
function cube(ctx, x, y, s, color, glyph, flash, glyphColor = '#0b0d13') {
  const d = s * 0.5; const fx = x - s - d / 2, fy = y - s + d / 2;
  poly(ctx, [[fx, fy], [fx + d, fy - d], [fx + 2 * s + d, fy - d], [fx + 2 * s, fy]], flash ? '#ffffff' : shade(color, 1.35));
  poly(ctx, [[fx + 2 * s, fy], [fx + 2 * s + d, fy - d], [fx + 2 * s + d, fy + 2 * s - d], [fx + 2 * s, fy + 2 * s]], flash ? '#e6edf3' : shade(color, 0.6));
  ctx.fillStyle = flash ? '#ffffff' : color; ctx.fillRect(fx, fy, 2 * s, 2 * s);
  ctx.strokeStyle = 'rgba(0,0,0,0.35)'; ctx.lineWidth = 1; ctx.strokeRect(fx + 0.5, fy + 0.5, 2 * s - 1, 2 * s - 1);
  if (glyph) text(ctx, glyph, fx + s, fy + s + s * 0.42, s * 1.25, glyphColor, 'center', 'bold');
}

function ship(ctx, g) {
  const p = g.player; if (p.invulnerable > 0 && Math.floor(g.time * 12) % 2 === 0) return;
  const flame = 8 + Math.sin(g.time * 60) * 4; poly(ctx, [[p.x - 6, p.y + 12], [p.x, p.y + 12 + flame], [p.x + 6, p.y + 12]], '#ffa657');
  poly(ctx, [[p.x, p.y - p.r], [p.x + p.r, p.y + 13], [p.x, p.y + 6], [p.x - p.r, p.y + 13]], '#58a6ff'); poly(ctx, [[p.x, p.y - 8], [p.x + 4, p.y + 2], [p.x - 4, p.y + 2]], '#cae8ff');
  if (p.shield > 0) { ctx.strokeStyle = `rgba(63,185,80,${0.5 + 0.3 * Math.sin(g.time * 8)})`; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(p.x, p.y, p.r + 8, 0, 6.283); ctx.stroke(); }
}

function enemy(ctx, e) {
  const fl = e.flash > 0; const t = ENEMY_TYPES[e.type];
  ctx.save(); ctx.translate(e.x, e.y);
  switch (e.type) {
    case 'drifter': cube(ctx, 0, 0, e.r * 0.8, t.color, '?', fl); break;
    case 'zigzag': ctx.rotate(Math.sin(e.t * 3) * 0.3); cube(ctx, 0, 0, e.r * 0.85, t.color, '~', fl); break;
    case 'tank': {
      cube(ctx, 0, 0, e.r * 0.82, t.color, '', fl); const s = e.r * 0.82;
      ctx.fillStyle = '#0b0d13'; ctx.fillRect(-s * 0.4 - 4, -s * 0.05, s * 0.8, s * 0.7); ctx.strokeStyle = '#0b0d13'; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(-4, -s * 0.05, s * 0.3, Math.PI, 0); ctx.stroke(); // a padlock
      for (let i = 0; i < e.hp; i++) circle(ctx, -s * 0.7 + i * (s * 0.7) - 4, s * 0.85, 2.5, '#fff');
      break;
    }
    case 'shooter': ctx.fillStyle = fl ? '#fff' : '#6b3410'; ctx.fillRect(-4, e.r * 0.4, 8, 16); cube(ctx, 0, 0, e.r * 0.82, t.color, '>_', fl); break;
    case 'swooper': ctx.rotate(Math.atan2(0, 1) + 0.0); cube(ctx, 0, 0, e.r * 0.78, t.color, '\u00bb', fl); break;
    case 'boss': {
      const st = BOSS_STYLE[e.kind] ?? BOSS_STYLE.gunship; const s = e.r * 0.78;
      if (e.enraged) circle(ctx, 0, 0, e.r + 10 + Math.sin(e.t * 12) * 3, 'rgba(248,81,73,0.35)');
      cube(ctx, 0, 0, s, e.enraged ? '#f43f5e' : st.color, '?', fl, '#0b0d13');
      break;
    }
  }
  ctx.restore();
}

function hud(ctx, g, fx) {
  text(ctx, g.score.toLocaleString('en-US'), 14, 28, 22, '#e6edf3', 'left', 'bold');
  if (g.multiplier > 1) text(ctx, `x${g.multiplier}`, 14, 50, 16, '#ffd37a', 'left', 'bold');
  text(ctx, `WAVE ${g.wave}`, WIDTH / 2, 24, 14, '#8b949e'); text(ctx, sectorOf(g.wave).name, WIDTH / 2, 40, 10, '#6e7681');
  for (let i = 0; i < g.bombs; i++) { circle(ctx, WIDTH - 20 - i * 24, HEIGHT - 22, 8, '#ffa657'); text(ctx, 'B', WIDTH - 20 - i * 24, HEIGHT - 18, 10, '#0d1117', 'center', 'bold'); }
  for (let i = 0; i < Math.min(5, Math.max(3, g.lives)); i++) circle(ctx, WIDTH - 20 - i * 20, 22, 6, i < g.lives ? '#f85149' : '#30363d');
  Object.keys(WEAPONS).forEach((w, i) => { // the weapons: number key, letter, level pips; the one in your hands is outlined
    const own = g.player.weapons[w] > 0; const x = 14 + i * 50; const y = HEIGHT - 74; const st = WEAPON_STYLE[w];
    ctx.fillStyle = own ? '#161b22' : '#0d1117'; ctx.fillRect(x, y, 44, 30); ctx.strokeStyle = g.player.weapon === w ? st.color : '#30363d'; ctx.lineWidth = g.player.weapon === w ? 2 : 1; ctx.strokeRect(x + 0.5, y + 0.5, 43, 29);
    text(ctx, `${i + 1}`, x + 8, y + 12, 10, '#6e7681', 'center'); text(ctx, st.letter, x + 26, y + 19, 16, own ? st.color : '#30363d', 'center', 'bold');
    for (let k = 0; k < MAX_WEAPON_LEVEL; k++) { ctx.fillStyle = k < g.player.weapons[w] ? st.color : '#21262d'; ctx.fillRect(x + 6 + k * 9, y + 24, 7, 3); }
  });
  for (let k = 0; k < TOKENS_PER_LEVEL; k++) { ctx.fillStyle = k < g.tokens ? '#facc15' : '#21262d'; ctx.fillRect(14 + k * 25, HEIGHT - 38, 21, 5); } // Think Tokens towards the next weapon level
  const bars = [['rapid', g.player.rapid, 8], ['shield', g.player.shield, 12]].filter((b) => b[1] > 0);
  bars.forEach(([k, v, max], i) => { const x = 14 + i * 74; ctx.fillStyle = '#21262d'; ctx.fillRect(x, HEIGHT - 20, 64, 8); ctx.fillStyle = POWER[k][0]; ctx.fillRect(x, HEIGHT - 20, 64 * (v / max), 8); text(ctx, k === 'rapid' ? 'OVERCLOCK' : k.toUpperCase(), x + 32, HEIGHT - 24, 8, '#8b949e'); });
  const boss = g.enemies.find((e) => e.type === 'boss');
  if (boss) { text(ctx, (BOSS_STYLE[boss.kind]?.name ?? 'Mega Think Box').toUpperCase(), WIDTH / 2, 46, 9, '#8b949e'); ctx.fillStyle = '#21262d'; ctx.fillRect(90, 50, WIDTH - 180, 6); ctx.fillStyle = boss.enraged ? '#f85149' : '#bc4c9e'; ctx.fillRect(90, 50, (WIDTH - 180) * Math.max(0, boss.hp / boss.maxHp), 6); }
}

function panel(ctx, y, h) { ctx.fillStyle = 'rgba(1,4,9,0.88)'; ctx.fillRect(50, y, WIDTH - 100, h); ctx.strokeStyle = '#30363d'; ctx.lineWidth = 1; ctx.strokeRect(50.5, y + 0.5, WIDTH - 101, h - 1); }
function table(ctx, scores, y, mine) {
  scores.slice(0, 5).forEach((e, i) => text(ctx, `${i + 1}.  ${e.name}   ${e.score.toLocaleString('en-US')}`, WIDTH / 2, y + i * 20, 14, mine === i ? '#ffd37a' : '#8b949e'));
}

export function draw(ctx, g, fx, view = {}) {
  const sector = sectorOf(g.wave); ctx.fillStyle = sector.sky; ctx.fillRect(0, 0, WIDTH, HEIGHT);
  const glow = ctx.createRadialGradient(WIDTH / 2, HEIGHT + 100, 20, WIDTH / 2, HEIGHT + 100, 520); glow.addColorStop(0, sector.glow); glow.addColorStop(1, 'rgba(0,0,0,0)'); ctx.fillStyle = glow; ctx.fillRect(0, 0, WIDTH, HEIGHT);
  for (const s of STARS) { const sp = [10, 25, 50][s.layer]; const y = (s.y + g.time * sp) % HEIGHT; ctx.fillStyle = ['#30363d', '#484f58', '#8b949e'][s.layer]; ctx.fillRect(s.x, y, s.layer + 1, s.layer + 1); }
  ctx.save();
  if (fx) { const o = fx.offset(); ctx.translate(o.x, o.y); }
  for (const u of g.powerups) {
    if (u.kind === 'token') { circle(ctx, u.x, u.y, 12, 'rgba(250,204,21,0.18)'); cube(ctx, u.x, u.y, 5, '#facc15', '', false); continue; } // a Think Token
    const crate = u.kind === 'weapon' ? WEAPON_STYLE[u.weapon] : null; const [col0, ch0] = POWER[u.kind]; const col = crate?.color ?? col0; const ch = crate?.letter ?? ch0;
    circle(ctx, u.x, u.y, u.r + 2, col); circle(ctx, u.x, u.y, u.r - 2, '#0d1117'); text(ctx, ch, u.x, u.y + 5, 14, col, 'center', 'bold');
  }
  for (const e of g.enemies) enemy(ctx, e);
  for (const b of g.bullets) {
    const wc = WEAPON_STYLE[b.kind]?.color ?? '#7ee787';
    if (b.kind === 'rail') { ctx.fillStyle = wc; ctx.fillRect(b.x - b.r * 0.5, b.y - 22, b.r, 34); ctx.fillStyle = '#fff'; ctx.fillRect(b.x - 1, b.y - 22, 2, 34); }
    else if (b.kind === 'missile') { ctx.save(); ctx.translate(b.x, b.y); ctx.rotate(Math.atan2(b.vx, -b.vy)); poly(ctx, [[0, -9], [4, 6], [-4, 6]], wc); poly(ctx, [[-2, 6], [2, 6], [0, 6 + 6 + Math.sin(g.time * 50) * 3]], '#ffd37a'); ctx.restore(); }
    else { ctx.fillStyle = wc; ctx.fillRect(b.x - 2, b.y - 8, 4, 12); }
  }
  for (const b of g.enemyBullets) { circle(ctx, b.x, b.y, b.r + 2, 'rgba(255,166,87,0.35)'); circle(ctx, b.x, b.y, b.r, '#ffa657'); }
  for (const q of g.particles) { ctx.globalAlpha = Math.min(1, q.life * 2); ctx.fillStyle = q.c ?? '#ffa657'; ctx.fillRect(q.x, q.y, q.c ? 4 : 3, q.c ? 4 : 3); } ctx.globalAlpha = 1; // broken boxes fall apart in their own colour
  if (g.state !== 'title') ship(ctx, g);
  if (fx) for (const p of fx.popups) text(ctx, p.text, p.x, p.y, p.size, `rgba(255,211,122,${Math.min(1, p.life * 1.5)})`, 'center', 'bold');
  ctx.restore();
  if (fx && fx.flash > 0) { ctx.fillStyle = `rgba(248,81,73,${fx.flash * 0.5})`; ctx.fillRect(0, 0, WIDTH, HEIGHT); }
  if (fx && fx.white > 0) { ctx.fillStyle = `rgba(255,255,255,${fx.white * 1.4})`; ctx.fillRect(0, 0, WIDTH, HEIGHT); }

  if (g.state !== 'title') hud(ctx, g, fx);
  if (fx && fx.banner && g.state === 'playing') { const a = Math.min(1, fx.banner.life * 1.2); text(ctx, fx.banner.text, WIDTH / 2, 250, 44, `rgba(88,166,255,${a})`, 'center', 'bold'); if (fx.banner.sub) text(ctx, fx.banner.sub, WIDTH / 2, 282, 18, `rgba(188,76,158,${a})`, 'center', 'bold'); }

  const scores = view.scores ?? [];
  if (g.state === 'title') {
    panel(ctx, 110, 440); text(ctx, 'STARFALL', WIDTH / 2, 172, 52, '#58a6ff', 'center', 'bold'); text(ctx, 'Shoot down the Think Boxes', WIDTH / 2, 198, 15, '#e6edf3');
    Object.entries(ENEMY_TYPES).forEach(([k, t], i) => { const x = 92 + i * 74; cube(ctx, x, 244, 9, t.color, { drifter: '?', zigzag: '~', tank: '', shooter: '>_', swooper: '\u00bb' }[k], false); text(ctx, t.name.replace(' Box', ''), x, 276, 10, '#8b949e'); });
    text(ctx, 'Arrow keys or A/D move, Space fires, B drops a bomb', WIDTH / 2, 312, 13, '#8b949e'); text(ctx, '1-4 or Q/E switch weapon: Laser, Spread, Missiles, Rail', WIDTH / 2, 332, 13, '#8b949e');
    text(ctx, 'Broken boxes drop yellow Think Tokens: 8 upgrade your weapon', WIDTH / 2, 356, 12, '#facc15'); text(ctx, 'Weapon crates unlock new weapons. Getting hit costs a level.', WIDTH / 2, 374, 12, '#8b949e');
    text(ctx, 'Drag on a phone to fly and shoot', WIDTH / 2, 396, 12, '#8b949e');
    text(ctx, 'Press Enter or tap to start', WIDTH / 2, 436, 20); text(ctx, `${(view.difficulty ?? 'normal').toUpperCase()}`, WIDTH / 2, 456, 12, '#d29922', 'center', 'bold');
    if (scores.length) { text(ctx, 'HIGH SCORES', WIDTH / 2, 482, 12, '#d29922', 'center', 'bold'); table(ctx, scores.slice(0, 3), 502, -1); }
    text(ctx, 'P pause   M sound', WIDTH / 2, 576, 11, '#6e7681');
  } else if (g.state === 'paused') {
    panel(ctx, 260, 100); text(ctx, 'Paused', WIDTH / 2, 312, 36); text(ctx, 'Press P to continue', WIDTH / 2, 342, 16, '#8b949e');
  } else if (g.state === 'over') {
    panel(ctx, 110, 420); const r = g.lastRun ?? { score: g.score, wave: g.wave, kills: g.kills, accuracy: 0 };
    text(ctx, 'GAME OVER', WIDTH / 2, 162, 38, '#f85149', 'center', 'bold'); text(ctx, r.score.toLocaleString('en-US'), WIDTH / 2, 212, 44, '#e6edf3', 'center', 'bold');
    text(ctx, `Wave ${r.wave}   Kills ${r.kills}   Accuracy ${r.accuracy}%`, WIDTH / 2, 244, 14, '#8b949e');
    if (view.entering) text(ctx, 'NEW HIGH SCORE! Type your initials, press Enter', WIDTH / 2, 284, 14, '#ffd37a', 'center', 'bold');
    else if (view.rank) text(ctx, `Rank ${view.rank}`, WIDTH / 2, 284, 14, '#ffd37a');
    if (scores.length) { text(ctx, 'HIGH SCORES', WIDTH / 2, 330, 12, '#d29922', 'center', 'bold'); table(ctx, scores, 352, view.rank ? view.rank - 1 : -1); }
    const ready = view.restartReady; text(ctx, view.entering ? '' : ready ? 'Press Enter or tap to play again' : '…', WIDTH / 2, 490, 16, ready ? '#e6edf3' : '#8b949e');
  }
}
