# Area memory

AICTX derives a lightweight `area_id` from observed paths.

Current deterministic rules:

- `src/aictx/middleware.py` -> `src/aictx`
- `tests/test_smoke.py` -> `tests/test_smoke.py`
- `docs/USAGE.md` -> `docs/USAGE.md`
- no observed paths -> `unknown`

Area memory is stored in `.aictx/area_memory/areas.json`.

Each area tracks only repo-local observed facts, such as:

- related files
- related tests
- executions count
- strategy count
- failure count

Important behavior:

- area hints are deterministic and local
- they are one signal in continuity and strategy selection, not an absolute router
- `prepare` can start with `prepared_area_id = unknown` when no files are known yet
- `finalize` can recalculate `final_area_id` from observed files/tests and expose `effective_area_id`
