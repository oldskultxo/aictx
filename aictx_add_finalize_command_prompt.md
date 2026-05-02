# Codex Prompt — Add canonical `aictx finalize` and remove finalize-discovery ambiguity

## Repository / branch

Work in:

```text
oldskultxo/aictx
branch: v5.2
```

## Problem

The agent can currently hit this error:

```text
usage: aictx [-h] [-v] {install,init,resume,advanced,clean,uninstall} ...
aictx: error: argument {install,init,resume,advanced,clean,uninstall}: invalid choice: 'finalize'
```

This can make the agent rediscover the repo/runtime repeatedly.

Why:

- AICTX runtime instructions mention `finalize`, `finalize_execution`, and the lifecycle:
  ```text
  prepare/startup context → resume capsule → work → finalize → final AICTX summary/persistence
  ```
- But there is no simple public CLI command:
  ```bash
  aictx finalize
  ```
- So the agent may try `aictx finalize`, fail, then start exploring:
  ```text
  aictx --help
  aictx internal -h
  .aictx/agent_runtime.md
  middleware.py
  cli.py
  source search for finalize_execution
  ```

That defeats the v5.1 goal of preventing AICTX tool/runtime discovery.

---

# Goal

Add a canonical, agent-facing end-of-task command:

```bash
aictx finalize --repo . --status success --summary "<what happened>" --json
```

The normal lifecycle contract should become:

```text
At task start:
  aictx resume --repo . --request "<current user request>" --json

After task work:
  aictx finalize --repo . --status success|failure --summary "<what happened>" --json
```

`resume` remains the only allowed AICTX command before the first task action.

`finalize` becomes the only allowed AICTX command after task work for persistence/final summary.

Do not make agents use:

```text
aictx internal execution finalize
```

Do not tell agents to shell-call:

```text
finalize_execution
```

---

# Scope

This is a surgical CLI/runtime contract fix.

Touch only:

```text
src/aictx/cli.py
src/aictx/agent_runtime.py
src/aictx/continuity.py
tests/test_resume_command.py
tests/test_smoke.py            # only if existing assertions require it
tests/test_wrappers.py         # only if existing assertions require it
```

Possibly touch an existing CLI test file if one exists and is more appropriate.

Do not touch:

```text
resume ranking logic
RepoMap scoring
first_action selection
path classification
advanced help behavior except listing finalize as normal lifecycle command
compaction
portability
README/public docs unless an existing test requires generated text
package version
release notes
```

---

# Required behavior

## 1. Add top-level `aictx finalize`

Add a top-level parser command:

```bash
aictx finalize --repo . --status success --summary "Implemented X and verified Y"
aictx finalize --repo . --status failure --summary "Attempted X but tests failed" --error "pytest failed"
aictx finalize --repo . --status success --summary "Done" --json
```

### Required args

```text
--repo
--status success|failure
--summary
--json
```

`--repo` may default to `.` if consistent with existing commands.

### Optional args

Add only if easy to map to existing middleware:

```text
--request
--task-type
--files-opened
--files-edited
--commands-executed
--tests-executed
--notable-errors
--error
--agent-id
--adapter-id
--session-id
```

Keep the command simple. Do not over-engineer.

---

## 2. Use existing middleware finalization

Do not reimplement finalization logic.

`src/aictx/cli.py` already imports:

```python
from .middleware import cli_finalize_execution, cli_prepare_execution
```

Use existing finalization machinery.

Implementation guidance:

1. Locate `cli_finalize_execution` in `src/aictx/middleware.py`.
2. Check its signature.
3. Build the minimal compatible payload/namespace from CLI args.
4. Call it from a new `cmd_finalize(args)` in `src/aictx/cli.py`.
5. Print JSON if `--json`.
6. Otherwise print the compact final summary text.

If `cli_finalize_execution` expects a namespace, pass a namespace.

If it expects a dict, pass a dict.

If there is an existing internal command path for finalization, reuse/factor it instead of duplicating logic.

The new command should be a thin public wrapper over the existing finalization path.

---

## 3. Output

For `--json`, print valid JSON.

The JSON should include, if available from existing finalization:

```text
agent_summary_text
agent_summary_render_payload
agent_summary_policy
last_execution_summary
handoff_stored
decision_stored
strategy_persisted
failure_recorded
```

Do not invent data.

For text mode, print a compact user-facing summary.

Preferred:

```text
payload["agent_summary_text"]
```

Fallback:

```text
AICTX summary unavailable
```

The command must return exit code 0 on valid input.

---

## 4. Top-level help must include `finalize`

The visible command list should become:

```text
{install,init,resume,finalize,advanced,clean,uninstall}
```

