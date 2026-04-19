from __future__ import annotations

import json
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

from .adapters import install_repo_adapters
from .runtime_versioning import compat_version_payload
from .state import (
    REPO_COST_DIR,
    REPO_DIRS,
    REPO_FAILURE_MEMORY_DIR,
    REPO_LIBRARY_DIR,
    REPO_MEMORY_DIR,
    REPO_MEMORY_GRAPH_DIR,
    REPO_METRICS_DIR,
    REPO_STATE_PATH,
    REPO_TASK_MEMORY_DIR,
    TASK_TYPES,
    write_json,
)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_template_json(name: str) -> dict:
    return json.loads((TEMPLATES_DIR / name).read_text(encoding="utf-8"))


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
            "load .ai_context_engine/memory/derived_boot_summary.json",
            "load .ai_context_engine/memory/user_preferences.json",
            "load .ai_context_engine/memory/project_bootstrap.json",
            "load smallest relevant local note",
            "apply preferences as runtime defaults",
        ],
        "default_behavior": {
            "memory_first": True,
            "fallback_to_standard_repo_analysis": True,
            "explicit_user_override_wins": True,
        },
    }


def canonical_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def merge_tree(source: Path, target: Path) -> None:
    if not source.exists():
        return
    target.mkdir(parents=True, exist_ok=True)
    for child in list(source.iterdir()):
        destination = target / child.name
        if child.is_dir():
            merge_tree(child, destination)
            if child.exists():
                child.rmdir()
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                shutil.move(str(child), str(destination))
            else:
                child.unlink()


def migrate_legacy_repo_layout(repo: Path) -> list[str]:
    if repo.resolve() == canonical_repo_root():
        return []
    migrated: list[str] = []
    mapping = {
        ".ai_context_memory": REPO_MEMORY_DIR,
        ".ai_context_cost": REPO_COST_DIR,
        ".ai_context_task_memory": REPO_TASK_MEMORY_DIR,
        ".ai_context_failure_memory": REPO_FAILURE_MEMORY_DIR,
        ".ai_context_memory_graph": REPO_MEMORY_GRAPH_DIR,
        ".ai_context_library": REPO_LIBRARY_DIR,
        ".context_metrics": REPO_METRICS_DIR,
    }
    for legacy_name, canonical_rel in mapping.items():
        source = repo / legacy_name
        if not source.exists():
            continue
        target = repo / canonical_rel
        merge_tree(source, target)
        if source.exists():
            source.rmdir()
        migrated.append(f"{source} -> {target}")
    return migrated


