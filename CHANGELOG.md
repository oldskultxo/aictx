# Changelog

## 6.10.0 - 2026-06-01

### Added
- Added Continuity Guard as a compact read-only action-boundary check through `aictx guard` and MCP tool `aictx_continuity_guard`.
- Added Steer Guard as a deterministic read-only user-intervention classifier through `aictx steer` and MCP tool `aictx_steer_guard`.
- Added dedicated Continuity Guard and Steer Guard documentation, plus README, usage, and MCP references.

### Changed
- Optimized repeated guard usage with compact Continuity Quality issue collection, shared lifecycle Work State reads, a lightweight `aictx guard` / `aictx steer` entrypoint, and process-local guard caching.
- Expanded the readonly MCP profile with `aictx_continuity_guard` and `aictx_steer_guard` so agents can use guard rails without mutating continuity state.
- Repo-local MCP JSON entries now include both `transport: "stdio"` and `type: "stdio"` for broader client compatibility.

### Fixed
- Fixed AICTX source-checkout MCP attachment by generating managed repo-local MCP entries that run the current checkout with `.venv/bin/python -m aictx` and `PYTHONPATH=src` instead of relying on a potentially stale global `aictx` binary.
- Kept guard outputs compact by omitting full resume capsules, loaded context, and long continuity payloads.

## 6.9.1 - 2026-05-28

### Changed
- `aictx install` now detects an existing `~/.codex/` directory and installs or updates AICTX-managed global Codex integration by default; interactive installs ask for confirmation, while `--yes` applies the detected Codex setup automatically.
- `--install-codex-global` now explicitly forces global Codex setup even when `~/.codex/` is not detected.
- `aictx resume --json` now exposes `communication_policy` and `runtime_text_policy` from effective user preferences so agents can apply `caveman_lite`, `caveman_full`, or `caveman_ultra` without changing startup banner or final summary rendering.

### Fixed
- Hardened Mermaid Live URL generation for Continuity View links by centralizing `generate_mermaid_live_url`, using zlib/pako-compatible compression, URL-safe base64 without padding, and Mermaid Live's full state shape with `autoSync`, `grid`, `rough`, `panZoom`, `pan`, `zoom`, `renderCount`, and `mermaid` as a JSON string.
- Fixed Mermaid Live links emitted by finalize/agent summaries so generated continuity maps open reliably in `https://mermaid.live/view#pako:` without manual URL reconstruction.
- Updated installation, safety, usage, quickstart, README, and technical overview documentation for the Codex auto-detection install behavior.

## 6.9.0 - 2026-05-25

### Added
- Added read-only Task Context Packs through `aictx prepare "<goal>" --repo . --json`.
- Added the `aictx_prepare_task_context` MCP tool to the readonly profile.
- Added best-effort lifecycle event tracking for resume, Work State writes, and finalize.
- Added lifecycle diagnostics in `resume --json`, `doctor --json`, MCP tool `aictx_lifecycle_status`, and resource `aictx://repo/current/lifecycle-status`.
- Added focused task context rendering for relevant files, areas, decisions, handoffs, failures, validation expectations, continuity quality and stale-context warnings.

### Changed
- Task context preparation is explicitly separate from the lifecycle `resume -> work -> finalize` contract and does not write resume contracts or continuity artifacts.
- Task Context Packs now filter unrelated CI/config background decisions when they do not match the supplied task goal.
- Lifecycle diagnostics report incomplete or stale control-loop usage as warnings only; they do not block work.
- Lifecycle diagnostics now use the neutral `mcp_resume_without_finalize` warning for MCP resume sessions without finalize instead of implying a readonly MCP profile.
- Generated MCP-first runner guidance now tells agents to use runner tool discovery for lazy-loaded MCP namespaces, searching for `aictx resume finalize lifecycle`, before falling back to CLI when `.mcp.json` or `.vscode/mcp.json` exists.
- Updated README, usage, MCP, upgrade and site documentation for task context preparation.

