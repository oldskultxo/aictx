PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV_PYTHON) -m pip
AICTX_MODULE := $(VENV_PYTHON) -m aictx
VENV_READY := $(VENV)/.aictx-ready
INSTALL_INPUTS := pyproject.toml Makefile $(shell find src -type f | sort)

.PHONY: venv test smoke package-check ci clean-smoke

$(VENV_PYTHON):
	@if [ ! -x "$(VENV_PYTHON)" ]; then $(PYTHON) -m venv $(VENV); fi

$(VENV_READY): $(VENV_PYTHON) $(INSTALL_INPUTS)
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install --ignore-installed -e . pytest build
	@touch $(VENV_READY)

venv: $(VENV_READY)

test: $(VENV_READY)
	$(VENV_PYTHON) -m pytest -q

clean-smoke:
	rm -rf .tmp/smoke-repo
	mkdir -p .tmp/smoke-repo

smoke: $(VENV_READY) clean-smoke
	$(AICTX_MODULE) init --repo .tmp/smoke-repo --yes --no-register
	$(AICTX_MODULE) boot --repo .tmp/smoke-repo >/dev/null
	$(AICTX_MODULE) packet --task "debug failing integration" >/dev/null
	$(AICTX_MODULE) execution prepare --repo .tmp/smoke-repo --request "review middleware behavior" --agent-id smoke-agent --execution-id smoke-prepare > .tmp/smoke-repo/prepared.json
	$(AICTX_MODULE) execution finalize --prepared .tmp/smoke-repo/prepared.json --success --validated-learning --result-summary "Smoke flow completed." >/dev/null

package-check: $(VENV_READY)
	$(VENV_PYTHON) -m build

ci: test smoke package-check
