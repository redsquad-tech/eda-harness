SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

MCPB := src/node_modules/.bin/mcpb
NPM_STAMP := src/node_modules/.package-lock.json
VERSION := $(shell node -p "require('./src/manifest.json').version")
DIST_FILE := dist/eda-harness-skills-$(VERSION).mcpb
CODEX_MARKETPLACE_DIR := dist/codex-marketplace
CODEX_PLUGIN_DIR := $(CODEX_MARKETPLACE_DIR)/plugins/eda-harness-skills

.PHONY: help bootstrap validate test dist dist-mcpb dist-codex verify-dist verify-mcpb verify-codex ci clean

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9_.-]+:.*## / {printf "%-14s %s\n", $$1, $$2}' Makefile | sort

bootstrap: $(NPM_STAMP) ## Install pinned MCPB development dependencies

$(NPM_STAMP): src/package.json src/package-lock.json
	npm ci --prefix src --ignore-scripts --audit=false

validate: bootstrap ## Validate distribution manifests and all Agent Skills
	$(MCPB) validate src/manifest.json
	node --test tests/skills.test.mjs tests/codex.test.mjs tests/cadence-assets.test.mjs

test: bootstrap ## Run wrapper and MCP protocol tests
	node --test tests/wrappers.test.mjs tests/mcp.test.mjs tests/runner.test.mjs

dist-mcpb: bootstrap validate ## Build and clean the versioned MCPB archive
	mkdir -p dist
	find dist -maxdepth 1 -type f -name 'eda-harness-skills-*.mcpb*' -delete
	$(MCPB) pack src $(DIST_FILE)
	$(MCPB) clean $(DIST_FILE)
	node -e 'const c=require("node:crypto"),f=require("node:fs"),p=process.argv[1],h=c.createHash("sha256").update(f.readFileSync(p)).digest("hex"); f.writeFileSync(p+".sha256", h+"  "+p.split("/").pop()+"\n")' $(DIST_FILE)

dist-codex: validate ## Build the local Codex plugin marketplace
	$(RM) -r $(CODEX_MARKETPLACE_DIR)
	mkdir -p $(CODEX_MARKETPLACE_DIR)/.agents/plugins $(CODEX_PLUGIN_DIR)/.codex-plugin
	cp src/codex/marketplace.json $(CODEX_MARKETPLACE_DIR)/.agents/plugins/marketplace.json
	cp src/codex/plugin.json $(CODEX_PLUGIN_DIR)/.codex-plugin/plugin.json
	cp LICENSE $(CODEX_PLUGIN_DIR)/LICENSE
	cp -R src/skills $(CODEX_PLUGIN_DIR)/skills

dist: dist-mcpb dist-codex ## Build all distribution formats

verify-mcpb: dist-mcpb ## Verify MCPB checksum, metadata, runtime, and contents
	DIST_FILE=$(abspath $(DIST_FILE)) MCPB_BIN=$(abspath $(MCPB)) node --test tests/dist.test.mjs

verify-codex: dist-codex ## Verify the Codex plugin marketplace and payload
	CODEX_MARKETPLACE_DIR=$(abspath $(CODEX_MARKETPLACE_DIR)) node --test tests/codex-dist.test.mjs

verify-dist: verify-mcpb verify-codex ## Verify every distribution format

ci: validate test verify-dist ## Run the complete CI pipeline

clean: ## Remove generated dependencies, archives, and caches
	$(RM) -r src/node_modules dist
	find . -type d -name __pycache__ -prune -exec $(RM) -r {} +
