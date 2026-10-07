# THINK BOX AI

The static, single-page site for **THINK BOX AI** (KUDBEE Agent OS) by kudbEE. Canonical URL: https://www.kudbee.xyz/

It is plain HTML, CSS and vanilla JS. There is no build step, no framework and no CDN at runtime.
- The 3D parts use **three.js r169, vendored locally** at `vendor/three.module.min.js` (MIT, see `vendor/three.LICENSE`).
- The display font is **Inter Tight** (variable, latin subset), self-hosted at `assets/fonts/InterTight-latin-var.woff2` from `@fontsource-variable/inter-tight@5.3.0`. It is SIL OFL 1.1, see `assets/fonts/OFL-InterTight.txt`. It loads with `font-display: swap` and a preload.

## Open it locally

The 3D cube and the block inspector are ES modules, and browsers block modules on `file://`. Serve the folder:

```bash
cd thinkTokens
python3 -m http.server 8000
# then open http://localhost:8000
```

You can also double-click `index.html`. Everything except WebGL works that way, and you get a CSS-only cube plus a still render instead.

## Files

| File | Purpose |
|------|---------|
| `index.html` | Every section, SEO meta, JSON-LD, noscript summary, PR/ADR data |
| `styles.css` | Design system, light/dark themes, responsive layout (390 / 768 / 1280+) |
| `script.js` | Nav, progress and minimap, theme, palette (Cmd/Ctrl-K), shortcuts (`?`), terminal demo, flow, routing, attack demo, changelog, ADRs, orbit, FAQ, configurator, proof strip, walkthrough hook. Lazy-loads `cube.js` after load and `block.js` near its section |
| `cube.js` + `cube-model.js` | Scroll-driven 3D cube: 54 labeled stickers (one texture atlas), tap-to-twist issue cards, Scramble/Solve |
| `block.js` | "Inside a single block": one cubelet, four explodable layers, hotspots, block picker |
| `assets/` | Section art and cube renders (WebP), og image (PNG), icons, favicon, fonts |
| `manifest.webmanifest`, `robots.txt`, `sitemap.xml` | PWA and SEO |

## Behavior notes

- **Reduced motion:** there is no idle spin and no twists. The cube snaps to each face, the terminal shows the full transcript instantly and counters show their final values.
- **No WebGL:** you get a CSS cube in the hero and a still render in the block inspector.
- **Performance:** devicePixelRatio is capped at 2 (1.75 on mobile), and rendering pauses offscreen. Three.js loads only after the page has loaded.
- **Illustrative content:** the terminal, the configurator JSON and the attack demo are scripted and labeled.
- **Proof strip:** the numbers are static values read from GitHub on Sep 30 to Oct 1, 2026. Refresh them by hand.

## Founder TODOs

Search `index.html` for `TODO founder` and `[Founder to write`:
1. Origin story under "The problem".
2. Founder note in "Build in public".
3. Dashboard walkthrough: drop `assets/video/dashboard.mp4`, then set `data-has-video="true"` on `#walk-video`.
