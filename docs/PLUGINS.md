---
title: "Plugin distribution artifacts"
description: "AICTX ships plugin distribution artifacts for Claude Code and Codex. The plugins package the same repo-local operational continuity workflow used by AICTX instructions and MCP."
---

# AICTX Agent Plugins

## Locations

- Codex plugin: `integrations/codex/plugins/aictx/`
- Claude Code plugin: `integrations/claude/plugins/aictx/`
- Codex marketplace: `.agents/plugins/marketplace.json`
- Claude marketplace: `.claude-plugin/marketplace.json`
- Shared guidance template: `integrations/templates/agent-guidance.md`
- Generated Cursor rule: `integrations/cursor/aictx.mdc`
- Generated Cline instructions: `integrations/cline/aictx.md`
- Generated generic instructions: `integrations/generic/aictx-agent-instructions.md`

## MCP-first, CLI-fallback model

The plugins are MCP-first when AICTX MCP tools are available. Compatible agents should prefer tools such as `aictx_resume`, `aictx_finalize`, and `aictx_view`.

When MCP tools are unavailable, agents fall back to the AICTX CLI:

```bash
aictx resume --repo . --task "<task summary>" --json
aictx finalize --repo . --status success --summary "<what changed>" --json
```

Use `--status failure` when work failed or remains blocked.

## Marketplace commands

Codex local marketplace:

```bash
codex plugin marketplace add oldskultxo/aictx
```

Claude Code local marketplace:

```text
/plugin marketplace add oldskultxo/aictx
/plugin install aictx@oldskultxo
```

For Claude listing validation:

```bash
claude plugin validate integrations/claude/plugins/aictx
```

## Generated guidance

Run the generator after editing `integrations/templates/agent-guidance.md`:

```bash
python scripts/generate-agent-integrations.py
```

The generator reads `pyproject.toml`, `LICENSE`, and the shared guidance template, then regenerates plugin manifests, skills, READMEs, marketplace files, Cursor/Cline/generic guidance, and plugin LICENSE files. Generated files include a do-not-edit notice.

## Install/init relationship

Plugins do not replace `aictx install` or `aictx init`. Those commands prepare AICTX runtime state and managed MCP configuration. Plugin artifacts only package guidance and discovery for compatible agents.

Cleanup and uninstall remain handled by AICTX managed config where applicable: use `aictx clean` for repo-local managed artifacts and `aictx uninstall` for global managed AICTX state.
