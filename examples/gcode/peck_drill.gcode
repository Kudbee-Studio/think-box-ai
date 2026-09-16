; peck_drill.gcode — Drill 3 holes using G81 (standard) and G83 (peck)
; Drill: Day 8 — Canned cycles (G81/G83)
; 2 holes peck-drilled, 1 standard drilled — for comparison
; GRBL/LinuxCNC compatible (G83 may be unsupported on some GRBL versions — check your controller)
; --- NEVER DRY-RUN THIS BEFORE VERIFYING IN SIMULATOR ---

G90          ; Absolute coordinates
G20          ; Inches
G17          ; XY plane
G54          ; Work offset 1

N10 G0 X0.5 Y0.5 Z1.0     ; Rapid to first hole position, clearance
N20 M3 S2000                ; Spindle CW at 2000 RPM (drilling needs high RPM)
N30 G43 H01 Z1.0           ; Tool length compensation, safety height

; --- Hole 1: Standard peck drill (G83) ---
N40 G83 Z-1.0 R0.1 Q0.1 F10   ; Peck drill: depth=1", retract=0.1", peck=0.1", feed=10 IPM
N50 X1.5 Y0.5                  ; Drill second hole (still in G83 cycle)

; --- Hole 2: Standard drill (G81) ---
N60 G80                        ; CANCEL CANNED CYCLE (critical!)
N70 G0 X2.5 Y0.5 Z1.0         ; Move to third hole
N80 G81 Z-1.0 R0.1 F10         ; Standard drill cycle
N90 G80                        ; CANCEL CANNED CYCLE again

; --- Done drilling — retract and stop ---
N100 G0 Z1.0                   ; Move to clearance
N110 M5                        ; Spindle stop
N120 M9                        ; Coolant off
N130 M30                       ; Program end

; NOTES:
; G81 = standard drill cycle — full depth in one pass
; G83 = peck drill — retracts Q inches each pass to break chips
; G80 = ALWAYS cancel canned cycles before any non-cycle move
; R = retract plane (between holes, above workpiece)
; Q = (G83 only) depth per peck pass
