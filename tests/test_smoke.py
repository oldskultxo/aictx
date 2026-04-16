from pathlib import Path

from aictx.agent_runtime import (
    AGENTS_END,
    AGENTS_START,
    render_agent_runtime,
    render_repo_agents_block,
    resolve_workspace_root,
    upsert_marked_block,
)
from aictx.scaffold import TEMPLATES_DIR
from aictx.state import default_global_config


def test_default_global_config_has_workspace():
    cfg = default_global_config()
    assert cfg["active_workspace"] == "default"


def test_templates_exist():
    assert (TEMPLATES_DIR / "context_packet_schema.json").exists()
    assert (TEMPLATES_DIR / "user_preferences.json").exists()
    assert (TEMPLATES_DIR / "model_routing.json").exists()


def test_agent_runtime_mentions_savings_sources():
    text = render_agent_runtime()
    assert ".context_metrics/weekly_summary.json" in text
    assert "global_context_savings.json" in text
    assert "unknown" in text


def test_upsert_marked_block_is_idempotent(tmp_path: Path):
    path = tmp_path / "AGENTS.md"
    block = render_repo_agents_block()
    upsert_marked_block(path, block)
    first = path.read_text(encoding="utf-8")
    upsert_marked_block(path, block)
    second = path.read_text(encoding="utf-8")
    assert first == second
    assert first.count(AGENTS_START) == 1
    assert first.count(AGENTS_END) == 1


def test_resolve_workspace_root_prefers_deepest_match(tmp_path: Path):
    outer = tmp_path / "workspace"
    inner = outer / "nested"
    repo = inner / "repo"
    repo.mkdir(parents=True)
    root = resolve_workspace_root(repo, [str(tmp_path), str(outer), str(inner)])
    assert root == inner
