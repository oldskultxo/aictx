from __future__ import annotations

from pathlib import Path

from .runtime_versioning import compat_version_payload
from .state import REPO_ENGINE_DIR, REPO_METRICS_DIR, REPO_STATE_PATH, REPO_STRATEGY_MEMORY_DIR, write_json

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def ensure_file(path: Path, content: str = "") -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return False
    path.write_text(content, encoding="utf-8")
    return True


def init_repo_scaffold(repo: Path, update_gitignore: bool = True) -> list[str]:
    created: list[str] = []

    engine_dir = repo / REPO_ENGINE_DIR
    metrics_dir = repo / REPO_METRICS_DIR
    strategy_dir = repo / REPO_STRATEGY_MEMORY_DIR
    for path in [engine_dir, metrics_dir, strategy_dir]:
        existed = path.exists()
        path.mkdir(parents=True, exist_ok=True)
        if not existed:
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

    for path in [
        strategy_dir / "strategies.jsonl",
        metrics_dir / "execution_logs.jsonl",
        metrics_dir / "execution_feedback.jsonl",
        repo / ".ai_context_engine" / "failure_memory" / "failure_patterns.jsonl",
    ]:
        if ensure_file(path):
            created.append(str(path))

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
