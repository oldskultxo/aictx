from __future__ import annotations

from pathlib import Path

from aictx.scaffold import init_repo_scaffold
from aictx.state import append_jsonl, read_json, read_jsonl, write_json


def test_init_repo_scaffold_creates_continuity_dir_and_preserves_existing_runtime_memory(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / ".aictx" / "metrics").mkdir(parents=True, exist_ok=True)
    (repo / ".aictx" / "strategy_memory").mkdir(parents=True, exist_ok=True)
    (repo / ".aictx" / "failure_memory").mkdir(parents=True, exist_ok=True)
    (repo / ".aictx" / "memory").mkdir(parents=True, exist_ok=True)
    (repo / ".aictx" / "metrics" / "execution_logs.jsonl").write_text('{"keep": "log"}\n', encoding="utf-8")
    (repo / ".aictx" / "metrics" / "execution_feedback.jsonl").write_text('{"keep": "feedback"}\n', encoding="utf-8")
    (repo / ".aictx" / "strategy_memory" / "strategies.jsonl").write_text('{"keep": "strategy"}\n', encoding="utf-8")
    (repo / ".aictx" / "failure_memory" / "failure_patterns.jsonl").write_text('{"keep": "failure"}\n', encoding="utf-8")
    (repo / ".aictx" / "memory" / "user_preferences.json").write_text('{"keep": "prefs"}\n', encoding="utf-8")

    created = init_repo_scaffold(repo, update_gitignore=False)

    assert str(repo / ".aictx" / "continuity") in created
    assert (repo / ".aictx" / "continuity").is_dir()
    assert (repo / ".aictx" / "metrics" / "execution_logs.jsonl").read_text(encoding="utf-8") == '{"keep": "log"}\n'
    assert (repo / ".aictx" / "metrics" / "execution_feedback.jsonl").read_text(encoding="utf-8") == '{"keep": "feedback"}\n'
    assert (repo / ".aictx" / "strategy_memory" / "strategies.jsonl").read_text(encoding="utf-8") == '{"keep": "strategy"}\n'
    assert (repo / ".aictx" / "failure_memory" / "failure_patterns.jsonl").read_text(encoding="utf-8") == '{"keep": "failure"}\n'
    assert read_json(repo / ".aictx" / "memory" / "user_preferences.json", {})["keep"] == "prefs"

    second_created = init_repo_scaffold(repo, update_gitignore=False)
    assert str(repo / ".aictx" / "continuity") not in second_created


def test_state_json_helpers_are_safe_and_deterministic(tmp_path: Path):
    json_path = tmp_path / "data" / "payload.json"
    write_json(json_path, {"b": 2, "a": 1})
    assert json_path.read_text(encoding="utf-8") == '{\n  "a": 1,\n  "b": 2\n}\n'
    assert read_json(json_path, {}) == {"a": 1, "b": 2}

    bad_json_path = tmp_path / "data" / "broken.json"
    bad_json_path.write_text('{broken', encoding="utf-8")
    assert read_json(bad_json_path, {"fallback": True}) == {"fallback": True}

    jsonl_path = tmp_path / "rows" / "items.jsonl"
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path.write_text('{"ok": 1}\nnot-json\n[1, 2, 3]\n\n{"ok": 2}\n', encoding="utf-8")
    assert read_jsonl(jsonl_path) == [{"ok": 1}, {"ok": 2}]

    append_jsonl(jsonl_path, {"z": 9, "a": 1})
    assert read_jsonl(jsonl_path)[-1] == {"a": 1, "z": 9}
