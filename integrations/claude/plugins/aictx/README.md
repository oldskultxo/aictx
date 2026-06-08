<!-- Generated from integrations/templates/agent-guidance.md. Do not edit directly. -->

# AICTX for Claude Code

This plugin packages AICTX repo-local continuity guidance for Claude Code.

Default model:

```text
aictx install
aictx init
then let Claude Code work
```

Claude Code should resume repo-local continuity before substantial work and finalize factual evidence after work.

## Contents

- `.claude-plugin/plugin.json`
- `skills/aictx/SKILL.md`

## Lifecycle

Prefer MCP tools when available:

- `aictx_resume`
- `aictx_finalize`
- `aictx_view`

If MCP tools are unavailable, use the AICTX CLI fallback:

```bash
aictx resume --repo . --task "<task summary>" --json
aictx finalize --repo . --status success --summary "<what changed>" --json
```

Use `--status failure` when work failed or remains blocked.

## Distribution

```text
/plugin marketplace add oldskultxo/aictx
/plugin install aictx@oldskultxo
```

For official Claude listing, validate this directory with:

```bash
claude plugin validate integrations/claude/plugins/aictx
```
