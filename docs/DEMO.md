# Demo

This demo shows AICTX as a repo-local continuity runtime for coding agents.

It is not a synthetic benchmark whose only goal is to minimize total token count. The demo is designed to make continuity visible, repeatable, and inspectable: Work State, resume capsules, execution contracts, contract compliance, RepoMap hints, Failure Memory, and real usage telemetry.

Current documented target: AICTX `5.3.x`.

---

## What this demo is meant to prove

AICTX should help a coding agent start with better operational context instead of repeatedly rediscovering the repository from scratch.

The expected signal is:

- the agent gets a compact startup brief through `aictx resume`;
- the active task state survives across sessions;
- the next action, active files, known risks, and recommended commands are explicit;
- prior failures can be reused as warnings;
- RepoMap can point the agent toward relevant files and symbols;
- execution contracts make the expected route inspectable;
- finalize stores factual continuity for the next run;
- real usage reports provide evidence instead of relying on vibes.

The demo should be evaluated as a continuity and reliability demo first, and as a token-efficiency demo second.

---

## What this demo does not prove

This demo does not claim that AICTX always reduces total tokens.

In the measured demo runs, AICTX produced useful continuity signals, but total token usage could increase when the agent spent extra context on runtime orientation, generated artifacts, instrumentation, or benchmark-specific prompt text.

That is an important result, not a failure:

```text
AICTX is not primarily a raw token compressor.
AICTX is a continuity layer that makes state, next actions, failures, and execution evidence reusable across coding-agent sessions.
```

The right question is not only “did total tokens go down?” but also:

- did the agent reach the first useful edit faster?
- did it touch fewer irrelevant files?
- did it repeat fewer failed paths?
- did it preserve active task state correctly?
- did the next session know where to continue?
- did it follow the expected execution contract?
- did the final summary become useful input for future work?

---

## Demo conclusions from the current analysis

The current demo analysis showed a consistent but nuanced signal.

### Positive signal

AICTX improved the first session in practical terms:

- less time spent orienting;
- fewer exploratory commands;
- roughly flat uncached input despite higher total context in the first measured run;
- clearer initial route through the repository;
- more explicit next actions and test expectations.

AICTX also made the second session more focused:

- fewer files edited;
- better preservation of task intent;
- less risk of drifting into unrelated cleanup;
- clearer reuse of execution evidence from the previous run.

### Caveat

Overall token and uncached-token usage may still increase if the agent consumes too much AICTX runtime detail, benchmark schema, or instrumentation text.

This is especially visible when the user prompt passed to the agent contains more than the task goal: reporting requirements, metrics instructions, JSON schema, demo instrumentation, or analysis rules.

The demo therefore separates the task goal from benchmark instrumentation.

---

## Measured demo data

The following tables summarize the measured demo run stored in the external demo repository:

- `https://github.com/oldskultxo/aictx-demo-taskflow/tree/main/.demo_metrics`

Within that external repo, the measured artifacts live under:

```text
.demo_metrics/with_aictx/
.demo_metrics/without_aictx/
```

The comparison uses the same model family recorded by Codex for the measured sessions: `gpt-5.4`.

Important interpretation rule:

```text
The data below is evidence from one controlled demo pair.
It is useful as a directional product signal, not as a universal benchmark claim.
```

### Operational footprint

| Session | Metric | Without AICTX | With AICTX | Delta with AICTX |
|---|---:|---:|---:|---:|
| Session 1 | Files explored | 9 | 8 | -1 (-11.1%) |
| Session 1 | Files edited | 6 | 5 | -1 (-16.7%) |
| Session 1 | Commands run | 11 | 11 | 0 (0.0%) |
| Session 1 | Test commands | 2 | 2 | 0 (0.0%) |
| Session 1 | Time to complete | 1'43'' | 1'34'' | -9s (-8.7%) |
| Session 2 | Files explored | 10 | 5 | -5 (-50.0%) |
| Session 2 | Files edited | 3 | 1 | -2 (-66.7%) |
| Session 2 | Commands run | 15 | 8 | -7 (-46.7%) |
| Session 2 | Test commands | 4 | 1 | -3 (-75.0%) |
| Session 2 | Exploration steps before first edit | 15 | 6 | -9 (-60.0%) |
| Session 2 | Time to complete | 1'59'' | 1'12'' | -47s (-39.5%) |

