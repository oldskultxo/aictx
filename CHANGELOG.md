# Changelog

## 5.1.0 - 2026-05-02

### Changed
- Implemented self-contained resume capsule first_action, startup guard, anti-runtime startup rule, task-biased entry ranking, and regression tests.

### Fixed
- Replaced parser/CLI-specific resume bias with generic task profile + request-term matching.
- Added path categories/penalties for runtime/generated/metrics/docs/config/source/tests.
- Kept .aictx/** excluded from action targets.
- Allows docs/config/metrics to win only for matching task intent.

## 5.0.0 - 2026-05-02

### Added
- Added the public `aictx resume --repo . --request "<current user request>"` command as the canonical agent-facing continuity query.
- Added structured `aictx resume --json` output for startup automation and JSON tooling.
- Added local generated resume trace artifacts:
  - `.aictx/continuity/resume_capsule.md`
  - `.aictx/continuity/resume_capsule.json`
- Added `aictx advanced` as the public index for diagnostic/building-block commands.
- Added tests covering resume capsule shape, startup/final-summary source separation, JSON pipe validity, compact/full resume output, RepoMap slicing, generated artifact portability, hidden advanced help behavior, agent identity inference, and startup banner policy instructions.

### Changed
- Bumped the documented/runtime package version from `4.7.1` to `5.1.0`.
- Updated generated agent instructions so normal startup runs exactly one continuity command with JSON output:
  - `aictx resume --repo . --request "<current user request>" --json`
- Clarified the lifecycle as `prepare/startup context → resume capsule → work → finalize → final AICTX summary/persistence`.
- Clarified startup banner ownership: normal startup renders `resume.startup_banner_text` or `resume.startup_banner_render_payload`; wrapped execution renders `prepare_execution().startup_banner_text` or `prepare_execution().startup_banner_render_payload`; agents must not render both.
- Repositioned `suggest`, `reuse`, `next`, `task`, `messages`, `map`, `report`, `reflect`, and `internal` as advanced/diagnostic/building-block commands instead of normal startup commands.
- Simplified top-level CLI help to the primary public surface: `install`, `init`, `resume`, `advanced`, `clean`, and `uninstall`.
- Updated docs to steer JSON inspection through `python3 -m json.tool` instead of piping JSON into `python3 -`.

### Fixed
- Fixed `aictx resume` default identity detection so Codex environments produce `codex@<repo>` startup banner labels instead of falling back to `generic@<repo>`.
- Strengthened startup banner policy so agents localize the banner to the user's language and do not consume it with transient progress/status messages that are absent from the final task response.

### Compatibility notes
- Existing advanced commands remain callable; they are hidden from top-level help and listed under `aictx advanced`.
- `aictx resume` does not replace `prepare_execution()`, `finalize_execution()`, startup banner rendering, final AICTX summary generation, or persistence.
- `resume_capsule.*` files are generated local runtime traces and remain excluded from portable continuity.

## 4.7.1 - 2026-04-29

### Fixed
- Introduce a new runtime_compact module to plan and perform compaction of repo runtime artifacts.
- Implements dry-run vs apply modes.
- Wire CLI: add internal compact command (--repo, --apply) and a cli_compact entrypoint.
- Surface maintenance notices in middleware and agent summaries
- Improve report.read_jsonl to skip invalid JSON lines. 

## 4.7.0 - 2026-04-29

### Added
- Added repo-local user-facing message controls with `aictx messages mute`, `aictx messages unmute`, and `aictx messages status`.
- Added `aictx -v` and `aictx --version`.
- Added docs coverage for the new message controls and version-check flows in installation, quickstart, usage, and release guidance.

### Changed
- Polished startup banner text and later-session continuity messaging.
- Updated startup banner rendering semantics so runners prefer structured render payloads when the runtime policy points to them.
- Polished final summary output and aligned the execution-summary docs with the current runtime behavior.
- Hardened AICTX user-visible text localization/translation policy so localized output preserves exact facts and technical tokens.

### Fixed
- Restored compatibility for legacy `task` and `agent` aliases in execution middleware flows.

## 4.6.0 - 2026-04-28

### Added
- Added opt-in git-portable continuity using an AICTX-managed `.gitignore` block and `.aictx/continuity/portability.json` without duplicating canonical artifacts.

## 4.5.3 - 2026-04-28

### Changed
- Reworked README around agent-driven setup and public product clarity.
- Added docs/INSTALLATION.md with install/init flows and example setup answers.
- Added docs/REPOMAP.md and gave RepoMap stronger positioning.
- Added docs/CLEANUP.md.
- Added docs/STRATEGY_MEMORY.md.
- Added docs/HANDOFFS.md.
- Expanded docs/TECHNICAL_OVERVIEW.md into a complete architecture/runtime overview.
- Reframed docs/USAGE.md as advanced command reference.

## 4.5.2 - 2026-04-27

### Fixed
- Handle skipped work-state and git branch detach

## 4.5.1 - 2026-04-27

### Added
- Added minimal branch-safe Work State loading using saved git branch/head context.
- Work State created on a merged feature branch can still load on main when the saved commit is reachable from current HEAD.
- Dirty Work State from another branch is skipped to avoid unsafe continuation.

## 4.5.0 - 2026-04-27

### Added
- Added repo-local Work State under `.aictx/tasks/` with public `aictx task start|status|update|close`.
- Added `aictx task list`, `task show <task-id>`, `task resume <task-id>`, `task status --all`, and close-time `--json-patch` support for stored Work State threads.
- Added `aictx task update --from-file`, compact `changed_fields` update output, internal `--work-state-file`, startup-banner hypothesis rendering, and Work State `recent_statuses` reporting.
- Added secondary `aictx next` visibility for the most recent paused or blocked Work State when no task is active.
- Added active Work State continuity loading to prepare/startup/`aictx next`, plus conservative finalize updates from factual execution evidence or explicit runtime payloads.
- Added compact Work State visibility to `aictx report real-usage` (`active`, `task_id`, `status`, `threads_count`, `last_updated_at`).
- Added `docs/WORK_STATE.md` and updated README/usage/overview/summary/limitations/upgrade docs for the Work State runtime contract.

## 4.4.1 - 2026-04-26

### Fixed
- Published release-hygiene patch with package/docs version aligned to `4.4.1`.
- Added the missing `4.4.0` changelog entry so the release history matches the published package lineage.

## 4.4.0 - 2026-04-26

### Added
- Added toolchain-aware failure capture for wrapped executions and explicit runtime signals.
- Added structured `error_events` with toolchain, phase, severity, message, code, file, line, command, exit code, and fingerprint when observed.
- Added structured failure pattern persistence and lookup across common Python, JavaScript/TypeScript, Go, Rust, Java/JVM, .NET, C/C++, Ruby, PHP, and generic toolchain outputs.
- Added finalize summaries that distinguish new learned failures, repeated known patterns, resolved prior failures, and related failure context that was only considered.

### Changed
- Derived backward-compatible `notable_errors` from structured error events when possible.
- Improved failure summaries to use compact human-readable descriptors for resolved and repeated patterns.
- Updated README and docs to describe AICTX 4.4 failure capture and summary semantics.

## 4.3.0 - 2026-04-26

### Added
- Added RepoMap status visibility to `aictx report real-usage` under a compact `repo_map` section (`enabled`, `available`, `files_indexed`, `symbols_indexed`, `last_refresh_status`).
- Added docs coverage for optional RepoMap setup/usage and realistic limitations.
- Added deterministic RepoMap runtime files and public `aictx map status|refresh|query` operations.
- Added prepared/final/effective task and area classification so finalize can correct provisional typing with observed execution evidence.

### Changed
- Updated continuity integration and docs to keep RepoMap claims factual and non-promissory (no speed/token savings guarantees).
- Updated startup/final-summary rendering and docs to align with the current runtime contract and localized output behavior.

## 4.2.1 - 2026-04-25

### Added
- Added public `aictx next` command for compact, human-readable continuity guidance backed by Continuity Brief v2.
- Added structured `--json` output for `aictx next` with the brief, ranked items, and `why_loaded` evidence.
- Added AICTX next details to `.aictx/continuity/last_execution_summary.md` so compact chat output can stay short while preserving actionable detail.
- Added tests for `aictx next`, Continuity Brief v2, context ranking, operational handoff, reuse confidence, real-usage health, and zero-value summary omission.

### Changed
- Compact final summaries now omit zero-value observations such as `0 tests`, `0 files`, `0 commands`, and `0 reopened files`.
- Final summaries now surface compact next-step guidance when useful, following the existing normalized/humanized AICTX summary style.

## 4.2.0 - 2026-04-25

### Added
- Added Continuity Brief v2 in `prepare_execution` with next focus, active decisions, probable paths, known risks, recommended commands/tests, ranked context evidence, and `why_loaded` explanations.
- Added ranked continuity items across handoff, decisions, failures, semantic repo memory, and procedural reuse.
- Added `reuse_confidence`, `continuity_value`, and `capture_quality` to finalize/summary outputs.
- Added continuity health signals to `report real-usage` for packet/context usefulness, stale memory exclusion, redundant exploration avoidance, capture gaps, and handoff freshness.

### Changed
- Handoff persistence now accepts structured operational handoff fields while preserving the existing stable artifact paths.
- Strategy reuse now favors real execution evidence from commands, tests, edited files, and strong matching signals.
- Test/error capture heuristics now recognize more common test commands and can surface notable error lines from captured output.

## 4.1.0 - 2026-04-25

### Added
- Added visible-session continuity UX improvements with startup banner handling and handoff history snapshots in `.aictx/continuity/handoffs.jsonl`.
- Added richer finalize reporting with compact `agent_summary_text` plus detailed execution output in `.aictx/continuity/last_execution_summary.md`.
- Added structured runtime text policies in execution payloads (`runtime_text_policy`, `startup_banner_policy`, `agent_summary_policy`) to guide localized/enriched runner output without inventing facts.

### Changed
- Updated runtime contract and runner integrations to propagate localization/enrichment policy metadata through prepare/finalize flows.
- Expanded smoke/continuity/session tests to cover policy exposure and runtime-summary output expectations.
- Updated README and execution-summary docs to reflect the `4.1.0` runtime contract language.

## 4.0.1 - 2026-04-24

### Fixed
- Corrected documentation to match the shipped runtime behavior more faithfully.
- Clarified that failed strategies are not reused as positive execution hints, but failure-aware context can still influence debugging/avoidance behavior.
- Updated usage and limitations docs to reflect the current packet middleware, enriched `reflect`, contextual `suggest`/`reuse`, and visible-session banner behavior.

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
