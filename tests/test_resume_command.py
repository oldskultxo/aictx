from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from aictx import cli
from aictx.agent_runtime import render_agent_runtime
from aictx.continuity import DECISIONS_PATH, HANDOFF_PATH, LAST_EXECUTION_SUMMARY_PATH, RESUME_CAPSULE_JSON_PATH, RESUME_CAPSULE_MARKDOWN_PATH
from aictx.middleware import finalize_execution, prepare_execution
from aictx.repo_map.config import write_repomap_config, write_repomap_index
from aictx.scaffold import init_repo_scaffold
from aictx.state import REPO_FAILURE_MEMORY_DIR, REPO_STRATEGY_MEMORY_DIR, write_json
from aictx.work_state import close_work_state, start_work_state


def _parser():
    return cli.build_parser()


def _seed_repomap(repo: Path) -> None:
    (repo / "src/aictx").mkdir(parents=True)
    (repo / "src/aictx/continuity.py").write_text("def build_resume_capsule():\n    pass\n", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests/test_resume_command.py").write_text("def test_resume():\n    pass\n", encoding="utf-8")
    write_repomap_config(repo, {"enabled": True})
    write_repomap_index(
        repo,
        {
            "version": 1,
            "provider": "tree_sitter",
            "mode": "full",
            "files": [
                {
                    "path": "src/aictx/continuity.py",
                    "language": "python",
                    "symbols": [{"name": "build_resume_capsule", "kind": "function", "line": 1, "language": "python"}],
                    "imports": [],
                    "metadata_only": False,
                    "provider": "tree_sitter",
                    "reason": "",
                    "size_bytes": 10,
                },
                {
                    "path": "tests/test_resume_command.py",
                    "language": "python",
                    "symbols": [{"name": "test_resume", "kind": "function", "line": 1, "language": "python"}],
                    "imports": [],
                    "metadata_only": False,
                    "provider": "tree_sitter",
                    "reason": "",
                    "size_bytes": 10,
                },
            ],
        },
    )


def _seed_parser_fixture(repo: Path) -> None:
    (repo / "src/taskflow").mkdir(parents=True)
    (repo / "src/taskflow/parser.py").write_text("def parse_blocked():\n    pass\n", encoding="utf-8")
    (repo / "tests").mkdir(exist_ok=True)
    (repo / "tests/test_parser.py").write_text("def test_blocked_edge_cases():\n    pass\n", encoding="utf-8")
    (repo / "README.md").write_text("# Quickstart\n", encoding="utf-8")
    write_repomap_config(repo, {"enabled": True})
    write_repomap_index(
        repo,
        {
            "version": 1,
            "files": [
                {
                    "path": "README.md",
                    "language": "markdown",
                    "symbols": [{"name": "Quickstart", "kind": "heading", "line": 1, "language": "markdown"}],
                },
                {
                    "path": "src/taskflow/parser.py",
                    "language": "python",
                    "symbols": [{"name": "parse_blocked", "kind": "function", "line": 1, "language": "python"}],
                },
                {
                    "path": "tests/test_parser.py",
                    "language": "python",
                    "symbols": [{"name": "test_blocked_edge_cases", "kind": "function", "line": 1, "language": "python"}],
                },
            ],
        },
    )


def _seed_generic_repomap(repo: Path, files: dict[str, tuple[str, str]]) -> None:
    for rel_path, (language, symbol) in files.items():
        target = repo / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if language == "markdown":
            target.write_text(f"# {symbol}\n", encoding="utf-8")
        elif language in {"toml", "yaml"}:
            target.write_text(f"# {symbol}\n", encoding="utf-8")
        else:
            target.write_text(f"def {symbol}():\n    pass\n", encoding="utf-8")
    write_repomap_config(repo, {"enabled": True})
    write_repomap_index(
        repo,
        {
            "version": 1,
            "files": [
                {
                    "path": rel_path,
                    "language": language,
                    "symbols": [
                        {
                            "name": symbol,
                            "kind": "heading" if language == "markdown" else "function",
                            "line": 1,
                            "language": language,
                        }
                    ],
                }
                for rel_path, (language, symbol) in files.items()
            ],
        },
    )


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_resume_default_markdown_and_budget(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "implement resume capsule"])
    assert args.func(args) == 0

    output = capsys.readouterr().out
    assert output.startswith("AICTX continuity capsule\n")
    assert "Startup banner to render" in output
    assert "Startup rule" in output
    assert "This capsule is the operational brief" in output
    assert "Do not read `.aictx/agent_runtime.md`" in output
    assert "Do not inspect `.aictx/**`" in output
    assert "Do not inspect local/global AICTX installation files" in output
    assert "Run no further AICTX discovery commands" in output
    assert "aictx finalize --repo ." in output
    assert "--status success|failure" in output
    assert "--summary" in output
    assert "First action" in output
    assert "startup_banner_policy.show_in_first_user_visible_response" not in output
    assert "Current request" in output
    assert "Avoid" in output
    assert len(output) <= 6000
    assert (repo / RESUME_CAPSULE_MARKDOWN_PATH).exists()
    assert (repo / RESUME_CAPSULE_JSON_PATH).exists()


