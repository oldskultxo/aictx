---
title: "Install AICTX for Repo-Local Coding-Agent Memory"
description: "Install and initialize the official Python `aictx` CLI for repo-local continuity, operational memory, and coding-agent handoffs."
---

# Installation

This guide explains how to install AICTX once, initialize a repo, and give supported coding agents a local continuity loop without changing how you work.

The normal product experience is:

```text
install -> init -> use your coding agent normally
```

Manual AICTX commands are mainly for inspection, debugging, examples, and advanced integrations.

---

## Requirements

- Python 3.11+
- `pip`
- a repository on disk
- git is recommended
- optional: Tree-sitter support through `aictx[repomap]`
- optional: Codex, Claude, and/or GitHub Copilot if you want runner integrations

---

## Fast path

From inside the target repository:

```bash
pip install aictx
aictx install
aictx init
aictx --version
```

Use `aictx --version` to verify the installed CLI version.

Equivalent explicit repo form:

```bash
aictx init --repo .
```

Use `--repo <path>` when running from outside the repository.

---

## Non-interactive setup

For CI, tests, temporary repositories, or scripted installation:

```bash
aictx install --yes
aictx init --repo . --yes
```

Temporary repo without registering:

```bash
aictx init --repo . --yes --no-register
```

Optional global Codex files:

```bash
aictx install --yes --install-codex-global
```

Optional RepoMap request:

```bash
pip install "aictx[repomap]"
aictx install --yes --with-repomap
aictx init --repo . --yes
```

---

## Interactive behavior

The CLI uses three interactive helpers:

```text
ask_yes_no(prompt, default)
ask_text(prompt, default)
ask_choice(prompt, options, default)
```

That means setup questions behave consistently:

- yes/no prompts accept `y`, `yes`, `n`, or empty input for the default;
- text prompts show a default in brackets when one exists;
- choice prompts list numbered options and ask `Select option number:`;
- invalid choices are rejected and asked again.

Prompt wording may change between releases. The decisions documented below are the current setup decisions users should expect.

---

## `aictx install`: global/runtime setup

`aictx install` prepares AICTX global/runtime state.

It is about the AICTX installation and workspace-level setup. It should not be described as the place where repo communication mode is chosen.

Default interactive setup is intentionally simple for non-advanced users. It uses the current defaults for workspace id, workspace root, and cross-project mode. If `~/.codex/` already exists, AICTX assumes Codex is installed and offers to update AICTX-managed global Codex integration files by default. It also asks whether to enable recommended RepoMap support using Tree-sitter.

Default interactive flow:

```text
aictx install

Detected ~/.codex. Install/update global Codex integration? [Y/n]: y

RepoMap uses Tree-sitter to build a compact structural map of files and symbols.
Recommended: it helps agents choose better starting points without reading the whole repo.

Enable recommended RepoMap support using Tree-sitter? [Y/n]: y
```

Advanced users can keep the full setup flow with `--manual`:

```text
aictx install --manual

Default workspace name [default]: default
Add a workspace root now? [Y/n]: y
Workspace root [/Users/me/projects]: /Users/me/dev
Enable RepoMap support using Tree-sitter? [y/N]: n
```

Install controls:

| Setup decision | Default/simple behavior | Advanced control |
|---|---|---|
| Workspace id | `default` | `--workspace-id <id>` or `--manual` |
| Workspace root | empty | `--workspace-root <path>` or `--manual` |
| Cross-project mode | `workspace` | `--cross-project-mode workspace|explicit|disabled` |
| Global Codex install | on when `~/.codex/` exists; otherwise off | confirm interactively, or force with `--install-codex-global` |
| RepoMap request | prompted, default `Y` | `--with-repomap`, `--yes --with-repomap`, or `--manual` |
| Dry run | off | `--dry-run` |
| Non-interactive mode | no prompts, safe defaults | `--yes` |
| Full interactive mode | off | `--manual` |

`--yes` skips prompts and keeps safe defaults. If `~/.codex/` exists, `--yes` also applies the AICTX-managed global Codex integration. To request RepoMap non-interactively, use:

```bash
aictx install --yes --with-repomap
```

---

## `aictx init`: repo-local setup

`aictx init` prepares one repository.

This prepares repo-local runtime behavior and generated agent integration files.

Default interactive setup assumes the current defaults for `.gitignore`, workspace registration, portable continuity, scaffold creation, and runtime communication behavior. It no longer asks for a communication mode.

Default interactive flow:

```text
aictx init

Using defaults for .gitignore, workspace registration, portable continuity and scaffold creation.
```

Advanced users can keep the full setup flow with `--manual`:

```text
aictx init --manual

Write .gitignore entries if missing? [Y/n]: y
Register this repo in the active workspace? [Y/n]: y
Enable AICTX git-portable continuity? [y/N]: n
Initialize full starter scaffold now? [Y/n]: y
```

Init controls:

| Setup decision | Default/simple behavior | Advanced control |
|---|---|---|
| Repo path | current directory | `--repo <path>` |
| Write `.gitignore` entries | yes unless `--no-gitignore` | `--manual` or `--no-gitignore` |
| Register repo | yes unless `--no-register` | `--manual` or `--no-register` |
| Git-portable continuity | disabled for new repos unless opted in | `--portable-continuity`, `--no-portable-continuity`, or `--manual` |
| Initialize scaffold | yes | `--manual` can cancel |
| RepoMap initialization | runs when globally requested | configure with `aictx install` |
| Non-interactive mode | no prompts, safe defaults | `--yes` |
| Full interactive mode | off | `--manual` |

Simple one-shot setup:

```bash
aictx init --repo . --yes
```

Portable continuity remains disabled by default for new repos. To opt in:

