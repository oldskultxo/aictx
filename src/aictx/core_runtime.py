#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from .runtime_contract import (
    communication_policy_from_defaults,
    normalize_communication_layer,
    normalize_communication_mode,
    resolve_effective_preferences,
    runtime_consistency_report,
)
from .runtime_versioning import (
    compat_version_payload,
    current_engine_capability_version as runtime_current_engine_capability_version,
    current_installed_version as runtime_current_installed_version,
)

BASE = Path(__file__).resolve().parents[2]
BOOT_DIR = BASE / "boot"
STORE_DIR = BASE / "store"
PROJECT_RECORDS_DIR = STORE_DIR / "project_records"
NOTES_STORE_DIR = STORE_DIR / "notes"
INDEXES_DIR = BASE / "indexes"
DELTA_DIR = BASE / "delta"
LAST_PACKETS_DIR = DELTA_DIR / "last_packets"
MIGRATION_DIR = BASE / "migration"
LOGS_DIR = BASE / "logs"
ENGINE_STATE_DIR = BASE / ".ai_context_engine"
COST_DIR = ENGINE_STATE_DIR / "cost"
TASK_MEMORY_DIR = ENGINE_STATE_DIR / "task_memory"
FAILURE_MEMORY_DIR = ENGINE_STATE_DIR / "failure_memory"
MEMORY_GRAPH_DIR = ENGINE_STATE_DIR / "memory_graph"
CONTEXT_METRICS_DIR = ENGINE_STATE_DIR / "metrics"
LIBRARY_DIR = ENGINE_STATE_DIR / "library"

ROOT_INDEX_PATH = BASE / "index.json"
ROOT_PREFS_PATH = BASE / "user_preferences.json"
ROOT_FAST_LOOKUP_PATH = BASE / "fast_lookup.json"
ROOT_SYMPTOMS_PATH = BASE / "symptoms.json"
ROOT_CHANGE_JOURNAL_PATH = BASE / "change_journal.md"

BOOT_SUMMARY_PATH = BOOT_DIR / "boot_summary.json"
BOOT_DEFAULTS_PATH = BOOT_DIR / "user_defaults.json"
BOOT_PROJECTS_PATH = BOOT_DIR / "project_registry.json"
BOOT_MODEL_ROUTING_PATH = BOOT_DIR / "model_routing.json"

STORE_GLOBAL_RECORDS_PATH = STORE_DIR / "global_records.jsonl"
STORE_USER_PREFERENCES_PATH = STORE_DIR / "user_preferences.jsonl"

INDEX_BY_TAG_PATH = INDEXES_DIR / "by_tag.json"
INDEX_BY_TYPE_PATH = INDEXES_DIR / "by_type.json"
INDEX_BY_PROJECT_PATH = INDEXES_DIR / "by_project.json"
INDEX_BY_PATH_PATH = INDEXES_DIR / "by_path.json"
INDEX_BY_SYMPTOM_PATH = INDEXES_DIR / "by_symptom.json"
INDEX_BY_PREFERENCE_PATH = INDEXES_DIR / "by_preference.json"
INDEX_RECENT_PATH = INDEXES_DIR / "recent_learnings.json"

DELTA_SCHEMA_PATH = DELTA_DIR / "task_packet_schema.json"
MIGRATION_REPORT_PATH = MIGRATION_DIR / "legacy_memory_migration_report.md"
MIGRATION_IMPORT_MAP_PATH = MIGRATION_DIR / "legacy_memory_import_map.json"
LOGS_CHANGE_JOURNAL_PATH = LOGS_DIR / "change_journal.md"
LOGS_MAINTENANCE_PATH = LOGS_DIR / "maintenance_log.md"
REPO_COMPAT_DIRNAME = ".ai_context_engine/memory"
ROOT_COMPACTION_REPORT_PATH = BASE / "compaction_report.json"
COST_CONFIG_PATH = COST_DIR / "optimizer_config.yaml"
COST_RULES_PATH = COST_DIR / "cost_estimation_rules.md"
COST_LATEST_REPORT_PATH = COST_DIR / "latest_optimization_report.md"
COST_STATUS_PATH = COST_DIR / "packet_budget_status.json"
COST_HISTORY_PATH = COST_DIR / "optimization_history.jsonl"
TASK_MEMORY_STATUS_PATH = TASK_MEMORY_DIR / "task_memory_status.json"
TASK_MEMORY_RULES_PATH = TASK_MEMORY_DIR / "task_resolution_rules.md"
TASK_MEMORY_HISTORY_PATH = TASK_MEMORY_DIR / "task_memory_history.jsonl"
TASK_MEMORY_TAXONOMY_PATH = TASK_MEMORY_DIR / "task_taxonomy.json"
FAILURE_MEMORY_INDEX_PATH = FAILURE_MEMORY_DIR / "index.json"
FAILURE_MEMORY_STATUS_PATH = FAILURE_MEMORY_DIR / "failure_memory_status.json"
FAILURE_MEMORY_SUMMARY_PATH = FAILURE_MEMORY_DIR / "summaries" / "common_patterns.md"
FAILURE_MEMORY_RECORDS_DIR = FAILURE_MEMORY_DIR / "failures"
MEMORY_GRAPH_NODES_PATH = MEMORY_GRAPH_DIR / "nodes" / "nodes.jsonl"
MEMORY_GRAPH_EDGES_PATH = MEMORY_GRAPH_DIR / "edges" / "edges.jsonl"
MEMORY_GRAPH_STATUS_PATH = MEMORY_GRAPH_DIR / "graph_status.json"
MEMORY_GRAPH_LABEL_INDEX_PATH = MEMORY_GRAPH_DIR / "indexes" / "by_label.json"
MEMORY_GRAPH_TYPE_INDEX_PATH = MEMORY_GRAPH_DIR / "indexes" / "by_type.json"
MEMORY_GRAPH_RELATION_INDEX_PATH = MEMORY_GRAPH_DIR / "indexes" / "by_relation.json"
MEMORY_GRAPH_SNAPSHOT_PATH = MEMORY_GRAPH_DIR / "snapshots" / "latest_graph_snapshot.json"
CONTEXT_TASK_LOGS_PATH = CONTEXT_METRICS_DIR / "task_logs.jsonl"
CONTEXT_WEEKLY_SUMMARY_PATH = CONTEXT_METRICS_DIR / "weekly_summary.json"
CONTEXT_BASELINE_PATH = CONTEXT_METRICS_DIR / "baseline_estimates.json"
ENGINE_STATE_PATH = ENGINE_STATE_DIR / "state.json"
LIBRARY_REGISTRY_PATH = LIBRARY_DIR / "registry.json"
LIBRARY_RETRIEVAL_STATUS_PATH = LIBRARY_DIR / "retrieval_status.json"

DEFAULT_AGENT_ADAPTER = "generic"
DEFAULT_ADAPTER_ID = "generic"
DEFAULT_ADAPTER_FAMILY = "multi_llm"
DEFAULT_PROVIDER_CAPABILITIES = [
    "chat_completion",
    "tool_use",
    "structured_output",
    "long_context",
]


NOTE_SKIP_NAMES = {
    "README.md",
    "protocol.md",
    "change_journal.md",
    "CONTEXT_HANDOFF.md",
    "note_template.md",
}

RECORD_TYPES = [
    "user_preference",
    "project_fact",
    "architecture_decision",
    "workflow_rule",
    "debugging_pattern",
    "failure_mode",
    "validation_recipe",
    "task_pattern",
    "naming_convention",
    "constraint",
    "open_question",
    "staleness_warning",
]

CURRENT_ENGINE_CAPABILITY_VERSION = runtime_current_engine_capability_version()
CURRENT_ENGINE_ITERATION = CURRENT_ENGINE_CAPABILITY_VERSION
MTIME_TOLERANCE_SECONDS = 0.5
SUPPORTED_INBOX_EXTENSIONS = {".md", ".txt", ".html", ".htm", ".pdf"}
SUPPORTED_REFERENCED_EXTENSIONS = SUPPORTED_INBOX_EXTENSIONS | {".sql", ".xml", ".json", ".yaml", ".yml", ".py", ".csv"}
REMOTE_DECLARED_TYPES = {"auto", "html", "pdf", "md", "txt"}
REMOTE_TYPE_EXTENSIONS = {"html": ".html", "pdf": ".pdf", "md": ".md", "txt": ".txt"}



