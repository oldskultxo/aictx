# RepoMap

RepoMap is AICTX’s optional structural lookup layer.

It helps answer:

```text
Where should the agent look first?
```

Work State tells the agent what was happening. RepoMap helps locate relevant files and symbols.

---

## What RepoMap does

When enabled, RepoMap can maintain a lightweight structural map of a repository using Tree-sitter support.

It can expose:

- indexed files;
- indexed symbols;
- structural query matches;
- refresh status;
- provider availability.

Commands:

```bash
aictx map status
aictx map refresh
aictx map query "startup banner"
```

---

## Installation

```bash
pip install "aictx[repomap]"
aictx install --with-repomap
aictx init
```

Check status:

```bash
aictx map status
```

---

## Why it matters

Agents often spend time rediscovering where relevant code lives.

RepoMap gives AICTX a structural source for entry-point hints:

```text
Work State -> continue this task.
Failure Memory -> avoid this known problem.
RepoMap -> start looking here.
```

---

## Runtime artifacts

RepoMap may create:

```text
.aictx/repo_map/config.json
.aictx/repo_map/manifest.json
.aictx/repo_map/index.json
.aictx/repo_map/status.json
```

If Tree-sitter support is unavailable, RepoMap can remain disabled or unavailable while the rest of AICTX still works.

---

## Limits

RepoMap:

- is optional;
- depends on Tree-sitter support;
- does not guarantee token savings;
- does not replace Work State or Failure Memory;
- is a structural hint source, not semantic understanding;
- may preserve last-known state when refresh is partial.
