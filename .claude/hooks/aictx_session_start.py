#!/usr/bin/env python3
import json
import os
import subprocess


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


repo = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
boot = run_json(["aictx", "boot", "--repo", repo])
repo_boot = boot.get("repo_bootstrap", {})
derived = repo_boot.get("derived_boot_summary", {})
project = repo_boot.get("project_bootstrap", {})
memory_graph = boot.get("memory_graph", {})
task_memory = boot.get("task_memory", {})

summary = [
    "AICTX bootstrap loaded automatically for this Claude session.",
    f"Project: {project.get('project') or 'unknown'}",
    f"Bootstrap required: {str(derived.get('bootstrap_required', True)).lower()}",
    f"Task-memory records: {sum((task_memory.get('records_by_task_type') or {}).values()) if isinstance(task_memory.get('records_by_task_type'), dict) else 0}",
    f"Memory-graph nodes: {memory_graph.get('nodes_total', 'unknown')}",
    "Prefer .ai_context_engine/agent_runtime.md and packet-oriented context for non-trivial work.",
]

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": "\n".join(summary)
    }
}))
