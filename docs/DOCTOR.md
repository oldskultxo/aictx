# Doctor diagnostics

`aictx doctor` is a read-only diagnostic command for support and release readiness.

```bash
aictx doctor --repo . --json
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
- lifecycle smoke compatibility;
- RepoMap provider/index/query/refresh status;
- capture quality;
- contract compliance health;
- stale/duplicate memory;
- Makefile/CI compatibility.

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

`make ci` remains the canonical release-readiness gate. Doctor can be used alongside it for support and CI diagnostics, but it should stay lightweight and read-only.
