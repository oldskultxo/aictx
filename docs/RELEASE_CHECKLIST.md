# Release checklist

## Release identity

- [ ] target version is intentionally set in `pyproject.toml`
- [ ] tag format is `vX.Y.Z`
- [ ] `CHANGELOG.md` is updated before tagging
- [ ] relevant upgrade notes are reflected in `docs/UPGRADE.md`

## Product trust

- [ ] README, `docs/USAGE.md`, and `docs/TECHNICAL_OVERVIEW.md` describe the same public surface
- [ ] limitations are honest and current
- [ ] continuity/runtime summary behavior documented in `docs/EXECUTION_SUMMARY.md` matches shipped behavior
- [ ] optional RepoMap docs match current CLI flags and limits

## Runtime integrity

- [ ] `aictx internal boot --repo <repo>` succeeds
- [ ] `aictx internal execution prepare ...` and `finalize ...` expose current classification/runtime fields
- [ ] startup banner and final summary policies match runner instructions
- [ ] missing data still surfaces as `unknown` / empty rather than invented values

## Validation commands

- [ ] `python3 -m venv .venv`
- [ ] `.venv/bin/pip install -e . pytest build`
- [ ] `make test`
- [ ] `make smoke`
- [ ] `make package-check`
- [ ] `python -m build`
- [ ] install clean wheel in a fresh venv
- [ ] `aictx --help` works from the clean wheel install
- [ ] `aictx init --repo <tmp> --yes --no-register` works from the clean wheel install
- [ ] `aictx internal boot --repo <tmp>` works from the clean wheel install
- [ ] optional RepoMap install path is validated when relevant

## CI and publish

- [ ] GitHub Actions pass on supported Python versions
- [ ] editable install is exercised in CI
- [ ] smoke flow passes in CI
- [ ] package build passes in CI
- [ ] tag-triggered release/publish workflows are ready
- [ ] `pip install aictx==X.Y.Z` works in a fresh venv after publish
