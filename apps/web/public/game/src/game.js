// Starfall's rules. Pure: no canvas, no keyboard, no clock. The page feeds it input and time and draws what it holds, so everything here is tested by calling step().
// The game advances in fixed 1/120 s pieces whatever the frame rate, so a run plays out the same on a slow or a fast screen (same seed, same input).
export const WIDTH = 480;
export const HEIGHT = 640;
const SUB = 1 / 120;
const MAX_DT = 1 / 20; // a long frame (tab in the background) is cut so nothing jumps through anything
const PLAYER_SPEED = 320;
const TOUCH_SPEED = 520; // how fast the ship follows a finger
const OVERCLOCK = 1.6; // fire-rate multiplier while the overclock power-up lasts
const MAX_BULLETS = 200;
const SAFE_SECONDS = 2;
const COMBO_WINDOW = 1.5;
const MAX_LIVES = 5;
const MAX_ENEMY_BULLETS = 300;
const MAX_PARTICLES = 400;
const BOSS_EVERY = 5;
const MAX_BOMBS = 3;
const BOMB_DAMAGE = 5; // to every ordinary enemy on screen
const BOMB_BOSS_DAMAGE = 12; // a bomb takes this off a boss but never kills it
const BOSS_KINDS = ['gunship', 'spiral', 'summoner'];

/** How hard the game is. Easy gives an extra life and slower, weaker enemies; hard one life fewer and faster, tougher ones. */
export const DIFFICULTIES = {
  easy: { lives: 4, speed: 0.85, shot: 0.85, boss: 0.8, drop: 1.4 },
  normal: { lives: 3, speed: 1, shot: 1, boss: 1, drop: 1 },
  hard: { lives: 2, speed: 1.2, shot: 1.15, boss: 1.3, drop: 0.75 },
};
/** The look of each sector (a stretch of five waves); they cycle. */
export const SECTORS = [
  { name: 'Nebula', sky: '#0d1117', glow: '#1f2a52' },
  { name: 'Ember Belt', sky: '#150d0d', glow: '#5a2a1a' },
  { name: 'Deep Space', sky: '#0a0d14', glow: '#12324a' },
  { name: 'Toxic Cloud', sky: '#0d140d', glow: '#2a5a2a' },
  { name: 'The Void', sky: '#100d17', glow: '#3d2a5a' },
];
export function sectorOf(wave) { const n = Number.isFinite(wave) && wave > 0 ? Math.floor((wave - 1) / BOSS_EVERY) : 0; return SECTORS[n % SECTORS.length]; }
export function bossKind(wave) { return BOSS_KINDS[(Math.max(1, Math.floor(wave / BOSS_EVERY)) - 1) % BOSS_KINDS.length]; }
const diff = (g) => DIFFICULTIES[g.difficulty] ?? DIFFICULTIES.normal;

/** The five ordinary enemies. (The boss is separate: see spawnEnemy.) */
export const ENEMY_TYPES = {
  drifter: { r: 16, hp: 1, pts: 10, drop: 0.08, tokens: 0.45, name: 'Idea Box', color: '#38bdf8' },
  zigzag: { r: 13, hp: 1, pts: 20, drop: 0.1, tokens: 0.5, name: 'Spin Box', color: '#a78bfa' },
  tank: { r: 24, hp: 3, pts: 30, drop: 0.3, tokens: 2, name: 'Vault Box', color: '#f43f5e' },
  shooter: { r: 17, hp: 2, pts: 40, drop: 0.2, tokens: 0.8, name: 'Cannon Box', color: '#fb923c' },
  swooper: { r: 14, hp: 1, pts: 25, drop: 0.12, tokens: 0.5, name: 'Dart Box', color: '#34d399' },
};
/** The bosses are Mega Think Boxes, one for each kind. */
export const BOSS_STYLE = {
  gunship: { name: 'Mega Box: Gunship', color: '#a78bfa' },
  spiral: { name: 'Mega Box: Spiral', color: '#facc15' },
  summoner: { name: 'Mega Box: Summoner', color: '#34d399' },
};

