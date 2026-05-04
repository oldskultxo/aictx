# Quickstart

This walkthrough shows the shortest path from setup to visible continuity.

For detailed setup prompts, see [Installation](INSTALLATION.md).

---

## 1. Install and initialize

From inside your repository:

```bash
pip install aictx
aictx install
aictx init
```

Optional install check:

```bash
aictx --version
```

Explicit form:

```bash
aictx init --repo .
```

After this, keep using your coding agent. AICTX is designed to be agent-driven.

---

## 2. Inspect continuity manually

Manual inspection is optional. Normal supported agent startup should use `--task` with only the work goal:

```bash
aictx resume --repo . --task "continue current work" --json
```

To inspect that JSON with Python, pipe it to a JSON reader, not to `python3 -` as a script:

```bash
aictx resume --repo . --task "continue current work" --json | python3 -m json.tool
```

`--request` remains available as legacy/raw input for compatibility, but `--task` is the preferred normal startup path.

A fresh repo may have little continuity. That is expected.

---

## 3. Create visible Work State

```bash
aictx task start "Fix login token refresh" --json
```

Add a next action:

```bash
aictx task update --json --json-patch '{"current_hypothesis":"token refresh replay happens before persisted token update","next_action":"inspect auth interceptor ordering","active_files":["src/api/client.ts"],"recommended_commands":["pytest -q tests/test_auth.py"]}'
```

Inspect:

```bash
aictx resume --repo . --task "continue token refresh work" --json
```

---

## 4. Optional RepoMap

```bash
pip install "aictx[repomap]"
aictx install --with-repomap
aictx init
aictx map status
aictx map query "auth interceptor"
```

RepoMap is optional. Core continuity works without it.

---

## 5. What supported agents should do

Supported agents should follow generated runtime guidance:

```text
prepare/startup context remains available
extract the task goal only from the user prompt
run one agent-facing continuity query: aictx resume --repo . --task "<task goal>" --json
use the returned capsule and execution_contract as the operational brief
execute the task
finalize after execution
use agent_summary_text as the factual final summary source
```

`resume` does not replace prepare/finalize, the startup banner, the final AICTX summary, or persistence. It compiles continuity so the agent does not discover AICTX internals at startup.

When observable execution evidence is available, finalize can add a compact contract compliance line such as `Contract: followed.` or `Contract: partial — canonical test was not observed.`.

The user does not need to call internal commands in normal use.

---

## 6. Advanced manual runtime simulation

Prepare:

```bash
aictx internal execution prepare --repo . --request "continue token refresh work" --agent-id demo --execution-id demo-1 > prepared.json
```

Finalize:

```bash
aictx internal execution finalize --prepared prepared.json --success --result-summary "targeted auth test passed" --tests-executed "pytest -q tests/test_auth.py"
```

Inspect:

```bash
aictx task status --json
cat .aictx/continuity/last_execution_summary.md
cat .aictx/metrics/contract_compliance.jsonl 2>/dev/null || true
```
