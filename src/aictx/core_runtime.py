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
COST_DIR = BASE / ".ai_context_cost"
TASK_MEMORY_DIR = BASE / ".ai_context_task_memory"
FAILURE_MEMORY_DIR = BASE / ".ai_context_failure_memory"
MEMORY_GRAPH_DIR = BASE / ".ai_context_memory_graph"
CONTEXT_METRICS_DIR = BASE / ".context_metrics"
ENGINE_STATE_DIR = BASE / ".ai_context_engine"
LIBRARY_DIR = BASE / ".ai_context_library"

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
REPO_COMPAT_DIRNAME = ".ai_context_memory"
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


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text(text + ("\n" if text else ""))


def repo_root_for_project(project: str) -> Path | None:
    if not project:
        return None
    candidate = BASE.parent / project
    return candidate if candidate.exists() else None


def ensure_repo_compat_readme(compat_dir: Path) -> None:
    readme = compat_dir / "README.md"
    readme.write_text(
        "# .ai_context_memory\n\n"
        "Compatibility bootstrap layer for AI agent sessions in this repository.\n\n"
        "- Canonical source: `ai_context_engine` (current repo path: `/Users/santisantamaria/Documents/projects/ai_context_engine`)\n"
        "- Purpose: fast local bootstrap and predictable artifact paths (`derived_boot_summary.json`, `user_preferences.json`, `project_bootstrap.json`).\n"
        "- Do not hand-edit generated JSON/JSONL here; rebuild from the canonical engine instead.\n"
    )


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "record"


def current_engine_iteration() -> int:
    return CURRENT_ENGINE_ITERATION


def default_adapter_contract() -> dict[str, Any]:
    return {
        "agent_adapter": DEFAULT_AGENT_ADAPTER,
        "adapter_id": DEFAULT_ADAPTER_ID,
        "adapter_family": DEFAULT_ADAPTER_FAMILY,
        "provider_capabilities": list(DEFAULT_PROVIDER_CAPABILITIES),
    }


VALID_COMMUNICATION_MODES = {"caveman_lite", "caveman_full", "caveman_ultra"}
VALID_COMMUNICATION_LAYERS = {"enabled", "disabled"}


def normalize_communication_mode(value: Any, default: str = "caveman_full") -> str:
    normalized = str(value or "").strip().lower()
    if normalized in VALID_COMMUNICATION_MODES:
        return normalized
    return default


def normalize_communication_layer(value: Any, default: str = "enabled") -> str:
    normalized = str(value or "").strip().lower()
    if normalized in VALID_COMMUNICATION_LAYERS:
        return normalized
    return default


def communication_policy_from_defaults(defaults_payload: dict[str, Any]) -> dict[str, Any]:
    communication = defaults_payload.get("communication", {}) if isinstance(defaults_payload.get("communication"), dict) else {}
    layer = normalize_communication_layer(communication.get("layer"), "enabled")
    mode = normalize_communication_mode(communication.get("mode"), "caveman_full")
    intermediate_updates = str(communication.get("intermediate_updates", "suppressed")).strip().lower() or "suppressed"
    final_style = str(communication.get("final_style", "plain_direct_final_only")).strip() or "plain_direct_final_only"
    return {
        "layer": layer,
        "mode": mode,
        "intermediate_updates": intermediate_updates,
        "final_style": final_style,
        "user_override_wins": True,
        "long_form_on_request": True,
        "step_by_step_on_request": True,
        "applies_to": [
            "implementation_summaries",
            "debugging_reports",
            "patch_explanations",
            "execution_loop_diagnostics",
            "final_execution_results",
        ],
        "does_not_apply_to": [
            "source_code_comments",
            "repository_documentation",
            "marketing_copy",
            "narrative_content",
            "normal_style_user_requested_prose",
        ],
        "preferred_patterns": [
            "found -> cause -> fix",
            "done -> files -> tests",
            "blocked -> reason -> need",
            "next -> verify -> continue",
            "changed A, updated B, left C",
        ],
    }


