from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .. import state as state_module
from ..state import read_json, write_json

MCP_PROFILES = {"readonly", "standard", "full"}
DEFAULT_MCP_PROFILE = "full"
MCP_SERVER_NAME = "aictx"
MCP_MANAGED = "aictx-managed"
MCP_MANAGED_BLOCK = "<AICTX>"


def global_mcp_status_path() -> Path:
    return state_module.ENGINE_HOME / "mcp" / "status.json"

def global_config_path() -> Path:
    return state_module.CONFIG_PATH


REPO_MCP_PATH = Path(".mcp.json")
VSCODE_MCP_PATH = Path(".vscode") / "mcp.json"


def server_container_key_for_path(path: Path) -> str:
    candidate = Path(path)
    return "servers" if candidate.name == VSCODE_MCP_PATH.name and candidate.parent.name == VSCODE_MCP_PATH.parent.name else "mcpServers"


def _other_server_container_key(key: str) -> str:
    return "servers" if key == "mcpServers" else "mcpServers"


def normalize_mcp_profile(profile: str | None) -> str:
    value = str(profile or DEFAULT_MCP_PROFILE).strip().lower()
    if value not in MCP_PROFILES:
        raise ValueError(f"Unknown MCP profile: {profile}")
    return value


def _is_aictx_source_checkout(repo: Path) -> bool:
    pyproject = repo / "pyproject.toml"
    package_init = repo / "src" / "aictx" / "__init__.py"
    if not package_init.exists() or not pyproject.exists():
        return False
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError:
        return False
    return 'name = "aictx"' in text or "name = 'aictx'" in text


