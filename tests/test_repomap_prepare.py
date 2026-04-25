from __future__ import annotations

from pathlib import Path

from aictx.middleware import prepare_execution
from aictx.repo_map.config import write_repomap_config
from aictx.scaffold import init_repo_scaffold


def _payload(repo: Path, execution_id: str = "exec-repomap-prepare") -> dict:
    return {
        "repo_root": str(repo),
        "user_request": "inspect repomap prepare integration",
        "agent_id": "codex",
        "adapter_id": "codex",
        "execution_id": execution_id,
        "timestamp": "2026-04-25T00:00:00Z",
    }


def test_prepare_works_without_repomap_enabled_or_provider(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    prepared = prepare_execution(_payload(repo))

    assert prepared["repo_map_status"] == {
        "enabled": False,
        "available": False,
        "used": False,
        "refresh_status": "disabled",
    }


def test_prepare_calls_quick_refresh_not_full(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    write_repomap_config(repo, {"enabled": True, "quick_refresh_budget_ms": 111, "quick_refresh_max_files": 7})
    calls: list[dict] = []

    def fake_refresh(repo_root, **kwargs):
        calls.append(kwargs)
        return {"status": "ok", "mode": "quick", "duration_ms": 12}

    monkeypatch.setattr("aictx.repo_map.refresh.refresh_repo_map", fake_refresh)

    prepared = prepare_execution(
        {
            **_payload(repo, "exec-repomap-quick"),
            "files_opened": ["src/aictx/middleware.py"],
            "files_edited": ["src/aictx/repo_map/refresh.py"],
            "tests_executed": ["tests/test_repomap_prepare.py", "pytest -q"],
        }
    )

    assert calls == [
        {
            "mode": "quick",
            "budget_ms": 111,
            "max_changed_files": 7,
            "changed_file_hints": [
                "src/aictx/middleware.py",
                "src/aictx/repo_map/refresh.py",
                "tests/test_repomap_prepare.py",
            ],
        }
    ]
    assert prepared["repo_map_status"]["used"] is True
    assert prepared["repo_map_status"]["refresh_mode"] == "quick"
    assert prepared["repo_map_status"]["refresh_status"] == "ok"


def test_prepare_quick_refresh_failure_does_not_break_prepare(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    write_repomap_config(repo, {"enabled": True})

    def boom(*_args, **_kwargs):
        raise RuntimeError("refresh failed")

    monkeypatch.setattr("aictx.repo_map.refresh.refresh_repo_map", boom)

    prepared = prepare_execution(_payload(repo, "exec-repomap-failure"))

    assert prepared["repo_map_status"]["enabled"] is True
    assert prepared["repo_map_status"]["available"] is False
    assert prepared["repo_map_status"]["used"] is False
    assert prepared["repo_map_status"]["refresh_status"] == "error"
    assert prepared["repo_map_status"]["error"] == "RuntimeError"


def test_prepare_payload_includes_unavailable_repo_map_status(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    write_repomap_config(repo, {"enabled": True})

    monkeypatch.setattr(
        "aictx.repo_map.refresh.refresh_repo_map",
        lambda *_args, **_kwargs: {"status": "skipped", "mode": "quick", "warnings": ["provider_unavailable"], "duration_ms": 3},
    )

    prepared = prepare_execution(_payload(repo, "exec-repomap-status"))

    assert prepared["repo_map_status"] == {
        "enabled": True,
        "available": False,
        "used": False,
        "refresh_mode": "quick",
        "refresh_status": "skipped",
        "refresh_ms": 3,
    }
