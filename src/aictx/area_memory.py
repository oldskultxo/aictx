from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .state import REPO_ENGINE_DIR, read_json, write_json

AREA_MEMORY_DIR = Path(REPO_ENGINE_DIR) / "area_memory"
AREAS_PATH = AREA_MEMORY_DIR / "areas.json"


def derive_area_id(paths: list[str]) -> str:
    cleaned = [str(path).strip().lstrip("./") for path in paths if str(path).strip()]
    if not cleaned:
        return "unknown"
    first = cleaned[0].split("/")
    if len(first) >= 2 and first[0] in {"src", "tests", "docs"}:
        return "/".join(first[:2])
    return first[0] if first else "unknown"


def load_area_memory(repo_root: Path) -> dict[str, Any]:
    return read_json(repo_root / AREAS_PATH, {"version": 1, "areas": {}})


def _top(counter: dict[str, int], limit: int = 8) -> list[str]:
    return [item for item, _count in Counter(counter).most_common(limit)]


def update_area_memory(repo_root: Path, execution_log: dict[str, Any], *, strategy_stored: bool = False, failure_recorded: bool = False) -> dict[str, Any]:
    files = list(execution_log.get("files_opened", [])) if isinstance(execution_log.get("files_opened"), list) else []
    tests = list(execution_log.get("tests_executed", [])) if isinstance(execution_log.get("tests_executed"), list) else []
    area_id = str(execution_log.get("area_id") or derive_area_id(files + tests))
    memory = load_area_memory(repo_root)
    areas = memory.setdefault("areas", {})
    area = areas.setdefault(
        area_id,
        {
            "area_id": area_id,
            "files": {},
            "tests": {},
            "strategy_count": 0,
            "failure_count": 0,
            "executions": 0,
        },
    )
    area["executions"] = int(area.get("executions", 0) or 0) + 1
    if strategy_stored:
        area["strategy_count"] = int(area.get("strategy_count", 0) or 0) + 1
    if failure_recorded:
        area["failure_count"] = int(area.get("failure_count", 0) or 0) + 1
    for path in files:
        area.setdefault("files", {})[path] = int(area.setdefault("files", {}).get(path, 0) or 0) + 1
    for test in tests:
        area.setdefault("tests", {})[test] = int(area.setdefault("tests", {}).get(test, 0) or 0) + 1
    area["related_files"] = _top(area.get("files", {}))
    area["related_tests"] = _top(area.get("tests", {}))
    write_json(repo_root / AREAS_PATH, memory)
    return area


def area_hints(repo_root: Path, area_id: str) -> dict[str, Any]:
    area = load_area_memory(repo_root).get("areas", {}).get(area_id, {})
    return {
        "area_id": area_id,
        "related_files": list(area.get("related_files", [])) if isinstance(area.get("related_files"), list) else [],
        "related_tests": list(area.get("related_tests", [])) if isinstance(area.get("related_tests"), list) else [],
        "area_strategy_count": int(area.get("strategy_count", 0) or 0),
        "area_failure_count": int(area.get("failure_count", 0) or 0),
    }

