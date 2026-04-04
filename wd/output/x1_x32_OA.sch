v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
C {devices/iopin.sym} 120 40 1 0 {name=p1 lab=VDD}
C {devices/iopin.sym} 800 1840 0 0 {name=p2 lab=VOUT}
C {devices/iopin.sym} 800 1880 0 0 {name=p3 lab=VINN}
C {devices/iopin.sym} 800 1920 0 0 {name=p4 lab=VINP}
C {devices/iopin.sym} 800 1960 0 0 {name=p5 lab=VBIAS}
C {devices/iopin.sym} 120 3820 3 0 {name=p6 lab=VSS}
C {sky130_fd_pr__nfet_01v8_lvt.sym} 200 1460 0 0 {name=XM1 L=0.15 W=7.5 nf=1 m=1}
C {sky130_fd_pr__nfet_01v8_lvt.sym} 200 2060 0 0 {name=XM2 L=0.15 W=7.5 nf=1 m=1}
C {spice_v.sym} 200 2660 0 0 {name=VISink value=0}
C {sky130_fd_pr__pfet_01v8_lvt.sym} 200 3060 0 0 {name=XM6 L=5 W=20 nf=1 m=2}
C {sky130_fd_pr__pfet_01v8_lvt.sym} 200 3260 0 0 {name=XM7 L=5 W=20 nf=1 m=2}
C {spice_v.sym} 200 2260 0 0 {name=VD1 value=0}
C {spice_v.sym} 200 2460 0 0 {name=VID2 value=0}
C {spice_v.sym} 200 1060 0 0 {name=VID1 value=0}
C {spice_v.sym} 200 1260 0 0 {name=VID3 value=0}
C {spice_v.sym} 200 860 0 0 {name=VIBIAS value=0}
C {sky130_fd_pr__nfet_05v0_nvt.sym} 200 1660 0 0 {name=XM10 L=2 W=1 nf=1 m=25}
C {sky130_fd_pr__nfet_05v0_nvt.sym} 200 1860 0 0 {name=XM12 L=2 W=1 nf=1 m=25}
C {sky130_fd_pr__nfet_g5v0d10v5.sym} 200 460 0 0 {name=XM3 L=1 W=5 nf=1 m=15}
C {sky130_fd_pr__nfet_g5v0d10v5.sym} 200 660 0 0 {name=XM5 L=1 W=5 nf=1 m=100}
C {sky130_fd_pr__pfet_g5v0d10v5.sym} 200 3460 0 0 {name=XM8 L=0.5 W=10 nf=1 m=10}
C {spice_v.sym} 440 1860 0 0 {name=VIVDD value=0}
C {sky130_fd_pr__cap_mim_m3_1.sym} 200 2860 0 0 {name=XC1 W=10 L=10 m=15}
C {sky130_fd_pr__res_high_po_0p69.sym} 200 260 0 0 {name=XR1 L=41 mult=1 m=1}
N 380 840 600 840 {lab=VBIAS}
N 600 840 600 1960 {}
N 600 1960 800 1960 {}
N 120 40 360 40 {lab=VDD}
N 360 40 360 1840 {}
N 360 1840 620 1840 {}
N 380 1440 380 1880 {lab=VINN}
N 800 1880 380 1880 {}
N 380 1840 380 2040 {lab=VINP}
N 800 1920 380 1920 {}
N 380 260 380 1840 {lab=VOUT}
N 800 1840 380 1840 {}
N 380 300 380 3820 {lab=VSS}
N 120 3820 380 3820 {}
N 380 1480 380 2640 {lab=net1}
N 380 440 380 880 {lab=net10}
N 380 1240 380 3400 {lab=net11}
N 380 600 380 1080 {lab=net12}
N 380 220 380 2880 {lab=net13}
N 380 400 380 2680 {lab=net2}
N 380 1880 380 2000 {lab=net3}
N 380 1400 380 1720 {lab=net4}
N 380 2240 380 3240 {lab=net5}
N 380 1880 380 3520 {lab=net6}
N 620 1880 380 1880 {}
N 380 2440 380 3440 {lab=net7}
N 380 1600 380 2280 {lab=net8}
N 380 1800 380 2480 {lab=net9}
