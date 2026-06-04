---
name: test2report
description: Generate analog verification reports from a verification-plan Markdown file, implementation plan, per-group metrics CSVs, logs, schematic images, and optional waveform/sample artifacts. Use when Codex must create a structured verification report with DUT description, grouped test results, conclusions, Markdown output, and PDF output when the local toolchain is available.
---

# Test Results To Report

Use this skill as the final reporting stage of the spec-to-testbench pipeline. It turns a generated EDA acceptance suite into an English sign-off style report.

Expected inputs are local suite artifacts:

- `verification_plan.md`
- `testbench_implementation_plan.md`
- `results/*_metrics.csv`
- optional `results/*_samples.csv` and `results/*_waveforms.csv`
- logs from `source_log` CSV fields or `results/*.log`
- optional schematics from `schematics/` or `schematic/`
- optional `README.md`

`README.md` is enrichment only. Do not require it and do not treat it as the source of truth when the verification plan, implementation plan, and result CSVs are present.

## Required Output

Always create:

- Markdown report, usually `test_report.md` or a user-specified path.

Create when the local PDF toolchain is available:

- PDF report with the same basename.

If `pandoc`, `xelatex`, or `lualatex` is missing or PDF rendering fails, keep the Markdown report intact and report the exact failure. Do not delete or invalidate the Markdown report.

The report must contain:

1. Report title.
2. DUT description and public interface from `verification_plan.md` when available.
3. Verification scope and acceptance matrix.
4. Results summary across all discovered metrics CSV files.
5. One chapter per testbench group with:
   - requirements covered;
   - analysis type and grouping reason from `testbench_implementation_plan.md`;
   - planned files and stable result paths;
   - pass/fail counts;
   - metric min/max ranges;
   - representative failures;
   - logs and optional schematic/sample/waveform evidence.
6. Conclusion with explicit DUT problems, suspicious result behavior, and residual verification limitations.

Do not write a vague “all good” conclusion when failures, missing numeric values, inconsistent pass/fail fields, missing planned artifacts, or limit-column violations exist.

## Quick Start

From the verification-suite root:

```bash
python .agents/skills/test2report/scripts/generate_test_report.py \
  --suite-root . \
  --output test_report.md \
  --pdf
```

The script discovers and merges per-group metrics CSV files:

```text
results/<group>_metrics.csv
results/*_metrics.csv
results/**/<legacy_group>_metrics.csv
```

It ignores samples/waveform CSVs as primary metrics inputs and writes a convenience aggregate when metrics rows are found:

```text
results/all_metrics.csv
```

Use an explicit metrics CSV only when the user asks for one:

```bash
python .agents/skills/test2report/scripts/generate_test_report.py \
  --suite-root . \
  --results-csv results/all_metrics.csv \
  --output test_report.md
```

## Workflow

1. Read `verification_plan.md` for DUT interface, scope, acceptance matrix, requirements, and criteria.
2. Read `testbench_implementation_plan.md` for fixture groups, group ordering, analysis types, grouping reasons, planned files, and stable outputs.
3. Treat `README.md` as optional descriptive context only.
4. Discover result artifacts:
   - prefer `--results-csv` if provided;
   - otherwise merge all valid `results/*_metrics.csv` and nested legacy `*_metrics.csv`;
   - never use `*_samples.csv`, `*_waveforms.csv`, `wave*.csv`, or similar debug CSVs as metrics inputs.
5. Discover optional evidence:
   - logs from `source_log` or `results/*.log`;
   - schematics from `schematics/` or `schematic/`;
   - flat `results/<group>_samples.csv`;
   - flat `results/<group>_waveforms.csv`;
   - legacy `results/latest/ngspice/<group>/**` waveform CSVs or plot images.
6. Generate Markdown first.
7. Render PDF with the bundled template and logo when `pandoc` and a LaTeX engine are available.

## Script

Use `scripts/generate_test_report.py` for the standard flow:

```bash
python <skill-root>/scripts/generate_test_report.py \
  --suite-root /path/to/suite \
  --output /path/to/test_report.md \
  --title "Block Acceptance Verification Report" \
  --pdf
```

Important options:

- `--suite-root`: suite directory, default current directory.
- `--output`: Markdown output path, default `<suite-root>/test_report.md`.
- `--results-csv`: explicit single metrics CSV. Without it, all discovered `*_metrics.csv` files are merged.
- `--all-metrics` / `--no-all-metrics`: write or skip `results/all_metrics.csv`; default writes it when rows exist.
- `--pdf` / `--no-pdf`: request or skip PDF rendering; Markdown is always written.
- `--title`: override inferred report title.

## CSV Handling

Metrics CSV files use the standard schema:

```csv
test_name,requirement,run_id,parameters,metric,value,unit,limit_min,limit_max,pass,fail_reason,source_log
```

The report generator:

- combines all valid metrics rows in memory;
- groups rows by `test_name`;
- orders groups by `testbench_implementation_plan.md` when present;
- lists all distinct requirements covered by each group;
- summarizes each metric by min/max range;
- uses `pass`, `fail_reason`, `limit_min`, and `limit_max` for conclusions.

Do not add suite-specific hardcoded numeric limits in the report generator. Universal suspicious checks may flag failed rows, non-finite values, PASS rows with missing values, inconsistent pass fields, CSV limit-column violations, missing planned artifacts, and carefully worded negative width/hysteresis observations.

## Waveform and Sample Handling

`*_samples.csv` files are debug/evidence tables. Include compact summaries, but do not treat them as full waveforms.

`*_waveforms.csv` files are plotted only when they look like real time-series or frequency-series data:

- comma-separated CSV is supported;
- whitespace-separated legacy ngspice output is supported as fallback;
- a time/frequency-like column and numeric signal columns must be present.

If plots cannot be generated, keep the report valid and state the limitation. Missing waveforms are a limitation only when relevant to planned transient/AC evidence.

## PDF Rendering Rules

The skill includes its own PDF assets:

- `assets/template.tex`
- `assets/logo.png`
- `assets/meta.example.yaml`

Use `scripts/render_report_pdf.py` when only PDF rendering is needed:

```bash
python <skill-root>/scripts/render_report_pdf.py /path/to/test_report.md \
  --subtitle "Verification Report" \
  --author "anadeto" \
  --company "anadeto" \
  --force-assets
```

The renderer uses bundled `template.tex` and `logo.png` by absolute path, writes only temporary hidden metadata, cleans it up, and tries `xelatex` first, then `lualatex`.

## Validation

After creating a report:

```bash
test -s test_report.md
```

If PDF dependencies are installed:

```bash
test -s test_report.pdf
```

When changing this skill itself, validate the skill folder when the validator is available:

```bash
python /home/tim/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  .agents/skills/test2report
```
