* LDO_DAO dynamic-load transient fixture.
* Parameters are supplied by run_all.sh: TB_VDD, TB_VREF, TB_IBIAS,
* TB_ILOAD_DC, TB_ILOAD_PULSE, TB_TSTART, TB_TPW, TB_TPER, TB_COUT_VAL.

V_VSS      vss       0      0
V_VDD      vdd_3v3   vss    {TB_VDD}
V_VREF     vref_0v8  vss    {TB_VREF}
I_IBIAS    vss       ibiasn_0u5  {TB_IBIAS}

R_FBSHORT  vfb_o     vfb_i  1m
COUT       vout_1v2  vss    {TB_COUT_VAL}

I_LOAD_DC  vout_1v2  vss    {TB_ILOAD_DC}
V_GATE_DYN gate_dyn  vss    PULSE(0 1 {TB_TSTART} 20p 20p {TB_TPW} {TB_TPER})
G_LOAD_DYN vout_1v2  vss    gate_dyn vss {TB_ILOAD_PULSE}

XDUT vdd_3v3 vout_1v2 vref_0v8 ibiasn_0u5 vfb_i vfb_o vss ldo_dao_test_dut

.save v(vout_1v2) v(vdd_3v3) v(gate_dyn) i(V_VDD)
