from pathlib import Path
import re

import hdl21 as h
import numpy as np
import sky130_hdl21
from hdl21.sim import Save, SaveMode, Sim, Tran
from vlsirtools.spice import ResultFormat, SimOptions, SupportedSimulators

from components import extract_subckt_name, print_metrics_table, require_sky130_install, run_ngspice_sim


VERIFICATION_PLAN = {
    "structural": {
        "specification_aspect": "generator/export contract",
        "category": "structural",
        "test_name": "run_structural_checks",
        "analysis_type": "generator/elaboration/export",
        "extracted_metrics": ["generator call", "elaboration", "subckt name", "MOS presence"],
        "pass_fail_rule": "all structural checks pass",
        "required_corners": [],
        "required_operating_conditions": [],
        "monte_carlo_required": False,
    },
    "tran_smoke_tt": {
        "specification_aspect": "two-phase non-overlap clock behavior",
        "category": "contract",
        "test_name": "run_tran_test",
        "analysis_type": "Tran",
        "extracted_metrics": ["phi1 max", "phi2 max", "max overlap"],
        "pass_fail_rule": "both phases switch and overlap stays low",
        "required_corners": ["TT"],
        "required_operating_conditions": ["pulse clock over several cycles"],
        "monte_carlo_required": False,
    },
}


def _mos_primitive(name: str):
    return getattr(sky130_hdl21.primitives, name)


def _mos_params(w: h.Scalar, l: h.Scalar):
    return sky130_hdl21.Sky130MosParams(w=w, l=l, nf=1, mult=1)


def _default_ngspice_options(test_name: str) -> SimOptions:
    return SimOptions(
        simulator=SupportedSimulators.NGSPICE,
        fmt=ResultFormat.SIM_DATA,
        rundir=f"./tmp/{test_name}",
    )


def _corner_to_hdl21(corner: str):
    corner_map = {
        "TT": h.pdk.Corner.TYP,
        "FF": h.pdk.Corner.FAST,
        "SS": h.pdk.Corner.SLOW,
    }
    try:
        return corner_map[corner]
    except KeyError as err:
        raise ValueError(f"Unsupported corner {corner}; currently supported: TT, FF, SS") from err


def _waveform(result, node: str):
    tran = result.an[0]
    target = f"v(xtop.{node.lower()})"
    for key, data in tran.data.items():
        if key.lower() == target:
            return np.asarray(data, dtype=float)
    raise RuntimeError(f"Waveform {node} not found in result keys: {list(tran.data.keys())}")


def _inv_module(name: str, scale: float) -> h.Module:
    nmos = _mos_primitive("NMOS_1p8V_STD")
    pmos = _mos_primitive("PMOS_1p8V_STD")
    npar = _mos_params(0.65 * scale, 0.15)
    ppar = _mos_params(1.0 * scale, 0.15)

    mod = h.Module(name=name)
    mod.A = h.Port()
    mod.Y = h.Port()
    mod.VDD = h.Port()
    mod.VSS = h.Port()
    mod.n = nmos(npar)(d=mod.Y, g=mod.A, s=mod.VSS, b=mod.VSS)
    mod.p = pmos(ppar)(d=mod.Y, g=mod.A, s=mod.VDD, b=mod.VDD)
    return mod


def _nand2_module(name: str, scale: float) -> h.Module:
    nmos = _mos_primitive("NMOS_1p8V_STD")
    pmos = _mos_primitive("PMOS_1p8V_STD")
    npar = _mos_params(0.65 * scale, 0.15)
    ppar = _mos_params(1.0 * scale, 0.15)

    mod = h.Module(name=name)
    mod.A = h.Port()
    mod.B = h.Port()
    mod.Y = h.Port()
    mod.VDD = h.Port()
    mod.VSS = h.Port()
    mod.n_mid = h.Signal(name="n_mid")

    mod.p0 = pmos(ppar)(d=mod.Y, g=mod.A, s=mod.VDD, b=mod.VDD)
    mod.p1 = pmos(ppar)(d=mod.Y, g=mod.B, s=mod.VDD, b=mod.VDD)
    mod.n0 = nmos(npar)(d=mod.Y, g=mod.A, s=mod.n_mid, b=mod.VSS)
    mod.n1 = nmos(npar)(d=mod.n_mid, g=mod.B, s=mod.VSS, b=mod.VSS)
    return mod


def _and2_module(name: str, scale: float) -> h.Module:
    nand2 = _nand2_module(f"{name}_nand2", scale)
    inv = _inv_module(f"{name}_inv", scale)

    mod = h.Module(name=name)
    mod.A = h.Port()
    mod.B = h.Port()
    mod.Y = h.Port()
    mod.VDD = h.Port()
    mod.VSS = h.Port()
    mod.yb = h.Signal(name="yb")
    mod.nand = nand2(A=mod.A, B=mod.B, Y=mod.yb, VDD=mod.VDD, VSS=mod.VSS)
    mod.buf = inv(A=mod.yb, Y=mod.Y, VDD=mod.VDD, VSS=mod.VSS)
    return mod