Session 1 shows a modest improvement, not a dramatic one. That is expected: the first run is where AICTX itself has to establish continuity, and the agent still needs to understand the task.

Session 2 is the stronger signal. The AICTX run explored half as many files, edited one third as many files, ran fewer commands, reached the relevant parser test directly, and finished faster.

### First relevant file and first edit

| Session | Run | First relevant file | First edited file | Interpretation |
|---|---|---|---|---|
| Session 2 | Without AICTX | `README.md` | `src/taskflow/parser.py` | The agent started from broader rediscovery and then moved into implementation. |
| Session 2 | With AICTX | `tests/test_parser.py` | `tests/test_parser.py` | The agent started directly at the validation surface for the pending parser edge cases. |

This is the most important qualitative result of the demo. AICTX did not merely reduce a count; it changed where the second session began.

### Token usage, session totals

These token numbers come from Codex `token_count` events captured in the session JSONL and summarized in the external `.demo_metrics` dataset linked above.

| Session | Run | Input tokens | Cached input | Uncached input | Output tokens | Total tokens |
|---|---|---:|---:|---:|---:|---:|
| Session 1 | Without AICTX | 192,685 | 156,672 | 36,013 | 3,958 | 196,643 |
| Session 1 | With AICTX | 243,972 | 207,360 | 36,612 | 3,523 | 247,495 |
| Session 2 | Without AICTX | 290,222 | 257,152 | 33,070 | 5,935 | 296,157 |
| Session 2 | With AICTX | 205,772 | 173,568 | 32,204 | 2,698 | 208,470 |
| Combined | Without AICTX | 482,907 | 413,824 | 69,083 | 9,893 | 492,800 |
| Combined | With AICTX | 449,744 | 380,928 | 68,816 | 6,221 | 455,965 |

### Token deltas

| Scope | Metric | Delta with AICTX | Interpretation |
|---|---:|---:|---|
| Session 1 | Total tokens | +50,852 (+25.9%) | First run spent more total context with AICTX. |
| Session 1 | Uncached input | +599 (+1.7%) | Uncached input was almost flat despite higher total/cached context. |
| Session 1 | Output tokens | -435 (-11.0%) | The AICTX run produced less output. |
| Session 2 | Total tokens | -87,687 (-29.6%) | The continuity run was materially cheaper in total tokens. |
| Session 2 | Uncached input | -866 (-2.6%) | Uncached input improved slightly. |
| Session 2 | Output tokens | -3,237 (-54.5%) | The second AICTX run required much less generated output. |
| Combined | Total tokens | -36,835 (-7.5%) | Across both sessions, AICTX used fewer total tokens. |
| Combined | Uncached input | -267 (-0.4%) | Uncached input was essentially flat overall. |
| Combined | Output tokens | -3,672 (-37.1%) | The clearest token reduction was in output verbosity. |

The token data should be read carefully. The first AICTX session used more total tokens, mostly because the agent had more runtime and continuity context available. The second AICTX session was substantially more focused. Across the two-session demo, AICTX reduced total tokens by about 7.5%, but the stronger claim is not raw token compression. The stronger claim is better continuity: fewer files explored, fewer files edited, fewer commands, and a sharper second-session starting point.

### Cost reference from recorded reports

The demo metrics also include a standard API-style cost reference calculated from the recorded token usage.

| Session | Run | Credits, standard | API USD reference |
|---|---|---:|---:|
| Session 1 | Without AICTX | 14.5063 | $0.5803 |
| Session 1 | With AICTX | 17.8654 | $0.7146 |
| Session 2 | Without AICTX | 21.9717 | $0.8789 |
| Session 2 | With AICTX | 14.9573 | $0.5983 |
| Combined | Without AICTX | 36.4780 | $1.4591 |
| Combined | With AICTX | 32.8227 | $1.3129 |

This cost table is only a reference derived from the script’s mapped rates. It should not be presented as exact ChatGPT/Codex billing behavior.

### Behavioral summary

