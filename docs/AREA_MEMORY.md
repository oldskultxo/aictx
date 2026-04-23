# Area memory

AICTX derives lightweight repository areas from observed paths, for example:

- `src/aictx/middleware.py` -> `src/aictx`
- `tests/test_smoke.py` -> `tests/test_smoke.py` parent bucket `tests/test_smoke.py` only when no broader known prefix applies

Area memory is stored in `.aictx/area_memory/areas.json` and tracks common files, tests, failures, and strategy counts per area.

Area hints are deterministic and local. They are used as one signal in strategy selection, not as an absolute routing rule.
