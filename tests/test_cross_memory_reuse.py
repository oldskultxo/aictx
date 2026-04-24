from __future__ import annotations

import json
from pathlib import Path

import aictx.strategy_memory as strategy_memory
from aictx.continuity import DECISIONS_PATH, HANDOFF_PATH, SEMANTIC_REPO_PATH, load_continuity_context
from aictx.failure_memory import FAILURE_PATTERNS_PATH
from aictx.scaffold import init_repo_scaffold


def _strategy(repo: Path, **overrides):
    row = {
        "task_id": overrides.pop("task_id"),
        "task_text": overrides.pop("task_text", "testing continuity reuse"),
        "task_type": overrides.pop("task_type", "testing"),
        "area_id": overrides.pop("area_id", "src/aictx"),
        "entry_points": overrides.pop("entry_points", []),
        "primary_entry_point": overrides.pop("primary_entry_point", None),
        "files_used": overrides.pop("files_used", []),
        "files_edited": overrides.pop("files_edited", []),
        "commands_executed": overrides.pop("commands_executed", []),
        "tests_executed": overrides.pop("tests_executed", []),
        "notable_errors": overrides.pop("notable_errors", []),
        "success": overrides.pop("success", True),
        "is_failure": overrides.pop("is_failure", False),
        "timestamp": overrides.pop("timestamp", "2026-04-24T00:00:00Z"),
    }
    row.update(overrides)
    strategy_memory.persist_strategy(repo, row)


def test_reuse_can_be_assisted_by_handoff_files(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    (repo / HANDOFF_PATH).write_text(
        json.dumps({"recommended_starting_points": ["src/aictx/middleware.py"]}),
        encoding="utf-8",
    )
    _strategy(
        repo,
        task_id="older-handoff-match",
        files_used=["src/aictx/middleware.py"],
        entry_points=["src/aictx/middleware.py"],
        primary_entry_point="src/aictx/middleware.py",
    )
    _strategy(
        repo,
        task_id="newer-no-handoff-match",
        files_used=["src/other.py"],
        entry_points=["src/other.py"],
        primary_entry_point="src/other.py",
        timestamp="2026-04-24T00:01:00Z",
    )

    context = load_continuity_context(repo, task_type="testing", request_text="testing continuity reuse")
    reuse = context["procedural_reuse"]

    assert reuse["task_id"] == "older-handoff-match"
    assert reuse["cross_memory_reuse"]["handoff_match"] is True
    assert "handoff_match:src/aictx/middleware.py" in reuse["matched_signals"]
    assert reuse["similarity_breakdown"]["handoff_match"] == 1


def test_reuse_exposes_failure_avoidance_without_selecting_failed_strategy(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _strategy(
        repo,
        task_id="successful-middleware",
        files_used=["src/aictx/middleware.py"],
        entry_points=["src/aictx/middleware.py"],
        primary_entry_point="src/aictx/middleware.py",
    )
    _strategy(
        repo,
        task_id="failed-middleware",
        files_used=["src/aictx/middleware.py"],
        entry_points=["src/aictx/middleware.py"],
        primary_entry_point="src/aictx/middleware.py",
        is_failure=True,
        success=False,
    )
    failure_path = repo / FAILURE_PATTERNS_PATH
    failure_path.parent.mkdir(parents=True, exist_ok=True)
    failure_path.write_text(
        json.dumps({
            "failure_id": "failure::middleware-loop",
            "task_type": "testing",
            "area_id": "src/aictx",
            "status": "open",
            "related_paths": ["src/aictx/middleware.py"],
            "symptoms": ["startup loop"],
            "resolution_hint": "Avoid rerunning the same startup loop.",
        }) + "\n",
        encoding="utf-8",
    )

    context = load_continuity_context(
        repo,
        task_type="testing",
        files=["src/aictx/middleware.py"],
        area_id="src/aictx",
        request_text="startup loop middleware",
    )
    reuse = context["procedural_reuse"]

    assert reuse["task_id"] == "successful-middleware"
    assert reuse["cross_memory_reuse"]["known_failure_avoidance"] is True
    assert reuse["similarity_breakdown"]["known_failure_avoidance"] == 0
    assert reuse["avoidance_warnings"] == ["avoid_known_failure:failure::middleware-loop"]
    assert "known_failure_avoidance:failure::middleware-loop" in reuse["matched_signals"]


def test_reuse_exposes_decision_and_semantic_support_as_json(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    (repo / DECISIONS_PATH).parent.mkdir(parents=True, exist_ok=True)
    (repo / DECISIONS_PATH).write_text(
        json.dumps({
            "decision": "Keep continuity in middleware.",
            "subsystem": "continuity_runtime",
            "related_paths": ["src/aictx/middleware.py"],
        }) + "\n",
        encoding="utf-8",
    )
    (repo / SEMANTIC_REPO_PATH).write_text(
        json.dumps({
            "repo_id": "repo",
            "subsystems": [{
                "name": "continuity_runtime",
                "description": "Continuity context loading.",
                "key_paths": ["src/aictx/middleware.py"],
                "entry_points": ["load_continuity_context"],
                "relevant_tests": ["tests/test_continuity_context.py"],
                "fragile_areas": [],
            }],
        }),
        encoding="utf-8",
    )
    _strategy(
        repo,
        task_id="middleware-strategy",
        files_used=["src/aictx/middleware.py"],
        entry_points=["src/aictx/middleware.py"],
        primary_entry_point="src/aictx/middleware.py",
    )

    context = load_continuity_context(repo, task_type="testing")
    reuse = context["procedural_reuse"]

    assert reuse["task_id"] == "middleware-strategy"
    assert reuse["cross_memory_reuse"] == {
        "handoff_match": False,
        "recent_decision_support": True,
        "known_failure_avoidance": False,
        "semantic_subsystem_match": True,
    }
    assert "recent_decision_support:continuity_runtime" in reuse["matched_signals"]
    assert "semantic_subsystem_match:continuity_runtime" in reuse["matched_signals"]
    assert reuse["similarity_breakdown"]["recent_decision_support"] == 1
    assert reuse["similarity_breakdown"]["semantic_subsystem_match"] == 1
