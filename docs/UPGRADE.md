# Upgrade guide

## 2.0.0

2.0.0 changes AICTX defaults toward non-destructive setup.

### Breaking changes

- `aictx install` no longer modifies global Codex configuration by default.
- Use `aictx install --install-codex-global` to update `~/.codex/AGENTS.override.md` and `~/.codex/config.toml`.
- `aictx init` no longer performs legacy ad hoc migration/deletion of old memory directories.

### Re-running init

It is safe to re-run:

```bash
aictx init
```

Existing execution logs, feedback, and strategy memory are preserved.
Claude project settings are merged instead of overwritten.

### Dry run

Use:

```bash
aictx install --dry-run
```

This prints planned install writes without mutating files.

### Cleanup compatibility

`aictx clean` and `aictx uninstall` remove AICTX-managed blocks, hooks, and global state while preserving unrelated user config.
