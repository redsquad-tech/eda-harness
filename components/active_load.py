from pathlib import Path
import re

import hdl21 as h
import sky130_hdl21
from hdl21.sim import Op, Save, SaveMode, Sim
from vlsirtools.spice import SimOptions, SupportedSimulators

from components import extract_subckt_name, print_metrics_table, require_sky130_install, run_ngspice_sim


VERIFICATION_PLAN = {
    "structural": {
        "test": "run_structural_checks",
        "analysis": "generator/elaboration/export",
        "metrics": ["generator call", "elaboration", "subckt name", "device presence"],
        "rule": "all structural checks pass",
        "corners": [],
        "sweeps": [],
        "monte_carlo": False,
    },
    "balanced_op_tt": {
        "test": "run_balanced_test",
        "analysis": "Op",
        "metrics": ["v(outp)", "v(outn)", "abs(v(outp)-v(outn))"],
        "rule": "balanced reference currents keep outputs close",
        "corners": ["TT"],
        "sweeps": [],
        "monte_carlo": False,
    },
    "steer_op_tt": {
        "test": "run_steer_test",
        "analysis": "Op",
        "metrics": ["v(outp)", "v(outn)", "output delta"],
        "rule": "output ordering follows reference-current ordering and cross-coupling mode",
        "corners": ["TT"],
        "sweeps": ["i_ref_p", "i_ref_n"],
        "monte_carlo": False,
    },
}


def _mos_primitive(name: str):
    try:
        return getattr(sky130_hdl21.primitives, name)
    except AttributeError as err:
        raise ValueError(f"Unsupported SKY130 primitive: {name}") from err


def _mos_params(w: h.Scalar, l: h.Scalar, nf: int, mult: int):
    return sky130_hdl21.Sky130MosParams(w=w, l=l, nf=nf, mult=mult)


def _default_ngspice_options(test_name: str) -> SimOptions:
    return SimOptions(
        simulator=SupportedSimulators.NGSPICE,
        rundir=f"./tmp/{test_name}",
    )


def _op_scalar(result, signal_name: str) -> float:
    op = result.an[0].op
    target = signal_name.lower()
    for name, value in zip(op.signals, op.data):
        if name.lower() == target:
            return float(value)
    raise RuntimeError(f"Signal {signal_name} not found in op result: {list(op.signals)}")


@h.paramclass
class ActiveLoadParams:
    device_type = h.Param(dtype=str, desc="Load polarity: n or p", default="p")
    style = h.Param(dtype=str, desc="Topology: mirror, diode, or cascoded", default="mirror")
    dev_load = h.Param(dtype=str, desc="SKY130 primitive name for load devices", default="PMOS_1p8V_STD")
    ratio = h.Param(dtype=h.Scalar, desc="Output-device width ratio relative to reference branch", default=1.0)
    w_load = h.Param(dtype=h.Scalar, desc="Load-device width in um", default=1.0)
    l_load = h.Param(dtype=h.Scalar, desc="Load-device length in um", default=0.15)
    nf_load = h.Param(dtype=int, desc="Load-device fingers", default=1)
    m_load = h.Param(dtype=int, desc="Load-device multiplier", default=1)
    cross_coupled = h.Param(dtype=bool, desc="Swap mirror control across branches", default=False)


@h.paramclass
class ActiveLoadBalancedTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    i_ref_p = h.Param(dtype=h.Scalar, desc="Reference current on INP branch in A", default=20e-6)
    i_ref_n = h.Param(dtype=h.Scalar, desc="Reference current on INN branch in A", default=20e-6)
    r_load = h.Param(dtype=h.Scalar, desc="Per-side output load resistance in ohm", default=20e3)


@h.paramclass
class ActiveLoadSteerTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    i_ref_p = h.Param(dtype=h.Scalar, desc="Reference current on INP branch in A", default=30e-6)
    i_ref_n = h.Param(dtype=h.Scalar, desc="Reference current on INN branch in A", default=10e-6)
    r_load = h.Param(dtype=h.Scalar, desc="Per-side output load resistance in ohm", default=20e3)


