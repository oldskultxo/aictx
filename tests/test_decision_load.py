from __future__ import annotations

import json
from pathlib import Path

from aictx.continuity import DECISIONS_PATH, load_continuity_context
from aictx.middleware import prepare_execution
from aictx.scaffold import init_repo_scaffold


def _payload(repo: Path, execution_id: str = "exec-decision-load") -> dict:
    return {
        "repo_root": str(repo),
        "user_request": "resume continuity reasoning",
        "agent_id": "codex",
        "adapter_id": "codex",
        "execution_id": execution_id,
        "timestamp": "2026-04-24T13:00:00Z",
        "files_opened": ["src/aictx/continuity.py"],
    }


def test_load_continuity_context_loads_last_five_decisions(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    decisions_path = repo / DECISIONS_PATH
    decisions_path.parent.mkdir(parents=True, exist_ok=True)
    for index in range(7):
        with decisions_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"decision": f"decision {index}", "timestamp": f"2026-04-24T13:0{index}:00Z"}) + "\n")

    context = load_continuity_context(repo, task_type="testing", request_text="resume continuity reasoning")

    assert [row["decision"] for row in context["decisions"]] == [
        "decision 2",
        "decision 3",
        "decision 4",
        "decision 5",
        "decision 6",
    ]
    assert context["loaded"]["decisions"] is True


def test_prepare_execution_reports_no_decisions_when_file_missing(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    prepared = prepare_execution(_payload(repo, "exec-no-decisions"))

    assert prepared["continuity_context"]["decisions"] == []
    assert prepared["continuity_context"]["loaded"]["decisions"] is False
    assert "- decisions: no" in prepared["continuity_summary_text"]


def test_prepare_execution_ignores_invalid_decision_lines_without_crash(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    decisions_path = repo / DECISIONS_PATH
    decisions_path.parent.mkdir(parents=True, exist_ok=True)
    decisions_path.write_text('{"decision": "valid"}\nnot-json\n[]\n', encoding="utf-8")

    prepared = prepare_execution(_payload(repo, "exec-bad-decisions"))

    context = prepared["continuity_context"]
    assert context["decisions"] == [{"decision": "valid"}]
    assert context["loaded"]["decisions"] is True
    assert "invalid_jsonl_lines:.aictx/continuity/decisions.jsonl:2" in context["warnings"]
    assert "- decisions: sí" in prepared["continuity_summary_text"]