def init_repo_scaffold(repo: Path, update_gitignore: bool = True) -> list[str]:
    created = migrate_legacy_repo_layout(repo)
    repo_name = repo.name
    for rel in REPO_DIRS:
        path = repo / rel
        path.mkdir(parents=True, exist_ok=True)
        if str(path) not in created:
            created.append(str(path))

    for task_type in TASK_TYPES:
        (repo / REPO_TASK_MEMORY_DIR / task_type).mkdir(parents=True, exist_ok=True)

    write_json(
        repo / REPO_STATE_PATH,
        {
            "engine_id": "ai_context_engine",
            "engine_name": "ai_context_engine",
            "adapter_id": "generic",
            "adapter_family": "multi_llm",
            "provider_capabilities": ["chat_completion", "tool_use", "structured_output", "long_context"],
            "installed_at": now_iso(),
            **compat_version_payload(),
            "repo_root": str(repo),
        },
    )

    compat = repo / REPO_MEMORY_DIR
    (compat / "README.md").write_text(
        "# .ai_context_engine/memory\n\nGenerated local bootstrap layer for AI agents.\n",
        encoding="utf-8",
    )
    write_json(
        compat / "manifest.json",
        {
            "version": 1,
            "project": repo_name,
            "artifacts": {
                "derived_boot_summary": "derived_boot_summary.json",
                "user_preferences": "user_preferences.json",
                "project_bootstrap": "project_bootstrap.json",
            },
        },
    )
    write_json(compat / "derived_boot_summary.json", bootstrap_payload(repo, repo_name))
    write_json(
        compat / "project_bootstrap.json",
        {
            "version": 1,
            "project": repo_name,
            "repo_root": str(repo),
            "engine_name": "ai_context_engine",
            "lookup_order": ["repo", "workspace", "global"],
        },
    )
    write_json(compat / "user_preferences.json", load_template_json("user_preferences.json"))

    write_json(repo / REPO_COST_DIR / "packet_budget_status.json", {"version": 1, "status": "not_initialized"})
    (repo / REPO_COST_DIR / "latest_optimization_report.md").write_text(
        "# latest optimization report\n\nstatus: not_initialized\n",
        encoding="utf-8",
    )
    (repo / REPO_COST_DIR / "optimizer_config.yaml").write_text(
        "budget_target_tokens: 3000\nsoft_limit_tokens: 2600\nhard_limit_tokens: 3200\n",
        encoding="utf-8",
    )

    write_json(repo / REPO_TASK_MEMORY_DIR / "task_memory_status.json", {"version": 1, **compat_version_payload(), "records_by_task_type": {t: 0 for t in TASK_TYPES}})
    write_json(repo / REPO_TASK_MEMORY_DIR / "task_taxonomy.json", {"version": 1, **compat_version_payload(), "task_types": TASK_TYPES})
    (repo / REPO_TASK_MEMORY_DIR / "task_resolution_rules.md").write_text("# task resolution rules\n\nStarter scaffold.\n", encoding="utf-8")

    write_json(repo / REPO_FAILURE_MEMORY_DIR / "index.json", {"version": 1, "failures": []})
    write_json(repo / REPO_FAILURE_MEMORY_DIR / "failure_memory_status.json", {"version": 1, "records_total": 0})
    (repo / REPO_FAILURE_MEMORY_DIR / "summaries").mkdir(parents=True, exist_ok=True)
    (repo / REPO_FAILURE_MEMORY_DIR / "summaries" / "common_patterns.md").write_text("# common failure patterns\n\nNone yet.\n", encoding="utf-8")
    (repo / REPO_FAILURE_MEMORY_DIR / "failures").mkdir(parents=True, exist_ok=True)

    write_json(repo / REPO_MEMORY_GRAPH_DIR / "graph_status.json", {"version": 1, **compat_version_payload(), "nodes_total": 0, "edges_total": 0})
    for sub in ["nodes", "edges", "indexes", "snapshots"]:
        (repo / REPO_MEMORY_GRAPH_DIR / sub).mkdir(parents=True, exist_ok=True)
    (repo / REPO_MEMORY_GRAPH_DIR / "snapshots" / "latest_graph_snapshot.json").write_text("{}\n", encoding="utf-8")

    write_json(repo / REPO_LIBRARY_DIR / "registry.json", {"version": 1, "mods": {}})
    write_json(repo / REPO_LIBRARY_DIR / "retrieval_status.json", {"version": 1, **compat_version_payload(), "retrieval_events": 0})
    (repo / REPO_LIBRARY_DIR / "REFERENCES_TEMPLATE.md").write_text("# references template\n\n- title:\n- source:\n- tags:\n", encoding="utf-8")
    (repo / REPO_LIBRARY_DIR / "mods").mkdir(parents=True, exist_ok=True)

    write_json(
        repo / REPO_METRICS_DIR / "weekly_summary.json",
        {
            "version": 3,
            "generated_at": "not_initialized",
            "confidence": "low",
            "tasks_sampled": 0,
            "repeated_tasks": 0,
            "phase_events_sampled": 0,
            "telemetry_granularity": "task_plus_phase",
            "evidence_status": "unknown",
            "measurement_basis": "execution_logs",
            "metrics": {
                "observed": {
                    "tasks_sampled": 0,
                    "repeated_tasks": 0,
                    "phase_events_sampled": 0,
                    "top_recorded_phases": [],
                }
            },
        },
    )
    (repo / REPO_METRICS_DIR / "task_logs.jsonl").write_text("", encoding="utf-8")

    if update_gitignore:
        ensure_gitignore(repo)
    for path in install_repo_adapters(repo):
        if str(path) not in created:
            created.append(str(path))
    return created


def ensure_gitignore(repo: Path) -> None:
    path = repo / ".gitignore"
    desired = [
        ".DS_Store",
        ".ai_context_engine/",
        "CONTEXT_SAVINGS.md",
    ]
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    merged = list(existing)
    for entry in desired:
        if entry not in merged:
            merged.append(entry)
    path.write_text("\n".join(merged).rstrip() + "\n", encoding="utf-8")
