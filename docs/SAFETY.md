# Safety

AICTX is repo-local, inspectable, and conservative.

Git-portable continuity is opt-in. Review `.aictx/` changes before committing because portable artifacts may still contain operational context.

---

## Default behavior

`aictx init` creates or updates repo-local artifacts and managed instruction blocks.

`aictx install` prepares AICTX global/runtime state. It does not modify global Codex files unless requested with:

```bash
aictx install --install-codex-global
```

---

## Files AICTX may create or update

```text
.aictx/
AGENTS.md
CLAUDE.md
.claude/settings.json
.claude/hooks/aictx_session_start.py
.claude/hooks/aictx_user_prompt_submit.py
.claude/hooks/aictx_pre_tool_use.py
.gitignore entries for AICTX runtime paths
```

Contract compliance history, when available, is stored repo-locally under:

```text
.aictx/metrics/contract_compliance.jsonl
```

---

## Managed blocks

Markdown sections are bounded by:

```md
<!-- AICTX:START -->
...
<!-- AICTX:END -->
```

Cleanup should remove only AICTX-managed content.

---

## Contract compliance safety posture

Contract compliance is audit-only.

It evaluates observed execution signals against the latest compatible resume contract, but it does not sandbox the agent, block edits, block commands, or guarantee that the resulting code is correct.

If observable execution evidence is missing, AICTX should report compliance as `not_evaluated` rather than inventing conclusions.

---

## Safety posture

AICTX does not guarantee productivity or token savings, autonomously repair repositories, replace human review, hide cloud memory, or infer missing facts as truth.

It keeps missing data empty, `unknown`, or `not_evaluated` depending on the surface.
