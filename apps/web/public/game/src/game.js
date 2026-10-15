// Starfall's rules. Pure: no canvas, no keyboard, no clock. The page feeds it input and time and draws what it holds, so everything here is tested by calling step().
// The game advances in fixed 1/120 s pieces whatever the frame rate, so a run plays out the same on a slow or a fast screen (same seed, same input).
export const WIDTH = 480;
export const HEIGHT = 640;
const SUB = 1 / 120;
const MAX_DT = 1 / 20; // a long frame (tab in the background) is cut so nothing jumps through anything
const PLAYER_SPEED = 320;
const TOUCH_SPEED = 520; // how fast the ship follows a finger
const FIRE_EVERY = 0.18;
const RAPID_EVERY = 0.09;
const BULLET_SPEED = 640;
const SAFE_SECONDS = 2;
const COMBO_WINDOW = 1.5;
const MAX_LIVES = 5;
const MAX_ENEMY_BULLETS = 300;
const MAX_PARTICLES = 400;
const BOSS_EVERY = 5;

/** The five ordinary enemies. (The boss is separate: see spawnEnemy.) */
export const ENEMY_TYPES = {
  drifter: { r: 16, hp: 1, pts: 10, drop: 0.08 },
  zigzag: { r: 13, hp: 1, pts: 20, drop: 0.1 },
  tank: { r: 24, hp: 3, pts: 30, drop: 0.3 },
  shooter: { r: 17, hp: 2, pts: 40, drop: 0.2 },
  swooper: { r: 14, hp: 1, pts: 25, drop: 0.12 },
};
const BOSS = { r: 44, pts: 1000 };
/** The wave an enemy type first appears in. */
const DEBUT = { drifter: 1, zigzag: 2, tank: 3, shooter: 4, swooper: 6 };
const WEIGHT = { drifter: 5, zigzag: 3, tank: 2, shooter: 2, swooper: 2 };

