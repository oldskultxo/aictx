---
title: "Upgrade AICTX"
description: "Upgrade the official Python `aictx` package and refresh repo-local coding-agent continuity instructions safely."
---

# Upgrade guide

## Current line: 6.9.x

Current documented runtime: `6.9.0`.

For users already on recent `4.x`, `5.x`, or `6.x`, there is no special data migration command. Re-run normal setup so generated runner instructions pick up the current startup contract:

```bash
aictx install
aictx init
```

---
## 6.9.0

`6.9.0` adds read-only Task Context Packs for on-demand task-specific context outside the normal lifecycle startup step.

This release does not require a data migration.

Added:
- `aictx prepare "<task goal>" --repo . --json` for a bounded Task Context Pack.
- `aictx_prepare_task_context` MCP tool in the readonly profile.
- Best-effort lifecycle event tracking for resume, Work State writes, and finalize.
- Lifecycle diagnostics in `aictx resume --json`, `aictx doctor --json`, MCP tool `aictx_lifecycle_status`, and resource `aictx://repo/current/lifecycle-status`.
- Task context output covering relevant files, areas, decisions, handoffs, failures, validation expectations, continuity quality and stale-context warnings.

Changed:
- Task context preparation is separate from `aictx resume`; it does not render startup banner policy, persist resume contracts, write generated trace artifacts, or replace the required `resume -> work -> finalize` lifecycle.
- Task Context Packs filter unrelated CI/config background decisions when they do not match the supplied goal.
- Lifecycle diagnostics are advisory warnings only. They detect incomplete control-loop usage without blocking users or requiring a daemon.

Upgrade notes:
- No data migration is required.
- Existing `.aictx/` continuity data remains compatible.
- Re-run setup if you want regenerated local runner instructions and MCP metadata from the current package:

```bash
aictx install
aictx init
```

Example:

```bash
aictx prepare "fix the MCP permissions bug" --repo . --json
```

---
## 6.8.0

`6.8.0` adds Continuity Quality scoring so AICTX can evaluate whether repo-local continuity is fresh, stale, missing, demoted, unverified, or safe to rely on.

This release does not require a data migration.

Added:
- Continuity Quality scoring for repo-local continuity artifacts.
- Stale-context warnings for handoffs, decisions, failures, Work State, RepoMap, Continuity View, and validation evidence.
- Detection of continuity items that reference deleted or missing files.
- Demotion semantics for old or weak memory without deleting existing artifacts.
- Distinction between:
  - `pending_validation_for_new_contract`: informational, for newly generated execution contracts that have not been validated yet.
  - `missing_validation_evidence`: warning, for older carried continuity that expected validation evidence but did not record it.
- Continuity Quality output in `aictx resume --json`.
- Continuity Quality diagnostic check in `aictx doctor --json`.
- Continuity Quality MCP tool/resource:
  - `aictx_continuity_quality`
  - `aictx://repo/current/continuity-quality`
- Compact `## Continuity Quality` section in generated Continuity View Markdown.

Changed:
- `aictx view` now includes a compact quality summary in `.aictx/reports/continuity-view.md`.
- Freshness thresholds are now explicit and advisory:
  - `fresh`: updated within 7 days
  - `possibly_stale`: updated within 30 days
  - `demoted`: older than 30 days but not older than 90 days
  - `obsolete`: older than 90 days
- `resume` avoids noisy warning-level validation messages for newly generated contracts.

Upgrade notes:
- No data migration is required.
- Existing `.aictx/` continuity data remains compatible.
- Continuity Quality is advisory. It does not delete or rewrite existing memory.
- Old continuity may now appear as `demoted`, `possibly_stale`, or `obsolete`. This means agents should treat it as background evidence and verify it against current files before acting.
- After upgrading, refresh repo-local integration files and regenerate the Continuity View:

```bash
aictx install
aictx init
aictx doctor --repo . --json
aictx view --repo .
```

