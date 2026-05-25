from __future__ import annotations

from pathlib import Path
from typing import Any

from .continuity import load_continuity_context
from .continuity.quality import build_continuity_quality_report
from .runtime_tasks import resolve_task_type

_GOAL_STOPWORDS = {
    "about",
    "add",
    "bug",
    "change",
    "fix",
    "from",
    "implement",
    "make",
    "para",
    "review",
    "the",
    "with",
}


def _clean_strings(values: Any, *, limit: int = 8) -> list[str]:
    if not isinstance(values, list):
        values = [values] if values else []
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip().replace("\\", "/")
        if not text or text in seen:
            continue
        result.append(text)
        seen.add(text)
        if len(result) >= limit:
            break
    return result


def _path_kind(path: str) -> str:
    text = str(path or "").strip().replace("\\", "/").lower()
    name = text.rsplit("/", 1)[-1]
    if text.startswith("tests/") or "/tests/" in f"/{text}" or name.startswith("test_"):
        return "test"
    if text.startswith("src/") or "/src/" in f"/{text}":
        return "source"
    if text.startswith("docs/") or name in {"readme.md", "quickstart.md"} or name.endswith(".md"):
        return "docs"
    if text.startswith(".github/workflows/"):
        return "ci"
    if name in {"pyproject.toml", "setup.py", "setup.cfg", "tox.ini", "pytest.ini", "ruff.toml"}:
        return "config"
    return "other"


def _file_kind_priority(path: str) -> int:
    order = {"source": 0, "test": 1, "ci": 2, "config": 3, "other": 4, "docs": 5}
    return order.get(_path_kind(path), 9)


def _file_source_priority(source: str) -> int:
    order = {"repo_map": 0, "decision": 1, "failure": 1, "handoff": 1, "semantic_repo": 1, "strategy": 2}
    return order.get(str(source or ""), 3)


def _live_path(repo_root: Path, path: str) -> bool:
    text = str(path or "").strip()
    if not text or text.startswith(".aictx/") or text == ".aictx":
        return False
    candidate = Path(text)
    return candidate.exists() if candidate.is_absolute() else (repo_root / candidate).exists()


def _item_paths(item: dict[str, Any]) -> list[str]:
    paths = _clean_strings(item.get("paths"), limit=6)
    if not paths and item.get("path"):
        paths = _clean_strings([item.get("path")], limit=1)
    return paths


def _goal_terms(goal: str) -> set[str]:
    terms: set[str] = set()
    token = ""
    for char in str(goal or "").lower():
        if char.isalnum() or char in {"_", "-"}:
            token += char
            continue
        if len(token) >= 4 and token not in _GOAL_STOPWORDS:
            terms.add(token)
        token = ""
    if len(token) >= 4 and token not in _GOAL_STOPWORDS:
        terms.add(token)
    return terms


def _item_matches_goal(item: dict[str, Any], path: str, goal_terms: set[str]) -> bool:
    if not goal_terms:
        return True
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    haystack = " ".join(
        _clean_strings(
            [
                path,
                item.get("id"),
                item.get("title"),
                item.get("decision"),
                *list(item.get("paths", []) if isinstance(item.get("paths"), list) else []),
                *list(item.get("related_paths", []) if isinstance(item.get("related_paths"), list) else []),
                *list(item.get("reasons", []) if isinstance(item.get("reasons"), list) else []),
                metadata.get("subsystem"),
                item.get("subsystem"),
                metadata.get("symbol"),
                metadata.get("symbol_kind"),
            ],
            limit=24,
        )
    ).lower()
    return any(term in haystack for term in goal_terms)


def _is_noisy_background_file(item: dict[str, Any], path: str, goal_terms: set[str]) -> bool:
    if str(item.get("kind") or "") != "decision":
        return False
    if _path_kind(path) not in {"ci", "config"}:
        return False
    return not _item_matches_goal(item, path, goal_terms)


