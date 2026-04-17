from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from aictx.adapters import install_global_adapters
import aictx.cli as cli
import aictx.core_runtime as core_runtime
import aictx.runtime_io as runtime_io
import aictx.runtime_memory as runtime_memory
import aictx.runtime_tasks as runtime_tasks
import aictx.runtime_knowledge as runtime_knowledge
import aictx.runtime_cost as runtime_cost
import aictx.runtime_failure as runtime_failure
import aictx.runtime_graph as runtime_graph
from aictx.agent_runtime import (
    AGENTS_END,
    AGENTS_START,
    render_agent_runtime,
    render_repo_agents_block,
    resolve_workspace_root,
    upsert_marked_block,
)
from aictx.core_runtime import communication_policy_from_defaults
from aictx.middleware import finalize_execution, prepare_execution
from aictx.runner_integrations import (
    install_codex_native_integration,
    install_repo_runner_integrations,
)
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


def test_install_global_adapters_creates_codex_and_claude(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("aictx.adapters.ENGINE_HOME", tmp_path / ".ai_context_engine")
    monkeypatch.setattr("aictx.adapters.GLOBAL_ADAPTERS_DIR", (tmp_path / ".ai_context_engine" / "adapters"))
    monkeypatch.setattr("aictx.adapters.GLOBAL_ADAPTERS_REGISTRY_PATH", (tmp_path / ".ai_context_engine" / "adapters" / "registry.json"))
    monkeypatch.setattr("aictx.adapters.GLOBAL_ADAPTERS_BIN_DIR", (tmp_path / ".ai_context_engine" / "adapters" / "bin"))
    monkeypatch.setattr("aictx.adapters.GLOBAL_ADAPTERS_INSTALL_STATUS_PATH", (tmp_path / ".ai_context_engine" / "adapters" / "install_status.json"))
    created = install_global_adapters()
    assert any(path.name == "codex.json" for path in created)
    assert any(path.name == "claude.json" for path in created)
    assert any(path.name == "aictx-codex-auto" for path in created)
    install_status = read_json(tmp_path / ".ai_context_engine" / "adapters" / "install_status.json", {})
    assert install_status["status"] == "wrapper_ready"
    assert install_status["runtime_entrypoint"] == "aictx internal run-execution"


def test_agent_runtime_mentions_savings_sources_and_communication_modes():
    text = render_agent_runtime()
    assert ".ai_context_engine/metrics/weekly_summary.json" in text
    assert "global_context_savings.json" in text
    assert "unknown" in text
    assert "## Communication mode" in text
    assert "## Execution middleware" in text
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


def test_init_repo_scaffold_installs_repo_adapters(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    registry = read_json(repo / ".ai_context_engine" / "adapters" / "registry.json", {})
    codex = read_json(repo / ".ai_context_engine" / "adapters" / "codex.json", {})
    claude = read_json(repo / ".ai_context_engine" / "adapters" / "claude.json", {})

    assert registry["middleware_mode"] == "always_on"
    assert codex["explicit_skill_metadata"] is True
    assert claude["middleware_always_on"] is True


def test_prepare_execution_plain_mode_without_skill_metadata(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "summarize current engine behavior",
            "agent_id": "agent-test",
            "execution_id": "exec-plain-1",
        }
    )

    assert prepared["execution_mode"] == "plain"
    assert prepared["skill_detection"]["authority"] == "none"
    assert prepared["communication_policy"]["layer"] == "disabled"
    assert prepared["boot_sources"]["derived_boot_summary"]["bootstrap_required"] is True
    assert prepared["adapter_profile"]["adapter_id"] == "generic"


def test_prepare_execution_skill_mode_with_explicit_metadata(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "apply github review comments",
            "agent_id": "agent-test",
            "adapter_id": "codex",
            "execution_id": "exec-skill-1",
            "skill_metadata": {
                "skill_id": "github:gh-address-comments",
                "skill_name": "gh-address-comments",
                "skill_path": "/tmp/skills/gh-address-comments/SKILL.md",
                "source": "runner",
            },
        }
    )

    assert prepared["execution_mode"] == "skill"
    assert prepared["skill_detection"]["authority"] == "explicit"
    assert prepared["skill_metadata"]["skill_id"] == "github:gh-address-comments"
    assert prepared["skill_context"]["skill_name"] == "gh-address-comments"
    assert prepared["adapter_profile"]["adapter_id"] == "codex"
    assert prepared["adapter_profile"]["explicit_skill_metadata"] is True


