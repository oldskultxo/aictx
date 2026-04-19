# Demo

This demo shows a real, reproducible flow using the current runtime.

It does not assume performance gains and it does not fabricate results.

## 1. Create a demo repo

```bash
mkdir -p /tmp/aictx-demo
cd /tmp/aictx-demo
python3 -m venv .venv
.venv/bin/pip install aictx
.venv/bin/aictx install
.venv/bin/aictx init --repo . --yes --no-register
```

## 2. Ask for guidance before work

```bash
.venv/bin/aictx suggest --repo .
.venv/bin/aictx reuse --repo .
.venv/bin/aictx reflect --repo .
```

On a fresh repo, these should return empty JSON structures rather than fake advice.

## 3. Run one execution through the middleware

```bash
.venv/bin/aictx execution prepare \
  --repo . \
  --request "review middleware behavior" \
  --agent-id demo \
  --execution-id demo-1 > /tmp/demo-prepared.json

.venv/bin/aictx execution finalize \
  --prepared /tmp/demo-prepared.json \
  --success \
  --validated-learning \
  --result-summary "first demo run completed"
```

## 4. Inspect real artifacts

```bash
cat .ai_context_engine/metrics/execution_logs.jsonl
cat .ai_context_engine/metrics/execution_feedback.jsonl
cat .ai_context_engine/strategy_memory/strategies.jsonl
```

At this point you should see:

- one real execution log
- one feedback row
- one strategy row if the execution was successful and validated for strategy persistence

## 5. Run a similar task again

```bash
.venv/bin/aictx execution prepare \
  --repo . \
  --request "review middleware behavior again" \
  --agent-id demo \
  --execution-id demo-2 > /tmp/demo-prepared-2.json

cat /tmp/demo-prepared-2.json
```

If strategy memory exists for the resolved task type, the prepared payload should include:

- `execution_hint`
- `execution_observation.used_strategy`

## 6. Finalize the second run

```bash
.venv/bin/aictx execution finalize \
  --prepared /tmp/demo-prepared-2.json \
  --success \
  --result-summary "second demo run completed"
```

## 7. Report real usage

```bash
.venv/bin/aictx report real-usage --repo .
```

This returns aggregated real data only, such as:

- total executions
- average execution time
- average files opened
- average reopened files
- strategy usage count
- packet usage count
- redundant exploration count

## What to highlight in a live demo

- empty outputs are acceptable when there is no history
- strategy reuse appears only after a real successful prior run
- report output is based on stored logs and feedback, not on synthetic benchmarks
- the runtime is meant to improve execution discipline and reuse, not to claim unmeasured performance gains