def test_resume_infers_codex_identity_from_environment(tmp_path: Path, capsys, monkeypatch):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-from-env")
    for key in ("CLAUDE_SESSION_ID", "CLAUDE_CONVERSATION_ID", "CLAUDE_THREAD_ID", "CLAUDE_CODE_SESSION_ID"):
        monkeypatch.delenv(key, raising=False)

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "identity", "--json"])
    assert args.func(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["startup_banner_render_payload"]["header"]["agent_label"].startswith("codex@")
    assert payload["startup_banner_text"].startswith("codex@")


def test_resume_policy_requires_localized_substantive_banner(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "policy", "--json", "--agent-id", "codex"])
    assert args.func(args) == 0

    policy = json.loads(capsys.readouterr().out)["startup_banner_policy"]
    assert policy["render_payload_field"] == "startup_banner_render_payload"
    assert "current user language" in policy["instruction"]
    assert "first substantive user-visible response" in policy["instruction"]
    assert "transient progress/status message" in policy["instruction"]


def test_resume_json_schema_and_written_files(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "resume command", "--json"])
    assert args.func(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "1.0"
    assert payload["mode"] == "agent_brief"
    assert payload["request"] == "resume command"
    assert payload["startup_banner_text"]
    assert payload["startup_banner_policy"]["source"] == "resume"
    assert payload["startup_banner_policy"]["data_source"] == "load_continuity_context"
    assert payload["startup_banner_policy"]["does_not_replace_prepare_execution"] is True
    assert payload["sources"]["startup_banner"] == "load_continuity_context.startup_banner_text"
    assert payload["sources"]["final_summary"] == "finalize_execution.agent_summary_text"
    assert payload["startup_guard"]["resume_is_self_contained"] is True
    assert payload["startup_guard"]["do_not_read_runtime_files"] is True
    assert payload["startup_guard"]["do_not_inspect_aictx_installation"] is True
    assert payload["startup_guard"]["allowed_aictx_commands_before_first_task_action"] == ["resume"]
    assert payload["startup_guard"]["allowed_aictx_commands_after_task_action"] == ["finalize"]
    assert "aictx internal execution finalize" in payload["startup_guard"]["forbidden_normal_flow"]
    assert "direct shell calls to finalize_execution" in payload["startup_guard"]["forbidden_normal_flow"]
    assert ".aictx/agent_runtime.md" in payload["startup_guard"]["forbidden_before_first_task_action"]
    assert "local/global AICTX installation files" in payload["startup_guard"]["forbidden_before_first_task_action"]
    assert payload["capsule"]["first_action"]["type"] in {"open_file", "inspect_entry_points", "follow_current_request", "ask_clarification"}
    assert payload["task_state"]["status"] in {"active", "completed", "blocked", "unknown"}
    assert payload["written_files"] == {
        "markdown": ".aictx/continuity/resume_capsule.md",
        "json": ".aictx/continuity/resume_capsule.json",
    }
    assert json.loads((repo / RESUME_CAPSULE_JSON_PATH).read_text(encoding="utf-8"))["schema_version"] == "1.0"


def test_resume_json_stdout_is_valid_for_json_tool(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")

    resume = subprocess.run(
        [
            sys.executable,
            "-m",
            "aictx",
            "resume",
            "--repo",
            str(repo),
            "--request",
            "json pipe check",
            "--json",
        ],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    formatted = subprocess.run(
        [sys.executable, "-m", "json.tool"],
        input=resume.stdout,
        text=True,
        capture_output=True,
        check=True,
    )
    assert '"schema_version": "1.0"' in formatted.stdout


def test_resume_full_has_more_detail_than_default(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    (repo / DECISIONS_PATH).write_text(
        "\n".join(json.dumps({"decision": f"Decision {i}", "related_paths": []}) for i in range(6)) + "\n",
        encoding="utf-8",
    )

    parser = _parser()
    assert parser.parse_args(["resume", "--repo", str(repo), "--request", "decision", "--json"]).func(
        parser.parse_args(["resume", "--repo", str(repo), "--request", "decision", "--json"])
    ) == 0
    compact = json.loads(capsys.readouterr().out)
    assert parser.parse_args(["resume", "--repo", str(repo), "--request", "decision", "--json", "--full"]).func(
        parser.parse_args(["resume", "--repo", str(repo), "--request", "decision", "--json", "--full"])
    ) == 0
    full = json.loads(capsys.readouterr().out)

    assert len(full["capsule"]["decisions"]) > len(compact["capsule"]["decisions"])


def test_resume_active_work_state_drives_task_state(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(
        repo,
        "Implement resume command",
        initial={"next_action": "inspect src/aictx/continuity.py", "active_files": ["src/aictx/continuity.py"]},
    )
    (repo / "src/aictx").mkdir(parents=True)
    (repo / "src/aictx/continuity.py").write_text("", encoding="utf-8")

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "resume", "--json"])
    assert args.func(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["task_state"]["status"] == "active"
    assert payload["task_state"]["confidence"] == "high"
    assert payload["capsule"]["next_action"] == "inspect src/aictx/continuity.py"
    assert payload["capsule"]["first_action"]["path"] == "src/aictx/continuity.py"


def test_resume_first_action_prefers_tests_for_implementation_task(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_parser_fixture(repo)

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "validate BLOCKED parser edge cases", "--json"])
    assert args.func(args) == 0

    first_action = json.loads(capsys.readouterr().out)["capsule"]["first_action"]
    assert first_action["type"] == "open_file"
    assert first_action["path"] == "tests/test_parser.py"


def test_resume_first_action_text_precedes_source_index(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_parser_fixture(repo)

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "validate parser edge cases"])
    assert args.func(args) == 0

    output = capsys.readouterr().out
    assert output.index("First action") < output.index("Source index")


def test_resume_implementation_task_does_not_choose_readme_first(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_parser_fixture(repo)
    write_json(repo / HANDOFF_PATH, {"summary": "readme stale", "recommended_starting_points": ["README.md", "src/taskflow/parser.py"]})

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "validate parser edge cases", "--json"])
    assert args.func(args) == 0

    assert json.loads(capsys.readouterr().out)["capsule"]["first_action"]["path"] != "README.md"


def test_resume_docs_task_can_choose_readme(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_parser_fixture(repo)
    write_json(repo / HANDOFF_PATH, {"summary": "docs", "recommended_starting_points": ["src/taskflow/parser.py", "README.md"]})

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "update README quickstart documentation", "--json"])
    assert args.func(args) == 0

    assert json.loads(capsys.readouterr().out)["capsule"]["first_action"]["path"] == "README.md"


