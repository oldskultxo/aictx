---
title: "AICTX Release Checklist"
description: "Checklist for preparing AICTX releases, including version metadata, docs, PyPI identity, and release validation."
---

# Release checklist

## Release identity

- [ ] `pyproject.toml` version updated
- [ ] `src/aictx/_version.py` updated
- [ ] README documented implementation updated
- [ ] `docs/UPGRADE.md` current runtime updated
- [ ] `CHANGELOG.md` updated
- [ ] official website / repository / PyPI package links validated
- [ ] tag format is `vX.Y.Z`

---

## Product clarity

- [ ] README explains normal agent-driven workflow
- [ ] README does not make AICTX look like a manual CLI-only tool
- [ ] README is Codex-first, GitHub Copilot-aware, Claude-aware, generic-agent compatible
- [ ] README shows real startup identity format
- [ ] RepoMap has appropriate visibility
- [ ] Install/init flow is documented with example answers
- [ ] Legacy communication-mode preferences are normalized safely and not exposed in first-run setup
- [ ] Cleanup is documented
- [ ] Technical overview covers all runtime capabilities
- [ ] Continuity View docs, README placement, docs homepage card, sitemap entry, and `llms*.txt` references are current
- [ ] `aictx doctor --repo . --release-readiness --json` reflects release diagnostics without modifying repo state
- [ ] Docs distinguish `internal boot` diagnostic output from user-visible startup banner
- [ ] Internal strategy/area hints are not exposed as primary docs or README core concepts
- [ ] Limitations remain honest

---

- [ ] `git check-ignore` tests cover portable/local-only artifacts
- [ ] `docs/PORTABILITY.md` updated
- [ ] `aictx portability status --repo . --json` documented
- [ ] `aictx portability compact --repo . --apply --json` documented
- [ ] `aictx init --yes` does not enable portability by default
- [ ] portability can be enabled after local-only init
- [ ] portability can be disabled after being enabled
- [ ] legacy messages mute/unmute/status remain compatible if still exposed through advanced paths
- [ ] default message mode is unmuted
- [ ] muted mode suppresses startup banner
- [ ] muted mode suppresses agent summary text
- [ ] explicit command output still works

## Validation

```bash
python -m pytest -q
python -m build
aictx doctor --repo . --release-readiness --json
```
