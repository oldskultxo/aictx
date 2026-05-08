# Contributing to AICTX

Thanks for helping improve AICTX.

AICTX is a repo-local continuity runtime for coding agents. Good contributions make it easier to install, understand, test, and trust in real repositories.

## Good first contributions

Useful first contributions include:

- try AICTX in a real repo and report confusing setup steps;
- improve docs for Codex, Claude, or generic agents;
- add examples of useful `aictx resume` capsules;
- test `install` / `init` on Windows, Linux, and macOS;
- improve demo reproducibility;
- clarify Failure Memory, Work State, RepoMap, or portability docs;
- add focused tests for edge cases you find.

## Development setup

From a fresh checkout:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m pip install pytest build
```

If you need RepoMap support:

```bash
python -m pip install -e '.[repomap]'
python -m pip install pytest build
```

## Validation

Run the focused test relevant to your change when possible. For broad validation:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q
```

For packaging checks:

```bash
python -m build
```

## Documentation contributions

For README changes, keep the top half product-oriented:

```text
what problem -> quick example -> demo signal -> install -> how it works
```

Move deep implementation detail to `docs/TECHNICAL_OVERVIEW.md` unless it is needed for first-time understanding.

When documenting runtime commands:

- normal startup uses `aictx resume --repo . --task "<task goal>" --json`;
- normal finalization uses `aictx finalize --repo . --status success|failure --summary "<what happened>" --json`;
- internal commands are for wrappers, hooks, diagnostics, and advanced integrations.

## Safety and claims

Do not overclaim.

AICTX improves continuity when agents or integrations cooperate with the runtime contract. It does not guarantee correctness, productivity gains, speedups, or token savings.

Use observed evidence and measured demo data carefully. If a result comes from one demo pair, describe it as directional evidence, not a universal benchmark.

## Pull request checklist

Before opening a PR:

- [ ] focused tests pass;
- [ ] docs and CLI examples match actual commands;
- [ ] README changes remain product-oriented;
- [ ] technical details are linked from or moved to `docs/TECHNICAL_OVERVIEW.md`;
- [ ] no generated `.aictx/` runtime artifacts are committed unless intentionally testing portability.