## 6.7.0

`6.7.0` adds local AICTX MCP support and plugin distribution artifacts so agents can use repo-local continuity through MCP-first workflows.

Added:
- Local AICTX MCP server exposing repo-local continuity as tools, resources, and prompts.
- MCP profiles for `readonly`, `standard`, and `full` usage.
- Default MCP preparation during `aictx install` and repo-local MCP configuration during `aictx init`.
- Safe cleanup/uninstall support for AICTX-managed MCP configuration.
- Claude Code and Codex plugin distribution artifacts for AICTX.
- Shared generated agent guidance for MCP-first, CLI-fallback AICTX usage.
- Plugin marketplace manifests for Claude Code and Codex.

Changed:
- Agent integration guidance now tells agents to prefer AICTX MCP tools when available and fall back to CLI commands otherwise.

Security:
- The MCP server is local-first and does not expose arbitrary shell, generic filesystem access, git push, or cloud sync capabilities.

Upgrade notes:
- No data migration is required.
- Existing `.aictx/` continuity data remains compatible.
- Re-run setup to generate or refresh AICTX-managed MCP configuration and plugin/agent guidance from the current package:

```bash
aictx install
aictx init
```

---
## 6.6.0

`6.6.0` simplifies the default interactive setup flow while preserving the previous full setup prompts for advanced users.

Added:
- `aictx install --manual` for the full advanced install prompt flow.
- `aictx init --manual` for the full advanced repo initialization prompt flow.

Changed:
- Default interactive `aictx install` now asks only whether to enable recommended RepoMap support using Tree-sitter.
- Default interactive `aictx init` now assumes setup defaults and asks only for repo communication mode.
- `aictx install` explains why RepoMap/Tree-sitter is recommended: it provides compact structural file and symbol context so agents can choose better starting points.
- `aictx init` explains the available communication modes before asking for a selection.
- Installation, Quickstart, Usage, RepoMap, and homepage documentation now describe the simplified setup flow.

Upgrade notes:
- No data migration is required.
- Existing flags still work, including `--yes`, `--with-repomap`, `--portable-continuity`, `--no-portable-continuity`, `--no-register`, and `--no-gitignore`.
- `--yes` still skips prompts and keeps safe defaults. To request RepoMap non-interactively, use:

```bash
aictx install --yes --with-repomap
```

- To keep the previous full interactive flow, use:

```bash
aictx install --manual
aictx init --manual
```

---
## 6.5.1

`6.5.1` is a patch release for contract-gap guidance hardening and legacy runtime quarantine.

Changed:
- Contract gaps now carry compact guidance fields:
  - `severity`
  - `policy`
  - `blocking`
  - `expected`
  - `observed`
- Initial severity mapping is now explicit:

```text
missing_validation -> needs-validation
edit_outside_scope -> needs-review
missing_first_action -> caution
structural_entrypoints_ignored -> caution
```

- Work State now preserves structured `contract_gaps` plus `strongest_contract_gap`.
- `aictx resume --json` now surfaces `carryover_gaps`, `strongest_carryover_gap`, and clearer carryover reasons such as `contract_gap:needs-validation`.

Fixed:
- Legacy generated runtime directories are now quarantined instead of being treated as normal editable/discoverable paths:
  - `.aictx_memory`
  - `.aictx_task_memory`
  - `.aictx_failure_memory`
  - `.context_metrics`
- Semantic repo shard filenames are now collision-safe.
- Area memory shard filenames are now collision-safe.
- `migrate_portability_scaffold()` now rewrites the AICTX-managed `.gitignore` block back to local-only policy when portability is disabled.
- Latest `resume_capsule.json` contract fallback is now stricter and no longer accepts weak fuzzy task matches.
- `aictx doctor` now reports partial contract compliance as `warning` instead of treating it as fully healthy.
- `python -m aictx.cli` is supported again through `src/aictx/cli/__main__.py`.

