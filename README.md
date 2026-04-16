# aictx

Portable multi-LLM context engine bootstrapper and local runtime.

## Goal

`aictx` installs and initializes a stable `.ai_context_*` contract inside a repository so LLM agents can use contextual memory from the first minute after installation.

## Initial scope

- global install config under `~/.ai_context_engine/`
- repo init scaffold under `.ai_context_*`
- workspace registry for cross-project discovery
- deterministic scripting/runtime ownership for filesystem artifacts
- no LLM-dependent filesystem creation

## Planned commands

- `aictx install`
- `aictx init`
- `aictx boot`
- `aictx health`
- `aictx workspace add-root`
- `aictx workspace list`
- `aictx refresh-global`

## Current status

This repository contains the first distributable scaffold and a working CLI for:

- global install
- repo init
- workspace root registration
- workspace listing

## Development

```bash
python3 -m aictx --help
python3 -m aictx install --yes --workspace-root ~/projects
python3 -m aictx init --repo . --yes
```
