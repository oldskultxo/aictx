from __future__ import annotations

import tomllib
from pathlib import Path

from aictx.continuity import (
    CONTINUITY_METRICS_PATH,
    DECISIONS_PATH,
    DEDUPE_REPORT_PATH,
    HANDOFF_PATH,
    SEMANTIC_REPO_PATH,
    STALENESS_PATH,
)
from aictx.failure_memory import FAILURE_PATTERNS_PATH
from aictx.scaffold import init_repo_scaffold
from aictx.state import REPO_CONTINUITY_SESSION_PATH, REPO_METRICS_DIR, REPO_STRATEGY_MEMORY_DIR, REPO_TASKS_ACTIVE_PATH, REPO_TASK_THREADS_DIR


ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
PYPROJECT_PATH = ROOT / "pyproject.toml"

def test_init_repo_scaffold_creates_required_base_runtime_structure(tmp_path: Path):
    repo = tmp_path / "repo"
    created = init_repo_scaffold(repo, update_gitignore=False)

    assert (repo / ".aictx").is_dir()
    assert (repo / ".aictx" / "continuity").is_dir()
    assert (repo / ".aictx" / "metrics").is_dir()
    assert (repo / ".aictx" / "strategy_memory").is_dir()
    assert (repo / ".aictx" / "failure_memory" / "failure_patterns.jsonl").is_file()
    assert (repo / ".aictx" / "metrics" / "execution_logs.jsonl").is_file()
    assert (repo / ".aictx" / "metrics" / "execution_feedback.jsonl").is_file()
    assert (repo / ".aictx" / "strategy_memory" / "strategies.jsonl").is_file()
    assert (repo / ".aictx" / "state.json").is_file()
    assert str(repo / ".aictx" / "continuity") in created


def test_pyproject_describes_continuity_runtime():
    payload = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))

    assert payload["project"]["version"] == "4.7.1"
    assert payload["project"]["description"] == "Repo-local continuity runtime for coding agents"


def test_readme_contract_section_mentions_current_runtime_and_optional_repomap_artifacts():
    text = README_PATH.read_text(encoding="utf-8")

    assert "Current documented implementation: `4.7.1`" in text
    assert "## Artifact contract" in text
    assert "The stable repo-local continuity artifact contract in `4.7.1` is:" in text
    assert ".aictx/repo_map/config.json" in text
    assert ".aictx/repo_map/manifest.json" in text
    assert ".aictx/repo_map/index.json" in text
    assert ".aictx/repo_map/status.json" in text
    assert "Optional or latest-run artifacts may also appear:" in text
