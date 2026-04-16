from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from .state import REPO_DIRS, TASK_TYPES, write_json


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def bootstrap_payload(repo: Path, repo_name: str) -> dict:
    return {
        "version": 1,
        "generated_at": date.today().isoformat(),
        "project": repo_name,
        "repo_root": str(repo),
        "engine_name": "ai_context_engine",
        "agent_adapter": "generic",
        "adapter_id": "generic",
        "adapter_family": "multi_llm",
        "provider_capabilities": [
            "chat_completion",
            "tool_use",
            "structured_output",
            "long_context",
        ],
        "bootstrap_required": True,
        "bootstrap_sequence": [
            "load .ai_context_memory/derived_boot_summary.json",
            "load .ai_context_memory/user_preferences.json",
            "load .ai_context_memory/project_bootstrap.json",
            "load smallest relevant local note",
            "apply preferences as runtime defaults",
        ],
        "default_behavior": {
            "memory_first": True,
            "fallback_to_standard_repo_analysis": True,
            "explicit_user_override_wins": True,
        },
    }


def init_repo_scaffold(repo: Path, update_gitignore: bool = True) -> list[str]:
    created: list[str] = []
    repo_name = repo.name
    for rel in REPO_DIRS:
        path = repo / rel
        path.mkdir(parents=True, exist_ok=True)
        created.append(str(path))

    for task_type in TASK_TYPES:
        (repo / ".ai_context_task_memory" / task_type).mkdir(parents=True, exist_ok=True)

    write_json(repo / ".ai_context_engine" / "state.json", {
        "engine_id": "ai_context_engine",
        "engine_name": "ai_context_engine",
        "adapter_id": "generic",
        "adapter_family": "multi_llm",
        "provider_capabilities": ["chat_completion", "tool_use", "structured_output", "long_context"],
        "installed_at": now_iso(),
        "repo_root": str(repo),
    })

    compat = repo / ".ai_context_memory"
    (compat / "README.md").write_text(
        "# .ai_context_memory\n\nGenerated local bootstrap layer for AI agents.\n",
        encoding="utf-8",
    )
    write_json(compat / "manifest.json", {
        "version": 1,
        "project": repo_name,
        "artifacts": {
            "derived_boot_summary": "derived_boot_summary.json",
            "user_preferences": "user_preferences.json",
            "project_bootstrap": "project_bootstrap.json",
            "context_packet_schema": "context_packet_schema.json",
        },
    })
    write_json(compat / "derived_boot_summary.json", bootstrap_payload(repo, repo_name))
    write_json(compat / "project_bootstrap.json", {
        "version": 1,
        "project": repo_name,
        "repo_root": str(repo),
        "engine_name": "ai_context_engine",
        "lookup_order": ["repo", "workspace", "global"],
    })
    write_json(compat / "user_preferences.json", {
        "version": 1,
        "preferred_language": "en",
        "response": {"verbosity": "concise", "response_structure": "final_only"},
        "workflow": {"memory_system": "ai_context_standard"},
    })
    write_json(compat / "context_packet_schema.json", {
        "version": 1,
        "required": ["task_id", "task_summary", "task_type", "relevant_memory"],
    })
    write_json(compat / "compaction_report.json", {"version": 1, "status": "not_initialized"})
    write_json(compat / "packet_budget_status.json", {"version": 1, "status": "not_initialized"})
    write_json(compat / "task_memory_summary.json", {"version": 1, "status": "not_initialized"})
    write_json(compat / "failure_memory_summary.json", {"version": 1, "status": "not_initialized"})
    write_json(compat / "memory_graph_summary.json", {"version": 1, "status": "not_initialized"})
    for name in ["architecture_learnings.jsonl", "technical_patterns.jsonl", "workflow_learnings.jsonl"]:
        (compat / name).write_text("", encoding="utf-8")

    write_json(repo / ".ai_context_cost" / "packet_budget_status.json", {"version": 1, "status": "not_initialized"})
    (repo / ".ai_context_cost" / "latest_optimization_report.md").write_text("# latest optimization report\n\nstatus: not_initialized\n", encoding="utf-8")
    (repo / ".ai_context_cost" / "optimizer_config.yaml").write_text("budget_target_tokens: 3000\nsoft_limit_tokens: 2600\nhard_limit_tokens: 3200\n", encoding="utf-8")

    write_json(repo / ".ai_context_task_memory" / "task_memory_status.json", {"version": 1, "records_by_task_type": {t: 0 for t in TASK_TYPES}})
    write_json(repo / ".ai_context_task_memory" / "task_taxonomy.json", {"version": 1, "task_types": TASK_TYPES})
    (repo / ".ai_context_task_memory" / "task_resolution_rules.md").write_text("# task resolution rules\n\nStarter scaffold.\n", encoding="utf-8")

    write_json(repo / ".ai_context_failure_memory" / "index.json", {"version": 1, "failures": []})
    write_json(repo / ".ai_context_failure_memory" / "failure_memory_status.json", {"version": 1, "records_total": 0})
    (repo / ".ai_context_failure_memory" / "summaries").mkdir(parents=True, exist_ok=True)
    (repo / ".ai_context_failure_memory" / "summaries" / "common_patterns.md").write_text("# common failure patterns\n\nNone yet.\n", encoding="utf-8")
    (repo / ".ai_context_failure_memory" / "failures").mkdir(parents=True, exist_ok=True)

    write_json(repo / ".ai_context_memory_graph" / "graph_status.json", {"version": 1, "nodes_total": 0, "edges_total": 0})
    for sub in ["nodes", "edges", "indexes", "snapshots"]:
        (repo / ".ai_context_memory_graph" / sub).mkdir(parents=True, exist_ok=True)
    (repo / ".ai_context_memory_graph" / "snapshots" / "latest_graph_snapshot.json").write_text("{}\n", encoding="utf-8")

    write_json(repo / ".ai_context_library" / "registry.json", {"version": 1, "mods": {}})
    write_json(repo / ".ai_context_library" / "retrieval_status.json", {"version": 1, "retrieval_events": 0})
    (repo / ".ai_context_library" / "REFERENCES_TEMPLATE.md").write_text("# references template\n\n- title:\n- source:\n- tags:\n", encoding="utf-8")
    (repo / ".ai_context_library" / "mods").mkdir(parents=True, exist_ok=True)

    write_json(repo / ".context_metrics" / "weekly_summary.json", {"version": 1, "confidence": "unknown", "tasks_sampled": 0})
    write_json(repo / ".context_metrics" / "baseline_estimates.json", {"version": 1, "status": "not_initialized"})
    (repo / ".context_metrics" / "task_logs.jsonl").write_text("", encoding="utf-8")

    if update_gitignore:
        ensure_gitignore(repo)
    return created


def ensure_gitignore(repo: Path) -> None:
    path = repo / ".gitignore"
    desired = [
        ".ai_context_engine/",
        ".ai_context_memory/",
        ".ai_context_cost/",
        ".ai_context_task_memory/",
        ".ai_context_failure_memory/",
        ".ai_context_memory_graph/",
        ".ai_context_library/",
        ".context_metrics/",
        "CONTEXT_SAVINGS.md",
    ]
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    merged = list(existing)
    for entry in desired:
        if entry not in merged:
            merged.append(entry)
    path.write_text("\n".join(merged).rstrip() + "\n", encoding="utf-8")
