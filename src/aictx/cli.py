from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from . import core_runtime
from ._version import __version__
from .adapters import install_global_adapters
from .area_memory import derive_area_id
from .agent_runtime import (
    copy_local_agent_runtime,
    install_global_agent_runtime,
    render_repo_agents_block,
    render_workspace_agents_block,
    resolve_workspace_root,
    upsert_marked_block,
)
from .middleware import cli_finalize_execution, cli_prepare_execution, finalize_execution, now_iso, prepare_execution
from .messages import MESSAGE_MODE_MUTED, MESSAGE_MODE_UNMUTED, get_message_mode, set_message_mode
from .portability import detect_portable_continuity_from_gitignore, load_portability_state
from .continuity import build_resume_capsule, load_continuity_context, render_next_text, render_resume_capsule
from .runner_integrations import install_codex_native_integration, install_repo_runner_integrations
from .runtime_launcher import cli_run_execution
from .runtime_compact import compact_repo_records
from .runtime_versioning import compat_version_payload
from .scaffold import TEMPLATES_DIR, ensure_repomap_scaffold, ensure_repo_user_preferences, init_repo_scaffold
from .report import build_real_usage_report
from .repo_map.config import load_repomap_config, load_repomap_manifest, load_repomap_status, resolve_repo_repomap_config, write_repomap_config, write_repomap_status
from .repo_map.query import query_repo_map
from .repo_map.refresh import refresh_repo_map
from .repo_map.paths import repo_map_config_path, repo_map_index_path, repo_map_manifest_path, repo_map_status_path
from .repo_map.provider import check_tree_sitter_available
from .repo_map.setup import (
    install_repomap_dependency,
    repomap_dependency_available,
    update_global_repomap_config,
)
from .cleanup import clean_repo_and_unregister, remove_marked_block, uninstall_all
from .strategy_memory import select_strategy
from .runtime_tasks import resolve_task_type
from .work_state import changed_work_state_fields, close_work_state, list_work_states, load_active_work_state, load_work_state, render_work_state_summary, resume_work_state, start_work_state, update_work_state

