---
title: "Install AICTX for Repo-Local Coding-Agent Memory"
description: "Install and initialize the official Python `aictx` CLI for repo-local continuity, operational memory, and coding-agent handoffs."
---

# Installation

This guide explains the setup flow and what AICTX asks during installation and repo initialization.

The normal product experience is:

```text
install -> init -> use your coding agent normally
```

Manual AICTX commands are mainly for inspection, debugging, demos, and advanced integrations.

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

For CI, demos, tests, or scripted installation:

```bash
aictx install --yes
aictx init --repo . --yes
```

Demo/temporary repo without registering:

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

Default interactive setup is intentionally simple for non-advanced users. It uses the current defaults for workspace id, workspace root, cross-project mode, and global Codex integration. It asks only whether to enable recommended RepoMap support using Tree-sitter.

Default interactive flow:

```text
aictx install

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
| Global Codex install | off | `--install-codex-global` |
| RepoMap request | prompted, default `Y` | `--with-repomap`, `--yes --with-repomap`, or `--manual` |
| Dry run | off | `--dry-run` |
| Non-interactive mode | no prompts, safe defaults | `--yes` |
| Full interactive mode | off | `--manual` |

`--yes` still skips prompts and keeps safe defaults. To request RepoMap non-interactively, use:

```bash
aictx install --yes --with-repomap
```

---

## `aictx init`: repo-local setup

`aictx init` prepares one repository.

This is where repo-local runtime behavior is configured, including communication mode.

Default interactive setup assumes the current defaults for `.gitignore`, workspace registration, portable continuity, and scaffold creation. It asks only for communication mode.

Default interactive flow:

```text
aictx init

Using defaults for .gitignore, workspace registration, portable continuity and scaffold creation.

Communication modes:
- disabled: No special communication layer; agents answer normally.
- caveman_lite: Light compact mode; keeps explanations but reduces chatter.
- caveman_full: Strong compact mode; recommended if you want less runtime noise.
- caveman_ultra: Aggressive compression; shortest responses, least prose.

Select default communication mode for this repo:
1. disabled (default)
2. caveman_lite
3. caveman_full
4. caveman_ultra
Select option number: 1
```

Advanced users can keep the full setup flow with `--manual`:

```text
aictx init --manual

Write .gitignore entries if missing? [Y/n]: y
Register this repo in the active workspace? [Y/n]: y
Enable AICTX git-portable continuity? [y/N]: n
Select default communication mode for this repo:
1. disabled (default)
2. caveman_lite
3. caveman_full
4. caveman_ultra
Select option number: 1
Initialize full starter scaffold now? [Y/n]: y
```

Init controls:

| Setup decision | Default/simple behavior | Advanced control |
|---|---|---|
| Repo path | current directory | `--repo <path>` |
| Write `.gitignore` entries | yes unless `--no-gitignore` | `--manual` or `--no-gitignore` |
| Register repo | yes unless `--no-register` | `--manual` or `--no-register` |
| Git-portable continuity | disabled for new repos unless opted in | `--portable-continuity`, `--no-portable-continuity`, or `--manual` |
| Communication mode | prompted, default `disabled` | interactive selection |
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

Demo/test setup without registry updates:

```bash
aictx init --repo . --yes --no-register
```

---

## Communication mode

Communication mode is repo-local.

It belongs to `aictx init`, because it is persisted in repo user preferences and then loaded into the repo runtime state.

Available modes:

| Mode | Intended use |
|---|---|
| `disabled` | No special communication layer; default |
| `caveman_lite` | Light compact mode; keeps explanations but reduces chatter |
| `caveman_full` | Strong compact mode; recommended if you want less runtime noise |
| `caveman_ultra` | Aggressive compression; shortest responses, least prose |

If unsure, use the default. Choose `caveman_full` only if you want AICTX to ask supported agents for compact runtime communication.

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

Optional global Codex support:

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

AICTX is unmuted by default after init. Use `aictx messages mute` if you want to suppress automatic startup and summary messages.

Manual inspection commands:

```bash
aictx next
aictx task status --json
aictx map status
aictx report real-usage
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

`aictx install` prepares local stdio MCP support by default with profile `full`. Use `aictx install --no-mcp` to opt out, or `aictx install --mcp-profile readonly|standard|full` to choose a profile.

`aictx init` writes repo-local AICTX-managed MCP config by default. Use `aictx init --no-mcp` to skip that config.