/** The ship's weapons, in the order the number keys pick them. Each has four levels, raised by weapon crates and by Think Tokens. */
export const WEAPONS = { laser: { name: 'Laser' }, spread: { name: 'Spread' }, missile: { name: 'Missiles' }, rail: { name: 'Rail' } };
export const MAX_WEAPON_LEVEL = 4;
export const TOKENS_PER_LEVEL = 8;

/** What one trigger pull of a weapon at a level fires: the bullets (sideways offset dx and angle a), the time between pulls, damage, how many boxes a bullet goes through, speed, size. */
export function fireSpec(weapon, level) {
  const lv = Math.max(1, Math.min(MAX_WEAPON_LEVEL, Math.floor(level) || 1)) - 1;
  switch (weapon) {
    case 'spread': { const n = [3, 5, 7, 9][lv]; const step = [0.2, 0.15, 0.13, 0.11][lv]; return { shots: Array.from({ length: n }, (_, i) => ({ a: (i - (n - 1) / 2) * step })), every: [0.26, 0.24, 0.22, 0.2][lv], dmg: 1, pierce: 1, speed: 620, r: 3 }; }
    case 'missile': return { shots: [[0], [-8, 8], [-12, 0, 12], [-18, -6, 6, 18]][lv].map((dx) => ({ dx, a: dx * 0.004 })), every: [0.45, 0.42, 0.4, 0.34][lv], dmg: 2, pierce: 1, speed: 380, r: 5, homing: true, splash: 36 };
    case 'rail': return { shots: [{}], every: [0.42, 0.36, 0.3, 0.24][lv], dmg: [3, 3, 4, 5][lv], pierce: [3, 5, 8, 99][lv], speed: 900, r: lv >= 2 ? 7 : 5 };
    default: return { shots: [[0], [-7, 7], [-10, 0, 10], [-10, 0, 10]][lv].map((dx) => ({ dx })), every: [0.18, 0.17, 0.16, 0.12][lv], dmg: 1, pierce: 1, speed: 640, r: 3 };
  }
}
const BOSS = { r: 44, pts: 1000 };
/** The wave an enemy type first appears in. */
const DEBUT = { drifter: 1, zigzag: 2, tank: 3, shooter: 4, swooper: 6 };
const WEIGHT = { drifter: 5, zigzag: 3, tank: 2, shooter: 2, swooper: 2 };
const CLUSTERS = new Set(['drifter', 'zigzag', 'swooper']); // these come in runs and formations
const FORMATIONS = ['line', 'v', 'column', 'pincer'];

