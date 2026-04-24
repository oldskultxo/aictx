from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .failure_memory import lookup_failures
from .state import (
    REPO_CONTINUITY_DIR,
    REPO_CONTINUITY_SESSION_PATH,
    REPO_MEMORY_DIR,
    append_jsonl,
    read_json,
    read_jsonl,
    write_json,
)
from .strategy_memory import select_strategy

HANDOFF_PATH = REPO_CONTINUITY_DIR / "handoff.json"
DECISIONS_PATH = REPO_CONTINUITY_DIR / "decisions.jsonl"
SEMANTIC_REPO_PATH = REPO_CONTINUITY_DIR / "semantic_repo.json"


def _read_optional_json(repo_root: Path, relative_path: Path, expected_type: type, warnings: list[str]) -> Any:
    path = repo_root / relative_path
    if not path.exists():
        return {} if expected_type is dict else []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        warnings.append(f"malformed:{relative_path.as_posix()}")
        return {} if expected_type is dict else []
    if not isinstance(payload, expected_type):
        warnings.append(f"invalid_type:{relative_path.as_posix()}")
        return {} if expected_type is dict else []
    return payload


def _read_optional_jsonl(repo_root: Path, relative_path: Path, warnings: list[str]) -> list[dict[str, Any]]:
    path = repo_root / relative_path
    if not path.exists():
        return []
    rows = read_jsonl(path)
    invalid_lines = 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        warnings.append(f"unreadable:{relative_path.as_posix()}")
        return rows
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            invalid_lines += 1
            continue
        if not isinstance(payload, dict):
            invalid_lines += 1
    if invalid_lines:
        warnings.append(f"invalid_jsonl_lines:{relative_path.as_posix()}:{invalid_lines}")
    return rows


def _session_from_payload(session_identity: dict[str, Any] | None, repo_root: Path, warnings: list[str]) -> dict[str, Any]:
    if isinstance(session_identity, dict):
        session = session_identity.get("session")
        if isinstance(session, dict):
            extra_warnings = session_identity.get("warnings")
            if isinstance(extra_warnings, list):
                warnings.extend(str(item) for item in extra_warnings if str(item).strip())
            return dict(session)
    return _read_optional_json(repo_root, REPO_CONTINUITY_SESSION_PATH, dict, warnings)


def _session_summary_parts(session: dict[str, Any], repo_root: Path) -> tuple[str, int]:
    runtime = str(session.get("runtime") or "agent").strip() or "agent"
    repo_id = str(session.get("repo_id") or repo_root.name).strip() or repo_root.name
    agent_label = str(session.get("agent_label") or f"{runtime}@{repo_id}").strip() or f"{runtime}@{repo_id}"
    try:
        session_count = int(session.get("session_count") or 0)
    except (TypeError, ValueError):
        session_count = 0
    return agent_label, max(session_count, 0)


def render_continuity_summary(context: dict[str, Any], repo_root: Path) -> str:
    session = context.get("session") if isinstance(context.get("session"), dict) else {}
    loaded = context.get("loaded") if isinstance(context.get("loaded"), dict) else {}
    agent_label, session_count = _session_summary_parts(session, repo_root)
    lines = [
        f"{agent_label} (session #{session_count}) - awake",
        "",
        "Loaded:",
        f"- handoff: {'yes' if loaded.get('handoff') else 'no'}",
        f"- decisions: {'yes' if loaded.get('decisions') else 'no'}",
        f"- failures: {'yes' if loaded.get('failures') else 'no'}",
        f"- preferences: {'yes' if loaded.get('preferences') else 'no'}",
        f"- semantic_repo: {'yes' if loaded.get('semantic_repo') else 'no'}",
        f"- procedural_reuse: {'yes' if loaded.get('procedural_reuse') else 'no'}",
    ]
    return "\n".join(lines)


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


def _observed_files(prepared: dict[str, Any]) -> list[str]:
    log = prepared.get("last_execution_log") if isinstance(prepared.get("last_execution_log"), dict) else {}
    observation = prepared.get("execution_observation") if isinstance(prepared.get("execution_observation"), dict) else {}
    candidates: list[str] = []
    for source in (log, observation):
        for key in ("files_edited", "files_opened"):
            value = source.get(key)
            if isinstance(value, list):
                candidates.extend(str(item) for item in value)
    return _clean_string_list(candidates, limit=8)


