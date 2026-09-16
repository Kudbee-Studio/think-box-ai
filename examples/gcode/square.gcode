; square.gcode — Cut a 2" x 2" square (0.1" deep)
; Drill: Day 2 — Motion modes (G0, G1)
; GRBL/LinuxCNC compatible
; --- NEVER DRY-RUN THIS BEFORE VERIFYING IN SIMULATOR ---

G90          ; Absolute coordinates
G20          ; Inches
G17          ; XY plane
G54          ; Work offset 1

N10 G0 X0 Y0 Z1.0     ; Rapid to start, clearance height
N20 M3 S1000           ; Spindle CW at 1000 RPM
N30 G1 Z-0.1 F10       ; Plunge to depth (0.1" cut)
N40 G1 X2.0 F10        ; Cut along bottom edge (2" long)
N50 G1 Y2.0 F10        ; Cut along right edge (2" long)
N60 G1 X0 Y2.0 F10     ; Cut along top edge
N70 G1 X0 Y0 F10       ; Cut along left edge (close)
N80 G0 Z1.0            ; Retract to clearance
N90 M5                 ; Spindle stop
N100 M9                ; Coolant off
N110 G91 G0 X0 Y0      ; Return home in incremental (verify you're at 0,0)
N120 G90               ; Back to absolute
N130 M30               ; Program end
