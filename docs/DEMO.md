# Demo

This demo shows one recorded execution and one later reuse.

## 1. Install and initialize

```bash
pip install aictx
aictx install --yes
aictx init --repo . --yes --no-register
```

## 2. First execution

```bash
aictx internal execution prepare \
  --repo . \
  --request "review middleware behavior" \
  --agent-id demo \
  --execution-id demo-1 \
  --files-opened src/a.py src/b.py \
  --files-reopened src/a.py > prepared-1.json

aictx internal execution finalize \
  --prepared prepared-1.json \
  --success \
  --validated-learning \
  --files-opened src/a.py src/b.py \
  --files-reopened src/a.py \
  --result-summary "first run"
```

What to inspect:

```bash
cat .aictx/metrics/execution_logs.jsonl
cat .aictx/metrics/execution_feedback.jsonl
cat .aictx/strategy_memory/strategies.jsonl
cat .aictx/continuity/last_execution_summary.md
```

## 3. Second execution

```bash
aictx internal execution prepare \
  --repo . \
  --request "review middleware behavior again" \
  --agent-id demo \
  --execution-id demo-2 > prepared-2.json
```

If the first run produced a reusable successful strategy, `prepared-2.json` can include `execution_hint`.

Finalize it:

```bash
aictx internal execution finalize \
  --prepared prepared-2.json \
  --success \
  --result-summary "second run"
```

## 4. Wrapped execution helper

For wrapped automations, `run-execution` performs prepare + command + finalize.
Without `--json`, it prints command output plus the startup banner when required and the AICTX summary.

```bash
aictx internal run-execution \
  --repo . \
  --request "run tests" \
  --agent-id demo \
  --validated-learning \
  -- python -m pytest -q
```

## 5. Continuity inspection

```bash
aictx next --repo .
aictx reuse --repo .
aictx report real-usage --repo .
```

This demo proves:

- run 1 records real execution
- run 2 can reuse a real prior strategy
- prepare can classify provisionally, while finalize can classify from observed evidence
- output comes from stored logs, feedback, continuity, and strategy memory only

## 6. Cleanup

```bash
aictx clean --repo .
```

To remove AICTX global state and registered repo content too:

```bash
aictx uninstall
```
