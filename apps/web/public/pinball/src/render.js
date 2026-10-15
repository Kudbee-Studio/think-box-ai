// Draws a game onto a canvas. All the rules live in game.js; this only reads the state. Effects that float over the table (popups, call-outs) are drawn BEFORE the ball,
// and the ball-lost banner only shows while the next ball waits in the lane, so the ball in play is never covered.
import { WIDTH, HEIGHT, BALL_R, flipperTip } from './game.js';

function line(ctx, x1, y1, x2, y2, w, color) { ctx.strokeStyle = color; ctx.lineWidth = w; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); }
function text(ctx, s, x, y, size = 16, color = '#e6edf3', align = 'center') { ctx.fillStyle = color; ctx.font = `${size}px system-ui, sans-serif`; ctx.textAlign = align; ctx.fillText(s, x, y); }
const fmt = (n) => Math.round(n).toLocaleString('en-US');

function hud(ctx, g, fx) {
  const shown = fx ? fx.shown : g.score;
  text(ctx, fmt(shown), 28, 34, 26, '#e6edf3', 'left');
  if (g.combo >= 3) text(ctx, `Combo x${g.combo}`, 28, 54, 13, '#d29922', 'left');
  const flash = fx ? fx.multiplierFlash : 0;
  if (g.multiplier > 1) text(ctx, `x${g.multiplier}`, WIDTH / 2, 34, 22 + flash * 20, flash > 0 ? '#ffd37a' : '#ffa657');
  for (let i = 0; i < 3; i++) { // balls left, the one in play included
    ctx.fillStyle = i < g.ballsLeft ? '#e6edf3' : '#30363d'; ctx.beginPath(); ctx.arc(WIDTH - 30 - i * 22, 30, 7, 0, 6.283); ctx.fill();
  }
  text(ctx, `Ball ${Math.min(3, 4 - Math.max(1, g.ballsLeft))} of 3`, WIDTH - 28, 54, 12, '#8b949e', 'right');
}

function panel(ctx, y, h) { ctx.fillStyle = 'rgba(1,4,9,0.85)'; ctx.fillRect(50, y, 380, h); ctx.strokeStyle = '#30363d'; ctx.lineWidth = 1; ctx.strokeRect(50.5, y + 0.5, 379, h - 1); } // inside the playfield: never over the launch lane

export function draw(ctx, g, walls, fx) {
  ctx.fillStyle = '#0d1117'; ctx.fillRect(0, 0, WIDTH, HEIGHT);
  ctx.save();
  if (fx) { const o = fx.offset(); ctx.translate(o.x, o.y); }
  for (const w of walls) line(ctx, w.x1, w.y1, w.x2, w.y2, w.thick ? w.thick * 2 : w.oneWay ? 3 : 4, w.oneWay ? '#3fb950' : '#58a6ff');
  for (const b of g.bumpers) {
    const hot = g.time - g.lastHit < 0.12 && g.lastBumper === b;
    ctx.fillStyle = hot ? '#ffa657' : '#bc4c00'; ctx.beginPath(); ctx.arc(b.x, b.y, b.r, 0, 6.283); ctx.fill();
    ctx.strokeStyle = '#f0e68c'; ctx.lineWidth = 3; ctx.stroke();
  }
  for (const side of ['left', 'right']) { const f = g.flippers[side]; const t = flipperTip(g, side); line(ctx, f.px, f.py, t.x, t.y, 12, '#f0e68c'); }
  if (g.state === 'ready' && g.charge > 0) { ctx.fillStyle = '#3fb950'; const h = 120 * g.charge; ctx.fillRect(466, 780 - h, 8, h); }
  if (fx) {
    fx.trailPoints.forEach((p, i) => { ctx.fillStyle = `rgba(230,237,243,${(i / fx.trailPoints.length) * 0.35})`; ctx.beginPath(); ctx.arc(p.x, p.y, BALL_R * (0.4 + 0.5 * (i / fx.trailPoints.length)), 0, 6.283); ctx.fill(); });
    for (const f of fx.flashes) { ctx.fillStyle = `rgba(255,220,120,${f.life * 2})`; ctx.beginPath(); ctx.arc(f.x, f.y, 26 + (0.25 - f.life) * 60, 0, 6.283); ctx.fill(); }
    ctx.fillStyle = '#ffd37a'; for (const s of fx.sparks) ctx.fillRect(s.x, s.y, 3, 3);
    for (const p of fx.popups) text(ctx, p.text, p.x, p.y, p.size, `rgba(255,211,122,${Math.min(1, p.life * 1.5)})`);
    if (fx.callout) text(ctx, fx.callout.text, WIDTH / 2, 150, 30, `rgba(255,163,87,${Math.min(1, fx.callout.life * 2)})`);
  }
  ctx.fillStyle = '#e6edf3'; ctx.beginPath(); ctx.arc(g.ball.x, g.ball.y, BALL_R, 0, 6.283); ctx.fill();
  ctx.restore();

  hud(ctx, g, fx);

  if (g.state === 'title') {
    panel(ctx, 250, 270);
    text(ctx, 'PINBALL', WIDTH / 2, 320, 48, '#58a6ff');
    text(ctx, 'Z / ← left flipper   M / → right flipper', WIDTH / 2, 370, 14, '#8b949e');
    text(ctx, 'Hold Space to pull the plunger, let go to launch', WIDTH / 2, 392, 14, '#8b949e');
    text(ctx, 'Quick bumper hits build a combo; every 5 hits raises the multiplier', WIDTH / 2, 414, 11, '#8b949e');
    text(ctx, 'Press Enter or tap to start', WIDTH / 2, 456, 20);
    text(ctx, 'S sound on/off   T change how it feels', WIDTH / 2, 480, 12, '#8b949e');
    if (g.best) text(ctx, `Best ${fmt(g.best)}`, WIDTH / 2, 506, 16, '#d29922');
  } else if (g.state === 'ready') {
    if (fx && fx.banner) {
      panel(ctx, 470, 60 + fx.banner.lines.length * 24);
      text(ctx, fx.banner.title, WIDTH / 2, 505, 24, '#f85149');
      fx.banner.lines.forEach((l, i) => text(ctx, l, WIDTH / 2, 534 + i * 24, 15, '#ffd37a'));
    }
    text(ctx, 'Hold Space, then let go', 230, 600, 14, '#8b949e');
  } else if (g.state === 'paused') {
    panel(ctx, 360, 100); text(ctx, 'Paused', WIDTH / 2, 410, 36); text(ctx, 'Press P to continue', WIDTH / 2, 445, 16, '#8b949e');
  } else if (g.state === 'over') {
    panel(ctx, 250, 270);
    text(ctx, 'Game over', WIDTH / 2, 305, 38, '#f85149');
    text(ctx, fmt(g.score), WIDTH / 2, 360, 44);
    if (g.newBest) text(ctx, 'NEW BEST!', WIDTH / 2, 392, 20, '#ffd37a'); else text(ctx, `Best ${fmt(g.best)}`, WIDTH / 2, 392, 16, '#d29922');
    if (g.lastBall && g.lastBall.bonus > 0) text(ctx, `Last ball bonus ${fmt(g.lastBall.bonus)}`, WIDTH / 2, 420, 14, '#8b949e');
    const ready = !fx || fx.restartReady;
    text(ctx, ready ? 'Press Enter or tap to play again' : '…', WIDTH / 2, 480, 16, ready ? '#e6edf3' : '#8b949e');
  }
}
