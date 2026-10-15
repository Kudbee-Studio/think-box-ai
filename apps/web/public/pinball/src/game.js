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
const LANE_X = 445;
const LANE_Y = 782;

/** The fixed walls: a round top (a half circle), side walls, the launch lane and the two guides that lead down to the flippers. */
function buildWalls() {
  const w = [];
  const cx = 240, cy = 260, R = 220, N = 28;
  for (let i = 0; i < N; i++) {
    const a0 = Math.PI - (i * Math.PI) / N, a1 = Math.PI - ((i + 1) * Math.PI) / N;
    w.push({ x1: cx + R * Math.cos(a0), y1: cy - R * Math.sin(a0), x2: cx + R * Math.cos(a1), y2: cy - R * Math.sin(a1) });
  }
  w.push({ x1: 20, y1: 260, x2: 20, y2: 640 });     // left wall
  w.push({ x1: 460, y1: 260, x2: 460, y2: 790 });   // right wall (outside of the launch lane)
  w.push({ x1: 430, y1: 330, x2: 430, y2: 790 });   // inside of the launch lane
  w.push({ x1: 430, y1: 790, x2: 460, y2: 790 });   // floor of the lane
  w.push({ x1: 460, y1: 316, x2: 432, y2: 330, oneWay: true }); // gate: a ball going up passes, one coming down slides off into the playfield
  w.push({ x1: 20, y1: 640, x2: 145, y2: 722 });    // left guide
  w.push({ x1: 430, y1: 640, x2: 335, y2: 722 });   // right guide
  return w;
}
export const WALLS = buildWalls();
const deg = (d) => (d * Math.PI) / 180;

export function createGame() {
  const g = { state: 'title', best: 0, tuning: { ...DEFAULTS } };
  reset(g);
  return g;
}

function reset(g) {
  g.bumpers = [{ x: 170, y: 300, r: 26 }, { x: 310, y: 300, r: 26 }, { x: 240, y: 400, r: 26 }];
  g.flippers = {
    left: { px: 160, py: 730, rest: deg(26), up: deg(-34), angle: deg(26), omega: 0 },
    right: { px: 320, py: 730, rest: deg(154), up: deg(214), angle: deg(154), omega: 0 },
  };
  g.ball = { x: LANE_X, y: LANE_Y, vx: 0, vy: 0 };
  g.events = []; g.score = 0; g.ballsLeft = 3; g.multiplier = 1; g.bumperHits = 0; g.charge = 0; g.time = 0; g.lastHit = -1;
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

function substep(g, h) {
  const b = g.ball;
  b.vy += g.tuning.gravity * h;
  b.x += b.vx * h; b.y += b.vy * h;
  const sp = Math.hypot(b.vx, b.vy);
  if (sp > MAX_SPEED) { b.vx *= MAX_SPEED / sp; b.vy *= MAX_SPEED / sp; }
  b.vx *= 1 - 0.05 * h; b.vy *= 1 - 0.05 * h;

  for (let pass = 0; pass < 2; pass++) {
    for (const w of WALLS) {
      if (w.oneWay && b.vy < 0) continue;
      const hit = collideSegment(b, w, 0, g.tuning.wallBounce);
      if (hit && hit.impact > HARD_HIT) emit(g, { type: 'wall', x: b.x, y: b.y, impact: hit.impact });
    }
    for (const side of ['left', 'right']) {
      const f = g.flippers[side];
      const seg = { x1: f.px, y1: f.py, x2: f.px + FLIPPER_LEN * Math.cos(f.angle), y2: f.py + FLIPPER_LEN * Math.sin(f.angle) };
      const hit = collideSegment(b, seg, FLIPPER_THICK, g.tuning.flipperBounce, 0, 0, f.px, f.py, f.omega);
      if (hit && hit.impact > HARD_HIT) emit(g, { type: 'flipper-hit', x: b.x, y: b.y, impact: hit.impact });
    }
  }
  for (const bu of g.bumpers) {
    let nx = b.x - bu.x, ny = b.y - bu.y; const d = Math.hypot(nx, ny); const reach = bu.r + BALL_R;
    if (d >= reach) continue;
    if (d < 1e-6) { nx = 0; ny = -1; } else { nx /= d; ny /= d; }
    b.x = bu.x + nx * reach; b.y = bu.y + ny * reach;
    const kick = g.tuning.bumperKick;
    if (b.vx * nx + b.vy * ny < kick) { const vn = b.vx * nx + b.vy * ny; b.vx += (kick - vn) * nx; b.vy += (kick - vn) * ny; }
    if (g.time - g.lastHit > 0.03 || bu !== g.lastBumper) { const pts = BUMPER_POINTS * g.multiplier; g.score += pts; emit(g, { type: 'bumper', x: bu.x, y: bu.y, pts }); g.bumperHits++; g.multiplier = Math.max(g.multiplier, Math.min(5, 1 + Math.floor(g.bumperHits / 5))); }
    g.lastHit = g.time; g.lastBumper = bu;
  }
}

function drain(g) {
  g.ballsLeft--; g.multiplier = 1; g.bumperHits = 0; g.charge = 0;
  g.ball = { x: LANE_X, y: LANE_Y, vx: 0, vy: 0 };
  emit(g, { type: 'drain' });
  if (g.ballsLeft <= 0) { g.ballsLeft = 0; g.state = 'over'; g.best = Math.max(g.best, g.score); emit(g, { type: 'over' }); } else g.state = 'ready';
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
    substep(g, h);
    if (g.ball.y > HEIGHT + 20) { drain(g); return; }
  }
}
