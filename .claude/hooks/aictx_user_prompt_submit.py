#!/usr/bin/env python3
import json
import os
import subprocess
import sys


def run_json(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return {}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {}


payload = json.load(sys.stdin)
prompt = str(payload.get("prompt") or "").strip()
repo = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
if not prompt:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "AICTX: empty prompt"}}))
    raise SystemExit(0)

packet = run_json(["aictx", "packet", "--task", prompt])
relevant_memory = packet.get("relevant_memory", [])[:3]
relevant_paths = packet.get("relevant_paths", [])[:5]
summary = [
    "AICTX packet prepared automatically for this prompt.",
    f"Resolved task type: {packet.get('task_type', 'unknown')}",
    f"Suggested model level: {packet.get('model_suggestion', 'unknown')}",
]
if relevant_memory:
    summary.append("Relevant memory: " + ", ".join(str(item.get("title") or item.get("id") or "") for item in relevant_memory))
if relevant_paths:
    summary.append("Relevant paths: " + ", ".join(str(path) for path in relevant_paths))
summary.append("Use .ai_context_engine as first context layer before broad repo scanning.")

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": "\n".join(summary)
    }
}))