def test_resume_generic_bugfix_prefers_source_or_tests_over_readme(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_generic_repomap(
        repo,
        {
            "README.md": ("markdown", "Payment validation docs"),
            "src/payments/validation.py": ("python", "validate_payment"),
            "tests/test_payment_validation.py": ("python", "test_payment_validation_bug"),
        },
    )

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "fix payment validation bug", "--json"])
    assert args.func(args) == 0

    first_path = json.loads(capsys.readouterr().out)["capsule"]["first_action"]["path"]
    assert first_path in {"tests/test_payment_validation.py", "src/payments/validation.py"}
    assert first_path != "README.md"


def test_resume_documentation_task_prefers_readme_over_code(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_generic_repomap(
        repo,
        {
            "README.md": ("markdown", "Install instructions"),
            "src/payments/validation.py": ("python", "validate_payment"),
            "tests/test_payment_validation.py": ("python", "test_payment_validation"),
        },
    )

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "update README install instructions", "--json"])
    assert args.func(args) == 0

    assert json.loads(capsys.readouterr().out)["capsule"]["first_action"]["path"] == "README.md"


def test_resume_config_task_can_choose_config_or_ci(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_generic_repomap(
        repo,
        {
            "README.md": ("markdown", "Configuration docs"),
            "pyproject.toml": ("toml", "pytest config"),
            ".github/workflows/test.yml": ("yaml", "pytest workflow"),
            "src/aictx/cli.py": ("python", "build_parser"),
            "tests/test_cli.py": ("python", "test_cli"),
        },
    )

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "adjust pytest config", "--json"])
    assert args.func(args) == 0

    assert json.loads(capsys.readouterr().out)["capsule"]["first_action"]["path"] in {
        "pyproject.toml",
        ".github/workflows/test.yml",
    }


