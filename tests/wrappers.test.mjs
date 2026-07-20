import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const python = process.env.PYTHON ?? "python3";
const wrappers = [
  "src/skills/hdl21-to-openaccess/scripts/hdl21_to_openaccess.py",
  "src/skills/hdl21-to-png/scripts/hdl21_to_png.py",
  "src/skills/openaccess-to-hdl21/scripts/openaccess_to_hdl21.py",
  "src/skills/test2report/scripts/generate_test_report.py",
  "src/skills/test2report/scripts/render_report_pdf.py",
  "src/skills/implementation-plan-to-testbenches/assets/run_test.py",
  "src/skills/testbenches-to-cadence/assets/verify_export.py",
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

test("bundled SPICE converter creates an xschem schematic", () => {
  const temporary = mkdtempSync(join(tmpdir(), "eda-harness-spice-"));
  try {
    const source = join(temporary, "divider.sp");
    const output = join(temporary, "schematic");
    writeFileSync(
      source,
      ".subckt divider vin vout vss\nR1 vin vout 1k\nR2 vout vss 2k\n.ends divider\n",
    );
    const moduleRoot = join(root, "src", "skills", "draw-schem", "scripts");
    const result = spawnSync(python, ["-m", "spice2xschem", source, "--output", output], {
      cwd: root,
      encoding: "utf8",
      env: {
        ...process.env,
        PYTHONDONTWRITEBYTECODE: "1",
        PYTHONPATH: [moduleRoot, process.env.PYTHONPATH].filter(Boolean).join(delimiter),
      },
    });
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.ok(readdirSync(output).some((name) => name.endsWith(".sch")));
  } finally {
    rmSync(temporary, { recursive: true, force: true });
  }
});
