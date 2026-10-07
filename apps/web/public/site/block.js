/* THINK BOX AI · "Inside a single block": one cubelet in its own canvas, four layers, hotspots.
   Loaded lazily (dynamic import) when the section approaches the viewport. */
import * as THREE from './vendor/three.module.min.js';

const BLOCKS = {
  approval: { c: '#fb923c', name: 'Approval gate', scn: 'tool', layers: [
    'A plan wants to write a file or call an API, and some side effects cannot be undone.',
    'The runtime turns the step into a tool request. Governance checks its permission level, and anything with side effects stops at the gate until a human answers.',
    'Nothing irreversible runs without a yes, and the decision is written to the ledger.',
    'PR #269 (approval gates, run tracking) · AGENTS.md §1.4 (tools default to RESTRICTED)'] },
  origin: { c: '#f43f5e', name: 'Origin check', scn: 'attack', layers: [
    'Any web page you visit can try to open a WebSocket to your agent on 127.0.0.1.',
    'On the upgrade request, the web tier checks the Host and Origin headers against an allow-list before a session exists.',
    'Cross-origin connections get a 403 and are closed, so no session is created.',
    'PR #290 (WebSocket Origin + Host gate, shell_exec off, workspace-confined file ops)'] },
  telemetry: { c: '#34d399', name: 'Token telemetry', scn: 'ask', layers: [
    'Token spend across routes is invisible, so costs drift and nobody notices.',
    'Each request records prompt and completion tokens, tagged with its route (cheap local or fallback).',
    'You can see where the tokens went per route and tune the routing on evidence.',
    'PR #271 (token telemetry + Qwen2.5 1.5B local route)'] },
  sqlite: { c: '#facc15', name: 'SQLite memory', scn: 'memory', layers: [
    'Agents forget between sessions, and a database server is one more thing to run and secure.',
    'Memory and learning live in a local SQLite file with FTS5 search: patterns, session outcomes and thought artifacts.',
    'Zero-config persistence with simple backups. Postgres returns only if a measured reopen criterion is met.',
    'PR #288 (persistent learning) · ADR 026 (Neon revert) · ADR 027 (reopen criteria)'] },
  ledger: { c: '#a78bfa', name: 'Ledger', scn: 'tool', layers: [
    'After an incident, logs can be missing or edited after the fact.',
    'Every governed action and denial is appended to the action ledger, and receipts carry integrity checks.',
    'A tamper-evident trail of who asked, what ran and why it was allowed. Hash-chained, signed audit rows are planned for E1.',
    'README (append-only audit) · PR #251 (durable receipts) · ADR 027 E1 (Planned)'] }
};
const LNAMES = ['Problem', 'How it works', 'Resolution', 'Proof'];

const canvas = document.getElementById('block-canvas');
const stageEl = document.getElementById('blk-stage');
const hot = document.getElementById('blk-hot');
const cardEl = document.getElementById('blk-card');
const picks = [...document.querySelectorAll('#blk-picks [role=radio]')];
const tabs = [...document.querySelectorAll('#blk-layers [role=tab]')];
const explodeBtn = document.getElementById('blk-explode');
const RM = matchMedia('(prefers-reduced-motion: reduce)').matches;
const mobile = matchMedia('(max-width: 900px), (pointer: coarse)').matches;
let cur = 'approval', layer = 0, exploded = false;
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function renderCard() {
  const b = BLOCKS[cur];
  cardEl.style.setProperty('--c', b.c);
  cardEl.innerHTML = `<p class="blk-card__k"><span></span>${esc(b.name)} · ${LNAMES[layer]}</p><h3>${LNAMES[layer]}</h3><p>${esc(b.layers[layer])}</p>
    <button type="button" class="chip-btn" data-scn="${b.scn}">Watch it in the terminal →</button>`;
  tabs.forEach((t, i) => { t.setAttribute('aria-selected', String(i === layer)); t.tabIndex = i === layer ? 0 : -1; });
  cardEl.setAttribute('aria-labelledby', 'bl-' + layer);
}
cardEl.addEventListener('click', (e) => {
  const b = e.target.closest('[data-scn]'); if (!b) return;
  document.getElementById('terminal').scrollIntoView({ behavior: RM ? 'auto' : 'smooth' });
  setTimeout(() => window.TT && TT.termSelect && TT.termSelect(b.dataset.scn), RM ? 0 : 600);
});
tabs.forEach((t, i) => {
  t.addEventListener('click', () => selectLayer(i));
  t.addEventListener('keydown', (e) => { const d = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0; if (d) { e.preventDefault(); const n = (i + d + 4) % 4; selectLayer(n); tabs[n].focus(); } });
});
picks.forEach((p, i) => {
  p.addEventListener('click', () => selectBlock(p.dataset.b));
  p.addEventListener('keydown', (e) => { const d = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0; if (d) { e.preventDefault(); const n = picks[(i + d + picks.length) % picks.length]; selectBlock(n.dataset.b); n.focus(); } });
});
explodeBtn.addEventListener('click', () => setExplode(!exploded));
function setExplode(v) { exploded = v; explodeBtn.setAttribute('aria-pressed', String(v)); explodeBtn.textContent = v ? 'Collapse' : 'Explode'; wake && wake(); }
let wake = null, onSelect = () => {}, onBlock = () => {};
function selectLayer(i) { layer = i; renderCard(); onSelect(i); if (!exploded) setExplode(true); }
function selectBlock(k) { if (k === cur) return; cur = k; picks.forEach((p) => p.setAttribute('aria-checked', String(p.dataset.b === k))); layer = 0; renderCard(); onBlock(k); }
renderCard();

