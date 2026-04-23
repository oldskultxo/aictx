from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .agent_runtime import AGENTS_END, AGENTS_START
from .runner_integrations import AICTX_END, AICTX_START, CODEX_CONFIG_PATH, CODEX_HOME
from .state import ENGINE_HOME, PROJECTS_REGISTRY_PATH, WORKSPACES_DIR, read_json, write_json

REPO_HOOK_FILES = [
    Path('.claude/hooks/aictx_session_start.py'),
    Path('.claude/hooks/aictx_user_prompt_submit.py'),
    Path('.claude/hooks/aictx_pre_tool_use.py'),
]
REPO_OPTIONAL_FILES = [
    Path('AGENTS.override.md'),
    Path('CLAUDE.md'),
    Path('AGENTS.md'),
]
AICTX_GITIGNORE_LINES = {
    '.aictx/',
    '.aictx/',
}
CODEX_MANAGED_COMMENT = '# AICTX managed fallback docs for stronger repo instruction loading'
CODEX_MANAGED_LINE = 'project_doc_fallback_filenames = ["CLAUDE.md"]'


def _safe_unlink(path: Path, removed: list[str]) -> None:
    if path.exists() or path.is_symlink():
        path.unlink()
        removed.append(str(path))


def _safe_rmtree(path: Path, removed: list[str]) -> None:
    if path.exists():
        shutil.rmtree(path)
        removed.append(str(path))


def _cleanup_empty_parents(path: Path, stop_at: Path | None = None) -> None:
    current = path.parent
    limit = stop_at.resolve() if stop_at else None
    while current.exists():
        if limit and current.resolve() == limit:
            break
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def remove_marked_block(path: Path, start_marker: str = AICTX_START, end_marker: str = AICTX_END) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding='utf-8')
    if start_marker not in text or end_marker not in text:
        return False
    start = text.index(start_marker)
    end = text.index(end_marker, start) + len(end_marker)
    head = text[:start].rstrip()
    tail = text[end:].lstrip()
    pieces = []
    if head:
        pieces.append(head)
    if tail:
        pieces.append(tail)
    updated = ('\n\n'.join(pieces)).rstrip()
    if updated:
        path.write_text(updated + '\n', encoding='utf-8')
    else:
        path.unlink()
    return True


def remove_gitignore_aictx_entries(path: Path) -> bool:
    if not path.exists():
        return False
    lines = path.read_text(encoding='utf-8').splitlines()
    filtered = [line for line in lines if line.strip() not in AICTX_GITIGNORE_LINES]
    if filtered == lines:
        return False
    if filtered:
        path.write_text('\n'.join(filtered).rstrip() + '\n', encoding='utf-8')
    else:
        path.unlink()
    return True


def remove_claude_settings_aictx_entries(path: Path) -> bool:
    if not path.exists():
        return False
    payload = read_json(path, {})
    if not isinstance(payload, dict):
        return False
    hooks = payload.get('hooks')
    if not isinstance(hooks, dict):
        return False

    changed = False
    cleaned_hooks: dict[str, Any] = {}
    for event_name, entries in hooks.items():
        if not isinstance(entries, list):
            cleaned_hooks[event_name] = entries
            continue
        kept_entries = []
        for entry in entries:
            if not isinstance(entry, dict):
                kept_entries.append(entry)
                continue
            entry_hooks = entry.get('hooks')
            if not isinstance(entry_hooks, list):
                kept_entries.append(entry)
                continue
            filtered_commands = []
            removed_any = False
            for hook in entry_hooks:
                if not isinstance(hook, dict):
                    filtered_commands.append(hook)
                    continue
                command = str(hook.get('command') or '')
                if 'aictx_session_start.py' in command or 'aictx_user_prompt_submit.py' in command or 'aictx_pre_tool_use.py' in command:
                    changed = True
                    removed_any = True
                    continue
                filtered_commands.append(hook)
            if filtered_commands:
                updated_entry = dict(entry)
                updated_entry['hooks'] = filtered_commands
                kept_entries.append(updated_entry)
            elif not removed_any:
                kept_entries.append(entry)
            else:
                changed = True
        if kept_entries:
            cleaned_hooks[event_name] = kept_entries
        elif event_name in hooks:
            changed = True
    if not changed:
        return False
    if cleaned_hooks:
        payload['hooks'] = cleaned_hooks
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    else:
        path.unlink()
    return True


def remove_codex_config_aictx_entries(path: Path = CODEX_CONFIG_PATH) -> bool:
    if not path.exists():
        return False
    lines = path.read_text(encoding='utf-8').splitlines()
    filtered = [line for line in lines if line.strip() not in {CODEX_MANAGED_COMMENT, CODEX_MANAGED_LINE}]
    if filtered == lines:
        return False
    while filtered and not filtered[-1].strip():
        filtered.pop()
    if filtered:
        path.write_text('\n'.join(filtered) + '\n', encoding='utf-8')
    else:
        path.unlink()
    return True