/** Small seeded random numbers (mulberry32): the same seed always plays out the same way. */
function mulberry(state) {
  let s = state | 0;
  return () => { s = (s + 0x6d2b79f5) | 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
function rand(g) { g.rng = (g.rng + 0x6d2b79f5) | 0; let t = g.rng; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }

export function createGame(seed = 1) {
  const g = { seed: seed | 0, rng: seed | 0, state: 'title', best: 0, lastRun: null, difficulty: 'normal' };
  reset(g);
  return g;
}

function reset(g) {
  g.rng = g.seed;
  g.player = { x: WIDTH / 2, y: HEIGHT - 60, r: 16, cool: 0, invulnerable: 0, rapid: 0, shield: 0, weapons: { laser: 1, spread: 0, missile: 0, rail: 0 }, weapon: 'laser' };
  g.bullets = []; g.enemyBullets = []; g.enemies = []; g.powerups = []; g.particles = []; g.events = [];
  g.tokens = 0; g.score = 0; g.kills = 0; g.lives = diff(g).lives; g.bombs = 1; g.hurtThisWave = false; g.time = 0; g.acc = 0;
  g.combo = 0; g.comboTimer = 0; g.multiplier = 1; g.stats = { shots: 0, hits: 0 };
  g.wave = 1; g.waveState = 'break'; g.breakTimer = 1; g.toSpawn = []; g.spawnTimer = 0;
}

export function setDifficulty(g, name) { if (Object.prototype.hasOwnProperty.call(DIFFICULTIES, name)) g.difficulty = name; }
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
  const total = kinds.reduce((s, k) => s + WEIGHT[k], 0);
  const groups = debuting.map((k) => [k]); let have = debuting.length;
  while (have < count) { // the small enemies come in runs (which become formations), the big ones one at a time
    let r = rnd() * total; let kind = kinds[0]; for (const k of kinds) { r -= WEIGHT[k]; if (r <= 0) { kind = k; break; } }
    const run = CLUSTERS.has(kind) ? Math.min(count - have, 2 + Math.floor(rnd() * 4)) : 1; groups.push(Array(run).fill(kind)); have += run;
  }
  for (let i = groups.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [groups[i], groups[j]] = [groups[j], groups[i]]; }
  return groups.flat();
}

/** Turns a wave's list of enemies into spawn entries. Runs of three to five of the same small enemy (from wave 2) become a formation: a line, a V, a column or a pincer,
 *  which arrive together; everything else comes one at a time. Each entry may carry an x, a height offset above the screen (dy) and a gap to wait after it. The same wave always gives the same plan. */
export function planSpawns(list, n, g) {
  const rnd = mulberry((g.seed | 0) + n * 104729);
  const plan = []; let i = 0;
  while (i < list.length) {
    const type = list[i]; let j = i; while (j < list.length && list[j] === type) j++;
    const run = Math.min(5, j - i);
    if (n >= 2 && run >= 3 && CLUSTERS.has(type)) {
      const formation = FORMATIONS[Math.floor(rnd() * FORMATIONS.length)]; const r = ENEMY_TYPES[type].r; const cx = 150 + rnd() * (WIDTH - 300); const colX = 50 + rnd() * (WIDTH - 100);
      for (let k = 0; k < run; k++) {
        let x; let dy = 0;
        if (formation === 'line') x = 60 + (k * (WIDTH - 120)) / (run - 1);
        else if (formation === 'v') { x = cx + (k - (run - 1) / 2) * 55; dy = Math.abs(k - (run - 1) / 2) * 38; }
        else if (formation === 'column') { x = colX; dy = k * 44; }
        else { x = k % 2 === 0 ? 40 : WIDTH - 40; dy = Math.floor(k / 2) * 44; }
        plan.push({ type, x: clamp(x, r, WIDTH - r), dy, formation, gap: k < run - 1 ? 0.03 : undefined });
      }
      i += run;
    } else { plan.push({ type }); i++; }
  }
  return plan;
}

function spawnEnemy(g, type, opts = {}) {
  if (type === 'boss') {
    const hp = Math.round((50 + 18 * Math.floor(g.wave / BOSS_EVERY)) * diff(g).boss); // 68 for the first boss, 18 more for each after (the weapons are far stronger than in v0.3)
    g.enemies.push({ type: 'boss', kind: bossKind(g.wave), x: WIDTH / 2, y: -BOSS.r, r: BOSS.r, hp, maxHp: hp, t: 0, fireT: 1.5, summonT: 4, spin: 0, burst: 0 });
    emit(g, { type: 'boss', kind: bossKind(g.wave) });
    g.powerups.push({ kind: 'shield', x: 60 + rand(g) * (WIDTH - 120), y: -12, r: 12 }); // a free shield falls from the top as a boss arrives
    return;
  }
  const d = ENEMY_TYPES[type]; const x = opts.x ?? d.r + rand(g) * (WIDTH - 2 * d.r);
  g.enemies.push({ type, x, y: -d.r - (opts.dy ?? 0), r: d.r, hp: d.hp, t: 0, ph: opts.x === undefined ? rand(g) * 6.28 : 0 });
}

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const touching = (a, b) => (a.x - b.x) ** 2 + (a.y - b.y) ** 2 < (a.r + b.r) ** 2;
const speedMul = (g) => (1 + Math.min(1.2, 0.05 * (g.wave - 1))) * diff(g).speed;

function enemyShot(g, e, speed, angle, absolute = false) {
  if (g.enemyBullets.length >= MAX_ENEMY_BULLETS) return;
  const p = g.player; const a = absolute ? angle : Math.atan2(p.x - e.x, p.y - e.y) + angle; // 0 = straight at the ship (or, if absolute, straight down)
  speed *= diff(g).shot; g.enemyBullets.push({ x: e.x, y: e.y + e.r * 0.6, vx: Math.sin(a) * speed, vy: Math.cos(a) * speed, r: 4 });
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
    case 'boss': {
      e.fireT ??= 1.5; e.summonT ??= 4; e.spin ??= 0; e.burst ??= 0; e.maxHp ??= e.hp; e.kind ??= 'gunship';
      if (e.y < 100) e.y += 60 * h; else e.x = WIDTH / 2 + Math.sin(e.t * 0.7) * (WIDTH / 2 - e.r - 20);
      if (!e.enraged && e.hp <= e.maxHp / 2) { e.enraged = true; emit(g, { type: 'boss-enrage', x: e.x, y: e.y }); }
      const rate = e.enraged ? 1.5 : 1; const wave = g.wave;
      if (e.y < 60) break;
      if (e.kind === 'spiral') {
        e.fireT -= h * rate;
        if (e.fireT <= 0) {
          if (e.burst === 0) { e.burst = 26; emit(g, { type: 'enemy-fire' }); }
          e.spin += 0.55; enemyShot(g, e, 170 + wave, e.spin, true); e.burst--; e.fireT = e.burst === 0 ? 1.3 : 0.1;
        }
      } else {
        e.fireT -= h * rate;
        if (e.fireT <= 0) {
          if (e.kind === 'summoner') enemyShot(g, e, 220 + wave, 0); else for (let k = -2; k <= 2; k++) enemyShot(g, e, 200 + 2 * wave, k * 0.28);
          emit(g, { type: 'enemy-fire' }); e.fireT = e.kind === 'summoner' ? 1.5 : Math.max(0.8, 1.4 - 0.02 * wave);
        }
        if (e.kind === 'summoner') {
          e.summonT -= h * rate;
          if (e.summonT <= 0) { for (const dx of [-70, 70]) spawnEnemy(g, 'swooper', { x: clamp(e.x + dx, 20, WIDTH - 20), dy: -(e.y + 20) }); emit(g, { type: 'summon', x: e.x, y: e.y }); e.summonT = 5; }
        }
      }
      break;
    }
  }
  e.x = clamp(e.x, e.r, WIDTH - e.r);
}

