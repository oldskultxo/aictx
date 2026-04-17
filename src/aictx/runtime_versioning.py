from __future__ import annotations

from typing import Any

from ._version import __version__

CURRENT_ENGINE_CAPABILITY_VERSION = 16
LEGACY_ITERATION_TO_CAPABILITY_VERSION = {
    str(version): version for version in range(1, CURRENT_ENGINE_CAPABILITY_VERSION + 1)
}


def current_installed_version() -> str:
    return __version__


def current_engine_capability_version() -> int:
    return CURRENT_ENGINE_CAPABILITY_VERSION


def deprecated_installed_iteration() -> int:
    return current_engine_capability_version()


def normalize_installed_version(value: Any, *, fallback: str = "unknown") -> str:
    text = str(value or "").strip()
    return text or fallback


def legacy_iteration_to_capability_version(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    mapped = LEGACY_ITERATION_TO_CAPABILITY_VERSION.get(text)
    if mapped is not None:
        return mapped
    try:
        parsed = int(text)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 1 else None


def normalize_engine_capability_version(value: Any, *, legacy_iteration: Any = None) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = None
    if parsed is not None and parsed >= 1:
        return parsed
    return legacy_iteration_to_capability_version(legacy_iteration)


def resolve_version_payload(
    payload: dict[str, Any] | None,
    *,
    fallback_installed_version: str = "unknown",
    fallback_capability_version: int | None = None,
) -> dict[str, Any]:
    source = payload or {}
    installed_version = normalize_installed_version(source.get("installed_version"), fallback=fallback_installed_version)
    capability_version = normalize_engine_capability_version(
        source.get("engine_capability_version"),
        legacy_iteration=source.get("installed_iteration"),
    )
    if capability_version is None:
        capability_version = fallback_capability_version
    compat_iteration = str(source.get("installed_iteration", "") or "").strip()
    if not compat_iteration:
        compat_iteration = str(capability_version) if capability_version is not None else "unknown"
    return {
        "installed_version": installed_version,
        "engine_capability_version": capability_version,
        "installed_iteration": compat_iteration,
    }


def compat_version_payload(
    *,
    installed_version: str | None = None,
    capability_version: int | None = None,
    include_deprecated_iteration: bool = True,
) -> dict[str, Any]:
    resolved_version = normalize_installed_version(installed_version, fallback=current_installed_version())
    resolved_capability = capability_version or current_engine_capability_version()
    payload: dict[str, Any] = {
        "installed_version": resolved_version,
        "engine_capability_version": resolved_capability,
    }
    if include_deprecated_iteration:
        payload["installed_iteration"] = resolved_capability
    return payload
