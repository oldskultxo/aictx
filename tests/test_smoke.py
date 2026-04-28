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
import aictx.runtime_cost as runtime_cost
import aictx.runtime_failure as runtime_failure
import aictx.runtime_graph as runtime_graph
import aictx.runtime_task_memory as runtime_task_memory
import aictx.runtime_metrics as runtime_metrics
import aictx.strategy_memory as strategy_memory
import aictx.report as report_module
from aictx.area_memory import derive_area_id
from aictx.failure_memory import load_failures, lookup_failures
from aictx.runtime_capture import build_capture
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
    CLAUDE_GITIGNORE_COMMENT,
    CLAUDE_DIR_GITIGNORE_LINE,
    CLAUDE_MD_GITIGNORE_LINE,
    install_codex_native_integration,
    install_repo_runner_integrations,
    render_claude_md_block,
    render_user_prompt_submit_script,
)
from aictx.scaffold import TEMPLATES_DIR, ensure_repo_memory_sources, ensure_repo_user_preferences, init_repo_scaffold
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


def test_root_prefs_path_points_to_canonical_repo_local_preferences():
    assert core_runtime.ROOT_PREFS_PATH.as_posix().endswith(".aictx/memory/user_preferences.json")


def test_init_repo_scaffold_seeds_repo_preferences_from_template(tmp_path: Path):
    repo = tmp_path / "repo"
    created = init_repo_scaffold(repo, update_gitignore=False)
    prefs_path = repo / ".aictx" / "memory" / "user_preferences.json"
    assert str(prefs_path) in created
    assert json.loads(prefs_path.read_text(encoding="utf-8")) == json.loads((TEMPLATES_DIR / "user_preferences.json").read_text(encoding="utf-8"))


def test_ensure_repo_user_preferences_merges_legacy_root_without_losing_canonical_overrides(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / ".aictx" / "memory").mkdir(parents=True, exist_ok=True)
    (repo / "user_preferences.json").write_text(json.dumps({
        "updated_at": "2026-04-16",
        "profile": {"preferred_language": "es"},
        "communication": {"layer": "enabled"},
    }), encoding="utf-8")
    (repo / ".aictx" / "memory" / "user_preferences.json").write_text(json.dumps({
        "communication": {"layer": "disabled", "mode": "caveman_full"},
    }), encoding="utf-8")

    path = ensure_repo_user_preferences(repo)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["updated_at"] == "2026-04-16"
    assert payload["profile"]["preferred_language"] == "es"
    assert payload["communication"]["layer"] == "disabled"
    assert payload["communication"]["mode"] == "caveman_full"


def test_install_global_adapters_creates_codex_and_claude(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("aictx.adapters.ENGINE_HOME", tmp_path / ".aictx")
    monkeypatch.setattr("aictx.adapters.GLOBAL_ADAPTERS_DIR", (tmp_path / ".aictx" / "adapters"))
    monkeypatch.setattr("aictx.adapters.GLOBAL_ADAPTERS_REGISTRY_PATH", (tmp_path / ".aictx" / "adapters" / "registry.json"))
    monkeypatch.setattr("aictx.adapters.GLOBAL_ADAPTERS_BIN_DIR", (tmp_path / ".aictx" / "adapters" / "bin"))
    monkeypatch.setattr("aictx.adapters.GLOBAL_ADAPTERS_INSTALL_STATUS_PATH", (tmp_path / ".aictx" / "adapters" / "install_status.json"))
    created = install_global_adapters()
    assert any(path.name == "codex.json" for path in created)
    assert any(path.name == "claude.json" for path in created)
    assert any(path.name == "aictx-codex-auto" for path in created)
    install_status = read_json(tmp_path / ".aictx" / "adapters" / "install_status.json", {})
    assert install_status["status"] == "wrapper_ready"
    assert install_status["runtime_entrypoint"] == "aictx internal run-execution"


def test_agent_runtime_mentions_execution_sources_and_communication_modes():
    text = render_agent_runtime()
    assert ".aictx/metrics/execution_logs.jsonl" in text
    assert ".aictx/metrics/execution_feedback.jsonl" in text
    assert ".aictx/strategy_memory/strategies.jsonl" in text
    assert "unknown" in text
    assert "## Communication mode" in text
    assert "## Execution middleware" in text
    assert "## aictx usage rules" in text
    assert "aictx suggest --repo ." in text
    assert "aictx reflect --repo ." in text
    assert "aictx reuse --repo ." in text
    assert "PYTHONPATH=src .venv/bin/python -m aictx" in text
    assert "enabled` or `disabled" in text
    assert "caveman_lite" in text
    assert "caveman_full" in text
    assert "caveman_ultra" in text
    assert "agent_summary_text" in text
    assert "startup_banner_text" in text
    assert "current user language" in text
    assert "never invent data" in text
    assert "AICTX summary unavailable" in text
    repo_block = render_repo_agents_block()
    assert "agent_summary_text" in repo_block
    assert "startup_banner_text" in repo_block
    assert "current user language" in repo_block
    assert "AICTX summary unavailable" in repo_block
    assert "PYTHONPATH=src .venv/bin/python -m aictx" in repo_block
    claude_block = render_claude_md_block()
    assert "agent_summary_text" in claude_block
    assert "startup_banner_text" in claude_block
    assert "current user language" in claude_block
    assert "AICTX summary unavailable" in claude_block
    assert "PYTHONPATH=src .venv/bin/python -m aictx" in claude_block
    prompt_hook = render_user_prompt_submit_script()
    assert "localized to the current user language" in prompt_hook
    assert "startup_banner_text" in prompt_hook
    assert "AICTX summary unavailable" in prompt_hook
    assert "PYTHONPATH=src .venv/bin/python -m aictx" in prompt_hook


def test_prepare_and_finalize_expose_runtime_text_localization_policies(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "explica el cambio",
            "agent_id": "codex-cli",
            "adapter_id": "codex-cli",
            "execution_id": "exec-policy",
            "declared_task_type": "architecture",
            "execution_mode": "plain",
        }
    )

    runtime_policy = prepared["runtime_text_policy"]
    startup_policy = prepared["startup_banner_policy"]
    assert runtime_policy["translate_to_user_language"] is True
    assert runtime_policy["allow_enrichment"] is True
    assert runtime_policy["preserve_facts"] is True
    assert startup_policy["render_in_user_language"] is True
    assert startup_policy["allow_language_adaptation"] is True
    assert startup_policy["allow_fact_enrichment"] is False
    assert startup_policy["allow_structure_changes"] is False
    assert startup_policy["preserve_technical_tokens"] is True
    assert startup_policy["do_not_invent"] is True

    finalized = finalize_execution(
        prepared,
        {
            "success": True,
            "result_summary": "done",
            "validated_learning": False,
            "decisions": [],
            "semantic_repo": [],
        },
    )
    summary_policy = finalized["agent_summary_policy"]
    assert summary_policy["append_to_final_response"] is True
    assert summary_policy["render_in_user_language"] is True
    assert summary_policy["allow_language_adaptation"] is True
    assert summary_policy["allow_fact_enrichment"] is False
    assert summary_policy["allow_enrichment"] is False
    assert summary_policy["preserve_facts"] is True
    assert summary_policy["do_not_invent"] is True


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
    (repo / ".aictx_memory").mkdir(parents=True)
    (repo / ".context_metrics").mkdir(parents=True)
    (repo / ".aictx" / "metrics").mkdir(parents=True)
    (repo / ".aictx" / "strategy_memory").mkdir(parents=True)
    (repo / ".aictx" / "metrics" / "execution_logs.jsonl").write_text('{"keep": "log"}\n', encoding="utf-8")
    (repo / ".aictx" / "metrics" / "execution_feedback.jsonl").write_text('{"keep": "feedback"}\n', encoding="utf-8")
    (repo / ".aictx" / "strategy_memory" / "strategies.jsonl").write_text('{"keep": "strategy"}\n', encoding="utf-8")

    init_repo_scaffold(repo, update_gitignore=False)

    assert (repo / ".aictx_memory").exists()
    assert (repo / ".context_metrics").exists()
    assert (repo / ".aictx" / "metrics" / "execution_logs.jsonl").exists()
    assert (repo / ".aictx" / "metrics" / "execution_feedback.jsonl").exists()
    assert (repo / ".aictx" / "strategy_memory" / "strategies.jsonl").exists()
    assert (repo / ".aictx" / "metrics" / "execution_logs.jsonl").read_text(encoding="utf-8") == '{"keep": "log"}\n'
    assert (repo / ".aictx" / "metrics" / "execution_feedback.jsonl").read_text(encoding="utf-8") == '{"keep": "feedback"}\n'
    assert (repo / ".aictx" / "strategy_memory" / "strategies.jsonl").read_text(encoding="utf-8") == '{"keep": "strategy"}\n'
    assert not (repo / ".aictx" / "memory_graph").exists()
    assert not (repo / ".aictx" / "library").exists()
    assert not (repo / ".aictx" / "adapters").exists()
    assert not (repo / ".aictx" / "task_memory").exists()
    assert (repo / ".aictx" / "failure_memory" / "failure_patterns.jsonl").exists()
    assert (repo / ".aictx" / "memory" / "source" / "index.json").exists()
    assert (repo / ".aictx" / "memory" / "source" / "symptoms.json").exists()
    assert (repo / ".aictx" / "memory" / "source" / "protocol.md").exists()
    assert (repo / ".aictx" / "memory" / "source" / "common" / "user_working_preferences.md").exists()
    assert (repo / ".aictx" / "memory" / "source" / "projects" / repo.name / "overview.md").exists()


