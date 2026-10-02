# P3.13: the 100-cell Think Token cube

Decision (founder, 2026-10-02, now Accepted in ADR 029): the 100-cell token is canonical; the 54-sticker Rubik's cube is a view only.

## What was built

- `apps/web/think-token-cube.ts` (pure): 100 named cells in 10 rows of 10 (identity, lesson, provenance, challenge, score, usage, links, lifecycle, health, propagation). Every cell has a source (a column, a ledger count, a link or a score component) and a one-line doc. A cell with no data is `empty`, never filled. A module-load assertion enforces exactly 100 definitions. `projectTo54` is the view: cell i is sticker i for i < 54, cells 54-99 fold onto stickers 0-45.
- Reconfigure on learning (schema v6): `think_token_cells` (last snapshot) and `think_token_cell_events` (cause, cell, before, after, ledger seq). Created, every lifecycle transition, operator action, feedback, use, outcome, propagation, link and merge diff the cells and record only the changed ones, plus one `cells` ledger receipt. Tokens that predate the cube get a silent baseline snapshot when the database is opened (no events, no receipt).
- Dashboard: each token card has a 100-cell cube button: the 10x10 grid, a hover/focus/tap inspector (field, value, source, meaning), the 54-sticker CSS-3D cube, and an SVG map of the token's links (line width = weight). Changed cells are outlined and pulse; `prefers-reduced-motion` removes the animation and lays the six faces out flat.
- Main dashboard dock (added after the founder asked why the cube was not on the Agent OS dashboard): a **Think Token Cube** panel sits directly below the Memory Graph (the Memory Graph stays). It loads the saved tokens by itself, shows the best accepted token, follows the token that was just used or learned from, and has a selector (a viewer's pick sticks). It uses the same cube renderer as the token cards. Screenshots: [dashboard-dock-1024.png](p313-screens/dashboard-dock-1024.png), [dashboard-dock-390.png](p313-screens/dashboard-dock-390.png).
- CLI: `kudbee token cube <TT-id> [--events] [--json]` (ASCII grid, `*` marks cells changed by the last update). Parity map entry added.

## Live proof (real database, real Mercury, $0.00297 for the one run; cap $0.10)

Before the migration the database was copied with `VACUUM INTO` to `apps/web/data/think-tokens.db.bak-pre-p313-20261002` (gitignored). The server then migrated it to v6 on start.

1. `kudbee token cube TT-000007 --events` before: [p313-cube-before.txt](p313-cube-before.txt): 94 of 100 cells have data, no cell changes recorded.
2. `kudbee "WHAT PR ARE WE WORKING ON? Use fresh tool output, not remembered notes."`: [p313-goal-run.txt](p313-goal-run.txt): retrieved and used TT-000007, TT-000012, TT-000006. The run could not read GitHub (network approval denied in a non-interactive shell) and said so; the run still counts as a use and an outcome for the token.
3. After: [p313-cube-after.txt](p313-cube-after.txt): changed by `used` (uses, distinct runs, 7-day uses, ledger uses), `linked:co_used` (link counts) and `outcome:win` (win rate 0.889 -> 0.900, successes 8 -> 9, score 0.917 -> 0.923, usefulness 0.818 -> 0.833).
4. Dashboard at 1024 and 390 px: [p313-screens/cube-1024.png](p313-screens/cube-1024.png), [cube-390.png](p313-screens/cube-390.png) (grid with changed cells outlined and the hover inspector), [cube-view-1024.png](p313-screens/cube-view-1024.png), [cube-view-390.png](p313-screens/cube-view-390.png) (the 3D cube and the link lines). [p313-dashboard-check.json](p313-dashboard-check.json): 100 cells, 54 stickers, the same 7 changed cells as the CLI, 4 link lines, no horizontal overflow at either width.

### What the live run found

The first live attempt showed "Loading the 100 cells..." forever: `app.js` did not forward the `think_token_cube` message to the Think Tokens view. The fake-DOM unit tests could not see that. Fixed, and a test now asserts that `app.js` routes every message type the view handles. The first CLI attempt also blamed a token's whole first snapshot on whichever hook ran first (`linked:co_used`); that led to the silent baseline above. The proof was redone from the pre-migration backup.

## Four-state table

| Item | State |
|---|---|
| 100 cells, honest empties, documented sources | CODE COMPLETE, TEST VERIFIED, LIVE VERIFIED (94/100 filled on TT-000007; the 6 empty cells have no data) |
| Stable pure mapping; changes only where the data changed; 100 -> 54 projection | CODE COMPLETE, TEST VERIFIED |
| cell_events + ledger receipts on use, outcome, link | CODE COMPLETE, TEST VERIFIED, LIVE VERIFIED (receipts #132, #148, #152) |
| cell_events on merge, challenge, scoring, feedback, operator, propagation | CODE COMPLETE, TEST VERIFIED; not observed live in this run |
| Dashboard dock below the Memory Graph and the same view on token cards, at 1024 and 390 | CODE COMPLETE, TEST VERIFIED, LIVE VERIFIED (screenshots) |
| Reduced-motion behavior | CODE COMPLETE, TEST VERIFIED (the CSS rules are asserted); UNPROVEN in a browser with the setting on |
| Changed cells pulse (animation) | CODE COMPLETE; a still screenshot shows the outline, not the pulse; UNPROVEN as motion |
| CLI `kudbee token cube` | CODE COMPLETE, TEST VERIFIED, LIVE VERIFIED |
| Cube helps learning | UNPROVEN: it is a view of the token; no claim is made |
| PRODUCTION READY | no |
