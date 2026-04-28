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
- optional: Codex and/or Claude if you want runner integrations

---

## Fast path

From inside the target repository:

```bash
pip install aictx
aictx install
aictx init
```

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

Current install decisions:

| Setup decision | Example answer | Effect |
|---|---|---|
| Continue install | `Y` | Applies global/runtime setup |
| Workspace id | `default` | Stores active workspace identity |
| Workspace root | `/Users/me/dev` or empty | Defines workspace root when provided |
| Cross-project mode | default `workspace` | Controls workspace-level cross-project behavior |
| Global Codex install | `--install-codex-global` | Allows AICTX-managed global Codex files |
| RepoMap request | `--with-repomap` | Marks RepoMap as requested in global config |
| Dry run | `--dry-run` | Shows intended changes without applying them |
| Non-interactive mode | `--yes` | Uses defaults and skips confirmation prompts |

Representative interactive flow:

```text
aictx install

This will prepare AICTX runtime files and configuration.
Proceed with install? [Y/n]: y

Workspace id [default]: default
Workspace root []: /Users/me/dev

Select cross-project mode:
1. workspace (default)
2. isolated
Select option number: 1
```

Recommended simple answer pattern:

```text
Press Enter for defaults unless you specifically want global Codex integration, RepoMap, or custom workspace behavior.
```

---

## `aictx init`: repo-local setup

`aictx init` prepares one repository.

This is where repo-local runtime behavior is configured, including communication mode.

Current init decisions:

| Setup decision | Example answer | Effect |
|---|---|---|
| Confirm repo initialization | `Y` | Allows `.aictx/` and repo instruction files |
| Repo path | current directory or `--repo <path>` | Selects target repository |
| Register repo | default yes unless `--no-register` | Adds repo to AICTX registry for cleanup/uninstall |
| Communication mode | `caveman_full` | Stores repo preference under `.aictx/memory/user_preferences.json` |
| Repo runner integrations | `Y` | Creates/updates `AGENTS.md`, `CLAUDE.md`, `.claude/*` |
| Git-portable continuity | default `N` for new repos | Switches the AICTX-managed `.gitignore` policy and writes `.aictx/continuity/portability.json` |
| RepoMap initialization | default when globally requested | Writes/refreshes `.aictx/repo_map/*` if available |

Representative interactive flow:

```text
aictx init

This will initialize AICTX in the current repository.
Proceed with repo initialization? [Y/n]: y

Select communication mode:
1. disabled
2. caveman_lite
3. caveman_full (default)
4. caveman_ultra
Select option number: 3

Register this repository for AICTX cleanup/uninstall? [Y/n]: y
Install/update repo runner integrations? [Y/n]: y
```

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
| `disabled` | No special communication layer |
| `caveman_lite` | Slightly compressed communication |
| `caveman_full` | Strong compact communication mode; default |
| `caveman_ultra` | Very aggressive compression |

If unsure, use the default.

---

## What files may appear after init

Common repo-local files:

```text
.aictx/
AGENTS.md
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
aictx install --with-repomap
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
aictx next --json
aictx internal execution prepare ...
aictx internal execution finalize ...
```

The agent must cooperate with the runtime contract for best results.

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
