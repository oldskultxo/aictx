from __future__ import annotations

import json
from pathlib import Path

from aictx.continuity import DECISIONS_PATH
from aictx.middleware import finalize_execution, prepare_execution
from aictx.scaffold import init_repo_scaffold
from aictx.state import read_jsonl


def _payload(repo: Path, execution_id: str) -> dict:
    return {
        "repo_root": str(repo),
        "user_request": "record architecture decision",
        "agent_id": "codex",
        "adapter_id": "codex",
        "execution_id": execution_id,
        "timestamp": "2026-04-24T12:30:00Z",
    }


def test_finalize_appends_valid_decision_memory(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    prepared = prepare_execution({**_payload(repo, "exec-decision-1"), "files_edited": ["src/aictx/continuity.py"]})

    finalized = finalize_execution(
        prepared,
        {
            "success": True,
            "result_summary": "Recorded decision persistence.",
            "validated_learning": False,
            "decisions": [
                {
                    "decision": "Use decisions.jsonl for continuity decisions.",
                    "rationale": "Append-only JSONL preserves a compact inspectable decision history.",
                    "alternatives": ["single decisions.json", "handoff-only decisions"],
                    "constraints": ["repo-local", "inspectable"],
                    "risks": ["future noise if trivial edits are recorded"],
                    "related_paths": [".aictx/continuity/decisions.jsonl"],
                    "subsystem": "continuity_runtime",
                }
            ],
        },
    )

    rows = read_jsonl(repo / DECISIONS_PATH)
    assert len(rows) == 1
    decision = rows[0]
    assert finalized["decisions_persisted"] == rows
    assert decision["decision"] == "Use decisions.jsonl for continuity decisions."
    assert decision["rationale"] == "Append-only JSONL preserves a compact inspectable decision history."
    assert decision["alternatives"] == ["single decisions.json", "handoff-only decisions"]
    assert decision["constraints"] == ["repo-local", "inspectable"]
    assert decision["risks"] == ["future noise if trivial edits are recorded"]
    assert decision["related_paths"] == [".aictx/continuity/decisions.jsonl"]
    assert decision["subsystem"] == "continuity_runtime"
    assert decision["timestamp"] == finalized["finalized_at"]
    assert decision["session"] == 1
    assert decision["execution_id"] == "exec-decision-1"


def test_multiple_decisions_are_valid_jsonl(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    prepared = prepare_execution(_payload(repo, "exec-decision-2"))

    finalize_execution(
        prepared,
        {
            "success": True,
            "result_summary": "",
            "validated_learning": False,
            "decisions": [
                {"decision": "Keep latest handoff canonical.", "rationale": "Startup should load one compact bridge."},
                {"decision": "Use JSONL for decisions.", "constraints": ["append-only", "human-readable"]},
            ],
        },
    )

    path = repo / DECISIONS_PATH
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    parsed = [json.loads(line) for line in lines]
    assert [row["decision"] for row in parsed] == ["Keep latest handoff canonical.", "Use JSONL for decisions."]
    assert read_jsonl(path) == parsed


def test_trivial_finalize_does_not_generate_decision_noise(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    prepared = prepare_execution(_payload(repo, "exec-trivial"))

    finalized = finalize_execution(
        prepared,
        {"success": True, "result_summary": "", "validated_learning": False},
    )

    assert finalized["decisions_persisted"] == []
    assert not (repo / DECISIONS_PATH).exists()


def test_insignificant_decision_payload_is_suppressed(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    prepared = prepare_execution(_payload(repo, "exec-insignificant"))

    finalized = finalize_execution(
        prepared,
        {
            "success": True,
            "result_summary": "",
            "validated_learning": False,
            "decisions": [{"decision": "Rename local variable."}],
        },
    )

    assert finalized["decisions_persisted"] == []
    assert not (repo / DECISIONS_PATH).exists()
