# aictx protocol

Purpose:
- keep a persistent low-cost operational memory outside the active prompt context
- support multi-LLM agents through stable local `.aictx_*` artifacts
- store only reusable information that saves future analysis time or avoids repeated failures

Query rules:
1. Read `.aictx_memory/derived_boot_summary.json` when present.
2. Apply `.aictx_memory/user_preferences.json` as defaults unless the current prompt overrides them.
3. Read the smallest relevant note first.
4. Fall back to code, runtime, and tests when memory is missing or stale.

Maintenance:
- rebuild derived artifacts with `aictx migrate`
- keep local runtime artifacts generated, not hand-maintained
- prefer editing markdown notes over hand-editing JSON artifacts
