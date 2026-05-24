# Codex Prompt — Harden Continuity Quality Scoring for AICTX issue #6

## Repository

Work in:

```text
https://github.com/oldskultxo/aictx/tree/continuity-quality-scoring
```

Target branch:

```text
continuity-quality-scoring
```

Related issue:

```text
https://github.com/oldskultxo/aictx/issues/6
```

## Context

The branch already implements the first version of Continuity Quality scoring:

- `src/aictx/continuity/quality.py`
- integration into `aictx resume`
- integration into `aictx doctor`
- MCP tool/resource integration
- docs update in `docs/CONTINUITY_VIEW.md`
- tests in `tests/test_continuity_quality.py`

The implementation is broadly aligned with issue #6, but it needs a few hardening adjustments before the issue can be considered complete.

## Goal

Make Continuity Quality less noisy, more inspectable, and more precise.

Specifically:

1. Separate **pending validation for a newly generated resume contract** from **missing validation evidence for carried continuity**.
2. Add a visible **Continuity Quality** section to the generated Continuity View Markdown.
3. Add deterministic tests for the two behaviours above.
4. Move/document the age thresholds used for staleness classification.

Do not redesign the feature. Do not add unrelated features.

---

# Required changes

## 1. Fix noisy validation warning for freshly generated resume contracts

### Problem

`build_resume_capsule()` generates a new `execution_contract` during `aictx resume`.

Then it calls `build_continuity_quality_report(...)` with that freshly generated contract.

The current quality logic can emit:

```text
missing_validation_evidence
```

simply because the new contract has no validation evidence yet.

That is misleading.

A newly generated contract has not been executed yet. It should not be treated the same as carried continuity that already claimed validation was required but never recorded evidence.

### Required behaviour

In `src/aictx/continuity/quality.py`, distinguish these two cases:

### Case A — current/new contract has no validation evidence yet

This is normal during `resume`.

Use either:

```text
pending_validation_for_new_contract
```

or do not emit an issue at all.

Preferred behaviour:

```json
{
  "code": "pending_validation_for_new_contract",
  "severity": "info",
  "source": ".aictx/continuity/contracts",
  "summary": "Execution contract is pending validation.",
  "recommendation": "Run or record the expected validation during finalize."
}
```

Rules:

- severity must be `info`
- it must not make the overall report `warning`
- it must not render in normal non-full resume markdown
- it may reduce score slightly only if the current scoring design already penalizes info items
- it must not be confused with a real validation gap

### Case B — carried/previous continuity lacks validation evidence

This is a real warning.

Keep using:

```text
missing_validation_evidence
```

Rules:

- severity should remain `warning`
- this should be emitted when `carryover_gaps` contains a missing validation gap
- this should also be emitted if existing Work State / prior continuity explicitly contains unverified carried validation gaps
- this is the case the agent should treat as a real risk

### Implementation constraints

Do not invent a new persistence model.

Use the existing context passed into `build_continuity_quality_report(...)`:

- `carryover_gaps`
- `execution_contract`
- `capsule.validated`
- active/recent Work State if already loaded
- existing contract/staleness helpers if already present

Minimal acceptable implementation:

- If `carryover_gaps` contains a `kind == "missing_validation"` gap, emit `missing_validation_evidence` warning.
- Else if `execution_contract` exists but `validated` is empty, emit `pending_validation_for_new_contract` info, not `missing_validation_evidence`.
- Do not emit warning-level validation issues for a clean freshly generated resume contract.

---

## 2. Add Continuity Quality to Continuity View Markdown

### Problem

The quality report is exposed through:

- `resume`
- `doctor`
- MCP tool
- MCP resource

But the generated Continuity View does not visibly include the quality summary.

Since Continuity View is the inspectable state of repo continuity, it should show the quality score.

### Required behaviour

Update `src/aictx/continuity_view.py`.

`build_continuity_view_model(repo_root)` should include a compact quality summary under a new key:

```python
model["continuity_quality"] = ...
```

Use `build_continuity_quality_report(repo_root)`.

Do not embed the entire huge quality report blindly into the Markdown.

The model may contain the full report if useful, but the Markdown should render a compact section.

### Required Markdown section

Add this section after `## Overview` and before `## Continuity Map`:

```markdown
## Continuity Quality

- Score: 82/100
- Status: warning
- Advisory only: yes
- Fresh: 3
- Possibly stale: 1
- Stale: 0
- Obsolete: 0
- Unverified: 1
- Demoted: 2
- Missing: 0

Top issues:
- Continuity View may be stale. Regenerate the Continuity View after significant work.
- Continuity item references files that are no longer present. Demote this item until current repo inspection validates it.
```

Rules:

- Render `Score`, `Status`, and `Advisory only` always.
- Render the summary counts from `quality["summary"]`.
- Render at most 3 top issues.
- Top issues should include only `warning` or `error` severity.
- If there are no warning/error issues, render:

```markdown
Top issues:
- None
```

- Do not include full JSON.
- Do not render dozens of items.
- Do not alter the Mermaid diagram unless required by existing tests.

### Avoid recursion/noise

`build_continuity_quality_report()` checks whether Continuity View exists and whether it may be stale.

When Continuity View is being generated, avoid creating confusing behaviour where the newly generated view immediately reports itself as missing just because it has not been written yet.

Acceptable options:

1. Pass context indicating that the view is being generated and should be treated as available, or
2. Call quality after calculating intended output path and pass a synthetic `continuity_view` context with `exists=True` and `generated_at=model["generated_at"]`, or
3. Keep current behaviour only if tests show it does not produce noisy missing-view warnings during normal `aictx view`.

