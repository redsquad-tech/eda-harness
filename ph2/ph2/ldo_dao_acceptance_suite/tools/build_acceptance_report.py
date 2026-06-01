#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt


CORNERS = ["typical", "fff", "ssf", "fsf", "sff"]
CORNER_LABEL = {
    "typical": "typical / tt",
    "fff": "fff / ff",
    "ssf": "ssf / ss",
    "fsf": "fsf / fs",
    "sff": "sff / sf",
}


def parse_params(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in text.split("; "):
        if "=" in part:
            key, value = part.split("=", 1)
            out[key] = value
    return out


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def finite_values(rows: list[dict[str, str]], metric: str) -> list[float]:
    vals: list[float] = []
    for row in rows:
        if row["metric"] != metric:
            continue
        try:
            val = float(row["value"])
        except ValueError:
            continue
        if math.isfinite(val):
            vals.append(val)
    return vals


def metric_range(rows: list[dict[str, str]], metric: str) -> str:
    vals = finite_values(rows, metric)
    if not vals:
        return "n/a"
    return f"{min(vals):.6g} .. {max(vals):.6g}"


def count_fail_reasons(rows: list[dict[str, str]]) -> Counter[str]:
    c: Counter[str] = Counter()
    for row in rows:
        if row["pass"] == "FAIL":
            reason = row["fail_reason"] or "FAIL"
            for item in reason.split(";"):
                if item:
                    c[item] += 1
    return c


def read_wrdata(path: Path, kind: str) -> list[dict[str, float]]:
    records: list[dict[str, float]] = []
    if not path.exists():
        return records
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        vals = [float(x) for x in line.split()]
        if kind == "dynamic" and len(vals) >= 12:
            records.append(
                {
                    "x": vals[0],
                    "temp": vals[1],
                    "vdd": vals[3],
                    "vout": vals[5],
                    "gate": vals[7],
                    "iin_uA": vals[9],
                    "load_mA": vals[11],
                }
            )
        elif kind == "psrr" and len(vals) >= 10:
            records.append(
                {
                    "x": vals[0],
                    "temp": vals[1],
                    "vdd": vals[4],
                    "psrr_db": vals[7],
                    "gain_db": vals[9],
                }
            )
        elif kind == "loop" and len(vals) >= 10:
            records.append(
                {
                    "x": vals[0],
                    "temp": vals[1],
                    "vdd": vals[4],
                    "gain_db": vals[7],
                    "phase_deg": vals[9],
                }
            )
    return records


def nominal(records: list[dict[str, float]]) -> list[dict[str, float]]:
    return [r for r in records if abs(r["temp"] - 27.0) < 1e-9 and abs(r["vdd"] - 3.3) < 1e-9]


def plot_waveforms(outdir: Path, figdir: Path) -> dict[str, str]:
    figdir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}

    dyn_by_corner = {
        c: nominal(read_wrdata(outdir / c / "dynamic_load_tran" / "dynamic_load_waveforms.dat", "dynamic"))
        for c in CORNERS
    }
    plt.figure(figsize=(9, 4.8))
    for corner, rows in dyn_by_corner.items():
        if rows:
            plt.plot([r["x"] * 1e9 for r in rows], [r["vout"] for r in rows], label=CORNER_LABEL[corner], linewidth=1.2)
    plt.xlabel("Time (ns)")
    plt.ylabel("Vout (V)")
    plt.title("Dynamic-load transient, nominal condition")
    plt.grid(True, alpha=0.3)
    plt.legend(fontsize=8)
    plt.tight_layout()
    p = figdir / "dynamic_load_vout_nominal.png"
    plt.savefig(p, dpi=180)
    plt.close()
    paths["dynamic_vout"] = str(p)

    rows = dyn_by_corner.get("typical", [])
    if rows:
        fig, ax1 = plt.subplots(figsize=(9, 4.8))
        ax1.plot([r["x"] * 1e9 for r in rows], [r["vout"] for r in rows], color="#1f77b4", label="Vout")
        ax1.set_xlabel("Time (ns)")
        ax1.set_ylabel("Vout (V)", color="#1f77b4")
        ax1.tick_params(axis="y", labelcolor="#1f77b4")
        ax2 = ax1.twinx()
        ax2.plot([r["x"] * 1e9 for r in rows], [r["load_mA"] for r in rows], color="#d62728", alpha=0.65, label="Load")
        ax2.set_ylabel("Load current (mA)", color="#d62728")
        ax2.tick_params(axis="y", labelcolor="#d62728")
        ax1.set_title("Dynamic-load stimulus and response, typical / tt")
        ax1.grid(True, alpha=0.3)
        fig.tight_layout()
        p = figdir / "dynamic_load_stimulus_response_typical.png"
        fig.savefig(p, dpi=180)
        plt.close(fig)
        paths["dynamic_stimulus"] = str(p)

    psrr_by_corner = {
        c: nominal(read_wrdata(outdir / c / "psrr_ac" / "psrr_waveforms.dat", "psrr"))
        for c in CORNERS
    }
    plt.figure(figsize=(9, 4.8))
    for corner, rows in psrr_by_corner.items():
        if rows:
            plt.semilogx([r["x"] for r in rows], [r["psrr_db"] for r in rows], label=CORNER_LABEL[corner], linewidth=1.2)
    plt.xlabel("Frequency (Hz)")
    plt.ylabel("PSRR (dB)")
    plt.title("PSRR AC response, nominal condition")
    plt.grid(True, which="both", alpha=0.3)
    plt.legend(fontsize=8)
    plt.tight_layout()
    p = figdir / "psrr_nominal.png"
    plt.savefig(p, dpi=180)
    plt.close()
    paths["psrr"] = str(p)

    loop_by_corner = {
        c: nominal(read_wrdata(outdir / c / "loop_stability_ac" / "loop_stability_waveforms.dat", "loop"))
        for c in CORNERS
    }
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    for corner, rows in loop_by_corner.items():
        if rows:
            freq = [r["x"] for r in rows]
            ax1.semilogx(freq, [r["gain_db"] for r in rows], label=CORNER_LABEL[corner], linewidth=1.2)
            ax2.semilogx(freq, [r["phase_deg"] for r in rows], label=CORNER_LABEL[corner], linewidth=1.2)
    ax1.axhline(0, color="black", linewidth=0.8, alpha=0.5)
    ax1.set_ylabel("Loop gain (dB)")
    ax1.set_title("Loop return-ratio AC response, nominal condition")
    ax1.grid(True, which="both", alpha=0.3)
    ax1.legend(fontsize=8)
    ax2.set_xlabel("Frequency (Hz)")
    ax2.set_ylabel("Wrapped phase (deg)")
    ax2.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    p = figdir / "loop_gain_phase_nominal.png"
    fig.savefig(p, dpi=180)
    plt.close(fig)
    paths["loop"] = str(p)
    return paths


