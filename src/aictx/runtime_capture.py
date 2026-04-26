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
    "error_events",
]

ERROR_EVENT_FIELDS = [
    "toolchain",
    "phase",
    "severity",
    "message",
    "code",
    "file",
    "line",
    "command",
    "exit_code",
    "fingerprint",
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


def _slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return text or "unknown"


def _phase_from_command(command: str) -> str:
    text = str(command or "").lower()
    if any(token in text for token in [" test", "pytest", "jest", "vitest", "go test", "cargo test", "dotnet test", "mvn test", "gradle test"]):
        return "test"
    if any(token in text for token in ["lint", "eslint", "ruff", "flake8", "rubocop", "phpstan"]):
        return "lint"
    if any(token in text for token in ["mypy", "tsc", "typecheck", "type-check", "pyright"]):
        return "typecheck"
    if any(token in text for token in ["build", "compile", "cargo check", "go build", "javac", "gcc", "clang", "dotnet build", "mvn package", "gradle build"]):
        return "build"
    return "runtime"


def _toolchain_from_command(command: str) -> str:
    text = str(command or "").lower()
    if any(token in text for token in ["pytest", "python", "mypy", "ruff", "pyright"]):
        return "python"
    if any(token in text for token in ["npm", "pnpm", "yarn", "node", "jest", "vitest", "tsc", "eslint"]):
        return "javascript"
    if "cargo" in text or "rustc" in text:
        return "rust"
    if re.search(r"\bgo\s+", text):
        return "go"
    if any(token in text for token in ["java", "javac", "mvn", "gradle"]):
        return "java"
    if "dotnet" in text:
        return "dotnet"
    if any(token in text for token in ["gcc", "clang", "cmake", "make"]):
        return "c_cpp"
    if "ruby" in text or "bundle" in text:
        return "ruby"
    if "php" in text or "composer" in text:
        return "php"
    return "unknown"


def _event(
    *,
    toolchain: str,
    phase: str,
    message: str,
    command: str,
    exit_code: int,
    severity: str = "error",
    code: str = "",
    file: str = "",
    line: str | int = "",
) -> dict[str, Any]:
    clean_message = str(message or "").strip()
    clean_file = str(file or "").strip()
    clean_code = str(code or "").strip()
    line_text = str(line or "").strip()
    fingerprint = _slug(":".join([toolchain, phase, clean_code, clean_file, clean_message[:160]]))[:96]
    return {
        "toolchain": str(toolchain or "unknown"),
        "phase": str(phase or "runtime"),
        "severity": str(severity or "error"),
        "message": clean_message[:500],
        "code": clean_code,
        "file": clean_file,
        "line": line_text,
        "command": str(command or "").strip(),
        "exit_code": int(exit_code),
        "fingerprint": fingerprint,
    }


def normalize_error_events(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, dict):
            continue
        event = {field: raw.get(field, "") for field in ERROR_EVENT_FIELDS}
        message = str(event.get("message") or "").strip()
        if not message:
            continue
        try:
            event["exit_code"] = int(event.get("exit_code") or 0)
        except (TypeError, ValueError):
            event["exit_code"] = 0
        for field in ("toolchain", "phase", "severity", "code", "file", "line", "command", "fingerprint"):
            event[field] = str(event.get(field) or "").strip()
        if not event["toolchain"]:
            event["toolchain"] = "unknown"
        if not event["phase"]:
            event["phase"] = "runtime"
        if not event["severity"]:
            event["severity"] = "error"
        if not event["fingerprint"]:
            event["fingerprint"] = _slug(":".join([event["toolchain"], event["phase"], event["code"], event["file"], message[:160]]))[:96]
        key = str(event["fingerprint"])
        if key in seen:
            continue
        seen.add(key)
        event["message"] = message[:500]
        events.append(event)
    return events[:8]


def notable_errors_from_events(events: list[dict[str, Any]]) -> list[str]:
    rendered: list[str] = []
    for event in normalize_error_events(events)[:3]:
        prefix = f"{event.get('toolchain')}:{event.get('phase')}"
        code = str(event.get("code") or "").strip()
        location = str(event.get("file") or "").strip()
        line = str(event.get("line") or "").strip()
        if location and line:
            location = f"{location}:{line}"
        details = " ".join(part for part in [code, location, str(event.get("message") or "").strip()] if part)
        rendered.append(f"{prefix}: {details}".strip())
    return normalize_list(rendered)


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


def error_events_from_output(exit_code: int, stdout: str = "", stderr: str = "", command: str = "") -> list[dict[str, Any]]:
    text = f"{stderr}\n{stdout}"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    phase = _phase_from_command(command)
    events: list[dict[str, Any]] = []
    matched_lines: set[int] = set()

    patterns: list[tuple[str, str, re.Pattern[str]]] = [
        ("typescript", "typecheck", re.compile(r"^(?P<file>[^()\s][^(]*?)\((?P<line>\d+),(?P<col>\d+)\):\s+error\s+(?P<code>TS\d+):\s+(?P<msg>.+)$")),
        ("pyright", "typecheck", re.compile(r"^(?P<file>[^:]+\.py):(?P<line>\d+):(?P<col>\d+)\s+-\s+error:\s+(?P<msg>.+?)\s+\((?P<code>[^)]+)\)$")),
        ("mypy", "typecheck", re.compile(r"^(?P<file>[^:]+\.py):(?P<line>\d+):\s+error:\s+(?P<msg>.+?)(?:\s+\[(?P<code>[^\]]+)\])?$")),
        ("ruff", "lint", re.compile(r"^(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+):\s+(?P<code>[A-Z]+\d+)\s+(?P<msg>.+)$")),
        ("go", "build", re.compile(r"^(?P<file>[^:]+\.go):(?P<line>\d+):(?P<col>\d+):\s+(?P<msg>.+)$")),
        ("rust", "build", re.compile(r"^error(?:\[(?P<code>E\d+)\])?:\s+(?P<msg>.+)$")),
        ("rust", "lint", re.compile(r"^warning:\\s+(?P<msg>.+)$")),
        ("java", "build", re.compile(r"^(?P<file>[^:]+\.java):(?P<line>\d+):\s+error:\s+(?P<msg>.+)$")),
        ("java", "build", re.compile(r"^\[ERROR\]\s+(?P<file>[^:]+\.java):\[(?P<line>\d+),(?P<col>\d+)\]\s+(?P<msg>.+)$")),
        ("dotnet", "build", re.compile(r"^(?P<file>[^(:]+)\((?P<line>\d+),(?P<col>\d+)\):\s+error\s+(?P<code>CS\d+):\s+(?P<msg>.+)$")),
        ("c_cpp", "build", re.compile(r"^(?P<file>[^:]+\.(?:c|cc|cpp|cxx|h|hpp)):(?P<line>\d+):(?P<col>\d+):\s+error:\s+(?P<msg>.+)$")),
        ("eslint", "lint", re.compile(r"^(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+):\s+(?P<msg>.+?)\s+(?P<code>[A-Za-z0-9@/_-]+)$")),
        ("jest", "test", re.compile(r"^FAIL\\s+(?P<file>.+)$")),
        ("vitest", "test", re.compile(r"^\\s*❯\\s+(?P<file>[^:]+):(?P<line>\\d+):(?P<col>\\d+)\\s*$")),
        ("javascript", "build", re.compile(r"^npm ERR!\\s+(?P<code>[A-Z0-9_-]+)?\\s*(?P<msg>.+)$")),
        ("ruby", "runtime", re.compile(r"^(?P<file>[^:]+\.rb):(?P<line>\d+):(?:in `[^`]+':\s*)?(?P<msg>.+)$")),
        ("php", "runtime", re.compile(r"^(?:PHP\s+)?(?:Fatal error|Parse error|Warning):\s+(?P<msg>.+?)\s+in\s+(?P<file>[^\s]+\.php)\s+on\s+line\s+(?P<line>\d+)")),
        ("python", "runtime", re.compile(r'^File "(?P<file>[^"]+\.py)", line (?P<line>\d+), in .+$')),
    ]
    for index, line in enumerate(lines):
        for toolchain, default_phase, pattern in patterns:
            match = pattern.search(line)
            if not match:
                continue
            data = match.groupdict()
            msg = data.get("msg") or line
            severity = "warning" if line.lower().startswith("warning:") else "error"
            events.append(
                _event(
                    toolchain=toolchain,
                    phase=default_phase if phase == "runtime" else phase,
                    message=msg,
                    severity=severity,
                    code=data.get("code") or "",
                    file=data.get("file") or "",
                    line=data.get("line") or "",
                    command=command,
                    exit_code=exit_code,
                )
            )
            matched_lines.add(index)
            break

    command_toolchain = _toolchain_from_command(command)
    for index, line in enumerate(lines):
        if index in matched_lines:
            continue
        lower = line.lower()
        if any(token in lower for token in ["assertionerror", "traceback", "exception", "failed", "failure", "error:", "fatal error", "panic:"]):
            toolchain = command_toolchain
            if toolchain == "unknown" and ("traceback" in lower or "assertionerror" in lower):
                toolchain = "python"
            events.append(_event(toolchain=toolchain, phase=phase, message=line, command=command, exit_code=exit_code))

    if exit_code != 0 and not events:
        fallback = lines[-1] if lines else f"Command failed with exit code {exit_code}"
        events.append(_event(toolchain=_toolchain_from_command(command), phase=phase, message=fallback, command=command, exit_code=exit_code))
    return normalize_error_events(events)


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
        if field == "error_events":
            explicit_events = normalize_error_events(payload.get(field))
            runtime_events = normalize_error_events(observed.get(field))
            if explicit_events:
                capture[field] = explicit_events
                capture["provenance"][field] = "explicit"
            elif runtime_events:
                capture[field] = runtime_events
                capture["provenance"][field] = "runtime_observed"
            else:
                capture[field] = []
                capture["provenance"][field] = "unknown"
            continue
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
    if not capture["notable_errors"] and capture.get("error_events"):
        derived = notable_errors_from_events(capture["error_events"])
        if derived:
            capture["notable_errors"] = derived
            capture["provenance"]["notable_errors"] = "derived_from_error_events"
    return capture
