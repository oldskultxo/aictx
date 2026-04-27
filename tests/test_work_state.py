from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from aictx.scaffold import init_repo_scaffold
from aictx.state import REPO_TASKS_ACTIVE_PATH, REPO_TASK_THREADS_DIR
from aictx.work_state import (
    capture_git_context,
    close_work_state,
    evaluate_work_state_git_context,
    list_work_states,
    load_active_task_id,
    load_active_work_state,
    load_active_work_state_checked,
    load_recent_inactive_work_state,
    load_work_state,
    resume_work_state,
    start_work_state,
    update_work_state,
)

GIT_AVAILABLE = shutil.which("git") is not None


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _init_git_repo(repo: Path) -> None:
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.com")
    tracked = repo / "tracked.txt"
    tracked.write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")


@pytest.mark.skipif(not GIT_AVAILABLE, reason="git binary unavailable")
def test_capture_git_context_records_branch_head_and_dirty_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _init_git_repo(repo)

    clean = capture_git_context(repo)
    (repo / "tracked.txt").write_text("base\nchange\n", encoding="utf-8")
    dirty = capture_git_context(repo)

    assert clean["available"] is True
    assert clean["branch"] == "main"
    assert clean["head"]
    assert clean["dirty"] is False
    assert dirty["dirty"] is True
    assert dirty["changed_files"] == ["tracked.txt"]


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


def test_list_show_resume_and_close_patch_work_state(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(repo, "Fix login token refresh")
    close_work_state(
        repo,
        status="blocked",
        patch={"risks": ["waiting on flaky CI"], "next_action": "rerun CI"},
    )
    start_work_state(repo, "Validate runtime summary")

    states = list_work_states(repo)
    assert [state["task_id"] for state in states] == ["validate-runtime-summary", "fix-login-token-refresh"]
    assert load_recent_inactive_work_state(repo)["task_id"] == "fix-login-token-refresh"
    assert load_work_state(repo, "fix-login-token-refresh")["risks"] == ["waiting on flaky CI"]

    resumed = resume_work_state(repo, "fix-login-token-refresh")

    assert resumed["status"] == "in_progress"
    assert load_active_task_id(repo) == "fix-login-token-refresh"
    events = (repo / REPO_TASK_THREADS_DIR / "fix-login-token-refresh.events.jsonl").read_text(encoding="utf-8").splitlines()
    assert any('"event": "resumed"' in line for line in events)


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


def test_existing_work_state_without_git_context_remains_loadable(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(repo, "Fix login token refresh")
    thread_path = repo / REPO_TASK_THREADS_DIR / "fix-login-token-refresh.json"
    payload = _read_json(thread_path)
    payload.pop("git_context", None)
    thread_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    checked = load_active_work_state_checked(repo)

    assert checked["active_work_state"]["task_id"] == "fix-login-token-refresh"
    assert checked["work_state_git_status"]["loadable"] is True
    assert checked["work_state_git_status"]["reason"] == "no_git_context"
    assert checked["skipped_work_state"] == {}


def test_non_git_repo_loads_work_state_with_git_unavailable_status(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    state = start_work_state(repo, "Fix login token refresh")
    checked = load_active_work_state_checked(repo)

    assert state["git_context"]["available"] is False
    assert checked["active_work_state"]["task_id"] == "fix-login-token-refresh"
    assert checked["work_state_git_status"]["reason"] == "git_unavailable"
    assert "unavailable" in checked["work_state_git_status"]["warning"]


@pytest.mark.skipif(not GIT_AVAILABLE, reason="git binary unavailable")
def test_same_branch_loads(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _init_git_repo(repo)
    start_work_state(repo, "Fix login token refresh")

    checked = load_active_work_state_checked(repo)

    assert checked["active_work_state"]["task_id"] == "fix-login-token-refresh"
    assert checked["work_state_git_status"]["loadable"] is True
    assert checked["work_state_git_status"]["reason"] == "same_branch"
    assert checked["skipped_work_state"] == {}


@pytest.mark.skipif(not GIT_AVAILABLE, reason="git binary unavailable")
def test_same_branch_changed_head_loads_with_warning(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _init_git_repo(repo)
    state = start_work_state(repo, "Fix login token refresh")
    saved_head = state["git_context"]["head"]
    (repo / "tracked.txt").write_text("base\nnext\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "next")

    status = evaluate_work_state_git_context(repo, load_work_state(repo, "fix-login-token-refresh"))

    assert status["loadable"] is True
    assert status["reason"] == "same_branch"
    assert status["saved_head"] == saved_head
    assert status["current_head"] != saved_head
    assert "HEAD changed" in status["warning"]


@pytest.mark.skipif(not GIT_AVAILABLE, reason="git binary unavailable")
def test_feature_branch_work_state_skipped_when_unmerged(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _init_git_repo(repo)
    _git(repo, "checkout", "-b", "feature/login")
    (repo / "tracked.txt").write_text("base\nfeature-only\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "feature commit")
    start_work_state(repo, "Fix login token refresh")
    _git(repo, "checkout", "main")
    (repo / "tracked.txt").write_text("base\nmain-only\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "main change")

    checked = load_active_work_state_checked(repo)

    assert checked["active_work_state"] == {}
    assert checked["work_state_git_status"]["loadable"] is False
    assert checked["work_state_git_status"]["reason"] == "branch_mismatch_unmerged"
    assert checked["skipped_work_state"]["task_id"] == "fix-login-token-refresh"


@pytest.mark.skipif(not GIT_AVAILABLE, reason="git binary unavailable")
def test_feature_branch_work_state_loads_when_merged(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _init_git_repo(repo)
    _git(repo, "checkout", "-b", "feature/login")
    (repo / "tracked.txt").write_text("base\nfeature\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "feature commit")
    state = start_work_state(repo, "Fix login token refresh")
    saved_head = state["git_context"]["head"]
    _git(repo, "checkout", "main")
    _git(repo, "merge", "--no-ff", "feature/login", "-m", "merge feature")

    checked = load_active_work_state_checked(repo)

    assert checked["active_work_state"]["task_id"] == "fix-login-token-refresh"
    assert checked["work_state_git_status"]["loadable"] is True
    assert checked["work_state_git_status"]["reason"] == "branch_changed_but_merged"
    assert checked["work_state_git_status"]["saved_head"] == saved_head
    assert "reachable from current HEAD" in checked["work_state_git_status"]["warning"]


@pytest.mark.skipif(not GIT_AVAILABLE, reason="git binary unavailable")
def test_dirty_work_state_from_another_branch_is_skipped(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _init_git_repo(repo)
    _git(repo, "checkout", "-b", "feature/login")
    state = start_work_state(repo, "Fix login token refresh")
    (repo / "scratch.txt").write_text("dirty\n", encoding="utf-8")
    update_work_state(repo, {"next_action": "inspect interceptor"})
    _git(repo, "checkout", "main")

    checked = load_active_work_state_checked(repo)

    assert state["git_context"]["dirty"] is False
    assert checked["active_work_state"] == {}
    assert checked["work_state_git_status"]["reason"] == "dirty_branch_mismatch"
    assert checked["skipped_work_state"]["reason"] == "dirty_branch_mismatch"
