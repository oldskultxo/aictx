from __future__ import annotations

import json
from pathlib import Path

from aictx.failure_memory import FAILURE_PATTERNS_PATH, link_resolved_failures, load_failures, lookup_failures
from aictx.middleware import finalize_execution, prepare_execution
from aictx.scaffold import init_repo_scaffold


def _payload(repo: Path, execution_id: str) -> dict:
    return {
        "repo_root": str(repo),
        "user_request": "fix runtime startup import error",
        "agent_id": "codex",
        "adapter_id": "codex",
        "execution_id": execution_id,
        "declared_task_type": "bug_fixing",
        "timestamp": "2026-04-24T13:30:00Z",
        "files_opened": ["src/aictx/middleware.py"],
        "commands_executed": [".venv/bin/python -m pytest -q"],
        "notable_errors": ["ImportError during startup"],
    }


def test_failure_pattern_persists_extended_schema(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    prepared = prepare_execution(_payload(repo, "exec-failure-schema"))

    finalized = finalize_execution(
        prepared,
        {"success": False, "result_summary": "Retried tests without fixing import chain", "validated_learning": False},
    )

    rows = load_failures(repo)
    assert finalized["failure_persisted"]["failure_id"] == rows[-1]["failure_id"]
    failure = rows[-1]
    assert failure["signature"] == failure["failure_signature"]
    assert failure["symptoms"] == ["ImportError during startup"]
    assert failure["failed_attempts"] == ["Retried tests without fixing import chain"]
    assert failure["ineffective_commands"] == [".venv/bin/python -m pytest -q"]
    assert failure["related_paths"] == ["src/aictx/middleware.py"]
    assert failure["subsystem"] == "src/aictx"
    assert failure["resolution_hint"]
    assert failure["resolved_by"] == ""
    assert failure["timestamp"]
    assert failure["session"] == 1
    assert not (repo / ".aictx" / "failures.jsonl").exists()


def test_lookup_supports_old_and_new_failure_patterns(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    path = repo / FAILURE_PATTERNS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "failure_id": "failure::old",
            "signature": "old_cli_assertion",
            "task_type": "bug_fixing",
            "area_id": "src/aictx",
            "error_text": "AssertionError: cli failed",
            "failed_command": "pytest tests/test_cli.py",
            "files_involved": ["src/aictx/cli.py"],
            "status": "open",
        })
        + "\n"
        + json.dumps({
            "failure_id": "failure::new",
            "signature": "runtime_startup_import",
            "failure_signature": "pytest_import_error_on_runtime_start",
            "task_type": "bug_fixing",
            "area_id": "src/aictx",
            "symptoms": ["ImportError during startup"],
            "ineffective_commands": ["pytest"],
            "related_paths": ["src/aictx/middleware.py"],
            "resolution_hint": "Check startup import chain before rerunning tests.",
            "status": "open",
        })
        + "\n",
        encoding="utf-8",
    )

    old_matches = lookup_failures(repo, task_type="bug_fixing", text="cli failed", files=["src/aictx/cli.py"], area_id="src/aictx")
    new_matches = lookup_failures(repo, task_type="bug_fixing", text="startup import", files=["src/aictx/middleware.py"], area_id="src/aictx")

    assert any(row["failure_id"] == "failure::old" for row in old_matches)
    assert any(row["failure_id"] == "failure::new" for row in new_matches)


def test_resolution_marks_extended_resolved_by(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    failed = prepare_execution(_payload(repo, "exec-failure-before-fix"))
    finalize_execution(failed, {"success": False, "result_summary": "ImportError during startup", "validated_learning": False})

    fixed = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "fix startup import error",
            "agent_id": "codex",
            "execution_id": "exec-fix",
            "declared_task_type": "bug_fixing",
            "files_opened": ["src/aictx/middleware.py"],
        }
    )
    execution_log = {
        "task_type": "bug_fixing",
        "files_opened": ["src/aictx/middleware.py"],
        "area_id": "src/aictx",
    }

    resolved = link_resolved_failures(repo, fixed, execution_log)

    assert resolved
    rows = load_failures(repo)
    assert rows[-1]["status"] == "resolved"
    assert rows[-1]["resolved_by"] == "exec-fix"
    assert rows[-1]["resolved_by_execution_id"] == "exec-fix"
