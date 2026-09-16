# G-Code Mastery Curriculum — 2-Week Daily Drills

**For:** Dominick (CNC beginner → solid)
**Dialect:** GRBL / LinuxCNC-friendly (Fanuc-only features flagged)
**Philosophy:** Learn by doing, not memorizing dictionaries.

---

## The 6 Universal Truths (Read Before Every Session)

1. **Never run unproven G-code on metal.** Dry-run in CAMotics or NC Viewer first.
2. **Z is the most dangerous axis.** Always know where Z is before X/Y move.
3. **Mode is everything.** G90 vs G91, G17 vs G18 vs G19, G20 vs G21 — check before you cut.
4. **Feeds and speeds kill.** Wrong F or S can destroy tooling, workpiece, or spindle.
5. **Soft limits save machines.** Use G10 to set them. Trust limit switches as the last line of defense.
6. **Comment everything.** Future-you at 2 AM will thank present-you.

---

## Week 1: Foundation — Movement, Modes, and Safety

### Day 1 — The Coordinate System (G20/G21, G17–G19)

**Concepts:** Units (inch vs mm), planes (XY, XZ, YZ).

**Drill:**
- Open your simulator. Set G20 (inch). Move G0 X1 Y1. Confirm position.
- Switch to G21 (mm). Move G0 X25.4 Y25.4. Confirm it's the same physical point.
- Practice G17 (XY plane — default), G18 (XZ), G19 (YZ). Note which plane your arcs use.

**Key G-code:**
```gcode
G20          ; Inches (US standard)
G21          ; Millimeters (ISO standard)
G17          ; XY plane (default — most operations)
G18          ; XZ plane (face milling, lathes)
G19          ; YZ plane (side milling)
```

**Check:** After every mode change, echo the mode back. `G17` on its own line is your confirmation.

---

### Day 2 — Motion Modes (G0, G1, G2/G3)

**Concepts:** Rapid traverse vs feed rate cut. CW vs CCW arcs.

**Drill:** `examples/gcode/square.gcode` — cut a 2" square, then rapids back to start.

**Key G-code:**
```gcode
G0 X0 Y0     ; Rapid (no cutting) — fast positioning
G1 X2 Y0 F10 ; Feed cut at 10 IPM
G2 X2 Y2 I0 J1 ; CW arc, center offset from current point
G3 X0 Y2 I-1 J0 ; CCW arc
```

**Practice:** Write a triangle by hand using only G0 and G1. Run it dry-run. Verify each vertex.

---

### Day 3 — Absolute vs Incremental (G90/G91)

**Concepts:** Coordinates are either from origin (absolute) or from last position (incremental).

**The Pitfall:** Forgetting which mode you're in. A G0 X1 in G91 after G0 X2 goes to X3, not X1. This has crashed many machines.

**Drill:**
- Write a square using G90 (absolute). Run dry-run.
- Rewrite using G91 (incremental). Same square, different code.
- Confirm both produce the same physical result.

**Key G-code:**
```gcode
G90          ; Absolute — all coords from origin
G91          ; Incremental — all coords from last position
G90          ; Always return to absolute before finishing
```

**Rule:** End every program with `G90`. Always know your mode.

---

### Day 4 — Work Offset (G54)

**Concepts:** G54–G59 define where the workpiece zero is relative to machine zero.

**Drill:** In simulator, set G54 Z = workpiece top surface. Practice Z-up approach.

**Key G-code:**
```gcode
G54          ; Use work coordinate system 1
G0 Z1.0      ; Rapid to clearance height (above workpiece)
G0 X0 Y0     ; Rapid to XY start (in G54 coordinates)
```

**Check:** Before any cut, `G0 Z[clearance]` then `G0 X[target] Y[target]`. Never plunge from a random Z.

---

### Day 5 — Feed, Spindle, and the Full Stop

**Concepts:** F (feed rate), S (spindle speed), M-codes.

**Drill:** Read the parameter table below. Write a program that starts spindle, cuts a line, stops spindle, and ends program.

**Key G-code:**
```gcode
M3 S1000      ; Spindle CW at 1000 RPM
M5            ; Spindle stop
M8            ; Coolant on (flood)
M9            ; Coolant off
M30           ; Program end and rewind
```

**Parameters cheat sheet (memorize these):**

