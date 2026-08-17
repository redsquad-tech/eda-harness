# DUT workspace runner contract

Copy `assets/run_test.py` unchanged to `<workspace>/tests/run_test.py`. Create one manifest at `<workspace>/tests/testbench_manifest.json`:

```json
{
  "schema_version": 1,
  "groups": [
    {
      "name": "dc_output_and_iq",
      "order": 1,
      "generator": "tests/dc_output_and_iq.py",
      "fixture": "tests/dc_output_and_iq.sp",
      "control": "tests/dc_output_and_iq.control",
      "log": "results/dc_output_and_iq.log",
      "metrics": "results/dc_output_and_iq_metrics.csv",
      "expected_runs": 81,
      "expected_results": 162,
      "parser": null,
      "canonical_inputs": [],
      "materializer": null,
      "generated_dependencies": [],
      "artifacts": []
    }
  ]
}
```

For a waveform artifact use:

```json
{
  "kind": "waveform",
  "path": "results/load_transient_response_waveforms.csv",
  "required_columns": ["run_id", "time", "vout"]
}
```

All paths are relative to the DUT workspace. Do not use absolute paths, `..`, or symlinks.

For a file-based stimulus group, declare all three fields together:

```json
{
  "canonical_inputs": ["stimuli/scenario.csv"],
  "materializer": "tests/materialize_stimuli.py",
  "generated_dependencies": ["tests/generated_stimuli/group_ngspice.inc"]
}
```

The runner checks the input paths, removes stale generated dependencies, runs
the materializer before the HDL21 generator, and requires every dependency to
be recreated and non-empty. The materializer owns CSV schema and waveform
validation.

## Commands and status

```bash
python tests/run_test.py <group>
python tests/run_test.py --all
```

Exit status `0` means a structurally valid simulation without declared DUT failures. Status `1` means a structurally valid simulation with one or more simulator-declared acceptance failures. Status `2` means preflight, generator, simulator, parser, schema, or reproducibility failure. `--all` continues independent groups and returns the maximum status.

## Simulator-owned records

Every `.control` must emit one RESULT per metrics CSV row and exactly one final SUMMARY:

```text
RESULT test=<group> requirement=<requirement> run_id=<id> parameters="<key=value; ...>" metric=<metric> value=<value> unit=<unit> limit_min="<value-or-empty>" limit_max="<value-or-empty>" pass=<0_or_1> fail_reason="<text-or-empty>"
SUMMARY test=<group> runs=<n> results=<n> fail_count=<n>
```

The `.control` owns analysis, physical measurements, derived metrics, limits, and pass/fail. It should write the final metrics CSV directly when possible.

If ngspice output needs structural conversion, save `tests/<group>_parse_results.py`, declare it in `parser`, and accept:

```text
--log <path> --manifest <path> --group <name>
```

The parser may tokenize records, quote CSV fields, copy explicit simulator values, and normalize simulator-native sample/waveform serialization. It must not perform arithmetic, unit conversion, interpolation, limit comparison, or pass/fail inference.

## Reproducibility gate

The runner deletes the selected group's generated dependencies, fixture, and declared result files before every run. Completion requires newly materialized simulator support when declared, a newly generated fixture, a successful ngspice process, one canonical SUMMARY, matching run/result/failure counts, a metrics CSV with the canonical header, and every declared artifact with its required columns. On infrastructure failure, generated dependencies and data outputs are removed and the current diagnostic log is retained.
