from __future__ import annotations

from aictx.contract_compliance import contract_gaps_from_compliance, evaluate_contract_compliance, strongest_contract_gap


def _contract() -> dict:
    return {
        "execution_contract": {
            "task_goal": "fix parser",
            "first_action": {"path": "tests/test_parser.py", "binding": "must_open_first"},
            "expected_first_files": ["tests/test_parser.py", "src/taskflow/parser.py"],
            "edit_scope": {"primary": ["tests/test_parser.py"], "secondary_if_needed": ["src/taskflow/parser.py"]},
            "test_command": {"command": "make test"},
        },
        "task_goal": "fix parser",
    }


def test_success_without_canonical_test_becomes_missing_validation_gap() -> None:
    compliance = evaluate_contract_compliance(_contract(), {"files_opened": ["tests/test_parser.py"]}, finalize_status="success")

    gaps = contract_gaps_from_compliance(compliance)

    assert gaps[0]["kind"] == "missing_validation"
    assert gaps[0]["severity"] == "needs-validation"
    assert gaps[0]["policy"] == "prioritize_before_new_work"
    assert gaps[0]["blocking"] is False
    assert gaps[0]["recommended_command"] == "make test"
    assert gaps[0]["next_action"] == "run expected validation command: make test"


def test_violations_become_scope_and_first_action_gaps() -> None:
    compliance = evaluate_contract_compliance(
        _contract(),
        {"files_opened": ["README.md"], "files_edited": ["README.md"], "commands_executed": ["echo done"]},
        finalize_status="failure",
    )

    gaps = contract_gaps_from_compliance(compliance)
    kinds = {gap["kind"] for gap in gaps}

    assert {"missing_first_action", "edit_outside_scope", "missing_validation", "structural_entrypoints_ignored"} <= kinds
    by_kind = {gap["kind"]: gap for gap in gaps}
    assert by_kind["edit_outside_scope"]["severity"] == "needs-review"
    assert by_kind["edit_outside_scope"]["policy"] == "surface_before_continuing"
    assert by_kind["edit_outside_scope"]["blocking"] is False
    assert by_kind["missing_first_action"]["severity"] == "caution"
    assert by_kind["structural_entrypoints_ignored"]["severity"] == "caution"
    assert strongest_contract_gap(gaps)["severity"] == "needs-validation"
    assert any("README.md" in gap.get("related_paths", []) for gap in gaps if gap["kind"] == "edit_outside_scope")
