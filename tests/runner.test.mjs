import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
  chmodSync,
  copyFileSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const python = process.env.PYTHON ?? "python3";
const runnerAsset = join(
  root,
  "src/skills/create-ngspice-testbench-group-from-implementation-plan/assets/run_test.py",
);
const metricsHeader = [
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
].join(",");

function group(name, order) {
  return {
    name,
    order,
    generator: `tests/${name}.py`,
    fixture: `tests/generated/${name}.sp`,
    control: `tests/${name}.control`,
    log: `results/${name}.log`,
    metrics: `results/${name}_metrics.csv`,
    expected_runs: 1,
    expected_results: 1,
    parser: null,
    artifacts: [],
  };
}

function workspace(groups) {
  const directory = mkdtempSync(join(tmpdir(), "eda-harness-runner-"));
  mkdirSync(join(directory, "tests", "generated"), { recursive: true });
  mkdirSync(join(directory, "results"), { recursive: true });
  mkdirSync(join(directory, "fake-modules"), { recursive: true });
  copyFileSync(runnerAsset, join(directory, "tests", "run_test.py"));
  writeFileSync(join(directory, "fake-modules", "hdl21.py"), "# test stub\n");
  writeFileSync(
    join(directory, "tests", "testbench_manifest.json"),
    JSON.stringify({ schema_version: 1, groups }, null, 2),
  );
  for (const item of groups) {
    writeFileSync(
      join(directory, "tests", `${item.name}.py`),
      `from pathlib import Path\nPath(${JSON.stringify(item.fixture)}).write_text("* generated\\n")\n`,
    );
    writeFileSync(join(directory, "tests", `${item.name}.control`), "* control\n");
  }
  const fake = join(directory, "fake-ngspice.py");
  writeFileSync(
    fake,
    `#!/usr/bin/env python3
import os, pathlib, sys
args = sys.argv[1:]
log = pathlib.Path(args[args.index("-o") + 1])
name = pathlib.Path(args[-1]).stem
scenario = os.environ.get("FAKE_NGSPICE_SCENARIO", "pass")
log.parent.mkdir(parents=True, exist_ok=True)
if scenario == "infra":
    log.write_text("simulator crashed\\n")
    raise SystemExit(5)
failed = scenario == "fail" or (scenario == "mixed" and name == "beta")
passed = "0" if failed else "1"
log.write_text(f"RESULT test={name} run=1 pass={passed}\\nSUMMARY test={name} runs=1 results=1 fail_count={1 if failed else 0}\\n")
metrics = pathlib.Path("results") / f"{name}_metrics.csv"
metrics.write_text(${JSON.stringify(metricsHeader + "\n")} + f"{name},REQ-1,1,,value,1,V,,," + passed + ",,results/.work/{name}/ngspice.log\\n")
`,
  );
  chmodSync(fake, 0o755);
  return { directory, fake };
}

function run(fixture, args, scenario = "pass") {
  return spawnSync(python, ["tests/run_test.py", ...args, "--ngspice", fixture.fake], {
    cwd: fixture.directory,
    encoding: "utf8",
    env: {
      ...process.env,
      FAKE_NGSPICE_SCENARIO: scenario,
      PYTHONDONTWRITEBYTECODE: "1",
      PYTHONPATH: [join(fixture.directory, "fake-modules"), process.env.PYTHONPATH]
        .filter(Boolean)
        .join(delimiter),
    },
  });
}

test("runner removes stale data and publishes only a fresh successful run", () => {
  const fixture = workspace([group("alpha", 1)]);
  try {
    const metrics = join(fixture.directory, "results", "alpha_metrics.csv");
    writeFileSync(metrics, "stale-data\n");
    const result = run(fixture, ["alpha"]);
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.ok(!readFileSync(metrics, "utf8").includes("stale-data"));
    assert.match(readFileSync(join(fixture.directory, "results", "alpha.log"), "utf8"), /SUMMARY test=alpha/);
  } finally {
    rmSync(fixture.directory, { recursive: true, force: true });
  }
});

test("runner distinguishes DUT failures and continues all independent groups", () => {
  const fixture = workspace([group("alpha", 1), group("beta", 2)]);
  try {
    const result = run(fixture, ["--all"], "mixed");
    assert.equal(result.status, 1, result.stdout + result.stderr);
    assert.match(result.stdout, /GROUP alpha status=pass/);
    assert.match(result.stdout, /GROUP beta status=dut_fail/);
    assert.match(readFileSync(join(fixture.directory, "results", "beta_metrics.csv"), "utf8"), /,0,,/);
  } finally {
    rmSync(fixture.directory, { recursive: true, force: true });
  }
});

test("runner rejects infrastructure failures without retaining stale metrics", () => {
  const fixture = workspace([group("alpha", 1)]);
  try {
    const metrics = join(fixture.directory, "results", "alpha_metrics.csv");
    writeFileSync(metrics, "stale-data\n");
    const result = run(fixture, ["alpha"], "infra");
    assert.equal(result.status, 2, result.stdout + result.stderr);
    assert.throws(() => readFileSync(metrics, "utf8"));
    assert.match(readFileSync(join(fixture.directory, "results", "alpha.log"), "utf8"), /RUNNER_ERROR/);
  } finally {
    rmSync(fixture.directory, { recursive: true, force: true });
  }
});