| Address | Meaning | Example | Notes |
|---------|---------|---------|-------|
| X | X-axis position | `X2.5` | In current units |
| Y | Y-axis position | `Y1.0` | In current units |
| Z | Z-axis position | `Z-0.5` | Negative = into workpiece |
| F | Feed rate | `F10` | IPM or MMPM depending on G20/G21 |
| S | Spindle speed | `S1000` | RPM |
| P | Dwell / sub-call | `P500` | Milliseconds in G4; group in M98 |
| Q | Depth per pass / mirror | `Q0.1` | Peck drill depth; mirror offset (Fanuc) |
| R | Retract plane / radius | `R1.0` | Z-clearance for canned cycles; arc radius |
| I | Arc center X offset | `I0.5` | From arc start point |
| J | Arc center Y offset | `J0.5` | From arc start point |
| K | Arc center Z offset | `K0.2` | For arcs in XZ or YZ plane |
| D | Tool offset / diameter comp | `D01` | Tool table index; cutter comp register |
| H | Tool length offset | `H01` | Length compensation register |

---

### Day 6 — Limit Switches vs Soft Limits (Safety)

**Concepts:**
- **Limit switches:** Physical sensors. Hard stop. They work when the computer is off.
- **Soft limits:** Software boundaries set via G10. The controller refuses moves past them — but only if it's running.

**Drill:**
- In simulator, set soft limits: `G10 P1 L20 X0 Y0` (set logical position at current machine position for axis 1, X=0, Y=0).
- Try to move past the limit. Observe the alarm.
- Test `M11` (GRBL: limit switch triggered input) and `M12` (GRBL: probe trigger input).

**Key G-code:**
```gcode
G10 P1 L20 X0 Y0   ; Set soft limit (homing position) at current location
```

**Rule:** Soft limits are your first line of defense. Limit switches are your last. Trust both.

---

### Day 7 — Week 1 Review

**Drill:** Write a complete program that:
1. Sets units, plane, absolute mode, work offset
2. Rapids to start position
3. Spindle on at 1000 RPM
4. Cuts a 1" square with feed rate 10 IPM
5. Spindle off, coolant off
6. Return to G90, return to home, program end

Run it through dry-run three times before calling it done.

---

## Week 2: Canned Cycles, Arcs, and Parameters

### Day 8 — Peck Drilling (G81/G83)

**Concepts:** Canned cycles automate repetitive drilling. G81 = standard drill, G83 = peck (breaks chips).

**Drill:** `examples/gcode/peck_drill.gcode` — 3 holes, two peck cycles.

**Key G-code:**
```gcode
G90 G80 G54        ; Absolute, cancel cycle, work offset
G0 X1.0 Y1.0       ; Rapid to first hole
G43 H01 Z1.0 M3 S1000  ; Tool length comp, clearance, spindle on
G81 Z-1.0 R0.1 F10 ; Drill cycle: Z=-depth, R=retract, F=feed
X2.0 Y1.0          ; Next hole (same cycle, just new XY)
X3.0 Y1.0          ; Third hole
G80                ; Cancel canned cycle (MUST DO)
G0 Z1.0            ; Retract
M5 M9 M30          ; Spindle off, coolant off, end
```

**G83 (peck drill) variant:**
```gcode
G83 Z-1.0 R0.1 Q0.1 F10  ; Q = peck depth (0.1" per pass)
```

**Check:** Always `G80` to cancel. Forgetting this causes the next move to be interpreted as a cycle entry.

---

### Day 9 — Facing (Z-Level Clearing)

**Concepts:** Facing removes material from the top surface. Step-over in X, clear in Z.

**Drill:** `examples/gcode/face.gcode` — face a 2" x 2" workpiece at 0.1" depth per pass.

**Key G-code:**
```gcode
G90 G54 G17
G0 X-1.0 Y-1.0 Z1.0       ; Start outside, clearance
G1 Z0.2 F10                ; Plunge to first depth (0.2" below top)
G1 X3.0 F10                ; Cut across
G0 Z0.3                    ; Raise for next pass
G1 Y2.0 F10                ; Cut back
G0 Z0.4                    ; Next pass
G1 X-1.0 F10               ; Final pass
```

**Parameter focus:** F (feed), Z depth per pass, the raise-move pattern.

---

### Day 10 — Pocket Milling (G2/G3 with depth steps)

**Concepts:** Pockets require multiple depth passes. Use arcs for rounded pockets.