@h.paramclass
class NonoverlapClkParams:
    style = h.Param(dtype=str, desc="Implementation style; only cmos is supported", default="cmos")
    t_dead = h.Param(dtype=h.Scalar, desc="Target dead time in s; design intent only", default=1e-9)
    duty = h.Param(dtype=h.Scalar, desc="Target duty cycle; design intent only", default=0.5)
    buf_stages = h.Param(dtype=int, desc="Number of delay buffers per path", default=2)
    inv_ratio = h.Param(dtype=h.Scalar, desc="Per-stage inverter scaling ratio", default=1.5)
    trf = h.Param(dtype=h.Scalar, desc="Target edge rate in s; design intent only", default=100e-12)


@h.paramclass
class NonoverlapClkTranTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    v_clk_lo = h.Param(dtype=h.Scalar, desc="Clock low level in V", default=0.0)
    v_clk_hi = h.Param(dtype=h.Scalar, desc="Clock high level in V", default=1.8)
    period = h.Param(dtype=h.Scalar, desc="Clock period in s", default=20e-9)
    rise = h.Param(dtype=h.Scalar, desc="Clock rise time in s", default=100e-12)
    fall = h.Param(dtype=h.Scalar, desc="Clock fall time in s", default=100e-12)
    width = h.Param(dtype=h.Scalar, desc="Clock high width in s", default=10e-9)
    delay = h.Param(dtype=h.Scalar, desc="Clock delay in s", default=0.0)
    tstop = h.Param(dtype=h.Scalar, desc="Transient stop time in s", default=80e-9)
    tstep = h.Param(dtype=h.Scalar, desc="Transient step in s", default=50e-12)


@h.generator
def nonoverlap_clk(params: NonoverlapClkParams) -> h.Module:
    if params.style != "cmos":
        raise ValueError(f"Unsupported style: {params.style}")
    if params.buf_stages < 1:
        raise ValueError(f"buf_stages must be >= 1, got {params.buf_stages}")
    if params.inv_ratio <= 0:
        raise ValueError(f"inv_ratio must be > 0, got {params.inv_ratio}")

    mod = h.Module(name="NonoverlapClk")
    mod.CLK_IN, mod.PHI1, mod.PHI1B, mod.PHI2, mod.PHI2B, mod.VDD, mod.VSS = h.Ports(7)
    mod.clkb = h.Signal(name="clkb")
    mod.clk_d = h.Signal(name="clk_d")
    mod.clkb_d = h.Signal(name="clkb_d")
    mod.clk_d_b = h.Signal(name="clk_d_b")
    mod.clkb_d_b = h.Signal(name="clkb_d_b")

    mod.inv_clk = _inv_module("NonoverlapInvClk", 1.0)(
        A=mod.CLK_IN, Y=mod.clkb, VDD=mod.VDD, VSS=mod.VSS
    )

    prev_clk = mod.CLK_IN
    for idx in range(2 * params.buf_stages):
        next_sig = mod.clk_d if idx == 2 * params.buf_stages - 1 else h.Signal(name=f"clk_d_{idx}")
        if idx != 2 * params.buf_stages - 1:
            setattr(mod, f"clk_d_{idx}", next_sig)
        scale = float(params.inv_ratio) ** idx
        stage = _inv_module(f"ClkDelayInv_{idx}", scale)
        setattr(mod, f"clk_delay_inv_{idx}", stage(A=prev_clk, Y=next_sig, VDD=mod.VDD, VSS=mod.VSS))
        prev_clk = next_sig

    prev_clkb = mod.clkb
    for idx in range(2 * params.buf_stages):
        next_sig = mod.clkb_d if idx == 2 * params.buf_stages - 1 else h.Signal(name=f"clkb_d_{idx}")
        if idx != 2 * params.buf_stages - 1:
            setattr(mod, f"clkb_d_{idx}", next_sig)
        scale = float(params.inv_ratio) ** idx
        stage = _inv_module(f"ClkbDelayInv_{idx}", scale)
        setattr(mod, f"clkb_delay_inv_{idx}", stage(A=prev_clkb, Y=next_sig, VDD=mod.VDD, VSS=mod.VSS))
        prev_clkb = next_sig

    and2 = _and2_module("NonoverlapAnd2", 1.0)
    inv = _inv_module("NonoverlapInvOut", 1.0)
    mod.inv_clk_d = inv(A=mod.clk_d, Y=mod.clk_d_b, VDD=mod.VDD, VSS=mod.VSS)
    mod.inv_clkb_d = inv(A=mod.clkb_d, Y=mod.clkb_d_b, VDD=mod.VDD, VSS=mod.VSS)
    mod.gen_phi1 = and2(A=mod.CLK_IN, B=mod.clkb_d_b, Y=mod.PHI1, VDD=mod.VDD, VSS=mod.VSS)
    mod.gen_phi2 = and2(A=mod.clkb, B=mod.clk_d_b, Y=mod.PHI2, VDD=mod.VDD, VSS=mod.VSS)
    mod.gen_phi1b = inv(A=mod.PHI1, Y=mod.PHI1B, VDD=mod.VDD, VSS=mod.VSS)
    mod.gen_phi2b = inv(A=mod.PHI2, Y=mod.PHI2B, VDD=mod.VDD, VSS=mod.VSS)

    return mod


