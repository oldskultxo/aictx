from __future__ import annotations

from pathlib import Path

from aictx.continuity import SEMANTIC_REPO_PATH, load_continuity_context
from aictx.middleware import prepare_execution
from aictx.scaffold import init_repo_scaffold
from aictx.state import write_json


def _payload(repo: Path, execution_id: str = "exec-semantic-load") -> dict:
    return {
        "repo_root": str(repo),
        "user_request": "inspect runtime startup continuity",
        "agent_id": "codex",
        "adapter_id": "codex",
        "execution_id": execution_id,
        "timestamp": "2026-04-24T15:30:00Z",
        "files_opened": ["src/aictx/middleware.py"],
    }


def test_valid_compact_semantic_repo_loads_fully(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    write_json(
        repo / SEMANTIC_REPO_PATH,
        {
            "repo_id": repo.name,
            "subsystems": [
                {
                    "name": "runtime_startup",
                    "description": "Startup/session initialization and continuity context assembly.",
                    "key_paths": ["src/aictx/middleware.py", "src/aictx/state.py"],
                    "entry_points": ["prepare_execution"],
                    "relevant_tests": ["tests/test_continuity_context.py"],
                    "fragile_areas": ["startup output coupling"],
                }
            ],
            "updated_at": "2026-04-24T15:30:00Z",
            "source_session": 2,
        },
    )

    prepared = prepare_execution(_payload(repo, "exec-semantic-compact"))

    semantic = prepared["continuity_context"]["semantic_repo"]
    assert semantic["repo_id"] == repo.name
    assert len(semantic["subsystems"]) == 1
    assert semantic["subsystems"][0]["name"] == "runtime_startup"
    assert prepared["continuity_context"]["loaded"]["semantic_repo"] is True
    assert "- semantic_repo: yes" in prepared["continuity_summary_text"]


def test_missing_or_malformed_semantic_repo_does_not_crash(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    malformed = repo / SEMANTIC_REPO_PATH
    malformed.parent.mkdir(parents=True, exist_ok=True)
    malformed.write_text("{broken", encoding="utf-8")

    prepared = prepare_execution(_payload(repo, "exec-semantic-bad"))

    assert prepared["continuity_context"]["semantic_repo"] == {}
    assert prepared["continuity_context"]["loaded"]["semantic_repo"] is False
    assert "malformed:.aictx/continuity/semantic_repo.json" in prepared["continuity_context"]["warnings"]
    assert "- semantic_repo: no" in prepared["continuity_summary_text"]


def test_large_semantic_repo_loads_only_relevant_subsystems(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    subsystems = []
    for index in range(6):
        subsystems.append(
            {
                "name": f"subsystem_{index}",
                "description": f"Unrelated area {index}.",
                "key_paths": [f"src/other_{index}.py"],
                "entry_points": [f"entry_{index}"],
                "relevant_tests": [f"tests/test_other_{index}.py"],
                "fragile_areas": [],
            }
        )
    subsystems.append(
        {
            "name": "runtime_startup",
            "description": "Startup/session initialization and continuity context assembly.",
            "key_paths": ["src/aictx/middleware.py", "src/aictx/state.py"],
            "entry_points": ["prepare_execution"],
            "relevant_tests": ["tests/test_continuity_context.py"],
            "fragile_areas": ["startup output coupling"],
        }
    )
    write_json(
        repo / SEMANTIC_REPO_PATH,
        {
            "repo_id": repo.name,
            "subsystems": subsystems,
            "updated_at": "2026-04-24T15:30:00Z",
            "source_session": 2,
        },
    )

    context = load_continuity_context(
        repo,
        task_type="testing",
        request_text="inspect runtime startup continuity",
        files=["src/aictx/middleware.py"],
        area_id="src/aictx",
    )

    loaded = context["semantic_repo"]
    assert loaded["repo_id"] == repo.name
    assert 1 <= len(loaded["subsystems"]) <= 3
    assert any(item["name"] == "runtime_startup" for item in loaded["subsystems"])