**Drill:** `examples/gcode/pocket.gcode` — read every comment. Trace the toolpath by hand before running.

**Key G-code:**
```gcode
; Pocket roughing: 0.1" deep per pass, 1" square pocket with 0.2" corner radius
G90 G54 G17
G0 X0 Y-1.0 Z1.0           ; Start position
; --- Depth pass 1 ---
G1 Z-0.1 F10               ; Plunge to depth
G1 X1.0 F10                ; Cut right
G2 X1.0 Y0 R0.2            ; CW arc to center-right (0.2" radius corner)
G2 Y1.0 R0.2               ; CW arc to top-right corner
G1 X0 Y1.0                 ; Cut left along top
G3 X-0.0 R0.2              ; ... continue contour
; --- End pocket ---
G0 Z1.0                    ; Retract for next depth
```

**Rule:** Read the comments. Trace the toolpath mentally. Then dry-run.

---

### Day 11 — Arc Mastery (G2/G3 with R vs I/J/K)

**Concepts:** Two ways to specify arcs: radius (R) or center offset (I/J/K). R is simpler but can't distinguish full circles or arcs > 180°.

**Drill:** Draw a 1" diameter circle two ways: once with R, once with I/J.

**Key G-code:**
```gcode
; Method 1: Radius (R) — semicircle
G0 X0 Y0
G1 X1.0 F10
G3 X0 Y0 R0.5              ; CCW semicircle, radius 0.5

; Method 2: Center offset (I/J) — full circle
G0 X0.5 Y0
G1 X0.5 Y0 F10
G3 X0.5 Y0 I-0.5 J0        ; CCW full circle, center at (0,0)
```

**Pitfall:** `R0.5` with a 1" distance is ambiguous (could be 180° or 360°). I/J/K is always precise.

**Fanuc-only flag:** Some Fanuc controls require `C` (clockwise) or `CC` (counterclockwise) on arcs in certain configurations. GRBL and LinuxCNC don't.

---

### Day 12 — Parameters and Macro Variables (Intro)

**Concepts:** `#100`-style variables (Fanuc macro), `#1`-style (LinuxCNC).

**Drill:** Set a variable, use it in a move, increment it.

**Key G-code (LinuxCNC/GRBL-compatible):**
```gcode
#1 = 10                    ; Assign 10 to variable 1
G0 X#1 Y0                  ; Move to X=10
#1 = #1 + 5                ; Increment
G0 X#1                     ; Move to X=15
```

**Fanuc vs GRBL differences:**

| Feature | Fanuc | GRBL/LinuxCNC |
|---------|-------|---------------|
| Variable syntax | `#100` | `#1` (or `N10` on some) |
| Macro loops | `WHILE ... DO ... END` | `G10` logic or external |
| Arithmetic | `#1 = #2 + #3` | Same syntax |
| Conditional | `IF [#1 GT 5] GOTO 100` | Limited or external |
| Built-in math | `SIN`, `COS`, `SQRT` | Limited; pre-compute |

**Rule:** Macro vars are powerful but dangerous. Always dry-run. A bad variable can drive the spindle into the fixture.

---

### Day 13 — Full Program Assembly

**Drill:** Write a complete 3" x 3" plate program that:
1. Faces the top (3 passes)
2. Drills 4 holes at corners (G81)
3. Cuts a 1" square pocket in center (2 depth passes)
4. Ends cleanly

**Requirements:**
- Every block commented
- G90 mode explicit
- G54 work offset set
- M30 at end
- Dry-run passes on every machine before metal touches

---

### Day 14 — Review and Freestyle

**Drill:** Pick any shape you want. Design it, write the G-code by hand, dry-run it, then run it (on scrap aluminum, not steel — not yet).

**Goal:** You should be able to:
- [ ] Set G20/G21, G17–19, G90/G91 correctly
- [ ] Write G0/G1 moves in any plane
- [ ] Write G2/G3 arcs with both R and I/J methods
- [ ] Run a G81/G83 cycle and cancel it properly
- [ ] Set and use soft limits
- [ ] Know what every letter address means (F, S, P, Q, R, I, J, K, D, H)
- [ ] Comment every line meaningfully
- [ ] NEVER run unproven code on metal

---

## Safety Checklist (Read Before Every Session)

See `docs/gcode-checklist.md` for the one-page version.
