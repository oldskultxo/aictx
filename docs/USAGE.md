# Usage guide

## Normal workflow

The intended human workflow is still:

1. install once
2. init a repo
3. use your agent normally

## Install

Public install:

```bash
pip install aictx
```

Then:

```bash
aictx install
```

Editable/development install:

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e . pytest build
```

## Global runtime setup

```bash
aictx install
```

Non-interactive:

```bash
aictx install --yes --workspace-root ~/projects
```

## Init

```bash
aictx init
```

Non-interactive:

```bash
aictx init --repo . --yes
```

Interactive init can persist a repo communication mode:

- `disabled`
- `caveman_lite`
- `caveman_full`
- `caveman_ultra`

## Advanced/internal commands

These are supported, but not the main product surface:

- `aictx boot`
- `aictx query`
- `aictx packet`
- `aictx global`
- `aictx execution prepare|finalize`
- `aictx internal run-execution`

## Runtime consistency checks

Both of these report effective communication policy and source-of-truth details:

```bash
aictx boot --repo .
aictx execution prepare --repo . --request "task" --agent-id demo --execution-id demo-1
```

Use this when validating that repo-local preferences and repo-local state are still aligned.

## Development workflow

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e . pytest build
make test
make smoke
make package-check
```

## Public-package validation

For release validation, also verify a clean wheel install:

```bash
python3 -m venv /tmp/aictx-release-venv
/tmp/aictx-release-venv/bin/pip install dist/aictx-0.3.0-py3-none-any.whl
/tmp/aictx-release-venv/bin/aictx --help
```

## Repo bootstrap status

`aictx boot --repo <path>` now reports repo bootstrap status explicitly:

- `initialized`
- `not_initialized`

That status is separate from communication defaults and helps distinguish missing runtime setup from normal operation.
