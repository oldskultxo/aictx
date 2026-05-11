from __future__ import annotations

from typing import Any

from ._version import __version__

CURRENT_ENGINE_CAPABILITY_VERSION = 17


def current_installed_version() -> str:
    return __version__


def current_engine_capability_version() -> int:
    return CURRENT_ENGINE_CAPABILITY_VERSION


def normalize_installed_version(value: Any, *, fallback: str = "unknown") -> str:
    text = str(value or "").strip()
    return text or fallback


def normalize_engine_capability_version(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 1 else None


def resolve_version_payload(
    payload: dict[str, Any] | None,
    *,
    fallback_installed_version: str = "unknown",
    fallback_capability_version: int | None = None,
) -> dict[str, Any]:
    source = payload or {}
    installed_version = normalize_installed_version(source.get("installed_version"), fallback=fallback_installed_version)
    capability_version = normalize_engine_capability_version(source.get("engine_capability_version"))
    if capability_version is None:
        capability_version = fallback_capability_version
    return {
        "installed_version": installed_version,
        "engine_capability_version": capability_version,
    }


def compat_version_payload(
    *,
    installed_version: str | None = None,
    capability_version: int | None = None,
    include_deprecated_iteration: bool = False,
) -> dict[str, Any]:
    resolved_version = normalize_installed_version(installed_version, fallback=current_installed_version())
    resolved_capability = capability_version or current_engine_capability_version()
    payload: dict[str, Any] = {
        "installed_version": resolved_version,
        "engine_capability_version": resolved_capability,
    }
    return payload
