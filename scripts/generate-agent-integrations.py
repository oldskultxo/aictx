#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "integrations" / "templates" / "agent-guidance.md"
NOTICE = "<!-- Generated from integrations/templates/agent-guidance.md. Do not edit directly. -->"


def read_project() -> dict[str, Any]:
    pyproject = ROOT / "pyproject.toml"
    if not pyproject.exists():
        return {"version": "0.0.0", "name": "aictx"}
    payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = payload.get("project", {}) if isinstance(payload.get("project"), dict) else {}
    return project


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8")


def license_text() -> str:
    path = ROOT / "LICENSE"
    return path.read_text(encoding="utf-8") if path.exists() else "MIT\n"


def skill_body(guidance: str) -> str:
    return f"""---
name: aictx
description: Use this skill when working in a repository that uses AICTX for repo-local operational continuity. Prefer AICTX MCP tools when available, fall back to CLI commands, resume before substantial work, and finalize factual continuity after work.
---

{NOTICE}

{guidance}
"""


def codex_manifest(version: str) -> dict[str, Any]:
    return {
        "name": "aictx",
        "version": version,
        "description": "Use AICTX repo-local operational continuity in Codex.",
        "author": {"name": "Santi Santamaria", "url": "https://github.com/oldskultxo"},
        "homepage": "https://aictx.org",
        "repository": "https://github.com/oldskultxo/aictx",
        "license": "MIT",
        "keywords": ["aictx", "coding-agents", "operational-continuity", "repo-local-memory", "mcp", "codex"],
        "skills": "./skills/",
        "interface": {
            "displayName": "AICTX",
            "shortDescription": "Resume and finalize repo-local continuity with AICTX.",
            "longDescription": "Packages the AICTX workflow for Codex. Agents should prefer AICTX MCP tools when available and fall back to CLI commands otherwise.",
            "developerName": "Santi Santamaria",
            "category": "Productivity",
            "websiteURL": "https://aictx.org",
            "defaultPrompt": [
                "Resume AICTX continuity before this task.",
                "Finalize AICTX continuity after this task.",
                "Inspect the AICTX Continuity View.",
            ],
        },
    }


def claude_manifest(version: str) -> dict[str, Any]:
    return {
        "name": "aictx",
        "description": "Use AICTX repo-local operational continuity in Claude Code.",
        "version": version,
        "author": {"name": "Santi Santamaria", "url": "https://github.com/oldskultxo"},
        "homepage": "https://aictx.org",
        "repository": "https://github.com/oldskultxo/aictx",
        "license": "MIT",
    }


def generate() -> None:
    project = read_project()
    version = str(project.get("version") or "0.0.0")
    guidance = TEMPLATE.read_text(encoding="utf-8")
    lic = license_text()

    codex_root = ROOT / "integrations" / "codex" / "plugins" / "aictx"
    claude_root = ROOT / "integrations" / "claude" / "plugins" / "aictx"

    write_json(codex_root / ".codex-plugin" / "plugin.json", codex_manifest(version))
    write_json(claude_root / ".claude-plugin" / "plugin.json", claude_manifest(version))
    write_text(codex_root / "skills" / "aictx" / "SKILL.md", skill_body(guidance))
    write_text(claude_root / "skills" / "aictx" / "SKILL.md", skill_body(guidance))
    write_text(codex_root / "LICENSE", lic)
    write_text(claude_root / "LICENSE", lic)

    write_text(codex_root / "README.md", f"""{NOTICE}

# AICTX for Codex

This plugin packages the `aictx` skill for Codex.

It is MCP-first when AICTX MCP tools are available and CLI-fallback otherwise.

## Contents

- `.codex-plugin/plugin.json`
- `skills/aictx/SKILL.md`

## Usage

Agents should call AICTX MCP tools when available:

- `aictx_resume`
- `aictx_finalize`
- `aictx_view`

If MCP tools are unavailable, agents must use the AICTX CLI fallback:

```bash
aictx resume --repo . --task "<task summary>" --json
aictx finalize --repo . --status success --summary "<what changed>" --json
```

## Distribution

This directory follows the Codex plugin format.

```bash
codex plugin marketplace add oldskultxo/aictx
```
""")
    write_text(claude_root / "README.md", f"""{NOTICE}

# AICTX for Claude Code

This plugin packages the `aictx` skill for Claude Code.

It is MCP-first when AICTX MCP tools are available and CLI-fallback otherwise.

## Contents

- `.claude-plugin/plugin.json`
- `skills/aictx/SKILL.md`

## Usage

Agents should call AICTX MCP tools when available:

- `aictx_resume`
- `aictx_finalize`
- `aictx_view`

If MCP tools are unavailable, agents must use the AICTX CLI fallback.

## Distribution

This directory follows the Claude Code plugin format.

```text
/plugin marketplace add oldskultxo/aictx
/plugin install aictx@oldskultxo
```

For official Claude listing, validate this directory with:

```bash
claude plugin validate integrations/claude/plugins/aictx
```
""")

    write_json(ROOT / ".agents" / "plugins" / "marketplace.json", {
        "name": "aictx",
        "interface": {"displayName": "AICTX"},
        "plugins": [{
            "name": "aictx",
            "source": {"source": "local", "path": "./integrations/codex/plugins/aictx"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Productivity",
        }],
    })
    write_json(ROOT / ".claude-plugin" / "marketplace.json", {
        "name": "aictx",
        "metadata": {"description": "AICTX repo-local operational continuity plugins for coding agents."},
        "owner": {"name": "Santi Santamaria"},
        "plugins": [{
            "name": "aictx",
            "source": "./integrations/claude/plugins/aictx",
            "description": "Use AICTX repo-local operational continuity in Claude Code.",
        }],
    })

    cursor_rule = f"""{NOTICE}

---
description: AICTX repo-local operational continuity
globs: **/*
alwaysApply: false
---

{guidance}
"""
    write_text(ROOT / "integrations" / "cursor" / "aictx.mdc", cursor_rule)
    write_text(ROOT / "integrations" / "cline" / "aictx.md", f"{NOTICE}\n\n{guidance}")
    write_text(ROOT / "integrations" / "generic" / "aictx-agent-instructions.md", f"{NOTICE}\n\n{guidance}")


if __name__ == "__main__":
    generate()
