/* thinkTokens: shared cube model (used by cube.js and the offline render page).
   54 labeled stickers. Each sticker names a real concept in that part of Think Box,
   with the problem it addresses and how the repo resolves it (PR / ADR refs where known). */

export const FACE_DEFS = {
  dashboard: { n: [0, 1, 0], e: [Math.PI / 2, 0, 0], c: '#38bdf8', center: 'UI', name: 'Dashboard', step: 1 },
  runtime:   { n: [0, 0, 1], e: [0, 0, 0], c: '#a78bfa', center: 'RUN', name: 'Agent runtime', step: 2 },
  tools:     { n: [1, 0, 0], e: [0, -Math.PI / 2, 0], c: '#fb923c', center: 'TOOLS', name: 'Tools & plugins', step: 3 },
  models:    { n: [-1, 0, 0], e: [0, Math.PI / 2, 0], c: '#34d399', center: 'MODELS', name: 'Local models', step: 4 },
  memory:    { n: [0, -1, 0], e: [-Math.PI / 2, 0, 0], c: '#facc15', center: 'MEMORY', name: 'Memory', step: 5 },
  security:  { n: [0, 0, -1], e: [0, Math.PI, 0], c: '#f43f5e', center: 'SECURITY', name: 'Security & approvals', step: 6 }
};

// [label, problem, resolution, ref, planned?]
export const CONCEPTS = {
  dashboard: {
    center: ['UI', 'Operators need one place to watch and steer agents.', 'A local dashboard (Express + WebSocket in apps/web).', 'ADR 027'],
    items: [
      ['Loopback', 'A dashboard on 0.0.0.0 is reachable from the network.', 'It binds to 127.0.0.1 only.', 'ADR 027'],
      ['Live WS', 'You cannot see what agents are doing right now.', 'Status streams over a local WebSocket.', 'apps/web'],
      ['Login', 'Today there is one implicit user and no sign-in.', 'Dashboard login + per-user identity is planned for E0.', 'ADR 027 · E0', true],
      ['Demo labels', 'Panels that look complete can be client-side demos.', 'Demo data is labeled honestly.', 'PR #292'],
      ['CLI', 'Not every operator wants a browser.', 'KUDBEECLI inspects swarm, ledger and env from a terminal.', 'PRs #178, #180'],
      ['HTTPS', 'Exposing the dashboard needs TLS.', 'A TLS deployment is planned for E6.', 'ADR 027 · E6', true],
      ['Escape HTML', 'Untrusted text in the UI can inject markup.', 'escapeHtml quote-injection fix.', 'PR #296'],
      ['Approve', 'Risky actions need a human decision.', 'You approve or deny from the dashboard.', 'PR #269']
    ]
  },
  runtime: {
    center: ['RUN', 'Goals have to become safe, checkable steps.', 'The runtime plans, schedules and asks governance first.', 'README'],
    items: [
      ['Decompose', 'A big goal is risky to run in one step.', 'The decomposer splits it into tasks.', 'README · L4'],
      ['Scheduler', 'Tasks compete for workers.', 'The scheduler orders and dispatches them.', 'README · L4'],
      ['Draft mode', 'Agents could act before anything is checked.', 'Draft/simulate is the default until a valid governance token exists.', 'README'],
      ['Swarm', 'Some goals need many agents at once.', 'Swarm runtime coordinates agents, and proofs are labeled in the chronicle.', 'PR #263'],
      ['Run track', 'You cannot audit what you cannot see.', 'Runs are tracked end to end.', 'PR #269'],
      ['Evidence', '"It works" claims drift from reality.', 'Every claim carries an evidence label.', 'README'],
      ['Honest fail', 'Model failures can be hidden as successes.', 'Failures are reported honestly.', 'PR #252'],
      ['Chaos test', 'Silent successes hide bugs.', 'A fault-injection chaos harness allows no silent successes.', 'PR #268']
    ]
  },
  tools: {
    center: ['TOOLS', 'Agents need tools, and tools have side effects.', 'Every tool call is a governed request.', 'AGENTS.md §1.4'],
    items: [
      ['Perm level', 'A new tool could ship with no permission set.', 'Tools without a level default to RESTRICTED.', 'AGENTS.md §1.4'],
      ['Approval', 'Some side effects cannot be undone.', 'An approval gate runs before side effects.', 'PR #269'],
      ['MCP', 'Finding the right tool is slow.', 'Interactive MCP plugin discovery.', 'PR #275'],
      ['Algorand RO', 'A chain tool could move funds.', 'A read-only lane with no signing keys.', 'PR #272'],
      ['FS confine', 'A tool could read files outside the project.', 'File tools are workspace-confined.', 'PR #290'],
      ['Allow-list', 'Remote worker commands could do anything.', 'Allow-listed read-only commands over governed SSH.', 'PRs #282, #284'],
      ['UPM deps', 'Workers need dependencies installed.', 'Optional UPM dependency installation, local only.', 'PR #294'],
      ['Specialists', 'One generic agent for every job.', 'Specialists run contract-selected jobs.', 'PR #303']
    ]
  },
  models: {
    center: ['MODELS', 'Every request does not need a big remote model.', 'Route small work to a small local model.', 'PR #271'],
    items: [
      ['qwen 1.5B', 'Small tasks do not need a large remote model.', 'Cheap route: qwen2.5:1.5b on Ollama.', 'PR #271'],
      ['Fallback', 'The local route may be unavailable.', 'A Mercury 2 fallback route (remote provider).', 'PR #269'],
      ['Telemetry', 'Token spend is invisible.', 'Token telemetry per route.', 'PR #271'],
      ['Router', 'Sending everything to one model wastes money.', 'A router picks the route.', 'PR #260'],
      ['Ollama', 'Running models locally is fiddly.', 'Ollama serves local models on loopback.', 'core/providers'],
      ['No SDKs', 'Provider SDKs lock you in.', 'No provider SDKs in runtime code. Providers swap by config.', 'CLAUDE.md'],
      ['Mock model', 'Tests that call live models are flaky.', 'A hermetic mock provider.', 'PR #297'],
      ['Cost route', 'Costs grow with usage.', 'Multi-model routing with cost optimization.', 'PR #260']
    ]
  },
  memory: {
    center: ['MEMORY', 'Agents forget, and a database server is overhead.', 'Layered memory in one local SQLite file.', 'ADR 026'],
    items: [
      ['SQLite', 'A database server is one more thing to run.', 'One SQLite file, zero config.', 'ADR 026'],
      ['FTS5', 'Memory has to be searchable.', 'SQLite FTS5 full-text search.', 'ADR 026'],
      ['Backups', 'Complicated backups get skipped.', 'A single file is easy to back up.', 'ADR 026'],
      ['Learning', 'Agents forget between sessions.', 'Persistent cross-session learning.', 'PR #288'],
      ['No Neon', 'An unused cloud DB adds cost and attack surface.', 'The Neon setup was reverted.', 'ADR 026 · PR #301'],
      ['Reopen', '"When scale demands it" is too vague.', 'Measurable Postgres reopen criteria.', 'ADR 027'],
      ['Think Tokens', 'Learned patterns are not saved yet.', 'A think_tokens table is planned on SQLite.', 'ADR 028', true],
      ['Layers', 'One memory for everything mixes concerns.', 'Session, task, organizational and verified-knowledge layers.', 'README · L2']
    ]
  },
  security: {
    center: ['SECURITY', 'An agent on your machine is a target.', 'Default deny, human approval, append-only audit.', 'ADR 027'],
    items: [
      ['Origin check', 'A malicious site opens a WebSocket to your agent.', 'Host/Origin gating rejects it.', 'PR #290'],
      ['Approval gate', 'A risky action runs unattended.', 'It waits for a human at the approval gate.', 'PR #269'],
      ['shell_exec off', 'A prompt-injected plan asks for a shell.', 'shell_exec is disabled by default.', 'PR #290'],
      ['Workspace jail', 'A ../../ path escapes the project.', 'File ops stay inside the workspace.', 'PR #290'],
      ['Ledger', 'Logs can be edited after the fact.', 'An append-only action ledger.', 'README'],
      ['Receipts', 'Results come with no proof.', 'Durable action receipts + an integrity endpoint.', 'PR #251'],
      ['Token gate', 'Governed runs start without authority.', 'Tokenless governed runs are denied.', 'PR #252'],
      ['Secret scan', 'Secrets leak into docs.', 'A doc secret scan runs on every meaningful change.', 'README']
    ]
  }
};

