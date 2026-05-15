from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

PORTABILITY_POLICY_VERSION = 2

AICTX_GITIGNORE_START = "# AICTX:START gitignore"
AICTX_GITIGNORE_END = "# AICTX:END gitignore"
AICTX_GITATTRIBUTES_START = "# AICTX:START gitattributes"
AICTX_GITATTRIBUTES_END = "# AICTX:END gitattributes"
PORTABILITY_MODE_LOCAL_ONLY = "local-only"
PORTABILITY_MODE_PORTABLE = "portable-continuity"
PORTABILITY_PROFILE_TEAM_SAFE = "team-safe"

PORTABILITY_STATE_PATH = Path(".aictx/continuity/portability.json")

PORTABLE_CONTINUITY_PATTERNS = [
    ".aictx/tasks/threads/*.json",
    ".aictx/tasks/threads/*.events.jsonl",
    ".aictx/continuity/portability.json",
    ".aictx/continuity/handoffs.jsonl",
    ".aictx/continuity/decisions.jsonl",
    ".aictx/continuity/semantic_repo/*.json",
    ".aictx/failure_memory/failure_patterns.jsonl",
    ".aictx/strategy_memory/strategies.jsonl",
    ".aictx/area_memory/areas/*.json",
    ".aictx/repo_map/config.json",
]

PORTABLE_JSONL_MERGE_PATTERNS = [
    ".aictx/tasks/threads/*.events.jsonl",
    ".aictx/continuity/handoffs.jsonl",
    ".aictx/continuity/decisions.jsonl",
    ".aictx/failure_memory/failure_patterns.jsonl",
    ".aictx/strategy_memory/strategies.jsonl",
]

LOCAL_ONLY_PATTERNS = [
    ".aictx/boot/**",
    ".aictx/cost/**",
    ".aictx/delta/**",
    ".aictx/indexes/**",
    ".aictx/logs/**",
    ".aictx/metrics/**",
    ".aictx/store/**",
    ".aictx/task_memory/**",
    ".aictx/memory_graph/**",
    ".aictx/tasks/active.json",
    ".aictx/continuity/handoff.json",
    ".aictx/continuity/semantic_repo.json",
    ".aictx/area_memory/areas.json",
    ".aictx/failure_memory/failure_index.json",
    ".aictx/failure_memory/index.json",
    ".aictx/failure_memory/failure_memory_status.json",
    ".aictx/continuity/session.json",
    ".aictx/continuity/last_execution_summary.md",
    ".aictx/continuity/continuity_metrics.json",
    ".aictx/continuity/dedupe_report.json",
    ".aictx/continuity/staleness.json",
    ".aictx/continuity/resume_capsule.md",
    ".aictx/continuity/resume_capsule.json",
    ".aictx/repo_map/index.json",
    ".aictx/repo_map/manifest.json",
    ".aictx/repo_map/status.json",
]

PORTABLE_GITATTRIBUTES_LINES = [
    AICTX_GITATTRIBUTES_START,
    f"# profile: {PORTABILITY_PROFILE_TEAM_SAFE}",
    "# Git's built-in union merge driver keeps independently appended JSONL rows.",
    *[f"{pattern} merge=union" for pattern in PORTABLE_JSONL_MERGE_PATTERNS],
    AICTX_GITATTRIBUTES_END,
]

LOCAL_ONLY_GITIGNORE_LINES = [
    AICTX_GITIGNORE_START,
    f"# mode: {PORTABILITY_MODE_LOCAL_ONLY}",
    ".aictx/",
    AICTX_GITIGNORE_END,
]

