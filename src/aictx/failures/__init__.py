from __future__ import annotations

import json
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..runtime_io import slugify
from ..state import REPO_FAILURE_MEMORY_DIR, read_jsonl, write_json

FAILURE_PATTERNS_PATH = REPO_FAILURE_MEMORY_DIR / "failure_patterns.jsonl"
FAILURE_INDEX_PATH = REPO_FAILURE_MEMORY_DIR / "failure_index.json"


@dataclass(slots=True)
class ErrorEvent:
    toolchain: str = "unknown"
    phase: str = "runtime"
    severity: str = "error"
    message: str = ""
    code: str = ""
    file: str = ""
    line: str = ""
    command: str = ""
    exit_code: int = 0
    fingerprint: str = ""

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ErrorEvent":
        message = str(payload.get("message") or "").strip()[:500]
        raw_exit = payload.get("exit_code")
        exit_code = int(raw_exit or 0) if isinstance(raw_exit, (int, str)) and str(raw_exit or "").lstrip("-").isdigit() else 0
        event = cls(
            toolchain=str(payload.get("toolchain") or "unknown").strip() or "unknown",
            phase=str(payload.get("phase") or "runtime").strip() or "runtime",
            severity=str(payload.get("severity") or "error").strip() or "error",
            message=message,
            code=str(payload.get("code") or "").strip(),
            file=str(payload.get("file") or "").strip(),
            line=str(payload.get("line") or "").strip(),
            command=str(payload.get("command") or "").strip(),
            exit_code=exit_code,
            fingerprint=str(payload.get("fingerprint") or "").strip(),
        )
        if not event.fingerprint:
            event.fingerprint = slugify(":".join([event.toolchain, event.phase, event.code, event.file, event.message[:160]]))[:96]
        return event

    def to_payload(self) -> dict[str, Any]:
        return {
            "toolchain": self.toolchain,
            "phase": self.phase,
            "severity": self.severity,
            "message": self.message,
            "code": self.code,
            "file": self.file,
            "line": self.line,
            "command": self.command,
            "exit_code": self.exit_code,
            "fingerprint": self.fingerprint,
        }


