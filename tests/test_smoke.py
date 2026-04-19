from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from aictx._version import __version__ as package_version
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
import aictx.runtime_task_memory as runtime_task_memory
import aictx.runtime_metrics as runtime_metrics
import aictx.global_metrics as global_metrics
import aictx.strategy_memory as strategy_memory
import aictx.report as report_module
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


def test_agent_runtime_mentions_execution_sources_and_communication_modes():
    text = render_agent_runtime()
    assert ".ai_context_engine/metrics/execution_logs.jsonl" in text
    assert ".ai_context_engine/metrics/execution_feedback.jsonl" in text
    assert ".ai_context_engine/strategy_memory/strategies.jsonl" in text
    assert "unknown" in text
    assert "## Communication mode" in text
    assert "## Execution middleware" in text
    assert "## aictx usage rules" in text
    assert "aictx suggest --repo ." in text
    assert "aictx reflect --repo ." in text
    assert "aictx reuse --repo ." in text
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


def test_init_repo_scaffold_creates_minimal_v1_structure(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / ".ai_context_memory").mkdir(parents=True)
    (repo / ".context_metrics").mkdir(parents=True)

    init_repo_scaffold(repo, update_gitignore=False)

    assert not (repo / ".ai_context_memory").exists()
    assert not (repo / ".context_metrics").exists()
    assert (repo / ".ai_context_engine" / "metrics" / "execution_logs.jsonl").exists()
    assert (repo / ".ai_context_engine" / "metrics" / "execution_feedback.jsonl").exists()
    assert (repo / ".ai_context_engine" / "strategy_memory" / "strategies.jsonl").exists()
    assert not (repo / ".ai_context_engine" / "memory_graph").exists()
    assert not (repo / ".ai_context_engine" / "library").exists()
    assert not (repo / ".ai_context_engine" / "adapters").exists()
    assert not (repo / ".ai_context_engine" / "task_memory").exists()
    assert not (repo / ".ai_context_engine" / "failure_memory").exists()


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