PORTABLE_GITIGNORE_LINES = [
    AICTX_GITIGNORE_START,
    f"# mode: {PORTABILITY_MODE_PORTABLE}",
    "",
    ".aictx/*",
    "!.aictx/",
    "",
    "!.aictx/tasks/",
    ".aictx/tasks/*",
    "!.aictx/tasks/threads/",
    ".aictx/tasks/threads/*",
    "!.aictx/tasks/threads/*.json",
    "!.aictx/tasks/threads/*.events.jsonl",
    "",
    "!.aictx/continuity/",
    ".aictx/continuity/*",
    "!.aictx/continuity/portability.json",
    "!.aictx/continuity/handoffs.jsonl",
    "!.aictx/continuity/decisions.jsonl",
    "!.aictx/continuity/semantic_repo/",
    ".aictx/continuity/semantic_repo/*",
    "!.aictx/continuity/semantic_repo/*.json",
    "",
    "!.aictx/failure_memory/",
    ".aictx/failure_memory/*",
    "!.aictx/failure_memory/failure_patterns.jsonl",
    "",
    "!.aictx/strategy_memory/",
    ".aictx/strategy_memory/*",
    "!.aictx/strategy_memory/strategies.jsonl",
    "",
    "!.aictx/area_memory/",
    ".aictx/area_memory/*",
    "!.aictx/area_memory/areas/",
    ".aictx/area_memory/areas/*",
    "!.aictx/area_memory/areas/*.json",
    "",
    "!.aictx/repo_map/",
    ".aictx/repo_map/*",
    "!.aictx/repo_map/config.json",
    "",
    AICTX_GITIGNORE_END,
]


def render_aictx_gitignore_block(*, portable_continuity: bool) -> str:
    lines = PORTABLE_GITIGNORE_LINES if portable_continuity else LOCAL_ONLY_GITIGNORE_LINES
    return "\n".join(lines).rstrip() + "\n"


def strip_aictx_gitignore_block(text: str) -> str:
    if AICTX_GITIGNORE_START not in text or AICTX_GITIGNORE_END not in text:
        return text
    start = text.index(AICTX_GITIGNORE_START)
    end = text.index(AICTX_GITIGNORE_END, start) + len(AICTX_GITIGNORE_END)
    head = text[:start].rstrip()
    tail = text[end:].lstrip("\n")
    pieces = [piece for piece in [head, tail] if piece]
    return ("\n".join(pieces) + ("\n" if pieces else ""))


def render_aictx_gitattributes_block(*, portable_continuity: bool) -> str:
    if not portable_continuity:
        return ""
    return "\n".join(PORTABLE_GITATTRIBUTES_LINES).rstrip() + "\n"


def strip_aictx_gitattributes_block(text: str) -> str:
    if AICTX_GITATTRIBUTES_START not in text or AICTX_GITATTRIBUTES_END not in text:
        return text
    start = text.index(AICTX_GITATTRIBUTES_START)
    end = text.index(AICTX_GITATTRIBUTES_END, start) + len(AICTX_GITATTRIBUTES_END)
    head = text[:start].rstrip()
    tail = text[end:].lstrip("\n")
    pieces = [piece for piece in [head, tail] if piece]
    return ("\n".join(pieces) + ("\n" if pieces else ""))


def remove_unmanaged_aictx_gitignore_lines(text: str) -> str:
    lines = text.splitlines()
    filtered = [line for line in lines if line.strip() != ".aictx/"]
    if not filtered:
        return ""
    return "\n".join(filtered).rstrip() + "\n"


def detect_portable_continuity_from_gitignore(repo: Path) -> bool | None:
    path = repo / ".gitignore"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    if AICTX_GITIGNORE_START not in text or AICTX_GITIGNORE_END not in text:
        return None
    start = text.index(AICTX_GITIGNORE_START)
    end = text.index(AICTX_GITIGNORE_END, start)
    block = text[start:end]
    if f"# mode: {PORTABILITY_MODE_PORTABLE}" in block:
        return True
    if f"# mode: {PORTABILITY_MODE_LOCAL_ONLY}" in block:
        return False
    return None


