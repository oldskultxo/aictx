from __future__ import annotations

from pathlib import Path

from aictx.continuity import SEMANTIC_REPO_PATH
from aictx.middleware import finalize_execution, prepare_execution
from aictx.scaffold import init_repo_scaffold
from aictx.state import read_json, write_json


def _payload(repo: Path, execution_id: str) -> dict:
    return {
        "repo_root": str(repo),
        "user_request": "record semantic repo memory",
        "agent_id": "codex",
        "adapter_id": "codex",
        "execution_id": execution_id,
        "timestamp": "2026-04-24T15:00:00Z",
        "files_opened": ["src/aictx/middleware.py", "src/aictx/state.py"],
        "tests_executed": ["tests/test_continuity_context.py"],
    }


def test_finalize_creates_semantic_repo_memory(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    prepared = prepare_execution(_payload(repo, "exec-semantic-create"))

    finalized = finalize_execution(
        prepared,
        {
            "success": True,
            "result_summary": "Recorded semantic repo memory.",
            "validated_learning": False,
            "semantic_repo": [
                {
                    "name": "runtime_startup",
                    "description": "Startup/session initialization and continuity context assembly.",
                    "key_paths": ["src/aictx/middleware.py"],
                    "entry_points": ["prepare_execution"],
                    "relevant_tests": ["tests/test_continuity_context.py"],
                    "fragile_areas": ["startup output coupling"],
                }
            ],
        },
    )

    path = repo / SEMANTIC_REPO_PATH
    assert path.exists()
    payload = read_json(path, {})
    assert finalized["semantic_repo_persisted"]["path"] == path.as_posix()
    assert payload["repo_id"] == repo.name
    assert payload["updated_at"] == finalized["finalized_at"]
    assert payload["source_session"] == 1
    subsystem = payload["subsystems"][0]
    assert subsystem["name"] == "runtime_startup"
    assert subsystem["description"] == "Startup/session initialization and continuity context assembly."
    assert subsystem["key_paths"] == ["src/aictx/middleware.py", "src/aictx/state.py"]
    assert subsystem["entry_points"] == ["prepare_execution"]
    assert subsystem["relevant_tests"] == ["tests/test_continuity_context.py"]
    assert subsystem["fragile_areas"] == ["startup output coupling"]


def test_finalize_updates_subsystem_without_duplicate_paths(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    write_json(
        repo / SEMANTIC_REPO_PATH,
        {
            "repo_id": "repo",
            "subsystems": [
                {
                    "name": "runtime_startup",
                    "description": "old description",
                    "key_paths": ["src/aictx/middleware.py"],
                    "entry_points": ["prepare_execution"],
                    "relevant_tests": ["tests/test_continuity_context.py"],
                    "fragile_areas": [],
                }
            ],
            "updated_at": "2026-04-24T14:00:00Z",
            "source_session": 1,
        },
    )
    prepared = prepare_execution({**_payload(repo, "exec-semantic-update"), "files_opened": ["src/aictx/middleware.py", "src/aictx/continuity.py", "src/aictx/state.py"]})

    finalize_execution(
        prepared,
        {
            "success": True,
            "result_summary": "Updated semantic repo memory.",
            "validated_learning": False,
            "semantic_repo": [
                {
                    "name": "runtime_startup",
                    "description": "Startup/session initialization and continuity context assembly.",
                    "key_paths": ["src/aictx/middleware.py", "src/aictx/continuity.py"],
                    "entry_points": ["prepare_execution"],
                    "relevant_tests": ["tests/test_continuity_context.py"],
                    "fragile_areas": ["startup output coupling"],
                }
            ],
        },
    )

    subsystem = read_json(repo / SEMANTIC_REPO_PATH, {})["subsystems"][0]
    assert subsystem["description"] == "Startup/session initialization and continuity context assembly."
    assert subsystem["key_paths"] == ["src/aictx/middleware.py", "src/aictx/continuity.py", "src/aictx/state.py"]
    assert subsystem["entry_points"] == ["prepare_execution"]
    assert subsystem["relevant_tests"] == ["tests/test_continuity_context.py"]
    assert subsystem["fragile_areas"] == ["startup output coupling"]


def test_finalize_preserves_other_subsystems_and_skips_empty_updates(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    write_json(
        repo / SEMANTIC_REPO_PATH,
        {
            "repo_id": "repo",
            "subsystems": [
                {
                    "name": "cli",
                    "description": "Command line interface.",
                    "key_paths": ["src/aictx/cli.py"],
                    "entry_points": ["build_parser"],
                    "relevant_tests": ["tests/test_smoke.py"],
                    "fragile_areas": [],
                }
            ],
            "updated_at": "2026-04-24T14:00:00Z",
            "source_session": 1,
        },
    )
    prepared = prepare_execution(_payload(repo, "exec-semantic-preserve"))

    finalized = finalize_execution(
        prepared,
        {
            "success": True,
            "result_summary": "No semantic update.",
            "validated_learning": False,
            "semantic_repo": [{"description": "missing name"}],
        },
    )

    payload = read_json(repo / SEMANTIC_REPO_PATH, {})
    assert finalized["semantic_repo_persisted"] is None
    assert payload["subsystems"][0]["name"] == "cli"
    assert payload["subsystems"][0]["key_paths"] == ["src/aictx/cli.py"]
