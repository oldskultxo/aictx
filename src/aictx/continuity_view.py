from __future__ import annotations

import base64
import json
import re
import subprocess
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .area_memory import load_area_memory
from .contract_compliance import load_persisted_resume_contract
from .continuity import LAST_EXECUTION_SUMMARY_PATH, load_handoff_history
from .failures import load_failures
from .portability import detect_portable_continuity_from_gitignore, load_portability_state
from .repo_map.config import is_repomap_enabled, load_repomap_index
from .state import REPO_METRICS_DIR, read_jsonl
from .strategy_memory import load_strategies, strategy_reuse_confidence
from .work_state import compact_work_state_for_prepare, load_active_work_state_checked, load_recent_inactive_work_state

CONTINUITY_REPORTS_DIR = Path(".aictx") / "reports"
CONTINUITY_VIEW_PATH = CONTINUITY_REPORTS_DIR / "continuity-view.md"
CONTINUITY_MAP_PATH = CONTINUITY_REPORTS_DIR / "continuity-map.mmd"
EXECUTION_FEEDBACK_PATH = REPO_METRICS_DIR / "execution_feedback.jsonl"

_GROUP_ORDER = (
    "work_state",
    "execution_contract",
    "execution_summaries",
    "handoffs",
    "failures",
    "strategies",
    "area_memory",
    "repomap_hints",
    "portable_continuity",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_git(repo_root: Path, *args: str) -> str:
    try:
        result = subprocess.run(["git", *args], cwd=repo_root, check=False, capture_output=True, text=True, timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.rstrip("\n")


def _repository_model(repo_root: Path) -> dict[str, Any]:
    branch = _run_git(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
    commit = _run_git(repo_root, "rev-parse", "--short", "HEAD")
    status_lines = _run_git(repo_root, "status", "--porcelain").splitlines() if branch or commit else []
    changed_files: list[str] = []
    for line in status_lines:
        path = line[3:].strip() if len(line) > 3 else line.strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        if path:
            changed_files.append(path)
    return {
        "root": repo_root.as_posix(),
        "name": repo_root.name,
        "branch": branch or "unknown",
        "commit": commit or "unknown",
        "dirty": bool(status_lines),
        "changed_files": _clean_list(changed_files, limit=8),
        "changed_count": len(changed_files),
    }


def _clean_text(value: Any, *, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _clean_list(values: Any, *, limit: int = 5) -> list[str]:
    if not isinstance(values, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean_text(value, limit=180)
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def _sort_key_recent(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("updated_at") or row.get("timestamp") or row.get("recorded_at") or row.get("generated_at") or ""), str(row.get("id") or row.get("task_id") or row.get("failure_id") or row.get("execution_id") or ""))


def _recent_value(row: dict[str, Any]) -> str:
    return str(row.get("updated_at") or row.get("timestamp") or row.get("recorded_at") or row.get("generated_at") or "")


def _work_state_model(repo_root: Path) -> dict[str, Any]:
    checked = load_active_work_state_checked(repo_root)
    active = checked.get("active_work_state", {}) if isinstance(checked, dict) else {}
    source = "active"
    if not active:
        active = load_recent_inactive_work_state(repo_root, statuses={"blocked", "paused"})
        source = "recent"
    compact = compact_work_state_for_prepare(active) if isinstance(active, dict) else {}
    if not compact:
        return {"exists": False, "source": "none"}
    return {
        "exists": True,
        "source": source,
        "task_id": _clean_text(compact.get("task_id"), limit=96),
        "status": _clean_text(compact.get("status"), limit=40),
        "title": _clean_text(compact.get("goal") or compact.get("task_id"), limit=120),
        "next_action": _clean_text(compact.get("next_action"), limit=180),
        "risk": _clean_text((_clean_list(compact.get("risks"), limit=1) or [""])[0], limit=180),
        "active_files": _clean_list(compact.get("active_files"), limit=5),
        "verified": _clean_list(compact.get("verified"), limit=3),
        "unverified": _clean_list(compact.get("unverified"), limit=3),
        "recommended_commands": _clean_list(compact.get("recommended_commands"), limit=3),
    }


def _handoff_model(repo_root: Path) -> tuple[list[dict[str, Any]], int]:
    rows = [row for row in load_handoff_history(repo_root, limit=50) if isinstance(row, dict)]

    def is_open(row: dict[str, Any]) -> bool:
        status = str(row.get("status") or "").strip().lower()
        return status in {"open", "active", "blocked", "paused"} or any(row.get(key) for key in ("next_steps", "open_items", "blocked", "risks"))

    rows.sort(key=lambda row: str(row.get("id") or row.get("source_execution_id") or row.get("summary") or ""))
    rows.sort(key=_recent_value, reverse=True)
    rows.sort(key=lambda row: 0 if is_open(row) else 1)
    selected = rows[:3]
    items = []
    for index, row in enumerate(selected, start=1):
        items.append(
            {
                "id": _clean_text(row.get("id") or row.get("source_execution_id") or f"handoff-{index}", limit=80),
                "title": _clean_text(row.get("summary") or row.get("task") or f"Handoff {index}", limit=120),
                "status": _clean_text(row.get("status") or ("open" if is_open(row) else "recent"), limit=40),
                "next_steps": _clean_list(row.get("next_steps"), limit=3),
                "open_items": _clean_list(row.get("open_items"), limit=3),
                "updated_at": _clean_text(row.get("updated_at") or row.get("timestamp"), limit=40),
            }
        )
    return items, max(0, len(rows) - len(items))


def _failure_model(repo_root: Path) -> tuple[list[dict[str, Any]], int]:
    rows = [row for row in load_failures(repo_root) if isinstance(row, dict)]

    def state_rank(row: dict[str, Any]) -> int:
        status = str(row.get("status") or "open").strip().lower()
        return 0 if status in {"open", "active", "unresolved"} else 1

    severity_order = {"critical": 0, "error": 1, "warning": 2, "info": 3}
    rows.sort(key=lambda row: str(row.get("failure_id") or row.get("signature") or ""))
    rows.sort(key=_recent_value, reverse=True)
    rows.sort(key=lambda row: (state_rank(row), severity_order.get(str(row.get("severity") or "error").lower(), 2)))
    selected = rows[:3]
    items = []
    for index, row in enumerate(selected, start=1):
        items.append(
            {
                "id": _clean_text(row.get("failure_id") or row.get("signature") or f"failure-{index}", limit=96),
                "title": _clean_text(row.get("error_text") or row.get("signature") or row.get("failure_signature") or f"Failure {index}", limit=120),
                "status": _clean_text(row.get("status") or "open", limit=40),
                "severity": _clean_text(row.get("severity") or row.get("toolchain") or "error", limit=40),
                "area_id": _clean_text(row.get("area_id") or row.get("subsystem"), limit=80),
                "related_paths": _clean_list(row.get("related_paths") or row.get("files_involved"), limit=3),
            }
        )
    return items, max(0, len(rows) - len(items))


def _strategy_model(repo_root: Path) -> tuple[list[dict[str, Any]], int]:
    rows = [row for row in load_strategies(repo_root) if isinstance(row, dict) and not bool(row.get("is_failure")) and bool(row.get("success", True))]
    rows.sort(key=lambda row: str(row.get("id") or row.get("strategy_id") or row.get("summary") or ""))
    rows.sort(key=_recent_value, reverse=True)
    rows.sort(key=lambda row: {"high": 0, "medium": 1, "low": 2}.get(strategy_reuse_confidence(row), 2))
    selected = rows[:3]
    items = []
    for index, row in enumerate(selected, start=1):
        items.append(
            {
                "id": _clean_text(row.get("id") or row.get("strategy_id") or f"strategy-{index}", limit=96),
                "title": _clean_text(row.get("summary") or row.get("task_type") or f"Strategy {index}", limit=120),
                "reuse_confidence": strategy_reuse_confidence(row),
                "task_type": _clean_text(row.get("task_type") or "unknown", limit=60),
                "entry_points": _clean_list(row.get("entry_points") or row.get("files_used"), limit=3),
            }
        )
    return items, max(0, len(rows) - len(items))


def _area_memory_model(repo_root: Path) -> tuple[list[dict[str, Any]], int]:
    memory = load_area_memory(repo_root)
    areas = memory.get("areas") if isinstance(memory.get("areas"), dict) else {}
    rows = [dict(value, area_id=str(key)) for key, value in areas.items() if isinstance(value, dict)]
    rows.sort(key=lambda row: (-(int(row.get("failure_count", 0) or 0) + int(row.get("strategy_count", 0) or 0) + int(row.get("executions", 0) or 0)), str(row.get("area_id") or "")))
    selected = rows[:5]
    items = []
    for row in selected:
        items.append(
            {
                "area_id": _clean_text(row.get("area_id") or "unknown", limit=96),
                "executions": int(row.get("executions", 0) or 0),
                "strategy_count": int(row.get("strategy_count", 0) or 0),
                "failure_count": int(row.get("failure_count", 0) or 0),
                "related_files": _clean_list(row.get("related_files"), limit=3),
                "related_tests": _clean_list(row.get("related_tests"), limit=2),
            }
        )
    return items, max(0, len(rows) - len(items))


def _contract_model(repo_root: Path) -> dict[str, Any]:
    source = load_persisted_resume_contract(repo_root)
    contract = source.get("execution_contract") if isinstance(source.get("execution_contract"), dict) else {}
    if not contract:
        return {"exists": False}
    first_action = contract.get("first_action") if isinstance(contract.get("first_action"), dict) else {}
    test_command = contract.get("test_command") if isinstance(contract.get("test_command"), dict) else {}
    return {
        "exists": True,
        "id": _clean_text(source.get("contract_id"), limit=96),
        "title": _clean_text(contract.get("task_goal") or source.get("task_goal") or "Execution Contract", limit=120),
        "strength": _clean_text(contract.get("contract_strength"), limit=40),
        "first_action": _clean_text(first_action.get("path") or first_action.get("type"), limit=120),
        "test_command": _clean_text(test_command.get("command"), limit=180),
        "generated_at": _clean_text(source.get("generated_at"), limit=40),
    }


def _execution_summary_model(repo_root: Path) -> tuple[list[dict[str, Any]], int]:
    rows = [row for row in read_jsonl(repo_root / EXECUTION_FEEDBACK_PATH) if isinstance(row, dict)]
    rows.sort(key=_sort_key_recent, reverse=True)
    selected = rows[:3]
    items = []
    for index, row in enumerate(selected, start=1):
        summary = row.get("agent_summary") if isinstance(row.get("agent_summary"), dict) else {}
        handoff = summary.get("handoff_payload") if isinstance(summary.get("handoff_payload"), dict) else {}
        title = handoff.get("summary") or summary.get("result_summary") or row.get("execution_id") or f"Execution Summary {index}"
        items.append(
            {
                "id": _clean_text(row.get("execution_id") or row.get("task_id") or f"summary-{index}", limit=96),
                "title": _clean_text(title, limit=120),
                "timestamp": _clean_text(row.get("timestamp"), limit=40),
            }
        )
    if not items and (repo_root / LAST_EXECUTION_SUMMARY_PATH).exists():
        items.append({"id": "last-execution-summary", "title": "Last execution summary", "timestamp": ""})
    return items, max(0, len(rows) - len(items))


def _repomap_model(repo_root: Path, seed_paths: list[str] | None = None) -> tuple[list[dict[str, Any]], str, int]:
    if not is_repomap_enabled(repo_root):
        return [], "disabled", 0
    index = load_repomap_index(repo_root)
    files = index.get("files") if isinstance(index.get("files"), list) else []
    rows = [row for row in files if isinstance(row, dict) and str(row.get("path") or "").strip()]
    seeds = [str(path or "").strip().replace("\\", "/") for path in seed_paths or [] if str(path or "").strip()]

    def score(row: dict[str, Any]) -> tuple[int, str]:
        path = str(row.get("path") or "").strip().replace("\\", "/")
        if path in seeds:
            return (0, path)
        if any(path.startswith(seed.rstrip("/") + "/") or seed.startswith(path.rstrip("/") + "/") for seed in seeds):
            return (1, path)
        if path.startswith(("src/", "tests/")):
            return (2, path)
        if path.startswith("docs/"):
            return (3, path)
        if path.startswith(".github/"):
            return (6, path)
        return (4, path)

    rows.sort(key=score)
    selected = rows[:5]
    items = []
    for row in selected:
        symbols = row.get("symbols") if isinstance(row.get("symbols"), list) else []
        items.append(
            {
                "path": _clean_text(row.get("path"), limit=140),
                "language": _clean_text(row.get("language"), limit=40),
                "symbols": _clean_list([symbol.get("name") for symbol in symbols if isinstance(symbol, dict)], limit=3),
            }
        )
    return items, "available" if rows else "unavailable", max(0, len(rows) - len(items))


def _portable_model(repo_root: Path) -> dict[str, str]:
    state = load_portability_state(repo_root)
    if isinstance(state, dict) and state:
        enabled = bool(state.get("enabled"))
        return {"status": "enabled" if enabled else "local-only", "mode": str(state.get("mode") or ("portable-continuity" if enabled else "local-only"))}
    detected = detect_portable_continuity_from_gitignore(repo_root)
    if detected is True:
        return {"status": "enabled", "mode": "portable-continuity"}
    if detected is False:
        return {"status": "local-only", "mode": "local-only"}
    return {"status": "not configured", "mode": "not configured"}


def _summary_counts(model: dict[str, Any]) -> dict[str, Any]:
    work = model.get("work_state") if isinstance(model.get("work_state"), dict) else {}
    contract = model.get("execution_contract") if isinstance(model.get("execution_contract"), dict) else {}
    portable = model.get("portable_continuity") if isinstance(model.get("portable_continuity"), dict) else {}
    repository = model.get("repository") if isinstance(model.get("repository"), dict) else {}
    return {
        "active_work_state": bool(work.get("exists")) and str(work.get("source") or "") == "active",
        "changed_files": int(repository.get("changed_count") or 0),
        "open_handoffs": len(model.get("open_handoffs", [])),
        "relevant_failures": len(model.get("relevant_failures", [])),
        "strategies": len(model.get("strategies", [])),
        "area_memory": len(model.get("area_memory", [])),
        "execution_contracts": 1 if contract.get("exists") else 0,
        "execution_summaries": len(model.get("execution_summaries", [])),
        "repomap_hints": len(model.get("repomap_hints", [])),
        "portable_continuity": str(portable.get("status") or "not configured"),
    }


def build_continuity_view_model(repo_root: Path) -> dict[str, Any]:
    repo_root = Path(repo_root).expanduser().resolve()
    repository = _repository_model(repo_root)
    work_state = _work_state_model(repo_root)
    handoffs, hidden_handoffs = _handoff_model(repo_root)
    failures, hidden_failures = _failure_model(repo_root)
    strategies, hidden_strategies = _strategy_model(repo_root)
    area_memory, hidden_areas = _area_memory_model(repo_root)
    contract = _contract_model(repo_root)
    summaries, hidden_summaries = _execution_summary_model(repo_root)
    seed_paths: list[str] = []
    seed_paths.extend(list(repository.get("changed_files") or []))
    seed_paths.extend(list(work_state.get("active_files") or []))
    if contract.get("first_action"):
        seed_paths.append(str(contract.get("first_action") or ""))
    for strategy in strategies:
        seed_paths.extend(list(strategy.get("entry_points") or []))
    repomap_hints, repomap_status, hidden_repomap = _repomap_model(repo_root, seed_paths=seed_paths)
    model: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at": _now_iso(),
        "repository": repository,
        "work_state": work_state,
        "open_handoffs": handoffs,
        "relevant_failures": failures,
        "strategies": strategies,
        "area_memory": area_memory,
        "execution_contract": contract,
        "execution_summaries": summaries,
        "repomap_hints": repomap_hints,
        "repomap_status": repomap_status,
        "portable_continuity": _portable_model(repo_root),
        "hidden_counts": {
            "handoffs": hidden_handoffs,
            "failures": hidden_failures,
            "strategies": hidden_strategies,
            "area_memory": hidden_areas,
            "execution_summaries": hidden_summaries,
            "repomap_hints": hidden_repomap,
        },
    }
    model["summary"] = _summary_counts(model)
    return model


def _mermaid_label(value: Any, *, limit: int = 72) -> str:
    text = _clean_text(value, limit=limit).replace('"', "'")
    text = re.sub(r"[\[\]{}<>`]", "", text)
    return text or "unknown"


def _mermaid_lines(*values: Any, limit: int = 72) -> str:
    parts: list[str] = []
    for value in values:
        text = _mermaid_label(value, limit=limit)
        if text and text != "unknown":
            parts.append(text)
    return "<br/>".join(parts) or "unknown"


def _node(node_id: str, label: str, *, limit: int = 72) -> str:
    return f'  {node_id}["{_mermaid_label(label, limit=limit)}"]'


def _rich_node(node_id: str, *lines: Any, limit: int = 120) -> str:
    return f'  {node_id}["{_mermaid_lines(*lines, limit=limit)}"]'


def _edge(left: str, right: str) -> str:
    return f"  {left} --> {right}"


def _has_operational_signal(model: dict[str, Any]) -> bool:
    contract = model.get("execution_contract") if isinstance(model.get("execution_contract"), dict) else {}
    work = model.get("work_state") if isinstance(model.get("work_state"), dict) else {}
    return any(
        [
            bool(work.get("exists")),
            bool(contract.get("exists")),
            bool(model.get("execution_summaries")),
            bool(model.get("open_handoffs")),
            bool(model.get("relevant_failures")),
            bool(model.get("strategies")),
            bool(model.get("area_memory")),
            bool(model.get("repomap_hints")),
        ]
    )


def render_continuity_mermaid(model: dict[str, Any]) -> str:
    repo = model.get("repository") if isinstance(model.get("repository"), dict) else {}
    repo_label = f"Repo: {repo.get('name') or 'Repository'} | {repo.get('branch') or 'unknown'} @ {repo.get('commit') or 'unknown'}"
    if repo.get("dirty"):
        repo_label += f" | {repo.get('changed_count') or len(repo.get('changed_files') or [])} changed"
    lines = ["flowchart TD", _node("Repo", repo_label)]
    if not _has_operational_signal(model):
        lines.extend([_node("Empty", "No active continuity signals found"), _edge("Repo", "Empty")])
        return "\n".join(lines).rstrip() + "\n"

    nodes: list[str] = []
    edges: list[str] = []
    work = model.get("work_state") if isinstance(model.get("work_state"), dict) else {}
    contract = model.get("execution_contract") if isinstance(model.get("execution_contract"), dict) else {}
    changed_files = list(repo.get("changed_files") or [])[:5]
    if changed_files:
        nodes.append(_node("CH", "Working Tree Changes"))
        edges.append(_edge("Repo", "CH"))
        for index, path in enumerate(changed_files, start=1):
            node_id = f"CH{index}"
            nodes.append(_node(node_id, str(path)))
            edges.append(_edge("CH", node_id))
    if work.get("exists"):
        status = str(work.get("status") or work.get("source") or "").strip().lower()
        if status == "blocked":
            work_prefix = "Blocked Work"
        elif status == "paused" or str(work.get("source") or "") == "recent":
            work_prefix = "Paused Work"
        else:
            work_prefix = "Active Work"
        nodes.append(_node("WS", f"{work_prefix}: {work.get('title') or work.get('task_id') or 'active'}"))
        edges.append(_edge("Repo", "WS"))
        if work.get("next_action"):
            nodes.append(_node("NX", f"Next Action: {work.get('next_action')}"))
            edges.append(_edge("WS", "NX"))
        active_files = list(work.get("active_files") or [])[:4]
        if active_files:
            nodes.append(_node("WF", "Work State Files"))
            edges.append(_edge("WS", "WF"))
            for index, path in enumerate(active_files, start=1):
                node_id = f"WF{index}"
                nodes.append(_node(node_id, str(path)))
                edges.append(_edge("WF", node_id))
        commands = list(work.get("recommended_commands") or [])[:2]
        if commands:
            nodes.append(_node("VC", "Recommended Validation"))
            edges.append(_edge("WS", "VC"))
            for index, command in enumerate(commands, start=1):
                node_id = f"VC{index}"
                nodes.append(_node(node_id, str(command)))
                edges.append(_edge("VC", node_id))
    if contract.get("exists"):
        nodes.append(_node("EC", f"Execution Contract: {contract.get('title') or contract.get('id') or 'latest'}"))
        edges.append(_edge("WS" if work.get("exists") else "Repo", "EC"))
        if contract.get("first_action"):
            nodes.append(_node("ECA", f"First Action: {contract.get('first_action')}"))
            edges.append(_edge("EC", "ECA"))
        if contract.get("test_command"):
            nodes.append(_node("ECT", f"Contract Test: {contract.get('test_command')}"))
            edges.append(_edge("EC", "ECT"))

    execution_summaries = list(model.get("execution_summaries") or [])[:3]
    if execution_summaries:
        nodes.append(_node("ES", "Recent Execution Summaries"))
        edges.append(_edge("EC" if contract.get("exists") else "Repo", "ES"))
    for index, item in enumerate(execution_summaries, start=1):
        node_id = f"ES{index}"
        nodes.append(_node(node_id, f"{item.get('title') or item.get('id')}"))
        edges.append(_edge("ES", node_id))

    handoffs = list(model.get("open_handoffs") or [])[:3]
    if handoffs:
        nodes.append(_node("HF", "Open Handoffs"))
        edges.append(_edge("Repo", "HF"))
        if work.get("exists"):
            edges.append(_edge("HF", "WS"))
    for index, item in enumerate(handoffs, start=1):
        node_id = f"HF{index}"
        next_steps = list(item.get("next_steps") or [])[:2]
        open_items = list(item.get("open_items") or [])[:2]
        detail_lines = [f"{item.get('status') or 'open'}: {item.get('title') or item.get('id')}"]
        detail_lines.extend(f"next: {step}" for step in next_steps)
        detail_lines.extend(f"open: {open_item}" for open_item in open_items)
        nodes.append(_rich_node(node_id, *detail_lines, limit=120))
        edges.append(_edge("HF", node_id))

    failures = list(model.get("relevant_failures") or [])[:3]
    if failures:
        nodes.append(_node("FM", "Relevant Failure Memory"))
        edges.append(_edge("Repo", "FM"))
        if contract.get("exists"):
            edges.append(_edge("FM", "EC"))
    for index, item in enumerate(failures, start=1):
        node_id = f"FM{index}"
        related_paths = list(item.get("related_paths") or [])[:2]
        detail_lines = [
            f"{item.get('status') or 'open'} {item.get('severity') or 'error'}: {item.get('title') or item.get('id')}",
        ]
        if item.get("area_id"):
            detail_lines.append(f"area: {item.get('area_id')}")
        detail_lines.extend(f"path: {path}" for path in related_paths)
        nodes.append(_rich_node(node_id, *detail_lines, limit=120))
        edges.append(_edge("FM", node_id))

    strategies = list(model.get("strategies") or [])[:3]
    if strategies:
        nodes.append(_node("SM", "Relevant Strategy Memory"))
        edges.append(_edge("Repo", "SM"))
        if work.get("exists"):
            edges.append(_edge("SM", "WS"))
    for index, item in enumerate(strategies, start=1):
        node_id = f"SM{index}"
        nodes.append(_node(node_id, f"{item.get('title') or item.get('task_type')}"))
        edges.append(_edge("SM", node_id))

    areas = list(model.get("area_memory") or [])[:5]
    if areas:
        nodes.append(_node("AM", "Area Memory Signals"))
        edges.append(_edge("Repo", "AM"))
    for index, item in enumerate(areas, start=1):
        node_id = f"AM{index}"
        nodes.append(_node(node_id, f"{item.get('area_id')}"))
        edges.append(_edge("AM", node_id))

    repomap = list(model.get("repomap_hints") or [])[:5]
    if repomap:
        nodes.append(_node("RM", "RepoMap Hints"))
        edges.append(_edge("Repo", "RM"))
        if work.get("exists"):
            edges.append(_edge("RM", "WS"))
    for index, item in enumerate(repomap, start=1):
        node_id = f"RM{index}"
        nodes.append(_node(node_id, f"{item.get('path')}"))
        edges.append(_edge("RM", node_id))
    if areas and repomap:
        edges.append(_edge("AM", "RM"))

    portable = model.get("portable_continuity") if isinstance(model.get("portable_continuity"), dict) else {}
    nodes.append(_node("PC", f"Portable continuity: {portable.get('status') or 'not configured'}"))
    edges.append(_edge("Repo", "PC"))
    lines.extend(nodes)
    lines.extend(edges)
    return "\n".join(lines).rstrip() + "\n"


def _markdown_list(values: list[str]) -> list[str]:
    return [f"- {value}" for value in values] if values else ["- None"]


def _section_items(items: list[dict[str, Any]], *, title_key: str = "title") -> list[str]:
    if not items:
        return ["- None"]
    lines: list[str] = []
    for item in items:
        title = str(item.get(title_key) or item.get("id") or item.get("path") or item.get("area_id") or "unknown")
        extra = []
        for key in ("status", "reuse_confidence", "area_id", "timestamp", "path"):
            value = str(item.get(key) or "").strip()
            if value and value != title:
                extra.append(f"{key}: {value}")
        suffix = f" ({'; '.join(extra)})" if extra else ""
        lines.append(f"- {title}{suffix}")
    return lines


def render_continuity_markdown(model: dict[str, Any]) -> str:
    repo = model.get("repository") if isinstance(model.get("repository"), dict) else {}
    summary = model.get("summary") if isinstance(model.get("summary"), dict) else {}
    work = model.get("work_state") if isinstance(model.get("work_state"), dict) else {}
    contract = model.get("execution_contract") if isinstance(model.get("execution_contract"), dict) else {}
    portable = model.get("portable_continuity") if isinstance(model.get("portable_continuity"), dict) else {}
    hidden = model.get("hidden_counts") if isinstance(model.get("hidden_counts"), dict) else {}
    mermaid = render_continuity_mermaid(model).rstrip()
    lines = [
        "# AICTX Continuity View",
        "",
        f"Generated: {model.get('generated_at') or ''}  ",
        f"Repository: {repo.get('root') or repo.get('name') or 'unknown'}  ",
        f"Branch: {repo.get('branch') or 'unknown'}  ",
        f"Commit: {repo.get('commit') or 'unknown'}  ",
        f"Dirty: {'yes' if repo.get('dirty') else 'no'}",
        "",
        "## Overview",
        "",
    ]
    if not _has_operational_signal(model):
        lines.extend(["AICTX Continuity View generated with limited data.", ""])
    active_task_title = work.get("title") if work.get("exists") and str(work.get("source") or "") == "active" else "None"
    lines.extend(
        [
            f"- Active task: {active_task_title}",
            f"- Next action: {work.get('next_action') or 'None'}",
            f"- Current risk: {work.get('risk') or 'None'}",
            f"- Changed files: {summary.get('changed_files', 0)}",
            f"- Last execution: {(model.get('execution_summaries') or [{}])[0].get('title') if model.get('execution_summaries') else 'None'}",
            f"- Open handoffs: {summary.get('open_handoffs', 0)}",
            f"- Relevant failures: {summary.get('relevant_failures', 0)}",
            f"- Latest compatible execution contract: {contract.get('title') if contract.get('exists') else 'None'}",
            f"- Portable continuity: {portable.get('status') or 'not configured'}",
            "",
            "## Continuity Map",
            "",
            "```mermaid",
            mermaid,
            "```",
            "",
            "## Working Tree Changes",
            "",
        ]
    )
    changed_files = list(repo.get("changed_files") or [])
    if changed_files:
        lines.extend([f"- {path}" for path in changed_files])
        changed_count = int(repo.get("changed_count") or len(changed_files))
        if changed_count > len(changed_files):
            lines.append(f"- + {changed_count - len(changed_files)} older entries hidden")
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Active Work State",
            "",
        ]
    )
    if work.get("exists"):
        lines.extend(
            [
                f"- Title: {work.get('title')}",
                f"- Status: {work.get('status') or 'unknown'}",
                f"- Source: {work.get('source') or 'unknown'}",
                f"- Next action: {work.get('next_action') or 'None'}",
                f"- Risk: {work.get('risk') or 'None'}",
                "- Active files:",
                *_markdown_list(list(work.get("active_files") or [])),
            ]
        )
    else:
        lines.append("No active Work State found.")

    for section, key, title_key in (
        ("Open Handoffs", "open_handoffs", "title"),
        ("Relevant Failures", "relevant_failures", "title"),
        ("Strategy Memory", "strategies", "title"),
        ("Area Memory", "area_memory", "area_id"),
    ):
        lines.extend(["", f"## {section}", ""])
        lines.extend(_section_items(list(model.get(key) or []), title_key=title_key))
        hidden_count = int(hidden.get(key if key != "relevant_failures" else "failures", 0) or 0)
        if hidden_count:
            lines.append(f"- + {hidden_count} older entries hidden")

    lines.extend(["", "## Execution Contracts", ""])
    if contract.get("exists"):
        lines.extend(
            [
                f"- Title: {contract.get('title')}",
                f"- Strength: {contract.get('strength') or 'unknown'}",
                f"- First action: {contract.get('first_action') or 'unknown'}",
                f"- Test command: {contract.get('test_command') or 'unknown'}",
            ]
        )
    else:
        lines.append("- None")

    for section, key, title_key in (
        ("Execution Summaries", "execution_summaries", "title"),
        ("RepoMap Hints", "repomap_hints", "path"),
    ):
        lines.extend(["", f"## {section}", ""])
        if key == "repomap_hints" and not model.get(key):
            lines.append(f"RepoMap hints: {model.get('repomap_status') or 'unavailable'}")
        else:
            lines.extend(_section_items(list(model.get(key) or []), title_key=title_key))
        hidden_count = int(hidden.get(key, 0) or 0)
        if hidden_count:
            lines.append(f"- + {hidden_count} older entries hidden")

    lines.extend(
        [
            "",
            "## Portable Continuity",
            "",
            f"- Status: {portable.get('status') or 'not configured'}",
            f"- Mode: {portable.get('mode') or 'not configured'}",
            "",
            "## Notes for the Next Agent",
            "",
            "- Continuity View shows the current operational continuity of the repository, not just the latest run.",
            "- The agent triggers it. AICTX generates it. Mermaid is deterministic.",
            "- Inspect this view before starting work that depends on prior continuity.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _relative_to_repo(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def continuity_view_status(repo_root: Path) -> dict[str, Any]:
    repo_root = Path(repo_root).expanduser().resolve()
    markdown_path = repo_root / CONTINUITY_VIEW_PATH
    mermaid_path = repo_root / CONTINUITY_MAP_PATH
    payload: dict[str, Any] = {
        "exists": markdown_path.exists(),
        "markdown_path": CONTINUITY_VIEW_PATH.as_posix(),
        "mermaid_path": CONTINUITY_MAP_PATH.as_posix(),
    }
    if markdown_path.exists():
        try:
            stat = markdown_path.stat()
            payload["generated_at"] = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        except OSError:
            payload["generated_at"] = ""
    return payload


def write_continuity_view(repo_root: Path, output: Path | str | None = None, map_output: Path | str | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root).expanduser().resolve()
    markdown_path = Path(output).expanduser() if output else repo_root / CONTINUITY_VIEW_PATH
    if not markdown_path.is_absolute():
        markdown_path = repo_root / markdown_path
    mermaid_path = Path(map_output).expanduser() if map_output else repo_root / CONTINUITY_MAP_PATH
    if not mermaid_path.is_absolute():
        mermaid_path = repo_root / mermaid_path
    model = build_continuity_view_model(repo_root)
    markdown = render_continuity_markdown(model)
    mermaid = render_continuity_mermaid(model)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    mermaid_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(markdown, encoding="utf-8")
    mermaid_path.write_text(mermaid, encoding="utf-8")
    return {
        "ok": True,
        "view": {
            "markdown_path": _relative_to_repo(repo_root, markdown_path),
            "mermaid_path": _relative_to_repo(repo_root, mermaid_path),
            "generated_at": str(model.get("generated_at") or ""),
        },
        "summary": model.get("summary", {}),
        "model": model,
    }


def mermaid_live_url(mermaid: str, *, mode: str = "edit") -> str:
    target_mode = "view" if str(mode or "").strip() == "view" else "edit"
    payload = json.dumps(
        {"code": str(mermaid or ""), "mermaid": {"theme": "default"}},
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    compressor = zlib.compressobj(9, zlib.DEFLATED, 15, 8, zlib.Z_DEFAULT_STRATEGY)
    compressed = compressor.compress(payload) + compressor.flush()
    encoded = base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("=")
    return f"https://mermaid.live/{target_mode}#pako:{encoded}"


def continuity_view_summary_links(repo_root: Path) -> dict[str, str]:
    repo_root = Path(repo_root).expanduser().resolve()
    mermaid_path = repo_root / CONTINUITY_MAP_PATH
    if mermaid_path.exists():
        try:
            mermaid = mermaid_path.read_text(encoding="utf-8")
        except OSError:
            mermaid = ""
    else:
        mermaid = render_continuity_mermaid(build_continuity_view_model(repo_root))
    file_path = CONTINUITY_MAP_PATH.as_posix()
    online_url = mermaid_live_url(mermaid, mode="view")
    return {
        "file_path": file_path,
        "file_link": f"[continuity-map.mmd]({file_path})",
        "online_url": online_url,
        "online_link": f"[mermaid.live view]({online_url})",
    }