### Fixed
- Kept `.aictx/continuity/lifecycle_events.jsonl` local-only by default so runtime/session telemetry is not included in the portable Git continuity subset.
- Centralized agent identity inference so Claude Code resolves as `claude`, GitHub Copilot resolves as `copilot`, and MCP/CLI resume/finalize payloads expose consistent `agent_id`, `adapter_id`, and `agent_identity`.
- Hardened Claude/Codex/Copilot runtime instructions so MCP tools discovered lazily by the runner are used before any CLI fallback.

## 6.8.0 - 2026-05-24

### Added
- Added Continuity Quality scoring.
- Added stale-context warnings.
- Added pending vs missing validation distinction.
- Added Continuity Quality section to Continuity View.
- Exposed quality through resume, doctor and MCP.

## 6.7.0 - 2026-05-20

### Added
- Added local AICTX MCP server exposing repo-local continuity as tools, resources and prompts.
- Added MCP profiles: `readonly`, `standard`, and `full`.
- Added default MCP preparation during `aictx install` and repo-local MCP configuration during `aictx init`.
- Added safe cleanup/uninstall support for AICTX-managed MCP configuration.
- Added Claude Code and Codex plugin distribution artifacts for AICTX.
- Added shared generated agent guidance for MCP-first, CLI-fallback AICTX usage.
- Added plugin marketplace manifests for Claude Code and Codex.

### Changed
- Agent integration guidance now tells agents to prefer AICTX MCP tools when available and fall back to CLI commands otherwise.

### Security
- MCP server is local-first and does not expose arbitrary shell, generic filesystem access, git push, or cloud sync capabilities.


## 6.6.0 - 2026-05-20

### Added
- Added `--manual` to `aictx install` and `aictx init` for the full advanced interactive setup flow.

### Changed
- Simplified default interactive `aictx install` to ask only about recommended RepoMap/Tree-sitter support.
- Simplified default interactive `aictx init` to assume setup defaults and ask only for repo communication mode.
- Updated installation, quickstart, usage, RepoMap, and homepage documentation for the simplified setup flow.

## 6.5.1 - 2026-05-18

### Changed
- Include severity, policy, blocking, expected, observed within Contract_gaps.
- New mapping:
```
missing_validation -> needs-validation
edit_outside_scope -> needs-review
missing_first_action -> caution
structural_entrypoints_ignored -> caution
```
- Work State preservs contract_gaps + strongest_contract_gap.
- `resume` exposes carryover_gaps, strongest_carryover_gap, and reasons like `contract_gap:needs-validation`

### Fixed
- Ignore legacy runtime dirs
- Make shard filenames collision-safe with slug + hash
- `migrate_portability_scaffold()` rewrites `.gitignore` to a local-only policy when portability is disabled.
- `load_latest_resume_contract()` fallback no longer accepts fuzzy weak matches from `resume_capsule.json`; it now requires exact/strong substrings.
- `doctor` marks partial contract compliance as a warning.
- The `python -m aictx.cli` shim has been added via `src/aictx/cli/__main__.py`.

## 6.5.0 - 2026-05-17

### Added
- Added Continuity View as a public inspectable continuity feature with `aictx view`, `aictx view --mermaid`, and `aictx view --json`.
- Added local deterministic Continuity View artifacts under `.aictx/reports/`: `continuity-view.md` and `continuity-map.mmd`.
- Added `aictx finalize --include-view` / `--view` integration so final summaries can link the local Mermaid map and generated `mermaid.live` online view.
- Added `continuity_view` metadata to `aictx resume --json` so agents can discover whether the latest view exists and where to inspect it.
- Added dedicated Continuity View documentation, sitemap entry, docs homepage placement, README positioning, and agent-readable docs references.

### Changed
- Updated the documented/runtime package version to `6.5.0`.
- Extended the documented artifact contract to include `.aictx/reports/*` and the stable Continuity View report/map paths.
- Clarified active-task semantics: recent paused or blocked carryover may appear as `Paused Work` or `Blocked Work`, but it is not counted as the current active task.
- Clarified final-summary behavior: agents must preserve exact `continuity-map.mmd` and `mermaid.live view` links returned by AICTX, without placeholders or manual pako URL reconstruction.