@h.generator
def active_load(params: ActiveLoadParams) -> h.Module:
    if params.device_type not in ("n", "p"):
        raise ValueError(f"Unsupported device_type: {params.device_type}")
    if params.style not in ("mirror", "diode", "cascoded"):
        raise ValueError(f"Unsupported style: {params.style}")
    if params.ratio <= 0:
        raise ValueError("ratio must be positive")
    if params.w_load <= 0 or params.l_load <= 0:
        raise ValueError("w_load and l_load must be positive")
    if params.nf_load < 1 or params.m_load < 1:
        raise ValueError("nf_load and m_load must be >= 1")

    prim = _mos_primitive(params.dev_load)
    ref_par = _mos_params(params.w_load, params.l_load, params.nf_load, params.m_load)
    out_par = _mos_params(params.w_load * params.ratio, params.l_load, params.nf_load, params.m_load)

    mod = h.Module(name="ActiveLoad")
    mod.INP, mod.INN, mod.OUTP, mod.OUTN, mod.VDD, mod.VSS = h.Ports(6)

    outp_gate = mod.INN if params.cross_coupled else mod.INP
    outn_gate = mod.INP if params.cross_coupled else mod.INN

    if params.device_type == "p":
        if params.style == "diode":
            mod.m_ref_p = prim(ref_par)(d=mod.INP, g=mod.INP, s=mod.VDD, b=mod.VDD)
            mod.m_ref_n = prim(ref_par)(d=mod.INN, g=mod.INN, s=mod.VDD, b=mod.VDD)
            mod.short_p = h.Res(r=1e-3)(p=mod.INP, n=mod.OUTP)
            mod.short_n = h.Res(r=1e-3)(p=mod.INN, n=mod.OUTN)
            return mod

        if params.style == "mirror":
            mod.m_ref_p = prim(ref_par)(d=mod.INP, g=mod.INP, s=mod.VDD, b=mod.VDD)
            mod.m_ref_n = prim(ref_par)(d=mod.INN, g=mod.INN, s=mod.VDD, b=mod.VDD)
            mod.m_out_p = prim(out_par)(d=mod.OUTP, g=outp_gate, s=mod.VDD, b=mod.VDD)
            mod.m_out_n = prim(out_par)(d=mod.OUTN, g=outn_gate, s=mod.VDD, b=mod.VDD)
            return mod

        mod.inp_mid = h.Signal(name="inp_mid")
        mod.inn_mid = h.Signal(name="inn_mid")
        mod.outp_mid = h.Signal(name="outp_mid")
        mod.outn_mid = h.Signal(name="outn_mid")
        mod.m_ref_p_top = prim(ref_par)(d=mod.INP, g=mod.INP, s=mod.VDD, b=mod.VDD)
        mod.m_ref_p_bot = prim(ref_par)(d=mod.inp_mid, g=mod.INP, s=mod.VDD, b=mod.VDD)
        mod.short_ref_p = h.Res(r=1e-3)(p=mod.INP, n=mod.inp_mid)
        mod.m_ref_n_top = prim(ref_par)(d=mod.INN, g=mod.INN, s=mod.VDD, b=mod.VDD)
        mod.m_ref_n_bot = prim(ref_par)(d=mod.inn_mid, g=mod.INN, s=mod.VDD, b=mod.VDD)
        mod.short_ref_n = h.Res(r=1e-3)(p=mod.INN, n=mod.inn_mid)
        mod.m_out_p_top = prim(out_par)(d=mod.OUTP, g=outp_gate, s=mod.VDD, b=mod.VDD)
        mod.m_out_p_bot = prim(out_par)(d=mod.outp_mid, g=outp_gate, s=mod.VDD, b=mod.VDD)
        mod.short_out_p = h.Res(r=1e-3)(p=mod.OUTP, n=mod.outp_mid)
        mod.m_out_n_top = prim(out_par)(d=mod.OUTN, g=outn_gate, s=mod.VDD, b=mod.VDD)
        mod.m_out_n_bot = prim(out_par)(d=mod.outn_mid, g=outn_gate, s=mod.VDD, b=mod.VDD)
        mod.short_out_n = h.Res(r=1e-3)(p=mod.OUTN, n=mod.outn_mid)
        return mod

    if params.style == "diode":
        mod.m_ref_p = prim(ref_par)(d=mod.INP, g=mod.INP, s=mod.VSS, b=mod.VSS)
        mod.m_ref_n = prim(ref_par)(d=mod.INN, g=mod.INN, s=mod.VSS, b=mod.VSS)
        mod.short_p = h.Res(r=1e-3)(p=mod.INP, n=mod.OUTP)
        mod.short_n = h.Res(r=1e-3)(p=mod.INN, n=mod.OUTN)
        return mod

    if params.style == "mirror":
        mod.m_ref_p = prim(ref_par)(d=mod.INP, g=mod.INP, s=mod.VSS, b=mod.VSS)
        mod.m_ref_n = prim(ref_par)(d=mod.INN, g=mod.INN, s=mod.VSS, b=mod.VSS)
        mod.m_out_p = prim(out_par)(d=mod.OUTP, g=outp_gate, s=mod.VSS, b=mod.VSS)
        mod.m_out_n = prim(out_par)(d=mod.OUTN, g=outn_gate, s=mod.VSS, b=mod.VSS)
        return mod

    mod.inp_mid = h.Signal(name="inp_mid")
    mod.inn_mid = h.Signal(name="inn_mid")
    mod.outp_mid = h.Signal(name="outp_mid")
    mod.outn_mid = h.Signal(name="outn_mid")
    mod.m_ref_p_top = prim(ref_par)(d=mod.INP, g=mod.INP, s=mod.inp_mid, b=mod.VSS)
    mod.m_ref_p_bot = prim(ref_par)(d=mod.inp_mid, g=mod.INP, s=mod.VSS, b=mod.VSS)
    mod.m_ref_n_top = prim(ref_par)(d=mod.INN, g=mod.INN, s=mod.inn_mid, b=mod.VSS)
    mod.m_ref_n_bot = prim(ref_par)(d=mod.inn_mid, g=mod.INN, s=mod.VSS, b=mod.VSS)
    mod.m_out_p_top = prim(out_par)(d=mod.OUTP, g=outp_gate, s=mod.outp_mid, b=mod.VSS)
    mod.m_out_p_bot = prim(out_par)(d=mod.outp_mid, g=outp_gate, s=mod.VSS, b=mod.VSS)
    mod.m_out_n_top = prim(out_par)(d=mod.OUTN, g=outn_gate, s=mod.outn_mid, b=mod.VSS)
    mod.m_out_n_bot = prim(out_par)(d=mod.outn_mid, g=outn_gate, s=mod.VSS, b=mod.VSS)
    return mod


