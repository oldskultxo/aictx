from __future__ import annotations

import json
from pathlib import Path

from aictx.continuity import DECISIONS_PATH, HANDOFF_PATH, SEMANTIC_REPO_PATH, STALENESS_PATH, load_continuity_context
from aictx.scaffold import init_repo_scaffold
from aictx.state import write_json


def test_context_ranking_combines_sources_and_explains_loaded_items(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    (repo / "src/aictx").mkdir(parents=True)
    (repo / "src/aictx/continuity.py").write_text("", encoding="utf-8")
    write_json(repo / HANDOFF_PATH, {"summary": "Continue continuity runtime", "recommended_starting_points": ["src/aictx/continuity.py"]})
    (repo / DECISIONS_PATH).write_text(json.dumps({
        "decision": "Rank continuity memory by live paths.",
        "related_paths": ["src/aictx/continuity.py"],
        "subsystem": "continuity_runtime",
    }) + "\n", encoding="utf-8")
    write_json(repo / SEMANTIC_REPO_PATH, {"repo_id": "repo", "subsystems": [{"name": "continuity_runtime", "key_paths": ["src/aictx/continuity.py"]}]})

    context = load_continuity_context(repo, request_text="rank continuity runtime", files=["src/aictx/continuity.py"])

    kinds = [item["kind"] for item in context["ranked_items"]]
    assert "handoff" in kinds
    assert "decision" in kinds
    assert "semantic_repo" in kinds
    assert context["ranked_items"] == sorted(context["ranked_items"], key=lambda item: (-item["score"], item["kind"], item["id"]))
    assert "live_starting_points" in context["why_loaded"]["handoff"]
    assert "live_related_paths" in context["why_loaded"]["decisions"]


def test_stale_handoff_is_excluded_and_explained(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    write_json(repo / HANDOFF_PATH, {"summary": "old", "recommended_starting_points": ["src/missing.py"]})
    write_json(repo / STALENESS_PATH, {"handoff": {"stale": True, "reasons": ["missing_paths:src/missing.py"]}})

    context = load_continuity_context(repo, request_text="resume")

    assert context["handoff"] == {}
    assert context["loaded"]["handoff"] is False
    assert context["why_loaded"]["handoff"] == ["stale_excluded"]
