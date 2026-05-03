# Codex Prompt — Convert `aictx resume` into a closed-loop execution contract

## Repository / branch

Work in:

```text
oldskultxo/aictx
branch: v5.3
```

Create the next fix on top of the current `v5.3` branch.

---

## Problem

Current AICTX behavior is not strong enough.

The agent correctly starts with:

```bash
aictx resume --repo . --request "..." --json
```

but then still enters a broad repo-orientation loop:

```text
git status
git diff
ls / find
README reads
examples reads
manual Python probes
partial tests
spacing fixes
more tests
```

In the demo, Codex behaves worse with AICTX than without it in Session 2, even though the repo is the same.

This means:

```text
AICTX is currently providing context.
AICTX is not yet providing a binding execution route.
```

The fix must make `aictx resume` return an explicit closed-loop execution contract:

```text
clean task goal
→ resume
→ first_action
→ limited edit scope
→ canonical test command
→ finalize
```

Do not add more memory.

Do not add more public docs.

Do not optimize for the demo specifically.

Make the behavior general and auditable.

---

# Core goal

Turn `resume` from:

```text
context package
```

into:

```text
execution contract
```

The agent should read `aictx resume --json` and know exactly:

```text
1. what task goal it is executing
2. what file/action to perform first
3. what it is forbidden to do before first edit
4. what files are in scope
5. what test command to run
6. how to finalize
```

---

# Strict non-goals

Do not:

```text
- add token/cost metrics
- add demo-specific sanitizer
- add demo-specific metrics handling
- add hardcoded parser/demo behavior
- add benchmark framework
- add more public README marketing
- rewrite the CLI broadly
- remove existing commands
- change compaction
- change portability
- change package version
- change release notes
- move large modules around
```

Do not weaken:

```text
startup_guard
first_action
aictx finalize
advanced help behavior
prepare/finalize lifecycle
startup banner
final AICTX summary
resume_capsule.md/json writing
```

---

# Files to touch

Touch only these files unless absolutely necessary:

```text
src/aictx/continuity.py
src/aictx/agent_runtime.py
src/aictx/cli.py
tests/test_resume_command.py
tests/test_smoke.py        # only if existing assertions require updates
tests/test_wrappers.py     # only if existing assertions require updates
AGENTS.md                  # only if managed block must be kept in sync
```

Do not touch README/docs unless a generated managed block test requires it.

---

# Required design changes

## 1. Add preferred `--task` argument to `aictx resume`

`--request` is currently used for the full user request.

Add a clearer preferred flag:

```bash
aictx resume --repo . --task "<task goal>" --json
```

Behavior:

```text
--task is the preferred task-goal-only input.
--request remains supported for backward compatibility.
If both are provided, --task wins.
Internally, the selected task goal may map to the existing request field if needed.
```

Do not remove `--request`.

Do not break existing tests.

### CLI help wording

For `resume --help`, make the difference clear:

```text
--task      Task goal only. Preferred for agent startup.
--request   Legacy/raw request input. Do not include reporting/output-format instructions.
```

---

## 2. Runtime instructions must require task-goal-only input

Update:

```text
src/aictx/agent_runtime.py
```

In both:

```text
render_agent_runtime()
render_repo_agents_block()
```

The normal startup instruction must say:

```text
At session start:
1. Extract the task goal from the user prompt.
2. Run:
   aictx resume --repo . --task "<task goal>" --json
3. Do not pass the full user prompt to resume.
```

Define task goal:

```text
The task goal answers:
"What work should be resumed or performed?"
```

Explicitly exclude:

```text
- reporting instructions
- metrics schemas
- output format rules
- final answer format
- benchmark/evaluation harness text
- logging instructions
- meta-instructions about how to report the work
```

Keep `--request` mentioned only as legacy/backward-compatible if necessary.

The agent-facing normal flow must become:

```text
aictx resume --repo . --task "<task goal>" --json
→ follow execution_contract.first_action before repo-wide orientation
→ edit within execution_contract.edit_scope
→ run execution_contract.test_command.command
→ run aictx finalize --repo . --status success|failure --summary "<what changed and what passed>" --json
```

---

## 3. `resume` JSON must include `execution_contract`

In `src/aictx/continuity.py`, add a structured field to the resume JSON:

```json
{
  "execution_contract": {
    "mode": "closed_loop",
    "task_goal": "...",
    "first_action": {
      "type": "open_file",
      "path": "tests/test_parser.py",
      "binding": "must_open_first",
      "reason": "..."
    },
    "first_action_policy": {
      "must_follow": true,
      "if_uncertain": "Inspect only fallback_entry_points; do not perform repo-wide orientation.",
      "allowed_before_first_edit": [
        "open:first_action.path",
        "open:paired_source_or_test_if_needed",
        "open:fallback_entry_points_only_if_first_action_is_missing_or_invalid"
      ]
    },
    "forbidden_before_first_edit": [
      "git status",
      "git diff",
      "ls",
      "find",
      "repo-wide grep",
      "read README.md",
      "read docs/**",
      "read examples/**",
      "read Makefile",
      "read pyproject.toml",
      "manual Python probes",
      "test command before first edit",
      "alternative test command discovery",
      "inspect .aictx/**",
      "inspect local/global AICTX installation files"
    ],
    "edit_scope": {
      "primary": ["tests/test_parser.py"],
      "secondary_if_needed": ["src/taskflow/parser.py"],
      "avoid": ["README.md", "examples/**", "src/taskflow/summary.py"]
    },
    "test_command": {
      "command": "make test",
      "source": "previous_successful_command|makefile|project_convention|fallback",
      "policy": "Do not try alternative test commands unless this command fails."
    },
    "finalize_command": "aictx finalize --repo . --status success|failure --summary \"<what changed and what passed>\" --json"
  }
}
```

