; circle.gcode — Cut a 1" diameter circle (0.1" deep)
; Drill: Day 11 — Arcs (G2/G3 with I/J method)
; GRBL/LinuxCNC compatible
; --- NEVER DRY-RUN THIS BEFORE VERIFYING IN SIMULATOR ---

G90          ; Absolute coordinates
G20          ; Inches
G17          ; XY plane
G54          ; Work offset 1

N10 G0 X0.5 Y0 Z1.0     ; Rapid to circle start (3 o'clock), clearance
N20 M3 S1000             ; Spindle CW at 1000 RPM
N30 G1 Z-0.1 F10         ; Plunge to depth
N40 G3 X0.5 Y0 I-0.5 J0  ; CCW full circle, center at (0,0)
                           ; Start at (0.5, 0), center offset = (-0.5, 0)
N50 G0 Z1.0              ; Retract to clearance
N60 M5                   ; Spindle stop
N70 M9                   ; Coolant off
N80 G30                  ; Return to reference (home) — Fanuc
                           ; For GRBL use: G0 X0 Y0 (after confirming position)
N90 M30                  ; Program end
