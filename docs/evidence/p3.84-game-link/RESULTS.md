# P3.84 Starfall linked from the dashboard

The dashboard serves a small arcade game at `/game/` (`apps/web/public/game/`, a copy of the separate project `~/projects/starfall`) and the header has a "Game" link next to "Website".

| Claim | State | Basis |
|---|---|---|
| The page uses relative paths; every file and module it imports exists; no inline script or handler | PROVEN | tests/game-served.test.ts |
| The real server serves the game and its scripts (200) with the security headers, and the header links to `/game/` | PROVEN | same file |
| The header keeps the link outside the Tools menu | PROVEN | tests/header-menu.test.ts |
| In a real browser, through the dashboard (its Content-Security-Policy applies): the link opens `/game/`, the game starts, fires and spawns enemies, no console errors | PROVEN once, by hand (Playwright against a second server on another port) | not an automated test |
| The game is fun, balanced, works on a phone | UNPROVEN | nobody has played it yet |
| The copy in `public/game/` stays in step with the game project | NOT CLAIMED | it is a manual copy; the README in that folder says how to refresh it |