| Area | Without AICTX | With AICTX | Demo signal |
|---|---|---|---|
| Session 1 orientation | Broad repo search and direct inspection | AICTX resume first, then targeted inspection | AICTX gives an explicit continuity entry point but still has first-run setup overhead. |
| Session 2 orientation | Starts from README / broad discovery | Starts from `tests/test_parser.py` | AICTX preserves the pending work surface. |
| Edit scope | Session 2 edits implementation and tests | Session 2 edits only parser tests | AICTX produced a narrower second-session edit. |
| Command volume | Session 2 runs 15 commands | Session 2 runs 8 commands | AICTX reduced rediscovery and verification churn. |
| Token profile | Higher Session 2 total and output tokens | Lower Session 2 total and output tokens | Continuity helps most after state exists. |

### Practical conclusion from the measured demo

The measured demo supports this narrower, defensible claim:

```text
AICTX improves second-session continuity.
In the measured two-session task, the AICTX run resumed from a more relevant file,
explored fewer files, edited fewer files, ran fewer commands, completed faster,
and used fewer total tokens across the full two-session comparison.
```

It does not support the broader claim that AICTX always reduces token usage on every run.

The better product framing is:

```text
AICTX is not a generic token compressor.
AICTX is a repo-local continuity layer that can reduce rediscovery,
narrow the agent's working set, and make later sessions more focused.
```

---

## Important demo protocol

To keep the demo fair and avoid contaminating the repository, follow these rules.

### Keep demo metrics outside the target repo

Do not run the demo with `.demo_metrics` present inside the target repository under test.

Prompt files, raw metrics, comparison outputs, and benchmark notes should live outside the target repo.

For the measured example documented here, those metrics were kept in a separate external demo repository:

- `https://github.com/oldskultxo/aictx-demo-taskflow/tree/main/.demo_metrics`

Recommended pattern:

```text
/tmp/aictx-demo-runs/
  baseline/
  with-aictx/
  metrics/
  prompts/
```

The repository should contain only the project under test and AICTX runtime artifacts generated by normal AICTX usage.

### Compare matched environments only

Only compare runs when the model and execution environment are matched.

For example, do not compare a baseline run from one model against an AICTX run from another model. If the demo is run with `gpt-5.4`, both baseline and AICTX runs should use `gpt-5.4`.

### Use `--task` for normal agent startup

Normal supported startup should use `--task`, and the value should contain only the task goal:

```bash
aictx resume --repo . --task "fix parser test" --json | python3 -m json.tool
```

Do not pass benchmark instructions, metrics schemas, reporting rules, or final-answer requirements as the task goal.

Bad demo input:

```bash
aictx resume --repo . --request "Fix parser test. Also collect these metrics, follow this benchmark schema, output this report..." --json
```

Good demo input:

```bash
aictx resume --repo . --task "fix parser test" --json
```

`--request` remains useful for legacy/raw compatibility and wrapped execution flows, but demo instrumentation should not be mixed into the agent-facing task.

If needed, future AICTX behavior should add an explicit sanitizer or warning when `--request` appears to contain benchmark/reporting instructions instead of just the work goal.

---

## Global memory vs latest execution

A key architectural conclusion from the demo analysis:

```text
The latest execution must update global repo memory.
It must not replace global repo memory.
```

AICTX should not become a tool that only remembers the last run.

The latest execution summary is valuable because it captures what just happened, but it should be treated as one event in a larger continuity model.

The durable continuity model should preserve:

- architecture memory;
- repo conventions;
- explicit decisions;
- failure memory;
- strategy memory;
- task history;
- user/project preferences;
- relevant files and entry points;
- latest execution summary.

The right mental model is:

```text
Repo global knowledge
  + latest execution event
  + task-specific Work State
  + observed failures
  + successful strategies
  + structural RepoMap hints
  = useful startup continuity
```

The latest execution should influence the next session strongly, but it must not erase older decisions, known failures, conventions, or architectural context.

---

## Install and initialize

From inside the target repository:

```bash
pip install aictx
aictx install
aictx init
```

Optional version check:

```bash
aictx --version
```

Explicit initialization form:

```bash
aictx init --repo .
```

For a demo script that should not register extra local state, you can use:

