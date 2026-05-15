from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import aictx.cli as cli
from aictx.cleanup import remove_gitattributes_aictx_entries, remove_gitignore_aictx_entries
from aictx.continuity import HANDOFFS_HISTORY_PATH, load_continuity_context
from aictx.area_memory import load_area_memory, update_area_memory
from aictx.portability import PORTABILITY_STATE_PATH, load_portability_state, write_portability_state
from aictx.scaffold import init_repo_scaffold
from aictx.work_state import load_active_task_id, load_active_work_state, start_work_state


PORTABLE_FILES = {
    ".aictx/tasks/threads/task.json": '{"task_id": "task-1"}\n',
    ".aictx/tasks/threads/task.events.jsonl": '{"event": "created"}\n',
    ".aictx/continuity/portability.json": '{"version": 1}\n',
    ".aictx/continuity/handoffs.jsonl": '{"summary": "keep"}\n',
    ".aictx/continuity/decisions.jsonl": '{"decision": "keep"}\n',
    ".aictx/continuity/semantic_repo/runtime.json": '{"name": "runtime"}\n',
    ".aictx/failure_memory/failure_patterns.jsonl": '{"failure": "keep"}\n',
    ".aictx/strategy_memory/strategies.jsonl": '{"strategy": "keep"}\n',
    ".aictx/area_memory/areas/src-aictx.json": '{"area_id": "src/aictx"}\n',
    ".aictx/repo_map/config.json": '{"enabled": true}\n',
}

LOCAL_ONLY_FILES = {
    ".aictx/tasks/active.json": '{"active_task_id": "task-1"}\n',
    ".aictx/boot/boot_summary.json": '{"boot": true}\n',
    ".aictx/metrics/execution_logs.jsonl": '{"log": true}\n',
    ".aictx/failure_memory/failure_index.json": '{"index": true}\n',
    ".aictx/failure_memory/failure_memory_status.json": '{"status": true}\n',
    ".aictx/task_memory/task_memory_status.json": '{"status": true}\n',
    ".aictx/memory_graph/graph_status.json": '{"status": true}\n',
    ".aictx/continuity/handoff.json": '{"summary": "keep"}\n',
    ".aictx/continuity/semantic_repo.json": '{"repo": "keep"}\n',
    ".aictx/continuity/session.json": '{"session": 1}\n',
    ".aictx/continuity/last_execution_summary.md": '# summary\n',
    ".aictx/continuity/continuity_metrics.json": '{"metrics": true}\n',
    ".aictx/continuity/resume_capsule.md": '# generated\n',
    ".aictx/continuity/resume_capsule.json": '{"generated": true}\n',
    ".aictx/area_memory/areas.json": '{"areas": []}\n',
    ".aictx/repo_map/index.json": '{"index": true}\n',
    ".aictx/repo_map/manifest.json": '{"manifest": true}\n',
    ".aictx/repo_map/status.json": '{"status": true}\n',
}


def init_git_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo, text=True, capture_output=True, check=True)


def git(repo: Path, *args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=True)
    return completed.stdout.strip()


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