def test_prepare_execution_accepts_explicit_file_tracking(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "inspect middleware files",
            "agent_id": "agent-test",
            "execution_id": "exec-files-prepare-1",
            "files_opened": ["src/aictx/middleware.py", "src/aictx/cli.py"],
            "files_reopened": ["src/aictx/middleware.py"],
        }
    )

    assert prepared["execution_observation"]["files_opened"] == ["src/aictx/middleware.py", "src/aictx/cli.py"]
    assert prepared["execution_observation"]["files_reopened"] == ["src/aictx/middleware.py"]


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
    assert finalized["strategy_persisted"]["task_id"] == "exec-finalize-1"
    strategies = [json.loads(line) for line in (repo / ".ai_context_engine" / "strategy_memory" / "strategies.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    feedback_rows = [json.loads(line) for line in (repo / ".ai_context_engine" / "metrics" / "execution_feedback.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(strategies) == 1
    assert len(feedback_rows) == 1
    assert strategies[0]["task_id"] == "exec-finalize-1"
    assert strategies[0]["task_type"] == prepared["resolved_task_type"]
    assert strategies[0]["files_used"] == []
    assert strategies[0]["entry_points"] == []
    assert strategies[0]["primary_entry_point"] is None
    assert strategies[0]["is_failure"] is False
    assert finalized["aictx_feedback"] == {
        "files_opened": 0,
        "reopened_files": 0,
        "used_strategy": False,
        "used_packet": bool(prepared["retrieval_summary"]["packet_built"]),
        "possible_redundant_exploration": False,
        "previous_strategy_reused": False,
    }
    assert feedback_rows[0]["execution_id"] == "exec-finalize-1"
    assert feedback_rows[0]["aictx_feedback"] == finalized["aictx_feedback"]
    assert "value_evidence" in finalized
    assert weekly["value_evidence"]["files_opened"] == []
    assert isinstance(finalized["value_evidence"]["execution_time_ms"], int)


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
    real_log_lines = (repo / ".ai_context_engine" / "metrics" / "execution_logs.jsonl").read_text(encoding="utf-8").splitlines()
    strategies = [json.loads(line) for line in (repo / ".ai_context_engine" / "strategy_memory" / "strategies.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert finalized["strategy_persisted"]["task_id"] == strategies[-1]["task_id"]
    assert finalized["failure_recorded"]["failure_id"].startswith("exec-failure-1_")
    assert failure_status["records_total"] == 1
    assert any("\"execution_mode\": \"skill\"" in row for row in log_lines)
    assert any("\"success\": false" in row for row in real_log_lines)
    assert strategies[-1]["is_failure"] is True
    assert strategies[-1]["success"] is False



def test_get_strategies_by_task_type_excludes_failures_by_default(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    strategy_memory.persist_strategy(
        repo,
        {
            "task_id": "success-1",
            "task_type": "feature_work",
            "entry_points": ["a.py"],
            "primary_entry_point": "a.py",
            "files_used": ["a.py"],
            "success": True,
            "is_failure": False,
            "timestamp": "2026-04-19T00:00:00Z",
        },
    )
    strategy_memory.persist_strategy(
        repo,
        {
            "task_id": "failure-1",
            "task_type": "feature_work",
            "entry_points": ["b.py"],
            "primary_entry_point": "b.py",
            "files_used": ["b.py"],
            "success": False,
            "is_failure": True,
            "timestamp": "2026-04-19T00:01:00Z",
        },
    )

    visible = strategy_memory.get_strategies_by_task_type(repo, "feature_work")
    all_rows = strategy_memory.get_strategies_by_task_type(repo, "feature_work", include_failures=True)

    assert [row["task_id"] for row in visible] == ["success-1"]
    assert [row["task_id"] for row in all_rows] == ["success-1", "failure-1"]


def test_failure_strategies_are_not_reused_by_prepare_execution(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "debug failing middleware run",
            "agent_id": "agent-test",
            "execution_id": "exec-failure-only-1",
            "declared_task_type": "debug_fix",
        }
    )
    finalize_execution(
        prepared,
        {
            "success": False,
            "result_summary": "failed run",
            "validated_learning": False,
        },
    )

    next_prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "debug failing middleware run again",
            "agent_id": "agent-test",
            "execution_id": "exec-failure-only-2",
            "declared_task_type": "debug_fix",
        }
    )

    assert "execution_hint" not in next_prepared


def test_prepare_execution_includes_execution_hint_from_latest_strategy(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    first = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "document strategy memory behavior",
            "agent_id": "agent-test",
            "execution_id": "exec-hint-1",
        }
    )
    finalize_execution(first, {"success": True, "result_summary": "ok", "validated_learning": True})

    second = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "another feature task",
            "agent_id": "agent-test",
            "execution_id": "exec-hint-2",
            "declared_task_type": first["resolved_task_type"],
        }
    )

    assert second["execution_hint"] == {
        "entry_points": [],
        "files_used": [],
        "based_on": "previous_successful_execution",
    }
    assert second["execution_observation"]["used_strategy"] is True



def test_prepare_execution_omits_execution_hint_when_no_strategy_exists(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "brand new task without history",
            "agent_id": "agent-test",
            "execution_id": "exec-no-hint-1",
        }
    )

    assert "execution_hint" not in prepared
    assert prepared["execution_observation"]["used_strategy"] is False


def test_strategy_memory_load_and_filter(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "document strategy memory behavior",
            "agent_id": "agent-test",
            "execution_id": "exec-strategy-1",
        }
    )
    finalize_execution(prepared, {"success": True, "result_summary": "ok", "validated_learning": True})

    all_rows = strategy_memory.load_strategies(repo)
    filtered = strategy_memory.get_strategies_by_task_type(repo, prepared["resolved_task_type"])
    assert len(all_rows) == 1
    assert len(filtered) == 1
    assert filtered[0]["task_id"] == "exec-strategy-1"


