from __future__ import annotations

from pathlib import Path

from aictx.continuity import HANDOFF_PATH, HANDOFFS_HISTORY_PATH, load_handoff_history
from aictx.middleware import finalize_execution, prepare_execution
from aictx.scaffold import init_repo_scaffold
from aictx.state import read_json


def _payload(repo: Path, execution_id: str) -> dict:
    return {
        "repo_root": str(repo),
        "user_request": "implement handoff memory",
        "agent_id": "codex",
        "adapter_id": "codex",
        "execution_id": execution_id,
        "timestamp": "2026-04-24T11:30:00Z",
    }


def test_finalize_nontrivial_task_writes_handoff_memory(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    prepared = prepare_execution({
        **_payload(repo, "exec-handoff-1"),
        "files_opened": ["src/aictx/middleware.py"],
        "files_edited": ["src/aictx/continuity.py"],
    })

    finalized = finalize_execution(
        prepared,
        {"success": True, "result_summary": "Implemented handoff memory.", "validated_learning": False},
    )

    handoff_path = repo / HANDOFF_PATH
    assert handoff_path.exists()
    handoff = read_json(handoff_path, {})
    assert finalized["handoff_persisted"]["path"] == handoff_path.as_posix()
    assert handoff == finalized["handoff_persisted"]["handoff"]
    assert handoff["summary"] == "Implemented handoff memory."
    assert handoff["completed"] == ["Implemented handoff memory."]
    assert handoff["open_items"] == []
    assert handoff["risks"] == []
    assert handoff["next_steps"] == []
    assert handoff["recommended_starting_points"] == ["src/aictx/continuity.py", "src/aictx/middleware.py"]
    assert handoff["source_session"] == 1
    assert handoff["source_execution_id"] == "exec-handoff-1"
    assert handoff["updated_at"] == finalized["finalized_at"]
    history = load_handoff_history(repo)
    assert len(history) == 1
    assert history[0]["execution_id"] == "exec-handoff-1"
    assert history[0]["status"] == "resolved"
    assert history[0]["task_type"] == "feature_work"
    assert history[0]["reason"] == "implement handoff memory"
    assert history[0]["recommended_starting_points"] == ["src/aictx/continuity.py", "src/aictx/middleware.py"]


def test_finalize_trivial_task_does_not_write_handoff_noise(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    prepared = prepare_execution(_payload(repo, "exec-trivial"))

    finalized = finalize_execution(
        prepared,
        {"success": True, "result_summary": "", "validated_learning": False},
    )

    assert finalized["handoff_persisted"] is None
    assert not (repo / HANDOFF_PATH).exists()


def test_second_handoff_replaces_first(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    first = prepare_execution({
        **_payload(repo, "exec-first"),
        "files_opened": ["src/first.py"],
    })
    finalize_execution(first, {"success": True, "result_summary": "First handoff.", "validated_learning": False})

    second = prepare_execution({
        **_payload(repo, "exec-second"),
        "files_opened": ["src/second.py"],
    })
    finalized = finalize_execution(second, {"success": True, "result_summary": "Second handoff.", "validated_learning": False})

    handoff = read_json(repo / HANDOFF_PATH, {})
    assert handoff["summary"] == "Second handoff."
    assert handoff["source_execution_id"] == "exec-second"
    assert handoff["recommended_starting_points"] == ["src/second.py"]
    assert finalized["handoff_persisted"]["handoff"] == handoff
    history = load_handoff_history(repo)
    assert len(history) == 2
    assert history[-1]["execution_id"] == "exec-second"
    assert history[-1]["summary"] == "Second handoff."


def test_handoff_history_is_capped_to_latest_ten_records(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    for idx in range(12):
        prepared = prepare_execution({
            **_payload(repo, f"exec-{idx}"),
            "files_opened": [f"src/file_{idx}.py"],
        })
        finalize_execution(prepared, {"success": True, "result_summary": f"handoff {idx}", "validated_learning": False})
    history = load_handoff_history(repo)
    assert len(history) == 10
    assert history[0]["execution_id"] == "exec-2"
    assert history[-1]["execution_id"] == "exec-11"
    assert (repo / HANDOFFS_HISTORY_PATH).exists()
