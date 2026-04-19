# Demo

This demo shows two real executions.

No fake improvements.

## 1. Install and initialize

```bash
pip install aictx
aictx install
aictx init --repo . --yes --no-register
```

## 2. First execution

Prepare and finalize one execution.

```bash
aictx internal execution prepare   --repo .   --request "review middleware behavior"   --agent-id demo   --execution-id demo-1 > prepared-1.json

aictx internal execution finalize   --prepared prepared-1.json   --success   --validated-learning   --result-summary "first run"
```

Inspect artifacts:

```bash
cat .ai_context_engine/metrics/execution_logs.jsonl
cat .ai_context_engine/strategy_memory/strategies.jsonl
```

At this point there is no prior strategy reuse. You only have the first real execution recorded.

## 3. Second execution

Run a similar task.

```bash
aictx internal execution prepare   --repo .   --request "review middleware behavior again"   --agent-id demo   --execution-id demo-2 > prepared-2.json
```

Inspect the prepared payload:

```bash
cat prepared-2.json
```

If the first run produced a successful reusable strategy, this second prepared payload includes `execution_hint`.

Finalize it:

```bash
aictx internal execution finalize   --prepared prepared-2.json   --success   --result-summary "second run"
```

## 4. Report real usage

```bash
aictx report real-usage --repo .
```

What this demo proves:
- run 1 records real execution
- run 2 can reuse a real prior strategy
- output comes from stored logs and strategy memory only
