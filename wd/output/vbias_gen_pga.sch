v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
C {devices/iopin.sym} 560 440 0 0 {name=p1 lab=VBIAS}
C {devices/iopin.sym} 560 480 0 0 {name=p2 lab=IBIAS}
C {devices/iopin.sym} 120 940 3 0 {name=p3 lab=VSS}
C {spice_v.sym} 200 660 0 0 {name=VIBIAS value=0}
C {sky130_fd_pr__nfet_g5v0d10v5.sym} 200 260 0 0 {name=XM4 L=1 W=5 nf=1 m=1}
C {sky130_fd_pr__res_generic_m1.sym} 200 460 0 0 {name=R1 W=1 L=0.08 m=1}
N 380 440 480 440 {lab=IBIAS}
N 480 440 480 480 {}
N 480 480 560 480 {}
N 380 200 380 680 {lab=VBIAS}
N 560 440 380 440 {}
N 380 280 380 940 {lab=VSS}
N 120 940 380 940 {}
N 380 480 380 640 {lab=net1}
