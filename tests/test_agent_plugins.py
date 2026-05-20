from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_generator() -> None:
    subprocess.run([sys.executable, "scripts/generate-agent-integrations.py"], cwd=ROOT, check=True)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_agent_plugin_generator_outputs_required_artifacts():
    run_generator()
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]

    codex_manifest_path = ROOT / "integrations" / "codex" / "plugins" / "aictx" / ".codex-plugin" / "plugin.json"
    claude_manifest_path = ROOT / "integrations" / "claude" / "plugins" / "aictx" / ".claude-plugin" / "plugin.json"
    codex_skill_path = ROOT / "integrations" / "codex" / "plugins" / "aictx" / "skills" / "aictx" / "SKILL.md"
    claude_skill_path = ROOT / "integrations" / "claude" / "plugins" / "aictx" / "skills" / "aictx" / "SKILL.md"

    assert codex_manifest_path.exists()
    assert claude_manifest_path.exists()
    assert codex_skill_path.exists()
    assert claude_skill_path.exists()

    codex_manifest = json.loads(codex_manifest_path.read_text(encoding="utf-8"))
    claude_manifest = json.loads(claude_manifest_path.read_text(encoding="utf-8"))
    assert codex_manifest["version"] == version
    assert claude_manifest["version"] == version
    assert codex_manifest["skills"] == "./skills/"

    for skill_path in (codex_skill_path, claude_skill_path):
        text = skill_path.read_text(encoding="utf-8")
        assert "Prefer AICTX MCP tools when available" in text
        assert "MCP-first" in text or "Prefer MCP tool" in text
        assert 'aictx resume --repo . --task "<task summary>" --json' in text
        assert 'aictx finalize --repo . --status success --summary "<what changed>" --json' in text
        assert "Generated from integrations/templates/agent-guidance.md" in text

    codex_marketplace = json.loads((ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    claude_marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert codex_marketplace["plugins"][0]["source"]["path"] == "./integrations/codex/plugins/aictx"
    assert claude_marketplace["plugins"][0]["source"] == "./integrations/claude/plugins/aictx"


def test_agent_plugin_generator_is_idempotent():
    run_generator()
    tracked = [
        ROOT / "integrations" / "codex" / "plugins" / "aictx" / ".codex-plugin" / "plugin.json",
        ROOT / "integrations" / "claude" / "plugins" / "aictx" / ".claude-plugin" / "plugin.json",
        ROOT / "integrations" / "codex" / "plugins" / "aictx" / "skills" / "aictx" / "SKILL.md",
        ROOT / "integrations" / "claude" / "plugins" / "aictx" / "skills" / "aictx" / "SKILL.md",
        ROOT / ".agents" / "plugins" / "marketplace.json",
        ROOT / ".claude-plugin" / "marketplace.json",
    ]
    before = {path: sha(path) for path in tracked}
    run_generator()
    after = {path: sha(path) for path in tracked}
    assert after == before