@dataclass(slots=True)
class FailurePattern:
    failure_id: str
    signature: str
    task_type: str = "unknown"
    area_id: str = "unknown"
    error_text: str = ""
    failed_command: str = ""
    files_involved: list[str] = field(default_factory=list)
    attempted_fix_summary: str = ""
    status: str = "open"
    resolved_by_execution_id: str = ""
    resolved_by: str = ""
    occurrences: int = 1
    previous_occurrences: int = 0
    last_execution_id: str = ""
    symptoms: list[str] = field(default_factory=list)
    failed_attempts: list[str] = field(default_factory=list)
    ineffective_commands: list[str] = field(default_factory=list)
    related_paths: list[str] = field(default_factory=list)
    error_events: list[ErrorEvent] = field(default_factory=list)
    toolchains: list[str] = field(default_factory=list)
    phases: list[str] = field(default_factory=list)
    error_codes: list[str] = field(default_factory=list)
    error_fingerprints: list[str] = field(default_factory=list)
    subsystem: str = "unknown"
    resolution_hint: str = ""
    timestamp: str = ""
    session: int = 0

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "FailurePattern":
        signature = str(payload.get("signature") or payload.get("failure_signature") or "").strip()
        failure_id = str(payload.get("failure_id") or (f"failure::{signature}" if signature else "failure::unknown")).strip()
        return cls(
            failure_id=failure_id,
            signature=signature,
            task_type=str(payload.get("task_type") or "unknown"),
            area_id=str(payload.get("area_id") or "unknown"),
            error_text=str(payload.get("error_text") or ""),
            failed_command=str(payload.get("failed_command") or ""),
            files_involved=_clean_string_list(payload.get("files_involved", []), limit=8),
            attempted_fix_summary=str(payload.get("attempted_fix_summary") or ""),
            status=str(payload.get("status") or "open"),
            resolved_by_execution_id=str(payload.get("resolved_by_execution_id") or ""),
            resolved_by=str(payload.get("resolved_by") or ""),
            occurrences=int(payload.get("occurrences") or 1),
            previous_occurrences=int(payload.get("previous_occurrences") or 0),
            last_execution_id=str(payload.get("last_execution_id") or ""),
            symptoms=_clean_string_list(payload.get("symptoms", []), limit=3),
            failed_attempts=_clean_string_list(payload.get("failed_attempts", []), limit=3),
            ineffective_commands=_clean_string_list(payload.get("ineffective_commands", []), limit=5),
            related_paths=_clean_string_list(payload.get("related_paths", []), limit=8),
            error_events=[ErrorEvent.from_payload(item) for item in payload.get("error_events", []) if isinstance(item, dict)],
            toolchains=_clean_string_list(payload.get("toolchains", []), limit=5),
            phases=_clean_string_list(payload.get("phases", []), limit=5),
            error_codes=_clean_string_list(payload.get("error_codes", []), limit=5),
            error_fingerprints=_clean_string_list(payload.get("error_fingerprints", []), limit=5),
            subsystem=str(payload.get("subsystem") or payload.get("area_id") or "unknown"),
            resolution_hint=str(payload.get("resolution_hint") or ""),
            timestamp=str(payload.get("timestamp") or ""),
            session=int(payload.get("session") or 0),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "failure_id": self.failure_id,
            "signature": self.signature,
            "failure_signature": self.signature,
            "task_type": self.task_type,
            "area_id": self.area_id,
            "error_text": self.error_text,
            "failed_command": self.failed_command,
            "files_involved": list(self.files_involved),
            "attempted_fix_summary": self.attempted_fix_summary,
            "status": self.status,
            "resolved_by_execution_id": self.resolved_by_execution_id,
            "resolved_by": self.resolved_by,
            "occurrences": self.occurrences,
            "previous_occurrences": self.previous_occurrences,
            "last_execution_id": self.last_execution_id,
            "symptoms": list(self.symptoms),
            "failed_attempts": list(self.failed_attempts),
            "ineffective_commands": list(self.ineffective_commands),
            "related_paths": list(self.related_paths),
            "error_events": [event.to_payload() for event in self.error_events],
            "toolchains": list(self.toolchains),
            "phases": list(self.phases),
            "error_codes": list(self.error_codes),
            "error_fingerprints": list(self.error_fingerprints),
            "subsystem": self.subsystem,
            "resolution_hint": self.resolution_hint,
            "timestamp": self.timestamp,
            "session": self.session,
        }


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clean_string_list(values: Any, *, limit: int = 8) -> list[str]:
    if not isinstance(values, list):
        return []
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


def _session_count(prepared: dict[str, Any]) -> int:
    session = prepared.get("continuity_context", {}).get("session", {}) if isinstance(prepared.get("continuity_context"), dict) else {}
    try:
        return int(session.get("session_count") or 0) if isinstance(session, dict) else 0
    except (TypeError, ValueError):
        return 0


def _resolution_hint(task_type: str, commands: list[str], errors: list[str]) -> str:
    if errors and commands:
        return "Inspect the failure symptoms and affected paths before rerunning the ineffective command."
    if errors:
        return "Inspect the failure symptoms and related paths before retrying the same approach."
    if task_type:
        return f"Review prior {task_type} failure context before repeating the attempt."
    return "Review prior failure context before repeating the attempt."


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def failure_signature(task_type: str, errors: list[str], command: str = "") -> str:
    basis = " ".join(errors[:2] or [command, task_type]).strip() or "unknown_failure"
    return slugify(f"{task_type}:{basis}")[:96]


def _clean_error_events(value: Any, *, limit: int = 5) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, dict):
            continue
        event = ErrorEvent.from_payload(raw)
        if not event.message or event.fingerprint in seen:
            continue
        seen.add(event.fingerprint)
        events.append(event.to_payload())
        if len(events) >= limit:
            break
    return events


def _event_values(events: list[dict[str, Any]], key: str, *, limit: int = 5) -> list[str]:
    return _clean_string_list([str(event.get(key) or "") for event in events], limit=limit)


def load_failures(repo_root: Path) -> list[dict[str, Any]]:
    return read_jsonl(repo_root / FAILURE_PATTERNS_PATH)