function burst(g, x, y, n, speed, life = 0.5, color = null) {
  for (let i = 0; i < n && g.particles.length < MAX_PARTICLES; i++) {
    const a = (i / n) * 6.283 + rand(g); const v = speed * (0.5 + rand(g));
    g.particles.push({ x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, life, c: color });
  }
}

function dropTokens(g, e) {
  const t = e.type === 'boss' ? 10 : ENEMY_TYPES[e.type]?.tokens ?? 0; let n = Math.floor(t); if (rand(g) < t - n) n++;
  for (let i = 0; i < n; i++) g.powerups.push({ kind: 'token', x: clamp(e.x + (i - (n - 1) / 2) * 14, 12, WIDTH - 12), y: e.y - (i % 2) * 8, r: 8 });
}

function drop(g, e) {
  dropTokens(g, e);
  const up = upgradable(g);
  if (e.type === 'boss' && up.length) { g.powerups.push({ kind: 'weapon', weapon: up.find((w) => g.player.weapons[w] === 0) ?? up[Math.floor(rand(g) * up.length)], x: clamp(e.x, 16, WIDTH - 16), y: e.y, r: 12 }); return; }
  const chance = e.type === 'boss' ? 1 : (ENEMY_TYPES[e.type]?.drop ?? 0.1);
  if (rand(g) >= chance * (e.type === 'boss' ? 1 : diff(g).drop)) return;
  const kinds = [['rapid', 2], ['shield', 3], ['bomb', 1.5]]; if (g.lives < MAX_LIVES) kinds.push(['life', e.type === 'boss' ? 4 : 1]); if (up.length) kinds.push(['weapon', 3]);
  let r = rand(g) * kinds.reduce((s, k) => s + k[1], 0); let kind = 'rapid'; for (const [k, w] of kinds) { r -= w; if (r <= 0) { kind = k; break; } }
  const item = { kind, x: clamp(e.x, 16, WIDTH - 16), y: e.y, r: 12 };
  if (kind === 'weapon') item.weapon = up.find((w) => g.player.weapons[w] === 0 && rand(g) < 0.6) ?? up[Math.floor(rand(g) * up.length)];
  g.powerups.push(item);
}

