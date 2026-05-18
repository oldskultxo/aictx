---
title: "AICTX Quickstart for Operational Continuity"
description: "Start using AICTX to preserve operational continuity across AI coding-agent sessions with the official aictx CLI."
---

# Quickstart

This walkthrough shows the shortest path from setup to visible operational continuity.

AICTX is built around one loop:

```text
resume before work -> work normally -> finalize evidence -> next session continues
```

## 1. Install and initialize

```bash
pip install aictx
aictx install
aictx init
```

Optional check:

```bash
aictx --version
aictx doctor --repo . --json
```

## 2. See what the next agent receives

```bash
aictx resume --repo . --task "continue current work" --json
```

Inspect JSON:

```bash
aictx resume --repo . --task "continue current work" --json | python3 -m json.tool
```

A fresh repo may have little continuity. That is expected. AICTX becomes more useful after work has been finalized and Work State, failures, decisions or handoffs exist.

## 3. Create visible Work State

```bash
aictx task start "Fix login token refresh" --json
aictx task update --json --json-patch '{"next_action":"inspect auth interceptor ordering","active_files":["src/api/client.ts"],"recommended_commands":["pytest -q tests/test_auth.py"]}'
aictx resume --repo . --task "continue token refresh work" --json
```

## 4. Finalize evidence

```bash
aictx finalize --repo . --status success --summary "targeted auth test passed" --json
```

Finalize is what turns one session's work into factual continuity for the next session.

## 5. Inspect Continuity View

```bash
aictx view --repo .
```

Default output:

```text
.aictx/reports/continuity-view.md
.aictx/reports/continuity-map.mmd
```

Not hidden memory. Reviewable operational continuity.

## 6. Optional RepoMap

```bash
pip install "aictx[repomap]"
aictx install --with-repomap
aictx init
aictx map status
aictx map query "auth interceptor"
```

RepoMap is optional. Core continuity works without it.
