from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from aictx._version import __version__
from aictx.cli import build_parser

ROOT = Path(__file__).resolve().parents[1]

ACTIVE_BIN_WRAPPERS = {
    "bin/ctx-boot": "internal boot",
    "bin/ctx-packet": "internal packet",
    "bin/ctx-query": "internal query",
    "bin/ctx-route": "internal route",
    "bin/ctx-update": "internal migrate",
    "bin/ctx-failure": "internal failure",
    "bin/ctx-task-memory": "internal task-memory",
    "bin/ctx-graph": "internal memory-graph",
}

ACTIVE_SCRIPT_WRAPPERS = {
    "scripts/boot.py": "internal boot",
    "scripts/packet.py": "internal packet",
    "scripts/query.py": "internal query",
    "scripts/model_route.py": "internal route",
    "scripts/migrate_ai_context_engine.py": "internal migrate",
    "scripts/update_memory.py": "internal migrate",
    "scripts/consolidate.py": "internal migrate",
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

DEPRECATED_WRAPPERS = [
    "bin/ctx-library",
    "bin/ctx-global",
    "scripts/library.py",
    "scripts/global_metrics.py",
]


def _env() -> dict[str, str]:
    env = os.environ.copy()
    exe_dir = str(Path(sys.executable).resolve().parent)
    env["PATH"] = exe_dir + os.pathsep + env.get("PATH", "")
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    env.setdefault("HOME", str(ROOT / ".tmp" / "test-home"))
    return env


def test_active_legacy_wrappers_route_to_existing_internal_commands():
    for rel_path, command in {**ACTIVE_BIN_WRAPPERS, **ACTIVE_SCRIPT_WRAPPERS}.items():
        path = ROOT / rel_path
        text = path.read_text(encoding="utf-8")
        assert "#!/usr/bin/env bash" in text
        assert "set -e" in text
        assert f"aictx {command}" in text

        result = subprocess.run(
            [str(path), "--help"],
            cwd=ROOT,
            env=_env(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        assert result.returncode == 0, (rel_path, result.stdout, result.stderr)
        assert "usage:" in (result.stdout + result.stderr).lower()


def test_deprecated_wrappers_exit_with_clear_message():
    for rel_path in DEPRECATED_WRAPPERS:
        result = subprocess.run(
            [str(ROOT / rel_path)],
            cwd=ROOT,
            env=_env(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        output = result.stdout + result.stderr
        assert result.returncode == 2, (rel_path, output)
        assert "deprecated" in output.lower()


def test_public_cli_version_flags_work_without_side_effects(tmp_path: Path):
    env = _env()
    env["PYTHONPATH"] = str(ROOT / "src")
    for flag in ["--version", "-v"]:
        result = subprocess.run(
            [sys.executable, "-m", "aictx.cli", flag],
            cwd=tmp_path,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        assert result.returncode == 0, (flag, result.stdout, result.stderr)
        assert result.stdout == f"aictx {__version__}\n"
        assert result.stderr == ""
        assert not (tmp_path / ".aictx").exists()



def test_public_cli_help_surface_is_stable_and_hides_internal_commands():
    help_text = build_parser().format_help()
    for command in ["install", "init", "suggest", "reflect", "reuse", "report", "clean", "uninstall"]:
        assert command in help_text
    help_lines = help_text.splitlines()
    for hidden in [
        "internal",
        "boot",
        "packet",
        "query",
        "route",
        "migrate",
        "memory-graph",
        "library",
        "global",
    ]:
        assert not any(line.startswith(f"  {hidden} ") for line in help_lines)
        assert f"{{{hidden}" not in help_text
        assert f",{hidden}" not in help_text
