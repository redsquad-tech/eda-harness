#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


METRICS_FIELDS = [
    "test_name",
    "requirement",
    "run_id",
    "parameters",
    "metric",
    "value",
    "unit",
    "limit_min",
    "limit_max",
    "pass",
    "fail_reason",
    "source_log",
]
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".svg", ".webp"}
METRICS_SUFFIX = "_metrics.csv"
NON_METRIC_TOKENS = ("_samples", "_waveforms", "wave", "current_wave", "sequence_wave", "plot", "scope")
FAIL_VALUES = {"0", "false", "fail", "failed", "no", "n"}
PASS_VALUES = {"1", "true", "pass", "passed", "yes", "y"}
TIME_COLUMNS = {"time", "t", "time_s", "time_sec", "time_seconds", "t_s"}
FREQ_COLUMNS = {"freq", "frequency", "freq_hz", "frequency_hz", "f_hz"}
METADATA_COLUMNS = {"run_id", "case", "parameters", "sweep_target", "corner", "temperature", "temp", "mode"}


@dataclass
class GroupInfo:
    name: str
    covers: list[str] = field(default_factory=list)
    analysis_type: str = ""
    grouping_reason: str = ""
    hdl21_source: str = ""
    spice_fixture: str = ""
    control: str = ""
    metrics_csv: str = ""
    sample_or_waveform_csv: str = ""
    order_index: int = 10_000


@dataclass
class ArtifactInfo:
    schematics: list[Path] = field(default_factory=list)
    waveform_csvs: list[Path] = field(default_factory=list)
    sample_csvs: list[Path] = field(default_factory=list)
    generated_plots: list[Path] = field(default_factory=list)
    image_plots: list[Path] = field(default_factory=list)
    logs: list[Path] = field(default_factory=list)
    missing_planned: list[str] = field(default_factory=list)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def first_h1(text: str) -> str | None:
    in_fence = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = re.match(r"^#\s+(.+?)\s*#*\s*$", line)
        if match:
            return match.group(1).strip()
    return None


def section_by_heading(text: str, heading_regex: str) -> str:
    lines = text.splitlines()
    start = None
    level = None
    for idx, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match and re.search(heading_regex, match.group(2), flags=re.I):
            start = idx
            level = len(match.group(1))
            break
    if start is None or level is None:
        return ""
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        match = re.match(r"^(#{1,6})\s+", lines[idx])
        if match and len(match.group(1)) <= level:
            end = idx
            break
    return "\n".join(lines[start + 1 : end]).strip()