def run_cli(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    return subprocess.run(
        [sys.executable, "-m", "aictx", *args, "--repo", str(repo), "--json"],
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
    attributes = (repo / ".gitattributes").read_text(encoding="utf-8")
    assert "# AICTX:START gitattributes" in attributes
    assert ".aictx/continuity/decisions.jsonl merge=union" in attributes


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
    state = load_portability_state(repo)
    assert state["enabled"] is True
    assert state["policy_version"] == 2
    assert state["profile"] == "team-safe"
    assert state["merge_policy"]["external_tool_required"] is False
    assert state["merge_policy"]["jsonl_merge_driver"] == "union"
    assert ".aictx/failure_memory/failure_index.json" not in state["portable_patterns"]
    assert ".aictx/failure_memory/failure_index.json" in state["local_only_patterns"]
    assert (repo / ".gitattributes").exists()
    write_files(repo, {k: v for k, v in (PORTABLE_FILES | LOCAL_ONLY_FILES).items() if k != ".aictx/continuity/portability.json"})
    assert is_ignored(repo, ".aictx/tasks/active.json") is True
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
        ".aictx/tasks/threads/existing.json": '{"task_id": "existing"}\n',
        ".aictx/failure_memory/failure_patterns.jsonl": '{"failure": "existing"}\n',
        ".aictx/strategy_memory/strategies.jsonl": '{"strategy": "existing"}\n',
        ".aictx/repo_map/config.json": '{"enabled": true}\n',
    }
    write_files(repo, existing_files)

    init_repo_scaffold(repo, update_gitignore=False, portable_continuity=True)

    for rel_path, expected in existing_files.items():
        assert (repo / rel_path).read_text(encoding="utf-8") == expected




def test_init_replaces_unmanaged_aictx_gitignore_line_with_managed_block(tmp_path: Path):
    repo = tmp_path / "repo"
    init_git_repo(repo)
    (repo / ".gitignore").write_text("*.pyc\n.aictx/\n.env\n", encoding="utf-8")

    init_repo_scaffold(repo, portable_continuity=True)

    text = (repo / ".gitignore").read_text(encoding="utf-8")
    before_block = text.split("# AICTX:START gitignore", 1)[0]
    assert ".aictx/" not in before_block.splitlines()
    assert "# AICTX:START gitignore" in text
    assert "# mode: portable-continuity" in text
    assert is_ignored(repo, ".aictx/failure_memory/failure_patterns.jsonl") is False
    assert is_ignored(repo, ".aictx/failure_memory/failure_index.json") is True

def test_cleanup_removes_managed_block_and_unmanaged_aictx_line(tmp_path: Path):
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


def test_cleanup_removes_managed_gitattributes_block(tmp_path: Path):
    path = tmp_path / ".gitattributes"
    path.write_text(
        "*.md text\n"
        "# AICTX:START gitattributes\n"
        "# profile: team-safe\n"
        ".aictx/continuity/decisions.jsonl merge=union\n"
        "# AICTX:END gitattributes\n"
        "*.png binary\n",
        encoding="utf-8",
    )

    assert remove_gitattributes_aictx_entries(path) is True
    assert path.read_text(encoding="utf-8") == "*.md text\n*.png binary\n"


def test_init_replaces_managed_gitattributes_block_and_preserves_user_rules(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitattributes").write_text(
        "*.md text\n"
        "# AICTX:START gitattributes\n"
        "old merge=ours\n"
        "# AICTX:END gitattributes\n",
        encoding="utf-8",
    )

    init_repo_scaffold(repo, portable_continuity=True)

    text = (repo / ".gitattributes").read_text(encoding="utf-8")
    assert "*.md text" in text
    assert "old merge=ours" not in text
    assert text.count("# AICTX:START gitattributes") == 1
    assert ".aictx/continuity/decisions.jsonl merge=union" in text


def test_init_can_toggle_portable_continuity_from_local_only_to_enabled(tmp_path: Path):
    repo = tmp_path / "repo"
    init_git_repo(repo)
    init_repo_scaffold(repo, portable_continuity=False)
    existing_files = {
        ".aictx/tasks/threads/existing.json": '{"task_id": "existing"}\n',
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
    assert "# AICTX:START gitattributes" in (repo / ".gitattributes").read_text(encoding="utf-8")
    assert is_ignored(repo, ".aictx/tasks/active.json") is True
    assert is_ignored(repo, ".aictx/continuity/handoff.json") is True
    assert is_ignored(repo, ".aictx/metrics/execution_logs.jsonl") is True


def test_init_can_toggle_portable_continuity_from_enabled_to_local_only(tmp_path: Path):
    repo = tmp_path / "repo"
    init_git_repo(repo)
    init_repo_scaffold(repo, portable_continuity=True)
    existing_files = {
        ".aictx/tasks/threads/existing.json": '{"task_id": "existing"}\n',
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
    assert not (repo / ".gitattributes").exists()
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
    assert payload["policy_version"] == 2
    assert payload["profile"] == "team-safe"
    assert payload["merge_policy"]["managed_gitattributes"] == ".gitattributes"


def test_init_migrates_policy_v1_state_to_team_safe_v2(tmp_path: Path):
    repo = tmp_path / "repo"
    init_git_repo(repo)
    path = repo / PORTABILITY_STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"version": 1, "enabled": True, "mode": "portable-continuity", "policy_version": 1}) + "\n",
        encoding="utf-8",
    )

    init_repo_scaffold(repo, portable_continuity=None)

    payload = load_portability_state(repo)
    assert payload["enabled"] is True
    assert payload["policy_version"] == 2
    assert payload["profile"] == "team-safe"
    assert ".aictx/strategy_memory/strategies.jsonl" in payload["merge_policy"]["portable_jsonl_patterns"]
    assert ".aictx/strategy_memory/strategies.jsonl merge=union" in (repo / ".gitattributes").read_text(encoding="utf-8")


