import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const skillsRoot = join(root, "src", "skills");
const requireFromSource = createRequire(join(root, "src", "package.json"));
const { parse } = requireFromSource("yaml");
const expectedSkills = [
  "create-maestro-project-il-generator-from-test-setup-il-files",
  "create-maestro-test-setup-il-from-ngspice-group",
  "create-mock-dut-from-verification-plan",
  "create-ngspice-testbench-group-from-implementation-plan",
  "create-systemverilog-model-from-model-plan",
  "create-systemverilog-model-plan-from-verification-plan",
  "create-testbench-implementation-plan-from-verification-plan",
  "create-verification-plan-from-spec",
  "create-verification-report-from-ngspice-results",
];

function filesBelow(directory) {
  const files = [];
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isSymbolicLink()) {
      assert.fail(`symlink is not allowed in a skill: ${relative(root, path)}`);
    }
    if (entry.isDirectory()) files.push(...filesBelow(path));
    if (entry.isFile()) files.push(path);
  }
  return files;
}

function metadataFor(skillFile) {
  const text = readFileSync(skillFile, "utf8");
  const match = text.match(/^---\s*\n([\s\S]*?)\n---(?:\s*\n|$)/);
  assert.ok(match, `${relative(root, skillFile)} is missing YAML front matter`);
  return { metadata: parse(match[1]), text };
}

test("canonical skills conform to the Agent Skills format", () => {
  const skillNames = readdirSync(skillsRoot)
    .filter((name) => statSync(join(skillsRoot, name)).isDirectory())
    .sort();
  assert.deepEqual(skillNames, expectedSkills);

  for (const name of skillNames) {
    const skillFile = join(skillsRoot, name, "SKILL.md");
    const { metadata } = metadataFor(skillFile);
    assert.equal(metadata.name, name, `${name}: frontmatter name must match its directory`);
    assert.match(name, /^(?!-)(?!.*--)[a-z0-9-]{1,64}(?<!-)$/);
    assert.equal(typeof metadata.description, "string", `${name}: description must be a string`);
    assert.ok(metadata.description.trim().length > 0, `${name}: description is empty`);
    assert.ok(metadata.description.length <= 1024, `${name}: description exceeds 1024 characters`);
  }
});

test("skill payload is portable and Python sources compile", () => {
  const textExtensions = new Set([".il", ".md", ".py", ".toml", ".yaml", ".yml", ".template"]);
  const forbidden = [".agents/", "/home/", "~/.codex"];

  for (const file of filesBelow(skillsRoot)) {
    const extension = file.slice(file.lastIndexOf("."));
    if (!textExtensions.has(extension)) continue;
    const text = readFileSync(file, "utf8");
    for (const needle of forbidden) {
      assert.ok(!text.includes(needle), `${relative(root, file)} contains non-portable path ${needle}`);
    }
    assert.ok(!file.endsWith("agents/openai.yaml"), `${relative(root, file)} is vendor-specific metadata`);

    if (extension === ".py") {
      const result = spawnSync(
        process.env.PYTHON ?? "python3",
        ["-c", "import sys; compile(sys.stdin.read(), sys.argv[1], 'exec')", relative(root, file)],
        { cwd: root, input: text, encoding: "utf8" },
      );
      assert.equal(result.status, 0, `${relative(root, file)}: ${result.stderr}`);
    }
  }
});

test("distribution metadata and license versions stay synchronized", () => {
  const manifest = JSON.parse(readFileSync(join(root, "src", "manifest.json"), "utf8"));
  const packageJson = JSON.parse(readFileSync(join(root, "src", "package.json"), "utf8"));
  const plugin = JSON.parse(readFileSync(join(root, "src", "codex", "plugin.json"), "utf8"));
  const server = readFileSync(join(root, "src", "server", "index.mjs"), "utf8");

  assert.equal(packageJson.version, manifest.version);
  assert.equal(plugin.version, manifest.version);
  assert.equal(manifest.server.entry_point, "server/index.mjs");
  assert.equal(manifest.server.mcp_config.env.EDA_HARNESS_VERSION, manifest.version);
  assert.ok(server.includes(`?? "${manifest.version}"`));
  assert.equal(readFileSync(join(root, "LICENSE"), "utf8"), readFileSync(join(root, "src", "LICENSE"), "utf8"));
});