```bash
aictx init --repo . --portable-continuity
aictx init --repo . --yes --portable-continuity
aictx init --repo . --no-portable-continuity
```

`--portable-continuity` enables the team-safe profile for one engineer or small teams sharing the same Git repository. Git remains the transport; no external sync service is required.

Temporary/test setup without registry updates:

```bash
aictx init --repo . --yes --no-register
```

---

## Runtime communication compatibility

AICTX no longer exposes a communication-mode setup choice during `aictx init`. Normal communication style should remain controlled by the user, the runner, and current session instructions.

Existing repos may contain legacy communication-style values in `.aictx/memory/user_preferences.json`. These values are accepted as compatibility input and normalized to the default disabled runtime communication behavior, so repos keep working without exposing communication-mode branding in the first-run product path.

---

## What files may appear after init

Common repo-local files:

```text
.aictx/
AGENTS.md
.github/copilot-instructions.md
CLAUDE.md
.claude/settings.json
.claude/hooks/aictx_session_start.py
.claude/hooks/aictx_user_prompt_submit.py
.claude/hooks/aictx_pre_tool_use.py
```

RepoMap files when enabled:

```text
.aictx/repo_map/config.json
.aictx/repo_map/manifest.json
.aictx/repo_map/index.json
.aictx/repo_map/status.json
```

---

## Codex setup

Minimal:

```bash
pip install aictx
aictx install
aictx init
```

Global Codex support:

- if `~/.codex/` exists, `aictx install` offers to install/update it by default;
- with `--yes`, detected `~/.codex/` is updated automatically;
- if `~/.codex/` does not exist, force global Codex setup with:

```bash
aictx install --install-codex-global
```

Repo-level Codex guidance is written through `AGENTS.md`.

---

## GitHub Copilot setup

```bash
pip install aictx
aictx install
aictx init
```

AICTX creates/updates:

```text
.github/copilot-instructions.md
.github/instructions/aictx.instructions.md
.github/prompts/aictx-resume.prompt.md
.github/prompts/aictx-finalize.prompt.md
```

`.github/copilot-instructions.md` is the standard repository-wide GitHub Copilot custom instructions file. `.github/instructions/aictx.instructions.md` duplicates the minimal lifecycle as path-specific instructions for Copilot surfaces that support them. The prompt files are optional manual prompts for starting and finalizing AICTX-aware Copilot work. AICTX writes these managed files during `aictx init`, not during `aictx install`. They are intended to remain versioned in git and tell Copilot to use:

```bash
aictx resume --repo . --task "<task goal>" --agent-id copilot --adapter-id copilot-vscode --json
aictx finalize --repo . --status success|failure --summary "<what happened>" --agent-id copilot --adapter-id copilot-vscode --json
```

AICTX does not install Copilot hooks, wrappers, VSCode settings, or non-standard Copilot integrations. Copilot support is best-effort instruction-based: verify usage by expanding a Copilot Chat response References list and confirming `.github/copilot-instructions.md` is listed. If Copilot cannot run terminal commands, it should state that the AICTX lifecycle could not be executed.

---

## Claude setup

```bash
pip install aictx
aictx install
aictx init
```

AICTX can create/update:

```text
CLAUDE.md
.claude/settings.json
.claude/hooks/aictx_session_start.py
.claude/hooks/aictx_user_prompt_submit.py
.claude/hooks/aictx_pre_tool_use.py
```

---

## RepoMap setup

```bash
pip install "aictx[repomap]"
aictx install --yes --with-repomap
aictx init
aictx map status
```

Refresh manually:

```bash
aictx map refresh
```

Query:

```bash
aictx map query "startup banner"
```

---

## Generic agent setup

Any agent can use AICTX through the CLI/runtime contract:

```bash
aictx resume --repo . --task "<task goal>" --json
aictx finalize --repo . --status success|failure --summary "<what happened>" --json
```

The agent must cooperate with the runtime contract for best results.

Advanced integrations may also use `aictx internal execution prepare ...`,
`aictx internal execution finalize ...`, or `aictx internal run-execution ...`
when wrapping execution directly.

---

## After setup

Use your coding agent normally.

After `aictx install` and `aictx init`, let the coding agent work normally. Supported agents should use `resume -> work -> finalize` without requiring manual AICTX commands.

Manual inspection commands:

```bash
aictx doctor --repo . --json
aictx view --repo .
aictx map status
```

---

## Cleanup

See [Cleanup](CLEANUP.md).

Quick commands:

```bash
aictx clean --repo .
aictx uninstall
```

## MCP support

`aictx install` prepares AICTX global MCP runtime metadata by default with profile `full`. Use `aictx install --no-mcp` to opt out, or `aictx install --mcp-profile readonly|standard|full` to choose a profile.

`aictx init` writes repo-local AICTX-managed MCP config by default. Use `aictx init --no-mcp` to skip that config.

## Agent lifecycle contract

`aictx resume --json` includes compact runtime metadata for supported agents:

- `runner_contract`: AICTX is required, MCP is preferred, CLI fallback is mandatory, and agents should verify `aictx_resume`, `aictx_finalize`, `aictx_continuity_guard`, and `aictx_steer_guard` once per session.
- `guard_triggers`: stable action boundaries for first edit, scope changes, risky commands, user steering, and final answers.
- `execution_contract.validation_policy`: task-type-aware validation expectations so code tasks require focused evidence while documentation and analysis tasks stay advisory.

Routine agent startup can use `aictx resume --repo . --task "<task goal>" --json --brief` for a smaller payload. Standard mode remains the default for compatibility.

`aictx finalize` captures a compact git-state snapshot when Git is available and persists handoffs with `agent_id`, `adapter_id`, `session_id`, and `evidence_quality`.