Upgrade notes:
- No data migration is required.
- AICTX 6.x continues to use `.aictx/` as the canonical runtime and continuity root.
- Older experimental runtime directories such as `.aictx_memory`, `.aictx_task_memory`, `.aictx_failure_memory`, and `.context_metrics` are not migrated or read by AICTX 6.x. They are treated as legacy generated artifacts and should not be edited directly.
- If you still need information from those directories, copy it manually into `.aictx/memory/source/` before removing them.
- Re-run setup if you want regenerated local runner instructions from the current package:

```bash
aictx install
aictx init
```

---
## 6.5.0

`6.5.0` adds Continuity View: a local, deterministic Markdown and Mermaid report for current repo continuity.

Added:
- Public Continuity View commands:
  - `aictx view --repo .`
  - `aictx view --repo . --mermaid`
  - `aictx view --repo . --json`
- Stable local report artifacts:
  - `.aictx/reports/continuity-view.md`
  - `.aictx/reports/continuity-map.mmd`
- `aictx finalize --include-view` / `--view` support so final summaries can include Continuity View links.
- `resume --json` `continuity_view` metadata with stable Markdown/Mermaid paths and existence state.
- Dedicated Continuity View documentation and site placement.

Changed:
- The artifact contract now documents `.aictx/reports/*` and the stable Continuity View report/map paths.
- The docs now position Continuity View as inspectable repo continuity, not a generic graph viewer.
- Agent-facing docs now state that AICTX generates the Mermaid deterministically and agents preserve the exact local `.mmd` and `mermaid.live view` summary links.
- Overview active-task semantics now distinguish actual active Work State from paused/blocked carryover.

Fixed:
- Continuity View Overview no longer counts recent paused or blocked carryover as the current active task. Carryover can still appear as `Paused Work` or `Blocked Work` where relevant.

Upgrade notes:
- No data migration is required.
- Existing `.aictx/` continuity data remains compatible.
- Run `aictx view --repo .` to create the first local Continuity View in an existing repository.
- Re-run setup if you want regenerated local runner instructions from the current package:

```bash
aictx install
aictx init
```

---
## 6.4.3

`6.4.3` is a patch release for GitHub Copilot instruction hardening.

- GitHub Copilot path-specific instruction and prompt files generated by `aictx init`:
  - `.github/instructions/aictx.instructions.md`
  - `.github/prompts/aictx-resume.prompt.md`
  - `.github/prompts/aictx-finalize.prompt.md`

---
## 6.4.2

`6.4.2` is a patch release for SEO documentation architecture, canonical project identity improvements.

Added:
- New documentation clusters for use cases, comparisons, and concepts:
  - `/use-cases/`
  - `/compare/`
  - `/concepts/`
- Agent-readable docs files: `llms.txt`, `llms-small.txt`, and `llms-full.txt`.

Changed:
- Existing Markdown docs now have SEO-focused front matter titles and descriptions.
- The docs homepage now emphasizes repo-local memory and continuity for coding agents and links to the new SEO hubs.
- The official project identity page now clearly documents the canonical website, GitHub repository, PyPI package, CLI, maintainer, and non-affiliation notice.
- Documentation pages now emit `TechArticle` JSON-LD and canonical breadcrumb structured data.
- The sitemap now includes all new SEO pages and cluster indexes.
- GitHub Copilot docs now describe the best-effort instruction model and how to verify `.github/copilot-instructions.md` in Copilot References.

Fixed:
- Nested breadcrumb JSON-LD now includes canonical `item` URLs for Use cases, Comparisons, and Concepts section breadcrumbs.

Upgrade notes:
- No runtime migration is required.
- No `.aictx/` data migration is required.
- Re-run setup if you want regenerated local docs/instructions from the current package, including the hardened Copilot instruction files:

```bash
aictx install
aictx init
```

---
## 6.4.1

