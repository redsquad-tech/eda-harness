* sky130 starter OPA core for NASP-style requirements
* no AZ / latch / output switch / test switch blocks
* intended as an architectural prototype only
* use the biasable core first; the self-biased wrapper is only a convenience starter

.SUBCKT DiffpairP_14x3
+ INP INN OUTP OUTN TAIL VDD VSS

rshort_p
+ TAIL srcp
+ 0.001

rshort_n
+ TAIL srcn
+ 0.001

xmp
+ OUTP INP srcp VDD
+ sky130_fd_pr__pfet_01v8
+ w='14' l='3' nf='1'

xmn
+ OUTN INN srcn VDD
+ sky130_fd_pr__pfet_01v8
+ w='14' l='3' nf='1'

.ENDS

.SUBCKT PTailSource_5x6
+ OUT VBP VDD VSS

xtail
+ OUT VBP VDD VDD
+ sky130_fd_pr__pfet_01v8
+ w='5' l='6' nf='1'

.ENDS

.SUBCKT NMirrorLoadCascode_4x8_2x4
+ REFH OUTH VBN VDD VSS

xmn_ref
+ nrefb nrefb VSS VSS
+ sky130_fd_pr__nfet_01v8
+ w='4' l='8' nf='1'

xmn_out
+ noutb nrefb VSS VSS
+ sky130_fd_pr__nfet_01v8
+ w='4' l='8' nf='1'

xmc_ref
+ REFH VBN nrefb VSS
+ sky130_fd_pr__nfet_01v8
+ w='2' l='4' nf='1'

xmc_out
+ OUTH VBN noutb VSS
+ sky130_fd_pr__nfet_01v8
+ w='2' l='4' nf='1'

.ENDS

.SUBCKT Stage1_PInput_CascLoad
+ VINP VINN VX VTAIL VBN1 VDD VSS

xxdp
+ VINP VINN vref1 VX VTAIL VDD VSS
+ DiffpairP_14x3

xxload
+ vref1 VX VBN1 VDD VSS
+ NMirrorLoadCascode_4x8_2x4

.ENDS

.SUBCKT Stage2_NCommonSource
+ VX VOUT VBP2 VDD VSS

xmp2
+ VOUT VBP2 VDD VDD
+ sky130_fd_pr__pfet_01v8
+ w='8' l='12' nf='1'

xmn2
+ VOUT VX VSS VSS
+ sky130_fd_pr__nfet_01v8
+ w='8' l='6' nf='1'

.ENDS

.SUBCKT MillerRzCc_120k_0p4p
+ N1 N2 VSS

xrz
+ N1 ncc VSS
+ sky130_fd_pr__res_xhigh_po_0p35
+ l='21' mult='1' m='1'

xcc
+ ncc N2
+ sky130_fd_pr__cap_mim_m3_1
+ w='14.142' l='14.142' mf='1'

.ENDS

.SUBCKT PBiasTailRef
+ VBP VDD VSS

xpd
+ VBP VBP VDD VDD
+ sky130_fd_pr__pfet_01v8
+ w='2' l='2' nf='1'

xrb
+ VBP VSS VSS
+ sky130_fd_pr__res_xhigh_po_0p35
+ l='75' mult='1' m='1'

.ENDS

.SUBCKT PBiasStage2Ref
+ VBP VDD VSS

xpd
+ VBP VBP VDD VDD
+ sky130_fd_pr__pfet_01v8
+ w='2' l='2' nf='1'

xrb
+ VBP VSS VSS
+ sky130_fd_pr__res_xhigh_po_0p35
+ l='120' mult='1' m='1'

.ENDS

.SUBCKT NBiasCascodeRef
+ VBN VDD VSS

xrb
+ VDD VBN VSS
+ sky130_fd_pr__res_xhigh_po_0p35
+ l='55' mult='1' m='1'

xnd
+ VBN VBN VSS VSS
+ sky130_fd_pr__nfet_01v8
+ w='1' l='1' nf='1'

.ENDS

* Biasable core. Prefer this one for real tuning.
* Suggested starting DC targets at 1.8 V prototype:
*   VTAIL = 1.30..1.45 V
*   VX    = 0.75..0.95 V
*   VOUT  = 0.80..1.00 V
* If .op does not land there, retune VBP1 / VBN1 / VBP2 before trusting AC.
.SUBCKT OpampCoreNoAz_biasable
+ VINP VINN VOUT VBP1 VBN1 VBP2 VDD VSS

x_tail
+ vtail VBP1 VDD VSS
+ PTailSource_5x6

x_stage1
+ VINP VINN vx vtail VBN1 VDD VSS
+ Stage1_PInput_CascLoad

x_stage2
+ vx vout_int VBP2 VDD VSS
+ Stage2_NCommonSource

x_comp
+ vx vout_int VSS
+ MillerRzCc_120k_0p4p

vvout_link
+ vout_int VOUT
+ dc '0'
+ ac '0'

.ENDS

* Standalone starter wrapper.
* This is just a first boot option; do not sign off the wrapper blindly.
.SUBCKT OpampCoreNoAz
+ VINP VINN VOUT VDD VSS

x_bp1
+ vbp1 VDD VSS
+ PBiasTailRef

x_bn1
+ vbn1 VDD VSS
+ NBiasCascodeRef

x_bp2
+ vbp2 VDD VSS
+ PBiasStage2Ref

x_core
+ VINP VINN VOUT vbp1 vbn1 vbp2 VDD VSS
+ OpampCoreNoAz_biasable

.ENDS
