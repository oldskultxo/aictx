from __future__ import annotations

from pathlib import Path

import aictx.strategy_memory as strategy_memory
from aictx.scaffold import init_repo_scaffold


def _persist(repo: Path, **overrides):
    row = {
        "task_id": overrides.pop("task_id"),
        "task_text": overrides.pop("task_text", ""),
        "task_type": overrides.pop("task_type", "testing"),
        "area_id": overrides.pop("area_id", "src/aictx"),
        "entry_points": overrides.pop("entry_points", []),
        "primary_entry_point": overrides.pop("primary_entry_point", None),
        "files_used": overrides.pop("files_used", []),
        "commands_executed": overrides.pop("commands_executed", []),
        "tests_executed": overrides.pop("tests_executed", []),
        "notable_errors": overrides.pop("notable_errors", []),
        "success": overrides.pop("success", True),
        "is_failure": overrides.pop("is_failure", False),
        "timestamp": overrides.pop("timestamp", "2026-04-24T00:00:00Z"),
    }
    row.update(overrides)
    strategy_memory.persist_strategy(repo, row)
    return row


def test_select_strategy_does_not_reuse_failures_as_positive_strategies(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _persist(
        repo,
        task_id="failed-perfect-match",
        task_text="fix middleware continuity failure",
        primary_entry_point="src/aictx/middleware.py",
        files_used=["src/aictx/middleware.py"],
        is_failure=True,
        success=False,
    )
    _persist(repo, task_id="successful-weaker-match", task_text="fix middleware continuity")

    selected = strategy_memory.select_strategy(
        repo,
        "testing",
        files=["src/aictx/middleware.py"],
        primary_entry_point="src/aictx/middleware.py",
        request_text="fix middleware continuity failure",
    )

    assert selected is not None
    assert selected["task_id"] == "successful-weaker-match"
    assert selected["reused_strategy"] is True
    assert selected["similarity_breakdown"]["success_status"] == "success"


def test_select_strategy_uses_strong_signals_over_weak_newer_reuse(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _persist(
        repo,
        task_id="old-strong",
        task_text="unrelated text",
        primary_entry_point="src/aictx/middleware.py",
        files_used=["src/aictx/middleware.py"],
        entry_points=["src/aictx/middleware.py"],
        commands_executed=["python -m pytest tests/test_smoke.py"],
        tests_executed=["tests/test_smoke.py"],
    )
    _persist(
        repo,
        task_id="new-weak",
        task_text="continuity middleware summary startup boot",
        files_used=["src/other.py"],
        primary_entry_point="src/other.py",
    )

    selected = strategy_memory.select_strategy(
        repo,
        "testing",
        files=["src/aictx/middleware.py"],
        primary_entry_point="src/aictx/middleware.py",
        request_text="continuity middleware summary startup boot",
        commands=["python -m pytest tests/test_smoke.py"],
        tests=["tests/test_smoke.py"],
    )

    assert selected is not None
    assert selected["task_id"] == "old-strong"
    assert selected["similarity_breakdown"]["primary_entry_point"] == 5000
    assert selected["similarity_breakdown"]["file_overlap"] == 3100
    assert "recency" in selected["similarity_breakdown"]


def test_select_strategy_reasons_are_structured_and_deterministic(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _persist(
        repo,
        task_id="deterministic",
        task_text="run middleware package validation",
        primary_entry_point="src/aictx/middleware.py",
        files_used=["src/aictx/middleware.py"],
        commands_executed=["python -m pytest tests/test_smoke.py"],
        tests_executed=["tests/test_smoke.py"],
        notable_errors=["AssertionError startup summary missing"],
    )

    selected = strategy_memory.select_strategy(
        repo,
        "testing",
        files=["src/aictx/middleware.py"],
        primary_entry_point="src/aictx/middleware.py",
        request_text="run middleware package validation",
        commands=["python -m pytest tests/test_smoke.py"],
        tests=["tests/test_smoke.py"],
        errors=["AssertionError startup summary missing"],
        area_id="src/aictx",
    )

    assert selected is not None
    assert selected["matched_signals"][:4] == [
        "task_type:testing",
        "primary_entry_point:src/aictx/middleware.py",
        "file_overlap:src/aictx/middleware.py",
        "prompt_similarity:1.0",
    ]
    assert selected["selection_reason"].startswith("task_type:testing; primary_entry_point:src/aictx/middleware.py")
    assert selected["similarity_breakdown"]["total"] == selected["score"]
    assert selected["overlapping_files"] == ["src/aictx/middleware.py"]
    assert selected["related_commands"] == ["python -m pytest tests/test_smoke.py"]
    assert selected["related_tests"] == ["tests/test_smoke.py"]


def test_select_strategy_matches_area_or_subsystem_overlap(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _persist(repo, task_id="generic-new", area_id="src/other", timestamp="2026-04-24T00:01:00Z")
    _persist(repo, task_id="subsystem-match", area_id="src/aictx/continuity", subsystem="src/aictx")

    selected = strategy_memory.select_strategy(repo, "testing", area_id="src/aictx/middleware")

    assert selected is not None
    assert selected["task_id"] == "subsystem-match"
    assert "subsystem:src/aictx" in selected["matched_signals"]
    assert selected["similarity_breakdown"]["subsystem"] == 600
