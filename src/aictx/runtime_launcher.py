from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .middleware import finalize_execution, prepare_execution
from .runtime_capture import changed_files_between, command_text, git_status_files, infer_tests_from_commands, notable_errors_from_output


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_execution_id(raw: str | None, agent_id: str) -> str:
    value = str(raw or "").strip()
    if value and value != "auto":
        return value
    normalized_agent = "".join(ch if ch.isalnum() else "-" for ch in (agent_id or "agent")).strip("-") or "agent"
    return f"exec-{normalized_agent}-{now_stamp()}"


def normalize_command(command: list[str]) -> list[str]:
    normalized = list(command)
    if normalized and normalized[0] == "--":
        normalized = normalized[1:]
    return normalized


def summarize_command_result(command: list[str], exit_code: int, stdout: str, stderr: str) -> str:
    command_text = " ".join(command).strip()
    if exit_code == 0:
        if stdout.strip():
            return stdout.strip().splitlines()[-1][:240]
        return f"Command succeeded: {command_text}"[:240]
    if stderr.strip():
        return stderr.strip().splitlines()[-1][:240]
    if stdout.strip():
        return stdout.strip().splitlines()[-1][:240]
    return f"Command failed with exit code {exit_code}: {command_text}"[:240]


def run_execution(payload: dict[str, Any], command: list[str], validated_learning: bool = False) -> dict[str, Any]:
    normalized_command = normalize_command(command)
    if not normalized_command:
        raise ValueError("command is required after --")
    prepared = prepare_execution(payload)
    repo_root = Path(prepared["envelope"]["repo_root"]).resolve()
    before_status = git_status_files(repo_root)
    try:
        completed = subprocess.run(
            normalized_command,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        exit_code = int(completed.returncode)
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
    except FileNotFoundError as exc:
        exit_code = 127
        stdout = ""
        stderr = str(exc)
    result = {
        "success": exit_code == 0,
        "result_summary": summarize_command_result(normalized_command, exit_code, stdout, stderr),
        "validated_learning": bool(validated_learning and exit_code == 0),
    }
    after_status = git_status_files(repo_root)
    observation = prepared.get("execution_observation", {}) if isinstance(prepared.get("execution_observation"), dict) else {}
    observed_command = command_text(normalized_command)
    observation["commands_executed"] = [observed_command] if observed_command else []
    observation["tests_executed"] = infer_tests_from_commands(observation["commands_executed"])
    observation["notable_errors"] = notable_errors_from_output(exit_code, stdout, stderr)
    edited = changed_files_between(before_status, after_status)
    if edited:
        observation["files_edited"] = edited
    provenance = dict(observation.get("capture_provenance", {})) if isinstance(observation.get("capture_provenance"), dict) else {}
    provenance["commands_executed"] = "runtime_observed"
    provenance["tests_executed"] = "heuristic" if observation["tests_executed"] else "unknown"
    provenance["notable_errors"] = "runtime_observed" if observation["notable_errors"] else "unknown"
    provenance["files_edited"] = "runtime_observed" if edited else provenance.get("files_edited", "unknown")
    observation["capture_provenance"] = provenance
    prepared["execution_observation"] = observation
    finalized = finalize_execution(prepared, result)
    return {
        "execution_id": prepared["envelope"]["execution_id"],
        "command": normalized_command,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "prepared": prepared,
        "finalized": finalized,
    }


def cli_run_execution(args: argparse.Namespace) -> int:
    payload = {
        "repo_root": args.repo,
        "user_request": args.request,
        "agent_id": args.agent_id,
        "adapter_id": args.adapter_id or args.agent_id,
        "execution_id": build_execution_id(args.execution_id, args.agent_id),
        "declared_task_type": args.task_type,
        "execution_mode": args.execution_mode or "plain",
        "files_opened": list(args.files_opened or []),
        "files_edited": list(args.files_edited or []),
        "files_reopened": list(args.files_reopened or []),
        "commands_executed": list(args.commands_executed or []),
        "tests_executed": list(args.tests_executed or []),
        "notable_errors": list(args.notable_errors or []),
        "skill_metadata": {
            "skill_id": args.skill_id,
            "skill_name": args.skill_name,
            "skill_path": args.skill_path,
            "source": args.skill_source,
        },
    }
    outcome = run_execution(payload, args.command, validated_learning=bool(args.validated_learning))
    if args.json:
        print(json.dumps(outcome, indent=2, ensure_ascii=False))
    else:
        if outcome["stdout"]:
            sys.stdout.write(outcome["stdout"])
        if outcome["stderr"]:
            sys.stderr.write(outcome["stderr"])
        finalized = outcome.get("finalized", {}) if isinstance(outcome.get("finalized"), dict) else {}
        summary = str(finalized.get("agent_summary_text") or "").strip()
        if summary:
            if outcome["stdout"] and not outcome["stdout"].endswith("\n"):
                sys.stdout.write("\n")
            sys.stdout.write(summary + "\n")
    return int(outcome["exit_code"])
