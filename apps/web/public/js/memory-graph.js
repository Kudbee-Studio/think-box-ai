// kudbEE Memory Graph: the saved memories as clusters (one per layer), linked where they share tags.
// Layout is computed by memory-graph-layout.js; this file only draws and handles hover/click.

const GRAPH_LAYERS = {
  verified: { color: '#10b981', label: 'Verified' },
  org: { color: '#f59e0b', label: 'Org' },
  task: { color: '#38bdf8', label: 'Task' },
  session: { color: '#a78bfa', label: 'Session' },
};
const GRAPH_FALLBACK = { color: '#22d3ee', label: 'Other' };

class MemoryGraph {
  constructor() {
    this.memories = [];
    this.nodes = [];
    this.edges = [];
    this.selected = null;
    this.hovered = null;
    this.width = 0;
    this.height = 0;
    this.canvas = document.getElementById('memory-graph-canvas');
    if (!this.canvas) return;
    this.canvas.addEventListener('click', (e) => this.handleClick(e));
    this.canvas.addEventListener('mousemove', (e) => this.handleMove(e));
    this.canvas.addEventListener('mouseleave', () => { this.hovered = null; this.draw(); });
    window.addEventListener('memory:updated', (e) => {
      this.memories = Array.isArray(e.detail?.memories) ? e.detail.memories : [];
      this.render();
    });
    if (typeof ResizeObserver === 'function') new ResizeObserver(() => this.render()).observe(this.canvas);
  }

  layerOf(layer) { return GRAPH_LAYERS[layer] || GRAPH_FALLBACK; }

  /** Recompute the layout for the canvas's real size, then draw. */
  render() {
    if (!this.canvas) return;
    const box = this.canvas.getBoundingClientRect();
    this.width = Math.max(0, Math.floor(box.width));
    this.height = Math.max(0, Math.floor(box.height));
    const ratio = window.devicePixelRatio || 1;
    this.canvas.width = Math.floor(this.width * ratio);
    this.canvas.height = Math.floor(this.height * ratio);
    const memories = this.memories.map((m) => ({ id: String(m.id), title: String(m.title || 'Untitled'), layer: String(m.layer || 'org'), tags: Array.isArray(m.tags) ? m.tags.map((t) => String(t).trim()).filter(Boolean) : [] }));
    const nodes = memories.map((m) => ({ id: m.id, title: m.title, layer: m.layer, tags: m.tags, radius: window.MemoryGraphLayout.radiusFor(m.tags.length) }));
    // A tag carried by more than a third of the memories says nothing about how two of them relate, so it draws no link.
    const freq = new Map();
    for (const m of memories) for (const t of new Set(m.tags)) freq.set(t, (freq.get(t) || 0) + 1);
    const informative = (t) => freq.get(t) <= Math.max(2, memories.length / 3);
    const edges = [];
    for (let i = 0; i < memories.length; i += 1) {
      for (let j = i + 1; j < memories.length; j += 1) {
        const common = memories[i].tags.filter((t) => informative(t) && memories[j].tags.includes(t)).length;
        if (common > 0) edges.push({ source: memories[i].id, target: memories[j].id, strength: Math.min(common / 3, 1) });
      }
    }
    const pos = window.MemoryGraphLayout.layoutGraph(nodes, edges, this.width, this.height);
    for (const n of nodes) Object.assign(n, pos.get(n.id) || { x: 0, y: 0 });
    this.nodes = nodes;
    this.edges = edges;
    if (this.selected && !nodes.some((n) => n.id === this.selected)) this.selected = null;
    this.renderLegend();
    this.draw();
  }

