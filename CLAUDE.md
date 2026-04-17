<!-- AICTX:START -->
# AICTX Claude integration

This repository is initialized with `aictx`.

- Prefer `.ai_context_engine/` as the first memory/bootstrap layer.
- Use packet-oriented context for non-trivial tasks.
- Claude project hooks may inject bootstrap and packet summaries automatically.
- Pre-tool enforcement may block direct edits to generated runtime artifacts and legacy parallel memory paths.
- Treat `aictx internal run-execution` as the preferred wrapped execution entrypoint when available.
<!-- AICTX:END -->
