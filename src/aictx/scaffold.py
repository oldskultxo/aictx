from __future__ import annotations

from pathlib import Path
import json

from .portability import (
    detect_portable_continuity_from_gitignore,
    load_portability_state,
    render_aictx_gitignore_block,
    remove_unmanaged_aictx_gitignore_lines,
    strip_aictx_gitignore_block,
    write_portability_state,
)
from .runtime_versioning import compat_version_payload
from .state import REPO_CONTINUITY_DIR, REPO_ENGINE_DIR, REPO_MAP_DIR, REPO_MEMORY_DIR, REPO_METRICS_DIR, REPO_STATE_PATH, REPO_STRATEGY_MEMORY_DIR, REPO_TASKS_DIR, REPO_TASK_THREADS_DIR, write_json

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def ensure_file(path: Path, content: str = "") -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return False
    path.write_text(content, encoding="utf-8")
    return True


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _deep_merge(base: dict, overlay: dict) -> dict:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def ensure_repo_user_preferences(repo: Path) -> Path:
    target = repo / REPO_MEMORY_DIR / "user_preferences.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    template_payload = _read_json(TEMPLATES_DIR / "user_preferences.json")
    current_payload = _read_json(target)
    merged = _deep_merge(template_payload, current_payload)
    target.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def _memory_source_root(repo: Path) -> Path:
    return repo / REPO_MEMORY_DIR / "source"


