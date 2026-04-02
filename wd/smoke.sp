.lib ../pdks/sky130A/libs.tech/ngspice/sky130.lib.spice tt

Vd d 0 0.9
Vg g 0 0.9
Vs s 0 0
Vb b 0 0

M1 d g s b sky130_fd_pr__nfet_01v8 W=2 L=0.15 nf=4

.op
.end


