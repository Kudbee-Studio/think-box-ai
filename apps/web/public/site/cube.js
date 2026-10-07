/* thinkTokens: scroll-driven, interactive 3D cube. three.js is vendored locally (vendor/three.module.js), no CDN.
   Tap any sticker: its layer twists and an "issue → resolution" card explains the concept.
   Scramble / Solve: a metaphor. Each twist stands for one problem, and solving replays the fixes in reverse. */
import * as THREE from './vendor/three.module.min.js';
import { createCube } from './cube-model.js';

const TT = window.TT || { progress: 0, parts: {}, stepParts: [] };
const root = document.documentElement;
const canvas = document.getElementById('cube-canvas');
const stage = document.getElementById('stage');
const tip = document.getElementById('cube-tip');
const card = document.getElementById('cube-card');
const btnScramble = document.getElementById('cube-scramble');
const btnSolve = document.getElementById('cube-solve');
const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const isMobile = window.matchMedia('(max-width: 900px), (pointer: coarse)').matches;

function fail() { root.classList.add('no-webgl'); TT.cubeReady = false; }

let renderer;
try {
  const test = document.createElement('canvas');
  if (!(test.getContext('webgl2') || test.getContext('webgl'))) throw new Error('no webgl');
  const dpr = Math.min(window.devicePixelRatio || 1, isMobile ? 1.75 : 2);
  renderer = new THREE.WebGLRenderer({ canvas, antialias: !isMobile || dpr < 1.5, alpha: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(dpr);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
} catch (e) { fail(); }

if (renderer) init();

function init() {
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
  scene.add(new THREE.AmbientLight(0xffffff, 0.6));
  const key = new THREE.DirectionalLight(0xffffff, 2.1); key.position.set(5, 8, 7); scene.add(key);
  const rim = new THREE.PointLight(0xa78bfa, 40, 30); rim.position.set(-6, -2, 5); scene.add(rim);
  if (!isMobile) { const rim2 = new THREE.PointLight(0x38bdf8, 30, 30); rim2.position.set(6, -5, -2); scene.add(rim2); }

  const M = createCube(THREE, { tex: isMobile ? 200 : 288, anisotropy: isMobile ? 2 : 4 });
  const { cube, cubies, pickables, FACES, FACE_KEYS, matsByFace, SP } = M;
  scene.add(cube);

  // Target orientation per step (0 = hero)
  const tilt = new THREE.Quaternion().setFromEuler(new THREE.Euler(0.42, -0.58, 0));
  const stepQ = [new THREE.Quaternion().setFromEuler(new THREE.Euler(0.5, -0.75, 0))];
  for (let i = 1; i < TT.stepParts.length; i++) stepQ.push(tilt.clone().multiply(FACES[TT.stepParts[i]].qAlign));
  const TW = [{ a: 'y', l: 1 }, { a: 'x', l: -1 }, { a: 'z', l: 0 }, { a: 'y', l: -1 }, { a: 'x', l: 1 }, { a: 'z', l: 1 }];
  const AX = { x: new THREE.Vector3(1, 0, 0), y: new THREE.Vector3(0, 1, 0), z: new THREE.Vector3(0, 0, 1) };

  /* ---------- Move engine (stateful layer twists) ---------- */
  const queue = []; let anim = null; const history = []; let seq = null; // seq: 'scramble' | 'solve' | null
  const qR = new THREE.Quaternion(), vTmp = new THREE.Vector3();
  function commit(m) {
    qR.setFromAxisAngle(AX[m.a], m.d * Math.PI / 2);
    for (const c of cubies) if (Math.round(c.userData.pos[m.a]) === m.l) {
      c.userData.pos.applyQuaternion(qR).round(); c.userData.rot.premultiply(qR).normalize();
    }
  }
  function enqueue(m) { queue.push(m); wake(); }
  function nextMove() {
    if (anim || !queue.length) return;
    const m = queue.shift();
    if (m.onStart) m.onStart();
    if (reduced || m.dur === 0) { commit(m); if (m.onEnd) m.onEnd(); nextMove(); return; }
    anim = { m, t: 0 };
  }

  /* ---------- Issue card ---------- */
  function esc(s) { return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
  function showCard(st, mode, extra) {
    const u = st.userData, f = FACES[u.face], [label, prob, res, ref, planned] = u.concept;
    const head = mode === 'issue' ? `<span class="cc__mode cc__mode--issue">${extra}</span>` : mode === 'solve' ? `<span class="cc__mode cc__mode--ok">${extra}</span>` : '';
    card.innerHTML = `<button type="button" class="cc__x" aria-label="Close">✕</button>${head}
      <p class="cc__k"><span style="background:${f.c}"></span>${esc(f.name)} · <b>${esc(label)}</b>${planned ? ' <span class="badge b-planned">Planned</span>' : ''}</p>
      <p class="cc__p"><b>Problem:</b> ${esc(prob)}</p><p class="cc__r"><b>Resolution:</b> ${esc(res)}</p>
      <p class="cc__ref">${esc(ref)}${u.isCenter && TT.goToStep ? ` · <button type="button" class="cc__go" data-step="${f.step}">Read about ${esc(f.name)} →</button>` : ''}</p>`;
    card.hidden = false;
  }
  function showSummary(html) { card.innerHTML = `<button type="button" class="cc__x" aria-label="Close">✕</button>${html}`; card.hidden = false; }
  card.addEventListener('click', (e) => {
    if (e.target.closest('.cc__x')) card.hidden = true;
    const go = e.target.closest('.cc__go'); if (go) TT.goToStep(+go.dataset.step);
  });
  function updateButtons() {
    btnScramble.disabled = !!seq; btnSolve.disabled = !!seq || history.length === 0;
    btnSolve.textContent = history.length ? `Solve (${history.length})` : 'Solve';
  }

  // Which layer does a tapped sticker twist? The face itself for centers, otherwise the outer layer through that sticker.
  const keyOf = (v) => { const ax = Math.abs(v.x), ay = Math.abs(v.y), az = Math.abs(v.z); return ax > ay && ax > az ? 'x' : ay > az ? 'y' : 'z'; };
  function moveFor(st) {
    const c = st.userData.cubie, pos = c.userData.pos;
    const nAx = keyOf(vTmp.copy(st.userData.normal).applyQuaternion(c.userData.rot));
    const others = ['x', 'y', 'z'].filter((a) => a !== nAx);
    let a = others.find((o) => Math.round(pos[o]) !== 0);
    if (!a) a = nAx; // center sticker: rotate its own face
    return { a, l: Math.round(pos[a]), d: 1 };
  }
  function tapSticker(st) {
    if (seq) return;
    const m = moveFor(st); m.dur = 0.34;
    m.onEnd = () => { history.push({ a: m.a, l: m.l, d: m.d, st }); updateButtons(); };
    enqueue(m); showCard(st);
    nextMove();
  }
  function scramble() {
    if (seq) return; seq = 'scramble'; updateButtons();
    const pool = pickables.filter((p) => !p.userData.isCenter).sort(() => Math.random() - 0.5);
    const N = 10; let last = null;
    for (let i = 0; i < N; i++) {
      let a, l; do { a = 'xyz'[Math.floor(Math.random() * 3)]; l = [-1, 0, 1][Math.floor(Math.random() * 3)]; } while (last && last.a === a && last.l === l);
      last = { a, l }; const st = pool[i], d = Math.random() < 0.5 ? 1 : -1;
      enqueue({ a, l, d, dur: 0.24, onStart: () => showCard(st, 'issue', `Issue ${i + 1} / ${N}`), onEnd: () => { history.push({ a, l, d, st }); updateButtons(); if (i === N - 1) { seq = null; updateButtons(); if (reduced) showSummary(`<p class="cc__mode cc__mode--issue">Scrambled · ${N} issues</p><p class="cc__p">Each twist stands for one real problem. Press <b>Solve</b> to see how each one is resolved.</p>`); } } });
    }
    nextMove();
  }
  function solve() {
    if (seq || !history.length) return; seq = 'solve'; updateButtons();
    const steps = history.splice(0).reverse(); const total = steps.length; const done = [];
    steps.forEach((h, i) => {
      enqueue({ a: h.a, l: h.l, d: -h.d, dur: 0.4, pause: 0.55,
        onStart: () => showCard(h.st, 'solve', `Resolving ${i + 1} / ${total}`),
        onEnd: () => { done.push(h.st); updateButtons(); if (i === total - 1) { seq = null; updateButtons();
          showSummary(`<p class="cc__mode cc__mode--ok">Solved · ${total} issue${total > 1 ? 's' : ''} resolved</p><ul class="cc__list">${done.slice(-6).map((s) => `<li><b>${esc(s.userData.concept[0])}</b>: ${esc(s.userData.concept[2])}</li>`).join('')}</ul><p class="cc__ref">A metaphor: the solve replays the twists in reverse.</p>`); } } });
    });
    updateButtons(); nextMove();
  }
  btnScramble.addEventListener('click', scramble);
  btnSolve.addEventListener('click', solve);
  updateButtons();

  /* ---------- Pointer interaction ---------- */
  let yaw = 0, pitch = 0, vyaw = 0, dragging = false, lx = 0, ly = 0, t0 = 0, moved = 0, pType = 'mouse';
  canvas.addEventListener('pointerdown', (e) => { dragging = true; pType = e.pointerType; lx = e.clientX; ly = e.clientY; t0 = performance.now(); moved = 0; if (e.pointerType === 'mouse') canvas.setPointerCapture(e.pointerId); });
  canvas.addEventListener('pointermove', (e) => {
    if (!dragging) { if (e.pointerType === 'mouse') hover(e); return; }
    const dx = e.clientX - lx, dy = e.clientY - ly; lx = e.clientX; ly = e.clientY;
    moved += Math.abs(dx) + Math.abs(dy);
    vyaw = dx * 0.012; yaw += vyaw;
    if (pType === 'mouse') pitch = THREE.MathUtils.clamp(pitch + dy * 0.008, -0.9, 0.9);
    wake();
  });
  canvas.addEventListener('pointerup', (e) => { if (!dragging) return; dragging = false; if (moved < 8 && performance.now() - t0 < 500) { const st = pick(e); if (st) tapSticker(st); } });
  canvas.addEventListener('pointercancel', () => { dragging = false; });
  canvas.addEventListener('pointerleave', () => { if (pType === 'mouse' && !dragging) { tip.hidden = true; canvas.style.cursor = ''; } });
  canvas.tabIndex = 0;
  canvas.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowLeft') { yaw -= .3; wake(); } if (e.key === 'ArrowRight') { yaw += .3; wake(); }
    if (e.key === 'Enter' || e.key === ' ') { // keyboard: twist the center of the face currently shown
      e.preventDefault(); const k = TT.stepParts[Math.round(TT.progress)] || 'runtime';
      const st = pickables.find((p) => p.userData.isCenter && p.userData.face === k); if (st) tapSticker(st);
    }
  });
  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
  function pick(e) {
    const r = canvas.getBoundingClientRect();
    ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const hit = ray.intersectObjects(pickables, false)[0];
    return hit ? hit.object : null;
  }
  let lastHover = 0;
  function hover(e) {
    const now = performance.now(); if (now - lastHover < 80) return; lastHover = now;
    const st = pick(e); canvas.style.cursor = st ? 'pointer' : '';
    if (st && card.hidden) { tip.innerHTML = `<b style="color:${FACES[st.userData.face].c}">${esc(st.userData.concept[0])}</b> · click to twist`; tip.hidden = false; } else tip.hidden = true;
  }

  /* ---------- Sizing ---------- */
  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight; if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.position.set(0, 0, 2.75 / Math.tan(THREE.MathUtils.degToRad(15)) / Math.min(1, camera.aspect) * 1.02);
    camera.updateProjectionMatrix(); wake();
  }
  new ResizeObserver(resize).observe(canvas);

  /* ---------- Loop: only while visible ---------- */
  let visible = true, running = false, last = performance.now(), time = 0, activeFace = null, twW = 1, pauseLeft = 0;
  const qTarget = new THREE.Quaternion(), qCur = stepQ[0].clone(), qTmp = new THREE.Quaternion(), qUser = new THREE.Quaternion(), eul = new THREE.Euler(), qTw = new THREE.Quaternion();
  const smooth = (t) => t * t * (3 - 2 * t);
  TT.onStep = (s) => { activeFace = TT.stepParts[s]; wake(); };
  activeFace = TT.stepParts[Math.round(TT.progress)] || null;
  function wake() { if (!running && visible) { running = true; last = performance.now(); requestAnimationFrame(frame); } }
  new IntersectionObserver((e) => { visible = e[0].isIntersecting; if (visible) wake(); }, { threshold: 0 }).observe(stage);
  document.addEventListener('visibilitychange', () => { visible = !document.hidden; if (visible) wake(); });
  window.addEventListener('scroll', wake, { passive: true });

  let idleFrames = 0;
  function frame(now) {
    const dt = Math.min(0.05, (now - last) / 1000); last = now; time += dt;
    const p = THREE.MathUtils.clamp(TT.progress || 0, 0, stepQ.length - 1);
    let i = Math.floor(p), f = p - i; if (i >= stepQ.length - 1) { i = stepQ.length - 2; f = 1; }
    if (reduced) qTarget.copy(stepQ[Math.round(p)]);
    else qTarget.copy(stepQ[i]).slerp(stepQ[i + 1], smooth(THREE.MathUtils.clamp((f - 0.15) / 0.7, 0, 1)));
    if (!reduced && p < 1) { qTmp.setFromAxisAngle(AX.y, Math.sin(time * 0.35) * 0.35 * (1 - p)); qTarget.premultiply(qTmp); }
    if (!dragging) { vyaw *= 0.92; yaw += vyaw; yaw *= 0.965; pitch *= 0.95; }
    eul.set(pitch, yaw, 0); qUser.setFromEuler(eul); qTarget.premultiply(qUser);
    qCur.slerp(qTarget, reduced ? 1 : 1 - Math.exp(-dt * 9));
    cube.quaternion.copy(qCur);
    cube.position.y = reduced ? 0 : Math.sin(time * 1.1) * 0.06;

    // advance the move animation (with an optional caption pause after each move)
    if (pauseLeft > 0) { pauseLeft -= dt; if (pauseLeft <= 0) nextMove(); }
    else if (anim) {
      anim.t += dt / anim.m.dur;
      if (anim.t >= 1) { const m = anim.m; anim = null; commit(m); if (m.onEnd) m.onEnd(); if (m.pause && queue.length) pauseLeft = m.pause; else nextMove(); }
    } else nextMove();
    const busy = !!anim || queue.length > 0 || pauseLeft > 0;
    twW += ((busy ? 0 : 1) - twW) * Math.min(1, dt * 8);

    // compose: logical state, then the active move OR the transient scroll twist
    let ma = null, ml = 0, mAng = 0;
    if (anim) { ma = anim.m.a; ml = anim.m.l; mAng = anim.m.d * (Math.PI / 2) * smooth(Math.min(1, anim.t)); }
    else if (!reduced) { const tw = TW[Math.min(i, TW.length - 1)]; ma = tw.a; ml = tw.l; mAng = (Math.PI / 2) * Math.sin(Math.PI * smooth(f)) * twW; }
    if (ma && mAng) qTw.setFromAxisAngle(AX[ma], mAng);
    for (const c of cubies) {
      const u = c.userData;
      c.position.copy(u.pos).multiplyScalar(SP); c.quaternion.copy(u.rot);
      if (ma && mAng && Math.round(u.pos[ma]) === ml) { c.position.applyQuaternion(qTw); c.quaternion.premultiply(qTw); }
    }
    // active-face glow
    for (const k of FACE_KEYS) {
      const target = k === activeFace ? 0.62 : (activeFace ? 0.12 : 0.22);
      for (const mat of matsByFace[k]) mat.emissiveIntensity += (target - mat.emissiveIntensity) * Math.min(1, dt * 6);
    }
    renderer.render(scene, camera);

    const settled = !busy && qCur.angleTo(qTarget) < 0.0005 && Math.abs(vyaw) < 1e-4 && Math.abs(yaw) < 1e-3 && !dragging;
    idleFrames = settled && (reduced || p >= 1) ? idleFrames + 1 : 0;
    if (visible && idleFrames < 30) requestAnimationFrame(frame); else running = false;
  }
  resize();
  TT.cubeReady = true; root.classList.add('webgl'); root.classList.remove('no-webgl');
  TT.cubeScramble = scramble; TT.cubeSolve = solve;
  cubies.forEach((c) => (c.userData.home = c.userData.pos.clone()));
  TT.cubeSolved = () => cubies.every((c) => c.userData.pos.equals(c.userData.home) && Math.abs(c.userData.rot.w) > 0.9999);
  TT.cubeHistory = () => history.length;
  wake();
  renderer.domElement.addEventListener('webglcontextlost', (e) => { e.preventDefault(); fail(); });
}
