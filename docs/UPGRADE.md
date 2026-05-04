# Upgrade guide

## Current line: 5.2.x

Current documented runtime: `5.3.0`.

For users already on recent `4.x`, there is no special data migration command. Re-run normal setup so generated runner instructions pick up the v5 startup contract:

```bash
aictx install
aictx init
```

---
## 5.2.x

Added:
- Added the Contract Compliance Ledger, evaluated during `aictx finalize`, with compact JSONL audit rows at `.aictx/metrics/contract_compliance.jsonl`.
- Added `contract_compliance` to finalize JSON output and a compact contract line in `agent_summary_text` / structured summary output.
- Added historical contract compliance metrics to `aictx report real-usage`.
- Added `previous_contract_result` to `aictx resume --json` and a single compact previous-contract line in default resume text.
- Added focused and end-to-end tests for followed, partial, violated, not-evaluated, persistence, reporting, and next-resume behavior.

Changed:
- Updated normal startup documentation to prefer `aictx resume --repo . --task "<task goal>" --json` and keep `--request` as legacy/raw compatibility input.
- Improved user-facing contract summaries so visible text says the reason in human terms while `main_issue` keeps compact machine-readable codes.

Fixed:
- Made not-evaluated contract summaries explicit about why evaluation was skipped, distinguishing missing matching resume contracts from missing execution observations.
- Verified finalize compliance evaluation uses the populated execution observation (`files_opened`, `files_edited`, `commands_executed`, `tests_executed`) before writing metrics and final summaries.


## Safe upgrade checklist

```bash
python -m pip install --upgrade aictx
aictx install
aictx init
aictx resume --repo . --request "continue current work" --json | python3 -m json.tool
aictx advanced
```
