from __future__ import annotations

import fnmatch
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .state import REPO_CONTINUITY_DIR, REPO_METRICS_DIR, read_json, write_json

CONTRACT_COMPLIANCE_VERSION = 1
CONTRACT_COMPLIANCE_LOG_PATH = REPO_METRICS_DIR / "contract_compliance.jsonl"
CONTRACT_STORE_DIR = REPO_CONTINUITY_DIR / "contracts"
CONTRACT_INDEX_PATH = CONTRACT_STORE_DIR / "index.json"

_ALLOWED_STATUSES = {"followed", "partial", "violated", "not_evaluated"}
_GAP_POLICY_BY_KIND = {
    "missing_validation": {"severity": "needs-validation", "policy": "prioritize_before_new_work", "blocking": False},
    "edit_outside_scope": {"severity": "needs-review", "policy": "surface_before_continuing", "blocking": False},
    "missing_first_action": {"severity": "caution", "policy": "surface_before_continuing", "blocking": False},
    "structural_entrypoints_ignored": {"severity": "caution", "policy": "surface_as_context", "blocking": False},
}
_GAP_SEVERITY_ORDER = {"info": 0, "caution": 1, "needs-review": 2, "needs-validation": 3, "blocking": 4}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clean_string_list(value: Any, limit: int = 20) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def _norm_command(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _path_matches(path: str, patterns: list[str]) -> bool:
    normalized = str(path or "").strip().replace("\\", "/")
    if not normalized:
        return False
    for pattern in patterns:
        pat = str(pattern or "").strip().replace("\\", "/")
        if not pat:
            continue
        if normalized == pat or fnmatch.fnmatch(normalized, pat):
            return True
    return False


def _issue(code: str, severity: str, detail: str = "", evidence: str = "") -> dict[str, str]:
    return {
        "code": str(code or "").strip(),
        "severity": str(severity or "").strip(),
        "detail": str(detail or "").strip(),
        "evidence": str(evidence or "").strip(),
    }


def _human_issue(code: str) -> str:
    return {
        "missing_first_action": "first action was not observed",
        "edit_outside_scope": "edited outside contract scope",
        "canonical_test_missing": "canonical test was not observed",
        "canonical_test_not_observed": "canonical test was not observed",
        "orientation_command_order_unknown": "orientation command order is unknown",
        "first_action_not_observable": "first action was not observable",
    }.get(str(code or "").strip(), str(code or "").strip())


def _gap(
    kind: str,
    *,
    source_code: str,
    summary: str,
    next_action: str = "",
    recommended_command: str = "",
    related_paths: list[str] | None = None,
    expected: str = "",
    observed: list[str] | None = None,
) -> dict[str, Any]:
    gap_kind = str(kind or "").strip()
    policy = dict(_GAP_POLICY_BY_KIND.get(gap_kind, {"severity": "info", "policy": "surface_as_context", "blocking": False}))
    payload = {
        "kind": gap_kind,
        "severity": str(policy.get("severity") or "info"),
        "policy": str(policy.get("policy") or "surface_as_context"),
        "blocking": bool(policy.get("blocking")),
        "source_code": str(source_code or "").strip(),
        "summary": str(summary or "").strip(),
        "expected": str(expected or "").strip(),
        "observed": _clean_string_list(observed or [], limit=8),
        "next_action": str(next_action or "").strip(),
        "recommended_command": str(recommended_command or "").strip(),
        "related_paths": _clean_string_list(related_paths or [], limit=8),
    }
    return {key: value for key, value in payload.items() if value not in ("", [], None)}


def contract_gap_strength(severity: str) -> int:
    return _GAP_SEVERITY_ORDER.get(str(severity or "info").strip(), 0)


def strongest_contract_gap(gaps: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [gap for gap in gaps if isinstance(gap, dict)]
    if not rows:
        return {}
    return max(rows, key=lambda gap: contract_gap_strength(str(gap.get("severity") or "info")))


def contract_gaps_from_compliance(compliance: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert evaluated contract compliance into carryover gaps.

    Pure helper: no repo reads/writes. The result is intentionally compact so
    Work State can persist unresolved contract obligations without a new store.
    """
    payload = compliance if isinstance(compliance, dict) else {}
    if str(payload.get("status") or "") not in {"partial", "violated"}:
        return []
    violations = [row for row in payload.get("violations", []) if isinstance(row, dict)] if isinstance(payload.get("violations"), list) else []
    warnings = [row for row in payload.get("warnings", []) if isinstance(row, dict)] if isinstance(payload.get("warnings"), list) else []
    issues = violations + warnings
    issue_codes = {str(item.get("code") or "").strip() for item in issues}
    by_code = {str(item.get("code") or "").strip(): item for item in issues}
    gaps: list[dict[str, Any]] = []

    if "canonical_test_not_observed" in issue_codes or "canonical_test_missing" in issue_codes:
        source_code = "canonical_test_missing" if "canonical_test_missing" in issue_codes else "canonical_test_not_observed"
        expected = str((payload.get("test_command") if isinstance(payload.get("test_command"), dict) else {}).get("expected") or "")
        detail = str(by_code.get(source_code, {}).get("detail") or "Canonical validation was not observed.")
        command_text = expected or str(by_code.get(source_code, {}).get("evidence") or "").strip()
        gaps.append(
            _gap(
                "missing_validation",
                source_code=source_code,
                summary=detail,
                next_action=f"run expected validation command: {command_text}" if command_text else "run expected validation command",
                recommended_command=command_text,
                expected=command_text,
                observed=_clean_string_list((payload.get("test_command") if isinstance(payload.get("test_command"), dict) else {}).get("observed"), limit=8),
            )
        )

    if "missing_first_action" in issue_codes:
        expected = str((payload.get("first_action") if isinstance(payload.get("first_action"), dict) else {}).get("expected") or "")
        gaps.append(
            _gap(
                "missing_first_action",
                source_code="missing_first_action",
                summary=str(by_code.get("missing_first_action", {}).get("detail") or "Expected first action was not observed."),
                next_action=f"inspect required first action: {expected}" if expected else "inspect required first action",
                related_paths=[expected] if expected else [],
                expected=expected,
                observed=_clean_string_list((payload.get("first_action") if isinstance(payload.get("first_action"), dict) else {}).get("observed"), limit=8),
            )
        )

    if "edit_outside_scope" in issue_codes:
        edit_scope = payload.get("edit_scope") if isinstance(payload.get("edit_scope"), dict) else {}
        outside = _clean_string_list(edit_scope.get("outside_scope"), limit=8)
        gaps.append(
            _gap(
                "edit_outside_scope",
                source_code="edit_outside_scope",
                summary="Edited files outside contract scope.",
                next_action="review out-of-scope edits and run expected validation",
                related_paths=outside,
                observed=outside,
            )
        )

    if str(payload.get("structural_alignment") or "") == "ignored":
        structural = payload.get("structural_entry_points") if isinstance(payload.get("structural_entry_points"), dict) else {}
        expected_paths = _clean_string_list(structural.get("expected_first_files"), limit=8)
        gaps.append(
            _gap(
                "structural_entrypoints_ignored",
                source_code="structural_alignment_ignored",
                summary="Expected structural entry points were not inspected or edited.",
                next_action="inspect expected structural entry points before continuing",
                related_paths=expected_paths,
                expected=", ".join(expected_paths),
                observed=_clean_string_list(structural.get("observed_files"), limit=8),
            )
        )

    cleaned: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in gaps:
        key = (str(item.get("kind") or ""), str(item.get("source_code") or ""))
        if not item.get("kind") or key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
        if len(cleaned) >= 8:
            break
    return cleaned


def _not_evaluated(task_goal: str = "", *, contract_present: bool = False, main_issue: str = "") -> dict[str, Any]:
    issue = str(main_issue or "").strip()
    if issue == "no_execution_observation":
        compact_summary = "Contract: not evaluated — no execution observation."
    elif issue == "no_resume_contract":
        compact_summary = "Contract: not evaluated — no matching resume contract."
    else:
        compact_summary = "Contract: not evaluated."
    return {
        "version": CONTRACT_COMPLIANCE_VERSION,
        "contract_present": bool(contract_present),
        "status": "not_evaluated",
        "score": None,
        "task_goal": str(task_goal or ""),
        "main_issue": issue,
        "structural_alignment": "not_evaluated",
        "checks": {},
        "violations": [],
        "warnings": [],
        "compact_summary": compact_summary,
    }


def _normalize_path(value: str) -> str:
    return str(value or "").strip().replace("\\", "/")


def _structural_alignment(expected: list[str], observation: dict[str, Any]) -> dict[str, Any]:
    expected_paths = [_normalize_path(path) for path in expected if _normalize_path(path)]
    files_opened = [_normalize_path(path) for path in _clean_string_list(observation.get("files_opened"), limit=40)]
    files_edited = [_normalize_path(path) for path in _clean_string_list(observation.get("files_edited"), limit=40)]
    tests = [_normalize_path(path) for path in _clean_string_list(observation.get("tests_executed"), limit=60)]
    observed_primary = files_opened + files_edited
    if not expected_paths or not (observed_primary or tests):
        return {
            "status": "not_evaluated",
            "expected_first_files": expected_paths,
            "observed_files": observed_primary[:12],
            "matched_files": [],
        }
    expected_set = set(expected_paths)
    primary_matches = [path for path in observed_primary if path in expected_set]
    if primary_matches:
        return {
            "status": "followed",
            "expected_first_files": expected_paths,
            "observed_files": observed_primary[:12],
            "matched_files": primary_matches[:8],
        }
    test_matches = [path for path in tests if path in expected_set]
    if test_matches:
        return {
            "status": "partially_followed",
            "expected_first_files": expected_paths,
            "observed_files": observed_primary[:12],
            "matched_files": test_matches[:8],
        }
    return {
        "status": "ignored",
        "expected_first_files": expected_paths,
        "observed_files": observed_primary[:12],
        "matched_files": [],
    }




def _contract_goal_match(task_goal: str, contract_goal: str) -> dict[str, Any]:
    left = re.sub(r"\s+", " ", str(task_goal or "").strip().lower())
    right = re.sub(r"\s+", " ", str(contract_goal or "").strip().lower())
    if not left or not right:
        return {"matches": False, "level": "unknown"}
    if left == right:
        return {"matches": True, "level": "exact"}
    if min(len(left), len(right)) >= 16 and (left in right or right in left):
        return {"matches": True, "level": "substring"}
    left_words = {w for w in re.split(r"\W+", left) if len(w) >= 4}
    right_words = {w for w in re.split(r"\W+", right) if len(w) >= 4}
    overlap = len(left_words & right_words) / max(1, len(left_words | right_words))
    return {"matches": overlap >= 0.35, "level": "token_overlap" if overlap >= 0.35 else "different", "score": round(overlap, 4)}


def _contract_id_from_record(record: dict[str, Any]) -> str:
    raw = str(record.get("execution_id") or record.get("session_id") or record.get("generated_at") or _now_iso())
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw).strip("-._")
    return (safe or "contract")[:96]


def _contract_ref_from_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_id": str(record.get("contract_id") or ""),
        "path": str(record.get("path") or ""),
        "session_id": str(record.get("session_id") or ""),
        "execution_id": str(record.get("execution_id") or ""),
        "generated_at": str(record.get("generated_at") or ""),
        "task_goal": str(record.get("task_goal") or ""),
    }


def persist_resume_contract(
    repo_root: Path,
    resume_payload: dict[str, Any],
    *,
    session_id: str = "",
    agent_id: str = "",
    execution_id: str = "",
) -> dict[str, Any]:
    payload = resume_payload if isinstance(resume_payload, dict) else {}
    contract = payload.get("execution_contract") if isinstance(payload.get("execution_contract"), dict) else {}
    if not contract:
        return {}
    record: dict[str, Any] = {
        "version": CONTRACT_COMPLIANCE_VERSION,
        "generated_at": str(payload.get("generated_at") or _now_iso()),
        "request": str(payload.get("request") or ""),
        "task_goal": str(contract.get("task_goal") or payload.get("request") or ""),
        "session_id": str(session_id or payload.get("session_id") or ""),
        "agent_id": str(agent_id or payload.get("agent_id") or ""),
        "execution_id": str(execution_id or payload.get("execution_id") or ""),
        "status": "active",
        "execution_contract": contract,
        "contract_checks": payload.get("contract_checks") if isinstance(payload.get("contract_checks"), dict) else {},
    }
    record["contract_id"] = _contract_id_from_record(record)
    record_path = Path(repo_root) / CONTRACT_STORE_DIR / f"{record['contract_id']}.json"
    record["path"] = (CONTRACT_STORE_DIR / f"{record['contract_id']}.json").as_posix()
    write_json(record_path, record)

    index_path = Path(repo_root) / CONTRACT_INDEX_PATH
    index = read_json(index_path, {})
    if not isinstance(index, dict):
        index = {}
    rows = [row for row in index.get("contracts", []) if isinstance(row, dict) and row.get("contract_id") != record["contract_id"]]
    rows.append(_contract_ref_from_record(record))
    index.update({"version": CONTRACT_COMPLIANCE_VERSION, "latest_contract_id": record["contract_id"], "contracts": rows[-200:]})
    write_json(index_path, index)
    return _contract_ref_from_record(record)


def _load_contract_record_by_id(repo_root: Path, contract_id: str) -> dict[str, Any]:
    cid = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(contract_id or "").strip())
    if not cid:
        return {}
    record = read_json(Path(repo_root) / CONTRACT_STORE_DIR / f"{cid}.json", {})
    return record if isinstance(record, dict) else {}


def _contract_source_from_record(record: dict[str, Any], task_goal: str = "") -> dict[str, Any]:
    contract = record.get("execution_contract") if isinstance(record.get("execution_contract"), dict) else {}
    if not contract:
        return {}
    contract_goal = str(contract.get("task_goal") or record.get("task_goal") or record.get("request") or "")
    match = _contract_goal_match(task_goal, contract_goal)
    return {
        "execution_contract": contract,
        "contract_checks": record.get("contract_checks") if isinstance(record.get("contract_checks"), dict) else {},
        "generated_at": str(record.get("generated_at") or ""),
        "task_goal": contract_goal,
        "contract_id": str(record.get("contract_id") or ""),
        "session_id": str(record.get("session_id") or ""),
        "execution_id": str(record.get("execution_id") or ""),
        "task_goal_match": bool(match.get("matches")),
        "task_goal_match_level": str(match.get("level") or ""),
        "task_goal_match_score": match.get("score"),
        "selection_reason": str(record.get("selection_reason") or ""),
    }


def load_persisted_resume_contract(
    repo_root: Path,
    *,
    task_goal: str = "",
    contract_id: str = "",
    session_id: str = "",
    execution_id: str = "",
) -> dict[str, Any]:
    if contract_id:
        source = _contract_source_from_record(_load_contract_record_by_id(repo_root, contract_id), task_goal)
        if task_goal and source and not source.get("task_goal_match"):
            return {}
        return source
    index = read_json(Path(repo_root) / CONTRACT_INDEX_PATH, {})
    if not isinstance(index, dict):
        return {}
    rows = [row for row in index.get("contracts", []) if isinstance(row, dict)]
    selected_id = ""
    for key, value in (("execution_id", execution_id), ("session_id", session_id)):
        if not value:
            continue
        for row in reversed(rows):
            if str(row.get(key) or "") == str(value):
                selected_id = str(row.get("contract_id") or "")
                break
        if selected_id:
            break
    if not selected_id:
        selected_id = str(index.get("latest_contract_id") or (rows[-1].get("contract_id") if rows else ""))
    source = _contract_source_from_record(_load_contract_record_by_id(repo_root, selected_id), task_goal)
    if task_goal and source and not source.get("task_goal_match"):
        return {}
    return source


def _command_observed(expected: str, commands: list[str]) -> bool:
    expected_norm = _norm_command(expected)
    if not expected_norm:
        return False
    observed = [_norm_command(command) for command in commands]
    if any(command == expected_norm for command in observed):
        return True
    return any(expected_norm in command for command in observed if command)


def _orientation_warnings(commands: list[str]) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    patterns = [
        ("git status", "git status"),
        ("git diff", "git diff"),
        ("ls", "ls"),
        ("find", "find"),
        ("grep -R", "grep -R"),
        ("rg .", "rg ."),
        ("cat README.md", "cat README.md"),
        ("cat docs/", "cat docs/"),
        ("cat examples/", "cat examples/"),
        ("python - <<", "python - <<"),
        ("python3 - <<", "python3 - <<"),
    ]
    for command in commands:
        norm = _norm_command(command)
        low = norm.lower()
        for label, needle in patterns:
            nlow = needle.lower()
            matched = low == nlow or low.startswith(nlow + " ") or nlow in low
            if label == "ls":
                matched = low == "ls" or low.startswith("ls ")
            if label == "find":
                matched = low == "find" or low.startswith("find ")
            if matched:
                warnings.append(_issue(
                    "orientation_command_order_unknown",
                    "warning",
                    f"{label} observed; order/purpose unknown.",
                    command,
                ))
                break
        if len(warnings) >= 8:
            break
    return warnings


def evaluate_contract_compliance(
    resume_contract: dict[str, Any],
    execution_observation: dict[str, Any],
    *,
    finalize_status: str = "",
) -> dict[str, Any]:
    source = resume_contract if isinstance(resume_contract, dict) else {}
    contract = source.get("execution_contract") if isinstance(source.get("execution_contract"), dict) else {}
    if not contract:
        return _not_evaluated(str(source.get("task_goal") or ""), main_issue="no_resume_contract")

    observation = execution_observation if isinstance(execution_observation, dict) else {}
    files_opened = _clean_string_list(observation.get("files_opened"), limit=40)
    files_edited = _clean_string_list(observation.get("files_edited"), limit=40)
    commands = _clean_string_list(observation.get("commands_executed"), limit=60)
    tests = _clean_string_list(observation.get("tests_executed"), limit=60)
    if not (files_opened or files_edited or commands or tests):
        return _not_evaluated(
            str(contract.get("task_goal") or source.get("task_goal") or ""),
            contract_present=True,
            main_issue="no_execution_observation",
        )

    first_action = contract.get("first_action") if isinstance(contract.get("first_action"), dict) else {}
    first_path = str(first_action.get("path") or "").strip()
    binding = str(first_action.get("binding") or "").strip()
    edit_scope = contract.get("edit_scope") if isinstance(contract.get("edit_scope"), dict) else {}
    primary = _clean_string_list(edit_scope.get("primary"), limit=20)
    secondary = _clean_string_list(edit_scope.get("secondary_if_needed"), limit=20)
    allowed = primary + secondary
    structural = _structural_alignment(_clean_string_list(contract.get("expected_first_files"), limit=3), observation)
    validation_policy = contract.get("validation_policy") if isinstance(contract.get("validation_policy"), dict) else {}
    task_type = str(validation_policy.get("task_type") or "").strip()
    validation_required = bool(validation_policy.get("required", True))
    contract_strength = str(contract.get("contract_strength") or "").strip()
    enforce_first_action = contract_strength != "exploratory" and task_type not in {"analysis", "investigation", "documentation", "qa"}

    violations: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if first_path and enforce_first_action:
        followed_first_action = first_path in files_opened or first_path in files_edited
        if not followed_first_action:
            violations.append(_issue("missing_first_action", "violation", "Expected first action path was not observed.", first_path))
    elif binding == "must_inspect_listed_entry_points_only":
        followed_first_action = bool(files_opened or files_edited) and any(_path_matches(path, allowed) for path in files_opened + files_edited)
        if not followed_first_action:
            warnings.append(_issue("first_action_not_observable", "warning", "No observable listed entry point was opened or edited."))
    else:
        followed_first_action = True

    outside_scope = [path for path in files_edited if allowed and not _path_matches(path, allowed)][:8]
    edited_within_scope = not outside_scope
    if outside_scope:
        violations.append(_issue("edit_outside_scope", "violation", "Edited files outside contract scope.", ", ".join(outside_scope)))

    test_command = contract.get("test_command") if isinstance(contract.get("test_command"), dict) else {}
    expected_test = str(test_command.get("command") or "").strip()
    canonical_test_used = _command_observed(expected_test, commands + tests) if expected_test else True
    if expected_test and not canonical_test_used and validation_required:
        if finalize_status == "success":
            warnings.append(_issue("canonical_test_not_observed", "warning", "Canonical test command was not observed.", expected_test))
        else:
            violations.append(_issue("canonical_test_missing", "violation", "Canonical test command was not observed.", expected_test))

    finalize_used = bool(finalize_status)
    warnings.extend(_orientation_warnings(commands)[: max(0, 8 - len(warnings))])
    violations = violations[:8]
    warnings = warnings[:8]

    score = 1.0
    if first_path and enforce_first_action and not followed_first_action:
        score -= 0.30
    if outside_scope:
        score -= 0.30
    if any(item.get("code") == "canonical_test_missing" for item in violations):
        score -= 0.25
    if any(item.get("code") == "canonical_test_not_observed" for item in warnings):
        score -= 0.10
    orientation_count = sum(1 for item in warnings if item.get("code") == "orientation_command_order_unknown")
    score -= min(0.15, orientation_count * 0.05)
    score = round(min(1.0, max(0.0, score)), 4)

    if violations:
        status = "violated"
    elif warnings or score < 0.95:
        status = "partial"
    else:
        status = "followed"
    main_issue = str((violations[0] if violations else warnings[0]).get("code") if (violations or warnings) else "")
    compact_summary = f"Contract: {status}." if not main_issue else f"Contract: {status} — {_human_issue(main_issue)}."
    if structural["status"] != "not_evaluated":
        compact_summary = compact_summary.rstrip(".") + f". Structural alignment: {structural['status']}."
    if len(compact_summary) > 120:
        compact_summary = compact_summary[:117].rstrip() + "..."

    checks = {
        "followed_first_action": bool(followed_first_action),
        "edited_within_scope": bool(edited_within_scope),
        "canonical_test_used": bool(canonical_test_used),
        "finalize_used": bool(finalize_used),
    }
    if structural["status"] != "not_evaluated":
        checks["structural_alignment"] = structural["status"]

    return {
        "version": CONTRACT_COMPLIANCE_VERSION,
        "contract_present": True,
        "status": status,
        "score": score,
        "task_goal": str(contract.get("task_goal") or source.get("task_goal") or ""),
        "main_issue": main_issue,
        "structural_alignment": structural["status"],
        "checks": checks,
        "structural_entry_points": structural,
        "first_action": {"expected": first_path, "observed": bool(followed_first_action)},
        "edit_scope": {
            "primary": primary,
            "secondary_if_needed": secondary,
            "edited_files": files_edited[:12],
            "outside_scope": outside_scope,
        },
        "test_command": {"expected": expected_test, "observed": bool(canonical_test_used)},
        "violations": violations,
        "warnings": warnings,
        "compact_summary": compact_summary,
    }


def append_contract_compliance(repo_root: Path, row: dict[str, Any]) -> dict[str, Any]:
    path = Path(repo_root) / CONTRACT_COMPLIANCE_LOG_PATH
    compact = dict(row) if isinstance(row, dict) else {}
    compact.setdefault("timestamp", _now_iso())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(compact, ensure_ascii=False, sort_keys=True) + "\n")
    return compact


def load_contract_compliance_history(repo_root: Path, limit: int = 50) -> list[dict[str, Any]]:
    path = Path(repo_root) / CONTRACT_COMPLIANCE_LOG_PATH
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows[-max(0, int(limit or 0)):]


def compact_previous_contract_result(repo_root: Path) -> dict[str, Any]:
    rows = load_contract_compliance_history(repo_root, limit=200)
    evaluated = [row for row in rows if isinstance(row, dict) and row.get("status") != "not_evaluated" and row.get("contract_present") is not False]
    if not evaluated:
        return {"status": "unknown", "score": None, "main_issue": "", "compact_summary": ""}
    latest = evaluated[-1]
    status = str(latest.get("status") or "unknown")
    if status not in _ALLOWED_STATUSES:
        status = "unknown"
    score = latest.get("score") if isinstance(latest.get("score"), (int, float)) else None
    main_issue = str(latest.get("main_issue") or "")
    compact_summary = str(latest.get("compact_summary") or "").strip()
    if not compact_summary and status != "unknown":
        compact_summary = f"Contract: {status}." if not main_issue else f"Contract: {status} — {_human_issue(main_issue)}."
    return {"status": status, "score": score, "main_issue": main_issue, "compact_summary": compact_summary}


def _issue_counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for issue in row.get(key, []) if isinstance(row.get(key), list) else []:
            code = str(issue.get("code") or issue if isinstance(issue, dict) else issue or "").strip()
            if code:
                counts[code] = counts.get(code, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _rate(rows: list[dict[str, Any]], check: str) -> float:
    eligible = [row for row in rows if isinstance(row.get("checks"), dict) and check in row["checks"]]
    if not eligible:
        return 0.0
    return round(sum(1 for row in eligible if row["checks"].get(check) is True) / len(eligible), 4)


def summarize_contract_compliance_history(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid_rows = [row for row in rows if isinstance(row, dict)]
    evaluated = [row for row in valid_rows if row.get("contract_present") is not False and row.get("status") != "not_evaluated"]
    scores = [float(row.get("score")) for row in evaluated if isinstance(row.get("score"), (int, float))]
    latest = compact_previous_contract_result_from_row(evaluated[-1]) if evaluated else {"status": "unknown", "score": None, "main_issue": "", "compact_summary": ""}
    return {
        "evaluated": len(evaluated),
        "not_evaluated": sum(1 for row in valid_rows if row.get("status") == "not_evaluated"),
        "followed": sum(1 for row in valid_rows if row.get("status") == "followed"),
        "partial": sum(1 for row in valid_rows if row.get("status") == "partial"),
        "violated": sum(1 for row in valid_rows if row.get("status") == "violated"),
        "avg_score": round(sum(scores) / len(scores), 4) if scores else None,
        "first_action_follow_rate": _rate(evaluated, "followed_first_action"),
        "edit_scope_follow_rate": _rate(evaluated, "edited_within_scope"),
        "canonical_test_use_rate": _rate(evaluated, "canonical_test_used"),
        "finalize_use_rate": _rate(evaluated, "finalize_used"),
        "top_violations": _issue_counts(valid_rows, "violations"),
        "top_warnings": _issue_counts(valid_rows, "warnings"),
        "latest": latest,
    }


def compact_previous_contract_result_from_row(row: dict[str, Any]) -> dict[str, Any]:
    status = str(row.get("status") or "unknown") if isinstance(row, dict) else "unknown"
    if status not in _ALLOWED_STATUSES:
        status = "unknown"
    score = row.get("score") if isinstance(row.get("score"), (int, float)) else None
    main_issue = str(row.get("main_issue") or "")
    compact_summary = str(row.get("compact_summary") or "").strip()
    if not compact_summary and status != "unknown":
        compact_summary = f"Contract: {status}." if not main_issue else f"Contract: {status} — {_human_issue(main_issue)}."
    return {"status": status, "score": score, "main_issue": main_issue, "compact_summary": compact_summary}
