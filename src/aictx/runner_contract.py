from __future__ import annotations

from typing import Any


REQUIRED_RUNNER_TOOLS = [
    "aictx_resume",
    "aictx_finalize",
    "aictx_continuity_guard",
    "aictx_steer_guard",
]


def build_runner_contract(agent_id: str = "", adapter_id: str = "") -> dict[str, Any]:
    return {
        "version": 1,
        "aictx_required": True,
        "preferred_surface": "mcp",
        "fallback_surface": "cli",
        "must_verify_mcp_once_per_session": True,
        "required_tools": list(REQUIRED_RUNNER_TOOLS),
        "if_tools_missing": "use_cli_fallback_and_report_degraded_mode",
        "do_not_skip_lifecycle": True,
    }


def build_guard_triggers(contract: dict[str, Any] | None = None, task_type: str = "") -> list[dict[str, Any]]:
    strength = str((contract or {}).get("contract_strength") or "").strip()
    task = str(task_type or "").strip()
    non_editing = task in {"analysis", "investigation", "documentation", "qa"}
    triggers: list[dict[str, Any]] = []
    if not non_editing and strength != "exploratory":
        triggers.extend(
            [
                {
                    "condition": "before_first_edit",
                    "tool": "aictx_continuity_guard",
                    "action": "before_first_edit",
                    "risk": "low",
                    "required": True,
                },
                {
                    "condition": "edit_path_outside_contract_scope",
                    "tool": "aictx_continuity_guard",
                    "action": "scope_change",
                    "risk": "normal",
                    "required": True,
                },
            ]
        )
    triggers.extend(
        [
            {
                "condition": "risky_command",
                "tool": "aictx_continuity_guard",
                "action": "risky_command",
                "risk": "high",
                "required": True,
            },
            {
                "condition": "before_final_answer_after_repo_work",
                "tool": "aictx_continuity_guard",
                "action": "final_answer",
                "risk": "normal",
                "required": True,
            },
            {
                "condition": "user_correction_or_task_redirect",
                "tool": "aictx_steer_guard",
                "action": "agent_switch",
                "risk": "high",
                "required": True,
            },
        ]
    )
    return triggers


def build_validation_policy(task_type: str = "", contract_strength: str = "") -> dict[str, Any]:
    task = str(task_type or "unknown").strip() or "unknown"
    strength = str(contract_strength or "soft").strip() or "soft"
    code_tasks = {"bug_fixing", "feature_work", "refactoring", "testing", "performance", "architecture"}
    docs_tasks = {"documentation", "analysis", "investigation", "qa"}
    if task in code_tasks:
        required = strength != "exploratory"
        return {
            "version": 1,
            "task_type": task,
            "required": required,
            "evidence": "focused_test_or_relevant_command",
            "missing_validation_severity": "needs-validation" if required else "caution",
        }
    if task in docs_tasks:
        return {
            "version": 1,
            "task_type": task,
            "required": False,
            "evidence": "inspection_or_relevant_command",
            "missing_validation_severity": "info",
        }
    return {
        "version": 1,
        "task_type": task,
        "required": False,
        "evidence": "task_relevant_command_when_available",
        "missing_validation_severity": "caution",
    }
