from __future__ import annotations

from aictx.contract_compliance import evaluate_contract_compliance


def _contract() -> dict:
    return {
        "execution_contract": {
            "task_goal": "improve repomap resume integration",
            "first_action": {"path": "src/aictx/middleware/__init__.py", "binding": "must_open_first"},
            "expected_first_files": [
                "src/aictx/middleware/__init__.py",
                "src/aictx/repo_map/query.py",
            ],
            "expected_first_files_source": "repo_map",
            "edit_scope": {
                "primary": ["src/aictx/middleware/__init__.py"],
                "secondary_if_needed": ["src/aictx/repo_map/query.py"],
            },
            "test_command": {"command": "pytest tests/test_resume_repomap_entry_points.py"},
        },
        "contract_checks": {},
        "task_goal": "improve repomap resume integration",
    }


def test_contract_compliance_structural_alignment_followed():
    payload = evaluate_contract_compliance(
        _contract(),
        {
            "files_opened": ["src/aictx/middleware/__init__.py"],
            "commands_executed": ["pytest tests/test_resume_repomap_entry_points.py"],
        },
        finalize_status="success",
    )

    assert payload["structural_alignment"] == "followed"
    assert payload["checks"]["structural_alignment"] == "followed"
    assert payload["structural_entry_points"]["matched_files"] == ["src/aictx/middleware/__init__.py"]
    assert "Structural alignment: followed." in payload["compact_summary"]


def test_contract_compliance_structural_alignment_ignored():
    payload = evaluate_contract_compliance(
        _contract(),
        {
            "files_opened": ["README.md"],
            "commands_executed": ["pytest tests/test_resume_repomap_entry_points.py"],
        },
        finalize_status="success",
    )

    assert payload["structural_alignment"] == "ignored"
    assert payload["structural_entry_points"]["matched_files"] == []
    assert "Structural alignment: ignored." in payload["compact_summary"]
