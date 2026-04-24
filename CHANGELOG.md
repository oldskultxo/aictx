# Changelog

## Unreleased

No unreleased changes.

## 4.0.0 - 2026-04-24

### Changed
- Promoted AICTX from the `3.1.x` execution-memory line to the `4.0.0` repo-local continuity runtime contract.
- Standardized continuity artifacts under `.aictx/continuity/` for session identity, handoff, decisions, semantic repo state, staleness, dedupe, and continuity metrics.
- Strengthened continuity loading and reuse with handoff memory, decision memory, semantic repo memory, cross-memory reuse, staleness handling, and truthful continuity summaries.
- Added visible startup banner behavior with show-once-per-visible-session semantics.
- Activated conservative packet/context middleware for non-trivial work and propagated real packet usage through runtime telemetry.
- Improved failure learning, failure-aware startup context, and real-usage reporting for debugging-oriented workflows.
- Improved deterministic `suggest`, `reflect`, and `reuse` guidance with richer signals and better entry-point selection.

### Clarified
- AICTX does not promise hidden state continuity, magical memory, or guaranteed productivity gains.
- Reuse and reporting remain deterministic and evidence-based, using only repo-local stored artifacts and observed execution signals.

## 3.1.0 - 2026-04-24

### Changed
- Clarified and cleaned the v3 CLI/product surface.
- Aligned legacy wrappers with the supported public/internal command layout.
- Improved local development workflow around Python >=3.11.

### Fixed
- Fixed broken legacy wrapper entrypoints that referenced removed top-level commands.

### Internal
- Prepared the codebase for the continuity roadmap without changing the public runtime contract.

## 3.0.1 - 2026-04-23

### Fixed
- `aictx init` now removes legacy repo-local `AGENTS.override.md` managed content instead of leaving stale override files behind after upgrade

## 3.0.0 - 2026-04-23

### Breaking
- `.aictx/memory/source/` is now the canonical repo-local source-knowledge layer
- `common/`, `projects/`, root `index.json`, root `symptoms.json`, and root `protocol.md` are no longer the canonical source layout
- `aictx init` now scaffolds source knowledge inside `.aictx/memory/source/`
- editing guidance now treats `.aictx/memory/source/` as user-editable while `.aictx/boot`, `.aictx/store`, `.aictx/indexes`, `.aictx/metrics`, and similar runtime folders remain generated
- knowledge mods / `.aictx/library` scaffolding were removed
- global metrics aggregation was removed; only per-repo real execution reporting remains

### Changed
- repo knowledge ingestion now reads from `.aictx/memory/source/` and preserves legacy-path migration compatibility
- `new-note` now writes into `.aictx/memory/source/projects/<repo>/...` by default
- repo cleanup and repo-native scaffolding now align with the new v3 source/derived split

### Added
- structured execution signal capture with explicit/runtime/heuristic/unknown provenance
- richer explainable strategy ranking across task text, files, entry points, commands, tests, errors, area, and recency
- repo-local failure memory and deterministic area memory
- finalize `agent_summary` and Markdown-friendly `agent_summary_text`
- extended real-usage reporting and non-destructive memory hygiene signals

## 2.0.0 - Unreleased

### Breaking
- `aictx install` no longer modifies global Codex configuration unless `--install-codex-global` is passed
- `aictx init` no longer removes legacy ad hoc memory directories

### Fixed
- `aictx init` preserves existing execution logs, feedback, and strategy memory on re-init
- `.claude/settings.json` is merged instead of overwritten

### Improved
- added dry-run install support
- added deterministic task type inference and explainable strategy ranking
- documented safety, upgrade, and optional global integration behavior

## 1.0.0 - 2026-04-19

- aligned public package metadata with the v1 product scope
- positioned `aictx` as repo-local execution memory for coding agents
- promoted the package to the first stable public v1 release

## 0.5.1 - 2026-04-18

- clarified telemetry limitations and evidence gating language in README and limitations docs
- aligned public claim guidance with `evidence_status` and `claim_label` semantics introduced in 0.5.0
- docs-only patch release (no runtime behavior change)

## 0.5.0 - 2026-04-18

- added benchmark CLI surface:
  - `aictx benchmark run --suite ... --arm A|B|C --out ...`
  - `aictx benchmark report --input ... --format json|md`
- added deterministic A/B/C benchmark artifacts and standardized report outputs (JSON + Markdown)
- introduced telemetry truthfulness model in weekly summary:
  - `evidence_status` and `measurement_basis`
  - additive `metrics.estimated` and nullable `metrics.measured`
  - `sample_requirements` and `sample_gaps`
- enforced evidence guardrails for reporting posture:
  - insufficient sample -> no measured claims
  - measured state requires sufficient sample + complete A/B/C benchmark coverage
- updated global aggregation to exclude `insufficient_data` contributors from savings ranges
- added `contributors_by_status` and global `claim_label` for publication posture (`exploratory` vs `material_repeatable`)
- updated scaffold defaults to include benchmark status and extended weekly summary schema
- expanded docs with benchmark quickstart and README evidence/claim policy

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
- fixed a wheel-install runtime import error in `runtime_memory.py` during `aictx internal boot`
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