def load_portability_state(repo: Path) -> dict[str, Any]:
    path = repo / PORTABILITY_STATE_PATH
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _expected_portability_state(*, enabled: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": 1,
        "enabled": enabled,
        "mode": PORTABILITY_MODE_PORTABLE if enabled else PORTABILITY_MODE_LOCAL_ONLY,
        "policy_version": PORTABILITY_POLICY_VERSION,
    }
    if enabled:
        payload["profile"] = PORTABILITY_PROFILE_TEAM_SAFE
        payload["portable_patterns"] = list(PORTABLE_CONTINUITY_PATTERNS)
        payload["local_only_patterns"] = list(LOCAL_ONLY_PATTERNS)
        payload["merge_policy"] = {
            "transport": "git",
            "external_tool_required": False,
            "jsonl_merge_driver": "union",
            "portable_jsonl_patterns": list(PORTABLE_JSONL_MERGE_PATTERNS),
            "managed_gitattributes": ".gitattributes",
        }
    return payload


def write_portability_state(repo: Path, *, enabled: bool) -> Path:
    path = repo / PORTABILITY_STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _expected_portability_state(enabled=enabled)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


PORTABLE_JSONL_LIMITS = {
    ".aictx/tasks/threads/*.events.jsonl": 500,
    ".aictx/continuity/handoffs.jsonl": 200,
    ".aictx/continuity/decisions.jsonl": 500,
    ".aictx/failure_memory/failure_patterns.jsonl": 500,
    ".aictx/strategy_memory/strategies.jsonl": 500,
}

_SENSITIVE_FIELD_HINTS = [
    ("private_key", "private_key"),
    ("private-key", "private_key"),
    ("ssh_key", "private_key"),
    ("api_key", "api_key"),
    ("apikey", "api_key"),
    ("access_key", "access_key"),
    ("client_secret", "secret"),
    ("secret", "secret"),
    ("passwd", "password"),
    ("password", "password"),
    ("authorization", "credential"),
    ("auth_header", "credential"),
    ("cookie", "credential"),
    ("credential", "credential"),
    ("session", "session"),
    ("token", "token"),
]
_PRIVATE_KEY_BLOCK_RE = re.compile(
    r"-----BEGIN (?:[A-Z ]*PRIVATE KEY|OPENSSH PRIVATE KEY)-----.*?-----END (?:[A-Z ]*PRIVATE KEY|OPENSSH PRIVATE KEY)-----",
    re.IGNORECASE | re.DOTALL,
)
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
_GITHUB_TOKEN_RE = re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")
_AWS_ACCESS_KEY_RE = re.compile(r"\b(?:AKIA|ASIA|AIDA|AROA)[A-Z0-9]{16}\b")
_BEARER_RE = re.compile(r"(?i)\bbearer\s+([A-Za-z0-9._~+/=-]{8,})\b")
_ENV_ASSIGNMENT_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
_INLINE_SECRET_RE = re.compile(
    r"(?i)\b(?P<key>token|password|passwd|secret|api[_-]?key|access[_-]?key|client[_-]?secret|authorization|cookie|credential|session)\b"
    r"(?P<sep>\s*[:=]\s*)(?P<value>\S+)"
)


def _redacted_marker(kind: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "_", str(kind or "secret").strip().lower()).strip("_")
    return f"[redacted:{cleaned or 'secret'}]"


def _normalized_field_name(field_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(field_name or "").strip().lower()).strip("_")


def _field_secret_kind(field_name: str) -> str:
    normalized = _normalized_field_name(field_name)
    if not normalized:
        return ""
    for hint, kind in _SENSITIVE_FIELD_HINTS:
        if hint in normalized:
            return kind
    return ""


def _sanitize_url_credentials(text: str) -> tuple[str, list[str]]:
    findings: list[str] = []
    try:
        parts = urlsplit(text)
    except ValueError:
        return text, findings
    if not parts.scheme or "@" not in parts.netloc:
        return text, findings
    if ":" not in parts.netloc.split("@", 1)[0]:
        return text, findings
    sanitized = urlunsplit((parts.scheme, f"{_redacted_marker('credential')}@{parts.hostname or ''}{f':{parts.port}' if parts.port else ''}", parts.path, parts.query, parts.fragment))
    if sanitized != text:
        findings.append("credential")
    return sanitized, findings