COMPAT_ARCHITECTURE_TYPES = {"architecture_decision"}
COMPAT_WORKFLOW_TYPES = {"workflow_rule"}
COMPAT_TECHNICAL_TYPES = {
    "project_fact",
    "debugging_pattern",
    "failure_mode",
    "validation_recipe",
    "task_pattern",
    "naming_convention",
    "constraint",
    "open_question",
}
TASK_TYPES = [
    "bug_fixing",
    "refactoring",
    "testing",
    "performance",
    "architecture",
    "feature_work",
    "unknown",
]
TASK_TYPE_KEYWORDS = {
    "bug_fixing": ["bug", "fix", "error", "crash", "regression", "broken", "failure", "debug", "falla"],
    "refactoring": ["refactor", "rename", "cleanup", "modular", "restructure", "reorganize", "split"],
    "testing": ["test", "testing", "coverage", "assert", "pytest", "spec", "validation", "smoke", "verify"],
    "performance": ["performance", "latency", "slow", "optimiz", "token", "cost", "hotspot", "throughput", "bottleneck"],
    "architecture": ["architecture", "protocol", "migration", "system", "boundary", "cross-system", "design", "data flow", "subsystem"],
    "feature_work": ["feature", "implement", "add", "introduce", "support", "workflow", "behavior", "ux", "endpoint"],
}
LEGACY_TASK_TYPE_ALIASES = {
    "tests": "testing",
    "general": "unknown",
}
GRAPH_NODE_TYPES = {
    "file",
    "module",
    "task_type",
    "memory_entry",
    "failure_pattern",
    "solution",
    "architecture_decision",
    "repository_area",
    "concept",
}
GRAPH_RELATIONS = {
    "relates_to",
    "affects",
    "caused",
    "fixed_by",
    "located_in",
    "referenced_by",
    "associated_with",
    "belongs_to_task_type",
    "derived_from",
}
FAILURE_CATEGORIES = [
    "build_failure",
    "test_failure",
    "runtime_failure",
    "config_failure",
    "environment_failure",
    "migration_failure",
    "refactor_regression",
    "tooling_failure",
    "unknown",
]


def ensure_dirs() -> None:
    for path in [
        BOOT_DIR,
        STORE_DIR,
        PROJECT_RECORDS_DIR,
        NOTES_STORE_DIR / "common",
        NOTES_STORE_DIR / "projects",
        INDEXES_DIR,
        LAST_PACKETS_DIR,
        MIGRATION_DIR,
        LOGS_DIR,
        COST_DIR,
        TASK_MEMORY_DIR,
        FAILURE_MEMORY_DIR,
        FAILURE_MEMORY_DIR / "summaries",
        FAILURE_MEMORY_RECORDS_DIR,
        MEMORY_GRAPH_DIR,
        MEMORY_GRAPH_DIR / "nodes",
        MEMORY_GRAPH_DIR / "edges",
        MEMORY_GRAPH_DIR / "indexes",
        MEMORY_GRAPH_DIR / "snapshots",
        CONTEXT_METRICS_DIR,
        ENGINE_STATE_DIR,
        LIBRARY_DIR,
        LIBRARY_DIR / "mods",
        BASE / "scripts",
        BASE / "bin",
    ]:
        path.mkdir(parents=True, exist_ok=True)
    for task_type in TASK_TYPES:
        (TASK_MEMORY_DIR / task_type).mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text())


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def write_text(path: Path, content: str) -> None:
    from .runtime_io import write_text as _impl
    return _impl(path, content)


def now_iso() -> str:
    from .runtime_io import now_iso as _impl
    return _impl()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    from .runtime_io import read_jsonl as _impl
    return _impl(path)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    from .runtime_io import write_jsonl as _impl
    return _impl(path, rows)


def repo_root_for_project(project: str) -> Path | None:
    if not project:
        return None
    candidate = BASE.parent / project
    return candidate if candidate.exists() else None


def ensure_repo_compat_readme(compat_dir: Path) -> None:
    from .runtime_compat import ensure_repo_compat_readme as _impl
    return _impl(compat_dir)



def slugify(text: str) -> str:
    from .runtime_io import slugify as _impl
    return _impl(text)


def current_engine_iteration() -> int:
    return current_engine_capability_version()


def current_engine_capability_version() -> int:
    return runtime_current_engine_capability_version()


def current_installed_version() -> str:
    return runtime_current_installed_version()


def default_adapter_contract() -> dict[str, Any]:
    return {
        "agent_adapter": DEFAULT_AGENT_ADAPTER,
        "adapter_id": DEFAULT_ADAPTER_ID,
        "adapter_family": DEFAULT_ADAPTER_FAMILY,
        "provider_capabilities": list(DEFAULT_PROVIDER_CAPABILITIES),
    }


def relative_posix(path: Path, root: Path) -> str:
    from .runtime_io import relative_posix as _impl
    return _impl(path, root)


def file_mtime(path: Path) -> float:
    from .runtime_io import file_mtime as _impl
    return _impl(path)


def mtime_changed(previous: Any, current: float) -> bool:
    from .runtime_io import mtime_changed as _impl
    return _impl(previous, current)


def file_md5(path: Path) -> str:
    from .runtime_io import file_md5 as _impl
    return _impl(path)


def load_mod_manifest(root: Path) -> dict[str, Any]:
    from .runtime_knowledge import load_mod_manifest as _impl
    return _impl(root)


def save_mod_manifest(root: Path, manifest: dict[str, Any]) -> None:
    from .runtime_knowledge import save_mod_manifest as _impl
    return _impl(root, manifest)


def default_mod_state() -> dict[str, Any]:
    from .runtime_knowledge import default_mod_state as _impl
    return _impl()


def load_mod_state(root: Path) -> dict[str, Any]:
    from .runtime_knowledge import load_mod_state as _impl
    return _impl(root)


def save_mod_state(root: Path, state: dict[str, Any]) -> None:
    from .runtime_knowledge import save_mod_state as _impl
    return _impl(root, state)


def references_template_text() -> str:
    from .runtime_knowledge import references_template_text as _impl
    return _impl()


def references_stub_text(mod_id: str) -> str:
    from .runtime_knowledge import references_stub_text as _impl
    return _impl(mod_id)


def ensure_references_template() -> None:
    from .runtime_knowledge import ensure_references_template as _impl
    return _impl()


def ensure_remote_manifest(root: Path) -> None:
    from .runtime_knowledge import ensure_remote_manifest as _impl
    return _impl(root)


def should_process_inbox_file(path: Path) -> bool:
    from .runtime_knowledge import should_process_inbox_file as _impl
    return _impl(path)


def resolve_reference_path(raw_path: str) -> Path:
    from .runtime_knowledge import resolve_reference_path as _impl
    return _impl(raw_path)


def parse_references_file(path: Path) -> list[dict[str, Any]]:
    from .runtime_knowledge import parse_references_file as _impl
    return _impl(path)


def sanitize_source_name(value: str, fallback: str = "source") -> str:
    from .runtime_knowledge import sanitize_source_name as _impl
    return _impl(value, fallback=fallback)


def delete_artifact_paths(root: Path, paths: list[str]) -> None:
    from .runtime_knowledge import delete_artifact_paths as _impl
    return _impl(root, paths)


def invalidate_source_artifacts(root: Path, previous: dict[str, Any]) -> None:
    from .runtime_knowledge import invalidate_source_artifacts as _impl
    return _impl(root, previous)


def rebuild_mod_indices(root: Path, state: dict[str, Any]) -> dict[str, list[str]]:
    from .runtime_knowledge import rebuild_mod_indices as _impl
    return _impl(root, state)


def remote_manifest_path(root: Path) -> Path:
    from .runtime_knowledge import remote_manifest_path as _impl
    return _impl(root)


def load_remote_sources_manifest(root: Path) -> dict[str, Any]:
    from .runtime_knowledge import load_remote_sources_manifest as _impl
    return _impl(root)


def save_remote_sources_manifest(root: Path, manifest: dict[str, Any]) -> None:
    from .runtime_knowledge import save_remote_sources_manifest as _impl
    return _impl(root, manifest)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw = text[4:end].splitlines()
    meta: dict[str, Any] = {}
    for line in raw:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if key.strip() == "tags":
            tags = [part.strip() for part in value.split(",") if part.strip()]
            meta[key.strip()] = tags
        else:
            meta[key.strip()] = value
    body = text[end + 5 :].strip()
    return meta, body


