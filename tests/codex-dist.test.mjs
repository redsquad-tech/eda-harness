import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { basename, join, relative, resolve, sep } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const marketplaceRoot = process.env.CODEX_MARKETPLACE_DIR;

function filesBelow(directory, base = directory) {
  const files = [];
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    assert.ok(!entry.isSymbolicLink(), `distribution contains symlink ${relative(base, path)}`);
    if (entry.isDirectory()) files.push(...filesBelow(path, base));
    if (entry.isFile()) files.push(relative(base, path).split(sep).join("/"));
  }
  return files.sort();
}

function digest(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

test("Codex marketplace contains only the skills-only plugin payload", () => {
  assert.ok(marketplaceRoot && existsSync(marketplaceRoot), "CODEX_MARKETPLACE_DIR must exist");

  const marketplacePath = join(marketplaceRoot, ".agents", "plugins", "marketplace.json");
  const marketplace = JSON.parse(readFileSync(marketplacePath, "utf8"));
  const entry = marketplace.plugins[0];
  const pluginRoot = resolve(marketplaceRoot, entry.source.path);
  assert.ok(pluginRoot.startsWith(`${resolve(marketplaceRoot)}${sep}`));

  const manifestPath = join(pluginRoot, ".codex-plugin", "plugin.json");
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  assert.equal(basename(pluginRoot), manifest.name);
  assert.equal(entry.name, manifest.name);
  assert.deepEqual(
    manifest,
    JSON.parse(readFileSync(join(root, "src", "codex", "plugin.json"), "utf8")),
  );
  assert.deepEqual(
    marketplace,
    JSON.parse(readFileSync(join(root, "src", "codex", "marketplace.json"), "utf8")),
  );

  const sourceSkills = join(root, "src", "skills");
  const bundledSkills = join(pluginRoot, "skills");
  const skillFiles = filesBelow(sourceSkills);
  assert.deepEqual(filesBelow(bundledSkills), skillFiles);
  for (const path of skillFiles) {
    assert.equal(digest(join(bundledSkills, path)), digest(join(sourceSkills, path)), path);
  }
  assert.equal(digest(join(pluginRoot, "LICENSE")), digest(join(root, "LICENSE")));

  const expected = [
    ".agents/plugins/marketplace.json",
    "plugins/eda-harness-skills/.codex-plugin/plugin.json",
    "plugins/eda-harness-skills/LICENSE",
    ...skillFiles.map((path) => `plugins/eda-harness-skills/skills/${path}`),
  ].sort();
  assert.deepEqual(filesBelow(marketplaceRoot), expected);
});