def _sanitize_env_assignment(text: str) -> tuple[str, str]:
    match = _ENV_ASSIGNMENT_RE.match(text.strip())
    if not match:
        return text, ""
    key, value = match.groups()
    kind = _field_secret_kind(key)
    if not kind or not value.strip():
        return text, ""
    return f"{key}={_redacted_marker(kind)}", kind


def _sanitize_string(text: str, *, field_name: str = "") -> tuple[str, list[str]]:
    if not isinstance(text, str):
        return str(text), []
    findings: list[str] = []
    field_kind = _field_secret_kind(field_name)
    if field_kind and text.strip():
        return _redacted_marker(field_kind), [field_kind]
    if not text.strip():
        return text, findings
    if _PRIVATE_KEY_BLOCK_RE.search(text):
        return _redacted_marker("private_key"), ["private_key"]
    env_lines = text.splitlines()
    if len(env_lines) > 1:
        updated_lines: list[str] = []
        for line in env_lines:
            sanitized_line, kind = _sanitize_env_assignment(line)
            if kind:
                findings.append(kind)
            updated_lines.append(sanitized_line)
        candidate = "\n".join(updated_lines)
        if candidate != text:
            return candidate, findings
    else:
        sanitized_line, kind = _sanitize_env_assignment(text)
        if kind:
            return sanitized_line, [kind]
    updated = text
    updated, url_findings = _sanitize_url_credentials(updated)
    findings.extend(url_findings)
    updated, bearer_count = _BEARER_RE.subn(lambda match: f"Bearer {_redacted_marker('token')}", updated)
    if bearer_count:
        findings.extend(["token"] * bearer_count)
    for pattern, kind in (
        (_JWT_RE, "token"),
        (_GITHUB_TOKEN_RE, "token"),
        (_AWS_ACCESS_KEY_RE, "access_key"),
    ):
        updated, count = pattern.subn(_redacted_marker(kind), updated)
        if count:
            findings.extend([kind] * count)
    def _inline_replace(match: re.Match[str]) -> str:
        kind = _field_secret_kind(match.group("key")) or "secret"
        findings.append(kind)
        return f"{match.group('key')}{match.group('sep')}{_redacted_marker(kind)}"
    updated = _INLINE_SECRET_RE.sub(_inline_replace, updated)
    return updated, findings


