from __future__ import annotations

from pathlib import Path

from aictx.middleware import finalize_execution, prepare_execution
from aictx.scaffold import init_repo_scaffold
from aictx.state import REPO_CONTINUITY_SESSION_PATH, read_json


def _payload(repo: Path, execution_id: str) -> dict:
    return {
        "repo_root": str(repo),
        "user_request": "inspect startup continuity",
        "agent_id": "codex",
        "adapter_id": "codex",
        "execution_id": execution_id,
        "timestamp": "2026-04-24T10:12:00Z",
    }


def test_prepare_execution_keeps_session_identity_stable_across_executions(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    first = prepare_execution(_payload(repo, "exec-1"))
    session_path = repo / REPO_CONTINUITY_SESSION_PATH
    assert session_path.exists()
    assert first["continuity_context"]["warnings"] == []
    assert first["continuity_context"]["session"]["session_count"] == 1
    assert first["continuity_context"]["session"]["execution_count"] == 1
    assert first["continuity_context"]["session"]["runtime"] == "codex"
    assert first["continuity_context"]["session"]["agent_label"] == f"codex@{repo.name}"
    assert first["startup_banner_text"] == (
        f"codex@{repo.name} (session #1) - despierto\n\n"
        "En la sesión anterior no había handoff previo que retomar."
    )
    assert first["startup_banner_policy"]["required"] is True
    assert first["startup_banner_policy"]["show_once_per_session"] is True

    repeated_before_finalize = prepare_execution(_payload(repo, "exec-1b"))
    assert repeated_before_finalize["startup_banner_text"] == first["startup_banner_text"]
    assert read_json(session_path, {}).get("banner_shown_session_id") == ""

    finalize_execution(first, {"success": True, "result_summary": "ok"})

    second = prepare_execution(_payload(repo, "exec-2"))
    assert second["continuity_context"]["session"]["session_count"] == 1
    assert second["continuity_context"]["session"]["execution_count"] == 3
    assert second["continuity_context"]["session"]["agent_label"] == first["continuity_context"]["session"]["agent_label"]
    assert second["agent_label"] == f"codex@{repo.name}"
    assert second["session_count"] == 1
    assert second["startup_banner_text"] == ""
    assert second["startup_banner_policy"]["show_in_first_user_visible_response"] is False
    assert second["startup_banner_policy"]["show_once_per_session"] is True
    assert second["startup_banner_policy"]["required"] is False
    assert second["startup_banner_policy"]["already_shown"] is True

    on_disk = read_json(session_path, {})
    assert on_disk["session_count"] == 1
    assert on_disk["execution_count"] == 3
    assert on_disk["repo_id"] == repo.name
    assert on_disk["runtime"] == "codex"
    assert on_disk["banner_shown_session_id"] == on_disk["session_id"]


def test_prepare_execution_uses_codex_thread_id_for_visible_session(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-123")

    prepared = prepare_execution(_payload(repo, "exec-thread"))

    assert prepared["startup_banner_policy"]["session_id"] == "thread-123"
    assert prepared["continuity_context"]["session"]["session_id"] == "thread-123"


def test_prepare_execution_uses_claude_session_id_for_claude_runtime(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    monkeypatch.setenv("CODEX_THREAD_ID", "codex-thread")
    monkeypatch.setenv("CLAUDE_SESSION_ID", "claude-session")

    prepared = prepare_execution(
        {
            **_payload(repo, "exec-claude"),
            "agent_id": "claude",
            "adapter_id": "claude",
        }
    )

    assert prepared["startup_banner_policy"]["session_id"] == "claude-session"
    assert prepared["continuity_context"]["session"]["session_id"] == "claude-session"


def test_prepare_execution_does_not_use_codex_thread_id_for_claude_runtime(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    monkeypatch.setenv("CODEX_THREAD_ID", "codex-thread")
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.delenv("CLAUDE_CONVERSATION_ID", raising=False)
    monkeypatch.delenv("CLAUDE_THREAD_ID", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.delenv("AICTX_SESSION_ID", raising=False)

    prepared = prepare_execution(
        {
            **_payload(repo, "exec-claude-fallback"),
            "agent_id": "claude",
            "adapter_id": "claude",
        }
    )

    session_id = prepared["startup_banner_policy"]["session_id"]
    assert session_id != "codex-thread"
    assert session_id.startswith("claude:process:")


def test_prepare_execution_increments_visible_session_when_session_id_changes(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    first = prepare_execution({**_payload(repo, "exec-1"), "session_id": "visible-1"})
    second = prepare_execution({**_payload(repo, "exec-2"), "session_id": "visible-2"})

    assert first["continuity_context"]["session"]["session_count"] == 1
    assert second["continuity_context"]["session"]["session_count"] == 2
    assert second["continuity_context"]["session"]["execution_count"] == 1
    assert second["startup_banner_text"] == (
        f"codex@{repo.name} (session #2) - despierto\n\n"
        "En la sesión anterior no había handoff previo que retomar."
    )


def test_prepare_execution_recovers_from_malformed_session_file(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    session_path = repo / REPO_CONTINUITY_SESSION_PATH
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text('{broken', encoding="utf-8")

    prepared = prepare_execution(_payload(repo, "exec-broken"))

    assert "continuity_session_malformed" in prepared["continuity_context"]["warnings"]
    assert prepared["continuity_context"]["session"]["session_count"] == 1
    assert read_json(session_path, {})["session_count"] == 1


def test_session_runtime_falls_back_to_agent_id_when_adapter_missing(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "inspect startup continuity",
            "agent_id": "Codex Runner",
            "execution_id": "exec-agent-fallback",
            "timestamp": "2026-04-24T10:12:00Z",
        }
    )

    session = prepared["continuity_context"]["session"]
    assert session["runtime"] == "codex-runner"
    assert session["agent_label"] == f"codex-runner@{repo.name}"
