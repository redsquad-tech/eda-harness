import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const skillsRoot = join(root, "src", "skills");
const python = process.env.PYTHON ?? "python3";
const groupSkill = join(skillsRoot, "create-maestro-test-setup-il-from-ngspice-group");
const projectSkill = join(skillsRoot, "create-maestro-project-il-generator-from-test-setup-il-files");

const fragment = `; EDA_HARNESS_GROUP: dc_group
; EDA_HARNESS_TESTS: 1
; EDA_HARNESS_OUTPUTS: 1
; EDA_HARNESS_CORNERS: 1
; EDA_HARNESS_ANALYSIS: dc
maeCreateTest(?name testName ?lib lib ?cell suiteCell ?view configView ?session sess)
ehSetAnalysis(sess testName "dc" nil)
ehAddOutput(sess testName "v(out)")
ehSetSpec(sess testName "v(out)" 0.0 1.0)
`;

test("pipeline skill contracts are independent and contain no forced approval gates", () => {
  const skills = [
    "create-verification-plan-from-spec",
    "create-mock-dut-from-verification-plan",
    "create-testbench-implementation-plan-from-verification-plan",
    "create-ngspice-testbench-group-from-implementation-plan",
    "create-maestro-test-setup-il-from-ngspice-group",
    "create-maestro-project-il-generator-from-test-setup-il-files",
  ];
  const forbidden = [/ask (?:the user )?whether to continue/i, /do not (?:move|proceed) to the next/i, /one group per iteration/i, /stop and ask/i];
  for (const name of skills) {
    const text = readFileSync(join(skillsRoot, name, "SKILL.md"), "utf8");
    for (const pattern of forbidden) assert.doesNotMatch(text, pattern, name);
  }
});

test("group validator accepts a normalized fragment and rejects suite ownership", () => {
  const directory = mkdtempSync(join(tmpdir(), "eda-harness-group-"));
  try {
    const path = join(directory, "dc_group.il");
    writeFileSync(path, fragment);
    const validator = join(groupSkill, "scripts", "validate_group_setup.py");
    assert.equal(spawnSync(python, [validator, path, "--group", "dc_group"], { encoding: "utf8" }).status, 0);
    writeFileSync(path, fragment + "\nmaeSaveSetup()\n");
    assert.notEqual(spawnSync(python, [validator, path, "--group", "dc_group"], { encoding: "utf8" }).status, 0);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("project assembler creates one portable suite with exact runtime environment", () => {
  const directory = mkdtempSync(join(tmpdir(), "eda-harness-project-"));
  try {
    mkdirSync(join(directory, "tests"), { recursive: true });
    mkdirSync(join(directory, "cadence_export", "maestro_setup"), { recursive: true });
    writeFileSync(join(directory, "tests", "dc_group.sp"), ".SUBCKT tb_top in out\nR1 in out 1k\n.ENDS tb_top\n");
    writeFileSync(join(directory, "tests", "testbench_manifest.json"), JSON.stringify({ schema_version: 1, groups: [{ name: "dc_group", order: 1, fixture: "tests/dc_group.sp" }] }));
    writeFileSync(join(directory, "dut.scs"), "subckt dut in out\nR1 (in out) resistor r=1k\nends dut\n");
    writeFileSync(join(directory, "cadence_export", "model_bindings.toml"), 'version = 1\n[common]\nmodels = []\n[corners.nominal]\nmodels = [{ file = "models/core.scs", section = "nominal" }]\n');
    writeFileSync(join(directory, "cadence_export", "maestro_setup", "dc_group.il"), fragment);

    const assembler = join(projectSkill, "scripts", "create_generate_il.py");
    const result = spawnSync(python, [assembler, "--workspace", directory, "--dut", join(directory, "dut.scs"), "--suite-cell", "tb_top"], { encoding: "utf8" });
    assert.equal(result.status, 0, result.stdout + result.stderr);
    const generate = readFileSync(join(directory, "cadence_export", "generate.il"), "utf8");
    const makefile = readFileSync(join(directory, "cadence_export", "Makefile"), "utf8");
    assert.equal((generate.match(/maeOpenSetup/g) ?? []).length, 2); // call plus failure text
    assert.equal((generate.match(/maeSaveSetup/g) ?? []).length, 1);
    assert.doesNotMatch(generate, /ehWriteValidation\([\s\S]*?\n\s+t\n\s+t\n\s+t\n/);
    assert.equal((generate.match(/maestroView\)/g) ?? []).length >= 1, true);
    for (const name of ["PDK_PATH", "CADENCE_LIB", "CADENCE_WORKDIR"]) assert.ok(makefile.includes(name));
    for (const forbidden of ["vs55", "dcOp", "chmod", "chown", "setfacl", "sudo", "EDA_HARNESS_EXPORT_DIR", "EDA_HARNESS_CDSTEXT"])
      assert.ok(!(makefile + generate).includes(forbidden), forbidden);
    assert.equal((generate.match(/ddDeleteObj\(ddGetObj\(lib suiteCell maestroView\)\)/g) ?? []).length, 1);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

function verify(logText, validation) {
  const directory = mkdtempSync(join(tmpdir(), "eda-harness-cadence-"));
  try {
    const log = join(directory, "import.log");
    const record = join(directory, "validation.json");
    writeFileSync(log, logText);
    writeFileSync(record, JSON.stringify(validation));
    return spawnSync(python, [join(projectSkill, "assets", "verify_export.py"), log, record], { encoding: "utf8" });
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
}

const validRecord = { status: "ok", expected_tests: 2, actual_tests: 2, analyses_valid: true, outputs_valid: true, corners_valid: true };

test("Cadence verifier rejects warnings and partial state", () => {
  assert.equal(verify("EDA_HARNESS_EXPORT_OK tests=2\n", validRecord).status, 0);
  assert.notEqual(verify("WARNING analysis changed\nEDA_HARNESS_EXPORT_OK tests=2\n", validRecord).status, 0);
  assert.notEqual(verify("EDA_HARNESS_EXPORT_OK tests=1\n", { ...validRecord, actual_tests: 1 }).status, 0);
});
