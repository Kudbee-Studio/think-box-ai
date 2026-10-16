// The page: wires keyboard, touch and the sound button to the game, runs the clock, keeps the high scores. Rules are in game.js, drawing in render.js.
import { createGame, step, startGame, togglePause, addHighScore, cleanInitials, useBomb, setDifficulty, selectWeapon, cycleWeapon, DIFFICULTIES, WEAPONS, WIDTH, HEIGHT } from './game.js';
import { createInput, GAME_KEYS } from './input.js';
import { draw } from './render.js';
import { createSound } from './sound.js';
import { createEffects } from './effects.js';
import { parseScores } from './scores.js';

const DIFFICULTY_KEY = 'starfall-difficulty';
const scoresKey = (d) => `starfall-scores-${d}`; // a table for each difficulty (v0.2's single table is read as Normal)
const MUTE_KEY = 'starfall-muted';
const RESTART_DELAY = 700;
const canvas = document.getElementById('game');
canvas.width = WIDTH; canvas.height = HEIGHT;
const ctx = canvas.getContext('2d');
const game = createGame(Date.now() & 0x7fffffff);
const input = createInput();
const sound = createSound(window.AudioContext || window.webkitAudioContext);
const fx = createEffects({ reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches });
const initialsBox = document.getElementById('initials');
const muteButton = document.getElementById('mute');

function loadScores(d) { try { return parseScores(localStorage.getItem(scoresKey(d)) ?? (d === 'normal' ? localStorage.getItem('starfall-scores') : null)); } catch { return []; } }
let difficulty = 'normal'; try { const saved = localStorage.getItem(DIFFICULTY_KEY); if (saved && Object.prototype.hasOwnProperty.call(DIFFICULTIES, saved)) difficulty = saved; sound.setMuted(localStorage.getItem(MUTE_KEY) === '1'); } catch { /* private window: nothing is remembered */ }
setDifficulty(game, difficulty);
let scores = loadScores(difficulty);
game.best = scores[0]?.score ?? 0;
const view = { scores, entering: false, rank: null, restartReady: true, difficulty };
let overAt = 0; let touchX = null;

function saveScores() { try { localStorage.setItem(scoresKey(difficulty), JSON.stringify(scores)); } catch { /* not remembered */ } }
function showMute() { muteButton.textContent = sound.muted ? 'Sound off' : 'Sound on'; muteButton.setAttribute('aria-pressed', String(sound.muted)); }
function toggleMute() { sound.setMuted(!sound.muted); showMute(); try { localStorage.setItem(MUTE_KEY, sound.muted ? '1' : '0'); } catch { /* not remembered */ } }
showMute();
muteButton.addEventListener('click', () => { sound.unlock(); toggleMute(); muteButton.blur(); });

// Easy / Normal / Hard: a change is only taken between games, and each difficulty keeps its own high scores
const difficultyHost = document.getElementById('difficulty'); const difficultyButtons = {};
function showDifficulty() { for (const [name, b] of Object.entries(difficultyButtons)) b.setAttribute('aria-pressed', String(name === difficulty)); }
for (const name of Object.keys(DIFFICULTIES)) {
  const b = document.createElement('button'); b.type = 'button'; b.className = 'difficulty-button'; b.textContent = name[0].toUpperCase() + name.slice(1);
  b.addEventListener('click', () => {
    if (game.state === 'playing' || game.state === 'paused' || view.entering) return;
    difficulty = name; setDifficulty(game, name); scores = loadScores(name); view.scores = scores; view.difficulty = name; game.best = scores[0]?.score ?? 0; view.rank = null; showDifficulty();
    try { localStorage.setItem(DIFFICULTY_KEY, name); } catch { /* not remembered */ } b.blur();
  });
  difficultyButtons[name] = b; difficultyHost.appendChild(b);
}
showDifficulty();

function startOrRestart() {
  if (view.entering) return;
  if (game.state === 'over' && performance.now() - overAt < RESTART_DELAY) return;
  if (game.state === 'title' || game.state === 'over') { input.clear(); startGame(game); fx.banner = null; view.rank = null; }
}

