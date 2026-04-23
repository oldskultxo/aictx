# Demo

This demo shows two real executions and one real reuse.

## 1. Install and initialize

```bash
pip install aictx
aictx install
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

The finalize output includes `agent_summary_text`; agents must append that summary to the final user response.

Inspect artifacts:

```bash
cat .ai_context_engine/metrics/execution_logs.jsonl
cat .ai_context_engine/metrics/execution_feedback.jsonl
cat .ai_context_engine/strategy_memory/strategies.jsonl
```

## 3. Second execution

```bash
aictx internal execution prepare \
  --repo . \
  --request "review middleware behavior again" \
  --agent-id demo \
  --execution-id demo-2 > prepared-2.json
cat prepared-2.json
```

If the first run produced a reusable successful strategy, `prepared-2.json` includes `execution_hint`.

Finalize it:

```bash
aictx internal execution finalize \
  --prepared prepared-2.json \
  --success \
  --result-summary "second run"
```

## 4. Wrapped execution helper

For wrapped automations, `run-execution` performs prepare + command + finalize. Without `--json`, it prints command output plus the AICTX summary:

```bash
aictx internal run-execution \
  --repo . \
  --request "run tests" \
  --agent-id demo \
  --validated-learning \
  -- python -m pytest -q
```

## 5. Report real usage

```bash
aictx report real-usage --repo .
```

This demo proves:
- run 1 records real execution
- run 2 can reuse a real prior strategy
- file tracking only appears when explicitly provided
- output comes from stored logs, feedback and strategy memory only


## 6. Cleanup

```bash
aictx clean --repo .
```

This removes only AICTX-managed repo content. To remove AICTX globally across registered repos and global config:

```bash
aictx uninstall
```
