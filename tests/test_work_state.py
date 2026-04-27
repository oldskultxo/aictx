from __future__ import annotations

import json
from pathlib import Path

from aictx.scaffold import init_repo_scaffold
from aictx.state import REPO_TASKS_ACTIVE_PATH, REPO_TASK_THREADS_DIR
from aictx.work_state import (
    close_work_state,
    load_active_task_id,
    load_active_work_state,
    load_work_state,
    start_work_state,
    update_work_state,
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_start_work_state_creates_active_thread_and_event(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    state = start_work_state(
        repo,
        "Fix login token refresh",
        initial={"active_files": ["src/api/client.ts"], "next_action": "Inspect interceptor"},
    )

    assert state["task_id"] == "fix-login-token-refresh"
    assert load_active_task_id(repo) == "fix-login-token-refresh"
    assert _read_json(repo / REPO_TASKS_ACTIVE_PATH)["active_task_id"] == "fix-login-token-refresh"
    assert (repo / REPO_TASK_THREADS_DIR / "fix-login-token-refresh.json").is_file()
    events = (repo / REPO_TASK_THREADS_DIR / "fix-login-token-refresh.events.jsonl").read_text(encoding="utf-8").splitlines()
    assert any('"event": "started"' in line for line in events)


def test_load_active_work_state_without_active_task_is_safe(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    assert load_active_task_id(repo) == ""
    assert load_active_work_state(repo) == {}


def test_update_work_state_merges_lists_with_dedupe(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(
        repo,
        "Fix login token refresh",
        initial={"active_files": ["src/api/client.ts"], "verified": ["login works"]},
    )

    state = update_work_state(
        repo,
        {
            "active_files": ["src/api/client.ts", "src/auth/session.ts"],
            "verified": ["login works", "401 path reproduces locally"],
            "recommended_commands": ["npm test -- auth", "npm test -- auth"],
        },
    )

    assert state["active_files"] == ["src/api/client.ts", "src/auth/session.ts"]
    assert state["verified"] == ["login works", "401 path reproduces locally"]
    assert state["recommended_commands"] == ["npm test -- auth"]


def test_close_work_state_keeps_thread_and_clears_active(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(repo, "Fix login token refresh")

    closed = close_work_state(repo, status="resolved")

    assert closed["status"] == "resolved"
    assert load_active_task_id(repo) == ""
    assert (repo / REPO_TASK_THREADS_DIR / "fix-login-token-refresh.json").is_file()
    assert _read_json(repo / REPO_TASKS_ACTIVE_PATH)["active_task_id"] == ""


def test_init_repo_scaffold_is_idempotent_for_existing_threads(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(repo, "Fix login token refresh", initial={"verified": ["login works"]})
    before = load_work_state(repo, "fix-login-token-refresh")

    created = init_repo_scaffold(repo, update_gitignore=False)
    after = load_work_state(repo, "fix-login-token-refresh")

    assert before == after
    assert (repo / REPO_TASK_THREADS_DIR).is_dir()
    assert str(repo / REPO_TASK_THREADS_DIR) not in created
