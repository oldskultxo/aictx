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

suggest = run_json(["aictx", "suggest", "--repo", repo])
reuse = run_json(["aictx", "reuse", "--repo", repo])
summary = [
    "AICTX runtime guidance loaded for this prompt.",
    "Use execution history and strategy memory before broad repo scanning.",
]
entry_points = suggest.get("suggested_entry_points", []) if isinstance(suggest, dict) else []
if entry_points:
    summary.append("Suggested entry points: " + ", ".join(str(item) for item in entry_points))
files_used = reuse.get("files_used", []) if isinstance(reuse, dict) else []
if files_used:
    summary.append("Reusable files: " + ", ".join(str(item) for item in files_used[:5]))
summary.append("Before opening more than 3 files or when unsure, run: aictx suggest --repo .")
summary.append("If you reopen the same file several times, run: aictx reflect --repo .")
summary.append("If the task matches previous work, run: aictx reuse --repo .")
summary.append("After finalize, append agent_summary_text verbatim to the final user response.")
summary.append("If no finalize output exists, say: AICTX summary unavailable.")

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": "\n".join(summary)
    }
}))
