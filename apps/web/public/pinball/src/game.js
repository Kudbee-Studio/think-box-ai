// Pinball's rules and physics. Pure: no canvas, no keyboard, no clock. The page feeds it input and time and draws what it holds, so everything here is tested by calling step().
// Coordinates are pixels, y points down. The ball moves in small fixed sub-steps so even a very fast ball cannot pass through a wall.
import { DEFAULTS } from './tuning.js';

export const WIDTH = 480;
export const HEIGHT = 800;
export const BALL_R = 8;
const MAX_SPEED = 2200;
const MAX_DT = 1 / 30;
const HARD_HIT = 250; // a bounce harder than this (px/s into the surface) is announced
const SUB = 1 / 480;
const FLIPPER_LEN = 66;
const FLIPPER_THICK = 5;
const BUMPER_POINTS = 100;
const COMBO_WINDOW = 2; // seconds between scoring hits that keep a combo going
const COMBO_STEP = 50; // extra points per hit once the combo reaches 3
const BONUS_PER_HIT = 25; // paid out per bumper hit when the ball is lost, times the multiplier
const SUPER_COMBO = 500; // flat bonus (times the multiplier) each time a combo reaches a multiple of 5
const JACKPOT = 2000; // all five main bumpers hit in one ball
const DECK_EXIT_Y = 230; // a ball on the upper deck that gets below this has dropped through the gap
const MAX_BALLS = 3; // balls in play at once (your ball plus up to two free extras)
const DECK_MAX = 20; // seconds: a ball still on the deck after this is let down anyway (it should never come to that)
const LANE_X = 445;
const LANE_Y = 782;
const DRAIN_Y = 795; // below the flippers the ball is lost (the launch lane floor holds a waiting ball at 782)

/** The fixed walls: a round top (a half circle), side walls, the launch lane and the two guides that lead down to the flippers. */
function buildWalls() {
  const w = [];
  const cx = 240, cy = 260, R = 220, N = 28;
  for (let i = 0; i < N; i++) {
    const a0 = Math.PI - (i * Math.PI) / N, a1 = Math.PI - ((i + 1) * Math.PI) / N;
    w.push({ x1: cx + R * Math.cos(a0), y1: cy - R * Math.sin(a0), x2: cx + R * Math.cos(a1), y2: cy - R * Math.sin(a1) });
  }
  w.push({ x1: 20, y1: 260, x2: 20, y2: 800 });     // left wall (down past the flippers, like the lane wall on the right, so a ball under the flippers cannot leave the table sideways)
  w.push({ x1: 460, y1: 260, x2: 460, y2: 790 });   // right wall (outside of the launch lane)
  w.push({ x1: 430, y1: 330, x2: 430, y2: 790 });   // inside of the launch lane
  w.push({ x1: 430, y1: 790, x2: 460, y2: 790 });   // floor of the lane
  w.push({ x1: 460, y1: 316, x2: 432, y2: 330, oneWay: true }); // gate: a ball going up passes, one coming down slides off into the playfield
  w.push({ x1: 20, y1: 640, x2: 160, y2: 730, thick: FLIPPER_THICK }); // left guide: as thick as a flipper and ending at its pivot, so the two surfaces meet with no notch and no step for the ball to stick on; thickness also stops a swinging flipper squeezing the ball through it
  w.push({ x1: 430, y1: 640, x2: 320, y2: 730, thick: FLIPPER_THICK }); // right guide (same)
  return w;
}
export const WALLS = buildWalls();
/** The upper deck: two rails that make a funnel with a gap in the middle. They only touch a ball that is on the deck (layer 1); the ball falls through the gap back to the main table. */
export const DECK_WALLS = [
  { x1: 44, y1: 144, x2: 210, y2: 215, thick: 4 },
  { x1: 436, y1: 144, x2: 270, y2: 215, thick: 4 },
];
/** Ball traps: a slow ball that rolls over one is held for `hold` seconds and paid, then let go (one ball per trap at a time). 'kick' throws it back onto the table and shoots out free extra balls; 'deck' lifts it onto the upper deck. */
export const SAUCERS = [
  { x: 42, y: 430, r: 16, kind: 'kick', pts: 500, hold: 3, vx: 260, vy: -620, extras: [{ vx: 140, vy: -700 }, { vx: 360, vy: -540 }] }, // beside the left wall, level with the left pop bumper: locks the ball for 3 s, then shoots it out with up to two free extra balls fanned at different angles
  { x: 240, y: 92, r: 13, kind: 'deck', pts: 1000, hold: 1.8 },
];
const deg = (d) => (d * Math.PI) / 180;

