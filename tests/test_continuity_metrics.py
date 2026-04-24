from __future__ import annotations

from pathlib import Path

from aictx.continuity import CONTINUITY_METRICS_PATH
from aictx.middleware import finalize_execution, prepare_execution
from aictx.report import build_real_usage_report
from aictx.scaffold import init_repo_scaffold
from aictx.state import read_json, write_json


def _payload(repo: Path, execution_id: str, request: str) -> dict:
    return {
        "repo_root": str(repo),
        "user_request": request,
        "agent_id": "agent-test",
        "execution_id": execution_id,
    }


def test_continuity_metrics_increment_with_real_loads_and_reuse(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    first = prepare_execution(_payload(repo, "exec-metrics-1", "first run"))
    finalize_execution(first, {"success": True, "result_summary": "first", "validated_learning": True})

    second = prepare_execution(_payload(repo, "exec-metrics-2", "second run"))
    second["continuity_context"]["loaded"]["handoff"] = True
    second["continuity_context"]["loaded"]["decisions"] = True
    second["continuity_context"]["loaded"]["failures"] = True
    second["continuity_context"]["loaded"]["semantic_repo"] = True
    second["continuity_context"]["procedural_reuse"] = {
        "cross_memory_reuse": {"known_failure_avoidance": True}
    }
    finalize_execution(second, {"success": True, "result_summary": "second", "validated_learning": True})

    metrics = read_json(repo / CONTINUITY_METRICS_PATH, {})

    assert metrics["strategy_reuse_count"] == 1
    assert metrics["non_reuse_count"] == 1
    assert metrics["handoff_load_count"] == 1
    assert metrics["decision_load_count"] == 1
    assert metrics["failure_match_count"] == 1
    assert metrics["semantic_memory_load_count"] == 1
    assert metrics["repeated_failure_avoidance_count"] == 1
    assert isinstance(metrics["updated_at"], str)


def test_real_usage_report_includes_continuity_metrics(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    write_json(repo / CONTINUITY_METRICS_PATH, {
        "strategy_reuse_count": 8,
        "non_reuse_count": 4,
        "handoff_load_count": 10,
        "decision_load_count": 7,
        "failure_match_count": 3,
        "semantic_memory_load_count": 5,
        "repeated_failure_avoidance_count": 2,
        "updated_at": "2026-04-24T11:40:00Z",
    })

    report = build_real_usage_report(repo)

    assert report["continuity_metrics"] == {
        "strategy_reuse_count": 8,
        "non_reuse_count": 4,
        "handoff_load_count": 10,
        "decision_load_count": 7,
        "failure_match_count": 3,
        "semantic_memory_load_count": 5,
        "repeated_failure_avoidance_count": 2,
        "updated_at": "2026-04-24T11:40:00Z",
    }