def test_resume_metrics_analysis_task_can_choose_metrics(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_generic_repomap(
        repo,
        {
            ".demo_metrics/with_aictx_v5/session_2_metrics.json": ("json", "session metrics"),
            ".demo_metrics/with_aictx_v5/codex_usage_session_2.json": ("json", "codex usage"),
            "src/taskflow/parser.py": ("python", "parse_tasks"),
            "tests/test_parser.py": ("python", "test_parser"),
        },
    )

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "analyze demo metrics and compare token usage", "--json"])
    assert args.func(args) == 0

    payload = json.loads(capsys.readouterr().out)
    paths = [payload["capsule"]["first_action"]["path"]]
    paths.extend(item["path"] for item in payload["capsule"]["repo_map"]["primary"] + payload["capsule"]["repo_map"]["secondary"])
    assert any(path.startswith(".demo_metrics/") for path in paths)


def test_resume_normal_coding_task_does_not_choose_metrics(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_generic_repomap(
        repo,
        {
            ".demo_metrics/with_aictx_v5/session_2_metrics.json": ("json", "parser metrics"),
            ".demo_metrics/with_aictx_v5/codex_usage_session_2.json": ("json", "parser usage"),
            "src/taskflow/parser.py": ("python", "parse_tasks"),
            "tests/test_parser.py": ("python", "test_parser_edge_cases"),
        },
    )

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "validate parser edge cases", "--json"])
    assert args.func(args) == 0

    first_path = json.loads(capsys.readouterr().out)["capsule"]["first_action"]["path"]
    assert not first_path.startswith(".demo_metrics/")
    assert "metrics" not in first_path


def test_resume_completed_previous_task_is_background(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(repo, "Old task", initial={"next_action": "done"})
    close_work_state(repo, status="resolved")
    write_json(repo / HANDOFF_PATH, {"summary": "Old task finished.", "completed": ["done"], "next_steps": ["continue old task"], "recommended_starting_points": []})

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "new task", "--json"])
    assert args.func(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["task_state"]["status"] == "completed"
    assert "background" in payload["capsule"]["resuming"]
    assert payload["capsule"]["current_request"] == "new task"
    assert payload["capsule"]["next_action"] != "continue old task"


def test_resume_missing_entry_point_lowers_confidence_and_uses_fallback(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_repomap(repo)
    write_json(
        repo / HANDOFF_PATH,
        {
            "summary": "Continue resume command.",
            "recommended_starting_points": ["src/aictx/missing.py"],
        },
    )

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "build resume capsule", "--json"])
    assert args.func(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["task_state"]["confidence"] in {"low", "medium"}
    assert "missing_entry_point:src/aictx/missing.py" in payload["warnings"]
    assert payload["capsule"]["entry_points"]
    assert payload["capsule"]["entry_points"][0]["path"] != "src/aictx/missing.py"


def test_resume_repomap_slice_has_primary_and_secondary(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_repomap(repo)

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "resume command", "--json"])
    assert args.func(args) == 0

    repo_map = json.loads(capsys.readouterr().out)["capsule"]["repo_map"]
    assert repo_map["primary"][0]["path"] in {"src/aictx/continuity.py", "tests/test_resume_command.py"}
    assert repo_map["secondary"]



