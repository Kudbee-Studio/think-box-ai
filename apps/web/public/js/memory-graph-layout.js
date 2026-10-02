// Pure layout for the Memory Graph (no DOM). The graph is drawn as a brain: nodes are kept inside a side-view cerebrum
// (four lobes), each memory layer gathers in its own region, and no two nodes overlap. Deterministic: the same input
// gives the same picture (the only "randomness" is a hash of the node id).

(function (root) {
  const LAYER_ORDER = ['verified', 'org', 'task', 'session'];
  const MIN_GAP = 3;

  // Normalised (0..1) lobes of the cerebrum, side view, front on the left; and the layer region each layer gathers in.
  const LOBES = [
    { name: 'frontal', cx: 0.30, cy: 0.42, rx: 0.26, ry: 0.30 },
    { name: 'parietal', cx: 0.52, cy: 0.32, rx: 0.30, ry: 0.26 },
    { name: 'occipital', cx: 0.76, cy: 0.44, rx: 0.20, ry: 0.26 },
    { name: 'temporal', cx: 0.50, cy: 0.58, rx: 0.30, ry: 0.17 },
  ];
  const REGION = { verified: [0.24, 0.42], org: [0.50, 0.26], task: [0.64, 0.50], session: [0.42, 0.62] };
  const CEREBELLUM = { cx: 0.80, cy: 0.77, rx: 0.13, ry: 0.09 };
  const STEM = { x1: 0.56, y1: 0.70, x2: 0.60, y2: 0.95 };

  function hash(text) {
    let h = 2166136261;
    for (let i = 0; i < text.length; i += 1) h = Math.imul(h ^ text.charCodeAt(i), 16777619) >>> 0;
    return h;
  }

  /** Node radius from the number of tags: 4..8 px. */
  function radiusFor(tagCount) {
    return 4 + Math.min(4, Math.max(0, tagCount));
  }

  /** The brain in canvas pixels, with a test for "is a disc of this radius fully inside the cerebrum". */
  function brainShape(width, height) {
    const lobes = LOBES.map((l) => ({ name: l.name, cx: l.cx * width, cy: l.cy * height, rx: l.rx * width, ry: l.ry * height }));
    const inside = (x, y, margin) => lobes.some((l) => {
      const rx = l.rx - margin; const ry = l.ry - margin;
      return rx > 0 && ry > 0 && ((x - l.cx) / rx) ** 2 + ((y - l.cy) / ry) ** 2 <= 1;
    });
    const regions = {};
    for (const k of Object.keys(REGION)) regions[k] = [REGION[k][0] * width, REGION[k][1] * height];
    return {
      lobes,
      inside,
      regions,
      cerebellum: { cx: CEREBELLUM.cx * width, cy: CEREBELLUM.cy * height, rx: CEREBELLUM.rx * width, ry: CEREBELLUM.ry * height },
      stem: { x1: STEM.x1 * width, y1: STEM.y1 * height, x2: STEM.x2 * width, y2: STEM.y2 * height },
      center: [0.52 * width, 0.42 * height],
    };
  }

  /**
   * nodes: [{id, layer, radius}], edges: [{source, target, strength}]. Returns Map id -> {x, y}, every node inside the brain.
   */
  function layoutGraph(nodes, edges, width, height) {
    const pos = new Map();
    if (!nodes.length || width < 60 || height < 50) return pos;
    const shape = brainShape(width, height);
    const regionOf = (layer) => shape.regions[layer] || shape.regions.task;
    // Target spacing so the nodes fill the brain instead of clumping: about a third of the cerebrum's area shared out per node.
    const area = shape.lobes.reduce((s, l) => s + Math.PI * l.rx * l.ry, 0) * 0.6;
    const spacing = Math.max(8, Math.sqrt((0.55 * area) / nodes.length));

    const keepInside = (n, p) => {
      const m = n.radius + 2;
      for (let i = 0; i < 600 && !shape.inside(p.x, p.y, m); i += 1) {
        const dx = shape.center[0] - p.x; const dy = shape.center[1] - p.y;
        const d = Math.hypot(dx, dy) || 1;
        p.x += (dx / d) * 1.5; p.y += (dy / d) * 1.5;
      }
    };

    const byLayer = new Map();
    for (const n of nodes) (byLayer.get(n.layer) || byLayer.set(n.layer, []).get(n.layer)).push(n);
    for (const [layer, group] of byLayer) {
      group.sort((a, b) => hash(a.id) - hash(b.id) || (a.id < b.id ? -1 : 1));
      const [ax, ay] = regionOf(layer);
      group.forEach((n, i) => {
        const a = i * 2.399963;
        const r = 7 * Math.sqrt(i + 0.5);
        const p = { x: ax + Math.cos(a) * r, y: ay + Math.sin(a) * r };
        keepInside(n, p);
        pos.set(n.id, p);
      });
    }
    const list = nodes.slice().sort((a, b) => (a.id < b.id ? -1 : 1));
    for (let step = 0; step < 240; step += 1) {
      const cool = 1 - step / 240;
      for (let i = 0; i < list.length; i += 1) {
        for (let j = i + 1; j < list.length; j += 1) {
          const a = list[i]; const b = list[j];
          const pa = pos.get(a.id); const pb = pos.get(b.id);
          let dx = pb.x - pa.x; let dy = pb.y - pa.y;
          let d = Math.hypot(dx, dy);
          if (d < 0.01) { dx = (hash(a.id) % 7) - 3 || 1; dy = (hash(b.id) % 7) - 3 || 1; d = Math.hypot(dx, dy); }
          const want = Math.max(a.radius + b.radius + MIN_GAP, a.layer === b.layer ? spacing * 1.2 : spacing * 1.35);
          if (d < want) {
            const push = ((want - d) / 2) * 0.6;
            pa.x -= (dx / d) * push; pa.y -= (dy / d) * push;
            pb.x += (dx / d) * push; pb.y += (dy / d) * push;
          }
        }
      }
      for (const e of edges) {
        const pa = pos.get(e.source); const pb = pos.get(e.target);
        if (!pa || !pb) continue;
        const k = 0.015 * Math.min(1, e.strength || 0.3) * cool;
        pa.x += (pb.x - pa.x) * k; pa.y += (pb.y - pa.y) * k;
        pb.x += (pa.x - pb.x) * k; pb.y += (pa.y - pb.y) * k;
      }
      for (const n of list) {
        const p = pos.get(n.id);
        const [ax, ay] = regionOf(n.layer);
        p.x += (ax - p.x) * 0.012 * cool; p.y += (ay - p.y) * 0.012 * cool;
        keepInside(n, p);
      }
    }
    // Final guarantee: strict passes that only separate overlapping pairs, each followed by a pull back inside the brain.
    for (let pass = 0; pass < 60; pass += 1) {
      let moved = false;
      for (let i = 0; i < list.length; i += 1) {
        for (let j = i + 1; j < list.length; j += 1) {
          const a = list[i]; const b = list[j];
          const pa = pos.get(a.id); const pb = pos.get(b.id);
          const dx = pb.x - pa.x || 0.01; const dy = pb.y - pa.y || 0.01;
          const d = Math.hypot(dx, dy);
          const want = a.radius + b.radius + 1;
          if (d < want) {
            const push = (want - d) / 2 + 0.1;
            pa.x -= (dx / d) * push; pa.y -= (dy / d) * push;
            pb.x += (dx / d) * push; pb.y += (dy / d) * push;
            moved = true;
          }
        }
      }
      for (const n of list) keepInside(n, pos.get(n.id));
      if (!moved) break;
    }
    return pos;
  }

  const api = { layoutGraph, radiusFor, brainShape, LAYER_ORDER };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.MemoryGraphLayout = api;
})(typeof window !== 'undefined' ? window : globalThis);
