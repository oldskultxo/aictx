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
    assert prepared["startup_banner_text"] == (
        f"codex@{repo.name} · session #1 · awake\n\n"
        "No previous handoff to resume."
    )


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
        f"codex@{repo.name} · session #1 · awake\n\n"
        "Resuming: release alignment.\n"
        "Last progress: updated release metadata.\n"
        "Entry point: pyproject.toml"
    )


def test_prepare_execution_startup_banner_summarizes_recent_handoff_history_compactly(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    history_path = repo / HANDOFFS_HISTORY_PATH
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "execution_id": "exec-1",
                        "timestamp": "2026-04-24T08:00:00Z",
                        "summary": "Phase 1 complete: laid down runtime middleware scaffolding and base continuity wiring.",
                        "status": "resolved",
                        "recommended_starting_points": ["src/aictx/runtime_launcher.py"],
                    }
                ),
                json.dumps(
                    {
                        "execution_id": "exec-2",
                        "timestamp": "2026-04-24T09:00:00Z",
                        "summary": "Phase 2 complete: implemented handoff history and startup banner.",
                        "status": "resolved",
                        "recommended_starting_points": ["src/aictx/continuity.py"],
                    }
                ),
                json.dumps(
                    {
                        "execution_id": "exec-3",
                        "timestamp": "2026-04-24T10:00:00Z",
                        "summary": "Phase 3 complete: added compact final summary and markdown details file.",
                        "status": "resolved",
                        "recommended_starting_points": ["src/aictx/middleware.py"],
                    }
                ),
                json.dumps(
                    {
                        "execution_id": "exec-4",
                        "timestamp": "2026-04-24T11:00:00Z",
                        "summary": "Phase 4 completed: aligned docs and ran full validation.",
                        "status": "resolved",
                        "recommended_starting_points": ["README.md"],
                    }
                ),
                json.dumps(
                    {
                        "execution_id": "exec-5",
                        "timestamp": "2026-04-24T12:00:00Z",
                        "summary": "Final phase executed: verified local init from source checkout and clean git status.",
                        "status": "resolved",
                        "recommended_starting_points": ["AGENTS.md", "CLAUDE.md"],
                    }
                ),
                json.dumps(
                    {
                        "execution_id": "exec-6",
                        "timestamp": "2026-04-24T13:00:00Z",
                        "summary": "Updated AICTX compact final summary details path to render as a clickable markdown link for IDE/chat surfaces.",
                        "status": "resolved",
                        "recommended_starting_points": ["src/aictx/middleware.py", "tests/test_smoke.py"],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    prepared = prepare_execution(_payload(repo, "exec-standup"))

    banner = prepared["startup_banner_text"]
    assert banner == (
        f"codex@{repo.name} · session #1 · awake\n\n"
        "Resuming: Updated AICTX compact final summary details path to render as a….\n"
        "Last progress: Updated AICTX compact final summary details path to render as a clickable markdown link for IDE/chat surfaces.\n"
        "Entry point: src/aictx/middleware.py"
    )
    assert banner.count(";") == 0
    assert "implemented handoff history and startup banner" not in banner


def test_prepare_execution_startup_banner_uses_next_steps_for_pending_work(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    write_json(
        repo / HANDOFF_PATH,
        {
            "summary": "Continue middleware cleanup.",
            "completed": ["Added handoff persistence."],
            "next_steps": ["Inspect continuity loader."],
            "recommended_starting_points": ["src/aictx/continuity.py"],
        },
    )

    banner = prepare_execution(_payload(repo, "exec-next-steps"))["startup_banner_text"]

    assert "Next: Inspect continuity loader." in banner
    assert "Entry point:" not in banner


def test_prepare_execution_startup_banner_uses_entry_point_without_pending_work(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    write_json(
        repo / HANDOFF_PATH,
        {
            "summary": "Updated release metadata",
            "completed": ["Aligned pyproject.toml and src/aictx/_version.py."],
            "recommended_starting_points": ["pyproject.toml", "src/aictx/_version.py"],
        },
    )

    banner = prepare_execution(_payload(repo, "exec-entry-point"))["startup_banner_text"]

    assert "Entry point: pyproject.toml" in banner
    assert "Next:" not in banner


def test_prepare_execution_startup_banner_omits_redundant_single_entry_point(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    write_json(
        repo / HANDOFF_PATH,
        {
            "summary": "Updated src/aictx/middleware.py",
            "completed": ["Updated src/aictx/middleware.py"],
            "recommended_starting_points": ["src/aictx/middleware.py"],
        },
    )

    banner = prepare_execution(_payload(repo, "exec-redundant-entry-point"))["startup_banner_text"]

    assert "Entry point:" not in banner
    assert "Next:" not in banner
    assert "src/aictx/middleware.py" in banner


def test_prepare_execution_startup_banner_uses_blocked_status_and_preserves_tokens(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    history_path = repo / HANDOFFS_HISTORY_PATH
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        json.dumps(
            {
                "execution_id": "exec-blocked",
                "timestamp": "2026-04-24T14:00:00Z",
                "summary": "portable continuity flag validation",
                "status": "blocked",
                "reason": "git-portable continuity",
                "blocked": ["Need to preserve --no-gitignore and --portable-continuity behavior."],
                "recommended_starting_points": ["tests/test_portability.py"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    banner = prepare_execution(_payload(repo, "exec-blocked"))["startup_banner_text"]

    assert "Blocked:" in banner
    assert "Last progress:" not in banner
    assert "Next: Need to preserve --no-gitignore and --portable-continuity behavior" in banner
    assert "--no-gitignore" in banner
    assert "--portable-continuity" in banner