or equivalent.

Do not expose advanced commands in top-level help.

Advanced commands remain callable but hidden/listed under:

```bash
aictx advanced
aictx advanced --help
```

---

## 5. Advanced help must not treat finalize as advanced

`finalize` is a normal lifecycle command, not an advanced/building-block command.

`aictx advanced` should still list:

```text
suggest
reuse
next
task
messages
map
report
reflect
internal
```

It should not list `finalize` as an advanced command.

It may include a normal lifecycle reminder:

```text
Normal agent lifecycle:
  aictx resume ...
  aictx finalize ...
```

but do not put `finalize` in the advanced command list.

---

# Mandatory runtime instruction changes

You must modify:

```text
src/aictx/agent_runtime.py
```

This is not optional.

The error comes partly from ambiguous runtime wording. Fix both:

```text
render_agent_runtime()
render_repo_agents_block()
```

## Required meaning

The runtime loop must say:

```text
At session start:
  run exactly one AICTX continuity command:
  aictx resume --repo . --request "<current user request>" --json

After task work:
  run exactly one AICTX finalization command:
  aictx finalize --repo . --status success|failure --summary "<what happened>" --json
```

Replace ambiguous wording like:

```text
Run finalize_execution with the real outcome when using the execution middleware.
```

with explicit wording:

```text
Use `aictx finalize --repo . --status success|failure --summary "<what happened>" --json` for normal agent finalization.
`finalize_execution` is the middleware API behind that command; do not call it directly from the shell.
Do not run `aictx internal execution finalize` during normal task flow.
```

Keep the lifecycle phrase:

```text
prepare/startup context → resume capsule → work → finalize → final AICTX summary/persistence
```

But make it clear that user/agent CLI finalization maps to:

```bash
aictx finalize
```

## Update repo AGENTS block generator

In `render_repo_agents_block()`, update the managed AICTX block so generated `AGENTS.md` says the same thing:

```text
- At session start, use `aictx resume ...`
- After task work, use `aictx finalize ...`
- Do not call `finalize_execution` directly from the shell.
- Do not run `aictx internal execution finalize` during normal task flow.
```

If the checked-in `AGENTS.md` is generated/managed and present in the repo, update it only if the project normally keeps generated text checked in.

---

# Resume startup guard changes

Modify:

```text
src/aictx/continuity.py
```

In `_resume_startup_guard()`:

Keep this unchanged:

```json
"allowed_aictx_commands_before_first_task_action": ["resume"]
```

Add:

```json
"allowed_aictx_commands_after_task_action": ["finalize"]
```

Add or extend a normal-flow forbidden section:

```json
"forbidden_normal_flow": [
  "aictx internal execution finalize",
  "direct shell calls to finalize_execution"
]
```

Keep all existing fields for backward compatibility.

Do not allow `finalize` before the first task action.

---

# Resume text output changes

In the default Markdown/plaintext resume output, keep:

```text
Run no further AICTX discovery commands before opening the first action target.
```

Add one compact line under `Startup rule` or `Avoid`:

```text
After completing the task, use `aictx finalize --repo . --status success|failure --summary "<what happened>" --json`.
```

This prevents the agent from inventing or searching for finalization syntax.

Keep the default output under the existing budget.

---

# CLI implementation specifics

## Locate parser setup

In:

```text
src/aictx/cli.py
```

Find:

```python
def build_parser(...)
```

Add `finalize` near `resume`, not under `advanced`.

Expected shape:

```python
finalize_parser = sub.add_parser(
    "finalize",
    help="Finalize an AICTX task execution and produce the final summary",
)
finalize_parser.add_argument("--repo", default=".")
finalize_parser.add_argument("--status", choices=["success", "failure"], required=True)
finalize_parser.add_argument("--summary", required=True)
finalize_parser.add_argument("--json", action="store_true")
...
finalize_parser.set_defaults(func=cmd_finalize)
```

Also update the top-level `metavar` / visible command list to include `finalize`:

```text
{install,init,resume,finalize,advanced,clean,uninstall}
```

## Add `cmd_finalize`

Add near `cmd_resume`:

```python
def cmd_finalize(args: argparse.Namespace) -> int:
    ...
```

It should:

```text
- resolve repo
- build result payload from args
- call existing middleware finalization helper
- print JSON if --json
- otherwise print compact summary text
- return 0
```

Pseudo-shape, adapt to actual middleware signature:

```python
def cmd_finalize(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").expanduser().resolve()
    result = {
        "success": args.status == "success",
        "status": args.status,
        "result_summary": args.summary,
    }
    if getattr(args, "error", ""):
        result["error"] = args.error
        result["notable_errors"] = [args.error]

    payload = cli_finalize_execution(...)

    if args.json:
        _print_json(payload)
    else:
        print(str(payload.get("agent_summary_text") or "AICTX summary unavailable"))
    return 0
```

