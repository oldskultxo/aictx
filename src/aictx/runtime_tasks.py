from __future__ import annotations

from typing import Any


TASK_TYPES_ORDER = ("bug_fixing", "refactoring", "testing", "performance", "architecture", "feature_work")


def route_task(task: str) -> dict[str, Any]:
    return {
        "task": task,
        "mode": "deterministic",
    }


def resolve_task_type(
    task: str,
    *,
    explicit_task_type: str | None = None,
    packet_metadata: dict[str, Any] | None = None,
    touched_files: list[str] | None = None,
) -> dict[str, Any]:
    explicit = str(explicit_task_type or "").strip()
    if explicit:
        return {
            "task_type": explicit,
            "source": "explicit_task_type",
            "fallback": False,
            "confidence": 1.0,
            "signals": [f"explicit:{explicit}"],
            "evidence": [f"explicit:{explicit}"],
            "ambiguous": False,
        }
    task_text = str(task or "")
    metadata_type = str((packet_metadata or {}).get("task_type") or "").strip()
    if metadata_type:
        return {
            "task_type": metadata_type,
            "source": "packet_metadata",
            "fallback": False,
            "confidence": 1.0,
            "signals": [f"packet_metadata:{metadata_type}"],
            "evidence": [f"packet_metadata:{metadata_type}"],
            "ambiguous": False,
        }
    files = [str(path) for path in (touched_files or []) if str(path).strip()]
    try:
        from . import core_runtime as cr

        inferred = cr.classify_task_type_from_text(task_text)
        path_signals = cr.infer_task_signals(task_text, files)
        if inferred == "unknown":
            for signal in path_signals:
                parts = signal.split(":", 2)
                if len(parts) >= 2 and parts[0] == "path":
                    inferred = parts[1]
                    break
        confidence = cr.task_type_confidence(task_text, inferred, files)
    except Exception:
        inferred = _fallback_infer_task_type(task_text, files)
        path_signals = _fallback_signals(task_text, files, inferred)
        confidence = 0.35 if inferred == "unknown" else 0.65
    if inferred != "unknown":
        evidence = path_signals or [f"heuristic:{inferred}"]
        return {
            "task_type": inferred,
            "source": "heuristic",
            "fallback": False,
            "confidence": confidence,
            "signals": evidence,
            "evidence": evidence,
            "ambiguous": confidence < 0.55,
        }
    return {
        "task_type": "unknown",
        "source": "unknown_fallback",
        "fallback": True,
        "confidence": confidence,
        "signals": path_signals,
        "evidence": path_signals or ["no_explicit_task_type"],
        "ambiguous": True,
    }


def resolve_observed_task_type(
    task: str,
    *,
    explicit_task_type: str | None = None,
    packet_metadata: dict[str, Any] | None = None,
    touched_files: list[str] | None = None,
    tests_executed: list[str] | None = None,
    commands_executed: list[str] | None = None,
    notable_errors: list[str] | None = None,
    result_summary: str | None = None,
) -> dict[str, Any]:
    explicit = str(explicit_task_type or "").strip()
    if explicit:
        resolved = resolve_task_type(
            task,
            explicit_task_type=explicit,
            packet_metadata=packet_metadata,
            touched_files=touched_files,
        )
        resolved["phase"] = "observed"
        return resolved
    files = [str(path) for path in (touched_files or []) if str(path).strip()]
    tests = [str(item) for item in (tests_executed or []) if str(item).strip()]
    commands = [str(item) for item in (commands_executed or []) if str(item).strip()]
    errors = [str(item) for item in (notable_errors or []) if str(item).strip()]
    summary = str(result_summary or "").strip()
    provisional = resolve_task_type(
        task,
        explicit_task_type=None,
        packet_metadata=packet_metadata,
        touched_files=files,
    )
    scored = _resolve_task_type_from_observed_signals(
        task,
        files=files,
        tests=tests,
        commands=commands,
        errors=errors,
        result_summary=summary,
    )
    if scored["task_type"] == "unknown":
        scored = provisional
    elif provisional.get("task_type") == scored["task_type"] and provisional.get("task_type") != "unknown":
        evidence = _merge_unique(list(provisional.get("evidence", [])), list(scored.get("evidence", [])))
        signals = _merge_unique(list(provisional.get("signals", [])), list(scored.get("signals", [])))
        scored = {
            **scored,
            "evidence": evidence,
            "signals": signals,
            "confidence": max(float(provisional.get("confidence", 0.0) or 0.0), float(scored.get("confidence", 0.0) or 0.0)),
        }
    scored["phase"] = "observed"
    return scored


def _fallback_infer_task_type(task: str, files: list[str]) -> str:
    haystack = f"{task} {' '.join(files)}".lower()
    rules = [
        ("architecture", ["architecture", "design", "protocol", "schema"]),
        ("performance", ["performance", "perf", "benchmark", "speed", "latency"]),
        ("testing", ["test", "pytest", "coverage", "assert", "spec"]),
        ("refactoring", ["refactor", "cleanup", "rename", "simplify"]),
        ("bug_fixing", ["bug", "fix", "debug", "failing", "error", "traceback"]),
        ("feature_work", ["feature", "add", "implement", "support"]),
    ]
    for task_type, keywords in rules:
        if any(keyword in haystack for keyword in keywords):
            return task_type
    return "unknown"


def _fallback_signals(task: str, files: list[str], task_type: str) -> list[str]:
    if task_type == "unknown":
        return []
    return [f"heuristic:{task_type}:{task or ','.join(files)}"][:1]