def test_prepare_execution_resolves_claude_adapter_without_user_extra_steps(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "summarize adapter support",
            "agent_id": "claude-code",
            "execution_id": "exec-claude-1",
        }
    )

    assert prepared["adapter_profile"]["adapter_id"] == "claude"
    assert prepared["adapter_profile"]["middleware_always_on"] is True


def test_prepare_execution_heuristic_skill_detection_stays_plain(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "use $github:gh-address-comments skill to review comments",
            "agent_id": "agent-test",
            "execution_id": "exec-heuristic-1",
        }
    )

    assert prepared["execution_mode"] == "plain"
    assert prepared["skill_detection"]["authority"] == "heuristic"
    assert prepared["skill_detection"]["confidence"] == "low"
    assert prepared["skill_metadata"] == {}


def test_finalize_execution_persists_learning_and_telemetry(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "document middleware behavior",
            "agent_id": "agent-test",
            "execution_id": "exec-finalize-1",
        }
    )

    finalized = finalize_execution(
        prepared,
        {
            "success": True,
            "result_summary": "Validated middleware flow and persisted behavior.",
            "validated_learning": True,
        },
    )

    weekly = read_json(repo / ".ai_context_engine" / "metrics" / "weekly_summary.json", {})
    workflow_rows = (repo / ".ai_context_engine" / "memory" / "workflow_learnings.jsonl").read_text(encoding="utf-8").splitlines()
    status = read_json(repo / ".ai_context_engine" / "metrics" / "agent_execution_status.json", {})
    assert finalized["learning_persisted"]["record_id"] == "execution_learning::exec-finalize-1"
    assert weekly["tasks_sampled"] >= 1
    assert status["last_execution_mode"] == "plain"
    assert any("exec-finalize-1" in row for row in workflow_rows)


def test_finalize_execution_failure_records_failure_memory(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "debug failing middleware run",
            "agent_id": "agent-test",
            "execution_id": "exec-failure-1",
            "skill_metadata": {
                "skill_id": "github:gh-fix-ci",
                "skill_name": "gh-fix-ci",
                "skill_path": "/tmp/skills/gh-fix-ci/SKILL.md",
                "source": "runner",
            },
        }
    )

    finalized = finalize_execution(
        prepared,
        {
            "success": False,
            "result_summary": "skill execution failed due to missing token",
            "validated_learning": False,
        },
    )

    failure_status = read_json(repo / ".ai_context_engine" / "failure_memory" / "failure_memory_status.json", {})
    log_lines = (repo / ".ai_context_engine" / "metrics" / "agent_execution_log.jsonl").read_text(encoding="utf-8").splitlines()
    assert finalized["failure_recorded"]["failure_id"].startswith("exec-failure-1_")
    assert failure_status["records_total"] == 1
    assert any("\"execution_mode\": \"skill\"" in row for row in log_lines)


