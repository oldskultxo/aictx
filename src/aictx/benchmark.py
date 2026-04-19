from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EXPERIMENTS_BENCHMARK_PATH = Path("experiments/simulated/benchmark.py")
REMOVAL_MESSAGE = (
    "Synthetic benchmark commands were removed from the product/runtime path. "
    "Historical simulated benchmark code lives at experiments/simulated/benchmark.py and is not part of the public CLI."
)


class SyntheticBenchmarkRemovedError(RuntimeError):
    pass


VALID_ARMS = {"A", "B", "C"}


def _error_payload() -> dict[str, Any]:
    return {
        "error": "synthetic_benchmark_removed",
        "message": REMOVAL_MESSAGE,
        "historical_path": EXPERIMENTS_BENCHMARK_PATH.as_posix(),
    }


def run_suite(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    raise SyntheticBenchmarkRemovedError(REMOVAL_MESSAGE)


def build_report(*_args: Any, **_kwargs: Any) -> tuple[dict[str, Any], int]:
    raise SyntheticBenchmarkRemovedError(REMOVAL_MESSAGE)


def load_runs(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
    raise SyntheticBenchmarkRemovedError(REMOVAL_MESSAGE)


def write_benchmark_status(*_args: Any, **_kwargs: Any) -> None:
    raise SyntheticBenchmarkRemovedError(REMOVAL_MESSAGE)


def cli_benchmark_run(_args: Any) -> int:
    print(json.dumps(_error_payload(), indent=2, ensure_ascii=False))
    return 1


def cli_benchmark_report(_args: Any) -> int:
    print(json.dumps(_error_payload(), indent=2, ensure_ascii=False))
    return 1
