# Limitations

This document describes current limits of the real system.

## Runtime limits

- `aictx` depends on the agent following repo instructions and hooks
- different runners may honor those instructions differently
- some runtime/internal commands still exist for compatibility and integration support

## Logging limits

- file tracking is still minimal, so `files_opened` and `files_reopened` may often remain empty
- average file-open metrics in reports may therefore understate actual browsing behavior
- execution logs only contain fields that are currently observable by the runtime

## Strategy memory limits

- strategies are stored only from successful validated executions
- strategy reuse is by exact task type only
- the runtime currently takes the latest matching strategy, not the best-ranked one
- there is no ranking, scoring, or clustering between strategies

## Guidance limits

- `suggest`, `reflect`, and `reuse` are intentionally simple
- `reflect` only checks a small set of real signals from the latest execution log
- no command claims that aictx caused a better result; they only expose observed data

## Reporting limits

- `aictx report real-usage` reports only real aggregates from stored logs and feedback
- if data is missing, metrics may be `null`, `0`, or empty
- there is no built-in baseline-vs-aictx comparison unless explicit real baseline data exists
- the system does not report synthetic improvements, estimated savings, or benchmark-style deltas

## Product limits

- `aictx` does not guarantee faster task completion
- `aictx` does not guarantee fewer file reads
- `aictx` does not guarantee better code quality
- `aictx` is a runtime layer for discipline and reuse, not a guarantee of outcome
