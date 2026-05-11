from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item or "").strip()]


@dataclass(slots=True)
class ExecutionEnvelope:
    repo_root: str
    user_request: str
    agent_id: str
    adapter_id: str
    execution_id: str
    timestamp: str = ""

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ExecutionEnvelope":
        user_request = str(payload.get("user_request") or payload.get("task") or "").strip()
        if not user_request:
            raise ValueError("user_request is required")
        agent_id = str(payload.get("agent_id") or payload.get("agent") or "").strip()
        if not agent_id:
            raise ValueError("agent_id is required")
        execution_id = str(payload.get("execution_id") or "").strip()
        if not execution_id:
            raise ValueError("execution_id is required")
        return cls(
            repo_root=str(Path(payload.get("repo_root") or ".").expanduser().resolve()),
            user_request=user_request,
            agent_id=agent_id,
            adapter_id=str(payload.get("adapter_id") or agent_id).strip() or agent_id,
            execution_id=execution_id,
            timestamp=str(payload.get("timestamp") or ""),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "repo_root": self.repo_root,
            "user_request": self.user_request,
            "agent_id": self.agent_id,
            "adapter_id": self.adapter_id,
            "execution_id": self.execution_id,
            "timestamp": self.timestamp,
        }


@dataclass(slots=True)
class ContextPacket:
    path: str = ""
    relevant_failures: list[dict[str, Any]] = field(default_factory=list)
    repo_scope: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ContextPacket":
        return cls(
            path=str(payload.get("path") or ""),
            relevant_failures=list(payload.get("relevant_failures") or []),
            repo_scope=list(payload.get("repo_scope") or []),
        )

    def to_payload(self) -> dict[str, Any]:
        return {"path": self.path, "relevant_failures": list(self.relevant_failures), "repo_scope": list(self.repo_scope)}


@dataclass(slots=True)
class PreparedExecution:
    envelope: ExecutionEnvelope
    execution_mode: str = "plain"
    related_failures: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "PreparedExecution":
        return cls(
            envelope=ExecutionEnvelope.from_payload(payload.get("envelope", payload)),
            execution_mode=str(payload.get("execution_mode") or "plain"),
            related_failures=list(payload.get("related_failures") or []),
        )

    def to_payload(self) -> dict[str, Any]:
        return {"envelope": self.envelope.to_payload(), "execution_mode": self.execution_mode, "related_failures": list(self.related_failures)}


@dataclass(slots=True)
class FinalizedExecution:
    execution_id: str
    success: bool
    result_summary: str = ""
    failure_persisted: dict[str, Any] | None = None
    resolved_failures: list[str] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "FinalizedExecution":
        telemetry = payload.get("telemetry_entry") if isinstance(payload.get("telemetry_entry"), dict) else {}
        return cls(
            execution_id=str(payload.get("execution_id") or telemetry.get("execution_id") or ""),
            success=bool(telemetry.get("success", payload.get("success", False))),
            result_summary=str(telemetry.get("result_summary") or payload.get("result_summary") or ""),
            failure_persisted=payload.get("failure_persisted") if isinstance(payload.get("failure_persisted"), dict) else None,
            resolved_failures=_list(payload.get("resolved_failures")),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "success": self.success,
            "result_summary": self.result_summary,
            "failure_persisted": self.failure_persisted,
            "resolved_failures": list(self.resolved_failures),
        }


@dataclass(slots=True)
class AgentSummary:
    text: str = ""
    details_path: str = ""

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "AgentSummary":
        return cls(text=str(payload.get("agent_summary_text") or ""), details_path=str(payload.get("details_path") or ""))

    def to_payload(self) -> dict[str, str]:
        return {"agent_summary_text": self.text, "details_path": self.details_path}
