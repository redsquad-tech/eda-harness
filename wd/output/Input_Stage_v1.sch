v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
C {devices/iopin.sym} 120 40 1 0 {name=p1 lab=AVDD}
C {devices/iopin.sym} 800 1160 0 0 {name=p2 lab=VINP}
C {devices/iopin.sym} 800 1200 0 0 {name=p3 lab=VOUT1}
C {devices/iopin.sym} 800 1240 0 0 {name=p4 lab=VINN}
C {devices/iopin.sym} 800 1280 0 0 {name=p5 lab=CM}
C {devices/iopin.sym} 120 2540 3 0 {name=p6 lab=AVSS}
C {devices/iopin.sym} 800 1320 0 0 {name=p7 lab=VBIAS}
C {spice_v.sym} 440 1060 0 0 {name=VI13 value=0}
C {spice_v.sym} 440 1260 0 0 {name=VI2 value=0}
C {spice_v.sym} 440 1460 0 0 {name=VI3 value=0}
C {spice_v.sym} 200 2260 0 0 {name=VI1 value=0}
C {spice_v.sym} 200 1460 0 0 {name=VI4 value=0}
C {Input_Stage_OA1.sym} 200 660 0 0 {name=x1}
C {Input_Stage_OA1.sym} 200 860 0 0 {name=x2}
C {Input_Stage_OA2.sym} 200 1260 0 0 {name=x3}
C {sky130_fd_pr__res_xhigh_po_0p35.sym} 200 460 0 0 {name=XR7 L=860 mult=1 m=1}
C {sky130_fd_pr__res_xhigh_po_0p35.sym} 200 260 0 0 {name=XR5 L=860 mult=1 m=1}
C {sky130_fd_pr__res_xhigh_po_0p35.sym} 200 1060 0 0 {name=XR6 L=278 mult=1 m=1}
C {sky130_fd_pr__res_xhigh_po_0p35.sym} 200 1860 0 0 {name=XR8 L=278 mult=1 m=1}
C {sky130_fd_pr__res_xhigh_po_0p35.sym} 200 2060 0 0 {name=XR9 L=34.5 mult=1 m=1}
C {sky130_fd_pr__res_xhigh_po_0p35.sym} 200 1660 0 0 {name=XR10 L=34.5 mult=1 m=1}
N 620 40 620 1440 {lab=AVDD}
N 120 40 620 40 {}
N 380 300 380 2540 {lab=AVSS}
N 120 2540 380 2540 {}
N 200 880 380 880 {}
N 200 1080 380 1080 {}
N 200 1480 380 1480 {}
N 380 260 380 1280 {lab=CM}
N 800 1280 380 1280 {}
N 380 720 380 1320 {lab=VBIAS}
N 800 1320 380 1320 {}
N 380 460 380 1240 {lab=VINN}
N 800 1240 380 1240 {}
N 380 220 380 1160 {lab=VINP}
N 800 1160 380 1160 {}
N 380 600 380 2060 {lab=VONEG}
N 380 800 380 1660 {lab=VOPOS}
N 380 1480 600 1480 {lab=VOUT1}
N 600 1480 600 1200 {}
N 600 1200 800 1200 {}
N 380 1060 380 1620 {lab=net1}
N 380 1240 380 2020 {lab=net2}
N 380 1820 380 2240 {lab=net3}
N 380 1200 380 2280 {lab=net4}
N 200 640 400 640 {lab=net5}
N 400 640 400 1080 {}
N 400 1080 620 1080 {}
N 200 1240 400 1240 {lab=net6}
N 400 1240 400 1280 {}
N 400 1280 620 1280 {}
N 200 840 400 840 {lab=net7}
N 400 840 400 1480 {}
N 400 1480 620 1480 {}
