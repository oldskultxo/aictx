# Current limitations

`aictx` is usable, but it is not a magic layer that upgrades every coding agent automatically.

## What it does today

- provisions a repo-local runtime contract under `.ai_context_engine/`
- installs repo-native instructions for Codex and Claude Code
- provides wrapped middleware for generic automation
- exposes bootstrap, packet, telemetry, and memory-oriented runtime commands

## What it does not guarantee

- that every runner will fully honor repo instructions or hooks
- that bootstrap memory is always better than direct code inspection
- that telemetry estimates are high-confidence on every project
- that advanced/internal commands are stable enough for broad third-party integrations
- that the current heuristic routing/ranking/graph layers will outperform plain repo inspection on every large or noisy codebase

## Operational limits

- some runtime capabilities are still being extracted from the canonical engine
- global metrics remain best-effort and should be read as directional unless confidence is high
- `0.x` means compatibility is best-effort, not a long-term stability promise
- public PyPI distribution does not change that promise: this is a public beta, not a stability guarantee
- upgrades for already-initialized repos are intended to be safe, but release notes should still be read before broad rollout
