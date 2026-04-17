# Changelog

## 0.4.0 - 2026-04-18

- repositioned product messaging to emphasize `runtime contract + execution discipline` as primary value
- expanded docs to make the heuristic nature of routing/ranking/graph behavior explicit
- improved deterministic retrieval ranking with structured score breakdowns
- strengthened task routing and task-type resolution with confidence/evidence/ambiguity signals
- upgraded packet assembly with budgeted intent groups, dedupe, and richer selection reporting
- added day-2/repeated-task value evidence in middleware telemetry (`task_fingerprint`, reuse indicators, repeat-task success proxy)
- updated runner integration handling for structured `repo_scope` entries
- expanded smoke coverage for new telemetry and heuristic packet behavior

## 0.3.1 - 2026-04-18

- fixed a Python 3.11 syntax error in `core_runtime.py` that broke test collection in CI
- fixed a wheel-install runtime import error in `runtime_memory.py` during `aictx boot`
- keeps the public beta distribution flow introduced in `0.3.0`

## 0.3.0 - 2026-04-17

- opened public beta distribution flow for PyPI + GitHub releases
- introduced versioned runtime contract fields: `installed_version` and `engine_capability_version`
- reduced legacy compatibility dependence on historical `installed_iteration`
- added public-package metadata and release automation scaffolding
- documented public install flow and public beta limits more explicitly

## 0.2.0 - 2026-04-17

- hardened runtime preference precedence so repo-local communication settings win over global defaults
- added consistency checks to `boot` and `execution prepare`
- added editable-install developer workflow via `Makefile`
- added CI, packaging checks, license, and release metadata
- improved wrapper and Claude hook degradation when `aictx` is unavailable
- added demo and limitations docs to cut hype and clarify current scope