```bash
aictx init --repo . --yes --no-register
```

After initialization, the normal product experience should remain:

```text
install -> init -> use your coding agent
```

The user should not need to manually drive many AICTX commands during normal development.

---

## Demo flow

### 1. Show startup continuity

Run:

```bash
aictx resume --repo . --task "fix parser test" --json | python3 -m json.tool
```

Look for:

```text
startup_banner_text
capsule
execution_contract
contract_checks
recommended_starting_points
previous_contract_result
```

The important product point is that the agent receives one operational brief instead of having to inspect all AICTX internals manually.

---

### 2. Create visible Work State

Start a task:

```bash
aictx task start "Fix token refresh loop" --json
```

Update it with operational details:

```bash
aictx task update --json --json-patch '{"current_hypothesis":"refresh replay happens before persisted token update","active_files":["src/api/client.ts"],"next_action":"inspect interceptor ordering","recommended_commands":["pytest -q tests/test_auth.py"]}'
```

Inspect continuity:

```bash
aictx next
```

Then resume:

```bash
aictx resume --repo . --task "continue token refresh work" --json | python3 -m json.tool
```

Expected result:

- the active task is visible;
- the current hypothesis is preserved;
- the next action is explicit;
- active files are suggested;
- recommended commands are available to the agent.

---

### 3. Show execution contract and compliance

Normal supported agent startup should use one continuity command:

```bash
aictx resume --repo . --task "fix parser test" --json | python3 -m json.tool
```

Look for the compact operational route:

```text
execution_contract.first_action
execution_contract.edit_scope
execution_contract.test_command
execution_contract.finalize_command
contract_checks
```

After an execution is finalized with observable files, commands, and tests, the final summary can include:

```text
Contract: followed.
```

or a compact partial, violated, or not-evaluated line.

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

### 4. Show RepoMap

Install with RepoMap support:

```bash
pip install "aictx[repomap]"
aictx install --with-repomap --yes
aictx init --repo . --yes --no-register
```

Inspect status:

```bash
aictx map status
```

Query structural hints:

```bash
aictx map query "work state"
aictx map query "startup banner"
aictx map query "contract compliance"
```

The demo point is not that RepoMap replaces normal code search. The point is that it gives the agent a structural starting point before it spends tokens rediscovering the repo.

---

### 5. Show failure capture

Simulate a failed execution:

```bash
aictx internal run-execution --repo . --request "run typecheck" --agent-id demo --json -- python -c "import sys; print('src/app.ts(4,7): error TS2322: Type mismatch', file=sys.stderr); sys.exit(1)"
```

Inspect captured failure memory:

```bash
cat .aictx/failure_memory/failure_patterns.jsonl
aictx report real-usage
```

Expected result:

- the failure is stored as structured memory;
- future startup context can warn the agent about known failure patterns;
- the failure becomes reusable continuity instead of being lost in chat history.

---

### 6. Show real usage report

Run:

```bash
aictx report real-usage
```

Use the report to discuss:

- execution count;
- contract compliance;
- observed failures;
- files touched;
- command/test evidence;
- whether the next session has useful continuity.

Do not overclaim from one metric. Total tokens alone can be misleading when the prompt includes benchmark instrumentation.

---

## Recommended benchmark shape

A useful demo compares at least two matched runs.

```text
Run A: baseline agent, no AICTX continuity.
Run B: same agent/model/environment, AICTX initialized and used through normal resume/finalize flow.
```

Recommended metrics:

| Metric | Why it matters |
|---|---|
| Time to first useful edit | Measures orientation overhead |
| Number of exploratory commands | Shows repo rediscovery cost |
| Number of files inspected | Shows whether search is focused |
| Number of files edited | Shows edit scope discipline |
| Repeated failed commands | Shows whether Failure Memory helps |
| Tests run | Shows verification behavior |
| Contract result | Shows whether the agent followed the expected route |
| Uncached tokens to useful action | Better than total tokens for startup efficiency |
| Total tokens | Useful, but not sufficient alone |
| Quality of next-session summary | Measures continuity value |

The strongest expected proof is not “AICTX always uses fewer tokens”.

The strongest expected proof is:

```text
The next session starts with more useful state, fewer blind spots, and a clearer operational route.
```

