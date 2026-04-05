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
        "metrics": ["generator call", "elaboration", "subckt name", "NMOS presence"],
        "rule": "all structural checks pass",
        "corners": [],
        "sweeps": [],
        "monte_carlo": False,
    },
    "balanced_op_tt": {
        "test": "run_balanced_test",
        "analysis": "Op",
        "metrics": ["v(outp)", "v(outn)", "abs(v(outp)-v(outn))"],
        "rule": "balanced input keeps output mismatch low",
        "corners": ["TT"],
        "sweeps": [],
        "monte_carlo": False,
    },
    "steer_op_tt": {
        "test": "run_steer_test",
        "analysis": "Op",
        "metrics": ["v(outp)", "v(outn)", "v(outn)-v(outp)"],
        "rule": "higher VINP steers more current to OUTP branch and lowers OUTP",
        "corners": ["TT"],
        "sweeps": [],
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
class DiffpairNParams:
    dev_in = h.Param(dtype=str, desc="SKY130 NMOS primitive name", default="NMOS_1p8V_STD")
    w_in = h.Param(dtype=h.Scalar, desc="Input-device width in um", default=1.0)
    l_in = h.Param(dtype=h.Scalar, desc="Input-device length in um", default=0.15)
    nf_in = h.Param(dtype=int, desc="Input-device fingers", default=1)
    m_in = h.Param(dtype=int, desc="Input-device multiplier", default=1)
    body_tie = h.Param(dtype=str, desc="NMOS body tie strategy: vss or tail", default="vss")
    use_degeneration = h.Param(dtype=bool, desc="Insert source degeneration resistors", default=False)
    r_deg = h.Param(dtype=h.Scalar, desc="Per-side degeneration resistance in ohm", default=100.0)


@h.paramclass
class DiffpairNBalancedTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    v_cm = h.Param(dtype=h.Scalar, desc="Input common-mode voltage in V", default=0.9)
    i_tail = h.Param(dtype=h.Scalar, desc="Tail current in A", default=100e-6)
    r_load = h.Param(dtype=h.Scalar, desc="Per-side load resistance to VDD in ohm", default=20e3)


@h.paramclass
class DiffpairNSteerTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    v_cm = h.Param(dtype=h.Scalar, desc="Input common-mode voltage in V", default=0.9)
    v_diff = h.Param(dtype=h.Scalar, desc="Differential input voltage in V", default=20e-3)
    i_tail = h.Param(dtype=h.Scalar, desc="Tail current in A", default=100e-6)
    r_load = h.Param(dtype=h.Scalar, desc="Per-side load resistance to VDD in ohm", default=20e3)


@h.generator
def diffpair_n(params: DiffpairNParams) -> h.Module:
    if params.body_tie not in ("vss", "tail"):
        raise ValueError(f"Unsupported body_tie: {params.body_tie}")
    if params.w_in <= 0 or params.l_in <= 0:
        raise ValueError("w_in and l_in must be positive")
    if params.nf_in < 1 or params.m_in < 1:
        raise ValueError("nf_in and m_in must be >= 1")
    if params.use_degeneration and params.r_deg <= 0:
        raise ValueError("r_deg must be positive when use_degeneration is enabled")

    nmos = _mos_primitive(params.dev_in)
    npar = _mos_params(params.w_in, params.l_in, params.nf_in, params.m_in)

    mod = h.Module(name="DiffpairN")
    mod.INP, mod.INN, mod.OUTP, mod.OUTN, mod.TAIL, mod.VDD, mod.VSS = h.Ports(7)
    mod.srcp = h.Signal(name="srcp")
    mod.srcn = h.Signal(name="srcn")

    if params.use_degeneration:
        mod.rdeg_p = h.Res(r=params.r_deg)(p=mod.srcp, n=mod.TAIL)
        mod.rdeg_n = h.Res(r=params.r_deg)(p=mod.srcn, n=mod.TAIL)
    else:
        mod.short_p = h.Res(r=1e-3)(p=mod.srcp, n=mod.TAIL)
        mod.short_n = h.Res(r=1e-3)(p=mod.srcn, n=mod.TAIL)

    body_node = mod.VSS if params.body_tie == "vss" else mod.TAIL
    mod.mp = nmos(npar)(d=mod.OUTP, g=mod.INP, s=mod.srcp, b=body_node)
    mod.mn = nmos(npar)(d=mod.OUTN, g=mod.INN, s=mod.srcn, b=body_node)
    return mod


def build_balanced_test(
    dut_params: DiffpairNParams,
    tb_params: DiffpairNBalancedTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
) -> Sim:
    tb_params = tb_params or DiffpairNBalancedTbParams()
    install = require_sky130_install()
    dut = diffpair_n(dut_params)

    @h.module
    class Tb:
        VSS = h.Port()
        inp, inn, outp, outn, tail, vdd = h.Signals(6)
        vvdd = h.Vdc(dc=tb_params.vdd)(p=vdd, n=VSS)
        vvinp = h.Vdc(dc=tb_params.v_cm)(p=inp, n=VSS)
        vvinn = h.Vdc(dc=tb_params.v_cm)(p=inn, n=VSS)
        i_tail = h.Idc(dc=tb_params.i_tail)(p=tail, n=VSS)
        rload_p = h.Res(r=tb_params.r_load)(p=vdd, n=outp)
        rload_n = h.Res(r=tb_params.r_load)(p=vdd, n=outn)
        xdut = dut(INP=inp, INN=inn, OUTP=outp, OUTN=outn, TAIL=tail, VDD=vdd, VSS=VSS)

    return Sim(tb=Tb, attrs=[Op(), Save(SaveMode.ALL), install.include(corner)])


def build_steer_test(
    dut_params: DiffpairNParams,
    tb_params: DiffpairNSteerTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
) -> Sim:
    tb_params = tb_params or DiffpairNSteerTbParams()
    install = require_sky130_install()
    dut = diffpair_n(dut_params)
    vinp = tb_params.v_cm + 0.5 * tb_params.v_diff
    vinn = tb_params.v_cm - 0.5 * tb_params.v_diff

    @h.module
    class Tb:
        VSS = h.Port()
        inp, inn, outp, outn, tail, vdd = h.Signals(6)
        vvdd = h.Vdc(dc=tb_params.vdd)(p=vdd, n=VSS)
        vvinp = h.Vdc(dc=vinp)(p=inp, n=VSS)
        vvinn = h.Vdc(dc=vinn)(p=inn, n=VSS)
        i_tail = h.Idc(dc=tb_params.i_tail)(p=tail, n=VSS)
        rload_p = h.Res(r=tb_params.r_load)(p=vdd, n=outp)
        rload_n = h.Res(r=tb_params.r_load)(p=vdd, n=outn)
        xdut = dut(INP=inp, INN=inn, OUTP=outp, OUTN=outn, TAIL=tail, VDD=vdd, VSS=VSS)

    return Sim(tb=Tb, attrs=[Op(), Save(SaveMode.ALL), install.include(corner)])


def run_balanced_test(
    dut_params: DiffpairNParams | None = None,
    tb_params: DiffpairNBalancedTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options=None,
):
    dut_params = dut_params or DiffpairNParams()
    sim = build_balanced_test(dut_params, tb_params, corner=corner)
    result = run_ngspice_sim(
        sim,
        sim_options if sim_options is not None else _default_ngspice_options("diffpair_n_balanced"),
    )
    v_outp = _op_scalar(result, "v(xtop.outp)")
    v_outn = _op_scalar(result, "v(xtop.outn)")
    return {
        "v_outp": v_outp,
        "v_outn": v_outn,
        "delta_abs": abs(v_outp - v_outn),
    }


def run_steer_test(
    dut_params: DiffpairNParams | None = None,
    tb_params: DiffpairNSteerTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options=None,
):
    dut_params = dut_params or DiffpairNParams()
    sim = build_steer_test(dut_params, tb_params, corner=corner)
    result = run_ngspice_sim(
        sim,
        sim_options if sim_options is not None else _default_ngspice_options("diffpair_n_steer"),
    )
    v_outp = _op_scalar(result, "v(xtop.outp)")
    v_outn = _op_scalar(result, "v(xtop.outn)")
    return {
        "v_outp": v_outp,
        "v_outn": v_outn,
        "v_outn_minus_v_outp": v_outn - v_outp,
    }


def run_all_tests(
    dut_params: DiffpairNParams | None = None,
    *,
    sim_options=None,
):
    dut_params = dut_params or DiffpairNParams()
    return {
        "structural": run_structural_checks(dut_params),
        "balanced_op": run_balanced_test(dut_params, sim_options=sim_options),
        "steer_op": run_steer_test(dut_params, sim_options=sim_options),
    }


def print_test_report(
    dut_params: DiffpairNParams | None = None,
    *,
    sim_options=None,
):
    results = run_all_tests(dut_params, sim_options=sim_options)
    print_metrics_table(results, title="diffpair_n")
    return results


def elaborate_dut(params: DiffpairNParams | None = None) -> h.Module:
    params = params or DiffpairNParams()
    return h.elaborate(diffpair_n(params))


def export_spice(path: str | Path, params: DiffpairNParams | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mod = elaborate_dut(params)
    with path.open("w") as f:
        h.netlist(mod, f, fmt="spice")
    return path


def run_structural_checks(params: DiffpairNParams | None = None):
    params = params or DiffpairNParams()
    dut = diffpair_n(params)
    mod = elaborate_dut(params)
    netlist_path = Path("./tmp/diffpair_n_structural/diffpair_n.sp")
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
    }
    if not all(checks.values()):
        raise RuntimeError(f"Structural checks failed: {checks}")
    return checks