def write_failure_index(repo_root: Path, rows: list[dict[str, Any]]) -> None:
    index = {
        "version": 1,
        "failure_count": len(rows),
        "records": [
            {
                "failure_id": row.get("failure_id"),
                "signature": row.get("signature"),
                "task_type": row.get("task_type"),
                "status": row.get("status"),
                "area_id": row.get("area_id"),
                "toolchains": row.get("toolchains", []),
                "phases": row.get("phases", []),
            }
            for row in rows
        ],
    }
    write_json(repo_root / FAILURE_INDEX_PATH, index)


def persist_failure_pattern(repo_root: Path, prepared: dict[str, Any], execution_log: dict[str, Any], result: dict[str, Any]) -> dict[str, Any] | None:
    errors = list(execution_log.get("notable_errors", [])) if isinstance(execution_log.get("notable_errors"), list) else []
    error_events = _clean_error_events(execution_log.get("error_events", []))
    if not errors and error_events:
        errors = _clean_string_list([str(event.get("message") or "") for event in error_events], limit=3)
    commands = list(execution_log.get("commands_executed", [])) if isinstance(execution_log.get("commands_executed"), list) else []
    if not errors and not result.get("success"):
        summary = str(result.get("result_summary") or "").strip()
        if summary:
            errors = [summary]
        elif commands:
            errors = [f"Command failed: {commands[0]}"]
    if not errors and result.get("success"):
        return None
    if not errors and not commands:
        return None
    event_fingerprint = str(error_events[0].get("fingerprint") or "") if error_events else ""
    signature = event_fingerprint or failure_signature(str(execution_log.get("task_type") or "unknown"), errors, commands[0] if commands else "")
    rows = load_failures(repo_root)
    existing = next((row for row in rows if row.get("signature") == signature and row.get("status") != "resolved"), None)
    task_type = str(execution_log.get("task_type") or "unknown")
    files_involved = _clean_string_list(execution_log.get("files_opened", []), limit=8)
    event_files = _event_values(error_events, "file", limit=8)
    related_paths = _clean_string_list(files_involved + event_files, limit=8)
    record = {
        "failure_id": existing.get("failure_id") if existing else f"failure::{signature}",
        "signature": signature,
        "failure_signature": signature,
        "task_type": task_type,
        "area_id": str(execution_log.get("area_id") or "unknown"),
        "error_text": "\n".join(errors[:3]),
        "failed_command": commands[0] if commands else "",
        "files_involved": files_involved,
        "attempted_fix_summary": str(result.get("result_summary") or ""),
        "status": "open",
        "resolved_by_execution_id": "",
        "resolved_by": "",
        "occurrences": int(existing.get("occurrences", 0) or 0) + 1 if existing else 1,
        "previous_occurrences": int(existing.get("occurrences", 0) or 0) if existing else 0,
        "last_execution_id": str(prepared.get("envelope", {}).get("execution_id") or ""),
        "symptoms": _clean_string_list(errors[:3], limit=3),
        "failed_attempts": _clean_string_list([str(result.get("result_summary") or "")], limit=3),
        "ineffective_commands": _clean_string_list(commands, limit=5),
        "related_paths": related_paths,
        "error_events": error_events,
        "toolchains": _event_values(error_events, "toolchain", limit=5),
        "phases": _event_values(error_events, "phase", limit=5),
        "error_codes": _event_values(error_events, "code", limit=5),
        "error_fingerprints": _event_values(error_events, "fingerprint", limit=5),
        "subsystem": str(execution_log.get("area_id") or task_type or "unknown"),
        "resolution_hint": _resolution_hint(task_type, commands, errors),
        "timestamp": now_iso(),
        "session": _session_count(prepared),
    }
    record = FailurePattern.from_payload(record).to_payload()
    append_jsonl(repo_root / FAILURE_PATTERNS_PATH, record)
    write_failure_index(repo_root, load_failures(repo_root))
    return {
        "path": (repo_root / FAILURE_PATTERNS_PATH).as_posix(),
        "failure_id": record["failure_id"],
        "signature": signature,
        "existing": bool(existing),
        "occurrences": record["occurrences"],
        "toolchains": record["toolchains"],
        "phases": record["phases"],
        "error_codes": record["error_codes"],
    }


GENERIC_FAILURE_TOKENS = {"fail", "failed", "failure", "error", "fix", "bug", "test", "tests"}


