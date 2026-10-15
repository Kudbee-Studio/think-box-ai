# P3.90 Starfall v0.3 in the dashboard: formations, three bosses, the bomb, perfect waves, difficulties, sectors

The dashboard's `/game/` copy is refreshed from the standalone project (`~/projects/starfall`, commit 7687135, v0.3) after #429 brought it to v0.2. "Lets make it better" came without play-test feedback, so these were chosen from what the measurements and the v0.2 "not built" list pointed to:
- **Formations:** from wave 2, runs of three to five small enemies arrive as a line, a V, a column or a pincer.
- **Bosses:** three kinds in turn (a gunship that fires fans, a spiral boss that sprays a turning pattern, a summoner that calls in swoopers); each is enraged at half health (faster, announced); the next of each kind is tougher.
- **Bomb:** B clears every enemy shot and hurts everything on screen (a boss loses a chunk but is never killed by it); you start with one, hold up to three, and one drops rarely.
- **Perfect wave:** a bonus of 100 times the wave number for a wave in which you were not hit and shot down at least half of it.
- **Easy / Normal / Hard:** lives, enemy speed and shot speed, boss strength, drop rate; each difficulty keeps its own high-score table (v0.2's table is read as Normal).
- **Sectors:** the background changes every five waves.

## Two problems found on the way
- **A bonus for doing nothing:** the first "perfect wave" paid for simply not being hit, so a bot that never touched anything scored 95 points. It now needs half the wave shot down; that bot scores 0.
- **A frozen screen waiting to happen:** the real browser showed a page error ("undefined is not iterable"): a bomb power-up had no drawing entry, so the drawing code would have thrown, stopping the animation loop and freezing the game, the first time one dropped. The unit tests did not draw anything. Added `tests/render.test.js`, which draws every enemy, boss kind, power-up, screen, sector and a 90-second random game through a fake canvas; with the bug put back, two of its tests fail with the same error.

| Claim | State | Basis |
|---|---|---|
| Formations (deterministic plans, in bounds, the members of a formation arrive together, none in wave 1, all four kinds occur), the three bosses and what each fires, enrage announced once and firing faster, the boss-down event names the kind, the bomb (all its rules), perfect waves, difficulty, sectors | PROVEN | standalone project: 74 tests, all pass |
| The drawing code runs on every kind of thing and every screen | PROVEN | `tests/render.test.js` (fake canvas; the bug-reintroduced check failed as expected) |
| The served copy is v0.3 and byte-identical to the project; no inline script; the difficulty buttons and the bomb button are on the page | PROVEN | tests/game-served.test.ts |
| In Chromium through the dashboard (CSP applies): keyboard play, a power-up, a boss with a free shield, the B key (one fewer bomb, shots cleared, white flash, a second of safety), the spiral boss spraying in 8 directions, a five-enemy line formation arriving together, a mouse used like a finger, the sound button, game over with initials, Hard selected (2 lives, its own empty table), early Enter refused, restart, no page errors | PROVEN | 4 of 4 runs through the dashboard; also passed standalone |
| Bots (20 runs each, Normal): never touching 37 s and 0 points; only firing 60 s; aiming without dodging 60 s (wave 5.7); also dodging 124 s (wave 9, dies between waves 5 and 15) | MEASURED, simulation | bots aim perfectly and dodge badly; not a human measure |
| Easy / Normal / Hard really differ | PARTLY | the passive bot survives 72 s, 60 s, 50 s; the dodging bot barely tells them apart (127, 124, 119 s) because it dies mostly at bosses whatever the lives |
| Sound for the new events; formations and boss patterns feel fair; fun | UNPROVEN | no person has played v0.3 |
| Phones: the drag control and the bomb button | UNPROVEN | a mouse in Chromium only |
| More bosses and patterns, a second weapon, music, an online table | NOT BUILT | |
| The copy stays in step with the project | NOT CLAIMED | manual copy |
