// Draws a game onto a canvas. All the rules live in game.js; this only reads the state.
import { WIDTH, HEIGHT, BALL_R, flipperTip } from './game.js';

function line(ctx, x1, y1, x2, y2, w, color) { ctx.strokeStyle = color; ctx.lineWidth = w; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); }
function text(ctx, s, x, y, size = 16, color = '#e6edf3', align = 'center') { ctx.fillStyle = color; ctx.font = `${size}px system-ui, sans-serif`; ctx.textAlign = align; ctx.fillText(s, x, y); }

export function draw(ctx, g, walls, fx) {
  ctx.fillStyle = '#0d1117'; ctx.fillRect(0, 0, WIDTH, HEIGHT);
  ctx.save();
  if (fx) { const o = fx.offset(); ctx.translate(o.x, o.y); }
  for (const w of walls) line(ctx, w.x1, w.y1, w.x2, w.y2, w.oneWay ? 3 : 4, w.oneWay ? '#3fb950' : '#58a6ff');
  for (const b of g.bumpers) {
    const hot = g.time - g.lastHit < 0.12 && g.lastBumper === b;
    ctx.fillStyle = hot ? '#ffa657' : '#bc4c00'; ctx.beginPath(); ctx.arc(b.x, b.y, b.r, 0, 6.283); ctx.fill();
    ctx.strokeStyle = '#f0e68c'; ctx.lineWidth = 3; ctx.stroke();
  }
  for (const side of ['left', 'right']) { const f = g.flippers[side]; const t = flipperTip(g, side); line(ctx, f.px, f.py, t.x, t.y, 12, '#f0e68c'); }
  if (fx) {
    fx.trailPoints.forEach((p, i) => { ctx.fillStyle = `rgba(230,237,243,${(i / fx.trailPoints.length) * 0.35})`; ctx.beginPath(); ctx.arc(p.x, p.y, BALL_R * (0.4 + 0.5 * (i / fx.trailPoints.length)), 0, 6.283); ctx.fill(); });
    for (const f of fx.flashes) { ctx.fillStyle = `rgba(255,220,120,${f.life * 2})`; ctx.beginPath(); ctx.arc(f.x, f.y, 26 + (0.25 - f.life) * 60, 0, 6.283); ctx.fill(); }
    ctx.fillStyle = '#ffd37a'; for (const s of fx.sparks) ctx.fillRect(s.x, s.y, 3, 3);
  }
  ctx.fillStyle = '#e6edf3'; ctx.beginPath(); ctx.arc(g.ball.x, g.ball.y, BALL_R, 0, 6.283); ctx.fill();
  if (fx) for (const p of fx.popups) text(ctx, p.text, p.x, p.y, 18, `rgba(255,211,122,${Math.min(1, p.life * 1.5)})`);
  ctx.restore();
  if (g.state === 'ready' && g.charge > 0) { ctx.fillStyle = '#3fb950'; const h = 120 * g.charge; ctx.fillRect(466, 780 - h, 8, h); }

  text(ctx, `Score ${g.score}`, 28, 28, 18, '#e6edf3', 'left');
  text(ctx, `Ball ${Math.min(3, 4 - g.ballsLeft)} of 3`, WIDTH - 28, 28, 14, '#8b949e', 'right');
  if (g.multiplier > 1) text(ctx, `x${g.multiplier}`, WIDTH / 2, 28, 22, '#ffa657');

  if (g.state === 'title') {
    ctx.fillStyle = 'rgba(1,4,9,0.8)'; ctx.fillRect(40, 250, WIDTH - 80, 250);
    text(ctx, 'PINBALL', WIDTH / 2, 320, 48, '#58a6ff');
    text(ctx, 'Z / ← left flipper   M / → right flipper', WIDTH / 2, 370, 14, '#8b949e');
    text(ctx, 'Hold Space to pull the plunger, let go to launch', WIDTH / 2, 392, 14, '#8b949e');
    text(ctx, 'Press Enter or tap to start', WIDTH / 2, 440, 20);
    text(ctx, 'S sound on/off   T change how it feels', WIDTH / 2, 462, 12, '#8b949e');
    if (g.best) text(ctx, `Best ${g.best}`, WIDTH / 2, 490, 16, '#d29922');
  } else if (g.state === 'ready') {
    text(ctx, 'Hold Space, then let go', 230, 600, 14, '#8b949e');
  } else if (g.state === 'paused') {
    text(ctx, 'Paused', WIDTH / 2, 400, 36); text(ctx, 'Press P to continue', WIDTH / 2, 435, 16, '#8b949e');
  } else if (g.state === 'over') {
    ctx.fillStyle = 'rgba(1,4,9,0.8)'; ctx.fillRect(40, 280, WIDTH - 80, 200);
    text(ctx, 'Game over', WIDTH / 2, 340, 40, '#f85149');
    text(ctx, `Score ${g.score}   Best ${g.best}`, WIDTH / 2, 385, 20);
    text(ctx, 'Press Enter or tap to play again', WIDTH / 2, 430, 16, '#8b949e');
  }
}
