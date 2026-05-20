---
title: "AICTX Limitations"
description: "Understand what AICTX does and does not do: repo-local continuity and operational memory, not an autonomous agent or hidden cloud memory service."
---

# Limitations

AICTX is a continuity runtime, not an autonomous coding system.

---

## Agent cooperation

AICTX is strongest when the agent or runner follows the runtime contract.

If the agent does not call prepare/finalize or pass observed facts, AICTX cannot record them.

---

## Signal capture

File, command, test, and error capture depends on explicit runtime signals, wrapped execution, runner support, and user workflow discipline.

Contract compliance also depends on these observed signals. If there is no compatible resume contract or no execution observation, compliance is reported as `not_evaluated`.

---

## Contract compliance

Contract compliance is an audit signal, not proof of correctness.

It can report whether observed execution appears to have followed the resume contract: first action, edit scope, canonical test command, and finalize lifecycle.

It does not:

- sandbox the agent;
- block edits or commands;
- prove code quality;
- infer unobserved files, commands, or tests;
- inspect hidden reasoning;
- know exact command order unless ordered trace data exists.

When orientation-like commands are observed without ordered trace data, AICTX should treat that as an order-unknown warning rather than hard proof of a pre-edit violation.

---

## Work State

Work State is explicit and conservative.

AICTX does not infer hidden intent, hypotheses, discarded paths, or product conclusions from sparse evidence.

Only one active task pointer exists per repo.

---

## RepoMap

RepoMap is optional.

It depends on Tree-sitter support and does not replace semantic understanding.

AICTX works without RepoMap.

## Explainability and entrypoint arbitration

`loaded_context` explains why context was selected for `aictx resume --json`. It is not proof of relevance or correctness, and it does not expose hidden agent reasoning.

The optional entrypoint arbiter is advisory only. It is disabled unless an operator configures an arbiter command through environment variables, and failures fall back to deterministic local ranking.

An arbiter is not an authority system. It must not manage secrets, credentials, service handles, or privileged runtime capabilities. If configured externally, the user or operator is responsible for that command.

---

## Portability

Git-portable continuity is selective, opt-in, and Git-based. It does not sync anything by itself, and committed portable artifacts may still reveal operational context that should be reviewed before sharing.

## Metrics

AICTX reports observed runtime evidence. It does not prove productivity gain, token savings, speed improvement, or code quality improvement.

Contract compliance metrics show whether observed execution aligned with a generated contract; they are not a benchmark.

---

## Bottom line

AICTX makes continuity visible, inspectable, and reusable.

It does not make agents correct, autonomous, or magically persistent.

## MCP limitations

MCP support depends on a compatible client that can launch a local stdio server. AICTX prepares managed config where supported, but CLI fallback remains required for clients without MCP support.
