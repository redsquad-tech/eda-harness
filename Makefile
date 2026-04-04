SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

APT ?= sudo apt-get
SYS_PACKAGES := xschem ngspice python3 python3-venv python3-pip git

.PHONY: help sysdeps

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
