# P3.86 Pinball arcade feel (v0.3) in the dashboard

The dashboard's `/pinball/` copy is updated from the standalone project (`~/projects/pinball`, commit cd5bf33 plus a browser-check tweak): it now has the ball-sticking fix (v0.2.1) that PR #425's copy lacked, and the v0.3 arcade feel: combo scoring, a drain bonus, a Ball lost banner, clearer game over (new best, guarded restart), more effects and sound, and a visible Sound button. Physics constants and collision geometry are unchanged since v0.2.1.

| Claim | State | Basis |
|---|---|---|
| The original 52 pinball tests from v0.2.1, unmodified, pass against the new source (the anti-sticking regression: 400+ drop positions with flippers at rest, flippers held then released, 300 random starts, immediate loss below the flippers) | PROVEN | run in the standalone project: 52 of 52; full suite 66 of 66 |
| Scoring (combo window and bonus, multiplier announced once, drain bonus before the drain, new best), flow (restart guard, score easing), effects (banner, call-out, popup size, popups drawn before the ball), sound (new tones, distinct, mute) | PROVEN | 14 new tests in the standalone project |
| The dashboard copy is the project at its latest version (sticking fix, bonus, mute button present; every file named exists; no inline script) | PROVEN | tests/pinball-served.test.ts; the copy is byte-identical to the project's `src/`, `index.html` |
| In Chromium through the dashboard (its CSP applies): launch, bumper score, mute button, a drain paying a 900 bonus with the banner, game over with "new best", an early Enter refused, a later Enter restarts with 3 balls, no console errors | PROVEN once by hand | `node tests/browser-check.mjs` with BASE set to the dashboard's `/pinball/`; not an automated dashboard test |
| The sounds are pleasant, the table feels like pinball | UNPROVEN | nobody has heard or played this version; sound was tested against a fake audio device |
| Phones and the touch buttons | UNPROVEN | not tried on a physical phone |
| Typecheck and build for the game | NOT APPLICABLE | the game is plain JavaScript with no build step; the dashboard's lint, typecheck and tsc gates run on this PR |
| Targets, slingshots, multiball | NOT BUILT | there are no targets, so hit effects apply to bumpers only |
| The copy stays in step with the project | NOT CLAIMED | manual copy; the folder README says how to refresh it |