function kill(g, e) {
  const base = e.type === 'boss' ? BOSS.pts : ENEMY_TYPES[e.type].pts;
  g.combo = g.comboTimer > 0 ? g.combo + 1 : 1; g.comboTimer = COMBO_WINDOW; g.multiplier = Math.min(4, 1 + Math.floor(g.combo / 5));
  const pts = base * g.multiplier; g.score += pts; g.kills++; g.waveKills = (g.waveKills ?? 0) + 1;
  emit(g, { type: e.type === 'boss' ? 'boss-down' : 'kill', kind: e.type === 'boss' ? e.kind : e.type, x: e.x, y: e.y, pts, big: e.r > 20 });
  if (g.combo >= 3) emit(g, { type: 'combo', combo: g.combo, multiplier: g.multiplier });
  burst(g, e.x, e.y, e.type === 'boss' ? 40 : e.r > 20 ? 16 : 10, e.type === 'boss' ? 260 : 140, e.type === 'boss' ? 1 : 0.5, e.type === 'boss' ? BOSS_STYLE[e.kind]?.color : ENEMY_TYPES[e.type]?.color);
  drop(g, e);
}

function hurt(g) {
  const p = g.player; if (p.invulnerable > 0) return;
  g.hurtThisWave = true; g.combo = 0; g.comboTimer = 0; g.multiplier = 1;
  if (p.shield > 0) { p.shield = 0; p.invulnerable = 0.5; emit(g, { type: 'shield-break', x: p.x, y: p.y }); burst(g, p.x, p.y, 12, 160, 0.4); return; }
  g.lives--; p.invulnerable = SAFE_SECONDS; p.rapid = 0; g.enemyBullets = [];
  if (p.weapons[p.weapon] > 1) p.weapons[p.weapon]--; // the weapon in your hands loses a level
  emit(g, { type: 'hit', x: p.x, y: p.y }); burst(g, p.x, p.y, 18, 200, 0.6);
  if (g.lives <= 0) {
    g.lives = 0; g.state = 'over'; g.best = Math.max(g.best, g.score);
    const shots = g.stats.shots; g.lastRun = { score: g.score, wave: g.wave, kills: g.kills, accuracy: shots ? Math.min(100, Math.round((g.stats.hits / shots) * 100)) : 0, seconds: Math.round(g.time) };
    emit(g, { type: 'over' });
  }
}

function pickup(g, up) {
  const p = g.player;
  if (up.kind === 'rapid') p.rapid = 8; else if (up.kind === 'weapon') upgradeWeapon(g, up.weapon, 'crate'); else if (up.kind === 'token') { g.tokens++; g.score += 10; if (g.tokens >= TOKENS_PER_LEVEL) { g.tokens = 0; upgradeWeapon(g, p.weapon, 'tokens'); } } else if (up.kind === 'shield') p.shield = 12; else if (up.kind === 'life') g.lives = Math.min(MAX_LIVES, g.lives + 1); else if (up.kind === 'bomb') g.bombs = Math.min(MAX_BOMBS, g.bombs + 1);
  if (up.kind !== 'token' && up.kind !== 'weapon') g.score += 25;
  emit(g, { type: 'pickup', kind: up.kind, weapon: up.weapon, x: up.x, y: up.y });
}

function advanceWave(g, h) {
  if (g.waveState === 'break') {
    g.breakTimer -= h;
    if (g.breakTimer <= 0) { g.toSpawn = planSpawns(composeWave(g.wave, g), g.wave, g); g.waveTotal = g.toSpawn.length; g.waveKills = 0; g.waveState = 'spawning'; g.spawnTimer = 0; }
  } else if (g.waveState === 'spawning') {
    g.spawnTimer -= h;
    if (g.spawnTimer <= 0 && g.toSpawn.length) {
      const item = g.toSpawn.shift(); const entry = typeof item === 'string' ? { type: item } : item; spawnEnemy(g, entry.type, entry);
      g.spawnTimer += entry.gap ?? Math.max(0.35, 0.95 - 0.03 * g.wave);
    }
    if (!g.toSpawn.length) g.waveState = 'clearing';
  }
  if (g.waveState === 'clearing' && g.enemies.length === 0) {
    // a perfect wave: not hit, and at least half of the wave shot down (so that doing nothing earns nothing)
    if (!g.hurtThisWave && (g.waveKills ?? 0) >= Math.ceil((g.waveTotal ?? 0) / 2)) { const pts = 100 * g.wave; g.score += pts; emit(g, { type: 'perfect', pts }); }
    g.hurtThisWave = false;
    g.wave++; g.waveState = 'break'; g.breakTimer = 2.2; emit(g, { type: 'wave', wave: g.wave }); }
}

