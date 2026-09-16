; pocket.gcode — 1" x 1" square pocket, 0.1" deep, 1" x 1" square outside
; Drill: Day 10 — Pocket milling with depth steps
; Tool: 0.25" end mill (hypothetical)
; Comments trace the toolpath so you can follow along by hand
; GRBL/LinuxCNC compatible
; --- NEVER DRY-RUN THIS BEFORE VERIFYING IN SIMULATOR ---

G90          ; Absolute coordinates
G20          ; Inches
G17          ; XY plane
G54          ; Work offset 1

N10 G0 X-0.5 Y-0.5 Z1.0    ; Rapid to pocket start (outside pocket), clearance
N20 M3 S800                 ; Spindle CW at 800 RPM (lower speed for milling)
N30 G43 H01 Z1.0            ; Tool length compensation

; ========== DEPTH PASS 1: Z = -0.1 ==========
N40 G1 Z-0.1 F10            ; Plunge to first depth (0.1" below top surface)
N50 G1 X0.5 F10             ; Cut to right edge of pocket (+1.0 in X)

; --- Contour around pocket bottom-right corner (0.25" radius) ---
N60 G2 X0.5 Y-0.5 I0 J0.25  ; CW arc to bottom-right corner
N70 G2 X-0.5 Y-0.5 I-0.25 J0 ; CW arc to bottom-left corner (continue)

; --- Contour around pocket bottom-left corner ---
N80 G1 Y0.5 F10             ; Cut up along left side
N90 G2 X-0.5 Y0.5 I0 J0.25  ; CW arc to top-left corner
N100 G2 X0.5 Y0.5 I0.25 J0  ; CW arc to top-right corner (close pocket)

; --- Back to start ---
N110 G0 Z1.0                ; Retract for next depth pass

; ========== DEPTH PASS 2: Z = -0.2 (deeper) ==========
N120 G1 Z-0.2 F10           ; Plunge to second depth (total 0.2")
N130 G1 X0.5 F10            ; Re-cut across bottom
N140 G2 X0.5 Y-0.5 I0 J0.25 ; Re-cut corner
N150 G2 X-0.5 Y-0.5 I-0.25 J0
N160 G1 Y0.5 F10
N170 G2 X-0.5 Y0.5 I0 J0.25
N180 G2 X0.5 Y0.5 I0.25 J0

; ========== DEPTH PASS 3: Z = -0.3 (final depth = 0.3") ==========
N190 G1 Z-0.3 F10
N200 G1 X0.5 F10
N210 G2 X0.5 Y-0.5 I0 J0.25
N220 G2 X-0.5 Y-0.5 I-0.25 J0
N230 G1 Y0.5 F10
N240 G2 X-0.5 Y0.5 I0 J0.25
N250 G2 X0.5 Y0.5 I0.25 J0

; ========== DONE — RETRACT AND STOP ==========
N260 G0 Z1.0                 ; Full retract above workpiece
N270 G0 X0 Y0                ; Return to XY home (verify position)
N280 M5                      ; Spindle stop
N290 M9                      ; Coolant off
N300 M30                     ; Program end

; HOW TO TRACE THIS BY HAND:
; 1. Draw a 1" x 1" square centered at (0,0), from (-0.5,-0.5) to (0.5,0.5)
; 2. Start at (-0.5, -0.5) — outside bottom-left corner
; 3. The tool plunges to Z=-0.1, then cuts along the bottom edge to (0.5, -0.5)
; 4. It rounds all four corners with 0.25" arcs, ending back at (0.5, 0.5)
; 5. Retract, plunge deeper, repeat the contour 3 times total
; 6. Final pocket depth is 0.3" below the workpiece top surface