export function createGame() {
  const g = { state: 'title', best: 0, tuning: { ...DEFAULTS } };
  reset(g);
  return g;
}

function reset(g) {
  g.bumpers = [
    { x: 170, y: 300, r: 26, bank: true }, { x: 310, y: 300, r: 26, bank: true }, { x: 240, y: 400, r: 26, bank: true }, // the original three
    { x: 105, y: 430, r: 18, pts: 150, bank: true }, { x: 375, y: 430, r: 18, pts: 150, bank: true }, // small pop bumpers pay more
    { x: 130, y: 118, r: 16, pts: 200, layer: 1 }, { x: 350, y: 118, r: 16, pts: 200, layer: 1 }, { x: 240, y: 160, r: 14, pts: 200, layer: 1 }, // upper deck
  ];
  g.saucers = SAUCERS.map((x) => ({ ...x, cool: 0 })); g.trap = null; g.extra = []; g.deckSide = 1; g.layerSince = 0;
  g.flippers = {
    left: { px: 160, py: 730, rest: deg(26), up: deg(-34), angle: deg(26), omega: 0 },
    right: { px: 320, py: 730, rest: deg(154), up: deg(214), angle: deg(154), omega: 0 },
  };
  g.ball = { x: LANE_X, y: LANE_Y, vx: 0, vy: 0, layer: 0 };
  g.events = []; g.score = 0; g.ballsLeft = 3; g.multiplier = 1; g.bumperHits = 0; g.charge = 0; g.time = 0; g.lastHit = -1;
  g.combo = 0; g.lastScoreAt = -10; g.lastBall = null; g.newBest = false;
}

export function startGame(g) { const best = g.best; reset(g); g.best = best; g.state = 'ready'; }
/** Things that happened this step (bumper hit, flip, launch, drain...), for sound and effects. The page reads and clears the list; it never grows past 64. */
function emit(g, e) { if (g.events.length < 64) g.events.push(e); }

export function togglePause(g) { if (g.state === 'playing') g.state = 'paused'; else if (g.state === 'paused') g.state = 'playing'; }

export function flipperTip(g, side) {
  const f = g.flippers[side];
  return { x: f.px + FLIPPER_LEN * Math.cos(f.angle), y: f.py + FLIPPER_LEN * Math.sin(f.angle) };
}

function nearestOnSegment(px, py, s) {
  const dx = s.x2 - s.x1, dy = s.y2 - s.y1;
  const t = Math.max(0, Math.min(1, ((px - s.x1) * dx + (py - s.y1) * dy) / (dx * dx + dy * dy)));
  return { x: s.x1 + t * dx, y: s.y1 + t * dy };
}

/** Pushes the ball out of a thick segment and bounces it. `wx, wy` is how fast the segment itself is moving at the contact (a swinging flipper). Returns null with no contact, or how hard the ball hit it. */
function collideSegment(ball, s, thick, bounce, wx = 0, wy = 0, ox = 0, oy = 0, omega = 0) {
  const c = nearestOnSegment(ball.x, ball.y, s);
  let nx = ball.x - c.x, ny = ball.y - c.y;
  let d = Math.hypot(nx, ny);
  const reach = BALL_R + thick;
  if (d >= reach) return null;
  if (d < 1e-6) { nx = 0; ny = -1; d = 0; } else { nx /= d; ny /= d; }
  ball.x += nx * (reach - d); ball.y += ny * (reach - d);
  if (omega) { wx = -omega * (c.y - oy); wy = omega * (c.x - ox); }
  const rvx = ball.vx - wx, rvy = ball.vy - wy;
  const vn = rvx * nx + rvy * ny;
  if (vn < 0) { ball.vx -= (1 + bounce) * vn * nx; ball.vy -= (1 + bounce) * vn * ny; }
  return { impact: Math.max(0, -vn) };
}

function moveFlippers(g, input, h) {
  for (const side of ['left', 'right']) {
    const f = g.flippers[side];
    if (input[side] && !f.pressed) emit(g, { type: 'flip', side });
    f.pressed = !!input[side];
    const target = input[side] ? f.up : f.rest;
    const before = f.angle;
    const delta = target - f.angle;
    const stepAngle = Math.sign(delta) * Math.min(Math.abs(delta), g.tuning.flipperSpeed * h);
    f.angle += stepAngle;
    f.omega = stepAngle / h;
    if (f.angle === before) f.omega = 0;
  }
}

