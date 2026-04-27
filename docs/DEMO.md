# Demo

This demo shows AICTX as an operational continuity runtime.

---

## Install and initialize

```bash
pip install aictx
aictx install
aictx init --yes --no-register
```

---

## Show Work State continuity

```bash
aictx task start "Fix token refresh loop" --json
aictx task update --json   --json-patch '{"current_hypothesis":"refresh replay happens before persisted token update","active_files":["src/api/client.ts"],"next_action":"inspect interceptor ordering","recommended_commands":["pytest -q tests/test_auth.py"]}'
aictx next
```

---

## Show RepoMap

```bash
pip install "aictx[repomap]"
aictx install --with-repomap --yes
aictx init --yes --no-register
aictx map status
aictx map query "work state"
```

---

## Show failure capture

```bash
aictx internal run-execution   --repo .   --request "run typecheck"   --agent-id demo   --json   -- python -c "import sys; print('src/app.ts(4,7): error TS2322: Type mismatch', file=sys.stderr); sys.exit(1)"
```

Inspect:

```bash
cat .aictx/failure_memory/failure_patterns.jsonl
aictx report real-usage
```
