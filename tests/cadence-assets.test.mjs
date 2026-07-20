import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const skillsRoot = join(root, "src", "skills");
const python = process.env.PYTHON ?? "python3";
const pipelineSkills = [
  "spec-to-verification-plan",
  "spec-to-hdl21-mock-dut",
  "verification-plan-to-implementation-plan",
  "implementation-plan-to-testbenches",
  "testbenches-to-cadence",
];

test("pipeline skill contracts are independent and contain no forced approval gates", () => {
  const forbiddenGates = [
    /ask (?:the user )?whether to continue/i,
    /do not (?:move|proceed) to the next/i,
    /one group per iteration/i,
    /stop and ask/i,
  ];
  for (const current of pipelineSkills) {
    const text = readFileSync(join(skillsRoot, current, "SKILL.md"), "utf8");
    for (const pattern of forbiddenGates) assert.doesNotMatch(text, pattern, current);
    for (const sibling of pipelineSkills) {
      if (sibling !== current) assert.ok(!text.includes(sibling), `${current} references ${sibling}`);
    }
  }
});

test("Cadence bundle is portable and recreates the suite only once", () => {
  const assetRoot = join(skillsRoot, "testbenches-to-cadence", "assets");
  const makefile = readFileSync(join(assetRoot, "Makefile.template"), "utf8");
  const generate = readFileSync(join(assetRoot, "generate.il.template"), "utf8");
  const api = readFileSync(join(assetRoot, "eda_harness_api.il"), "utf8");
  const allAssets = makefile + generate + api;

  for (const name of ["PDK_PATH", "CADENCE_LIB", "CADENCE_WORKDIR"]) assert.ok(makefile.includes(name));
  for (const forbidden of ["vs55", "dcOp", "chmod", "chown", "setfacl", "sudo"])
    assert.ok(!allAssets.includes(forbidden), `Cadence assets contain ${forbidden}`);
  assert.equal((generate.match(/ddDeleteObj/g) ?? []).length, 1);
  assert.ok(generate.indexOf("ddDeleteObj") < generate.indexOf("{{GROUP_BLOCKS}}"));
  assert.equal((generate.match(/maeSaveSetup/g) ?? []).length, 1);
  assert.match(api, /kind == "op" \|\| kind == "dc"\) "dc"/);
});

function verify(logText, validation) {
  const directory = mkdtempSync(join(tmpdir(), "eda-harness-cadence-"));
  try {
    const log = join(directory, "import.log");
    const record = join(directory, "validation.json");
    writeFileSync(log, logText);
    writeFileSync(record, JSON.stringify(validation));
    return spawnSync(
      python,
      [join(skillsRoot, "testbenches-to-cadence", "assets", "verify_export.py"), log, record],
      { cwd: root, encoding: "utf8", env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" } },
    );
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
}

const validRecord = {
  status: "ok",
  expected_tests: 2,
  actual_tests: 2,
  analyses_valid: true,
  outputs_valid: true,
  corners_valid: true,
};

test("Cadence verifier accepts a complete suite and rejects warnings or partial state", () => {
  assert.equal(verify("EDA_HARNESS_EXPORT_OK tests=2\n", validRecord).status, 0);
  assert.notEqual(verify("WARNING analysis changed\nEDA_HARNESS_EXPORT_OK tests=2\n", validRecord).status, 0);
  assert.notEqual(verify("EDA_HARNESS_EXPORT_OK tests=1\n", { ...validRecord, actual_tests: 1 }).status, 0);
});
