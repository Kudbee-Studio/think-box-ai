# G-Code Examples — Dry-Run Guide

## ⚠ SAFETY FIRST

**NEVER run unproven G-code on metal.**

These programs are training examples. Before running on any material:
1. Dry-run in a simulator (see below)
2. Trace the toolpath by hand on graph paper
3. Verify every X, Y, Z position makes physical sense
4. Check that your tool is rated for the spindle speed (S value)
5. Start with soft limits enabled
6. Confirm your machine's actual max spindle speed — 2000 RPM on a small mill can fly the tool off

---

## Dry-Run in CAMotics (Free, Open-Source)

1. Download from [camotics.org](https://camotics.org)
2. Open the `.gcode` file
3. CAMotics parses standard G-code (G0, G1, G2, G3, G81, G83, M-codes)
4. Click **Play** to watch the toolpath
5. Toggle **2D view** or **3D view** to inspect
6. CAMotics shows tool path but not material removal — pair with NC Viewer for that

---

## Dry-Run in NC Viewer (Free, Web-Based)

1. Go to [ncviewer.com](https://ncviewer.com)
2. Drag and drop the `.gcode` file
3. The toolpath renders immediately in 3D
4. Use the timeline slider to scrub through the cut
5. Toggle **2D/3D** view modes
6. NC Viewer simulates material removal — you'll see the pocket and holes form

**Note:** NC Viewer may not support all GRBL-specific codes. If a block is skipped, check for non-standard syntax.

---

## What Each Example Demonstrates

| File | Concept | Drill Day | Key Codes |
|------|---------|-----------|-----------|
| `square.gcode` | Basic linear moves | Day 2 | G0, G1, F, M3, M5, M30 |
| `circle.gcode` | Arc moves (G2/G3) | Day 11 | G3, I/J center offset |
| `face.gcode` | Z-level facing | Day 9 | F, Z depth steps, G0 raises |
| `peck_drill.gcode` | Canned cycles | Day 8 | G81, G83, Q, R, G80 cancel |
| `pocket.gcode` | Pocket milling | Day 10 | G2 arcs, depth passes, comments |

---

## Reading a G-Code Block

Every line is a command. Here's how to read one:

```gcode
N40 G83 Z-1.0 R0.1 Q0.1 F10
```

- **N40** — Line number (for reference, not required)
- **G83** — Peck drill canned cycle
- **Z-1.0** — Drill depth: 1.0 inches below surface
- **R0.1** — Retract plane: 0.1" above surface (between passes)
- **Q0.1** — Peck depth: cut 0.1", retract, repeat
- **F10** — Feed rate: 10 inches per minute

**Ask yourself before running:**
- ✅ Is Z safe? (Am I above the workpiece?)
- ✅ Is F reasonable for this material?
- ✅ Is S (spindle RPM) within tool limits?
- ✅ Is the tool actually installed at the expected length?
- ✅ Have I dry-runed this?

---

## GRBL-Specific Notes

- GRBL may not support all M-codes (e.g., M9 might not exist on older versions)
- G83 peck drilling support varies by GRBL version — check your controller's documentation
- Some GRBL builds use `$` for settings (e.g., `$1=1000` for soft limits) instead of G10
- Homing switches are configured via GRBL settings, not G-code
- **Always check your GRBL version's supported code list before running an unfamiliar program**

---

## Fanuc-Only Flags in These Examples

The following are included for reference but **are not standard GRBL/LinuxCNC**:
- `G30` (return to reference position) — used in `circle.gcode`; use `G0 X0 Y0` instead in GRBL
- `G43 H01` (tool length comp) — supported in GRBL but requires a tool table to be configured
- `M30` vs `M2` — both end the program; M30 rewinds, M2 stops
