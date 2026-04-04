v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
C {devices/iopin.sym} 800 360 0 0 {name=p1 lab=V[9]}
C {devices/iopin.sym} 800 400 0 0 {name=p2 lab=V[8]}
C {devices/iopin.sym} 800 440 0 0 {name=p3 lab=V[7]}
C {devices/iopin.sym} 800 480 0 0 {name=p4 lab=V[6]}
C {devices/iopin.sym} 800 520 0 0 {name=p5 lab=V[5]}
C {devices/iopin.sym} 800 560 0 0 {name=p6 lab=V[4]}
C {devices/iopin.sym} 800 600 0 0 {name=p7 lab=V[3]}
C {devices/iopin.sym} 800 640 0 0 {name=p8 lab=V[2]}
C {devices/iopin.sym} 800 680 0 0 {name=p9 lab=V[1]}
C {devices/iopin.sym} 800 720 0 0 {name=p10 lab=V[0]}
C {devices/ipin.sym} 40 80 0 0 {name=p11 lab=VCM}
C {devices/ipin.sym} 40 120 0 0 {name=p12 lab=IBIAS}
C {devices/iopin.sym} 120 40 1 0 {name=p13 lab=AVDD}
C {devices/ipin.sym} 40 160 0 0 {name=p14 lab=VINN}
C {devices/iopin.sym} 180 40 1 0 {name=p15 lab=DVDD}
C {devices/opin.sym} 800 1020 2 0 {name=p16 lab=VOUT}
C {devices/iopin.sym} 120 1140 3 0 {name=p17 lab=AVSS}
C {devices/iopin.sym} 180 1140 3 0 {name=p18 lab=DVSS}
C {devices/ipin.sym} 40 200 0 0 {name=p19 lab=VINP}
C {Parallel_10B_Block2.sym} 440 260 0 0 {name=x1}
C {Input_Stage_v1.sym} 440 460 0 0 {name=x2}
C {spice_v.sym} 440 860 0 0 {name=VI2 value=0}
C {vbias_gen_pga.sym} 440 660 0 0 {name=x3}
N 460 40 460 840 {lab=AVDD}
N 120 40 460 40 {}
N 620 840 460 840 {}
N 440 720 440 1140 {lab=AVSS}
N 120 1140 440 1140 {}
N 460 880 440 880 {}
N 180 40 300 40 {lab=DVDD}
N 300 40 300 240 {}
N 300 240 420 240 {}
N 180 1140 300 1140 {lab=DVSS}
N 300 1140 300 880 {}
N 300 880 420 880 {}
N 40 120 320 120 {lab=IBIAS}
N 320 120 320 680 {}
N 320 680 620 680 {}
N 620 520 620 640 {lab=VBIAS}
N 620 80 620 500 {lab=VCM}
N 40 80 620 80 {}
N 40 160 320 160 {lab=VINN}
N 320 160 320 460 {}
N 320 460 620 460 {}
N 40 200 320 200 {lab=VINP}
N 320 200 320 380 {}
N 320 380 620 380 {}
N 620 200 620 420 {lab=VO1}
N 620 240 720 240 {lab=VOUT}
N 720 240 720 1020 {}
N 720 1020 800 1020 {}
N 620 440 720 440 {lab=V[0]}
N 720 440 720 720 {}
N 720 720 800 720 {}
N 620 400 720 400 {lab=V[1]}
N 720 400 720 680 {}
N 720 680 800 680 {}
N 620 360 720 360 {lab=V[2]}
N 720 360 720 640 {}
N 720 640 800 640 {}
N 620 320 720 320 {lab=V[3]}
N 720 320 720 600 {}
N 720 600 800 600 {}
N 620 280 720 280 {lab=V[4]}
N 720 280 720 560 {}
N 720 560 800 560 {}
N 620 40 720 40 {lab=V[5]}
N 720 40 720 520 {}
N 720 520 800 520 {}
N 620 0 720 0 {lab=V[6]}
N 720 0 720 480 {}
N 720 480 800 480 {}
N 620 160 720 160 {lab=V[7]}
N 720 160 720 440 {}
N 720 440 800 440 {}
N 620 80 720 80 {lab=V[8]}
N 720 80 720 400 {}
N 720 400 800 400 {}
N 620 120 720 120 {lab=V[9]}
N 720 120 720 360 {}
N 720 360 800 360 {}
N 440 440 520 440 {lab=net1}
N 520 440 520 880 {}
N 520 880 620 880 {}
