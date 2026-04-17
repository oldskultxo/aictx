# 5-minute demo

## Goal

Show the real happy path without pretending more than the product does today.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -e .
```

## Demo flow

```bash
mkdir -p /tmp/aictx-demo-repo
.venv/bin/aictx init --repo /tmp/aictx-demo-repo --yes --no-register
.venv/bin/aictx boot --repo /tmp/aictx-demo-repo
.venv/bin/aictx packet --task "debug failing integration"
.venv/bin/aictx execution prepare \
  --repo /tmp/aictx-demo-repo \
  --request "review middleware behavior" \
  --agent-id demo-agent \
  --execution-id demo-1 > /tmp/aictx-demo-repo/prepared.json
.venv/bin/aictx execution finalize \
  --prepared /tmp/aictx-demo-repo/prepared.json \
  --success \
  --validated-learning \
  --result-summary "demo completed"
```

## What to point out

- `init` provisions repo-local runtime files and runner integration files.
- `boot` now reports effective preferences plus runtime consistency checks.
- `packet` gives compact heuristic context for a task without pretending to solve the task.
- `execution prepare/finalize` provides the middleware contract used by wrappers.

## Day-2 value demo

After the first run, repeat a similar task:

```bash
.venv/bin/aictx execution prepare \
  --repo /tmp/aictx-demo-repo \
  --request "review middleware behavior again and reuse prior findings" \
  --agent-id demo-agent \
  --execution-id demo-2 > /tmp/aictx-demo-repo/prepared-2.json

.venv/bin/aictx execution finalize \
  --prepared /tmp/aictx-demo-repo/prepared-2.json \
  --success \
  --validated-learning \
  --result-summary "second demo completed"
```

Then inspect:

- `.ai_context_engine/metrics/weekly_summary.json`
- `value_evidence`
- `task_memory_reused`
- `repeated_context_request`

The point is not “magic intelligence”.
The point is that the second run should enter with more reusable repo-local context and better execution discipline.

## Honest framing

- this is still a `0.x` product
- native behavior still depends on the runner honoring instructions/hooks
- advanced/internal commands exist and are supported, but the sellable surface remains `install + init`