const TOKEN_MAGNET = 90;
/** A missile speeds up and turns towards the nearest box in front of it (turning at most 5 radians a second). */
function steerMissile(g, b, h) {
  let ang = Math.atan2(b.vx, -b.vy); const speed = Math.min(560, Math.hypot(b.vx, b.vy) + 400 * h);
  let target = null, best = 420 * 420;
  for (const e of g.enemies) { if (e.hp <= 0 || e.y > b.y + 20) continue; const d = (e.x - b.x) ** 2 + (e.y - b.y) ** 2; if (d < best) { best = d; target = e; } }
  if (target) { let turn = Math.atan2(target.x - b.x, -(target.y - b.y)) - ang; turn = Math.atan2(Math.sin(turn), Math.cos(turn)); ang += clamp(turn, -5 * h, 5 * h); }
  b.vx = Math.sin(ang) * speed; b.vy = -Math.cos(ang) * speed;
}
/** A missile's blast: every other box within its radius loses one hit point. */
function splashDamage(g, b, hit) {
  for (const o of g.enemies) {
    if (o === hit || o.hp <= 0) continue; if (Math.hypot(o.x - b.x, o.y - b.y) - o.r > b.splash) continue;
    o.hp -= 1; o.flash = 0.08; if (o.hp <= 0) kill(g, o); else emit(g, { type: 'hit-enemy', x: o.x, y: o.y });
  }
  burst(g, b.x, b.y, 6, 120, 0.3, '#ffa657');
}

