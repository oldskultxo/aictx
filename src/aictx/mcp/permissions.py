from __future__ import annotations

READONLY_TOOLS = {
    "aictx_resume", "aictx_next", "aictx_view", "aictx_doctor", "aictx_task_list", "aictx_task_show",
    "aictx_map_status", "aictx_map_query", "aictx_portability_status", "aictx_messages_status", "aictx_report_real_usage", "aictx_continuity_quality",
}
STANDARD_TOOLS = READONLY_TOOLS | {"aictx_finalize", "aictx_task_start", "aictx_task_update", "aictx_task_close", "aictx_continuity_view_generate"}
FULL_TOOLS = STANDARD_TOOLS | {"aictx_record_decision", "aictx_record_handoff", "aictx_record_failure", "aictx_strategy_suggest", "aictx_map_refresh", "aictx_portability_compact", "aictx_messages_set"}
PROFILE_TOOLS = {"readonly": READONLY_TOOLS, "standard": STANDARD_TOOLS, "full": FULL_TOOLS}


def allowed_tools(profile: str) -> set[str]:
    return set(PROFILE_TOOLS.get(profile, FULL_TOOLS))
