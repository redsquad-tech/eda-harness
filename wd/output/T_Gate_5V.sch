v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
C {devices/iopin.sym} 800 1000 0 0 {name=p1 lab=UPPER}
C {devices/iopin.sym} 800 1040 0 0 {name=p2 lab=PGATE}
C {devices/iopin.sym} 800 1080 0 0 {name=p3 lab=NGATE}
C {devices/iopin.sym} 800 1120 0 0 {name=p4 lab=LOWER}
C {devices/iopin.sym} 120 2140 3 0 {name=p5 lab=AVSS}
C {devices/iopin.sym} 120 40 1 0 {name=p6 lab=AVDD}
C {spice_v.sym} 200 1860 0 0 {name=VI6 value=0}
C {spice_v.sym} 200 1260 0 0 {name=VI1 value=0}
C {spice_v.sym} 200 1460 0 0 {name=VI2 value=0}
C {spice_v.sym} 200 1660 0 0 {name=VI3 value=0}
C {sky130_fd_pr__nfet_g5v0d10v5.sym} 200 1060 0 0 {name=XM1 L=0.5 W=1 nf=1 m=1}
C {sky130_fd_pr__pfet_g5v0d10v5.sym} 440 1060 0 0 {name=XM2 L=0.5 W=1 nf=1 m=1}
C {spice_v.sym} 200 260 0 0 {name=VI4 value=0}
C {spice_v.sym} 200 460 0 0 {name=VI5 value=0}
C {spice_v.sym} 200 660 0 0 {name=VI7 value=0}
C {spice_v.sym} 200 860 0 0 {name=VI8 value=0}
N 120 40 360 40 {lab=AVDD}
N 360 40 360 1120 {}
N 360 1120 620 1120 {}
N 120 2140 240 2140 {lab=AVSS}
N 240 2140 240 1120 {}
N 240 1120 380 1120 {}
N 380 440 600 440 {lab=LOWER}
N 600 440 600 1120 {}
N 600 1120 800 1120 {}
N 380 880 600 880 {lab=NGATE}
N 600 880 600 1080 {}
N 600 1080 800 1080 {}
N 380 640 600 640 {lab=PGATE}
N 600 640 600 1040 {}
N 600 1040 800 1040 {}
N 380 280 600 280 {lab=UPPER}
N 600 280 600 1000 {}
N 600 1000 800 1000 {}
N 380 1080 380 1880 {lab=net1}
N 380 480 380 1840 {lab=net2}
N 380 1280 500 1280 {lab=net3}
N 500 1280 500 1000 {}
N 500 1000 620 1000 {}
N 380 240 380 1680 {lab=net4}
N 380 1000 380 1640 {lab=net5}
N 380 1440 500 1440 {lab=net6}
N 500 1440 500 1080 {}
N 500 1080 620 1080 {}
N 380 840 380 1040 {lab=net7}
N 380 680 500 680 {lab=net8}
N 500 680 500 1040 {}
N 500 1040 620 1040 {}
