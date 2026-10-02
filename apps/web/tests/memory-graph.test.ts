// The Memory Graph: a layout that never overlaps or leaves the canvas, deterministic, and details that are text-only.
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const pub = join(dirname(fileURLToPath(import.meta.url)), '../public');
const layoutSrc = readFileSync(join(pub, 'js/memory-graph-layout.js'), 'utf8');
const graphSrc = readFileSync(join(pub, 'js/memory-graph.js'), 'utf8');

type N = { id: string; layer: string; radius: number };
const load = () => {
  const ctx: any = { window: {}, globalThis: undefined };
  ctx.globalThis = ctx.window;
  vm.createContext(ctx);
  vm.runInContext(layoutSrc, ctx);
  return ctx.window.MemoryGraphLayout as { layoutGraph(n: N[], e: any[], w: number, h: number): Map<string, { x: number; y: number }>; radiusFor(n: number): number };
};
const make = (count: number, layers = ['task', 'org', 'verified']): N[] =>
  Array.from({ length: count }, (_, i) => ({ id: `mem-${i}-${(i * 7919) % 1000}`, layer: layers[i % layers.length]!, radius: 4 + (i % 5) }));

describe('Memory Graph layout', () => {
  const { layoutGraph, radiusFor } = load();

  it('places 60 nodes in the real 329x260 canvas with no overlaps and every node inside', () => {
    const nodes = make(60);
    const pos = layoutGraph(nodes, [], 329, 260);
    assert.equal(pos.size, 60);
    for (const n of nodes) {
      const p = pos.get(n.id)!;
      assert.ok(Number.isFinite(p.x) && Number.isFinite(p.y));
      assert.ok(p.x - n.radius >= 0 && p.x + n.radius <= 329 && p.y - n.radius >= 0 && p.y + n.radius <= 260, `${n.id} inside`);
    }
    for (let i = 0; i < nodes.length; i += 1) for (let j = i + 1; j < nodes.length; j += 1) {
      const a = pos.get(nodes[i]!.id)!; const b = pos.get(nodes[j]!.id)!;
      assert.ok(Math.hypot(a.x - b.x, a.y - b.y) >= nodes[i]!.radius + nodes[j]!.radius, `${nodes[i]!.id} / ${nodes[j]!.id} overlap`);
    }
  });

  it('keeps every node inside the cerebrum, at several canvas sizes', () => {
    const { brainShape } = (load() as any);
    for (const [w, h, count] of [[329, 260, 56], [382, 260, 56], [240, 180, 20], [600, 400, 120]] as const) {
      const shape = brainShape(w, h);
      const nodes = make(count);
      const pos = layoutGraph(nodes, [], w, h);
      for (const n of nodes) {
        const p = pos.get(n.id)!;
        assert.ok(shape.inside(p.x, p.y, 0), `${w}x${h} ${n.id} is inside the brain`);
      }
    }
  });

  it('puts verified memories in the frontal lobe and org memories above the task mass', () => {
    const nodes = make(30, ['verified', 'org', 'task']);
    const pos = layoutGraph(nodes, [], 329, 260);
    const mean = (layer: string, k: 'x' | 'y') => { const g = nodes.filter((n) => n.layer === layer).map((n) => pos.get(n.id)![k]); return g.reduce((s, v) => s + v, 0) / g.length; };
    assert.ok(mean('verified', 'x') < mean('task', 'x'), 'frontal is in front');
    assert.ok(mean('org', 'y') < mean('task', 'y'), 'org sits higher');
  });

  it('is deterministic and does not depend on input order', () => {
    const nodes = make(30);
    const a = layoutGraph(nodes, [], 320, 240);
    const b = layoutGraph(nodes.slice().reverse(), [], 320, 240);
    for (const n of nodes) assert.deepEqual(a.get(n.id), b.get(n.id));
  });

  it('gathers each layer around its own anchor (cluster centers are apart)', () => {
    const nodes = make(45);
    const pos = layoutGraph(nodes, [], 329, 260);
    const center = (layer: string) => {
      const group = nodes.filter((n) => n.layer === layer).map((n) => pos.get(n.id)!);
      return { x: group.reduce((s, p) => s + p.x, 0) / group.length, y: group.reduce((s, p) => s + p.y, 0) / group.length };
    };
    const [t, o, v] = [center('task'), center('org'), center('verified')];
    for (const [a, b] of [[t, o], [t, v], [o, v]] as const) assert.ok(Math.hypot(a.x - b.x, a.y - b.y) > 25);
  });

  it('pulls tag-linked nodes of one layer closer than unlinked ones', () => {
    const nodes = make(12, ['task']);
    const none = layoutGraph(nodes, [], 329, 260);
    const linked = layoutGraph(nodes, [{ source: nodes[0]!.id, target: nodes[1]!.id, strength: 1 }], 329, 260);
    const d = (m: Map<string, { x: number; y: number }>) => Math.hypot(m.get(nodes[0]!.id)!.x - m.get(nodes[1]!.id)!.x, m.get(nodes[0]!.id)!.y - m.get(nodes[1]!.id)!.y);
    assert.ok(d(linked) <= d(none));
  });

  it('handles nothing, one node, identical ids hashing alike, and a tiny canvas without NaN or a crash', () => {
    assert.equal(layoutGraph([], [], 300, 200).size, 0);
    assert.equal(layoutGraph(make(5), [], 5, 5).size, 0);
    const one = layoutGraph(make(1), [], 300, 200).values().next().value!;
    assert.ok(Number.isFinite(one.x) && Number.isFinite(one.y));
    const many = layoutGraph(make(200), [], 329, 260);
    for (const p of many.values()) assert.ok(Number.isFinite(p.x) && Number.isFinite(p.y));
  });

  it('radius grows with tags but stays between 4 and 8', () => {
    assert.equal(radiusFor(0), 4);
    assert.equal(radiusFor(2), 6);
    assert.equal(radiusFor(99), 8);
  });
});

