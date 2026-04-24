from __future__ import annotations

from pathlib import Path

from aictx.continuity import HANDOFF_PATH, load_continuity_context
from aictx.middleware import prepare_execution
from aictx.scaffold import init_repo_scaffold
from aictx.state import write_json


def _payload(repo: Path, execution_id: str = "exec-handoff-load") -> dict:
    return {
        "repo_root": str(repo),
        "user_request": "resume previous task",
        "agent_id": "codex",
        "adapter_id": "codex",
        "execution_id": execution_id,
        "timestamp": "2026-04-24T12:00:00Z",
    }


def test_load_continuity_context_loads_valid_handoff(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    write_json(
        repo / HANDOFF_PATH,
        {
            "summary": "Continue middleware cleanup.",
            "completed": ["Added handoff persistence."],
            "open_items": ["Wire handoff load tests."],
            "risks": [],
            "next_steps": ["Inspect continuity loader."],
            "recommended_starting_points": ["src/aictx/continuity.py"],
            "updated_at": "2026-04-24T12:00:00Z",
            "source_session": 2,
            "source_execution_id": "exec-prev",
        },
    )

    context = load_continuity_context(repo, task_type="testing", request_text="resume previous task")

    assert context["handoff"]["summary"] == "Continue middleware cleanup."
    assert context["loaded"]["handoff"] is True
    assert "- handoff: yes" in context["continuity_summary_text"]


def test_prepare_execution_reports_handoff_no_when_missing(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    prepared = prepare_execution(_payload(repo, "exec-no-handoff"))

    assert prepared["continuity_context"]["handoff"] == {}
    assert prepared["continuity_context"]["loaded"]["handoff"] is False
    assert "- handoff: no" in prepared["continuity_summary_text"]


def test_prepare_execution_handles_malformed_handoff_with_warning(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    handoff_path = repo / HANDOFF_PATH
    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    handoff_path.write_text("{broken", encoding="utf-8")

    prepared = prepare_execution(_payload(repo, "exec-bad-handoff"))

    context = prepared["continuity_context"]
    assert context["handoff"] == {}
    assert context["loaded"]["handoff"] is False
    assert "malformed:.aictx/continuity/handoff.json" in context["warnings"]
    assert "- handoff: no" in prepared["continuity_summary_text"]
