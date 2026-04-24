from __future__ import annotations

from pathlib import Path

import json

from aictx.continuity import HANDOFF_PATH, HANDOFFS_HISTORY_PATH, load_continuity_context
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
    assert prepared["startup_banner_text"] == f"AICTX: codex@{repo.name} session #1 — no previous handoff yet."


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


def test_prepare_execution_startup_banner_uses_latest_handoff_history(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    history_path = repo / HANDOFFS_HISTORY_PATH
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "execution_id": "exec-old",
                        "timestamp": "2026-04-24T10:00:00Z",
                        "summary": "old summary",
                        "status": "resolved",
                        "reason": "old reason",
                        "task_type": "testing",
                        "recommended_starting_points": ["src/old.py"],
                    }
                ),
                json.dumps(
                    {
                        "execution_id": "exec-new",
                        "timestamp": "2026-04-24T11:00:00Z",
                        "summary": "updated release metadata",
                        "status": "resolved",
                        "reason": "release alignment",
                        "task_type": "testing",
                        "recommended_starting_points": ["pyproject.toml", "src/aictx/_version.py"],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    prepared = prepare_execution(_payload(repo, "exec-from-history"))
    assert prepared["startup_banner_text"] == (
        f"AICTX: codex@{repo.name} session #1 — last time we resolved: updated release metadata."
        " Next likely start: pyproject.toml, src/aictx/_version.py."
    )
