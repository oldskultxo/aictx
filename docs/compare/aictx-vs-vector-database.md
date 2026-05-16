---
title: "AICTX vs Vector Databases"
description: "Compare vector databases with AICTX repo-local operational memory for coding agents, including work state, failure memory, and handoffs."
---

# AICTX vs Vector Databases

Vector databases retrieve semantically similar chunks. AICTX stores operational execution evidence and continuity for coding agents.

AICTX is not a vector database. Its memory is repo-local, inspectable, and focused on what happened during work.

## The difference

| Capability | Vector database | AICTX |
| --- | --- | --- |
| Semantic chunk retrieval | Yes | Not the main role |
| Active task Work State | Custom-built | Built in |
| Failure memory | Custom-built | Built in |
| Handoff memory | Custom-built | Built in |
| Local inspectable artifacts | Depends | Yes |
| Resume/finalize lifecycle | No by default | Yes |

## When a vector database is useful

A vector database can help retrieve large knowledge bases or semantic document chunks.

## When AICTX is useful

AICTX is useful when a coding agent needs operational continuity: current task state, known failures, decisions, handoffs, and execution summaries.

Related docs:
- [Operational memory](/concepts/operational-memory.html)
- [Failure Memory](/FAILURE_MEMORY.html)
- [Technical overview](/TECHNICAL_OVERVIEW.html)
- [Official AICTX project identity](/OFFICIAL_PROJECT.html)