def build_balanced_test(
    dut_params: ActiveLoadParams,
    tb_params: ActiveLoadBalancedTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
) -> Sim:
    tb_params = tb_params or ActiveLoadBalancedTbParams()
    install = require_sky130_install()
    dut = active_load(dut_params)

    @h.module
    class Tb:
        VSS = h.Port()
        inp, inn, outp, outn, vdd = h.Signals(5)
        vvdd = h.Vdc(dc=tb_params.vdd)(p=vdd, n=VSS)
        xdut = dut(INP=inp, INN=inn, OUTP=outp, OUTN=outn, VDD=vdd, VSS=VSS)

        if dut_params.device_type == "p":
            iref_p = h.Idc(dc=tb_params.i_ref_p)(p=inp, n=VSS)
            iref_n = h.Idc(dc=tb_params.i_ref_n)(p=inn, n=VSS)
            rload_p = h.Res(r=tb_params.r_load)(p=outp, n=VSS)
            rload_n = h.Res(r=tb_params.r_load)(p=outn, n=VSS)
        else:
            iref_p = h.Idc(dc=tb_params.i_ref_p)(p=vdd, n=inp)
            iref_n = h.Idc(dc=tb_params.i_ref_n)(p=vdd, n=inn)
            rload_p = h.Res(r=tb_params.r_load)(p=vdd, n=outp)
            rload_n = h.Res(r=tb_params.r_load)(p=vdd, n=outn)

    return Sim(tb=Tb, attrs=[Op(), Save(SaveMode.ALL), install.include(corner)])


