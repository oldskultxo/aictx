from __future__ import annotations

import fnmatch
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .state import REPO_METRICS_DIR

CONTRACT_COMPLIANCE_VERSION = 1
CONTRACT_COMPLIANCE_LOG_PATH = REPO_METRICS_DIR / "contract_compliance.jsonl"

_ALLOWED_STATUSES = {"followed", "partial", "violated", "not_evaluated"}


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
        "checks": {},
        "violations": [],
        "warnings": [],
        "compact_summary": compact_summary,
    }


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

    violations: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if first_path:
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
    if expected_test and not canonical_test_used:
        if finalize_status == "success":
            warnings.append(_issue("canonical_test_not_observed", "warning", "Canonical test command was not observed.", expected_test))
        else:
            violations.append(_issue("canonical_test_missing", "violation", "Canonical test command was not observed.", expected_test))

    finalize_used = bool(finalize_status)
    warnings.extend(_orientation_warnings(commands)[: max(0, 8 - len(warnings))])
    violations = violations[:8]
    warnings = warnings[:8]

    score = 1.0
    if first_path and not followed_first_action:
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
    if len(compact_summary) > 120:
        compact_summary = compact_summary[:117].rstrip() + "..."

    return {
        "version": CONTRACT_COMPLIANCE_VERSION,
        "contract_present": True,
        "status": status,
        "score": score,
        "task_goal": str(contract.get("task_goal") or source.get("task_goal") or ""),
        "main_issue": main_issue,
        "checks": {
            "followed_first_action": bool(followed_first_action),
            "edited_within_scope": bool(edited_within_scope),
            "canonical_test_used": bool(canonical_test_used),
            "finalize_used": bool(finalize_used),
        },
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
    rows = load_contract_compliance_history(repo_root, limit=1)
    if not rows:
        return {"status": "unknown", "score": None, "main_issue": "", "compact_summary": ""}
    latest = rows[-1]
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
    latest = compact_previous_contract_result_from_row(valid_rows[-1]) if valid_rows else {"status": "unknown", "score": None, "main_issue": "", "compact_summary": ""}
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
