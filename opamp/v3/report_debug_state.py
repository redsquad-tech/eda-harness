from __future__ import annotations

import json
from pathlib import Path

import hdl21 as h

from opamp.v3.measure_core import (
    OpampCoreDisabledTbParams,
    OpampCoreFollowerTbParams,
    run_disable_nodes_test,
    run_loop_stability_debug,
)
from opamp.v3.tests._helpers import init_sky130_install


def main() -> int:
    init_sky130_install()
    outdir = Path("tmp/opamp_v3_debug_state")
    outdir.mkdir(parents=True, exist_ok=True)

    disable = run_disable_nodes_test(
        tb_params=OpampCoreDisabledTbParams(vdd=1.98, v_cm=0.4, temp_c=-40.0),
        corner=h.pdk.Corner.FAST,
    )
    (outdir / "disable_nodes_FF_V1.98_T-40C.json").write_text(
        json.dumps(disable, indent=2, sort_keys=True), encoding="utf-8"
    )

    debug_cases = {
        "TT_V1.60_T27C": (h.pdk.Corner.TYP, 1.6, 27.0),
        "SS_V1.60_T-40C": (h.pdk.Corner.SLOW, 1.6, -40.0),
    }
    for label, (corner, vdd, temp_c) in debug_cases.items():
        debug = run_loop_stability_debug(
            tb_params=OpampCoreFollowerTbParams(
                vdd=vdd,
                c_load=1e-12,
                r_probe=1e12,
                vout_low_target=0.1,
                vout_high_target=vdd - 0.2,
                vout_mid_target=0.5 * vdd,
                drive_current_uA=20.0,
                f_start=1.0,
                f_stop=1e9,
                npts=40,
                temp_c=temp_c,
            ),
            corner=corner,
        )
        (outdir / f"loop_debug_{label}.json").write_text(json.dumps(debug, indent=2), encoding="utf-8")

    print(outdir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