def test_git_union_merge_allows_parallel_decision_appends(tmp_path: Path):
    repo = tmp_path / "repo"
    init_git_repo(repo)
    subprocess.run(["git", "config", "user.email", "aictx@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "AICTX Test"], cwd=repo, check=True)
    init_repo_scaffold(repo, portable_continuity=True)
    decisions = repo / ".aictx" / "continuity" / "decisions.jsonl"
    decisions.write_text('{"decision": "base"}\n', encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore", ".gitattributes", ".aictx/continuity"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=repo, text=True, capture_output=True, check=True)
    base_branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()

    subprocess.run(["git", "checkout", "-b", "left"], cwd=repo, text=True, capture_output=True, check=True)
    with decisions.open("a", encoding="utf-8") as handle:
        handle.write('{"decision": "left"}\n')
    subprocess.run(["git", "commit", "-am", "left"], cwd=repo, text=True, capture_output=True, check=True)

    subprocess.run(["git", "checkout", base_branch], cwd=repo, text=True, capture_output=True, check=True)
    subprocess.run(["git", "checkout", "-b", "right"], cwd=repo, text=True, capture_output=True, check=True)
    with decisions.open("a", encoding="utf-8") as handle:
        handle.write('{"decision": "right"}\n')
    subprocess.run(["git", "commit", "-am", "right"], cwd=repo, text=True, capture_output=True, check=True)

    merged = subprocess.run(["git", "merge", "left"], cwd=repo, text=True, capture_output=True, check=False)

    assert merged.returncode == 0, merged.stderr
    text = decisions.read_text(encoding="utf-8")
    assert '{"decision": "left"}' in text
    assert '{"decision": "right"}' in text


def test_portable_policy_derives_snapshots_from_shards_and_history(tmp_path: Path):
    repo = tmp_path / "repo"
    init_git_repo(repo)
    init_repo_scaffold(repo, portable_continuity=True)
    write_files(
        repo,
        {
            ".aictx/tasks/threads/task-1.json": '{"task_id": "task-1", "goal": "portable", "status": "in_progress"}\n',
            ".aictx/continuity/handoffs.jsonl": '{"execution_id": "exec-1", "timestamp": "2026-05-15T00:00:00Z", "summary": "latest portable handoff", "status": "resolved"}\n',
            ".aictx/continuity/semantic_repo/runtime.json": '{"name": "runtime", "description": "portable shard", "key_paths": ["src/aictx/runtime.py"]}\n',
            ".aictx/area_memory/areas/src-aictx.json": '{"area_id": "src/aictx", "executions": 3, "related_files": ["src/aictx/portability.py"], "related_tests": ["tests/test_portability.py"]}\n',
        },
    )

    assert is_ignored(repo, ".aictx/tasks/active.json") is True
    assert is_ignored(repo, ".aictx/continuity/handoff.json") is True
    assert is_ignored(repo, ".aictx/continuity/semantic_repo.json") is True
    assert is_ignored(repo, ".aictx/area_memory/areas.json") is True
    assert is_ignored(repo, ".aictx/continuity/semantic_repo/runtime.json") is False
    assert is_ignored(repo, ".aictx/area_memory/areas/src-aictx.json") is False
    assert load_active_task_id(repo) == "task-1"
    assert load_active_work_state(repo)["goal"] == "portable"
    context = load_continuity_context(repo, request_text="runtime")
    assert context["handoff"]["summary"] == "latest portable handoff"
    assert context["semantic_repo"]["subsystems"][0]["name"] == "runtime"
    assert load_area_memory(repo)["areas"]["src/aictx"]["executions"] == 3


def test_portable_work_state_thread_respects_branch_safety_when_active_snapshot_missing(tmp_path: Path):
    repo = tmp_path / "repo"
    init_git_repo(repo)
    git(repo, "config", "user.name", "Test User")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "checkout", "-b", "main")
    (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "-m", "initial")
    init_repo_scaffold(repo, portable_continuity=True)

    git(repo, "checkout", "-b", "feature/portable")
    (repo / "tracked.txt").write_text("base\nfeature-only\n", encoding="utf-8")
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "-m", "feature commit")
    state = start_work_state(repo, "Portable continuation")

    git(repo, "checkout", "main")
    (repo / "tracked.txt").write_text("base\nmain-only\n", encoding="utf-8")
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "-m", "main commit")
    (repo / ".aictx" / "tasks" / "active.json").unlink()

    context = load_continuity_context(repo, request_text="continue portable work")

    assert state["task_id"] == "portable-continuation"
    assert context["active_work_state"] == {}
    assert context["loaded"].get("work_state") is not True
    assert context["skipped_work_state"]["reason"] in {"branch_mismatch_unmerged", "dirty_branch_mismatch"}
    assert context["skipped_work_state"]["task_id"] == "portable-continuation"
    assert context["work_state_git_status"]["reason"] in {"branch_mismatch_unmerged", "dirty_branch_mismatch"}


