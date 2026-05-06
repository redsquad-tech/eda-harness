* v4 output drive sink 25.0uA
.include "../../dut/neuron_core_oa_sky130.sp"
.lib __SKY130_LIB_SPICE__ tt
.temp 27

VVDD avdd1p2 0 DC 1.8
VVIP vinp 0 DC 0.9
VIREF in0u25_oa 0 DC 0
IIREF in0u25_oa 0 DC 0.25u
VDEN d_en_oa 0 DC 1.8
VDAZ d_az_oa 0 DC 0
VDINF d_inf_oa 0 DC 1.8
VDTR d_treset_oa 0 DC 0
VDTCKI d_tcki 0 DC 0
VDTDI d_tdi 0 DC 0
RVBASE vbase 0 1e12
RVFEED vfeed 0 1e12
RVTEST vtest 0 1e12
RDTCKO d_tcko 0 1e12
RDTDO d_tdo 0 1e12
VVINN vinn 0 DC 0
EFB vinn 0 vout 0 1
CLOAD vout 0 1p
RLOAD vout 0 1e9
ILOAD avdd1p2 vout DC 25.0u
XDUT avdd1p2 agnd vinp vinn vout in0u25_oa vbase vfeed d_en_oa d_az_oa d_inf_oa vtest d_treset_oa d_tcki d_tcko d_tdi d_tdo NeuronCoreOaSky130_4f6ed3d2a22f7fd4752668b8eace8b8f_
.save i(VVDD) v(vout)
.op
.end
