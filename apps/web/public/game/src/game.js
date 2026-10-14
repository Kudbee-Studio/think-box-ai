// Starfall's rules. Pure: no canvas, no keyboard, no clock. The page feeds it input and time and draws what it holds, so everything here can be tested by calling step().
export const WIDTH = 480;
export const HEIGHT = 640;
const MAX_DT = 1 / 30; // a long frame (tab in the background) is cut so nothing jumps through anything
const PLAYER_SPEED = 320;
const FIRE_EVERY = 0.18;
const BULLET_SPEED = 640;
const SAFE_SECONDS = 2;
const KILLS_PER_LEVEL = 10;

/** Small seeded random numbers (mulberry32): the same seed always plays out the same way. */
function rand(g) {
  g.rng = (g.rng + 0x6d2b79f5) | 0;
  let t = g.rng;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}

export function createGame(seed = 1) {
  const g = { rng: seed | 0, state: 'title', best: 0 };
  reset(g);
  return g;
}

function reset(g) {
  g.player = { x: WIDTH / 2, y: HEIGHT - 60, r: 18, cool: 0, invulnerable: 0 };
  g.bullets = []; g.enemies = []; g.particles = [];
  g.score = 0; g.kills = 0; g.level = 1; g.lives = 3; g.spawned = 0; g.time = 0;
  g.spawnTimer = 0.6;
}

export function startGame(g) { reset(g); g.state = 'playing'; }
export function togglePause(g) { if (g.state === 'playing') g.state = 'paused'; else if (g.state === 'paused') g.state = 'playing'; }

const spawnEvery = (level) => Math.max(0.25, 1.1 - 0.1 * (level - 1));
const enemySpeed = (level) => 70 + 12 * level;

function spawn(g) {
  const r = 14 + rand(g) * 6;
  g.enemies.push({ x: r + rand(g) * (WIDTH - 2 * r), y: -r, r, vy: enemySpeed(g.level) * (0.8 + rand(g) * 0.5), drift: 20 + rand(g) * 50, phase: rand(g) * 6.28, hp: 1 });
  g.spawned++;
}

function explode(g, x, y) {
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * 6.283 + rand(g);
    g.particles.push({ x, y, vx: Math.cos(a) * (60 + rand(g) * 80), vy: Math.sin(a) * (60 + rand(g) * 80), life: 0.5 });
  }
}

const touching = (a, b) => (a.x - b.x) ** 2 + (a.y - b.y) ** 2 < (a.r + b.r) ** 2;

export function step(g, input, rawDt) {
  if (g.state !== 'playing') return;
  const dt = Math.min(Math.max(rawDt, 0), MAX_DT);
  g.time += dt;
  const p = g.player;

  p.x += ((input.right ? 1 : 0) - (input.left ? 1 : 0)) * PLAYER_SPEED * dt;
  p.x = Math.min(WIDTH - p.r, Math.max(p.r, p.x));
  p.cool = Math.max(0, p.cool - dt);
  p.invulnerable = Math.max(0, p.invulnerable - dt);
  if (input.fire && p.cool === 0) { g.bullets.push({ x: p.x, y: p.y - p.r, r: 3, vy: -BULLET_SPEED }); p.cool = FIRE_EVERY; }

  for (const b of g.bullets) b.y += b.vy * dt;
  g.bullets = g.bullets.filter((b) => b.y > -10);

  g.spawnTimer -= dt;
  if (g.spawnTimer <= 0) { spawn(g); g.spawnTimer += spawnEvery(g.level); }
  for (const e of g.enemies) { e.y += e.vy * dt; e.phase += dt * 2; e.x = Math.min(WIDTH - e.r, Math.max(e.r, e.x + Math.sin(e.phase) * e.drift * dt)); }

  for (const b of g.bullets) {
    for (const e of g.enemies) {
      if (b.dead || e.hp <= 0 || !touching(b, e)) continue;
      b.dead = true; e.hp--;
      if (e.hp <= 0) { g.score += 10; g.kills++; g.level = 1 + Math.floor(g.kills / KILLS_PER_LEVEL); explode(g, e.x, e.y); }
    }
  }
  g.bullets = g.bullets.filter((b) => !b.dead);
  g.enemies = g.enemies.filter((e) => e.hp > 0);

  for (const e of g.enemies) {
    if (!touching(e, p)) continue;
    e.hp = 0; explode(g, e.x, e.y);
    if (p.invulnerable === 0) { g.lives--; p.invulnerable = SAFE_SECONDS; }
  }
  g.enemies = g.enemies.filter((e) => e.hp > 0 && e.y < HEIGHT + 30);

  for (const q of g.particles) { q.x += q.vx * dt; q.y += q.vy * dt; q.life -= dt; }
  g.particles = g.particles.filter((q) => q.life > 0);

  if (g.lives <= 0) { g.lives = 0; g.state = 'over'; g.best = Math.max(g.best, g.score); }
}