def clean_repo(repo: Path) -> dict[str, Any]:
    repo = repo.expanduser().resolve()
    removed: list[str] = []
    updated: list[str] = []

    engine_dir = repo / '.aictx'
    if engine_dir.exists():
        _safe_rmtree(engine_dir, removed)

    for rel_path in REPO_HOOK_FILES:
        hook_path = repo / rel_path
        if hook_path.exists():
            _safe_unlink(hook_path, removed)
            _cleanup_empty_parents(hook_path, stop_at=repo)

    settings_path = repo / '.claude/settings.json'
    if remove_claude_settings_aictx_entries(settings_path):
        if settings_path.exists():
            updated.append(str(settings_path))
        else:
            removed.append(str(settings_path))
        _cleanup_empty_parents(settings_path, stop_at=repo)

    for rel_path in REPO_OPTIONAL_FILES:
        file_path = repo / rel_path
        if remove_marked_block(file_path, AGENTS_START, AGENTS_END):
            if file_path.exists():
                updated.append(str(file_path))
            else:
                removed.append(str(file_path))

    gitignore_path = repo / '.gitignore'
    if remove_gitignore_aictx_entries(gitignore_path):
        if gitignore_path.exists():
            updated.append(str(gitignore_path))
        else:
            removed.append(str(gitignore_path))

    return {
        'repo': str(repo),
        'removed': sorted(dict.fromkeys(removed)),
        'updated': sorted(dict.fromkeys(updated)),
    }


def _remove_repo_from_registry(repo: Path) -> None:
    registry = read_json(PROJECTS_REGISTRY_PATH, {'version': 1, 'projects': []})
    if isinstance(registry, dict) and isinstance(registry.get('projects'), list):
        repo_str = str(repo)
        registry['projects'] = [row for row in registry['projects'] if str(row.get('repo_path') or '') != repo_str]
        write_json(PROJECTS_REGISTRY_PATH, registry)


def _workspace_files() -> list[Path]:
    if not WORKSPACES_DIR.exists():
        return []
    return sorted(path for path in WORKSPACES_DIR.glob('*.json') if path.is_file())


def _clean_workspace_file(path: Path, target_repo: Path | None = None) -> list[str]:
    payload = read_json(path, None)
    if not isinstance(payload, dict):
        return []
    removed_roots: list[str] = []
    changed = False
    repo_str = str(target_repo) if target_repo else None
    if repo_str and isinstance(payload.get('repos'), list):
        repos = [item for item in payload['repos'] if str(item) != repo_str]
        if repos != payload['repos']:
            payload['repos'] = repos
            changed = True
    if isinstance(payload.get('roots'), list):
        for root in payload['roots']:
            root_path = Path(str(root)).expanduser().resolve()
            agents_path = root_path / 'AGENTS.md'
            if remove_marked_block(agents_path, AGENTS_START, AGENTS_END):
                removed_roots.append(str(agents_path))
    if changed:
        write_json(path, payload)
    return removed_roots


def clean_repo_and_unregister(repo: Path) -> dict[str, Any]:
    result = clean_repo(repo)
    if ENGINE_HOME.exists():
        _remove_repo_from_registry(repo.expanduser().resolve())
        workspace_updates = []
        for workspace_file in _workspace_files():
            workspace_updates.extend(_clean_workspace_file(workspace_file, target_repo=repo.expanduser().resolve()))
        result['updated'] = sorted(dict.fromkeys(result['updated'] + workspace_updates))
    return result


def uninstall_all() -> dict[str, Any]:
    removed: list[str] = []
    updated: list[str] = []
    repos: list[str] = []

    registry = read_json(PROJECTS_REGISTRY_PATH, {'version': 1, 'projects': []}) if PROJECTS_REGISTRY_PATH.exists() else {'projects': []}
    if isinstance(registry, dict):
        for row in registry.get('projects', []):
            repo_path = Path(str(row.get('repo_path') or '')).expanduser()
            if repo_path and str(repo_path):
                repos.append(str(repo_path.resolve()))

    for workspace_file in _workspace_files():
        payload = read_json(workspace_file, {})
        if isinstance(payload, dict):
            for repo_item in payload.get('repos', []):
                repo_path = Path(str(repo_item)).expanduser()
                if str(repo_path):
                    repos.append(str(repo_path.resolve()))

    for repo_str in sorted(dict.fromkeys(repos)):
        repo_path = Path(repo_str)
        if repo_path.exists():
            result = clean_repo(repo_path)
            removed.extend(result['removed'])
            updated.extend(result['updated'])

    for workspace_file in _workspace_files():
        updated.extend(_clean_workspace_file(workspace_file, target_repo=None))

    for file_path in [CODEX_HOME / 'AGENTS.override.md']:
        if remove_marked_block(file_path, AICTX_START, AICTX_END):
            if file_path.exists():
                updated.append(str(file_path))
            else:
                removed.append(str(file_path))

    if remove_codex_config_aictx_entries(CODEX_CONFIG_PATH):
        if CODEX_CONFIG_PATH.exists():
            updated.append(str(CODEX_CONFIG_PATH))
        else:
            removed.append(str(CODEX_CONFIG_PATH))

    if ENGINE_HOME.exists():
        _safe_rmtree(ENGINE_HOME, removed)

    return {
        'repos_cleaned': sorted(dict.fromkeys(repos)),
        'removed': sorted(dict.fromkeys(removed)),
        'updated': sorted(dict.fromkeys(updated)),
    }