def _ranked_files(repo_root: Path, ranked_items: list[dict[str, Any]], *, goal: str = "", limit: int = 8) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    goal_terms = _goal_terms(goal)
    for rank, item in enumerate(ranked_items):
        if not isinstance(item, dict):
            continue
        reasons = _clean_strings(item.get("reasons"), limit=4)
        for path in _item_paths(item):
            if path in seen or _is_noisy_background_file(item, path, goal_terms) or not _live_path(repo_root, path):
                continue
            seen.add(path)
            rows.append({
                "path": path,
                "kind": _path_kind(path),
                "score": int(item.get("score", 0) or 0),
                "source": str(item.get("kind") or ""),
                "why_loaded": "; ".join(reasons) or "ranked continuity item",
                "rank": rank + 1,
            })
    rows.sort(key=lambda row: (
        _file_source_priority(str(row.get("source") or "")),
        _file_kind_priority(str(row.get("path") or "")),
        -int(row.get("score", 0) or 0),
        int(row.get("rank", 0) or 0),
        str(row.get("path") or ""),
    ))
    return rows[:limit]


def _repo_map_entrypoints(ranked_items: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in ranked_items:
        if not isinstance(item, dict) or str(item.get("kind") or "") != "repo_map":
            continue
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        path = _clean_strings(item.get("paths"), limit=1)
        if not path and item.get("path"):
            path = [str(item.get("path"))]
        rows.append({
            "path": path[0] if path else "",
            "title": str(item.get("title") or ""),
            "score": int(item.get("score", 0) or 0),
            "reasons": _clean_strings(item.get("reasons"), limit=4),
            "symbol": str(metadata.get("symbol") or ""),
            "symbol_kind": str(metadata.get("symbol_kind") or ""),
            "line": int(metadata.get("line") or 0),
        })
        if len(rows) >= limit:
            break
    return rows


def _compact_work_state(context: dict[str, Any]) -> dict[str, Any]:
    active = context.get("active_work_state") if isinstance(context.get("active_work_state"), dict) else {}
    recent = context.get("recent_work_state") if isinstance(context.get("recent_work_state"), dict) else {}
    selected = active or recent
    if not selected:
        return {"active": False}
    return {
        "active": bool(active),
        "task_id": str(selected.get("task_id") or ""),
        "status": str(selected.get("status") or ("active" if active else "")),
        "goal": str(selected.get("goal") or ""),
        "current_hypothesis": str(selected.get("current_hypothesis") or ""),
        "next_action": str(selected.get("next_action") or ""),
        "recommended_commands": _clean_strings(selected.get("recommended_commands"), limit=4),
    }


def _compact_handoff(context: dict[str, Any]) -> list[dict[str, Any]]:
    handoff = context.get("handoff") if isinstance(context.get("handoff"), dict) else {}
    if not handoff:
        return []
    return [{
        "summary": str(handoff.get("summary") or ""),
        "next_steps": _clean_strings(handoff.get("next_steps"), limit=3),
        "recommended_starting_points": _clean_strings(handoff.get("recommended_starting_points"), limit=5),
        "why_loaded": "latest relevant handoff",
    }]


def _compact_decisions(context: dict[str, Any], *, goal: str = "", limit: int = 5) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    goal_terms = _goal_terms(goal)
    for item in context.get("decisions", []) if isinstance(context.get("decisions"), list) else []:
        if not isinstance(item, dict):
            continue
        paths = _clean_strings(item.get("related_paths"), limit=5)
        if paths and all(_path_kind(path) in {"ci", "config"} for path in paths) and not _item_matches_goal(item, paths[0], goal_terms):
            continue
        rows.append({
            "decision": str(item.get("decision") or ""),
            "subsystem": str(item.get("subsystem") or ""),
            "related_paths": paths,
            "why_loaded": "recent decision memory",
        })
        if len(rows) >= limit:
            break
    return rows


def _compact_failures(context: dict[str, Any], *, limit: int = 5) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in context.get("failures", []) if isinstance(context.get("failures"), list) else []:
        if not isinstance(item, dict):
            continue
        rows.append({
            "summary": str(item.get("error_text") or item.get("signature") or item.get("failure_signature") or ""),
            "related_paths": _clean_strings(list(item.get("related_paths", []) or []) + list(item.get("files_involved", []) or []), limit=5),
            "status": str(item.get("status") or ""),
            "why_loaded": "matched failure memory",
        })
        if len(rows) >= limit:
            break
    return rows


def _relevant_areas(files: list[dict[str, Any]], context: dict[str, Any]) -> list[dict[str, Any]]:
    areas: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in files:
        path = str(row.get("path") or "")
        area = path.split("/", 2)[0] if path else ""
        if area and area not in seen:
            seen.add(area)
            areas.append({"area": area, "why_loaded": f"relevant file: {path}"})
    semantic = context.get("semantic_repo") if isinstance(context.get("semantic_repo"), dict) else {}
    for subsystem in semantic.get("subsystems", []) if isinstance(semantic.get("subsystems"), list) else []:
        if not isinstance(subsystem, dict):
            continue
        name = str(subsystem.get("name") or "").strip()
        if name and name not in seen:
            seen.add(name)
            areas.append({"area": name, "why_loaded": "semantic repo match"})
    return areas[:6]


def _staleness_warnings(quality: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    for issue in quality.get("issues", []) if isinstance(quality.get("issues"), list) else []:
        if not isinstance(issue, dict):
            continue
        if str(issue.get("severity") or "") in {"warning", "error"}:
            warnings.append({
                "code": str(issue.get("code") or ""),
                "severity": str(issue.get("severity") or ""),
                "summary": str(issue.get("summary") or ""),
                "recommendation": str(issue.get("recommendation") or ""),
                "related_paths": _clean_strings(issue.get("related_paths"), limit=4),
            })
    return warnings[:8]


def _validation_expectations(context: dict[str, Any], task_type: str) -> list[str]:
    brief = context.get("continuity_brief") if isinstance(context.get("continuity_brief"), dict) else {}
    tests = _clean_strings(brief.get("recommended_tests"), limit=4)
    commands = _clean_strings(brief.get("recommended_commands"), limit=4)
    if tests:
        return tests
    if commands:
        return commands
    if task_type in {"bug_fixing", "feature_work", "refactoring", "testing"}:
        return ["Run the focused pytest or validation command for the files touched by this task."]
    return []


def _suggested_first_action(files: list[dict[str, Any]], context: dict[str, Any]) -> str:
    work_state = _compact_work_state(context)
    next_action = str(work_state.get("next_action") or "").strip()
    if next_action:
        return next_action
    top_paths = [str(row.get("path") or "") for row in files[:2] if str(row.get("path") or "").strip()]
    if top_paths:
        return "Open " + " and ".join(top_paths) + " before changing runtime behavior."
    return "Inspect the task-relevant source and tests before making changes."


def build_task_context_pack(repo_root: Path, goal: str, *, task_type: str = "") -> dict[str, Any]:
    repo_root = Path(repo_root).expanduser().resolve()
    normalized_goal = " ".join(str(goal or "").strip().split())
    resolved = resolve_task_type(normalized_goal, explicit_task_type=task_type or None, touched_files=[])
    resolved_task_type = str(resolved.get("task_type") or task_type or "unknown")
    context = load_continuity_context(
        repo_root,
        task_type=resolved_task_type,
        request_text=normalized_goal,
        files=[],
        request_sensitive_banner=False,
    )
    ranked_items = context.get("ranked_items") if isinstance(context.get("ranked_items"), list) else []
    relevant_files = _ranked_files(repo_root, [item for item in ranked_items if isinstance(item, dict)], goal=normalized_goal, limit=8)
    quality = build_continuity_quality_report(repo_root, request_text=normalized_goal, task_type=resolved_task_type, context=context)
    validation = _validation_expectations(context, resolved_task_type)
    pack = {
        "schema_version": "1.0",
        "mode": "task_context_pack",
        "repo": repo_root.as_posix(),
        "goal": {
            "raw": str(goal or ""),
            "normalized": normalized_goal,
        },
        "task_type": resolved_task_type,
        "task_type_confidence": float(resolved.get("confidence", 0.0) or 0.0),
        "task_type_resolution": resolved,
        "relevant_files": relevant_files,
        "relevant_areas": _relevant_areas(relevant_files, context),
        "repo_map_entrypoints": _repo_map_entrypoints([item for item in ranked_items if isinstance(item, dict)], limit=5),
        "work_state": _compact_work_state(context),
        "decisions": _compact_decisions(context, goal=normalized_goal),
        "handoffs": _compact_handoff(context),
        "failures": _compact_failures(context),
        "execution_contract": {
            "mode": "focused_context_only",
            "task_goal": normalized_goal,
            "first_action": {"type": "inspect", "instruction": "Follow suggested_first_action before editing."},
            "validation_expectations": validation,
            "read_only_pack": True,
        },
        "validation_expectations": validation,
        "suggested_first_action": _suggested_first_action(relevant_files, context),
        "continuity_quality": {
            "score": quality.get("score"),
            "status": quality.get("status"),
            "advisory_only": quality.get("advisory_only"),
            "summary": quality.get("summary", {}),
        },
        "staleness_warnings": _staleness_warnings(quality),
        "why_loaded": context.get("why_loaded", {}) if isinstance(context.get("why_loaded"), dict) else {},
        "warnings": _clean_strings(context.get("warnings"), limit=8),
    }
    if not pack["repo_map_entrypoints"]:
        pack["warnings"].append("RepoMap did not return task-specific entrypoints; pack built from available continuity only.")
    return pack


def render_task_context_pack(pack: dict[str, Any]) -> str:
    goal = pack.get("goal") if isinstance(pack.get("goal"), dict) else {}
    lines = ["Task Context Pack", "", "Goal:", f"- {goal.get('normalized') or ''}", "", "Task type:", f"- {pack.get('task_type') or 'unknown'} ({pack.get('task_type_confidence')})"]
    files = pack.get("relevant_files") if isinstance(pack.get("relevant_files"), list) else []
    if files:
        lines.extend(["", "Relevant files:"])
        lines.extend([f"- {item.get('path')} — {item.get('why_loaded')}" for item in files if isinstance(item, dict)])
    decisions = pack.get("decisions") if isinstance(pack.get("decisions"), list) else []
    if decisions:
        lines.extend(["", "Relevant decisions:"])
        lines.extend([f"- {item.get('decision')}" for item in decisions if isinstance(item, dict) and item.get("decision")])
    failures = pack.get("failures") if isinstance(pack.get("failures"), list) else []
    if failures:
        lines.extend(["", "Known failures:"])
        lines.extend([f"- {item.get('summary')}" for item in failures if isinstance(item, dict) and item.get("summary")])
    validation = _clean_strings(pack.get("validation_expectations"), limit=5)
    if validation:
        lines.extend(["", "Validation contract:"])
        lines.extend([f"- {item}" for item in validation])
    stale = pack.get("staleness_warnings") if isinstance(pack.get("staleness_warnings"), list) else []
    if stale:
        lines.extend(["", "Staleness warnings:"])
        lines.extend([f"- {item.get('summary') or item.get('code')}" for item in stale if isinstance(item, dict)])
    warnings = _clean_strings(pack.get("warnings"), limit=5)
    if warnings:
        lines.extend(["", "Warnings:"])
        lines.extend([f"- {item}" for item in warnings])
    first = str(pack.get("suggested_first_action") or "").strip()
    if first:
        lines.extend(["", "Suggested first action:", f"- {first}"])
    return "\n".join(lines).rstrip() + "\n"
