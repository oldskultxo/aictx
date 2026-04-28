from __future__ import annotations

import json
from pathlib import Path

from aictx.continuity import load_continuity_context
from aictx.failure_memory import FAILURE_PATTERNS_PATH
from aictx.middleware import prepare_execution
from aictx.scaffold import init_repo_scaffold


def _payload(repo: Path, execution_id: str = "exec-failure-aware") -> dict:
    return {
        "repo_root": str(repo),
        "user_request": "fix startup import failure",
        "agent_id": "codex",
        "adapter_id": "codex",
        "execution_id": execution_id,
        "declared_task_type": "bug_fixing",
        "timestamp": "2026-04-24T14:00:00Z",
        "files_opened": ["src/aictx/middleware.py"],
    }


def _write_failure(repo: Path, row: dict) -> None:
    path = repo / FAILURE_PATTERNS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def test_missing_failure_memory_does_not_crash_startup(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    prepared = prepare_execution(_payload(repo, "exec-no-failures"))

    assert prepared["continuity_context"]["failures"] == []
    assert prepared["continuity_context"]["loaded"]["failures"] is False
    assert "- failures: no" in prepared["continuity_summary_text"]


def test_old_failure_pattern_can_load_into_startup_context(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _write_failure(
        repo,
        {
            "failure_id": "failure::old",
            "signature": "old_startup_import",
            "task_type": "bug_fixing",
            "area_id": "src/aictx",
            "error_text": "ImportError during startup",
            "failed_command": "pytest tests/test_runtime.py",
            "files_involved": ["src/aictx/middleware.py"],
            "status": "open",
        },
    )

    prepared = prepare_execution(_payload(repo, "exec-old-failure"))

    failures = prepared["continuity_context"]["failures"]
    assert [row["failure_id"] for row in failures] == ["failure::old"]
    assert prepared["continuity_context"]["loaded"]["failures"] is True
    assert "- failures: yes" in prepared["continuity_summary_text"]


def test_relevant_failure_patterns_are_bounded_to_five(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    for index in range(7):
        _write_failure(
            repo,
            {
                "failure_id": f"failure::{index}",
                "signature": f"startup_import_failure_{index}",
                "failure_signature": f"pytest_import_error_on_runtime_start_{index}",
                "task_type": "bug_fixing",
                "area_id": "src/aictx",
                "symptoms": ["ImportError during startup"],
                "related_paths": ["src/aictx/middleware.py"],
                "resolution_hint": "Check startup import chain before rerunning tests.",
                "status": "open",
            },
        )

    context = load_continuity_context(
        repo,
        task_type="bug_fixing",
        request_text="pytest import error runtime start",
        files=["src/aictx/middleware.py"],
        area_id="src/aictx",
    )

    assert len(context["failures"]) == 5
    assert context["loaded"]["failures"] is True
    assert all(row["match_score"] > 0 for row in context["failures"])


def test_unrelated_failures_do_not_contaminate_startup_context(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _write_failure(
        repo,
        {
            "failure_id": "failure::docs",
            "signature": "docs_spellcheck_failure",
            "failure_signature": "markdown_spellcheck_failure",
            "task_type": "documentation",
            "area_id": "docs",
            "symptoms": ["typo in docs"],
            "related_paths": ["docs/index.md"],
            "status": "open",
        },
    )

    prepared = prepare_execution(_payload(repo, "exec-unrelated-failure"))

    assert prepared["continuity_context"]["failures"] == []
    assert prepared["continuity_context"]["loaded"]["failures"] is False
    assert "- failures: no" in prepared["continuity_summary_text"]