Use this exact conceptual shape.

Field names may follow project style, but preserve the meaning.

Do not remove existing fields.

Do not break existing consumers.

---

## 4. `resume` text output must put the execution contract first

Default text output should begin with a compact operational contract before broader context.

Required order:

```text
Execution contract
Startup rule
First action
Current request / task goal
Task state
Entry points
...
Source index
```

`Execution contract` must appear before `Source index`.

It must include:

```text
1. Open first action:
   <path>

2. Do not perform repo-wide orientation before first edit.
   Do not run git status, git diff, ls/find, README/examples/docs reads, manual probes, or alternative test discovery unless explicitly allowed by this contract.

3. Edit scope:
   Primary: ...
   Secondary if needed: ...
   Avoid: ...

4. Validate with:
   <test command>
   Do not try alternatives unless it fails.

5. Finalize with:
   aictx finalize --repo . --status success|failure --summary "<what changed and what passed>" --json
```

Keep default output under the existing budget.

If needed, reduce lower-priority context sections.

---

## 5. `first_action` must become binding, not informational

The existing `first_action` must be upgraded or mirrored into the contract.

Rules:

```text
first_action.binding must be "must_open_first".
first_action_policy.must_follow must be true.
```

If there is no high-confidence path:

```json
{
  "first_action": {
    "type": "inspect_entry_points",
    "path": "",
    "binding": "must_inspect_listed_entry_points_only",
    "reason": "No single high-confidence entry point was available."
  }
}
```

In that case:

```text
The agent may inspect only listed entry_points/fallback_entry_points.
It must not perform repo-wide orientation.
```

---

## 6. `resume` must include a canonical test command

Add helper logic in `continuity.py`:

```text
_select_canonical_test_command()
```

Priority:

```text
1. Last successful test command from AICTX continuity/finalize/workflow memory, if available.
2. `make test` if Makefile exists.
3. `.venv/bin/python -m pytest -q` if pytest project and venv detected.
4. `python -m pytest -q` if pytest project.
5. `pytest -q` as last fallback.
```

For v1 of this fix, keep it deterministic and simple.

Do not run commands to discover this.

Only inspect existing repo files/state already available to resume.

For the demo repo, if `Makefile` exists, the contract should prefer:

```bash
make test
```

The policy must say:

```text
Do not try alternative test commands unless this command fails.
```

---

## 7. `resume` must include `contract_checks`

Add machine-readable checks:

```json
{
  "contract_checks": {
    "expected_first_action": "open:first_action.path",
    "expected_test_command": "make test",
    "expected_final_command": "aictx finalize",
    "violations_to_report": [
      "repo_wide_orientation_before_first_edit",
      "git_status_before_first_edit",
      "git_diff_before_first_edit",
      "ls_or_find_before_first_edit",
      "read_docs_before_first_edit",
      "read_examples_before_first_edit",
      "manual_probe_before_first_edit",
      "alternative_test_command_before_canonical_test",
      "missing_finalize"
    ]
  }
}
```

This does not need to enforce behavior at runtime.

It makes violations auditable.

---

## 8. Keep and strengthen startup guard

Preserve existing `startup_guard`.

It should still include:

```json
"resume_is_self_contained": true,
"do_not_read_runtime_files": true,
"do_not_inspect_aictx_installation": true,
"allowed_aictx_commands_before_first_task_action": ["resume"],
"allowed_aictx_commands_after_task_action": ["finalize"]
```

Do not remove existing forbidden lists.

Make sure the startup guard and execution contract do not contradict each other.

---

# Important behavior details

## Repo-wide orientation

The contract must explicitly forbid these before first edit unless first_action is missing/invalid and fallback_entry_points are insufficient:

```text
git status
git diff
ls
find
repo-wide grep
README/docs/examples reads
Makefile/pyproject reads for orientation
manual probes
test command before first edit
alternative test command discovery
```

Caveat:

```text
pyproject/Makefile may be used internally by AICTX to select test_command.
The agent should not read them during normal execution unless contract allows it.
```

## Paired files

The contract may allow paired source/test reads.

Examples:

```text
first_action = tests/test_parser.py
paired file allowed = src/taskflow/parser.py

first_action = src/foo/bar.py
paired file allowed = tests/test_bar.py if obvious
```

Keep this simple.

Do not implement complex graph logic.

If a paired file cannot be inferred, omit it.

## Scope

The contract should avoid unrelated files.

