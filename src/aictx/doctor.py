from __future__ import annotations

from pathlib import Path
from typing import Any

from ._version import __version__
from .contract_compliance import load_contract_compliance_history, summarize_contract_compliance_history
from .failures import load_failures
from .report import build_repo_map_report, read_jsonl
from .state import REPO_METRICS_DIR, REPO_STRATEGY_MEMORY_DIR


def _check(name: str, status: str, summary: str, *, details: dict[str, Any] | None = None, recommended_action: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": str(name or ""),
        "status": status if status in {"ok", "warning", "error"} else "warning",
        "summary": str(summary or ""),
        "details": details or {},
    }
    if recommended_action:
        payload["recommended_action"] = recommended_action
    return payload


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError:
        return ""


def _aggregate_status(checks: list[dict[str, Any]]) -> str:
    statuses = {str(item.get("status") or "warning") for item in checks}
    if "error" in statuses:
        return "error"
    if "warning" in statuses:
        return "warning"
    return "ok"


def _capture_quality_snapshot(repo: Path) -> dict[str, Any]:
    logs = read_jsonl(repo / REPO_METRICS_DIR / "execution_logs.jsonl")
    feedback = read_jsonl(repo / REPO_METRICS_DIR / "execution_feedback.jsonl")
    capture_fields = ["files_opened", "files_edited", "commands_executed", "tests_executed", "notable_errors", "error_events"]
    coverage = {
        field: sum(1 for row in logs if isinstance(row.get(field), list) and bool(row.get(field)))
        for field in capture_fields
    }
    ratios: list[float] = []
    for row in feedback:
        summary = row.get("agent_summary") if isinstance(row.get("agent_summary"), dict) else {}
        quality = summary.get("capture_quality") if isinstance(summary.get("capture_quality"), dict) else {}
        ratio = quality.get("coverage_ratio") if isinstance(quality, dict) else None
        if isinstance(ratio, (int, float)):
            ratios.append(float(ratio))
    return {
        "avg_capture_quality": round(sum(ratios) / len(ratios), 4) if ratios else None,
        "capture_coverage": coverage,
    }


def _memory_hygiene_snapshot(repo: Path) -> dict[str, Any]:
    strategies = read_jsonl(repo / REPO_STRATEGY_MEMORY_DIR / "strategies.jsonl")
    failures = load_failures(repo)
    seen_strategies: set[tuple[Any, ...]] = set()
    duplicate_strategies = 0
    for row in strategies:
        key = (
            row.get("task_type"),
            tuple(row.get("files_used", []) if isinstance(row.get("files_used"), list) else []),
            tuple(row.get("commands_executed", []) if isinstance(row.get("commands_executed"), list) else []),
        )
        if key in seen_strategies:
            duplicate_strategies += 1
        seen_strategies.add(key)
    seen_failures: set[str] = set()
    duplicate_failures = 0
    for row in failures:
        signature = str(row.get("signature") or "")
        if signature and signature in seen_failures:
            duplicate_failures += 1
        seen_failures.add(signature)
    return {
        "stale_strategy_candidates": max(0, len(strategies) - 50),
        "duplicate_strategy_candidates": duplicate_strategies,
        "duplicate_failure_candidates": duplicate_failures,
    }