def _has_nonempty_list(payload: dict[str, Any], key: str) -> bool:
    value = payload.get(key)
    return isinstance(value, list) and any(str(item or "").strip() for item in value)


def is_nontrivial_handoff_candidate(
    prepared: dict[str, Any],
    result: dict[str, Any],
    *,
    strategy_stored: bool = False,
    failure_recorded: bool = False,
    learning_stored: bool = False,
) -> bool:
    log = prepared.get("last_execution_log") if isinstance(prepared.get("last_execution_log"), dict) else {}
    observation = prepared.get("execution_observation") if isinstance(prepared.get("execution_observation"), dict) else {}
    for payload in (log, observation):
        if any(_has_nonempty_list(payload, key) for key in ("files_edited", "commands_executed", "tests_executed", "notable_errors")):
            return True
    if strategy_stored or failure_recorded or learning_stored:
        return True
    summary = str(result.get("result_summary") or "").strip()
    return bool(summary)


def persist_handoff_memory(
    repo_root: Path,
    prepared: dict[str, Any],
    result: dict[str, Any],
    *,
    timestamp: str,
    strategy_stored: bool = False,
    failure_recorded: bool = False,
    learning_stored: bool = False,
) -> dict[str, Any] | None:
    if not is_nontrivial_handoff_candidate(
        prepared,
        result,
        strategy_stored=strategy_stored,
        failure_recorded=failure_recorded,
        learning_stored=learning_stored,
    ):
        return None
    summary = str(result.get("result_summary") or "").strip()
    if not summary:
        return None
    session = prepared.get("continuity_context", {}).get("session", {}) if isinstance(prepared.get("continuity_context"), dict) else {}
    try:
        source_session = int(session.get("session_count") or 0) if isinstance(session, dict) else 0
    except (TypeError, ValueError):
        source_session = 0
    source_execution_id = str(prepared.get("envelope", {}).get("execution_id") or "") if isinstance(prepared.get("envelope"), dict) else ""
    handoff = {
        "summary": summary,
        "completed": [summary],
        "open_items": [],
        "risks": [],
        "next_steps": [],
        "recommended_starting_points": _observed_files(prepared),
        "updated_at": timestamp,
        "source_session": source_session,
        "source_execution_id": source_execution_id,
    }
    write_json(repo_root / HANDOFF_PATH, handoff)
    return {"path": (repo_root / HANDOFF_PATH).as_posix(), "handoff": handoff}


def _significant_decision(decision: dict[str, Any]) -> bool:
    if not str(decision.get("decision") or "").strip():
        return False
    if str(decision.get("rationale") or "").strip():
        return True
    return any(_clean_string_list(decision.get(key), limit=1) for key in ("alternatives", "constraints", "risks", "related_paths"))


def _session_count_from_prepared(prepared: dict[str, Any]) -> int:
    session = prepared.get("continuity_context", {}).get("session", {}) if isinstance(prepared.get("continuity_context"), dict) else {}
    try:
        return int(session.get("session_count") or 0) if isinstance(session, dict) else 0
    except (TypeError, ValueError):
        return 0


def persist_decision_memory(
    repo_root: Path,
    prepared: dict[str, Any],
    result: dict[str, Any],
    *,
    timestamp: str,
) -> list[dict[str, Any]]:
    raw_decisions = result.get("decisions")
    if not isinstance(raw_decisions, list):
        return []
    session_count = _session_count_from_prepared(prepared)
    execution_id = str(prepared.get("envelope", {}).get("execution_id") or "") if isinstance(prepared.get("envelope"), dict) else ""
    persisted: list[dict[str, Any]] = []
    for raw in raw_decisions:
        if not isinstance(raw, dict):
            continue
        if not _significant_decision(raw):
            continue
        entry = {
            "decision": str(raw.get("decision") or "").strip(),
            "rationale": str(raw.get("rationale") or "").strip(),
            "alternatives": _clean_string_list(raw.get("alternatives"), limit=8),
            "constraints": _clean_string_list(raw.get("constraints"), limit=8),
            "risks": _clean_string_list(raw.get("risks"), limit=8),
            "related_paths": _clean_string_list(raw.get("related_paths"), limit=8),
            "subsystem": str(raw.get("subsystem") or "").strip(),
            "timestamp": timestamp,
            "session": session_count,
            "execution_id": execution_id,
        }
        append_jsonl(repo_root / DECISIONS_PATH, entry)
        persisted.append(entry)
    return persisted


