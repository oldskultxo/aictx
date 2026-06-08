<!-- Generated from integrations/templates/agent-guidance.md. Do not edit directly. -->

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