### Fixed
- Fixed Continuity View overview reporting so recent paused/blocked carryover is no longer rendered or counted as an active task.

## 6.4.3 - 2026-05-16

### Fixed
- Added GitHub Copilot instruction hardening through `.github/instructions/aictx.instructions.md` and optional `.github/prompts/aictx-*.prompt.md` files generated by `aictx init`.
- Hardened `.github/copilot-instructions.md` with shorter lifecycle-first instructions and explicit best-effort/no-command-execution fallback language.

## 6.4.2 - 2026-05-16

### Added
- Added SEO-first documentation architecture for `https://aictx.org` with use-case, comparison, and concept page clusters.
- Added agent-readable documentation entry points: `docs/llms.txt`, `docs/llms-small.txt`, and `docs/llms-full.txt`.
- Added section index pages for `/use-cases/`, `/compare/`, and `/concepts/` so documentation clusters have canonical SEO hubs.

### Changed
- Added SEO-focused `title` and `description` front matter to existing Markdown documentation pages.
- Expanded `docs/OFFICIAL_PROJECT.md` into the canonical AICTX identity page for the official website, GitHub repository, PyPI package, CLI, maintainer, and non-affiliation statement.
- Updated the docs homepage to emphasize repo-local memory and continuity, link to high-value SEO pages, and show a dynamic GitHub star count with an inline star icon.
- Updated docs layout navigation with Use cases, Comparisons, Concepts, and Project identity sections.
- Added `TechArticle` and canonical `BreadcrumbList` JSON-LD for documentation pages, including section index URLs for nested breadcrumbs.
- Updated `docs/sitemap.xml` with all new SEO pages and canonical cluster index URLs.

### Fixed
- Fixed nested docs breadcrumb structured data so section items such as Use cases, Comparisons, and Concepts include canonical `item` URLs.

## 6.4.1 - 2026-05-16

### Added
- Added `docs/OFFICIAL_PROJECT.md` as the canonical project identity page for the official website, repository, PyPI package, and CLI name.

### Changed
- Updated package/runtime/docs versioning from `6.4.0` to `6.4.1`.
- Updated README project identity links so the official website, repository, package, and canonical project statement are easier to find.
- Updated installation, usage, portability, safety, upgrade, release checklist, and generated site metadata/docs references for the `6.4.1` line.

### Fixed
- Closed the remaining portable JSONL rewrite bypass by routing resolved-failure rewrites through the shared portable JSONL writer path.
- Aligned portable continuity JSONL rewrites on one shared helper so portable rewrite flows follow the same sanitizer rule as portable append flows.
- Improved human-readable `aictx portability status` output so it surfaces overall status, drift, invalid JSONL rows, secret findings, and warnings without requiring `--json`.

## 6.4.0 - 2026-05-15

### Added
- Added public portability maintenance commands:
  - `aictx portability status --repo . --json`
  - `aictx portability compact --repo . --apply --json`

### Changed
- `aictx init --portable-continuity` now enables the `policy_version: 2` team-safe portability profile for small teams sharing one Git repository.
- Portable continuity now keeps append-only/sharded artifacts versionable while leaving conflict-prone latest-run snapshots local-only and derivable from portable history when needed.
- Portable continuity now manages an AICTX-owned `.gitattributes` block with `merge=union` hints for append-only JSONL continuity files without requiring any external sync service.
- Re-running `aictx init --portable-continuity` now migrates existing portable repos to the team-safe layout and merge policy.
- Portable Work State fallback is now stricter: if `.aictx/tasks/active.json` is missing and the selected portable thread has no saved `git_context`, AICTX skips it as ambiguous instead of loading it as active work.
- `aictx portability status` now reports drift between `portability.json`, the AICTX-managed `.gitignore` block, and the AICTX-managed `.gitattributes` block.
- Portable continuity is now secret-safe by default for the Git-visible subset: AICTX redacts detected passwords, tokens, API keys, private keys, credential-bearing URLs, and similar secret-shaped values before writing portable artifacts, with no bypass/override in this line.
- Updated README, portability, installation, usage, upgrade, and release checklist docs for the 6.4.0 portability model.

