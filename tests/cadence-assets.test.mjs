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
const assembler = join(projectSkill, "scripts", "create_generate_il.py");

function groupFragment(group, testNames) {
  const lines = [
    `; EDA_HARNESS_GROUP: ${group}`,
    `; EDA_HARNESS_TESTS: ${testNames.join(",")}`,
  ];
  for (const testName of testNames) {
    lines.push(
      `testName = "${testName}"`,
      "ehCreateTest(sess testName lib suiteCell configView)",
      'ehSetTestVar(sess testName "TB_VDD" "1.2")',
      'ehSetAnalysis(sess testName "tran" `(("stop" "10u") ("maxstep" "1n")))',
      'ehAddWaveform(sess testName "aout" "/aout")',
      'ehAddMetric(sess testName "output_max" sprintf(nil "ymax(%s)" ehVT("/aout")))',
      'ehSetMaximum(sess testName "output_max" "1.2")',
    );
  }
  const applicable = testNames.map((name) => `"${name}"`).join(" ");
  lines.push(
    "let((cornerName applicableTests)",
    `  cornerName = "${group}__tt_27"`,
    "  ehCreateCorner(sess cornerName)",
    '  ehSetCornerVar(sess cornerName "temperature" "27")',
    '  ehSetCornerVar(sess cornerName "TB_VDD" "1.2")',
  );
  for (const [index, testName] of testNames.entries()) {
    lines.push(
      `  testName = "${testName}"`,
      `  ehAddCornerModel(sess cornerName "${group}__model_${index + 1}" strcat(pdkPath "/models/core.scs") "nominal" testName)`,
    );
  }
  lines.push(
    `  applicableTests = list(${applicable})`,
    "  generatedCornerAssignments = cons(",
    "    list(cornerName applicableTests)",
    "    generatedCornerAssignments",
    "  )",
    ")",
  );
  return `${lines.join("\n")}\n`;
}

function createWorkspace(groups) {
  const directory = mkdtempSync(join(tmpdir(), "eda-harness-project-"));
  mkdirSync(join(directory, "tests"), { recursive: true });
  mkdirSync(join(directory, "cadence_export", "maestro_setup"), { recursive: true });
  const manifestGroups = [];
  for (const [index, group] of groups.entries()) {
    const fixture = `tests/${group.name}.sp`;
    writeFileSync(
      join(directory, fixture),
      ".SUBCKT tb_top in out\nR1 in out 1k\n.ENDS tb_top\n",
    );
    writeFileSync(
      join(directory, "cadence_export", "maestro_setup", `${group.name}.il`),
      group.fragment ?? groupFragment(group.name, group.tests),
    );
    manifestGroups.push({ name: group.name, order: index + 1, fixture });
  }
  writeFileSync(
    join(directory, "tests", "testbench_manifest.json"),
    JSON.stringify({ schema_version: 1, groups: manifestGroups }),
  );
  writeFileSync(
    join(directory, "dut.scs"),
    "subckt dut in out\nR1 (in out) resistor r=1k\nends dut\n",
  );
  writeFileSync(
    join(directory, "cadence_export", "model_bindings.toml"),
    'version = 1\n[common]\nmodels = []\n[corners.nominal]\nmodels = [{ file = "models/core.scs", section = "nominal" }]\n',
  );
  return directory;
}

function assemble(directory) {
  return spawnSync(
    python,
    [assembler, "--workspace", directory, "--dut", join(directory, "dut.scs"), "--suite-cell", "tb_top"],
    { encoding: "utf8" },
  );
}

function generatedTests(generate) {
  const match = generate.match(/expectedTests = list\(([\s\S]*?)\n\s*\)/);
  assert.ok(match, "generated expectedTests list is missing");
  return [...match[1].matchAll(/"([^"]+)"/g)].map((item) => item[1]);
}

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

