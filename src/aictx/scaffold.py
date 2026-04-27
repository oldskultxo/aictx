from __future__ import annotations

from pathlib import Path
import json

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
    legacy_root_payload = _read_json(repo / "user_preferences.json")
    current_payload = _read_json(target)
    merged = _deep_merge(template_payload, legacy_root_payload)
    merged = _deep_merge(merged, current_payload)
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

    legacy_common = repo / "common" / "user_working_preferences.md"
    target_common = common_dir / "user_working_preferences.md"
    if legacy_common.exists():
        _copy_text_if_missing(legacy_common, target_common, created)
    else:
        _write_text_if_missing(
            target_common,
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

    copied_project_notes = False
    legacy_projects_root = repo / "projects"
    if legacy_projects_root.exists():
        for source in sorted(legacy_projects_root.rglob("*.md")):
            relative = source.relative_to(legacy_projects_root)
            target = source_root / "projects" / relative
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
                created.append(str(target))
            copied_project_notes = True
    if not copied_project_notes:
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

    legacy_index = repo / "index.json"
    if legacy_index.exists():
        payload = _rewrite_source_refs(_read_json(legacy_index))
    else:
        common_ref = ".aictx/memory/source/common/user_working_preferences.md"
        project_ref = f".aictx/memory/source/projects/{repo.name}/overview.md"
        payload = {
            "version": 1,
            "lookup_order": ["projects", "common"],
            "projects": {
                repo.name: {
                    "summary": f"Project-scoped knowledge for {repo.name}.",
                    "subprojects": {"shared": [project_ref]},
                }
            },
            "common": [common_ref],
            "tags": {
                "preferences": [common_ref],
                repo.name: [project_ref],
            },
        }
    _write_json_if_missing(source_root / "index.json", payload, created)

    legacy_symptoms = repo / "symptoms.json"
    if legacy_symptoms.exists():
        symptoms_payload = _rewrite_source_refs(_read_json(legacy_symptoms))
    else:
        symptoms_payload = {"version": 1, "symptoms": {}}
    _write_json_if_missing(source_root / "symptoms.json", symptoms_payload, created)

    legacy_protocol = repo / "protocol.md"
    if legacy_protocol.exists():
        protocol_text = (
            legacy_protocol.read_text(encoding="utf-8")
            .replace(".aictx_memory/derived_boot_summary.json", ".aictx/boot/boot_summary.json")
            .replace(".aictx_memory/user_preferences.json", ".aictx/memory/user_preferences.json")
            .replace(".aictx_*", ".aictx/")
        )
    else:
        protocol_text = (
            "# aictx protocol\n\n"
            "Purpose:\n"
            "- keep durable, low-cost project knowledge inside `.aictx/`\n"
            "- treat `.aictx/memory/source/` as the editable knowledge source layer\n"
            "- keep `.aictx/boot`, `.aictx/store`, and `.aictx/indexes` as derived runtime layers\n"
        )
    _write_text_if_missing(source_root / "protocol.md", protocol_text, created)

    return created


def init_repo_scaffold(repo: Path, update_gitignore: bool = True) -> list[str]:
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

    if update_gitignore:
        ensure_gitignore(repo)
    return created


def ensure_repomap_scaffold(repo: Path) -> list[str]:
    created: list[str] = []
    repo_map_dir = repo / REPO_MAP_DIR
    existed = repo_map_dir.exists()
    repo_map_dir.mkdir(parents=True, exist_ok=True)
    if not existed:
        created.append(str(repo_map_dir))
    return created


def ensure_gitignore(repo: Path) -> None:
    path = repo / ".gitignore"
    desired = [
        ".DS_Store",
        ".aictx/",
    ]
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    merged = list(existing)
    for entry in desired:
        if entry not in merged:
            merged.append(entry)
    path.write_text("\n".join(merged).rstrip() + "\n", encoding="utf-8")