def lookup_failures(repo_root: Path, *, task_type: str = "", text: str = "", files: list[str] | None = None, area_id: str = "", limit: int = 5) -> list[dict[str, Any]]:
    rows = [row for row in load_failures(repo_root) if row.get("status") != "resolved"]
    tokens = {token for token in slugify(text).split("_") if len(token) > 2 and token not in GENERIC_FAILURE_TOKENS}
    file_set = set(files or [])
    ranked: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        score = 0
        if task_type and row.get("task_type") == task_type:
            score += 5
        if area_id and row.get("area_id") == area_id:
            score += 4
        signature_text = " ".join([str(row.get("signature", "")), str(row.get("failure_signature", ""))])
        signature_tokens = {token for token in slugify(signature_text).split("_") if len(token) > 2 and token not in GENERIC_FAILURE_TOKENS}
        score += 2 * len(tokens.intersection(signature_tokens))
        row_files = set(_clean_string_list(row.get("files_involved", [])) + _clean_string_list(row.get("related_paths", [])))
        if file_set.intersection(row_files):
            score += 3
        event_tokens: set[str] = set()
        for event in _clean_error_events(row.get("error_events", [])):
            event_tokens.update(token for token in slugify(" ".join([
                str(event.get("toolchain") or ""),
                str(event.get("phase") or ""),
                str(event.get("code") or ""),
                str(event.get("fingerprint") or ""),
                str(event.get("message") or ""),
            ])).split("_") if len(token) > 2 and token not in GENERIC_FAILURE_TOKENS)
        for key in ("toolchains", "phases", "error_codes", "error_fingerprints"):
            event_tokens.update(token for token in slugify(" ".join(_clean_string_list(row.get(key, [])))).split("_") if len(token) > 2 and token not in GENERIC_FAILURE_TOKENS)
        score += 2 * len(tokens.intersection(event_tokens))
        haystack = slugify(" ".join([
            str(row.get("error_text", "")),
            str(row.get("failed_command", "")),
            str(row.get("attempted_fix_summary", "")),
            str(row.get("failure_signature", "")),
            " ".join(_clean_string_list(row.get("symptoms", []))),
            " ".join(_clean_string_list(row.get("ineffective_commands", []))),
            " ".join(_clean_string_list(row.get("related_paths", []))),
            str(row.get("resolution_hint", "")),
            " ".join(_clean_string_list(row.get("toolchains", []))),
            " ".join(_clean_string_list(row.get("phases", []))),
            " ".join(_clean_string_list(row.get("error_codes", []))),
            " ".join(_clean_string_list(row.get("error_fingerprints", []))),
        ]))
        score += len(tokens.intersection(set(haystack.split("_"))))
        if score:
            ranked.append((score, row))
    ranked.sort(key=lambda item: (-item[0], str(item[1].get("failure_id", ""))))
    safe_limit = max(0, int(limit or 0))
    return [{**row, "match_score": score} for score, row in ranked[:safe_limit]]


def link_resolved_failures(repo_root: Path, prepared: dict[str, Any], execution_log: dict[str, Any]) -> list[str]:
    related = lookup_failures(
        repo_root,
        task_type=str(execution_log.get("task_type") or ""),
        text=str(prepared.get("envelope", {}).get("user_request") or ""),
        files=list(execution_log.get("files_opened", [])) if isinstance(execution_log.get("files_opened"), list) else [],
        area_id=str(execution_log.get("area_id") or ""),
    )
    if not related:
        return []
    rows = load_failures(repo_root)
    resolved_ids = {row["failure_id"] for row in related[:2]}
    updated: list[dict[str, Any]] = []
    for row in rows:
        if row.get("failure_id") in resolved_ids and row.get("status") != "resolved":
            row = dict(row)
            row["status"] = "resolved"
            resolved_by = str(prepared.get("envelope", {}).get("execution_id") or "")
            row["resolved_by_execution_id"] = resolved_by
            row["resolved_by"] = resolved_by
        updated.append(row)
    path = repo_root / FAILURE_PATTERNS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in updated) + ("\n" if updated else ""), encoding="utf-8")
    write_failure_index(repo_root, updated)
    return sorted(resolved_ids)
