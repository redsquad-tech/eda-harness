from __future__ import annotations

from pathlib import Path

import sky130_hdl21 as sky130


def init_sky130_install() -> None:
    """Initialize the repository-local SKY130 install for simulation-backed tests."""
    if sky130.install is not None:
        return
    sky130.install = sky130.Install(
        pdk_path=Path("pdks/sky130A/sky130A").resolve(),
        lib_path=Path("libs.tech/ngspice/sky130.lib.spice"),
        model_ref=Path("libs.ref/sky130_fd_pr/spice"),
    )
