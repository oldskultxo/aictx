from __future__ import annotations

from pathlib import Path

import aictx.strategy_memory as strategy_memory
from aictx.scaffold import init_repo_scaffold


def _persist(repo: Path, **overrides):
    row = {
        "task_id": overrides.pop("task_id"),
        "task_text": overrides.pop("task_text", "continuity runtime"),
        "task_type": overrides.pop("task_type", "testing"),
        "area_id": overrides.pop("area_id", "src/aictx"),
        "entry_points": overrides.pop("entry_points", []),
        "primary_entry_point": overrides.pop("primary_entry_point", None),
        "files_used": overrides.pop("files_used", []),
        "files_edited": overrides.pop("files_edited", []),
        "commands_executed": overrides.pop("commands_executed", []),
        "tests_executed": overrides.pop("tests_executed", []),
        "success": True,
        "is_failure": False,
        "timestamp": overrides.pop("timestamp", "2026-04-24T00:00:00Z"),
    }
    row.update(overrides)
    strategy_memory.persist_strategy(repo, row)


def test_strategy_reuse_confidence_high_medium_low(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _persist(repo, task_id="low", task_text="unrelated")
    _persist(repo, task_id="medium", commands_executed=["make test"], tests_executed=["make test"], files_edited=["src/aictx/continuity.py"])
    _persist(repo, task_id="high", primary_entry_point="src/aictx/continuity.py", files_used=["src/aictx/continuity.py"])

    high = strategy_memory.select_strategy(repo, "testing", files=["src/aictx/continuity.py"], primary_entry_point="src/aictx/continuity.py", request_text="continuity runtime")
    assert high["task_id"] == "high"
    assert high["reuse_confidence"] == "high"

    medium = strategy_memory.select_strategy(repo, "testing", request_text="different request")
    assert medium["reuse_confidence"] in {"medium", "high"}

    assert strategy_memory.strategy_reuse_confidence({"matched_signals": ["recency"], "similarity_breakdown": {"total": 0}}) == "low"
