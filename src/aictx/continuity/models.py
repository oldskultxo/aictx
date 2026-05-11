from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class StartupBanner:
    agent_label: str
    session_count: int
    lines: list[dict[str, Any]] = field(default_factory=list)
    canonical_text: str = ""

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "StartupBanner":
        header = payload.get("header") if isinstance(payload.get("header"), dict) else {}
        return cls(
            agent_label=str(header.get("agent_label") or payload.get("agent_label") or "agent"),
            session_count=int(header.get("session_count") or payload.get("session_count") or 0),
            lines=list(payload.get("lines") or []),
            canonical_text=str(payload.get("canonical_text") or ""),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "header": {"agent_label": self.agent_label, "session_count": self.session_count},
            "lines": list(self.lines),
            "canonical_text": self.canonical_text,
        }


@dataclass(slots=True)
class ResumeCapsule:
    request: str
    capsule: dict[str, Any]
    startup_banner_text: str = ""
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ResumeCapsule":
        return cls(
            request=str(payload.get("request") or ""),
            capsule=dict(payload.get("capsule") or {}),
            startup_banner_text=str(payload.get("startup_banner_text") or ""),
            warnings=[str(item) for item in payload.get("warnings", []) if str(item or "").strip()],
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "request": self.request,
            "capsule": dict(self.capsule),
            "startup_banner_text": self.startup_banner_text,
            "warnings": list(self.warnings),
        }
