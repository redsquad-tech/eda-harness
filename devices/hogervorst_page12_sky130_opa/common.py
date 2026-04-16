from pathlib import Path

import sky130_hdl21 as sky130

from devices.opamp.v2.common import (
    default_ngspice_options,
    extract_ac_trace,
    extract_subckt_name,
    interp_crossing,
    interp_value,
    make_test_result,
    negative_feedback_phase_trace,
    op_scalar,
    run_ngspice_sim,
)


def sky130_root() -> Path:
    root = Path("pdks/sky130A/sky130A").resolve()
    if not root.exists():
        raise RuntimeError(f"Missing SKY130 PDK root: {root}")
    return root


def init_sky130_install() -> None:
    if sky130.install is not None:
        return
    root = sky130_root()
    lib_path = root / "libs.tech/ngspice/sky130.lib.spice"
    model_ref = root / "libs.ref/sky130_fd_pr/spice"
    if not lib_path.exists():
        raise RuntimeError(f"Missing SKY130 ngspice library: {lib_path}")
    if not model_ref.exists():
        raise RuntimeError(f"Missing SKY130 model directory: {model_ref}")
    sky130.install = sky130.Install(pdk_path=root, lib_path=lib_path, model_ref=model_ref)


__all__ = [
    "default_ngspice_options",
    "extract_ac_trace",
    "extract_subckt_name",
    "init_sky130_install",
    "interp_crossing",
    "interp_value",
    "make_test_result",
    "negative_feedback_phase_trace",
    "op_scalar",
    "run_ngspice_sim",
    "sky130_root",
]