For a testing/parser task:

```text
primary: tests/test_parser.py
secondary_if_needed: src/taskflow/parser.py
avoid: README.md, examples/**, summary/cli unless task explicitly requires them
```

For docs tasks, docs/README may be primary.

For config tasks, pyproject/CI may be primary.

Do not hardcode parser-specific logic.

Use existing generic ranking/path category logic.

---

# Tests to add/update

Add focused tests in:

```text
tests/test_resume_command.py
```

Do not create a large new suite.

## 1. CLI accepts `--task` and it wins over `--request`

Test:

```bash
aictx resume --repo <repo> --task "Fix parser tests" --request "FULL PROMPT WITH REPORTING" --json
```

Assert JSON task goal/effective request is:

```text
Fix parser tests
```

Assert the full request/reporting text is not used as the execution contract task goal.

## 2. Runtime instructions require task-goal-only

Test `render_agent_runtime()` contains:

```text
aictx resume --repo . --task "<task goal>" --json
Do not pass the full user prompt to resume
reporting instructions
metrics schemas
output format rules
```

Also assert it still contains:

```text
aictx finalize --repo .
final AICTX summary
```

## 3. Resume JSON includes execution_contract

Create a repo fixture with:

```text
Makefile
src/taskflow/parser.py
tests/test_parser.py
README.md
examples/tasks.txt
pyproject.toml
```

Run:

```bash
aictx resume --repo <repo> --task "Continue previous task: handle BLOCKED parser edge cases" --json
```

Assert:

```python
payload["execution_contract"]["mode"] == "closed_loop"
payload["execution_contract"]["first_action"]["binding"] == "must_open_first"
payload["execution_contract"]["first_action_policy"]["must_follow"] is True
payload["execution_contract"]["test_command"]["command"] == "make test"
"git status" in payload["execution_contract"]["forbidden_before_first_edit"]
"git diff" in payload["execution_contract"]["forbidden_before_first_edit"]
"read README.md" in payload["execution_contract"]["forbidden_before_first_edit"]
"manual Python probes" in payload["execution_contract"]["forbidden_before_first_edit"]
"alternative test command discovery" in payload["execution_contract"]["forbidden_before_first_edit"]
"aictx finalize" in payload["execution_contract"]["finalize_command"]
```

## 4. Execution contract appears before source index in text

Run default text output.

Assert:

```python
output.index("Execution contract") < output.index("Source index")
```

Assert output contains:

```text
Open first action
Do not perform repo-wide orientation before first edit
Validate with
Finalize with
```

## 5. Contract selects Makefile test command

Fixture with Makefile.

Assert:

```python
payload["execution_contract"]["test_command"]["command"] == "make test"
```

Fixture without Makefile but with pytest/pyproject.

Assert fallback is pytest-like.

Do not make this brittle.

## 6. Contract forbids broad orientation before first edit

Assert forbidden list includes:

```text
git status
git diff
ls
find
repo-wide grep
read README.md
read docs/**
read examples/**
manual Python probes
test command before first edit
alternative test command discovery
```

## 7. Contract keeps `.aictx/**` forbidden

Assert `.aictx/**` and local/global AICTX installation files are still forbidden.

## 8. First action remains non-demo-specific

Use a non-parser fixture:

```text
src/payments/validation.py
tests/test_payment_validation.py
README.md
Makefile
```

Task:

```text
Fix payment validation bug
```

Assert first_action is one of:

```text
tests/test_payment_validation.py
src/payments/validation.py
```

Assert not README.

## 9. Docs task can still choose README

Task:

```text
Update README install instructions
```

Assert docs/README can be first_action and forbidden docs-before-edit rule does not contradict docs task.

For docs tasks, the contract should not forbid reading the first_action if it is README.

## 10. Contract checks present

Assert JSON includes:

```text
contract_checks.expected_first_action
contract_checks.expected_test_command
contract_checks.expected_final_command
contract_checks.violations_to_report
```

and `violations_to_report` contains:

```text
missing_finalize
repo_wide_orientation_before_first_edit
alternative_test_command_before_canonical_test
```

## 11. Budget still holds

For rich fixture, assert:

```python
len(default_output) <= 6000
```

If it exceeds, trim lower priority sections.

---

# Acceptance criteria

This task is complete when:

```text
- `aictx resume` supports preferred `--task`.
- `--task` wins over `--request`.
- Runtime instructions tell agents to pass task goal only, not full prompt.
- Resume JSON includes `execution_contract`.
- Resume text puts `Execution contract` before broader context/source index.
- First action is binding.
- Repo-wide orientation is explicitly forbidden before first edit.
- Canonical test command is selected and included.
- Alternative test command discovery is forbidden unless canonical command fails.
- Finalize command is part of the contract.
- Contract checks make violations auditable.
- Existing startup_guard remains intact.
- Existing finalize behavior remains intact.
- Existing resume ranking/path classification remains generic.
- Focused tests pass.
```

---

# Commands to run

Run focused tests:

```bash
PYTHONPATH=src pytest -q tests/test_resume_command.py
```

Run affected tests:

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