function substep(g, input, h) {
  g.time += h; const p = g.player;
  if (typeof input.targetX === 'number') p.x = clamp(p.x + clamp(input.targetX - p.x, -TOUCH_SPEED * h, TOUCH_SPEED * h), p.r, WIDTH - p.r); // a finger on the screen: glide to it
  else p.x = clamp(p.x + ((input.right ? 1 : 0) - (input.left ? 1 : 0)) * PLAYER_SPEED * h, p.r, WIDTH - p.r);
  p.cool = Math.max(0, p.cool - h); p.invulnerable = Math.max(0, p.invulnerable - h);
  p.rapid = Math.max(0, p.rapid - h); p.shield = Math.max(0, p.shield - h);
  if (input.fire && p.cool === 0 && g.bullets.length < MAX_BULLETS) {
    const spec = fireSpec(p.weapon, p.weapons[p.weapon]);
    for (const sh of spec.shots) {
      const a = sh.a ?? 0;
      g.bullets.push({ x: p.x + (sh.dx ?? 0), y: p.y - p.r, r: spec.r, vx: Math.sin(a) * spec.speed, vy: -Math.cos(a) * spec.speed, dmg: spec.dmg, pierce: spec.pierce, kind: p.weapon, homing: !!spec.homing, splash: spec.splash ?? 0, hits: [] });
      g.stats.shots++;
    }
    p.cool = spec.every / (p.rapid > 0 ? OVERCLOCK : 1); emit(g, { type: 'fire', weapon: p.weapon });
  }
  for (const b of g.bullets) {
    if (b.homing) steerMissile(g, b, h);
    b.x += b.vx * h; b.y += b.vy * h;
  }
  g.bullets = g.bullets.filter((b) => b.y > -10 && b.x > -10 && b.x < WIDTH + 10 && b.y < HEIGHT + 10);

  advanceWave(g, h);
  for (const e of g.enemies) moveEnemy(g, e, h);
  for (const b of g.enemyBullets) { b.x += b.vx * h; b.y += b.vy * h; }
  g.enemyBullets = g.enemyBullets.filter((b) => b.y < HEIGHT + 10 && b.y > -20 && b.x > -20 && b.x < WIDTH + 20);
  for (const u of g.powerups) {
    if (u.kind === 'token') { // Think Tokens drift towards the ship when it is close
      const dx = p.x - u.x, dy = p.y - u.y, d = Math.hypot(dx, dy);
      if (d < TOKEN_MAGNET && d > 1) { u.x += (dx / d) * 220 * h; u.y += (dy / d) * 220 * h; } else u.y += 75 * h;
    } else u.y += 90 * h;
  }
  g.powerups = g.powerups.filter((u) => u.y < HEIGHT + 20);

  for (const b of g.bullets) {
    b.hits ??= []; b.dmg ??= 1; b.pierce ??= 1; // (bullets made by the game always have these; older shapes are tolerated)
    for (const e of g.enemies) {
      if (b.dead || e.hp <= 0 || !touching(b, e) || b.hits.includes(e)) continue;
      b.hits.push(e); g.stats.hits++; e.flash = 0.08; e.hp -= b.dmg;
      if (e.hp <= 0) kill(g, e); else emit(g, { type: 'hit-enemy', x: b.x, y: b.y });
      if (b.splash) splashDamage(g, b, e);
      if (--b.pierce <= 0) b.dead = true;
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

/** Switches to a weapon you own. Returns whether it worked. */
export function selectWeapon(g, name) {
  const p = g.player; if (!Object.prototype.hasOwnProperty.call(WEAPONS, name) || !(p.weapons[name] > 0)) return false;
  p.weapon = name; emit(g, { type: 'weapon', weapon: name, level: p.weapons[name] }); return true;
}
/** The next (or, with -1, the previous) weapon you own, going round. */
export function cycleWeapon(g, dir = 1) {
  const owned = Object.keys(WEAPONS).filter((w) => g.player.weapons[w] > 0); if (owned.length < 2) return false;
  const at = owned.indexOf(g.player.weapon); return selectWeapon(g, owned[(at + (dir < 0 ? owned.length - 1 : 1)) % owned.length]);
}
/** A weapon crate (source 'crate'): unlocks the weapon and switches to it, or raises its level. A full token meter (source 'tokens') raises the level of the weapon in your hands.
 *  At the top level either pays points instead. */
function upgradeWeapon(g, name, source) {
  const p = g.player;
  if (p.weapons[name] >= MAX_WEAPON_LEVEL) { g.score += 500; emit(g, { type: 'weapon-up', weapon: name, level: MAX_WEAPON_LEVEL, max: true }); return; }
  const fresh = p.weapons[name] === 0; p.weapons[name]++;
  if (source === 'crate') { p.weapon = name; emit(g, { type: 'weapon', weapon: name, level: p.weapons[name] }); if (!fresh) emit(g, { type: 'weapon-up', weapon: name, level: p.weapons[name] }); }
  else emit(g, { type: 'weapon-up', weapon: name, level: p.weapons[name] });
}
const upgradable = (g) => Object.keys(WEAPONS).filter((w) => g.player.weapons[w] < MAX_WEAPON_LEVEL);

/** The bomb: clears every enemy shot, hurts every enemy on screen (a boss loses a chunk but is never killed by it), gives a second of safety. Returns whether it went off. */
export function useBomb(g) {
  if (g.state !== 'playing' || g.bombs <= 0) return false;
  g.bombs--; g.enemyBullets = []; g.player.invulnerable = Math.max(g.player.invulnerable, 1);
  emit(g, { type: 'bomb', x: g.player.x, y: g.player.y });
  for (const e of g.enemies) {
    if (e.type === 'boss') { e.hp = Math.max(1, e.hp - BOMB_BOSS_DAMAGE); e.flash = 0.15; continue; }
    e.hp -= BOMB_DAMAGE; e.flash = 0.15; if (e.hp <= 0) kill(g, e);
  }
  g.enemies = g.enemies.filter((e) => e.hp > 0);
  burst(g, g.player.x, g.player.y, 40, 320, 0.7);
  return true;
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