`6.4.1` is a patch release for portable continuity hardening and release/documentation identity consistency.

Added:
- `docs/OFFICIAL_PROJECT.md` as the canonical project identity page.

Changed:
- Portable continuity human status output now surfaces warning-level information directly in text mode:
  - overall status
  - portability drift
  - invalid portable JSONL row count
  - secret finding count
  - warning messages
- README, installation, usage, portability, safety, release checklist, and generated site metadata now describe the `6.4.1` line and official project identity consistently.

Fixed:
- `link_resolved_failures()` now rewrites `.aictx/failure_memory/failure_patterns.jsonl` through the shared portable JSONL writer instead of bypassing the portable rewrite path.
- Shared portable JSONL rewrite flows now consistently follow the sanitizer-backed writer path for rewrites as well as appends.

Upgrade notes:
- No data migration is required.
- Re-run setup only if you want regenerated local instructions or docs-aligned repo scaffolding:

```bash
aictx install
aictx init
```

---
## 6.4.0

`6.4.0` is a minor release for team-safe git-portable continuity.

Added:
- Public portability maintenance commands:
  - `aictx portability status --repo . --json`
  - `aictx portability compact --repo . --apply --json`

Changed:
- `aictx init --portable-continuity` now writes the `policy_version: 2` / `profile: team-safe` portability policy.
- Portable continuity now prefers append-only histories and sharded portable artifacts:
  - `.aictx/continuity/handoffs.jsonl`
  - `.aictx/continuity/semantic_repo/*.json`
  - `.aictx/area_memory/areas/*.json`
- Conflict-prone snapshots stay local-only and are derived when missing:
  - `.aictx/tasks/active.json`
  - `.aictx/continuity/handoff.json`
  - `.aictx/continuity/semantic_repo.json`
  - `.aictx/area_memory/areas.json`
- If `.aictx/tasks/active.json` is missing and portable Work State falls back to `threads/*.json`, AICTX now skips fallback threads that do not have saved `git_context`.
- AICTX now manages `.gitattributes` merge hints for portable append-only JSONL files. Git remains the only required transport; no external sync/lock service is required.
- `aictx portability status --repo . --json` now reports sync/drift for the managed portability policy files.
- Portable artifacts are now secret-safe by default: AICTX redacts detected tokens, passwords, API keys, private keys, credential-bearing URLs, and similar secret-shaped values before writing the portable subset.
- `aictx portability status --repo . --json` now also reports portable secret-scan findings without printing raw secret values.
- `aictx portability compact --repo . --apply --json` now redacts secret-like values in valid rows, but still refuses to rewrite files containing invalid JSONL rows.

Upgrade notes:
- If you were already using local-only continuity, no migration is required unless you want to opt into portable continuity.
- If you already had portable continuity enabled on an older repo, re-run:

```bash
aictx init --repo . --portable-continuity
```

- Then verify the effective policy:

```bash
aictx portability status --repo . --json | python3 -m json.tool
```

- After large merges, you can compact portable JSONL artifacts:

```bash
aictx portability compact --repo . --apply --json | python3 -m json.tool
```

- There is no secret-redaction override in this line. If a portable artifact is meant to be committed, AICTX will persist the redacted form.

---
## 6.3.2

`6.3.2` is a patch release for GitHub Copilot repository instructions and related docs.

Added:
- `aictx init` now creates `.github/copilot-instructions.md` with AICTX-managed GitHub Copilot repository custom instructions.

Changed:
- README, installation, quickstart, technical overview, docs index, and release checklist now describe GitHub Copilot as a supported runner surface.
- GitHub Copilot instructions are documented as a standard repository file that remains versioned in git and uses explicit Copilot identity:
  - `--agent-id copilot`
  - `--adapter-id copilot-vscode`
- `aictx clean` and `aictx uninstall` now remove the AICTX-managed block from `.github/copilot-instructions.md` while preserving non-AICTX user content in that file.

