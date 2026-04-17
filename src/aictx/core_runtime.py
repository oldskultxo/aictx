#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import mimetypes
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request
from .runtime_contract import (
    communication_policy_from_defaults,
    normalize_communication_layer,
    normalize_communication_mode,
    resolve_effective_preferences,
    runtime_consistency_report,
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

CURRENT_ENGINE_ITERATION = 16
MTIME_TOLERANCE_SECONDS = 0.5
SUPPORTED_INBOX_EXTENSIONS = {".md", ".txt", ".html", ".htm", ".pdf"}
SUPPORTED_REFERENCED_EXTENSIONS = SUPPORTED_INBOX_EXTENSIONS | {".sql", ".xml", ".json", ".yaml", ".yml", ".py", ".csv"}
REMOTE_DECLARED_TYPES = {"auto", "html", "pdf", "md", "txt"}
REMOTE_TYPE_EXTENSIONS = {"html": ".html", "pdf": ".pdf", "md": ".md", "txt": ".txt"}


class HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self.in_title = False
        self.in_pre = False
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "nav", "footer", "header", "noscript", "svg"}:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in {"title"}:
            self.in_title = True
        if tag in {"pre", "code"}:
            self.in_pre = True
            self.parts.append("\n```text\n")
        elif tag in {"br"}:
            self.parts.append("\n")
        elif tag in {"p", "div", "section", "article", "main", "tr"}:
            self.parts.append("\n\n")
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = min(int(tag[1]), 6)
            self.parts.append(f"\n\n{'#' * level} ")
        elif tag == "li":
            self.parts.append("\n- ")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "nav", "footer", "header", "noscript", "svg"}:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth:
            return
        if tag == "title":
            self.in_title = False
        if tag in {"pre", "code"}:
            self.parts.append("\n```\n")
            self.in_pre = False
        elif tag in {"p", "div", "section", "article", "main", "table"}:
            self.parts.append("\n\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        value = html.unescape(data)
        if not value.strip():
            if self.in_pre:
                self.parts.append(value)
            return
        if self.in_title:
            self.title_parts.append(re.sub(r"\s+", " ", value).strip())
        if self.in_pre:
            self.parts.append(value)
        else:
            self.parts.append(re.sub(r"\s+", " ", value).strip() + " ")

    def result(self) -> tuple[str, str]:
        text = "".join(self.parts)
        text = re.sub(r"\n{3,}", "\n\n", text)
        lines = [line.rstrip() for line in text.splitlines()]
        compact_lines = []
        previous_blank = False
        for line in lines:
            blank = not line.strip()
            if blank and previous_blank:
                continue
            compact_lines.append(line)
            previous_blank = blank
        title = re.sub(r"\s+", " ", " ".join(self.title_parts)).strip()
        return "\n".join(compact_lines).strip(), title

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
    readme = compat_dir / "README.md"
    readme.write_text(
        "# .ai_context_engine/memory\n\n"
        "Repo-local bootstrap layer for AI agent sessions in this repository.\n\n"
        "- Canonical source: `.ai_context_engine/`\n"
        "- Purpose: fast local bootstrap and predictable artifact paths (`derived_boot_summary.json`, `user_preferences.json`, `project_bootstrap.json`).\n"
        "- Do not hand-edit generated JSON/JSONL here; rebuild from the runtime instead.\n"
    )


def slugify(text: str) -> str:
    from .runtime_io import slugify as _impl
    return _impl(text)


def current_engine_iteration() -> int:
    return CURRENT_ENGINE_ITERATION


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
    return path.is_file() and path.name != "references.md" and path.suffix.lower() in SUPPORTED_INBOX_EXTENSIONS


def resolve_reference_path(raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (BASE / raw_path).resolve()


def parse_references_file(path: Path) -> list[dict[str, Any]]:
    from .runtime_knowledge import parse_references_file as _impl
    return _impl(path)


def sanitize_source_name(value: str, fallback: str = "source") -> str:
    cleaned = slugify(Path(value).stem if value else fallback)
    return cleaned[:80] or fallback


def delete_artifact_paths(root: Path, paths: list[str]) -> None:
    for raw_path in paths:
        if not raw_path:
            continue
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = root / raw_path
        if candidate.exists() and candidate.is_file():
            candidate.unlink()


def invalidate_source_artifacts(root: Path, previous: dict[str, Any]) -> None:
    delete_artifact_paths(root, list(previous.get("note_files", [])))
    delete_artifact_paths(root, list(previous.get("summary_files", [])))
    delete_artifact_paths(root, [previous.get("processed_path", ""), previous.get("manifest_path", "")])


def rebuild_mod_indices(root: Path, state: dict[str, Any]) -> dict[str, list[str]]:
    from .runtime_knowledge import rebuild_mod_indices as _impl
    return _impl(root, state)


def remote_manifest_path(root: Path) -> Path:
    return root / "remote_sources" / "manifest.json"


def load_remote_sources_manifest(root: Path) -> dict[str, Any]:
    ensure_remote_manifest(root)
    manifest = read_json(remote_manifest_path(root), {"version": 1, "sources": []})
    manifest.setdefault("version", 1)
    manifest.setdefault("sources", [])
    return manifest


def save_remote_sources_manifest(root: Path, manifest: dict[str, Any]) -> None:
    manifest["version"] = 1
    write_json(remote_manifest_path(root), manifest)


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
    legacy_memory_paths = find_legacy_memory_dirs()
    lines = [
        "# legacy memory migration report",
        "",
        f"- Date: {date.today().isoformat()}",
        f"- Legacy memory dirs detected: {'yes' if legacy_memory_paths else 'no'}",
        "- Migration target: existing `ai_context_engine` upgraded in place to structured boot/store/indexes/delta layout.",
        f"- Notes imported from legacy markdown store: {len(import_map)}",
        "",
        "## Result",
        "",
    ]
    if legacy_memory_paths:
        lines.append("- A legacy memory directory exists and still needs explicit import handling.")
    else:
        lines.append("- No legacy memory directory was found under `/Users/santisantamaria/Documents/projects`.")
        lines.append("- The new schema therefore migrated from the pre-existing `ai_context_engine` note system.")
    lines.extend(
        [
            "",
            "## Imported notes",
            "",
        ]
    )
    lines.extend(f"- `{item['source']}` -> `{item['target_record_id']}`" for item in import_map)
    MIGRATION_REPORT_PATH.write_text("\n".join(lines) + "\n")


def sync_repo_compat_layers(
    *,
    project_rows: dict[str, list[dict[str, Any]]],
    global_rows: list[dict[str, Any]],
    defaults_payload: dict[str, Any],
    project_registry: dict[str, Any],
    boot_summary_payload: dict[str, Any],
    model_routing: dict[str, Any],
) -> list[str]:
    synced = []
    project_map = project_registry.get("projects", {})
    adapter_contract = default_adapter_contract()
    for project, rows in project_rows.items():
        repo_root = repo_root_for_project(project)
        if not repo_root:
            continue
        compat_dir = repo_root / REPO_COMPAT_DIRNAME
        compat_dir.mkdir(parents=True, exist_ok=True)
        ensure_repo_compat_readme(compat_dir)

        project_info = project_map.get(project, {})
        project_bootstrap = {
            "version": 1,
            "generated_at": date.today().isoformat(),
            "project": project,
            "repo_root": repo_root.as_posix(),
            "engine_name": "ai_context_engine",
            **adapter_contract,
            "summary": project_info.get("summary", ""),
            "lookup_order": project_registry.get("lookup_order", []),
            "subprojects": project_info.get("subprojects", {}),
            "canonical_memory_root": BASE.as_posix(),
            "external_index": ROOT_INDEX_PATH.as_posix(),
            "external_preferences": ROOT_PREFS_PATH.as_posix(),
        }
        derived_boot_summary = {
            "version": 1,
            "generated_at": date.today().isoformat(),
            "project": project,
            "repo_root": repo_root.as_posix(),
            "engine_name": boot_summary_payload.get("engine_name", "ai_context_engine"),
            "agent_adapter": boot_summary_payload.get("agent_adapter", DEFAULT_AGENT_ADAPTER),
            "adapter_id": boot_summary_payload.get("adapter_id", DEFAULT_ADAPTER_ID),
            "adapter_family": boot_summary_payload.get("adapter_family", DEFAULT_ADAPTER_FAMILY),
            "provider_capabilities": boot_summary_payload.get("provider_capabilities", list(DEFAULT_PROVIDER_CAPABILITIES)),
            "canonical_memory_root": BASE.as_posix(),
            "bootstrap_required": True,
            "bootstrap_sequence": [
                f"load {REPO_COMPAT_DIRNAME}/derived_boot_summary.json",
                f"load {REPO_COMPAT_DIRNAME}/user_preferences.json",
                f"load {REPO_COMPAT_DIRNAME}/project_bootstrap.json",
                "load smallest relevant project note from canonical ai_context_engine",
                "apply preferences as runtime defaults",
            ],
            "fallback_order": [
                REPO_COMPAT_DIRNAME,
                "ai_context_engine",
                "normal_repo_analysis",
            ],
            "preference_precedence": boot_summary_payload.get("preference_precedence", []),
            "default_behavior": boot_summary_payload.get("default_behavior", {}),
            "preferred_output_patterns": boot_summary_payload.get("preferred_output_patterns", []),
            "communication_policy": boot_summary_payload.get("communication_policy", {}),
            "communication_contract": boot_summary_payload.get("communication_contract", {}),
            "model_routing_profile": model_routing.get("profile", "default"),
            "active_subprojects": sorted(project_info.get("subprojects", {}).keys()),
        }
        manifest = {
            "version": 1,
            "generated_at": date.today().isoformat(),
            "canonical_memory_root": BASE.as_posix(),
            "project": project,
            "artifacts": {
                "derived_boot_summary": "derived_boot_summary.json",
                "user_preferences": "user_preferences.json",
                "project_bootstrap": "project_bootstrap.json",
                "context_packet_schema": "context_packet_schema.json",
                "compaction_report": "compaction_report.json",
                "packet_budget_status": "packet_budget_status.json",
                "task_memory_summary": "task_memory_summary.json",
                "failure_memory_summary": "failure_memory_summary.json",
                "memory_graph_summary": "memory_graph_summary.json",
                "architecture_learnings": "architecture_learnings.jsonl",
                "technical_patterns": "technical_patterns.jsonl",
                "workflow_learnings": "workflow_learnings.jsonl",
            },
        }

        combined_rows = list(global_rows) + list(rows)
        architecture_rows = [row for row in combined_rows if row.get("type") in COMPAT_ARCHITECTURE_TYPES]
        workflow_rows = [row for row in combined_rows if row.get("type") in COMPAT_WORKFLOW_TYPES]
        technical_rows = [row for row in combined_rows if row.get("type") in COMPAT_TECHNICAL_TYPES]

        write_json(compat_dir / "manifest.json", manifest)
        write_json(compat_dir / "derived_boot_summary.json", derived_boot_summary)
        write_json(compat_dir / "project_bootstrap.json", project_bootstrap)
        write_json(compat_dir / "context_packet_schema.json", read_json(DELTA_SCHEMA_PATH, {}))
        write_json(compat_dir / "compaction_report.json", read_json(ROOT_COMPACTION_REPORT_PATH, {}))
        write_json(compat_dir / "packet_budget_status.json", read_json(COST_STATUS_PATH, {}))
        write_json(compat_dir / "task_memory_summary.json", read_json(TASK_MEMORY_STATUS_PATH, {}))
        write_json(compat_dir / "failure_memory_summary.json", read_json(FAILURE_MEMORY_STATUS_PATH, {}))
        write_json(compat_dir / "memory_graph_summary.json", read_json(MEMORY_GRAPH_STATUS_PATH, {}))
        write_json(compat_dir / "user_preferences.json", defaults_payload)
        write_jsonl(compat_dir / "architecture_learnings.jsonl", architecture_rows)
        write_jsonl(compat_dir / "technical_patterns.jsonl", technical_rows)
        write_jsonl(compat_dir / "workflow_learnings.jsonl", workflow_rows)
        synced.append(repo_root.as_posix())
    return synced


def sync_repo_cost_status(project: str | None) -> None:
    if not project:
        return
    repo_root = repo_root_for_project(project)
    if not repo_root:
        return
    compat_dir = repo_root / REPO_COMPAT_DIRNAME
    compat_dir.mkdir(parents=True, exist_ok=True)
    ensure_repo_compat_readme(compat_dir)
    write_json(compat_dir / "packet_budget_status.json", read_json(COST_STATUS_PATH, {}))


def sync_repo_task_memory_status(project: str | None) -> None:
    if not project:
        return
    repo_root = repo_root_for_project(project)
    if not repo_root:
        return
    compat_dir = repo_root / REPO_COMPAT_DIRNAME
    compat_dir.mkdir(parents=True, exist_ok=True)
    ensure_repo_compat_readme(compat_dir)
    write_json(compat_dir / "task_memory_summary.json", read_json(TASK_MEMORY_STATUS_PATH, {}))


def sync_repo_failure_memory_status(project: str | None) -> None:
    if not project:
        return
    repo_root = repo_root_for_project(project)
    if not repo_root:
        return
    compat_dir = repo_root / REPO_COMPAT_DIRNAME
    compat_dir.mkdir(parents=True, exist_ok=True)
    ensure_repo_compat_readme(compat_dir)
    write_json(compat_dir / "failure_memory_summary.json", read_json(FAILURE_MEMORY_STATUS_PATH, {}))


def sync_repo_memory_graph_status(project: str | None) -> None:
    if not project:
        return
    repo_root = repo_root_for_project(project)
    if not repo_root:
        return
    compat_dir = repo_root / REPO_COMPAT_DIRNAME
    compat_dir.mkdir(parents=True, exist_ok=True)
    ensure_repo_compat_readme(compat_dir)
    write_json(compat_dir / "memory_graph_summary.json", read_json(MEMORY_GRAPH_STATUS_PATH, {}))


def find_legacy_memory_dirs() -> list[str]:
    root = BASE.parent
    matches = []
    for pattern in ["legacy_memory", ".legacy_memory"]:
        for path in root.rglob(pattern):
            matches.append(path.as_posix())
    return sorted(set(matches))


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


DEFAULT_COST_CONFIG = {
    "version": 1,
    "budget_target_tokens": 3000,
    "soft_limit_tokens": 2600,
    "hard_limit_tokens": 3200,
    "summary_max_words": 20,
    "mandatory_summary_max_words": 28,
    "max_items_per_section": {
        "user_preferences": 5,
        "constraints": 5,
        "architecture_rules": 5,
        "relevant_memory": 5,
        "relevant_patterns": 5,
        "validation_recipes": 5,
        "relevant_failures": 3,
        "relevant_graph_context": 4,
        "repo_scope": 8,
        "known_patterns": 10,
    },
}


def yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)


def render_simple_yaml(payload: dict[str, Any], indent: int = 0) -> str:
    lines: list[str] = []
    prefix = " " * indent
    for key, value in payload.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(render_simple_yaml(value, indent + 2).rstrip())
        else:
            lines.append(f"{prefix}{key}: {yaml_scalar(value)}")
    return "\n".join(lines) + "\n"


def parse_simple_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw_line in path.read_text().splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()
        if ":" not in stripped:
            continue
        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        current = stack[-1][1]
        if value == "":
            child: dict[str, Any] = {}
            current[key] = child
            stack.append((indent, child))
            continue
        if value in {"true", "false"}:
            parsed: Any = value == "true"
        else:
            try:
                parsed = int(value)
            except ValueError:
                try:
                    parsed = float(value)
                except ValueError:
                    parsed = value
        current[key] = parsed
    return root


def cost_config() -> dict[str, Any]:
    ensure_cost_artifacts()
    payload = parse_simple_yaml(COST_CONFIG_PATH)
    merged = dict(DEFAULT_COST_CONFIG)
    for key, value in payload.items():
        if key == "max_items_per_section" and isinstance(value, dict):
            merged[key] = {**DEFAULT_COST_CONFIG[key], **value}
        else:
            merged[key] = value
    return merged


def ensure_cost_artifacts() -> None:
    ensure_dirs()
    if not COST_CONFIG_PATH.exists():
        write_text(COST_CONFIG_PATH, render_simple_yaml(DEFAULT_COST_CONFIG))
    if not COST_RULES_PATH.exists():
        write_text(
            COST_RULES_PATH,
            "# cost estimation rules\n\n"
            "- Estimation heuristic: `estimated_tokens ~= ceil(characters / 4) + structural_overhead`.\n"
            "- Lists add a small overhead per entry to stay stable across runs.\n"
            "- Duplicate entries are detected by `id`, `title`, or normalized summary text and collapsed deterministically.\n"
            "- Mandatory sections are preserved first: `user_preferences`, `constraints`, `architecture_rules`.\n"
            "- Optional sections are ranked by value-per-cost using existing deterministic scores plus section priority.\n"
            "- Compression keeps `id`, `title`, and a shortened summary before omission is considered.\n"
            "- Optimization status values: `within_budget`, `optimized`, `over_budget_after_optimization`.\n"
        )
    if not COST_STATUS_PATH.exists():
        write_json(
            COST_STATUS_PATH,
            {
                "version": 1,
                "generated_at": date.today().isoformat(),
                "optimization_events": 0,
                "over_budget_events": 0,
                "average_estimated_reduction_tokens": 0,
                "average_kept_ratio": 1.0,
                "last_status": "not_run",
                "last_task": "",
                "last_packet_path": "",
            },
        )
    if not COST_LATEST_REPORT_PATH.exists():
        write_text(
            COST_LATEST_REPORT_PATH,
            "# latest optimization report\n\n"
            "- Status: not_run\n"
            "- The optimizer has not processed a task packet yet.\n",
        )
    if not COST_HISTORY_PATH.exists():
        write_text(COST_HISTORY_PATH, "")


def ensure_task_memory_artifacts() -> None:
    ensure_dirs()
    write_json(
        TASK_MEMORY_TAXONOMY_PATH,
        {
            "version": 2,
            "installed_iteration": 8,
            "generated_at": date.today().isoformat(),
            "task_types": TASK_TYPES,
            "aliases": {
                "tests": "testing",
                "test": "testing",
                "general": "unknown",
                "generic": "unknown",
                "feature": "feature_work",
            },
        },
    )
    write_text(
        TASK_MEMORY_RULES_PATH,
        "# task resolution rules\n\n"
        "- Resolution order: explicit task type -> packet/runtime metadata -> heuristic task inference -> `unknown`.\n"
        "- Stable canonical task types: `bug_fixing`, `refactoring`, `testing`, `performance`, `architecture`, `feature_work`, `unknown`.\n"
        "- Existing markdown notes remain canonical; `.ai_context_engine/task_memory/` is derived from them.\n"
        "- Retrieval prefers the resolved task bucket first, then `unknown`, then deterministic fallback matches only when needed.\n"
        "- Ambiguous notes stay in `unknown` rather than being force-migrated.\n"
    )
    if not TASK_MEMORY_STATUS_PATH.exists():
        write_json(
            TASK_MEMORY_STATUS_PATH,
            {
                "version": 2,
                "installed_iteration": 8,
                "task_taxonomy_version": 2,
                "generated_at": date.today().isoformat(),
                "task_types": TASK_TYPES,
                "records_by_task_type": {task_type: 0 for task_type in TASK_TYPES},
                "resolved_task_packets": 0,
                "fallback_to_general_events": 0,
                "task_memory_write_count": 0,
                "manual_records": 0,
                "last_resolved_task_type": "unknown",
                "last_packet_path": "",
            },
        )
    if not TASK_MEMORY_HISTORY_PATH.exists():
        write_text(TASK_MEMORY_HISTORY_PATH, "")


def build_task_memory_artifacts(rows: list[dict[str, Any]]) -> dict[str, int]:
    ensure_task_memory_artifacts()
    records_by_task_type = {task_type: 0 for task_type in TASK_TYPES}
    for task_type in TASK_TYPES:
        derived_rows = [
            row
            for row in rows
            if row.get("type") != "user_preference" and normalize_task_type(row.get("task_type")) == task_type
        ]
        task_rows = derived_rows + manual_task_memory_records(task_type)
        task_rows.sort(key=lambda row: (row.get("project") or "", row.get("path") or "", row.get("id") or ""))
        records_by_task_type[task_type] = len(task_rows)
        write_jsonl(TASK_MEMORY_DIR / task_type / "records.jsonl", task_rows)
        summary = summarize_task_memory_rows(task_type, task_rows)
        write_json(
            TASK_MEMORY_DIR / task_type / "summary.json",
            {
                "task_type": task_type,
                "records": len(task_rows),
                "derived_records": len(derived_rows),
                "manual_records": max(0, len(task_rows) - len(derived_rows)),
                "projects": sorted({str(row.get("project")) for row in task_rows if row.get("project")}),
                "updated_at": date.today().isoformat(),
                **summary,
            },
        )
        write_text(
            TASK_MEMORY_DIR / task_type / "summary.md",
            "\n".join(
                [
                    f"# {task_type} task memory",
                    "",
                    f"- Records: {len(task_rows)}",
                    f"- Derived records: {len(derived_rows)}",
                    f"- Manual records: {max(0, len(task_rows) - len(derived_rows))}",
                    f"- Common locations: {', '.join(summary['common_locations']) if summary['common_locations'] else 'none'}",
                    f"- Patterns: {', '.join(summary['patterns']) if summary['patterns'] else 'none'}",
                    f"- Preferred validation: {'; '.join(summary['preferred_validation']) if summary['preferred_validation'] else 'none'}",
                ]
            )
            + "\n",
        )
    for legacy_task_type, canonical_task_type in LEGACY_TASK_TYPE_ALIASES.items():
        legacy_dir = TASK_MEMORY_DIR / legacy_task_type
        canonical_dir = TASK_MEMORY_DIR / canonical_task_type
        legacy_dir.mkdir(parents=True, exist_ok=True)
        write_jsonl(legacy_dir / "records.jsonl", read_jsonl(canonical_dir / "records.jsonl"))
        write_json(
            legacy_dir / "summary.json",
            {
                **read_json(canonical_dir / "summary.json", {}),
                "task_type": legacy_task_type,
                "alias_of": canonical_task_type,
                "updated_at": date.today().isoformat(),
            },
        )
    previous_status = read_json(TASK_MEMORY_STATUS_PATH, {})
    write_json(
        TASK_MEMORY_STATUS_PATH,
        {
            **previous_status,
            "version": 2,
            "installed_iteration": 8,
            "task_taxonomy_version": 2,
            "generated_at": date.today().isoformat(),
            "task_types": TASK_TYPES,
            "records_by_task_type": records_by_task_type,
            "task_memory_write_count": sum(records_by_task_type.values()),
            "manual_records": sum(len(manual_task_memory_records(task_type)) for task_type in TASK_TYPES),
        },
    )
    return records_by_task_type


def update_task_memory_status(packet: dict[str, Any], packet_path: Path) -> None:
    status = read_json(TASK_MEMORY_STATUS_PATH, {})
    packets = int(status.get("resolved_task_packets", 0) or 0) + 1
    fallback_event = 1 if packet.get("task_memory", {}).get("fallback_to_general") else 0
    updated = {
        **status,
        "version": 2,
        "installed_iteration": 8,
        "task_taxonomy_version": 2,
        "generated_at": date.today().isoformat(),
        "resolved_task_packets": packets,
        "fallback_to_general_events": int(status.get("fallback_to_general_events", 0) or 0) + fallback_event,
        "last_resolved_task_type": packet.get("task_type", "unknown"),
        "last_packet_path": packet_path.as_posix(),
        "last_queried_categories": packet.get("task_memory", {}).get("queried_categories", []),
    }
    write_json(TASK_MEMORY_STATUS_PATH, updated)
    history = read_jsonl(TASK_MEMORY_HISTORY_PATH)
    history.append(
        {
            "generated_at": date.today().isoformat(),
            "task": packet.get("task"),
            "task_type": packet.get("task_type", "unknown"),
            "task_memory_used": bool(packet.get("task_memory", {}).get("task_specific_memory_used")),
            "fallback_to_general": bool(packet.get("task_memory", {}).get("fallback_to_general")),
            "queried_categories": packet.get("task_memory", {}).get("queried_categories", []),
        }
    )
    write_jsonl(TASK_MEMORY_HISTORY_PATH, history[-50:])


def ensure_failure_memory_artifacts() -> None:
    ensure_dirs()
    if not FAILURE_MEMORY_STATUS_PATH.exists():
        write_json(
            FAILURE_MEMORY_STATUS_PATH,
            {
                "version": 1,
                "generated_at": date.today().isoformat(),
                "records_total": 0,
                "manual_records": 0,
                "derived_records": 0,
                "retrieval_events": 0,
                "write_events": 0,
                "last_packet_path": "",
                "last_recorded_failure_id": "",
            },
        )
    if not FAILURE_MEMORY_INDEX_PATH.exists():
        write_json(FAILURE_MEMORY_INDEX_PATH, {"version": 1, "generated_at": date.today().isoformat(), "records": []})
    if not FAILURE_MEMORY_SUMMARY_PATH.exists():
        write_text(
            FAILURE_MEMORY_SUMMARY_PATH,
            "# common failure patterns\n\n"
            "- No failure patterns recorded yet.\n",
        )


def extract_related_commands(text: str) -> list[str]:
    return sorted({match.strip() for match in re.findall(r"`([^`]+)`", text) if match.strip()})[:6]


def derive_failure_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    derived = []
    for row in rows:
        if row.get("type") not in {"failure_mode", "debugging_pattern", "validation_recipe"}:
            continue
        combined_text = "\n".join(
            [
                str(row.get("title", "")),
                str(row.get("summary", "")),
                " ".join(section.get("text", "") for section in row.get("sections", [])),
            ]
        )
        failure_id = f"derived_{slugify(str(row.get('id', 'failure')))}"
        derived.append(
            {
                "id": failure_id,
                "category": classify_failure_category(combined_text),
                "title": str(row.get("title", "Known failure pattern")),
                "symptoms": [str(row.get("summary", ""))][:1] + [section.get("text", "") for section in row.get("sections", [])[:2] if section.get("text")],
                "root_cause": str(row.get("summary", "")),
                "solution": next((section.get("text", "") for section in row.get("sections", []) if "validation" in str(section.get("section", "")).lower() or "check" in str(section.get("section", "")).lower()), "Inspect the referenced note and apply the documented fix path."),
                "files_involved": list(row.get("files_involved", [])),
                "related_commands": extract_related_commands(combined_text),
                "reusability": "high" if float(row.get("relevance_score", 0.6)) >= 0.7 else "medium",
                "confidence": round(min(0.95, max(0.45, float(row.get("relevance_score", 0.6)))), 2),
                "first_seen_at": str(row.get("last_verified", date.today().isoformat())),
                "last_seen_at": date.today().isoformat(),
                "occurrences": max(1, sum(1 for section in row.get("sections", []) if section.get("text"))),
                "status": "resolved",
                "notes": f"Derived from {row.get('path', '')}",
                "source": "derived_from_record",
                "source_record_id": row.get("id"),
            }
        )
    return derived


def manual_failure_records() -> list[dict[str, Any]]:
    ensure_failure_memory_artifacts()
    rows = []
    for path in sorted(FAILURE_MEMORY_RECORDS_DIR.glob("*.json")):
        payload = read_json(path, {})
        if payload.get("source") == "derived_from_record":
            continue
        if payload:
            rows.append(payload)
    return rows


def build_failure_memory_artifacts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ensure_failure_memory_artifacts()
    manual_rows = manual_failure_records()
    derived_rows = derive_failure_records(rows)
    derived_ids = {row["id"] for row in derived_rows}
    for path in sorted(FAILURE_MEMORY_RECORDS_DIR.glob("derived_*.json")):
        if path.stem not in derived_ids:
            path.unlink()
    for row in derived_rows:
        write_json(FAILURE_MEMORY_RECORDS_DIR / f"{row['id']}.json", row)
    combined = sorted(manual_rows + derived_rows, key=lambda row: (-int(row.get("occurrences", 1)), -float(row.get("confidence", 0.5)), str(row.get("id", ""))))
    write_json(
        FAILURE_MEMORY_INDEX_PATH,
        {
            "version": 1,
            "generated_at": date.today().isoformat(),
            "records": [
                {
                    "id": row["id"],
                    "category": row.get("category", "unknown"),
                    "title": row.get("title", ""),
                    "confidence": row.get("confidence", 0.5),
                    "occurrences": row.get("occurrences", 1),
                    "status": row.get("status", "resolved"),
                    "source": row.get("source", "manual"),
                }
                for row in combined
            ],
        },
    )
    summary_lines = [
        "# common failure patterns",
        "",
    ]
    if not combined:
        summary_lines.append("- No failure patterns recorded yet.")
    else:
        for row in combined[:12]:
            summary_lines.append(f"- `{row['category']}` | `{row['id']}` | occ {row.get('occurrences', 1)} | {row.get('title', '')}")
    write_text(FAILURE_MEMORY_SUMMARY_PATH, "\n".join(summary_lines) + "\n")
    previous = read_json(FAILURE_MEMORY_STATUS_PATH, {})
    status = {
        **previous,
        "version": 1,
        "generated_at": date.today().isoformat(),
        "records_total": len(combined),
        "manual_records": len(manual_rows),
        "derived_records": len(derived_rows),
    }
    write_json(FAILURE_MEMORY_STATUS_PATH, status)
    return status


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
    ensure_failure_memory_artifacts()
    path = FAILURE_MEMORY_RECORDS_DIR / f"{slugify(failure_id)}.json"
    existing = read_json(path, {}) if path.exists() else {}
    today = date.today().isoformat()
    record = {
        "id": slugify(failure_id),
        "category": category if category in FAILURE_CATEGORIES else "unknown",
        "title": title or existing.get("title", "Known failure"),
        "symptoms": symptoms or existing.get("symptoms", []),
        "root_cause": root_cause or existing.get("root_cause", ""),
        "solution": solution or existing.get("solution", ""),
        "files_involved": files_involved or existing.get("files_involved", []),
        "related_commands": related_commands or existing.get("related_commands", []),
        "reusability": existing.get("reusability", "high"),
        "confidence": round(float(confidence or existing.get("confidence", 0.75)), 2),
        "first_seen_at": existing.get("first_seen_at", today),
        "last_seen_at": today,
        "occurrences": int(existing.get("occurrences", 0) or 0) + 1,
        "status": "resolved",
        "notes": notes or existing.get("notes", ""),
        "source": "manual",
    }
    write_json(path, record)
    status = build_failure_memory_artifacts([normalize_record(row) for row in load_records()])
    build_memory_graph_artifacts([normalize_record(row) for row in load_records()])
    status["write_events"] = int(status.get("write_events", 0) or 0) + 1
    status["last_recorded_failure_id"] = record["id"]
    write_json(FAILURE_MEMORY_STATUS_PATH, status)
    return record


def should_consult_failure_memory(task: str, task_type: str) -> bool:
    task_l = task.lower()
    if task_type in {"bug_fixing", "testing", "performance"}:
        return True
    return any(keyword in task_l for keyword in ["fail", "error", "regression", "broken", "flaky", "trap", "cannot", "build", "test"])


def rank_failure_records(task: str) -> list[dict[str, Any]]:
    ensure_failure_memory_artifacts()
    index_rows = read_json(FAILURE_MEMORY_INDEX_PATH, {}).get("records", [])
    ranked = []
    for item in index_rows:
        full = read_json(FAILURE_MEMORY_RECORDS_DIR / f"{item['id']}.json", {})
        haystack = " ".join(
            [
                full.get("title", ""),
                full.get("category", ""),
                " ".join(full.get("symptoms", [])),
                full.get("root_cause", ""),
                full.get("solution", ""),
                " ".join(full.get("files_involved", [])),
                " ".join(full.get("related_commands", [])),
            ]
        )
        lexical = score_match(task, haystack) / 100
        confidence = float(full.get("confidence", 0.5))
        occurrences = min(int(full.get("occurrences", 1)), 5) / 5
        total = round(lexical * 0.6 + confidence * 0.25 + occurrences * 0.15, 4)
        if total >= 0.18:
            ranked.append((total, full))
    ranked.sort(key=lambda item: (-item[0], -int(item[1].get("occurrences", 1)), item[1].get("id", "")))
    return [{"score": score, **row} for score, row in ranked[:3]]


def update_failure_memory_status(packet: dict[str, Any], packet_path: Path) -> None:
    status = read_json(FAILURE_MEMORY_STATUS_PATH, {})
    updated = {
        **status,
        "version": 1,
        "generated_at": date.today().isoformat(),
        "retrieval_events": int(status.get("retrieval_events", 0) or 0) + (1 if packet.get("failure_memory", {}).get("failure_memory_used") else 0),
        "last_packet_path": packet_path.as_posix(),
    }
    write_json(FAILURE_MEMORY_STATUS_PATH, updated)


def graph_node_id(node_type: str, raw_id: str) -> str:
    return f"{node_type}:{slugify(raw_id)}"


def edge_identity(from_id: str, to_id: str, relation: str) -> str:
    return f"{from_id}|{relation}|{to_id}"


def infer_repository_area(row: dict[str, Any]) -> str | None:
    if row.get("project") and row.get("subproject"):
        return f"{row['project']}/{row['subproject']}"
    if row.get("project"):
        return str(row["project"])
    path = str(row.get("path", ""))
    if path.startswith("projects/"):
        parts = path.split("/")
        if len(parts) >= 3:
            return f"{parts[1]}/{parts[2]}"
    return None


def graph_node_type_for_record(row: dict[str, Any]) -> str:
    if row.get("type") == "architecture_decision":
        return "architecture_decision"
    return "memory_entry"


def graph_label_index_key(label: str) -> str:
    return slugify(label).replace("_", " ")


def ensure_memory_graph_artifacts() -> None:
    ensure_dirs()
    if not MEMORY_GRAPH_STATUS_PATH.exists():
        write_json(
            MEMORY_GRAPH_STATUS_PATH,
            {
                "version": 1,
                "installed_iteration": 9,
                "generated_at": date.today().isoformat(),
                "nodes_total": 0,
                "edges_total": 0,
                "expansion_events": 0,
                "last_seed_count": 0,
                "last_expansion_depth": 0,
                "last_packet_path": "",
                "last_graph_hit_count": 0,
            },
        )
    for path in [MEMORY_GRAPH_NODES_PATH, MEMORY_GRAPH_EDGES_PATH]:
        if not path.exists():
            write_jsonl(path, [])
    for path in [MEMORY_GRAPH_LABEL_INDEX_PATH, MEMORY_GRAPH_TYPE_INDEX_PATH, MEMORY_GRAPH_RELATION_INDEX_PATH]:
        if not path.exists():
            write_json(path, {})
    if not MEMORY_GRAPH_SNAPSHOT_PATH.exists():
        write_json(
            MEMORY_GRAPH_SNAPSHOT_PATH,
            {
                "version": 1,
                "generated_at": date.today().isoformat(),
                "nodes_sample": [],
                "edges_sample": [],
            },
        )


def graph_add_node(nodes: dict[str, dict[str, Any]], *, node_id: str, node_type: str, label: str, source: str, confidence: float = 0.7, tags: list[str] | None = None, metadata: dict[str, Any] | None = None) -> None:
    if node_type not in GRAPH_NODE_TYPES:
        node_type = "concept"
    current = nodes.get(node_id)
    payload = {
        "id": node_id,
        "type": node_type,
        "label": label,
        "source": source,
        "last_updated_at": date.today().isoformat(),
        "confidence": round(confidence, 2),
        "tags": sorted({tag for tag in (tags or []) if tag}),
        "metadata": metadata or {},
    }
    if current:
        payload["confidence"] = round(max(float(current.get("confidence", 0.5)), payload["confidence"]), 2)
        payload["tags"] = sorted(set(current.get("tags", [])) | set(payload["tags"]))
        payload["metadata"] = {**current.get("metadata", {}), **payload["metadata"]}
    nodes[node_id] = payload


def graph_add_edge(edges: dict[str, dict[str, Any]], *, from_id: str, to_id: str, relation: str, source: str, confidence: float = 0.65) -> None:
    if relation not in GRAPH_RELATIONS:
        relation = "relates_to"
    identity = edge_identity(from_id, to_id, relation)
    current = edges.get(identity)
    payload = {
        "id": identity,
        "from": from_id,
        "to": to_id,
        "relation": relation,
        "source": source,
        "confidence": round(confidence, 2),
        "timestamp": date.today().isoformat(),
    }
    if current:
        payload["confidence"] = round(max(float(current.get("confidence", 0.5)), payload["confidence"]), 2)
    edges[identity] = payload


def build_memory_graph_artifacts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ensure_memory_graph_artifacts()
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    normalized_rows = [normalize_record(row) for row in rows] + manual_task_memory_records()
    for task_type in TASK_TYPES:
        task_node_id = graph_node_id("task_type", task_type)
        graph_add_node(nodes, node_id=task_node_id, node_type="task_type", label=task_type, source="task_taxonomy", confidence=0.95, tags=[task_type])
    for row in normalized_rows:
        node_type = graph_node_type_for_record(row)
        record_node_id = graph_node_id(node_type, str(row.get("id", "")))
        graph_add_node(
            nodes,
            node_id=record_node_id,
            node_type=node_type,
            label=str(row.get("title") or row.get("id") or "memory entry"),
            source=str(row.get("source", "record")),
            confidence=float(row.get("relevance_score", 0.65)),
            tags=list(row.get("tags", [])),
            metadata={
                "record_id": row.get("id"),
                "record_type": row.get("type"),
                "path": row.get("path"),
                "task_type": row.get("task_type"),
            },
        )
        task_type = normalize_task_type(row.get("task_type"))
        graph_add_edge(edges, from_id=record_node_id, to_id=graph_node_id("task_type", task_type), relation="belongs_to_task_type", source="record_task_type", confidence=0.9)
        repo_area = infer_repository_area(row)
        if repo_area:
            area_node_id = graph_node_id("repository_area", repo_area)
            graph_add_node(nodes, node_id=area_node_id, node_type="repository_area", label=repo_area, source="path_heuristic", confidence=0.78, tags=[repo_area])
            graph_add_edge(edges, from_id=record_node_id, to_id=area_node_id, relation="associated_with", source="record_area", confidence=0.78)
        for path in row.get("files_involved", [])[:6]:
            file_node_id = graph_node_id("file", path)
            graph_add_node(nodes, node_id=file_node_id, node_type="file", label=path, source="files_involved", confidence=0.85, tags=[task_type] if task_type else [])
            graph_add_edge(edges, from_id=record_node_id, to_id=file_node_id, relation="referenced_by", source="record_file", confidence=0.85)
            module_label = str(Path(path).parent.as_posix() or ".")
            module_node_id = graph_node_id("module", module_label)
            graph_add_node(nodes, node_id=module_node_id, node_type="module", label=module_label, source="path_parent", confidence=0.72, tags=[repo_area] if repo_area else [])
            graph_add_edge(edges, from_id=file_node_id, to_id=module_node_id, relation="located_in", source="path_parent", confidence=0.72)
        for tag in row.get("tags", [])[:6]:
            concept_node_id = graph_node_id("concept", tag)
            graph_add_node(nodes, node_id=concept_node_id, node_type="concept", label=tag, source="record_tag", confidence=0.68, tags=[tag])
            graph_add_edge(edges, from_id=record_node_id, to_id=concept_node_id, relation="associated_with", source="record_tag", confidence=0.68)
    for failure in read_json(FAILURE_MEMORY_INDEX_PATH, {}).get("records", []):
        full = read_json(FAILURE_MEMORY_RECORDS_DIR / f"{failure['id']}.json", {})
        if not full:
            continue
        failure_node_id = graph_node_id("failure_pattern", str(full.get("id", "")))
        solution_node_id = graph_node_id("solution", str(full.get("id", "")))
        graph_add_node(nodes, node_id=failure_node_id, node_type="failure_pattern", label=str(full.get("title", full.get("id", "failure"))), source="failure_memory", confidence=float(full.get("confidence", 0.75)), tags=[str(full.get("category", "unknown"))])
        graph_add_node(nodes, node_id=solution_node_id, node_type="solution", label=f"solution:{full.get('title', full.get('id', 'failure'))}", source="failure_memory", confidence=float(full.get("confidence", 0.75)), tags=["solution"])
        graph_add_edge(edges, from_id=failure_node_id, to_id=solution_node_id, relation="fixed_by", source="failure_solution", confidence=float(full.get("confidence", 0.75)))
        category_node_id = graph_node_id("concept", str(full.get("category", "unknown")))
        graph_add_node(nodes, node_id=category_node_id, node_type="concept", label=str(full.get("category", "unknown")), source="failure_category", confidence=0.7, tags=["failure"])
        graph_add_edge(edges, from_id=failure_node_id, to_id=category_node_id, relation="associated_with", source="failure_category", confidence=0.7)
        for path in full.get("files_involved", [])[:6]:
            file_node_id = graph_node_id("file", path)
            graph_add_node(nodes, node_id=file_node_id, node_type="file", label=path, source="failure_memory", confidence=0.72, tags=["failure"])
            graph_add_edge(edges, from_id=failure_node_id, to_id=file_node_id, relation="affects", source="failure_file", confidence=0.74)
        source_record_id = full.get("source_record_id")
        if source_record_id:
            candidate_memory_nodes = [graph_node_id("memory_entry", str(source_record_id)), graph_node_id("architecture_decision", str(source_record_id))]
            for candidate in candidate_memory_nodes:
                if candidate in nodes:
                    graph_add_edge(edges, from_id=failure_node_id, to_id=candidate, relation="derived_from", source="failure_source_record", confidence=0.86)
                    break
    node_rows = sorted(nodes.values(), key=lambda row: (row["type"], row["label"], row["id"]))
    edge_rows = sorted(edges.values(), key=lambda row: (row["relation"], row["from"], row["to"]))
    write_jsonl(MEMORY_GRAPH_NODES_PATH, node_rows)
    write_jsonl(MEMORY_GRAPH_EDGES_PATH, edge_rows)
    label_index: dict[str, list[str]] = defaultdict(list)
    type_index: dict[str, list[str]] = defaultdict(list)
    relation_index: dict[str, list[str]] = defaultdict(list)
    for node in node_rows:
        label_index[graph_label_index_key(str(node.get("label", "")))].append(node["id"])
        type_index[str(node.get("type", "concept"))].append(node["id"])
    for edge in edge_rows:
        relation_index[str(edge.get("relation", "relates_to"))].append(edge["id"])
    write_json(MEMORY_GRAPH_LABEL_INDEX_PATH, dict(sorted(label_index.items())))
    write_json(MEMORY_GRAPH_TYPE_INDEX_PATH, dict(sorted(type_index.items())))
    write_json(MEMORY_GRAPH_RELATION_INDEX_PATH, dict(sorted(relation_index.items())))
    previous = read_json(MEMORY_GRAPH_STATUS_PATH, {})
    status = {
        **previous,
        "version": 1,
        "installed_iteration": 9,
        "generated_at": date.today().isoformat(),
        "nodes_total": len(node_rows),
        "edges_total": len(edge_rows),
        "node_types": {node_type: len(type_index.get(node_type, [])) for node_type in sorted(GRAPH_NODE_TYPES)},
        "relation_types": {relation: len(relation_index.get(relation, [])) for relation in sorted(GRAPH_RELATIONS)},
    }
    write_json(MEMORY_GRAPH_STATUS_PATH, status)
    write_json(
        MEMORY_GRAPH_SNAPSHOT_PATH,
        {
            "version": 1,
            "generated_at": date.today().isoformat(),
            "nodes_sample": node_rows[:12],
            "edges_sample": edge_rows[:12],
        },
    )
    return status


def graph_nodes() -> dict[str, dict[str, Any]]:
    ensure_memory_graph_artifacts()
    return {row["id"]: row for row in read_jsonl(MEMORY_GRAPH_NODES_PATH) if row.get("id")}


def graph_edges() -> list[dict[str, Any]]:
    ensure_memory_graph_artifacts()
    return read_jsonl(MEMORY_GRAPH_EDGES_PATH)


def graph_find_nodes(query: str) -> list[dict[str, Any]]:
    nodes = graph_nodes()
    q = query.strip().lower()
    if not q:
        return []
    ranked = []
    for node in nodes.values():
        haystack = " ".join([str(node.get("label", "")), str(node.get("id", "")), " ".join(node.get("tags", []))])
        score = score_match(q, haystack)
        if score > 0:
            ranked.append((score + int(float(node.get("confidence", 0.5)) * 10), node))
    ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
    return [node for _, node in ranked[:10]]


def graph_neighbors(node_id: str, relation: str | None = None) -> list[dict[str, Any]]:
    nodes = graph_nodes()
    results = []
    for edge in graph_edges():
        if edge.get("from") != node_id:
            continue
        if relation and edge.get("relation") != relation:
            continue
        neighbor = nodes.get(str(edge.get("to")))
        if not neighbor:
            continue
        results.append({"edge": edge, "node": neighbor})
    results.sort(key=lambda item: (-float(item["edge"].get("confidence", 0.5)), item["node"]["id"]))
    return results


def graph_expand(seed_ids: list[str], *, depth: int = 1, node_budget: int = 8, edge_budget: int = 12, task_type: str | None = None, repository_area: str | None = None) -> dict[str, Any]:
    nodes = graph_nodes()
    if not nodes:
        return {"nodes": [], "edges": [], "connected_record_ids": [], "depth_used": 0}
    frontier = [seed_id for seed_id in seed_ids if seed_id in nodes]
    visited_nodes: set[str] = set(frontier)
    visited_edges: list[dict[str, Any]] = []
    collected_nodes: list[dict[str, Any]] = [nodes[seed_id] for seed_id in frontier]
    current_depth = 0
    while frontier and current_depth < max(0, depth) and len(collected_nodes) < node_budget and len(visited_edges) < edge_budget:
        next_frontier: list[str] = []
        for current in frontier:
            for item in graph_neighbors(current):
                neighbor = item["node"]
                edge = item["edge"]
                if repository_area and neighbor.get("type") == "repository_area" and repository_area not in str(neighbor.get("label", "")):
                    continue
                if task_type and neighbor.get("type") == "task_type" and normalize_task_type(neighbor.get("label")) != normalize_task_type(task_type):
                    continue
                if neighbor["id"] not in visited_nodes:
                    visited_nodes.add(neighbor["id"])
                    collected_nodes.append(neighbor)
                    next_frontier.append(neighbor["id"])
                if len(visited_edges) < edge_budget:
                    visited_edges.append(edge)
                if len(collected_nodes) >= node_budget or len(visited_edges) >= edge_budget:
                    break
            if len(collected_nodes) >= node_budget or len(visited_edges) >= edge_budget:
                break
        frontier = next_frontier
        current_depth += 1
    connected_record_ids = []
    for node in collected_nodes:
        record_id = str(node.get("metadata", {}).get("record_id", "")).strip()
        if record_id:
            connected_record_ids.append(record_id)
    return {
        "nodes": collected_nodes[:node_budget],
        "edges": visited_edges[:edge_budget],
        "connected_record_ids": sorted(set(connected_record_ids)),
        "depth_used": current_depth,
    }


def update_memory_graph_status(packet: dict[str, Any], packet_path: Path) -> None:
    status = read_json(MEMORY_GRAPH_STATUS_PATH, {})
    graph_meta = packet.get("memory_graph", {})
    updated = {
        **status,
        "version": 1,
        "installed_iteration": 9,
        "generated_at": date.today().isoformat(),
        "expansion_events": int(status.get("expansion_events", 0) or 0) + (1 if graph_meta.get("graph_used") else 0),
        "last_seed_count": int(graph_meta.get("seed_count", 0) or 0),
        "last_expansion_depth": int(graph_meta.get("expansion_depth_used", 0) or 0),
        "last_graph_hit_count": int(graph_meta.get("graph_hits", 0) or 0),
        "last_packet_path": packet_path.as_posix(),
    }
    write_json(MEMORY_GRAPH_STATUS_PATH, updated)


def ensure_context_metrics_artifacts() -> None:
    ensure_dirs()
    if not CONTEXT_TASK_LOGS_PATH.exists():
        write_text(CONTEXT_TASK_LOGS_PATH, "")
    if not CONTEXT_BASELINE_PATH.exists():
        write_json(
            CONTEXT_BASELINE_PATH,
            {
                "version": 1,
                "generated_at": date.today().isoformat(),
                "source": "derived_from_packets",
                "assumptions": {
                    "average_task_context_tokens_without_engine": 3200,
                    "average_task_context_tokens_with_engine": 1900,
                },
            },
        )
    if not CONTEXT_WEEKLY_SUMMARY_PATH.exists():
        write_json(
            CONTEXT_WEEKLY_SUMMARY_PATH,
            {
                "version": 2,
                "generated_at": date.today().isoformat(),
                "confidence": "low",
                "tasks_sampled": 0,
                "repeated_tasks": 0,
                "phase_events_sampled": 0,
                "telemetry_granularity": "task_plus_phase",
                "estimated_context_reduction": {"range": [0.0, 0.0], "point": 0.0},
                "estimated_total_token_reduction": {"range": [0.0, 0.0]},
                "estimated_latency_improvement": {"range": [0.0, 0.0]},
                "estimated_cost_reduction": {"range": [0.0, 0.0]},
                "top_expensive_phases": [],
            },
        )


def estimate_tokens(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (dict, list)):
        return max(1, len(json.dumps(value, ensure_ascii=False)) // 4)
    return max(1, len(str(value)) // 4)


def summarize_granular_telemetry(log_rows: list[dict[str, Any]]) -> dict[str, Any]:
    task_rows = [row for row in log_rows if row.get("level") == "task"]
    phase_rows = [row for row in log_rows if row.get("level") == "phase"]
    if not task_rows:
        return read_json(CONTEXT_WEEKLY_SUMMARY_PATH, {})
    context_reductions = [float(row.get("context_reduction_ratio", 0.0) or 0.0) for row in task_rows]
    token_reductions = [float(row.get("token_reduction_estimate", 0.0) or 0.0) for row in task_rows]
    latency_improvements = [float(row.get("latency_reduction_estimate", 0.0) or 0.0) for row in task_rows]
    phase_costs: dict[str, int] = defaultdict(int)
    for row in phase_rows:
        phase_costs[str(row.get("phase_name", "unknown"))] += int(row.get("estimated_tokens", 0) or 0)
    point = sum(context_reductions) / len(context_reductions)
    token_point = sum(token_reductions) / len(token_reductions)
    latency_point = sum(latency_improvements) / len(latency_improvements)
    return {
        "version": 2,
        "generated_at": date.today().isoformat(),
        "confidence": "medium" if len(task_rows) >= 5 else "low",
        "tasks_sampled": len(task_rows),
        "repeated_tasks": max(0, len(task_rows) - len({row.get("task_summary") for row in task_rows})),
        "phase_events_sampled": len(phase_rows),
        "telemetry_granularity": "task_plus_phase",
        "estimated_context_reduction": {
            "range": [round(max(0.0, point * 0.85), 4), round(min(1.0, point * 1.15), 4)],
            "point": round(point, 4),
        },
        "estimated_total_token_reduction": {
            "range": [round(max(0.0, token_point * 0.85), 2), round(max(0.0, token_point * 1.15), 2)],
        },
        "estimated_latency_improvement": {
            "range": [round(max(0.0, latency_point * 0.85), 2), round(max(0.0, latency_point * 1.15), 2)],
        },
        "estimated_cost_reduction": {
            "range": [round(max(0.0, token_point * 0.00001), 4), round(max(0.0, token_point * 0.00002), 4)],
        },
        "top_expensive_phases": [
            {"phase_name": name, "estimated_tokens": tokens}
            for name, tokens in sorted(phase_costs.items(), key=lambda item: (-item[1], item[0]))[:5]
        ],
    }


def record_granular_telemetry(packet: dict[str, Any], packet_path: Path, optimization_report: dict[str, Any]) -> dict[str, Any]:
    ensure_context_metrics_artifacts()
    task_id = str(packet.get("task_id") or slugify(str(packet.get("task_summary", packet.get("task", "task")))))
    phases = list(packet.get("telemetry_granularity", {}).get("phases", []))
    task_tokens_before = int(optimization_report.get("estimated_tokens_before", 0) or 0)
    task_tokens_after = int(optimization_report.get("estimated_tokens_after", 0) or 0)
    reduction = max(0, task_tokens_before - task_tokens_after)
    task_row = {
        "generated_at": now_iso(),
        "task_id": task_id,
        "level": "task",
        "task_summary": packet.get("task_summary", packet.get("task")),
        "task_type": packet.get("task_type", "unknown"),
        "phase_count": len(phases),
        "packet_path": packet_path.as_posix(),
        "estimated_tokens_before": task_tokens_before,
        "estimated_tokens_after": task_tokens_after,
        "token_reduction_estimate": reduction,
        "context_reduction_ratio": round((reduction / task_tokens_before), 4) if task_tokens_before else 0.0,
        "latency_reduction_estimate": round(reduction * 0.002, 4),
    }
    phase_rows = []
    for index, phase in enumerate(phases):
        estimated_tokens = int(phase.get("estimated_tokens", 0) or 0)
        phase_rows.append(
            {
                "generated_at": now_iso(),
                "task_id": task_id,
                "parent_task_id": task_id,
                "level": "phase",
                "phase_name": phase.get("phase_name", f"phase_{index + 1}"),
                "sequence": index + 1,
                "estimated_tokens": estimated_tokens,
                "notes": phase.get("notes", ""),
            }
        )
    existing = read_jsonl(CONTEXT_TASK_LOGS_PATH)
    write_jsonl(CONTEXT_TASK_LOGS_PATH, (existing + [task_row] + phase_rows)[-400:])
    summary = summarize_granular_telemetry(read_jsonl(CONTEXT_TASK_LOGS_PATH))
    write_json(CONTEXT_WEEKLY_SUMMARY_PATH, summary)
    return summary


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
                "installed_iteration": current_engine_iteration(),
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
    existing = (previous or {}).get("source_name")
    if existing:
        return str(existing)
    base = sanitize_source_name(source_path.stem if source_kind == "inbox" else f"{source_path.stem}_{hashlib.md5(source_key.encode('utf-8')).hexdigest()[:8]}")
    return base


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
                "installed_iteration": current_engine_iteration(),
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
            "installed_iteration": current_engine_iteration(),
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
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        parts = []
        for key in ["id", "key", "title", "summary", "path"]:
            value = item.get(key)
            if value:
                parts.append(str(value))
        if "value" in item:
            parts.append(json.dumps(item.get("value"), ensure_ascii=False, sort_keys=True))
        return " | ".join(parts)
    return json.dumps(item, ensure_ascii=False, sort_keys=True)


def estimate_tokens_from_text(text: str, structural_overhead: int = 0) -> int:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return max(1, structural_overhead)
    return max(1, (len(compact) + 3) // 4 + structural_overhead)


def estimate_packet_tokens(packet: dict[str, Any]) -> dict[str, Any]:
    sections: dict[str, int] = {}
    for key, value in packet.items():
        if key in {"context_budget", "optimization_report"}:
            continue
        if isinstance(value, list):
            section_tokens = 2
            for item in value:
                section_tokens += estimate_tokens_from_text(packet_item_text(item), structural_overhead=4)
        elif isinstance(value, dict):
            section_tokens = estimate_tokens_from_text(json.dumps(value, ensure_ascii=False, sort_keys=True), structural_overhead=6)
        else:
            section_tokens = estimate_tokens_from_text(str(value), structural_overhead=2)
        sections[key] = section_tokens
    total = sum(sections.values())
    return {"estimated_total_tokens": total, "sections": sections}


SECTION_RULES = {
    "user_preferences": {"mandatory": True, "priority": 4.0},
    "constraints": {"mandatory": True, "priority": 3.8},
    "architecture_rules": {"mandatory": True, "priority": 3.6},
    "architecture_decisions": {"mandatory": False, "priority": 2.8, "mirror_of": "architecture_rules"},
    "relevant_memory": {"mandatory": False, "priority": 3.2},
    "relevant_patterns": {"mandatory": False, "priority": 2.4},
    "validation_recipes": {"mandatory": False, "priority": 2.3},
    "relevant_failures": {"mandatory": False, "priority": 3.0},
    "relevant_graph_context": {"mandatory": False, "priority": 2.9},
    "knowledge_artifacts": {"mandatory": False, "priority": 2.7},
    "repo_scope": {"mandatory": False, "priority": 1.4},
    "relevant_paths": {"mandatory": False, "priority": 1.4, "mirror_of": "repo_scope"},
    "known_patterns": {"mandatory": False, "priority": 1.1},
}


def item_identity(item: Any) -> str:
    if isinstance(item, dict):
        for key in ["id", "key", "title", "path"]:
            value = item.get(key)
            if value:
                return str(value)
        if item.get("summary"):
            return slugify(str(item["summary"]))
    return slugify(str(item))


def item_value(item: Any, section_name: str) -> float:
    if isinstance(item, dict):
        base = float(item.get("score", item.get("relevance_score", 0.55)) or 0.55)
        success = float(item.get("success_rate", 0.75) or 0.75)
        cost_penalty = float(item.get("context_cost", 4) or 4) / 20
    else:
        base = 0.45
        success = 0.7
        cost_penalty = 0.05
    priority = SECTION_RULES.get(section_name, {}).get("priority", 1.0)
    return round(base * 0.65 + success * 0.15 + priority * 0.2 - cost_penalty, 4)


def item_cost(item: Any) -> int:
    if isinstance(item, dict) and item.get("context_cost") is not None:
        return max(1, int(item.get("context_cost", 1)))
    return estimate_tokens_from_text(packet_item_text(item), structural_overhead=2)


def compress_item(item: Any, max_words: int) -> Any:
    if isinstance(item, str):
        return truncate_words(item, max_words)
    if not isinstance(item, dict):
        return item
    compressed = dict(item)
    if compressed.get("summary"):
        compressed["summary"] = truncate_words(str(compressed["summary"]), max_words)
    if compressed.get("title"):
        compressed["title"] = truncate_words(str(compressed["title"]), min(max_words, 8))
    original_cost = item_cost(item)
    compressed["context_cost"] = max(1, min(original_cost, estimate_tokens_from_text(packet_item_text(compressed), structural_overhead=1)))
    compressed["compression"] = "summary_truncated"
    return compressed


def dedupe_items(items: list[Any]) -> tuple[list[Any], list[dict[str, Any]]]:
    seen: dict[str, Any] = {}
    dropped: list[dict[str, Any]] = []
    for item in items:
        identity = item_identity(item)
        if identity in seen:
            dropped.append({"identity": identity, "reason": "duplicate"})
            continue
        seen[identity] = item
    ordered = sorted(seen.values(), key=lambda item: (item_cost(item), item_identity(item)))
    return ordered, dropped


def optimize_list_section(section_name: str, items: list[Any], config: dict[str, Any], available_tokens: int) -> tuple[list[Any], list[dict[str, Any]], int]:
    if not items:
        return [], [], available_tokens
    rules = SECTION_RULES.get(section_name, {"mandatory": False, "priority": 1.0})
    mandatory = bool(rules.get("mandatory"))
    max_items = int(config.get("max_items_per_section", {}).get(section_name, len(items)) or len(items))
    deduped, dedupe_events = dedupe_items(items)
    events: list[dict[str, Any]] = [
        {"section": section_name, "action": "omitted", "entry": event["identity"], "reason": event["reason"]}
        for event in dedupe_events
    ]
    ranked = sorted(
        deduped,
        key=lambda item: (
            -((item_value(item, section_name) + (0.3 if mandatory else 0.0)) / max(item_cost(item), 1)),
            -item_value(item, section_name),
            item_cost(item),
            item_identity(item),
        ),
    )
    selected: list[Any] = []
    used = 0
    limit_words = int(config.get("mandatory_summary_max_words" if mandatory else "summary_max_words", 20))
    for index, item in enumerate(ranked):
        if len(selected) >= max_items:
            events.append({"section": section_name, "action": "omitted", "entry": item_identity(item), "reason": "section_item_cap"})
            continue
        current_item = item
        current_cost = item_cost(current_item)
        needs_fit = used + current_cost > available_tokens
        if needs_fit:
            compressed = compress_item(item, limit_words)
            compressed_cost = item_cost(compressed)
            if compressed_cost < current_cost and used + compressed_cost <= available_tokens:
                current_item = compressed
                current_cost = compressed_cost
                events.append({"section": section_name, "action": "compressed", "entry": item_identity(item), "reason": "fit_budget"})
            elif not mandatory and index > 0:
                events.append({"section": section_name, "action": "omitted", "entry": item_identity(item), "reason": "low_value_for_budget"})
                continue
            elif mandatory and compressed_cost < current_cost:
                current_item = compressed
                current_cost = compressed_cost
                events.append({"section": section_name, "action": "compressed", "entry": item_identity(item), "reason": "mandatory_section_trim"})
        selected.append(current_item)
        used += current_cost
        if not any(event.get("entry") == item_identity(item) and event.get("action") in {"compressed", "omitted"} for event in events):
            events.append({"section": section_name, "action": "preserved", "entry": item_identity(current_item), "reason": "selected"})
    return selected, events, max(0, available_tokens - used)


def sync_packet_mirrors(packet: dict[str, Any]) -> None:
    packet["architecture_decisions"] = list(packet.get("architecture_rules", []))
    packet["relevant_paths"] = list(packet.get("repo_scope", []))


def update_cost_status(report: dict[str, Any], packet_path: Path) -> None:
    status = read_json(COST_STATUS_PATH, {})
    events = int(status.get("optimization_events", 0))
    new_events = events + 1
    reduction = int(report.get("estimated_tokens_before", 0)) - int(report.get("estimated_tokens_after", 0))
    kept = int(report.get("kept_entries", 0))
    total = max(int(report.get("candidate_entries", 0)), 1)
    previous_avg_reduction = float(status.get("average_estimated_reduction_tokens", 0) or 0)
    previous_avg_kept = float(status.get("average_kept_ratio", 1.0) or 1.0)
    updated = {
        "version": 1,
        "generated_at": date.today().isoformat(),
        "optimization_events": new_events,
        "over_budget_events": int(status.get("over_budget_events", 0)) + (1 if report.get("status") != "within_budget" else 0),
        "average_estimated_reduction_tokens": round(((previous_avg_reduction * events) + reduction) / new_events, 2),
        "average_kept_ratio": round(((previous_avg_kept * events) + (kept / total)) / new_events, 4),
        "last_status": report.get("status"),
        "last_task": report.get("task"),
        "last_packet_path": packet_path.as_posix(),
        "last_budget": report.get("budget"),
        "last_estimated_tokens_before": report.get("estimated_tokens_before"),
        "last_estimated_tokens_after": report.get("estimated_tokens_after"),
    }
    write_json(COST_STATUS_PATH, updated)
    history_row = {
        "generated_at": date.today().isoformat(),
        "task": report.get("task"),
        "status": report.get("status"),
        "estimated_tokens_before": report.get("estimated_tokens_before"),
        "estimated_tokens_after": report.get("estimated_tokens_after"),
        "kept_entries": kept,
        "candidate_entries": total,
    }
    history = read_jsonl(COST_HISTORY_PATH)
    history.append(history_row)
    write_jsonl(COST_HISTORY_PATH, history[-50:])


def render_optimization_report(report: dict[str, Any]) -> str:
    lines = [
        "# latest optimization report",
        "",
        f"- Task: {report.get('task', '')}",
        f"- Status: {report.get('status', 'unknown')}",
        f"- Budget: target {report['budget']['budget_target_tokens']} / soft {report['budget']['soft_limit_tokens']} / hard {report['budget']['hard_limit_tokens']}",
        f"- Estimated tokens: {report.get('estimated_tokens_before', 0)} -> {report.get('estimated_tokens_after', 0)}",
        f"- Candidate entries: {report.get('candidate_entries', 0)}",
        f"- Kept entries: {report.get('kept_entries', 0)}",
        "",
        "## Actions",
        "",
    ]
    actions = report.get("actions", [])
    if not actions:
        lines.append("- No optimization actions were required.")
    else:
        for action in actions:
            lines.append(f"- `{action['section']}` | {action['action']} | `{action['entry']}` | {action['reason']}")
    lines.extend(
        [
            "",
            "## Rationale",
            "",
            f"- {report.get('rationale', 'No rationale captured.')}",
        ]
    )
    return "\n".join(lines) + "\n"


def optimize_packet(packet: dict[str, Any]) -> dict[str, Any]:
    ensure_cost_artifacts()
    config = cost_config()
    before = estimate_packet_tokens(packet)
    optimized = dict(packet)
    actions: list[dict[str, Any]] = []
    candidate_entries = 0
    kept_entries = 0
    available_tokens = int(config.get("budget_target_tokens", 3000))
    for fixed_key in ["task", "task_id", "task_summary", "task_type", "project", "model_suggestion", "fallback_mode", "knowledge_retrieval", "telemetry_granularity"]:
        available_tokens = max(0, available_tokens - before["sections"].get(fixed_key, 0))
    for section_name in [
        "user_preferences",
        "constraints",
        "architecture_rules",
        "relevant_memory",
        "relevant_patterns",
        "validation_recipes",
        "relevant_failures",
        "relevant_graph_context",
        "knowledge_artifacts",
        "repo_scope",
        "known_patterns",
    ]:
        items = list(optimized.get(section_name, []))
        candidate_entries += len(items)
        selected, section_actions, available_tokens = optimize_list_section(section_name, items, config, available_tokens)
        optimized[section_name] = selected
        actions.extend(section_actions)
        kept_entries += len(selected)
    sync_packet_mirrors(optimized)
    if before["estimated_total_tokens"] <= int(config.get("soft_limit_tokens", 2600)):
        status = "within_budget"
        rationale = "Estimated packet cost stayed below the soft limit, so only deterministic deduplication and per-section caps were applied."
    else:
        after_estimate = estimate_packet_tokens(optimized)
        status = "optimized" if after_estimate["estimated_total_tokens"] <= int(config.get("hard_limit_tokens", 3200)) else "over_budget_after_optimization"
        rationale = (
            "The optimizer preserved mandatory sections first, then ranked optional entries by value-per-cost, compressing verbose summaries before omitting low-value items."
        )
    after = estimate_packet_tokens(optimized)
    budget = {
        "budget_target_tokens": int(config.get("budget_target_tokens", 3000)),
        "soft_limit_tokens": int(config.get("soft_limit_tokens", 2600)),
        "hard_limit_tokens": int(config.get("hard_limit_tokens", 3200)),
        "estimated_tokens_before": before["estimated_total_tokens"],
        "estimated_tokens_after": after["estimated_total_tokens"],
        "status": status,
    }
    report = {
        "task": packet.get("task", ""),
        "status": status,
        "budget": budget,
        "estimated_tokens_before": before["estimated_total_tokens"],
        "estimated_tokens_after": after["estimated_total_tokens"],
        "candidate_entries": candidate_entries,
        "kept_entries": kept_entries,
        "actions": actions,
        "rationale": rationale,
    }
    optimized["context_budget"] = budget
    optimized["optimization_report"] = {
        "status": status,
        "actions_count": len(actions),
        "kept_entries": kept_entries,
        "candidate_entries": candidate_entries,
        "report_path": COST_LATEST_REPORT_PATH.as_posix(),
    }
    return {"packet": optimized, "report": report}


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


