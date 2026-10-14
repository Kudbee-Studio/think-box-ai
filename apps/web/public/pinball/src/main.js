// The page: wires keyboard and touch to the game, runs the clock, saves the best score. Rules are in game.js, drawing in render.js.
import { createGame, step, startGame, togglePause, WALLS, WIDTH, HEIGHT } from './game.js';
import { createInput, GAME_KEYS } from './input.js';
import { draw } from './render.js';
import { createSound } from './sound.js';
import { createEffects } from './effects.js';
import { buildTuningPanel, loadTuning } from './tuning-ui.js';

const BEST_KEY = 'pinball-best';
const TUNING_KEY = 'pinball-tuning';
const MUTE_KEY = 'pinball-muted';
const canvas = document.getElementById('game');
canvas.width = WIDTH; canvas.height = HEIGHT;
const ctx = canvas.getContext('2d');
const game = createGame();
const input = createInput();
const sound = createSound(window.AudioContext || window.webkitAudioContext);
const fx = createEffects({ reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches });

try { game.best = Number(localStorage.getItem(BEST_KEY)) || 0; } catch { /* private window: the best score just is not remembered */ }
let savedBest = game.best;
try { loadTuning(game, localStorage.getItem(TUNING_KEY)); sound.setMuted(localStorage.getItem(MUTE_KEY) === '1'); } catch { /* private window: settings are not remembered */ }
const tuningHost = document.getElementById('tuning');
tuningHost.appendChild(buildTuningPanel(document, game, (t) => { try { localStorage.setItem(TUNING_KEY, JSON.stringify(t)); } catch { /* not remembered */ } }));

function startOrRestart() { if (game.state === 'title' || game.state === 'over') { input.clear(); startGame(game); } }

addEventListener('keydown', (e) => {
  sound.unlock();
  if (GAME_KEYS.has(e.code)) e.preventDefault();
  if (!e.repeat && e.code === 'KeyS') { sound.setMuted(!sound.muted); try { localStorage.setItem(MUTE_KEY, sound.muted ? '1' : '0'); } catch { /* not remembered */ } return; }
  if (!e.repeat && e.code === 'KeyT') { tuningHost.hidden = !tuningHost.hidden; return; }
  if (!e.repeat) {
    if (e.code === 'Enter') startOrRestart();
    else if (e.code === 'KeyP') togglePause(game);
    else if (e.code === 'Space' && (game.state === 'title' || game.state === 'over')) { startOrRestart(); return; }
  }
  input.key(e.code, true);
});
addEventListener('keyup', (e) => input.key(e.code, false));
addEventListener('blur', () => { input.clear(); if (game.state === 'playing') togglePause(game); });
canvas.addEventListener('pointerdown', () => { sound.unlock(); startOrRestart(); });

for (const btn of document.querySelectorAll('[data-touch]')) {
  const name = btn.dataset.touch;
  btn.addEventListener('pointerdown', (e) => { e.preventDefault(); sound.unlock(); startOrRestart(); input.touch(name, true); });
  for (const ev of ['pointerup', 'pointerleave', 'pointercancel']) btn.addEventListener(ev, () => input.touch(name, false));
}

let last = performance.now();
function frame(now) {
  const dt = (now - last) / 1000;
  step(game, input.read(), dt);
  last = now;
  for (const e of game.events) { sound.play(e); fx.handle(e); if (e.type === 'drain' || e.type === 'launch') fx.clearTrail(); }
  game.events.length = 0;
  if (game.state === 'playing') fx.trail(game.ball.x, game.ball.y);
  fx.update(Math.min(dt, 0.05));
  if (game.best > savedBest) { savedBest = game.best; try { localStorage.setItem(BEST_KEY, String(savedBest)); } catch { /* not remembered */ } }
  draw(ctx, game, WALLS, fx);
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
window.__pinball = game; window.__pinballFx = fx; window.__pinballSound = sound; // read by the browser check in tests/browser-check.mjs