  draw() {
    const ctx = this.canvas?.getContext('2d');
    if (!ctx) return;
    const ratio = window.devicePixelRatio || 1;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, this.width, this.height);
    if (!this.nodes.length) {
      ctx.fillStyle = '#94a3b8';
      ctx.font = '12px system-ui, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('No memories to show yet', this.width / 2, this.height / 2);
      return;
    }
    const byId = new Map(this.nodes.map((n) => [n.id, n]));
    const focus = this.selected || this.hovered;
    this.drawBrain(ctx);
    for (const e of this.edges) {
      const a = byId.get(e.source); const b = byId.get(e.target);
      const lit = focus && (e.source === focus || e.target === focus);
      ctx.strokeStyle = lit ? 'rgba(248, 250, 252, 0.85)' : 'rgba(186, 230, 253, 0.4)';
      ctx.lineWidth = lit ? 1.8 : 1.2;
      // A link bows away from the straight line, like a synapse; only real shared-tag links are drawn.
      const mx = (a.x + b.x) / 2; const my = (a.y + b.y) / 2;
      const dx = b.x - a.x; const dy = b.y - a.y;
      const len = Math.hypot(dx, dy) || 1;
      ctx.beginPath(); ctx.moveTo(a.x, a.y);
      ctx.quadraticCurveTo(mx - (dy / len) * len * 0.18, my + (dx / len) * len * 0.18, b.x, b.y);
      ctx.stroke();
    }
    for (const n of this.nodes) {
      ctx.globalAlpha = focus && focus !== n.id && !this.edges.some((e) => (e.source === focus && e.target === n.id) || (e.target === focus && e.source === n.id)) ? 0.45 : 1;
      ctx.fillStyle = this.layerOf(n.layer).color;
      ctx.beginPath(); ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2); ctx.fill();
      if (n.id === this.selected || n.id === this.hovered) {
        ctx.globalAlpha = 1;
        ctx.strokeStyle = '#f8fafc'; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(n.x, n.y, n.radius + 3, 0, Math.PI * 2); ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
    const labelled = this.nodes.find((n) => n.id === (this.hovered || this.selected));
    if (labelled) this.drawLabel(ctx, labelled);
  }

  /** The brain silhouette: four lobes, cerebellum and stem, with a few fold lines. The folds are decoration; they carry no data. */
  drawBrain(ctx) {
    const shape = window.MemoryGraphLayout.brainShape(this.width, this.height);
    const ellipse = (e) => { ctx.beginPath(); ctx.ellipse(e.cx, e.cy, e.rx, e.ry, 0, 0, Math.PI * 2); };
    const parts = [...shape.lobes, shape.cerebellum];
    // Outline of the union: stroke every part thick, then fill every part over it.
    ctx.lineWidth = 3;
    ctx.strokeStyle = 'rgba(244, 114, 182, 0.55)';
    ctx.lineJoin = 'round';
    for (const p of parts) { ellipse(p); ctx.stroke(); }
    ctx.beginPath(); ctx.moveTo(shape.stem.x1, shape.stem.y1); ctx.lineTo(shape.stem.x2, shape.stem.y2);
    ctx.lineWidth = Math.max(8, this.width * 0.03); ctx.lineCap = 'round'; ctx.strokeStyle = 'rgba(244, 114, 182, 0.35)'; ctx.stroke();
    ctx.fillStyle = '#0f172a';
    for (const p of parts) { ellipse(p); ctx.fill(); }
    ctx.fillStyle = 'rgba(244, 114, 182, 0.07)';
    for (const p of parts) { ellipse(p); ctx.fill(); }
    // Folds (gyri) and the fissure between the frontal and parietal lobes.
    const w = this.width; const h = this.height;
    ctx.lineWidth = 1; ctx.strokeStyle = 'rgba(244, 114, 182, 0.22)'; ctx.lineCap = 'round';
    const curve = (x1, y1, cx, cy, x2, y2) => { ctx.beginPath(); ctx.moveTo(x1 * w, y1 * h); ctx.quadraticCurveTo(cx * w, cy * h, x2 * w, y2 * h); ctx.stroke(); };
    curve(0.44, 0.16, 0.40, 0.34, 0.47, 0.50);
    curve(0.18, 0.30, 0.28, 0.22, 0.36, 0.28);
    curve(0.62, 0.14, 0.70, 0.24, 0.66, 0.36);
    curve(0.80, 0.30, 0.86, 0.42, 0.80, 0.52);
    curve(0.34, 0.64, 0.50, 0.70, 0.66, 0.62);
    curve(0.72, 0.74, 0.80, 0.70, 0.88, 0.76);
    curve(0.72, 0.80, 0.80, 0.77, 0.88, 0.82);
  }

