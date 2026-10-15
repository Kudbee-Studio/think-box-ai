# P3.89 Starfall v0.2 in the dashboard: waves, enemy variety, bosses, power-ups, combos, sound, touch, high scores

The dashboard's `/game/` copy is refreshed from the standalone project (`~/projects/starfall`, commit a2c965c plus two browser-check-only commits, v0.2). v0.1 was one enemy that only drifted. Now:
- **Enemies:** five kinds (drifter, zigzag, tank, shooter that fires aimed shots, swooper that homes in), introduced one by one over the first waves; every fifth wave is a boss with escorts (36 hp for the first, 14 more each time) that fires fans of shots and arrives with a free shield falling from the top.
- **Power-ups:** rapid fire, three-way spread, a shield that absorbs one hit, an extra life (max five).
- **Scoring:** kill combos up to a x4 multiplier; a top-ten high-score table with initials, kept in the browser, read back with every entry checked.
- **Feel:** sound (tones made in the browser, nothing before the first key press, a mute button and the M key), screen shake, floating scores, wave banners, a damage flash.
- **Controls and engine:** touch (drag a finger and the ship follows and fires); the game advances in fixed 1/120 s steps so a run plays the same at any frame rate.

## Why: measured before changing anything
Simple bots, 20 seeded runs each. v0.1: never moving and just firing survived 162 s; a bot that dodged enemies never died (level 50 after 5 minutes). The difficulty did not exist.

| Bot | v0.1 | v0.2 |
|---|---|---|
| never touches anything | 28 s | 41 s (enemies that leave unshot are not punished) |
| only holds fire, never moves | 162 s | 68 s (dies around wave 4) |
| aims at the lowest enemy, no dodging | 79 s | 66 s (wave 5) |
| also dodges enemies and enemy shots | never died | 125 s on average, dies between waves 5 and 13 |

The first boss was killing about half of the dodging bot's runs at first; it was softened (36 hp instead of 44, plus the free shield) and the bot now beats it about two times in three (33 of 49 meetings).

| Claim | State | Basis |
|---|---|---|
| Rules: enemy types and behaviours, wave order and sizes, boss waves and boss strength, power-ups and timers, shield, combos and the cap, scoring, lives, game over with stats, high-score list and initials cleaning, touch following, determinism and frame-rate independence, lists that cannot grow without limit | PROVEN | standalone project: 47 tests, all pass |
| Sound (one tone per event, silent before the first key, mute, thinned bursts, no-op without audio) | PROVEN against a fake audio device | `tests/modules.test.js` |
| The served copy is v0.2, every file it names exists, no inline script, the sound button and the initials box are present | PROVEN | tests/game-served.test.ts |
| In Chromium through the dashboard (its CSP applies): play with the keyboard steering at enemies and killing some, a power-up collected, a boss with its free shield, a mouse used like a finger flying the ship and shooting, the sound button, game over asking for initials, typing "abc!" saved as ABC, an early Enter refused, a restart, no console errors | PROVEN | 5 of 5 runs. Earlier runs failed because of flaws in my check, not the game (a blind sweep that sometimes killed nothing; a free shield landing on the ship so the forced hit was absorbed); both were fixed in the check |
| Bot difficulty numbers above | MEASURED, simulation | the bots aim perfectly and dodge badly, so they are not a measure of how a person finds it |
| The sounds are pleasant, the difficulty curve and the first boss feel fair, it is fun | UNPROVEN | no person has played v0.2 |
| Phones: the drag control | UNPROVEN | tested with a mouse in Chromium, never on a physical phone |
| Bombs, bosses with different patterns, formations, music, an online table | NOT BUILT | |
| The copy stays in step with the project | NOT CLAIMED | manual copy |
