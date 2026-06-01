* LDO_DAO loop-stability AC fixture.
* Uses public vfb_o/vfb_i loop-break interface.
* Parameters are supplied by run_all.sh: TB_VDD, TB_VREF, TB_IBIAS,
* TB_COUT_VAL.

V_VSS      vss       0      0
V_VDD      vdd_3v3   vss    {TB_VDD}
V_VREF     vref_0v8  vss    {TB_VREF}
I_IBIAS    vss       ibiasn_0u5  {TB_IBIAS}

COUT       vout_1v2  vss    {TB_COUT_VAL}
I_LOAD_DC  vout_1v2  vss    15u

* DC-closed / AC-injected public loop break.
V_INJ      vfb_o     vfb_i   DC 0 AC 1

XDUT vdd_3v3 vout_1v2 vref_0v8 ibiasn_0u5 vfb_i vfb_o vss ldo_dao_test_dut

.save v(vfb_i) v(vfb_o) v(vout_1v2)
