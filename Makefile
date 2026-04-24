PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV_PYTHON) -m pip
AICTX_MODULE := $(VENV_PYTHON) -m aictx
VENV_READY := $(VENV)/.aictx-ready
INSTALL_INPUTS := pyproject.toml Makefile $(shell find src -type f | sort)

.PHONY: check-python venv test smoke package-check ci clean-smoke

check-python:
	@$(PYTHON) -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' || { echo "aictx requires Python >= 3.11. Run with: make test PYTHON=python3.12"; exit 1; }

$(VENV_PYTHON): | check-python
	@if [ ! -x "$(VENV_PYTHON)" ]; then $(PYTHON) -m venv $(VENV); fi

$(VENV_READY): $(VENV_PYTHON) $(INSTALL_INPUTS)
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install --ignore-installed -e . pytest build
	@touch $(VENV_READY)

venv: $(VENV_READY)

test: check-python $(VENV_READY)
	$(VENV_PYTHON) -m pytest -q

clean-smoke:
	rm -rf .tmp/smoke-repo
	mkdir -p .tmp/smoke-repo

smoke: check-python $(VENV_READY) clean-smoke
	$(AICTX_MODULE) init --repo .tmp/smoke-repo --yes --no-register
	$(AICTX_MODULE) internal boot --repo .tmp/smoke-repo >/dev/null
	$(AICTX_MODULE) internal packet --task "debug failing integration" >/dev/null
	$(AICTX_MODULE) internal execution prepare --repo .tmp/smoke-repo --request "review middleware behavior" --agent-id smoke-agent --execution-id smoke-prepare --files-opened src/a.py src/b.py --files-reopened src/a.py > .tmp/smoke-repo/prepared.json
	$(AICTX_MODULE) internal execution finalize --prepared .tmp/smoke-repo/prepared.json --success --validated-learning --files-opened src/a.py src/b.py --files-reopened src/a.py --result-summary "Smoke flow completed." >/dev/null
	$(AICTX_MODULE) report real-usage --repo .tmp/smoke-repo >/dev/null

package-check: check-python $(VENV_READY)
	$(VENV_PYTHON) -m build

ci: test smoke package-check