def relative_posix(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def file_mtime(path: Path) -> float:
    return round(path.stat().st_mtime, 6)


def mtime_changed(previous: Any, current: float) -> bool:
    if previous is None:
        return True
    return abs(float(previous) - current) > MTIME_TOLERANCE_SECONDS


def file_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_mod_manifest(root: Path) -> dict[str, Any]:
    return read_json(root / "mod.json", {})


def save_mod_manifest(root: Path, manifest: dict[str, Any]) -> None:
    manifest["manifest_path"] = (root / "mod.json").as_posix()
    manifest["library_root"] = root.as_posix()
    manifest["updated_at"] = now_iso()
    write_json(root / "mod.json", manifest)


def default_mod_state() -> dict[str, Any]:
    return {"version": 2, "last_processed": None, "processed_docs": {}, "referenced_files": {}}


def load_mod_state(root: Path) -> dict[str, Any]:
    state = read_json(root / "manifests" / "state.json", default_mod_state())
    state.setdefault("version", 2)
    state.setdefault("last_processed", None)
    state.setdefault("processed_docs", {})
    state.setdefault("referenced_files", {})
    return state


def save_mod_state(root: Path, state: dict[str, Any]) -> None:
    state["version"] = 2
    write_json(root / "manifests" / "state.json", state)


def references_template_text() -> str:
    return (
        "# References Template\n\n"
        "List one file path per line to ingest knowledge from files that live outside the mod inbox.\n\n"
        "- Lines starting with `#` are comments.\n"
        "- A comment immediately before a path is stored as the label for that file.\n"
        "- Relative paths are resolved from the engine root.\n"
        "- Supported referenced formats: `.md`, `.txt`, `.html`, `.htm`, `.pdf`, `.sql`, `.xml`, `.json`, `.yaml`, `.yml`, `.py`, `.csv`.\n\n"
        "Example:\n\n"
        "```md\n"
        "# API schema\n"
        "docs/api/openapi.yaml\n\n"
        "# SQL views\n"
        "/absolute/path/to/reporting_view.sql\n"
        "```\n"
    )


def references_stub_text(mod_id: str) -> str:
    return (
        f"# Knowledge References — {slugify(mod_id)}\n\n"
        "# Add one absolute or repo-relative path per line.\n"
        "# See ../../REFERENCES_TEMPLATE.md for the full format.\n"
        "# Example:\n"
        "# /absolute/path/to/file.sql\n"
        "# docs/architecture/api.yaml\n"
    )


def ensure_references_template() -> None:
    template_path = LIBRARY_DIR / "REFERENCES_TEMPLATE.md"
    if not template_path.exists():
        write_text(template_path, references_template_text())


def ensure_remote_manifest(root: Path) -> None:
    manifest_path = root / "remote_sources" / "manifest.json"
    if not manifest_path.exists():
        write_json(manifest_path, {"version": 1, "sources": []})


def should_process_inbox_file(path: Path) -> bool:
    return path.is_file() and path.name != "references.md" and path.suffix.lower() in SUPPORTED_INBOX_EXTENSIONS


def resolve_reference_path(raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (BASE / raw_path).resolve()


def parse_references_file(path: Path) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    if not path.exists():
        return references
    current_label: str | None = None
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line:
            current_label = None
            continue
        if line.startswith("#"):
            current_label = line.lstrip("#").strip() or None
            continue
        resolved = resolve_reference_path(line)
        references.append({"path": resolved, "raw_path": line, "label": current_label})
    return references


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
    topic_index: dict[str, list[str]] = defaultdict(list)
    keyword_index: dict[str, list[str]] = defaultdict(list)
    notes: list[str] = []
    summaries: list[str] = []
    for bucket_name in ["processed_docs", "referenced_files"]:
        for entry in state.get(bucket_name, {}).values():
            if entry.get("status") != "processed":
                continue
            for path in entry.get("note_files", []):
                notes.append(path)
            for path in entry.get("summary_files", []):
                summaries.append(path)
            for keyword in entry.get("keywords", [])[:8]:
                for path in entry.get("note_files", [])[:1]:
                    if path not in topic_index[keyword]:
                        topic_index[keyword].append(path)
                for path in entry.get("summary_files", [])[:1]:
                    if path not in keyword_index[keyword]:
                        keyword_index[keyword].append(path)
            for section in entry.get("sections", []):
                for keyword in section.get("keywords", [])[:10]:
                    note_path = section.get("note_path")
                    summary_path = section.get("summary_path")
                    if note_path and note_path not in topic_index[keyword]:
                        topic_index[keyword].append(note_path)
                    if summary_path and summary_path not in keyword_index[keyword]:
                        keyword_index[keyword].append(summary_path)
    topic_path = root / "indices" / "topic_index.json"
    keyword_path = root / "indices" / "keyword_index.json"
    retrieval_path = root / "indices" / "retrieval_map.json"
    write_json(topic_path, dict(sorted(topic_index.items())))
    write_json(keyword_path, dict(sorted(keyword_index.items())))
    write_json(
        retrieval_path,
        {
            "version": 1,
            "mod_id": root.name,
            "notes": notes,
            "summaries": summaries,
            "generated_at": now_iso(),
        },
    )
    return {
        "topic_index": [relative_posix(topic_path, root)],
        "keyword_index": [relative_posix(keyword_path, root)],
        "retrieval_map": [relative_posix(retrieval_path, root)],
    }


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
    prefs = read_json(ROOT_PREFS_PATH, {})
    updated_at = prefs.get("updated_at", date.today().isoformat())
    rows = []

    def walk(node: Any, prefix: str = "") -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "history":
                    continue
                next_prefix = f"{prefix}.{key}" if prefix else key
                walk(value, next_prefix)
            return
        rows.append(
            {
                "id": f"pref.{slugify(prefix)}",
                "type": "user_preference",
                "scope": "global",
                "project": None,
                "tags": [part for part in prefix.split(".") if part],
                "key": prefix,
                "value": node,
                "priority": "high",
                "confidence": "high",
                "last_verified": updated_at,
                "source": "user_preferences.json",
                "override_rule": "explicit_user_instruction_wins",
                "relevance_score": 0.95,
                "last_used_at": updated_at,
                "times_used": 0,
                "success_rate": 1.0,
                "context_cost": 1,
                "source_type": "preference",
                "staleness_score": 0.05,
            }
        )

    walk(prefs)
    return rows


def load_records() -> list[dict[str, Any]]:
    rows = read_jsonl(STORE_GLOBAL_RECORDS_PATH)
    rows.extend(read_jsonl(STORE_USER_PREFERENCES_PATH))
    if PROJECT_RECORDS_DIR.exists():
        for path in sorted(PROJECT_RECORDS_DIR.glob("*.jsonl")):
            rows.extend(read_jsonl(path))
    return rows


def iso_date_or_today(value: Any) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    return date.today().isoformat()


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(record)
    normalized["relevance_score"] = float(record.get("relevance_score", 0.6))
    normalized["last_used_at"] = iso_date_or_today(record.get("last_used_at") or record.get("last_verified"))
    normalized["times_used"] = int(record.get("times_used", 0))
    normalized["success_rate"] = float(record.get("success_rate", 0.75))
    normalized["context_cost"] = int(record.get("context_cost", max(1, min(12, len(str(record.get("summary", "")).split()) // 8 or 1))))
    normalized["source_type"] = str(record.get("source_type", "legacy"))
    normalized["staleness_score"] = float(record.get("staleness_score", 0.2))
    normalized["task_type"] = normalize_task_type(record.get("task_type"))
    normalized["files_involved"] = list(record.get("files_involved", [record.get("path")] if record.get("path") else []))
    return normalized


def days_since(value: Any) -> int:
    text = iso_date_or_today(value)
    year, month, day = (int(part) for part in text.split("-"))
    current = date.today()
    return max(0, (current - date(year, month, day)).days)


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
    ensure_dirs()
    ensure_cost_artifacts()
    ensure_task_memory_artifacts()
    ensure_failure_memory_artifacts()
    ensure_memory_graph_artifacts()
    note_infos = [classify_note(path) for path in note_paths()]
    project_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    global_rows: list[dict[str, Any]] = []
    import_map: list[dict[str, str]] = []

    for note in note_infos:
        record = note_to_record(note)
        import_map.append({"source": note.rel_path, "target_record_id": record["id"]})
        if note.project:
            project_rows[note.project].append(record)
        else:
            global_rows.append(record)

    write_jsonl(STORE_GLOBAL_RECORDS_PATH, global_rows)
    for project, rows in project_rows.items():
        write_jsonl(PROJECT_RECORDS_DIR / f"{project}.jsonl", rows)

    user_rows = preference_records()
    write_jsonl(STORE_USER_PREFERENCES_PATH, user_rows)

    index = read_json(ROOT_INDEX_PATH, {})
    project_registry = {
        "version": 1,
        "lookup_order": index.get("lookup_order", []),
        "projects": index.get("projects", {}),
        "generated_at": date.today().isoformat(),
    }
    write_json(BOOT_PROJECTS_PATH, project_registry)

    defaults_payload = read_json(ROOT_PREFS_PATH, {})
    normalized_defaults = {
        "version": 1,
        "updated_at": defaults_payload.get("updated_at", date.today().isoformat()),
        "preferred_language": defaults_payload.get("profile", {}).get("preferred_language", "es"),
        "response": defaults_payload.get("response", {}),
        "interaction": defaults_payload.get("interaction", {}),
        "communication": communication_policy_from_defaults(defaults_payload),
        "coding": defaults_payload.get("coding", {}),
        "workflow": defaults_payload.get("workflow", {}),
        "quality_gates": defaults_payload.get("quality_gates", {}),
    }
    write_json(BOOT_DEFAULTS_PATH, normalized_defaults)

    model_routing = default_model_routing()
    write_json(BOOT_MODEL_ROUTING_PATH, model_routing)
    communication_policy = communication_policy_from_defaults(defaults_payload)
    adapter_contract = default_adapter_contract()
    boot_summary_payload = {
        "version": 1,
        "engine_name": "ai_context_engine",
        **adapter_contract,
        "default_behavior": {
            "memory_first": True,
            "fallback_to_standard_repo_analysis": True,
            "explicit_user_override_wins": True,
            "bootstrap_required_every_session": True,
        },
        "preferred_output_patterns": [
            communication_policy.get("mode", "caveman_full"),
            communication_policy.get("final_style", "plain_direct_final_only"),
            defaults_payload.get("response", {}).get("verbosity", defaults_payload.get("workflow", {}).get("default_response_style", "concise")),
            defaults_payload.get("profile", {}).get("preferred_language", "es"),
        ],
        "communication_policy": communication_policy,
        "communication_contract": {
            "default_mode": communication_policy.get("mode", "caveman_full"),
            "layer": communication_policy.get("layer", "enabled"),
            "intermediate_output": communication_policy.get("intermediate_updates", "suppressed"),
            "final_output": communication_policy.get("final_style", "plain_direct_final_only"),
            "plain_direct": True,
            "single_final_answer_default": True,
            "explicit_user_override_wins": True,
        },
        "preference_precedence": [
            "explicit_user_instruction",
            "persisted_user_preferences",
            "assistant_default",
        ],
        "active_projects": sorted(project_rows.keys()),
        "model_routing_profile": model_routing.get("profile", "default"),
        "provider_capabilities": list(adapter_contract["provider_capabilities"]),
        "last_maintenance": date.today().isoformat(),
    }
    write_json(BOOT_SUMMARY_PATH, boot_summary_payload)

    all_rows = [normalize_record(row) for row in (global_rows + user_rows + [row for rows in project_rows.values() for row in rows])]
    write_jsonl(STORE_GLOBAL_RECORDS_PATH, [normalize_record(row) for row in global_rows])
    for project, rows in project_rows.items():
        write_jsonl(PROJECT_RECORDS_DIR / f"{project}.jsonl", [normalize_record(row) for row in rows])
    write_jsonl(STORE_USER_PREFERENCES_PATH, [normalize_record(row) for row in user_rows])
    normalized_all_rows = [normalize_record(row) for row in all_rows]
    write_indexes(normalized_all_rows)
    task_memory_counts = build_task_memory_artifacts(normalized_all_rows)
    failure_memory_status = build_failure_memory_artifacts(normalized_all_rows)
    memory_graph_status = build_memory_graph_artifacts(normalized_all_rows)
    ensure_context_metrics_artifacts()
    ensure_library_artifacts()
    write_json(
        DELTA_SCHEMA_PATH,
        {
            "version": 7,
            "required": [
                "task_summary",
                "task_id",
                "task_type",
                "task_type_resolution",
                "repo_scope",
                "user_preferences",
                "constraints",
                "architecture_rules",
                "relevant_memory",
                "known_patterns",
                "fallback_mode",
                "task_memory",
                "failure_memory",
                "memory_graph",
                "telemetry_granularity",
                "knowledge_retrieval",
                "context_budget",
                "optimization_report",
            ],
            "compatibility_fields": [
                "project",
                "architecture_decisions",
                "relevant_paths",
                "relevant_patterns",
                "validation_recipes",
                "model_suggestion",
                "packet_budget_status",
                "task_memory_summary",
                "failure_memory_summary",
                "relevant_failures",
                "memory_graph_summary",
                "relevant_graph_context",
                "knowledge_artifacts",
            ],
        },
    )
    write_json(MIGRATION_IMPORT_MAP_PATH, {"version": 1, "imports": import_map})
    write_migration_report(import_map)
    append_if_missing(
        LOGS_MAINTENANCE_PATH,
        f"- {date.today().isoformat()} | rebuilt store/indexes/boot artifacts from current ai_context_engine notes and preferences.\n",
    )
    write_json(
        ROOT_COMPACTION_REPORT_PATH,
        {
            "generated_at": date.today().isoformat(),
            "dry_run": True,
            "stores_scanned": 2 + len(project_rows),
            "duplicates_detected": 0,
            "near_duplicates_detected": 0,
            "stale_records_detected": 0,
            "verbose_records_detected": 0,
            "fragmented_groups_detected": 0,
            "actions": [],
        },
    )
    write_json(
        COST_STATUS_PATH,
        {
            **read_json(COST_STATUS_PATH, {}),
            "version": 1,
            "generated_at": date.today().isoformat(),
        },
    )
    write_json(
        TASK_MEMORY_STATUS_PATH,
        {
            **read_json(TASK_MEMORY_STATUS_PATH, {}),
            "version": 2,
            "installed_iteration": 8,
            "task_taxonomy_version": 2,
            "generated_at": date.today().isoformat(),
            "records_by_task_type": task_memory_counts,
        },
    )
    write_json(
        FAILURE_MEMORY_STATUS_PATH,
        {
            **read_json(FAILURE_MEMORY_STATUS_PATH, {}),
            **failure_memory_status,
            "version": 1,
            "generated_at": date.today().isoformat(),
        },
    )
    write_json(
        MEMORY_GRAPH_STATUS_PATH,
        {
            **read_json(MEMORY_GRAPH_STATUS_PATH, {}),
            **memory_graph_status,
            "version": 1,
            "installed_iteration": 9,
            "generated_at": date.today().isoformat(),
        },
    )
    refresh_engine_state()
    sync_repo_compat_layers(
        project_rows=project_rows,
        global_rows=global_rows,
        defaults_payload=defaults_payload,
        project_registry=project_registry,
        boot_summary_payload=boot_summary_payload,
        model_routing=model_routing,
    )
    return {
        "notes": len(note_infos),
        "records": len(normalized_all_rows),
        "projects": sorted(project_rows.keys()),
        "task_memory_records": task_memory_counts,
        "failure_memory_records": int(failure_memory_status.get("records_total", 0) or 0),
        "memory_graph_nodes": int(memory_graph_status.get("nodes_total", 0) or 0),
        "memory_graph_edges": int(memory_graph_status.get("edges_total", 0) or 0),
    }


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
    rows = [normalize_record(row) for row in load_records()] + manual_task_memory_records()
    ranked = []
    for row in rows:
        if record_type and row.get("type") != record_type:
            continue
        if task_type and normalize_task_type(row.get("task_type")) != normalize_task_type(task_type):
            continue
        if project and row.get("project") not in {None, project}:
            continue
        score = deterministic_score(query, row)
        if score > 0:
            ranked.append((score, row))
    ranked.sort(key=lambda item: (-item[0], item[1].get("context_cost", 99), item[1].get("id", "")))
    return [{"score": score, **row} for score, row in ranked[:12]]


def summarize_query(query: str, mode: str = "all") -> dict[str, Any]:
    if mode == "prefs":
        return {"query": query, "preferences": rank_records(query or "workflow", "user_preference")}
    if mode == "architecture":
        return {"query": query, "matches": rank_records(query, "architecture_decision")}
    if mode == "symptom":
        symptom_map = read_json(INDEX_BY_SYMPTOM_PATH, {})
        ranked = []
        for symptom, paths in symptom_map.items():
            score = score_match(query, symptom)
            if score > 0:
                ranked.append({"symptom": symptom, "score": score, "paths": paths})
        ranked.sort(key=lambda item: (-item["score"], item["symptom"]))
        return {"query": query, "symptoms": ranked[:12]}
    return {"query": query, "matches": rank_records(query)}


def route_task(task: str) -> dict[str, Any]:
    task_l = task.lower()
    files_hint = 1
    if any(word in task_l for word in ["cross-system", "migration", "architecture", "redesign", "protocol"]):
        level = "heavy"
        files_hint = 10
    elif any(word in task_l for word in ["add", "implement", "fix", "debug", "test", "refactor"]):
        level = "medium"
        files_hint = 4
    else:
        level = "light"
        files_hint = 1
    return {
        "task": task,
        "model_suggestion": level,
        "signals": {
            "estimated_files": files_hint,
            "ambiguity": "medium" if level != "light" else "low",
            "cross_system": level == "heavy",
        },
    }


def resolve_task_type(
    task: str,
    *,
    explicit_task_type: str | None = None,
    packet_metadata: dict[str, Any] | None = None,
    touched_files: list[str] | None = None,
) -> dict[str, Any]:
    task_signals = infer_task_signals(task, touched_files=touched_files)
    normalized_explicit = normalize_task_type(explicit_task_type)
    if explicit_task_type and normalized_explicit in TASK_TYPES:
        return {
            "task_type": normalized_explicit,
            "source": "explicit_task_type",
            "fallback": normalized_explicit == "unknown",
            "confidence": 0.95,
            "signals": [f"explicit:{normalized_explicit}"],
        }
    metadata_task_type = normalize_task_type((packet_metadata or {}).get("task_type"))
    if packet_metadata and packet_metadata.get("task_type") and metadata_task_type in TASK_TYPES:
        return {
            "task_type": metadata_task_type,
            "source": "packet_metadata",
            "fallback": metadata_task_type == "unknown",
            "confidence": 0.9,
            "signals": [f"metadata:{metadata_task_type}"],
        }
    inferred = classify_task_type_from_text(
        "\n".join([task, " ".join(touched_files or [])]),
        tags=[],
        record_type=None,
    )
    if inferred != "unknown":
        return {
            "task_type": inferred,
            "source": "heuristic_inference",
            "fallback": False,
            "confidence": task_type_confidence(task, inferred, touched_files=touched_files),
            "signals": task_signals,
        }
    return {
        "task_type": "unknown",
        "source": "unknown_fallback",
        "fallback": True,
        "confidence": 0.35,
        "signals": task_signals,
    }


def packet_for_task(task: str, project: str | None = None, task_type: str | None = None) -> dict[str, Any]:
    ensure_cost_artifacts()
    ensure_task_memory_artifacts()
    ensure_failure_memory_artifacts()
    ensure_memory_graph_artifacts()
    ensure_context_metrics_artifacts()
    ensure_library_artifacts()
    refresh_engine_state()
    initial_matches = rank_records(task)
    project_name = infer_project_name(task, initial_matches, explicit_project=project)
    touched_files = [str(row.get("path")) for row in initial_matches[:6] if row.get("path")]
    resolved_task = resolve_task_type(task, explicit_task_type=task_type, touched_files=touched_files)
    task_specific_matches = []
    queried_task_categories = [resolved_task["task_type"]]
    if resolved_task["task_type"] != "unknown":
        task_specific_matches = [
            row
            for row in rank_records(task, task_type=resolved_task["task_type"], project=project_name)
            if row.get("type") != "user_preference"
        ]
    fallback_task_matches = [
        row
        for row in rank_records(task, task_type="unknown", project=project_name)
        if row.get("type") != "user_preference"
    ]
    if "unknown" not in queried_task_categories:
        queried_task_categories.append("unknown")
    general_matches = [
        row
        for row in rank_records(task, project=project_name)
        if row.get("type") != "user_preference"
    ]
    merged_memory: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in task_specific_matches + fallback_task_matches + general_matches:
        row_id = str(row.get("id", ""))
        if row_id in seen_ids:
            continue
        seen_ids.add(row_id)
        merged_memory.append(row)
    memory_matches = merged_memory
    if not memory_matches and project_name:
        memory_matches = [
            row
            for row in rank_records(project_name, task_type=resolved_task["task_type"], project=project_name)
            if row.get("type") != "user_preference" and row.get("project") == project_name
        ]
    if not memory_matches:
        memory_matches = [row for row in initial_matches if row.get("type") != "user_preference"]
    prefs = summarize_query(task, mode="prefs").get("preferences", [])[:5]
    architecture = [row for row in memory_matches if row.get("type") == "architecture_decision"][:5]
    constraints = [row for row in memory_matches if row.get("type") == "constraint"][:5]
    patterns = [row for row in memory_matches if row.get("type") in {"debugging_pattern", "failure_mode", "task_pattern"}][:5]
    validation = [row for row in memory_matches if row.get("type") == "validation_recipe"][:5]
    relevant_paths = []
    for row in memory_matches[:8]:
        path = row.get("path")
        if path and path not in relevant_paths:
            relevant_paths.append(path)
    route = route_task(task)
    relevant_failures = rank_failure_records(task) if should_consult_failure_memory(task, resolved_task["task_type"]) else []
    knowledge_pack = retrieve_knowledge(task)
    graph_seed_ids = [graph_node_id("task_type", resolved_task["task_type"])]
    graph_seed_ids.extend(graph_node_id(graph_node_type_for_record(row), str(row.get("id", ""))) for row in memory_matches[:4] if row.get("id"))
    graph_seed_ids.extend(graph_node_id("failure_pattern", str(row.get("id", ""))) for row in relevant_failures[:2] if row.get("id"))
    if project_name:
        graph_seed_ids.append(graph_node_id("repository_area", project_name))
    expansion_depth = 2 if resolved_task["task_type"] in {"architecture", "bug_fixing"} and (memory_matches or relevant_failures) else 1
    graph_expansion = graph_expand(
        sorted(set(graph_seed_ids)),
        depth=expansion_depth,
        node_budget=10,
        edge_budget=14,
        task_type=resolved_task["task_type"],
        repository_area=project_name,
    )
    graph_connected_ids = set(graph_expansion.get("connected_record_ids", []))
    graph_context = []
    for node in graph_expansion.get("nodes", []):
        if node.get("type") == "task_type":
            continue
        graph_context.append(
            {
                "id": node.get("id"),
                "title": node.get("label"),
                "summary": f"{node.get('type')} from {node.get('source')}",
                "score": round(float(node.get("confidence", 0.5)), 2),
                "context_cost": 2,
                "source_type": "memory_graph",
            }
        )
    if graph_connected_ids:
        connected_rows = {
            row.get("id"): row
            for row in ([normalize_record(row) for row in load_records()] + manual_task_memory_records())
            if row.get("id") in graph_connected_ids
        }
        for record_id in sorted(graph_connected_ids):
            row = connected_rows.get(record_id)
            if not row or any(existing.get("id") == record_id for existing in memory_matches):
                continue
            memory_matches.append({**row, "score": round(float(row.get("relevance_score", 0.65)) * 0.9, 4)})
    relevant_memory = []
    known_patterns = []
    for row in memory_matches[:5]:
        relevant_memory.append(
            {
                "id": row.get("id"),
                "title": row.get("title"),
                "summary": row.get("summary"),
                "score": row.get("score"),
                "source_type": row.get("source_type", "legacy"),
                "context_cost": row.get("context_cost", 5),
            }
        )
        for tag in row.get("tags", []):
            if tag not in known_patterns:
                known_patterns.append(tag)
    task_id = f"{date.today().isoformat()}_{slugify(task)[:40]}"
    packet = {
        "task_id": task_id,
        "task": task,
        "task_summary": task,
        "task_type": resolved_task["task_type"],
        "task_type_resolution": resolved_task,
        "project": project_name,
        "repo_scope": relevant_paths,
        "user_preferences": prefs,
        "constraints": constraints,
        "architecture_rules": architecture,
        "architecture_decisions": architecture,
        "relevant_memory": relevant_memory,
        "relevant_paths": relevant_paths,
        "known_patterns": known_patterns,
        "relevant_patterns": patterns,
        "validation_recipes": validation,
        "relevant_failures": relevant_failures,
        "relevant_graph_context": graph_context[:5],
        "knowledge_artifacts": knowledge_pack.get("artifacts", []),
        "knowledge_retrieval": knowledge_pack,
        "model_suggestion": route["model_suggestion"],
        "fallback_mode": "normal_repo_analysis",
        "task_memory": {
            "resolved_task_type": resolved_task["task_type"],
            "task_type_source": resolved_task["source"],
            "task_type_confidence": resolved_task.get("confidence", 0.35),
            "task_type_signals": resolved_task.get("signals", []),
            "task_specific_memory_used": bool(task_specific_matches),
            "task_specific_records_retrieved": len(task_specific_matches[:5]),
            "unknown_records_retrieved": len(fallback_task_matches[:5]),
            "general_records_retrieved": len(general_matches[:5]),
            "queried_categories": queried_task_categories,
            "category_summary_paths": [
                (TASK_MEMORY_DIR / category / "summary.json").as_posix()
                for category in queried_task_categories
                if (TASK_MEMORY_DIR / category / "summary.json").exists()
            ],
            "fallback_to_general": resolved_task["task_type"] == "unknown" or not task_specific_matches,
            "task_memory_written": False,
            "learning_channel": "scripts/task_memory.py",
        },
        "failure_memory": {
            "failure_memory_used": bool(relevant_failures),
            "records_retrieved": len(relevant_failures),
            "index_path": FAILURE_MEMORY_INDEX_PATH.as_posix(),
            "summary_path": FAILURE_MEMORY_SUMMARY_PATH.as_posix(),
        },
        "memory_graph": {
            "graph_used": bool(graph_context),
            "seed_count": len(sorted(set(graph_seed_ids))),
            "expansion_depth_used": graph_expansion.get("depth_used", 0),
            "graph_hits": len(graph_expansion.get("nodes", [])),
            "connected_record_hits": len(graph_connected_ids),
            "nodes_total": int(read_json(MEMORY_GRAPH_STATUS_PATH, {}).get("nodes_total", 0) or 0),
            "edges_total": int(read_json(MEMORY_GRAPH_STATUS_PATH, {}).get("edges_total", 0) or 0),
            "status_path": MEMORY_GRAPH_STATUS_PATH.as_posix(),
            "snapshot_path": MEMORY_GRAPH_SNAPSHOT_PATH.as_posix(),
        },
        "telemetry_granularity": {
            "supported": True,
            "task_id": task_id,
            "level": "task",
            "phase_count": 4,
            "phases": [
                {
                    "phase_name": "memory_retrieval",
                    "estimated_tokens": estimate_tokens(relevant_memory) + estimate_tokens(knowledge_pack.get("artifacts", [])),
                    "notes": "memory, failures, graph seeds, and knowledge artifacts",
                },
                {
                    "phase_name": "graph_expansion",
                    "estimated_tokens": estimate_tokens(graph_context),
                    "notes": "bounded memory-graph expansion",
                },
                {
                    "phase_name": "packet_optimization",
                    "estimated_tokens": estimate_tokens({"constraints": constraints, "architecture": architecture, "patterns": patterns}),
                    "notes": "budget-aware packet optimization",
                },
                {
                    "phase_name": "packet_persistence",
                    "estimated_tokens": estimate_tokens({"packet": task_id, "writes": 5}),
                    "notes": "packet and status persistence",
                },
            ],
        },
    }
    optimized = optimize_packet(packet)
    final_packet = optimized["packet"]
    packet_name = f"{date.today().isoformat()}_{slugify(task)[:60]}.json"
    packet_path = LAST_PACKETS_DIR / packet_name
    write_json(packet_path, final_packet)
    write_text(COST_LATEST_REPORT_PATH, render_optimization_report(optimized["report"]))
    update_cost_status(optimized["report"], packet_path)
    update_task_memory_status(final_packet, packet_path)
    update_failure_memory_status(final_packet, packet_path)
    update_memory_graph_status(final_packet, packet_path)
    weekly_summary = record_granular_telemetry(final_packet, packet_path, optimized["report"])
    sync_repo_cost_status(project_name)
    sync_repo_task_memory_status(project_name)
    sync_repo_failure_memory_status(project_name)
    sync_repo_memory_graph_status(project_name)
    final_packet.setdefault("telemetry_granularity", {})
    final_packet["telemetry_granularity"]["weekly_summary_path"] = CONTEXT_WEEKLY_SUMMARY_PATH.as_posix()
    final_packet["telemetry_granularity"]["phase_events_sampled"] = int(weekly_summary.get("phase_events_sampled", 0) or 0)
    return final_packet


def detect_stale_records() -> dict[str, Any]:
    rows = [normalize_record(row) for row in load_records()]
    stale = []
    duplicate_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    missing_paths = []
    today = date.today().isoformat()
    for row in rows:
        verified = str(row.get("last_verified", ""))
        if verified and verified < "2026-01-01":
            stale.append({"id": row["id"], "last_verified": verified})
        duplicate_groups[(str(row.get("type")), str(row.get("title", row.get("key", ""))))].append(row["id"])
        rel_path = row.get("path")
        if rel_path and not (BASE / rel_path).exists():
            missing_paths.append({"id": row["id"], "path": rel_path})
    duplicates = [
        {"type": group[0], "title": group[1], "record_ids": ids}
        for group, ids in duplicate_groups.items()
        if len(ids) > 1
    ]
    report = {
        "generated_at": today,
        "stale": stale,
        "duplicates": duplicates,
        "missing_paths": missing_paths,
    }
    write_json(BASE / "staleness_report.json", report)
    return report


def compact_records(apply: bool = False) -> dict[str, Any]:
    rows = [normalize_record(row) for row in load_records()]
    stale = []
    duplicates = []
    verbose = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("type") == "user_preference":
            signature = f"pref:{row.get('key', row.get('id', ''))}"
        elif row.get("path"):
            signature = f"path:{row.get('path')}"
        elif row.get("title") or row.get("summary"):
            signature_text = f"{row.get('title', '')} {row.get('summary', '')}"
            signature = f"text:{slugify(signature_text)}"
        else:
            signature = f"id:{row.get('id', '')}"
        key = (str(row.get("type", "")), signature)
        grouped[key].append(row)
        if len(str(row.get("summary", ""))) > 320:
            verbose.append(row["id"])
        if days_since(row.get("last_used_at")) > 180 and float(row.get("relevance_score", 0.6)) < 0.5:
            stale.append(row["id"])
    for key, group in grouped.items():
        if len(group) > 1:
            duplicates.append(
                {
                    "type": key[0],
                    "signature": key[1],
                    "record_ids": [row["id"] for row in group],
                    "kept_id": sorted(group, key=lambda row: (-float(row.get("success_rate", 0.75)), row["context_cost"], row["id"]))[0]["id"],
                }
            )
    report = {
        "generated_at": date.today().isoformat(),
        "dry_run": not apply,
        "stores_scanned": len(list(PROJECT_RECORDS_DIR.glob("*.jsonl"))) + 2,
        "duplicates_detected": len(duplicates),
        "near_duplicates_detected": 0,
        "stale_records_detected": len(stale),
        "verbose_records_detected": len(verbose),
        "fragmented_groups_detected": 0,
        "actions": [
            *[
                {"type": "duplicate", "record_ids": item["record_ids"], "kept_id": item["kept_id"], "recommendation": "merge_or_prune"}
                for item in duplicates
            ],
            *[
                {"type": "stale_low_value", "record_id": record_id, "recommendation": "review"}
                for record_id in stale
            ],
            *[
                {"type": "verbose", "record_id": record_id, "recommendation": "tighten_summary"}
                for record_id in verbose
            ],
        ],
    }
    write_json(ROOT_COMPACTION_REPORT_PATH, report)
    return report


def append_if_missing(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    current = path.read_text() if path.exists() else ""
    if line not in current:
        path.write_text(current + line)


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
        "- Existing markdown notes remain canonical; `.ai_context_task_memory/` is derived from them.\n"
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
    ensure_library_artifacts()
    return read_json(LIBRARY_REGISTRY_PATH, {"version": 1, "generated_at": date.today().isoformat(), "mods": {}})


def ensure_library_artifacts() -> None:
    ensure_dirs()
    readme = LIBRARY_DIR / "README.md"
    if not readme.exists():
        write_text(
            readme,
            "# .ai_context_library\n\n"
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
    ensure_library_artifacts()
    normalized = slugify(mod_id)
    root = mod_root(normalized)
    for name in [
        "inbox",
        "sources",
        "processed",
        "notes",
        "summaries",
        "indices",
        "manifests",
        "remote_sources",
        "remote_sources/raw",
        "remote_sources/snapshots",
        "remote_sources/extracted",
    ]:
        (root / name).mkdir(parents=True, exist_ok=True)
    ensure_remote_manifest(root)
    manifest = load_mod_manifest(root)
    created_at = manifest.get("created_at") or now_iso()
    existing_aliases = set(manifest.get("aliases", []))
    manifest.update(
        {
            "id": normalized,
            "title": title or manifest.get("title") or normalized.replace("_", " ").title(),
            "aliases": sorted({normalized, *(slugify(alias) for alias in (aliases or [])), *existing_aliases}),
            "created_at": created_at,
            "status": "ready",
            "last_processed": manifest.get("last_processed"),
            "inbox_count": int(manifest.get("inbox_count", 0) or 0),
            "referenced_count": int(manifest.get("referenced_count", 0) or 0),
            "remote_sources_count": int(manifest.get("remote_sources_count", 0) or 0),
        }
    )
    save_mod_manifest(root, manifest)
    if create_reference_stub:
        references_path = root / "inbox" / "references.md"
        if not references_path.exists():
            write_text(references_path, references_stub_text(normalized))
    registry = library_registry()
    registry.setdefault("mods", {})[normalized] = {
        "title": manifest["title"],
        "aliases": manifest["aliases"],
        "manifest_path": (root / "mod.json").as_posix(),
        "library_root": root.as_posix(),
        "updated_at": manifest["updated_at"],
    }
    registry["generated_at"] = date.today().isoformat()
    write_json(LIBRARY_REGISTRY_PATH, registry)
    status = read_json(LIBRARY_RETRIEVAL_STATUS_PATH, {})
    status.update(
        {
            "installed_iteration": current_engine_iteration(),
            "mods_total": len(registry.get("mods", {})),
            "supports_reference_ingestion": True,
            "supports_remote_ingestion": True,
        }
    )
    write_json(LIBRARY_RETRIEVAL_STATUS_PATH, status)
    return manifest


def extract_text_from_html(raw_html: str) -> tuple[str, str]:
    parser = HTMLTextExtractor()
    parser.feed(raw_html)
    text, title = parser.result()
    parser.close()
    return text, title


def extract_text_for_knowledge(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt", ".json", ".yaml", ".yml", ".rst", ".sql", ".xml", ".py", ".csv"}:
        return path.read_text(encoding="utf-8", errors="ignore").strip()
    if suffix in {".html", ".htm"}:
        text, _ = extract_text_from_html(path.read_text(encoding="utf-8", errors="ignore"))
        return text
    if suffix == ".pdf":
        if shutil.which("pdftotext"):
            result = subprocess.run(
                ["pdftotext", "-layout", "-nopgbrk", "-q", path.as_posix(), "-"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
            text = result.stdout.strip()
            if text and not text.lstrip().startswith("%PDF-"):
                return text
        for module_name in ["pypdf", "PyPDF2"]:
            try:
                module = __import__(module_name, fromlist=["PdfReader"])
                reader = module.PdfReader(path.as_posix())
                pages = []
                for index, page in enumerate(reader.pages):
                    if index >= 120:
                        break
                    page_text = (page.extract_text() or "").strip()
                    if page_text:
                        pages.append(page_text)
                    if sum(len(chunk) for chunk in pages) >= 80000:
                        break
                text = "\n\n".join(pages).strip()
                if text:
                    return text
            except Exception:
                continue
    return ""


def clean_extracted_knowledge_text(text: str) -> str:
    if not text.strip():
        return ""
    raw_lines = [line.replace("\x00", "").strip() for line in text.splitlines()]
    normalized_counts: dict[str, int] = defaultdict(int)
    for line in raw_lines:
        normalized = re.sub(r"\s+", " ", line).strip().lower()
        if normalized:
            normalized_counts[normalized] += 1

    cleaned_lines: list[str] = []
    index = 0
    while index < len(raw_lines):
        line = re.sub(r"\s+", " ", raw_lines[index]).strip()
        next_line = re.sub(r"\s+", " ", raw_lines[index + 1]).strip() if index + 1 < len(raw_lines) else ""
        if line.endswith("-") and next_line and next_line[:1].islower():
            line = f"{line[:-1]}{next_line}"
            index += 1
        normalized = line.lower()
        if not line:
            cleaned_lines.append("")
            index += 1
            continue
        if re.match(r"^\d+_\d+ .* page [ivxlcdm0-9]+$", normalized):
            index += 1
            continue
        if re.match(r"^page [ivxlcdm0-9]+$", normalized):
            index += 1
            continue
        if re.match(r"^\d+( \d+)+$", normalized):
            index += 1
            continue
        if len(line) <= 80 and normalized_counts.get(normalized, 0) >= 3:
            index += 1
            continue
        if any(
            normalized.startswith(prefix)
            for prefix in [
                "copyright",
                "published by",
                "library of congress cataloging",
                "trademarks:",
                "for general information on our other products",
                "limit of liability/disclaimer",
                "requests to the publisher",
                "wiley also publishes",
            ]
        ):
            index += 1
            continue
        cleaned_lines.append(line)
        index += 1

    paragraphs: list[str] = []
    current: list[str] = []
    for line in cleaned_lines:
        if not line:
            if current:
                paragraphs.append(" ".join(current).strip())
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append(" ".join(current).strip())

    compact_paragraphs = []
    seen: set[str] = set()
    for paragraph in paragraphs:
        paragraph = re.sub(r"\s+", " ", paragraph).strip()
        if len(paragraph) < 40:
            continue
        signature = paragraph.lower()
        if signature in seen:
            continue
        seen.add(signature)
        compact_paragraphs.append(paragraph)
    return "\n\n".join(compact_paragraphs).strip()


def normalize_knowledge_text(text: str) -> str:
    cleaned = clean_extracted_knowledge_text(text)
    if cleaned:
        return cleaned
    fallback = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n").strip()
    fallback = re.sub(r"[ \t]+\n", "\n", fallback)
    fallback = re.sub(r"\n{3,}", "\n\n", fallback)
    return fallback.strip()


def summarize_knowledge_text(text: str) -> str:
    cleaned = normalize_knowledge_text(text)
    if not cleaned:
        return ""
    paragraphs = [paragraph.strip() for paragraph in cleaned.split("\n\n") if paragraph.strip()]
    scored: list[tuple[int, str]] = []
    for paragraph in paragraphs:
        haystack = paragraph.lower()
        if any(
            marker in haystack
            for marker in [
                "copyright",
                "isbn",
                "wiley publishing",
                "library of congress",
                "trademarks",
                "permissions",
                "fax",
                "executive editor",
                "production editor",
                "credits",
            ]
        ):
            continue
        score = 0
        for keyword in ["goal", "design", "user", "interaction", "product", "behavior", "persona", "workflow", "research", "interface"]:
            if keyword in haystack:
                score += 2
        if "chapter 1" in haystack or "goal-directed design" in haystack:
            score += 4
        if len(paragraph) >= 120:
            score += 1
        scored.append((score, paragraph))
    scored.sort(key=lambda item: (-item[0], -len(item[1])))
    preferred = [paragraph for score, paragraph in scored if score > 0][:3]
    if preferred:
        return truncate_words(" ".join(preferred), 60)
    return truncate_words(cleaned, 60)


def detect_main_content_start(text: str) -> str:
    for marker in [
        "What This Book Is and What It Is Not",
        "Chapter 1 Goal-Directed Design",
        "Chapter 1",
    ]:
        index = text.find(marker)
        if index != -1:
            return text[index:]
    return text


def chapter_title_from_chunk(chunk: str, fallback_index: int) -> str:
    chunk = re.sub(r"\s+", " ", chunk).strip()
    match = re.match(r"^Chapter\s+(\d+)\s+(.+)$", chunk)
    if match:
        number = match.group(1)
        tail = re.sub(r"\s+", " ", match.group(2)).strip(" -:")
        title_words = []
        for word in tail.split():
            if len(title_words) >= 10:
                break
            if re.fullmatch(r"\d{1,3}", word):
                break
            title_words.append(word)
        title = " ".join(title_words).strip(" -:")
        return f"Chapter {number} — {title}" if title else f"Chapter {number}"
    if chunk.startswith("What This Book Is and What It Is Not"):
        return "Introduction — What This Book Is and What It Is Not"
    words = chunk.split()
    return f"Section {fallback_index} — {' '.join(words[:8])}".strip()


def section_title_from_keywords(text: str, fallback_index: int) -> str:
    keywords = topic_keywords(text, limit=4)
    if keywords:
        return f"Section {fallback_index} — {' / '.join(keywords)}"
    words = text.split()
    return f"Section {fallback_index} — {' '.join(words[:8])}".strip()


def split_knowledge_sections(text: str) -> list[dict[str, Any]]:
    cleaned = normalize_knowledge_text(text)
    if not cleaned:
        return []
    main_text = detect_main_content_start(cleaned)
    parts = re.split(r"(?=Chapter\s+\d+\s)", main_text)
    sections: list[dict[str, Any]] = []
    preface = parts[0].strip() if parts else ""
    section_index = 1
    if preface and len(preface) > 400:
        title = chapter_title_from_chunk(preface, section_index)
        sections.append({"title": title, "slug": slugify(title)[:80], "text": preface})
        section_index += 1
    for chunk in parts[1:] if len(parts) > 1 else ([] if preface else parts):
        chunk = chunk.strip()
        if len(chunk) < 300:
            continue
        title = chapter_title_from_chunk(chunk, section_index)
        sections.append({"title": title, "slug": slugify(title)[:80], "text": chunk})
        section_index += 1
    chapter_numbers = []
    for section in sections:
        match = re.match(r"^Chapter\s+(\d+)", section["title"])
        if match:
            chapter_numbers.append(int(match.group(1)))
    chapter_split_is_valid = len(chapter_numbers) >= 5 and chapter_numbers[:3] == [1, 2, 3]
    if not sections or not chapter_split_is_valid:
        sections = []
        section_index = 1
        paragraphs = [paragraph.strip() for paragraph in main_text.split("\n\n") if paragraph.strip()]
        buffer: list[str] = []
        target_size = 4500
        for paragraph in paragraphs:
            buffer.append(paragraph)
            if len(" ".join(buffer)) >= target_size:
                text_chunk = "\n\n".join(buffer)
                title = section_title_from_keywords(text_chunk, section_index)
                sections.append({"title": title, "slug": slugify(title)[:80], "text": text_chunk})
                section_index += 1
                buffer = []
        if buffer:
            text_chunk = "\n\n".join(buffer)
            title = section_title_from_keywords(text_chunk, section_index)
            sections.append({"title": title, "slug": slugify(title)[:80], "text": text_chunk})
    return sections[:18]


def topic_keywords(text: str, *, limit: int = 12) -> list[str]:
    text = normalize_knowledge_text(text)
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{3,}", text.lower())
    stop = {"this", "that", "with", "from", "have", "into", "your", "about", "para", "cuando", "where", "which", "using", "there", "their", "will", "should", "after", "page", "pages", "chapter", "copyright", "published"}
    counts: dict[str, int] = defaultdict(int)
    for word in words:
        if word in stop:
            continue
        counts[word] += 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [word for word, _ in ranked[:limit]]


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
    text = extract_text_for_knowledge(source_path)
    cleaned_text = normalize_knowledge_text(text)
    source_name = stable_source_name(source_path, source_kind, source_key, previous)
    if source_kind == "inbox":
        copied_source = root / "sources" / source_path.name
        copied_source.write_bytes(source_path.read_bytes())
    status = "processed" if cleaned_text else "unsupported"
    sections = split_knowledge_sections(cleaned_text) if cleaned_text else []
    excerpt = truncate_words(cleaned_text, 120) if cleaned_text else f"Unsupported source type: {source_path.suffix or 'unknown'}"
    summary_text = summarize_knowledge_text(cleaned_text) if cleaned_text else "No extractable text was generated for this source."
    note_path = root / "notes" / f"{source_name}.md"
    summary_path = root / "summaries" / f"{source_name}.md"
    manifest_path = root / "manifests" / f"{source_name}.json"
    processed_path = root / "processed" / f"{source_name}.txt"
    write_text(note_path, f"# {title}\n\n{excerpt}\n")
    write_text(summary_path, f"# {title} summary\n\n- {summary_text}\n")
    write_text(processed_path, cleaned_text + ("\n" if cleaned_text else ""))
    keywords = topic_keywords(cleaned_text)
    note_files = [relative_posix(note_path, root)]
    summary_files = [relative_posix(summary_path, root)]
    section_entries: list[dict[str, Any]] = []
    for section in sections:
        section_note_path = root / "notes" / f"{source_name}__{section['slug']}.md"
        section_summary_path = root / "summaries" / f"{source_name}__{section['slug']}.md"
        section_excerpt = truncate_words(section["text"], 160)
        section_summary = summarize_knowledge_text(section["text"])
        write_text(section_note_path, f"# {section['title']}\n\n{section_excerpt}\n")
        write_text(section_summary_path, f"# {section['title']} summary\n\n- {section_summary}\n")
        section_keywords = topic_keywords(section["text"], limit=10)
        section_entries.append(
            {
                "title": section["title"],
                "slug": section["slug"],
                "note_path": relative_posix(section_note_path, root),
                "summary_path": relative_posix(section_summary_path, root),
                "keywords": section_keywords,
            }
        )
        note_files.append(relative_posix(section_note_path, root))
        summary_files.append(relative_posix(section_summary_path, root))
    write_json(
        manifest_path,
        {
            "source": source_key,
            "source_kind": source_kind,
            "title": title,
            "label": label,
            "status": status,
            "processed_path": relative_posix(processed_path, root),
            "note_path": relative_posix(note_path, root),
            "summary_path": relative_posix(summary_path, root),
            "keywords": keywords,
            "sections": section_entries,
            "updated_at": now_iso(),
        },
    )
    return {
        "status": status,
        "processed_at": now_iso(),
        "source_name": source_name,
        "title": title,
        "label": label,
        "keywords": keywords,
        "sections": section_entries,
        "note_files": note_files,
        "summary_files": summary_files,
        "index_files": [],
        "processed_path": relative_posix(processed_path, root),
        "manifest_path": relative_posix(manifest_path, root),
    }


def canonicalize_url(raw_url: str) -> str:
    parsed = urllib_parse.urlsplit(raw_url.strip())
    scheme = (parsed.scheme or "https").lower()
    host = (parsed.hostname or "").lower()
    port = parsed.port
    netloc = host
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    query_pairs = urllib_parse.parse_qsl(parsed.query, keep_blank_values=True)
    kept_query = [(key, value) for key, value in query_pairs if key.lower() not in {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"}]
    query = urllib_parse.urlencode(kept_query, doseq=True)
    return urllib_parse.urlunsplit((scheme, netloc, path, query, ""))


def build_source_id(url: str, existing_sources: list[dict[str, Any]]) -> str:
    parsed = urllib_parse.urlsplit(url)
    base = slugify("_".join(part for part in [parsed.hostname or "", parsed.path.strip("/").replace("/", "_")] if part))
    base = base[:80] or "remote_source"
    existing_ids = {row.get("id") for row in existing_sources}
    if base not in existing_ids:
        return base
    suffix = hashlib.md5(url.encode("utf-8")).hexdigest()[:8]
    return f"{base[:71]}_{suffix}"


def detect_remote_type(url: str, declared_type: str, content_type_header: str, raw_bytes: bytes) -> str:
    if declared_type != "auto":
        return declared_type
    header = (content_type_header or "").lower()
    if "pdf" in header or raw_bytes.startswith(b"%PDF-"):
        return "pdf"
    if "html" in header:
        return "html"
    if "markdown" in header:
        return "md"
    if header.startswith("text/plain"):
        return "txt"
    suffix = Path(urllib_parse.urlsplit(url).path).suffix.lower()
    if suffix in {".html", ".htm"}:
        return "html"
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".md", ".markdown"}:
        return "md"
    if suffix == ".txt":
        return "txt"
    sample = raw_bytes[:2048].decode("utf-8", errors="ignore").lower()
    if "<html" in sample or "<body" in sample:
        return "html"
    return "txt"


def title_from_text(text: str, fallback: str) -> str:
    for line in text.splitlines():
        candidate = line.strip().lstrip("#").strip()
        if len(candidate) >= 4:
            return candidate[:160]
    return fallback


def extract_remote_payload(raw_path: Path, detected_type: str) -> tuple[str, str, list[str]]:
    notes: list[str] = []
    if detected_type == "html":
        html_text = raw_path.read_text(encoding="utf-8", errors="ignore")
        extracted, title = extract_text_from_html(html_text)
        if title:
            notes.append("Preserved HTML title")
        notes.append("Removed obvious HTML boilerplate")
        return extracted, title, notes
    if detected_type == "pdf":
        extracted = extract_text_for_knowledge(raw_path)
        notes.append("Used PDF text extraction")
        return extracted, "", notes
    extracted = raw_path.read_text(encoding="utf-8", errors="ignore")
    notes.append("Preserved text content with normalized UTF-8 decoding")
    return extracted, "", notes


def remote_frontmatter(tags: list[str]) -> str:
    if not tags:
        return "tags: []"
    lines = ["tags:"]
    lines.extend(f"  - {tag}" for tag in tags)
    return "\n".join(lines)


def parse_http_headers(raw_headers: str) -> tuple[int, dict[str, str]]:
    normalized = raw_headers.replace("\r\n", "\n")
    blocks = [block.strip() for block in re.split(r"\n\s*\n", normalized) if block.strip()]
    if not blocks:
        return 0, {}
    final_block = blocks[-1]
    lines = [line.strip() for line in final_block.splitlines() if line.strip()]
    status_line = lines[0] if lines else ""
    match = re.match(r"HTTP/\S+\s+(\d+)", status_line)
    status_code = int(match.group(1)) if match else 0
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip()] = value.strip()
    return status_code, headers


def fetch_remote_payload_bytes(url: str) -> tuple[bytes, int, dict[str, str]]:
    request = urllib_request.Request(
        url,
        headers={"User-Agent": "ai-context-engine/16 (+local knowledge ingestion)"},
    )
    try:
        with urllib_request.urlopen(request, timeout=20) as response:
            raw_bytes = response.read()
            status_code = getattr(response, "status", response.getcode())
            headers = {key: value for key, value in response.headers.items()}
        return raw_bytes, int(status_code), headers
    except urllib_error.URLError as exc:
        if not shutil.which("curl"):
            raise
        with tempfile.TemporaryDirectory(prefix="ai_context_engine_fetch_") as temp_dir:
            headers_path = Path(temp_dir) / "headers.txt"
            body_path = Path(temp_dir) / "body.bin"
            result = subprocess.run(
                [
                    "curl",
                    "-L",
                    "-sS",
                    "--fail",
                    "-D",
                    headers_path.as_posix(),
                    "-o",
                    body_path.as_posix(),
                    url,
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise exc
            raw_bytes = body_path.read_bytes()
            status_code, headers = parse_http_headers(headers_path.read_text(encoding="utf-8", errors="ignore"))
            return raw_bytes, status_code or 200, headers


def register_remote_source(mod_id: str, url: str, declared_type: str = "auto", tags: list[str] | None = None) -> dict[str, Any]:
    normalized = slugify(mod_id)
    root = mod_root(normalized)
    if not (root / "mod.json").exists():
        raise ValueError(f"Mod `{normalized}` does not exist. Run `ctx-library learn {normalized}` first.")
    if declared_type not in REMOTE_DECLARED_TYPES:
        raise ValueError(f"Unsupported source type `{declared_type}`.")
    parsed = urllib_parse.urlsplit(url.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must use http or https and include a host.")
    manifest = load_remote_sources_manifest(root)
    canonical_url = canonicalize_url(url)
    if any(row.get("canonical_url") == canonical_url for row in manifest.get("sources", [])):
        raise ValueError(f"Source already registered for `{canonical_url}`.")
    source_id = build_source_id(canonical_url, manifest.get("sources", []))
    row = {
        "id": source_id,
        "url": url.strip(),
        "canonical_url": canonical_url,
        "declared_type": declared_type,
        "detected_type": None,
        "tags": sorted(set(tags or [])),
        "status": "pending",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "last_fetched_at": None,
        "last_successful_snapshot_id": None,
        "last_error": None,
    }
    manifest.setdefault("sources", []).append(row)
    save_remote_sources_manifest(root, manifest)
    mod_manifest = load_mod_manifest(root)
    mod_manifest["remote_sources_count"] = len(manifest.get("sources", []))
    save_mod_manifest(root, mod_manifest)
    return {"mod_id": normalized, "source": row, "manifest_path": remote_manifest_path(root).as_posix(), "events": [f"registered:{source_id}"]}


def fetch_remote_sources(mod_id: str, source_id: str | None = None, force: bool = False) -> dict[str, Any]:
    normalized = slugify(mod_id)
    root = mod_root(normalized)
    if not (root / "mod.json").exists():
        raise ValueError(f"Mod `{normalized}` does not exist. Run `ctx-library learn {normalized}` first.")
    manifest = load_remote_sources_manifest(root)
    sources = manifest.get("sources", [])
    selected = [row for row in sources if source_id in {None, row.get("id")}]
    if source_id and not selected:
        raise ValueError(f"Unknown source id `{source_id}` for mod `{normalized}`.")
    events: list[str] = []
    results: list[dict[str, Any]] = []
    success_count = 0
    for row in selected:
        try:
            raw_bytes, status_code, response_headers = fetch_remote_payload_bytes(row["url"])
            content_type_header = response_headers.get("Content-Type", "")
            etag = response_headers.get("ETag")
            last_modified = response_headers.get("Last-Modified")
            if int(status_code) < 200 or int(status_code) >= 300:
                raise RuntimeError(f"HTTP status {status_code}")
            detected_type = detect_remote_type(row["canonical_url"], row.get("declared_type", "auto"), content_type_header, raw_bytes)
            if detected_type not in REMOTE_TYPE_EXTENSIONS:
                raise RuntimeError(f"Unsupported detected type `{detected_type}`")
            checksum = hashlib.sha256(raw_bytes).hexdigest()
            if not force and checksum == row.get("last_checksum_sha256"):
                row["status"] = "fetched"
                row["updated_at"] = now_iso()
                row["last_error"] = None
                events.append(f"skipped_unchanged:{row['id']}")
                results.append({"source_id": row["id"], "status": "skipped", "reason": "unchanged"})
                continue
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            snapshot_id = f"{row['id']}_{timestamp}"
            raw_extension = REMOTE_TYPE_EXTENSIONS[detected_type]
            raw_path = root / "remote_sources" / "raw" / f"{snapshot_id}{raw_extension}"
            raw_path.write_bytes(raw_bytes)
            extracted_text, extracted_title, extraction_notes = extract_remote_payload(raw_path, detected_type)
            cleaned_text = normalize_knowledge_text(extracted_text)
            if not cleaned_text:
                raise RuntimeError("Extraction produced empty content")
            title = extracted_title or title_from_text(cleaned_text, row["id"].replace("_", " ").title())
            extracted_path = root / "remote_sources" / "extracted" / f"{snapshot_id}.md"
            write_text(extracted_path, cleaned_text + "\n")
            inbox_path = root / "inbox" / f"remote_{row['id']}.md"
            canonical_doc = (
                "---\n"
                "source_kind: remote_url\n"
                f"source_id: {row['id']}\n"
                f"snapshot_id: {snapshot_id}\n"
                f"source_url: {row['url']}\n"
                f"canonical_url: {row['canonical_url']}\n"
                f"detected_type: {detected_type}\n"
                f"fetched_at: {now_iso()}\n"
                f"title: {title}\n"
                f"{remote_frontmatter(row.get('tags', []))}\n"
                "---\n\n"
                f"# {title}\n\n"
                f"{cleaned_text}\n"
            )
            write_text(inbox_path, canonical_doc)
            snapshot = {
                "snapshot_id": snapshot_id,
                "source_id": row["id"],
                "url": row["url"],
                "canonical_url": row["canonical_url"],
                "fetched_at": now_iso(),
                "declared_type": row.get("declared_type", "auto"),
                "detected_type": detected_type,
                "content_type_header": content_type_header,
                "http_status": status_code,
                "checksum_sha256": checksum,
                "raw_path": relative_posix(raw_path, root),
                "extracted_path": relative_posix(extracted_path, root),
                "inbox_path": relative_posix(inbox_path, root),
                "title": title,
                "etag": etag,
                "last_modified": last_modified,
                "word_count": len(cleaned_text.split()),
                "extraction_notes": extraction_notes,
            }
            write_json(root / "remote_sources" / "snapshots" / f"{snapshot_id}.json", snapshot)
            row.update(
                {
                    "status": "fetched",
                    "detected_type": detected_type,
                    "updated_at": now_iso(),
                    "last_fetched_at": snapshot["fetched_at"],
                    "last_successful_snapshot_id": snapshot_id,
                    "last_checksum_sha256": checksum,
                    "last_error": None,
                }
            )
            success_count += 1
            events.extend(
                [
                    f"fetched:{row['id']}",
                    f"snapshot_created:{snapshot_id}",
                    f"extracted:{relative_posix(extracted_path, root)}",
                    f"inbox_emitted:{relative_posix(inbox_path, root)}",
                ]
            )
            results.append({"source_id": row["id"], "status": "fetched", "snapshot_id": snapshot_id, "inbox_path": inbox_path.as_posix()})
        except (urllib_error.URLError, RuntimeError, OSError, ValueError) as exc:
            row["status"] = "failed"
            row["updated_at"] = now_iso()
            row["last_error"] = str(exc)
            events.append(f"failed:{row['id']}")
            results.append({"source_id": row["id"], "status": "failed", "error": str(exc)})
    save_remote_sources_manifest(root, manifest)
    mod_manifest = load_mod_manifest(root)
    mod_manifest["remote_sources_count"] = len(manifest.get("sources", []))
    save_mod_manifest(root, mod_manifest)
    all_failed = bool(selected) and success_count == 0 and all(result.get("status") == "failed" for result in results)
    return {
        "mod_id": normalized,
        "selected_sources": [row.get("id") for row in selected],
        "results": results,
        "events": events,
        "exit_code": 1 if all_failed else 0,
    }


def process_mod_documents(mod_id: str) -> dict[str, Any]:
    manifest = bootstrap_mod(mod_id)
    root = mod_root(mod_id)
    state = load_mod_state(root)
    warnings: list[str] = []
    pending: list[dict[str, Any]] = []
    seen_sources: list[str] = []

    for source_path in sorted((root / "inbox").glob("*")):
        if not should_process_inbox_file(source_path):
            continue
        source_key = source_path.name
        seen_sources.append(source_key)
        current_hash = file_md5(source_path)
        current_mtime = file_mtime(source_path)
        previous = state["processed_docs"].get(source_key, {})
        if previous.get("hash") != current_hash or mtime_changed(previous.get("mtime"), current_mtime):
            invalidate_source_artifacts(root, previous)
            pending.append(
                {
                    "kind": "inbox",
                    "path": source_path,
                    "key": source_key,
                    "title": source_path.stem,
                    "hash": current_hash,
                    "mtime": current_mtime,
                    "previous": previous,
                }
            )

    references = parse_references_file(root / "inbox" / "references.md")
    for reference in references:
        reference_path = reference["path"]
        reference_key = reference_path.as_posix()
        if reference_path.suffix.lower() not in SUPPORTED_REFERENCED_EXTENSIONS:
            warnings.append(f"unsupported_reference:{reference_key}")
            continue
        previous = state["referenced_files"].get(reference_key, {})
        if not reference_path.exists():
            warnings.append(f"missing_reference:{reference_key}")
            continue
        current_mtime = file_mtime(reference_path)
        if mtime_changed(previous.get("mtime"), current_mtime) or previous.get("label") != reference.get("label"):
            invalidate_source_artifacts(root, previous)
            pending.append(
                {
                    "kind": "reference",
                    "path": reference_path,
                    "key": reference_key,
                    "title": reference.get("label") or reference_path.stem,
                    "label": reference.get("label"),
                    "mtime": current_mtime,
                    "previous": previous,
                }
            )

    for item in pending:
        processed = process_knowledge_source(
            root,
            source_path=item["path"],
            source_kind=item["kind"],
            source_key=item["key"],
            title=item["title"],
            label=item.get("label"),
            previous=item.get("previous"),
        )
        processed["mtime"] = item["mtime"]
        if item["kind"] == "inbox":
            processed["hash"] = item["hash"]
            state["processed_docs"][item["key"]] = processed
        else:
            state["referenced_files"][item["key"]] = processed

    index_files = rebuild_mod_indices(root, state)
    for bucket_name in ["processed_docs", "referenced_files"]:
        for entry in state.get(bucket_name, {}).values():
            entry["index_files"] = sorted({path for paths in index_files.values() for path in paths})
    state["last_processed"] = now_iso()
    save_mod_state(root, state)
    manifest = bootstrap_mod(mod_id, aliases=manifest.get("aliases", []), title=manifest.get("title"))
    manifest["last_processed"] = state["last_processed"]
    manifest["inbox_count"] = len(seen_sources)
    manifest["referenced_count"] = len(references)
    manifest["remote_sources_count"] = len(load_remote_sources_manifest(root).get("sources", []))
    save_mod_manifest(root, manifest)
    return {
        "mod_id": slugify(mod_id),
        "sources_seen": seen_sources,
        "pending_count": len(pending),
        "notes_generated": sum(len(entry.get("note_files", [])) for entry in state["processed_docs"].values()) + sum(len(entry.get("note_files", [])) for entry in state["referenced_files"].values()),
        "summaries_generated": sum(len(entry.get("summary_files", [])) for entry in state["processed_docs"].values()) + sum(len(entry.get("summary_files", [])) for entry in state["referenced_files"].values()),
        "referenced_count": len(references),
        "warnings": warnings,
        "status": "processed" if state["processed_docs"] or state["referenced_files"] else "ready_empty",
    }


def infer_candidate_mods(task: str) -> list[str]:
    registry = library_registry().get("mods", {})
    haystack = task.lower()
    matches = []
    for mod_id, info in registry.items():
        aliases = [mod_id, *info.get("aliases", [])]
        if any(alias and alias in haystack for alias in aliases):
            matches.append(mod_id)
    if matches:
        return sorted(set(matches))
    for hint, mod_id in {
        "ux": "ux",
        "ui": "ux",
        "design": "ux",
        "accessibility": "accessibility",
        "a11y": "accessibility",
        "architecture": "architecture",
        "api": "api",
        "testing": "testing",
    }.items():
        if hint in haystack:
            bootstrap_mod(mod_id)
            matches.append(mod_id)
    return sorted(set(matches))


def retrieve_knowledge(task: str) -> dict[str, Any]:
    ensure_library_artifacts()
    candidate_mods = infer_candidate_mods(task)
    topics = topic_keywords(task, limit=6)
    selected_artifacts: list[str] = []
    artifact_rows: list[dict[str, Any]] = []
    for mod_id in candidate_mods[:3]:
        root = mod_root(mod_id)
        topic_index = read_json(root / "indices" / "topic_index.json", {})
        keyword_index = read_json(root / "indices" / "keyword_index.json", {})
        for topic in topics:
            for path in topic_index.get(topic, [])[:2] + keyword_index.get(topic, [])[:1]:
                if path in selected_artifacts:
                    continue
                selected_artifacts.append(path)
                text = Path(path).read_text(encoding="utf-8", errors="ignore") if Path(path).exists() else ""
                artifact_rows.append(
                    {
                        "path": path,
                        "summary": truncate_words(text.replace("\n", " "), 28),
                        "estimated_tokens": estimate_tokens(text),
                    }
                )
        if selected_artifacts:
            break
    status = read_json(LIBRARY_RETRIEVAL_STATUS_PATH, {})
    status.update(
        {
            "generated_at": date.today().isoformat(),
            "installed_iteration": current_engine_iteration(),
            "mods_total": len(library_registry().get("mods", {})),
            "retrieval_events": int(status.get("retrieval_events", 0) or 0) + 1,
            "last_selected_artifacts": selected_artifacts[:6],
            "supports_reference_ingestion": True,
            "supports_remote_ingestion": True,
        }
    )
    write_json(LIBRARY_RETRIEVAL_STATUS_PATH, status)
    return {
        "mods": candidate_mods[:3],
        "topics": topics,
        "selected_artifacts": selected_artifacts[:6],
        "artifacts": artifact_rows[:6],
        "strategy": "topic_first_minimal_pack" if selected_artifacts else "empty_fallback",
    }


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
                "memory_dir": ".ai_context_memory",
                "telemetry_dir": ".context_metrics",
                "global_metrics_dir": ".ai_context_global_metrics",
                "cost_dir": ".ai_context_cost",
                "task_memory_dir": ".ai_context_task_memory",
                "failure_memory_dir": ".ai_context_failure_memory",
                "memory_graph_dir": ".ai_context_memory_graph",
                "library_dir": ".ai_context_library",
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
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]).strip() + " ..."


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
    repo_compat_dir = repo / REPO_COMPAT_DIRNAME if repo else None
    return {
        "boot_summary": read_json(BOOT_SUMMARY_PATH, {}),
        "user_defaults": read_json(BOOT_DEFAULTS_PATH, {}),
        "project_registry": read_json(BOOT_PROJECTS_PATH, {}),
        "model_routing": read_json(BOOT_MODEL_ROUTING_PATH, {}),
        "cost_optimizer": read_json(COST_STATUS_PATH, {}),
        "task_memory": read_json(TASK_MEMORY_STATUS_PATH, {}),
        "task_taxonomy": read_json(TASK_MEMORY_TAXONOMY_PATH, {}),
        "failure_memory": read_json(FAILURE_MEMORY_STATUS_PATH, {}),
        "memory_graph": read_json(MEMORY_GRAPH_STATUS_PATH, {}),
        "repo_compat": {
            "exists": bool(repo_compat_dir and repo_compat_dir.exists()),
            "path": repo_compat_dir.as_posix() if repo_compat_dir else "",
            "derived_boot_summary": read_json(repo_compat_dir / "derived_boot_summary.json", {}) if repo_compat_dir and repo_compat_dir.exists() else {},
            "project_bootstrap": read_json(repo_compat_dir / "project_bootstrap.json", {}) if repo_compat_dir and repo_compat_dir.exists() else {},
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
        ".ai_context_memory/",
        ".context_metrics/",
        ".ai_context_global_metrics/",
        ".ai_context_cost/",
        ".ai_context_planner/",
        ".ai_context_task_memory/",
        ".ai_context_failure_memory/",
        ".ai_context_memory_graph/",
        ".ai_context_library/",
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
    command = getattr(args, "command", "status")
    try:
        if command == "learn":
            payload = bootstrap_mod(args.mod_id, aliases=getattr(args, "aliases", []) or [], create_reference_stub=True)
        elif command == "process":
            payload = process_mod_documents(args.mod_id)
        elif command == "add-source":
            payload = register_remote_source(args.mod_id, args.url, getattr(args, "declared_type", "auto"), getattr(args, "tags", []) or [])
        elif command == "fetch-sources":
            payload = fetch_remote_sources(args.mod_id, getattr(args, "source_id", None), bool(getattr(args, "force", False)))
        elif command == "retrieve":
            payload = retrieve_knowledge(args.task)
        else:
            payload = {
                "state": refresh_engine_state(),
                "registry": library_registry(),
                "telemetry": read_json(CONTEXT_WEEKLY_SUMMARY_PATH, {}),
                "retrieval_status": read_json(LIBRARY_RETRIEVAL_STATUS_PATH, {}),
            }
    except ValueError as exc:
        payload = {"error": str(exc), "command": command}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 1
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return int(payload.get("exit_code", 0) or 0)
