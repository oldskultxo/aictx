from __future__ import annotations

from pathlib import Path

from aictx.report import build_real_usage_report
from aictx.scaffold import init_repo_scaffold
from aictx.state import append_jsonl, write_json


def test_real_usage_report_includes_continuity_health_quality(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    append_jsonl(repo / ".aictx" / "metrics" / "execution_logs.jsonl", {
        "task_id": "t1",
        "success": True,
        "files_opened": ["src/a.py"],
        "files_edited": [],
        "commands_executed": ["make test"],
        "tests_executed": ["make test"],
        "notable_errors": [],
        "capture_provenance": {"files_opened": "explicit", "files_edited": "unknown", "commands_executed": "explicit", "tests_executed": "heuristic", "notable_errors": "unknown"},
        "used_packet": True,
        "used_strategy": True,
    })
    append_jsonl(repo / ".aictx" / "metrics" / "execution_feedback.jsonl", {
        "task_id": "t1",
        "aictx_feedback": {"used_strategy": True, "used_packet": True, "possible_redundant_exploration": False},
        "agent_summary": {"capture_quality": {"coverage_ratio": 0.6}},
    })
    write_json(repo / ".aictx" / "continuity" / "continuity_metrics.json", {"strategy_reuse_count": 2})
    write_json(repo / ".aictx" / "continuity" / "handoff.json", {"updated_at": "2026-04-25T00:00:00Z"})
    write_json(repo / ".aictx" / "continuity" / "staleness.json", {"handoff": {"stale": False}, "decisions": [{"stale": True}], "strategies": []})

    report = build_real_usage_report(repo)

    health = report["continuity_health"]
    assert health["packet_context_usefulness"]["packet_usage_rate"] == 1.0
    assert health["stale_memory_excluded"] == 1
    assert health["redundant_exploration_avoided"] == 2
    assert health["capture_coverage_gaps"]["files_edited"] == 1
    assert health["avg_capture_quality"] == 0.6
    assert health["handoff_freshness"]["present"] is True
