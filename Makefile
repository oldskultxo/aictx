PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
VENV_AICTX := $(VENV)/bin/aictx

.PHONY: venv test smoke package-check ci

venv:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PIP) install -e . pytest build

test: venv
	$(VENV_PYTHON) -m pytest -q

smoke: venv
	rm -rf .tmp/smoke-repo
	mkdir -p .tmp/smoke-repo
	$(VENV_AICTX) init --repo .tmp/smoke-repo --yes --no-register
	$(VENV_AICTX) boot --repo .tmp/smoke-repo >/dev/null
	$(VENV_AICTX) packet --task "debug failing integration" >/dev/null
	$(VENV_AICTX) execution prepare --repo .tmp/smoke-repo --request "review middleware behavior" --agent-id smoke-agent --execution-id smoke-prepare > .tmp/smoke-repo/prepared.json
	$(VENV_AICTX) execution finalize --prepared .tmp/smoke-repo/prepared.json --success --validated-learning --result-summary "Smoke flow completed." >/dev/null

package-check: venv
	$(VENV_PYTHON) -m build

ci: test smoke package-check
