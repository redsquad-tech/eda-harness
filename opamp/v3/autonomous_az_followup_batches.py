from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from components.frontend_az import FrontendAzParams
from tests.structural._helpers import init_sky130_install

from .autonomous_az_batches import (
    _default_timing,
    _frontend_params,
    _rank_key,
    render_batch_markdown,
    run_batch,
    write_index,
    AzBatchCase,
)


def log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).isoformat()}] {msg}", flush=True)


def _timing(**updates) -> dict[str, float]:
    payload = _default_timing()
    payload.update(updates)
    return payload


def build_batches() -> dict[str, list[AzBatchCase]]:
    baseline = AzBatchCase(
        name="baseline",
        hypothesis="Reference baseline for follow-up AZ combinations.",
        frontend_params=_frontend_params(c_az=70e-15, r_vcm_top=8e2, r_vcm_bot=5.0),
        timing=_default_timing(),
    )
    return {
        "combo_frontier": [
            baseline,
            AzBatchCase("shunt_p10_freq200k", "Combine the best topology lever with the best timing lever seen so far.", _frontend_params(c_az=70e-15, r_vcm_top=8e2, r_vcm_bot=5.0, c_out_p=10e-15), _timing(period=5e-6, tstop=60e-6, dead_time=0.5e-6)),
            AzBatchCase("shunt_both10_freq200k", "Symmetric shunt plus high AZ frequency may further reduce corner settling.", _frontend_params(c_az=70e-15, r_vcm_top=8e2, r_vcm_bot=5.0, c_out_p=10e-15, c_out_n=10e-15), _timing(period=5e-6, tstop=60e-6, dead_time=0.5e-6)),
            AzBatchCase("cap200_shuntp10_freq200k", "Largest surviving cap plus positive shunt plus fast timing.", _frontend_params(c_az=200e-15, r_vcm_top=8e2, r_vcm_bot=5.0, c_out_p=10e-15), _timing(period=5e-6, tstop=60e-6, dead_time=0.5e-6)),
            AzBatchCase("cap150_shuntp10_freq200k", "Slightly smaller cap may trade nominal residual for better corner balance.", _frontend_params(c_az=150e-15, r_vcm_top=8e2, r_vcm_bot=5.0, c_out_p=10e-15), _timing(period=5e-6, tstop=60e-6, dead_time=0.5e-6)),
            AzBatchCase("cap200_shuntp10_dead50ns", "Combine the best cap/topology branch with the milder dead-time improvement.", _frontend_params(c_az=200e-15, r_vcm_top=8e2, r_vcm_bot=5.0, c_out_p=10e-15), _timing(dead_time=50e-9, tstop=120e-6)),
            AzBatchCase("cap200_shuntp10_duty_live50", "Longer PHI3 live window on the current best cap/topology branch.", _frontend_params(c_az=200e-15, r_vcm_top=8e2, r_vcm_bot=5.0, c_out_p=10e-15), _timing(phi1_share=0.35, phi2_share=0.15, phi3_share=0.50)),
        ],
        "finish_frontier": [
            baseline,
            AzBatchCase("cap200_shuntp10_rtop600", "Best cap/topology branch plus the best nominal RC trim seen so far.", _frontend_params(c_az=200e-15, r_vcm_top=6e2, r_vcm_bot=5.0, c_out_p=10e-15), _default_timing()),
            AzBatchCase("cap200_shuntp10_rtop600_freq200k", "Combine cap/topology/RC winner with the best timing lever.", _frontend_params(c_az=200e-15, r_vcm_top=6e2, r_vcm_bot=5.0, c_out_p=10e-15), _timing(period=5e-6, tstop=60e-6, dead_time=0.5e-6)),
            AzBatchCase("cap200_shuntp10_rbot10_freq200k", "Softer bottom return with best cap/topology and fast timing.", _frontend_params(c_az=200e-15, r_vcm_top=8e2, r_vcm_bot=10.0, c_out_p=10e-15), _timing(period=5e-6, tstop=60e-6, dead_time=0.5e-6)),
            AzBatchCase("shunt_p10_rtop600_freq200k", "Lighter-cap topology/timing combination with nominal-improving top resistor.", _frontend_params(c_az=70e-15, r_vcm_top=6e2, r_vcm_bot=5.0, c_out_p=10e-15), _timing(period=5e-6, tstop=60e-6, dead_time=0.5e-6)),
            AzBatchCase("cap150_shuntp10_rtop600_freq200k", "Intermediate-cap full combo to test if 200 fF is too much.", _frontend_params(c_az=150e-15, r_vcm_top=6e2, r_vcm_bot=5.0, c_out_p=10e-15), _timing(period=5e-6, tstop=60e-6, dead_time=0.5e-6)),
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", action="append", dest="batches")
    parser.add_argument("--outdir", default="tmp/opamp_v3_autonomous_az_followup")
    args = parser.parse_args(argv)
    init_sky130_install()
    outroot = Path(args.outdir)
    batches = build_batches()
    selected = args.batches or list(batches.keys())
    results: dict[str, dict] = {}
    log(f"starting autonomous AZ follow-up batches: {selected}")
    for batch_name in selected:
        if batch_name not in batches:
            raise SystemExit(f"Unknown batch: {batch_name}")
        results[batch_name] = run_batch(batch_name, batches[batch_name], outroot)
        write_index(outroot, results)
    log("autonomous AZ follow-up batches complete")
    print(outroot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