Prefer option 2 if it is simple.

---

## 3. Add tests

Update existing tests or add new tests. Do not remove existing coverage.

### Required test A

Add a test to `tests/test_continuity_quality.py`.

Name suggestion:

```python
def test_resume_new_contract_reports_pending_validation_not_missing_validation(...)
```

Test behaviour:

- Initialize repo scaffold.
- Seed enough healthy context so the report is not dominated by unrelated warnings:
  - RepoMap available
  - Continuity View available
  - at least one live file
- Run `aictx resume --repo <repo> --task "live" --json`.
- Inspect `payload["continuity_quality"]["issues"]`.
- Assert that there is no warning-level issue with:

```text
code == "missing_validation_evidence"
```

just because resume generated a contract.
- If `pending_validation_for_new_contract` is emitted, assert its severity is `info`.
- Assert non-JSON resume output does not render a visible `Continuity quality` section for this healthy/pending case.

### Required test B

Add a test to `tests/test_continuity_view.py`.

Name suggestion:

```python
def test_continuity_view_renders_quality_summary(...)
```

Test behaviour:

- Initialize repo scaffold.
- Generate the Continuity View with existing helper/CLI.
- Read `.aictx/reports/continuity-view.md`.
- Assert it contains:

```text
## Continuity Quality
- Score:
- Status:
- Advisory only:
Top issues:
```

- Assert it does not dump raw full JSON such as:

```text
"loaded_items"
"scoring_breakdown"
```

inside the Markdown.

### Required test C

Add or update a test to ensure real carried validation gaps still warn.

Name suggestion:

```python
def test_continuity_quality_warns_for_carried_missing_validation_gap(...)
```

Test behaviour:

- Call `build_continuity_quality_report(...)` with a context containing:

```python
{
    "carryover_gaps": [
        {
            "kind": "missing_validation",
            "source_execution_id": "prev-exec",
            "summary": "Expected pytest was not recorded",
            "next_action": "Run pytest"
        }
    ]
}
```

- Assert it emits `missing_validation_evidence`.
- Assert severity is `warning`.
- Assert report status becomes `warning`.

---

## 4. Make age thresholds explicit and documented

### Problem

The quality logic currently uses implicit thresholds:

- <= 7 days: fresh
- <= 30 days: possibly stale
- <= 90 days: demoted
- > 90 days: obsolete

These should not be hidden magic numbers.

### Required implementation

In `src/aictx/continuity/quality.py`, define named constants near the top:

```python
FRESH_MAX_DAYS = 7
POSSIBLY_STALE_MAX_DAYS = 30
DEMOTED_MAX_DAYS = 90
```

Use those constants inside `_item_status(...)`.

Do not change the threshold values unless an existing test forces it.

### Required docs

Update `docs/CONTINUITY_VIEW.md` in the Continuity Quality section.

Add a short explanation:

```markdown
Default age thresholds are advisory:

- `fresh`: updated within 7 days
- `possibly_stale`: updated within 30 days
- `demoted`: older than 30 days but not older than 90 days
- `obsolete`: older than 90 days

These statuses do not delete artifacts. They guide agents on whether continuity should be treated as primary guidance or background evidence.
```

Also document the distinction:

```markdown
A newly generated execution contract can be `pending_validation_for_new_contract`.
That is informational. It means validation has not happened yet.

`missing_validation_evidence` is different: it means older carried continuity expected validation evidence but none was recorded.
```

---

# Non-goals

Do not implement these in this task:

- Do not add a new `aictx quality` CLI command.
- Do not redesign scoring from scratch.
- Do not add a vector database.
- Do not change persistence layout.
- Do not delete old memory automatically.
- Do not add a UI/dashboard.
- Do not change MCP permissions except if tests require the already existing `aictx_continuity_quality` readonly tool.
- Do not rename existing public commands.
- Do not change issue #6 wording.
- Do not bump package version unless the repository already requires version bumps for every branch task.

---

# Files likely to edit

Expected files:

```text
src/aictx/continuity/quality.py
src/aictx/continuity_view.py
docs/CONTINUITY_VIEW.md
tests/test_continuity_quality.py
tests/test_continuity_view.py
```

Only edit other files if strictly required by failing tests.

---

# Validation commands

Run targeted tests first:

```bash
python -m pytest tests/test_continuity_quality.py tests/test_continuity_view.py tests/test_mcp_server.py tests/test_mcp_tools.py
```

Then run the full suite if time allows:

```bash
python -m pytest
```

If full suite is too slow, report exactly which targeted tests passed and which were not run.

---

# Acceptance criteria

The task is complete only if all of these are true:

- Freshly generated resume contracts do not produce warning-level `missing_validation_evidence`.
- Real carried missing validation gaps still produce warning-level `missing_validation_evidence`.
- `pending_validation_for_new_contract`, if emitted, is `info`.
- `aictx resume` remains non-noisy in normal markdown output.
- `aictx resume --json` still includes `continuity_quality`.
- `aictx doctor --json` still includes the `continuity_quality` check.
- MCP still exposes:
  - tool `aictx_continuity_quality`
  - resource `aictx://repo/current/continuity-quality`
- Continuity View Markdown includes a compact `## Continuity Quality` section.
- Continuity View Markdown does not dump full quality JSON.
- Age thresholds are named constants and documented.
- Existing tests still pass or any failures are explained precisely.

---

# Output required from Codex

At the end, report:

1. Files changed.
2. Summary of implementation.
3. Tests run and results.
4. Any intentional non-goals left untouched.
5. Whether issue #6 can now be considered complete.
