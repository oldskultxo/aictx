<!-- AICTX:START -->
# AICTX Claude integration

This repository is initialized with `aictx`.

- Use repo-local execution history and strategy memory for non-trivial tasks.
- Claude project hooks may inject runtime guidance automatically.
- Pre-tool enforcement may block direct edits to generated runtime artifacts and legacy parallel memory paths.
- Treat `aictx internal run-execution` as the preferred wrapped execution entrypoint when available.

## aictx usage rules

- Before opening more than 3 files: run `aictx suggest --repo .`
- If you reopen the same file: run `aictx reflect --repo .`
- If the task seems similar to a previous one: run `aictx reuse --repo .`
- If you are unsure about the next step: run `aictx suggest --repo .`
<!-- AICTX:END -->
