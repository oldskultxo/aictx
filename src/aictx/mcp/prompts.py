from __future__ import annotations

PROMPTS = {
    "aictx_continue_task": "Call aictx_resume first. Use active Work State and next action. Avoid known failures. Use aictx_map_query if entry points are unclear. End with aictx_finalize.",
    "aictx_finalize_task": "Summarize changed files, commands, tests and errors. Call aictx_finalize. Generate Continuity View only if useful.",
    "aictx_debug_failure": "Call aictx_resume. Inspect failure memory. Avoid repeated failed commands. Update Work State if unfinished. Finalize success or failure.",
    "aictx_review_repo_continuity": "Call aictx_view or generate Continuity View. Summarize active work, handoffs, failures, decisions and portability. Do not modify project code.",
    "aictx_prepare_release": "Run doctor with release readiness when applicable. Inspect version alignment, docs, changelog and release checklist. Finalize findings in AICTX.",
}


def list_prompts() -> list[dict[str, str]]:
    return [{"name": name, "description": text[:120]} for name, text in PROMPTS.items()]


def get_prompt(name: str) -> dict:
    text = PROMPTS.get(name)
    if text is None:
        raise KeyError(name)
    return {"description": text, "messages": [{"role": "user", "content": {"type": "text", "text": text}}]}
