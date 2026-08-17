import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const python = process.env.PYTHON ?? "python3";
const wrappers = [
  "src/skills/create-verification-report-from-ngspice-results/scripts/generate_test_report.py",
  "src/skills/create-verification-report-from-ngspice-results/scripts/render_report_pdf.py",
  "src/skills/create-ngspice-testbench-group-from-implementation-plan/assets/run_test.py",
  "src/skills/create-maestro-project-il-generator-from-test-setup-il-files/scripts/create_generate_il.py",
  "src/skills/create-maestro-project-il-generator-from-test-setup-il-files/assets/verify_export.py",
];

test("bundled Python command wrappers expose help", () => {
  for (const wrapper of wrappers) {
    const result = spawnSync(python, [wrapper, "--help"], {
      cwd: root,
      encoding: "utf8",
      env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
    });
    assert.equal(result.status, 0, `${wrapper}: ${result.stdout}${result.stderr}`);
  }
});