def _merge_unique(existing: Any, incoming: Any, *, limit: int = 12) -> list[str]:
    return _clean_string_list(_clean_string_list(existing, limit=limit) + _clean_string_list(incoming, limit=limit), limit=limit)


def _normalize_subsystem_update(raw: dict[str, Any], observed_files: list[str], observed_tests: list[str]) -> dict[str, Any] | None:
    name = str(raw.get("name") or "").strip()
    if not name:
        return None
    key_paths = _merge_unique(raw.get("key_paths"), observed_files)
    relevant_tests = _merge_unique(raw.get("relevant_tests"), observed_tests)
    return {
        "name": name,
        "description": str(raw.get("description") or "").strip(),
        "key_paths": key_paths,
        "entry_points": _clean_string_list(raw.get("entry_points"), limit=8),
        "relevant_tests": relevant_tests,
        "fragile_areas": _clean_string_list(raw.get("fragile_areas"), limit=8),
    }


def _semantic_session(prepared: dict[str, Any]) -> int:
    session = prepared.get("continuity_context", {}).get("session", {}) if isinstance(prepared.get("continuity_context"), dict) else {}
    try:
        return int(session.get("session_count") or 0) if isinstance(session, dict) else 0
    except (TypeError, ValueError):
        return 0


def persist_semantic_repo_memory(
    repo_root: Path,
    prepared: dict[str, Any],
    result: dict[str, Any],
    *,
    timestamp: str,
) -> dict[str, Any] | None:
    raw_updates = result.get("semantic_repo")
    if not isinstance(raw_updates, list):
        return None
    observation = prepared.get("execution_observation") if isinstance(prepared.get("execution_observation"), dict) else {}
    observed_files = _clean_string_list(
        list(observation.get("files_edited", []) or []) + list(observation.get("files_opened", []) or []),
        limit=12,
    )
    observed_tests = _clean_string_list(observation.get("tests_executed", []), limit=12)
    updates = [item for item in (_normalize_subsystem_update(raw, observed_files, observed_tests) for raw in raw_updates if isinstance(raw, dict)) if item]
    if not updates:
        return None
    path = repo_root / SEMANTIC_REPO_PATH
    existing = read_json(path, {})
    if not isinstance(existing, dict):
        existing = {}
    existing_subsystems = existing.get("subsystems") if isinstance(existing.get("subsystems"), list) else []
    by_name: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for raw in existing_subsystems:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        by_name[name] = {
            "name": name,
            "description": str(raw.get("description") or "").strip(),
            "key_paths": _clean_string_list(raw.get("key_paths"), limit=12),
            "entry_points": _clean_string_list(raw.get("entry_points"), limit=8),
            "relevant_tests": _clean_string_list(raw.get("relevant_tests"), limit=12),
            "fragile_areas": _clean_string_list(raw.get("fragile_areas"), limit=8),
        }
        order.append(name)
    for update in updates:
        name = update["name"]
        current = by_name.get(name)
        if current:
            current["description"] = update["description"] or current.get("description", "")
            current["key_paths"] = _merge_unique(current.get("key_paths"), update.get("key_paths"), limit=12)
            current["entry_points"] = _merge_unique(current.get("entry_points"), update.get("entry_points"), limit=8)
            current["relevant_tests"] = _merge_unique(current.get("relevant_tests"), update.get("relevant_tests"), limit=12)
            current["fragile_areas"] = _merge_unique(current.get("fragile_areas"), update.get("fragile_areas"), limit=8)
        else:
            by_name[name] = update
            order.append(name)
    payload = {
        "repo_id": str(existing.get("repo_id") or repo_root.name),
        "subsystems": [by_name[name] for name in order if name in by_name],
        "updated_at": timestamp,
        "source_session": _semantic_session(prepared),
    }
    write_json(path, payload)
    return {"path": path.as_posix(), "subsystems_updated": [item["name"] for item in updates], "semantic_repo": payload}


