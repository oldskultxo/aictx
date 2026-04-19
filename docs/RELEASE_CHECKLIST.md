# Release checklist

## Release identity

- [ ] target version is set (for example `0.4.0` for the current public beta release)
- [ ] release remains intentionally `0.x`
- [ ] tag format is `vX.Y.Z`
- [ ] changelog entry is ready before tagging

## Product trust

- [ ] README, USAGE, and TECHNICAL_OVERVIEW describe the same product surface
- [ ] README includes honest limitations and demo links
- [ ] README and USAGE show the public `pip install aictx` flow
- [ ] `LICENSE` exists
- [ ] `CHANGELOG.md` is updated
- [ ] version stays in `0.x` unless compatibility policy changes

## Runtime integrity

- [ ] `aictx internal boot --repo <repo>` reports effective communication policy
- [ ] `aictx internal execution prepare ...` reports the same communication policy for the same repo
- [ ] contradictions between repo prefs and repo state surface as warnings
- [ ] missing data is reported as `unknown` or `not_initialized`

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

## CI

- [ ] GitHub Actions passes on supported Python versions
- [ ] editable install is exercised in CI
- [ ] smoke flow passes in CI
- [ ] package build passes in CI
- [ ] clean-wheel install validation passes in CI

## Publish

- [ ] push tag `vX.Y.Z`
- [ ] GitHub Release is created from the tag
- [ ] PyPI publish workflow succeeds
- [ ] `pip install aictx==X.Y.Z` works in a fresh venv