def note_paths() -> list[Path]:
    paths = []
    for path in sorted(BASE.rglob("*.md")):
        rel = path.relative_to(BASE).as_posix()
        if rel.startswith(".ai_context_"):
            continue
        if rel.startswith("metrics/"):
            continue
        if rel.startswith("store/") or rel.startswith("migration/") or rel.startswith("logs/"):
            continue
        if path.name in NOTE_SKIP_NAMES:
            continue
        paths.append(path)
    return paths


@dataclass
class NoteInfo:
    path: Path
    rel_path: str
    meta: dict[str, Any]
    body: str
    project: str | None
    subproject: str | None
    scope: str
    tags: list[str]
    record_type: str
    title: str
    task_type: str


def classify_note_type(rel_path: str, title: str, body: str) -> str:
    path_hint = rel_path.lower()
    text = f"{title}\n{body}".lower()
    if "decision" in path_hint or "decision" in text or "architecture" in text:
        return "architecture_decision"
    if "testing" in path_hint or "validation" in text or "preferred checks" in text:
        return "validation_recipe"
    if "debug" in path_hint:
        return "debugging_pattern"
    if "pitfall" in path_hint or "failure" in text:
        return "failure_mode"
    if "preference" in path_hint or "workflow" in text:
        return "workflow_rule"
    if "open_edges" in path_hint or "open question" in text:
        return "open_question"
    if "constraint" in text:
        return "constraint"
    return "project_fact"