def _load_semantic_repo(
    repo_root: Path,
    warnings: list[str],
    *,
    request_text: str,
    files: list[str],
    area_id: str,
    max_full_subsystems: int = 4,
    max_relevant_subsystems: int = 3,
) -> dict[str, Any]:
    payload = _read_optional_json(repo_root, SEMANTIC_REPO_PATH, dict, warnings)
    if not payload:
        return {}
    subsystems = payload.get("subsystems") if isinstance(payload.get("subsystems"), list) else []
    normalized: list[dict[str, Any]] = []
    for raw in subsystems:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        normalized.append({
            "name": name,
            "description": str(raw.get("description") or "").strip(),
            "key_paths": _clean_string_list(raw.get("key_paths"), limit=12),
            "entry_points": _clean_string_list(raw.get("entry_points"), limit=8),
            "relevant_tests": _clean_string_list(raw.get("relevant_tests"), limit=12),
            "fragile_areas": _clean_string_list(raw.get("fragile_areas"), limit=8),
        })
    compact = len(normalized) <= max_full_subsystems
    if compact:
        return {
            "repo_id": str(payload.get("repo_id") or repo_root.name),
            "subsystems": normalized,
            "updated_at": str(payload.get("updated_at") or ""),
            "source_session": payload.get("source_session"),
        }
    tokens = {token for token in str(request_text or "").lower().replace("/", " ").replace("_", " ").split() if len(token) > 2}
    file_set = set(files or [])
    ranked: list[tuple[int, dict[str, Any]]] = []
    for subsystem in normalized:
        score = 0
        name = subsystem["name"].lower()
        description = subsystem["description"].lower()
        score += len(tokens.intersection(set(name.replace("_", " ").split()))) * 3
        score += len(tokens.intersection(set(description.replace("_", " ").split())))
        key_paths = subsystem.get("key_paths", []) if isinstance(subsystem.get("key_paths"), list) else []
        if file_set.intersection(set(key_paths)):
            score += 4
        if area_id and any(str(path).startswith(area_id) for path in key_paths):
            score += 3
        entry_points = subsystem.get("entry_points", []) if isinstance(subsystem.get("entry_points"), list) else []
        score += len(tokens.intersection(set(" ".join(entry_points).lower().replace("_", " ").split())))
        if score > 0:
            ranked.append((score, subsystem))
    ranked.sort(key=lambda item: (-item[0], item[1]["name"]))
    selected = [subsystem for _, subsystem in ranked[:max_relevant_subsystems]]
    return {
        "repo_id": str(payload.get("repo_id") or repo_root.name),
        "subsystems": selected,
        "updated_at": str(payload.get("updated_at") or ""),
        "source_session": payload.get("source_session"),
    }

def load_continuity_context(
    repo_root: Path,
    *,
    session_identity: dict[str, Any] | None = None,
    task_type: str = "",
    request_text: str = "",
    files: list[str] | None = None,
    primary_entry_point: str | None = None,
    commands: list[str] | None = None,
    tests: list[str] | None = None,
    errors: list[str] | None = None,
    area_id: str = "",
    max_decisions: int = 5,
    max_failures: int = 5,
) -> dict[str, Any]:
    warnings: list[str] = []
    session = _session_from_payload(session_identity, repo_root, warnings)
    preferences = _read_optional_json(repo_root, REPO_MEMORY_DIR / "user_preferences.json", dict, warnings)
    handoff = _read_optional_json(repo_root, HANDOFF_PATH, dict, warnings)
    decisions = _read_optional_jsonl(repo_root, DECISIONS_PATH, warnings)[-max_decisions:]
    semantic_repo = _load_semantic_repo(
        repo_root,
        warnings,
        request_text=request_text,
        files=list(files or []),
        area_id=str(area_id or ""),
    )
    failures = lookup_failures(
        repo_root,
        task_type=str(task_type or ""),
        text=str(request_text or ""),
        files=list(files or []),
        area_id=str(area_id or ""),
        limit=max_failures,
    )
    procedural_reuse = select_strategy(
        repo_root,
        str(task_type or "") or None,
        files=list(files or []),
        primary_entry_point=primary_entry_point,
        request_text=request_text,
        commands=list(commands or []),
        tests=list(tests or []),
        errors=list(errors or []),
        area_id=area_id,
    ) or {}
    loaded = {
        "session": bool(session),
        "handoff": bool(handoff),
        "decisions": bool(decisions),
        "failures": bool(failures),
        "preferences": bool(preferences),
        "semantic_repo": bool(semantic_repo),
        "procedural_reuse": bool(procedural_reuse),
    }
    context = {
        "agent_identity": session,
        "session": session,
        "loaded": loaded,
        "handoff": handoff,
        "decisions": decisions,
        "failures": failures,
        "semantic_repo": semantic_repo,
        "preferences": preferences,
        "procedural_reuse": procedural_reuse,
        "warnings": warnings,
    }
    context["continuity_summary_text"] = render_continuity_summary(context, repo_root)
    return context
