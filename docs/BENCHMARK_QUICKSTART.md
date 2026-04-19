# Benchmark note

The previous A/B/C benchmark flow was removed from the product/runtime path because it generated deterministic simulated metrics rather than measurements from real executions.

## Current status

- `aictx benchmark ...` is no longer part of the public product surface.
- historical simulation code was moved to `experiments/simulated/benchmark.py`
- that code is retained only for historical or experimental reference
- do not use simulated benchmark artifacts as product evidence, demo evidence, or publication material

## What to use instead

For product/runtime evidence, use real execution artifacts under `.ai_context_engine/metrics/` and real wrapped runs.

Until real baseline vs `aictx` comparison tooling exists, prefer explicit `unknown` over inferred performance claims.
