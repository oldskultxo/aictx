from __future__ import annotations

import stat
from pathlib import Path
from typing import Any

from .state import ENGINE_HOME, REPO_ADAPTERS_DIR, write_json, read_json

GLOBAL_ADAPTERS_DIR = ENGINE_HOME / "adapters"
GLOBAL_ADAPTERS_REGISTRY_PATH = GLOBAL_ADAPTERS_DIR / "registry.json"
GLOBAL_ADAPTERS_BIN_DIR = GLOBAL_ADAPTERS_DIR / "bin"
GLOBAL_ADAPTERS_INSTALL_STATUS_PATH = GLOBAL_ADAPTERS_DIR / "install_status.json"


def adapter_runtime_contract(adapter_id: str) -> dict[str, Any]:
    return {
        "runtime_entrypoint": "aictx internal run-execution",
        "integration_mode": "wrapper",
        "auto_prepare_finalize": True,
        "requires_request_context": True,
        "wrapper_env": [
            "AICTX_REQUEST",
            "AICTX_REPO",
            "AICTX_EXECUTION_ID",
            "AICTX_AGENT_ID",
            "AICTX_TASK_TYPE",
            "AICTX_EXECUTION_MODE",
            "AICTX_VALIDATED_LEARNING",
        ],
        "wrapper_script_name": f"aictx-{adapter_id}-auto",
    }


def adapter_profiles() -> dict[str, dict[str, Any]]:
    return {
        "generic": {
            "adapter_id": "generic",
            "display_name": "Generic multi-LLM runner",
            "family": "multi_llm",
            "middleware_always_on": True,
            "explicit_skill_metadata": False,
            "structured_skill_metadata": True,
            "heuristic_skill_fallback": True,
            "auto_installed": True,
            "runtime_contract": adapter_runtime_contract("generic"),
        },
        "codex": {
            "adapter_id": "codex",
            "display_name": "OpenAI Codex",
            "family": "openai_codex",
            "middleware_always_on": True,
            "explicit_skill_metadata": True,
            "structured_skill_metadata": True,
            "heuristic_skill_fallback": True,
            "expected_skill_metadata_fields": ["skill_id", "skill_name", "skill_path", "source"],
            "auto_installed": True,
            "runtime_contract": adapter_runtime_contract("codex"),
        },
        "claude": {
            "adapter_id": "claude",
            "display_name": "Anthropic Claude",
            "family": "anthropic_claude",
            "middleware_always_on": True,
            "explicit_skill_metadata": True,
            "structured_skill_metadata": True,
            "heuristic_skill_fallback": True,
            "expected_skill_metadata_fields": ["skill_id", "skill_name", "skill_path", "source"],
            "auto_installed": True,
            "runtime_contract": adapter_runtime_contract("claude"),
        },
    }


def adapter_registry_payload(scope: str) -> dict[str, Any]:
    profiles = adapter_profiles()
    return {
        "version": 1,
        "scope": scope,
        "default_adapter_id": "generic",
        "supported_adapters": sorted(profiles.keys()),
        "middleware_mode": "always_on",
        "skill_detection_contract": {
            "authoritative_signal": "explicit_runner_metadata",
            "structured_fallback": True,
            "heuristic_fallback": True,
        },
        "runtime_contract": {
            "entrypoint": "aictx internal run-execution",
            "integration_mode": "wrapper",
            "supported_runners": sorted(profiles.keys()),
        },
    }


