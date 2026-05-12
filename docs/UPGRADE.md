# Upgrade guide

## Current line: 6.1.x

Current documented runtime: `6.1.0`.

For users already on recent `4.x` or `5.x`, there is no special data migration command. Re-run normal setup so generated runner instructions pick up the current startup contract:

```bash
aictx install
aictx init
```

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
