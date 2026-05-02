from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import aictx.cli as cli
from aictx.cleanup import remove_gitignore_aictx_entries
from aictx.portability import PORTABILITY_STATE_PATH, load_portability_state, write_portability_state
from aictx.scaffold import init_repo_scaffold


PORTABLE_FILES = {
    ".aictx/tasks/active.json": '{"active_task_id": "task-1"}\n',
    ".aictx/tasks/threads/task.json": '{"task_id": "task-1"}\n',
    ".aictx/tasks/threads/task.events.jsonl": '{"event": "created"}\n',
    ".aictx/continuity/portability.json": '{"version": 1}\n',
    ".aictx/continuity/handoff.json": '{"summary": "keep"}\n',
    ".aictx/continuity/handoffs.jsonl": '{"summary": "keep"}\n',
    ".aictx/continuity/decisions.jsonl": '{"decision": "keep"}\n',
    ".aictx/continuity/semantic_repo.json": '{"repo": "keep"}\n',
    ".aictx/failure_memory/failure_patterns.jsonl": '{"failure": "keep"}\n',
    ".aictx/strategy_memory/strategies.jsonl": '{"strategy": "keep"}\n',
    ".aictx/area_memory/areas.json": '{"areas": []}\n',
    ".aictx/repo_map/config.json": '{"enabled": true}\n',
}

LOCAL_ONLY_FILES = {
    ".aictx/metrics/execution_logs.jsonl": '{"log": true}\n',
    ".aictx/continuity/session.json": '{"session": 1}\n',
    ".aictx/continuity/last_execution_summary.md": '# summary\n',
    ".aictx/continuity/continuity_metrics.json": '{"metrics": true}\n',
    ".aictx/continuity/resume_capsule.md": '# generated\n',
    ".aictx/continuity/resume_capsule.json": '{"generated": true}\n',
    ".aictx/repo_map/index.json": '{"index": true}\n',
    ".aictx/repo_map/manifest.json": '{"manifest": true}\n',
    ".aictx/repo_map/status.json": '{"status": true}\n',
}


def init_git_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo, text=True, capture_output=True, check=True)


