from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

import aictx.cli as cli
from aictx.agent_runtime import (
    AGENTS_END,
    AGENTS_START,
    render_agent_runtime,
    render_repo_agents_block,
    resolve_workspace_root,
    upsert_marked_block,
)
from aictx.core_runtime import communication_policy_from_defaults
from aictx.scaffold import TEMPLATES_DIR, init_repo_scaffold
from aictx.state import Workspace, default_global_config, read_json


def test_default_global_config_has_workspace():
    cfg = default_global_config()
    assert cfg["active_workspace"] == "default"


def test_templates_exist():
    assert (TEMPLATES_DIR / "context_packet_schema.json").exists()
    assert (TEMPLATES_DIR / "user_preferences.json").exists()
    assert (TEMPLATES_DIR / "model_routing.json").exists()


def test_template_defaults_communication_layer_disabled():
    payload = json.loads((TEMPLATES_DIR / "user_preferences.json").read_text(encoding="utf-8"))
    assert payload["communication"]["layer"] == "disabled"
    assert payload["communication"]["mode"] == "caveman_full"


def test_agent_runtime_mentions_savings_sources_and_communication_modes():
    text = render_agent_runtime()
    assert ".ai_context_engine/metrics/weekly_summary.json" in text
    assert "global_context_savings.json" in text
    assert "unknown" in text
    assert "## Communication mode" in text
    assert "enabled` or `disabled" in text
    assert "caveman_lite" in text
    assert "caveman_full" in text
    assert "caveman_ultra" in text


def test_communication_policy_uses_disabled_template_default():
    payload = json.loads((TEMPLATES_DIR / "user_preferences.json").read_text(encoding="utf-8"))
    policy = communication_policy_from_defaults(payload)
    assert policy["layer"] == "disabled"
    assert policy["mode"] == "caveman_full"


def test_upsert_marked_block_is_idempotent(tmp_path: Path):
    path = tmp_path / "AGENTS.md"
    block = render_repo_agents_block()
    upsert_marked_block(path, block)
    first = path.read_text(encoding="utf-8")
    upsert_marked_block(path, block)
    second = path.read_text(encoding="utf-8")
    assert first == second
    assert first.count(AGENTS_START) == 1
    assert first.count(AGENTS_END) == 1


def test_resolve_workspace_root_prefers_deepest_match(tmp_path: Path):
    outer = tmp_path / "workspace"
    inner = outer / "nested"
    repo = inner / "repo"
    repo.mkdir(parents=True)
    root = resolve_workspace_root(repo, [str(tmp_path), str(outer), str(inner)])
    assert root == inner


def test_init_repo_scaffold_migrates_legacy_repo_layout(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / ".ai_context_memory").mkdir(parents=True)
    (repo / ".ai_context_memory" / "user_preferences.json").write_text("{}", encoding="utf-8")
    (repo / ".context_metrics").mkdir(parents=True)
    (repo / ".context_metrics" / "weekly_summary.json").write_text("{}", encoding="utf-8")

    init_repo_scaffold(repo, update_gitignore=False)

    assert not (repo / ".ai_context_memory").exists()
    assert not (repo / ".context_metrics").exists()
    assert (repo / ".ai_context_engine" / "memory" / "user_preferences.json").exists()
    assert (repo / ".ai_context_engine" / "metrics" / "weekly_summary.json").exists()


def test_persist_repo_communication_mode_disabled(tmp_path: Path):
    repo = tmp_path / "repo"
    prefs_path = repo / ".ai_context_engine" / "memory" / "user_preferences.json"
    prefs_path.parent.mkdir(parents=True)
    prefs_path.write_text((TEMPLATES_DIR / "user_preferences.json").read_text(encoding="utf-8"), encoding="utf-8")

    cli.persist_repo_communication_mode(repo, "disabled")

    prefs = read_json(prefs_path, {})
    assert prefs["communication"]["layer"] == "disabled"
    assert prefs["communication"]["mode"] == "caveman_full"


def test_persist_repo_communication_mode_enabled_mode(tmp_path: Path):
    repo = tmp_path / "repo"
    prefs_path = repo / ".ai_context_engine" / "memory" / "user_preferences.json"
    prefs_path.parent.mkdir(parents=True)
    prefs_path.write_text((TEMPLATES_DIR / "user_preferences.json").read_text(encoding="utf-8"), encoding="utf-8")

    cli.persist_repo_communication_mode(repo, "caveman_ultra")

    prefs = read_json(prefs_path, {})
    assert prefs["communication"]["layer"] == "enabled"
    assert prefs["communication"]["mode"] == "caveman_ultra"


def test_cmd_init_interactive_sets_disabled_mode(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    answers = iter(["", "", "1", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt='': next(answers))
    monkeypatch.setattr(cli, "ensure_global_home", lambda: None)
    monkeypatch.setattr(cli, "install_global_agent_runtime", lambda _write_json: [])
    monkeypatch.setattr(cli, "copy_local_agent_runtime", lambda repo_path: repo_path / ".ai_context_engine" / "agent_runtime.md")
    monkeypatch.setattr(cli, "load_active_workspace", lambda: Workspace("default", [], []))

    args = argparse.Namespace(repo=str(repo), no_gitignore=False, no_register=True, yes=False)
    assert cli.cmd_init(args) == 0

    prefs = read_json(repo / ".ai_context_engine" / "memory" / "user_preferences.json", {})
    assert prefs["communication"]["layer"] == "disabled"
    assert prefs["communication"]["mode"] == "caveman_full"


@pytest.mark.parametrize(("choice", "expected_mode"), [("2", "caveman_lite"), ("3", "caveman_full"), ("4", "caveman_ultra")])
def test_cmd_init_interactive_sets_selected_caveman_mode(tmp_path: Path, monkeypatch, choice: str, expected_mode: str):
    repo = tmp_path / "repo"
    repo.mkdir()
    answers = iter(["", "", choice, ""])
    monkeypatch.setattr("builtins.input", lambda _prompt='': next(answers))
    monkeypatch.setattr(cli, "ensure_global_home", lambda: None)
    monkeypatch.setattr(cli, "install_global_agent_runtime", lambda _write_json: [])
    monkeypatch.setattr(cli, "copy_local_agent_runtime", lambda repo_path: repo_path / ".ai_context_engine" / "agent_runtime.md")
    monkeypatch.setattr(cli, "load_active_workspace", lambda: Workspace("default", [], []))

    args = argparse.Namespace(repo=str(repo), no_gitignore=False, no_register=True, yes=False)
    assert cli.cmd_init(args) == 0

    prefs = read_json(repo / ".ai_context_engine" / "memory" / "user_preferences.json", {})
    assert prefs["communication"]["layer"] == "enabled"
    assert prefs["communication"]["mode"] == expected_mode


def test_cmd_init_yes_keeps_disabled_default(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(cli, "ensure_global_home", lambda: None)
    monkeypatch.setattr(cli, "install_global_agent_runtime", lambda _write_json: [])
    monkeypatch.setattr(cli, "copy_local_agent_runtime", lambda repo_path: repo_path / ".ai_context_engine" / "agent_runtime.md")
    monkeypatch.setattr(cli, "load_active_workspace", lambda: Workspace("default", [], []))

    args = argparse.Namespace(repo=str(repo), no_gitignore=False, no_register=True, yes=True)
    assert cli.cmd_init(args) == 0

    prefs = read_json(repo / ".ai_context_engine" / "memory" / "user_preferences.json", {})
    assert prefs["communication"]["layer"] == "disabled"
    assert prefs["communication"]["mode"] == "caveman_full"