---

## How to interpret demo results

### Strong result

A strong AICTX run looks like this:

- the agent starts from `aictx resume`;
- it identifies the relevant files sooner;
- it avoids unrelated exploration;
- it follows or partially follows the execution contract;
- it runs the expected test or explains why not;
- finalize records what happened;
- the next resume includes useful prior evidence;
- the next session edits are narrower or more targeted.

### Weak result

A weak or contaminated run looks like this:

- the task goal includes benchmark instructions;
- `.demo_metrics` or demo scaffolding is present in the repo;
- the agent edits metrics files instead of project files;
- the agent spends too much time interpreting the demo harness;
- total tokens increase because instrumentation polluted the task;
- the next resume overweights the latest execution and loses broader repo context.

### Product interpretation

If the run improves orientation, focus, and continuity but does not reduce total tokens, the correct conclusion is:

```text
AICTX is already useful as an operational continuity layer.
Further work should reduce startup verbosity and separate instrumentation from task context.
```

---

## Demo checklist

Before running:

- [ ] Same model for baseline and AICTX runs.
- [ ] Same repo state for baseline and AICTX runs.
- [ ] `.demo_metrics` absent from the target repo.
- [ ] Prompt/metrics files stored outside the repo.
- [ ] `aictx --version` recorded.
- [ ] Task goal separated from benchmark/reporting instructions.
- [ ] `aictx resume --task "<task goal>"` used for normal startup.

During the run:

- [ ] Capture time to first useful edit.
- [ ] Capture exploratory commands.
- [ ] Capture files inspected and edited.
- [ ] Capture tests/commands executed.
- [ ] Capture repeated failures.
- [ ] Capture contract result.
- [ ] Capture final AICTX summary.

After the run:

- [ ] Run `aictx report real-usage`.
- [ ] Inspect `.aictx/continuity/last_execution_summary.md`.
- [ ] Inspect `.aictx/metrics/contract_compliance.jsonl` if present.
- [ ] Confirm the next `aictx resume` contains useful continuity.
- [ ] Compare matched runs only.
- [ ] Interpret total tokens alongside focus, time, command count, and continuity quality.

---

## Current next improvements suggested by the demo

The demo analysis points to these product improvements:

1. Prefer `--task` as the documented normal startup interface.
2. Keep `--request` as legacy/raw compatibility, but warn or sanitize when it contains non-task benchmark instructions.
3. Reduce startup verbosity so the agent receives less runtime explanation and more operational context.
4. Make the distinction clear between latest execution summary and durable global repo memory.
5. Ensure latest execution updates global memory instead of replacing it.
6. Keep demo metrics outside the repo to avoid contaminating agent behavior.
7. Report continuity quality, focus, and repeated-failure avoidance, not only total token count.

---

## Short demo script

Use this for a compact live demo.

```bash
# Install and init
pip install aictx
aictx install
aictx init --repo . --yes --no-register

# Version
aictx --version

# Create work state
aictx task start "Fix token refresh loop" --json
aictx task update --json --json-patch '{"current_hypothesis":"refresh replay happens before persisted token update","active_files":["src/api/client.ts"],"next_action":"inspect interceptor ordering","recommended_commands":["pytest -q tests/test_auth.py"]}'

# Resume as an agent would
aictx resume --repo . --task "continue token refresh work" --json | python3 -m json.tool

# Optional RepoMap
pip install "aictx[repomap]"
aictx install --with-repomap --yes
aictx map status
aictx map query "work state"

# Failure memory demo
aictx internal run-execution --repo . --request "run typecheck" --agent-id demo --json -- python -c "import sys; print('src/app.ts(4,7): error TS2322: Type mismatch', file=sys.stderr); sys.exit(1)"
cat .aictx/failure_memory/failure_patterns.jsonl

# Usage and compliance
aictx report real-usage
cat .aictx/metrics/contract_compliance.jsonl 2>/dev/null || true
```

---

## One-sentence takeaway

AICTX makes coding-agent continuity explicit, repo-local, inspectable, and reusable; the demo shows stronger orientation and session-to-session focus, while also revealing that token savings require careful separation between task context and benchmark instrumentation.