def sanitize_portable_payload(
    payload: Any,
    *,
    relative_path: str,
    field_path: str = "",
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []

    def _walk(value: Any, *, current_field: str, current_name: str) -> tuple[Any, int]:
        if isinstance(value, Mapping):
            redactions = 0
            updated: dict[str, Any] = {}
            for key, item in value.items():
                key_text = str(key)
                sanitized_key, key_kinds = _sanitize_string(key_text)
                for kind in key_kinds:
                    findings.append(
                        {
                            "path": relative_path,
                            "field": f"{current_field}.<key>" if current_field else "<key>",
                            "kind": kind,
                            "action": "redact",
                        }
                    )
                next_key = sanitized_key if isinstance(sanitized_key, str) else key_text
                next_field = f"{current_field}.{next_key}" if current_field else next_key
                sanitized, count = _walk(item, current_field=next_field, current_name=next_key)
                updated[next_key] = sanitized
                redactions += count + len(key_kinds)
            return updated, redactions
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            redactions = 0
            updated_items: list[Any] = []
            for index, item in enumerate(value):
                next_field = f"{current_field}[{index}]" if current_field else f"[{index}]"
                sanitized, count = _walk(item, current_field=next_field, current_name=current_name)
                updated_items.append(sanitized)
                redactions += count
            return updated_items, redactions
        if isinstance(value, str):
            sanitized, kinds = _sanitize_string(value, field_name=current_name)
            for kind in kinds:
                findings.append(
                    {
                        "path": relative_path,
                        "field": current_field or current_name or "<value>",
                        "kind": kind,
                        "action": "redact",
                    }
                )
            return sanitized, len(kinds)
        return value, 0

    sanitized_payload, redacted_fields_count = _walk(payload, current_field=field_path, current_name=field_path.rsplit(".", 1)[-1] if field_path else "")
    return {
        "payload": sanitized_payload,
        "changed": sanitized_payload != payload,
        "findings": findings,
        "redacted_fields_count": redacted_fields_count,
    }


def _relative_portable_path(repo_root: Path, path: Path | str) -> str:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate.relative_to(repo_root).as_posix()
    return candidate.as_posix()


def write_portable_json(repo_root: Path, path: Path | str, payload: Any) -> dict[str, Any]:
    relative_path = _relative_portable_path(repo_root, path)
    target = repo_root / relative_path
    sanitized = sanitize_portable_payload(payload, relative_path=relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(sanitized["payload"], indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return sanitized


def append_portable_jsonl(repo_root: Path, path: Path | str, row: dict[str, Any]) -> dict[str, Any]:
    relative_path = _relative_portable_path(repo_root, path)
    target = repo_root / relative_path
    sanitized = sanitize_portable_payload(row, relative_path=relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(sanitized["payload"], ensure_ascii=False, sort_keys=True) + "\n")
    return sanitized


def _jsonl_parse(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"rows": [], "invalid_rows": 0}
    rows: list[dict[str, Any]] = []
    invalid_rows = 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {"rows": [], "invalid_rows": 0}
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            invalid_rows += 1
            continue
        if isinstance(payload, dict):
            rows.append(payload)
        else:
            invalid_rows += 1
    return {"rows": rows, "invalid_rows": invalid_rows}


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        key = json.dumps(row, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def compact_portable_jsonl(repo: Path, *, apply: bool = False) -> dict[str, Any]:
    root = repo.expanduser().resolve()
    files: list[dict[str, Any]] = []
    total_duplicates = 0
    total_truncated = 0
    total_invalid_rows = 0
    total_secret_redactions = 0
    total_secret_findings = 0
    for pattern in PORTABLE_JSONL_MERGE_PATTERNS:
        limit = PORTABLE_JSONL_LIMITS.get(pattern, 500)
        for path in sorted(root.glob(pattern)):
            parsed = _jsonl_parse(path)
            before = list(parsed["rows"])
            invalid_rows = int(parsed["invalid_rows"] or 0)
            secret_findings: list[dict[str, str]] = []
            redacted_rows: list[dict[str, Any]] = []
            secret_redactions = 0
            relative_path = path.relative_to(root).as_posix()
            for index, row in enumerate(before):
                sanitized = sanitize_portable_payload(row, relative_path=relative_path, field_path=f"row[{index}]")
                secret_findings.extend(sanitized["findings"])
                secret_redactions += int(sanitized["redacted_fields_count"] or 0)
                redacted_rows.append(sanitized["payload"])
            deduped = _dedupe_rows(redacted_rows)
            truncated = max(0, len(deduped) - limit)
            after = deduped[-limit:] if limit and len(deduped) > limit else deduped
            duplicates = len(redacted_rows) - len(deduped)
            blocked = invalid_rows > 0
            changed = duplicates > 0 or truncated > 0 or secret_redactions > 0
            would_change = changed or blocked
            if changed and apply and not blocked:
                _write_jsonl(path, after)
            total_duplicates += duplicates
            total_truncated += truncated
            total_invalid_rows += invalid_rows
            total_secret_redactions += secret_redactions
            total_secret_findings += len(secret_findings)
            files.append({
                "path": relative_path,
                "rows_before": len(before),
                "rows_after": len(after),
                "duplicates_removed": duplicates,
                "rows_truncated": truncated,
                "invalid_rows": invalid_rows,
                "blocked_by_invalid_rows": blocked,
                "secret_redactions": secret_redactions,
                "secret_findings": secret_findings,
                "changed": changed,
                "would_change": would_change,
            })
    return {
        "applied": apply,
        "files": files,
        "duplicates_removed": total_duplicates,
        "rows_truncated": total_truncated,
        "invalid_rows": total_invalid_rows,
        "secret_redactions": total_secret_redactions,
        "secret_findings": total_secret_findings,
        "blocked_by_invalid_rows": any(item["blocked_by_invalid_rows"] for item in files),
        "changed": any(item["changed"] for item in files),
        "would_change": any(item["would_change"] for item in files),
    }


def _extract_managed_block(text: str, start_marker: str, end_marker: str) -> str:
    if start_marker not in text or end_marker not in text:
        return ""
    start = text.index(start_marker)
    end = text.index(end_marker, start) + len(end_marker)
    return text[start:end].strip()


def _portability_sync(root: Path, *, enabled: bool, state: dict[str, Any]) -> dict[str, Any]:
    expected_state = _expected_portability_state(enabled=enabled)
    gitignore_text = (root / ".gitignore").read_text(encoding="utf-8") if (root / ".gitignore").exists() else ""
    gitattributes_text = (root / ".gitattributes").read_text(encoding="utf-8") if (root / ".gitattributes").exists() else ""
    expected_gitignore = render_aictx_gitignore_block(portable_continuity=enabled).strip()
    expected_gitattributes = render_aictx_gitattributes_block(portable_continuity=enabled).strip()
    actual_gitignore = _extract_managed_block(gitignore_text, AICTX_GITIGNORE_START, AICTX_GITIGNORE_END)
    actual_gitattributes = _extract_managed_block(gitattributes_text, AICTX_GITATTRIBUTES_START, AICTX_GITATTRIBUTES_END)
    state_in_sync = state == expected_state if state else False
    gitignore_in_sync = actual_gitignore == expected_gitignore if expected_gitignore else not actual_gitignore
    gitattributes_in_sync = actual_gitattributes == expected_gitattributes if expected_gitattributes else not actual_gitattributes
    drift: list[str] = []
    if not state_in_sync:
        drift.append("portability_state")
    if not gitignore_in_sync:
        drift.append("gitignore")
    if not gitattributes_in_sync:
        drift.append("gitattributes")
    return {
        "state_in_sync": state_in_sync,
        "gitignore_in_sync": gitignore_in_sync,
        "gitattributes_in_sync": gitattributes_in_sync,
        "drift": drift,
    }


def portability_status(repo: Path) -> dict[str, Any]:
    root = repo.expanduser().resolve()
    state = load_portability_state(root)
    enabled = bool(state.get("enabled")) if isinstance(state.get("enabled"), bool) else bool(detect_portable_continuity_from_gitignore(root))
    portable_patterns = list(state.get("portable_patterns", PORTABLE_CONTINUITY_PATTERNS)) if isinstance(state, dict) else list(PORTABLE_CONTINUITY_PATTERNS)
    local_only_patterns = list(state.get("local_only_patterns", LOCAL_ONLY_PATTERNS)) if isinstance(state, dict) else list(LOCAL_ONLY_PATTERNS)
    snapshot_paths = [
        ".aictx/tasks/active.json",
        ".aictx/continuity/handoff.json",
        ".aictx/continuity/semantic_repo.json",
        ".aictx/area_memory/areas.json",
    ]
    legacy_snapshot_risks = [pattern for pattern in snapshot_paths if pattern in portable_patterns]
    tracked_snapshot_risks: list[str] = []
    try:
        tracked = subprocess.run(
            ["git", "ls-files", *snapshot_paths],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        if tracked.returncode == 0:
            tracked_snapshot_risks = [line.strip() for line in tracked.stdout.splitlines() if line.strip()]
    except OSError:
        tracked_snapshot_risks = []
    sync = _portability_sync(root, enabled=enabled, state=state if isinstance(state, dict) else {})
    status = "ok"
    compaction = compact_portable_jsonl(root, apply=False)
    secret_scan = scan_portable_secrets(root)
    if sync["drift"] or tracked_snapshot_risks or legacy_snapshot_risks or compaction.get("blocked_by_invalid_rows") or secret_scan.get("findings_count"):
        status = "warning"
    return {
        "status": status,
        "enabled": enabled,
        "mode": state.get("mode", PORTABILITY_MODE_PORTABLE if enabled else PORTABILITY_MODE_LOCAL_ONLY) if isinstance(state, dict) else "",
        "policy_version": state.get("policy_version") if isinstance(state, dict) else None,
        "profile": state.get("profile", "") if isinstance(state, dict) else "",
        "state_path": PORTABILITY_STATE_PATH.as_posix(),
        "gitattributes_path": ".gitattributes",
        "gitattributes_present": (root / ".gitattributes").exists(),
        "portable_patterns": portable_patterns,
        "local_only_patterns": local_only_patterns,
        "merge_policy": state.get("merge_policy", {}) if isinstance(state, dict) else {},
        "jsonl_compaction": compaction,
        "secret_scan": secret_scan,
        "sync": sync,
        "legacy_snapshot_risks": legacy_snapshot_risks,
        "tracked_snapshot_risks": tracked_snapshot_risks,
        "recommendations": [
            "run aictx portability compact --repo . --apply --json" if enabled else "enable with aictx init --portable-continuity",
        ]
        + (["run aictx internal migrate to upgrade portable snapshot policy"] if legacy_snapshot_risks else [])
        + (["untrack local-only snapshots with git rm --cached <path>"] if tracked_snapshot_risks else []),
        "warnings": (
            (["portable JSONL compaction is blocked by invalid rows; repair the file before applying compaction"] if compaction.get("blocked_by_invalid_rows") else [])
            + (["AICTX portability files are out of sync; re-run aictx init --portable-continuity"] if sync["drift"] else [])
            + (["portable artifacts contain sensitive values that should be redacted before commit"] if secret_scan.get("findings_count") else [])
        ),
    }


def scan_portable_secrets(repo: Path) -> dict[str, Any]:
    root = repo.expanduser().resolve()
    files: list[dict[str, Any]] = []
    findings: list[dict[str, str]] = []
    redacted_fields_count = 0
    for pattern in PORTABLE_CONTINUITY_PATTERNS:
        for path in sorted(root.glob(pattern)):
            relative_path = path.relative_to(root).as_posix()
            if path.suffix == ".jsonl":
                parsed = _jsonl_parse(path)
                file_findings: list[dict[str, str]] = []
                file_redactions = 0
                for index, row in enumerate(parsed["rows"]):
                    sanitized = sanitize_portable_payload(row, relative_path=relative_path, field_path=f"row[{index}]")
                    file_findings.extend(sanitized["findings"])
                    file_redactions += int(sanitized["redacted_fields_count"] or 0)
                try:
                    raw_lines = path.read_text(encoding="utf-8").splitlines()
                except OSError:
                    raw_lines = []
                for index, raw_line in enumerate(raw_lines):
                    stripped = raw_line.strip()
                    if not stripped:
                        continue
                    try:
                        payload = json.loads(stripped)
                    except json.JSONDecodeError:
                        sanitized_text, kinds = _sanitize_string(stripped)
                        if sanitized_text != stripped or kinds:
                            for kind in kinds or ["secret"]:
                                file_findings.append(
                                    {
                                        "path": relative_path,
                                        "field": f"line[{index}]",
                                        "kind": kind,
                                        "action": "redact",
                                    }
                                )
                            file_redactions += max(1, len(kinds))
                        continue
                    if not isinstance(payload, dict):
                        continue
                if file_findings:
                    files.append({"path": relative_path, "findings_count": len(file_findings), "redacted_fields_count": file_redactions})
                    findings.extend(file_findings)
                    redacted_fields_count += file_redactions
                continue
            if path.suffix != ".json":
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            sanitized = sanitize_portable_payload(payload, relative_path=relative_path)
            if sanitized["findings"]:
                files.append(
                    {
                        "path": relative_path,
                        "findings_count": len(sanitized["findings"]),
                        "redacted_fields_count": int(sanitized["redacted_fields_count"] or 0),
                    }
                )
                findings.extend(sanitized["findings"])
                redacted_fields_count += int(sanitized["redacted_fields_count"] or 0)
    return {
        "status": "warning" if findings else "ok",
        "findings_count": len(findings),
        "files": files,
        "redacted_fields_count": redacted_fields_count,
        "findings": findings,
    }
