* LDO_DAO PSRR AC fixture.
* Parameters are supplied by run_all.sh: TB_VDD, TB_VREF, TB_IBIAS,
* TB_COUT_VAL.

V_VSS      vss       0      0
V_VDD      vdd_3v3   vss    DC {TB_VDD} AC 1
V_VREF     vref_0v8  vss    {TB_VREF}
I_IBIAS    vss       ibiasn_0u5  {TB_IBIAS}

R_FBSHORT  vfb_o     vfb_i  1m
COUT       vout_1v2  vss    {TB_COUT_VAL}
I_LOAD_DC  vout_1v2  vss    15u

XDUT vdd_3v3 vout_1v2 vref_0v8 ibiasn_0u5 vfb_i vfb_o vss ldo_dao_test_dut

.save v(vdd_3v3) v(vout_1v2)
