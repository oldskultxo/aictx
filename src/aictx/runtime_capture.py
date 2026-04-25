from __future__ import annotations

import subprocess
import re
from pathlib import Path
from typing import Any

SIGNAL_FIELDS = [
    "files_opened",
    "files_edited",
    "files_reopened",
    "commands_executed",
    "tests_executed",
    "notable_errors",
]


def normalize_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    seen: set[str] = set()
    items: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in seen:
            items.append(text)
            seen.add(text)
    return items


def command_text(command: list[str]) -> str:
    return " ".join(str(part) for part in command if str(part).strip()).strip()


def infer_tests_from_commands(commands: list[str]) -> list[str]:
    tests: list[str] = []
    patterns = [
        r"\bpytest\b",
        r"\bpython(?:3(?:\.\d+)?)?\s+-m\s+pytest\b",
        r"\bunittest\b",
        r"\bmake\s+[^;&|]*\btest\b",
        r"\bnpm\s+(?:run\s+)?test\b",
        r"\bpnpm\s+(?:run\s+)?test\b",
        r"\byarn\s+(?:run\s+)?test\b",
        r"\btox\b",
        r"\bgo\s+test\b",
        r"\bcargo\s+(?:test|nextest)\b",
        r"\bdotnet\s+test\b",
        r"\bmix\s+test\b",
        r"\btest_[A-Za-z0-9_./-]+",
    ]
    for command in commands:
        text = str(command or "").strip()
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
            tests.append(text)
    return normalize_list(tests)


def notable_errors_from_output(exit_code: int, stdout: str = "", stderr: str = "") -> list[str]:
    lines = [line.strip() for line in f"{stderr}\n{stdout}".splitlines() if line.strip()]
    if exit_code == 0 and not lines:
        return []
    benign_patterns = [
        r"\b0 failed\b",
        r"\b0 errors?\b",
        r"\bno errors?\b",
        r"\bpassed\b",
        r"\bsuccess(?:ful|fully)?\b",
    ]
    interesting = [
        line
        for line in lines
        if any(token in line.lower() for token in ["error", "failed", "failure", "traceback", "exception", "assert"])
        and not any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in benign_patterns)
    ]
    if exit_code == 0:
        return normalize_list(interesting[-3:])
    return normalize_list((interesting or lines)[-3:])


def git_status_files(repo: Path) -> list[str]:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return []
    if proc.returncode != 0:
        return []
    files: list[str] = []
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        files.append(line[3:].strip())
    return normalize_list(files)


def changed_files_between(before: list[str], after: list[str]) -> list[str]:
    before_set = set(before)
    return normalize_list([path for path in after if path not in before_set])


def build_capture(payload: dict[str, Any], *, runtime_observed: dict[str, list[str]] | None = None) -> dict[str, Any]:
    observed = runtime_observed or {}
    capture: dict[str, Any] = {"provenance": {}}
    for field in SIGNAL_FIELDS:
        explicit = normalize_list(payload.get(field))
        runtime_values = normalize_list(observed.get(field))
        if explicit:
            capture[field] = explicit
            capture["provenance"][field] = "explicit"
        elif runtime_values:
            capture[field] = runtime_values
            capture["provenance"][field] = "runtime_observed"
        else:
            capture[field] = []
            capture["provenance"][field] = "unknown"
    if not capture["tests_executed"]:
        inferred = infer_tests_from_commands(capture["commands_executed"])
        if inferred:
            capture["tests_executed"] = inferred
            capture["provenance"]["tests_executed"] = "heuristic"
    return capture