def write_files(repo: Path, files: dict[str, str]) -> None:
    for rel_path, content in files.items():
        path = repo / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def is_ignored(repo: Path, rel_path: str) -> bool:
    completed = subprocess.run(
        ["git", "check-ignore", rel_path],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    raise AssertionError(completed.stderr)


def run_init_cli(repo: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    return subprocess.run(
        [sys.executable, "-m", "aictx", "init", "--repo", str(repo), "--yes", "--no-register", *extra_args],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def test_default_scaffold_keeps_local_only(tmp_path: Path):
    repo = tmp_path / "repo"
    init_git_repo(repo)

    init_repo_scaffold(repo, portable_continuity=False)

    text = (repo / ".gitignore").read_text(encoding="utf-8")
    assert "# AICTX:START gitignore" in text
    assert "# mode: local-only" in text
    assert ".aictx/" in text
    assert is_ignored(repo, ".aictx/tasks/active.json") is True
    assert load_portability_state(repo)["enabled"] is False


def test_portable_policy_makes_only_portable_subset_versionable(tmp_path: Path):
    repo = tmp_path / "repo"
    init_git_repo(repo)

    init_repo_scaffold(repo, portable_continuity=True)
    write_files(repo, PORTABLE_FILES | LOCAL_ONLY_FILES)

    for rel_path in PORTABLE_FILES:
        assert is_ignored(repo, rel_path) is False, rel_path
    for rel_path in LOCAL_ONLY_FILES:
        assert is_ignored(repo, rel_path) is True, rel_path


def test_init_yes_does_not_enable_portability_by_default(tmp_path: Path):
    repo = tmp_path / "repo"
    init_git_repo(repo)

    completed = run_init_cli(repo)

    assert completed.returncode == 0, completed.stderr
    text = (repo / ".gitignore").read_text(encoding="utf-8")
    assert "# mode: local-only" in text
    assert load_portability_state(repo)["enabled"] is False


def test_explicit_flag_enables_portability(tmp_path: Path):
    repo = tmp_path / "repo"
    init_git_repo(repo)

    completed = run_init_cli(repo, "--portable-continuity")

    assert completed.returncode == 0, completed.stderr
    text = (repo / ".gitignore").read_text(encoding="utf-8")
    assert "# mode: portable-continuity" in text
    assert load_portability_state(repo)["enabled"] is True
    write_files(repo, {k: v for k, v in (PORTABLE_FILES | LOCAL_ONLY_FILES).items() if k != ".aictx/continuity/portability.json"})
    assert is_ignored(repo, ".aictx/tasks/active.json") is False
    assert is_ignored(repo, ".aictx/metrics/execution_logs.jsonl") is True


def test_init_portable_continuity_requires_gitignore_updates(tmp_path: Path):
    repo = tmp_path / "repo"
    init_git_repo(repo)

    completed = run_init_cli(repo, "--no-gitignore", "--portable-continuity")

    assert completed.returncode == 2
    assert "--portable-continuity requires updating .gitignore" in completed.stderr
    assert not (repo / ".gitignore").exists()
    assert not (repo / ".aictx" / "continuity" / "portability.json").exists()


def test_init_no_gitignore_with_no_portable_continuity_is_allowed(tmp_path: Path):
    repo = tmp_path / "repo"
    init_git_repo(repo)

    completed = run_init_cli(repo, "--no-gitignore", "--no-portable-continuity")

    assert completed.returncode == 0, completed.stderr
    assert load_portability_state(repo)["enabled"] is False
    assert not (repo / ".gitignore").exists()


def test_init_no_gitignore_does_not_enable_portability_by_default(tmp_path: Path):
    repo = tmp_path / "repo"
    init_git_repo(repo)

    completed = run_init_cli(repo, "--no-gitignore")

    assert completed.returncode == 0, completed.stderr
    assert load_portability_state(repo)["enabled"] is False
    assert not (repo / ".gitignore").exists()


def test_explicit_no_flag_disables_portability(tmp_path: Path):
    repo = tmp_path / "repo"
    init_git_repo(repo)

    completed = run_init_cli(repo, "--no-portable-continuity")

    assert completed.returncode == 0, completed.stderr
    text = (repo / ".gitignore").read_text(encoding="utf-8")
    assert "# mode: local-only" in text
    assert load_portability_state(repo)["enabled"] is False


def test_init_preserves_existing_portable_artifacts(tmp_path: Path):
    repo = tmp_path / "repo"
    existing_files = {
        ".aictx/tasks/active.json": '{"active_task_id": "existing"}\n',
        ".aictx/tasks/threads/existing.json": '{"task_id": "existing"}\n',
        ".aictx/continuity/handoff.json": '{"summary": "existing"}\n',
        ".aictx/failure_memory/failure_patterns.jsonl": '{"failure": "existing"}\n',
        ".aictx/strategy_memory/strategies.jsonl": '{"strategy": "existing"}\n',
        ".aictx/repo_map/config.json": '{"enabled": true}\n',
    }
    write_files(repo, existing_files)

    init_repo_scaffold(repo, update_gitignore=False, portable_continuity=True)

    for rel_path, expected in existing_files.items():
        assert (repo / rel_path).read_text(encoding="utf-8") == expected


def test_cleanup_removes_managed_block_and_legacy_line(tmp_path: Path):
    path = tmp_path / ".gitignore"
    path.write_text(
        "*.pyc\n"
        ".aictx/\n"
        "# AICTX:START gitignore\n"
        "# mode: portable-continuity\n\n"
        ".aictx/*\n"
        "!.aictx/\n\n"
        "# AICTX:END gitignore\n"
        ".env\n",
        encoding="utf-8",
    )

    assert remove_gitignore_aictx_entries(path) is True
    assert path.read_text(encoding="utf-8") == "*.pyc\n.env\n"


def test_init_can_toggle_portable_continuity_from_local_only_to_enabled(tmp_path: Path):
    repo = tmp_path / "repo"
    init_git_repo(repo)
    init_repo_scaffold(repo, portable_continuity=False)
    existing_files = {
        ".aictx/tasks/active.json": '{"active_task_id": "existing"}\n',
        ".aictx/tasks/threads/existing.json": '{"task_id": "existing"}\n',
        ".aictx/continuity/handoff.json": '{"summary": "existing"}\n',
        ".aictx/continuity/decisions.jsonl": '{"decision": "existing"}\n',
        ".aictx/failure_memory/failure_patterns.jsonl": '{"failure": "existing"}\n',
        ".aictx/strategy_memory/strategies.jsonl": '{"strategy": "existing"}\n',
        ".aictx/repo_map/config.json": '{"enabled": true}\n',
        ".aictx/metrics/execution_logs.jsonl": '{"log": true}\n',
    }
    write_files(repo, existing_files)

    originals = {rel_path: (repo / rel_path).read_text(encoding="utf-8") for rel_path in existing_files}
    init_repo_scaffold(repo, portable_continuity=True)

    for rel_path, expected in originals.items():
        assert (repo / rel_path).read_text(encoding="utf-8") == expected
    assert "# mode: portable-continuity" in (repo / ".gitignore").read_text(encoding="utf-8")
    assert load_portability_state(repo)["enabled"] is True
    assert is_ignored(repo, ".aictx/tasks/active.json") is False
    assert is_ignored(repo, ".aictx/continuity/handoff.json") is False
    assert is_ignored(repo, ".aictx/metrics/execution_logs.jsonl") is True


def test_init_can_toggle_portable_continuity_from_enabled_to_local_only(tmp_path: Path):
    repo = tmp_path / "repo"
    init_git_repo(repo)
    init_repo_scaffold(repo, portable_continuity=True)
    existing_files = {
        ".aictx/tasks/active.json": '{"active_task_id": "existing"}\n',
        ".aictx/tasks/threads/existing.json": '{"task_id": "existing"}\n',
        ".aictx/continuity/handoff.json": '{"summary": "existing"}\n',
        ".aictx/failure_memory/failure_patterns.jsonl": '{"failure": "existing"}\n',
        ".aictx/strategy_memory/strategies.jsonl": '{"strategy": "existing"}\n',
        ".aictx/repo_map/config.json": '{"enabled": true}\n',
        ".aictx/metrics/execution_logs.jsonl": '{"log": true}\n',
    }
    write_files(repo, existing_files)

    originals = {rel_path: (repo / rel_path).read_text(encoding="utf-8") for rel_path in existing_files}
    init_repo_scaffold(repo, portable_continuity=False)

    for rel_path, expected in originals.items():
        assert (repo / rel_path).read_text(encoding="utf-8") == expected
    assert "# mode: local-only" in (repo / ".gitignore").read_text(encoding="utf-8")
    assert load_portability_state(repo)["enabled"] is False
    assert is_ignored(repo, ".aictx/tasks/active.json") is True
    assert is_ignored(repo, ".aictx/metrics/execution_logs.jsonl") is True


def test_interactive_resolution_asks_and_preserves_existing_enabled_default(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    write_portability_state(repo, enabled=True)

    prompts: list[str] = []

    class _Tty:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(cli.sys, "stdin", _Tty())
    monkeypatch.setattr("builtins.input", lambda prompt='': prompts.append(prompt) or "")

    args = argparse.Namespace(yes=False, portable_continuity=False, no_portable_continuity=False)
    assert cli.resolve_init_portable_continuity(args, repo) is True
    assert prompts
    assert "Enable AICTX git-portable continuity?" in prompts[0]
    assert "[Y/n]" in prompts[0]


def test_portability_state_written_to_canonical_path(tmp_path: Path):
    repo = tmp_path / "repo"
    path = write_portability_state(repo, enabled=True)
    assert path == repo / PORTABILITY_STATE_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["enabled"] is True
    assert payload["mode"] == "portable-continuity"
