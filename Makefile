SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

APT ?= sudo apt-get
SYS_PACKAGES := xschem ngspice python3 python3-venv python3-pip git

.PHONY: help sysdeps test

VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
VOLARE := $(VENV)/bin/volare
XSCHEM := $(VENV)/bin/xschem
VOLARE_PDKS_DIR := pdks
VOLARE_PDK_NAME := sky130
VOLARE_PDK_HASH := 0fe599b2afb6708d281543108caf8310912f54af
PDK_DIR := $(VOLARE_PDKS_DIR)/sky130A

DEVICE ?=
ifeq ($(firstword $(MAKECMDGOALS)),test)
  ifeq ($(DEVICE),)
    DEVICE := $(word 2,$(MAKECMDGOALS))
  endif
  ifneq ($(DEVICE),)
    $(eval $(DEVICE):;@:)
  endif
endif

DEVICE_PKG := $(patsubst devices/%,%,$(DEVICE))
ACCEPT_RUNNER := devices/$(DEVICE_PKG)/tests/run_acceptance.py


help: ## Show targets
	@grep -E '^[a-zA-Z0-9_.-]+:.*## ' Makefile | sort | awk 'BEGIN {FS = ":.*## "}; {printf "%-16s %s\n", $$1, $$2}'

sysdeps: ## Install system dependencies via apt
	$(APT) update
	$(APT) install -y $(SYS_PACKAGES)

init: ## Create virtualenv
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r dev-requirements.txt
	mkdir -p $(VOLARE_PDKS_DIR)
	PDK_ROOT=$(VOLARE_PDKS_DIR) $(VOLARE) enable --pdk $(VOLARE_PDK_NAME) $(VOLARE_PDK_HASH)
	git init
	git add .
	git commit -m "Initial commit"

test: ## Run acceptance tests for a device: make test devices/<device> or make test DEVICE=<device>
	@if [ -z "$(DEVICE_PKG)" ]; then \
		echo "Usage: make test devices/<device> or make test DEVICE=<device>"; \
		exit 2; \
	fi
	@if [ ! -f "$(ACCEPT_RUNNER)" ]; then \
		echo "Acceptance runner not found: $(ACCEPT_RUNNER)"; \
		exit 2; \
	fi
	@runner_py="$(PY)"; \
	if ! "$$runner_py" -c 'import hdl21' >/dev/null 2>&1; then \
		runner_py="python3"; \
	fi; \
	PDK_ROOT=$(VOLARE_PDKS_DIR) "$$runner_py" -m devices.$(subst /,.,$(DEVICE_PKG)).tests.run_acceptance
