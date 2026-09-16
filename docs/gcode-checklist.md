# G-Code "Read This Block" Checklist — One-Page Safety Check

**Read this before running ANY G-code program.**

Tick each box. If any box is unchecked, STOP and fix it.

---

## 1. Setup Mode (3 blocks at the top)

| Check | G-Code | What to verify |
|-------|--------|----------------|
| ✅ | `G20` or `G21` | Inches or mm? Match your caliper. |
| ✅ | `G17`, `G18`, or `G19` | Which plane? XY for most milling. |
| ✅ | `G90` | Absolute mode confirmed. End program with this too. |
| ✅ | `G54` | Correct work offset for your setup. |
| ✅ | `G80` | Canned cycle cancelled (if used). |

---

## 2. Z — The Kill Axis

| Check | What to verify |
|-------|----------------|
| ✅ | **Z is positive (above workpiece)** before any rapid move (G0) |
| ✅ | **Z is negative (below surface)** only during a cutting move (G1, G2, G3, or canned cycle) |
| ✅ | **Retract to Z+** between operations (G0 Z1.0 or higher) |
| ✅ | **Clearance height is consistent** — same Z before every move to new XY position |
| ❌ | **Never** move XY while Z is down at cut depth |

---

## 3. Feed and Spindle (The Damage Duo)

| Check | What to verify |
|-------|----------------|
| ✅ | **M3 S____** — Spindle on with RPM. Is the RPM within your tool's rating? |
| ✅ | **F____** — Feed rate. Is it reasonable for your material? (10 IPM is safe for steel, 50+ for aluminum) |
| ✅ | **M5** — Spindle OFF before retracting and ending |
| ✅ | **M9** — Coolant OFF (if turned on with M8) |
| ❌ | **Never** leave spindle running at end of program |

---

## 4. Canned Cycles (G81/G83 — Drill Codes)

| Check | What to verify |
|-------|----------------|
| ✅ | **R value** — Retract plane above workpiece surface |
| ✅ | **Z value** — Hole depth (negative number) |
| ✅ | **Q value** (G83 only) — Peck depth per pass |
| ✅ | **G80** — Cycle Cancelled after ALL holes are drilled |
| ❌ | **Never** make a non-cycle move (XY or Z change) inside a G81/G83 cycle without cancelling first |

---

## 5. Arcs (G2/G3) — Common Mistake

| Check | What to verify |
|-------|----------------|
| ✅ | **I/J/K** — Center offset from arc START point, NOT center of arc |
| ✅ | **R** — If using radius, the arc is ≤ 180° (otherwise use I/J) |
| ✅ | **Plane** — G17 (XY), G18 (XZ), or G19 (YZ) matches your arc plane |
| ❌ | **Never** use R for arcs > 180° or full circles — use I/J |

---

## 6. End of Program

```gcode
; The proper ending pattern:
G0 Z1.0       ; ✅ Full retract above workpiece
G0 X0 Y0      ; ✅ Return to home (confirm position)
M5            ; ✅ Spindle stop
M9            ; ✅ Coolant off (if applicable)
G90           ; ✅ Back to absolute mode (if you used G91)
M30           ; ✅ Program end and rewind
```

| Check | What to verify |
|-------|----------------|
| ✅ | Z is retracted (positive) |
| ✅ | XY is at known safe position |
| ✅ | Spindle stopped (M5) |
| ✅ | Coolant off (M9) |
| ✅ | Program ended properly (M30 or M2) |

---

## 7. Pre-Run (Every Single Time)

- [ ] **Dry-run in CAMotics or NC Viewer** — watch full toolpath
- [ ] **Soft limits set** — `G10 P1 L20 X____ Y____ Z____` or controller settings
- [ ] **Limit switches functional** — test if possible
- [ ] **Tool installed and measured** — tool length offset correct (H value)
- [ ] **Material secured** — clamped or bolted, cannot shift
- [ ] **Emergency stop accessible** — know where the E-stop is before you hit Cycle Start
- [ ] **First piece at reduced feed** — run at 50% F for first pass if uncertain

---

## Quick Reference: What Each Letter Means

| Letter | Meaning | When to check |
|--------|---------|---------------|
| X, Y, Z | Position | Every move — where is the tool? |
| F | Feed rate | Before cutting — too fast = broken tool |
| S | Spindle RPM | Before spindle on — too fast = tool fly-off |
| R | Retract plane / arc radius | In canned cycles and arcs |
| I, J, K | Arc center offset | In every arc — wrong values = wrong shape |
| Q | Peck depth / sub-program | In G83 cycles and macro calls |
| P | Dwell time / sub-program group | In G4 (dwell) and M98 (call) |
| H | Tool length offset | Before first cut — wrong H = crash |
| D | Cutter comp / tool offset | In offset operations |
| M3/M5 | Spindle on/off | Start and end of every operation |
| M8/M9 | Coolant on/off | Start and end of cutting operations |
| G80 | Cancel canned cycle | After every G81/G82/G83/G84 |
| G90/G91 | Absolute/Incremental | At setup and at end — always know which |