function fitLines(g, text, maxW, maxLines, size, weight) {
  const font = (px) => `${weight} ${px}px ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif`;
  let s = size; let lines = [text];
  for (let pass = 0; pass < 3; pass++) {
    g.font = font(s);
    const words = text.split(' '); lines = []; let cur = '';
    for (const w of words) { const t = cur ? cur + ' ' + w : w; if (!cur || g.measureText(t).width <= maxW) cur = t; else if (lines.length < maxLines - 1) { lines.push(cur); cur = w; } else cur = t; }
    if (cur) lines.push(cur);
    const widest = Math.max(...lines.map((l) => g.measureText(l).width));
    if (widest <= maxW) break;
    s = Math.max(Math.floor(size * 0.4), Math.floor(s * maxW / widest));
  }
  g.font = font(s); return { lines, s };
}

/* Draw one sticker into a 2D context at (ox, oy), size TEX. */
export function drawSticker(g, ox, oy, TEX, fill, label, isCenter) {
  g.save(); g.translate(ox, oy);
  const r = TEX * 0.18, p = TEX * 0.02;
  g.beginPath(); g.roundRect(p, p, TEX - 2 * p, TEX - 2 * p, r); g.fillStyle = fill; g.fill();
  const grd = g.createLinearGradient(0, 0, TEX, TEX); grd.addColorStop(0, 'rgba(255,255,255,.38)'); grd.addColorStop(.5, 'rgba(255,255,255,0)'); grd.addColorStop(1, 'rgba(0,0,0,.2)');
  g.fillStyle = grd; g.fill();
  if (label) {
    g.fillStyle = 'rgba(6,7,12,.92)'; g.textAlign = 'center'; g.textBaseline = 'middle';
    const { lines, s } = fitLines(g, label, TEX * 0.8, 2, Math.round(TEX * (isCenter ? 0.24 : 0.2)), isCenter ? 800 : 700);
    const lh = s * 1.08, y0 = TEX / 2 - (lines.length - 1) * lh / 2 + TEX * 0.01;
    lines.forEach((l, i) => g.fillText(l, TEX / 2, y0 + i * lh));
    if (isCenter) { g.fillStyle = 'rgba(6,7,12,.55)'; g.fillRect(TEX * 0.38, TEX * 0.84, TEX * 0.24, TEX * 0.025); }
  }
  g.restore();
}

