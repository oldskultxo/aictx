from __future__ import annotations

from pathlib import Path

from aictx.middleware import finalize_execution, prepare_execution
from aictx.scaffold import init_repo_scaffold


def _payload(repo: Path, execution_id: str) -> dict:
    return {
        "repo_root": str(repo),
        "user_request": "summarize continuity outcome",
        "agent_id": "codex",
        "adapter_id": "codex",
        "execution_id": execution_id,
        "timestamp": "2026-04-24T14:30:00Z",
        "files_opened": ["src/aictx/middleware.py"],
    }


def test_final_summary_with_reuse_reports_continuity_and_stored_artifacts(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    prepared = prepare_execution({**_payload(repo, "exec-summary-reuse"), "files_edited": ["src/aictx/middleware.py"]})
    prepared["execution_hint"] = {
        "selection_reason": "previous_successful_execution",
        "entry_points": ["src/aictx/middleware.py"],
    }
    prepared["continuity_context"]["loaded"]["handoff"] = True
    prepared["continuity_context"]["loaded"]["decisions"] = True

    finalized = finalize_execution(
        prepared,
        {
            "success": True,
            "result_summary": "Updated continuity final summary.",
            "validated_learning": False,
            "decisions": [
                {
                    "decision": "Use continuity-first final summaries.",
                    "rationale": "Agents need compact evidence of reused and stored continuity.",
                }
            ],
        },
    )

    text = finalized["agent_summary_text"]
    assert text.startswith(
        "AICTX: we closed this run with useful continuity context: we reused a previously successful strategy; "
        "we stored handoff, decision; we observed 1 file."
    )
    assert "0 tests" not in text
    assert "Details: [`.aictx/continuity/last_execution_summary.md`](.aictx/continuity/last_execution_summary.md)" in text
    assert finalized["agent_summary"]["handoff_stored"] is True
    assert finalized["agent_summary"]["decision_stored"] is True
    detailed_path = repo / ".aictx" / "continuity" / "last_execution_summary.md"
    assert detailed_path.exists()
    detailed = detailed_path.read_text(encoding="utf-8")
    assert "# AICTX Execution Summary" in detailed
    assert "- Reused strategy: yes" in detailed
    assert "- Handoff stored: yes" in detailed
    assert "- Files observed: 1" in detailed
    assert "Tests observed" not in detailed
    assert "Commands observed: 0" not in detailed
    assert "Reopened files: 0" not in detailed


def test_final_summary_without_reuse_is_honest_and_compatible(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    prepared = prepare_execution(_payload(repo, "exec-summary-no-reuse"))

    finalized = finalize_execution(
        prepared,
        {"success": True, "result_summary": "", "validated_learning": False},
    )

    text = finalized["agent_summary_text"]
    assert text == (
        "AICTX: this was a lightweight run and did not add new continuity context, but it was recorded for reference. "
        "Details: [`.aictx/continuity/last_execution_summary.md`](.aictx/continuity/last_execution_summary.md)"
    )