Do not duplicate persistence/final summary logic.

---

# Tests to add/update

Use existing test style, mostly in:

```text
tests/test_resume_command.py
```

## 1. Top-level help includes finalize

Update existing top-level help test.

Assert:

```text
resume
finalize
advanced
```

Assert visible command list includes:

```text
{install,init,resume,finalize,advanced,clean,uninstall}
```

or equivalent.

Assert advanced commands remain hidden from the normal top-level help.

## 2. Advanced help does not list finalize as advanced

For:

```bash
aictx advanced
```

or:

```bash
aictx advanced --help
```

Assert advanced commands are present:

```text
suggest
reuse
next
task
messages
map
report
reflect
internal
```

Assert `finalize` is not listed as an advanced/building-block command.

If `finalize` appears only inside a normal lifecycle sentence, make the assertion precise enough not to fail on that.

## 3. `aictx finalize` JSON smoke test

Create initialized temp repo:

```python
init_repo_scaffold(repo, update_gitignore=False)
```

Run parser or subprocess:

```bash
aictx finalize --repo <repo> --status success --summary "Implemented parser edge tests" --json
```

Assert:

```text
exit 0
stdout valid JSON
JSON contains agent_summary_text or equivalent final summary field
JSON does not say invalid choice
```

Prefer invoking through parser if the suite already uses parser tests.

## 4. `aictx finalize` text smoke test

Run:

```bash
aictx finalize --repo <repo> --status success --summary "Done"
```

Assert output contains:

```text
AICTX summary
```

or the canonical compact fallback:

```text
AICTX summary unavailable
```

Prefer the real summary if available.

## 5. Resume startup guard allows finalize only after task

Update existing JSON test for resume.

Assert:

```python
payload["startup_guard"]["allowed_aictx_commands_before_first_task_action"] == ["resume"]
payload["startup_guard"]["allowed_aictx_commands_after_task_action"] == ["finalize"]
```

If you add `forbidden_normal_flow`, assert it contains:

```text
aictx internal execution finalize
direct shell calls to finalize_execution
```

## 6. Resume text mentions exact finalize command

Update `test_resume_default_markdown_and_budget`.

Assert default resume text contains:

```text
aictx finalize --repo .
--status success|failure
--summary
```

Keep output under budget.

## 7. Runtime contract test

Update `test_runtime_contract_says_resume_does_not_replace_lifecycle`.

Assert `render_agent_runtime()` contains:

```text
aictx resume --repo .
aictx finalize --repo .
finalize_execution is the middleware API behind that command
do not call it directly from the shell
Do not render both
final AICTX summary
```

Use exact strings if stable.

## 8. Parser accepts finalize regression test

Add direct parser regression:

```python
args = _parser().parse_args([
    "finalize",
    "--repo", str(repo),
    "--status", "success",
    "--summary", "Done",
    "--json",
])
assert args.func(args) == 0
```

This prevents the reported invalid-choice regression.

---

# Non-goals

Do not:

```text
- change resume ranking
- change first_action scoring
- change RepoMap behavior
- change path categories
- change token/cost metrics
- change compaction
- change portability
- expose advanced commands in top-level help
- remove internal finalize paths
- rewrite README
- bump version
```

---

# Acceptance criteria

This task is complete when:

```text
- `aictx finalize` is a valid top-level command.
- `aictx --help` shows finalize as part of the normal lifecycle.
- `aictx advanced` still contains advanced commands, not finalize as advanced.
- Runtime instructions tell agents to use `aictx finalize`, not shell-call `finalize_execution`.
- Runtime instructions explicitly say not to use `aictx internal execution finalize` during normal task flow.
- Resume startup_guard allows only resume before first task action and finalize after task action.
- Resume text tells the agent the exact finalize command shape.
- Existing resume/ranking behavior remains unchanged.
- Focused tests pass.
```

---

# Commands to run

Run focused resume/CLI tests:

```bash
PYTHONPATH=src pytest -q tests/test_resume_command.py
```

Run affected smoke/wrapper/portability tests:

```bash
PYTHONPATH=src pytest -q tests/test_smoke.py tests/test_wrappers.py tests/test_portability.py
```

Run full suite if practical:

```bash
PYTHONPATH=src pytest -q
```

If full suite is not run, report why.

---

# Final response format

Return only:

```text
Files changed:
Behavior fixed:
Tests run:
Full suite run: yes/no
Remaining risks:
```
