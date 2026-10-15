// Draws a game onto a canvas. All the rules live in game.js; this only reads the state.
import { WIDTH, HEIGHT, sectorOf } from './game.js';

const STARS = Array.from({ length: 70 }, (_, i) => ({ x: (i * 97) % WIDTH, y: (i * 211) % HEIGHT, layer: i % 3 }));
const POWER = { rapid: ['#f0e68c', 'R'], spread: ['#58a6ff', 'S'], shield: ['#3fb950', '◇'], life: ['#f85149', '+'], bomb: ['#ffa657', 'B'] };
const BOSS_COLOR = { gunship: '#bc4c9e', spiral: '#d29922', summoner: '#2ea043' };

function text(ctx, s, x, y, size = 16, color = '#e6edf3', align = 'center', weight = '') { ctx.fillStyle = color; ctx.font = `${weight} ${size}px system-ui, sans-serif`; ctx.textAlign = align; ctx.fillText(s, x, y); }
function poly(ctx, pts, fill) { ctx.fillStyle = fill; ctx.beginPath(); pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y))); ctx.closePath(); ctx.fill(); }
function circle(ctx, x, y, r, fill) { ctx.fillStyle = fill; ctx.beginPath(); ctx.arc(x, y, r, 0, 6.283); ctx.fill(); }

function ship(ctx, g) {
  const p = g.player; if (p.invulnerable > 0 && Math.floor(g.time * 12) % 2 === 0) return;
  const flame = 8 + Math.sin(g.time * 60) * 4; poly(ctx, [[p.x - 6, p.y + 12], [p.x, p.y + 12 + flame], [p.x + 6, p.y + 12]], '#ffa657');
  poly(ctx, [[p.x, p.y - p.r], [p.x + p.r, p.y + 13], [p.x, p.y + 6], [p.x - p.r, p.y + 13]], '#58a6ff'); poly(ctx, [[p.x, p.y - 8], [p.x + 4, p.y + 2], [p.x - 4, p.y + 2]], '#cae8ff');
  if (p.shield > 0) { ctx.strokeStyle = `rgba(63,185,80,${0.5 + 0.3 * Math.sin(g.time * 8)})`; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(p.x, p.y, p.r + 8, 0, 6.283); ctx.stroke(); }
}

function enemy(ctx, e) {
  const c = e.flash > 0 ? '#ffffff' : null;
  switch (e.type) {
    case 'drifter': circle(ctx, e.x, e.y, e.r, c ?? '#f85149'); circle(ctx, e.x, e.y, e.r * 0.5, c ?? '#8e1519'); break;
    case 'zigzag': poly(ctx, [[e.x, e.y - e.r - 3], [e.x + e.r + 3, e.y], [e.x, e.y + e.r + 3], [e.x - e.r - 3, e.y]], c ?? '#ffa657'); break;
    case 'tank': poly(ctx, [0, 1, 2, 3, 4, 5].map((i) => [e.x + Math.cos(i * 1.047) * e.r, e.y + Math.sin(i * 1.047) * e.r]), c ?? '#8b949e'); for (let i = 0; i < e.hp; i++) circle(ctx, e.x - 8 + i * 8, e.y, 3, '#0d1117'); break;
    case 'shooter': poly(ctx, [[e.x - e.r, e.y - 8], [e.x + e.r, e.y - 8], [e.x + 8, e.y + 10], [e.x - 8, e.y + 10]], c ?? '#a371f7'); ctx.fillStyle = c ?? '#d2a8ff'; ctx.fillRect(e.x - 3, e.y + 6, 6, 14); break;
    case 'swooper': poly(ctx, [[e.x, e.y + e.r + 4], [e.x + e.r, e.y - e.r], [e.x - e.r, e.y - e.r]], c ?? '#f0e68c'); break;
    case 'boss':
      if (e.enraged) circle(ctx, e.x, e.y, e.r + 8 + Math.sin(e.t * 12) * 3, 'rgba(248,81,73,0.35)');
      poly(ctx, [0, 1, 2, 3, 4, 5, 6, 7].map((i) => [e.x + Math.cos(i * 0.785 + 0.39) * e.r, e.y + Math.sin(i * 0.785 + 0.39) * e.r]), c ?? BOSS_COLOR[e.kind] ?? '#bc4c9e'); circle(ctx, e.x, e.y, e.r * 0.45, c ?? '#ffd37a'); circle(ctx, e.x, e.y, e.r * 0.2, e.enraged ? '#f85149' : '#8e1519'); break;
  }
}

