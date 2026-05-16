---
title: "AICTX Doctor Diagnostics"
description: "Use `aictx doctor` to inspect installation health, release readiness, portability state, and repo-local continuity diagnostics."
---

# Doctor diagnostics

`aictx doctor` is a read-only diagnostic command. Default mode is a general support check for normal user repositories; `--release-readiness` adds strict checks for the aictx release gate.

```bash
aictx doctor --repo . --json
# strict aictx release checks
aictx doctor --repo . --release-readiness --json
```

It is a human/CI diagnostic surface. It is not part of normal agent startup and should not replace the normal lifecycle:

```text
resume -> work -> finalize
```

---

## JSON shape

```json
{
  "status": "ok|warning|error",
  "mode": "general|release_readiness",
  "checks": [],
  "recommended_actions": []
}
```

Each check includes a stable name, status, summary, and details object.

---

## Checks

Doctor can inspect:

- CLI version;
- repo initialization;
- runner files;
- RepoMap provider/index/query/refresh status;
- capture quality;
- contract compliance health;
- stale/duplicate memory.

When `--release-readiness` is set, Doctor also enforces stricter aictx release checks:

- lifecycle smoke compatibility from `Makefile`;
- Makefile/CI compatibility and `make ci` delegation.

Doctor does not modify repo state.

---

## RepoMap status

Doctor uses the v6.3 RepoMap status model:

```text
provider_available
index_available
query_available
refresh_available
last_refresh_status
files_indexed
symbols_indexed
```

This makes support output clear when a provider is unavailable but an existing index is still queryable.

---

## Release readiness

`make ci` remains the canonical release-readiness gate. Use:

```bash
aictx doctor --repo . --release-readiness --json
```

for aictx release diagnostics. Plain `aictx doctor --repo . --json` stays suitable for user repositories that do not have this project’s `Makefile`/CI layout.
