// The page: wires the keyboard and touch buttons to the game, runs the clock, saves the best score. Rules are in game.js, drawing in render.js.
import { createGame, step, startGame, togglePause, WIDTH, HEIGHT } from './game.js';
import { createInput, GAME_KEYS } from './input.js';
import { draw } from './render.js';

const BEST_KEY = 'starfall-best';
const canvas = document.getElementById('game');
canvas.width = WIDTH; canvas.height = HEIGHT;
const ctx = canvas.getContext('2d');
const game = createGame(Date.now() & 0x7fffffff);
const input = createInput();

try { game.best = Number(localStorage.getItem(BEST_KEY)) || 0; } catch { /* private window: the best score just is not remembered */ }
let savedBest = game.best;

function startOrRestart() { if (game.state === 'title' || game.state === 'over') { input.clear(); startGame(game); } }

addEventListener('keydown', (e) => {
  if (GAME_KEYS.has(e.code)) e.preventDefault();
  if (e.repeat) { input.key(e.code, true); return; }
  if (e.code === 'Enter') startOrRestart();
  else if (e.code === 'KeyP') togglePause(game);
  else if (e.code === 'Space' && (game.state === 'title' || game.state === 'over')) startOrRestart();
  input.key(e.code, true);
});
addEventListener('keyup', (e) => input.key(e.code, false));
addEventListener('blur', () => { input.clear(); if (game.state === 'playing') togglePause(game); });
canvas.addEventListener('pointerdown', startOrRestart);

for (const btn of document.querySelectorAll('[data-touch]')) {
  const name = btn.dataset.touch;
  btn.addEventListener('pointerdown', (e) => { e.preventDefault(); startOrRestart(); input.touch(name, true); });
  for (const ev of ['pointerup', 'pointerleave', 'pointercancel']) btn.addEventListener(ev, () => input.touch(name, false));
}

let last = performance.now();
function frame(now) {
  step(game, input.read(), (now - last) / 1000);
  last = now;
  if (game.best > savedBest) { savedBest = game.best; try { localStorage.setItem(BEST_KEY, String(savedBest)); } catch { /* not remembered */ } }
  draw(ctx, game);
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
window.__starfall = game; // read by the browser check in tests/browser-check.mjs