function finishInitials() {
  if (!view.entering) return;
  const result = addHighScore(scores, { name: cleanInitials(initialsBox.value), score: game.score });
  scores = result.list; view.scores = scores; view.rank = result.rank; view.entering = false; saveScores();
  initialsBox.hidden = true; initialsBox.value = ''; canvas.focus(); overAt = performance.now();
}
initialsBox.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') { e.preventDefault(); finishInitials(); } });
initialsBox.addEventListener('input', () => { initialsBox.value = initialsBox.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 3); });

addEventListener('keydown', (e) => {
  if (e.target === initialsBox) return;
  sound.unlock();
  if (GAME_KEYS.has(e.code)) e.preventDefault();
  if (!e.repeat) {
    if (e.code === 'KeyM') { toggleMute(); return; }
    if (e.code === 'KeyB') { useBomb(game); return; }
    if (/^Digit[1-4]$/.test(e.code)) { selectWeapon(game, Object.keys(WEAPONS)[Number(e.code.slice(5)) - 1]); return; }
    if (e.code === 'KeyQ') { cycleWeapon(game, -1); return; }
    if (e.code === 'KeyE') { cycleWeapon(game, 1); return; }
    if (e.code === 'Enter') startOrRestart();
    else if (e.code === 'KeyP') togglePause(game);
    else if (e.code === 'Space' && (game.state === 'title' || game.state === 'over')) { startOrRestart(); return; }
  }
  input.key(e.code, true);
});
addEventListener('keyup', (e) => input.key(e.code, false));
addEventListener('blur', () => { input.clear(); touchX = null; if (game.state === 'playing') togglePause(game); });

const toGame = (e) => { const r = canvas.getBoundingClientRect(); return ((e.clientX - r.left) / r.width) * WIDTH; };
canvas.addEventListener('pointerdown', (e) => { sound.unlock(); if (game.state !== 'playing') { startOrRestart(); return; } touchX = toGame(e); canvas.setPointerCapture?.(e.pointerId); });
canvas.addEventListener('pointermove', (e) => { if (touchX !== null) touchX = toGame(e); });
for (const ev of ['pointerup', 'pointercancel']) canvas.addEventListener(ev, () => { touchX = null; });

document.querySelector('[data-weapon]')?.addEventListener('pointerdown', (e) => { e.preventDefault(); sound.unlock(); cycleWeapon(game, 1); });
document.querySelector('[data-bomb]')?.addEventListener('pointerdown', (e) => { e.preventDefault(); sound.unlock(); useBomb(game); });
for (const btn of document.querySelectorAll('[data-touch]')) {
  const name = btn.dataset.touch;
  btn.addEventListener('pointerdown', (e) => { e.preventDefault(); sound.unlock(); startOrRestart(); input.touch(name, true); });
  for (const ev of ['pointerup', 'pointerleave', 'pointercancel']) btn.addEventListener(ev, () => input.touch(name, false));
}

let last = performance.now();
function frame(now) {
  const dt = (now - last) / 1000; last = now;
  const keys = input.read();
  const was = game.state;
  step(game, { left: keys.left, right: keys.right, fire: keys.fire || touchX !== null, ...(touchX !== null ? { targetX: touchX } : {}) }, dt);
  for (const e of game.events) {
    sound.play(e); fx.handle(e);
    if (e.type === 'over') { overAt = performance.now(); const preview = addHighScore(scores, { name: 'AAA', score: game.score }); if (preview.rank !== null) { view.entering = true; initialsBox.hidden = false; initialsBox.focus(); } }
  }
  game.events.length = 0;
  fx.update(Math.min(dt, 0.05));
  view.restartReady = !view.entering && performance.now() - overAt >= RESTART_DELAY;
  draw(ctx, game, fx, view);
  requestAnimationFrame(frame);
  void was;
}
requestAnimationFrame(frame);
window.__starfall = game; window.__starfallFx = fx; window.__starfallSound = sound; window.__starfallView = view; // read by the browser check in tests/browser-check.mjs