test("project assembler supports one group with one exact test", () => {
  const directory = createWorkspace([{ name: "enable", tests: ["enable__tran"] }]);
  try {
    const result = assemble(directory);
    assert.equal(result.status, 0, result.stdout + result.stderr);
    const generate = readFileSync(join(directory, "cadence_export", "generate.il"), "utf8");
    assert.deepEqual(generatedTests(generate), ["enable__tran"]);
    assert.equal((generate.match(/\bsess\s*=\s*maeOpenSetup\s*\(/g) ?? []).length, 1);
    assert.equal((generate.match(/\bmaeCloseSession\s*\(/g) ?? []).length, 1);
    assert.match(generate, /missing Maestro test/);
    assert.match(generate, /unexpected Maestro test/);
    assert.doesNotMatch(generate, /actualTests\s*=\s*actualTests\s*\+/);
    assert.doesNotMatch(generate, /validated(?:Analyses|Outputs|Corners)/);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("project assembler supports three tests in one group and ordered corner setup", () => {
  const tests = ["dac__static", "dac__rise", "dac__fall"];
  const directory = createWorkspace([{ name: "dac", tests }]);
  try {
    const result = assemble(directory);
    assert.equal(result.status, 0, result.stdout + result.stderr);
    const generate = readFileSync(join(directory, "cadence_export", "generate.il"), "utf8");
    assert.deepEqual(generatedTests(generate), tests);
    const createCorner = generate.indexOf("ehCreateCorner(sess cornerName)");
    const cornerVar = generate.indexOf("ehSetCornerVar(sess cornerName");
    const cornerModel = generate.indexOf("ehAddCornerModel(sess cornerName");
    const registration = generate.indexOf("generatedCornerAssignments = cons(");
    assert.ok(createCorner < cornerVar && cornerVar < cornerModel && cornerModel < registration);
    assert.match(generate, /\?disableTests disabledTests/);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("project assembler preserves exact test order across unequal groups", () => {
  const directory = createWorkspace([
    { name: "dac", tests: ["dac__static", "dac__rise", "dac__fall"] },
    { name: "enable", tests: ["enable__tran"] },
  ]);
  try {
    const result = assemble(directory);
    assert.equal(result.status, 0, result.stdout + result.stderr);
    const generate = readFileSync(join(directory, "cadence_export", "generate.il"), "utf8");
    assert.deepEqual(generatedTests(generate), [
      "dac__static",
      "dac__rise",
      "dac__fall",
      "enable__tran",
    ]);
    assert.match(result.stdout, /groups=2 tests=4/);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("project assembler rejects duplicate test names within and across groups", () => {
  const local = createWorkspace([
    { name: "dac", tests: ["dac__static"], fragment: "; EDA_HARNESS_GROUP: dac\n; EDA_HARNESS_TESTS: dac__static,dac__static\n" },
  ]);
  try {
    const result = assemble(local);
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /duplicate Maestro test name/);
  } finally {
    rmSync(local, { recursive: true, force: true });
  }

  const global = createWorkspace([
    { name: "dac", tests: ["shared__tran"] },
    { name: "enable", tests: ["shared__tran"] },
  ]);
  try {
    const result = assemble(global);
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /duplicate Maestro test name/);
  } finally {
    rmSync(global, { recursive: true, force: true });
  }
});

test("project assembler enforces only the structural fragment boundary", () => {
  const invalidFragments = [
    ["empty tests", "; EDA_HARNESS_GROUP: dac\n; EDA_HARNESS_TESTS:\n"],
    ["wrong group", "; EDA_HARNESS_GROUP: other\n; EDA_HARNESS_TESTS: dac__tran\n"],
    ["obsolete metadata", "; EDA_HARNESS_GROUP: dac\n; EDA_HARNESS_TESTS: dac__tran\n; EDA_HARNESS_OUTPUTS: 1\n"],
    ["placeholder", "; EDA_HARNESS_GROUP: dac\n; EDA_HARNESS_TESTS: dac__tran\n{{TODO}}\n"],
    ["suite lifecycle", "; EDA_HARNESS_GROUP: dac\n; EDA_HARNESS_TESTS: dac__tran\nmaeSaveSetup()\n"],
    ["direct Maestro", "; EDA_HARNESS_GROUP: dac\n; EDA_HARNESS_TESTS: dac__tran\nmaeCreateTest(testName)\n"],
    ["direct AXL", "; EDA_HARNESS_GROUP: dac\n; EDA_HARNESS_TESTS: dac__tran\naxlGetCorner(nil \"dac\")\n"],
  ];
  for (const [label, fragment] of invalidFragments) {
    const directory = createWorkspace([{ name: "dac", tests: ["dac__tran"], fragment }]);
    try {
      const result = assemble(directory);
      assert.notEqual(result.status, 0, `${label}: ${result.stdout}${result.stderr}`);
    } finally {
      rmSync(directory, { recursive: true, force: true });
    }
  }
});

test("Maestro API adapter exposes the exact wrapper contract", () => {
  const api = readFileSync(join(projectSkill, "assets", "eda_harness_api.il"), "utf8");
  const template = readFileSync(join(projectSkill, "assets", "generate.il.template"), "utf8");
  const groupInstructions = readFileSync(join(groupSkill, "SKILL.md"), "utf8");

  assert.match(api, /procedure\(ehCreateTest[\s\S]*?maeCreateTest\(\s*testName[\s\S]*?\?simulator "spectre"/);
  assert.doesNotMatch(api, /maeCreateTest\(\s*\?name/);
  assert.doesNotMatch(api, /^\s*simulator "spectre"/m);
  assert.match(api, /procedure\(ehSetTestVar[\s\S]*?\?typeName "test"[\s\S]*?\?typeValue list\(testName\)/);
  assert.match(api, /procedure\(ehSetAnalysis[\s\S]*?\(\(kind == "op"\) "dc"\)[\s\S]*?\?options options/);
  assert.match(api, /procedure\(ehAddWaveform[\s\S]*?\?outputType "net"[\s\S]*?\?signalName signalName/);
  assert.match(api, /procedure\(ehAddMetric[\s\S]*?\?outputType "point"[\s\S]*?\?expr expression/);
  for (const helper of ["ehSetMinimum", "ehSetMaximum", "ehSetRange", "ehVT", "ehVF", "ehVAR", "ehCreateCorner", "ehSetCornerVar", "ehAddCornerModel"])
    assert.ok(api.includes(`procedure(${helper}`), helper);
  assert.match(api, /procedure\(ehSetMinimum[\s\S]*?\?gt value/);
  assert.match(api, /procedure\(ehSetMaximum[\s\S]*?\?lt value/);
  assert.match(api, /procedure\(ehSetRange[\s\S]*?\?gt minimum[\s\S]*?\?lt maximum/);
  for (const expression of ["VT", "VF", "VAR"])
    assert.ok(api.includes(`${expression}(\\\"%s\\\")`), expression);
  assert.doesNotMatch(api, /procedure\(eh(?:AnalysisName|AddOutput|SetSpec|ConfigureCorner)/);

  assert.match(template, /generatedCornerAssignments = nil/);
  assert.match(template, /maeGetSetup\([\s\S]*?\?typeName "tests"/);
  assert.match(template, /maeSaveSetup\([\s\S]*?maeCloseSession\(/);
  assert.doesNotMatch(template, /validated(?:Analyses|Outputs|Corners)/);
  assert.doesNotMatch(template, /EXPECTED_TEST_COUNT/);

  assert.match(groupInstructions, /Create one or more Maestro tests per group\./);
  assert.match(groupInstructions, /Read the entire `\.control` block\./);
  assert.match(groupInstructions, /Escape every quote[\s\S]*?`\\"`/);
  assert.doesNotMatch(groupInstructions, /^; EDA_HARNESS_(?:OUTPUTS|CORNERS|ANALYSIS):/m);
  assert.doesNotMatch(groupInstructions, /validate_group_setup\.py/);
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

const validRecord = { status: "ok", expected_tests: 2, actual_tests: 2 };

test("Cadence verifier accepts only the minimal exact validation record", () => {
  assert.equal(verify("EDA_HARNESS_EXPORT_OK tests=2\n", validRecord).status, 0);
  assert.notEqual(verify("WARNING analysis changed\nEDA_HARNESS_EXPORT_OK tests=2\n", validRecord).status, 0);
  assert.notEqual(verify("EDA_HARNESS_EXPORT_OK tests=1\n", { ...validRecord, actual_tests: 1 }).status, 0);
  assert.notEqual(verify("EDA_HARNESS_EXPORT_OK tests=2\n", { ...validRecord, analyses_valid: true }).status, 0);
});
