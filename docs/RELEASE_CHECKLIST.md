# Release checklist

## Release identity

- [ ] `pyproject.toml` version updated
- [ ] `src/aictx/_version.py` updated
- [ ] README documented implementation updated
- [ ] `docs/UPGRADE.md` current runtime updated
- [ ] `CHANGELOG.md` updated
- [ ] tag format is `vX.Y.Z`

---

## Product clarity

- [ ] README explains normal agent-driven workflow
- [ ] README does not make AICTX look like a manual CLI-only tool
- [ ] README is Codex-first, Claude-aware, generic-agent compatible
- [ ] README shows real startup identity format
- [ ] RepoMap has appropriate visibility
- [ ] Install/init flow is documented with example answers
- [ ] Communication mode is documented under init, not install
- [ ] Cleanup is documented
- [ ] Technical overview covers all runtime capabilities
- [ ] Docs distinguish `internal boot` diagnostic output from user-visible startup banner
- [ ] Strategy Memory and Handoffs have dedicated docs if listed as README core concepts
- [ ] Limitations remain honest

---

## Validation

```bash
python -m pytest -q
python -m build
```
