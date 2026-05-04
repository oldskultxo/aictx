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
