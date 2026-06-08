---
title: "Comparing coding-agent continuity approaches"
description: "Compare repo-local operational continuity with instructions, long context, memory files, vector memory, agent-specific harness memory, and custom agent layers."
---

# Comparing approaches to coding-agent continuity

Use this comparison to decide which memory layer you need. Repo-local operational continuity is different from prompts, long context, memory files, vector memory, and agent-specific harness memory.

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

<div class="continuity-matrix" role="region" aria-label="Coding-agent continuity approach comparison">
<table class="continuity-matrix-table">
  <thead>
    <tr>
      <th scope="col">Capability / outcome</th>
      <th scope="col">Plain instructions</th>
      <th scope="col">Long context / chat history</th>
      <th scope="col">Generic memory files</th>
      <th scope="col">Vector memory</th>
      <th scope="col">Agent-specific harness memory</th>
      <th scope="col">Skills / custom layers</th>
      <th scope="col">AICTX repo-local continuity</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th scope="row">Repo-local by default</th>
      <td data-label="Plain instructions">Yes</td>
      <td data-label="Long context / chat history">No</td>
      <td data-label="Generic memory files">Depends</td>
      <td data-label="Vector memory">Usually no</td>
      <td data-label="Agent-specific harness memory">Usually no</td>
      <td data-label="Skills / custom layers">Depends</td>
      <td data-label="AICTX repo-local continuity">Yes</td>
    </tr>
    <tr>
      <th scope="row">Inspectable by developer</th>
      <td data-label="Plain instructions">Yes</td>
      <td data-label="Long context / chat history">Partial</td>
      <td data-label="Generic memory files">Yes</td>
      <td data-label="Vector memory">Often no</td>
      <td data-label="Agent-specific harness memory">Depends</td>
      <td data-label="Skills / custom layers">Depends</td>
      <td data-label="AICTX repo-local continuity">Yes</td>
    </tr>
    <tr>
      <th scope="row">Directly correctable</th>
      <td data-label="Plain instructions">Yes</td>
      <td data-label="Long context / chat history">Partial</td>
      <td data-label="Generic memory files">Yes</td>
      <td data-label="Vector memory">Often no</td>
      <td data-label="Agent-specific harness memory">Depends</td>
      <td data-label="Skills / custom layers">Depends</td>
      <td data-label="AICTX repo-local continuity">Yes</td>
    </tr>
    <tr>
      <th scope="row">Portable across agents</th>
      <td data-label="Plain instructions">Yes</td>
      <td data-label="Long context / chat history">No</td>
      <td data-label="Generic memory files">Partial</td>
      <td data-label="Vector memory">Depends</td>
      <td data-label="Agent-specific harness memory">Usually no</td>
      <td data-label="Skills / custom layers">Usually no</td>
      <td data-label="AICTX repo-local continuity">Yes</td>
    </tr>
    <tr>
      <th scope="row">Tracks active Work State</th>
      <td data-label="Plain instructions">No</td>
      <td data-label="Long context / chat history">Partial</td>
      <td data-label="Generic memory files">Manual</td>
      <td data-label="Vector memory">Partial</td>
      <td data-label="Agent-specific harness memory">Depends</td>
      <td data-label="Skills / custom layers">Depends</td>
      <td data-label="AICTX repo-local continuity">Yes</td>
    </tr>
    <tr>
      <th scope="row">Tracks failed commands</th>
      <td data-label="Plain instructions">No</td>
      <td data-label="Long context / chat history">Partial</td>
      <td data-label="Generic memory files">Manual</td>
      <td data-label="Vector memory">Partial</td>
      <td data-label="Agent-specific harness memory">Depends</td>
      <td data-label="Skills / custom layers">Depends</td>
      <td data-label="AICTX repo-local continuity">Yes</td>
    </tr>
    <tr>
      <th scope="row">Tracks validation evidence</th>
      <td data-label="Plain instructions">No</td>
      <td data-label="Long context / chat history">Partial</td>
      <td data-label="Generic memory files">Manual</td>
      <td data-label="Vector memory">Partial</td>
      <td data-label="Agent-specific harness memory">Depends</td>
      <td data-label="Skills / custom layers">Depends</td>
      <td data-label="AICTX repo-local continuity">Yes</td>
    </tr>
    <tr>
      <th scope="row">Tracks decisions / handoffs</th>
      <td data-label="Plain instructions">Manual</td>
      <td data-label="Long context / chat history">Partial</td>
      <td data-label="Generic memory files">Manual</td>
      <td data-label="Vector memory">Partial</td>
      <td data-label="Agent-specific harness memory">Depends</td>
      <td data-label="Skills / custom layers">Depends</td>
      <td data-label="AICTX repo-local continuity">Yes</td>
    </tr>
    <tr>
      <th scope="row">Tracks structural repo entry points</th>
      <td data-label="Plain instructions">No</td>
      <td data-label="Long context / chat history">Partial</td>
      <td data-label="Generic memory files">No</td>
      <td data-label="Vector memory">Partial</td>
      <td data-label="Agent-specific harness memory">Depends</td>
      <td data-label="Skills / custom layers">Depends</td>
      <td data-label="AICTX repo-local continuity">Yes, via RepoMap</td>
    </tr>
    <tr>
      <th scope="row">Surfaces relationships visually</th>
      <td data-label="Plain instructions">No</td>
      <td data-label="Long context / chat history">No</td>
      <td data-label="Generic memory files">No</td>
      <td data-label="Vector memory">No</td>
      <td data-label="Agent-specific harness memory">Depends</td>
      <td data-label="Skills / custom layers">Depends</td>
      <td data-label="AICTX repo-local continuity">Yes, via Continuity View</td>
    </tr>
    <tr>
      <th scope="row">Handles stale/superseded context</th>
      <td data-label="Plain instructions">No</td>
      <td data-label="Long context / chat history">No</td>
      <td data-label="Generic memory files">Manual</td>
      <td data-label="Vector memory">Hard to inspect</td>
      <td data-label="Agent-specific harness memory">Depends</td>
      <td data-label="Skills / custom layers">Depends</td>
      <td data-label="AICTX repo-local continuity">Yes, via Continuity Quality</td>
    </tr>
    <tr>
      <th scope="row">Exposes continuity as tools</th>
      <td data-label="Plain instructions">No</td>
      <td data-label="Long context / chat history">No</td>
      <td data-label="Generic memory files">No</td>
      <td data-label="Vector memory">Depends</td>
      <td data-label="Agent-specific harness memory">Yes</td>
      <td data-label="Skills / custom layers">Depends</td>
      <td data-label="AICTX repo-local continuity">Yes, via MCP</td>
    </tr>
    <tr>
      <th scope="row">Requires cloud/backend</th>
      <td data-label="Plain instructions">No</td>
      <td data-label="Long context / chat history">Depends</td>
      <td data-label="Generic memory files">No</td>
      <td data-label="Vector memory">Often yes</td>
      <td data-label="Agent-specific harness memory">Depends</td>
      <td data-label="Skills / custom layers">Depends</td>
      <td data-label="AICTX repo-local continuity">No</td>
    </tr>
    <tr>
      <th scope="row">Survives switching vendor/harness</th>
      <td data-label="Plain instructions">Yes</td>
      <td data-label="Long context / chat history">No</td>
      <td data-label="Generic memory files">Partial</td>
      <td data-label="Vector memory">Depends</td>
      <td data-label="Agent-specific harness memory">No/Depends</td>
      <td data-label="Skills / custom layers">Usually no</td>
      <td data-label="AICTX repo-local continuity">Yes</td>
    </tr>
  </tbody>
</table>
</div>

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

AICTX stores continuity around active Work State, Failure Memory, Handoffs, Decisions, Execution Summary, Execution Contracts, Contract Compliance, optional structural hints, Continuity View, Continuity Quality, and MCP tools/resources/prompts. These artifacts live under the repo-local `.aictx/` runtime area rather than only inside a chat transcript or a vendor harness.

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
