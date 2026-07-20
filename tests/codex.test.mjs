import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const plugin = JSON.parse(readFileSync(join(root, "src", "codex", "plugin.json"), "utf8"));
const marketplace = JSON.parse(
  readFileSync(join(root, "src", "codex", "marketplace.json"), "utf8"),
);
const mcpb = JSON.parse(readFileSync(join(root, "src", "manifest.json"), "utf8"));
const packageJson = JSON.parse(readFileSync(join(root, "src", "package.json"), "utf8"));
const semver = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$/;

function nonEmptyString(value, field) {
  assert.equal(typeof value, "string", `${field} must be a string`);
  assert.ok(value.trim(), `${field} must not be empty`);
}

test("Codex plugin manifest is complete and skills-only", () => {
  assert.equal(plugin.name, "eda-harness-skills");
  assert.match(plugin.version, semver);
  assert.equal(plugin.version, mcpb.version);
  assert.equal(plugin.version, packageJson.version);
  assert.equal(plugin.skills, "./skills/");
  assert.equal(plugin.author.name, "RedSquad Tech");
  assert.ok(!JSON.stringify(plugin).includes("[TODO:"));

  for (const field of ["description", "homepage", "repository", "license"]) {
    nonEmptyString(plugin[field], field);
  }
  for (const field of [
    "displayName",
    "shortDescription",
    "longDescription",
    "developerName",
    "category",
  ]) {
    nonEmptyString(plugin.interface[field], `interface.${field}`);
  }

  assert.ok(Array.isArray(plugin.interface.capabilities));
  assert.ok(plugin.interface.capabilities.length > 0);
  assert.ok(plugin.interface.capabilities.every((value) => typeof value === "string" && value.trim()));
  assert.ok(Array.isArray(plugin.interface.defaultPrompt));
  assert.ok(plugin.interface.defaultPrompt.length >= 1 && plugin.interface.defaultPrompt.length <= 3);
  for (const prompt of plugin.interface.defaultPrompt) {
    nonEmptyString(prompt, "interface.defaultPrompt[]");
    assert.ok(prompt.length <= 128, `default prompt exceeds 128 characters: ${prompt}`);
  }

  for (const url of [plugin.homepage, plugin.repository, plugin.author.url, plugin.interface.websiteURL]) {
    assert.equal(new URL(url).protocol, "https:", `${url} must use HTTPS`);
  }
  for (const forbidden of ["apps", "mcpServers", "hooks"]) {
    assert.ok(!(forbidden in plugin), `skills-only plugin must not declare ${forbidden}`);
  }
});

test("Codex marketplace exposes exactly the bundled plugin", () => {
  assert.equal(marketplace.name, "eda-harness");
  assert.equal(marketplace.interface.displayName, "EDA Harness");
  assert.equal(marketplace.plugins.length, 1);

  const entry = marketplace.plugins[0];
  assert.equal(entry.name, plugin.name);
  assert.deepEqual(entry.source, {
    source: "local",
    path: "./plugins/eda-harness-skills",
  });
  assert.deepEqual(entry.policy, {
    installation: "AVAILABLE",
    authentication: "ON_INSTALL",
  });
  assert.equal(entry.category, plugin.interface.category);
  assert.ok(!("products" in entry.policy));
  assert.ok(entry.source.path.startsWith("./") && !entry.source.path.includes(".."));
});
