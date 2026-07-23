#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const server = new McpServer({
  name: "eda-harness-skills",
  version: process.env.EDA_HARNESS_VERSION ?? "0.0.1",
});

const transport = new StdioServerTransport();
await server.connect(transport);

async function shutdown() {
  await server.close();
  process.exit(0);
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