Upgrade notes:
- No data migration is required.
- Re-run `aictx init` after upgrading so existing repositories receive the Copilot instructions file and refreshed runner instructions.

---
## 6.3.1

`6.3.1` is a patch release for visible-session banner behavior and repository presentation.

Fixed:
- `aictx finalize` now preserves the inferred Codex adapter identity when no explicit `--adapter-id` is provided.
- This prevents `resume` from using `CODEX_THREAD_ID` while CLI `finalize` marks a separate `generic` session, which made the startup banner appear again on later responses in the same visible session.

Changed:
- README top-of-page copy now states the real repo-local runtime loop, `.aictx/` artifact model, install path, use cases, and limits more directly.
- Added GitHub community health files for contribution, issue, PR, conduct, and security workflows.

Upgrade notes:
- No data migration is required.
- Re-run `aictx install` and `aictx init` after upgrading so generated runtime instructions match the current runtime.

---
## 6.3.0

`6.3.0` hardens the repo-local continuity loop: release readiness, contract-gap carryover, resume relevance, RepoMap status clarity, and read-only diagnostics.

Added:
- Contract compliance gaps carry over into Work State as `unverified`, `risks`, `recommended_commands`, `next_action`, and `source_execution_ids`.
- `aictx resume --json` explains loaded context with `role`, `selection_reason`, `confidence`, `staleness`, and `related_paths`.
- RepoMap status separates provider, index, query, and refresh availability.
- Public read-only `aictx doctor --repo . --json` general diagnostic report, with `--release-readiness` for strict aictx release-gate checks.
- `make ci` remains the canonical release gate, including clean wheel install/version checks.

Upgrade notes:
- No external Jira, Confluence, Slack, email, cloud cache, hosted dashboard, or external RAG integrations are added in this line.
- No new carryover store is required; Work State remains the source for unresolved continuation.
- Re-run `aictx install` and `aictx init` after upgrading so generated runtime instructions match the current runtime.

---
## 6.2.0

`6.2.0` makes RepoMap actionable inside the normal continuity workflow.

Added:
- Top-level `structural_entry_points` and `structural_context` to `aictx resume --json` when RepoMap is enabled and indexed.
- Compact text rendering of structural entry points in `aictx resume` output.
- Optional `execution_contract.expected_first_files` derived from RepoMap structural entry points.
- Contract compliance `structural_alignment` metadata for whether observed files followed, partially followed, ignored, or could not evaluate the expected structural entry points.

Upgrade notes:
- RepoMap remains optional. Core continuity works when RepoMap is disabled, unavailable, stale, or unindexed.
- Structural entry points are bounded hints, not semantic understanding, enforcement, or correctness guarantees.
- Re-run `aictx install` and `aictx init` after upgrading so generated runtime instructions match the current runtime.

---
## 6.1.0

`6.1.0` extends the v6 runtime with explainable loaded-context metadata and optional entrypoint arbitration for request-sensitive resume routing.

Added:
- Top-level `loaded_context` in `aictx resume --json`, with bounded additive metadata for failures, handoffs, decisions, strategy reuse, and RepoMap hints.
- `src/aictx/continuity/explain.py` to explain why continuity items were selected without introducing a second unrelated retrieval pass.
- Official entrypoint-arbiter adapter contracts and wrapper scripts for Codex, Claude, and generic runners.

Changed:
- `aictx resume` can now use configured runner-specific arbiter commands (`AICTX_CODEX_ENTRYPOINT_ARBITER_COMMAND`, `AICTX_CLAUDE_ENTRYPOINT_ARBITER_COMMAND`, `AICTX_GENERIC_ENTRYPOINT_ARBITER_COMMAND`) in addition to `AICTX_ENTRYPOINT_ARBITER_COMMAND`.
- Technical overview, usage docs, limitations, and README now document explainable loaded context and the arbiter trust/fallback model.

