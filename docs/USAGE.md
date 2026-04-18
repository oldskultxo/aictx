# Usage guide

## Normal workflow

The intended human workflow is still:

1. install once
2. init a repo
3. use your agent normally

## Product posture (important)

`aictx` should be read as:

- **primary**: repo-native runtime contract + execution discipline
- **secondary**: heuristic packet/memory/failure/graph acceleration

So the current value is strongest in reproducible runtime behavior and structured reuse, not in “deep intelligence” claims.

## Install

Public install:

```bash
pip install aictx
```

Then:

```bash
aictx install
```

Editable/development install:

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e . pytest build
```

## Global runtime setup

```bash
aictx install
```

Non-interactive:

```bash
aictx install --yes --workspace-root ~/projects
```

## Init

```bash
aictx init
```

Non-interactive:

```bash
aictx init --repo . --yes
```

Interactive init can persist a repo communication mode:

- `disabled`
- `caveman_lite`
- `caveman_full`
- `caveman_ultra`

## Advanced/internal commands

These are supported, but not the main product surface:

- `aictx boot`
- `aictx query`
- `aictx packet`
- `aictx global`
- `aictx execution prepare|finalize`
- `aictx internal run-execution`

## Runtime consistency checks

Both of these report effective communication policy and source-of-truth details:

```bash
aictx boot --repo .
aictx execution prepare --repo . --request "task" --agent-id demo --execution-id demo-1
```

Use this when validating that repo-local preferences and repo-local state are still aligned.

## Heuristic context behavior

`aictx packet` and `execution prepare` use deterministic/heuristic routing and ranking:

- task typing with confidence/evidence/ambiguity
- bounded graph expansion
- budgeted packet groups with selection reports

Use this for compact, explainable context assembly, not as a guarantee of superior understanding on every repo/task.

Quick check:

```bash
aictx packet --task "debug failing integration"
```

Look at:

- `task_type_resolution`
- `selection_report`
- `packet_strategy`

## Development workflow

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e . pytest build
make test
make smoke
make package-check
```

## Public-package validation

For release validation, also verify a clean wheel install:

```bash
python3 -m venv /tmp/aictx-release-venv
/tmp/aictx-release-venv/bin/pip install dist/aictx-<version>-py3-none-any.whl
/tmp/aictx-release-venv/bin/aictx --help
```

## Repo bootstrap status

`aictx boot --repo <path>` now reports repo bootstrap status explicitly:

- `initialized`
- `not_initialized`

That status is separate from communication defaults and helps distinguish missing runtime setup from normal operation.

## Day-2 value evidence (second run)

Run two similar executions and inspect telemetry:

```bash
aictx execution prepare --repo . --request "review middleware behavior" --agent-id demo --execution-id demo-1 > /tmp/prepared-1.json
aictx execution finalize --prepared /tmp/prepared-1.json --success --validated-learning --result-summary "first pass"

aictx execution prepare --repo . --request "review middleware behavior" --agent-id demo --execution-id demo-2 > /tmp/prepared-2.json
aictx execution finalize --prepared /tmp/prepared-2.json --success --result-summary "second pass"
```

Then inspect:

- `.ai_context_engine/metrics/weekly_summary.json`
- `value_evidence`
- `repeated_context_request`
- `task_memory_reused`
- `failure_memory_reused`

## Benchmark A/B/C

Run benchmark artifacts:

```bash
aictx benchmark run --suite benchmark_suite.json --arm A --out .ai_context_engine/metrics/benchmark_runs
aictx benchmark run --suite benchmark_suite.json --arm B --out .ai_context_engine/metrics/benchmark_runs
aictx benchmark run --suite benchmark_suite.json --arm C --out .ai_context_engine/metrics/benchmark_runs
aictx benchmark report --input .ai_context_engine/metrics/benchmark_runs --format json
```

This generates:

- `.ai_context_engine/metrics/benchmark_runs/benchmark_report.json`
- `.ai_context_engine/metrics/benchmark_runs/benchmark_report.md`

For full setup and gating rules, see `docs/BENCHMARK_QUICKSTART.md`.