def build_steer_test(
    dut_params: ActiveLoadParams,
    tb_params: ActiveLoadSteerTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
) -> Sim:
    tb_params = tb_params or ActiveLoadSteerTbParams()
    install = require_sky130_install()
    dut = active_load(dut_params)

    @h.module
    class Tb:
        VSS = h.Port()
        inp, inn, outp, outn, vdd = h.Signals(5)
        vvdd = h.Vdc(dc=tb_params.vdd)(p=vdd, n=VSS)
        xdut = dut(INP=inp, INN=inn, OUTP=outp, OUTN=outn, VDD=vdd, VSS=VSS)

        if dut_params.device_type == "p":
            iref_p = h.Idc(dc=tb_params.i_ref_p)(p=inp, n=VSS)
            iref_n = h.Idc(dc=tb_params.i_ref_n)(p=inn, n=VSS)
            rload_p = h.Res(r=tb_params.r_load)(p=outp, n=VSS)
            rload_n = h.Res(r=tb_params.r_load)(p=outn, n=VSS)
        else:
            iref_p = h.Idc(dc=tb_params.i_ref_p)(p=vdd, n=inp)
            iref_n = h.Idc(dc=tb_params.i_ref_n)(p=vdd, n=inn)
            rload_p = h.Res(r=tb_params.r_load)(p=vdd, n=outp)
            rload_n = h.Res(r=tb_params.r_load)(p=vdd, n=outn)

    return Sim(tb=Tb, attrs=[Op(), Save(SaveMode.ALL), install.include(corner)])


def run_balanced_test(
    dut_params: ActiveLoadParams | None = None,
    tb_params: ActiveLoadBalancedTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options=None,
):
    dut_params = dut_params or ActiveLoadParams()
    sim = build_balanced_test(dut_params, tb_params, corner=corner)
    result = run_ngspice_sim(
        sim,
        sim_options if sim_options is not None else _default_ngspice_options("active_load_balanced"),
    )
    v_outp = _op_scalar(result, "v(xtop.outp)")
    v_outn = _op_scalar(result, "v(xtop.outn)")
    return {
        "v_outp": v_outp,
        "v_outn": v_outn,
        "delta_abs": abs(v_outp - v_outn),
    }


def run_steer_test(
    dut_params: ActiveLoadParams | None = None,
    tb_params: ActiveLoadSteerTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options=None,
):
    dut_params = dut_params or ActiveLoadParams()
    sim = build_steer_test(dut_params, tb_params, corner=corner)
    result = run_ngspice_sim(
        sim,
        sim_options if sim_options is not None else _default_ngspice_options("active_load_steer"),
    )
    v_outp = _op_scalar(result, "v(xtop.outp)")
    v_outn = _op_scalar(result, "v(xtop.outn)")
    return {
        "v_outp": v_outp,
        "v_outn": v_outn,
        "delta": v_outp - v_outn,
    }


def run_all_tests(
    dut_params: ActiveLoadParams | None = None,
    *,
    sim_options=None,
):
    dut_params = dut_params or ActiveLoadParams()
    return {
        "structural": run_structural_checks(dut_params),
        "balanced_op": run_balanced_test(dut_params, sim_options=sim_options),
        "steer_op": run_steer_test(dut_params, sim_options=sim_options),
    }


def print_test_report(
    dut_params: ActiveLoadParams | None = None,
    *,
    sim_options=None,
):
    results = run_all_tests(dut_params, sim_options=sim_options)
    print_metrics_table(results, title="active_load")
    return results


def elaborate_dut(params: ActiveLoadParams | None = None) -> h.Module:
    params = params or ActiveLoadParams()
    return h.elaborate(active_load(params))


def export_spice(path: str | Path, params: ActiveLoadParams | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mod = elaborate_dut(params)
    with path.open("w") as f:
        h.netlist(mod, f, fmt="spice")
    return path


def run_structural_checks(params: ActiveLoadParams | None = None):
    params = params or ActiveLoadParams()
    dut = active_load(params)
    mod = elaborate_dut(params)
    netlist_path = Path("./tmp/active_load_structural/active_load.sp")
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
    }
    if params.device_type == "p":
        checks["contains_device"] = "sky130_fd_pr__pfet_01v8" in text
    else:
        checks["contains_device"] = "sky130_fd_pr__nfet_01v8" in text
    if params.style == "cascoded":
        checks["contains_mid_nodes"] = "inp_mid" in text and "outp_mid" in text
    if not all(checks.values()):
        raise RuntimeError(f"Structural checks failed: {checks}")
    return checks
