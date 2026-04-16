* starter sterile bench for OpampCoreNoAz_biasable
* add your PDK model includes before running

.include opamp_core_no_az_sky130.spice

VDD   VDD   0 1.8
VBP1  VBP1  0 1.28
VBN1  VBN1  0 0.78
VBP2  VBP2  0 1.18

VINP  VINP  0 dc 0.90 ac 0.5
VINN  VINN  0 dc 0.90 ac -0.5

XU0
+ VINP VINN VOUT VBP1 VBN1 VBP2 VDD 0
+ OpampCoreNoAz_biasable

CL
+ VOUT 0
+ 1p

*.probe v(VOUT) v(vx)
.op
.ac dec 50 1 100MEG
.end
