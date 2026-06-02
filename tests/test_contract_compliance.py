from __future__ import annotations

from pathlib import Path

from aictx.contract_compliance import (
    append_contract_compliance,
    compact_previous_contract_result,
    evaluate_contract_compliance,
    load_contract_compliance_history,
    load_persisted_resume_contract,
    persist_resume_contract,
    summarize_contract_compliance_history,
)


def _contract() -> dict:
    return {
        "execution_contract": {
            "task_goal": "fix parser",
            "first_action": {"path": "tests/test_parser.py", "binding": "must_open_first"},
            "edit_scope": {
                "primary": ["tests/test_parser.py"],
                "secondary_if_needed": ["src/taskflow/parser.py"],
            },
            "test_command": {"command": "make test"},
        },
        "contract_checks": {},
        "generated_at": "2026-05-04T00:00:00Z",
        "task_goal": "fix parser",
    }


def test_no_contract_returns_not_evaluated():
    payload = evaluate_contract_compliance({}, {})
    assert payload["contract_present"] is False
    assert payload["status"] == "not_evaluated"
    assert payload["score"] is None
    assert payload["main_issue"] == "no_resume_contract"
    assert payload["compact_summary"] == "Contract: not evaluated — no matching resume contract."



def test_contract_without_observation_returns_not_evaluated():
    payload = evaluate_contract_compliance(_contract(), {}, finalize_status="success")
    assert payload["contract_present"] is True
    assert payload["status"] == "not_evaluated"
    assert payload["main_issue"] == "no_execution_observation"
    assert payload["compact_summary"] == "Contract: not evaluated — no execution observation."

def test_compliant_execution_gets_followed_high_score():
    payload = evaluate_contract_compliance(
        _contract(),
        {
            "files_opened": ["tests/test_parser.py"],
            "files_edited": ["src/taskflow/parser.py"],
            "commands_executed": ["make test"],
            "tests_executed": ["make test"],
        },
        finalize_status="success",
    )
    assert payload["status"] == "followed"
    assert payload["score"] >= 0.95
    assert payload["checks"]["followed_first_action"] is True
    assert payload["checks"]["edited_within_scope"] is True
    assert payload["checks"]["canonical_test_used"] is True


def test_missing_first_action_is_violation():
    payload = evaluate_contract_compliance(_contract(), {"commands_executed": ["make test"]}, finalize_status="success")
    assert payload["status"] == "violated"
    assert payload["main_issue"] == "missing_first_action"


def test_edit_outside_scope_is_violation():
    payload = evaluate_contract_compliance(
        _contract(),
        {"files_opened": ["tests/test_parser.py"], "files_edited": ["README.md"], "commands_executed": ["make test"]},
        finalize_status="success",
    )
    assert any(item["code"] == "edit_outside_scope" for item in payload["violations"])
    assert payload["compact_summary"] == "Contract: violated — edited outside contract scope."


def test_missing_canonical_test_is_violation_on_failure():
    payload = evaluate_contract_compliance(_contract(), {"files_opened": ["tests/test_parser.py"]}, finalize_status="failure")
    assert any(item["code"] == "canonical_test_missing" for item in payload["violations"])


def test_missing_canonical_test_is_warning_on_success():
    payload = evaluate_contract_compliance(_contract(), {"files_opened": ["tests/test_parser.py"]}, finalize_status="success")
    assert any(item["code"] == "canonical_test_not_observed" for item in payload["warnings"])
    assert payload["compact_summary"] == "Contract: partial — canonical test was not observed."


def test_orientation_command_is_order_unknown_warning_not_violation():
    payload = evaluate_contract_compliance(
        _contract(),
        {"files_opened": ["tests/test_parser.py"], "commands_executed": ["make test", "git status"]},
        finalize_status="success",
    )
    assert any(item["code"] == "orientation_command_order_unknown" for item in payload["warnings"])
    assert not any(item["code"] == "orientation_command_order_unknown" for item in payload["violations"])


def test_historical_summary_aggregates_correctly(tmp_path: Path):
    rows = [
        {"status": "followed", "contract_present": True, "score": 1.0, "checks": {"followed_first_action": True, "edited_within_scope": True, "canonical_test_used": True, "finalize_used": True}, "violations": [], "warnings": [], "compact_summary": "Contract: followed."},
        {"status": "partial", "contract_present": True, "score": 0.9, "main_issue": "canonical_test_not_observed", "checks": {"followed_first_action": True, "edited_within_scope": True, "canonical_test_used": False, "finalize_used": True}, "violations": [], "warnings": [{"code": "canonical_test_not_observed"}], "compact_summary": "Contract: partial — canonical_test_not_observed."},
        {"status": "violated", "contract_present": True, "score": 0.7, "main_issue": "edit_outside_scope", "checks": {"followed_first_action": True, "edited_within_scope": False, "canonical_test_used": True, "finalize_used": True}, "violations": [{"code": "edit_outside_scope"}], "warnings": [], "compact_summary": "Contract: violated — edit_outside_scope."},
        {"status": "not_evaluated", "contract_present": False, "score": None, "checks": {}, "violations": [], "warnings": [], "compact_summary": "Contract: not evaluated."},
    ]
    summary = summarize_contract_compliance_history(rows)
    assert summary["evaluated"] == 3
    assert summary["followed"] == 1
    assert summary["partial"] == 1
    assert summary["violated"] == 1
    assert summary["avg_score"] == 0.8667
    assert summary["top_violations"] == {"edit_outside_scope": 1}
    assert summary["top_warnings"] == {"canonical_test_not_observed": 1}
    assert summary["latest"]["status"] == "violated"

    append_contract_compliance(tmp_path, rows[3])
    append_contract_compliance(tmp_path, rows[0])
    assert load_contract_compliance_history(tmp_path, limit=5)[-1]["status"] == "followed"
    assert compact_previous_contract_result(tmp_path)["status"] == "followed"


def test_persisted_resume_contract_loads_with_fuzzy_task_match(tmp_path: Path):
    resume_payload = {
        "generated_at": "2026-05-04T00:00:00Z",
        "request": "fix parser",
        **_contract(),
    }
    ref = persist_resume_contract(tmp_path, resume_payload, session_id="session-1", agent_id="codex")

    loaded = load_persisted_resume_contract(tmp_path, task_goal="fix parser regression", session_id="session-1")
    unrelated = load_persisted_resume_contract(tmp_path, task_goal="publish release workflow", session_id="session-1")

    assert ref["contract_id"]
    assert loaded["contract_id"] == ref["contract_id"]
    assert loaded["execution_contract"]["task_goal"] == "fix parser"
    assert loaded["task_goal_match"] is True
    assert unrelated == {}
    assert (tmp_path / ".aictx" / "continuity" / "contracts" / "index.json").exists()


def test_documentation_contract_does_not_fake_first_action_or_validation_penalties():
    contract = _contract()
    contract["execution_contract"]["contract_strength"] = "soft"
    contract["execution_contract"]["validation_policy"] = {"task_type": "documentation", "required": False}
    payload = evaluate_contract_compliance(
        contract,
        {"files_opened": ["README.md"], "files_edited": ["README.md"], "commands_executed": ["echo reviewed"]},
        finalize_status="success",
    )
    assert payload["main_issue"] != "missing_first_action"
    assert not any(item["code"].startswith("canonical_test") for item in payload["warnings"] + payload["violations"])
