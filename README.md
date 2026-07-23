# EDA Harness Skills

EDA Harness is an agent-neutral collection of Agent Skills for analog and mixed-signal verification. The skills guide compatible agents from a circuit specification through verification planning, HDL21/ngspice testbench development, reporting, and Cadence/Virtuoso export.

All distribution sources live in [`src`](src): it contains the canonical skills, MCPB sources, Codex metadata, and an intentionally empty MCP compatibility server.

## Included skills

| Skill | Purpose |
| --- | --- |
| `create-verification-plan-from-spec` | Turn a circuit specification into an acceptance verification plan. |
| `create-mock-dut-from-verification-plan` | Create a minimal HDL21/ngspice development DUT when a runnable DUT is unavailable. |
| `create-testbench-implementation-plan-from-verification-plan` | Define the minimum ordered testbench groups and stable outputs. |
| `create-ngspice-testbench-group-from-implementation-plan` | Implement and execute one named group or all unfinished ngspice groups. |
| `create-verification-report-from-ngspice-results` | Build Markdown and optional PDF verification reports. |
| `create-maestro-test-setup-il-from-ngspice-group` | Convert each completed ngspice group into a portable Maestro SKILL fragment. |
| `create-maestro-project-il-generator-from-test-setup-il-files` | Assemble group fragments into one strict, portable Cadence export bundle. |

## Install skills

Each direct child of [`src/skills`](src/skills) is a standalone Agent Skill rooted at `SKILL.md`. Install one skill by copying or linking its directory into a skills location supported by your agent. Install the complete suite by copying or linking all direct children of `src/skills/`.

Clients that install from GitHub paths can address an individual skill as:

```text
redsquad-tech/eda-harness:src/skills/<skill-name>
```

The exact command and destination are client-specific because the Agent Skills specification defines the skill directory format, not one universal package installer.

## MCPB distribution

`make dist-mcpb` creates one `.mcpb` containing all skills and a standards-compliant Node.js MCP server. The server deliberately advertises no tools, resources, or prompts: current skills orchestrate command-line tools from the user's environment.

MCPB hosts install and run the MCP server but do not automatically register arbitrary Agent Skills payloads. To use the bundled skills, extract or inspect the ZIP-compatible `.mcpb` and import or link its `skills/` children according to the target agent.

## Codex plugin distribution

`make dist-codex` creates a local Codex marketplace at `dist/codex-marketplace/`. It contains one skills-only plugin and deliberately excludes the MCP server and Node.js dependencies.

```bash
make dist-codex
codex plugin marketplace add ./dist/codex-marketplace
codex plugin add eda-harness-skills@eda-harness
```

The generated marketplace is a local build artifact. It is not installable directly with `codex plugin marketplace add redsquad-tech/eda-harness`; publish the generated marketplace as the root of a dedicated distribution repository or branch if Git-backed installation is needed later.

## Runtime tools

Individual skills may require Python, HDL21, ngspice, pandoc/LaTeX, or Cadence/Virtuoso. Heavy EDA dependencies and PDKs are neither installed by repository CI nor included in MCPB.

## Development

Repository development requires Node.js 18+ and Python 3.11+. Node dependencies are isolated under `src/node_modules/`; there is no repository Python environment.

```bash
make bootstrap
make ci
```

Targets:

- `make validate` validates the MCPB and Codex metadata plus all skills.
- `make test` runs Python-wrapper smoke tests and the MCP handshake test.
- `make dist-mcpb` runs the official MCPB pack and clean flow, then writes a SHA-256 sidecar.
- `make dist-codex` builds the local skills-only Codex marketplace.
- `make dist` builds both distribution formats in `dist/`.
- `make verify-dist` checks both formats, their metadata, isolation, and complete skill payloads.
- `make clean` removes generated dependencies, archives, and caches.

The bundle version is explicit and must match in `src/manifest.json`, `src/package.json`, and `src/codex/plugin.json`. Before creating a `vX.Y.Z` Git tag, update those files and the server fallback to `X.Y.Z`; CI enforces synchronization.

## Repository layout

```text
src/                    shared distribution sources
  codex/                Codex plugin and marketplace metadata
  manifest.json         MCPB metadata
  package.json          pinned runtime and development dependencies
  server/index.mjs      empty MCP stdio server
  skills/               canonical Agent Skills for both formats
tests/                  Node-based validation and smoke tests
analytics/              curated quality research and benchmark definitions
.github/                 CI and automated review workflows
dist/                    ignored MCPB and Codex marketplace output
```

## License

MIT. See [LICENSE](LICENSE).