function hud(ctx, g, fx) {
  text(ctx, g.score.toLocaleString('en-US'), 14, 28, 22, '#e6edf3', 'left', 'bold');
  if (g.multiplier > 1) text(ctx, `x${g.multiplier}`, 14, 50, 16, '#ffd37a', 'left', 'bold');
  text(ctx, `WAVE ${g.wave}`, WIDTH / 2, 24, 14, '#8b949e'); text(ctx, sectorOf(g.wave).name, WIDTH / 2, 40, 10, '#6e7681');
  for (let i = 0; i < g.bombs; i++) { circle(ctx, WIDTH - 20 - i * 24, HEIGHT - 22, 8, '#ffa657'); text(ctx, 'B', WIDTH - 20 - i * 24, HEIGHT - 18, 10, '#0d1117', 'center', 'bold'); }
  for (let i = 0; i < Math.min(5, Math.max(3, g.lives)); i++) circle(ctx, WIDTH - 20 - i * 20, 22, 6, i < g.lives ? '#f85149' : '#30363d');
  const bars = [['rapid', g.player.rapid, 8], ['spread', g.player.spread, 10], ['shield', g.player.shield, 12]].filter((b) => b[1] > 0);
  bars.forEach(([k, v, max], i) => { const x = 14 + i * 74; ctx.fillStyle = '#21262d'; ctx.fillRect(x, HEIGHT - 20, 64, 8); ctx.fillStyle = POWER[k][0]; ctx.fillRect(x, HEIGHT - 20, 64 * (v / max), 8); text(ctx, k.toUpperCase(), x + 32, HEIGHT - 26, 9, '#8b949e'); });
  const boss = g.enemies.find((e) => e.type === 'boss');
  if (boss) { ctx.fillStyle = '#21262d'; ctx.fillRect(90, 50, WIDTH - 180, 6); ctx.fillStyle = boss.enraged ? '#f85149' : '#bc4c9e'; ctx.fillRect(90, 50, (WIDTH - 180) * Math.max(0, boss.hp / boss.maxHp), 6); }
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
  for (const u of g.powerups) { const [col, ch] = POWER[u.kind]; circle(ctx, u.x, u.y, u.r + 2, col); circle(ctx, u.x, u.y, u.r - 2, '#0d1117'); text(ctx, ch, u.x, u.y + 5, 14, col, 'center', 'bold'); }
  for (const e of g.enemies) enemy(ctx, e);
  ctx.fillStyle = '#7ee787'; for (const b of g.bullets) ctx.fillRect(b.x - 2, b.y - 8, 4, 12);
  for (const b of g.enemyBullets) { circle(ctx, b.x, b.y, b.r + 2, 'rgba(255,166,87,0.35)'); circle(ctx, b.x, b.y, b.r, '#ffa657'); }
  ctx.fillStyle = '#ffa657'; for (const q of g.particles) { ctx.globalAlpha = Math.min(1, q.life * 2); ctx.fillRect(q.x, q.y, 3, 3); } ctx.globalAlpha = 1;
  if (g.state !== 'title') ship(ctx, g);
  if (fx) for (const p of fx.popups) text(ctx, p.text, p.x, p.y, p.size, `rgba(255,211,122,${Math.min(1, p.life * 1.5)})`, 'center', 'bold');
  ctx.restore();
  if (fx && fx.flash > 0) { ctx.fillStyle = `rgba(248,81,73,${fx.flash * 0.5})`; ctx.fillRect(0, 0, WIDTH, HEIGHT); }
  if (fx && fx.white > 0) { ctx.fillStyle = `rgba(255,255,255,${fx.white * 1.4})`; ctx.fillRect(0, 0, WIDTH, HEIGHT); }

  if (g.state !== 'title') hud(ctx, g, fx);
  if (fx && fx.banner && g.state === 'playing') { const a = Math.min(1, fx.banner.life * 1.2); text(ctx, fx.banner.text, WIDTH / 2, 250, 44, `rgba(88,166,255,${a})`, 'center', 'bold'); if (fx.banner.sub) text(ctx, fx.banner.sub, WIDTH / 2, 282, 18, `rgba(188,76,158,${a})`, 'center', 'bold'); }

  const scores = view.scores ?? [];
  if (g.state === 'title') {
    panel(ctx, 150, 360); text(ctx, 'STARFALL', WIDTH / 2, 215, 52, '#58a6ff', 'center', 'bold');
    text(ctx, 'Arrow keys or A/D to move, Space to fire', WIDTH / 2, 262, 14, '#8b949e'); text(ctx, 'Drag on a phone to fly and shoot', WIDTH / 2, 282, 14, '#8b949e');
    text(ctx, 'Collect R (rapid)  S (spread)  ◇ (shield)  + (life)', WIDTH / 2, 306, 12, '#8b949e'); text(ctx, 'Kill quickly to build a combo. A boss every 5th wave.', WIDTH / 2, 324, 12, '#8b949e');
    text(ctx, 'B drops a bomb: it clears every enemy shot', WIDTH / 2, 342, 12, '#8b949e');
    text(ctx, 'Press Enter or tap to start', WIDTH / 2, 376, 20); text(ctx, `${(view.difficulty ?? 'normal').toUpperCase()}`, WIDTH / 2, 394, 12, '#d29922', 'center', 'bold'); if (scores.length) { text(ctx, 'HIGH SCORES', WIDTH / 2, 418, 12, '#d29922', 'center', 'bold'); table(ctx, scores, 438, -1); }
    text(ctx, 'P pause   M sound   B bomb', WIDTH / 2, 504, 11, '#6e7681');
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
