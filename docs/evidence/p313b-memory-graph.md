# P3.13b: Memory Graph as a brain, without the layering

Founder feedback (2026-10-02): the Memory Graph was too layered, needed to be fixed and professional, and should look like a brain.

## What was wrong (measured on the live dashboard, 56 memories)

- The canvas drawing buffer was 300x150 but CSS stretched it to about 329x260: blurry, and click hit-testing used the wrong coordinates.
- 56 nodes were hash-placed into a 252x102 box with radius 20 or more, so they stacked into one pile; every node drew an 11px label on top of the others. See `docs/evidence/adr-029-p3/p313-screens/dashboard-dock-1024.png` (taken before this change).
- Node details were written with `innerHTML` from memory titles and tags (untrusted text).
- A dead "Expand" button, unused zoom/pan, a `Math.random` loader and a grab cursor with no drag.

## What it is now

- `public/js/memory-graph-layout.js` (pure, tested): a deterministic layout inside a side-view brain (four lobes). Layers gather in regions (verified: frontal, org: top, task: back, session: temporal), nodes keep a target spacing, never overlap and never leave the cerebrum.
- `public/js/memory-graph.js`: sizes the canvas to its box times the device pixel ratio, draws the brain (lobes, cerebellum, stem, fold lines), nodes by layer colour, only real links, and one label for the hovered or selected node. Details use `textContent` only. A legend shows the layer counts.
- Links are only real shared tags, and a tag carried by more than a third of the memories draws no link (before: 1378 links, all from generic tags; now 4). The fold lines are decoration and carry no data.

## Evidence

- Screenshots, after: `p313b-memory-graph/graph-after-1024.png`, `graph-after-390.png` (hovering the org memory shows its label).
- Live check at 1024 and 390: 56 nodes, 4 links, 0 overlaps, canvas buffer equals its display size.
- Tests: `tests/memory-graph.test.ts` (12): no overlap and inside the brain at four canvas sizes, determinism and input-order independence, layer placement, tiny/empty/200-node inputs, hostile title shown literally, generic tags draw no link, canvas sized to its box.

## Four-state table

| Item | State |
|---|---|
| Layout never overlaps or leaves the brain | CODE COMPLETE, TEST VERIFIED, LIVE VERIFIED (56 real memories, 2 widths) |
| Details are text-only | CODE COMPLETE, TEST VERIFIED |
| Looks like a brain | LIVE VERIFIED (screenshots); taste is the founder's call |
| Dragging, zooming, filtering by layer | not built (not asked for) |
| Real-device pixel ratio above 1 | UNPROVEN (headless Chrome ran at ratio 1; a test covers the maths) |