Fixed:
- Handoff staleness now accepts both `updated_at` and `timestamp`.
- `loaded_context.related_paths` normalizes repo-internal absolute paths to repo-relative form, removes duplicates, and omits repo-external absolute paths.
- Arbiter failures, invalid JSON, non-zero exits, and timeouts now fall back cleanly to deterministic local ranking without corrupting `resume --json`.

Upgrade notes:
- Re-run `aictx install` and `aictx init` after upgrading so generated runner instructions and wrapper paths match the current runtime.
- Entrypoint arbitration remains disabled unless one of the arbiter command environment variables is explicitly configured.
- `loaded_context` is inspection/debugging metadata only; it explains selection but does not prove relevance or correctness.

---
## 6.0.0

`6.0.0` is a breaking runtime cleanup and Contract Compliance redesign. Re-run setup after upgrading so generated runner instructions and repo-local scaffold files match the v6 contract.

Added:
- Persisted resume contracts under `.aictx/continuity/contracts/`, indexed by `contract_id`, `session_id`, and `execution_id`.
- `contract_ref` in resume capsules, so finalize/prepare can resolve the generated contract without depending only on the latest `.aictx/continuity/resume_capsule.json`.
- Canonical `aictx finalize --task "<task goal>"`.

Changed:
- Contract matching no longer depends on exact task text. It uses task-intent matching and refuses stale/unrelated contracts.
- `aictx finalize` resolves task context in this order: `--task`, legacy `--request`, active Work State, then `--summary`.
- Contract reporting only surfaces evaluated results: `followed`, `partial`, or `violated`.
- Final summaries only include `Contract:` when there was a usable contract and enough observation to evaluate it.

Fixed:
- Low-signal `not_evaluated` rows are no longer appended to `.aictx/metrics/contract_compliance.jsonl`.
- Historical reports ignore old `not_evaluated` rows when choosing the latest useful contract result.
- Missing contracts no longer create false `contract_missing` adherence violations.

Upgrade notes:
- Existing old `not_evaluated` rows may remain in historical JSONL files, but v6 reporting ignores them for latest useful contract status.
- Prefer `aictx resume --repo . --task "<task goal>" --json` at startup and `aictx finalize --repo . --status success|failure --task "<task goal>" --summary "<what happened>" --json` at finalization.
- If an active Work State exists, `finalize` can use it when neither `--task` nor `--request` is provided.

---
## 5.3.0

Added:
- Added the Contract Compliance Ledger, evaluated during `aictx finalize`, with compact JSONL audit rows at `.aictx/metrics/contract_compliance.jsonl`.
- Added `contract_compliance` to finalize JSON output and a compact contract line in `agent_summary_text` / structured summary output.
- Added historical contract compliance metrics to `aictx report real-usage`.
- Added `previous_contract_result` to `aictx resume --json` and a single compact previous-contract line in default resume text.
- Added focused and end-to-end tests for followed, partial, violated, not-evaluated, persistence, reporting, and next-resume behavior.

Changed:
- Updated normal startup documentation to prefer `aictx resume --repo . --task "<task goal>" --json` and remove legacy `--request` startup compatibility.
- Improved user-facing contract summaries so visible text says the reason in human terms while `main_issue` keeps compact machine-readable codes.

Fixed:
- Made not-evaluated contract summaries explicit about why evaluation was skipped, distinguishing missing matching resume contracts from missing execution observations.
- Verified finalize compliance evaluation uses the populated execution observation (`files_opened`, `files_edited`, `commands_executed`, `tests_executed`) before writing metrics and final summaries.


## Safe upgrade checklist

```bash
python -m pip install --upgrade aictx
aictx install
aictx init
aictx resume --repo . --task "continue current work" --json | python3 -m json.tool
aictx finalize --repo . --status success --task "upgrade validation" --summary "Validated AICTX v6 upgrade" --json | python3 -m json.tool
aictx advanced
```
