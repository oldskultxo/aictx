from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import core_runtime, global_metrics
from .adapters import install_global_adapters
from .agent_runtime import (
    copy_local_agent_runtime,
    install_global_agent_runtime,
    render_repo_agents_block,
    render_workspace_agents_block,
    resolve_workspace_root,
    upsert_marked_block,
)
from .middleware import cli_finalize_execution, cli_prepare_execution
from .runner_integrations import install_codex_native_integration, install_repo_runner_integrations
from .runtime_launcher import cli_run_execution
from .runtime_versioning import compat_version_payload
from .scaffold import TEMPLATES_DIR, init_repo_scaffold
from .report import build_real_usage_report
from .cleanup import clean_repo_and_unregister, uninstall_all
from .strategy_memory import select_strategy
from .state import (
    CONFIG_PATH,
    ENGINE_HOME,
    GLOBAL_METRICS_DIR,
    PROJECTS_REGISTRY_PATH,
        REPO_MEMORY_DIR,
    REPO_METRICS_DIR,
    REPO_STRATEGY_MEMORY_DIR,
    REPO_STATE_PATH,
    default_global_config,
    ensure_global_home,
    load_active_workspace,
    read_json,
    save_workspace,
    write_json,
    workspace_path,
)


COMMUNICATION_MODE_OPTIONS = [
    ("disabled", "disabled"),
    ("caveman_lite", "caveman_lite"),
    ("caveman_full", "caveman_full"),
    ("caveman_ultra", "caveman_ultra"),
]

