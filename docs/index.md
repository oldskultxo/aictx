# AICTX - Repo-Local Continuity Runtime for Coding Agents

Welcome to AICTX documentation. This site is your complete guide to understanding, installing, and using AICTX.

## What is AICTX?

**AICTX** helps coding agents maintain continuity across sessions. Instead of starting cold each time, agents resume from where they left off with:

- ✅ Active task state and next actions
- ✅ Known failures and workarounds  
- ✅ Successful strategies from prior work
- ✅ Architectural decisions and context
- ✅ Repo-local evidence of progress

## Quick Navigation

### Getting Started
- **[Installation](INSTALLATION.md)** - Set up AICTX in your repository
- **[Quickstart](QUICKSTART.md)** - Get running in 5 minutes
- **[Demo](DEMO.md)** - See real continuity in action

### Understanding AICTX
- **[Technical Overview](TECHNICAL_OVERVIEW.md)** - How AICTX works internally
- **[Work State](WORK_STATE.md)** - Preserving task progress
- **[Failure Memory](FAILURE_MEMORY.md)** - Learning from mistakes
- **[Strategy Memory](STRATEGY_MEMORY.md)** - Reusing what works

### Advanced Topics
- **[RepoMap](REPOMAP.md)** - Structural repository mapping
- **[Handoffs & Decisions](HANDOFFS.md)** - Explicit context transfer
- **[Execution Contracts](EXECUTION_CONTRACTS.md)** - Compliance and auditing
- **[API Usage](USAGE.md)** - Detailed command reference

### Operations
- **[Doctor Diagnostics](DOCTOR.md)** - Read-only support checks and strict release-readiness mode
- **[Safety](SAFETY.md)** - Trust and security considerations
- **[Limitations](LIMITATIONS.md)** - What AICTX doesn't do
- **[Cleanup](CLEANUP.md)** - Maintaining your continuity store
- **[Upgrade Guide](UPGRADE.md)** - Moving to new versions

## Supported Agents

AICTX works with:
- 🤖 **Codex** - Full integration with repo instructions
- 🐙 **GitHub Copilot** - Standard repo-wide custom instructions via `.github/copilot-instructions.md`
- 🧠 **Claude** - Deep Claude.ai workspace support
- 🔧 **Generic agents** - CLI/JSON compatible with any coding agent

## Why AICTX?

Without AICTX:
```
Session 1 → Do work → Chat ends
Session 2 → Start cold → Rediscover repo → Repeat mistakes
```

With AICTX:
```
Session 1 → Do work → Record continuity
Session 2 → Resume from capsule → Continue immediately
```

See the [Demo](DEMO.md) for measured results.

## Installation

```bash
pip install aictx
aictx install
aictx init
```

Then use your coding agent normally. AICTX handles continuity automatically.

See [Installation](INSTALLATION.md) for details.

## Quick Example

Resume from last session:
```bash
aictx resume --repo . --task "continue parser work" --json
```

Returns continuity context:
```
Resuming: parser edge cases
Last progress: BLOCKED status added
Next: expand tests/test_parser.py
Known failure: pytest unavailable outside .venv
Suggested command: .venv/bin/python -m pytest -q
```

Then at the end of your session:
```bash
aictx finalize --repo . --status success --summary "Parser now handles all edge cases" --json
```

## Community

- 💬 [Discussions](https://github.com/oldskultxo/aictx/discussions) - Share ideas and get help
- 🐛 [Issues](https://github.com/oldskultxo/aictx/issues) - Report bugs or request features
- 📝 [Contributing](https://github.com/oldskultxo/aictx/blob/main/CONTRIBUTING.md) - Help build AICTX

## License

MIT License - See [LICENSE](https://github.com/oldskultxo/aictx/blob/main/LICENSE)

---

**Ready to get started?** → [Installation Guide](INSTALLATION.md)
