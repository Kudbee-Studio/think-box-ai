// Draws a game onto a canvas. All the rules live in game.js; this only reads the state.
import { WIDTH, HEIGHT } from './game.js';

const stars = Array.from({ length: 60 }, (_, i) => ({ x: (i * 97) % WIDTH, y: (i * 211) % HEIGHT, s: 0.5 + (i % 3) * 0.5 }));

function ship(ctx, p, blink) {
  if (blink) return;
  ctx.fillStyle = '#58a6ff';
  ctx.beginPath(); ctx.moveTo(p.x, p.y - p.r); ctx.lineTo(p.x + p.r, p.y + p.r * 0.8); ctx.lineTo(p.x, p.y + p.r * 0.4); ctx.lineTo(p.x - p.r, p.y + p.r * 0.8); ctx.closePath(); ctx.fill();
}

function text(ctx, s, x, y, size = 16, color = '#e6edf3', align = 'center') {
  ctx.fillStyle = color; ctx.font = `${size}px system-ui, sans-serif`; ctx.textAlign = align; ctx.fillText(s, x, y);
}

export function draw(ctx, g) {
  ctx.fillStyle = '#0d1117'; ctx.fillRect(0, 0, WIDTH, HEIGHT);
  ctx.fillStyle = '#30363d';
  for (const s of stars) { const y = (s.y + g.time * 30 * s.s) % HEIGHT; ctx.fillRect(s.x, y, s.s, s.s); }

  ctx.fillStyle = '#f85149';
  for (const e of g.enemies) { ctx.beginPath(); ctx.arc(e.x, e.y, e.r, 0, 6.283); ctx.fill(); }
  ctx.fillStyle = '#f0e68c';
  for (const b of g.bullets) ctx.fillRect(b.x - 2, b.y - 8, 4, 12);
  ctx.fillStyle = '#ffa657';
  for (const q of g.particles) ctx.fillRect(q.x, q.y, 3, 3);
  if (g.state !== 'title') ship(ctx, g.player, g.player.invulnerable > 0 && Math.floor(g.time * 10) % 2 === 0);

  if (g.state !== 'title') {
    text(ctx, `Score ${g.score}`, 12, 24, 16, '#e6edf3', 'left');
    text(ctx, `Level ${g.level}`, WIDTH / 2, 24);
    text(ctx, `Lives ${'♥'.repeat(g.lives)}`, WIDTH - 12, 24, 16, '#f85149', 'right');
  }
  if (g.state === 'title') {
    text(ctx, 'STARFALL', WIDTH / 2, 230, 48, '#58a6ff');
    text(ctx, 'Arrow keys or A/D to move, Space to fire, P to pause', WIDTH / 2, 290, 14, '#8b949e');
    text(ctx, 'Press Enter or tap to start', WIDTH / 2, 340, 20);
    if (g.best) text(ctx, `Best ${g.best}`, WIDTH / 2, 380, 16, '#d29922');
  } else if (g.state === 'paused') {
    text(ctx, 'Paused', WIDTH / 2, 300, 36); text(ctx, 'Press P to continue', WIDTH / 2, 335, 16, '#8b949e');
  } else if (g.state === 'over') {
    text(ctx, 'Game over', WIDTH / 2, 280, 40, '#f85149');
    text(ctx, `Score ${g.score}   Best ${g.best}`, WIDTH / 2, 325, 20);
    text(ctx, 'Press Enter or tap to play again', WIDTH / 2, 370, 16, '#8b949e');
  }
}
