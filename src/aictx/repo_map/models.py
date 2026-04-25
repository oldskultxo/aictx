from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .setup import REPO_MAP_PROVIDER


@dataclass
class RepoMapConfig:
    version: int = 1
    enabled: bool = False
    provider: str = REPO_MAP_PROVIDER
    quick_refresh_budget_ms: int = 300
    quick_refresh_max_files: int = 20
    max_parse_file_bytes: int = 512000

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": int(self.version),
            "enabled": bool(self.enabled),
            "provider": str(self.provider or REPO_MAP_PROVIDER),
            "quick_refresh_budget_ms": int(self.quick_refresh_budget_ms),
            "quick_refresh_max_files": int(self.quick_refresh_max_files),
            "max_parse_file_bytes": int(self.max_parse_file_bytes),
        }


@dataclass
class RepoMapStatus:
    version: int = 1
    enabled: bool = False
    available: bool = False
    provider: str = REPO_MAP_PROVIDER
    last_refresh_status: str = "never"
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": int(self.version),
            "enabled": bool(self.enabled),
            "available": bool(self.available),
            "provider": str(self.provider or REPO_MAP_PROVIDER),
            "last_refresh_status": str(self.last_refresh_status or "never"),
            "warnings": [str(item) for item in self.warnings],
        }


@dataclass
class RepoMapSymbol:
    name: str = ""
    kind: str = ""
    line: int = 0
    end_line: int = 0
    language: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": str(self.name or ""),
            "kind": str(self.kind or ""),
            "line": int(self.line),
            "end_line": int(self.end_line),
            "language": str(self.language or ""),
        }


@dataclass
class RepoMapImport:
    module: str = ""
    symbol: str = ""
    alias: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": str(self.module or ""),
            "symbol": str(self.symbol or ""),
            "alias": str(self.alias or ""),
        }


@dataclass
class RepoMapFileRecord:
    path: str = ""
    language: str = ""
    symbols: list[RepoMapSymbol] = field(default_factory=list)
    imports: list[RepoMapImport] = field(default_factory=list)
    metadata_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path or ""),
            "language": str(self.language or ""),
            "symbols": [item.to_dict() for item in self.symbols],
            "imports": [item.to_dict() for item in self.imports],
            "metadata_only": bool(self.metadata_only),
        }


def normalize_repomap_config(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(payload or {})
    return RepoMapConfig(
        version=int(data.get("version", 1)),
        enabled=bool(data.get("enabled", False)),
        provider=str(data.get("provider") or REPO_MAP_PROVIDER),
        quick_refresh_budget_ms=int(data.get("quick_refresh_budget_ms", 300)),
        quick_refresh_max_files=int(data.get("quick_refresh_max_files", 20)),
        max_parse_file_bytes=int(data.get("max_parse_file_bytes", 512000)),
    ).to_dict()


def normalize_repomap_status(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(payload or {})
    return RepoMapStatus(
        version=int(data.get("version", 1)),
        enabled=bool(data.get("enabled", False)),
        available=bool(data.get("available", False)),
        provider=str(data.get("provider") or REPO_MAP_PROVIDER),
        last_refresh_status=str(data.get("last_refresh_status") or "never"),
        warnings=[str(item) for item in data.get("warnings", [])] if isinstance(data.get("warnings", []), list) else [],
    ).to_dict()
