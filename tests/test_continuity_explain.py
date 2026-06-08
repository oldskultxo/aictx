from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from aictx.continuity import DECISIONS_PATH, HANDOFF_PATH, build_resume_capsule, render_resume_capsule
from aictx.failure_memory import FAILURE_PATTERNS_PATH
from aictx.scaffold import init_repo_scaffold
from aictx.state import write_json
from aictx.strategy_memory import persist_strategy
from aictx.repo_map.config import write_repomap_config, write_repomap_index


def test_resume_loaded_context_explains_loaded_sources_in_priority_order(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    (repo / "src/aictx").mkdir(parents=True)
    (repo / "src/aictx/middleware.py").write_text("def load_continuity_context():\n    pass\n", encoding="utf-8")
    write_json(repo / HANDOFF_PATH, {
        "summary": "Resume middleware startup work",
        "next_steps": ["inspect middleware import path"],
        "recommended_starting_points": ["src/aictx/middleware.py"],
        "updated_at": "2026-05-10T10:00:00Z",
        "source_execution_id": "exec-handoff-1",
    })
    (repo / DECISIONS_PATH).parent.mkdir(parents=True, exist_ok=True)
    (repo / DECISIONS_PATH).write_text(json.dumps({
        "decision": "Keep continuity loading in middleware.",
        "related_paths": ["src/aictx/middleware.py"],
        "subsystem": "continuity_runtime",
        "timestamp": "2026-05-10T11:00:00Z",
        "execution_id": "decision-1",
    }) + "\n", encoding="utf-8")
    failure_path = repo / FAILURE_PATTERNS_PATH
    failure_path.parent.mkdir(parents=True, exist_ok=True)
    failure_path.write_text(json.dumps({
        "failure_id": "failure::startup-import",
        "signature": "startup_import_error",
        "task_type": "bug_fixing",
        "area_id": "src/aictx/middleware.py",
        "error_text": "ImportError during startup middleware load",
        "related_paths": ["src/aictx/middleware.py"],
        "timestamp": "2026-05-10T12:00:00Z",
        "status": "open",
    }) + "\n", encoding="utf-8")
    persist_strategy(repo, {
        "task_id": "strategy-1",
        "task_text": "fix startup import bug",
        "task_type": "bug_fixing",
        "area_id": "src/aictx/middleware.py",
        "entry_points": ["src/aictx/middleware.py"],
        "primary_entry_point": "src/aictx/middleware.py",
        "files_used": ["src/aictx/middleware.py"],
        "success": True,
        "timestamp": "2026-05-10T13:00:00Z",
    })
    write_repomap_config(repo, {"enabled": True})
    write_repomap_index(repo, {
        "version": 1,
        "files": [{
            "path": "src/aictx/middleware.py",
            "language": "python",
            "symbols": [{"name": "load_continuity_context", "kind": "function", "line": 1, "language": "python"}],
        }],
    })

    payload = build_resume_capsule(repo, request_text="fix startup import bug", task_type="bug_fixing", agent_id="codex")

    loaded = payload["loaded_context"]
    assert [item["kind"] for item in loaded[:4]] == ["handoff", "failure", "strategy", "decision"]
    assert [item["rank"] for item in loaded] == list(range(1, len(loaded) + 1))
    assert all(item["role"] in {"primary", "carryover", "caution", "background"} for item in loaded)
    assert all(item["selection_reason"] for item in loaded)
    assert loaded[0]["source_id"].startswith("handoff::")
    assert loaded[0]["role"] == "carryover"
    assert "latest_handoff" in loaded[0]["match_reasons"]
    assert loaded[1]["source"] == ".aictx/failure_memory/failure_patterns.jsonl"
    assert loaded[1]["role"] == "caution"
    assert "task_type:bug_fixing" in loaded[1]["match_reasons"]
    assert any(reason.startswith("path_overlap:src/aictx/middleware.py") for reason in loaded[1]["match_reasons"])
    assert loaded[1]["confidence"] in {"medium", "high"}
    assert loaded[2]["source_id"] == "strategy-1"
    assert any(reason.startswith("strategy_confidence:") for reason in loaded[2]["match_reasons"])
    assert any(reason.startswith("decision_related_path:src/aictx/middleware.py") for reason in loaded[3]["match_reasons"])
    assert all(item["kind"] != "repo_map" for item in loaded)
    assert all(not Path(path).is_absolute() for item in loaded for path in item["related_paths"])


def test_resume_json_includes_communication_policy_without_rendering_it(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    prefs_path = repo / ".aictx" / "memory" / "user_preferences.json"
    prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
    prefs["communication"] = {
        "layer": "enabled",
        "mode": "caveman_ultra",
        "intermediate_updates": "suppressed",
        "final_style": "plain_direct_final_only",
    }
    prefs_path.write_text(json.dumps(prefs), encoding="utf-8")

    payload = build_resume_capsule(repo, request_text="test communication policy", agent_id="codex")

    assert payload["communication_policy"]["layer"] == "disabled"
    assert payload["communication_policy"]["mode"] == "disabled"
    assert payload["runtime_text_policy"]["communication"]["mode"] == "disabled"
    assert payload["runtime_text_policy"]["does_not_modify_startup_banner"] is True
    assert payload["runtime_text_policy"]["does_not_modify_agent_summary"] is True
    assert "Communication: caveman_ultra" not in render_resume_capsule(payload)


def test_resume_loaded_context_is_additive_when_no_context_is_loaded(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    payload = build_resume_capsule(repo, request_text="new task", task_type="testing", agent_id="codex")

    assert "loaded_context" in payload
    assert payload["loaded_context"] == []
    assert "capsule" in payload
    assert "execution_contract" in payload


def test_resume_loaded_context_repo_map_matches_repo_map_slice(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    (repo / "docs").mkdir(parents=True)
    (repo / "docs/startup.md").write_text("# Startup Banner\n", encoding="utf-8")
    write_repomap_config(repo, {"enabled": True})
    write_repomap_index(repo, {
        "version": 1,
        "files": [{
            "path": "docs/startup.md",
            "language": "markdown",
            "symbols": [{"name": "Startup Banner", "kind": "heading", "line": 1, "language": "markdown"}],
        }],
    })

    payload = build_resume_capsule(repo, request_text="startup banner", task_type="documentation", agent_id="codex")

    repo_map_paths = [item["path"] for item in payload["capsule"]["repo_map"]["primary"] + payload["capsule"]["repo_map"]["secondary"]]
    loaded_repo_map = [item for item in payload["loaded_context"] if item["kind"] == "repo_map"]
    assert repo_map_paths
    assert loaded_repo_map
    assert loaded_repo_map[0]["related_paths"] == [repo_map_paths[0]]
    assert loaded_repo_map[0]["source"] == ".aictx/repo_map/index.json"
    assert any(reason.startswith("repo_map:") for reason in loaded_repo_map[0]["match_reasons"])


def test_resume_loaded_context_handoff_timestamp_and_path_hygiene(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    source_path = repo / "src/aictx/middleware.py"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("def load_continuity_context():\n    pass\n", encoding="utf-8")
    outside_path = tmp_path / "outside.py"
    outside_path.write_text("print('outside')\n", encoding="utf-8")
    write_json(repo / HANDOFF_PATH, {
        "summary": "Resume middleware startup work",
        "recommended_starting_points": [
            str(source_path),
            str(source_path),
            str(outside_path),
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    payload = build_resume_capsule(repo, request_text="fix middleware startup", agent_id="codex")

    handoff_items = [item for item in payload["loaded_context"] if item["kind"] == "handoff"]
    assert handoff_items
    assert handoff_items[0]["staleness"] == "fresh"
    assert handoff_items[0]["related_paths"] == ["src/aictx/middleware.py"]
    assert all(not Path(path).is_absolute() for path in handoff_items[0]["related_paths"])
