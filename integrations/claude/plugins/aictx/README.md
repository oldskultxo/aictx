<!-- Generated from integrations/templates/agent-guidance.md. Do not edit directly. -->

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
