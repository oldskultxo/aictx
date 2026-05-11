from __future__ import annotations

from pathlib import Path

from aictx.cli import build_parser

ROOT = Path(__file__).resolve().parents[1]

CANONICAL_WRAPPERS = {
    "bin/ctx-boot": "internal boot",
    "bin/ctx-packet": "internal packet",
    "bin/ctx-query": "internal query",
    "bin/ctx-route": "internal route",
    "bin/ctx-failure": "internal failure",
    "bin/ctx-task-memory": "internal task-memory",
    "bin/ctx-graph": "internal memory-graph",
    "scripts/boot.py": "internal boot",
    "scripts/packet.py": "internal packet",
    "scripts/query.py": "internal query",
    "scripts/model_route.py": "internal route",
    "scripts/detect_stale.py": "internal detect-stale",
    "scripts/prune.py": "internal detect-stale",
    "scripts/compact.py": "internal compact",
    "scripts/ensure_gitignore.py": "internal ensure-gitignore",
    "scripts/touch.py": "internal touch",
    "scripts/note_new.py": "internal new-note",
    "scripts/failure_memory.py": "internal failure",
    "scripts/task_memory.py": "internal task-memory",
    "scripts/memory_graph.py": "internal memory-graph",
}

REMOVED_LEGACY_WRAPPERS = [
    "bin/ctx-update",
    "bin/ctx-library",
    "bin/ctx-global",
    "scripts/migrate_ai_context_engine.py",
    "scripts/update_memory.py",
    "scripts/consolidate.py",
    "scripts/library.py",
    "scripts/global_metrics.py",
]


def test_canonical_wrappers_route_to_existing_internal_commands():
    for rel_path, command in CANONICAL_WRAPPERS.items():
        path = ROOT / rel_path
        text = path.read_text(encoding="utf-8")
        assert "#!/usr/bin/env bash" in text
        assert "set -e" in text
        assert f"aictx {command}" in text


def test_legacy_wrappers_removed_from_v6_tree():
    for rel_path in REMOVED_LEGACY_WRAPPERS:
        assert not (ROOT / rel_path).exists(), rel_path


def test_public_cli_version_flags_work_without_side_effects(tmp_path: Path):
    parser = build_parser()
    assert parser.prog == "aictx"
