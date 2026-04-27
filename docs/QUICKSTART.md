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

Explicit form:

```bash
aictx init --repo .
```

After this, keep using your coding agent. AICTX is designed to be agent-driven.

---

## 2. Inspect continuity manually

Manual inspection is optional:

```bash
aictx next
```

Structured output:

```bash
aictx next --json
```

A fresh repo may have little continuity. That is expected.

---

## 3. Create visible Work State

```bash
aictx task start "Fix login token refresh" --json
```

Add a next action:

```bash
aictx task update --json   --json-patch '{"current_hypothesis":"token refresh replay happens before persisted token update","next_action":"inspect auth interceptor ordering","active_files":["src/api/client.ts"],"recommended_commands":["pytest -q tests/test_auth.py"]}'
```

Inspect:

```bash
aictx next
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
boot or load startup continuity
prepare before meaningful work
execute the task
finalize after execution
use agent_summary_text as the factual final summary source
```

The user does not need to call these internal commands in normal use.

---

## 6. Advanced manual runtime simulation

Prepare:

```bash
aictx internal execution prepare   --repo .   --request "continue token refresh work"   --agent-id demo   --execution-id demo-1 > prepared.json
```

Finalize:

```bash
aictx internal execution finalize   --prepared prepared.json   --success   --result-summary "targeted auth test passed"   --tests-executed "pytest -q tests/test_auth.py"
```

Inspect:

```bash
aictx task status --json
cat .aictx/continuity/last_execution_summary.md
```
