# P3.88 Pinball v0.7 in the dashboard: a livelier deck, ball save, slingshots, presets

The dashboard's `/pinball/` copy is refreshed from the standalone project (`~/projects/pinball`, commit 331049c plus a browser-check-only change, v0.7) after #427 brought it to v0.6. Changes, in the order the owner asked for them ("the top needs work", answered "the upper deck is dull"; then ball save, slingshots, presets):
- **Deck:** a second-tier shelf under the funnel gap (the ball rolls across it), a fourth deck bumper, a per-hit bonus paid when the ball leaves the deck, and a deck jackpot (all four deck bumpers in one ride).
- **Ball save:** a lost last ball is returned free inside a window after launch, once per ball.
- **Slingshots:** two kicker faces above the flippers with channels down to the flippers.
- **Presets:** Easy / Normal / Hard buttons, plus ball-save length and lock time as settings.
- **Lock limit and a softer slingshot (found by measurement, see below):** the ball lock works twice per ball.

## A problem the slingshots exposed
After the slingshots went in, balls with the flippers never touched survived for minutes: 76 of 100 were still alive after 90 s, with about 11 locks per ball, because the slingshots fed a released ball straight back into the funnel and the lock. Without the slingshots none survived 90 s. The lock now works twice per ball, and the slingshot kick is 450 (a sweep showed that at 480 and up some balls bounce between the slingshots for ever and at 460 and down none do). Every one of 200 balls with no flipper input now drains within 10.8 s (median 7.7 s).

| Claim | State | Basis |
|---|---|---|
| Deck ride (shelf over a second, 200 start positions come down by themselves within 15 s, a ball left anywhere on the shelf rolls off in 8 s, per-hit bonus, deck jackpot separate from the main jackpot, lights reset) | PROVEN | standalone `tests/deck-ride.test.js`, `tests/deck.test.js` |
| Ball save (window opens on launch, lost ball returns free, once per ball, game time only, extras promote first, reopened by multiball, real loss resets) | PROVEN | `tests/save.test.js` |
| Slingshots (mirror images, ends 36+ px clear of the guides, kick only from the inner side, flat points once per touch, side channels and faces never stick) | PROVEN | `tests/sling.test.js` |
| Presets (all inside the slider ranges, normal is the default, pressed button follows the settings, a hand-changed setting shows none) and the lock-time setting | PROVEN | `tests/save.test.js`, `tests/tuning-ui.test.js` |
| The lock limit and "every ball drains with no flipper input" (40 launches, none alive after 100 s) | PROVEN | `tests/exploit.test.js`; measured over 200 balls: all drained, median 7.7 s, max 10.8 s |
| The original v0.3 anti-sticking suite (66 tests) run against the final source | PARTLY: 63 of 66 pass untouched | The three that differ: a text-order check in `render.js` (changed on purpose, the screen now draws every ball); the old "falls back into the launch lane" test checked only the end position and now sees a legitimately drained ball waiting in the lane (the current version checks every step); the old "never wedges" test counted a ball held in the lock as stuck (held frames are excluded and a lock held over 3.5 s fails). No physics regression was found behind any of the three |
| The full standalone suite | PROVEN | 143 tests, all pass |
| The served copy is v0.7, byte-identical to the project, every file exists, no inline script | PROVEN | tests/pinball-served.test.ts |
| In Chromium through the dashboard (its CSP applies): natural lock then multiball, deck ride, ball save, presets, a slingshot kick, game over and restart, no console errors | PROVEN | 4 of 4 runs. The first three runs (one passed) failed because my check's own setup collided with the new rules (an earlier natural lock had used the ball's two locks, and the ball save caught balls the check forced to drain); the check now resets them. Standalone: 3 of 3 |
| A simple bot that always flips when the ball is low: balls last 56 s on average (many reach the 60 s cap), 116 of 150 balls got a lock | MEASURED, simulation | far better than a typical player, so this is not a difficulty measure |
| Fun, balance, whether Normal is too easy (use Hard), phone use | UNPROVEN | no person has play-tested v0.7 |
| Ball-to-ball collisions, nudge/tilt, drop targets, lane letters, missions, high-score names, more tables | NOT BUILT | |
| The copy stays in step with the project | NOT CLAIMED | manual copy |