describe('Memory Graph renderer', () => {
  it('shows details through textContent only, so a hostile title or tag is shown literally', () => {
    class El { children: any[] = []; className = ''; textContent = ''; tag: string; constructor(t: string) { this.tag = t; } append(...c: any[]) { this.children.push(...c); } replaceChildren(...c: any[]) { this.children = c; } }
    const details = new El('div');
    const ctx: any = {
      window: {}, document: { getElementById: (id: string) => (id === 'graph-details' ? details : null), createElement: (t: string) => new El(t), createTextNode: (t: string) => { const e = new El('#text'); e.textContent = t; return e; }, addEventListener: () => {} },
    };
    vm.createContext(ctx);
    const { MemoryGraph } = vm.runInContext(`${graphSrc}\n;({ MemoryGraph })`, ctx) as { MemoryGraph: any };
    const g = new MemoryGraph();
    g.edges = [];
    const hostile = '<img src=x onerror=alert(1)>';
    g.showDetails({ id: 'm', title: hostile, layer: 'org"><script>', tags: [hostile] });
    const walk = (e: any): any[] => [e, ...(e.children ?? []).flatMap(walk)];
    const all = details.children.flatMap(walk);
    assert.ok(all.some((e) => e.textContent === hostile));
    assert.ok(all.every((e) => e.tag !== 'img' && e.tag !== 'script'));
    assert.equal((details as any).innerHTML, undefined);
    const layer = all.find((e) => String(e.className).startsWith('memory-layer'))!;
    assert.equal(layer.className, 'memory-layer orgscript', 'the layer class is stripped to letters');
  });

  it('sizes the canvas to its box, links only on informative shared tags, and draws without throwing', () => {
    const calls: string[] = [];
    const g2d = new Proxy({}, { get: (_t, k) => (k === 'measureText' ? () => ({ width: 40 }) : () => { calls.push(String(k)); }), set: () => true });
    const canvas: any = { width: 0, height: 0, style: {}, addEventListener: () => {}, getBoundingClientRect: () => ({ left: 0, top: 0, width: 329, height: 260 }), getContext: () => g2d };
    const ctx: any = { window: { devicePixelRatio: 2, addEventListener: () => {} }, document: { getElementById: (id: string) => (id === 'memory-graph-canvas' ? canvas : null), addEventListener: () => {} } };
    ctx.window.MemoryGraphLayout = load();
    vm.createContext(ctx);
    const { MemoryGraph } = vm.runInContext(`${graphSrc}\n;({ MemoryGraph })`, ctx) as { MemoryGraph: any };
    const g = new MemoryGraph();
    // 9 memories all carry "common" (generic); only m0 and m1 share "rare".
    g.memories = Array.from({ length: 9 }, (_, i) => ({ id: `m${i}`, title: `Memory ${i}`, layer: i < 2 ? 'org' : 'task', tags: ['common', ...(i < 2 ? ['rare'] : [])] }));
    g.render();
    assert.equal(canvas.width, 658, 'drawing buffer = CSS size x device pixel ratio');
    assert.equal(g.edges.length, 1);
    assert.deepEqual([g.edges[0].source, g.edges[0].target], ['m0', 'm1']);
    assert.ok(calls.includes('quadraticCurveTo') && calls.includes('ellipse'), 'brain and links were drawn');
    g.memories = [];
    g.render();
    assert.equal(g.nodes.length, 0);
  });

  it('has no innerHTML, no console logging and no fake interaction left', () => {
    assert.ok(!/innerHTML|console\.log|Math\.random|onclick=/.test(graphSrc));
  });

  it('the page loads the layout before the renderer and gives the graph a legend', () => {
    const html = readFileSync(join(pub, 'index.html'), 'utf8');
    assert.ok(html.indexOf('memory-graph-layout.js') < html.indexOf('memory-graph.js"'));
    assert.match(html, /id="graph-legend"/);
  });
});
