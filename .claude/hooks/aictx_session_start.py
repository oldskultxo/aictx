#!/usr/bin/env python3
import json

summary = [
    "AICTX runtime loaded for this Claude session.",
    "Prefer .ai_context_engine/metrics/execution_logs.jsonl as real execution history.",
    "Prefer .ai_context_engine/strategy_memory/strategies.jsonl for reusable patterns.",
    "Use aictx suggest/reuse/reflect when needed.",
]

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": "\n".join(summary)
    }
}))
