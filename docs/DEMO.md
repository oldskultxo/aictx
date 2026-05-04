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
aictx task update --json --json-patch '{"current_hypothesis":"refresh replay happens before persisted token update","active_files":["src/api/client.ts"],"next_action":"inspect interceptor ordering","recommended_commands":["pytest -q tests/test_auth.py"]}'
aictx next
```

---

## Show execution contract and compliance

Normal supported agent startup should use one continuity command:

```bash
aictx resume --repo . --task "fix parser test" --json | python3 -m json.tool
```

Look for the compact operational route in the JSON:

```text
execution_contract.first_action
execution_contract.edit_scope
execution_contract.test_command
execution_contract.finalize_command
contract_checks
```

After an execution is finalized with observable files/commands/tests, the final summary can include:

```text
Contract: followed.
```

or a compact partial/violated/not-evaluated line.

Inspect contract compliance history and aggregates:

```bash
cat .aictx/metrics/contract_compliance.jsonl 2>/dev/null || true
aictx report real-usage
```

Run another resume and look for the compact previous-contract signal:

```bash
aictx resume --repo . --task "next parser task" --json | python3 -m json.tool
```

The next resume may include:

```text
previous_contract_result
```

and the Markdown capsule may include:

```text
Previous contract: followed.
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
aictx internal run-execution --repo . --request "run typecheck" --agent-id demo --json -- python -c "import sys; print('src/app.ts(4,7): error TS2322: Type mismatch', file=sys.stderr); sys.exit(1)"
```

Inspect:

```bash
cat .aictx/failure_memory/failure_patterns.jsonl
aictx report real-usage
```
