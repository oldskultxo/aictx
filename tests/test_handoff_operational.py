from __future__ import annotations

from pathlib import Path

from aictx.continuity import HANDOFF_PATH, HANDOFFS_HISTORY_PATH, load_handoff_history, render_startup_banner
from aictx.middleware import finalize_execution, prepare_execution
from aictx.scaffold import init_repo_scaffold
from aictx.state import read_json


def test_finalize_accepts_structured_operational_handoff(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    prepared = prepare_execution({
        "repo_root": str(repo),
        "user_request": "implement operational handoff",
        "agent_id": "codex",
        "adapter_id": "codex",
        "execution_id": "handoff-v2",
        "timestamp": "2026-04-25T00:00:00Z",
        "files_edited": ["src/aictx/continuity.py"],
    })

    finalize_execution(prepared, {
        "success": True,
        "result_summary": "Fallback summary should not win.",
        "handoff": {
            "summary": "Implemented operational handoff.",
            "completed": ["Added structured fields."],
            "next_steps": ["Run smoke tests."],
            "blocked": ["No blocker."],
            "risks": ["Banner noise."],
            "recommended_starting_points": ["src/aictx/continuity.py"],
        },
    })

    handoff = read_json(repo / HANDOFF_PATH, {})
    assert handoff["summary"] == "Implemented operational handoff."
    assert handoff["completed"] == ["Added structured fields."]
    assert handoff["next_steps"] == ["Run smoke tests."]
    assert handoff["blocked"] == ["No blocker."]
    assert handoff["open_items"] == ["No blocker."]
    assert handoff["risks"] == ["Banner noise."]
    history = load_handoff_history(repo)
    assert history[-1]["completed"] == ["Added structured fields."]


def test_startup_banner_uses_compact_handoff_history_clause(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    (repo / HANDOFFS_HISTORY_PATH).parent.mkdir(parents=True, exist_ok=True)
    (repo / HANDOFFS_HISTORY_PATH).write_text(
        '{"summary":"Very long fallback narrative that should be ignored when completed exists","completed":["Compact done."],"status":"resolved","recommended_starting_points":["src/aictx/continuity.py"]}\n',
        encoding="utf-8",
    )

    banner = render_startup_banner({"session": {"agent_label": "codex@repo", "session_count": 2}}, repo)

    assert "Compact done" in banner
    assert "Last progress: Compact done." in banner
