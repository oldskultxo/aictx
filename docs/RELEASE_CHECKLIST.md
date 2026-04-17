# Release checklist

## Product trust

- [ ] README, USAGE, and TECHNICAL_OVERVIEW describe the same product surface
- [ ] README includes honest limitations and demo links
- [ ] `LICENSE` exists
- [ ] `CHANGELOG.md` is updated
- [ ] version stays in `0.x` unless compatibility policy changes

## Runtime integrity

- [ ] `aictx boot --repo <repo>` reports effective communication policy
- [ ] `aictx execution prepare ...` reports the same communication policy for the same repo
- [ ] contradictions between repo prefs and repo state surface as warnings
- [ ] missing data is reported as `unknown` or `not_initialized`

## Validation commands

- [ ] `python3 -m venv .venv`
- [ ] `.venv/bin/pip install -e . pytest build`
- [ ] `make test`
- [ ] `make smoke`
- [ ] `make package-check`

## CI

- [ ] GitHub Actions passes on supported Python versions
- [ ] editable install is exercised in CI
- [ ] smoke flow passes in CI
- [ ] package build passes in CI
