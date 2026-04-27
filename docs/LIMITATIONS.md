# Limitations

AICTX is a continuity runtime, not an autonomous coding system.

---

## Agent cooperation

AICTX is strongest when the agent or runner follows the runtime contract.

If the agent does not call prepare/finalize or pass observed facts, AICTX cannot record them.

---

## Signal capture

File, command, test, and error capture depends on explicit runtime signals, wrapped execution, runner support, and user workflow discipline.

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

## Metrics

AICTX reports observed runtime evidence. It does not prove productivity gain, token savings, speed improvement, or code quality improvement.

---

## Bottom line

AICTX makes continuity visible, inspectable, and reusable.

It does not make agents correct, autonomous, or magically persistent.