  /** The only label on the canvas: the hovered or selected node, on a small plate that stays inside the canvas. */
  drawLabel(ctx, node) {
    const text = node.title.length > 44 ? `${node.title.slice(0, 43)}…` : node.title;
    ctx.font = '12px system-ui, sans-serif';
    const w = ctx.measureText(text).width + 14;
    const h = 22;
    const x = Math.min(this.width - w - 4, Math.max(4, node.x - w / 2));
    const y = node.y - node.radius - h - 6 < 4 ? node.y + node.radius + 8 : node.y - node.radius - h - 6;
    ctx.fillStyle = 'rgba(15, 23, 42, 0.95)';
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.5)';
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.roundRect(x, y, w, h, 5); ctx.fill(); ctx.stroke();
    ctx.fillStyle = '#f8fafc';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, x + 7, y + h / 2);
  }

  renderLegend() {
    const legend = document.getElementById('graph-legend');
    if (!legend) return;
    const counts = new Map();
    for (const n of this.nodes) counts.set(n.layer, (counts.get(n.layer) || 0) + 1);
    legend.replaceChildren(...[...counts].map(([layer, count]) => {
      const item = document.createElement('span');
      item.className = 'graph-legend-item';
      const dot = document.createElement('i');
      dot.style.background = this.layerOf(layer).color;
      item.append(dot, document.createTextNode(`${this.layerOf(layer).label} ${count}`));
      return item;
    }));
  }

  nodeAt(e) {
    const rect = this.canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    let best = null; let bestDist = Infinity;
    for (const n of this.nodes) {
      const d = Math.hypot(x - n.x, y - n.y);
      if (d <= n.radius + 4 && d < bestDist) { best = n; bestDist = d; }
    }
    return best;
  }

  handleMove(e) {
    const hit = this.nodeAt(e);
    const id = hit ? hit.id : null;
    this.canvas.style.cursor = hit ? 'pointer' : 'default';
    if (id !== this.hovered) { this.hovered = id; this.draw(); }
  }

  handleClick(e) {
    const hit = this.nodeAt(e);
    this.selected = hit ? hit.id : null;
    this.showDetails(hit);
    this.draw();
  }

  /** Details are built with textContent only: memory titles and tags are untrusted text. */
  showDetails(node) {
    const details = document.getElementById('graph-details');
    if (!details) return;
    if (!node) { const empty = document.createElement('div'); empty.className = 'empty-state'; empty.textContent = 'Click a node to view details'; details.replaceChildren(empty); return; }
    const head = document.createElement('div');
    head.className = 'graph-detail-header';
    const title = document.createElement('h4');
    title.textContent = node.title;
    const layer = document.createElement('span');
    layer.className = `memory-layer ${node.layer.replace(/[^a-z]/g, '')}`;
    layer.textContent = node.layer;
    head.append(title, layer);
    const body = document.createElement('div');
    body.className = 'graph-detail-content';
    const tags = document.createElement('p');
    const strong = document.createElement('strong');
    strong.textContent = 'Tags: ';
    tags.append(strong, document.createTextNode(node.tags.join(', ') || 'None'));
    const linked = document.createElement('p');
    const s2 = document.createElement('strong');
    s2.textContent = 'Linked memories: ';
    linked.append(s2, document.createTextNode(String(this.edges.filter((x) => x.source === node.id || x.target === node.id).length)));
    body.append(tags, linked);
    details.replaceChildren(head, body);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  window.memoryGraph = new MemoryGraph();
});