def _repo_python(repo: Path) -> str:
    candidates = [
        repo / ".venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate.relative_to(repo))
    return "python3"


def mcp_server_command(profile: str = DEFAULT_MCP_PROFILE, *, repo: Path | None = None) -> list[str]:
    profile = normalize_mcp_profile(profile)
    if repo is not None:
        root = repo.expanduser().resolve()
        if _is_aictx_source_checkout(root):
            return [_repo_python(root), "-m", "aictx", "mcp-server", "--repo", ".", "--profile", profile]
    return ["aictx", "mcp-server", "--repo", ".", "--profile", profile]


def mcp_server_entry(profile: str = DEFAULT_MCP_PROFILE, *, repo: Path | None = None) -> dict[str, Any]:
    root = repo.expanduser().resolve() if repo is not None else None
    command = mcp_server_command(profile, repo=root)
    entry: dict[str, Any] = {
        "command": command[0],
        "args": command[1:],
        "transport": "stdio",
        "type": "stdio",
        "_aictx_managed": True,
        "_aictx_block": MCP_MANAGED_BLOCK,
    }
    if root is not None and _is_aictx_source_checkout(root):
        entry["cwd"] = "."
        entry["env"] = {"PYTHONPATH": "src"}
    return entry


def _upsert_json_server(path: Path, profile: str, *, repo: Path | None = None, dry_run: bool = False) -> tuple[bool, str]:
    existing: dict[str, Any] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing = loaded
        except json.JSONDecodeError:
            return False, "invalid_json_skipped"
    updated = dict(existing)
    container_key = server_container_key_for_path(path)
    alternate_key = _other_server_container_key(container_key)
    servers = updated.get(container_key)
    if not isinstance(servers, dict):
        servers = {}
    before = json.dumps(updated, sort_keys=True, ensure_ascii=False)
    current = servers.get(MCP_SERVER_NAME)
    if isinstance(current, dict) and current and not bool(current.get("_aictx_managed", False)):
        return False, "user_server_preserved"
    alternate_servers = updated.get(alternate_key)
    if isinstance(alternate_servers, dict):
        alternate_current = alternate_servers.get(MCP_SERVER_NAME)
        if isinstance(alternate_current, dict) and bool(alternate_current.get("_aictx_managed", False)):
            alternate_servers = dict(alternate_servers)
            alternate_servers.pop(MCP_SERVER_NAME, None)
            if alternate_servers:
                updated[alternate_key] = alternate_servers
            else:
                updated.pop(alternate_key, None)
    servers = dict(servers)
    servers[MCP_SERVER_NAME] = mcp_server_entry(profile, repo=repo)
    updated[container_key] = servers
    updated["_aictx"] = {"managed": True, "kind": MCP_MANAGED, "block": MCP_MANAGED_BLOCK}
    after = json.dumps(updated, sort_keys=True, ensure_ascii=False)
    changed = before != after
    if changed and not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(updated, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return changed, "updated" if changed else "unchanged"


def install_repo_mcp_config(repo: Path, *, profile: str = DEFAULT_MCP_PROFILE, dry_run: bool = False) -> dict[str, Any]:
    repo = repo.expanduser().resolve()
    profile = normalize_mcp_profile(profile)
    warnings: list[str] = []
    files: list[str] = []
    changed = False
    for rel in (REPO_MCP_PATH, VSCODE_MCP_PATH):
        path = repo / rel
        file_changed, status = _upsert_json_server(path, profile, repo=repo, dry_run=dry_run)
        if status.endswith("skipped") or status == "user_server_preserved":
            warnings.append(f"{rel.as_posix()}: {status}")
        if file_changed or status in {"updated", "unchanged"}:
            files.append(str(path))
        changed = changed or file_changed
    return {
        "ok": True,
        "enabled": True,
        "profile": profile,
        "transport": "stdio",
        "changed": changed,
        "dry_run": dry_run,
        "files": sorted(dict.fromkeys(files)),
        "warnings": warnings,
    }


def install_global_mcp_config(*, profile: str = DEFAULT_MCP_PROFILE, dry_run: bool = False) -> dict[str, Any]:
    profile = normalize_mcp_profile(profile)
    config_path = global_config_path()
    status_path = global_mcp_status_path()
    planned = [str(config_path), str(status_path)]
    if dry_run:
        return {"ok": True, "enabled": True, "profile": profile, "transport": "stdio", "changed": False, "dry_run": True, "files": planned, "warnings": []}
    state_module.ENGINE_HOME.mkdir(parents=True, exist_ok=True)
    config = read_json(config_path, {})
    if not isinstance(config, dict):
        config = {}
    before = json.dumps(config, sort_keys=True, ensure_ascii=False)
    config["mcp"] = {"enabled": True, "profile": profile, "transport": "stdio", "server_command": mcp_server_command(profile)}
    write_json(config_path, config)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status = {"enabled": True, "profile": profile, "transport": "stdio", "managed": True}
    status_path.write_text(json.dumps(status, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, "enabled": True, "profile": profile, "transport": "stdio", "changed": before != json.dumps(config, sort_keys=True, ensure_ascii=False), "dry_run": False, "files": planned, "warnings": []}


def _path_has_aictx_server(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    for key in ("mcpServers", "servers"):
        servers = payload.get(key)
        if isinstance(servers, dict) and MCP_SERVER_NAME in servers:
            return True
    return False


def mcp_status(repo: Path | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": True, "global": {"enabled": False}, "repo": {"enabled": False}}
    config_path = global_config_path()
    config = read_json(config_path, {}) if config_path.exists() else {}
    if isinstance(config, dict) and isinstance(config.get("mcp"), dict):
        payload["global"] = dict(config["mcp"])
    if repo is not None:
        root = repo.expanduser().resolve()
        files = []
        for rel in (REPO_MCP_PATH, VSCODE_MCP_PATH):
            path = root / rel
            if _path_has_aictx_server(path):
                files.append(str(path))
        payload["repo"] = {"enabled": bool(files), "files": files}
    return payload


def _remove_json_server(path: Path) -> tuple[bool, bool]:
    if not path.exists():
        return False, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False, False
    if not isinstance(payload, dict):
        return False, False
    changed = False
    for key in ("mcpServers", "servers"):
        servers = payload.get(key)
        if not isinstance(servers, dict):
            continue
        servers = dict(servers)
        current = servers.get(MCP_SERVER_NAME)
        if isinstance(current, dict) and bool(current.get("_aictx_managed", False)):
            servers.pop(MCP_SERVER_NAME, None)
            changed = True
        if servers:
            payload[key] = servers
        else:
            payload.pop(key, None)
    if isinstance(payload.get("_aictx"), dict) and payload.get("_aictx", {}).get("kind") == MCP_MANAGED:
        payload.pop("_aictx", None)
        changed = True
    if not changed:
        return False, False
    if not payload:
        path.unlink()
        return True, True
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return True, False


def remove_repo_mcp_config(repo: Path) -> dict[str, list[str]]:
    removed: list[str] = []
    updated: list[str] = []
    for rel in (REPO_MCP_PATH, VSCODE_MCP_PATH):
        path = repo / rel
        changed, deleted = _remove_json_server(path)
        if changed:
            if deleted:
                removed.append(str(path))
                parent = path.parent
                while parent != repo and parent.exists():
                    try:
                        parent.rmdir()
                    except OSError:
                        break
                    parent = parent.parent
            else:
                updated.append(str(path))
    return {"removed": removed, "updated": updated}


def remove_global_mcp_config() -> dict[str, list[str]]:
    removed: list[str] = []
    updated: list[str] = []
    config_path = global_config_path()
    config = read_json(config_path, {}) if config_path.exists() else {}
    if isinstance(config, dict) and "mcp" in config:
        config.pop("mcp", None)
        write_json(config_path, config)
        updated.append(str(config_path))
    status_path = global_mcp_status_path()
    if status_path.exists():
        status_path.unlink()
        removed.append(str(status_path))
    return {"removed": removed, "updated": updated}
