v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
C {devices/iopin.sym} 920 880 0 0 {name=p1 lab=VD}
C {devices/iopin.sym} 120 40 1 0 {name=p2 lab=DVDD}
C {devices/iopin.sym} 920 920 0 0 {name=p3 lab=VIRTOUT}
C {devices/iopin.sym} 920 960 0 0 {name=p4 lab=CMOUT}
C {devices/iopin.sym} 920 1000 0 0 {name=p5 lab=R2RIN}
C {devices/iopin.sym} 920 1040 0 0 {name=p6 lab=R2ROUT}
C {devices/iopin.sym} 120 1940 3 0 {name=p7 lab=DVSS}
C {devices/iopin.sym} 180 40 1 0 {name=p8 lab=AVDD}
C {devices/iopin.sym} 180 1940 3 0 {name=p9 lab=AVSS}
C {T_Gate_5V.sym} 440 1160 0 0 {name=x12}
C {T_Gate_5V.sym} 440 1360 0 0 {name=x13}
C {spice_v.sym} 200 1660 0 0 {name=VI12 value=0}
C {spice_v.sym} 200 260 0 0 {name=VI1 value=0}
C {spice_v.sym} 200 460 0 0 {name=VI2 value=0}
C {spice_v.sym} 200 660 0 0 {name=VI3 value=0}
C {spice_v.sym} 200 860 0 0 {name=VI4 value=0}
C {xschem_verilog_import/sky130_fd_sc_hvl__lsbuflv2hv_1.sym} 440 560 0 0 {name=x1}
C {sky130_fd_sc_hvl__inv_1.sym} 440 960 0 0 {name=x2}
C {sky130_fd_pr__res_xhigh_po_0p35.sym} 200 1060 0 0 {name=XR1 L=20 mult=1 m=1}
C {sky130_fd_pr__res_xhigh_po_0p35.sym} 200 1460 0 0 {name=XR3 L=20 mult=1 m=1}
C {sky130_fd_pr__res_xhigh_po_0p35.sym} 200 1260 0 0 {name=XR2 L=20 mult=1 m=1}
C {sky130_fd_sc_hvl__diode_2.sym} 440 760 0 0 {name=x3}
N 620 40 620 1340 {lab=AVDD}
N 180 40 620 40 {}
N 440 1140 620 1140 {}
N 440 1340 620 1340 {}
N 740 620 620 620 {}
N 740 640 620 640 {}
N 380 1100 380 1940 {lab=AVSS}
N 180 1940 380 1940 {}
N 440 1380 380 1380 {}
N 440 1580 380 1580 {}
N 380 480 640 480 {lab=CMOUT}
N 640 480 640 960 {}
N 640 960 920 960 {}
N 120 40 360 40 {lab=DVDD}
N 360 40 360 560 {}
N 360 560 600 560 {}
N 620 580 620 1940 {lab=DVSS}
N 120 1940 620 1940 {}
N 740 580 620 580 {}
N 740 600 620 600 {}
N 380 840 640 840 {lab=R2RIN}
N 640 840 640 1000 {}
N 640 1000 920 1000 {}
N 380 280 640 280 {lab=R2ROUT}
N 640 280 640 1040 {}
N 640 1040 920 1040 {}
N 620 560 620 880 {lab=VD}
N 600 560 620 560 {}
N 920 880 620 880 {}
N 620 1060 620 1380 {lab=VDBAR}
N 620 660 620 1340 {lab=VDbuf}
N 740 660 620 660 {}
N 380 680 640 680 {lab=VIRTOUT}
N 640 680 640 920 {}
N 640 920 920 920 {}
N 620 1220 620 1460 {lab=VX}
N 380 1460 620 1460 {}
N 380 240 380 1640 {lab=net1}
N 380 880 380 1260 {lab=net2}
N 380 1060 380 1420 {lab=net3}
N 380 1020 380 1680 {lab=net4}
N 380 440 500 440 {lab=net5}
N 500 440 500 1300 {}
N 500 1300 620 1300 {}
N 380 640 500 640 {lab=net6}
N 500 640 500 1100 {}
N 500 1100 620 1100 {}
