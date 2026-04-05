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
    "mirror_op_tt": {
        "test": "run_mirror_test",
        "analysis": "Op",
        "metrics": ["v(out)", "i_out_est", "i_ref", "i_out_est / i_ref"],
        "rule": "output branch current should qualitatively track mirror ratio",
        "corners": ["TT"],
        "sweeps": [],
        "monte_carlo": False,
    },
    "ratio_order_tt": {
        "test": "run_ratio_order_test",
        "analysis": "Op",
        "metrics": ["i_out_est at low ratio", "i_out_est at high ratio"],
        "rule": "higher ratio should increase mirrored output current",
        "corners": ["TT"],
        "sweeps": ["ratio"],
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
class CurrentMirrorParams:
    device_type = h.Param(dtype=str, desc="Mirror polarity: n or p", default="n")
    style = h.Param(dtype=str, desc="Topology: simple, cascoded, or wide_swing", default="simple")
    dev_ref = h.Param(dtype=str, desc="SKY130 primitive name for reference-side devices", default="NMOS_1p8V_STD")
    dev_out = h.Param(dtype=str, desc="SKY130 primitive name for output-side devices", default="NMOS_1p8V_STD")
    ratio = h.Param(dtype=h.Scalar, desc="Current ratio relative to reference branch", default=1.0)
    w_ref = h.Param(dtype=h.Scalar, desc="Reference-device width in um", default=1.0)
    l_ref = h.Param(dtype=h.Scalar, desc="Reference-device length in um", default=0.15)
    nf_ref = h.Param(dtype=int, desc="Reference-device fingers", default=1)
    m_ref = h.Param(dtype=int, desc="Reference-device multiplier", default=1)
    w_out = h.Param(dtype=h.Scalar, desc="Output-device width in um", default=1.0)
    l_out = h.Param(dtype=h.Scalar, desc="Output-device length in um", default=0.15)
    nf_out = h.Param(dtype=int, desc="Output-device fingers", default=1)
    m_out = h.Param(dtype=int, desc="Output-device multiplier", default=1)


@h.paramclass
class CurrentMirrorOpTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    i_ref = h.Param(dtype=h.Scalar, desc="Reference current in A", default=20e-6)
    r_load = h.Param(dtype=h.Scalar, desc="Output load resistor in ohm", default=20e3)


@h.paramclass
class CurrentMirrorRatioOrderTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    i_ref = h.Param(dtype=h.Scalar, desc="Reference current in A", default=20e-6)
    r_load = h.Param(dtype=h.Scalar, desc="Output load resistor in ohm", default=20e3)
    ratio_lo = h.Param(dtype=h.Scalar, desc="Lower mirror ratio", default=1.0)
    ratio_hi = h.Param(dtype=h.Scalar, desc="Higher mirror ratio", default=2.0)


@h.generator
def current_mirror(params: CurrentMirrorParams) -> h.Module:
    if params.device_type not in ("n", "p"):
        raise ValueError(f"Unsupported device_type: {params.device_type}")
    if params.style not in ("simple", "cascoded", "wide_swing"):
        raise ValueError(f"Unsupported style: {params.style}")
    if params.ratio <= 0:
        raise ValueError("ratio must be positive")
    for name, value in (
        ("w_ref", params.w_ref),
        ("l_ref", params.l_ref),
        ("w_out", params.w_out),
        ("l_out", params.l_out),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be positive")
    for name, value in (
        ("nf_ref", params.nf_ref),
        ("m_ref", params.m_ref),
        ("nf_out", params.nf_out),
        ("m_out", params.m_out),
    ):
        if value < 1:
            raise ValueError(f"{name} must be >= 1")

    ref_prim = _mos_primitive(params.dev_ref)
    out_prim = _mos_primitive(params.dev_out)
    ref_par = _mos_params(params.w_ref, params.l_ref, params.nf_ref, params.m_ref)
    out_par = _mos_params(params.w_out * params.ratio, params.l_out, params.nf_out, params.m_out)

    mod = h.Module(name="CurrentMirror")
    mod.IN, mod.OUT, mod.VDD, mod.VSS = h.Ports(4)

    if params.device_type == "n":
        if params.style == "simple":
            mod.m_ref = ref_prim(ref_par)(d=mod.IN, g=mod.IN, s=mod.VSS, b=mod.VSS)
            mod.m_out = out_prim(out_par)(d=mod.OUT, g=mod.IN, s=mod.VSS, b=mod.VSS)
            return mod

        mod.ref_mid = h.Signal(name="ref_mid")
        mod.out_mid = h.Signal(name="out_mid")
        mod.m_ref_top = ref_prim(ref_par)(d=mod.IN, g=mod.IN, s=mod.ref_mid, b=mod.VSS)
        mod.m_ref_bot = ref_prim(ref_par)(d=mod.ref_mid, g=mod.IN, s=mod.VSS, b=mod.VSS)
        mod.m_out_top = out_prim(out_par)(d=mod.OUT, g=mod.IN, s=mod.out_mid, b=mod.VSS)
        mod.m_out_bot = out_prim(out_par)(d=mod.out_mid, g=mod.IN, s=mod.VSS, b=mod.VSS)
        return mod

    if params.style == "simple":
        mod.m_ref = ref_prim(ref_par)(d=mod.IN, g=mod.IN, s=mod.VDD, b=mod.VDD)
        mod.m_out = out_prim(out_par)(d=mod.OUT, g=mod.IN, s=mod.VDD, b=mod.VDD)
        return mod

    mod.ref_mid = h.Signal(name="ref_mid")
    mod.out_mid = h.Signal(name="out_mid")
    mod.m_ref_top = ref_prim(ref_par)(d=mod.IN, g=mod.IN, s=mod.VDD, b=mod.VDD)
    mod.m_ref_bot = ref_prim(ref_par)(d=mod.ref_mid, g=mod.IN, s=mod.VDD, b=mod.VDD)
    mod.short_ref = h.Res(r=1e-3)(p=mod.IN, n=mod.ref_mid)
    mod.m_out_top = out_prim(out_par)(d=mod.OUT, g=mod.IN, s=mod.VDD, b=mod.VDD)
    mod.m_out_bot = out_prim(out_par)(d=mod.out_mid, g=mod.IN, s=mod.VDD, b=mod.VDD)
    mod.short_out = h.Res(r=1e-3)(p=mod.OUT, n=mod.out_mid)
    return mod


def build_mirror_test(
    dut_params: CurrentMirrorParams,
    tb_params: CurrentMirrorOpTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
) -> Sim:
    tb_params = tb_params or CurrentMirrorOpTbParams()
    install = require_sky130_install()
    dut = current_mirror(dut_params)

    @h.module
    class Tb:
        VSS = h.Port()
        inn, out, vdd = h.Signals(3)
        vvdd = h.Vdc(dc=tb_params.vdd)(p=vdd, n=VSS)
        xdut = dut(IN=inn, OUT=out, VDD=vdd, VSS=VSS)

        if dut_params.device_type == "n":
            iref = h.Idc(dc=tb_params.i_ref)(p=vdd, n=inn)
            rload = h.Res(r=tb_params.r_load)(p=vdd, n=out)
        else:
            iref = h.Idc(dc=tb_params.i_ref)(p=inn, n=VSS)
            rload = h.Res(r=tb_params.r_load)(p=out, n=VSS)

    return Sim(tb=Tb, attrs=[Op(), Save(SaveMode.ALL), install.include(corner)])


def run_mirror_test(
    dut_params: CurrentMirrorParams | None = None,
    tb_params: CurrentMirrorOpTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options=None,
):
    dut_params = dut_params or CurrentMirrorParams()
    tb_params = tb_params or CurrentMirrorOpTbParams()
    sim = build_mirror_test(dut_params, tb_params, corner=corner)
    result = run_ngspice_sim(
        sim,
        sim_options if sim_options is not None else _default_ngspice_options("current_mirror_op"),
    )
    v_out = _op_scalar(result, "v(xtop.out)")
    if dut_params.device_type == "n":
        i_out_est = max((tb_params.vdd - v_out) / tb_params.r_load, 0.0)
    else:
        i_out_est = max(v_out / tb_params.r_load, 0.0)
    ratio_est = i_out_est / tb_params.i_ref if tb_params.i_ref > 0 else float("nan")
    return {
        "v_out": v_out,
        "i_ref": float(tb_params.i_ref),
        "i_out_est": float(i_out_est),
        "ratio_est": float(ratio_est),
    }


def run_ratio_order_test(
    dut_params: CurrentMirrorParams | None = None,
    tb_params: CurrentMirrorRatioOrderTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options=None,
):
    dut_params = dut_params or CurrentMirrorParams()
    tb_params = tb_params or CurrentMirrorRatioOrderTbParams()

    lo = run_mirror_test(
        CurrentMirrorParams(
            device_type=dut_params.device_type,
            style=dut_params.style,
            dev_ref=dut_params.dev_ref,
            dev_out=dut_params.dev_out,
            ratio=tb_params.ratio_lo,
            w_ref=dut_params.w_ref,
            l_ref=dut_params.l_ref,
            nf_ref=dut_params.nf_ref,
            m_ref=dut_params.m_ref,
            w_out=dut_params.w_out,
            l_out=dut_params.l_out,
            nf_out=dut_params.nf_out,
            m_out=dut_params.m_out,
        ),
        CurrentMirrorOpTbParams(vdd=tb_params.vdd, i_ref=tb_params.i_ref, r_load=tb_params.r_load),
        corner=corner,
        sim_options=sim_options if sim_options is not None else _default_ngspice_options("current_mirror_ratio_lo"),
    )
    hi = run_mirror_test(
        CurrentMirrorParams(
            device_type=dut_params.device_type,
            style=dut_params.style,
            dev_ref=dut_params.dev_ref,
            dev_out=dut_params.dev_out,
            ratio=tb_params.ratio_hi,
            w_ref=dut_params.w_ref,
            l_ref=dut_params.l_ref,
            nf_ref=dut_params.nf_ref,
            m_ref=dut_params.m_ref,
            w_out=dut_params.w_out,
            l_out=dut_params.l_out,
            nf_out=dut_params.nf_out,
            m_out=dut_params.m_out,
        ),
        CurrentMirrorOpTbParams(vdd=tb_params.vdd, i_ref=tb_params.i_ref, r_load=tb_params.r_load),
        corner=corner,
        sim_options=sim_options if sim_options is not None else _default_ngspice_options("current_mirror_ratio_hi"),
    )
    return {
        "i_out_lo": lo["i_out_est"],
        "i_out_hi": hi["i_out_est"],
        "delta_i_out": hi["i_out_est"] - lo["i_out_est"],
    }


def run_all_tests(
    dut_params: CurrentMirrorParams | None = None,
    *,
    sim_options=None,
):
    dut_params = dut_params or CurrentMirrorParams()
    return {
        "structural": run_structural_checks(dut_params),
        "mirror_op": run_mirror_test(dut_params, sim_options=sim_options),
        "ratio_order": run_ratio_order_test(dut_params, sim_options=sim_options),
    }


def print_test_report(
    dut_params: CurrentMirrorParams | None = None,
    *,
    sim_options=None,
):
    results = run_all_tests(dut_params, sim_options=sim_options)
    print_metrics_table(results, title="current_mirror")
    return results


def elaborate_dut(params: CurrentMirrorParams | None = None) -> h.Module:
    params = params or CurrentMirrorParams()
    return h.elaborate(current_mirror(params))


def export_spice(path: str | Path, params: CurrentMirrorParams | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mod = elaborate_dut(params)
    with path.open("w") as f:
        h.netlist(mod, f, fmt="spice")
    return path


def run_structural_checks(params: CurrentMirrorParams | None = None):
    params = params or CurrentMirrorParams()
    dut = current_mirror(params)
    mod = elaborate_dut(params)
    netlist_path = Path("./tmp/current_mirror_structural/current_mirror.sp")
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
    if params.device_type == "n":
        checks["contains_device"] = "sky130_fd_pr__nfet_01v8" in text
    else:
        checks["contains_device"] = "sky130_fd_pr__pfet_01v8" in text
    if params.style != "simple":
        checks["contains_mid_nodes"] = "ref_mid" in text and "out_mid" in text
    if not all(checks.values()):
        raise RuntimeError(f"Structural checks failed: {checks}")
    return checks
