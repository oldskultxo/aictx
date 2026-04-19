#!/usr/bin/env python3
import json
import os
import subprocess
import sys


def run_json(cmd):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return {}
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
relevant_paths = packet.get("repo_scope", packet.get("relevant_paths", []))[:5]
normalized_paths = []
for path in relevant_paths:
    if isinstance(path, dict):
        value = str(path.get("path") or "").strip()
        if value:
            normalized_paths.append(value)
    elif str(path).strip():
        normalized_paths.append(str(path).strip())
summary = [
    "AICTX packet prepared automatically for this prompt.",
    f"Resolved task type: {packet.get('task_type', 'unknown')}",
    f"Suggested model level: {packet.get('model_suggestion', 'unknown')}",
]
if relevant_memory:
    summary.append("Relevant memory: " + ", ".join(str(item.get("title") or item.get("id") or "") for item in relevant_memory))
if normalized_paths:
    summary.append("Relevant paths: " + ", ".join(normalized_paths))
summary.append("Use .ai_context_engine as first context layer before broad repo scanning.")
summary.append("Before opening more than 3 files or when unsure, run: aictx suggest --repo .")
summary.append("If you reopen the same file, run: aictx reflect --repo .")
summary.append("If the task matches previous work, run: aictx reuse --repo .")

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": "\n".join(summary)
    }
}))
