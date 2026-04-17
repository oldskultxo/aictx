# Usage guide

## Normal workflow

The intended human workflow is still:

1. install once
2. init a repo
3. use your agent normally

## Install

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