/** Small seeded random numbers (mulberry32): the same seed always plays out the same way. */
function mulberry(state) {
  let s = state | 0;
  return () => { s = (s + 0x6d2b79f5) | 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
function rand(g) { g.rng = (g.rng + 0x6d2b79f5) | 0; let t = g.rng; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }

export function createGame(seed = 1) {
  const g = { seed: seed | 0, rng: seed | 0, state: 'title', best: 0, lastRun: null };
  reset(g);
  return g;
}

function reset(g) {
  g.rng = g.seed;
  g.player = { x: WIDTH / 2, y: HEIGHT - 60, r: 16, cool: 0, invulnerable: 0, rapid: 0, spread: 0, shield: 0 };
  g.bullets = []; g.enemyBullets = []; g.enemies = []; g.powerups = []; g.particles = []; g.events = [];
  g.score = 0; g.kills = 0; g.lives = 3; g.time = 0; g.acc = 0;
  g.combo = 0; g.comboTimer = 0; g.multiplier = 1; g.stats = { shots: 0, hits: 0 };
  g.wave = 1; g.waveState = 'break'; g.breakTimer = 1; g.toSpawn = []; g.spawnTimer = 0;
}

export function startGame(g) { const best = g.best; reset(g); g.best = best; g.state = 'playing'; emit(g, { type: 'wave', wave: 1 }); }
export function togglePause(g) { if (g.state === 'playing') g.state = 'paused'; else if (g.state === 'paused') g.state = 'playing'; }

/** Things that happened (a kill, a hit, a pick-up, a new wave...), for sound and effects. The page reads and clears the list; it never grows past 64. */
function emit(g, e) { if (g.events.length < 64) g.events.push(e); }

/** The enemies a wave sends, in order. Wave 1 is a handful of drifters; every wave from then adds a kind or more of them, every fifth wave is a boss with escorts. The same wave always gives the same list. */
export function composeWave(n, g) {
  const rnd = mulberry((g.seed | 0) + n * 7919);
  if (n % BOSS_EVERY === 0) return ['drifter', 'drifter', 'boss', 'zigzag', 'zigzag'];
  const count = Math.min(34, 5 + 2 * n);
  const kinds = Object.keys(DEBUT).filter((k) => n >= DEBUT[k]);
  const debuting = kinds.filter((k) => DEBUT[k] === n || (n > 6 && k === 'swooper' && DEBUT[k] + 2 >= n)); // a new kind is sure to show up in its first wave
  const list = [...debuting];
  const total = kinds.reduce((s, k) => s + WEIGHT[k], 0);
  while (list.length < count) { let r = rnd() * total; for (const k of kinds) { r -= WEIGHT[k]; if (r <= 0) { list.push(k); break; } } }
  for (let i = list.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [list[i], list[j]] = [list[j], list[i]]; } // a shuffle, so the new kind is not always first
  return list;
}

function spawnEnemy(g, type) {
  if (type === 'boss') {
    const hp = 22 + 14 * Math.floor(g.wave / BOSS_EVERY); // 36 for the first boss, 14 more for each after
    g.enemies.push({ type: 'boss', x: WIDTH / 2, y: -BOSS.r, r: BOSS.r, hp, maxHp: hp, t: 0, fireT: 1.5 });
    emit(g, { type: 'boss' });
    g.powerups.push({ kind: 'shield', x: 60 + rand(g) * (WIDTH - 120), y: -12, r: 12 }); // a free shield falls from the top as a boss arrives
    return;
  }
  const d = ENEMY_TYPES[type]; const x = d.r + rand(g) * (WIDTH - 2 * d.r);
  g.enemies.push({ type, x, y: -d.r, r: d.r, hp: d.hp, t: 0, ph: rand(g) * 6.28 });
}

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const touching = (a, b) => (a.x - b.x) ** 2 + (a.y - b.y) ** 2 < (a.r + b.r) ** 2;
const speedMul = (g) => 1 + Math.min(1.2, 0.05 * (g.wave - 1));

function enemyShot(g, e, speed, angle) {
  if (g.enemyBullets.length >= MAX_ENEMY_BULLETS) return;
  const p = g.player; const a = Math.atan2(p.x - e.x, p.y - e.y) + angle; // 0 = straight at the ship
  g.enemyBullets.push({ x: e.x, y: e.y + e.r * 0.6, vx: Math.sin(a) * speed, vy: Math.cos(a) * speed, r: 4 });
}

function moveEnemy(g, e, h) {
  e.t += h; if (e.flash > 0) e.flash = Math.max(0, e.flash - h); const sp = speedMul(g); const p = g.player;
  switch (e.type) {
    case 'drifter': e.y += 80 * sp * h; e.x += Math.sin(e.t * 2 + (e.ph ?? 0)) * 40 * h; break;
    case 'zigzag': e.x0 ??= e.x; e.y += 110 * sp * h; e.x = e.x0 + Math.sin(e.t * 3 + (e.ph ?? 0)) * 110; break;
    case 'tank': e.y += 45 * sp * h; break;
    case 'swooper': e.y += 170 * sp * h; if (e.y > 30) e.x += Math.sign(p.x - e.x) * Math.min(Math.abs(p.x - e.x), 150 * h); break;
    case 'shooter':
      e.hoverY ??= 110;
      if (e.t > 9) { e.y += 170 * h; break; } // leaves after a while
      if (e.y < e.hoverY) { e.y += 120 * h; break; }
      e.x += Math.sin(e.t * 1.2) * 30 * h; e.fireT = (e.fireT ?? 0.8) - h;
      if (e.fireT <= 0) { enemyShot(g, e, Math.min(300, 190 + 3 * g.wave), 0); emit(g, { type: 'enemy-fire' }); e.fireT = Math.max(0.9, 1.7 - 0.04 * g.wave); }
      break;
    case 'boss':
      if (e.y < 100) e.y += 60 * h; else e.x = WIDTH / 2 + Math.sin(e.t * 0.7) * (WIDTH / 2 - e.r - 20);
      e.fireT = (e.fireT ?? 1.5) - h;
      if (e.fireT <= 0 && e.y >= 60) { for (let k = -2; k <= 2; k++) enemyShot(g, e, 200 + 2 * g.wave, k * 0.28); emit(g, { type: 'enemy-fire' }); e.fireT = Math.max(0.8, 1.4 - 0.02 * g.wave); }
      break;
  }
  e.x = clamp(e.x, e.r, WIDTH - e.r);
}

function burst(g, x, y, n, speed, life = 0.5) {
  for (let i = 0; i < n && g.particles.length < MAX_PARTICLES; i++) {
    const a = (i / n) * 6.283 + rand(g); const v = speed * (0.5 + rand(g));
    g.particles.push({ x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, life });
  }
}

function drop(g, e) {
  const chance = e.type === 'boss' ? 1 : (ENEMY_TYPES[e.type]?.drop ?? 0.1);
  if (rand(g) >= chance) return;
  const kinds = [['rapid', 3], ['spread', 3], ['shield', 3]]; if (g.lives < MAX_LIVES) kinds.push(['life', e.type === 'boss' ? 4 : 1]);
  let r = rand(g) * kinds.reduce((s, k) => s + k[1], 0); let kind = 'rapid'; for (const [k, w] of kinds) { r -= w; if (r <= 0) { kind = k; break; } }
  g.powerups.push({ kind, x: clamp(e.x, 16, WIDTH - 16), y: e.y, r: 12 });
}

function kill(g, e) {
  const base = e.type === 'boss' ? BOSS.pts : ENEMY_TYPES[e.type].pts;
  g.combo = g.comboTimer > 0 ? g.combo + 1 : 1; g.comboTimer = COMBO_WINDOW; g.multiplier = Math.min(4, 1 + Math.floor(g.combo / 5));
  const pts = base * g.multiplier; g.score += pts; g.kills++;
  emit(g, { type: e.type === 'boss' ? 'boss-down' : 'kill', kind: e.type, x: e.x, y: e.y, pts, big: e.r > 20 });
  if (g.combo >= 3) emit(g, { type: 'combo', combo: g.combo, multiplier: g.multiplier });
  burst(g, e.x, e.y, e.type === 'boss' ? 40 : e.r > 20 ? 16 : 10, e.type === 'boss' ? 260 : 140, e.type === 'boss' ? 1 : 0.5);
  drop(g, e);
}

function hurt(g) {
  const p = g.player; if (p.invulnerable > 0) return;
  g.combo = 0; g.comboTimer = 0; g.multiplier = 1;
  if (p.shield > 0) { p.shield = 0; p.invulnerable = 0.5; emit(g, { type: 'shield-break', x: p.x, y: p.y }); burst(g, p.x, p.y, 12, 160, 0.4); return; }
  g.lives--; p.invulnerable = SAFE_SECONDS; p.rapid = 0; p.spread = 0; g.enemyBullets = [];
  emit(g, { type: 'hit', x: p.x, y: p.y }); burst(g, p.x, p.y, 18, 200, 0.6);
  if (g.lives <= 0) {
    g.lives = 0; g.state = 'over'; g.best = Math.max(g.best, g.score);
    const shots = g.stats.shots; g.lastRun = { score: g.score, wave: g.wave, kills: g.kills, accuracy: shots ? Math.round((g.stats.hits / shots) * 100) : 0, seconds: Math.round(g.time) };
    emit(g, { type: 'over' });
  }
}

function pickup(g, up) {
  const p = g.player;
  if (up.kind === 'rapid') p.rapid = 8; else if (up.kind === 'spread') p.spread = 10; else if (up.kind === 'shield') p.shield = 12; else if (up.kind === 'life') g.lives = Math.min(MAX_LIVES, g.lives + 1);
  g.score += 25; emit(g, { type: 'pickup', kind: up.kind, x: up.x, y: up.y });
}

function advanceWave(g, h) {
  if (g.waveState === 'break') {
    g.breakTimer -= h;
    if (g.breakTimer <= 0) { g.toSpawn = composeWave(g.wave, g); g.waveState = 'spawning'; g.spawnTimer = 0; }
  } else if (g.waveState === 'spawning') {
    g.spawnTimer -= h;
    if (g.spawnTimer <= 0 && g.toSpawn.length) { spawnEnemy(g, g.toSpawn.shift()); g.spawnTimer += Math.max(0.35, 0.95 - 0.03 * g.wave); }
    if (!g.toSpawn.length) g.waveState = 'clearing';
  }
  if (g.waveState === 'clearing' && g.enemies.length === 0) { g.wave++; g.waveState = 'break'; g.breakTimer = 2.2; emit(g, { type: 'wave', wave: g.wave }); }
}

function substep(g, input, h) {
  g.time += h; const p = g.player;
  if (typeof input.targetX === 'number') p.x = clamp(p.x + clamp(input.targetX - p.x, -TOUCH_SPEED * h, TOUCH_SPEED * h), p.r, WIDTH - p.r); // a finger on the screen: glide to it
  else p.x = clamp(p.x + ((input.right ? 1 : 0) - (input.left ? 1 : 0)) * PLAYER_SPEED * h, p.r, WIDTH - p.r);
  p.cool = Math.max(0, p.cool - h); p.invulnerable = Math.max(0, p.invulnerable - h);
  p.rapid = Math.max(0, p.rapid - h); p.spread = Math.max(0, p.spread - h); p.shield = Math.max(0, p.shield - h);
  if (input.fire && p.cool === 0) {
    const angles = p.spread > 0 ? [-0.18, 0, 0.18] : [0];
    for (const a of angles) { g.bullets.push({ x: p.x, y: p.y - p.r, r: 3, vx: Math.sin(a) * BULLET_SPEED, vy: -Math.cos(a) * BULLET_SPEED }); g.stats.shots++; }
    p.cool = p.rapid > 0 ? RAPID_EVERY : FIRE_EVERY; emit(g, { type: 'fire' });
  }
  for (const b of g.bullets) { b.x += b.vx * h; b.y += b.vy * h; }
  g.bullets = g.bullets.filter((b) => b.y > -10 && b.x > -10 && b.x < WIDTH + 10);

  advanceWave(g, h);
  for (const e of g.enemies) moveEnemy(g, e, h);
  for (const b of g.enemyBullets) { b.x += b.vx * h; b.y += b.vy * h; }
  g.enemyBullets = g.enemyBullets.filter((b) => b.y < HEIGHT + 10 && b.y > -20 && b.x > -20 && b.x < WIDTH + 20);
  for (const u of g.powerups) u.y += 90 * h;
  g.powerups = g.powerups.filter((u) => u.y < HEIGHT + 20);

  for (const b of g.bullets) {
    for (const e of g.enemies) {
      if (b.dead || e.hp <= 0 || !touching(b, e)) continue;
      b.dead = true; e.hp--; g.stats.hits++; e.flash = 0.08;
      if (e.hp <= 0) kill(g, e); else emit(g, { type: 'hit-enemy', x: b.x, y: b.y });
    }
  }
  g.bullets = g.bullets.filter((b) => !b.dead);
  g.enemies = g.enemies.filter((e) => e.hp > 0);

  for (const e of g.enemies) { // ramming: the ship is hurt, and anything but a boss is destroyed
    if (!touching(e, p)) continue;
    if (e.type !== 'boss') { e.hp = 0; burst(g, e.x, e.y, 8, 120); }
    hurt(g);
  }
  g.enemies = g.enemies.filter((e) => e.hp > 0 && e.y < HEIGHT + 40);
  for (const b of g.enemyBullets) if (!b.dead && touching(b, p)) { b.dead = true; hurt(g); }
  g.enemyBullets = g.enemyBullets.filter((b) => !b.dead);
  for (const u of g.powerups) if (!u.dead && touching(u, p)) { u.dead = true; pickup(g, u); }
  g.powerups = g.powerups.filter((u) => !u.dead);

  g.comboTimer = Math.max(0, g.comboTimer - h); if (g.comboTimer === 0) g.combo = 0;
  g.multiplier = Math.min(4, 1 + Math.floor(g.combo / 5));
  for (const q of g.particles) { q.x += q.vx * h; q.y += q.vy * h; q.life -= h; }
  g.particles = g.particles.filter((q) => q.life > 0);
}

export function step(g, input, rawDt) {
  if (g.state !== 'playing') return;
  g.acc += Math.min(Math.max(rawDt, 0), MAX_DT);
  while (g.acc >= SUB - 1e-9 && g.state === 'playing') { g.acc -= SUB; substep(g, input, SUB); }
}

/** Adds a score to a top-ten list. Returns the new list and the 1-based rank, or null when it did not make the list. A tie goes below the scores already there; a score of 0 is never recorded. */
export function addHighScore(list, entry, max = 10) {
  if (!(entry.score > 0)) return { list: [...list], rank: null };
  let at = list.findIndex((e) => e.score < entry.score); if (at === -1) at = list.length;
  if (at >= max) return { list: [...list], rank: null };
  const next = [...list.slice(0, at), { name: entry.name, score: entry.score }, ...list.slice(at)].slice(0, max);
  return { list: next, rank: at + 1 };
}

/** Initials for the high-score table: letters and digits only, upper case, three at most, "AAA" when nothing usable was typed. */
export function cleanInitials(s) { const c = String(s ?? '').toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 3); return c || 'AAA'; }
