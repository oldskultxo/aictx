---
title: "Comparing coding-agent continuity approaches"
description: "Compare repo-local operational continuity with instructions, long context, memory files, vector memory, agent-specific harness memory, and custom agent layers."
---

# Comparing approaches to coding-agent continuity

Why repo-local operational continuity is different from prompts, long context, memory files, vector memory, and agent-specific harness memory.

Coding agents do not only need more context. They need continuity:

- what was the active task?
- what changed last session?
- what failed?
- what validation was expected?
- which architectural decisions matter?
- which files should be checked first?
- which old notes are stale or superseded?

This comparison is not about which approach stores more text.

It compares whether an approach helps the next coding-agent session continue useful repo work with less rediscovery, fewer repeated mistakes, clearer validation expectations, and more inspectable state.

## The problem: continuation, not just context

A coding session leaves behind operational state. Some of that state is stable project knowledge, but much of it is execution state: active Work State, failed commands, validation evidence, recent decisions, handoffs, and the next likely files to inspect.

Plain instructions, long context, memory files, vector retrieval, harness memory, and custom layers can all help. They optimize for different outcomes. The question is whether the next session can continue repo work from the last known useful state without guessing what is current, stale, missing, or already tried.

## Comparison matrix

| Capability / outcome | Plain instructions | Long context / chat history | Generic memory files | Vector memory | Agent-specific harness memory | Skills / custom layers | AICTX repo-local continuity |
|---|---:|---:|---:|---:|---:|---:|---:|
| Repo-local by default | Yes | No | Depends | Usually no | Usually no | Depends | Yes |
| Inspectable by developer | Yes | Partial | Yes | Often no | Depends | Depends | Yes |
| Directly correctable | Yes | Partial | Yes | Often no | Depends | Depends | Yes |
| Portable across agents | Yes | No | Partial | Depends | Usually no | Usually no | Yes |
| Tracks active Work State | No | Partial | Manual | Partial | Depends | Depends | Yes |
| Tracks failed commands | No | Partial | Manual | Partial | Depends | Depends | Yes |
| Tracks validation evidence | No | Partial | Manual | Partial | Depends | Depends | Yes |
| Tracks decisions / handoffs | Manual | Partial | Manual | Partial | Depends | Depends | Yes |
| Tracks structural repo entry points | No | Partial | No | Partial | Depends | Depends | Yes, via RepoMap |
| Surfaces relationships visually | No | No | No | No | Depends | Depends | Yes, via Continuity View |
| Handles stale/superseded context | No | No | Manual | Hard to inspect | Depends | Depends | Yes, via Continuity Quality |
| Exposes continuity as tools | No | No | No | Depends | Yes | Depends | Yes, via MCP |
| Requires cloud/backend | No | Depends | No | Often yes | Depends | Depends | No |
| Survives switching vendor/harness | Yes | No | Partial | Depends | No/Depends | Usually no | Yes |

## What each approach is good at

Plain instructions are excellent for stable project rules, but they are not enough for changing execution state. They tell the agent how to work in the repo, not what happened in the last run.

Long context helps during one session, but it does not create durable repo-level continuity. It is useful for in-session awareness and weaker when work spans multiple agent sessions or harnesses.

Generic memory files are inspectable, but without lifecycle and validation signals they can become manual notes that agents may or may not use correctly.

Vector memory can retrieve related notes, but it often makes it harder to inspect exactly what was stored, why it was retrieved, and whether it is still current.

Agent-specific harness memory can be powerful, but it may not survive switching tools. It optimizes for one runtime's model of memory and execution.

Skills and custom layers can encode useful behaviors, but they are often tied to one agent or one runtime. They are strongest for reusable procedures, conventions, and tool use patterns.

AICTX focuses on repo-local operational continuity: the state of the work, not just memories about the project.

## Where AICTX fits

AICTX optimizes for repo-level operational continuity.

It is strongest when the same repository is worked on across repeated agent sessions, failed commands and validation expectations matter, and the user wants inspectable repo-local artifacts that can be reviewed or corrected.

AICTX stores continuity around active Work State, Failure Memory, Strategy Memory, Handoffs, Decisions, Execution Summary, Execution Contracts, Contract Compliance, RepoMap, Continuity View, Continuity Quality, and MCP tools/resources/prompts. These artifacts live under the repo-local `.aictx/` runtime area rather than only inside a chat transcript or a vendor harness.

That makes AICTX useful when:

- the agent should continue from actual Work State instead of chat memory;
- previous failures and validation expectations should be visible before rerunning commands;
- stale or superseded context should be surfaced instead of hidden;
- structural entry points should guide the first files to inspect;
- continuity should be available through CLI, MCP, and generated agent instructions;
- teams want continuity that can survive switching agents or harnesses.

AICTX does not replace stable instructions, long context, skills, or vector retrieval. It complements them by focusing on the operational state needed to continue repo work.

## Where AICTX is not the right tool

AICTX is not the best fit when:

- the task is a one-off prompt;
- there is no repository;
- all continuity is already handled inside one vendor harness and portability does not matter;
- the user only wants personal cross-app memory;
- the user expects a cloud-hosted personal memory product;
- the user does not want repo-local artifacts.

It is also not a benchmark system, an autonomous coding agent, or a replacement for human review. Its goal is to make continuity inspectable and operational for coding-agent work in a repository.

## What to measure

Useful measurement is not:

```md
how much memory is stored
```

The useful measurement is whether the next session:

- opens fewer irrelevant files;
- repeats fewer failed commands;
- reaches the first useful edit faster;
- preserves validation expectations;
- continues from the previous Work State;
- avoids treating stale context as current truth;
- produces fewer “what were we doing?” interruptions;
- can be reviewed/corrected by the developer.

These are the kinds of outcomes a serious comparison should measure.
