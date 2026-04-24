from __future__ import annotations

import json
from pathlib import Path

from aictx.continuity import DECISIONS_PATH, HANDOFF_PATH, SEMANTIC_REPO_PATH
from aictx.middleware import prepare_execution
from aictx.scaffold import init_repo_scaffold
from aictx.state import write_json


def _payload(repo: Path, execution_id: str = "exec-summary") -> dict:
    return {
        "repo_root": str(repo),
        "user_request": "continue startup continuity work",
        "agent_id": "codex",
        "adapter_id": "codex",
        "execution_id": execution_id,
        "timestamp": "2026-04-24T11:05:00Z",
        "files_opened": ["src/aictx/middleware.py"],
    }


def test_prepare_execution_reports_empty_continuity_summary(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    prepared = prepare_execution(_payload(repo, "exec-empty"))

    expected = (
        f"codex@{repo.name} (session #1) - awake\n\n"
        "Loaded:\n"
        "- handoff: no\n"
        "- decisions: no\n"
        "- failures: no\n"
        "- preferences: yes\n"
        "- semantic_repo: no\n"
        "- procedural_reuse: no"
    )
    assert prepared["continuity_summary_text"] == expected
    assert prepared["continuity_context"]["continuity_summary_text"] == expected
    assert prepared["startup_banner_text"] == f"AICTX: codex@{repo.name} session #1 — no previous handoff yet."
    assert prepared["startup_banner_policy"]["show_in_first_user_visible_response"] is True
    assert prepared["continuity_context"]["startup_banner_text"] == f"AICTX: codex@{repo.name} session #1 — no previous handoff yet."


def test_prepare_execution_reports_rich_continuity_summary(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    write_json(repo / HANDOFF_PATH, {"summary": "resume continuity task"})
    write_json(repo / SEMANTIC_REPO_PATH, {"subsystems": [{"name": "startup"}]})
    decisions_path = repo / DECISIONS_PATH
    decisions_path.parent.mkdir(parents=True, exist_ok=True)
    decisions_path.write_text(json.dumps({"decision": "keep summary truthful"}) + "\n", encoding="utf-8")
    failures_path = repo / ".aictx" / "failure_memory" / "failure_patterns.jsonl"
    failures_path.write_text(
        json.dumps({
            "failure_id": "failure::startup",
            "signature": "startup",
            "task_type": "bug_fixing",
            "area_id": "src/aictx/middleware.py",
            "error_text": "startup continuity bug",
            "files_involved": ["src/aictx/middleware.py"],
            "status": "open",
        }) + "\n",
        encoding="utf-8",
    )
    strategies_path = repo / ".aictx" / "strategy_memory" / "strategies.jsonl"
    strategies_path.write_text(
        json.dumps({
            "task_id": "strategy-1",
            "task_text": "continue startup continuity work",
            "task_type": "bug_fixing",
            "area_id": "src/aictx/middleware.py",
            "entry_points": ["src/aictx/middleware.py"],
            "primary_entry_point": "src/aictx/middleware.py",
            "files_used": ["src/aictx/middleware.py"],
            "success": True,
        }) + "\n",
        encoding="utf-8",
    )

    prepared = prepare_execution(
        {
            **_payload(repo, "exec-rich"),
            "declared_task_type": "bug_fixing",
        }
    )

    expected = (
        f"codex@{repo.name} (session #1) - awake\n\n"
        "Loaded:\n"
        "- handoff: yes\n"
        "- decisions: yes\n"
        "- failures: yes\n"
        "- preferences: yes\n"
        "- semantic_repo: yes\n"
        "- procedural_reuse: yes"
    )
    assert prepared["continuity_summary_text"] == expected
    assert prepared["startup_banner_text"] == f"AICTX: codex@{repo.name} session #1 — last time we resolved: resume continuity task."
    assert prepared["continuity_context"]["loaded"] == {
        "session": True,
        "handoff": True,
        "decisions": True,
        "failures": True,
        "preferences": True,
        "semantic_repo": True,
        "procedural_reuse": True,
    }
