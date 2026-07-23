import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const generator = join(root, "src/skills/create-verification-report-from-ngspice-results/scripts/generate_test_report.py");
const header = "test_name,requirement,run_id,parameters,metric,value,unit,limit_min,limit_max,pass,fail_reason,source_log\n";

test("report generator uses stable flat results and ignores historical nested artifacts", () => {
  const workspace = mkdtempSync(join(tmpdir(), "eda-harness-report-"));
  try {
    mkdirSync(join(workspace, "results", "old"), { recursive: true });
    mkdirSync(join(workspace, "tests"), { recursive: true });
    writeFileSync(join(workspace, "verification_plan.md"), "# Demo Verification Plan\n\n## DUT Interface\n\nPublic pins only.\n");
    writeFileSync(join(workspace, "testbench_implementation_plan.md"), "# Implementation Plan\n");
    writeFileSync(join(workspace, "tests", "testbench_manifest.json"), JSON.stringify({ schema_version: 1, groups: [{ name: "dc_group", order: 1, metrics: "results/dc_group_metrics.csv", log: "results/dc_group.log", artifacts: [] }] }));
    writeFileSync(join(workspace, "results", "dc_group_metrics.csv"), header + "dc_group,REQ-1,nominal,,vout,1,V,0.9,1.1,1,,results/dc_group.log\n");
    writeFileSync(join(workspace, "results", "dc_group.log"), "SUMMARY test=dc_group runs=1 results=1 fail_count=0\n");
    writeFileSync(join(workspace, "results", "old", "stale_metrics.csv"), header + "stale,REQ-X,old,,bad,0,V,1,2,0,stale,old.log\n");
    const result = spawnSync(process.env.PYTHON ?? "python3", [generator, "--suite-root", workspace, "--no-pdf"], { encoding: "utf8", env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" } });
    assert.equal(result.status, 0, result.stdout + result.stderr);
    const report = readFileSync(join(workspace, "test_report.md"), "utf8");
    assert.match(report, /Overall result: \*\*PASS\*\*/);
    assert.match(report, /`dc_group`/);
    assert.doesNotMatch(report, /stale/);
  } finally {
    rmSync(workspace, { recursive: true, force: true });
  }
});
