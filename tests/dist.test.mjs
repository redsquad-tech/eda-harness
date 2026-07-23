import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, join, relative, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const archive = process.env.DIST_FILE;
const mcpb = process.env.MCPB_BIN;
const sourceManifest = JSON.parse(readFileSync(join(root, "src", "manifest.json"), "utf8"));

function filesBelow(directory) {
  const files = [];
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) files.push(...filesBelow(path));
    if (entry.isFile()) files.push(path);
  }
  return files;
}

test("MCPB checksum, metadata, and payload are valid", () => {
  assert.ok(archive && existsSync(archive), "DIST_FILE must point to the built MCPB");
  assert.ok(mcpb && existsSync(mcpb), "MCPB_BIN must point to the pinned CLI");

  const checksum = readFileSync(`${archive}.sha256`, "utf8").trim().split(/\s+/);
  const digest = createHash("sha256").update(readFileSync(archive)).digest("hex");
  assert.equal(checksum[0], digest);
  assert.equal(checksum[1], basename(archive));

  const info = spawnSync(mcpb, ["info", archive], { cwd: root, encoding: "utf8" });
  assert.equal(info.status, 0, info.stdout + info.stderr);

  const temporary = mkdtempSync(join(tmpdir(), "eda-harness-mcpb-"));
  const unpacked = join(temporary, "bundle");
  try {
    const unpack = spawnSync(mcpb, ["unpack", archive, unpacked], { cwd: root, encoding: "utf8" });
    assert.equal(unpack.status, 0, unpack.stdout + unpack.stderr);

    for (const required of ["manifest.json", "package.json", "LICENSE", "server/index.mjs"]) {
      assert.ok(existsSync(join(unpacked, required)), `bundle is missing ${required}`);
    }
    const forbiddenRoots = [
      ".agents",
      ".codex-plugin",
      ".github",
      "analytics",
      "build",
      "codex",
      "dist",
      "packaging",
      "scripts",
      "tests",
    ];
    for (const forbidden of forbiddenRoots) {
      assert.ok(!existsSync(join(unpacked, forbidden)), `bundle contains ${forbidden}`);
    }

    const sourceSkills = readdirSync(join(root, "src", "skills"))
      .filter((name) => statSync(join(root, "src", "skills", name)).isDirectory())
      .sort();
    const bundledSkills = readdirSync(join(unpacked, "skills"))
      .filter((name) => existsSync(join(unpacked, "skills", name, "SKILL.md")))
      .sort();
    assert.deepEqual(bundledSkills, sourceSkills);

    const manifest = JSON.parse(readFileSync(join(unpacked, "manifest.json"), "utf8"));
    const packageJson = JSON.parse(readFileSync(join(unpacked, "package.json"), "utf8"));
    assert.equal(manifest.version, sourceManifest.version);
    assert.equal(packageJson.version, manifest.version);
    assert.ok(existsSync(join(unpacked, "node_modules", "@modelcontextprotocol", "sdk")));
    assert.ok(!existsSync(join(unpacked, "node_modules", "@anthropic-ai", "mcpb")));
    assert.ok(!existsSync(join(unpacked, "node_modules", "yaml")));

    for (const file of filesBelow(unpacked)) {
      const path = relative(unpacked, file);
      assert.ok(!path.includes("__pycache__"), `bundle contains cache ${path}`);
      assert.ok(!path.endsWith(".pyc") && !path.endsWith(".pyo"), `bundle contains cache ${path}`);
    }
  } finally {
    rmSync(temporary, { recursive: true, force: true });
  }
});