// Hotspot buttons (real buttons, positioned over the 3D layers)
const hotBtns = LNAMES.map((n, i) => { const b = document.createElement('button'); b.type = 'button'; b.className = 'blk-dot'; b.innerHTML = `<span>${i + 1}</span><em>${n}</em>`; b.setAttribute('aria-label', 'Layer ' + (i + 1) + ': ' + n); b.addEventListener('click', () => selectLayer(i)); hot.appendChild(b); return b; });

/* ---------- 3D ---------- */
let renderer;
try {
  if (!(document.createElement('canvas').getContext('webgl2') || document.createElement('canvas').getContext('webgl'))) throw 0;
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, mobile ? 1.75 : 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.ACESFilmicToneMapping;
} catch (e) { renderer = null; }

if (!renderer) { stageEl.classList.add('blk--fallback'); hot.hidden = true; }
else init3d();

function capTex(label, color) {
  const S = 512, c = document.createElement('canvas'); c.width = c.height = S; const g = c.getContext('2d');
  g.beginPath(); g.roundRect(10, 10, S - 20, S - 20, 90); g.fillStyle = color; g.fill();
  const gr = g.createLinearGradient(0, 0, S, S); gr.addColorStop(0, 'rgba(255,255,255,.4)'); gr.addColorStop(.5, 'rgba(255,255,255,0)'); gr.addColorStop(1, 'rgba(0,0,0,.2)'); g.fillStyle = gr; g.fill();
  g.fillStyle = 'rgba(6,7,12,.92)'; g.textAlign = 'center'; g.textBaseline = 'middle';
  const words = label.split(' '); let fs = 120; g.font = `800 ${fs}px ui-sans-serif,system-ui,sans-serif`;
  while (words.some((w) => g.measureText(w).width > S * .8) && fs > 40) { fs -= 4; g.font = `800 ${fs}px ui-sans-serif,system-ui,sans-serif`; }
  words.forEach((w, i) => g.fillText(w, S / 2, S / 2 + (i - (words.length - 1) / 2) * fs * 1.05));
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t;
}

