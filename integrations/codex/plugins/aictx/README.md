<!-- Generated from integrations/templates/agent-guidance.md. Do not edit directly. -->

# AICTX for Codex

This plugin packages AICTX repo-local continuity guidance for Codex.

Default model:

```text
aictx install
aictx init
then let Codex work
```

Codex should resume repo-local continuity before substantial work and finalize factual evidence after work.

## Contents

- `.codex-plugin/plugin.json`
- `skills/aictx/SKILL.md`

## Lifecycle

Prefer MCP tools when available:

- `aictx_resume`
- `aictx_finalize`
- `aictx_view`

CLI fallback:

```bash
aictx resume --repo . --task "<task summary>" --json
aictx finalize --repo . --status success --summary "<what changed>" --json
```

Use `--status failure` when work failed or remains blocked.

## Distribution

```bash
codex plugin marketplace add oldskultxo/aictx
```