def _merge_unique(*parts: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for values in parts:
        for raw in values:
            item = str(raw or "").strip()
            if not item or item in seen:
                continue
            merged.append(item)
            seen.add(item)
    return merged[:12]


def _resolve_task_type_from_observed_signals(
    task: str,
    *,
    files: list[str],
    tests: list[str],
    commands: list[str],
    errors: list[str],
    result_summary: str,
) -> dict[str, Any]:
    scores = {task_type: 0 for task_type in TASK_TYPES_ORDER}
    evidence: dict[str, list[str]] = {task_type: [] for task_type in TASK_TYPES_ORDER}
    request = str(task or "").strip()
    combined_text = "\n".join(
        item for item in [request, result_summary, "\n".join(errors)] if str(item).strip()
    ).lower()
    command_text = "\n".join(commands + tests).lower()
    normalized_files = [str(path).strip() for path in files if str(path).strip()]
    src_files = [path for path in normalized_files if path.startswith("src/")]
    test_files = [path for path in normalized_files if path.startswith("tests/") or "/tests/" in path or "test_" in path]

    _score_keywords(combined_text, scores=scores, evidence=evidence)

    if errors:
        scores["bug_fixing"] += 4
        evidence["bug_fixing"].append("observed_errors")
    if any(token in command_text for token in ("pytest", "coverage", "smoke", "assert")):
        if src_files:
            evidence["testing"].append("validation_commands")
        else:
            scores["testing"] += 1
            evidence["testing"].append("validation_commands")
    if any(token in command_text for token in ("benchmark", "latency", "throughput", "perf")):
        scores["performance"] += 2
        evidence["performance"].append("performance_commands")

    for path in normalized_files:
        path_l = str(path).lower()
        if any(part in path_l for part in ["test", "spec", "pytest"]):
            scores["testing"] += 2
            evidence["testing"].append(f"path:{path}")
        if any(part in path_l for part in ["perf", "benchmark"]):
            scores["performance"] += 3
            evidence["performance"].append(f"path:{path}")
        if any(part in path_l for part in ["arch", "protocol", "migration"]):
            scores["architecture"] += 2
            evidence["architecture"].append(f"path:{path}")

    if test_files and not src_files:
        scores["testing"] += 3
        evidence["testing"].append("tests_only_change")
    elif tests and not src_files:
        scores["testing"] += 1
        evidence["testing"].append("tests_executed")
    if src_files and test_files and not errors:
        scores["refactoring"] += 3
        evidence["refactoring"].append("src_and_tests_change")
    if src_files and tests and not errors:
        scores["refactoring"] += 2
        evidence["refactoring"].append("validation_after_source_change")
    if src_files and not errors:
        scores["feature_work"] += 2
        evidence["feature_work"].append("source_change")

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    best_type, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0
    if best_score <= 0:
        return {
            "task_type": "unknown",
            "source": "observed_unknown",
            "fallback": True,
            "confidence": 0.35,
            "signals": [],
            "evidence": ["no_observed_task_signals"],
            "ambiguous": True,
        }
    confidence = 0.55 + min(0.35, best_score * 0.03) + min(0.1, max(0, best_score - second_score) * 0.02)
    confidence = round(min(0.95, confidence), 2)
    merged_evidence = _merge_unique(evidence.get(best_type, []), _fallback_signals(task, files, best_type))
    return {
        "task_type": best_type,
        "source": "observed_signals",
        "fallback": False,
        "confidence": confidence,
        "signals": merged_evidence,
        "evidence": merged_evidence,
        "ambiguous": confidence < 0.65,
        "score_breakdown": scores,
    }


def _score_keywords(text: str, *, scores: dict[str, int], evidence: dict[str, list[str]]) -> None:
    weighted_keywords = {
        "bug_fixing": ("bug", "fix", "error", "crash", "failure", "debug", "corregir", "fallo"),
        "refactoring": ("refactor", "cleanup", "simplify", "rename", "align", "localize", "mejorar", "ajustar", "summary", "output", "render", "banner"),
        "testing": ("test", "testing", "coverage", "assert", "pytest", "spec", "validation", "smoke", "verify"),
        "performance": ("performance", "latency", "slow", "optimiz", "throughput", "bottleneck"),
        "architecture": ("architecture", "protocol", "migration", "system", "boundary", "design", "subsystem"),
        "feature_work": ("feature", "implement", "add", "introduce", "support", "behavior", "workflow", "ux", "expose"),
    }
    for task_type, keywords in weighted_keywords.items():
        for keyword in keywords:
            if keyword in text:
                scores[task_type] += 3
                evidence[task_type].append(f"text:{keyword}")


def packet_for_task(
    task: str | dict[str, Any],
    ctx: dict[str, Any] | None = None,
    *,
    project: str | None = None,
    task_type: str | None = None,
) -> dict[str, Any]:
    del project
    if isinstance(task, dict):
        return {
            "task_type": str(task.get("task_type", "unknown") or "unknown"),
            "description": str(task.get("description", "") or ""),
            "context": dict((ctx or {}).get("context", {})) if isinstance(ctx, dict) else {},
        }

    resolved = resolve_task_type(task, explicit_task_type=task_type)
    return {
        "task_type": resolved["task_type"],
        "description": str(task or ""),
        "context": dict((ctx or {}).get("context", {})) if isinstance(ctx, dict) else {},
    }