def rel(path: str, base: Path) -> str:
    return Path(path).resolve().relative_to(base.resolve()).as_posix()


def write_report(csv_path: Path, outdir: Path, report_path: Path) -> None:
    rows = load_csv(csv_path)
    figdir = report_path.parent / "figures"
    figures = plot_waveforms(outdir, figdir)

    by_test: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_test[row["test_name"]].append(row)

    total_fail = sum(1 for r in rows if r["pass"] == "FAIL")
    test_lines = []
    for test in ["dc_iq", "dynamic_load_tran", "psrr_ac", "loop_stability_ac", "vout_variation_mc"]:
        tr = by_test[test]
        fails = sum(1 for r in tr if r["pass"] == "FAIL")
        status = "FAIL" if fails else "PASS"
        test_lines.append(f"| `{test}` | {status} | {len(tr)} | {fails} |")

    def reason_text(test: str) -> str:
        c = count_fail_reasons(by_test[test])
        if not c:
            return "none"
        return ", ".join(f"`{k}`: {v}" for k, v in c.most_common())

    def status(test: str) -> str:
        return "FAIL" if any(r["pass"] == "FAIL" for r in by_test[test]) else "PASS"

    no_load_iq = [
        float(r["value"])
        for r in by_test["dc_iq"]
        if r["metric"] == "Iq_uA" and "iload_A=0" in r["parameters"] and r["value"]
    ]
    loaded_iq = [
        float(r["value"])
        for r in by_test["dc_iq"]
        if r["metric"] == "Iq_uA" and "iload_A=1.5E-05" in r["parameters"] and r["value"]
    ]
    loaded_iin = [
        float(r["value"])
        for r in by_test["dc_iq"]
        if r["metric"] == "Iin_total_uA" and "iload_A=1.5E-05" in r["parameters"] and r["value"]
    ]

    report = f"""---
title: "LDO_DAO SKY130 Acceptance Test Report"
subtitle: "Five-corner ngspice rerun with corrected measurements and waveform plots"
author: "anadeto"
city: "Moscow"
year: "2026"
toc: true
---

# LDO_DAO SKY130 Acceptance Test Report

## Executive Summary

The full five-corner SKY130/ngspice acceptance suite was rerun from the updated testbenches.
The suite status is **FAIL**. The failing checks are `dc_iq` and `loop_stability_ac`.
`dc_iq` still violates the `Iq <= 3 uA` limit and the low-reference DC output check still fails in several points.
`loop_stability_ac` now reports the corrected ngspice phase margin and fails several PVT points near the `40 deg` limit.

The earlier apparent large change of `Iq_uA` under static load was a test/reporting error: the old report used total VDD source current as `Iq_uA`, so the `15 uA` load current was included. The updated report separates total input current from corrected quiescent current.
The earlier `PM ~= 177 deg` loop-stability result was also a measurement error: ngspice `vp(...)` returned radians, but the old scalar calculation treated that value as degrees.

| Test | Status | CSV metric rows | Failed rows |
|---|---:|---:|---:|
{chr(10).join(test_lines)}

Total CSV rows: {len(rows)}. Failed metric rows: {total_fail}.

## DUT and Conditions

- DUT netlist: `examples/ldo_dao_sky130_from_gf55.sp`.
- Model library: SKY130 `sky130.lib.spice`.
- Corners: `typical -> tt`, `fff -> ff`, `ssf -> ss`, `fsf -> fs`, `sff -> sf`.
- Output capacitor in all acceptance fixtures: `COUT = 449 pF`.
- Nominal operating point: `VDD = 3.3 V`, `VREF = 0.80 V`, `IBIAS = 400 nA`, `TEMP = 27 C`.
- Static load condition: `15 uA`.
- Dynamic load condition: `15 uA` DC plus `30 mA`, `200 ps`, `10 MHz` pulse load.

## Results by Test

### DC and Quiescent Current

Status: **{status("dc_iq")}**. Failure reasons: {reason_text("dc_iq")}.

![DC regulation and quiescent-current testbench](schematics/dc_iq.png)

The DC fixture measures the operating point at `vout_1v2` and the current through the VDD source.
ngspice defines current through a voltage source from the positive terminal into the source, so positive DUT consumption is reported as:

```text
Iin_total_uA = -1e6 * i(V_VDD)
Iq_uA = Iin_total_uA - 1e6 * ILOAD_DC
```

For no-load quiescent-current acceptance, `ILOAD_DC = 0`, so `Iq_uA = Iin_total_uA`.
The acceptance checks are:

```text
1.08 V <= Vout_V <= 1.32 V
Iq_uA <= 3.0 uA
```

Measured ranges:

| Metric | Range |
|---|---:|
| `Vout_V` | {metric_range(by_test["dc_iq"], "Vout_V")} |
| `Iin_total_uA` | {metric_range(by_test["dc_iq"], "Iin_total_uA")} |
| `Iq_uA` | {metric_range(by_test["dc_iq"], "Iq_uA")} |

No-load `Iq_uA` range: {min(no_load_iq):.4g} .. {max(no_load_iq):.4g} uA.
Loaded corrected `Iq_uA` range: {min(loaded_iq):.4g} .. {max(loaded_iq):.4g} uA.
Loaded total input-current range: {min(loaded_iin):.4g} .. {max(loaded_iin):.4g} uA.

Interpretation: the previous `~10 .. 27 uA` quiescent-current range mixed no-load current with total input current under a `15 uA` external load. After correction, `Iq_uA` remains around `10 .. 12 uA`; this is still above the `3 uA` limit, but it no longer shows the artificial `15 uA` load-current jump.

The DUT netlist contains an internal feedback-divider path of approximately `40.0176 kOhm + 40.0176 kOhm + 40.0176 kOhm`, which alone implies about `1.2 V / 120 kOhm ~= 10 uA`. That matches the corrected no-load `Iq_uA` and explains why the current limit still fails.

### Dynamic-Load Transient

Status: **{status("dynamic_load_tran")}**. Failure reasons: {reason_text("dynamic_load_tran")}.

![Dynamic-load transient testbench](schematics/dynamic_load_tran.png)

The transient fixture measures a pre-step level, a minimum, a maximum, and a dynamic average:

```text
Vout_pre       = avg(V(vout_1v2), 150 ns .. 190 ns)
Vout_min       = min(V(vout_1v2), 200 ns .. 400 ns)
Vout_max       = max(V(vout_1v2), 200 ns .. 400 ns)
Vout_dyn_avg   = avg(V(vout_1v2), 400 ns .. 900 ns)

drop_mV      = max(0, 1000 * (Vout_pre - Vout_min))
overshoot_mV = max(0, 1000 * (Vout_max - Vout_pre))
avg_drop_mV  = max(0, 1000 * (Vout_pre - Vout_dyn_avg))
```

Acceptance limits are `drop_mV <= 50`, `overshoot_mV <= 20`, and `avg_drop_mV <= 25`.

Measured ranges:

| Metric | Range |
|---|---:|
| `drop_mV` | {metric_range(by_test["dynamic_load_tran"], "drop_mV")} |
| `overshoot_mV` | {metric_range(by_test["dynamic_load_tran"], "overshoot_mV")} |
| `avg_drop_mV` | {metric_range(by_test["dynamic_load_tran"], "avg_drop_mV")} |
| `Vout_min_V` | {metric_range(by_test["dynamic_load_tran"], "Vout_min_V")} |

![Dynamic-load Vout waveform]({rel(figures["dynamic_vout"], report_path.parent)})

![Dynamic-load stimulus and response]({rel(figures["dynamic_stimulus"], report_path.parent)})

### PSRR AC

Status: **{status("psrr_ac")}**. Failure reasons: {reason_text("psrr_ac")}.

![PSRR AC testbench](schematics/psrr_ac.png)

The PSRR fixture applies `AC 1` on `V_VDD`, so the AC output transfer directly gives `Vout/Vdd`:

```text
ratio(f)     = V(vout_1v2, f) / V(vdd_3v3, f)
PSRR_dB(f)   = -20 * log10(|ratio(f)|)
PSRR_min_dB  = min(PSRR_dB(f)), f = 1 Hz .. 1 GHz
```

The acceptance limit is `PSRR_min_dB >= 40`.

Measured range:

| Metric | Range |
|---|---:|
| `PSRR_min_dB` | {metric_range(by_test["psrr_ac"], "PSRR_min_dB")} |

![PSRR waveform]({rel(figures["psrr"], report_path.parent)})

### Loop Stability AC

Status: **{status("loop_stability_ac")}**. Failure reasons: {reason_text("loop_stability_ac")}.

![Loop-stability AC testbench](schematics/loop_stability_ac.png)

The loop-stability fixture keeps the DC feedback path closed with a zero-volt injection source between the public feedback pins and injects `AC 1`.
The ngspice return-ratio expression is:

```text
T(f) = -V(vfb_o, f) / V(vfb_i, f)
loop_gain_dB(f) = 20 * log10(|T(f)|)
loop_phase_deg(f) = rad_to_deg(wrapped_phase(T(f)))

GBW_Hz = first f where loop_gain_dB(f) crosses 0 dB falling
PM_deg = 180 + loop_phase_deg(GBW_Hz)
```

The acceptance limits are `GBW_Hz >= 100 kHz`, `PM_deg >= 40 deg`, and `GM_dB >= 20 dB`.

Measured ranges:

| Metric | Range |
|---|---:|
| `GBW_Hz` | {metric_range(by_test["loop_stability_ac"], "GBW_Hz")} |
| `PM_deg` | {metric_range(by_test["loop_stability_ac"], "PM_deg")} |
| `GM_dB` | {metric_range(by_test["loop_stability_ac"], "GM_dB")} |

![Loop gain and phase waveform]({rel(figures["loop"], report_path.parent)})

Interpretation: ngspice `vp(...)` returns phase in radians in this flow. The measurement control converts it to degrees before calculating phase margin. The loop-stability result should therefore be read from the corrected `PM_deg` range above, not from the legacy report that added a radian phase directly to `180`. The failing points are phase-margin failures, while gain bandwidth and gain margin remain above their limits.

### Monte Carlo Output Variation

Status: **{status("vout_variation_mc")}**. Failure reasons: {reason_text("vout_variation_mc")}.

![Monte Carlo output-variation testbench](schematics/vout_variation_mc.png)

The Monte Carlo fixture runs 50 operating-point samples using the SKY130 mismatch sections and reports:

```text
mean_V    = average(Vout_i)
sigma_mV  = 1000 * standard_deviation(Vout_i)
```

The acceptance limit is `sigma_mV <= 20`.

Measured ranges:

| Metric | Range |
|---|---:|
| `mean_V` | {metric_range(by_test["vout_variation_mc"], "mean_V")} |
| `sigma_mV` | {metric_range(by_test["vout_variation_mc"], "sigma_mV")} |

## Conclusions

The test bug behind the apparent load-dependent quiescent-current swing is fixed: total input current and corrected quiescent current are now reported separately.

The DUT still fails DC acceptance because corrected no-load `Iq_uA` is roughly `10 .. 12 uA`, above the `3 uA` requirement, and low-reference points still violate the output lower bound.

The loop-stability scalar must use degree-converted ngspice phase. A stronger follow-up would still be to compare this public-pin return-ratio setup against a Middlebrook/Tian-style return-ratio setup or against simulator-native stability analysis.
"""
    report_path.write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    write_report(Path(args.csv), Path(args.outdir), Path(args.report))
    print(args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
