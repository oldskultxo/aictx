# Upgrade guide


## 3.0.0

3.0.0 introduces a breaking restructure of repo-local knowledge sources.

### Breaking changes

- `.aictx/memory/source/` is now the canonical editable source-knowledge layer.
- Legacy source locations like `common/`, `projects/`, root `index.json`, root `symptoms.json`, and root `protocol.md` are no longer the canonical layout.
- `aictx init` scaffolds source knowledge under `.aictx/memory/source/`.
- Only `.aictx/memory/source/` should be edited directly; `.aictx/boot`, `.aictx/store`, `.aictx/indexes`, `.aictx/metrics`, and similar runtime folders remain generated.
- `aictx` no longer ships knowledge mods / `.aictx/library`.
- `aictx` no longer ships global metrics aggregation or `--disable-global-metrics`.

### Migration notes

- Existing legacy source files are migrated into `.aictx/memory/source/` by repo scaffolding/migration flows.
- Queries, bootstrap generation, and project knowledge ingestion now read from `.aictx/memory/source/`.
- `aictx internal new-note` now writes into `.aictx/memory/source/projects/<repo>/...` by default.
- Remove any legacy `.aictx/library/` and `.aictx/global_metrics/` expectations from local automation or docs.

No release publishing is implied by this metadata update.

## 2.2.0

2.2.0 is additive and keeps the 2.0 safety contract.

### Added

- structured execution signal capture with provenance
- richer explainable strategy ranking
- repo-local failure memory with resolution linkage
- deterministic repo-area memory
- `agent_summary` and `agent_summary_text` in finalize output; current runtime instructions require agents to append `agent_summary_text` to final user responses
- extended `report real-usage` capture, failure, area, and hygiene fields

No release publishing is implied by this metadata update.

## 2.0.0

2.0.0 changes AICTX defaults toward non-destructive setup.

### Breaking changes

- `aictx install` no longer modifies global Codex configuration by default.
- Use `aictx install --install-codex-global` to update `~/.codex/AGENTS.override.md` and `~/.codex/config.toml`.
- `aictx init` now consolidates repo-local Codex guidance into `AGENTS.md`; it no longer creates `AGENTS.override.md` for new repos.
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