/** One scoring hit (a bumper or a trap): counts for the combo, the multiplier and the end-of-ball bonus. */
function scoreHit(g, base, x, y, type, extra = {}) {
  g.combo = g.time - g.lastScoreAt <= COMBO_WINDOW && g.combo > 0 ? g.combo + 1 : 1; g.lastScoreAt = g.time;
  const pts = (base + COMBO_STEP * Math.max(0, g.combo - 2)) * g.multiplier;
  g.score += pts; emit(g, { type, x, y, pts, ...extra });
  if (g.combo >= 3) emit(g, { type: 'combo', combo: g.combo });
  if (g.combo % 5 === 0) { const bonus = SUPER_COMBO * g.multiplier; g.score += bonus; emit(g, { type: 'supercombo', combo: g.combo, pts: bonus }); }
  g.bumperHits++;
  const level = Math.max(g.multiplier, Math.min(5, 1 + Math.floor(g.bumperHits / 5)));
  if (level > g.multiplier) { g.multiplier = level; emit(g, { type: 'multiplier', value: level }); }
}

/** Every ball in play: yours first, then the free extras. */
export function allBalls(g) { return [g.ball, ...g.extra]; }

function release(g) {
  const t = g.trap; const b = t.ball; const sa = t.s; g.trap = null; sa.cool = g.time + 0.8;
  if (sa.kind === 'kick') {
    b.vx = sa.vx; b.vy = sa.vy; // up and across the table
    const room = Math.max(0, MAX_BALLS - 1 - g.extra.length); const shots = sa.extras.slice(0, room);
    for (const sh of shots) g.extra.push({ x: sa.x, y: sa.y, vx: sh.vx, vy: sh.vy, layer: 0 });
    if (shots.length) emit(g, { type: 'multiball', count: shots.length, x: sa.x, y: sa.y });
  } else { b.layer = 1; b.layerSince = g.time; g.layerSince = g.time; g.deckSide = -g.deckSide; b.vx = 40 * g.deckSide; b.vy = 60; emit(g, { type: 'layer', layer: 1 }); } // the sideways nudge keeps it off the exact centre line
  emit(g, { type: 'release', x: sa.x, y: sa.y, kind: sa.kind });
}