def build_tran_test(
    dut_params: NonoverlapClkParams,
    tb_params: NonoverlapClkTranTbParams | None = None,
    *,
    corner: str,
) -> Sim:
    tb_params = tb_params or NonoverlapClkTranTbParams()
    install = require_sky130_install()
    dut = nonoverlap_clk(dut_params)

    @h.module
    class Tb:
        VSS = h.Port()
        clk_in, phi1, phi1b, phi2, phi2b, vdd = h.Signals(6)
        vvdd = h.Vdc(dc=tb_params.vdd)(p=vdd, n=VSS)
        vclk = h.Vpulse(
            v1=tb_params.v_clk_lo,
            v2=tb_params.v_clk_hi,
            delay=tb_params.delay,
            rise=tb_params.rise,
            fall=tb_params.fall,
            width=tb_params.width,
            period=tb_params.period,
        )(p=clk_in, n=VSS)
        xdut = dut(CLK_IN=clk_in, PHI1=phi1, PHI1B=phi1b, PHI2=phi2, PHI2B=phi2b, VDD=vdd, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Tran(tstop=tb_params.tstop, tstep=tb_params.tstep),
            Save(SaveMode.ALL),
            install.include(_corner_to_hdl21(corner)),
        ],
    )


def run_tran_test(
    dut_params: NonoverlapClkParams | None = None,
    tb_params: NonoverlapClkTranTbParams | None = None,
    *,
    corner: str = "TT",
    sim_options=None,
):
    dut_params = dut_params or NonoverlapClkParams()
    sim = build_tran_test(dut_params, tb_params, corner=corner)
    return run_ngspice_sim(
        sim,
        sim_options if sim_options is not None else _default_ngspice_options("nonoverlap_clk_tran"),
    )


def run_all_tests(
    dut_params: NonoverlapClkParams | None = None,
    *,
    sim_options=None,
):
    dut_params = dut_params or NonoverlapClkParams()
    structural = run_structural_checks(dut_params)
    tran_result = run_tran_test(dut_params, sim_options=sim_options)
    phi1 = _waveform(tran_result, "phi1")
    phi2 = _waveform(tran_result, "phi2")
    return {
        "structural": structural,
        "tran_smoke": {
            "phi1_max": float(np.max(phi1)),
            "phi2_max": float(np.max(phi2)),
            "max_overlap": float(np.max(np.minimum(phi1, phi2))),
        },
    }


def print_test_report(
    dut_params: NonoverlapClkParams | None = None,
    *,
    sim_options=None,
):
    results = run_all_tests(dut_params, sim_options=sim_options)
    print_metrics_table(results, title="nonoverlap_clk")
    return results


def elaborate_dut(params: NonoverlapClkParams | None = None) -> h.Module:
    params = params or NonoverlapClkParams()
    return h.elaborate(nonoverlap_clk(params))


def export_spice(path: str | Path, params: NonoverlapClkParams | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mod = elaborate_dut(params)
    with path.open("w") as f:
        h.netlist(mod, f, fmt="spice")
    return path


def run_structural_checks(params: NonoverlapClkParams | None = None):
    params = params or NonoverlapClkParams()
    dut = nonoverlap_clk(params)
    mod = elaborate_dut(params)
    netlist_path = Path("./tmp/nonoverlap_clk_structural/nonoverlap_clk.sp")
    export_spice(netlist_path, params)
    text = netlist_path.read_text()
    subckt_name = extract_subckt_name(text)
    top_level_prefix = mod.name.split("(", 1)[0]
    top_level_present = re.search(rf"^\.SUBCKT\s+{re.escape(top_level_prefix)}", text, flags=re.MULTILINE) is not None

    checks = {
        "generator_call": dut is not None,
        "elaboration": mod is not None,
        "subckt_name": subckt_name is not None,
        "top_level_subckt": top_level_present,
        "contains_nmos": "sky130_fd_pr__nfet_01v8" in text,
        "contains_pmos": "sky130_fd_pr__pfet_01v8" in text,
    }
    if not all(checks.values()):
        raise RuntimeError(f"Structural checks failed: {checks}")
    return checks
