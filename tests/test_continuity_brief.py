from __future__ import annotations

import json
from pathlib import Path

from aictx.continuity import DECISIONS_PATH, HANDOFF_PATH, SEMANTIC_REPO_PATH
from aictx.middleware import prepare_execution
from aictx.scaffold import init_repo_scaffold
from aictx.state import write_json


def test_prepare_execution_exposes_deterministic_continuity_brief(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    (repo / "src/aictx").mkdir(parents=True)
    (repo / "src/aictx/middleware.py").write_text("", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests/test_continuity.py").write_text("", encoding="utf-8")
    write_json(repo / HANDOFF_PATH, {
        "summary": "Resume middleware continuity.",
        "next_steps": ["finish continuity brief"],
        "risks": ["avoid noisy context"],
        "recommended_starting_points": ["src/aictx/middleware.py"],
    })
    (repo / DECISIONS_PATH).write_text(
        json.dumps({
            "decision": "Expose additive v4.2 continuity fields.",
            "rationale": "Keep 4.1 compatible.",
            "related_paths": ["src/aictx/middleware.py"],
            "risks": ["breaking payload consumers"],
            "subsystem": "continuity_runtime",
        }) + "\n",
        encoding="utf-8",
    )
    write_json(repo / SEMANTIC_REPO_PATH, {
        "repo_id": "repo",
        "subsystems": [{
            "name": "continuity_runtime",
            "description": "prepare/finalize continuity payloads",
            "key_paths": ["src/aictx/middleware.py"],
            "relevant_tests": ["tests/test_continuity.py"],
            "fragile_areas": ["payload compatibility"],
        }],
    })

    prepared = prepare_execution({
        "repo_root": str(repo),
        "user_request": "implement continuity brief for middleware",
        "agent_id": "codex",
        "adapter_id": "codex",
        "execution_id": "brief-1",
        "timestamp": "2026-04-25T00:00:00Z",
        "files_opened": ["src/aictx/middleware.py"],
    })

    brief = prepared["continuity_brief"]
    assert brief["version"] == 2
    assert brief["where_to_continue"] == ["finish continuity brief"]
    assert "Expose additive v4.2 continuity fields." in brief["active_decisions"]
    assert "src/aictx/middleware.py" in brief["probable_paths"]
    assert "avoid noisy context" in brief["known_risks"]
    assert prepared["continuity_context"]["continuity_brief"] == brief
    assert prepared["continuity_context"]["why_loaded"]["handoff"]
