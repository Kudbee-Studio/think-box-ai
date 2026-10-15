# P3.87 Pinball v0.5 in the dashboard: upper deck, ball traps, multiball

The dashboard's `/pinball/` copy is refreshed from the standalone project (`~/projects/pinball`, commit 2a5faef) after #426 brought it to v0.3. It now has: two more bumpers, a bumper-bank jackpot, super combos, an upper deck (a second layer) reached by a trap at the top, a side ball lock that holds a ball for 3 seconds and then shoots it out with up to two free extra balls (multiball, at most 3 balls at once), and new effects and sounds. Physics constants and the main-table collision geometry (the ball-sticking fix) are unchanged since v0.2.1.

| Claim | State | Basis |
|---|---|---|
| The v0.3 test suite run against the new source: all physics and anti-sticking tests (400+ drop positions with flippers at rest, flippers held then released, 300 random starts, loss below the flippers) pass | PROVEN | standalone project: 65 of 66 pass untouched; the one that differs checks the order of text in `render.js` and was updated on purpose (the screen now loops over every ball) |
| New behaviour: lock holds 3 s and releases by 3.2 s; two free extras, never more than 3 balls; a drained extra just disappears; an extra is promoted when your ball drains; only the last ball's loss costs a ball and pays the bonus; extras score; one ball held per trap | PROVEN | standalone project: 98 tests in all, all pass (`tests/multiball.test.js`, `tests/deck.test.js`) |
| 200 deck starting positions all come down by themselves within 15 s (not by the 20 s safety net) and none leave the table | PROVEN | `tests/deck.test.js` (a first version of this test used start points outside the curved walls; it was fixed, the game was not changed for it) |
| Three moving balls, random starts, random flipper use: every ball stays on the table | PROVEN for 40 runs of 10 s | slower than the single-ball case, so fewer runs |
| The served copy is the project at v0.5 (deck, traps, MAX_BALLS, 3 s lock, sticking fix present; every file exists; no inline script; byte-identical to the project) | PROVEN | tests/pinball-served.test.ts |
| In Chromium through the dashboard (its CSP applies): ball locked and still held at 2 s, released at 3 s with 2 extra balls, a ball sent to the deck and back down, game over, guarded restart, mute button, no console errors | PROVEN once by hand | `node tests/browser-check.mjs` with BASE set to the dashboard's `/pinball/`; not an automated dashboard test |
| A 3-second lock with a single ball may feel long; two extras may be too generous; the trap may be too easy or too hard to hit; point values | UNPROVEN | no person has play-tested v0.4 or v0.5. The owner reported the sounds as good; nothing else |
| Phones and touch buttons | UNPROVEN | not tried on a physical phone |
| Ball-to-ball collisions, a ball save, slingshots, drop targets, nudge/tilt | NOT BUILT | |
| The copy stays in step with the project | NOT CLAIMED | manual copy |