def test_ensure_repo_memory_sources_imports_legacy_source_files(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "common").mkdir(parents=True)
    (repo / "projects" / "demo").mkdir(parents=True)
    (repo / "common" / "user_working_preferences.md").write_text("# legacy common\n", encoding="utf-8")
    (repo / "projects" / "demo" / "decisions.md").write_text("# legacy decisions\n", encoding="utf-8")
    (repo / "index.json").write_text(json.dumps({"version": 1, "common": ["common/user_working_preferences.md"]}), encoding="utf-8")
    (repo / "symptoms.json").write_text(json.dumps({"version": 1, "symptoms": {"broken": ["projects/demo/decisions.md"]}}), encoding="utf-8")
    (repo / "protocol.md").write_text("# legacy protocol\n", encoding="utf-8")

    created = ensure_repo_memory_sources(repo)

    assert str(repo / ".aictx" / "memory" / "source" / "common" / "user_working_preferences.md") in created
    assert (repo / ".aictx" / "memory" / "source" / "projects" / "demo" / "decisions.md").read_text(encoding="utf-8") == "# legacy decisions\n"
    index_payload = json.loads((repo / ".aictx" / "memory" / "source" / "index.json").read_text(encoding="utf-8"))
    assert index_payload["common"] == [".aictx/memory/source/common/user_working_preferences.md"]
    symptoms_payload = json.loads((repo / ".aictx" / "memory" / "source" / "symptoms.json").read_text(encoding="utf-8"))
    assert symptoms_payload["symptoms"]["broken"] == [".aictx/memory/source/projects/demo/decisions.md"]


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

    weekly = read_json(repo / ".aictx" / "metrics" / "weekly_summary.json", {})
    workflow_rows = (repo / ".aictx" / "memory" / "workflow_learnings.jsonl").read_text(encoding="utf-8").splitlines()
    status = read_json(repo / ".aictx" / "metrics" / "agent_execution_status.json", {})
    assert finalized["learning_persisted"]["record_id"] == "execution_learning::exec-finalize-1"
    assert weekly["tasks_sampled"] >= 1
    assert status["last_execution_mode"] == "plain"
    assert any("exec-finalize-1" in row for row in workflow_rows)
    assert finalized["strategy_persisted"]["task_id"] == "exec-finalize-1"
    strategies = [json.loads(line) for line in (repo / ".aictx" / "strategy_memory" / "strategies.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    feedback_rows = [json.loads(line) for line in (repo / ".aictx" / "metrics" / "execution_feedback.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
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
        "commands_observed": 0,
        "tests_observed": 0,
    }
    assert feedback_rows[0]["execution_id"] == "exec-finalize-1"
    assert feedback_rows[0]["aictx_feedback"] == finalized["aictx_feedback"]
    assert "value_evidence" in finalized
    assert weekly["value_evidence"]["files_opened"] == []
    assert isinstance(finalized["value_evidence"]["execution_time_ms"], int)


def test_finalize_execution_failure_persists_failure_strategy(tmp_path: Path):
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

    log_lines = (repo / ".aictx" / "metrics" / "agent_execution_log.jsonl").read_text(encoding="utf-8").splitlines()
    real_log_lines = (repo / ".aictx" / "metrics" / "execution_logs.jsonl").read_text(encoding="utf-8").splitlines()
    strategies = [json.loads(line) for line in (repo / ".aictx" / "strategy_memory" / "strategies.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert finalized["strategy_persisted"]["task_id"] == strategies[-1]["task_id"]
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

    assert second["execution_hint"]["entry_points"] == []
    assert second["execution_hint"]["primary_entry_point"] is None
    assert second["execution_hint"]["files_used"] == []
    assert second["execution_hint"]["based_on"] == "previous_successful_execution"
    assert second["execution_hint"]["selection_reason"]
    assert isinstance(second["execution_hint"]["matched_signals"], list)
    assert {
        "entry_points": [],
        "primary_entry_point": None,
        "files_used": [],
        "based_on": "previous_successful_execution",
    }.items() <= second["execution_hint"].items()
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


def test_strategy_selection_prefers_file_overlap_over_newer_recency(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    strategy_memory.persist_strategy(
        repo,
        {
            "task_id": "older-overlap",
            "task_type": "feature_work",
            "entry_points": ["src/aictx/runner_integrations.py"],
            "primary_entry_point": "src/aictx/runner_integrations.py",
            "files_used": ["src/aictx/runner_integrations.py"],
            "success": True,
            "is_failure": False,
            "timestamp": "2026-04-19T00:00:00Z",
        },
    )
    strategy_memory.persist_strategy(
        repo,
        {
            "task_id": "newer-no-overlap",
            "task_type": "feature_work",
            "entry_points": ["src/aictx/cli.py"],
            "primary_entry_point": "src/aictx/cli.py",
            "files_used": ["src/aictx/cli.py"],
            "success": True,
            "is_failure": False,
            "timestamp": "2026-04-19T00:01:00Z",
        },
    )

    selected = strategy_memory.select_strategy(repo, "feature_work", files=["src/aictx/runner_integrations.py"])

    assert selected is not None
    assert selected["task_id"] == "older-overlap"
    assert "file_overlap:src/aictx/runner_integrations.py" in selected["selection_reason"]


def test_strategy_selection_uses_prompt_primary_command_test_and_area_signals(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    strategy_memory.persist_strategy(
        repo,
        {
            "task_id": "generic-new",
            "task_text": "generic feature work",
            "task_type": "feature_work",
            "area_id": "src/other",
            "entry_points": ["src/other/tool.py"],
            "primary_entry_point": "src/other/tool.py",
            "files_used": ["src/other/tool.py"],
            "commands_executed": ["python -m pytest tests/test_other.py"],
            "tests_executed": ["tests/test_other.py"],
            "success": True,
            "is_failure": False,
            "timestamp": "2026-04-19T00:01:00Z",
        },
    )
    strategy_memory.persist_strategy(
        repo,
        {
            "task_id": "specific-old",
            "task_text": "improve Claude settings merge safety",
            "task_type": "feature_work",
            "area_id": "src/aictx",
            "entry_points": ["src/aictx/runner_integrations.py"],
            "primary_entry_point": "src/aictx/runner_integrations.py",
            "files_used": ["src/aictx/runner_integrations.py"],
            "commands_executed": ["python -m pytest tests/test_smoke.py"],
            "tests_executed": ["tests/test_smoke.py"],
            "success": True,
            "is_failure": False,
            "timestamp": "2026-04-19T00:00:00Z",
        },
    )

    selected = strategy_memory.select_strategy(
        repo,
        "feature_work",
        files=["src/aictx/runner_integrations.py"],
        primary_entry_point="src/aictx/runner_integrations.py",
        request_text="improve Claude settings merge safety",
        commands=["python -m pytest tests/test_smoke.py"],
        tests=["tests/test_smoke.py"],
        area_id="src/aictx",
    )

    assert selected is not None
    assert selected["task_id"] == "specific-old"
    assert selected["similarity_breakdown"]["primary_entry_point"] == 5000
    assert selected["related_commands"] == ["python -m pytest tests/test_smoke.py"]
    assert selected["related_tests"] == ["tests/test_smoke.py"]


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

    rows = [json.loads(line) for line in (repo / ".aictx" / "metrics" / "execution_logs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    row = rows[0]
    assert row["task_id"]
    assert row["prepared_task_type"] == prepared["resolved_task_type"]
    assert row["task_type"] == finalized["effective_task_type"]
    assert row["files_opened"] == ["src/aictx/middleware.py", "src/aictx/cli.py"]
    assert row["files_reopened"] == ["src/aictx/middleware.py"]
    assert row["success"] is True
    assert row["used_packet"] == bool(prepared["retrieval_summary"]["packet_built"])
    assert isinstance(row["execution_time_ms"], int)
    assert finalized["value_evidence"]["used_packet"] == row["used_packet"]
    assert finalized["value_evidence"]["used_strategy"] is False
    assert finalized["aictx_feedback"]["files_opened"] == 2
    assert finalized["aictx_feedback"]["reopened_files"] == 1

    feedback_rows = [json.loads(line) for line in (repo / ".aictx" / "metrics" / "execution_feedback.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert feedback_rows[-1]["aictx_feedback"]["files_opened"] == 2
    assert feedback_rows[-1]["aictx_feedback"]["reopened_files"] == 1

    strategies = [json.loads(line) for line in (repo / ".aictx" / "strategy_memory" / "strategies.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
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


def test_prepare_execution_accepts_legacy_agent_and_task_aliases(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "task": "review middleware behavior",
            "agent": "agent-test",
            "execution_id": "exec-legacy-aliases",
            "status": "started",
        }
    )

    assert prepared["envelope"]["user_request"] == "review middleware behavior"
    assert prepared["envelope"]["agent_id"] == "agent-test"
    assert prepared["envelope"]["execution_id"] == "exec-legacy-aliases"


def test_persist_repo_communication_mode_disabled(tmp_path: Path):
    repo = tmp_path / "repo"
    prefs_path = repo / ".aictx" / "memory" / "user_preferences.json"
    prefs_path.parent.mkdir(parents=True)
    prefs_path.write_text((TEMPLATES_DIR / "user_preferences.json").read_text(encoding="utf-8"), encoding="utf-8")

    cli.persist_repo_communication_mode(repo, "disabled")

    prefs = read_json(prefs_path, {})
    assert prefs["communication"]["layer"] == "disabled"
    assert prefs["communication"]["mode"] == "caveman_full"


def test_persist_repo_communication_mode_enabled_mode(tmp_path: Path):
    repo = tmp_path / "repo"
    prefs_path = repo / ".aictx" / "memory" / "user_preferences.json"
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
    monkeypatch.setattr(cli, "copy_local_agent_runtime", lambda repo_path: repo_path / ".aictx" / "agent_runtime.md")
    monkeypatch.setattr(cli, "load_active_workspace", lambda: Workspace("default", [], []))

    args = argparse.Namespace(repo=str(repo), no_gitignore=False, no_register=True, yes=False)
    assert cli.cmd_init(args) == 0

    prefs = read_json(repo / ".aictx" / "memory" / "user_preferences.json", {})
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
    monkeypatch.setattr(cli, "copy_local_agent_runtime", lambda repo_path: repo_path / ".aictx" / "agent_runtime.md")
    monkeypatch.setattr(cli, "load_active_workspace", lambda: Workspace("default", [], []))

    args = argparse.Namespace(repo=str(repo), no_gitignore=False, no_register=True, yes=False)
    assert cli.cmd_init(args) == 0

    prefs = read_json(repo / ".aictx" / "memory" / "user_preferences.json", {})
    assert prefs["communication"]["layer"] == "enabled"
    assert prefs["communication"]["mode"] == expected_mode


def test_cmd_init_yes_keeps_disabled_default(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(cli, "ensure_global_home", lambda: None)
    monkeypatch.setattr(cli, "install_global_agent_runtime", lambda _write_json: [])
    monkeypatch.setattr(cli, "copy_local_agent_runtime", lambda repo_path: repo_path / ".aictx" / "agent_runtime.md")
    monkeypatch.setattr(cli, "load_active_workspace", lambda: Workspace("default", [], []))

    args = argparse.Namespace(repo=str(repo), no_gitignore=False, no_register=True, yes=True)
    assert cli.cmd_init(args) == 0

    prefs = read_json(repo / ".aictx" / "memory" / "user_preferences.json", {})
    assert prefs["communication"]["layer"] == "disabled"
    assert prefs["communication"]["mode"] == "caveman_full"


def test_cmd_init_prepares_repo_runtime_state(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(cli, "ensure_global_home", lambda: None)
    monkeypatch.setattr(cli, "install_global_agent_runtime", lambda _write_json: [])
    monkeypatch.setattr(cli, "copy_local_agent_runtime", lambda repo_path: repo_path / ".aictx" / "agent_runtime.md")
    monkeypatch.setattr(cli, "load_active_workspace", lambda: Workspace("default", [], []))

    args = argparse.Namespace(repo=str(repo), no_gitignore=False, no_register=True, yes=True)
    assert cli.cmd_init(args) == 0

    state = read_json(repo / ".aictx" / "state.json", {})
    assert state["installed_version"] == package_version
    assert state["engine_capability_version"] >= 1
    assert state["installed_iteration"] == state["engine_capability_version"]
    assert state["engine_role"] == "initialized_repo_runtime"
    assert state["supports"]["strategy_memory"] is True
    assert state["supports"]["real_execution_logging"] is True
    assert state["supports"]["feedback_reporting"] is True
    assert state["adapter_runtime_enabled"] is True
    assert state["runner_integration_status"] == "native_ready"
    assert state["auto_execution_entrypoint"] == "aictx internal run-execution"
    assert state["runner_native_integrations"]["codex"]["status"] == "native_hardened"
    assert state["runner_native_integrations"]["claude"]["status"] == "native_hardened"
    assert state["communication_layer"] == "disabled"
    assert (repo / ".aictx" / "metrics" / "execution_logs.jsonl").exists()
    assert (repo / ".aictx" / "metrics" / "execution_feedback.jsonl").exists()
    assert (repo / ".aictx" / "strategy_memory" / "strategies.jsonl").exists()
    assert (repo / ".aictx" / "memory" / "source" / "index.json").exists()
    assert (repo / ".aictx" / "memory" / "source" / "projects" / repo.name / "overview.md").exists()
    assert not (repo / ".aictx" / "cost" / "optimization_history.jsonl").exists()
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
        "selection_reason": "",
        "matched_signals": [],
        "similarity_breakdown": {},
        "overlapping_files": [],
        "related_commands": [],
        "related_tests": [],
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
    assert payload["selection_reason"]
    assert isinstance(payload["matched_signals"], list)



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
    assert payload["suggested_entry_points"] == []
    assert payload["suggested_files"] == []
    assert payload["source"] == "strategy_memory"
    assert payload["selection_reason"] == "task_type:feature_work"
    assert payload["matched_signals"] == ["task_type:feature_work"]
    assert payload["similarity_breakdown"]["task_type"] == 1000


def test_cli_suggest_accepts_contextual_ranking_signals(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    strategy_memory.persist_strategy(
        repo,
        {
            "task_id": "old-strong",
            "task_text": "unrelated",
            "task_type": "testing",
            "entry_points": ["src/aictx/middleware.py"],
            "primary_entry_point": "src/aictx/middleware.py",
            "files_used": ["src/aictx/middleware.py"],
            "commands_executed": ["python -m pytest tests/test_smoke.py"],
            "tests_executed": ["tests/test_smoke.py"],
            "notable_errors": ["AssertionError startup summary missing"],
            "success": True,
            "is_failure": False,
            "timestamp": "2026-04-24T00:00:00Z",
        },
    )
    strategy_memory.persist_strategy(
        repo,
        {
            "task_id": "new-weak",
            "task_text": "startup summary",
            "task_type": "testing",
            "entry_points": ["src/other.py"],
            "primary_entry_point": "src/other.py",
            "files_used": ["src/other.py"],
            "commands_executed": [],
            "tests_executed": [],
            "notable_errors": [],
            "success": True,
            "is_failure": False,
            "timestamp": "2026-04-24T00:01:00Z",
        },
    )
    parser = cli.build_parser()
    args = parser.parse_args([
        "suggest",
        "--repo",
        str(repo),
        "--task-type",
        "testing",
        "--request",
        "fix startup summary assertion",
        "--files-opened",
        "src/aictx/middleware.py",
        "--commands-executed",
        "python -m pytest tests/test_smoke.py",
        "--tests-executed",
        "tests/test_smoke.py",
        "--notable-errors",
        "AssertionError startup summary missing",
    ])
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["suggested_entry_points"] == ["src/aictx/middleware.py"]
    assert "file_overlap:src/aictx/middleware.py" in payload["matched_signals"]
    assert "test_overlap:tests/test_smoke.py" in payload["matched_signals"]



def test_cli_reflect_detects_looping_on_same_files(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    log_path = repo / ".aictx" / "metrics" / "execution_logs.jsonl"
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
    assert payload["reopened_files"] == ["a.py", "b.py", "c.py"]
    assert payload["possible_issue"] == "looping_on_same_files"
    assert payload["opened_files_count"] == 2
    assert payload["suggested_next_action"]
    assert payload["recommended_entry_points"] == ["a.py", "b.py"]
    assert "reopened" in payload["reason"]



def test_cli_reflect_detects_too_much_exploration(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    log_path = repo / ".aictx" / "metrics" / "execution_logs.jsonl"
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
    assert payload["reopened_files"] == []
    assert payload["possible_issue"] == "too_much_exploration"
    assert payload["opened_files_count"] == 9
    assert payload["recommended_entry_points"] == ["1.py", "2.py", "3.py", "4.py", "5.py"]
    assert "Narrow".lower() in payload["suggested_next_action"].lower()



def test_cli_reflect_returns_none_without_history(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    parser = cli.build_parser()
    args = parser.parse_args(["reflect", "--repo", str(repo)])
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["reopened_files"] == []
    assert payload["possible_issue"] == "none"
    assert payload["opened_files_count"] == 0
    assert payload["suggested_next_action"] == "continue"


def test_report_real_usage_returns_empty_metrics_without_history(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    parser = cli.build_parser()
    args = parser.parse_args(["report", "real-usage", "--repo", str(repo)])
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["total_executions"] == 0
    assert payload["avg_execution_time_ms"] is None
    assert payload["avg_files_opened"] is None
    assert payload["avg_reopened_files"] is None
    assert payload["strategy_usage"] == 0
    assert payload["packet_usage"] == 0
    assert payload["redundant_exploration_cases"] == 0
    assert payload["capture_coverage"]["commands_executed"] == 0
    assert payload["failure_pattern_count"] == 0
    assert payload["error_capture"]["notable_error_count"] == 0
    assert payload["failure_patterns"]["open"] == 0
    assert payload["work_state"]["active"] is False



def test_report_real_usage_aggregates_real_logs_and_feedback(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    metrics_dir = repo / ".aictx" / "metrics"
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
                "success": False,
                "used_packet": False,
                "notable_errors": ["AssertionError: cli failed"],
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
    assert payload["total_executions"] == 2
    assert payload["avg_execution_time_ms"] == 1500
    assert payload["avg_files_opened"] == 3
    assert payload["avg_reopened_files"] == 0
    assert payload["strategy_usage"] == 1
    assert payload["packet_usage"] == 2
    assert payload["redundant_exploration_cases"] == 1
    assert payload["strategy_reuse_rate"] == 0.5
    assert payload["capture_coverage"]["files_opened"] == 2
    assert payload["capture_coverage"]["notable_errors"] == 1
    assert payload["error_capture"]["notable_error_count"] == 1
    assert payload["error_capture"]["failed_executions"] == 1
    assert payload["work_state"]["threads_count"] == 0



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
    assert "clean" in help_text
    assert "uninstall" in help_text
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
        cross_project_mode="workspace",
        yes=False,
    )
    answers = iter(["default", "n", "y"])
    monkeypatch.setattr("builtins.input", lambda _prompt='': next(answers))
    assert cli.cmd_install(install_args) == 0
    install_out = capsys.readouterr().out
    assert "install engine runtime artifacts" in install_out
    assert "prepare repos to work after a single `aictx init`" in install_out
    assert "Skipped global Codex integration" in install_out
    assert "Next: run `aictx init` inside a repository." in install_out

    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(cli, "ensure_global_home", lambda: None)
    monkeypatch.setattr(cli, "install_global_agent_runtime", lambda _write_json: [])
    monkeypatch.setattr(cli, "copy_local_agent_runtime", lambda repo_path: repo_path / ".aictx" / "agent_runtime.md")
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

    status = read_json(repo / ".aictx" / "metrics" / "agent_execution_status.json", {})
    assert status["last_execution_id"] == "exec-wrap-1"


def test_internal_run_execution_non_json_prints_agent_summary_text(tmp_path: Path, capsys):
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
            "run wrapped command and show summary",
            "--agent-id",
            "codex",
            "--execution-id",
            "exec-wrap-summary",
            "--validated-learning",
            "--",
            "python3",
            "-c",
            "print('wrapped ok')",
        ]
    )

    assert args.func(args) == 0
    output = capsys.readouterr().out
    assert output.startswith(
        f"codex@{repo.name} · session #1 · awake\n\nNo previous handoff to resume.\n"
    )
    assert "wrapped ok" in output
    assert "AICTX summary\n" in output
    assert "Details: [last_execution_summary.md](.aictx/continuity/last_execution_summary.md)" in output


def test_runtime_capture_provenance_and_prepare_fields(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    capture = build_capture({"files_opened": ["src/aictx/cli.py"], "commands_executed": ["python -m pytest tests/test_smoke.py"]})
    assert capture["provenance"]["files_opened"] == "explicit"
    assert capture["provenance"]["tests_executed"] == "heuristic"
    assert capture["tests_executed"] == ["python -m pytest tests/test_smoke.py"]

    prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "fix cli test",
            "agent_id": "agent-test",
            "execution_id": "capture-1",
            "files_opened": ["src/aictx/cli.py"],
            "commands_executed": ["python -m pytest tests/test_smoke.py"],
        }
    )
    assert prepared["execution_signal_capture"]["provenance"]["files_opened"] == "explicit"
    assert prepared["execution_observation"]["tests_executed"] == ["python -m pytest tests/test_smoke.py"]
    assert prepared["area_id"] == "src/aictx"


def test_run_execution_captures_command_tests_errors_and_agent_summary(tmp_path: Path, capsys):
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
            "run failing pytest command",
            "--agent-id",
            "codex",
            "--execution-id",
            "exec-wrap-fail",
            "--json",
            "--",
            "python3",
            "-c",
            "import sys; print('pytest failed assertion', file=sys.stderr); sys.exit(1)",
        ]
    )

    assert args.func(args) == 1
    payload = json.loads(capsys.readouterr().out)
    finalized = payload["finalized"]
    assert finalized["failure_persisted"]["failure_id"]
    assert finalized["agent_summary"]["failure_recorded"] is True
    assert finalized["agent_summary_text"].startswith("AICTX summary\n")
    log_rows = [
        json.loads(line)
        for line in (repo / ".aictx" / "metrics" / "execution_logs.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert log_rows[-1]["commands_executed"]
    assert log_rows[-1]["notable_errors"]


def test_failure_memory_lookup_and_resolution_link(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    failed = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "fix failing cli test",
            "agent_id": "agent-test",
            "execution_id": "failure-1",
            "declared_task_type": "bug_fixing",
            "files_opened": ["src/aictx/cli.py"],
            "commands_executed": ["pytest tests/test_cli.py"],
            "notable_errors": ["AssertionError: cli failed"],
        }
    )
    finalize_execution(failed, {"success": False, "result_summary": "AssertionError: cli failed", "validated_learning": False})
    assert load_failures(repo)
    assert lookup_failures(repo, task_type="bug_fixing", text="cli failed", files=["src/aictx/cli.py"], area_id="src/aictx")

    fixed = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "fix cli failed assertion",
            "agent_id": "agent-test",
            "execution_id": "failure-2",
            "declared_task_type": "bug_fixing",
            "files_opened": ["src/aictx/cli.py"],
        }
    )
    finalized = finalize_execution(fixed, {"success": True, "result_summary": "fixed cli assertion", "validated_learning": True})
    assert finalized["resolved_failures"]


def test_failed_finalize_derives_failure_pattern_from_summary_without_notable_errors(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "debug failed startup",
            "agent_id": "agent-test",
            "execution_id": "failure-summary",
            "declared_task_type": "bug_fixing",
            "commands_executed": ["python -m aictx internal boot"],
        }
    )
    finalized = finalize_execution(prepared, {"success": False, "result_summary": "RuntimeError: startup failed", "validated_learning": False})
    failures = load_failures(repo)
    assert finalized["failure_persisted"]["failure_id"]
    assert failures[-1]["symptoms"] == ["RuntimeError: startup failed"]
    assert failures[-1]["failed_command"] == "python -m aictx internal boot"


def test_failed_finalize_without_failure_signals_does_not_invent_pattern(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "attempt unknown task",
            "agent_id": "agent-test",
            "execution_id": "failure-empty",
            "declared_task_type": "bug_fixing",
        }
    )
    finalized = finalize_execution(prepared, {"success": False, "result_summary": "", "validated_learning": False})
    assert finalized["failure_persisted"] is None
    assert load_failures(repo) == []


def test_area_memory_hints_are_stable_and_reported(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    assert derive_area_id(["src/aictx/middleware.py", "src/aictx/cli.py"]) == "src/aictx"
    prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "document area memory",
            "agent_id": "agent-test",
            "execution_id": "area-1",
            "declared_task_type": "feature_work",
            "files_opened": ["src/aictx/middleware.py"],
            "tests_executed": ["tests/test_smoke.py"],
        }
    )
    finalize_execution(prepared, {"success": True, "result_summary": "ok", "validated_learning": True})
    next_prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "more area work",
            "agent_id": "agent-test",
            "execution_id": "area-2",
            "declared_task_type": "feature_work",
            "files_opened": ["src/aictx/cli.py"],
        }
    )
    assert next_prepared["area_hints"]["area_id"] == "src/aictx"
    assert "src/aictx/middleware.py" in next_prepared["area_hints"]["related_files"]


def test_install_repo_runner_integrations_creates_codex_and_claude_native_files(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    created = install_repo_runner_integrations(repo)
    assert repo / "CLAUDE.md" in created
    settings = read_json(repo / ".claude" / "settings.json", {})
    assert "SessionStart" in settings["hooks"]
    assert "UserPromptSubmit" in settings["hooks"]
    assert "PreToolUse" in settings["hooks"]
    assert (repo / ".claude" / "hooks" / "aictx_user_prompt_submit.py").exists()
    assert (repo / ".claude" / "hooks" / "aictx_pre_tool_use.py").exists()
    assert (repo / ".gitignore").exists()
    gitignore = (repo / ".gitignore").read_text(encoding="utf-8")
    assert CLAUDE_GITIGNORE_COMMENT in gitignore
    assert CLAUDE_DIR_GITIGNORE_LINE in gitignore
    assert CLAUDE_MD_GITIGNORE_LINE in gitignore
    assert "aictx suggest --repo ." in (repo / "CLAUDE.md").read_text(encoding="utf-8")


def test_install_repo_runner_integrations_merges_claude_settings_idempotently(tmp_path: Path):
    repo = tmp_path / "repo"
    settings_path = repo / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(
        json.dumps(
            {
                "permissions": {"allow": ["Bash(pytest)"]},
                "hooks": {
                    "PreToolUse": [
                        {"matcher": "Write", "hooks": [{"type": "command", "command": "custom.py", "timeout": 5}]}
                    ],
                    "Stop": [{"hooks": [{"type": "command", "command": "stop.py"}]}],
                },
            }
        ),
        encoding="utf-8",
    )

    install_repo_runner_integrations(repo)
    first = settings_path.read_text(encoding="utf-8")
    install_repo_runner_integrations(repo)
    second = settings_path.read_text(encoding="utf-8")
    settings = json.loads(second)

    assert first == second
    assert settings["permissions"] == {"allow": ["Bash(pytest)"]}
    assert settings["hooks"]["Stop"] == [{"hooks": [{"type": "command", "command": "stop.py"}]}]
    assert any(
        hook.get("command") == "custom.py"
        for entry in settings["hooks"]["PreToolUse"]
        for hook in entry.get("hooks", [])
    )
    assert any(
        "aictx_pre_tool_use.py" in str(hook.get("command"))
        for entry in settings["hooks"]["PreToolUse"]
        for hook in entry.get("hooks", [])
    )


def test_install_repo_runner_integrations_does_not_add_gitignore_when_claude_preexists_and_unignored(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    install_repo_runner_integrations(repo)
    gitignore = repo / ".gitignore"
    assert gitignore.exists()
    text = gitignore.read_text(encoding="utf-8")
    assert CLAUDE_GITIGNORE_COMMENT in text
    assert CLAUDE_DIR_GITIGNORE_LINE not in text
    assert CLAUDE_MD_GITIGNORE_LINE in text


def test_install_repo_runner_integrations_preserves_existing_claude_gitignore(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".gitignore").write_text(".claude/\n", encoding="utf-8")
    install_repo_runner_integrations(repo)
    text = (repo / ".gitignore").read_text(encoding="utf-8")
    assert text == f".claude/\n\n{CLAUDE_GITIGNORE_COMMENT}\n{CLAUDE_MD_GITIGNORE_LINE}\n"


def test_install_repo_runner_integrations_does_not_add_claude_md_gitignore_when_claude_md_preexists(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "CLAUDE.md").write_text("User Claude notes.\n", encoding="utf-8")
    install_repo_runner_integrations(repo)
    text = (repo / ".gitignore").read_text(encoding="utf-8")
    assert CLAUDE_DIR_GITIGNORE_LINE in text
    assert CLAUDE_MD_GITIGNORE_LINE not in text


def test_cmd_install_default_does_not_touch_codex_global(tmp_path: Path, monkeypatch, capsys):
    codex_home = tmp_path / ".codex"
    monkeypatch.setattr(cli, "ensure_global_home", lambda: None)
    monkeypatch.setattr(cli, "install_global_agent_runtime", lambda _write_json: [])
    monkeypatch.setattr(cli, "install_global_adapters", lambda: [])
    monkeypatch.setattr(cli, "write_json", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "read_json", lambda _path, default: default)
    monkeypatch.setattr(cli, "workspace_path", lambda wid: tmp_path / f"{wid}.json")
    monkeypatch.setattr("aictx.runner_integrations.CODEX_HOME", codex_home)
    monkeypatch.setattr("aictx.runner_integrations.CODEX_CONFIG_PATH", codex_home / "config.toml")

    args = argparse.Namespace(
        workspace_id="default",
        workspace_root=None,
        cross_project_mode="workspace",
        install_codex_global=False,
        dry_run=False,
        yes=True,
    )
    assert cli.cmd_install(args) == 0
    assert not codex_home.exists()
    assert "Skipped global Codex integration" in capsys.readouterr().out


def test_cmd_install_codex_global_opt_in_touches_codex_global(tmp_path: Path, monkeypatch, capsys):
    codex_home = tmp_path / ".codex"
    monkeypatch.setattr(cli, "ensure_global_home", lambda: None)
    monkeypatch.setattr(cli, "install_global_agent_runtime", lambda _write_json: [])
    monkeypatch.setattr(cli, "install_global_adapters", lambda: [])
    monkeypatch.setattr(cli, "write_json", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "read_json", lambda _path, default: default)
    monkeypatch.setattr(cli, "workspace_path", lambda wid: tmp_path / f"{wid}.json")
    monkeypatch.setattr("aictx.runner_integrations.CODEX_HOME", codex_home)
    monkeypatch.setattr("aictx.runner_integrations.CODEX_CONFIG_PATH", codex_home / "config.toml")

    args = argparse.Namespace(
        workspace_id="default",
        workspace_root=None,
        cross_project_mode="workspace",
        install_codex_global=True,
        dry_run=False,
        yes=True,
    )
    assert cli.cmd_install(args) == 0
    assert (codex_home / "AGENTS.override.md").exists()
    assert (codex_home / "config.toml").exists()
    assert "WARNING: updating global Codex files" in capsys.readouterr().out


def test_cmd_install_dry_run_does_not_mutate(tmp_path: Path, monkeypatch, capsys):
    called = {"ensure": False}
    monkeypatch.setattr(cli, "ensure_global_home", lambda: called.__setitem__("ensure", True))
    monkeypatch.setattr(cli, "workspace_path", lambda wid: tmp_path / f"{wid}.json")

    args = argparse.Namespace(
        workspace_id="default",
        workspace_root=str(tmp_path / "ws"),
        cross_project_mode="workspace",
        install_codex_global=True,
        dry_run=True,
        yes=True,
    )
    assert cli.cmd_install(args) == 0
    out = capsys.readouterr().out
    assert "Dry run. Would create/update:" in out
    assert called["ensure"] is False


def test_install_codex_native_integration_writes_home_override(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("aictx.runner_integrations.CODEX_HOME", tmp_path / ".codex")
    monkeypatch.setattr("aictx.runner_integrations.CODEX_CONFIG_PATH", tmp_path / ".codex" / "config.toml")
    created = install_codex_native_integration()
    assert (tmp_path / ".codex" / "AICTX_Codex.md") in created
    assert (tmp_path / ".codex" / "AGENTS.override.md") in created
    assert (tmp_path / ".codex" / "config.toml") in created
    instructions = (tmp_path / ".codex" / "AICTX_Codex.md").read_text(encoding="utf-8")
    assert "Use AICTX in every Codex session" in instructions
    assert "aictx suggest --repo ." in instructions
    text = (tmp_path / ".codex" / "AGENTS.override.md").read_text(encoding="utf-8")
    assert "AICTX Codex integration" in text
    config = (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert 'project_doc_fallback_filenames = ["CLAUDE.md"]' in config
    assert 'model_instructions_file = "' in config


def test_claude_pre_tool_hook_blocks_generated_runtime_edits(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    install_repo_runner_integrations(repo)
    script = repo / ".claude" / "hooks" / "aictx_pre_tool_use.py"

    write_payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(repo / ".aictx" / "memory" / "derived_boot_summary.json"),
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

    state_path = repo / ".aictx" / "state.json"
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


def test_boot_and_prepare_warn_when_native_runtime_files_are_missing(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    cli.prepare_repo_runtime(repo)
    install_repo_runner_integrations(repo)
    upsert_marked_block(repo / "AGENTS.md", render_repo_agents_block())

    for path in [
        repo / "CLAUDE.md",
        repo / ".claude/settings.json",
    ]:
        path.unlink()

    boot = core_runtime.bootstrap(str(repo))
    prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "review runtime contract health",
            "agent_id": "agent-test",
            "execution_id": "exec-runtime-contract-1",
        }
    )

    for payload in [boot["consistency_checks"], prepared["consistency_checks"]]:
        assert payload["status"] == "warning"
        assert payload["repair_hint"] == "Run `aictx internal migrate` to restore missing AICTX repo runtime files."
        checks = {issue["check"] for issue in payload["issues"]}
        assert "native_runtime_contract_incomplete" in checks
        assert "runner_integration_status_incorrect" in checks


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


def test_migrate_repairs_repo_runtime_contract_files(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    cli.prepare_repo_runtime(repo)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")

    for path in [
        repo / "CLAUDE.md",
        repo / ".claude" / "settings.json",
        repo / ".claude" / "hooks" / "aictx_session_start.py",
        repo / ".claude" / "hooks" / "aictx_user_prompt_submit.py",
        repo / ".claude" / "hooks" / "aictx_pre_tool_use.py",
    ]:
        if path.exists():
            path.unlink()
    agents_path = repo / "AGENTS.md"
    agents_path.write_text("# repo instructions\n", encoding="utf-8")

    original_base = core_runtime.BASE
    original_engine_state_dir = core_runtime.ENGINE_STATE_DIR
    original_engine_state_path = core_runtime.ENGINE_STATE_PATH
    try:
        core_runtime.BASE = repo
        core_runtime.ENGINE_STATE_DIR = repo / ".aictx"
        core_runtime.ENGINE_STATE_PATH = repo / ".aictx" / "state.json"
        payload = {"repo_runtime_repair": core_runtime.repair_repo_runtime_contract(repo)}
    finally:
        core_runtime.BASE = original_base
        core_runtime.ENGINE_STATE_DIR = original_engine_state_dir
        core_runtime.ENGINE_STATE_PATH = original_engine_state_path

    repair = payload["repo_runtime_repair"]
    assert repair["repaired"] is True
    assert (repo / "CLAUDE.md").exists()
    assert (repo / ".claude" / "settings.json").exists()
    assert (repo / ".claude" / "hooks" / "aictx_session_start.py").exists()
    assert (repo / ".claude" / "hooks" / "aictx_user_prompt_submit.py").exists()
    assert (repo / ".claude" / "hooks" / "aictx_pre_tool_use.py").exists()
    assert "<!-- AICTX:START -->" in (repo / "AGENTS.md").read_text(encoding="utf-8")

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


def test_core_runtime_keeps_compatibility_exports_after_refactor():
    assert core_runtime.rank_records is not None
    assert core_runtime.packet_for_task is not None
    assert callable(core_runtime.rank_records)
    assert callable(core_runtime.packet_for_task)


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
    assert packet["description"] == "debug failing integration"
    assert packet["task_type"] == "bug_fixing"
    assert packet["context"] == {}
    assert "selection_report" not in packet
    assert "communication_policy" not in packet


@pytest.mark.parametrize(
    ("user_request", "files", "expected"),
    [
        ("fix failing login error", [], "bug_fixing"),
        ("add pytest coverage", ["tests/test_cli.py"], "testing"),
        ("improve benchmark latency", ["benchmarks/perf.py"], "performance"),
        ("document architecture decision", ["docs/architecture.md"], "architecture"),
        ("implement new install flag", ["src/aictx/cli.py"], "feature_work"),
        ("mejorar output del summary", ["src/aictx/middleware.py"], "unknown"),
        ("summarize repository", [], "unknown"),
    ],
)
def test_resolve_task_type_heuristics(user_request: str, files: list[str], expected: str):
    resolved = runtime_tasks.resolve_task_type(user_request, touched_files=files)
    assert resolved["task_type"] == expected
    if expected == "unknown":
        assert resolved["source"] == "unknown_fallback"
    else:
        assert resolved["source"] == "heuristic"
        assert resolved["evidence"]


def test_finalize_execution_recalculates_final_task_type_and_area_from_observed_signals(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "mejorar output del summary",
            "agent_id": "agent-test",
            "execution_id": "exec-final-task-area",
        }
    )
    assert prepared["prepared_task_type"] == "unknown"
    assert prepared["prepared_area_id"] == "unknown"

    prepared["execution_observation"]["files_opened"] = ["src/aictx/middleware.py", "tests/test_smoke.py"]
    prepared["execution_observation"]["files_edited"] = ["src/aictx/middleware.py", "tests/test_smoke.py"]
    prepared["execution_observation"]["tests_executed"] = ["python -m pytest tests/test_smoke.py"]
    prepared["execution_observation"]["commands_executed"] = ["python -m pytest tests/test_smoke.py"]

    finalized = finalize_execution(
        prepared,
        {
            "success": True,
            "result_summary": "Mejoré el render del summary y alineé la salida final.",
            "validated_learning": True,
        },
    )

    assert finalized["prepared_task_type"] == "unknown"
    assert finalized["final_task_type"] == "refactoring"
    assert finalized["effective_task_type"] == "refactoring"
    assert finalized["prepared_area_id"] == "unknown"
    assert finalized["final_area_id"] == "src/aictx"
    assert finalized["effective_area_id"] == "src/aictx"
    assert finalized["final_task_resolution"]["source"] == "observed_signals"
    assert "unknown" not in finalized["agent_summary_text"]
    detailed = (repo / ".aictx" / "continuity" / "last_execution_summary.md").read_text(encoding="utf-8")
    assert "- Final task type: refactoring" in detailed
    assert "- Final area: src/aictx" in detailed

    log_rows = [
        json.loads(line)
        for line in (repo / ".aictx" / "metrics" / "execution_logs.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert log_rows[-1]["task_type"] == "refactoring"
    assert log_rows[-1]["final_task_type"] == "refactoring"
    assert log_rows[-1]["area_id"] == "src/aictx"
    assert log_rows[-1]["final_area_id"] == "src/aictx"


def test_observed_task_type_does_not_overweight_validation_tests_for_implementation():
    resolved = runtime_tasks.resolve_observed_task_type(
        "implementar clasificación provisional/final/effective para task_type y area_id",
        touched_files=[
            "src/aictx/runtime_tasks.py",
            "src/aictx/middleware.py",
            "src/aictx/strategy_memory.py",
            "src/aictx/continuity.py",
            "tests/test_smoke.py",
        ],
        tests_executed=["PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_smoke.py"],
        commands_executed=["PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_smoke.py"],
        result_summary="Implementé clasificación provisional/final/effective para task_type y area_id.",
    )

    assert resolved["task_type"] in {"feature_work", "refactoring"}
    assert resolved["task_type"] != "testing"


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


def test_prepare_execution_builds_packet_for_debug_but_not_trivial_tasks(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    debug_prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "debug failing integration test",
            "agent_id": "agent-test",
            "execution_id": "packet-debug",
            "declared_task_type": "bug_fixing",
        }
    )
    assert debug_prepared["retrieval_summary"]["packet_built"] is True
    assert debug_prepared["execution_observation"]["used_packet"] is True
    assert debug_prepared["packet"]["task_type"] == "bug_fixing"
    assert Path(debug_prepared["packet_path"]).exists()

    trivial_prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "say hello",
            "agent_id": "agent-test",
            "execution_id": "packet-trivial",
        }
    )
    assert trivial_prepared["retrieval_summary"]["packet_built"] is False
    assert trivial_prepared["packet"] == {}


def test_finalize_telemetry_marks_used_packet_when_packet_built(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "debug failing integration test",
            "agent_id": "agent-test",
            "execution_id": "packet-telemetry",
            "declared_task_type": "bug_fixing",
        }
    )
    finalized = finalize_execution(prepared, {"success": True, "result_summary": "ok", "validated_learning": False})
    assert finalized["aictx_feedback"]["used_packet"] is True
    assert finalized["value_evidence"]["used_packet"] is True
    rows = [
        json.loads(line)
        for line in (repo / ".aictx" / "metrics" / "execution_logs.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows[-1]["used_packet"] is True


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

    weekly = read_json(repo / ".aictx" / "metrics" / "weekly_summary.json", {})
    assert finalized["value_evidence"]["repeated_context_request"] is True
    assert weekly["value_evidence"]["repeated_tasks_observed"] >= 1
    assert weekly["value_evidence"]["last_used_packet"] in {True, False}


def test_scaffold_status_files_include_version_contract(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    state = read_json(repo / ".aictx" / "state.json", {})

    assert state["installed_version"] == package_version
    assert state["engine_capability_version"] >= 1
    assert state["installed_iteration"] == state["engine_capability_version"]


def test_task_memory_writes_only_canonical_buckets(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(core_runtime, "BASE", tmp_path)
    monkeypatch.setattr(core_runtime, "ENGINE_STATE_DIR", tmp_path / ".aictx")
    monkeypatch.setattr(core_runtime, "TASK_MEMORY_DIR", tmp_path / ".aictx" / "task_memory")
    monkeypatch.setattr(core_runtime, "TASK_MEMORY_STATUS_PATH", tmp_path / ".aictx" / "task_memory" / "task_memory_status.json")
    monkeypatch.setattr(core_runtime, "TASK_MEMORY_TAXONOMY_PATH", tmp_path / ".aictx" / "task_memory" / "task_taxonomy.json")
    monkeypatch.setattr(core_runtime, "TASK_MEMORY_RULES_PATH", tmp_path / ".aictx" / "task_memory" / "task_resolution_rules.md")
    monkeypatch.setattr(core_runtime, "TASK_MEMORY_HISTORY_PATH", tmp_path / ".aictx" / "task_memory" / "task_memory_history.jsonl")

    runtime_task_memory.build_task_memory_artifacts([
        {"id": "r1", "type": "task_pattern", "task_type": "testing", "title": "Run tests", "summary": "Use pytest", "project": "aictx"}
    ])
    assert (tmp_path / ".aictx" / "task_memory" / "testing" / "summary.json").exists()
    assert not (tmp_path / ".aictx" / "task_memory" / "tests" / "summary.json").exists()
    assert not (tmp_path / ".aictx" / "task_memory" / "general" / "summary.json").exists()
    assert runtime_task_memory.category_summary_path("tests").name == "summary.json"


def test_runtime_cost_module_optimizer_roundtrip(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(core_runtime, "BASE", tmp_path)
    monkeypatch.setattr(core_runtime, "ENGINE_STATE_DIR", tmp_path / ".aictx")
    monkeypatch.setattr(core_runtime, "COST_DIR", tmp_path / ".aictx" / "cost")
    monkeypatch.setattr(core_runtime, "COST_CONFIG_PATH", tmp_path / ".aictx" / "cost" / "optimizer_config.yaml")
    monkeypatch.setattr(core_runtime, "COST_RULES_PATH", tmp_path / ".aictx" / "cost" / "cost_estimation_rules.md")
    monkeypatch.setattr(core_runtime, "COST_STATUS_PATH", tmp_path / ".aictx" / "cost" / "packet_budget_status.json")
    monkeypatch.setattr(core_runtime, "COST_HISTORY_PATH", tmp_path / ".aictx" / "cost" / "optimization_history.jsonl")
    monkeypatch.setattr(core_runtime, "COST_LATEST_REPORT_PATH", tmp_path / ".aictx" / "cost" / "latest_optimization_report.md")

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
    monkeypatch.setattr(core_runtime, "ENGINE_STATE_DIR", tmp_path / ".aictx")
    monkeypatch.setattr(core_runtime, "FAILURE_MEMORY_DIR", tmp_path / ".aictx" / "failure_memory")
    monkeypatch.setattr(core_runtime, "FAILURE_MEMORY_RECORDS_DIR", tmp_path / ".aictx" / "failure_memory" / "failures")
    monkeypatch.setattr(core_runtime, "FAILURE_MEMORY_INDEX_PATH", tmp_path / ".aictx" / "failure_memory" / "index.json")
    monkeypatch.setattr(core_runtime, "FAILURE_MEMORY_STATUS_PATH", tmp_path / ".aictx" / "failure_memory" / "failure_memory_status.json")
    monkeypatch.setattr(core_runtime, "FAILURE_MEMORY_SUMMARY_PATH", tmp_path / ".aictx" / "failure_memory" / "summaries" / "common_patterns.md")
    monkeypatch.setattr(core_runtime, "TASK_MEMORY_DIR", tmp_path / ".aictx" / "task_memory")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_DIR", tmp_path / ".aictx" / "memory_graph")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_NODES_PATH", tmp_path / ".aictx" / "memory_graph" / "nodes" / "nodes.jsonl")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_EDGES_PATH", tmp_path / ".aictx" / "memory_graph" / "edges" / "edges.jsonl")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_STATUS_PATH", tmp_path / ".aictx" / "memory_graph" / "graph_status.json")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_LABEL_INDEX_PATH", tmp_path / ".aictx" / "memory_graph" / "indexes" / "by_label.json")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_TYPE_INDEX_PATH", tmp_path / ".aictx" / "memory_graph" / "indexes" / "by_type.json")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_RELATION_INDEX_PATH", tmp_path / ".aictx" / "memory_graph" / "indexes" / "by_relation.json")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_SNAPSHOT_PATH", tmp_path / ".aictx" / "memory_graph" / "snapshots" / "latest_graph_snapshot.json")

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
    monkeypatch.setattr(core_runtime, "ENGINE_STATE_DIR", tmp_path / ".aictx")
    monkeypatch.setattr(core_runtime, "TASK_MEMORY_DIR", tmp_path / ".aictx" / "task_memory")
    monkeypatch.setattr(core_runtime, "FAILURE_MEMORY_DIR", tmp_path / ".aictx" / "failure_memory")
    monkeypatch.setattr(core_runtime, "FAILURE_MEMORY_INDEX_PATH", tmp_path / ".aictx" / "failure_memory" / "index.json")
    monkeypatch.setattr(core_runtime, "FAILURE_MEMORY_RECORDS_DIR", tmp_path / ".aictx" / "failure_memory" / "failures")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_DIR", tmp_path / ".aictx" / "memory_graph")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_NODES_PATH", tmp_path / ".aictx" / "memory_graph" / "nodes" / "nodes.jsonl")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_EDGES_PATH", tmp_path / ".aictx" / "memory_graph" / "edges" / "edges.jsonl")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_STATUS_PATH", tmp_path / ".aictx" / "memory_graph" / "graph_status.json")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_LABEL_INDEX_PATH", tmp_path / ".aictx" / "memory_graph" / "indexes" / "by_label.json")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_TYPE_INDEX_PATH", tmp_path / ".aictx" / "memory_graph" / "indexes" / "by_type.json")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_RELATION_INDEX_PATH", tmp_path / ".aictx" / "memory_graph" / "indexes" / "by_relation.json")
    monkeypatch.setattr(core_runtime, "MEMORY_GRAPH_SNAPSHOT_PATH", tmp_path / ".aictx" / "memory_graph" / "snapshots" / "latest_graph_snapshot.json")

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


def test_cmd_clean_removes_only_repo_managed_aictx_content(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo_scaffold(repo, update_gitignore=True)
    install_repo_runner_integrations(repo)
    upsert_marked_block(repo / "AGENTS.md", render_repo_agents_block())

    user_agents = repo / "AGENTS.md"
    user_agents.write_text(user_agents.read_text(encoding="utf-8") + "\nUser note.\n", encoding="utf-8")
    extra_claude_hook = repo / ".claude" / "hooks" / "custom.py"
    extra_claude_hook.parent.mkdir(parents=True, exist_ok=True)
    extra_claude_hook.write_text("print('keep')\n", encoding="utf-8")
    legacy_refresh_hook = repo / ".claude" / "hooks" / "aictx_refresh_memory_graph.sh"
    legacy_refresh_hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    payload = cli.clean_repo_and_unregister(repo)

    assert not (repo / ".aictx").exists()
    assert not (repo / "AGENTS.override.md").exists()
    assert not (repo / "CLAUDE.md").exists()
    assert not legacy_refresh_hook.exists()
    assert extra_claude_hook.exists()
    assert 'AICTX:START' not in (repo / 'AGENTS.md').read_text(encoding='utf-8')
    assert 'User note.' in (repo / 'AGENTS.md').read_text(encoding='utf-8')
    assert '.aictx/' not in (repo / '.gitignore').read_text(encoding='utf-8')
    assert 'CLAUDE.md' not in (repo / '.gitignore').read_text(encoding='utf-8')
    settings_path = repo / '.claude' / 'settings.json'
    assert not settings_path.exists()
    assert any(item.endswith('.aictx') for item in payload['removed'])


def test_cmd_init_removes_legacy_repo_agents_override_block(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "AGENTS.override.md").write_text(
        "<!-- AICTX:START -->\nlegacy\n<!-- AICTX:END -->\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(cli, "ensure_global_home", lambda: None)
    monkeypatch.setattr(cli, "install_global_agent_runtime", lambda _write_json: [])
    monkeypatch.setattr(cli, "copy_local_agent_runtime", lambda repo_path: repo_path / ".aictx" / "agent_runtime.md")
    monkeypatch.setattr(cli, "load_active_workspace", lambda: Workspace("default", [], []))

    args = argparse.Namespace(repo=str(repo), no_gitignore=False, no_register=True, yes=True)
    assert cli.cmd_init(args) == 0
    assert not (repo / "AGENTS.override.md").exists()


def test_cmd_uninstall_removes_global_and_registered_repo_content_only(tmp_path: Path, monkeypatch):
    engine_home = tmp_path / '.aictx_home'
    codex_home = tmp_path / '.codex'
    monkeypatch.setattr('aictx.state.ENGINE_HOME', engine_home)
    monkeypatch.setattr('aictx.state.CONFIG_PATH', engine_home / 'config.json')
    monkeypatch.setattr('aictx.state.PROJECTS_REGISTRY_PATH', engine_home / 'projects_registry.json')
    monkeypatch.setattr('aictx.state.WORKSPACES_DIR', engine_home / 'workspaces')
    monkeypatch.setattr('aictx.cleanup.ENGINE_HOME', engine_home)
    monkeypatch.setattr('aictx.cleanup.PROJECTS_REGISTRY_PATH', engine_home / 'projects_registry.json')
    monkeypatch.setattr('aictx.cleanup.WORKSPACES_DIR', engine_home / 'workspaces')
    monkeypatch.setattr('aictx.cleanup.CODEX_HOME', codex_home)
    monkeypatch.setattr('aictx.cleanup.CODEX_CONFIG_PATH', codex_home / 'config.toml')
    monkeypatch.setattr('aictx.runner_integrations.CODEX_HOME', codex_home)
    monkeypatch.setattr('aictx.runner_integrations.CODEX_CONFIG_PATH', codex_home / 'config.toml')
    monkeypatch.setattr('aictx.agent_runtime.ENGINE_HOME', engine_home)
    monkeypatch.setattr('aictx.adapters.ENGINE_HOME', engine_home)
    monkeypatch.setattr('aictx.adapters.GLOBAL_ADAPTERS_DIR', engine_home / 'adapters')
    monkeypatch.setattr('aictx.adapters.GLOBAL_ADAPTERS_REGISTRY_PATH', engine_home / 'adapters' / 'registry.json')
    monkeypatch.setattr('aictx.adapters.GLOBAL_ADAPTERS_BIN_DIR', engine_home / 'adapters' / 'bin')
    monkeypatch.setattr('aictx.adapters.GLOBAL_ADAPTERS_INSTALL_STATUS_PATH', engine_home / 'adapters' / 'install_status.json')

    repo = tmp_path / 'repo'
    repo.mkdir()
    init_repo_scaffold(repo, update_gitignore=True)
    install_repo_runner_integrations(repo)
    upsert_marked_block(repo / 'AGENTS.md', render_repo_agents_block())

    engine_home.mkdir(parents=True, exist_ok=True)
    (engine_home / 'workspaces').mkdir(parents=True, exist_ok=True)
    cli.write_json(engine_home / 'projects_registry.json', {'version': 1, 'projects': [{'name': 'repo', 'repo_path': str(repo), 'workspace': 'default'}]})
    cli.write_json(engine_home / 'workspaces' / 'default.json', {'version': 1, 'workspace_id': 'default', 'roots': [], 'repos': [str(repo)], 'cross_project_mode': 'workspace'})
    install_codex_native_integration()
    user_file = codex_home / 'notes.txt'
    user_file.parent.mkdir(parents=True, exist_ok=True)
    user_file.write_text('keep\n', encoding='utf-8')

    payload = cli.uninstall_all()

    assert not engine_home.exists()
    assert not (repo / '.aictx').exists()
    assert user_file.exists()
    assert not (codex_home / 'AICTX_Codex.md').exists()
    codex_override = codex_home / 'AGENTS.override.md'
    assert (not codex_override.exists()) or ('AICTX:START' not in codex_override.read_text(encoding='utf-8'))
    assert str(repo) in payload['repos_cleaned']