def write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def render_wrapper_script(adapter_id: str) -> str:
    return f"""#!/bin/sh
set -eu
REQUEST="${{AICTX_REQUEST:-}}"
if [ -z "$REQUEST" ]; then
  echo "AICTX_REQUEST must be set for {adapter_id} auto wrapper." >&2
  exit 64
fi
REPO="${{AICTX_REPO:-.}}"
EXEC_ID="${{AICTX_EXECUTION_ID:-auto}}"
AGENT_ID="${{AICTX_AGENT_ID:-{adapter_id}}}"
TASK_TYPE="${{AICTX_TASK_TYPE:-}}"
EXEC_MODE="${{AICTX_EXECUTION_MODE:-plain}}"
VALIDATED="${{AICTX_VALIDATED_LEARNING:-0}}"
if [ "$VALIDATED" = "1" ] || [ "$VALIDATED" = "true" ]; then
  VALIDATED_FLAG="--validated-learning"
else
  VALIDATED_FLAG=""
fi
if [ -n "$TASK_TYPE" ]; then
  exec aictx internal run-execution --repo "$REPO" --request "$REQUEST" --agent-id "$AGENT_ID" --adapter-id "{adapter_id}" --execution-id "$EXEC_ID" --execution-mode "$EXEC_MODE" $VALIDATED_FLAG --task-type "$TASK_TYPE" -- "$@"
fi
exec aictx internal run-execution --repo "$REPO" --request "$REQUEST" --agent-id "$AGENT_ID" --adapter-id "{adapter_id}" --execution-id "$EXEC_ID" --execution-mode "$EXEC_MODE" $VALIDATED_FLAG -- "$@"
"""


def install_adapter_wrappers() -> list[Path]:
    created: list[Path] = []
    GLOBAL_ADAPTERS_BIN_DIR.mkdir(parents=True, exist_ok=True)
    for adapter_id in sorted(adapter_profiles().keys()):
        wrapper_name = adapter_runtime_contract(adapter_id)["wrapper_script_name"]
        path = GLOBAL_ADAPTERS_BIN_DIR / wrapper_name
        write_executable(path, render_wrapper_script(adapter_id))
        created.append(path)
    return created


def adapter_install_status_payload(wrapper_paths: list[Path]) -> dict[str, Any]:
    profiles = adapter_profiles()
    wrappers = {
        adapter_id: str(GLOBAL_ADAPTERS_BIN_DIR / profiles[adapter_id]["runtime_contract"]["wrapper_script_name"])
        for adapter_id in sorted(profiles.keys())
    }
    return {
        "version": 1,
        "engine_home": str(ENGINE_HOME),
        "integration_mode": "wrapper",
        "runtime_entrypoint": "aictx internal run-execution",
        "supported_runners": sorted(profiles.keys()),
        "wrappers": wrappers,
        "artifacts": [str(path) for path in wrapper_paths],
        "status": "wrapper_ready",
    }


def install_global_adapters() -> list[Path]:
    GLOBAL_ADAPTERS_DIR.mkdir(parents=True, exist_ok=True)
    write_json(GLOBAL_ADAPTERS_REGISTRY_PATH, adapter_registry_payload("global"))
    created = [GLOBAL_ADAPTERS_REGISTRY_PATH]
    for adapter_id, payload in adapter_profiles().items():
        path = GLOBAL_ADAPTERS_DIR / f"{adapter_id}.json"
        write_json(path, payload)
        created.append(path)
    wrapper_paths = install_adapter_wrappers()
    created.extend(wrapper_paths)
    write_json(GLOBAL_ADAPTERS_INSTALL_STATUS_PATH, adapter_install_status_payload(wrapper_paths))
    created.append(GLOBAL_ADAPTERS_INSTALL_STATUS_PATH)
    return created


def install_repo_adapters(repo: Path) -> list[Path]:
    adapters_dir = repo / REPO_ADAPTERS_DIR
    adapters_dir.mkdir(parents=True, exist_ok=True)
    registry_path = adapters_dir / "registry.json"
    write_json(registry_path, adapter_registry_payload("repo"))
    created = [registry_path]
    for adapter_id, payload in adapter_profiles().items():
        path = adapters_dir / f"{adapter_id}.json"
        write_json(path, payload)
        created.append(path)
    return created


def resolve_adapter_profile(adapter_id: str | None, agent_id: str | None = None, repo_root: Path | None = None) -> dict[str, Any]:
    requested = str(adapter_id or "").strip().lower()
    agent = str(agent_id or "").strip().lower()
    profiles = adapter_profiles()
    resolved_id = requested if requested in profiles else "generic"
    if resolved_id == "generic":
        if "codex" in requested or "codex" in agent:
            resolved_id = "codex"
        elif "claude" in requested or "claude" in agent:
            resolved_id = "claude"
    if repo_root:
        repo_path = repo_root / REPO_ADAPTERS_DIR / f"{resolved_id}.json"
        if repo_path.exists():
            payload = read_json(repo_path, {})
            if payload:
                return payload
    return dict(profiles[resolved_id])
