* -----------------------------------------------------------------------------
* LDO_DAO Golden Behavioral Mock
* -----------------------------------------------------------------------------
* Purpose:
*   Drop-in runnable mock DUT for developing LDO_DAO acceptance testbenches.
*
* Important rules:
*   - Public subckt interface matches the verification plan.
*   - Testbenches must instantiate this mock exactly like the real DUT:
*
*       XDUT vdd_3v3 vout_1v2 vref_0v8 ibiasn_0u5 vfb_i vfb_o vss ldo_dao
*
*   - Do not pass mock-specific parameters through XDUT.
*   - PVT and Monte Carlo variation are intentionally not modeled here.
*   - This mock is not a transistor-accurate LDO model.
*   - It is intended to pass nominal/ref/ibias/load/transient/AC smoke checks
*     and to validate testbench measurement/reporting logic.
*
* Expected external testbench setup:
*   - Normal closed-loop tests short vfb_o to vfb_i.
*   - Acceptance testbenches connect external COUT = 449 pF from vout_1v2 to vss.
*   - Static/dynamic output loads are applied by the testbench, not by the mock.
*   - ibiasn_0u5 is driven by injecting the specified current into this pin.
* -----------------------------------------------------------------------------

.subckt ldo_dao vdd_3v3 vout_1v2 vref_0v8 ibiasn_0u5 vfb_i vfb_o vss

* Internal behavioral parameters.
.param RFB_TOP=40k
.param RFB_BOT=80k
.param ROUT=1.0
.param PSRR_FEED=0.002

* Error amplifier behavioral parameters.
* GMERR*RCTRL gives about 50 V/V low-frequency error gain.
.param GMERR=50u
.param RCTRL=1meg
.param CCTRL=1.6p
* Soft-limiting terms improve transient numerical robustness of the mock.
.param ERR_LIM_V=50m
.param CTRL_LIM_V=300m

* Bias and quiescent-current behavior.
* RBIAS gives about 0.5 V at ibiasn_0u5 for 400 nA injected into the pin.
.param RBIAS=1.25meg
.param IQ_BASE=2.0u
.param IQ_BIAS_GAIN=0.2u

* Feedback divider.
* vfb_o is approximately 2/3 * vout_1v2, so vout_1v2 ~= 1.2 V
* when vfb_o/vfb_i regulates to vref_0v8 ~= 0.8 V.
RFBT vout_1v2 vfb_o {RFB_TOP}
RFBB vfb_o vss {RFB_BOT}

* Weak leakage path for convergence if vfb_i is not shorted in a malformed deck.
RVFBI_LEAK vfb_i vss 1e12

* Bias input emulation.
* The external current source should inject current into ibiasn_0u5.
RBIASPIN ibiasn_0u5 vss {RBIAS}

* Quiescent supply current.
* Current is drawn from vdd_3v3 into vss. The small dependence on ibiasn_0u5
* makes ibias sweeps visible in reports without requiring any mock-only params.
BIQ vdd_3v3 vss I={IQ_BASE + IQ_BIAS_GAIN*(V(ibiasn_0u5,vss)/0.5)}

* Error amplifier / loop-control node.
* First-order response gives AC/stability tests a real pole and finite loop gain.
* Limit error drive to avoid unrealistic integrator wind-up in long transients.
* Sign is chosen for negative feedback in ngspice current-source convention.
BERR ctrl vss I={-GMERR*tanh((V(vref_0v8,vss)-V(vfb_i,vss))/ERR_LIM_V)}
RCTRLNODE ctrl vss {RCTRL}
CCTRLNODE ctrl vss {CCTRL}

* Regulated source and output resistance.
* Feed-forward term sets target near 1.5*vref_0v8.
* Feedback correction term uses ctrl.
* Small vdd feedthrough provides finite PSRR behavior.
* ROUT gives finite output impedance for static/dynamic load tests.
* Limit control contribution so the mock remains bounded during large-signal stress.
BREG vreg vss V={1.5*V(vref_0v8,vss) + CTRL_LIM_V*tanh(V(ctrl,vss)/CTRL_LIM_V) + PSRR_FEED*(V(vdd_3v3,vss)-3.3)}

ROUTREG vreg vout_1v2 {ROUT}

* Weak output leakage for numerical robustness.
ROUT_LEAK vout_1v2 vss 1e9

.ends ldo_dao
