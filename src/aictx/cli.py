from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from .scaffold import TEMPLATES_DIR, init_repo_scaffold
from .state import (
    CONFIG_PATH,
    ENGINE_HOME,
    GLOBAL_METRICS_DIR,
    PROJECTS_REGISTRY_PATH,
    default_global_config,
    ensure_global_home,
    load_active_workspace,
    read_json,
    save_workspace,
    write_json,
    workspace_path,
)


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


def cmd_install(args: argparse.Namespace) -> int:
    workspace_id = args.workspace_id or "default"
    workspace_root = args.workspace_root
    global_metrics_enabled = not args.disable_global_metrics
    cross_project_mode = args.cross_project_mode or "workspace"

    if not args.yes:
        print("AI Context Engine installer")
        print()
        print("This will:")
        print("- create your global engine home")
        print("- configure workspace discovery")
        print("- enable cross-project memory and metrics")
        print("- prepare the engine for repo initialization")
        print()
        workspace_id = ask_text("Default workspace name", workspace_id)
        if not workspace_root and ask_yes_no("Add a workspace root now?", True):
            workspace_root = ask_text("Workspace root", str(Path("~/projects").expanduser()))
        global_metrics_enabled = ask_yes_no("Enable global metrics aggregation?", global_metrics_enabled)

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

    print("Created:")
    print(f"- {ENGINE_HOME}")
    print(f"- {CONFIG_PATH}")
    print(f"- {PROJECTS_REGISTRY_PATH}")
    print(f"- {GLOBAL_METRICS_DIR}")
    print(f"- {workspace_path(workspace_id)}")
    if workspace_root:
        print("Registered workspace root:")
        print(f"- {str(Path(workspace_root).expanduser().resolve())}")
    print("Installation complete.")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    update_gitignore = not args.no_gitignore
    register_repo = not args.no_register

    if not args.yes:
        print("AI Context Engine repo initialization")
        print()
        print(f"Repository:\n- {repo}")
        print()
        print("This will:")
        print("- create local .ai_context_* runtime directories")
        print("- generate repo bootstrap artifacts")
        print("- register this repo in the active workspace")
        print("- add safe .gitignore entries")
        print()
        update_gitignore = ask_yes_no("Write .gitignore entries if missing?", update_gitignore)
        register_repo = ask_yes_no("Register this repo in the active workspace?", register_repo)
        proceed = ask_yes_no("Initialize full starter scaffold now?", True)
        if not proceed:
            print("Cancelled.")
            return 1

    ensure_global_home()
    created = init_repo_scaffold(repo, update_gitignore=update_gitignore)
    ws = load_active_workspace()
    repo_str = str(repo)
    if register_repo and repo_str not in ws.repos:
        ws.repos.append(repo_str)
        save_workspace(ws)
    registry = read_json(PROJECTS_REGISTRY_PATH, {"version": 1, "projects": []})
    if register_repo and repo_str not in [row.get("repo_path") for row in registry.get("projects", [])]:
        registry["projects"].append({"name": repo.name, "repo_path": repo_str, "workspace": ws.workspace_id})
        write_json(PROJECTS_REGISTRY_PATH, registry)
    print("Created:")
    for item in created:
        print(f"- {item}")
    if register_repo:
        print("Registered repo in workspace:")
        print(f"- {ws.workspace_id} -> {repo_str}")
    print("Initialization complete.")
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


def cmd_extract_legacy(args: argparse.Namespace) -> int:
    source = Path(args.source).expanduser().resolve()
    copied: list[str] = []
    mapping = {
        source / "delta" / "task_packet_schema.json": TEMPLATES_DIR / "context_packet_schema.json",
        source / "boot" / "user_defaults.json": TEMPLATES_DIR / "user_preferences.json",
        source / "boot" / "model_routing.json": TEMPLATES_DIR / "model_routing.json",
    }
    for src, dest in mapping.items():
        if src.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
            copied.append(f"{src} -> {dest}")
    print("Copied:")
    for row in copied:
        print(f"- {row}")
    if not copied:
        print("- nothing copied")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aictx", description="Portable multi-LLM context engine CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    install = sub.add_parser("install", help="Install global engine home")
    install.add_argument("--workspace-root", help="Initial workspace root")
    install.add_argument("--workspace-id", help="Workspace id", default="default")
    install.add_argument("--cross-project-mode", choices=["workspace", "explicit", "disabled"], help="Cross-project discovery mode")
    install.add_argument("--disable-global-metrics", action="store_true", help="Disable global metrics aggregation")
    install.add_argument("--yes", action="store_true", help="Accept defaults without prompting")
    install.set_defaults(func=cmd_install)

    init = sub.add_parser("init", help="Initialize repo-local .ai_context_* scaffold")
    init.add_argument("--repo", default=".", help="Repository path")
    init.add_argument("--yes", action="store_true", help="Accept defaults without prompting")
    init.add_argument("--no-gitignore", action="store_true", help="Do not modify .gitignore")
    init.add_argument("--no-register", action="store_true", help="Do not register repo in active workspace")
    init.set_defaults(func=cmd_init)

    workspace = sub.add_parser("workspace", help="Workspace operations")
    workspace_sub = workspace.add_subparsers(dest="workspace_command", required=True)
    add_root = workspace_sub.add_parser("add-root", help="Register a workspace root")
    add_root.add_argument("path")
    add_root.set_defaults(func=cmd_workspace_add_root)
    list_cmd = workspace_sub.add_parser("list", help="List workspace roots and repos")
    list_cmd.set_defaults(func=cmd_workspace_list)

    extract = sub.add_parser("extract-legacy", help="Copy starter templates from an existing ai_context_engine repo")
    extract.add_argument("--source", required=True, help="Path to an existing ai_context_engine repo")
    extract.set_defaults(func=cmd_extract_legacy)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)