### Fixed
- Memory hygiene now rewrites duplicate semantic repo string lists from raw `semantic_repo.json` input before writing the dedupe report.
- `aictx portability compact --apply` now redacts secret-like values in valid portable JSONL rows and still refuses to rewrite files that contain invalid JSONL rows, instead of silently dropping those lines.
- `aictx portability status --repo . --json` now surfaces portable secret-scan findings without printing raw secret values.
- Top-level CLI help now reflects the public `portability` command in the primary command list.

## 6.3.2 - 2026-05-14

### Added
- Added standard GitHub Copilot repository custom instructions at `.github/copilot-instructions.md` during `aictx init`.

### Changed
- Documented GitHub Copilot as a supported runner surface across README, installation, quickstart, technical overview, docs index, and release checklist.
- Clarified that `.github/copilot-instructions.md` is created by `aictx init`, stays versioned in git, and uses explicit Copilot identity for `aictx resume` / `aictx finalize`.
- `aictx clean` / `aictx uninstall` now remove the AICTX-managed block from `.github/copilot-instructions.md` while preserving any user-authored Copilot notes in the same file.

## 6.3.1 - 2026-05-14

### Changed
- Clarified the README top section so it states the real AICTX runtime loop, repo-local `.aictx/` artifact model, install path, use cases, and limitations.
- Added GitHub community health files for issue reports, feature requests, pull requests, security reporting, and contributor conduct.

### Fixed
- Fixed CLI `aictx finalize` session identity inference so Codex sessions keep the inferred Codex adapter instead of falling back to `generic`.
- Prevented repeated startup banners caused by `resume` using `CODEX_THREAD_ID` while CLI `finalize` marked a different generic visible session.

## 6.3.0 - 2026-05-13

### Added
- Added contract-gap carryover from `contract_compliance` into Work State using existing `unverified`, `risks`, `recommended_commands`, `next_action`, and `source_execution_ids` fields.
- Added `loaded_context.role` and `selection_reason` metadata so `resume --json` distinguishes primary context, carryover, cautions, and background.
- Added explicit RepoMap status fields: `provider_available`, `index_available`, `query_available`, `refresh_available`, `last_refresh_status`, `files_indexed`, and `symbols_indexed`.
- Added public read-only diagnostics with `aictx doctor --repo . --json`, plus strict `--release-readiness` mode for aictx release-gate checks.

### Changed
- Promoted `make ci` as the canonical release-readiness gate with tests, smoke, package build, clean wheel install, and installed-version verification.
- Updated `resume` relevance so active/paused Work State and unresolved contract gaps outrank completed handoffs and generic strategy memory.
- Updated `aictx map status --json`, `report real-usage`, `resume.structural_context`, and `context_planner.structural_context_status()` to report queryable indexes separately from provider refresh availability.

### Fixed
- Prevented missing canonical validation, missing first action, out-of-scope edits, and ignored structural entry points from disappearing after `finalize`.
- Kept smoke lifecycle on `--task` and guarded release readiness against falling back to legacy `--request`.

## 6.2.0 - 2026-05-12

### Added
- Added RepoMap-powered `structural_entry_points` and `structural_context` to `aictx resume --json`.
- Added compact text rendering for structural entry points in `aictx resume`.
- Added optional `execution_contract.expected_first_files` derived from RepoMap structural entry points.
- Added contract compliance `structural_alignment` metadata for followed, partially followed, ignored, and not-evaluated structural paths.
- Added focused tests for the context planner, resume structural entry points, and structural alignment.

### Changed
- Documented RepoMap as an optional continuity context-planning signal in README, Quickstart, Usage, RepoMap, Technical overview, and Upgrade docs.

## 6.1.0 - 2026-05-12

### Added
- Added top-level `loaded_context` to `aictx resume --json`, with bounded additive metadata for failures, handoffs, decisions, strategy reuse, and RepoMap hints.
- Added `src/aictx/continuity/explain.py` to make loaded continuity selection explainable without a second unrelated retrieval pass.
- Added official entrypoint-arbiter contracts and wrapper support for Codex, Claude, and generic adapters.
- Added focused tests for explainable loaded context, request-sensitive handoff ranking, arbiter wrapper resolution, and fallback behavior.