def test_finalize_execution_writes_real_execution_log(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "inspect middleware behavior",
            "agent_id": "agent-test",
            "execution_id": "exec-real-log-1",
            "files_opened": ["src/aictx/middleware.py", "src/aictx/cli.py"],
            "files_reopened": ["src/aictx/middleware.py"],
        }
    )

    finalized = finalize_execution(
        prepared,
        {
            "success": True,
            "result_summary": "ok",
            "validated_learning": True,
        },
    )

    rows = [json.loads(line) for line in (repo / ".ai_context_engine" / "metrics" / "execution_logs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    row = rows[0]
    assert row["task_id"]
    assert row["task_type"] == prepared["resolved_task_type"]
    assert row["files_opened"] == ["src/aictx/middleware.py", "src/aictx/cli.py"]
    assert row["files_reopened"] == ["src/aictx/middleware.py"]
    assert row["success"] is True
    assert row["used_packet"] == bool(prepared["retrieval_summary"]["packet_built"])
    assert isinstance(row["execution_time_ms"], int)
    assert finalized["value_evidence"]["used_packet"] == row["used_packet"]
    assert finalized["value_evidence"]["used_strategy"] is False
    assert finalized["aictx_feedback"]["files_opened"] == 2
    assert finalized["aictx_feedback"]["reopened_files"] == 1

    feedback_rows = [json.loads(line) for line in (repo / ".ai_context_engine" / "metrics" / "execution_feedback.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert feedback_rows[-1]["aictx_feedback"]["files_opened"] == 2
    assert feedback_rows[-1]["aictx_feedback"]["reopened_files"] == 1

    strategies = [json.loads(line) for line in (repo / ".ai_context_engine" / "strategy_memory" / "strategies.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert strategies[-1]["files_used"] == ["src/aictx/middleware.py", "src/aictx/cli.py"]
    assert strategies[-1]["entry_points"] == ["src/aictx/middleware.py", "src/aictx/cli.py"]
    assert strategies[-1]["primary_entry_point"] == "src/aictx/middleware.py"


def test_cli_execution_prepare_and_finalize_round_trip(tmp_path: Path, monkeypatch, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    parser = cli.build_parser()

    prepare_args = parser.parse_args(
        [
            "internal",
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
            "--files-opened",
            "src/aictx/middleware.py",
            "src/aictx/cli.py",
            "--files-reopened",
            "src/aictx/middleware.py",
        ]
    )
    assert prepare_args.func(prepare_args) == 0
    prepared_output = json.loads(capsys.readouterr().out)
    prepared_path = repo / "prepared_execution.json"
    prepared_path.write_text(json.dumps(prepared_output), encoding="utf-8")

    finalize_args = parser.parse_args(
        [
            "internal",
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
    assert finalized_output["aictx_feedback"]["files_opened"] == 2
    assert finalized_output["aictx_feedback"]["reopened_files"] == 1


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
    assert state["installed_version"] == package_version
    assert state["engine_capability_version"] >= 1
    assert state["installed_iteration"] == state["engine_capability_version"]
    assert state["engine_role"] == "initialized_repo_runtime"
    assert state["supports"]["packet_construction"] is True
    assert state["adapter_runtime_enabled"] is True
    assert state["runner_integration_status"] == "native_ready"
    assert state["auto_execution_entrypoint"] == "aictx internal run-execution"
    assert state["runner_native_integrations"]["codex"]["status"] == "native_hardened"
    assert state["runner_native_integrations"]["claude"]["status"] == "native_hardened"
    assert state["communication_layer"] == "disabled"
    assert (repo / ".ai_context_engine" / "metrics" / "execution_logs.jsonl").exists()
    assert (repo / ".ai_context_engine" / "metrics" / "execution_feedback.jsonl").exists()
    assert (repo / ".ai_context_engine" / "strategy_memory" / "strategies.jsonl").exists()
    assert (repo / ".ai_context_engine" / "cost" / "optimization_history.jsonl").exists()
    assert (repo / "AGENTS.override.md").exists()
    assert (repo / "CLAUDE.md").exists()
    assert (repo / ".claude" / "settings.json").exists()
    assert (repo / ".claude" / "hooks" / "aictx_session_start.py").exists()
    assert (repo / ".claude" / "hooks" / "aictx_pre_tool_use.py").exists()


def test_cli_suggest_returns_empty_json_without_history(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    parser = cli.build_parser()
    args = parser.parse_args(["suggest", "--repo", str(repo)])
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "suggested_entry_points": [],
        "suggested_files": [],
        "source": "none",
    }



def test_cli_reuse_returns_latest_strategy(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    first = prepare_execution({
        "repo_root": str(repo),
        "user_request": "document strategy behavior",
        "agent_id": "agent-test",
        "execution_id": "exec-reuse-1",
        "declared_task_type": "feature_work",
    })
    finalize_execution(first, {"success": True, "result_summary": "ok", "validated_learning": True})

    parser = cli.build_parser()
    args = parser.parse_args(["reuse", "--repo", str(repo), "--task-type", "feature_work"])
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["task_type"] == "feature_work"
    assert payload["entry_points"] == []
    assert payload["files_used"] == []
    assert payload["source"] == "previous_successful_execution"



def test_cli_suggest_uses_latest_strategy(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    first = prepare_execution({
        "repo_root": str(repo),
        "user_request": "document strategy behavior",
        "agent_id": "agent-test",
        "execution_id": "exec-suggest-1",
        "declared_task_type": "feature_work",
    })
    finalize_execution(first, {"success": True, "result_summary": "ok", "validated_learning": True})

    parser = cli.build_parser()
    args = parser.parse_args(["suggest", "--repo", str(repo), "--task-type", "feature_work"])
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "suggested_entry_points": [],
        "suggested_files": [],
        "source": "strategy_memory",
    }



def test_cli_reflect_detects_looping_on_same_files(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    log_path = repo / ".ai_context_engine" / "metrics" / "execution_logs.jsonl"
    log_path.write_text(json.dumps({
        "task_id": "t1",
        "timestamp": "2026-04-19T00:00:00Z",
        "task_type": "feature_work",
        "files_opened": ["a.py", "b.py"],
        "files_reopened": ["a.py", "b.py", "c.py"],
        "execution_time_ms": 100,
        "success": True,
        "used_packet": False,
    }) + "\n", encoding="utf-8")
    parser = cli.build_parser()
    args = parser.parse_args(["reflect", "--repo", str(repo)])
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "reopened_files": ["a.py", "b.py", "c.py"],
        "possible_issue": "looping_on_same_files",
    }



def test_cli_reflect_detects_too_much_exploration(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    log_path = repo / ".ai_context_engine" / "metrics" / "execution_logs.jsonl"
    log_path.write_text(json.dumps({
        "task_id": "t1",
        "timestamp": "2026-04-19T00:00:00Z",
        "task_type": "feature_work",
        "files_opened": ["1.py", "2.py", "3.py", "4.py", "5.py", "6.py", "7.py", "8.py", "9.py"],
        "files_reopened": [],
        "execution_time_ms": 100,
        "success": True,
        "used_packet": False,
    }) + "\n", encoding="utf-8")
    parser = cli.build_parser()
    args = parser.parse_args(["reflect", "--repo", str(repo)])
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "reopened_files": [],
        "possible_issue": "too_much_exploration",
    }



def test_cli_reflect_returns_none_without_history(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    parser = cli.build_parser()
    args = parser.parse_args(["reflect", "--repo", str(repo)])
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "reopened_files": [],
        "possible_issue": "none",
    }


def test_report_real_usage_returns_empty_metrics_without_history(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    parser = cli.build_parser()
    args = parser.parse_args(["report", "real-usage", "--repo", str(repo)])
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "total_executions": 0,
        "avg_execution_time_ms": None,
        "avg_files_opened": None,
        "avg_reopened_files": None,
        "strategy_usage": 0,
        "packet_usage": 0,
        "redundant_exploration_cases": 0,
    }



def test_report_real_usage_aggregates_real_logs_and_feedback(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    metrics_dir = repo / ".ai_context_engine" / "metrics"
    (metrics_dir / "execution_logs.jsonl").write_text(
        "\n".join([
            json.dumps({
                "task_id": "t1",
                "timestamp": "2026-04-19T00:00:00Z",
                "task_type": "feature_work",
                "files_opened": ["a.py", "b.py"],
                "files_reopened": ["a.py"],
                "execution_time_ms": 1000,
                "success": True,
                "used_packet": True,
            }),
            json.dumps({
                "task_id": "t2",
                "timestamp": "2026-04-19T00:05:00Z",
                "task_type": "feature_work",
                "files_opened": ["c.py", "d.py", "e.py", "f.py"],
                "files_reopened": [],
                "execution_time_ms": 2000,
                "success": True,
                "used_packet": False,
            }),
        ]) + "\n",
        encoding="utf-8",
    )
    (metrics_dir / "execution_feedback.jsonl").write_text(
        "\n".join([
            json.dumps({
                "task_id": "t1",
                "execution_id": "e1",
                "timestamp": "2026-04-19T00:00:01Z",
                "aictx_feedback": {
                    "files_opened": 2,
                    "reopened_files": 1,
                    "used_strategy": True,
                    "used_packet": True,
                    "possible_redundant_exploration": True,
                    "previous_strategy_reused": True,
                },
            }),
            json.dumps({
                "task_id": "t2",
                "execution_id": "e2",
                "timestamp": "2026-04-19T00:05:01Z",
                "aictx_feedback": {
                    "files_opened": 4,
                    "reopened_files": 0,
                    "used_strategy": False,
                    "used_packet": True,
                    "possible_redundant_exploration": False,
                    "previous_strategy_reused": False,
                },
            }),
        ]) + "\n",
        encoding="utf-8",
    )
    parser = cli.build_parser()
    args = parser.parse_args(["report", "real-usage", "--repo", str(repo)])
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "total_executions": 2,
        "avg_execution_time_ms": 1500,
        "avg_files_opened": 3,
        "avg_reopened_files": 0,
        "strategy_usage": 1,
        "packet_usage": 2,
        "redundant_exploration_cases": 1,
    }



def test_report_module_build_real_usage_report(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    payload = report_module.build_real_usage_report(repo)
    assert payload["total_executions"] == 0
    assert payload["avg_execution_time_ms"] is None


def test_cli_main_help_shows_simple_surface_only():
    parser = cli.build_parser()
    help_text = parser.format_help()
    assert "install" in help_text
    assert "init" in help_text
    assert "suggest" in help_text
    assert "reflect" in help_text
    assert "reuse" in help_text
    assert "report" in help_text
    assert "benchmark" not in help_text
    assert "workspace" not in help_text
    assert "boot" not in help_text
    assert "memory-graph" not in help_text


def test_should_render_banner_defaults_to_tty_when_not_suppressed():
    assert cli.should_render_banner(["install", "--yes"], stdout_is_tty=True) is True


def test_should_render_banner_respects_no_banner_json_and_help():
    assert cli.should_render_banner(["--no-banner", "init"], stdout_is_tty=True) is False
    assert cli.should_render_banner(["internal", "run-execution", "--json"], stdout_is_tty=True) is False
    assert cli.should_render_banner(["install", "--help"], stdout_is_tty=True) is False
    assert cli.should_render_banner(["--banner", "install", "--help"], stdout_is_tty=True) is True
    assert cli.should_render_banner(["internal", "workspace", "list"], stdout_is_tty=False) is False


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


def test_runtime_metrics_truthfulness_status_rules():
    low = runtime_metrics.apply_truthfulness_guardrails({"tasks_sampled": 0})
    assert low["evidence_status"] == "unknown"
    assert low["measurement_basis"] == "execution_logs"
    assert low["confidence"] == "low"

    observed = runtime_metrics.apply_truthfulness_guardrails({"tasks_sampled": 25, "repeated_tasks": 3, "phase_events_sampled": 12})
    assert observed["evidence_status"] == "unknown"
    assert observed["measurement_basis"] == "execution_logs"
    assert observed["metrics"]["observed"]["tasks_sampled"] == 25
    assert observed["metrics"]["observed"]["repeated_tasks"] == 3


def test_global_aggregation_excludes_insufficient_data():
    rows = [
        {"telemetry": {"context_range": [0.1, 0.2], "context_point": 0.15, "tasks_sampled": 30, "evidence_status": "estimated"}},
        {"telemetry": {"context_range": [0.8, 0.9], "context_point": 0.85, "tasks_sampled": 80, "evidence_status": "insufficient_data"}},
    ]
    context = global_metrics.aggregate_range(rows, "context_range")
    assert context["projects_with_telemetry"] == 1
    assert context["projects_excluded_insufficient_data"] == 1
    assert context["range"] == [0.1, 0.2]


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
    assert "aictx suggest --repo ." in (repo / "AGENTS.override.md").read_text(encoding="utf-8")
    assert "aictx reflect --repo ." in (repo / "AGENTS.override.md").read_text(encoding="utf-8")
    assert "aictx reuse --repo ." in (repo / "AGENTS.override.md").read_text(encoding="utf-8")
    assert "aictx suggest --repo ." in (repo / "CLAUDE.md").read_text(encoding="utf-8")


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

    assert prepared["communication_policy"]["layer"] == "disabled"
    assert boot["consistency_checks"]["status"] in {"warning", "not_initialized"}
    assert prepared["consistency_checks"]["status"] in {"warning", "not_initialized"}


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
        [sys.executable, "-m", "aictx", "internal", "boot", "--repo", str(repo)],
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
        [sys.executable, "-m", "aictx", "internal", "packet", "--task", "debug failing integration"],
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
            "internal",
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
            "internal",
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
    assert project_check["consistency"]["status"] in {"warning", "not_initialized"}


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
    assert packet["repo_scope"] == []
    assert packet["relevant_paths"] == []
    assert packet["architecture_rules"] == []
    assert packet["architecture_decisions"] == []
    assert isinstance(packet["task_type_resolution"]["ambiguous"], bool)
    assert packet["context"] == {}
    assert "selection_report" not in packet
    assert "communication_policy" not in packet


def test_rank_records_returns_score_breakdown(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    matches = runtime_memory.rank_records("workflow contract")
    assert isinstance(matches, list)
    if matches:
        assert "score_breakdown" in matches[0]
        assert "total" in matches[0]["score_breakdown"]


def test_finalize_execution_feedback_marks_strategy_reuse(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    first = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "document strategy memory behavior",
            "agent_id": "agent-test",
            "execution_id": "exec-feedback-1",
            "declared_task_type": "feature_work",
        }
    )
    finalize_execution(first, {"success": True, "result_summary": "ok", "validated_learning": True})

    second = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "follow similar feature task",
            "agent_id": "agent-test",
            "execution_id": "exec-feedback-2",
            "declared_task_type": "feature_work",
        }
    )
    finalized = finalize_execution(second, {"success": True, "result_summary": "ok", "validated_learning": False})

    assert finalized["aictx_feedback"]["used_strategy"] is True
    assert finalized["aictx_feedback"]["previous_strategy_reused"] is True
    assert finalized["aictx_feedback"]["used_packet"] in {True, False}


def test_repeated_task_reports_value_evidence(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    first = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "review middleware behavior",
            "agent_id": "agent-test",
            "execution_id": "repeat-1",
        }
    )
    finalize_execution(first, {"success": True, "result_summary": "first", "validated_learning": True})

    second = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "review middleware behavior",
            "agent_id": "agent-test",
            "execution_id": "repeat-2",
        }
    )
    finalized = finalize_execution(second, {"success": True, "result_summary": "second", "validated_learning": False})

    weekly = read_json(repo / ".ai_context_engine" / "metrics" / "weekly_summary.json", {})
    assert finalized["value_evidence"]["repeated_context_request"] is True
    assert weekly["value_evidence"]["repeated_tasks_observed"] >= 1
    assert weekly["value_evidence"]["last_used_packet"] in {True, False}


def test_scaffold_status_files_include_version_contract(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    state = read_json(repo / ".ai_context_engine" / "state.json", {})

    assert state["installed_version"] == package_version
    assert state["engine_capability_version"] >= 1
    assert state["installed_iteration"] == state["engine_capability_version"]


def test_task_memory_writes_only_canonical_buckets(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(core_runtime, "BASE", tmp_path)
    monkeypatch.setattr(core_runtime, "ENGINE_STATE_DIR", tmp_path / ".ai_context_engine")
    monkeypatch.setattr(core_runtime, "TASK_MEMORY_DIR", tmp_path / ".ai_context_engine" / "task_memory")
    monkeypatch.setattr(core_runtime, "TASK_MEMORY_STATUS_PATH", tmp_path / ".ai_context_engine" / "task_memory" / "task_memory_status.json")
    monkeypatch.setattr(core_runtime, "TASK_MEMORY_TAXONOMY_PATH", tmp_path / ".ai_context_engine" / "task_memory" / "task_taxonomy.json")
    monkeypatch.setattr(core_runtime, "TASK_MEMORY_RULES_PATH", tmp_path / ".ai_context_engine" / "task_memory" / "task_resolution_rules.md")
    monkeypatch.setattr(core_runtime, "TASK_MEMORY_HISTORY_PATH", tmp_path / ".ai_context_engine" / "task_memory" / "task_memory_history.jsonl")

    runtime_task_memory.build_task_memory_artifacts([
        {"id": "r1", "type": "task_pattern", "task_type": "testing", "title": "Run tests", "summary": "Use pytest", "project": "aictx"}
    ])
    assert (tmp_path / ".ai_context_engine" / "task_memory" / "testing" / "summary.json").exists()
    assert not (tmp_path / ".ai_context_engine" / "task_memory" / "tests" / "summary.json").exists()
    assert not (tmp_path / ".ai_context_engine" / "task_memory" / "general" / "summary.json").exists()
    assert runtime_task_memory.category_summary_path("tests").name == "summary.json"


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
        [sys.executable, "-m", "aictx", "internal", "boot", "--repo", str(repo)],
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


def test_global_metrics_reads_legacy_iteration_only_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / ".ai_context_engine").mkdir(parents=True)
    (repo / "AGENTS.md").write_text("ai_context_engine enabled\n", encoding="utf-8")
    (repo / ".ai_context_engine" / "state.json").write_text(json.dumps({"installed_iteration": 9}), encoding="utf-8")

    import aictx.global_metrics as global_metrics

    assert global_metrics.infer_installed_version(repo) == "unknown"
    assert global_metrics.infer_engine_capability_version(repo) == 9