def rel(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except Exception:
        return str(path)


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def split_cell_items(value: str) -> list[str]:
    value = re.sub(r"`", "", value or "")
    raw = re.split(r"\s*(?:;|,|\bor\b|\band\b)\s*", value)
    return [normalize_name(item) for item in raw if normalize_name(item) and normalize_name(item).lower() != "none"]


def is_separator_row(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{2,}:?", cell.strip()) for cell in cells if cell.strip())


def parse_markdown_tables(text: str) -> list[tuple[list[str], list[dict[str, str]]]]:
    tables: list[tuple[list[str], list[dict[str, str]]]] = []
    lines = text.splitlines()
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if not line.startswith("|") or not line.endswith("|"):
            idx += 1
            continue
        header = [cell.strip() for cell in line.strip("|").split("|")]
        if idx + 1 >= len(lines):
            idx += 1
            continue
        separator = [cell.strip() for cell in lines[idx + 1].strip().strip("|").split("|")]
        if not is_separator_row(separator):
            idx += 1
            continue
        rows: list[dict[str, str]] = []
        idx += 2
        while idx < len(lines):
            row_line = lines[idx].strip()
            if not row_line.startswith("|") or not row_line.endswith("|"):
                break
            cells = [cell.strip() for cell in row_line.strip("|").split("|")]
            if len(cells) < len(header):
                cells.extend([""] * (len(header) - len(cells)))
            rows.append(dict(zip(header, cells[: len(header)])))
            idx += 1
        tables.append((header, rows))
    return tables


def parse_verification_requirements(plan_text: str) -> dict[str, str]:
    requirements: dict[str, str] = {}
    for header, rows in parse_markdown_tables(plan_text):
        lowered = {h.lower(): h for h in header}
        test_col = lowered.get("testbench")
        coverage_col = lowered.get("specification coverage")
        criteria_col = lowered.get("acceptance criteria")
        if not test_col or not coverage_col:
            continue
        for row in rows:
            test = normalize_name(row.get(test_col, "").strip("`"))
            coverage = normalize_name(row.get(coverage_col, ""))
            criteria = normalize_name(row.get(criteria_col, "")) if criteria_col else ""
            if test:
                requirements[test] = f"{coverage}: {criteria}" if criteria else coverage
    return requirements


def parse_implementation_plan(plan_text: str) -> dict[str, GroupInfo]:
    groups: dict[str, GroupInfo] = {}
    for header, rows in parse_markdown_tables(plan_text):
        lowered = {h.lower(): h for h in header}
        group_col = lowered.get("fixture group")
        if not group_col:
            continue
        if "covers verification plan items" in lowered:
            covers_col = lowered["covers verification plan items"]
            analysis_col = lowered.get("analysis type")
            reason_col = lowered.get("grouping reason")
            for row in rows:
                name = normalize_name(row.get(group_col, "").strip("`"))
                if not name:
                    continue
                info = groups.setdefault(name, GroupInfo(name=name))
                info.covers = split_cell_items(row.get(covers_col, ""))
                info.analysis_type = normalize_name(row.get(analysis_col, "")) if analysis_col else ""
                info.grouping_reason = normalize_name(row.get(reason_col, "")) if reason_col else ""
        elif "metrics csv" in lowered:
            hdl_col = lowered.get("hdl21 source")
            spice_col = lowered.get("exported spice fixture")
            control_col = lowered.get("ngspice control")
            metrics_col = lowered.get("metrics csv")
            sample_col = lowered.get("samples / waveform csv")
            for row in rows:
                name = normalize_name(row.get(group_col, "").strip("`"))
                if not name:
                    continue
                info = groups.setdefault(name, GroupInfo(name=name))
                info.hdl21_source = normalize_name(row.get(hdl_col, "").strip("`")) if hdl_col else ""
                info.spice_fixture = normalize_name(row.get(spice_col, "").strip("`")) if spice_col else ""
                info.control = normalize_name(row.get(control_col, "").strip("`")) if control_col else ""
                info.metrics_csv = normalize_name(row.get(metrics_col, "").strip("`")) if metrics_col else ""
                info.sample_or_waveform_csv = normalize_name(row.get(sample_col, "").strip("`")) if sample_col else ""

    order_section = section_by_heading(plan_text, r"Implementation Order")
    order = 0
    for line in order_section.splitlines():
        match = re.match(r"\s*(?:\d+\.|-)\s+`?([A-Za-z0-9_./-]+)`?", line)
        if not match:
            continue
        token = Path(match.group(1)).stem
        if token.endswith(METRICS_SUFFIX):
            token = token[: -len(METRICS_SUFFIX)]
        if token in groups:
            groups[token].order_index = order
            order += 1
    return groups


def is_metrics_csv(path: Path) -> bool:
    name = path.name.lower()
    if name == "all_metrics.csv":
        return False
    if name.endswith(METRICS_SUFFIX):
        return True
    return False


def discover_metrics_csvs(suite_root: Path, explicit: str | None) -> list[Path]:
    if explicit:
        path = Path(explicit).expanduser()
        return [(path if path.is_absolute() else suite_root / path).resolve()]
    results_dir = suite_root / "results"
    candidates: list[Path] = []
    if results_dir.exists():
        candidates.extend(path for path in results_dir.glob("*_metrics.csv") if path.is_file() and is_metrics_csv(path))
        candidates.extend(path for path in results_dir.glob("**/*_metrics.csv") if path.is_file() and is_metrics_csv(path))
    root_candidates = [path for path in suite_root.glob("*_metrics.csv") if path.is_file() and is_metrics_csv(path)]
    candidates.extend(root_candidates)
    return sorted({path.resolve() for path in candidates})


def read_metrics_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return []
        fieldnames = {name.strip() for name in reader.fieldnames if name}
        if not {"test_name", "metric", "pass"}.issubset(fieldnames):
            return []
        rows: list[dict[str, str]] = []
        for raw in reader:
            row = {field: (raw.get(field, "") or "").strip() for field in METRICS_FIELDS}
            for key, value in raw.items():
                if key and key not in row:
                    row[key] = (value or "").strip()
            if any(row.get(field, "") for field in ("test_name", "requirement", "metric", "value")):
                rows.append(row)
        return rows


def merge_metrics_rows(paths: Iterable[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(paths):
        for row in read_metrics_csv(path):
            if not row.get("source_log"):
                group_log = None
                if path.name.lower().endswith(METRICS_SUFFIX):
                    group_log = path.with_name(path.name[: -len(METRICS_SUFFIX)] + ".log")
                fallback_logs = [candidate for candidate in (group_log, path.with_suffix(".log")) if candidate]
                for guessed_log in fallback_logs:
                    if guessed_log.exists():
                        row["source_log"] = str(guessed_log)
                        break
            rows.append(row)
    return rows


def write_all_metrics_csv(suite_root: Path, rows: list[dict[str, str]]) -> Path | None:
    if not rows:
        return None
    out = suite_root / "results" / "all_metrics.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    extra_fields = sorted({key for row in rows for key in row if key not in METRICS_FIELDS})
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=METRICS_FIELDS + extra_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in METRICS_FIELDS + extra_fields})
    return out


def grouped_rows(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        test_name = row.get("test_name") or row.get("test") or row.get("testbench") or "unknown"
        grouped[test_name].append(row)
    return dict(grouped)


def numeric(value: str) -> float | None:
    try:
        parsed = float(str(value).strip())
    except Exception:
        return None
    return parsed if math.isfinite(parsed) else None


def pass_state(row: dict[str, str]) -> str:
    value = (row.get("pass", "") or "").strip().lower()
    if value in FAIL_VALUES:
        return "fail"
    if value in PASS_VALUES:
        return "pass"
    return "unknown"


def row_violates_limits(row: dict[str, str]) -> bool:
    value = numeric(row.get("value", ""))
    if value is None:
        return False
    limit_min = numeric(row.get("limit_min", ""))
    limit_max = numeric(row.get("limit_max", ""))
    if limit_min is not None and value < limit_min:
        return True
    if limit_max is not None and value > limit_max:
        return True
    return False


def fail_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if pass_state(row) == "fail" or row_violates_limits(row)]


def status(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "UNKNOWN"
    states = [pass_state(row) for row in rows]
    if any(state == "fail" for state in states) or any(row_violates_limits(row) for row in rows):
        return "FAIL"
    return "PASS" if all(state == "pass" for state in states) else "UNKNOWN"


def unique_nonempty(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        item = normalize_name(value)
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def metric_ranges(rows: list[dict[str, str]]) -> dict[str, tuple[float, float, str]]:
    values: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        metric = row.get("metric", "")
        value = numeric(row.get("value", ""))
        unit = row.get("unit", "")
        if metric and value is not None:
            values[(metric, unit)].append(value)
    return {metric: (min(nums), max(nums), unit) for (metric, unit), nums in values.items() if nums}


def summarize_ranges(rows: list[dict[str, str]]) -> str:
    ranges = metric_ranges(rows)
    if not ranges:
        return "No finite numeric metric values were found."
    parts = []
    for metric in sorted(ranges):
        lo, hi, unit = ranges[metric]
        suffix = f" {unit}" if unit else ""
        parts.append(f"`{metric}`: {lo:.6g} .. {hi:.6g}{suffix}")
    return "; ".join(parts) + "."


def latex_image(path: Path, base: Path, max_width: str, max_height: str) -> str:
    return f"\\reportimage{{{rel(path, base)}}}{{{max_width}}}{{{max_height}}}"


def read_table_like_csv(path: Path) -> tuple[list[str], list[dict[str, str]], bool]:
    text = read_text(path)
    if not text.strip():
        return [], [], False
    first = next((line for line in text.splitlines() if line.strip()), "")
    if "," in first:
        with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
            reader = csv.DictReader(handle)
            return list(reader.fieldnames or []), [{k: v for k, v in row.items() if k is not None} for row in reader], True
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    header = re.split(r"\s+", lines[0])
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        parts = re.split(r"\s+", line)
        if len(parts) == len(header):
            rows.append(dict(zip(header, parts)))
    return header, rows, False


def is_axis_column(name: str) -> bool:
    lowered = name.strip().lower()
    return lowered in TIME_COLUMNS or lowered in FREQ_COLUMNS or lowered.endswith("_time")


def axis_column_index(header: list[str]) -> int | None:
    for idx, name in enumerate(header):
        if is_axis_column(name):
            return idx
    return None


def is_metadata_column(name: str) -> bool:
    lowered = name.strip().lower()
    return lowered in METADATA_COLUMNS or lowered.endswith("_id")


def signal_indexes(header: list[str], rows: list[dict[str, str]], x_index: int) -> list[int]:
    indexes: list[int] = []
    for idx, name in enumerate(header):
        if idx == x_index or is_metadata_column(name):
            continue
        values = [numeric(row.get(name, "")) for row in rows]
        if values and all(value is not None for value in values):
            indexes.append(idx)
    return indexes


def representative_row_groups(rows: list[dict[str, str]]) -> list[tuple[str, list[dict[str, str]]]]:
    group_col = next((col for col in ("run_id", "case") if any(row.get(col, "") for row in rows)), "")
    if not group_col:
        return [("", rows)]
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get(group_col, "") or "unknown"].append(row)
    return [(name, grouped[name]) for name in sorted(grouped)[:3]]


def is_time_series_waveform(path: Path) -> bool:
    if "_samples" in path.name.lower():
        return False
    header, rows, _ = read_table_like_csv(path)
    if len(header) < 2 or len(rows) < 2:
        return False
    x_index = axis_column_index(header)
    if x_index is None:
        return False
    for row in rows[:20]:
        if numeric(row.get(header[x_index], "")) is None:
            return False
    if not signal_indexes(header, rows, x_index):
        return False
    return True


def signal_label(name: str) -> str:
    cleaned = name.strip()
    if cleaned.lower().startswith("v(") and cleaned.endswith(")"):
        return cleaned[2:-1].upper()
    if cleaned.lower().startswith("i(") and cleaned.endswith(")"):
        return cleaned[2:-1].upper()
    return cleaned


def generate_plot_if_possible(csv_path: Path, output_path: Path, title: str) -> list[Path]:
    if not is_time_series_waveform(csv_path):
        return []
    header, rows, _ = read_table_like_csv(csv_path)
    x_index = axis_column_index(header)
    if x_index is None:
        return []

    import os

    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-create-verification-report")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    generated: list[Path] = []
    for group_name, group_rows in representative_row_groups(rows):
        numeric_series = signal_indexes(header, group_rows, x_index)
        if not numeric_series:
            continue
        x_values = [numeric(row.get(header[x_index], "")) or 0.0 for row in group_rows]
        x_label = header[x_index]
        x_lower = header[x_index].strip().lower()
        if x_lower in TIME_COLUMNS:
            x_values = [value * 1e6 for value in x_values]
            x_label = "time, us"
        elif x_lower in FREQ_COLUMNS:
            x_label = "frequency, Hz"

        fig, axis = plt.subplots(figsize=(8.5, 4.8), dpi=180)
        for idx in numeric_series[:8]:
            axis.plot(
                x_values,
                [numeric(row.get(header[idx], "")) or 0.0 for row in group_rows],
                label=signal_label(header[idx]),
                linewidth=1.25,
            )
        suffix = f": {group_name}" if group_name else ""
        axis.set_xlabel(x_label)
        axis.set_ylabel("value")
        axis.set_title(title + suffix)
        axis.grid(True, which="both", alpha=0.28)
        axis.legend(loc="best", fontsize=8)
        fig.tight_layout()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        safe_group = re.sub(r"[^A-Za-z0-9_.-]+", "_", group_name)
        plot_path = output_path.with_name(f"{output_path.stem}_{safe_group}{output_path.suffix}") if safe_group else output_path
        fig.savefig(plot_path)
        plt.close(fig)
        generated.append(plot_path)
    return generated


def paths_from_plan_field(value: str) -> list[str]:
    cleaned = value.strip().strip("`")
    if not cleaned or cleaned.lower() == "none":
        return []
    return [part.strip().strip("`") for part in re.split(r"\s+or\s+|,|;", cleaned) if part.strip() and part.strip().lower() != "none"]


def discover_group_artifacts(suite_root: Path, group: str, info: GroupInfo | None) -> ArtifactInfo:
    artifacts = ArtifactInfo()
    for dirname in ("schematics", "schematic"):
        root = suite_root / dirname
        if root.exists():
            artifacts.schematics.extend(sorted(path for path in root.glob(f"*{group}*") if path.suffix.lower() in IMAGE_EXTS))

    results = suite_root / "results"
    if results.exists():
        artifacts.sample_csvs.extend(sorted(results.glob(f"{group}*_samples.csv")))
        artifacts.waveform_csvs.extend(sorted(results.glob(f"{group}*_waveforms.csv")))
        artifacts.waveform_csvs.extend(sorted(path for path in results.glob(f"{group}*.csv") if "wave" in path.name.lower() and not is_metrics_csv(path)))
        artifacts.logs.extend(sorted(results.glob(f"{group}.log")))
        artifacts.logs.extend(sorted(results.glob(f"{group}*.log")))
        artifacts.image_plots.extend(sorted(path for path in results.glob(f"**/*{group}*") if path.suffix.lower() in IMAGE_EXTS))
        legacy = results / "latest" / "ngspice" / group
        if legacy.exists():
            artifacts.waveform_csvs.extend(sorted(path for path in legacy.glob("**/*.csv") if any(tok in path.name.lower() for tok in ("wave", "tran", "ac"))))

    if info:
        planned = [info.metrics_csv, info.control, info.hdl21_source, info.spice_fixture]
        planned.extend(paths_from_plan_field(info.sample_or_waveform_csv))
        for item in planned:
            if item and item.lower() != "none" and not (suite_root / item).exists():
                artifacts.missing_planned.append(item)
    artifacts.schematics = sorted({path.resolve() for path in artifacts.schematics})
    artifacts.sample_csvs = sorted({path.resolve() for path in artifacts.sample_csvs})
    artifacts.waveform_csvs = sorted({path.resolve() for path in artifacts.waveform_csvs})
    artifacts.logs = sorted({path.resolve() for path in artifacts.logs})
    artifacts.image_plots = sorted({path.resolve() for path in artifacts.image_plots})
    return artifacts


def source_logs_for_rows(rows: list[dict[str, str]], suite_root: Path) -> list[Path]:
    paths: list[Path] = []
    for row in rows:
        source = row.get("source_log", "").strip()
        if not source:
            continue
        path = Path(source)
        if not path.is_absolute():
            path = suite_root / path
        if path.exists():
            paths.append(path.resolve())
    return sorted(set(paths))


def group_order(groups: Iterable[str], infos: dict[str, GroupInfo]) -> list[str]:
    def key(name: str) -> tuple[int, str]:
        return (infos.get(name, GroupInfo(name)).order_index, name)

    return sorted(groups, key=key)


def group_requirements(group: str, rows: list[dict[str, str]], info: GroupInfo | None, verification_map: dict[str, str]) -> list[str]:
    reqs = unique_nonempty(row.get("requirement", "") for row in rows)
    if info and info.covers:
        reqs = unique_nonempty([*reqs, *info.covers])
    if not reqs and group in verification_map:
        reqs = [verification_map[group]]
    return reqs


def generic_description(group: str, rows: list[dict[str, str]], info: GroupInfo | None, requirements: list[str]) -> str:
    pieces = []
    if info and info.analysis_type:
        pieces.append(f"`{group}` is a {info.analysis_type} fixture group.")
    else:
        pieces.append(f"`{group}` is a discovered fixture group.")
    if requirements:
        pieces.append("It covers: " + "; ".join(f"`{req}`" for req in requirements) + ".")
    metrics = unique_nonempty(row.get("metric", "") for row in rows)
    if metrics:
        pieces.append("Measured metrics: " + ", ".join(f"`{metric}`" for metric in metrics) + ".")
    if info and info.grouping_reason:
        pieces.append(f"Grouping reason: {info.grouping_reason}")
    if info and any([info.hdl21_source, info.spice_fixture, info.control, info.metrics_csv]):
        files = [item for item in [info.hdl21_source, info.spice_fixture, info.control, info.metrics_csv] if item]
        pieces.append("Planned files: " + ", ".join(f"`{item}`" for item in files) + ".")
    return " ".join(pieces)


def sample_summary(path: Path) -> str:
    header, rows, comma = read_table_like_csv(path)
    if not header:
        return f"`{path.name}` is empty or unreadable."
    delimiter = "CSV" if comma else "whitespace table"
    return f"`{path.name}`: {delimiter}, {len(rows)} rows, columns `{', '.join(header[:8])}`."


def build_suspicious_notes(rows: list[dict[str, str]], grouped: dict[str, list[dict[str, str]]], artifacts_by_group: dict[str, ArtifactInfo]) -> list[str]:
    notes: list[str] = []
    for row in rows:
        group = row.get("test_name", "unknown")
        metric = row.get("metric", "metric")
        state = pass_state(row)
        value = numeric(row.get("value", ""))
        if state == "fail":
            reason = row.get("fail_reason", "") or "CSV pass field is failing"
            notes.append(f"`{group}` / `{metric}` failed: {reason}.")
        if state == "pass" and value is None:
            notes.append(f"`{group}` / `{metric}` is marked PASS but has a missing or non-finite numeric value.")
        if state == "unknown":
            notes.append(f"`{group}` / `{metric}` has an unrecognized pass value `{row.get('pass', '')}`.")
        if row_violates_limits(row):
            notes.append(f"`{group}` / `{metric}` violates its CSV limit columns.")
        if value is not None and re.search(r"hyst|width", metric, flags=re.I) and value < 0:
            notes.append(f"`{group}` / `{metric}` is negative; this is suspicious for a width/hysteresis-like metric.")
        if value is not None and not row.get("limit_min", "").strip() and not row.get("limit_max", "").strip():
            notes.append(f"`{group}` / `{metric}` has a numeric value but no CSV limit_min/limit_max fields.")
    for group, artifact in artifacts_by_group.items():
        for missing in artifact.missing_planned:
            if missing.endswith(("_waveforms.csv", "_samples.csv")):
                notes.append(f"`{group}` planned `{missing}` but it was not found.")
    return sorted(set(notes))


def build_report(args: argparse.Namespace) -> tuple[str, Path | None, list[Path]]:
    suite_root = Path(args.suite_root).expanduser().resolve()
    readme = read_text(suite_root / "README.md")
    verification_plan = read_text(suite_root / "verification_plan.md")
    implementation_plan = read_text(suite_root / "testbench_implementation_plan.md")
    existing_report = read_text(suite_root / "test_report.md")

    metrics_paths = discover_metrics_csvs(suite_root, args.results_csv)
    rows = merge_metrics_rows(metrics_paths)
    all_metrics_path = write_all_metrics_csv(suite_root, rows) if args.all_metrics else None
    grouped = grouped_rows(rows)
    infos = parse_implementation_plan(implementation_plan)
    verification_map = parse_verification_requirements(verification_plan)

    all_group_names = set(grouped) | set(infos)
    if not all_group_names and verification_map:
        all_group_names = set(verification_map)
    ordered_groups = group_order(all_group_names, infos)

    artifacts_by_group: dict[str, ArtifactInfo] = {}
    for group in ordered_groups:
        artifacts = discover_group_artifacts(suite_root, group, infos.get(group))
        artifacts.logs = sorted(set(artifacts.logs + source_logs_for_rows(grouped.get(group, []), suite_root)))
        plot_root = suite_root / "results" / "plots" / group
        for csv_path in artifacts.waveform_csvs[:4]:
            out = plot_root / f"{csv_path.stem}.png"
            artifacts.generated_plots.extend(path.resolve() for path in generate_plot_if_possible(csv_path, out, f"{group}: {csv_path.stem}"))
        artifacts_by_group[group] = artifacts

    existing_title = first_h1(existing_report)
    plan_title = first_h1(verification_plan)
    title = args.title or existing_title or (plan_title.replace("Verification Plan", "Verification Report") if plan_title else None)
    title = title or f"{suite_root.name}: Verification Report"

    fail_count = len(fail_rows(rows))
    overall = "FAIL" if fail_count else ("PASS" if rows and all(pass_state(row) == "pass" for row in rows) else ("UNKNOWN" if not rows else "UNKNOWN"))
    artifacts_with_notes = artifacts_by_group
    suspicious = build_suspicious_notes(rows, grouped, artifacts_with_notes)

    dut_section = section_by_heading(verification_plan, r"DUT Interface|DUT")
    scope_section = section_by_heading(verification_plan, r"Purpose and Scope|Scope")
    matrix_section = section_by_heading(verification_plan, r"Acceptance Test Matrix|Test Matrix")
    readme_context = section_by_heading(readme, r"DUT|Overview|Description|Testbench|Verification") if readme else ""

    lines: list[str] = [f"# {title}", ""]
    lines += ["## DUT Description and Public Interface", ""]
    if dut_section:
        lines += [dut_section, ""]
    elif readme_context:
        lines += [readme_context, ""]
    else:
        lines += ["No README was required or found. DUT/interface context is taken from available verification artifacts only.", ""]

    lines += ["## Verification Scope", ""]
    if scope_section:
        lines += [scope_section, ""]
    if matrix_section:
        lines += ["### Plan Matrix", "", matrix_section, ""]

    lines += [
        "## Results Summary",
        "",
        f"Overall result: **{overall}**.",
        f"Metric rows: {len(rows)}; failing rows: {fail_count}; fixture groups: {len(ordered_groups)}.",
    ]
    if metrics_paths:
        lines.append("Metrics CSV inputs: " + ", ".join(f"`{rel(path, suite_root)}`" for path in metrics_paths) + ".")
    else:
        lines.append("Metrics CSV inputs: none discovered.")
    if all_metrics_path:
        lines.append(f"Merged metrics artifact: `{rel(all_metrics_path, suite_root)}`.")
    if not readme:
        lines.append("README.md was absent; report generation used the verification plan, implementation plan, results, logs, and optional artifacts.")
    lines.append("")

    lines += ["## Testbench Groups", ""]
    for group in ordered_groups:
        rows_for_group = grouped.get(group, [])
        info = infos.get(group)
        artifacts = artifacts_by_group[group]
        fails = fail_rows(rows_for_group)
        requirements = group_requirements(group, rows_for_group, info, verification_map)
        reasons = Counter(row.get("fail_reason", "-") or "-" for row in fails)

        lines += ["\\Needspace{0.42\\textheight}", f"### `{group}`", ""]
        for schematic in artifacts.schematics[:2]:
            lines += [latex_image(schematic, suite_root, "\\linewidth", "0.30\\textheight"), ""]
        lines += [generic_description(group, rows_for_group, info, requirements), ""]
        if requirements:
            lines += ["Requirements covered:", ""]
            for req in requirements:
                lines.append(f"- `{req}`")
            lines.append("")
        lines += [
            f"Result: **{status(rows_for_group)}**. Metrics: {len(rows_for_group)}, FAIL metrics: {len(fails)}.",
            summarize_ranges(rows_for_group),
            "",
        ]
        if reasons:
            lines.append("FAIL reasons: " + ", ".join(f"`{reason}`: {count}" for reason, count in sorted(reasons.items())) + ".")
            lines.append("")
        if fails:
            lines += ["Representative failures:", ""]
            for row in fails[:6]:
                limit_min = row.get("limit_min", "") or "-"
                limit_max = row.get("limit_max", "") or "-"
                params = row.get("parameters", "") or "-"
                lines.append(
                    f"- `{row.get('metric', '-')}` = `{row.get('value', '-')}` `{row.get('unit', '')}`; "
                    f"limits `{limit_min}` .. `{limit_max}`; reason `{row.get('fail_reason', '-') or '-'}`; params: {params}."
                )
            lines.append("")
        if artifacts.logs:
            lines.append("Logs: " + ", ".join(f"`{rel(path, suite_root)}`" for path in artifacts.logs[:6]) + ".")
            lines.append("")
        if artifacts.sample_csvs:
            lines += ["Sample evidence:", ""]
            for sample in artifacts.sample_csvs[:4]:
                lines.append(f"- {sample_summary(sample)}")
            lines.append("")
        plots = sorted(set(artifacts.generated_plots + artifacts.image_plots))
        if plots:
            lines += ["Waveform evidence:", ""]
            for image in plots[:6]:
                lines.append(latex_image(image, suite_root, "\\linewidth", "0.36\\textheight"))
            lines.append("")
        elif artifacts.waveform_csvs:
            lines.append("Waveform CSV artifacts were found, but no time-series plot could be generated from their columns.")
            lines.append("")
        if artifacts.missing_planned:
            lines.append("Missing planned artifacts: " + ", ".join(f"`{item}`" for item in artifacts.missing_planned) + ".")
            lines.append("")

    lines += ["## Conclusion", ""]
    if overall == "FAIL":
        lines.append("The DUT or mock does not pass the discovered acceptance result set.")
    elif overall == "PASS":
        lines.append("All discovered metrics rows pass their CSV pass/fail fields and limit columns.")
    else:
        lines.append("Overall status is unknown because no complete passing metrics set was discovered.")
    if suspicious:
        lines += ["", "Findings and limitations:", ""]
        lines += [f"- {note}" for note in suspicious[:24]]
        if len(suspicious) > 24:
            lines.append(f"- {len(suspicious) - 24} additional findings were omitted from this summary.")
    if not any((artifact.generated_plots or artifact.image_plots) for artifact in artifacts_by_group.values()):
        lines += ["", "No waveform plots were available or generated. This is acceptable for non-waveform groups, but transient/AC evidence should include waveform CSVs or images when required by the plan."]
    lines += [
        "",
        "This report summarizes black-box acceptance artifacts available in the suite. Layout sign-off, PEX, DRC/LVS/ERC, reliability, EM/IR, ESD, and Monte Carlo/PVT closure require separate evidence unless explicitly present in the verification plan and results.",
        "",
    ]
    return "\n".join(lines), all_metrics_path, metrics_paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Markdown and optional PDF verification report from suite artifacts.")
    parser.add_argument("--suite-root", default=".")
    parser.add_argument("--output", default=None)
    parser.add_argument("--results-csv")
    parser.add_argument("--title")
    parser.add_argument("--pdf", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--all-metrics", action=argparse.BooleanOptionalAction, default=True, help="Write results/all_metrics.csv when metrics rows are discovered.")
    args = parser.parse_args()

    suite_root = Path(args.suite_root).expanduser().resolve()
    output = Path(args.output).expanduser() if args.output else suite_root / "test_report.md"
    if not output.is_absolute():
        output = suite_root / output
    output.parent.mkdir(parents=True, exist_ok=True)

    report, all_metrics_path, metrics_paths = build_report(args)
    output.write_text(report, encoding="utf-8")
    print(output)
    if all_metrics_path:
        print(all_metrics_path)
    if not metrics_paths:
        print("WARNING: no metrics CSV files were discovered", file=sys.stderr)

    if args.pdf:
        render_script = Path(__file__).resolve().parent / "render_report_pdf.py"
        cmd = [
            sys.executable,
            str(render_script),
            str(output),
            "--subtitle",
            "Verification Report",
            "--author",
            "anadeto",
            "--company",
            "anadeto",
            "--force-assets",
        ]
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(f"WARNING: PDF rendering failed with exit code {result.returncode}; Markdown report remains at {output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
