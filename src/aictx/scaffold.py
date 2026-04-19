from __future__ import annotations

from pathlib import Path

from .runtime_versioning import compat_version_payload
from .state import REPO_COST_DIR, REPO_ENGINE_DIR, REPO_METRICS_DIR, REPO_STATE_PATH, REPO_STRATEGY_MEMORY_DIR, write_json

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def migrate_legacy_repo_layout(repo: Path) -> list[str]:
    cleaned: list[str] = []
    for legacy_name in [
        ".ai_context_memory",
        ".ai_context_cost",
        ".ai_context_task_memory",
        ".ai_context_failure_memory",
        ".ai_context_memory_graph",
        ".ai_context_library",
        ".context_metrics",
    ]:
        source = repo / legacy_name
        if not source.exists():
            continue
        if source.is_dir():
            for child in sorted(source.rglob("*"), reverse=True):
                if child.is_file() or child.is_symlink():
                    child.unlink()
                elif child.is_dir():
                    child.rmdir()
            source.rmdir()
        else:
            source.unlink()
        cleaned.append(str(source))
    return cleaned


def init_repo_scaffold(repo: Path, update_gitignore: bool = True) -> list[str]:
    created = migrate_legacy_repo_layout(repo)

    engine_dir = repo / REPO_ENGINE_DIR
    metrics_dir = repo / REPO_METRICS_DIR
    strategy_dir = repo / REPO_STRATEGY_MEMORY_DIR
    cost_dir = repo / REPO_COST_DIR
    for path in [engine_dir, metrics_dir, strategy_dir, cost_dir]:
        path.mkdir(parents=True, exist_ok=True)
        if str(path) not in created:
            created.append(str(path))

    write_json(
        repo / REPO_STATE_PATH,
        {
            "engine_id": "ai_context_engine",
            "engine_name": "ai_context_engine",
            "adapter_id": "generic",
            "adapter_family": "multi_llm",
            "provider_capabilities": ["chat_completion", "tool_use", "structured_output", "long_context"],
            **compat_version_payload(),
            "repo_root": str(repo),
        },
    )

    (strategy_dir / "strategies.jsonl").write_text("", encoding="utf-8")
    (metrics_dir / "execution_logs.jsonl").write_text("", encoding="utf-8")
    (metrics_dir / "execution_feedback.jsonl").write_text("", encoding="utf-8")

    if update_gitignore:
        ensure_gitignore(repo)
    return created


def ensure_gitignore(repo: Path) -> None:
    path = repo / ".gitignore"
    desired = [
        ".DS_Store",
        ".ai_context_engine/",
    ]
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    merged = list(existing)
    for entry in desired:
        if entry not in merged:
            merged.append(entry)
    path.write_text("\n".join(merged).rstrip() + "\n", encoding="utf-8")
