import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { createInterface } from "node:readline";
import { join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const serverPath = join(root, "src", "server", "index.mjs");
const version = JSON.parse(readFileSync(join(root, "src", "manifest.json"), "utf8")).version;

test("empty MCP server initializes and responds to ping", async () => {
  const child = spawn(process.execPath, [serverPath], {
    cwd: root,
    env: { ...process.env, EDA_HARNESS_VERSION: version },
    stdio: ["pipe", "pipe", "pipe"],
  });
  const lines = createInterface({ input: child.stdout });
  const pending = new Map();
  let nextId = 1;
  let stderr = "";
  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk) => (stderr += chunk));
  lines.on("line", (line) => {
    const message = JSON.parse(line);
    const handler = pending.get(message.id);
    if (handler) {
      pending.delete(message.id);
      handler(message);
    }
  });

  function request(method, params) {
    const id = nextId++;
    return new Promise((resolveRequest, reject) => {
      const timeout = setTimeout(() => {
        pending.delete(id);
        reject(new Error(`timeout waiting for ${method}; stderr=${stderr}`));
      }, 5000);
      pending.set(id, (message) => {
        clearTimeout(timeout);
        resolveRequest(message);
      });
      child.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", id, method, ...(params && { params }) })}\n`);
    });
  }

  try {
    const initialized = await request("initialize", {
      protocolVersion: "2025-11-25",
      capabilities: {},
      clientInfo: { name: "eda-harness-ci", version: "1.0.0" },
    });
    assert.equal(initialized.error, undefined, JSON.stringify(initialized.error));
    assert.deepEqual(initialized.result.capabilities, {});
    assert.equal(initialized.result.serverInfo.name, "eda-harness-skills");
    assert.equal(initialized.result.serverInfo.version, version);

    child.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" })}\n`);
    const ping = await request("ping");
    assert.equal(ping.error, undefined, JSON.stringify(ping.error));
    assert.deepEqual(ping.result, {});
  } finally {
    lines.close();
    child.stdin.end();
    child.kill("SIGTERM");
  }
});
