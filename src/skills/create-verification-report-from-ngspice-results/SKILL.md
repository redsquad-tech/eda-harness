---
name: create-verification-report-from-ngspice-results
description: Generate a Markdown and PDF acceptance-verification report from the verification plans, stable ngspice metrics, logs, and waveform/sample CSV artifacts in a DUT workspace. Use after reproducible ngspice testbench groups have run.
---

# Create Verification Report from ngspice Results

Generate the final report from saved, reproducible suite artifacts. Reporting summarizes simulator-owned measurements; it must not recompute physical metrics, change limits, or turn missing evidence into a pass.

## Workspace Inputs

Read only stable paths inside the DUT workspace:

```text
verification_plan.md
testbench_implementation_plan.md
tests/testbench_manifest.json
results/<group>_metrics.csv
results/<group>.log
results/<group>_samples.csv       # when declared
results/<group>_waveforms.csv     # when declared
```

The manifest defines group order and expected artifacts. Do not recursively discover historical result trees or infer results from unrelated files.

## Outputs

Create:

```text
test_report.md
test_report.pdf
```

Markdown is mandatory. PDF is mandatory when `pandoc` and `xelatex` or `lualatex` are available; otherwise retain Markdown and report the missing renderer as a limitation.

## Procedure

1. Verify that the workspace, plans, manifest, and every declared metrics file exist.
2. Reject stale or partial evidence: each manifest group must have its declared log and outputs, and result counts must match the manifest.
3. Merge only flat `results/*_metrics.csv` files declared by the manifest, preserving group order.
4. Summarize DUT scope, requirements, conditions, metric ranges, limits, pass/fail, and limitations.
5. Plot declared flat waveform CSVs only when they contain a numeric time/frequency axis and numeric signals. Samples are compact evidence, not waveform substitutes.
6. Generate Markdown, then render PDF with the bundled template and logo.

Use the bundled generator:

```bash
python <skill-root>/scripts/generate_test_report.py \
  --suite-root /path/to/workspace \
  --output /path/to/workspace/test_report.md \
  --title "Block Acceptance Verification Report" \
  --pdf
```

Useful options are `--results-csv` for one explicit metrics file, `--no-all-metrics` to skip `results/all_metrics.csv`, and `--no-pdf` when the user explicitly requests Markdown only.

Metrics use this schema:

```csv
test_name,requirement,run_id,parameters,metric,value,unit,limit_min,limit_max,pass,fail_reason,source_log
```

The generator may validate and aggregate these fields. It must not calculate circuit metrics, interpolate acceptance values, or infer a pass. `unmeasurable`, missing, or non-finite values are failures/limitations, never successful measurements.

For PDF-only rerendering:

```bash
python <skill-root>/scripts/render_report_pdf.py /path/to/workspace/test_report.md \
  --subtitle "Verification Report" \
  --author "anadeto" \
  --company "anadeto"
```

The renderer uses bundled `assets/template.tex` and `assets/logo.png`, creates only temporary metadata, and cleans it up.

## Validation

After generation, require:

```bash
test -s test_report.md
test -s test_report.pdf  # when a renderer is available
```

Report the artifact paths, group/result counts, acceptance summary, missing evidence, and PDF-rendering status.
