from __future__ import annotations

import re
from pathlib import Path
from typing import Any

STEER_CLASSIFICATIONS = {
    "scope_change",
    "scope_constraint",
    "priority_change",
    "validation_change",
    "strategy_change",
    "new_requirement",
    "cancellation",
    "clarification",
    "side_comment",
    "risk_warning",
    "agent_correction",
    "unknown",
}
STEER_DECISIONS = {
    "continue",
    "pause",
    "replan",
    "re_ground",
    "update_contract",
    "update_validation",
    "append_requirement",
    "ignore_as_side_comment",
    "ask_user",
}
STEER_CURRENT_ACTIONS = {"edit", "command", "finalize", "final_answer", "planning", "unknown"}

_PATH_RE = re.compile(r"(?<![A-Za-z0-9_./-])(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+|\b[A-Za-z0-9_.-]+\.(?:py|js|ts|tsx|jsx|md|rst|txt|toml|yaml|yml|json|css|html)\b")


def _clean(value: Any, limit: int = 220) -> str:
    text = " ".join(str(value or "").strip().split())
    return text[:limit].rstrip()


def _normalize_path(path: str) -> str:
    text = str(path or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text.strip("/")


def _dedupe(values: list[str], *, limit: int = 12) -> list[str]:
    result: list[str] = []
    for value in values:
        text = _normalize_path(value)
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _message_paths(message: str) -> list[str]:
    paths = [match.group(0).rstrip(".,;:)") for match in _PATH_RE.finditer(message)]
    low = message.casefold()
    if "docs" in low and not any(path == "docs" or path.startswith("docs/") for path in paths):
        paths.append("docs")
    return _dedupe(paths)


def infer_discarded_hypothesis_from_correction(message: str) -> dict[str, Any]:
    text = _clean(message)
    if not text:
        return {}
    paths = _message_paths(text)
    hypothesis = "Previous agent understanding or path was corrected by the user."
    if paths:
        hypothesis = f"Previous direction involving {', '.join(paths[:3])} was wrong or incomplete."
    reason = text
    return {
        "hypothesis": hypothesis,
        "reason": reason,
        "evidence": "user_correction",
        "confidence": "medium",
        "related_paths": paths,
    }


def _has(text: str, *patterns: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _payload(
    *,
    status: str,
    classification: str,
    decision: str,
    impact: str,
    summary: str,
    agent_instruction: str,
    suggested_updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "classification": classification,
        "decision": decision,
        "impact": impact,
        "summary": _clean(summary),
        "agent_instruction": _clean(agent_instruction, 320),
        "suggested_updates": suggested_updates or {},
    }


def build_steer_guard(
    repo_root: Path,
    *,
    message: str,
    current_action: str = "unknown",
    paths: list[str] | None = None,
    agent_id: str = "",
    session_id: str = "",
) -> dict[str, Any]:
    # repo/agent/session are accepted for API symmetry and future read-only context checks.
    Path(repo_root).expanduser().resolve()
    text = _clean(message, 1000)
    if not text:
        raise ValueError("message is required")
    action = str(current_action or "unknown").strip().lower() or "unknown"
    if action not in STEER_CURRENT_ACTIONS:
        action = "unknown"

    supplied_paths = _dedupe(paths or [])
    inferred_paths = _message_paths(text)
    relevant_paths = _dedupe(supplied_paths + inferred_paths)
    low = text.casefold()
    path_text = ", ".join(relevant_paths) if relevant_paths else "the affected path"

    if _has(low, r"\b(stop|pause|wait|hold on)\b", r"don['’]?t\s+continue", r"do\s+not\s+continue"):
        return _payload(
            status="warning",
            classification="cancellation",
            decision="pause",
            impact="work_should_pause",
            summary="User asked the agent to stop or wait.",
            agent_instruction="Stop current work and wait for a new instruction.",
        )

    if _has(low, r"don['’]?t\s+(touch|edit|modify|change)", r"do\s+not\s+(touch|edit|modify|change)", r"\bavoid\b.+\b(file|path|edit|touch|modify|change)"):
        updates: dict[str, Any] = {"work_state_note": f"Avoid {path_text} unless the user explicitly allows it."}
        if relevant_paths:
            updates["forbidden_paths"] = relevant_paths
        return _payload(
            status="warning",
            classification="scope_constraint",
            decision="update_contract",
            impact="contract_update_required",
            summary=f"User added a constraint: do not edit {path_text}.",
            agent_instruction=f"Pause before the next edit and continue without touching {path_text}.",
            suggested_updates=updates,
        )

    if _has(low, r"don['’]?t\s+run\s+(the\s+)?full\s+suite", r"do\s+not\s+run\s+(the\s+)?full\s+suite", r"\bskip\s+tests?\b", r"\brun\s+only\b", r"\btargeted\s+tests?\b"):
        return _payload(
            status="warning",
            classification="validation_change",
            decision="update_validation",
            impact="validation_update_required",
            summary="User changed validation expectations.",
            agent_instruction="Update validation expectations before finalizing this task.",
            suggested_updates={"validation_note": text},
        )

    if _has(low, r"\b(simpler|simplest)\b", r"\binstead\b", r"\banother approach\b", r"\bdifferent approach\b"):
        return _payload(
            status="warning",
            classification="strategy_change",
            decision="replan",
            impact="plan_update_required",
            summary="User changed or constrained the implementation strategy.",
            agent_instruction="Replan before continuing and preserve the user's strategy constraint.",
            suggested_updates={"strategy_note": text},
        )

    if _has(low, r"\b(i mean|to clarify|clarification|what i meant)\b"):
        return _payload(
            status="warning",
            classification="clarification",
            decision="replan",
            impact="plan_update_required",
            summary="User clarified the current task.",
            agent_instruction="Update the current plan with this clarification before continuing.",
            suggested_updates={"clarification_note": text},
        )

    if _has(low, r"\b(be careful|careful|risky|risk|don['’]?t break|do not break)\b"):
        return _payload(
            status="warning",
            classification="risk_warning",
            decision="re_ground",
            impact="caution_required",
            summary="User added a risk warning.",
            agent_instruction="Re-ground before the next risky action and preserve the warning.",
            suggested_updates={"risk_note": text},
        )

    if _has(low, r"\b(that['’]?s wrong|wrong|not that|you misunderstood|misunderstood)\b"):
        discarded = infer_discarded_hypothesis_from_correction(text)
        return _payload(
            status="warning",
            classification="agent_correction",
            decision="replan",
            impact="plan_update_required",
            summary="User corrected the agent's understanding.",
            agent_instruction="Pause and update the plan according to the correction before continuing.",
            suggested_updates={"correction_note": text, "discarded_hypothesis": discarded} if discarded else {"correction_note": text},
        )

    if _has(low, r"\b(also|add|include)\b", r"\bupdate\s+docs\b", r"\bupdate\s+documentation\b"):
        updates = {"requirement_note": text}
        if relevant_paths:
            updates["required_paths"] = relevant_paths
        return _payload(
            status="warning",
            classification="new_requirement",
            decision="append_requirement",
            impact="work_state_update_recommended",
            summary="User added a requirement to the current task.",
            agent_instruction="Append this requirement to the active task before continuing.",
            suggested_updates=updates,
        )

    if _has(low, r"\b(just an idea|ignore that|never mind|nevermind|for later|side note|fyi)\b"):
        return _payload(
            status="ok",
            classification="side_comment",
            decision="ignore_as_side_comment",
            impact="none",
            summary="User comment does not change the current task.",
            agent_instruction="Continue with the current plan.",
        )

    return _payload(
        status="warning",
        classification="unknown",
        decision="ask_user",
        impact="clarification_required",
        summary="User message is ambiguous for the active task.",
        agent_instruction="Ask the user whether this changes the current task before continuing.",
    )
