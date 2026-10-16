# P3.91 Starfall v0.4 in the dashboard: Think Boxes and a four-weapon system

The dashboard's `/game/` copy is refreshed from the standalone project (`~/projects/starfall`, v0.4) after #430 brought it to v0.3. The request: "the starfighter game should be think boxes that we have to shoot down and better weapons systems".
- **Think Boxes:** the enemies are drawn as cubes in the six layer colours of the Think Box architecture (taken from the product site's stylesheet): Idea Box (sky blue), Spin Box (violet), Vault Box (rose, padlock, three hits), Cannon Box (orange, shoots back), Dart Box (green, homes in); the bosses are Mega Think Boxes. Broken boxes fall apart in their own colour and drop yellow Think Tokens.
- **Weapons:** Laser, Spread, Missiles (homing, with a small blast) and Rail (pierces), each with four levels, chosen with 1 to 4 or Q/E (and a button on touch screens). Eight Think Tokens raise the weapon in hand one level; weapon crates unlock or raise a weapon; a lost life costs the weapon in hand one level; the old timed "spread" power-up became the Spread weapon, and "rapid" became the overclock.

## Measured, and what that changed
- The Rail first came out as the worst weapon at every level (it barely scaled with level), so it was given faster fire and more damage per level. Killing speed per weapon and level, and time to kill a boss-sized box, are in the project README.
- A first boss-time measurement was wrong because my harness held the boss's position only at the start of each frame while the boss swayed to an absolute position inside the step, so bullets missed; it was fixed in the harness, not the game.
- With the weapons so much stronger, a level-4 weapon killed a 36-point boss in about 2 s, so boss health was raised to 68 for the first and 18 more for each after (it was 36 and 14).
- Bots (20 runs, Normal; the dodging bot collects tokens and crates like a player): never touching 37 s and 0 points; only firing 64 s; aiming without dodging 69 s (wave 6.7); dodging 141 s (wave 11, holds 7.5 weapon levels, beats 28 of 40 bosses). The weapons raised the dodging bot from 124 s to 141 s.

| Claim | State | Basis |
|---|---|---|
| Think Box names and colours (all from the six layer colours, no two alike), the three Mega Boxes, four weapons by level (shots, rate, damage, piercing, homing, blast), switching and cycling, overclock, crates (unlock or level up, only offering what can still be upgraded, bosses drop one), Think Tokens (drops, magnet, eight per level, a bonus at the top), a lost life costs one level (a shield costs none), accuracy capped at 100%, determinism with every weapon, capped lists | PROVEN | standalone project: 101 tests, all pass |
| No weapon is the clear best: killing speed with each at level 3 is within a factor of two of the Laser's | PROVEN | `tests/weapons.test.js` |
| Every box, boss, crate, token, shot kind and weapon level can be drawn; every screen | PROVEN | `tests/render.test.js` (fake canvas) |
| The served copy is v0.4, byte-identical to the project, no inline script, with the names, colours, weapons, cube drawing, weapon keys and the weapon button | PROVEN | tests/game-served.test.ts |
| In Chromium through the dashboard (CSP applies): crates unlock three weapons, the number keys and Q/E switch, every weapon fires its own kind of shot, eight tokens raise the weapon one level, plus everything from v0.3, no page errors | PROVEN | 5 of 5 runs (an earlier run failed because my check assumed a clean slate when the player had already found a crate in play; the game was right) |
| Bot numbers and the weapon table | MEASURED, simulation | bots aim perfectly and dodge badly; not a human measure |
| The weapons feel good and distinct; eight tokens a level is the right pace; the Think Box look reads as intended; sounds; fun | UNPROVEN | no person has played v0.4 |
| Phones: the drag control, the bomb button, the weapon button | UNPROVEN | a mouse in Chromium only |
| A charged shot, drones, weapon-specific bosses, music, an online table | NOT BUILT | |
| The copy stays in step with the project | NOT CLAIMED | manual copy |