def test_finalize_json_smoke(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    args = _parser().parse_args(["finalize", "--repo", str(repo), "--status", "success", "--summary", "Implemented parser edge tests", "--json"])
    assert args.func(args) == 0

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload.get("agent_summary_text") or payload.get("agent_summary")
    assert "invalid choice" not in output


def test_finalize_text_smoke(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    args = _parser().parse_args(["finalize", "--repo", str(repo), "--status", "success", "--summary", "Done"])
    assert args.func(args) == 0

    output = capsys.readouterr().out
    assert "AICTX summary" in output or "AICTX summary unavailable" in output


def test_parser_accepts_finalize_regression(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    args = _parser().parse_args([
        "finalize",
        "--repo", str(repo),
        "--status", "success",
        "--summary", "Done",
        "--json",
    ])
    assert args.func(args) == 0
    assert json.loads(capsys.readouterr().out).get("agent_summary_text")

def test_advanced_help_lists_advanced_commands(capsys):
    with pytest.raises(SystemExit) as exc:
        _parser().parse_args(["advanced", "--help"])
    assert exc.value.code == 0
    output = capsys.readouterr().out
    for command in ["suggest", "reuse", "next", "task", "messages", "map", "report", "reflect", "internal"]:
        assert command in output
    assert 'aictx resume --repo . --request "<current user request>"' in output
    assert "finalize" not in [line.strip() for line in output.splitlines() if line.strip().startswith("-")]


def test_advanced_command_without_help_lists_commands(capsys):
    args = _parser().parse_args(["advanced"])
    assert args.func(args) == 0
    output = capsys.readouterr().out
    for command in ["suggest", "reuse", "next", "task", "messages", "map", "report", "reflect", "internal"]:
        assert f"- {command}:" in output
    assert 'aictx resume --repo . --request "<current user request>"' in output
    assert "aictx finalize --repo . --status success|failure" in output
    assert "- finalize:" not in output


def test_top_level_help_hides_advanced_commands(capsys):
    with pytest.raises(SystemExit) as exc:
        _parser().parse_args(["--help"])
    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "resume" in output
    assert "finalize" in output
    assert "advanced" in output
    assert "{install,init,resume,finalize,advanced,clean,uninstall}" in output
    for command in ["suggest", "reuse", "next", "task", "messages", "map", "report", "reflect", "internal"]:
        assert f"    {command}" not in output


def test_runtime_contract_says_resume_does_not_replace_lifecycle():
    text = render_agent_runtime()
    for term in [
        "Render exactly one startup banner source",
        "resume.startup_banner_text",
        "resume.startup_banner_render_payload",
        "prepare_execution().startup_banner_text",
        "prepare_execution().startup_banner_render_payload",
        "Do not render both",
        "does not replace",
        "finalize",
        "final AICTX summary",
        "aictx resume --repo .",
        "aictx finalize --repo .",
        "finalize_execution is the middleware API behind that command",
        "do not call it directly from the shell",
        "Do not run `aictx internal execution finalize`",
        "Do not render both",
        "--json",
        "prepare/startup context → resume capsule → work → finalize → final AICTX summary/persistence",
    ]:
        assert term in text


def test_resume_startup_source_and_finalize_summary_source_are_separate(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    write_json(repo / HANDOFF_PATH, {"summary": "resume source check", "completed": ["source check done"]})

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "source check", "--json", "--agent-id", "codex", "--session-id", "visible-resume"])
    assert args.func(args) == 0
    resume_payload = json.loads(capsys.readouterr().out)
    assert "Resuming: resume source check." in resume_payload["startup_banner_text"]
    assert resume_payload["startup_banner_render_payload"]["canonical_text"] == resume_payload["startup_banner_text"]

    prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "source check",
            "agent_id": "codex",
            "adapter_id": "codex",
            "execution_id": "exec-source-check",
            "session_id": "visible-prepare",
            "files_opened": ["src/aictx/continuity.py"],
        }
    )
    finalized = finalize_execution(prepared, {"success": True, "result_summary": "Verified source separation."})
    assert finalized["agent_summary_text"].startswith("────────────────────────────────\nAICTX summary\n")
    assert finalized["agent_summary_policy"]["render_payload_field"] == "agent_summary_render_payload"