export function stickerCanvas(fill, label, isCenter, TEX) {
  const c = document.createElement('canvas'); c.width = c.height = TEX;
  drawSticker(c.getContext('2d'), 0, 0, TEX, fill, label, isCenter); return c;
}

/* Build the 3x3x3 cube. Returns everything callers need to animate and pick. */
export function createCube(THREE, opts = {}) {
  const TEX = opts.tex || 256;
  const FACES = {};
  for (const k of Object.keys(FACE_DEFS)) {
    const d = FACE_DEFS[k];
    const qAlign = new THREE.Quaternion().setFromEuler(new THREE.Euler(...d.e));
    FACES[k] = { ...d, key: k, n: new THREE.Vector3(...d.n), qAlign, qSticker: qAlign.clone().invert() };
  }
  const FACE_KEYS = Object.keys(FACES);
  const cube = new THREE.Group();
  const bodyGeo = new THREE.BoxGeometry(0.97, 0.97, 0.97);
  const bodyMat = new THREE.MeshStandardMaterial({ color: 0x0c0e14, roughness: 0.38, metalness: 0.45 });
  // One texture atlas for all 54 stickers (one upload instead of 54), one material per face.
  const COLS = 8, ROWS = 7;
  const atlas = document.createElement('canvas'); atlas.width = COLS * TEX; atlas.height = ROWS * TEX;
  const ag = atlas.getContext('2d');
  const atlasTex = new THREE.CanvasTexture(atlas); atlasTex.colorSpace = THREE.SRGBColorSpace; atlasTex.anisotropy = opts.anisotropy || 4;
  const matsByFace = {};
  FACE_KEYS.forEach((k) => (matsByFace[k] = [new THREE.MeshStandardMaterial({ color: 0xffffff, map: atlasTex, emissive: 0xffffff, emissiveMap: atlasTex, emissiveIntensity: 0.22, roughness: 0.3, metalness: 0.05, alphaTest: 0.5 })]));
  const counters = {}; FACE_KEYS.forEach((k) => (counters[k] = 0));
  const cubies = [], pickables = [], stickers = [];
  let cell = 0;
  for (let x = -1; x <= 1; x++) for (let y = -1; y <= 1; y++) for (let z = -1; z <= 1; z++) {
    const g = new THREE.Group();
    g.userData.pos = new THREE.Vector3(x, y, z);       // logical position (integers)
    g.userData.rot = new THREE.Quaternion();           // logical orientation
    g.add(new THREE.Mesh(bodyGeo, bodyMat));
    for (const k of FACE_KEYS) {
      const n = FACES[k].n;
      if ((n.x && n.x === x) || (n.y && n.y === y) || (n.z && n.z === z)) {
        const isCenter = n.x ? (y === 0 && z === 0) : n.y ? (x === 0 && z === 0) : (x === 0 && y === 0);
        const concept = isCenter ? CONCEPTS[k].center : CONCEPTS[k].items[counters[k]++];
        const col = cell % COLS, row = Math.floor(cell / COLS); cell++;
        drawSticker(ag, col * TEX, row * TEX, TEX, FACES[k].c, concept[0], isCenter);
        const geo = new THREE.PlaneGeometry(0.86, 0.86); const uv = geo.attributes.uv;
        for (let i = 0; i < uv.count; i++) uv.setXY(i, (col + uv.getX(i)) / COLS, 1 - (row + 1) / ROWS + uv.getY(i) / ROWS);
        const m = new THREE.Mesh(geo, matsByFace[k][0]);
        m.quaternion.copy(FACES[k].qSticker);
        m.position.copy(n).multiplyScalar(0.487);
        m.userData = { face: k, normal: n.clone(), concept, isCenter, cubie: g };
        pickables.push(m); stickers.push(m); g.add(m);
      }
    }
    cube.add(g); cubies.push(g);
  }
  atlasTex.needsUpdate = true;
  return { cube, cubies, pickables, stickers, FACES, FACE_KEYS, matsByFace, SP: 1.02 };
}

export const AXES = ['x', 'y', 'z'];