function init3d() {
  stageEl.classList.add('blk--3d');
  const scene = new THREE.Scene();
  const cam = new THREE.PerspectiveCamera(32, 1, .1, 50);
  scene.add(new THREE.AmbientLight(0xffffff, .55));
  const d = new THREE.DirectionalLight(0xffffff, 2); d.position.set(4, 6, 5); scene.add(d);
  const p = new THREE.PointLight(0xa78bfa, 30, 20); p.position.set(-4, -1, 4); scene.add(p);
  const root = new THREE.Group(); scene.add(root);
  const W = 1.8, Hs = 0.42, N = 4;
  const bodyMat = new THREE.MeshStandardMaterial({ color: 0x0d0f16, roughness: .35, metalness: .5 });
  const slabs = [], bands = [];
  const accent = new THREE.Color(BLOCKS[cur].c);
  for (let i = 0; i < N; i++) {
    const g = new THREE.Group();
    g.add(new THREE.Mesh(new THREE.BoxGeometry(W, Hs, W), bodyMat));
    const bm = new THREE.MeshStandardMaterial({ color: accent, emissive: accent, emissiveIntensity: .25, roughness: .3, transparent: true, opacity: .95 });
    const band = new THREE.Mesh(new THREE.BoxGeometry(W * 1.004, Hs * .34, W * 1.004), bm); g.add(band); bands.push(bm);
    const e = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(W, Hs, W)), new THREE.LineBasicMaterial({ color: accent, transparent: true, opacity: .45 })); g.add(e); g.userData.edge = e.material;
    root.add(g); slabs.push(g);
  }
  const capMat = new THREE.MeshStandardMaterial({ map: capTex(BLOCKS[cur].name, BLOCKS[cur].c), emissive: 0xffffff, emissiveIntensity: .2, roughness: .3, alphaTest: .5 });
  capMat.emissiveMap = capMat.map;
  const cap = new THREE.Mesh(new THREE.PlaneGeometry(W * .88, W * .88), capMat); cap.rotation.x = -Math.PI / 2; cap.position.y = Hs / 2 + .003; slabs[N - 1].add(cap);
  // glow sprite
  const gc = document.createElement('canvas'); gc.width = gc.height = 128; const gg = gc.getContext('2d'); const rg = gg.createRadialGradient(64, 64, 0, 64, 64, 64); rg.addColorStop(0, 'rgba(255,255,255,.9)'); rg.addColorStop(1, 'rgba(255,255,255,0)'); gg.fillStyle = rg; gg.fillRect(0, 0, 128, 128);
  const glowM = new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(gc), color: accent, transparent: true, opacity: .35, blending: THREE.AdditiveBlending, depthWrite: false });
  const glow = new THREE.Sprite(glowM); glow.scale.set(7, 7, 1); glow.position.z = -2; scene.add(glow);

  // slab order: index 0 (Problem) on top → visual top; we stack top-down
  const order = (i) => N - 1 - i; // layer i sits at slab order(i)
  let yaw = -0.6, vy = 0, pitch = 0.5, drag = false, lx = 0, ly = 0, ex = 0, sel = 0, swap = 0, swapTo = null, t = 0, last = performance.now(), running = false, visible = false;
  onSelect = (i) => { sel = i; kick(); };
  onBlock = (k) => { if (RM) { applyBlock(k); kick(); return; } swapTo = k; swap = 0.0001; kick(); };
  function applyBlock(k) {
    const col = new THREE.Color(BLOCKS[k].c);
    bands.forEach((m) => { m.color.copy(col); m.emissive.copy(col); }); slabs.forEach((s) => s.userData.edge.color.copy(col));
    glowM.color.copy(col); capMat.map.dispose(); capMat.map = capTex(BLOCKS[k].name, BLOCKS[k].c); capMat.emissiveMap = capMat.map; capMat.needsUpdate = true;
  }
  canvas.addEventListener('pointerdown', (e) => { drag = true; lx = e.clientX; ly = e.clientY; if (e.pointerType === 'mouse') canvas.setPointerCapture(e.pointerId); kick(); });
  canvas.addEventListener('pointermove', (e) => { if (!drag) return; const dx = e.clientX - lx, dy = e.clientY - ly; lx = e.clientX; ly = e.clientY; vy = dx * .012; yaw += vy; if (e.pointerType === 'mouse') pitch = Math.max(.1, Math.min(1.1, pitch + dy * .006)); kick(); });
  const up = () => { drag = false; }; canvas.addEventListener('pointerup', up); canvas.addEventListener('pointercancel', up);
  function resize() { const w = canvas.clientWidth, h = canvas.clientHeight; if (!w || !h) return; renderer.setSize(w, h, false); cam.aspect = w / h; cam.position.set(0, 0, 3.4 / Math.tan(THREE.MathUtils.degToRad(16)) / Math.min(1, cam.aspect)); cam.lookAt(0, 0, 0); cam.updateProjectionMatrix(); kick(); }
  new ResizeObserver(resize).observe(canvas);
  new IntersectionObserver((e) => { visible = e[0].isIntersecting; if (visible) kick(); }, { threshold: 0 }).observe(stageEl);
  function kick() { if (!running && visible) { running = true; last = performance.now(); requestAnimationFrame(frame); } }
  wake = kick;
  const v = new THREE.Vector3(); let idle = 0;
  function frame(now) {
    const dt = Math.min(.05, (now - last) / 1000); last = now; t += dt;
    if (!drag) { vy *= .92; yaw += vy + (RM ? 0 : dt * .18); }
    const exT = exploded ? 1 : 0; ex += (exT - ex) * (RM ? 1 : Math.min(1, dt * 7));
    let sc = 1, spin = 0;
    if (swap > 0) { swap += dt / .7; const k = Math.min(1, swap); if (swapTo && k >= .5) { applyBlock(swapTo); swapTo = null; } sc = 1 - Math.sin(Math.PI * k) * .35; spin = Math.sin(Math.PI * k) * 1.4; if (k >= 1) swap = 0; }
    root.rotation.set(pitch * .6, yaw + spin, 0); root.scale.setScalar(sc);
    root.position.y = RM ? 0 : Math.sin(t * 1.2) * .04;
    for (let i = 0; i < N; i++) {
      const s = slabs[order(i)]; const baseY = (order(i) - (N - 1) / 2) * Hs;
      const isSel = i === sel && exploded;
      s.position.set(isSel ? ex * .35 : 0, baseY + (order(i) - (N - 1) / 2) * ex * .62, 0);
      const target = isSel ? 1.1 : (exploded ? .18 : .3); bands[order(i)].emissiveIntensity += (target - bands[order(i)].emissiveIntensity) * Math.min(1, dt * 8);
    }
    renderer.render(scene, cam);
    // hotspots follow the layers
    const r = canvas.getBoundingClientRect();
    for (let i = 0; i < N; i++) {
      const s = slabs[order(i)]; v.set(W / 2, 0, W / 2); s.localToWorld(v); v.project(cam);
      const x = (v.x * .5 + .5) * r.width, y = (-v.y * .5 + .5) * r.height;
      const b = hotBtns[i]; b.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`; b.classList.toggle('on', i === sel); b.style.opacity = ex > .5 ? 1 : 0; b.tabIndex = ex > .5 ? 0 : -1;
    }
    const busy = drag || swap > 0 || Math.abs(ex - exT) > .002 || Math.abs(vy) > 1e-4;
    idle = busy ? 0 : idle + 1;
    if (visible && (!RM || idle < 20)) requestAnimationFrame(frame); else running = false;
  }
  resize();
  if (!RM) setTimeout(() => setExplode(true), 600); else setExplode(true);
}