def _rewrite_source_refs(value):
    if isinstance(value, dict):
        return {key: _rewrite_source_refs(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_rewrite_source_refs(item) for item in value]
    if isinstance(value, str):
        if value.startswith(".aictx/memory/source/"):
            return value
        if value.startswith("projects/") or value.startswith("common/"):
            return f".aictx/memory/source/{value}"
    return value


def _copy_text_if_missing(source: Path, target: Path, created: list[str]) -> None:
    if target.exists() or not source.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    created.append(str(target))


def _write_json_if_missing(path: Path, payload: dict, created: list[str]) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    created.append(str(path))


def _write_text_if_missing(path: Path, content: str, created: list[str]) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    created.append(str(path))


def ensure_repo_memory_sources(repo: Path) -> list[str]:
    created: list[str] = []
    source_root = _memory_source_root(repo)
    common_dir = source_root / "common"
    projects_dir = source_root / "projects" / repo.name
    for path in [source_root, common_dir, projects_dir]:
        existed = path.exists()
        path.mkdir(parents=True, exist_ok=True)
        if not existed:
            created.append(str(path))

    common_ref = ".aictx/memory/source/common/user_working_preferences.md"
    project_ref = f".aictx/memory/source/projects/{repo.name}/overview.md"
    _write_text_if_missing(
        common_dir / "user_working_preferences.md",
        (
            "---\n"
            "priority: important\n"
            "confidence: high\n"
            "last_verified: 2026-04-23\n"
            "tags: workflow, preferences, user\n"
            "---\n\n"
            "# common: user working preferences\n\n"
            "- `.aictx/memory/user_preferences.json` is the canonical source of default user preferences.\n"
            "- Explicit user instructions always override persisted defaults.\n"
        ),
        created,
    )
    _write_text_if_missing(
        projects_dir / "overview.md",
        (
            "---\n"
            "priority: important\n"
            "confidence: medium\n"
            "last_verified: 2026-04-23\n"
            f"tags: {repo.name}, project, bootstrap\n"
            "---\n\n"
            f"# {repo.name}: project overview\n\n"
            "- Capture durable project rules and architecture notes here.\n"
            "- Prefer editing `.aictx/memory/source/**` for reusable project knowledge.\n"
        ),
        created,
    )
    _write_json_if_missing(
        source_root / "index.json",
        {
            "version": 2,
            "lookup_order": ["projects", "common"],
            "projects": {
                repo.name: {
                    "summary": f"Project-scoped knowledge for {repo.name}.",
                    "subprojects": {"shared": [project_ref]},
                }
            },
            "common": [common_ref],
            "tags": {"preferences": [common_ref], repo.name: [project_ref]},
        },
        created,
    )
    _write_json_if_missing(source_root / "symptoms.json", {"version": 2, "symptoms": {}}, created)
    _write_text_if_missing(
        source_root / "protocol.md",
        (
            "# aictx protocol\n\n"
            "Purpose:\n"
            "- keep durable, low-cost project knowledge inside `.aictx/`\n"
            "- treat `.aictx/memory/source/` as the editable knowledge source layer\n"
            "- keep `.aictx/boot`, `.aictx/store`, and `.aictx/indexes` as derived runtime layers\n"
        ),
        created,
    )
    return created

def _resolve_portable_continuity(repo: Path, portable_continuity: bool | None) -> bool:
    if portable_continuity is not None:
        return portable_continuity
    existing_payload = load_portability_state(repo)
    existing_enabled = existing_payload.get("enabled") if isinstance(existing_payload, dict) else None
    if isinstance(existing_enabled, bool):
        return existing_enabled
    detected = detect_portable_continuity_from_gitignore(repo)
    return bool(detected) if detected is not None else False


def init_repo_scaffold(repo: Path, update_gitignore: bool = True, *, portable_continuity: bool | None = None) -> list[str]:
    created: list[str] = []

    engine_dir = repo / REPO_ENGINE_DIR
    metrics_dir = repo / REPO_METRICS_DIR
    strategy_dir = repo / REPO_STRATEGY_MEMORY_DIR
    continuity_dir = repo / REPO_CONTINUITY_DIR
    tasks_dir = repo / REPO_TASKS_DIR
    task_threads_dir = repo / REPO_TASK_THREADS_DIR
    for path in [engine_dir, metrics_dir, strategy_dir, continuity_dir, tasks_dir, task_threads_dir]:
        existed = path.exists()
        path.mkdir(parents=True, exist_ok=True)
        if not existed:
            created.append(str(path))

    prefs_path = repo / REPO_MEMORY_DIR / "user_preferences.json"
    prefs_existed = prefs_path.exists()
    ensure_repo_user_preferences(repo)
    if not prefs_existed:
        created.append(str(prefs_path))
    created.extend(path for path in ensure_repo_memory_sources(repo) if path not in created)

    write_json(
        repo / REPO_STATE_PATH,
        {
            "engine_id": "aictx",
            "engine_name": "aictx",
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
        repo / ".aictx" / "failure_memory" / "failure_patterns.jsonl",
    ]:
        if ensure_file(path):
            created.append(str(path))

    resolved_portable_continuity = _resolve_portable_continuity(repo, portable_continuity)
    portability_path = repo / ".aictx" / "continuity" / "portability.json"
    portability_existed = portability_path.exists()
    write_portability_state(repo, enabled=resolved_portable_continuity)
    if not portability_existed:
        created.append(str(portability_path))

    if update_gitignore:
        ensure_gitignore(repo, portable_continuity=resolved_portable_continuity)
    return created


def ensure_repomap_scaffold(repo: Path) -> list[str]:
    created: list[str] = []
    repo_map_dir = repo / REPO_MAP_DIR
    existed = repo_map_dir.exists()
    repo_map_dir.mkdir(parents=True, exist_ok=True)
    if not existed:
        created.append(str(repo_map_dir))
    return created


def ensure_gitignore(repo: Path, *, portable_continuity: bool = False) -> None:
    path = repo / ".gitignore"
    existing_text = path.read_text(encoding="utf-8") if path.exists() else ""
    cleaned = strip_aictx_gitignore_block(existing_text)
    cleaned = remove_unmanaged_aictx_gitignore_lines(cleaned)
    lines = cleaned.splitlines() if cleaned else []
    if ".DS_Store" not in lines:
        lines.append(".DS_Store")
    cleaned = "\n".join(lines).rstrip()
    block = render_aictx_gitignore_block(portable_continuity=portable_continuity)
    final = "\n".join(part for part in [cleaned, block.rstrip()] if part).rstrip() + "\n"
    path.write_text(final, encoding="utf-8")