def test_cli_execution_prepare_and_finalize_round_trip(tmp_path: Path, monkeypatch, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    parser = cli.build_parser()

    prepare_args = parser.parse_args(
        [
            "execution",
            "prepare",
            "--repo",
            str(repo),
            "--request",
            "review middleware behavior",
            "--agent-id",
            "agent-test",
            "--execution-id",
            "exec-cli-1",
        ]
    )
    assert prepare_args.func(prepare_args) == 0
    prepared_output = json.loads(capsys.readouterr().out)
    prepared_path = repo / "prepared_execution.json"
    prepared_path.write_text(json.dumps(prepared_output), encoding="utf-8")

    finalize_args = parser.parse_args(
        [
            "execution",
            "finalize",
            "--prepared",
            str(prepared_path),
            "--success",
            "--validated-learning",
            "--result-summary",
            "CLI finalize completed.",
        ]
    )
    assert finalize_args.func(finalize_args) == 0
    finalized_output = json.loads(capsys.readouterr().out)
    assert finalized_output["execution_id"] == "exec-cli-1"


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


def test_cmd_init_prepares_repo_runtime_state(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(cli, "ensure_global_home", lambda: None)
    monkeypatch.setattr(cli, "install_global_agent_runtime", lambda _write_json: [])
    monkeypatch.setattr(cli, "copy_local_agent_runtime", lambda repo_path: repo_path / ".ai_context_engine" / "agent_runtime.md")
    monkeypatch.setattr(cli, "load_active_workspace", lambda: Workspace("default", [], []))

    args = argparse.Namespace(repo=str(repo), no_gitignore=False, no_register=True, yes=True)
    assert cli.cmd_init(args) == 0

    state = read_json(repo / ".ai_context_engine" / "state.json", {})
    assert state["installed_iteration"] >= 1
    assert state["engine_role"] == "initialized_repo_runtime"
    assert state["supports"]["packet_construction"] is True
    assert state["adapter_runtime_enabled"] is True
    assert state["runner_integration_status"] == "native_ready"
    assert state["auto_execution_entrypoint"] == "aictx internal run-execution"
    assert state["runner_native_integrations"]["codex"]["status"] == "native_hardened"
    assert state["runner_native_integrations"]["claude"]["status"] == "native_hardened"
    assert state["communication_layer"] == "disabled"
    assert (repo / ".ai_context_engine" / "metrics" / "agent_execution_status.json").exists()
    assert (repo / ".ai_context_engine" / "metrics" / "agent_execution_log.jsonl").exists()
    assert (repo / ".ai_context_engine" / "cost" / "optimization_history.jsonl").exists()
    assert (repo / "AGENTS.override.md").exists()
    assert (repo / "CLAUDE.md").exists()
    assert (repo / ".claude" / "settings.json").exists()
    assert (repo / ".claude" / "hooks" / "aictx_session_start.py").exists()
    assert (repo / ".claude" / "hooks" / "aictx_pre_tool_use.py").exists()


def test_cli_main_help_shows_simple_surface_only():
    parser = cli.build_parser()
    help_text = parser.format_help()
    assert "install" in help_text
    assert "init" in help_text
    assert "workspace" not in help_text
    assert "boot" not in help_text
    assert "memory-graph" not in help_text
    assert "execution" not in help_text


def test_install_and_init_copy_match_product_story(tmp_path: Path, monkeypatch, capsys):
    def fake_read_json(path, default):
        path_str = str(path)
        if "workspaces" in path_str or path == tmp_path / "default.json":
            return None
        return {} if default is None else default

    monkeypatch.setattr(cli, "ensure_global_home", lambda: None)
    monkeypatch.setattr(cli, "install_global_agent_runtime", lambda _write_json: [])
    monkeypatch.setattr(cli, "install_global_adapters", lambda: [])
    monkeypatch.setattr(cli, "install_codex_native_integration", lambda: [])
    monkeypatch.setattr(cli, "write_json", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "read_json", fake_read_json)
    monkeypatch.setattr(cli, "workspace_path", lambda wid: tmp_path / f"{wid}.json")
    install_args = argparse.Namespace(
        workspace_id="default",
        workspace_root=str(tmp_path / "ws"),
        disable_global_metrics=False,
        cross_project_mode="workspace",
        yes=False,
    )
    answers = iter(["default", "n", "y"])
    monkeypatch.setattr("builtins.input", lambda _prompt='': next(answers))
    assert cli.cmd_install(install_args) == 0
    install_out = capsys.readouterr().out
    assert "prepare repos to work after a single `aictx init`" in install_out
    assert "Next: run `aictx init` inside a repository." in install_out

    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(cli, "ensure_global_home", lambda: None)
    monkeypatch.setattr(cli, "install_global_agent_runtime", lambda _write_json: [])
    monkeypatch.setattr(cli, "copy_local_agent_runtime", lambda repo_path: repo_path / ".ai_context_engine" / "agent_runtime.md")
    monkeypatch.setattr(cli, "load_active_workspace", lambda: Workspace("default", [], []))
    init_answers = iter(["", "", "1", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt='': next(init_answers))
    args = argparse.Namespace(repo=str(repo), no_gitignore=False, no_register=True, yes=False)
    assert cli.cmd_init(args) == 0
    init_out = capsys.readouterr().out
    assert "provision Codex and Claude native repo integration files" in init_out
    assert "Use your coding agent normally in this repo." in init_out


def test_internal_run_execution_wraps_command_and_persists_status(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    cli.prepare_repo_runtime(repo)
    parser = cli.build_parser()

    args = parser.parse_args(
        [
            "internal",
            "run-execution",
            "--repo",
            str(repo),
            "--request",
            "run wrapped command",
            "--agent-id",
            "codex",
            "--adapter-id",
            "codex",
            "--execution-id",
            "exec-wrap-1",
            "--validated-learning",
            "--json",
            "--",
            "python3",
            "-c",
            "print('wrapped ok')",
        ]
    )

    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["exit_code"] == 0
    assert "wrapped ok" in payload["stdout"]
    assert payload["prepared"]["adapter_profile"]["adapter_id"] == "codex"
    assert payload["finalized"]["learning_persisted"]["record_id"] == "execution_learning::exec-wrap-1"

    status = read_json(repo / ".ai_context_engine" / "metrics" / "agent_execution_status.json", {})
    assert status["last_execution_id"] == "exec-wrap-1"


def test_install_repo_runner_integrations_creates_codex_and_claude_native_files(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    created = install_repo_runner_integrations(repo)
    assert repo / "AGENTS.override.md" in created
    assert repo / "CLAUDE.md" in created
    settings = read_json(repo / ".claude" / "settings.json", {})
    assert "SessionStart" in settings["hooks"]
    assert "UserPromptSubmit" in settings["hooks"]
    assert "PreToolUse" in settings["hooks"]
    assert (repo / ".claude" / "hooks" / "aictx_user_prompt_submit.py").exists()
    assert (repo / ".claude" / "hooks" / "aictx_pre_tool_use.py").exists()


def test_install_codex_native_integration_writes_home_override(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("aictx.runner_integrations.CODEX_HOME", tmp_path / ".codex")
    monkeypatch.setattr("aictx.runner_integrations.CODEX_CONFIG_PATH", tmp_path / ".codex" / "config.toml")
    created = install_codex_native_integration()
    assert (tmp_path / ".codex" / "AGENTS.override.md") in created
    assert (tmp_path / ".codex" / "config.toml") in created
    text = (tmp_path / ".codex" / "AGENTS.override.md").read_text(encoding="utf-8")
    assert "AICTX Codex integration" in text
    config = (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert 'project_doc_fallback_filenames = ["CLAUDE.md"]' in config


def test_claude_pre_tool_hook_blocks_generated_runtime_edits(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    install_repo_runner_integrations(repo)
    script = repo / ".claude" / "hooks" / "aictx_pre_tool_use.py"

    write_payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(repo / ".ai_context_engine" / "memory" / "derived_boot_summary.json"),
        },
    }
    proc = subprocess.run(
        ["python3", str(script)],
        input=json.dumps(write_payload),
        text=True,
        capture_output=True,
        env={"CLAUDE_PROJECT_DIR": str(repo)},
        check=False,
    )
    assert proc.returncode == 2
    assert "generated runtime artifacts" in proc.stderr


def test_claude_pre_tool_hook_allows_normal_edits(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    install_repo_runner_integrations(repo)
    script = repo / ".claude" / "hooks" / "aictx_pre_tool_use.py"

    write_payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(repo / "src" / "main.py"),
        },
    }
    proc = subprocess.run(
        ["python3", str(script)],
        input=json.dumps(write_payload),
        text=True,
        capture_output=True,
        env={"CLAUDE_PROJECT_DIR": str(repo)},
        check=False,
    )
    assert proc.returncode == 0


def test_boot_prefers_repo_communication_policy_and_reports_mismatch(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    cli.prepare_repo_runtime(repo)

    state_path = repo / ".ai_context_engine" / "state.json"
    state = read_json(state_path, {})
    state["communication_layer"] = "enabled"
    state["communication_mode"] = "caveman_ultra"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    boot = core_runtime.bootstrap(str(repo))
    prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "summarize communication policy",
            "agent_id": "agent-test",
            "execution_id": "exec-consistency-1",
        }
    )

    assert boot["communication_policy"]["layer"] == "disabled"
    assert prepared["communication_policy"]["layer"] == "disabled"
    assert boot["communication_sources"]["layer"] == "repo_preferences"
    assert boot["consistency_checks"]["status"] == "warning"
    assert prepared["consistency_checks"]["status"] == "warning"
    assert any(issue["check"] == "communication_layer_mismatch" for issue in boot["consistency_checks"]["issues"])


def test_cli_smoke_flow_runs_through_python_module(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")

    init_proc = subprocess.run(
        [sys.executable, "-m", "aictx", "init", "--repo", str(repo), "--yes", "--no-register"],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert init_proc.returncode == 0, init_proc.stderr

    boot_proc = subprocess.run(
        [sys.executable, "-m", "aictx", "boot", "--repo", str(repo)],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert boot_proc.returncode == 0, boot_proc.stderr
    boot_payload = json.loads(boot_proc.stdout)
    assert boot_payload["repo_bootstrap"]["exists"] is True
    assert boot_payload["communication_policy"]["layer"] == "disabled"

    packet_proc = subprocess.run(
        [sys.executable, "-m", "aictx", "packet", "--task", "debug failing integration"],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert packet_proc.returncode == 0, packet_proc.stderr

    prepared_path = repo / "prepared.json"
    prepare_proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "aictx",
            "execution",
            "prepare",
            "--repo",
            str(repo),
            "--request",
            "review middleware behavior",
            "--agent-id",
            "cli-smoke",
            "--execution-id",
            "cli-smoke-1",
        ],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert prepare_proc.returncode == 0, prepare_proc.stderr
    prepared_path.write_text(prepare_proc.stdout, encoding="utf-8")

    finalize_proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "aictx",
            "execution",
            "finalize",
            "--prepared",
            str(prepared_path),
            "--success",
            "--validated-learning",
            "--result-summary",
            "CLI smoke finalize completed.",
        ],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert finalize_proc.returncode == 0, finalize_proc.stderr
    finalized_payload = json.loads(finalize_proc.stdout)
    assert finalized_payload["execution_id"] == "cli-smoke-1"


def test_boot_reports_not_initialized_for_plain_repo(tmp_path: Path):
    repo = tmp_path / "plain-repo"
    repo.mkdir()

    boot = core_runtime.bootstrap(str(repo))

    assert boot["repo_bootstrap"]["exists"] is False
    assert boot["repo_bootstrap"]["status"] == "not_initialized"
    assert boot["consistency_checks"]["status"] == "not_initialized"
    assert boot["communication_sources"]["layer"] in {"global_defaults", "hardcoded_fallback"}


def test_global_health_check_reports_runtime_consistency_warning(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    cli.prepare_repo_runtime(repo)

    state_path = repo / ".ai_context_engine" / "state.json"
    state = read_json(state_path, {})
    state["communication_layer"] = "enabled"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    monkeypatch.setattr("aictx.global_metrics.PROJECTS_INDEX_PATH", tmp_path / "projects_index.json")
    monkeypatch.setattr("aictx.global_metrics.CONTEXT_SAVINGS_PATH", tmp_path / "context.json")
    monkeypatch.setattr("aictx.global_metrics.TELEMETRY_SOURCES_PATH", tmp_path / "telemetry_sources.json")
    monkeypatch.setattr("aictx.global_metrics.HEALTH_REPORT_PATH", tmp_path / "health.json")

    (tmp_path / "projects_index.json").write_text(json.dumps({"projects": [{"name": repo.name, "repo_path": str(repo), "installed_iteration": "16", "telemetry_dir": "unknown"}]}), encoding="utf-8")
    (tmp_path / "context.json").write_text(json.dumps({"project_breakdown": [{"name": repo.name}], "projects_with_telemetry": 0, "projects_with_memory": 1}), encoding="utf-8")
    (tmp_path / "telemetry_sources.json").write_text(json.dumps({"sources": [{"project": repo.name}]}), encoding="utf-8")

    import aictx.global_metrics as global_metrics
    health = global_metrics.run_health_check()

    project_check = next(item for item in health["checks"] if item["scope"] == repo.name and item["check"] == "project_health")
    assert project_check["consistency"]["status"] == "warning"
    assert any(issue["check"] == "runtime_consistency" for issue in project_check["issues"])


def test_core_runtime_keeps_compatibility_exports_after_refactor():
    assert core_runtime.rank_records is not None
    assert core_runtime.packet_for_task is not None
    assert core_runtime.retrieve_knowledge is not None
    assert callable(core_runtime.rank_records)
    assert callable(core_runtime.packet_for_task)
    assert callable(core_runtime.retrieve_knowledge)


def test_runtime_io_helpers_are_available():
    assert runtime_io.slugify("Hello World") == "hello_world"
    assert runtime_io.truncate_words("one two three four", 2) == "one two ..."


def test_runtime_memory_and_tasks_modules_work_with_scaffold(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    matches = runtime_memory.rank_records("workflow")
    assert isinstance(matches, list)

    resolved = runtime_tasks.resolve_task_type("debug failing integration")
    assert resolved["task_type"] in {"bug_fixing", "unknown"}

    packet = runtime_tasks.packet_for_task("debug failing integration")
    assert packet["task_summary"] == "debug failing integration"
    assert "communication_policy" not in packet


def test_runtime_knowledge_module_bootstrap_mod(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(core_runtime, "LIBRARY_DIR", tmp_path / ".ai_context_engine" / "library")
    monkeypatch.setattr(core_runtime, "LIBRARY_REGISTRY_PATH", tmp_path / ".ai_context_engine" / "library" / "registry.json")
    monkeypatch.setattr(core_runtime, "LIBRARY_RETRIEVAL_STATUS_PATH", tmp_path / ".ai_context_engine" / "library" / "retrieval_status.json")
    manifest = runtime_knowledge.bootstrap_mod("ux", create_reference_stub=True)
    assert manifest["id"] == "ux"
    assert (tmp_path / ".ai_context_engine" / "library" / "mods" / "ux" / "inbox" / "references.md").exists()


def test_runtime_cost_module_optimizer_roundtrip(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(core_runtime, "BASE", tmp_path)
    monkeypatch.setattr(core_runtime, "ENGINE_STATE_DIR", tmp_path / ".ai_context_engine")
    monkeypatch.setattr(core_runtime, "COST_DIR", tmp_path / ".ai_context_engine" / "cost")
    monkeypatch.setattr(core_runtime, "COST_CONFIG_PATH", tmp_path / ".ai_context_engine" / "cost" / "optimizer_config.yaml")
    monkeypatch.setattr(core_runtime, "COST_RULES_PATH", tmp_path / ".ai_context_engine" / "cost" / "cost_estimation_rules.md")
    monkeypatch.setattr(core_runtime, "COST_STATUS_PATH", tmp_path / ".ai_context_engine" / "cost" / "packet_budget_status.json")
    monkeypatch.setattr(core_runtime, "COST_HISTORY_PATH", tmp_path / ".ai_context_engine" / "cost" / "optimization_history.jsonl")
    monkeypatch.setattr(core_runtime, "COST_LATEST_REPORT_PATH", tmp_path / ".ai_context_engine" / "cost" / "latest_optimization_report.md")

    payload = {
        "task": "debug failing integration",
        "task_summary": "debug failing integration",
        "task_type": "bug_fixing",
        "user_preferences": [{"id": "p1", "summary": "keep concise"}],
        "constraints": [{"id": "c1", "summary": "do not break cli"}],
        "architecture_rules": [{"id": "a1", "summary": "respect adapter contract"}],
        "relevant_memory": [{"id": "m1", "summary": "past fix", "context_cost": 120}],
        "repo_scope": [{"path": "src/aictx/core_runtime.py"}],
        "known_patterns": [],
    }
    optimized = runtime_cost.optimize_packet(payload)
    assert optimized["packet"]["optimization_report"]["status"] in {"within_budget", "optimized", "over_budget_after_optimization"}


def test_runtime_failure_module_record_and_rank(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(core_runtime, "BASE", tmp_path)
    monkeypatch.setattr(core_runtime, "ENGINE_STATE_DIR", tmp_path / ".ai_context_engine")
    monkeypatch.setattr(core_runtime, "FAILURE_MEMORY_DIR", tmp_path / ".ai_context_engine" / "failure_memory")
    monkeypatch.setattr(core_runtime, "FAILURE_MEMORY_RECORDS_DIR", tmp_path / ".ai_context_engine" / "failure_memory" / "failures")
    monkeypatch.setattr(core_runtime, "FAILURE_MEMORY_INDEX_PATH", tmp_path / ".ai_context_engine" / "failure_memory" / "index.json")
    monkeypatch.setattr(core_runtime, "FAILURE_MEMORY_STATUS_PATH", tmp_path / ".ai_context_engine" / "failure_memory" / "failure_memory_status.json")
    monkeypatch.setattr(core_runtime, "FAILURE_MEMORY_SUMMARY_PATH", tmp_path / ".ai_context_engine" / "failure_memory" / "summaries" / "common_patterns.md")
    monkeypatch.setattr(core_runtime, "TASK_MEMORY_DIR", tmp_path / ".ai_context_engine" / "task_memory")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_DIR", tmp_path / ".ai_context_engine" / "memory_graph")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_NODES_PATH", tmp_path / ".ai_context_engine" / "memory_graph" / "nodes" / "nodes.jsonl")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_EDGES_PATH", tmp_path / ".ai_context_engine" / "memory_graph" / "edges" / "edges.jsonl")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_STATUS_PATH", tmp_path / ".ai_context_engine" / "memory_graph" / "graph_status.json")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_LABEL_INDEX_PATH", tmp_path / ".ai_context_engine" / "memory_graph" / "indexes" / "by_label.json")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_TYPE_INDEX_PATH", tmp_path / ".ai_context_engine" / "memory_graph" / "indexes" / "by_type.json")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_RELATION_INDEX_PATH", tmp_path / ".ai_context_engine" / "memory_graph" / "indexes" / "by_relation.json")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_SNAPSHOT_PATH", tmp_path / ".ai_context_engine" / "memory_graph" / "snapshots" / "latest_graph_snapshot.json")

    rec = runtime_failure.record_failure(
        failure_id="build-regression",
        category="build_failure",
        title="Build regression",
        symptoms=["Module not found"],
        root_cause="missing dependency",
        solution="restore dependency",
        files_involved=["src/aictx/core_runtime.py"],
        related_commands=["pytest -q"],
    )
    assert rec["id"] == "build_regression"
    ranked = runtime_failure.rank_failure_records("module not found build")
    assert isinstance(ranked, list)


def test_runtime_graph_module_expand_after_refresh(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(core_runtime, "BASE", tmp_path)
    monkeypatch.setattr(core_runtime, "ENGINE_STATE_DIR", tmp_path / ".ai_context_engine")
    monkeypatch.setattr(core_runtime, "TASK_MEMORY_DIR", tmp_path / ".ai_context_engine" / "task_memory")
    monkeypatch.setattr(core_runtime, "FAILURE_MEMORY_DIR", tmp_path / ".ai_context_engine" / "failure_memory")
    monkeypatch.setattr(core_runtime, "FAILURE_MEMORY_INDEX_PATH", tmp_path / ".ai_context_engine" / "failure_memory" / "index.json")
    monkeypatch.setattr(core_runtime, "FAILURE_MEMORY_RECORDS_DIR", tmp_path / ".ai_context_engine" / "failure_memory" / "failures")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_DIR", tmp_path / ".ai_context_engine" / "memory_graph")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_NODES_PATH", tmp_path / ".ai_context_engine" / "memory_graph" / "nodes" / "nodes.jsonl")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_EDGES_PATH", tmp_path / ".ai_context_engine" / "memory_graph" / "edges" / "edges.jsonl")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_STATUS_PATH", tmp_path / ".ai_context_engine" / "memory_graph" / "graph_status.json")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_LABEL_INDEX_PATH", tmp_path / ".ai_context_engine" / "memory_graph" / "indexes" / "by_label.json")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_TYPE_INDEX_PATH", tmp_path / ".ai_context_engine" / "memory_graph" / "indexes" / "by_type.json")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_RELATION_INDEX_PATH", tmp_path / ".ai_context_engine" / "memory_graph" / "indexes" / "by_relation.json")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_SNAPSHOT_PATH", tmp_path / ".ai_context_engine" / "memory_graph" / "snapshots" / "latest_graph_snapshot.json")

    runtime_graph.build_memory_graph_artifacts([
        {
            "id": "r1",
            "type": "project_fact",
            "title": "Keep CLI stable",
            "summary": "Do not break subcommands",
            "path": "src/aictx/cli.py",
            "task_type": "refactoring",
            "tags": ["cli", "stability"],
            "files_involved": ["src/aictx/cli.py"],
            "source": "test",
            "project": "aictx",
        }
    ])
    matches = runtime_graph.graph_find_nodes("cli stability")
    assert isinstance(matches, list)
    if matches:
        expanded = runtime_graph.graph_expand([matches[0]["id"]], depth=1)
        assert "nodes" in expanded


def test_python_module_entrypoint_smoke(tmp_path: Path):
    repo = tmp_path / "repo"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")

    init_proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "aictx",
            "init",
            "--repo",
            str(repo),
            "--yes",
            "--no-register",
        ],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert init_proc.returncode == 0, init_proc.stderr

    boot_proc = subprocess.run(
        [sys.executable, "-m", "aictx", "boot", "--repo", str(repo)],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert boot_proc.returncode == 0, boot_proc.stderr
    payload = json.loads(boot_proc.stdout)
    assert payload["repo_bootstrap"]["status"] == "initialized"


def test_global_health_check_marks_not_initialized_repo_as_warning(tmp_path: Path, monkeypatch):
    repo = tmp_path / "plain"
    repo.mkdir()

    monkeypatch.setattr("aictx.global_metrics.PROJECTS_INDEX_PATH", tmp_path / "projects_index.json")
    monkeypatch.setattr("aictx.global_metrics.CONTEXT_SAVINGS_PATH", tmp_path / "context.json")
    monkeypatch.setattr("aictx.global_metrics.TELEMETRY_SOURCES_PATH", tmp_path / "telemetry_sources.json")
    monkeypatch.setattr("aictx.global_metrics.HEALTH_REPORT_PATH", tmp_path / "health.json")

    (tmp_path / "projects_index.json").write_text(json.dumps({"projects": [{"name": repo.name, "repo_path": str(repo), "installed_iteration": "unknown", "telemetry_dir": "unknown"}]}), encoding="utf-8")
    (tmp_path / "context.json").write_text(json.dumps({"project_breakdown": [{"name": repo.name}], "projects_with_telemetry": 0, "projects_with_memory": 0}), encoding="utf-8")
    (tmp_path / "telemetry_sources.json").write_text(json.dumps({"sources": [{"project": repo.name}]}), encoding="utf-8")

    import aictx.global_metrics as global_metrics

    health = global_metrics.run_health_check()
    project_check = next(item for item in health["checks"] if item["scope"] == repo.name and item["check"] == "project_health")
    assert project_check["status"] == "warning"
    assert project_check["consistency"]["status"] == "not_initialized"
    assert any(issue["check"] == "runtime_consistency" for issue in project_check["issues"])
