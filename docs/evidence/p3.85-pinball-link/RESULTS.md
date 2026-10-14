# P3.85 Pinball linked from the dashboard

The dashboard serves a second small arcade game at `/pinball/` (`apps/web/public/pinball/`, a copy of the separate project `~/projects/pinball`, v0.2) and the header has a "Pinball" link beside "Game" (Starfall, the space shooter at `/game/`).

| Claim | State | Basis |
|---|---|---|
| Relative paths; every file and module it imports exists (9 modules); no inline script or handler | PROVEN | tests/pinball-served.test.ts |
| The real server serves the game and its scripts (200) with the security headers; the header links to `/pinball/`, outside the Tools menu | PROVEN | pinball-served and header-menu tests |
| In a real browser through the dashboard (its CSP applies): the link opens `/pinball/`, the ball launches, flippers and a bumper score, the T panel opens, no console errors | PROVEN once by hand | Playwright against a second server; not an automated test |
| Starfall at `/game/` is unchanged | PROVEN | game-served tests still pass |
| The pinball game feels right, sounds good, or works on a phone | UNPROVEN | nobody has played it or heard it |
| The copy stays in step with the pinball project | NOT CLAIMED | manual copy; the folder README says how to refresh it |