def test_resume_excludes_aictx_paths_from_action_candidates(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    (repo / ".aictx/continuity").mkdir(parents=True, exist_ok=True)
    (repo / ".aictx/continuity/resume_capsule.md").write_text("# generated", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src/resume.py").write_text("def resume_capsule():\n    pass\n", encoding="utf-8")
    write_json(repo / HANDOFF_PATH, {"summary": "generated capsule", "recommended_starting_points": [".aictx/continuity/resume_capsule.md", "src/resume.py"]})
    write_repomap_config(repo, {"enabled": True})
    write_repomap_index(
        repo,
        {
            "version": 1,
            "files": [
                {"path": ".aictx/continuity/resume_capsule.md", "language": "markdown", "symbols": [{"name": "resume capsule", "kind": "heading", "line": 1, "language": "markdown"}]},
                {"path": "src/resume.py", "language": "python", "symbols": [{"name": "resume_capsule", "kind": "function", "line": 1, "language": "python"}]},
            ],
        },
    )

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "resume capsule", "--json"])
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["capsule"]["first_action"]["path"] == "src/resume.py"
    paths = []
    paths.append(payload["capsule"]["first_action"]["path"])
    paths.extend(item["path"] for item in payload["capsule"]["entry_points"])
    paths.extend(item["path"] for item in payload["capsule"]["fallback_entry_points"])
    repo_map = payload["capsule"]["repo_map"]
    paths.extend(item["path"] for item in repo_map["primary"] + repo_map["secondary"])
    assert paths
    assert all(not path.startswith(".aictx/") for path in paths)


def test_rich_resume_fixture_stays_compact_and_compiled(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_repomap(repo)
    start_work_state(
        repo,
        "Build resume capsule",
        initial={
            "next_action": "update src/aictx/continuity.py",
            "active_files": ["src/aictx/continuity.py"],
            "verified": [f"verified item {index}" for index in range(8)],
        },
    )
    write_json(
        repo / HANDOFF_PATH,
        {
            "summary": "Previous resume capsule work " * 40,
            "completed": [f"completed resume step {index}" for index in range(12)],
            "next_steps": [f"next resume step {index}" for index in range(12)],
            "recommended_starting_points": ["src/aictx/continuity.py"],
        },
    )
    (repo / LAST_EXECUTION_SUMMARY_PATH).write_text("# Summary\n\n" + ("large summary\n" * 100), encoding="utf-8")
    _write_jsonl(
        repo / DECISIONS_PATH,
        [{"decision": f"Resume decision {index}", "related_paths": ["src/aictx/continuity.py"], "subsystem": "resume"} for index in range(10)],
    )
    _write_jsonl(
        repo / REPO_FAILURE_MEMORY_DIR / "failure_patterns.jsonl",
        [
            {
                "failure_id": f"failure-{index}",
                "signature": f"resume capsule failure {index}",
                "failure_signature": f"resume capsule failure {index}",
                "task_type": "feature_work",
                "status": "open",
                "error_text": f"resume capsule error {index}",
                "related_paths": ["src/aictx/continuity.py"],
            }
            for index in range(10)
        ],
    )
    _write_jsonl(
        repo / REPO_STRATEGY_MEMORY_DIR / "strategies.jsonl",
        [
            {
                "task_id": "resume-strategy",
                "task_text": "resume capsule",
                "task_type": "feature_work",
                "entry_points": ["src/aictx/continuity.py", "tests/test_resume_command.py"],
                "files_used": ["src/aictx/continuity.py", "tests/test_resume_command.py"],
                "commands_executed": ["pytest tests/test_resume_command.py"],
                "tests_executed": ["tests/test_resume_command.py"],
                "success": True,
            }
        ],
    )

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "resume capsule", "--task-type", "feature_work"])
    assert args.func(args) == 0
    output = capsys.readouterr().out
    assert len(output) <= 6000
    for section in ["Startup rule", "First action", "Current request", "Task state", "Next action", "Entry points", "Relevant RepoMap", "Relevant failures", "Relevant decisions", "Strategy", "Avoid"]:
        assert section in output
    assert '{"' not in output
    payload = json.loads((repo / RESUME_CAPSULE_JSON_PATH).read_text(encoding="utf-8"))
    assert payload["sources"]["handoff"]
    assert payload["sources"]["last_execution_summary"]
    assert payload["sources"]["work_state"]
    assert payload["sources"]["repo_map"]
    assert payload["capsule"]["failures"]
    assert payload["capsule"]["decisions"]
    assert payload["capsule"]["strategy"] != "None relevant"


def test_resume_capsules_are_local_generated_in_portable_mode(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, text=True, capture_output=True, check=True)
    init_repo_scaffold(repo, portable_continuity=True)
    for rel_path in [RESUME_CAPSULE_MARKDOWN_PATH.as_posix(), RESUME_CAPSULE_JSON_PATH.as_posix()]:
        path = repo / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("generated", encoding="utf-8")
        completed = subprocess.run(["git", "check-ignore", rel_path], cwd=repo, text=True, capture_output=True, check=False)
        assert completed.returncode == 0, rel_path
