from __future__ import annotations

import json
from pathlib import Path

from aictx.continuity import DECISIONS_PATH, HANDOFF_PATH, SEMANTIC_REPO_PATH, load_continuity_context
from aictx.middleware import prepare_execution
from aictx.scaffold import init_repo_scaffold
from aictx.state import REPO_CONTINUITY_SESSION_PATH, write_json


def _payload(repo: Path, execution_id: str = "exec-continuity") -> dict:
    return {
        "repo_root": str(repo),
        "user_request": "fix startup import bug",
        "agent_id": "codex",
        "adapter_id": "codex",
        "execution_id": execution_id,
        "timestamp": "2026-04-24T10:36:00Z",
        "files_opened": ["src/aictx/middleware.py"],
    }


def test_load_continuity_context_missing_artifacts_returns_empty_shapes(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    context = load_continuity_context(repo, task_type="testing", request_text="new task")

    assert context["session"] == {}
    assert context["handoff"] == {}
    assert context["decisions"] == []
    assert context["failures"] == []
    assert context["semantic_repo"] == {}
    assert context["procedural_reuse"] == {}
    assert context["loaded"]["preferences"] is True
    assert context["loaded"]["handoff"] is False
    assert context["warnings"] == []


def test_load_continuity_context_loads_bounded_relevant_memory(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    write_json(repo / REPO_CONTINUITY_SESSION_PATH, {
        "repo_id": "repo",
        "runtime": "codex",
        "agent_label": "codex@repo",
        "session_count": 3,
        "last_session_at": "2026-04-24T10:36:00Z",
    })
    write_json(repo / HANDOFF_PATH, {"summary": "resume startup work", "next_steps": ["inspect middleware"]})
    write_json(repo / SEMANTIC_REPO_PATH, {"repo_id": "repo", "subsystems": [{"name": "runtime_startup"}]})
    decisions_path = repo / DECISIONS_PATH
    decisions_path.parent.mkdir(parents=True, exist_ok=True)
    for index in range(7):
        with decisions_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"decision": f"decision {index}", "timestamp": f"2026-04-24T10:3{index}:00Z"}) + "\n")
    failures_path = repo / ".aictx" / "failure_memory" / "failure_patterns.jsonl"
    failures_path.write_text(
        json.dumps({
            "failure_id": "failure::import",
            "signature": "import",
            "task_type": "bug_fixing",
            "area_id": "src/aictx/middleware.py",
            "error_text": "startup import bug",
            "failed_command": "pytest",
            "files_involved": ["src/aictx/middleware.py"],
            "status": "open",
        }) + "\n",
        encoding="utf-8",
    )
    strategies_path = repo / ".aictx" / "strategy_memory" / "strategies.jsonl"
    strategies_path.write_text(
        json.dumps({
            "task_id": "strategy-1",
            "task_text": "fix startup import bug",
            "task_type": "bug_fixing",
            "area_id": "src/aictx/middleware.py",
            "entry_points": ["src/aictx/middleware.py"],
            "primary_entry_point": "src/aictx/middleware.py",
            "files_used": ["src/aictx/middleware.py"],
            "success": True,
        }) + "\n",
        encoding="utf-8",
    )

    context = load_continuity_context(
        repo,
        task_type="bug_fixing",
        request_text="fix startup import bug",
        files=["src/aictx/middleware.py"],
        primary_entry_point="src/aictx/middleware.py",
        area_id="src/aictx/middleware.py",
    )

    assert context["loaded"] == {
        "session": True,
        "handoff": True,
        "decisions": True,
        "failures": True,
        "preferences": True,
        "semantic_repo": True,
        "procedural_reuse": True,
    }
    assert context["session"]["agent_label"] == "codex@repo"
    assert context["handoff"]["summary"] == "resume startup work"
    assert [row["decision"] for row in context["decisions"]] == ["decision 2", "decision 3", "decision 4", "decision 5", "decision 6"]
    assert context["failures"][0]["failure_id"] == "failure::import"
    assert context["procedural_reuse"]["task_id"] == "strategy-1"


def test_load_continuity_context_ignores_malformed_artifacts_with_warnings(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    (repo / HANDOFF_PATH).write_text("{broken", encoding="utf-8")
    (repo / SEMANTIC_REPO_PATH).write_text("[]", encoding="utf-8")
    decisions_path = repo / DECISIONS_PATH
    decisions_path.parent.mkdir(parents=True, exist_ok=True)
    decisions_path.write_text('{"ok": true}\nnot-json\n[]\n', encoding="utf-8")
    (repo / ".aictx" / "failure_memory" / "failure_patterns.jsonl").write_text("not-json\n", encoding="utf-8")
    (repo / ".aictx" / "strategy_memory" / "strategies.jsonl").write_text("not-json\n", encoding="utf-8")

    context = load_continuity_context(repo, task_type="bug_fixing", request_text="startup")

    assert context["handoff"] == {}
    assert context["semantic_repo"] == {}
    assert context["decisions"] == [{"ok": True}]
    assert context["failures"] == []
    assert context["procedural_reuse"] == {}
    assert "malformed:.aictx/continuity/handoff.json" in context["warnings"]
    assert "invalid_type:.aictx/continuity/semantic_repo.json" in context["warnings"]
    assert "invalid_jsonl_lines:.aictx/continuity/decisions.jsonl:2" in context["warnings"]


def test_prepare_execution_includes_unified_continuity_context(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    write_json(repo / HANDOFF_PATH, {"summary": "continue here"})

    prepared = prepare_execution(_payload(repo))

    context = prepared["continuity_context"]
    assert context["session"]["session_count"] == 1
    assert context["agent_identity"]["agent_label"] == f"codex@{repo.name}"
    assert context["handoff"]["summary"] == "continue here"
    assert context["loaded"]["session"] is True
    assert context["loaded"]["handoff"] is True
