* SKY130 ngspice port converted from GF55 Spectre point netlist LDO_DAO_netlist
* Intended as an acceptance-bench runnable example, not a layout-faithful migration.
.subckt ldo_dao vdd_3v3 vout_1v2 vref_0v8 ibiasn_0u5 vfb_i vfb_o vss
XMNd_7 vss vss vss vss sky130_fd_pr__nfet_01v8 w=2 l=0.5 nf=1 mult=1 m=1
XMNd_6 vss vss vss vss sky130_fd_pr__nfet_01v8 w=2 l=0.5 nf=1 mult=1 m=1
XMNd_5 vss vss vss vss sky130_fd_pr__nfet_01v8 w=2 l=0.5 nf=1 mult=1 m=1
XMNd_4 vss vss vss vss sky130_fd_pr__nfet_01v8 w=2 l=0.5 nf=1 mult=1 m=1
XMN2 net21 ibiasn_0u5 vss vss sky130_fd_pr__nfet_01v8 w=2 l=2 nf=1 mult=6 m=6
XMNbias ibiasn_0u5 ibiasn_0u5 vss vss sky130_fd_pr__nfet_01v8 w=2 l=2 nf=1 mult=2 m=2
XMN1 pmirr vfb_i net21 vss sky130_fd_pr__nfet_01v8 w=1 l=0.5 nf=2 mult=2 m=2
XMN0 ota_out vref_0v8 net21 vss sky130_fd_pr__nfet_01v8 w=1 l=0.5 nf=2 mult=2 m=2
XMNd_3 vss vss vss vss sky130_fd_pr__nfet_01v8 w=0.5 l=0.5 nf=1 mult=1 m=1
XMNd_2 vss vss vss vss sky130_fd_pr__nfet_01v8 w=0.5 l=0.5 nf=1 mult=1 m=1
XMNd_1 vss vss vss vss sky130_fd_pr__nfet_01v8 w=0.5 l=0.5 nf=1 mult=1 m=1
XMNd_0 vss vss vss vss sky130_fd_pr__nfet_01v8 w=0.5 l=0.5 nf=1 mult=1 m=1
RD0_ESD vss vref_0v8 1e12
RD1_ESD vss vfb_i 1e12
RR1 vout_1v2 vfb_o 40.0176K
RR2_0 net3 vss 40.0176K
RR2_1 vfb_o net3 40.0176K
CC1 ota_out vss 2.5f
XMP0 ota_out pmirr vdd_3v3 vdd_3v3 sky130_fd_pr__pfet_01v8 w=1.4 l=0.4 nf=1 mult=2 m=2
XMPMOS vout_1v2 ota_out vdd_3v3 vdd_3v3 sky130_fd_pr__pfet_01v8 w=1.4 l=0.4 nf=1 mult=4 m=4
XMPd_3 vdd_3v3 vdd_3v3 vdd_3v3 vdd_3v3 sky130_fd_pr__pfet_01v8 w=1.4 l=0.4 nf=1 mult=1 m=1
XMPd_2 vdd_3v3 vdd_3v3 vdd_3v3 vdd_3v3 sky130_fd_pr__pfet_01v8 w=1.4 l=0.4 nf=1 mult=1 m=1
XMPd_1 vdd_3v3 vdd_3v3 vdd_3v3 vdd_3v3 sky130_fd_pr__pfet_01v8 w=1.4 l=0.4 nf=1 mult=1 m=1
XMPd_0 vdd_3v3 vdd_3v3 vdd_3v3 vdd_3v3 sky130_fd_pr__pfet_01v8 w=1.4 l=0.4 nf=1 mult=1 m=1
XMP1 pmirr pmirr vdd_3v3 vdd_3v3 sky130_fd_pr__pfet_01v8 w=1.4 l=0.4 nf=1 mult=2 m=2
.ends ldo_dao