def test_portable_work_state_thread_loads_when_git_context_is_safe(tmp_path: Path):
    repo = tmp_path / "repo"
    init_git_repo(repo)
    git(repo, "config", "user.name", "Test User")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "checkout", "-b", "main")
    (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "-m", "initial")
    init_repo_scaffold(repo, portable_continuity=True)

    state = start_work_state(repo, "Portable continuation")
    (repo / ".aictx" / "tasks" / "active.json").unlink()

    context = load_continuity_context(repo, request_text="continue portable work")

    assert context["active_work_state"]["task_id"] == state["task_id"]
    assert context["loaded"]["work_state"] is True
    assert context["skipped_work_state"] == {}
    assert context["work_state_git_status"]["reason"] == "same_branch"


def test_enabling_portability_migrates_existing_snapshots_to_portable_sources(tmp_path: Path):
    repo = tmp_path / "repo"
    init_git_repo(repo)
    write_files(
        repo,
        {
            ".aictx/continuity/handoff.json": '{"summary": "snapshot handoff", "updated_at": "2026-05-15T00:00:00Z"}\n',
            ".aictx/continuity/semantic_repo.json": '{"subsystems": [{"name": "runtime", "key_paths": ["src/aictx/runtime.py"]}]}\n',
            ".aictx/area_memory/areas.json": '{"version": 1, "areas": {"src/aictx": {"area_id": "src/aictx", "executions": 2}}}\n',
        },
    )

    init_repo_scaffold(repo, portable_continuity=True)

    assert (repo / HANDOFFS_HISTORY_PATH).read_text(encoding="utf-8")
    assert (repo / ".aictx" / "continuity" / "semantic_repo" / "runtime.json").exists()
    assert (repo / ".aictx" / "area_memory" / "areas" / "src-aictx.json").exists()
    context = load_continuity_context(repo, request_text="runtime")
    assert context["handoff"]["summary"] == "snapshot handoff"
    assert context["semantic_repo"]["subsystems"][0]["name"] == "runtime"


def test_area_memory_writes_portable_shard(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, portable_continuity=True)

    update_area_memory(repo, {"area_id": "src/aictx", "files_opened": ["src/aictx/portability.py"], "tests_executed": ["tests/test_portability.py"]})

    assert (repo / ".aictx" / "area_memory" / "areas" / "src-aictx.json").exists()


def test_portability_status_and_compact_cli(tmp_path: Path):
    repo = tmp_path / "repo"
    init_git_repo(repo)
    init_repo_scaffold(repo, portable_continuity=True)
    decisions = repo / ".aictx" / "continuity" / "decisions.jsonl"
    decisions.write_text('{"decision": "same"}\n{"decision": "same"}\n', encoding="utf-8")

    status_proc = run_cli(repo, "portability", "status")
    assert status_proc.returncode == 0, status_proc.stderr
    status = json.loads(status_proc.stdout)
    assert status["enabled"] is True
    assert status["policy_version"] == 2
    assert status["jsonl_compaction"]["changed"] is True

    compact_proc = run_cli(repo, "portability", "compact", "--apply")
    assert compact_proc.returncode == 0, compact_proc.stderr
    compact = json.loads(compact_proc.stdout)
    assert compact["duplicates_removed"] == 1
    assert decisions.read_text(encoding="utf-8") == '{"decision": "same"}\n'