function substep(g, b, h) {
  if (g.trap && g.trap.ball === b) { b.x = g.trap.s.x; b.y = g.trap.s.y; b.vx = 0; b.vy = 0; if (g.time >= g.trap.until) release(g); return; }
  b.vy += g.tuning.gravity * h;
  b.x += b.vx * h; b.y += b.vy * h;
  const sp = Math.hypot(b.vx, b.vy);
  if (sp > MAX_SPEED) { b.vx *= MAX_SPEED / sp; b.vy *= MAX_SPEED / sp; }
  b.vx *= 1 - 0.05 * h; b.vy *= 1 - 0.05 * h;

  for (let pass = 0; pass < 2; pass++) {
    for (const w of WALLS) {
      if (w.oneWay && b.vy < 0) continue;
      const hit = collideSegment(b, w, w.thick ?? 0, g.tuning.wallBounce);
      if (hit && hit.impact > HARD_HIT) emit(g, { type: 'wall', x: b.x, y: b.y, impact: hit.impact });
    }
    if (b.layer === 1) for (const w of DECK_WALLS) collideSegment(b, w, w.thick, g.tuning.wallBounce);
    else for (const side of ['left', 'right']) {
      const f = g.flippers[side];
      const seg = { x1: f.px, y1: f.py, x2: f.px + FLIPPER_LEN * Math.cos(f.angle), y2: f.py + FLIPPER_LEN * Math.sin(f.angle) };
      const hit = collideSegment(b, seg, FLIPPER_THICK, g.tuning.flipperBounce, 0, 0, f.px, f.py, f.omega);
      if (hit && hit.impact > HARD_HIT) emit(g, { type: 'flipper-hit', x: b.x, y: b.y, impact: hit.impact });
    }
  }
  for (const bu of g.bumpers) {
    if ((bu.layer ?? 0) !== b.layer) continue;
    let nx = b.x - bu.x, ny = b.y - bu.y; const d = Math.hypot(nx, ny); const reach = bu.r + BALL_R;
    if (d >= reach) continue;
    if (d < 1e-6) { nx = 0; ny = -1; } else { nx /= d; ny /= d; }
    b.x = bu.x + nx * reach; b.y = bu.y + ny * reach;
    const kick = g.tuning.bumperKick;
    if (b.vx * nx + b.vy * ny < kick) { const vn = b.vx * nx + b.vy * ny; b.vx += (kick - vn) * nx; b.vy += (kick - vn) * ny; }
    if (g.time - (b.lastHit ?? -1) > 0.03 || bu !== b.lastBumper) {
      scoreHit(g, bu.pts ?? BUMPER_POINTS, bu.x, bu.y, 'bumper');
      if (bu.bank) {
        bu.lit = true;
        const bank = g.bumpers.filter((x) => x.bank);
        if (bank.every((x) => x.lit)) { const pts = JACKPOT * g.multiplier; g.score += pts; emit(g, { type: 'jackpot', pts, multiplier: g.multiplier }); for (const x of bank) x.lit = false; }
      }
    }
    b.lastHit = g.time; b.lastBumper = bu; g.lastHit = g.time; g.lastBumper = bu;
  }
  if (b.layer === 0) {
    for (const sa of g.saucers) {
      if (g.trap || g.time < sa.cool || Math.hypot(b.x - sa.x, b.y - sa.y) >= sa.r || Math.hypot(b.vx, b.vy) >= 800) continue;
      g.trap = { s: sa, until: g.time + sa.hold, ball: b }; b.x = sa.x; b.y = sa.y; b.vx = 0; b.vy = 0;
      scoreHit(g, sa.pts, sa.x, sa.y, 'trap', { kind: sa.kind });
      break;
    }
  } else if (b.y > DECK_EXIT_Y || g.time - (b.layerSince ?? g.layerSince) > DECK_MAX) { b.layer = 0; emit(g, { type: 'layer', layer: 0 }); }
}

function drain(g) {
  const number = 3 - g.ballsLeft + 1;
  const bonus = BONUS_PER_HIT * g.bumperHits * g.multiplier;
  if (bonus > 0) { g.score += bonus; emit(g, { type: 'bonus', pts: bonus, hits: g.bumperHits, multiplier: g.multiplier }); }
  g.lastBall = { number, bonus, hits: g.bumperHits };
  g.ballsLeft--; g.multiplier = 1; g.bumperHits = 0; g.combo = 0; g.charge = 0; g.trap = null; g.extra = [];
  for (const x of g.bumpers) x.lit = false;
  g.ball = { x: LANE_X, y: LANE_Y, vx: 0, vy: 0, layer: 0 };
  emit(g, { type: 'drain' });
  if (g.ballsLeft <= 0) { g.ballsLeft = 0; g.state = 'over'; g.newBest = g.score > g.best; g.best = Math.max(g.best, g.score); emit(g, { type: 'over' }); } else g.state = 'ready';
}

export function step(g, input, rawDt) {
  const dt = Math.min(Math.max(rawDt, 0), MAX_DT);
  if (g.state === 'ready') {
    if (input.plunger) g.charge = Math.min(1, g.charge + dt / 0.8);
    else if (g.charge > 0.02) { g.ball.vy = -(700 + 1000 * g.charge); g.ball.vx = 0; emit(g, { type: 'launch', power: g.charge }); g.charge = 0; g.state = 'playing'; }
    else g.charge = 0;
    moveFlippers(g, input, dt || 1);
    return;
  }
  if (g.state !== 'playing') return;
  const n = Math.max(1, Math.ceil(dt / SUB)); const h = dt / n;
  for (let i = 0; i < n; i++) {
    g.time += h;
    moveFlippers(g, input, h);
    for (const b of allBalls(g)) substep(g, b, h);
    const lost = g.extra.filter((x) => x.y > DRAIN_Y);
    if (lost.length) { g.extra = g.extra.filter((x) => x.y <= DRAIN_Y); for (const x of lost) emit(g, { type: 'extra-lost', x: x.x }); }
    if (g.ball.y > DRAIN_Y) {
      if (g.extra.length) { g.ball = g.extra.shift(); emit(g, { type: 'extra-lost', x: g.ball.x }); } // an extra becomes your ball: no ball is lost while another is in play
      else { drain(g); return; }
    }
  }
}