def build_doctor_report(repo_root: Path) -> dict[str, Any]:
    """Build a read-only support/release-readiness diagnostic report."""
    repo = Path(repo_root).expanduser().resolve()
    checks: list[dict[str, Any]] = []
    recommended_actions: list[str] = []

    checks.append(_check("cli_version", "ok", f"aictx {__version__}", details={"version": __version__}))

    initialized = (repo / ".aictx").is_dir()
    checks.append(_check(
        "repo_initialized",
        "ok" if initialized else "error",
        "repo-local .aictx scaffold is present" if initialized else "repo-local .aictx scaffold is missing",
        recommended_action="run aictx init --repo ." if not initialized else "",
    ))

    runner_files = {
        "AGENTS.md": (repo / "AGENTS.md").exists(),
        "CLAUDE.md": (repo / "CLAUDE.md").exists(),
        ".claude/settings.json": (repo / ".claude" / "settings.json").exists(),
    }
    present_count = sum(1 for value in runner_files.values() if value)
    checks.append(_check(
        "runner_files_present",
        "ok" if present_count else "warning",
        f"{present_count}/{len(runner_files)} runner integration files present",
        details=runner_files,
        recommended_action="run aictx init --repo . to refresh runner integrations" if not present_count else "",
    ))

    makefile = _read_text(repo / "Makefile")
    ci_workflow = _read_text(repo / ".github" / "workflows" / "ci.yml")
    lifecycle_details = {
        "makefile_present": bool(makefile),
        "uses_task_flag": "--task" in makefile,
        "uses_request_flag": "--request" in makefile,
        "ci_delegates_to_make_ci": "make ci" in ci_workflow,
    }
    lifecycle_ok = bool(makefile) and lifecycle_details["uses_task_flag"] and not lifecycle_details["uses_request_flag"]
    checks.append(_check(
        "lifecycle_smoke_compatibility",
        "ok" if lifecycle_ok else "error",
        "smoke lifecycle uses --task" if lifecycle_ok else "smoke lifecycle is not aligned with --task",
        details=lifecycle_details,
        recommended_action="update Makefile smoke lifecycle to use aictx resume --task and remove --request" if not lifecycle_ok else "",
    ))
    make_ci_ok = bool(makefile) and "ci:" in makefile and "make ci" in ci_workflow
    checks.append(_check(
        "makefile_ci_compatibility",
        "ok" if make_ci_ok else "warning",
        "CI delegates release gate to make ci" if make_ci_ok else "make ci is not clearly the canonical CI/release gate",
        details={"makefile_has_ci_target": "ci:" in makefile, "workflow_mentions_make_ci": "make ci" in ci_workflow},
        recommended_action="make GitHub Actions call make ci and keep release readiness in Makefile" if not make_ci_ok else "",
    ))

    repo_map = build_repo_map_report(repo)
    repo_map_ok = bool(repo_map.get("query_available")) or not bool(repo_map.get("enabled"))
    checks.append(_check(
        "repomap_status",
        "ok" if repo_map_ok else "warning",
        "RepoMap query path is available" if repo_map.get("query_available") else "RepoMap has no queryable index",
        details=repo_map,
        recommended_action="run aictx map refresh --repo . --json" if bool(repo_map.get("enabled")) and not bool(repo_map.get("query_available")) else "",
    ))

    capture = _capture_quality_snapshot(repo)
    capture_quality = capture.get("avg_capture_quality")
    capture_coverage = capture.get("capture_coverage") if isinstance(capture.get("capture_coverage"), dict) else {}
    capture_status = "ok" if isinstance(capture_quality, (int, float)) and capture_quality >= 0.5 else "warning"
    checks.append(_check(
        "capture_quality",
        capture_status,
        f"average capture quality: {capture_quality}" if capture_quality is not None else "capture quality has insufficient samples",
        details={"avg_capture_quality": capture_quality, "capture_coverage": capture_coverage},
        recommended_action="run normal lifecycle with explicit capture fields or wrapper capture enabled" if capture_status == "warning" else "",
    ))

    contract = summarize_contract_compliance_history(load_contract_compliance_history(repo, limit=500))
    violated = int(contract.get("violated") or 0)
    partial = int(contract.get("partial") or 0)
    evaluated = int(contract.get("evaluated") or 0)
    contract_status = "ok" if evaluated and not violated and partial <= evaluated else "warning"
    checks.append(_check(
        "contract_compliance_health",
        contract_status,
        "contract compliance history is healthy" if contract_status == "ok" else "contract compliance has gaps or insufficient evaluated history",
        details=contract,
        recommended_action="inspect recent contract gaps and ensure finalize observes first action, scope, and canonical test" if contract_status == "warning" else "",
    ))

    hygiene = _memory_hygiene_snapshot(repo)
    stale_count = int(hygiene.get("stale_strategy_candidates") or 0)
    duplicate_count = int(hygiene.get("duplicate_strategy_candidates") or 0) + int(hygiene.get("duplicate_failure_candidates") or 0)
    hygiene_status = "ok" if stale_count == 0 and duplicate_count == 0 else "warning"
    checks.append(_check(
        "stale_duplicate_memory",
        hygiene_status,
        "no stale or duplicate memory reported" if hygiene_status == "ok" else "stale or duplicate memory needs cleanup",
        details=hygiene,
        recommended_action="run maintenance/compaction diagnostics before release" if hygiene_status == "warning" else "",
    ))

    for item in checks:
        action = str(item.get("recommended_action") or "").strip()
        if action and action not in recommended_actions:
            recommended_actions.append(action)

    return {
        "status": _aggregate_status(checks),
        "repo": repo.as_posix(),
        "version": __version__,
        "checks": checks,
        "recommended_actions": recommended_actions,
    }
