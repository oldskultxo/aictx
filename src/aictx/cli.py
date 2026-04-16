from __future__ import annotations

import argparse
from pathlib import Path

from .scaffold import init_repo_scaffold
from .state import (
    CONFIG_PATH,
    ENGINE_HOME,
    GLOBAL_METRICS_DIR,
    PROJECTS_REGISTRY_PATH,
    Workspace,
    default_global_config,
    ensure_global_home,
    load_active_workspace,
    read_json,
    save_workspace,
    write_json,
)


def cmd_install(args: argparse.Namespace) -> int:
    ensure_global_home()
    config = read_json(CONFIG_PATH, default_global_config())
    if args.workspace_root:
        ws = load_active_workspace()
        root = str(Path(args.workspace_root).expanduser().resolve())
        if root not in ws.roots:
            ws.roots.append(root)
            save_workspace(ws)
    print("Created:")
    print(f"- {ENGINE_HOME}")
    print(f"- {CONFIG_PATH}")
    print(f"- {PROJECTS_REGISTRY_PATH}")
    print(f"- {GLOBAL_METRICS_DIR}")
    if args.workspace_root:
        print("Registered workspace root:")
        print(f"- {str(Path(args.workspace_root).expanduser().resolve())}")
    print("Installation complete.")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    ensure_global_home()
    created = init_repo_scaffold(repo, update_gitignore=not args.no_gitignore)
    ws = load_active_workspace()
    repo_str = str(repo)
    if repo_str not in ws.repos:
        ws.repos.append(repo_str)
        save_workspace(ws)
    registry = read_json(PROJECTS_REGISTRY_PATH, {"version": 1, "projects": []})
    if repo_str not in [row.get("repo_path") for row in registry.get("projects", [])]:
        registry["projects"].append({"name": repo.name, "repo_path": repo_str, "workspace": ws.workspace_id})
        write_json(PROJECTS_REGISTRY_PATH, registry)
    print("Created:")
    for item in created:
        print(f"- {item}")
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aictx", description="Portable multi-LLM context engine CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    install = sub.add_parser("install", help="Install global engine home")
    install.add_argument("--workspace-root", help="Initial workspace root")
    install.add_argument("--yes", action="store_true", help="Accept defaults")
    install.set_defaults(func=cmd_install)

    init = sub.add_parser("init", help="Initialize repo-local .ai_context_* scaffold")
    init.add_argument("--repo", default=".", help="Repository path")
    init.add_argument("--yes", action="store_true", help="Accept defaults")
    init.add_argument("--no-gitignore", action="store_true", help="Do not modify .gitignore")
    init.set_defaults(func=cmd_init)

    workspace = sub.add_parser("workspace", help="Workspace operations")
    workspace_sub = workspace.add_subparsers(dest="workspace_command", required=True)
    add_root = workspace_sub.add_parser("add-root", help="Register a workspace root")
    add_root.add_argument("path")
    add_root.set_defaults(func=cmd_workspace_add_root)
    list_cmd = workspace_sub.add_parser("list", help="List workspace roots and repos")
    list_cmd.set_defaults(func=cmd_workspace_list)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)