### Changed
- `aictx resume` now supports configured runner-specific arbiter commands in addition to the generic `AICTX_ENTRYPOINT_ARBITER_COMMAND`.
- Updated README, technical overview, usage, and limitations docs to describe explainable loaded context and optional advisory entrypoint arbitration.

### Fixed
- Handoff staleness explanation now accepts both `updated_at` and `timestamp`.
- `loaded_context.related_paths` now converts repo-internal absolute paths to repo-relative form, removes duplicates, and omits repo-external absolute paths.
- Arbiter invalid JSON, non-zero exits, and timeouts now fall back safely to deterministic local ranking without polluting `resume --json`.

## 6.0.0 - 2026-05-11

### Added
- Added canonical persisted resume contracts under `.aictx/continuity/contracts/`, with an index keyed by `contract_id`, `session_id`, and `execution_id`.
- Added `contract_ref` to resume capsules so contract evaluation can resolve the generated contract instead of relying only on the latest `resume_capsule.json`.
- Added canonical `aictx finalize --task "<task goal>"` support for finalization-time contract matching.

### Changed
- Redesigned Contract Compliance to match contracts fuzzily by task intent instead of exact task text.
- `aictx finalize` now resolves task context in this order: `--task`, legacy `--request`, active Work State, then `--summary`.
- Contract summaries and `report real-usage` now report the latest evaluated contract result only; `not_evaluated` rows no longer mask useful historical results.
- Final AICTX summaries now include a `Contract:` line only when there was both a usable contract and enough execution observation to evaluate it.

### Fixed
- Stopped writing low-signal `not_evaluated` rows to `.aictx/metrics/contract_compliance.jsonl` when no useful contract evaluation was possible.
- Avoided false `contract_missing` adherence violations when no contract is available.
- Prevented stale/unrelated resume contracts from torpedoing new executions while preserving useful contract checks for related tasks.

## 5.3.0 - 2026-05-04

### Added
- Added the Contract Compliance Ledger, evaluated during `aictx finalize`, with compact JSONL audit rows at `.aictx/metrics/contract_compliance.jsonl`.
- Added `contract_compliance` to finalize JSON output and a compact contract line in `agent_summary_text` / structured summary output.
- Added historical contract compliance metrics to `aictx report real-usage`.
- Added `previous_contract_result` to `aictx resume --json` and a single compact previous-contract line in default resume text.
- Added focused and end-to-end tests for followed, partial, violated, not-evaluated, persistence, reporting, and next-resume behavior.

### Changed
- Updated normal startup documentation to prefer `aictx resume --repo . --task "<task goal>" --json` and keep `--request` as legacy/raw compatibility input.
- Improved user-facing contract summaries so visible text says the reason in human terms while `main_issue` keeps compact machine-readable codes.

### Fixed
- Made not-evaluated contract summaries explicit about why evaluation was skipped, distinguishing missing matching resume contracts from missing execution observations.
- Verified finalize compliance evaluation uses the populated execution observation (`files_opened`, `files_edited`, `commands_executed`, `tests_executed`) before writing metrics and final summaries.

## 5.2.0 - 2026-05-02

### Added
- Added top-level `aictx finalize --repo . --status success|failure --summary "<what happened>" --json` as the canonical agent-facing end-of-task command.
- Added resume startup guard fields that keep `resume` as the only pre-task AICTX command and `finalize` as the normal post-task command.

### Changed
- Updated generated runtime/AGENTS instructions so agents use `aictx finalize` instead of discovering internal execution finalization paths.
- Updated top-level CLI help to include `finalize` in the normal lifecycle command list while keeping advanced commands hidden under `aictx advanced`.

### Fixed
- Removed ambiguous runtime wording that could lead agents to shell-call `finalize_execution` or use `aictx internal execution finalize` during normal task flow.
- Removed the accidental prompt artifact from the release branch.

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