def normalize_task_type(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in TASK_TYPES:
        return text
    aliases = {
        "bugfix": "bug_fixing",
        "bug_fix": "bug_fixing",
        "debugging": "bug_fixing",
        "test": "testing",
        "tests": "testing",
        "perf": "performance",
        "feature": "feature_work",
        "general": "unknown",
        "generic": "unknown",
    }
    return aliases.get(text, "unknown")


def classify_task_type_from_text(text: str, tags: list[str] | None = None, record_type: str | None = None) -> str:
    haystack = f"{text} {' '.join(tags or [])} {record_type or ''}".lower()
    if record_type == "architecture_decision":
        return "architecture"
    if record_type == "validation_recipe":
        return "testing"
    if record_type in {"debugging_pattern", "failure_mode"}:
        return "bug_fixing"
    if record_type == "workflow_rule" and any(keyword in haystack for keyword in TASK_TYPE_KEYWORDS["refactoring"]):
        return "refactoring"
    if any(keyword in haystack for keyword in TASK_TYPE_KEYWORDS["architecture"]):
        return "architecture"
    if any(keyword in haystack for keyword in TASK_TYPE_KEYWORDS["performance"]):
        return "performance"
    if any(keyword in haystack for keyword in TASK_TYPE_KEYWORDS["testing"]):
        return "testing"
    if any(keyword in haystack for keyword in TASK_TYPE_KEYWORDS["refactoring"]):
        return "refactoring"
    if any(keyword in haystack for keyword in TASK_TYPE_KEYWORDS["bug_fixing"]):
        return "bug_fixing"
    if any(keyword in haystack for keyword in TASK_TYPE_KEYWORDS["feature_work"]):
        return "feature_work"
    return "unknown"


def task_type_confidence(task: str, task_type: str, touched_files: list[str] | None = None) -> float:
    if task_type == "unknown":
        return 0.35
    haystack = f"{task} {' '.join(touched_files or [])}".lower()
    matches = sum(1 for keyword in TASK_TYPE_KEYWORDS.get(task_type, []) if keyword in haystack)
    return round(min(0.95, 0.45 + matches * 0.12), 2)


def infer_task_signals(task: str, touched_files: list[str] | None = None) -> list[str]:
    signals: list[str] = []
    haystack = task.lower()
    for task_type, keywords in TASK_TYPE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in haystack:
                signals.append(f"text:{task_type}:{keyword}")
    for path in touched_files or []:
        path_l = path.lower()
        if any(part in path_l for part in ["test", "spec", "pytest"]):
            signals.append(f"path:testing:{path}")
        elif any(part in path_l for part in ["perf", "benchmark"]):
            signals.append(f"path:performance:{path}")
        elif any(part in path_l for part in ["arch", "protocol"]):
            signals.append(f"path:architecture:{path}")
    return signals[:8]


def classify_failure_category(text: str) -> str:
    haystack = text.lower()
    if any(keyword in haystack for keyword in ["build", "module resolution", "cannot find module", "compile"]):
        return "build_failure"
    if any(keyword in haystack for keyword in ["test", "assert", "smoke", "validation"]):
        return "test_failure"
    if any(keyword in haystack for keyword in ["runtime", "reload", "render", "reader", "preview", "crash"]):
        return "runtime_failure"
    if any(keyword in haystack for keyword in ["config", "settings", "gitignore"]):
        return "config_failure"
    if any(keyword in haystack for keyword in ["env", "environment", "netlify", "local", "deploy"]):
        return "environment_failure"
    if any(keyword in haystack for keyword in ["migration", "import", "export contract"]):
        return "migration_failure"
    if any(keyword in haystack for keyword in ["refactor", "rename", "moved", "regression"]):
        return "refactor_regression"
    if any(keyword in haystack for keyword in ["tooling", "script", "build-writer", "build-reader"]):
        return "tooling_failure"
    return "unknown"


def summarize_task_memory_rows(task_type: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    locations = sorted({str(path) for row in rows for path in row.get("files_involved", []) if path})[:8]
    patterns = sorted({tag for row in rows for tag in row.get("tags", []) if tag})[:8]
    constraints = [row.get("summary", "") for row in rows if row.get("type") == "constraint" and row.get("summary")][:4]
    validation = [row.get("summary", "") for row in rows if row.get("type") == "validation_recipe" and row.get("summary")][:4]
    mistakes = [row.get("summary", "") for row in rows if row.get("type") in {"failure_mode", "debugging_pattern"} and row.get("summary")][:4]
    compact_summaries = [row.get("summary", "") for row in rows if row.get("summary")][:5]
    return {
        "task_type": task_type,
        "common_locations": locations,
        "patterns": patterns,
        "constraints": constraints,
        "frequent_mistakes": mistakes,
        "preferred_validation": validation,
        "summary_samples": compact_summaries,
    }


def manual_task_memory_records(task_type: str | None = None) -> list[dict[str, Any]]:
    task_types = [normalize_task_type(task_type)] if task_type else TASK_TYPES
    rows: list[dict[str, Any]] = []
    for current in task_types:
        rows.extend(read_jsonl(TASK_MEMORY_DIR / current / "manual_records.jsonl"))
    return [normalize_record(row) for row in rows if row]


def record_task_memory(
    *,
    task_type: str,
    title: str,
    summary: str,
    signals: list[str] | None = None,
    common_locations: list[str] | None = None,
    patterns: list[str] | None = None,
    constraints: list[str] | None = None,
    frequent_mistakes: list[str] | None = None,
    preferred_validation: list[str] | None = None,
    related_files: list[str] | None = None,
    confidence: float = 0.75,
    source: str = "manual",
) -> dict[str, Any]:
    normalized_task_type = normalize_task_type(task_type)
    path = TASK_MEMORY_DIR / normalized_task_type / "manual_records.jsonl"
    rows = read_jsonl(path)
    normalized_summary = re.sub(r"\s+", " ", summary.strip().lower())
    existing = next(
        (
            row
            for row in rows
            if slugify(str(row.get("title", ""))) == slugify(title)
            or re.sub(r"\s+", " ", str(row.get("summary", "")).strip().lower()) == normalized_summary
        ),
        None,
    )
    today = date.today().isoformat()
    record = {
        "id": existing.get("id") if existing else f"task_memory.{normalized_task_type}.{slugify(title)[:48]}",
        "type": "task_pattern",
        "task_type": normalized_task_type,
        "scope": "global",
        "project": None,
        "title": title,
        "summary": summary,
        "signals": sorted({signal for signal in (signals or existing.get("signals", [])) if signal}) if existing else sorted({signal for signal in (signals or []) if signal}),
        "common_locations": sorted({item for item in (common_locations or existing.get("common_locations", [])) if item}) if existing else sorted({item for item in (common_locations or []) if item}),
        "patterns": sorted({item for item in (patterns or existing.get("patterns", [])) if item}) if existing else sorted({item for item in (patterns or []) if item}),
        "constraints": sorted({item for item in (constraints or existing.get("constraints", [])) if item}) if existing else sorted({item for item in (constraints or []) if item}),
        "frequent_mistakes": sorted({item for item in (frequent_mistakes or existing.get("frequent_mistakes", [])) if item}) if existing else sorted({item for item in (frequent_mistakes or []) if item}),
        "preferred_validation": sorted({item for item in (preferred_validation or existing.get("preferred_validation", [])) if item}) if existing else sorted({item for item in (preferred_validation or []) if item}),
        "related_files": sorted({item for item in (related_files or existing.get("related_files", [])) if item}) if existing else sorted({item for item in (related_files or []) if item}),
        "tags": sorted({normalized_task_type, *[item for item in (patterns or []) if item]}),
        "confidence": round(float(confidence or (existing or {}).get("confidence", 0.75)), 2),
        "relevance_score": round(max(0.6, float(confidence or (existing or {}).get("confidence", 0.75))), 2),
        "context_cost": 3,
        "source_type": "task_memory_manual",
        "source": source,
        "last_verified": today,
        "last_used_at": today,
        "times_used": int((existing or {}).get("times_used", 0) or 0),
        "success_rate": float((existing or {}).get("success_rate", 0.8)),
        "staleness_score": 0.08,
        "files_involved": sorted({item for item in ((related_files or []) + (common_locations or [])) if item}),
    }
    if existing:
        rows = [row for row in rows if row.get("id") != existing.get("id")]
    rows.append(record)
    rows.sort(key=lambda row: str(row.get("id", "")))
    write_jsonl(path, rows)
    build_memory_graph_artifacts([normalize_record(row) for row in load_records()])
    return record


def classify_note(path: Path) -> NoteInfo:
    text = path.read_text()
    meta, body = parse_frontmatter(text)
    rel_path = path.relative_to(BASE).as_posix()
    parts = path.relative_to(BASE).parts
    project = None
    subproject = None
    scope = "global"
    if parts and parts[0] == "projects":
        scope = "project"
        if len(parts) > 1:
            project = parts[1]
        if len(parts) > 3:
            subproject = parts[2]
    title = next((line.strip("# ").strip() for line in body.splitlines() if line.strip().startswith("#")), path.stem)
    tags = list(meta.get("tags", []))
    if project:
        tags.append(project)
    if subproject:
        tags.append(subproject)
    tags = sorted({tag for tag in tags if tag})
    record_type = classify_note_type(rel_path, title, body)
    explicit_task_type = normalize_task_type(meta.get("task_type"))
    meta_task_type = str(meta.get("task_type", "")).strip().lower()
    task_type = explicit_task_type if explicit_task_type != "unknown" or meta_task_type in {"unknown", "general"} else classify_task_type_from_text(f"{rel_path}\n{title}\n{body}", tags=tags, record_type=record_type)
    return NoteInfo(
        path=path,
        rel_path=rel_path,
        meta=meta,
        body=body,
        project=project,
        subproject=subproject,
        scope=scope,
        tags=tags,
        record_type=record_type,
        title=title,
        task_type=task_type,
    )


def note_to_record(note: NoteInfo) -> dict[str, Any]:
    sections = []
    current = None
    for line in note.body.splitlines():
        stripped = line.strip()
        if stripped.endswith(":") and not stripped.startswith("-"):
            current = stripped[:-1]
            continue
        if stripped.startswith("- "):
            sections.append({"section": current or "notes", "text": stripped[2:].strip()})
    summary = " ".join(item["text"] for item in sections[:4]).strip() or note.title
    record_id = ".".join(
        part
        for part in [
            note.project or "global",
            note.subproject or "shared",
            slugify(note.path.stem),
        ]
        if part
    )
    return {
        "id": record_id,
        "type": note.record_type,
        "task_type": note.task_type,
        "scope": note.scope,
        "project": note.project,
        "subproject": note.subproject,
        "path": note.rel_path,
        "title": note.title,
        "tags": note.tags,
        "priority": note.meta.get("priority", "reference"),
        "confidence": note.meta.get("confidence", "medium"),
        "last_verified": note.meta.get("last_verified", date.today().isoformat()),
        "source": "migrated_from_ai_context_engine_note",
        "summary": summary,
        "sections": sections,
        "relevance_score": 0.75 if note.record_type in {"architecture_decision", "workflow_rule", "validation_recipe"} else 0.65,
        "last_used_at": note.meta.get("last_verified", date.today().isoformat()),
        "times_used": 0,
        "success_rate": 0.8,
        "context_cost": max(1, min(12, max(len(summary.split()) // 8, 1))),
        "source_type": "note",
        "staleness_score": 0.1,
        "files_involved": [note.rel_path],
    }


def preference_records() -> list[dict[str, Any]]:
    from .runtime_memory import preference_records as _impl
    return _impl()


def load_records() -> list[dict[str, Any]]:
    from .runtime_memory import load_records as _impl
    return _impl()


def iso_date_or_today(value: Any) -> str:
    from .runtime_io import iso_date_or_today as _impl
    return _impl(value)


def clamp(value: float, low: float, high: float) -> float:
    from .runtime_io import clamp as _impl
    return _impl(value, low, high)


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    from .runtime_memory import normalize_record as _impl
    return _impl(record)


def days_since(value: Any) -> int:
    from .runtime_io import days_since as _impl
    return _impl(value)


def deterministic_score(task: str, row: dict[str, Any]) -> float:
    query = task.lower().strip()
    haystacks = [
        row.get("id", ""),
        row.get("title", ""),
        row.get("summary", ""),
        row.get("path", ""),
        " ".join(row.get("tags", [])),
        row.get("key", ""),
        json.dumps(row.get("value", ""), ensure_ascii=False) if "value" in row else "",
    ]
    lexical = max(score_match(query, text) for text in haystacks) / 100 if query else 0
    if row.get("project"):
        lexical += 0.04
    if row.get("subproject"):
        lexical += 0.02
    recency = 1 - clamp(days_since(row.get("last_used_at")) / 365, 0, 1)
    compactness = 1 - clamp(float(row.get("context_cost", 5)) / 20, 0, 1)
    usage = clamp(float(row.get("times_used", 0)) / 10, 0, 1)
    staleness = 1 - clamp(float(row.get("staleness_score", 0.2)), 0, 1)
    total = (
        lexical * 0.35
        + float(row.get("relevance_score", 0.6)) * 0.2
        + recency * 0.15
        + float(row.get("success_rate", 0.75)) * 0.15
        + usage * 0.05
        + compactness * 0.05
        + staleness * 0.05
    )
    return round(total, 4)


def infer_project_name(task: str, matches: list[dict[str, Any]], explicit_project: str | None = None) -> str | None:
    if explicit_project:
        return explicit_project

    project_counts: dict[str, int] = defaultdict(int)
    for row in matches:
        project = row.get("project")
        if project:
            project_counts[str(project)] += 1
    if project_counts:
        return sorted(project_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]

    task_l = task.lower()
    registry = read_json(BOOT_PROJECTS_PATH, {}).get("projects", {})
    for project_name in sorted(registry.keys()):
        if project_name.lower() in task_l:
            return project_name

    return None


def rebuild_memory_store() -> dict[str, Any]:
    from .runtime_memory import rebuild_memory_store as _impl
    return _impl()


def write_indexes(rows: list[dict[str, Any]]) -> None:
    by_tag: dict[str, list[str]] = defaultdict(list)
    by_type: dict[str, list[str]] = defaultdict(list)
    by_project: dict[str, list[str]] = defaultdict(list)
    by_path: dict[str, dict[str, Any]] = {}
    by_preference: dict[str, dict[str, Any]] = {}
    symptoms = read_json(ROOT_SYMPTOMS_PATH, {"symptoms": {}}).get("symptoms", {})
    by_symptom = {key: value for key, value in symptoms.items()}

    for row in rows:
        row_id = row["id"]
        for tag in row.get("tags", []):
            by_tag[tag].append(row_id)
        by_type[row.get("type", "project_fact")].append(row_id)
        if row.get("project"):
            by_project[str(row["project"])].append(row_id)
        if row.get("path"):
            by_path[str(row["path"])] = {
                "record_id": row_id,
                "project": row.get("project"),
                "type": row.get("type"),
            }
        if row.get("type") == "user_preference":
            by_preference[str(row.get("key", row_id))] = {
                "record_id": row_id,
                "value": row.get("value"),
            }

    recent = sorted(rows, key=lambda row: str(row.get("last_verified", "")), reverse=True)[:25]
    write_json(INDEX_BY_TAG_PATH, dict(sorted(by_tag.items())))
    write_json(INDEX_BY_TYPE_PATH, dict(sorted(by_type.items())))
    write_json(INDEX_BY_PROJECT_PATH, dict(sorted(by_project.items())))
    write_json(INDEX_BY_PATH_PATH, by_path)
    write_json(INDEX_BY_SYMPTOM_PATH, by_symptom)
    write_json(INDEX_BY_PREFERENCE_PATH, by_preference)
    write_json(INDEX_RECENT_PATH, recent)


def write_migration_report(import_map: list[dict[str, str]]) -> None:
    from .runtime_compat import write_migration_report as _impl
    return _impl(import_map)



def sync_repo_compat_layers(
    *,
    project_rows: dict[str, list[dict[str, Any]]],
    global_rows: list[dict[str, Any]],
    defaults_payload: dict[str, Any],
    project_registry: dict[str, Any],
    boot_summary_payload: dict[str, Any],
    model_routing: dict[str, Any],
) -> list[str]:
    from .runtime_compat import sync_repo_compat_layers as _impl
    return _impl(project_rows=project_rows, global_rows=global_rows, defaults_payload=defaults_payload, project_registry=project_registry, boot_summary_payload=boot_summary_payload, model_routing=model_routing)



def sync_repo_cost_status(project: str | None) -> None:
    from .runtime_compat import sync_repo_cost_status as _impl
    return _impl(project)



def sync_repo_task_memory_status(project: str | None) -> None:
    from .runtime_compat import sync_repo_task_memory_status as _impl
    return _impl(project)



def sync_repo_failure_memory_status(project: str | None) -> None:
    from .runtime_compat import sync_repo_failure_memory_status as _impl
    return _impl(project)



def sync_repo_memory_graph_status(project: str | None) -> None:
    from .runtime_compat import sync_repo_memory_graph_status as _impl
    return _impl(project)



def find_legacy_memory_dirs() -> list[str]:
    from .runtime_compat import find_legacy_memory_dirs as _impl
    return _impl()



def default_model_routing() -> dict[str, Any]:
    adapter_contract = default_adapter_contract()
    return {
        "version": 1,
        "profile": "default",
        "adapter_defaults": {
            "adapter_id": adapter_contract["adapter_id"],
            "adapter_family": adapter_contract["adapter_family"],
            "provider_capabilities": adapter_contract["provider_capabilities"],
        },
        "levels": {
            "light": {
                "max_files": 2,
                "keywords": ["rename", "label", "copy", "text", "format"],
            },
            "medium": {
                "max_files": 8,
                "keywords": ["add", "implement", "fix", "debug", "test", "refactor"],
            },
            "heavy": {
                "min_files": 9,
                "keywords": ["architecture", "migration", "redesign", "cross-system", "protocol"],
            },
        },
    }


def score_match(query: str, candidate: str) -> int:
    query = query.lower().strip()
    candidate = candidate.lower()
    if not query:
        return 0
    if query == candidate:
        return 100
    if query in candidate:
        return 70
    parts = [part for part in re.split(r"[\s_\-]+", query) if part]
    if parts and all(part in candidate for part in parts):
        return 40 + len(parts)
    return sum(6 for part in parts if part in candidate)


def rank_records(
    query: str,
    record_type: str | None = None,
    task_type: str | None = None,
    project: str | None = None,
) -> list[dict[str, Any]]:
    from .runtime_memory import rank_records as _impl
    return _impl(query, record_type=record_type, task_type=task_type, project=project)


def summarize_query(query: str, mode: str = "all") -> dict[str, Any]:
    from .runtime_memory import summarize_query as _impl
    return _impl(query, mode=mode)


def route_task(task: str) -> dict[str, Any]:
    from .runtime_tasks import route_task as _impl
    return _impl(task)


def resolve_task_type(
    task: str,
    *,
    explicit_task_type: str | None = None,
    packet_metadata: dict[str, Any] | None = None,
    touched_files: list[str] | None = None,
) -> dict[str, Any]:
    from .runtime_tasks import resolve_task_type as _impl
    return _impl(task, explicit_task_type=explicit_task_type, packet_metadata=packet_metadata, touched_files=touched_files)


def packet_for_task(task: str, project: str | None = None, task_type: str | None = None) -> dict[str, Any]:
    from .runtime_tasks import packet_for_task as _impl
    return _impl(task, project=project, task_type=task_type)


def detect_stale_records() -> dict[str, Any]:
    from .runtime_tasks import detect_stale_records as _impl
    return _impl()


def compact_records(apply: bool = False) -> dict[str, Any]:
    from .runtime_tasks import compact_records as _impl
    return _impl(apply=apply)


def append_if_missing(path: Path, line: str) -> None:
    from .runtime_io import append_if_missing as _impl
    return _impl(path, line)




def yaml_scalar(value: Any) -> str:
    from .runtime_cost import yaml_scalar as _impl
    return _impl(value)



def render_simple_yaml(payload: dict[str, Any], indent: int = 0) -> str:
    from .runtime_cost import render_simple_yaml as _impl
    return _impl(payload, indent)



def parse_simple_yaml(path: Path) -> dict[str, Any]:
    from .runtime_cost import parse_simple_yaml as _impl
    return _impl(path)



def cost_config() -> dict[str, Any]:
    from .runtime_cost import cost_config as _impl
    return _impl()



def ensure_cost_artifacts() -> None:
    from .runtime_cost import ensure_cost_artifacts as _impl
    return _impl()



def ensure_task_memory_artifacts() -> None:
    from .runtime_task_memory import ensure_task_memory_artifacts as _impl
    return _impl()



def build_task_memory_artifacts(rows: list[dict[str, Any]]) -> dict[str, int]:
    from .runtime_task_memory import build_task_memory_artifacts as _impl
    return _impl(rows)



def update_task_memory_status(packet: dict[str, Any], packet_path: Path) -> None:
    from .runtime_task_memory import update_task_memory_status as _impl
    return _impl(packet, packet_path)



def ensure_failure_memory_artifacts() -> None:
    from .runtime_failure import ensure_failure_memory_artifacts as _impl
    return _impl()



def extract_related_commands(text: str) -> list[str]:
    from .runtime_failure import extract_related_commands as _impl
    return _impl(text)



def derive_failure_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from .runtime_failure import derive_failure_records as _impl
    return _impl(rows)



def manual_failure_records() -> list[dict[str, Any]]:
    from .runtime_failure import manual_failure_records as _impl
    return _impl()



def build_failure_memory_artifacts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    from .runtime_failure import build_failure_memory_artifacts as _impl
    return _impl(rows)



def record_failure(
    *,
    failure_id: str,
    category: str,
    title: str,
    symptoms: list[str],
    root_cause: str,
    solution: str,
    files_involved: list[str] | None = None,
    related_commands: list[str] | None = None,
    confidence: float = 0.75,
    notes: str = "",
) -> dict[str, Any]:
    from .runtime_failure import record_failure as _impl
    return _impl(failure_id=failure_id, category=category, title=title, symptoms=symptoms, root_cause=root_cause, solution=solution, files_involved=files_involved, related_commands=related_commands, confidence=confidence, notes=notes)



def should_consult_failure_memory(task: str, task_type: str) -> bool:
    from .runtime_failure import should_consult_failure_memory as _impl
    return _impl(task, task_type)



def rank_failure_records(task: str) -> list[dict[str, Any]]:
    from .runtime_failure import rank_failure_records as _impl
    return _impl(task)



def update_failure_memory_status(packet: dict[str, Any], packet_path: Path) -> None:
    from .runtime_failure import update_failure_memory_status as _impl
    return _impl(packet, packet_path)



def graph_node_id(node_type: str, raw_id: str) -> str:
    from .runtime_graph import graph_node_id as _impl
    return _impl(node_type, raw_id)



def edge_identity(from_id: str, to_id: str, relation: str) -> str:
    from .runtime_graph import edge_identity as _impl
    return _impl(from_id, to_id, relation)



def infer_repository_area(row: dict[str, Any]) -> str | None:
    from .runtime_graph import infer_repository_area as _impl
    return _impl(row)



def graph_node_type_for_record(row: dict[str, Any]) -> str:
    from .runtime_graph import graph_node_type_for_record as _impl
    return _impl(row)



def graph_label_index_key(label: str) -> str:
    from .runtime_graph import graph_label_index_key as _impl
    return _impl(label)



def ensure_memory_graph_artifacts() -> None:
    from .runtime_graph import ensure_memory_graph_artifacts as _impl
    return _impl()



def graph_add_node(nodes: dict[str, dict[str, Any]], *, node_id: str, node_type: str, label: str, source: str, confidence: float = 0.7, tags: list[str] | None = None, metadata: dict[str, Any] | None = None) -> None:
    from .runtime_graph import graph_add_node as _impl
    return _impl(nodes, node_id=node_id, node_type=node_type, label=label, source=source, confidence=confidence, tags=tags, metadata=metadata)



def graph_add_edge(edges: dict[str, dict[str, Any]], *, from_id: str, to_id: str, relation: str, source: str, confidence: float = 0.65) -> None:
    from .runtime_graph import graph_add_edge as _impl
    return _impl(edges, from_id=from_id, to_id=to_id, relation=relation, source=source, confidence=confidence)



def build_memory_graph_artifacts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    from .runtime_graph import build_memory_graph_artifacts as _impl
    return _impl(rows)



def graph_nodes() -> dict[str, dict[str, Any]]:
    from .runtime_graph import graph_nodes as _impl
    return _impl()



def graph_edges() -> list[dict[str, Any]]:
    from .runtime_graph import graph_edges as _impl
    return _impl()



def graph_find_nodes(query: str) -> list[dict[str, Any]]:
    from .runtime_graph import graph_find_nodes as _impl
    return _impl(query)



def graph_neighbors(node_id: str, relation: str | None = None) -> list[dict[str, Any]]:
    from .runtime_graph import graph_neighbors as _impl
    return _impl(node_id, relation)



def graph_expand(seed_ids: list[str], *, depth: int = 1, node_budget: int = 8, edge_budget: int = 12, task_type: str | None = None, repository_area: str | None = None) -> dict[str, Any]:
    from .runtime_graph import graph_expand as _impl
    return _impl(seed_ids, depth=depth, node_budget=node_budget, edge_budget=edge_budget, task_type=task_type, repository_area=repository_area)



def update_memory_graph_status(packet: dict[str, Any], packet_path: Path) -> None:
    from .runtime_graph import update_memory_graph_status as _impl
    return _impl(packet, packet_path)



def ensure_context_metrics_artifacts() -> None:
    from .runtime_metrics import ensure_context_metrics_artifacts as _impl
    return _impl()



def estimate_tokens(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (dict, list)):
        return max(1, len(json.dumps(value, ensure_ascii=False)) // 4)
    return max(1, len(str(value)) // 4)


def summarize_granular_telemetry(log_rows: list[dict[str, Any]]) -> dict[str, Any]:
    from .runtime_metrics import summarize_granular_telemetry as _impl
    return _impl(log_rows)



def record_granular_telemetry(packet: dict[str, Any], packet_path: Path, optimization_report: dict[str, Any]) -> dict[str, Any]:
    from .runtime_metrics import record_granular_telemetry as _impl
    return _impl(packet, packet_path, optimization_report)



def library_registry() -> dict[str, Any]:
    from .runtime_knowledge import library_registry as _impl
    return _impl()


def ensure_library_artifacts() -> None:
    ensure_dirs()
    readme = LIBRARY_DIR / "README.md"
    if not readme.exists():
        write_text(
            readme,
            "# .ai_context_engine/library\n\n"
            "Local knowledge library for ai_context_engine.\n\n"
            "- `mods/` contains domain workspaces.\n"
            "- `inbox/` is the raw drop zone.\n"
            "- `notes/`, `summaries/`, `indices/`, and `manifests/` are derived artifacts.\n",
        )
    ensure_references_template()
    if not LIBRARY_REGISTRY_PATH.exists():
        write_json(LIBRARY_REGISTRY_PATH, {"version": 1, "generated_at": date.today().isoformat(), "mods": {}})
    if not LIBRARY_RETRIEVAL_STATUS_PATH.exists():
        write_json(
            LIBRARY_RETRIEVAL_STATUS_PATH,
            {
                "version": 1,
                "generated_at": date.today().isoformat(),
                **compat_version_payload(),
                "mods_total": 0,
                "retrieval_events": 0,
                "last_selected_artifacts": [],
                "supports_reference_ingestion": True,
                "supports_remote_ingestion": True,
            },
        )


def mod_root(mod_id: str) -> Path:
    return LIBRARY_DIR / "mods" / slugify(mod_id)


def bootstrap_mod(
    mod_id: str,
    *,
    aliases: list[str] | None = None,
    title: str | None = None,
    create_reference_stub: bool = False,
) -> dict[str, Any]:
    from .runtime_knowledge import bootstrap_mod as _impl
    return _impl(mod_id, aliases=aliases, title=title, create_reference_stub=create_reference_stub)


def extract_text_from_html(raw_html: str) -> tuple[str, str]:
    from .runtime_knowledge import extract_text_from_html as _impl
    return _impl(raw_html)


def extract_text_for_knowledge(path: Path) -> str:
    from .runtime_knowledge import extract_text_for_knowledge as _impl
    return _impl(path)


def clean_extracted_knowledge_text(text: str) -> str:
    from .runtime_knowledge import clean_extracted_knowledge_text as _impl
    return _impl(text)


def normalize_knowledge_text(text: str) -> str:
    from .runtime_knowledge import normalize_knowledge_text as _impl
    return _impl(text)


def summarize_knowledge_text(text: str) -> str:
    from .runtime_knowledge import summarize_knowledge_text as _impl
    return _impl(text)


def detect_main_content_start(text: str) -> str:
    from .runtime_knowledge import detect_main_content_start as _impl
    return _impl(text)


def chapter_title_from_chunk(chunk: str, fallback_index: int) -> str:
    from .runtime_knowledge import chapter_title_from_chunk as _impl
    return _impl(chunk, fallback_index)


def section_title_from_keywords(text: str, fallback_index: int) -> str:
    from .runtime_knowledge import section_title_from_keywords as _impl
    return _impl(text, fallback_index)


def split_knowledge_sections(text: str) -> list[dict[str, Any]]:
    from .runtime_knowledge import split_knowledge_sections as _impl
    return _impl(text)


def topic_keywords(text: str, *, limit: int = 12) -> list[str]:
    from .runtime_knowledge import topic_keywords as _impl
    return _impl(text, limit=limit)


def stable_source_name(source_path: Path, source_kind: str, source_key: str, previous: dict[str, Any] | None = None) -> str:
    from .runtime_knowledge import stable_source_name as _impl
    return _impl(source_path, source_kind, source_key, previous=previous)


def process_knowledge_source(
    root: Path,
    *,
    source_path: Path,
    source_kind: str,
    source_key: str,
    title: str,
    label: str | None = None,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from .runtime_knowledge import process_knowledge_source as _impl
    return _impl(root, source_path=source_path, source_kind=source_kind, source_key=source_key, title=title, label=label, previous=previous)


def canonicalize_url(raw_url: str) -> str:
    from .runtime_knowledge import canonicalize_url as _impl
    return _impl(raw_url)


def build_source_id(url: str, existing_sources: list[dict[str, Any]]) -> str:
    from .runtime_knowledge import build_source_id as _impl
    return _impl(url, existing_sources)


def detect_remote_type(url: str, declared_type: str, content_type_header: str, raw_bytes: bytes) -> str:
    from .runtime_knowledge import detect_remote_type as _impl
    return _impl(url, declared_type, content_type_header, raw_bytes)


def title_from_text(text: str, fallback: str) -> str:
    from .runtime_knowledge import title_from_text as _impl
    return _impl(text, fallback)


def extract_remote_payload(raw_path: Path, detected_type: str) -> tuple[str, str, list[str]]:
    from .runtime_knowledge import extract_remote_payload as _impl
    return _impl(raw_path, detected_type)


def remote_frontmatter(tags: list[str]) -> str:
    from .runtime_knowledge import remote_frontmatter as _impl
    return _impl(tags)


def parse_http_headers(raw_headers: str) -> tuple[int, dict[str, str]]:
    from .runtime_knowledge import parse_http_headers as _impl
    return _impl(raw_headers)


def fetch_remote_payload_bytes(url: str) -> tuple[bytes, int, dict[str, str]]:
    from .runtime_knowledge import fetch_remote_payload_bytes as _impl
    return _impl(url)


def register_remote_source(mod_id: str, url: str, declared_type: str = "auto", tags: list[str] | None = None) -> dict[str, Any]:
    from .runtime_knowledge import register_remote_source as _impl
    return _impl(mod_id, url, declared_type=declared_type, tags=tags)


def fetch_remote_sources(mod_id: str, source_id: str | None = None, force: bool = False) -> dict[str, Any]:
    from .runtime_knowledge import fetch_remote_sources as _impl
    return _impl(mod_id, source_id=source_id, force=force)


def process_mod_documents(mod_id: str) -> dict[str, Any]:
    from .runtime_knowledge import process_mod_documents as _impl
    return _impl(mod_id)


def infer_candidate_mods(task: str) -> list[str]:
    from .runtime_knowledge import infer_candidate_mods as _impl
    return _impl(task)


def retrieve_knowledge(task: str) -> dict[str, Any]:
    from .runtime_knowledge import retrieve_knowledge as _impl
    return _impl(task)


def ensure_engine_state() -> None:
    ensure_dirs()
    if not ENGINE_STATE_PATH.exists():
        defaults_payload = read_json(ROOT_PREFS_PATH, {})
        communication_policy = communication_policy_from_defaults(defaults_payload)
        adapter_contract = default_adapter_contract()
        write_json(
            ENGINE_STATE_PATH,
            {
                "engine_id": "ai_context_engine",
                "engine_name": "ai_context_engine",
                **adapter_contract,
                **compat_version_payload(),
                "install_mode": "in_repo",
                "engine_role": "canonical_runtime",
                "communication_layer": communication_policy.get("layer", "enabled"),
                "communication_mode": communication_policy.get("mode", "caveman_full"),
                "communication_contract": {
                    "intermediate_updates": communication_policy.get("intermediate_updates", "suppressed"),
                    "final_style": communication_policy.get("final_style", "plain_direct_final_only"),
                    "single_final_answer_default": True,
                    "explicit_user_override_wins": True,
                },
                "last_upgrade_at": now_iso(),
            },
        )


def refresh_engine_state() -> dict[str, Any]:
    ensure_engine_state()
    state = read_json(ENGINE_STATE_PATH, {})
    defaults_payload = read_json(ROOT_PREFS_PATH, {})
    communication_policy = communication_policy_from_defaults(defaults_payload)
    adapter_contract = default_adapter_contract()
    state.update(
        {
            "engine_id": "ai_context_engine",
            "engine_name": "ai_context_engine",
            "agent_adapter": str(state.get("agent_adapter") or adapter_contract["agent_adapter"]),
            "adapter_id": str(state.get("adapter_id") or adapter_contract["adapter_id"]),
            "adapter_family": str(state.get("adapter_family") or adapter_contract["adapter_family"]),
            "provider_capabilities": list(state.get("provider_capabilities") or adapter_contract["provider_capabilities"]),
            **compat_version_payload(),
            "install_mode": "in_repo",
            "engine_role": "canonical_runtime",
            "communication_layer": normalize_communication_layer(state.get("communication_layer"), communication_policy.get("layer", "enabled")),
            "communication_mode": normalize_communication_mode(state.get("communication_mode"), communication_policy.get("mode", "caveman_full")),
            "communication_contract": {
                "intermediate_updates": communication_policy.get("intermediate_updates", "suppressed"),
                "final_style": communication_policy.get("final_style", "plain_direct_final_only"),
                "single_final_answer_default": True,
                "explicit_user_override_wins": True,
                "preserve_precision": True,
                "no_intermediate_output_by_default": True,
            },
            "last_upgrade_at": now_iso(),
            "shared_layers": {
                "memory_dir": ".ai_context_engine/memory",
                "telemetry_dir": ".ai_context_engine/metrics",
                "global_metrics_dir": ".ai_context_global_metrics",
                "cost_dir": ".ai_context_engine/cost",
                "task_memory_dir": ".ai_context_engine/task_memory",
                "failure_memory_dir": ".ai_context_engine/failure_memory",
                "memory_graph_dir": ".ai_context_engine/memory_graph",
                "library_dir": ".ai_context_engine/library",
            },
            "supports": {
                "granular_telemetry": True,
                "knowledge_mods": True,
                "knowledge_pipeline": True,
                "knowledge_retrieval": True,
                "reference_ingestion": True,
                "remote_ingestion": True,
            },
        }
    )
    write_json(ENGINE_STATE_PATH, state)
    return state


def truncate_words(text: str, max_words: int) -> str:
    from .runtime_io import truncate_words as _impl
    return _impl(text, max_words)


def packet_item_text(item: Any) -> str:
    from .runtime_cost import packet_item_text as _impl
    return _impl(item)



def estimate_tokens_from_text(text: str, structural_overhead: int = 0) -> int:
    from .runtime_cost import estimate_tokens_from_text as _impl
    return _impl(text, structural_overhead)



def estimate_packet_tokens(packet: dict[str, Any]) -> dict[str, Any]:
    from .runtime_cost import estimate_packet_tokens as _impl
    return _impl(packet)





def item_identity(item: Any) -> str:
    from .runtime_cost import item_identity as _impl
    return _impl(item)



def item_value(item: Any, section_name: str) -> float:
    from .runtime_cost import item_value as _impl
    return _impl(item, section_name)



def item_cost(item: Any) -> int:
    from .runtime_cost import item_cost as _impl
    return _impl(item)



def compress_item(item: Any, max_words: int) -> Any:
    from .runtime_cost import compress_item as _impl
    return _impl(item, max_words)



def dedupe_items(items: list[Any]) -> tuple[list[Any], list[dict[str, Any]]]:
    from .runtime_cost import dedupe_items as _impl
    return _impl(items)



def optimize_list_section(section_name: str, items: list[Any], config: dict[str, Any], available_tokens: int) -> tuple[list[Any], list[dict[str, Any]], int]:
    from .runtime_cost import optimize_list_section as _impl
    return _impl(section_name, items, config, available_tokens)



def sync_packet_mirrors(packet: dict[str, Any]) -> None:
    from .runtime_cost import sync_packet_mirrors as _impl
    return _impl(packet)



def update_cost_status(report: dict[str, Any], packet_path: Path) -> None:
    from .runtime_cost import update_cost_status as _impl
    return _impl(report, packet_path)



def render_optimization_report(report: dict[str, Any]) -> str:
    from .runtime_cost import render_optimization_report as _impl
    return _impl(report)



def optimize_packet(packet: dict[str, Any]) -> dict[str, Any]:
    from .runtime_cost import optimize_packet as _impl
    return _impl(packet)



def bootstrap(repo_path: str | None = None) -> dict[str, Any]:
    required_boot_files = [
        BOOT_SUMMARY_PATH,
        BOOT_DEFAULTS_PATH,
        BOOT_PROJECTS_PATH,
        BOOT_MODEL_ROUTING_PATH,
        COST_STATUS_PATH,
        TASK_MEMORY_STATUS_PATH,
        TASK_MEMORY_TAXONOMY_PATH,
        FAILURE_MEMORY_STATUS_PATH,
        MEMORY_GRAPH_STATUS_PATH,
    ]
    if any(not path.exists() for path in required_boot_files):
        rebuild_memory_store()
    repo = Path(repo_path).resolve() if repo_path else None
    repo_name = repo.name if repo else "unknown"
    repo_memory_dir = repo / ".ai_context_engine" / "memory" if repo else None
    repo_state_path = repo / ".ai_context_engine" / "state.json" if repo else None
    resolved_preferences = resolve_effective_preferences(repo, global_defaults_path=ROOT_PREFS_PATH)
    consistency = runtime_consistency_report(repo, global_defaults_path=ROOT_PREFS_PATH)
    repo_exists = bool(repo_memory_dir and repo_memory_dir.exists())
    return {
        "boot_summary": read_json(BOOT_SUMMARY_PATH, {}),
        "user_defaults": read_json(BOOT_DEFAULTS_PATH, {}),
        "effective_preferences": resolved_preferences.get("effective_preferences", {}),
        "communication_policy": resolved_preferences.get("effective_preferences", {}).get("communication", {}),
        "communication_sources": resolved_preferences.get("sources", {}).get("communication", {}),
        "project_registry": read_json(BOOT_PROJECTS_PATH, {}),
        "model_routing": read_json(BOOT_MODEL_ROUTING_PATH, {}),
        "cost_optimizer": read_json(COST_STATUS_PATH, {}),
        "task_memory": read_json(TASK_MEMORY_STATUS_PATH, {}),
        "task_taxonomy": read_json(TASK_MEMORY_TAXONOMY_PATH, {}),
        "failure_memory": read_json(FAILURE_MEMORY_STATUS_PATH, {}),
        "memory_graph": read_json(MEMORY_GRAPH_STATUS_PATH, {}),
        "consistency_checks": consistency,
        "repo_bootstrap": {
            "exists": repo_exists,
            "status": "initialized" if repo_exists else "not_initialized",
            "path": repo_memory_dir.as_posix() if repo_memory_dir else "",
            "derived_boot_summary": read_json(repo_memory_dir / "derived_boot_summary.json", {}) if repo_memory_dir and repo_memory_dir.exists() else {},
            "project_bootstrap": read_json(repo_memory_dir / "project_bootstrap.json", {}) if repo_memory_dir and repo_memory_dir.exists() else {},
            "user_preferences": read_json(repo_memory_dir / "user_preferences.json", {}) if repo_memory_dir and repo_memory_dir.exists() else {},
            "state": read_json(repo_state_path, {}) if repo_state_path and repo_state_path.exists() else {},
        },
        "session": {
            "repo_name": repo_name,
            "booted_at": date.today().isoformat(),
        },
    }


def ensure_gitignore(target_repo: str) -> dict[str, Any]:
    repo = Path(target_repo).resolve()
    gitignore = repo / ".gitignore"
    desired = [
        ".ai_context_engine/",
        ".ai_context_global_metrics/",
        ".ai_context_planner/",
        "CONTEXT_SAVINGS.md",
    ]
    try:
        memory_rel = BASE.relative_to(repo)
        desired.extend(
            [
                f"{memory_rel.as_posix()}/delta/last_packets/",
                f"{memory_rel.as_posix()}/logs/maintenance_log.md",
            ]
        )
    except ValueError:
        pass
    existing = gitignore.read_text().splitlines() if gitignore.exists() else []
    changed = False
    for entry in desired:
        if entry not in existing:
            existing.append(entry)
            changed = True
    if changed:
        gitignore.write_text("\n".join(existing) + "\n")
    return {"gitignore": gitignore.as_posix(), "changed": changed, "entries": desired}


def touch_records(paths: list[str]) -> dict[str, Any]:
    updated = []
    rows = load_records()
    path_set = set(paths)
    for row in rows:
        if row.get("path") in path_set or row.get("id") in path_set:
            row["last_verified"] = date.today().isoformat()
            updated.append(row["id"])
    project_rows: dict[str | None, list[dict[str, Any]]] = defaultdict(list)
    global_rows: list[dict[str, Any]] = []
    pref_rows: list[dict[str, Any]] = []
    for row in rows:
        if row.get("type") == "user_preference":
            pref_rows.append(row)
        elif row.get("project"):
            project_rows[row.get("project")].append(row)
        else:
            global_rows.append(row)
    write_jsonl(STORE_GLOBAL_RECORDS_PATH, global_rows)
    write_jsonl(STORE_USER_PREFERENCES_PATH, pref_rows)
    for project, project_list in project_rows.items():
        if project:
            write_jsonl(PROJECT_RECORDS_DIR / f"{project}.jsonl", project_list)
    return {"updated": updated}


def new_note(path: str, title: str, tags: list[str] | None = None, task_type: str | None = None) -> dict[str, Any]:
    note_path = BASE / path
    note_path.parent.mkdir(parents=True, exist_ok=True)
    tag_list = ", ".join(tags or [])
    normalized_task_type = normalize_task_type(task_type) if task_type else None
    note_path.write_text(
        (
            "---\n"
            "priority: reference\n"
            "confidence: medium\n"
            f"last_verified: {date.today().isoformat()}\n"
            f"tags: {tag_list}\n"
            f"{f'task_type: {normalized_task_type}\\n' if normalized_task_type else ''}"
            "---\n\n"
            f"# {title}\n\n"
            "Problem\n"
            "- \n\n"
            "Invariant\n"
            "- \n\n"
            "Known failure modes\n"
            "- \n\n"
            "Fastest validation\n"
            "- \n"
        )
    )
    rebuild_memory_store()
    return {"created": note_path.as_posix()}


def cli_boot(args: argparse.Namespace) -> int:
    print(json.dumps(bootstrap(args.repo), indent=2, ensure_ascii=False))
    return 0


def cli_query(args: argparse.Namespace) -> int:
    mode = "all"
    if args.prefs:
        mode = "prefs"
    elif args.architecture:
        mode = "architecture"
    elif args.symptom:
        mode = "symptom"
    query = " ".join(args.query).strip()
    if not query and mode != "prefs":
        print("Query required.")
        return 1
    payload = summarize_query(query, mode=mode)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def cli_packet(args: argparse.Namespace) -> int:
    packet = packet_for_task(args.task, project=args.project, task_type=getattr(args, "task_type", None))
    print(json.dumps(packet, indent=2, ensure_ascii=False))
    return 0


def cli_route(args: argparse.Namespace) -> int:
    print(json.dumps(route_task(args.task), indent=2, ensure_ascii=False))
    return 0


def cli_migrate(_: argparse.Namespace) -> int:
    summary = rebuild_memory_store()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def cli_stale(_: argparse.Namespace) -> int:
    print(json.dumps(detect_stale_records(), indent=2, ensure_ascii=False))
    return 0


def cli_compact(args: argparse.Namespace) -> int:
    print(json.dumps(compact_records(apply=args.apply), indent=2, ensure_ascii=False))
    return 0


def cli_gitignore(args: argparse.Namespace) -> int:
    print(json.dumps(ensure_gitignore(args.repo), indent=2, ensure_ascii=False))
    return 0


def cli_touch(args: argparse.Namespace) -> int:
    print(json.dumps(touch_records(args.items), indent=2, ensure_ascii=False))
    return 0


def cli_new_note(args: argparse.Namespace) -> int:
    print(json.dumps(new_note(args.path, args.title, args.tags, getattr(args, "task_type", None)), indent=2, ensure_ascii=False))
    return 0


def cli_failure(args: argparse.Namespace) -> int:
    record = record_failure(
        failure_id=args.failure_id,
        category=args.category,
        title=args.title,
        symptoms=args.symptoms or [],
        root_cause=args.root_cause,
        solution=args.solution,
        files_involved=args.files or [],
        related_commands=args.commands or [],
        confidence=args.confidence,
        notes=args.notes or "",
    )
    print(json.dumps(record, indent=2, ensure_ascii=False))
    return 0


def cli_task_memory(args: argparse.Namespace) -> int:
    record = record_task_memory(
        task_type=args.task_type,
        title=args.title,
        summary=args.summary,
        signals=args.signals or [],
        common_locations=args.common_locations or [],
        patterns=args.patterns or [],
        constraints=args.constraints or [],
        frequent_mistakes=args.frequent_mistakes or [],
        preferred_validation=args.preferred_validation or [],
        related_files=args.related_files or [],
        confidence=args.confidence,
        source="manual_cli",
    )
    build_task_memory_artifacts([normalize_record(row) for row in load_records()])
    print(json.dumps(record, indent=2, ensure_ascii=False))
    return 0


def cli_memory_graph(args: argparse.Namespace) -> int:
    if getattr(args, "refresh", False):
        payload = build_memory_graph_artifacts([normalize_record(row) for row in load_records()])
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    query = str(getattr(args, "query", "") or "").strip()
    if not query:
        print(json.dumps(read_json(MEMORY_GRAPH_STATUS_PATH, {}), indent=2, ensure_ascii=False))
        return 0
    matches = graph_find_nodes(query)
    seed_ids = [row["id"] for row in matches[:3]]
    expansion = graph_expand(seed_ids, depth=int(getattr(args, "depth", 1) or 1), node_budget=8, edge_budget=12)
    print(json.dumps({"query": query, "matches": matches, "expansion": expansion}, indent=2, ensure_ascii=False))
    return 0


def cli_library(args: argparse.Namespace) -> int:
    from .runtime_knowledge import cli_library as _impl
    return _impl(args)