from .state import (
    CONFIG_PATH,
    ENGINE_HOME,
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


def _infer_agent_id(explicit: str = "") -> str:
    value = str(explicit or "").strip()
    if value:
        return value
    if any(os.environ.get(key) for key in ("CODEX_THREAD_ID", "CODEX_SESSION_ID", "CODEX_CONVERSATION_ID", "CODEX_CI")):
        return "codex"
    if any(os.environ.get(key) for key in ("CLAUDE_SESSION_ID", "CLAUDE_CONVERSATION_ID", "CLAUDE_THREAD_ID", "CLAUDE_CODE_SESSION_ID")):
        return "claude"
    return "generic"


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


def resolve_init_portable_continuity(args: argparse.Namespace, repo: Path) -> bool:
    if getattr(args, "portable_continuity", False):
        return True
    if getattr(args, "no_portable_continuity", False):
        return False

    existing_payload = load_portability_state(repo)
    existing = existing_payload.get("enabled") if isinstance(existing_payload, dict) else None
    if existing is None:
        existing = detect_portable_continuity_from_gitignore(repo)

    default = bool(existing) if existing is not None else False
    if getattr(args, "yes", False):
        return default
    if not sys.stdin.isatty():
        return default

    return ask_yes_no(
        "Enable AICTX git-portable continuity?\n\n"
        "This allows committing a safe subset of .aictx/ so Work State,\n"
        "handoffs, decisions, failure memory, strategy memory and RepoMap config\n"
        "can travel with the repository.\n\n"
        "Volatile/local artifacts such as metrics, session identity, execution logs\n"
        "and RepoMap indexes will remain ignored.\n\n"
        "Enable git-portable continuity?",
        default=default,
    )


def persist_repo_communication_mode(repo: Path, selected_mode: str) -> None:
    ensure_repo_user_preferences(repo)
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
    context = _strategy_cli_context(args)
    strategy = select_strategy(repo, context["task_type"], **context["signals"])
    payload = {
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
    if strategy:
        payload = {
            "suggested_entry_points": list(strategy.get("entry_points", [])) if isinstance(strategy.get("entry_points"), list) else [],
            "suggested_files": list(strategy.get("files_used", [])) if isinstance(strategy.get("files_used"), list) else [],
            "source": "strategy_memory",
            "selection_reason": str(strategy.get("selection_reason") or "recency"),
            "matched_signals": list(strategy.get("matched_signals", [])) if isinstance(strategy.get("matched_signals"), list) else [],
            "similarity_breakdown": dict(strategy.get("similarity_breakdown", {})) if isinstance(strategy.get("similarity_breakdown"), dict) else {},
            "overlapping_files": list(strategy.get("overlapping_files", [])) if isinstance(strategy.get("overlapping_files"), list) else [],
            "related_commands": list(strategy.get("related_commands", [])) if isinstance(strategy.get("related_commands"), list) else [],
            "related_tests": list(strategy.get("related_tests", [])) if isinstance(strategy.get("related_tests"), list) else [],
        }
    print(__import__("json").dumps(payload, ensure_ascii=False))
    return 0


def cmd_reuse(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    context = _strategy_cli_context(args)
    strategy = select_strategy(repo, context["task_type"], **context["signals"])
    payload = {
        "task_type": "",
        "entry_points": [],
        "files_used": [],
        "source": "none",
        "selection_reason": "",
        "matched_signals": [],
        "similarity_breakdown": {},
        "overlapping_files": [],
        "related_commands": [],
        "related_tests": [],
    }
    if strategy:
        payload = {
            "task_type": str(strategy.get("task_type", "") or ""),
            "entry_points": list(strategy.get("entry_points", [])) if isinstance(strategy.get("entry_points"), list) else [],
            "files_used": list(strategy.get("files_used", [])) if isinstance(strategy.get("files_used"), list) else [],
            "source": "previous_successful_execution",
            "selection_reason": str(strategy.get("selection_reason") or "recency"),
            "matched_signals": list(strategy.get("matched_signals", [])) if isinstance(strategy.get("matched_signals"), list) else [],
            "similarity_breakdown": dict(strategy.get("similarity_breakdown", {})) if isinstance(strategy.get("similarity_breakdown"), dict) else {},
            "overlapping_files": list(strategy.get("overlapping_files", [])) if isinstance(strategy.get("overlapping_files"), list) else [],
            "related_commands": list(strategy.get("related_commands", [])) if isinstance(strategy.get("related_commands"), list) else [],
            "related_tests": list(strategy.get("related_tests", [])) if isinstance(strategy.get("related_tests"), list) else [],
        }
    print(__import__("json").dumps(payload, ensure_ascii=False))
    return 0


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def _parse_json_dict(raw: str, *, field_name: str) -> dict[str, Any]:
    try:
        payload = json.loads(str(raw or ""))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid {field_name} JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    return payload


def _parse_json_file(path: str, *, field_name: str) -> dict[str, Any]:
    target = Path(path).expanduser()
    try:
        return _parse_json_dict(target.read_text(encoding="utf-8"), field_name=field_name)
    except OSError as exc:
        raise ValueError(f"Invalid {field_name} file: {exc}") from exc


def _patch_from_args(args: argparse.Namespace, *, required: bool = False) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    from_file = str(getattr(args, "from_file", "") or "").strip()
    raw_patch = str(getattr(args, "json_patch", "") or "").strip()
    if from_file:
        patch.update(_parse_json_file(from_file, field_name="from-file"))
    if raw_patch:
        patch.update(_parse_json_dict(raw_patch, field_name="json-patch"))
    if required and not patch:
        raise ValueError("json-patch or from-file is required")
    return patch


def _state_with_update_meta(state: dict[str, Any], changed_fields: list[str], *, action: str = "updated") -> dict[str, Any]:
    payload = dict(state)
    payload[action] = True
    payload["changed_fields"] = changed_fields
    return payload


def cmd_task_start(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    initial = _parse_json_dict(args.initial_json, field_name="initial") if str(getattr(args, "initial_json", "") or "").strip() else {}
    state = start_work_state(repo, args.goal, task_id=getattr(args, "task_id", None), initial=initial)
    if bool(getattr(args, "json", False)):
        _print_json(state)
    else:
        print(render_work_state_summary(state))
    return 0


def cmd_task_status(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    if bool(getattr(args, "all", False)):
        return cmd_task_list(args)
    state = load_active_work_state(repo)
    if bool(getattr(args, "json", False)):
        if not state:
            _print_json({"active": False})
        else:
            payload = {"active": True}
            payload.update(state)
            _print_json(payload)
    else:
        print(render_work_state_summary(state) if state else "No active task.")
    return 0


def cmd_messages_mute(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    payload = set_message_mode(repo, MESSAGE_MODE_MUTED)
    if bool(getattr(args, "json", False)):
        _print_json(payload)
    else:
        print("AICTX messages: muted")
    return 0


def cmd_messages_unmute(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    payload = set_message_mode(repo, MESSAGE_MODE_UNMUTED)
    if bool(getattr(args, "json", False)):
        _print_json(payload)
    else:
        print("AICTX messages: unmuted")
    return 0


def cmd_messages_status(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    mode = get_message_mode(repo)
    payload = {"messages": {"mode": mode}}
    if bool(getattr(args, "json", False)):
        _print_json(payload)
    else:
        print(f"AICTX messages: {mode}")
    return 0


def _task_list_payload(repo: Path) -> dict[str, Any]:
    active_task_id = str(load_active_work_state(repo).get("task_id") or "")
    tasks = []
    for state in list_work_states(repo):
        item = {
            "task_id": str(state.get("task_id") or ""),
            "status": str(state.get("status") or ""),
            "goal": str(state.get("goal") or ""),
            "updated_at": str(state.get("updated_at") or ""),
            "active": str(state.get("task_id") or "") == active_task_id,
        }
        tasks.append(item)
    return {"tasks": tasks}


def _render_task_list(tasks: list[dict[str, Any]]) -> str:
    if not tasks:
        return "No task threads."
    lines = []
    for task in tasks:
        active = " active" if bool(task.get("active")) else ""
        goal = str(task.get("goal") or task.get("task_id") or "").strip()
        lines.append(f"{task.get('task_id')} [{task.get('status')}{active}] {goal}".strip())
    return "\n".join(lines)


def cmd_task_list(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    payload = _task_list_payload(repo)
    if bool(getattr(args, "json", False)):
        _print_json(payload)
    else:
        print(_render_task_list(list(payload.get("tasks", []))))
    return 0


def cmd_task_show(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    state = load_work_state(repo, str(getattr(args, "task_id", "") or ""))
    if bool(getattr(args, "json", False)):
        _print_json(state if state else {"found": False})
    else:
        print(render_work_state_summary(state) if state else "Task not found.")
    return 0


def cmd_task_update(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    patch = _patch_from_args(args, required=True)
    before = load_work_state(repo, str(getattr(args, "task_id", "") or "")) if getattr(args, "task_id", None) else load_active_work_state(repo)
    state = update_work_state(repo, patch, task_id=getattr(args, "task_id", None))
    changed_fields = changed_work_state_fields(before, state, patch)
    if bool(getattr(args, "json", False)):
        _print_json(_state_with_update_meta(state, changed_fields))
    else:
        if changed_fields:
            print("Updated: " + ", ".join(changed_fields))
        print(render_work_state_summary(state))
    return 0


def cmd_task_resume(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    state = resume_work_state(repo, str(getattr(args, "task_id", "") or ""))
    if bool(getattr(args, "json", False)):
        _print_json(state if state else {"resumed": False})
    else:
        print(render_work_state_summary(state) if state else "Task not found.")
    return 0


def cmd_task_close(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    patch = _patch_from_args(args)
    state = close_work_state(
        repo,
        task_id=getattr(args, "task_id", None),
        status=str(getattr(args, "status", "resolved") or "resolved"),
        patch=patch,
    )
    if bool(getattr(args, "json", False)):
        changed_fields = changed_work_state_fields({}, state, patch)
        _print_json(_state_with_update_meta(state, changed_fields, action="closed"))
    else:
        print(render_work_state_summary(state))
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    request = str(getattr(args, "request", "") or "").strip()
    files = _list_arg(args, "files_opened")
    commands = _list_arg(args, "commands_executed")
    tests = _list_arg(args, "tests_executed")
    errors = _list_arg(args, "notable_errors")
    explicit_task_type = str(getattr(args, "task_type", "") or "").strip()
    resolved = resolve_task_type(request, explicit_task_type=explicit_task_type or None, touched_files=files)
    task_type = str(resolved.get("task_type") or explicit_task_type or "")
    context = load_continuity_context(
        repo,
        task_type=task_type,
        request_text=request,
        files=files,
        primary_entry_point=files[0] if files else None,
        commands=commands,
        tests=tests,
        errors=errors,
        area_id=derive_area_id(files + tests) if files or tests else "",
    )
    brief = context.get("continuity_brief", {}) if isinstance(context.get("continuity_brief"), dict) else {}
    if bool(getattr(args, "json", False)):
        print(__import__("json").dumps({"continuity_brief": brief, "ranked_items": context.get("ranked_items", []), "why_loaded": context.get("why_loaded", {})}, ensure_ascii=False))
    else:
        print(render_next_text(brief))
    return 0


def cmd_finalize(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    status = str(getattr(args, "status", "") or "")
    summary = str(getattr(args, "summary", "") or "")
    error = str(getattr(args, "error", "") or "").strip()
    notable_errors = _list_arg(args, "notable_errors")
    if error:
        notable_errors.append(error)
    request = str(getattr(args, "request", "") or summary).strip()
    prepared = prepare_execution(
        {
            "repo_root": repo.as_posix(),
            "user_request": request,
            "agent_id": _infer_agent_id(str(getattr(args, "agent_id", "") or "")),
            "adapter_id": str(getattr(args, "adapter_id", "") or getattr(args, "agent_id", "") or "generic"),
            "execution_id": str(getattr(args, "session_id", "") or f"cli-finalize-{now_iso()}"),
            "timestamp": now_iso(),
            "declared_task_type": str(getattr(args, "task_type", "") or "") or None,
            "execution_mode": "plain",
            "files_opened": _list_arg(args, "files_opened"),
            "files_edited": _list_arg(args, "files_edited"),
            "files_reopened": [],
            "commands_executed": _list_arg(args, "commands_executed"),
            "tests_executed": _list_arg(args, "tests_executed"),
            "notable_errors": notable_errors,
            "error_events": [],
            "work_state": {},
            "skill_metadata": {},
        }
    )
    result = {
        "success": status == "success",
        "result_summary": summary,
        "validated_learning": False,
        "decisions": [],
        "semantic_repo": [],
        "work_state": {},
    }
    payload = finalize_execution(prepared, result)
    if bool(getattr(args, "json", False)):
        _print_json(payload)
    else:
        print(str(payload.get("agent_summary_text") or "AICTX summary unavailable"))
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    task = str(getattr(args, "task", "") or "").strip()
    request = task or str(getattr(args, "request", "") or "").strip()
    explicit_task_type = str(getattr(args, "task_type", "") or "").strip()
    resolved = resolve_task_type(request, explicit_task_type=explicit_task_type or None, touched_files=[])
    task_type = str(resolved.get("task_type") or explicit_task_type or "")
    payload = build_resume_capsule(
        repo,
        request_text=request,
        full=bool(getattr(args, "full", False)),
        task_type=task_type,
        agent_id=_infer_agent_id(str(getattr(args, "agent_id", "") or "")),
        adapter_id=str(getattr(args, "adapter_id", "") or ""),
        session_id=str(getattr(args, "session_id", "") or ""),
    )
    if bool(getattr(args, "json", False)):
        _print_json(payload)
    else:
        print(render_resume_capsule(payload, full=bool(getattr(args, "full", False))), end="")
    return 0


def cmd_advanced(args: argparse.Namespace) -> int:
    print(
        "\n".join(
            [
                "AICTX advanced commands",
                "",
                "Normal agent lifecycle:",
                '  aictx resume --repo . --task "<task goal>" --json',
                '  aictx finalize --repo . --status success|failure --summary "<what happened>" --json',
                "",
                "Advanced/diagnostic/building-block commands:",
                "- suggest: deterministic next-step guidance from strategy memory",
                "- reuse: latest reusable successful strategy",
                "- next: compact continuity guidance",
                "- task: repo-local Work State management",
                "- messages: automatic runtime message visibility",
                "- map: RepoMap operations",
                "- report: real runtime usage reports",
                "- reflect: exploration pattern diagnostics",
                "- internal: internal runtime/building-block commands",
            ]
        )
    )
    return 0


def _repomap_status_payload(repo: Path) -> dict[str, Any]:
    config = load_repomap_config(repo)
    status = load_repomap_status(repo)
    manifest = load_repomap_manifest(repo)
    files_indexed = int(manifest.get("files_indexed", 0)) if isinstance(manifest, dict) else 0
    symbols_indexed = int(manifest.get("symbols_indexed", 0)) if isinstance(manifest, dict) else 0
    return {
        "enabled": bool(status.get("enabled", config.get("enabled", False))),
        "available": bool(status.get("available", False)),
        "provider": str(status.get("provider") or config.get("provider") or "tree_sitter"),
        "files_indexed": files_indexed,
        "symbols_indexed": symbols_indexed,
        "last_refresh_status": str(status.get("last_refresh_status") or "never"),
    }


def cmd_map_status(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    payload = _repomap_status_payload(repo)
    if bool(getattr(args, "json", False)):
        print(__import__("json").dumps(payload, ensure_ascii=False))
        return 0
    print("AICTX map status")
    print(f"- enabled: {payload['enabled']}")
    print(f"- available: {payload['available']}")
    print(f"- provider: {payload['provider']}")
    print(f"- files_indexed: {payload['files_indexed']}")
    print(f"- symbols_indexed: {payload['symbols_indexed']}")
    print(f"- last_refresh_status: {payload['last_refresh_status']}")
    return 0


def cmd_map_refresh(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    requested_mode = "full" if bool(getattr(args, "full", False)) else "incremental"
    payload = refresh_repo_map(repo, mode=requested_mode)
    output = {
        "requested_mode": requested_mode,
        "executed_mode": str(payload.get("mode") or "full"),
        **payload,
    }
    if bool(getattr(args, "json", False)):
        print(__import__("json").dumps(output, ensure_ascii=False))
        return 0
    print("AICTX map refresh")
    print(f"- requested_mode: {requested_mode}")
    print(f"- status: {output.get('status', 'unknown')}")
    if "files_indexed" in output:
        print(f"- files_indexed: {output['files_indexed']}")
    if "symbols_indexed" in output:
        print(f"- symbols_indexed: {output['symbols_indexed']}")
    if "reason" in output and str(output.get("reason", "")).strip():
        print(f"- reason: {output['reason']}")
    return 0


def cmd_map_query(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    text = str(getattr(args, "text", "") or "")
    limit = int(getattr(args, "limit", 10) or 10)
    results = query_repo_map(repo, text, limit=limit)
    if bool(getattr(args, "json", False)):
        print(__import__("json").dumps(results, ensure_ascii=False))
        return 0
    print(f"AICTX map query: {text}")
    if not results:
        print("- no matches")
        return 0
    for item in results:
        symbols = ", ".join([str(symbol) for symbol in item.get("symbols", []) if str(symbol).strip()])
        print(f"- {item.get('path', '')} (score={item.get('score', 0)})")
        print(f"  reasons: {', '.join(item.get('reasons', []))}")
        if symbols:
            print(f"  symbols: {symbols}")
    return 0


def _list_arg(args: argparse.Namespace, key: str) -> list[str]:
    value = getattr(args, key, []) or []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _strategy_cli_context(args: argparse.Namespace) -> dict[str, Any]:
    request = str(getattr(args, "request", "") or "").strip()
    files = _list_arg(args, "files_opened")
    commands = _list_arg(args, "commands_executed")
    tests = _list_arg(args, "tests_executed")
    errors = _list_arg(args, "notable_errors")
    explicit_task_type = str(getattr(args, "task_type", "") or "").strip()
    task_type = explicit_task_type
    if not task_type and request:
        task_type = str(resolve_task_type(request, touched_files=files).get("task_type") or "")
        if task_type == "unknown":
            task_type = ""
    signals = {
        "files": files,
        "primary_entry_point": files[0] if files else None,
        "request_text": request,
        "commands": commands,
        "tests": tests,
        "errors": errors,
        "area_id": derive_area_id(files + tests) if files or tests else None,
    }
    return {"task_type": task_type, "signals": signals}


def cmd_reflect(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    rows = read_jsonl_rows(repo / REPO_METRICS_DIR / "execution_logs.jsonl")
    latest = rows[-1] if rows else {}
    reopened = list(latest.get("files_reopened", [])) if isinstance(latest.get("files_reopened"), list) else []
    opened = list(latest.get("files_opened", [])) if isinstance(latest.get("files_opened"), list) else []
    edited = list(latest.get("files_edited", [])) if isinstance(latest.get("files_edited"), list) else []
    tests = list(latest.get("tests_executed", [])) if isinstance(latest.get("tests_executed"), list) else []
    recommended_entry_points = _dedupe_for_cli(edited + opened + tests, limit=5)
    issue = "none"
    reason = "latest execution does not show repeated file loops or broad exploration"
    action = "continue"
    if len(reopened) > 2:
        issue = "looping_on_same_files"
        reason = f"{len(reopened)} files were reopened in the latest execution"
        action = "stop reopening the same files; use recommended_entry_points and prior strategy context"
    elif len(opened) > 8:
        issue = "too_much_exploration"
        reason = f"{len(opened)} files were opened in the latest execution"
        action = "narrow scope before reading more files; start from recommended_entry_points"
    payload = {
        "reopened_files": reopened,
        "possible_issue": issue,
        "opened_files_count": len(opened),
        "suggested_next_action": action,
        "recommended_entry_points": recommended_entry_points,
        "reason": reason,
    }
    print(__import__("json").dumps(payload, ensure_ascii=False))
    return 0


def cli_compact(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    payload = compact_repo_records(repo, apply=bool(getattr(args, "apply", False)))
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _dedupe_for_cli(values: list[Any], *, limit: int) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        cleaned.append(item)
        seen.add(item)
        if len(cleaned) >= limit:
            break
    return cleaned


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
    ensure_repo_user_preferences(repo)
    prefs = read_json(repo / REPO_MEMORY_DIR / "user_preferences.json", {})
    communication = prefs.get("communication", {}) if isinstance(prefs.get("communication"), dict) else {}
    layer = "enabled" if str(communication.get("layer", "")).strip() == "enabled" else "disabled"
    mode = str(communication.get("mode", "caveman_full") or "caveman_full").strip() or "caveman_full"
    state_path = repo / REPO_STATE_PATH
    state = read_json(state_path, {})
    state.update(
        {
            "version": 1,
            "engine_id": "aictx",
            "engine_name": "aictx",
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
                    "mechanism": "repo AGENTS.md + optional global ~/.codex model instructions via aictx install --install-codex-global",
                    "project_file": "AGENTS.md",
                    "optional_global_files": [
                        "~/.codex/AGENTS.override.md",
                        "~/.codex/AICTX_Codex.md",
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
                "telemetry_dir": ".aictx/metrics",
                "strategy_memory_dir": ".aictx/strategy_memory",
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


def _init_repomap_from_global(repo: Path, global_config: dict[str, Any]) -> tuple[list[str], str | None]:
    repomap = global_config.get("repomap", {}) if isinstance(global_config.get("repomap"), dict) else {}
    if not bool(repomap.get("requested", False)):
        return [], None

    created = ensure_repomap_scaffold(repo)
    repo_config = resolve_repo_repomap_config(global_config)
    write_repomap_config(repo, repo_config)
    config_path = str(repo_map_config_path(repo))
    if config_path not in created:
        created.append(config_path)

    provider_info = check_tree_sitter_available()
    if not provider_info.get("available", False):
        write_repomap_status(
            repo,
            {
                "enabled": bool(repo_config.get("enabled", False)),
                "available": False,
                "provider": str(repo_config.get("provider") or "tree_sitter"),
                "last_refresh_status": "unavailable",
                "warnings": [str(provider_info.get("error") or "provider_unavailable")],
            },
        )
        return created + [str(repo_map_status_path(repo))], "unavailable"

    refresh = refresh_repo_map(repo, mode="full")
    repomap_paths = [str(repo_map_status_path(repo))]
    if (repo_map_manifest_path(repo)).exists():
        repomap_paths.append(str(repo_map_manifest_path(repo)))
    if (repo_map_index_path(repo)).exists():
        repomap_paths.append(str(repo_map_index_path(repo)))
    return created + [path for path in repomap_paths if path not in created], str(refresh.get("status") or "ok")


def cmd_install(args: argparse.Namespace) -> int:
    workspace_id = args.workspace_id or "default"
    workspace_root = args.workspace_root
    cross_project_mode = args.cross_project_mode or "workspace"
    install_codex_global = bool(getattr(args, "install_codex_global", False))
    with_repomap = bool(getattr(args, "with_repomap", False))
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
        with_repomap = ask_yes_no("Enable RepoMap support using Tree-sitter?", False)

    if dry_run:
        planned = [
            ENGINE_HOME,
            CONFIG_PATH,
            PROJECTS_REGISTRY_PATH,
                    workspace_path(workspace_id),
        ]
        if install_codex_global:
            planned.extend([
                Path.home() / ".codex" / "AGENTS.override.md",
                Path.home() / ".codex" / "AICTX_Codex.md",
                Path.home() / ".codex" / "config.toml",
            ])
        print("Dry run. Would create/update:")
        for path in planned:
            print(f"- {path}")
        if workspace_root:
            print("Would register workspace root:")
            print(f"- {str(Path(workspace_root).expanduser().resolve())}")
        if with_repomap:
            print("Would request RepoMap support and check/install the optional Tree-sitter dependency if needed.")
        return 0

    ensure_global_home()
    config = read_json(CONFIG_PATH, default_global_config())
    repomap_requested = with_repomap
    repomap_available = False
    config.update(
        {
            "active_workspace": workspace_id,
            "cross_project_mode": cross_project_mode,
        }
    )
    if repomap_requested:
        repomap_available = repomap_dependency_available()
        if not repomap_available:
            should_install_repomap = False
            if args.yes and with_repomap:
                should_install_repomap = True
            elif not args.yes:
                should_install_repomap = ask_yes_no("RepoMap needs the optional Tree-sitter dependency. Install it now?", True)
            if should_install_repomap:
                install_result = install_repomap_dependency()
                repomap_available = install_result.returncode == 0 and repomap_dependency_available()
            if not repomap_available:
                print("RepoMap unavailable.")
        config = update_global_repomap_config(config, requested=True, available=repomap_available)
    else:
        config = update_global_repomap_config(config, requested=False, available=False)
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
    if repomap_requested:
        if repomap_available:
            print("RepoMap support: enabled (Tree-sitter available).")
        else:
            print("RepoMap support: requested but unavailable.")
    else:
        print("RepoMap support: disabled.")
    print("Install complete. Next: run `aictx init` inside a repository.")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    gitignore_path = repo / ".gitignore"
    original_gitignore_exists = gitignore_path.exists()
    original_gitignore_text = gitignore_path.read_text(encoding="utf-8") if original_gitignore_exists else ""
    update_gitignore = not args.no_gitignore
    if args.no_gitignore and getattr(args, "portable_continuity", False):
        print(
            "Error: --portable-continuity requires updating .gitignore. "
            "Remove --no-gitignore or use --no-portable-continuity.",
            file=sys.stderr,
        )
        return 2
    register_repo = not args.no_register
    selected_communication_mode = "disabled"
    portable_continuity = False

    if args.yes:
        portable_continuity = resolve_init_portable_continuity(args, repo)

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
        portable_continuity = resolve_init_portable_continuity(args, repo)
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
    global_config = read_json(CONFIG_PATH, default_global_config())
    created = init_repo_scaffold(repo, update_gitignore=update_gitignore, portable_continuity=portable_continuity)
    persist_repo_communication_mode(repo, selected_communication_mode)
    install_global_agent_runtime(write_json)
    local_runtime_path = copy_local_agent_runtime(repo)
    prepared = prepare_repo_runtime(repo)
    runner_integrations = install_repo_runner_integrations(repo)
    if not update_gitignore:
        if original_gitignore_exists:
            gitignore_path.write_text(original_gitignore_text, encoding="utf-8")
        elif gitignore_path.exists():
            gitignore_path.unlink()
            runner_integrations = [item for item in runner_integrations if item != gitignore_path]
    upsert_marked_block(repo / "AGENTS.md", render_repo_agents_block())
    legacy_override = repo / "AGENTS.override.md"
    remove_marked_block(legacy_override)
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
    repomap_created, repomap_result = _init_repomap_from_global(repo, global_config)
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
    for item in repomap_created:
        print(f"- {item}")
    if register_repo:
        print("Registered repo in workspace:")
        print(f"- {ws.workspace_id} -> {repo_str}")
    if repomap_result == "ok":
        print("RepoMap init: full map built.")
    elif repomap_result == "unavailable":
        print("RepoMap init: provider unavailable; status recorded.")
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
    suppressed_flags = {"--json", "--quiet", "-q", "-h", "--help", "-v", "--version"}
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
    parser.add_argument("-v", "--version", action="version", version=f"aictx {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="{install,init,resume,finalize,advanced,clean,uninstall}")

    install = sub.add_parser("install", help="Install global engine home")
    install.add_argument("--workspace-root", help="Initial workspace root")
    install.add_argument("--workspace-id", help="Workspace id", default="default")
    install.add_argument("--cross-project-mode", choices=["workspace", "explicit", "disabled"], help="Cross-project discovery mode")
    install.add_argument("--install-codex-global", action="store_true", help="Opt in to global Codex ~/.codex integration")
    install.add_argument("--with-repomap", action="store_true", help="Request optional RepoMap support using Tree-sitter")
    install.add_argument("--dry-run", action="store_true", help="Show planned install writes without mutating files")
    install.add_argument("--yes", action="store_true", help="Accept defaults without prompting")
    install.set_defaults(func=cmd_install)

    init = sub.add_parser("init", help="Initialize repo-local .aictx_* scaffold")
    init.add_argument("--repo", default=".", help="Repository path")
    init.add_argument("--yes", action="store_true", help="Accept defaults without prompting")
    init.add_argument("--no-gitignore", action="store_true", help="Do not modify .gitignore")
    portable_group = init.add_mutually_exclusive_group()
    portable_group.add_argument("--portable-continuity", action="store_true", help="Enable git-portable AICTX continuity artifacts")
    portable_group.add_argument("--no-portable-continuity", action="store_true", help="Keep all AICTX runtime artifacts local/ignored")
    init.add_argument("--no-register", action="store_true", help="Do not register repo in active workspace")
    init.set_defaults(func=cmd_init)

    resume = sub.add_parser("resume", help="Compile agent continuity capsule")
    resume.add_argument("--repo", default=".", help="Repository root")
    resume.add_argument("--task", default="", help="Task goal only. Preferred for agent startup.")
    resume.add_argument("--request", default="", help="Legacy/raw request input. Do not include reporting/output-format instructions.")
    resume.add_argument("--json", action="store_true", help="Print structured continuity capsule JSON")
    resume.add_argument("--full", action="store_true", help="Include a larger continuity capsule")
    resume.add_argument("--task-type", default="", help="Optional task type override")
    resume.add_argument("--agent-id", default="", help=argparse.SUPPRESS)
    resume.add_argument("--adapter-id", default="", help=argparse.SUPPRESS)
    resume.add_argument("--session-id", default="", help=argparse.SUPPRESS)
    resume.set_defaults(func=cmd_resume)

    finalize = sub.add_parser("finalize", help="Finalize an AICTX task execution and produce the final summary")
    finalize.add_argument("--repo", default=".", help="Repository root")
    finalize.add_argument("--status", choices=["success", "failure"], required=True, help="Task outcome")
    finalize.add_argument("--summary", required=True, help="What happened")
    finalize.add_argument("--json", action="store_true", help="Print structured finalization JSON")
    finalize.add_argument("--request", default="", help="Original user request")
    finalize.add_argument("--task-type", default="", help="Optional task type override")
    finalize.add_argument("--files-opened", nargs="*", default=[], help="Explicit files opened during execution")
    finalize.add_argument("--files-edited", nargs="*", default=[], help="Explicit files edited during execution")
    finalize.add_argument("--commands-executed", nargs="*", default=[], help="Explicit commands executed during execution")
    finalize.add_argument("--tests-executed", nargs="*", default=[], help="Explicit tests executed during execution")
    finalize.add_argument("--notable-errors", nargs="*", default=[], help="Explicit notable errors observed during execution")
    finalize.add_argument("--error", default="", help="Compact failure/error detail")
    finalize.add_argument("--agent-id", default="", help=argparse.SUPPRESS)
    finalize.add_argument("--adapter-id", default="", help=argparse.SUPPRESS)
    finalize.add_argument("--session-id", default="", help=argparse.SUPPRESS)
    finalize.set_defaults(func=cmd_finalize)

    advanced = sub.add_parser(
        "advanced",
        help="Show advanced/diagnostic AICTX commands",
        description=(
            "Advanced/diagnostic/building-block commands. Normal agents should use "
            'aictx resume --repo . --task "<task goal>" --json at startup '
            'and aictx finalize --repo . --status success|failure --summary "<what happened>" --json after task work.'
        ),
        epilog="Commands: suggest, reuse, next, task, messages, map, report, reflect, internal.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    advanced.set_defaults(func=cmd_advanced)

    suggest = sub.add_parser("suggest", help=argparse.SUPPRESS)
    suggest.add_argument("--repo", default=".", help="Repository root")
    suggest.add_argument("--task-type", default="", help="Optional task type filter")
    suggest.add_argument("--request", default="", help="Optional request text for contextual ranking")
    suggest.add_argument("--files-opened", nargs="*", default=[], help="Optional files already opened")
    suggest.add_argument("--commands-executed", nargs="*", default=[], help="Optional commands already executed")
    suggest.add_argument("--tests-executed", nargs="*", default=[], help="Optional tests already executed")
    suggest.add_argument("--notable-errors", nargs="*", default=[], help="Optional notable errors observed")
    suggest.set_defaults(func=cmd_suggest)

    reflect = sub.add_parser("reflect", help=argparse.SUPPRESS)
    reflect.add_argument("--repo", default=".", help="Repository root")
    reflect.set_defaults(func=cmd_reflect)

    reuse = sub.add_parser("reuse", help=argparse.SUPPRESS)
    reuse.add_argument("--repo", default=".", help="Repository root")
    reuse.add_argument("--task-type", default="", help="Optional task type filter")
    reuse.add_argument("--request", default="", help="Optional request text for contextual ranking")
    reuse.add_argument("--files-opened", nargs="*", default=[], help="Optional files already opened")
    reuse.add_argument("--commands-executed", nargs="*", default=[], help="Optional commands already executed")
    reuse.add_argument("--tests-executed", nargs="*", default=[], help="Optional tests already executed")
    reuse.add_argument("--notable-errors", nargs="*", default=[], help="Optional notable errors observed")
    reuse.set_defaults(func=cmd_reuse)

    task_cmd = sub.add_parser("task", help=argparse.SUPPRESS)
    task_sub = task_cmd.add_subparsers(dest="task_command", required=True)

    task_start = task_sub.add_parser("start", help="Start a repo-local active task")
    task_start.add_argument("goal", help="Active task goal")
    task_start.add_argument("--repo", default=".", help="Repository root")
    task_start.add_argument("--task-id", help="Optional stable task id")
    task_start.add_argument("--initial-json", default="", help="Optional initial state JSON object")
    task_start.add_argument("--json", action="store_true", help="Print task state as JSON")
    task_start.set_defaults(func=cmd_task_start)

    task_status = task_sub.add_parser("status", help="Show active repo-local task")
    task_status.add_argument("--repo", default=".", help="Repository root")
    task_status.add_argument("--all", action="store_true", help="List all task threads")
    task_status.add_argument("--json", action="store_true", help="Print task state as JSON")
    task_status.set_defaults(func=cmd_task_status)

    task_list = task_sub.add_parser("list", help="List repo-local task threads")
    task_list.add_argument("--repo", default=".", help="Repository root")
    task_list.add_argument("--json", action="store_true", help="Print task list as JSON")
    task_list.set_defaults(func=cmd_task_list)

    task_show = task_sub.add_parser("show", help="Show a repo-local task thread")
    task_show.add_argument("task_id", help="Task id")
    task_show.add_argument("--repo", default=".", help="Repository root")
    task_show.add_argument("--json", action="store_true", help="Print task state as JSON")
    task_show.set_defaults(func=cmd_task_show)

    task_update = task_sub.add_parser("update", help="Update active repo-local task")
    task_update.add_argument("--repo", default=".", help="Repository root")
    task_update.add_argument("--task-id", help="Optional task id override")
    task_update.add_argument("--json-patch", default="", help="Task patch JSON object")
    task_update.add_argument("--from-file", default="", help="Read task patch JSON object from file")
    task_update.add_argument("--json", action="store_true", help="Print task state as JSON")
    task_update.set_defaults(func=cmd_task_update)

    task_resume = task_sub.add_parser("resume", help="Resume a repo-local task thread")
    task_resume.add_argument("task_id", help="Task id")
    task_resume.add_argument("--repo", default=".", help="Repository root")
    task_resume.add_argument("--json", action="store_true", help="Print task state as JSON")
    task_resume.set_defaults(func=cmd_task_resume)

    task_close = task_sub.add_parser("close", help="Close active repo-local task")
    task_close.add_argument("--repo", default=".", help="Repository root")
    task_close.add_argument("--task-id", help="Optional task id override")
    task_close.add_argument("--status", default="resolved", choices=["resolved", "abandoned", "blocked", "paused"], help="Final task status")
    task_close.add_argument("--json-patch", default="", help="Optional final task patch JSON object")
    task_close.add_argument("--from-file", default="", help="Read optional final task patch JSON object from file")
    task_close.add_argument("--json", action="store_true", help="Print task state as JSON")
    task_close.set_defaults(func=cmd_task_close)

    next_cmd = sub.add_parser("next", help=argparse.SUPPRESS)
    next_cmd.add_argument("--repo", default=".", help="Repository root")
    next_cmd.add_argument("--request", default="", help="Optional request text for contextual continuity ranking")
    next_cmd.add_argument("--task-type", default="", help="Optional task type filter")
    next_cmd.add_argument("--files-opened", nargs="*", default=[], help="Optional files already opened")
    next_cmd.add_argument("--commands-executed", nargs="*", default=[], help="Optional commands already executed")
    next_cmd.add_argument("--tests-executed", nargs="*", default=[], help="Optional tests already executed")
    next_cmd.add_argument("--notable-errors", nargs="*", default=[], help="Optional notable errors observed")
    next_cmd.add_argument("--json", action="store_true", help="Print structured continuity brief JSON")
    next_cmd.set_defaults(func=cmd_next)

    messages = sub.add_parser("messages", help=argparse.SUPPRESS)
    messages_sub = messages.add_subparsers(dest="messages_command", required=True)

    messages_mute = messages_sub.add_parser("mute", help="Suppress automatic startup banner and execution summary")
    messages_mute.add_argument("--repo", default=".", help="Repository root")
    messages_mute.add_argument("--json", action="store_true", help="Print status as JSON")
    messages_mute.set_defaults(func=cmd_messages_mute)

    messages_unmute = messages_sub.add_parser("unmute", help="Allow automatic startup banner and execution summary")
    messages_unmute.add_argument("--repo", default=".", help="Repository root")
    messages_unmute.add_argument("--json", action="store_true", help="Print status as JSON")
    messages_unmute.set_defaults(func=cmd_messages_unmute)

    messages_status = messages_sub.add_parser("status", help="Show automatic AICTX runtime message visibility")
    messages_status.add_argument("--repo", default=".", help="Repository root")
    messages_status.add_argument("--json", action="store_true", help="Print status as JSON")
    messages_status.set_defaults(func=cmd_messages_status)

    map_cmd = sub.add_parser("map", help=argparse.SUPPRESS)
    map_sub = map_cmd.add_subparsers(dest="map_command", required=True)

    map_status = map_sub.add_parser("status", help="Show RepoMap status")
    map_status.add_argument("--repo", default=".", help="Repository root")
    map_status.add_argument("--json", action="store_true", help="Print status as JSON")
    map_status.set_defaults(func=cmd_map_status)

    map_refresh = map_sub.add_parser("refresh", help="Refresh RepoMap index")
    map_refresh.add_argument("--repo", default=".", help="Repository root")
    map_refresh.add_argument("--full", action="store_true", help="Force full refresh")
    map_refresh.add_argument("--json", action="store_true", help="Print refresh result as JSON")
    map_refresh.set_defaults(func=cmd_map_refresh)

    map_query = map_sub.add_parser("query", help="Search RepoMap index")
    map_query.add_argument("--repo", default=".", help="Repository root")
    map_query.add_argument("--json", action="store_true", help="Print query results as JSON")
    map_query.add_argument("--limit", type=int, default=10, help="Maximum number of matches")
    map_query.add_argument("text", help="Query text")
    map_query.set_defaults(func=cmd_map_query)

    clean = sub.add_parser("clean", help="Remove AICTX content from the current repository")
    clean.add_argument("--repo", default=".", help="Repository root")
    clean.set_defaults(func=cmd_clean)

    uninstall = sub.add_parser("uninstall", help="Remove AICTX content from all registered repos and global config")
    uninstall.set_defaults(func=cmd_uninstall)

    report = sub.add_parser("report", help=argparse.SUPPRESS)
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
    compact.add_argument("--repo", default=".", help="Repository root.")
    compact.add_argument("--apply", action="store_true", help="Apply the compaction plan. Without this flag, compact runs as dry-run.")
    compact.set_defaults(func=cli_compact)

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
    prepare.add_argument("--files-edited", nargs="*", default=[], help="Explicit files edited during execution")
    prepare.add_argument("--files-reopened", nargs="*", default=[], help="Explicit files reopened during execution")
    prepare.add_argument("--commands-executed", nargs="*", default=[], help="Explicit commands executed during execution")
    prepare.add_argument("--tests-executed", nargs="*", default=[], help="Explicit tests executed during execution")
    prepare.add_argument("--notable-errors", nargs="*", default=[], help="Explicit notable errors observed during execution")
    prepare.add_argument("--error-event-json", action="append", default=[], help="JSON error_event object observed during execution")
    prepare.add_argument("--work-state-json", default="", help="Optional work state JSON object")
    prepare.add_argument("--work-state-file", default="", help="Optional work state JSON file")
    prepare.set_defaults(func=cli_prepare_execution)

    finalize = execution_sub.add_parser("finalize", help=argparse.SUPPRESS)
    finalize.add_argument("--prepared", required=True, help="Path to prepared execution JSON.")
    finalize.add_argument("--success", action="store_true", help="Mark execution as successful.")
    finalize.add_argument("--result-summary", default="", help="Execution result summary.")
    finalize.add_argument("--validated-learning", action="store_true", help="Persist validated learning when successful.")
    finalize.add_argument("--files-opened", nargs="*", default=[], help="Explicit files opened during execution")
    finalize.add_argument("--files-edited", nargs="*", default=[], help="Explicit files edited during execution")
    finalize.add_argument("--files-reopened", nargs="*", default=[], help="Explicit files reopened during execution")
    finalize.add_argument("--commands-executed", nargs="*", default=[], help="Explicit commands executed during execution")
    finalize.add_argument("--tests-executed", nargs="*", default=[], help="Explicit tests executed during execution")
    finalize.add_argument("--notable-errors", nargs="*", default=[], help="Explicit notable errors observed during execution")
    finalize.add_argument("--error-event-json", action="append", default=[], help="JSON error_event object observed during execution")
    finalize.add_argument("--decision-json", action="append", default=[], help="JSON object for a significant continuity decision")
    finalize.add_argument("--semantic-json", action="append", default=[], help="JSON object for a semantic repo subsystem update")
    finalize.add_argument("--work-state-json", default="", help="Optional work state JSON object")
    finalize.add_argument("--work-state-file", default="", help="Optional work state JSON file")
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
    run_execution.add_argument("--files-edited", nargs="*", default=[], help="Explicit files edited during execution")
    run_execution.add_argument("--files-reopened", nargs="*", default=[], help="Explicit files reopened during execution")
    run_execution.add_argument("--commands-executed", nargs="*", default=[], help="Explicit commands executed during execution")
    run_execution.add_argument("--tests-executed", nargs="*", default=[], help="Explicit tests executed during execution")
    run_execution.add_argument("--notable-errors", nargs="*", default=[], help="Explicit notable errors observed during execution")
    run_execution.add_argument("--error-event-json", action="append", default=[], help="JSON error_event object observed during execution")
    run_execution.add_argument("--work-state-json", default="", help="Optional work state JSON object")
    run_execution.add_argument("--work-state-file", default="", help="Optional work state JSON file")
    run_execution.add_argument("command", nargs=argparse.REMAINDER, help="Wrapped command after --.")
    run_execution.set_defaults(func=cli_run_execution)

    return parser


def main() -> int:
    if should_render_banner(sys.argv[1:], sys.stdout.isatty()):
        print(ASCII_BANNER)
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