ASCII_BANNER = "\n".join(
    [
        "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
        "~                                            ~",
        "~             .__          __                ~",
        "~     _____   |__|  ____ _/  |_ ___  ___     ~",
        "~     \\__  \\  |  |_/ ___\\\\   __\\\\  \\/  /     ~",
        "~      / __ \\_|  |\\  \\___ |  |   >    <      ~",
        "~     (____  /|__| \\___  >|__|  /__/\\_ \\     ~",
        "~          \\/          \\/             \\/     ~",
        "~                                            ~",
        "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    ]
)


class ProductArgumentParser(argparse.ArgumentParser):
    def format_help(self) -> str:
        text = super().format_help()
        filtered = [line for line in text.splitlines() if "==SUPPRESS==" not in line]
        return "\n".join(filtered).rstrip() + "\n"


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    raw = input(f"{prompt} {suffix}: ").strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes"}


def ask_text(prompt: str, default: str = "") -> str:
    shown = f" [{default}]" if default else ""
    raw = input(f"{prompt}{shown}: ").strip()
    return raw or default


def ask_choice(prompt: str, options: list[tuple[str, str]], default: str) -> str:
    labels = {value: label for value, label in options}
    if default not in labels:
        raise ValueError(f"Unknown default option: {default}")
    print(prompt)
    for index, (value, label) in enumerate(options, start=1):
        default_suffix = " (default)" if value == default else ""
        print(f"{index}. {label}{default_suffix}")
    while True:
        raw = input("Select option number: ").strip()
        if not raw:
            return default
        if raw.isdigit():
            choice = int(raw)
            if 1 <= choice <= len(options):
                return options[choice - 1][0]
        print("Invalid selection. Enter the option number.")


def persist_repo_communication_mode(repo: Path, selected_mode: str) -> None:
    prefs_path = repo / REPO_MEMORY_DIR / "user_preferences.json"
    prefs = read_json(prefs_path, {})
    communication = prefs.get("communication", {}) if isinstance(prefs.get("communication"), dict) else {}
    if selected_mode == "disabled":
        communication["layer"] = "disabled"
        communication["mode"] = "caveman_full"
    else:
        communication["layer"] = "enabled"
        communication["mode"] = selected_mode
    prefs["communication"] = communication
    write_json(prefs_path, prefs)


def read_jsonl_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(__import__("json").loads(line))
    return rows


def cmd_suggest(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    strategy = select_strategy(repo, args.task_type)
    payload = {
        "suggested_entry_points": [],
        "suggested_files": [],
        "source": "none",
        "selection_reason": "",
        "matched_signals": [],
    }
    if strategy:
        payload = {
            "suggested_entry_points": list(strategy.get("entry_points", [])) if isinstance(strategy.get("entry_points"), list) else [],
            "suggested_files": list(strategy.get("files_used", [])) if isinstance(strategy.get("files_used"), list) else [],
            "source": "strategy_memory",
            "selection_reason": str(strategy.get("selection_reason") or "recency"),
            "matched_signals": list(strategy.get("matched_signals", [])) if isinstance(strategy.get("matched_signals"), list) else [],
        }
    print(__import__("json").dumps(payload, ensure_ascii=False))
    return 0


def cmd_reuse(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    strategy = select_strategy(repo, args.task_type)
    payload = {
        "task_type": "",
        "entry_points": [],
        "files_used": [],
        "source": "none",
        "selection_reason": "",
        "matched_signals": [],
    }
    if strategy:
        payload = {
            "task_type": str(strategy.get("task_type", "") or ""),
            "entry_points": list(strategy.get("entry_points", [])) if isinstance(strategy.get("entry_points"), list) else [],
            "files_used": list(strategy.get("files_used", [])) if isinstance(strategy.get("files_used"), list) else [],
            "source": "previous_successful_execution",
            "selection_reason": str(strategy.get("selection_reason") or "recency"),
            "matched_signals": list(strategy.get("matched_signals", [])) if isinstance(strategy.get("matched_signals"), list) else [],
        }
    print(__import__("json").dumps(payload, ensure_ascii=False))
    return 0


def cmd_reflect(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    rows = read_jsonl_rows(repo / REPO_METRICS_DIR / "execution_logs.jsonl")
    latest = rows[-1] if rows else {}
    reopened = list(latest.get("files_reopened", [])) if isinstance(latest.get("files_reopened"), list) else []
    opened = list(latest.get("files_opened", [])) if isinstance(latest.get("files_opened"), list) else []
    issue = "none"
    if len(reopened) > 2:
        issue = "looping_on_same_files"
    elif len(opened) > 8:
        issue = "too_much_exploration"
    payload = {
        "reopened_files": reopened,
        "possible_issue": issue,
    }
    print(__import__("json").dumps(payload, ensure_ascii=False))
    return 0


def cmd_report_real_usage(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    print(__import__("json").dumps(build_real_usage_report(repo), ensure_ascii=False))
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    payload = clean_repo_and_unregister(repo)
    print(__import__("json").dumps(payload, ensure_ascii=False))
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    payload = uninstall_all()
    print(__import__("json").dumps(payload, ensure_ascii=False))
    return 0


def prepare_repo_runtime(repo: Path) -> list[str]:
    prefs = read_json(repo / REPO_MEMORY_DIR / "user_preferences.json", {})
    communication = prefs.get("communication", {}) if isinstance(prefs.get("communication"), dict) else {}
    layer = "enabled" if str(communication.get("layer", "")).strip() == "enabled" else "disabled"
    mode = str(communication.get("mode", "caveman_full") or "caveman_full").strip() or "caveman_full"
    state_path = repo / REPO_STATE_PATH
    state = read_json(state_path, {})
    state.update(
        {
            "version": 1,
            "engine_id": "ai_context_engine",
            "engine_name": "ai_context_engine",
            "agent_adapter": str(state.get("agent_adapter") or "generic"),
            "adapter_id": str(state.get("adapter_id") or "generic"),
            "adapter_family": str(state.get("adapter_family") or "multi_llm"),
            "provider_capabilities": list(
                state.get("provider_capabilities") or ["chat_completion", "tool_use", "structured_output", "long_context"]
            ),
            **compat_version_payload(),
            "install_mode": "repo_init",
            "engine_role": "initialized_repo_runtime",
            "adapter_runtime_enabled": True,
            "middleware_entry_mode": "auto_launcher",
            "runner_integration_status": "native_ready",
            "auto_execution_entrypoint": "aictx internal run-execution",
            "runner_native_integrations": {
                "codex": {
                    "status": "native_hardened",
                    "mechanism": "repo AGENTS.override.md; optional global ~/.codex integration via aictx install --install-codex-global",
                    "project_file": "AGENTS.override.md",
                    "optional_global_files": [
                        "~/.codex/AGENTS.override.md",
                        "~/.codex/config.toml",
                    ],
                },
                "claude": {
                    "status": "native_hardened",
                    "mechanism": "CLAUDE.md + .claude/settings.json hooks + PreToolUse enforcement",
                    "project_files": [
                        "CLAUDE.md",
                        ".claude/settings.json",
                        ".claude/hooks/aictx_pre_tool_use.py",
                    ],
                },
                "generic": {
                    "status": "wrapper_ready",
                    "mechanism": "aictx internal run-execution",
                },
            },
            "communication_layer": layer,
            "communication_mode": mode,
            "communication_contract": {
                "intermediate_updates": str(communication.get("intermediate_updates") or "suppressed"),
                "final_style": str(communication.get("final_style") or "plain_direct_final_only"),
                "single_final_answer_default": True,
                "explicit_user_override_wins": True,
                "no_intermediate_output_by_default": True,
            },
            "shared_layers": {
                "telemetry_dir": ".ai_context_engine/metrics",
                "strategy_memory_dir": ".ai_context_engine/strategy_memory",
            },
            "supports": {
                "always_on_middleware": True,
                "strategy_memory": True,
                "real_execution_logging": True,
                "feedback_reporting": True,
                "auto_execution_launcher": True,
            },
        }
    )
    write_json(state_path, state)
    created = [str(state_path)]

    execution_logs_path = repo / REPO_METRICS_DIR / "execution_logs.jsonl"
    if not execution_logs_path.exists():
        execution_logs_path.write_text("", encoding="utf-8")
        created.append(str(execution_logs_path))

    strategies_path = repo / REPO_STRATEGY_MEMORY_DIR / "strategies.jsonl"
    if not strategies_path.exists():
        strategies_path.parent.mkdir(parents=True, exist_ok=True)
        strategies_path.write_text("", encoding="utf-8")
        created.append(str(strategies_path))

    return created


def cmd_install(args: argparse.Namespace) -> int:
    workspace_id = args.workspace_id or "default"
    workspace_root = args.workspace_root
    global_metrics_enabled = not args.disable_global_metrics
    cross_project_mode = args.cross_project_mode or "workspace"
    install_codex_global = bool(getattr(args, "install_codex_global", False))
    dry_run = bool(getattr(args, "dry_run", False))

    if not args.yes:
        print("aictx install")
        print()
        print("This will:")
        print("- create the global AICTX runtime home")
        print("- configure workspace discovery")
        print("- install engine runtime artifacts")
        print("- prepare repos to work after a single `aictx init`")
        if install_codex_global:
            print("- WARNING: update global Codex files under ~/.codex because --install-codex-global was passed")
        print()
        workspace_id = ask_text("Default workspace name", workspace_id)
        if not workspace_root and ask_yes_no("Add a workspace root now?", True):
            workspace_root = ask_text("Workspace root", str(Path("~/projects").expanduser()))
        global_metrics_enabled = ask_yes_no("Enable global metrics aggregation?", global_metrics_enabled)

    if dry_run:
        planned = [
            ENGINE_HOME,
            CONFIG_PATH,
            PROJECTS_REGISTRY_PATH,
            GLOBAL_METRICS_DIR,
            workspace_path(workspace_id),
        ]
        if install_codex_global:
            planned.extend([Path.home() / ".codex" / "AGENTS.override.md", Path.home() / ".codex" / "config.toml"])
        print("Dry run. Would create/update:")
        for path in planned:
            print(f"- {path}")
        if workspace_root:
            print("Would register workspace root:")
            print(f"- {str(Path(workspace_root).expanduser().resolve())}")
        return 0

    ensure_global_home()
    config = read_json(CONFIG_PATH, default_global_config())
    config.update(
        {
            "active_workspace": workspace_id,
            "cross_project_mode": cross_project_mode,
            "global_metrics_enabled": global_metrics_enabled,
        }
    )
    write_json(CONFIG_PATH, config)

    ws = read_json(workspace_path(workspace_id), None)
    if ws is None:
        ws = {
            "version": 1,
            "workspace_id": workspace_id,
            "roots": [],
            "repos": [],
            "cross_project_mode": cross_project_mode,
        }
    if workspace_root:
        root = str(Path(workspace_root).expanduser().resolve())
        if root not in ws["roots"]:
            ws["roots"].append(root)
    write_json(workspace_path(workspace_id), ws)
    runtime_paths = install_global_agent_runtime(write_json)
    adapter_paths = install_global_adapters()
    native_runner_paths = []
    if install_codex_global:
        print("WARNING: updating global Codex files under ~/.codex because --install-codex-global was passed.")
        native_runner_paths = install_codex_native_integration()

    print("Created:")
    print(f"- {ENGINE_HOME}")
    print(f"- {CONFIG_PATH}")
    print(f"- {PROJECTS_REGISTRY_PATH}")
    print(f"- {GLOBAL_METRICS_DIR}")
    print(f"- {workspace_path(workspace_id)}")
    for path in runtime_paths:
        print(f"- {path}")
    for path in adapter_paths:
        print(f"- {path}")
    for path in native_runner_paths:
        print(f"- {path}")
    if not install_codex_global:
        print("Skipped global Codex integration. Use --install-codex-global to update ~/.codex files.")
    if workspace_root:
        print("Registered workspace root:")
        print(f"- {str(Path(workspace_root).expanduser().resolve())}")
    print("Install complete. Next: run `aictx init` inside a repository.")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    update_gitignore = not args.no_gitignore
    register_repo = not args.no_register
    selected_communication_mode = "disabled"

    if not args.yes:
        print("aictx init")
        print()
        print(f"Repository:\n- {repo}")
        print()
        print("This will:")
        print("- create the local AICTX runtime")
        print("- provision Codex and Claude native repo integration files")
        print("- make the repo ready for automatic execution-memory usage")
        print("- register this repo in the active workspace")
        print("- add safe .gitignore entries")
        print()
        update_gitignore = ask_yes_no("Write .gitignore entries if missing?", update_gitignore)
        register_repo = ask_yes_no("Register this repo in the active workspace?", register_repo)
        selected_communication_mode = ask_choice(
            "Select default communication mode for this repo:",
            COMMUNICATION_MODE_OPTIONS,
            default="disabled",
        )
        proceed = ask_yes_no("Initialize full starter scaffold now?", True)
        if not proceed:
            print("Cancelled.")
            return 1

    ensure_global_home()
    created = init_repo_scaffold(repo, update_gitignore=update_gitignore)
    persist_repo_communication_mode(repo, selected_communication_mode)
    install_global_agent_runtime(write_json)
    local_runtime_path = copy_local_agent_runtime(repo)
    prepared = prepare_repo_runtime(repo)
    runner_integrations = install_repo_runner_integrations(repo)
    upsert_marked_block(repo / "AGENTS.md", render_repo_agents_block())
    ws = load_active_workspace()
    repo_str = str(repo)
    if register_repo and repo_str not in ws.repos:
        ws.repos.append(repo_str)
        save_workspace(ws)
    registry = read_json(PROJECTS_REGISTRY_PATH, {"version": 1, "projects": []})
    if register_repo and repo_str not in [row.get("repo_path") for row in registry.get("projects", [])]:
        registry["projects"].append({"name": repo.name, "repo_path": repo_str, "workspace": ws.workspace_id})
        write_json(PROJECTS_REGISTRY_PATH, registry)
    workspace_root = resolve_workspace_root(repo, ws.roots)
    workspace_agents_path = None
    if workspace_root:
        workspace_agents_path = workspace_root / "AGENTS.md"
        upsert_marked_block(workspace_agents_path, render_workspace_agents_block())
    print("Created:")
    for item in created:
        print(f"- {item}")
    print(f"- {local_runtime_path}")
    for item in prepared:
        if item not in created and item != str(local_runtime_path):
            print(f"- {item}")
    for item in runner_integrations:
        print(f"- {item}")
    print(f"- {repo / 'AGENTS.md'}")
    if workspace_agents_path and workspace_agents_path != repo / 'AGENTS.md':
        print(f"- {workspace_agents_path}")
    if register_repo:
        print("Registered repo in workspace:")
        print(f"- {ws.workspace_id} -> {repo_str}")
    print("Init complete. Use your coding agent normally in this repo.")
    return 0


def cmd_workspace_add_root(args: argparse.Namespace) -> int:
    ensure_global_home()
    ws = load_active_workspace()
    root = str(Path(args.path).expanduser().resolve())
    if root not in ws.roots:
        ws.roots.append(root)
        save_workspace(ws)
    print(root)
    return 0


def cmd_workspace_list(args: argparse.Namespace) -> int:
    ws = load_active_workspace()
    print(f"workspace: {ws.workspace_id}")
    print("roots:")
    for root in ws.roots:
        print(f"- {root}")
    print("repos:")
    for repo in ws.repos:
        print(f"- {repo}")
    return 0



def cmd_global(args: argparse.Namespace) -> int:
    payload: dict[str, object] = {}
    if args.refresh:
        payload["refresh"] = global_metrics.refresh_global_metrics()
    if args.health_check:
        payload["health_check"] = global_metrics.run_health_check()
    if args.json:
        import json
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        import json
        print(json.dumps({
            "global_metrics_dir": global_metrics.rel(global_metrics.GLOBAL_DIR),
            "refreshed": bool(args.refresh),
            "health_checked": bool(args.health_check),
        }, indent=2, ensure_ascii=False))
    return 0


def should_render_banner(argv: list[str], stdout_is_tty: bool) -> bool:
    if not stdout_is_tty:
        return False
    if "--no-banner" in argv:
        return False
    if "--banner" in argv:
        return True
    effective = argv
    if "--" in effective:
        effective = effective[: effective.index("--")]
    suppressed_flags = {"--json", "--quiet", "-q", "-h", "--help"}
    return not any(flag in effective for flag in suppressed_flags)


def build_parser() -> argparse.ArgumentParser:
    parser = ProductArgumentParser(
        prog="aictx",
        description="Install once. Init each repo. Advanced runtime commands stay available for agents without extra user setup.",
        epilog="Quickstart:\n  aictx install\n  aictx init",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--banner", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--no-banner", action="store_true", help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True, metavar="{install,init,suggest,reflect,reuse,report,clean,uninstall}")

    install = sub.add_parser("install", help="Install global engine home")
    install.add_argument("--workspace-root", help="Initial workspace root")
    install.add_argument("--workspace-id", help="Workspace id", default="default")
    install.add_argument("--cross-project-mode", choices=["workspace", "explicit", "disabled"], help="Cross-project discovery mode")
    install.add_argument("--disable-global-metrics", action="store_true", help="Disable global metrics aggregation")
    install.add_argument("--install-codex-global", action="store_true", help="Opt in to global Codex ~/.codex integration")
    install.add_argument("--dry-run", action="store_true", help="Show planned install writes without mutating files")
    install.add_argument("--yes", action="store_true", help="Accept defaults without prompting")
    install.set_defaults(func=cmd_install)

    init = sub.add_parser("init", help="Initialize repo-local .ai_context_* scaffold")
    init.add_argument("--repo", default=".", help="Repository path")
    init.add_argument("--yes", action="store_true", help="Accept defaults without prompting")
    init.add_argument("--no-gitignore", action="store_true", help="Do not modify .gitignore")
    init.add_argument("--no-register", action="store_true", help="Do not register repo in active workspace")
    init.set_defaults(func=cmd_init)

    suggest = sub.add_parser("suggest", help="Get deterministic next-step guidance from strategy memory")
    suggest.add_argument("--repo", default=".", help="Repository root")
    suggest.add_argument("--task-type", default="", help="Optional task type filter")
    suggest.set_defaults(func=cmd_suggest)

    reflect = sub.add_parser("reflect", help="Reflect on recent exploration patterns from real execution logs")
    reflect.add_argument("--repo", default=".", help="Repository root")
    reflect.set_defaults(func=cmd_reflect)

    reuse = sub.add_parser("reuse", help="Return the latest reusable successful strategy")
    reuse.add_argument("--repo", default=".", help="Repository root")
    reuse.add_argument("--task-type", default="", help="Optional task type filter")
    reuse.set_defaults(func=cmd_reuse)

    clean = sub.add_parser("clean", help="Remove AICTX content from the current repository")
    clean.add_argument("--repo", default=".", help="Repository root")
    clean.set_defaults(func=cmd_clean)

    uninstall = sub.add_parser("uninstall", help="Remove AICTX content from all registered repos and global config")
    uninstall.set_defaults(func=cmd_uninstall)

    report = sub.add_parser("report", help="Report real aggregated runtime usage")
    report_sub = report.add_subparsers(dest="report_command", required=True)
    report_real_usage = report_sub.add_parser("real-usage", help="Aggregate real execution logs and feedback")
    report_real_usage.add_argument("--repo", default=".", help="Repository root")
    report_real_usage.set_defaults(func=cmd_report_real_usage)

    internal = sub.add_parser("internal", help=argparse.SUPPRESS)
    internal_sub = internal.add_subparsers(dest="internal_command", required=True)

    workspace = internal_sub.add_parser("workspace", help=argparse.SUPPRESS)
    workspace_sub = workspace.add_subparsers(dest="workspace_command", required=True)
    add_root = workspace_sub.add_parser("add-root", help=argparse.SUPPRESS)
    add_root.add_argument("path")
    add_root.set_defaults(func=cmd_workspace_add_root)
    list_cmd = workspace_sub.add_parser("list", help=argparse.SUPPRESS)
    list_cmd.set_defaults(func=cmd_workspace_list)

    boot = internal_sub.add_parser("boot", help=argparse.SUPPRESS)
    boot.add_argument("--repo", default=".", help="Repository path for session boot context.")
    boot.set_defaults(func=core_runtime.cli_boot)

    query = internal_sub.add_parser("query", help=argparse.SUPPRESS)
    query.add_argument("--prefs", action="store_true", help="Query preferences.")
    query.add_argument("--architecture", action="store_true", help="Query architecture decisions.")
    query.add_argument("--symptom", action="store_true", help="Query symptom index.")
    query.add_argument("query", nargs="*", help="Keyword query.")
    query.set_defaults(func=core_runtime.cli_query)

    packet = internal_sub.add_parser("packet", help=argparse.SUPPRESS)
    packet.add_argument("--task", required=True, help="Task description.")
    packet.add_argument("--project", help="Optional project override.")
    packet.add_argument("--task-type", help="Optional explicit task type override.")
    packet.set_defaults(func=core_runtime.cli_packet)

    route = internal_sub.add_parser("route", help=argparse.SUPPRESS)
    route.add_argument("--task", required=True, help="Task description.")
    route.set_defaults(func=core_runtime.cli_route)

    migrate = internal_sub.add_parser("migrate", help=argparse.SUPPRESS)
    migrate.set_defaults(func=core_runtime.cli_migrate)

    stale = internal_sub.add_parser("detect-stale", help=argparse.SUPPRESS)
    stale.set_defaults(func=core_runtime.cli_stale)

    compact = internal_sub.add_parser("compact", help=argparse.SUPPRESS)
    compact.add_argument("--apply", action="store_true", help="Reserved for future non-dry-run compaction.")
    compact.set_defaults(func=core_runtime.cli_compact)

    gitignore = internal_sub.add_parser("ensure-gitignore", help=argparse.SUPPRESS)
    gitignore.add_argument("--repo", required=True, help="Repository root to update.")
    gitignore.set_defaults(func=core_runtime.cli_gitignore)

    touch = internal_sub.add_parser("touch", help=argparse.SUPPRESS)
    touch.add_argument("items", nargs="+", help="Record ids or note paths.")
    touch.set_defaults(func=core_runtime.cli_touch)

    new_note = internal_sub.add_parser("new-note", help=argparse.SUPPRESS)
    new_note.add_argument("--path", required=True, help="Note path relative to repo root.")
    new_note.add_argument("--title", required=True, help="Markdown H1 title.")
    new_note.add_argument("--tags", nargs="*", default=[], help="Optional tag list.")
    new_note.add_argument("--task-type", help="Optional task type for derived task-memory routing.")
    new_note.set_defaults(func=core_runtime.cli_new_note)

    failure = internal_sub.add_parser("failure", help=argparse.SUPPRESS)
    failure.add_argument("--failure-id", required=True, help="Stable failure identifier.")
    failure.add_argument("--category", default="unknown", help="Failure category.")
    failure.add_argument("--title", required=True, help="Short failure title.")
    failure.add_argument("--symptoms", nargs="*", default=[], help="Observed symptoms.")
    failure.add_argument("--root-cause", default="", help="Likely root cause.")
    failure.add_argument("--solution", default="", help="Known resolution.")
    failure.add_argument("--files", nargs="*", default=[], help="Files or areas involved.")
    failure.add_argument("--commands", nargs="*", default=[], help="Related commands.")
    failure.add_argument("--confidence", type=float, default=0.75, help="Reuse confidence.")
    failure.add_argument("--notes", default="", help="Optional manual notes.")
    failure.set_defaults(func=core_runtime.cli_failure)

    task_memory = internal_sub.add_parser("task-memory", help=argparse.SUPPRESS)
    task_memory.add_argument("--task-type", required=True, help="Task type bucket.")
    task_memory.add_argument("--title", required=True, help="Short reusable pattern title.")
    task_memory.add_argument("--summary", required=True, help="Compact reusable lesson.")
    task_memory.add_argument("--signals", action="append", help="Optional routing or trigger signals.")
    task_memory.add_argument("--common-locations", action="append", help="Optional repeated locations.")
    task_memory.add_argument("--patterns", action="append", help="Optional task patterns or tags.")
    task_memory.add_argument("--constraints", action="append", help="Optional durable constraints.")
    task_memory.add_argument("--frequent-mistakes", action="append", help="Optional mistakes to avoid.")
    task_memory.add_argument("--preferred-validation", action="append", help="Optional validation guidance.")
    task_memory.add_argument("--related-files", action="append", help="Optional related files.")
    task_memory.add_argument("--confidence", type=float, default=0.75, help="Confidence score between 0 and 1.")
    task_memory.set_defaults(func=core_runtime.cli_task_memory)

    graph = internal_sub.add_parser("memory-graph", help=argparse.SUPPRESS)
    graph.add_argument("--refresh", action="store_true", help="Rebuild the memory graph from current artifacts.")
    graph.add_argument("--query", help="Node id or label query.")
    graph.add_argument("--depth", type=int, default=1, help="Expansion depth for queries.")
    graph.set_defaults(func=core_runtime.cli_memory_graph)

    library = internal_sub.add_parser("library", help=argparse.SUPPRESS)
    library_sub = library.add_subparsers(dest="library_command")
    learn = library_sub.add_parser("learn", help=argparse.SUPPRESS)
    learn.add_argument("mod_id", help="Mod identifier.")
    learn.add_argument("--alias", dest="aliases", action="append", default=[], help="Optional alias.")
    process = library_sub.add_parser("process", help=argparse.SUPPRESS)
    process.add_argument("mod_id", help="Mod identifier.")
    add_source = library_sub.add_parser("add-source", help=argparse.SUPPRESS)
    add_source.add_argument("mod_id", help="Mod identifier.")
    add_source.add_argument("--url", required=True, help="Remote source URL.")
    add_source.add_argument("--type", dest="declared_type", default="auto", help="Declared source type: auto|html|pdf|md|txt.")
    add_source.add_argument("--tag", dest="tags", action="append", default=[], help="Optional source tag.")
    fetch = library_sub.add_parser("fetch-sources", help=argparse.SUPPRESS)
    fetch.add_argument("mod_id", help="Mod identifier.")
    fetch.add_argument("--source-id", help="Optional source id to fetch.")
    fetch.add_argument("--force", action="store_true", help="Force a new fetch even when checksum is unchanged.")
    retrieve = library_sub.add_parser("retrieve", help=argparse.SUPPRESS)
    retrieve.add_argument("--task", required=True, help="Task description.")
    library_sub.add_parser("status", help=argparse.SUPPRESS)
    library.set_defaults(func=core_runtime.cli_library)

    global_cmd = internal_sub.add_parser("global", help=argparse.SUPPRESS)
    global_cmd.add_argument("--refresh", action="store_true", help="Refresh projects index and global savings artifacts.")
    global_cmd.add_argument("--health-check", action="store_true", help="Run global health checks.")
    global_cmd.add_argument("--json", action="store_true", help="Print full JSON output.")
    global_cmd.set_defaults(func=cmd_global)

    execution = internal_sub.add_parser("execution", help=argparse.SUPPRESS)
    execution_sub = execution.add_subparsers(dest="execution_command", required=True)

    prepare = execution_sub.add_parser("prepare", help=argparse.SUPPRESS)
    prepare.add_argument("--repo", default=".", help="Repository root.")
    prepare.add_argument("--request", required=True, help="User request or task description.")
    prepare.add_argument("--agent-id", required=True, help="Agent identifier.")
    prepare.add_argument("--adapter-id", help="Optional adapter identifier.")
    prepare.add_argument("--execution-id", required=True, help="Stable execution id.")
    prepare.add_argument("--timestamp", help="Optional ISO timestamp override.")
    prepare.add_argument("--task-type", help="Optional declared task type.")
    prepare.add_argument("--execution-mode", choices=["plain", "skill"], help="Optional explicit execution mode.")
    prepare.add_argument("--skill-id", default="", help="Optional skill identifier.")
    prepare.add_argument("--skill-name", default="", help="Optional skill name.")
    prepare.add_argument("--skill-path", default="", help="Optional skill path.")
    prepare.add_argument("--skill-source", default="", help="Optional skill source.")
    prepare.add_argument("--files-opened", nargs="*", default=[], help="Explicit files opened during execution")
    prepare.add_argument("--files-reopened", nargs="*", default=[], help="Explicit files reopened during execution")
    prepare.set_defaults(func=cli_prepare_execution)

    finalize = execution_sub.add_parser("finalize", help=argparse.SUPPRESS)
    finalize.add_argument("--prepared", required=True, help="Path to prepared execution JSON.")
    finalize.add_argument("--success", action="store_true", help="Mark execution as successful.")
    finalize.add_argument("--result-summary", default="", help="Execution result summary.")
    finalize.add_argument("--validated-learning", action="store_true", help="Persist validated learning when successful.")
    finalize.add_argument("--files-opened", nargs="*", default=[], help="Explicit files opened during execution")
    finalize.add_argument("--files-reopened", nargs="*", default=[], help="Explicit files reopened during execution")
    finalize.set_defaults(func=cli_finalize_execution)

    run_execution = internal_sub.add_parser("run-execution", help=argparse.SUPPRESS)
    run_execution.add_argument("--repo", default=".", help="Repository root.")
    run_execution.add_argument("--request", required=True, help="User request or task description.")
    run_execution.add_argument("--agent-id", required=True, help="Agent identifier.")
    run_execution.add_argument("--adapter-id", help="Optional adapter identifier.")
    run_execution.add_argument("--execution-id", default="auto", help="Stable execution id or 'auto'.")
    run_execution.add_argument("--task-type", help="Optional declared task type.")
    run_execution.add_argument("--execution-mode", choices=["plain", "skill"], default="plain", help="Optional explicit execution mode.")
    run_execution.add_argument("--skill-id", default="", help="Optional skill identifier.")
    run_execution.add_argument("--skill-name", default="", help="Optional skill name.")
    run_execution.add_argument("--skill-path", default="", help="Optional skill path.")
    run_execution.add_argument("--skill-source", default="", help="Optional skill source.")
    run_execution.add_argument("--validated-learning", action="store_true", help="Persist validated learning when the wrapped command succeeds.")
    run_execution.add_argument("--json", action="store_true", help="Print full JSON outcome instead of only command output.")
    run_execution.add_argument("--files-opened", nargs="*", default=[], help="Explicit files opened during execution")
    run_execution.add_argument("--files-reopened", nargs="*", default=[], help="Explicit files reopened during execution")
    run_execution.add_argument("command", nargs=argparse.REMAINDER, help="Wrapped command after --.")
    run_execution.set_defaults(func=cli_run_execution)

    return parser


def main() -> int:
    if should_render_banner(sys.argv[1:], sys.stdout.isatty()):
        print(ASCII_BANNER)
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)
