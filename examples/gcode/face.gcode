; face.gcode — Face a 2" x 2" workpiece, 0.1" depth per pass, 3 passes total
; Drill: Day 9 — Facing (Z-level clearing)
; GRBL/LinuxCNC compatible
; --- NEVER DRY-RUN THIS BEFORE VERIFYING IN SIMULATOR ---

G90          ; Absolute coordinates
G20          ; Inches
G17          ; XY plane
G54          ; Work offset 1

N10 G0 X-1.0 Y-1.0 Z1.0    ; Start outside workpiece, clearance height
N20 M3 S1000                ; Spindle CW at 1000 RPM

; --- Pass 1: depth Z = -0.1 ---
N30 G1 Z-0.1 F10            ; Plunge to first depth
N40 G1 X3.0 F10             ; Cut across in X (2" wide, from -1 to 3)
N50 G0 Z0.2                 ; Raise for next pass (0.1" higher)
N60 G1 Y3.0 F10             ; Cut back in Y (2" long, from -1 to 3)
N70 G0 Z0.3                 ; Raise for next pass

; --- Pass 2: depth Z = -0.2 ---
N80 G1 X-1.0 F10            ; Cut back in -X
N90 G0 Z0.4                 ; Raise for next pass
N100 G1 Y-1.0 F10           ; Cut back in -Y (close the loop)
N110 G0 Z0.5                 ; Raise for next pass

; --- Pass 3: depth Z = -0.3 ---
N120 G1 X3.0 F10            ; Final pass — across in X
N130 G0 Z0.6                 ; Raise
N140 G1 Y3.0 F10            ; Final pass — across in Y

N150 G0 Z1.0                ; Full retract
N160 M5                     ; Spindle stop
N170 M9                     ; Coolant off
N180 M30                    ; Program end
