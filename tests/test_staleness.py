from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import aictx.strategy_memory as strategy_memory
from aictx.continuity import DECISIONS_PATH, HANDOFF_PATH, SEMANTIC_REPO_PATH, STALENESS_PATH, load_continuity_context, refresh_staleness
from aictx.scaffold import init_repo_scaffold


def _strategy(repo: Path, **overrides):
    row = {
        "task_id": overrides.pop("task_id"),
        "task_text": overrides.pop("task_text", "staleness task"),
        "task_type": overrides.pop("task_type", "testing"),
        "area_id": overrides.pop("area_id", "src/aictx"),
        "entry_points": overrides.pop("entry_points", []),
        "primary_entry_point": overrides.pop("primary_entry_point", None),
        "files_used": overrides.pop("files_used", []),
        "success": overrides.pop("success", True),
        "is_failure": overrides.pop("is_failure", False),
        "timestamp": overrides.pop("timestamp", "2026-04-24T00:00:00Z"),
    }
    row.update(overrides)
    strategy_memory.persist_strategy(repo, row)


def test_missing_handoff_paths_mark_stale_and_exclude_startup_handoff(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    (repo / HANDOFF_PATH).write_text(
        json.dumps({
            "summary": "continue deleted file work",
            "updated_at": "2026-04-24T00:00:00Z",
            "recommended_starting_points": ["src/deleted.py"],
        }),
        encoding="utf-8",
    )

    result = refresh_staleness(repo, now=datetime(2026, 4, 24, tzinfo=timezone.utc))
    context = load_continuity_context(repo, task_type="testing")

    assert result["staleness"]["handoff"]["stale"] is True
    assert result["staleness"]["handoff"]["reasons"] == ["missing_paths:src/deleted.py"]
    assert context["handoff"] == {}
    assert context["loaded"]["handoff"] is False


def test_recent_memory_with_existing_paths_is_not_penalized(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    (repo / "src").mkdir()
    (repo / "src" / "live.py").write_text("print('live')\n", encoding="utf-8")
    (repo / HANDOFF_PATH).write_text(
        json.dumps({
            "summary": "continue live work",
            "updated_at": "2026-04-24T00:00:00Z",
            "recommended_starting_points": ["src/live.py"],
        }),
        encoding="utf-8",
    )
    (repo / SEMANTIC_REPO_PATH).write_text(
        json.dumps({
            "repo_id": "repo",
            "updated_at": "2026-04-24T00:00:00Z",
            "subsystems": [{
                "name": "live_subsystem",
                "description": "Recent live subsystem.",
                "key_paths": ["src/live.py"],
                "entry_points": [],
                "relevant_tests": [],
                "fragile_areas": [],
            }],
        }),
        encoding="utf-8",
    )

    result = refresh_staleness(repo, now=datetime(2026, 4, 24, tzinfo=timezone.utc))
    context = load_continuity_context(repo, task_type="testing")

    assert result["staleness"]["handoff"]["stale"] is False
    assert result["staleness"]["semantic_repo"]["subsystems"] == []
    assert context["loaded"]["handoff"] is True
    assert context["semantic_repo"]["subsystems"][0]["name"] == "live_subsystem"


def test_reuse_selection_excludes_clearly_stale_strategy(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _strategy(
        repo,
        task_id="stale-perfect-match",
        files_used=["src/deleted.py"],
        entry_points=["src/deleted.py"],
        primary_entry_point="src/deleted.py",
    )
    _strategy(
        repo,
        task_id="fresh-fallback",
        task_text="staleness task",
        files_used=[],
        entry_points=[],
        timestamp="2026-04-24T00:01:00Z",
    )

    refresh_staleness(repo, now=datetime(2026, 4, 24, tzinfo=timezone.utc))
    context = load_continuity_context(
        repo,
        task_type="testing",
        request_text="staleness task",
        files=["src/deleted.py"],
        primary_entry_point="src/deleted.py",
    )

    assert context["staleness"]["strategies"] == [{
        "task_id": "stale-perfect-match",
        "stale": True,
        "reasons": ["all_paths_missing:src/deleted.py"],
    }]
    assert context["procedural_reuse"]["task_id"] == "fresh-fallback"


def test_superseded_decision_is_marked_and_excluded_from_startup(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    (repo / DECISIONS_PATH).parent.mkdir(parents=True, exist_ok=True)
    old = {
        "decision": "Use old continuity path.",
        "execution_id": "old-exec",
        "subsystem": "continuity_runtime",
        "related_paths": [],
    }
    new = {
        "decision": "Use new continuity path.",
        "execution_id": "new-exec",
        "subsystem": "continuity_runtime",
        "related_paths": [],
    }
    (repo / DECISIONS_PATH).write_text("\n".join(json.dumps(item) for item in [old, new]) + "\n", encoding="utf-8")

    result = refresh_staleness(repo, now=datetime(2026, 4, 24, tzinfo=timezone.utc))
    context = load_continuity_context(repo, task_type="testing", max_decisions=5)

    assert result["staleness"]["decisions"][0]["ref"] == "old-exec:Use old continuity path."
    assert result["staleness"]["decisions"][0]["reasons"] == ["superseded_by:new-exec:Use new continuity path."]
    assert [decision["execution_id"] for decision in context["decisions"]] == ["new-exec"]
    assert (repo / STALENESS_PATH).exists()
